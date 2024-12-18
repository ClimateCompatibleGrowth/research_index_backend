"""Create a memgraph database from a list of DOIs

1. Check the DOIs are valid
2. Query to OpenAire Graph API and retrieve the output and author metadata for
   each of the DOIs
4. For each output, check if the output exists using DOI, title to avoid
   duplication
    - If not exist: create the output node
    - For each author, if the author exists already using ORCID, lastname
      and firstname to deduplicate
    - If not exist: create the author node
    - Create the author_of relation between author and output
"""

import argparse
from collections import defaultdict
from dataclasses import asdict
from difflib import SequenceMatcher
from logging import DEBUG, basicConfig, getLogger
from os import environ
from os.path import join
from re import IGNORECASE, compile
from typing import Dict, List
from uuid import uuid4

import requests
import requests_cache
from gqlalchemy import Memgraph, match
from gqlalchemy.query_builders.memgraph_query_builder import Operator
from mgclient import DatabaseError
from tqdm import tqdm

from .create_graph import load_initial_data
from .get_metadata import (
    get_metadata_from_openaire,
    get_metadata_from_openalex,
)
from .models import Article, ArticleMetadata, Author, author_of
from .parser import parse_metadata
from .config import config

TOKEN = config.token

MG_HOST = config.mg_host
MG_PORT = config.mg_port

ORCID_NAME_SIMILARITY_THRESHOLD = config.orcid_name_similarity_threshold
NAME_SIMILARITY_THRESHOLD = config.name_similarity_threshold

OPENAIRE_API = "https://api.openaire.eu"
OPENAIRE_SERVICE = "https://services.openaire.eu"

logger = getLogger(__name__)
basicConfig(
    filename="research_index_backend.log",
    filemode="w",
    encoding="utf-8",
    level=DEBUG,
)


# Use regex pattern from
# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
PATTERN = compile("10\\.\\d{4,9}/[-._;()/:A-Z0-9]+$", IGNORECASE)


def validate_dois(list_of_dois: List) -> Dict[str, List]:
    """Validate DOIs"""

    dois = defaultdict(list)
    # Iterate over the list of possible DOIs and return valid, otherwise raise
    # a warning
    for doi in list_of_dois:
        if not doi == "":
            search = PATTERN.search(doi)
            if search:
                logger.info(f"{search.group()} is a valid DOI.")
                dois["valid"].append(search.group())
            else:
                logger.warning(f"{doi} is not a DOI.")
                dois["invalid"].append(doi)

    return dois


def get_output_metadata(
    session: requests_cache.CachedSession, doi: str, source: str = "OpenAire"
) -> Dict:
    """Request metadata from OpenAire Graph

    Arguments
    ---------
    session: CachedSession
    doi: str
    source: str, default='OpenAire'
        The API to connect to
    """
    if source == "OpenAire":
        return get_metadata_from_openaire(session, doi, TOKEN)
    elif source == "OpenAlex":
        return get_metadata_from_openalex(session, doi)
    else:
        raise ValueError("Incorrect argument for output metadata source")


def match_author_name(author: Dict) -> List:
    name = f"{author['first_name'][0]} {author['last_name']}"
    return list(
        match()
        .node(labels="Author", variable="a")
        .where(
            item="left(a.first_name, 1) + ' ' + a.last_name",
            operator=Operator.EQUAL,
            literal=name,
        )
        .return_(results=[("a.uuid", "uuid")])
        .execute()
    )


def score_name_similarity(name_results: str, name_author: str) -> float:
    """Scores the similarity of two names

    Arguments
    ---------
    name_results: str
        Name from the database
    name_author: str
        Name from the author
    """
    logger.debug(f"Comparing {name_results} with {name_author}")

    def clean(name: str) -> str:
        return name.strip().lower()

    name_results = clean(name_results)
    name_author = clean(name_author)

    def inverse(name: str) -> str:
        return " ".join(reversed(name.split(" ")))

    matcher = SequenceMatcher(None, a=name_results, b=name_author)
    ratio_a = matcher.ratio()
    if ratio_a > NAME_SIMILARITY_THRESHOLD:
        return ratio_a
    else:
        # Try reversing the name order
        matcher.set_seq1(inverse(name_results))
        ratio_b = matcher.ratio()

    if ratio_b > NAME_SIMILARITY_THRESHOLD:
        return ratio_b
    else:
        return (ratio_a + ratio_b) / 2.0


def check_upload_author(author: Dict, graph: Memgraph) -> Author:
    """Checks is an author exists, and creates if not

    A new author is created with a new uuid4 identifier

    Arguments
    ---------
    author: Author
        A node object representing an author
    graph: Memgraph
        Connection to a Memgraph instance
    """
    results = None

    orcid = author.get("orcid", None)
    if orcid:
        # Match the ORCID (preferred)
        results = list(
            match()
            .node(labels="Author", variable="a")
            .where(
                item="a.orcid",
                operator=Operator.EQUAL,
                literal=f"https://orcid.org/{author['orcid']}",
            )
            .return_(
                [
                    ("a.uuid", "uuid"),
                    ("a.first_name", "first_name"),
                    ("a.last_name", "last_name"),
                ]
            )
            .execute()
        )

    # Check that the ORCID name actually matches the author name
    # (is the ORCID correct?)
    if results:
        error_message = (
            f"Result from ORCID {author['orcid']} does not match author name: "
            + f"{author['first_name']} {author['last_name']}"
        )
        logger.debug(f"Results: {results}")
        name_results = results[0]["first_name"] + " " + results[0]["last_name"]
        name_author = author["first_name"] + " " + author["last_name"]
        score = score_name_similarity(name_results, name_author)
        if score < ORCID_NAME_SIMILARITY_THRESHOLD:
            logger.warning(error_message + f". Ratio: {score}")
            results = match_author_name(author)
    else:
        # Try a match on full name, or create new node
        results = match_author_name(author)

    if results:
        name = f"{author['first_name']} {author['last_name']}"
        logger.info(f"Author {name} exists")
        author_node = Author(uuid=results[0]["uuid"]).load(graph)
    else:
        # Create author node
        author["uuid"] = str(uuid4())
        if author["orcid"]:
            author["orcid"] = f"https://orcid.org/{author['orcid']}"
        else:
            author.pop("orcid")
        author_object = Author(**author)

        author_node = author_object.save(graph)
        logger.info(
            (
                f"Author {author['first_name']} {author['last_name']} "
                + "does not exist. Created new node."
            )
        )

    return author_node


