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
from difflib import SequenceMatcher
from logging import DEBUG, basicConfig, getLogger
from os.path import join
from re import IGNORECASE, compile
from typing import Dict, List
from uuid import uuid4

import requests_cache
from neo4j import Driver
from neo4j.exceptions import DatabaseError
from tqdm import tqdm

from .config import config
from .create_graph import load_initial_data
from .get_metadata import MetadataFetcher
from .models import AnonymousArticle, Article, Author
from .parser import parse_metadata
from .session import connect_to_db
from .doi import DOIManager

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

@connect_to_db
def match_author_name(db: Driver, author: Dict) -> List:
    name = f"{author['first_name'][0]} {author['last_name']}"

    query = """
            MATCH (a:Author)
            WHERE left(a.first_name, 1) + ' ' + a.last_name = $name
            RETURN a.uuid as uuid
            """

    results, summary, keys = db.execute_query(query, name=name)

    return results.data()


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


@connect_to_db
def check_upload_author(db: Driver, author: Dict) -> Author:
    """Checks is an author exists, and creates if not

    A new author is created with a new uuid4 identifier

    Arguments
    ---------
    db: neo4j.Driver
        A graph database connection
    author: Author
        A node object representing an author

    """
    results = None

    orcid = author.get("orcid", None)
    orcid_url = "https://orcid.org/{orcid}"
    if orcid:
        # Match the ORCID (preferred)

        query = """
                MATCH (a:Author)
                WHERE a.orcid = $orcid
                RETURN a.uuid as uuid,
                       a.first_name as first_name,
                       a.list_name as list_name
                """
        results, _, _ = db.execute_query(
            query, orcid=orcid_url
        )  # typing: tuple[neo4j.Result, Any, Any]

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
            logger.warning(f"{error_message}. Ratio: {score}")
            results = match_author_name(author)
    else:
        # Try a match on full name, or create new node
        results = match_author_name(author)

    if results:
        name = f"{author['first_name']} {author['last_name']}"
        logger.info(f"Author {name} exists")
        query = """MATCH (a:Author {uuid=$uuid} RETURN *)"""
        results, _, _ = db.execute_query(query, uuid=results[0]["uuid"])
    else:
        # Create author node
        author["uuid"] = str(uuid4())
        if author["orcid"]:
            author["orcid"] = f"https://orcid.org/{author['orcid']}"
        else:
            author.pop("orcid")
        author_object = Author(**author)

        author_node = author_object.save()
        logger.info(
            (
                f"Author {author['first_name']} {author['last_name']} "
                + "does not exist. Created new node."
            )
        )

    return author_node


def upload_article_to_memgraph(output: AnonymousArticle) -> bool:
    """

    Arguments:
    ----------
    output: Node
        A gqlalchemy Node representing an output
    db: neo4j.Driver
        Connection to a Memgraph instance
    """
    article_dict = output.model_dump()
    Article(uuid=uuid4(), **article_dict).save()

    return True


def main(list_of_dois: list,limit: int, update_metadata: bool):
    try: 
        doi_manager = DOIManager(list_of_dois, limit=limit, update_metadata=update_metadata)
        
        doi_manager.start_ingestion()
        doi_manager.validate_dois()
        if not doi_manager.update_metadata and not doi_manager.num_new_dois:
            logger.warning("No new DOIs to process or valid existing DOIs to update.")
            doi_manager.end_ingestion()
            return doi_manager
    except Exception as e:
        logger.error(f"Error validating DOIs: {e}")
        raise e
    

    session = requests_cache.CachedSession("doi_cache", expire_after=30)
    metadata_fetcher = MetadataFetcher(session)
    
    for doi in tqdm(doi_manager.doi_tracker):
        if doi_manager.doi_tracker[doi].already_exists and not doi_manager.update_metadata:
            logger.info(f"DOI {doi} already exists in the database.")
            continue        
        try:
            openalex_metadata = metadata_fetcher.get_output_metadata(
                doi, source="OpenAlex"
            )
            doi_manager.doi_tracker[doi].openalex_metadata = True
        except ValueError as ex:
            logger.error(
                f"No OpenAlex metadata found for doi {doi}: {ex}"
            )
            openalex_metadata = {"id": None}                
        try:
            metadata = metadata_fetcher.get_output_metadata(
                doi, source="OpenAire"
            )
            doi_manager.doi_tracker[doi].openaire_metadata = True
        except ValueError as ex:
            logger.error(
                f"No OpenAire metadata found for doi {doi}: {ex}"
            )
        else:
            outputs_metadata = parse_metadata(
                metadata, doi, openalex_metadata
            )
            for output in outputs_metadata:
                try:
                    result = upload_article_to_memgraph(output)
                    doi_manager.doi_tracker[doi].ingestion_success = True
                except DatabaseError as ex:
                    logger.error(f"Error uploading {output.doi} to Memgraph")
                    logger.error(f"{ex}")
                    logger.debug(output)
                    raise ex
                if result:
                    logger.info(f"Upload {doi} successful")
                else:
                    logger.warning(f"Upload {doi} failed")
    doi_manager.end_ingestion()
    return doi_manager


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Process DOIs and create/update a graph database"
    )
    parser.add_argument(
        "list_of_dois",
        help="Path to CSV file containing list of DOIs"
    )
    parser.add_argument(
        "-i", "--initialise",
        action="store_true",
        help="Delete existing data and create new database"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=50,
        help="Limit number of DOIs to process (default: 50)"
    )
    parser.add_argument(
        "-u", "--update-metadata",
        action="store_true",
        help="Update metadata for existing DOIs"
    )
    return parser.parse_args()


@connect_to_db
def add_country_relations(db: Driver):
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
        AND NOT exists((o:Output)-[:refers_to]->(c:Country))
        CREATE (o)-[r:refers_to]->(c)
        RETURN r
        LIMIT 1
        }
        RETURN r
        """
    db.execute_query(query)

    query = """
        MATCH (c:Country)
        CALL {
        WITH c
        MATCH (o:Output)
        WHERE o.title CONTAINS c.name
        AND NOT exists((o:Output)-[:refers_to]->(c:Country))
        CREATE (o)-[r:refers_to]->(c)
        RETURN r
        LIMIT 1
        }
        RETURN r
        """
    db.execute_query(query)


@connect_to_db
def entry_point(db: Driver):
    """This is the console entry point to the programme"""

    args = argument_parser()    
    list_of_dois = []
    with open(args.list_of_dois, "r") as csv_file:
        for line in csv_file:
            list_of_dois.append(line.strip())

    if args.initialise:
        query = """MATCH (node) DETACH DELETE node;"""
        _, _, _ = db.execute_query(query)
        logger.info("Deleted graph")
        load_initial_data(join("data", "init"))

    doi_manager = main(list_of_dois, limit=args.limit, update_metadata=args.update_metadata)
    add_country_relations()
    metrics, processed_dois = doi_manager.ingestion_metrics()
    logger.info(f"Report: {metrics}, {processed_dois}")
    print(f"Report: {metrics}")    
    return metrics, processed_dois

if __name__ == "__main__":
    entry_point()