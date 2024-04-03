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
from json import dump
from logging import DEBUG, basicConfig, getLogger
from os import environ
from os.path import join
from re import IGNORECASE, compile
from typing import Dict, List
from uuid import uuid4

import requests
from gqlalchemy import Memgraph, match
from gqlalchemy.query_builders.memgraph_query_builder import Operator
from tqdm import tqdm

from .create_graph import load_initial_data
from .models import Article, ArticleMetadata, Author, author_of
from .parser import parse_metadata

logger = getLogger(__name__)
basicConfig(
    filename="research_index_backend.log", filemode="w", encoding="utf-8", level=DEBUG
)

TOKEN = environ.get("TOKEN")

# Use regex pattern from
# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
PATTERN = compile("10.\d{4,9}\/[-._;()\/:A-Z0-9]+", IGNORECASE)


def validate_dois(list_of_dois: List) -> Dict[str, List]:
    """Validate DOIs"""

    dois = defaultdict(list)
    # Iterate over the list of possible DOIs and return valid, otherwise raise
    # a warning
    for doi in list_of_dois:
        match = PATTERN.search(doi)
        if match:
            # logger.info(f"{match.group()} is a valid DOI.")
            dois["valid"].append(match.group())
        else:
            logger.warn(f"{doi} is not a DOI.")
            dois["invalid"].append(doi)

    return dois


def get_personal_token():
    """Get personal token by providing a refresh token"""
    refresh_token = environ.get("REFRESH_TOKEN", None)
    global TOKEN

    if refresh_token:
        logger.info("Found refresh token. Obtaining personal token.")
        query = f"?refreshToken={refresh_token}"
        api_url = (
            "https://services.openaire.eu/uoa-user-management/api/users/getAccessToken"
        )
        response = requests.get(api_url + query)
        logger.info(f"Status code: {response.status_code}")
        logger.debug(response.json())
        if response.status_code == 200:
            TOKEN = response.json()["access_token"]
        else:
            TOKEN = environ.get("TOKEN", None)
    else:
        TOKEN = environ.get("TOKEN", None)


def get_output_metadata(doi: str) -> Dict:
    """Request metadata from OpenAire Graph"""
    query = f"?format=json&doi={doi}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    api_url = "https://api.openaire.eu/search/researchProducts"
    response = requests.get(api_url + query, headers=headers)

    logger.debug(f"Response code: {response.status_code}")
    response.raise_for_status()

    error = response.json().get("error")
    if error:
        raise ValueError(error)

    clean_doi = doi.replace("/", "")
    with open(f"data/json/{clean_doi}.json", "w") as json_file:
        dump(response.json(), json_file)

    if response.json()["response"]["results"]:
        return response.json()
    else:
        raise ValueError(f"DOI {doi} returned no results")


def match_author_name(author: Dict) -> List:
    name = f"{author['first_name'][0]} {author['last_name']}"
    results = list(
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
    return results


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
    if author["orcid"]:
        # Match the ORCID (preferred)
        results = list(
            match()
            .node(labels="Author", variable="a")
            .where(
                item="a.orcid",
                operator=Operator.EQUAL,
                literal=f"https://orcid.org/{author['orcid']}",
            )
            .return_([("a.uuid", "uuid"), ("a.last_name", "last_name")])
            .execute()
        )

    # Check that the ORCID name actually matches the author name (is the ORCID correct?)
    if results:
        error_message = (
            f"Result from ORCID {author['orcid']} does not match author name: "
            + f"{author['first_name']} {author['last_name']}"
        )
        if not results[0]["last_name"] == author["last_name"]:
            logger.warning(error_message)
            results = match_author_name(author)
    else:
        # Try a match on full name, or create new node
        results = match_author_name(author)

    if results:
        logger.info(f"Author {author['first_name']} {author['last_name']} exists")
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


def upload_article_to_memgraph(output: ArticleMetadata, graph: Memgraph) -> bool:
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

    get_personal_token()

    for valid_doi in tqdm(valid_dois):
        try:
            metadata = get_output_metadata(valid_doi)
        except ValueError as ex:
            logger.error(f"No metadata found for doi {valid_doi}. Message: {ex}")
        else:
            outputs_metadata = parse_metadata(metadata, valid_doi)
            for output in outputs_metadata:
                result = upload_article_to_memgraph(output, graph)
                if result:
                    logger.info("Upload successful")
                else:
                    logger.info("Upload failed")

    return True


def argument_parser():

    parser = argparse.ArgumentParser()
    help = "Provide the path to CSV file containing a list of dois"
    parser.add_argument("list_of_dois", help=help)
    help = "Deletes any existing data and creates a new database"
    parser.add_argument("--initialise", action="store_true", help=help)
    args = parser.parse_args()
    return args


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
        }
        RETURN r
        """
    graph.execute(query)


def entry_point():
    """This is the console entry point to the programme"""

    args = argument_parser()
    list_of_dois = []
    with open(args.list_of_dois, "r") as csv_file:
        for line in csv_file:
            list_of_dois.append(line.strip())

    MG_HOST = environ.get("MG_HOST", "127.0.0.1")
    MG_PORT = int(environ.get("MG_PORT", 7687))

    logger.info(f"Connecting to Memgraph at {MG_HOST}:{MG_PORT}")
    graph = Memgraph(host=MG_HOST, port=MG_PORT)

    if args.initialise:
        graph.drop_database()
        load_initial_data(graph, join("data", "init"))

    result = main(list_of_dois, graph)
    add_country_relations(graph)

    if result:
        print("Success")


if __name__ == "__main__":

    result = entry_point()
    if result:
        print("Success")