def upload_article_to_memgraph(
    output: ArticleMetadata, graph: Memgraph
) -> bool:
    """

    Arguments:
    ----------
    output: Node
        A gqlalchemy Node representing an output
    graph: Memgraph
        Connection to a Memgraph instance
    """

    author_nodes: List[Author] = []

    article_dict = asdict(output)
    author_list: List[Dict] = article_dict.pop("authors")

    # Check output exists, otherwise create
    results = list(
        match()
        .node(labels="Article", variable="a")
        .where(item="a.doi", operator=Operator.EQUAL, literal=output.doi)
        .return_([("a.doi", "doi")])
        .execute()
    )
    if results:

        article_node = Article(doi=results[0]["doi"]).load(graph)
        logger.info(f"Output {output.doi} exists. Loaded from graph")

    else:
        # Create article node
        article_dict["uuid"] = str(uuid4())

        # Create Article object
        article = Article(**article_dict)
        article_node = article.save(graph)
        logger.info(f"Output {output.doi} did not exist. Created new node")

        # Check authors exists, otherwise create
        for author in author_list:
            author_node = check_upload_author(author, graph)
            author_nodes.append(author_node)

            # Create relations between output and authors
            author_of(
                _start_node_id=author_node._id,
                _end_node_id=article_node._id,
                rank=author["rank"],
            ).save(graph)

    return True


def main(list_of_dois, graph) -> bool:
    """ """

    dois = validate_dois(list_of_dois)
    valid_dois = dois["valid"]

    session = requests_cache.CachedSession("doi_cache", expire_after=30)

    for valid_doi in tqdm(valid_dois):
        try:
            openalex_metadata = get_output_metadata(
                session, valid_doi, "OpenAlex"
            )
        except ValueError as ex:
            logger.error(
                f"No OpenAlex metadata found for doi {valid_doi}: {ex}"
            )
            openalex_metadata = {"id": None}
        try:
            metadata = get_output_metadata(session, valid_doi, "OpenAire")
        except ValueError as ex:
            logger.error(
                f"No OpenAire metadata found for doi {valid_doi}: {ex}"
            )
        else:
            outputs_metadata = parse_metadata(
                metadata, valid_doi, openalex_metadata
            )
            for output in outputs_metadata:
                try:
                    result = upload_article_to_memgraph(output, graph)
                except DatabaseError as ex:
                    logger.error(f"Error uploading {output.doi} to Memgraph")
                    logger.error(f"{ex}")
                    logger.debug(output)
                    raise ex
                if result:
                    logger.info(f"Upload {valid_doi} successful")
                else:
                    logger.warning(f"Upload {valid_doi} failed")

    return True


def argument_parser():

    parser = argparse.ArgumentParser()
    help = "Provide the path to CSV file containing a list of dois"
    parser.add_argument("list_of_dois", help=help)
    help = "Deletes any existing data and creates a new database"
    parser.add_argument("--initialise", action="store_true", help=help)
    return parser.parse_args()


def add_country_relations(graph: Memgraph):
    """Runs a query to add links to countries

    Adds a link to a country if the abstract contains the name
    of the country
    """
    query = """
        MATCH (c:Country)
        CALL {
        WITH c
        MATCH (o:Output)
        WHERE o.abstract CONTAINS c.name
        AND NOT exists((o:Output)-[:REFERS_TO]->(c:Country))
        CREATE (o)-[r:REFERS_TO]->(c)
        RETURN r
        LIMIT 1
        }
        RETURN r
        """
    graph.execute(query)

    query = """
        MATCH (c:Country)
        CALL {
        WITH c
        MATCH (o:Output)
        WHERE o.title CONTAINS c.name
        AND NOT exists((o:Output)-[:REFERS_TO]->(c:Country))
        CREATE (o)-[r:REFERS_TO]->(c)
        RETURN r
        LIMIT 1
        }
        RETURN r
        """
    graph.execute(query)


def add_indexes(graph: Memgraph):
    queries = [
        "CREATE INDEX ON :Country(id);",
        "CREATE INDEX ON :Author(uuid);",
        "CREATE INDEX ON :Article(uuid);",
        "CREATE INDEX ON :Article(result_type);",
        # "CREATE EDGE INDEX ON :author_of(rank);",
        "ANALYZE GRAPH;",
    ]
    for query in queries:
        graph.execute(query)


def entry_point():
    """This is the console entry point to the programme"""

    args = argument_parser()
    list_of_dois = []
    with open(args.list_of_dois, "r") as csv_file:
        for line in csv_file:
            list_of_dois.append(line.strip())

    logger.info(f"Connecting to Memgraph at {MG_HOST}:{MG_PORT}")
    graph = Memgraph(host=MG_HOST, port=MG_PORT)

    if args.initialise:
        graph.drop_database()
        load_initial_data(graph, join("data", "init"))

    result = main(list_of_dois, graph)
    add_country_relations(graph)

    add_indexes(graph)

    if result:
        print("Success")


if __name__ == "__main__":

    if result := entry_point():
        print("Success")
