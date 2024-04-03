"""Create a memgraph database from a list of DOIs

1. Check the DOIs are valid
2. Query to OpenAire Graph API and retrieve the output and author metadata for each of the DOIs
4. For each output, check if the output exists using DOI, title to avoid duplication
    - If not exist: create the output node
    - For each author, if the author exists already using ORCID, lastname and firstname to deduplicate
    - If not exist: create the author node
    - Create the author_of relation between author and output
"""

from re import compile, sub, IGNORECASE
import requests
from typing import List, Dict
from logging import getLogger, basicConfig, DEBUG
from os import environ
from gqlalchemy import Memgraph, Node, Relationship, match
from typing import Optional
from gqlalchemy.query_builders.memgraph_query_builder import Operator
from uuid import uuid4
from collections import defaultdict
from dataclasses import dataclass, asdict
from json import dump
from sys import argv

from . parser import parse_metadata
from . models import Article, ArticleMetadata, Author, author_of


logger = getLogger(__name__)
basicConfig(filename='example.log', filemode='w', encoding='utf-8', level=DEBUG)

TOKEN = environ.get('TOKEN')

# Use regex pattern from https://www.crossref.org/blog/dois-and-matching-regular-expressions/
PATTERN = compile("10.\d{4,9}\/[-._;()\/:A-Z0-9]+", IGNORECASE)


def validate_dois(list_of_dois: List) -> Dict[str, List]:
    """Validate DOIs
    """

    dois = defaultdict(list)
    # Iterate over the list of possible DOIs and return valid, otherwise raise a warning
    for doi in list_of_dois:
        match = PATTERN.search(doi)
        if match:
            # logger.info(f"{match.group()} is a valid DOI.")
            dois['valid'].append(match.group())
        else:
            logger.warn(f"{doi} is not a DOI.")
            dois['invalid'].append(doi)

    return dois


def get_personal_token():
    """
    GET https://services.openaire.eu/uoa-user-management/api/users/getAccessToken?refreshToken={your_refresh_token}
    """
    refresh_token = environ.get('REFRESH_TOKEN', None)
    global TOKEN

    if refresh_token:
        logger.info(f"Found refresh token. Obtaining personal token.")
        query = f"?refreshToken={refresh_token}"
        api_url = "https://services.openaire.eu/uoa-user-management/api/users/getAccessToken"
        response = requests.get(api_url + query)
        logger.info(f"Status code: {response.status_code}")
        logger.debug(response.json())
        if response.status_code == 200:
            TOKEN = response.json()['access_token']
        else:
            TOKEN = environ.get('TOKEN', None)
    else:
        TOKEN = environ.get('TOKEN', None)


def get_output_metadata(doi: str):
    """Request metadata from OpenAire Graph
    """
    query = f"?format=json&doi={doi}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    api_url = "https://api.openaire.eu/search/researchProducts"
    response = requests.get(api_url + query, headers=headers)

    logger.debug(f"Response code: {response.status_code}")
    response.raise_for_status()

    error = response.json().get('error')
    if error:
        raise ValueError(error)

    clean_doi = doi.replace("/", "")
    with open(f'data/json/{clean_doi}.json', 'w') as json_file:
        dump(response.json(), json_file)

    if response.json()['response']['results']:
        return response.json()
    else:
        raise ValueError(f"DOI {doi} returned no results")

def match_author_name(author:Dict) -> List:
    name = f"{author['first_name'][0]} {author['last_name']}"
    results = list(
                match()
                .node(labels="Author", variable="a")
                .where(item="left(a.first_name, 1) + ' ' + a.last_name",
                        operator=Operator.EQUAL, literal=name)
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
    if author['orcid']:
        # Match the ORCID (preferred)
        results = list(
                    match()
                    .node(labels="Author", variable="a")
                    .where(item="a.orcid", operator=Operator.EQUAL,
                           literal=f"https://orcid.org/{author['orcid']}")
                    .return_([("a.uuid", 'uuid'), ("a.last_name", "last_name")])
                    .execute()
        )

    # Check that the ORCID name actually matches the author name (is the ORCID correct?)
    if results:
        error_message = f"Result from ORCID {author['orcid']} does not match name of author"
        if not results[0]['last_name'] == author['last_name']:
            logger.warning(error_message)
            results = match_author_name(author)
    else:
        # Try a match on full name, or create new node
        results = match_author_name(author)

    if results:
        logger.info(f"Author {author['first_name']} {author['last_name']} exists")
        author_node = Author(uuid=results[0]['uuid']).load(graph)
    else:
        # Create author node
        author['uuid'] = str(uuid4())
        if author['orcid']:
            author['orcid'] = f"https://orcid.org/{author['orcid']}"
        else:
            author.pop('orcid')
        author_object = Author(**author)

        author_node = author_object.save(graph)

    return author_node


def upload_article_to_memgraph(output: ArticleMetadata,
                               graph: Memgraph) -> bool:
    """

    Arguments:
    ----------
    output: Node
        A gqlalchemy Node representing an output
    graph: Memgraph
        Connection to a Memgraph instance
    """

    author_nodes: List[Author] = []

    # Check output exists, otherwise create
    results = list(
                    match()
                    .node(labels="Article", variable="a")
                    .where(item="a.doi", operator=Operator.EQUAL,
                           literal=output.doi)
                    .return_([("a.doi", 'doi')])
                    .execute()
                    )
    if results:

        article_node = Article(doi=results[0]['doi']).load(graph)

    else:
        # Create article node

        article_dict = asdict(output)
        author_list: List[Dict] = article_dict.pop('authors')

        article_dict['uuid'] = str(uuid4())

        # Create Article object
        article = Article(**article_dict)
        article_node = article.save(graph)

        # Check authors exists, otherwise create
        for author in author_list:
            author_node = check_upload_author(author, graph)
            author_nodes.append(author_node)

            # Create relations between output and authors
            author_of(_start_node_id=author_node._id,
                      _end_node_id=article_node._id,
                      rank=author['rank']
                      ).save(graph)

    return True


def main(list_of_dois, graph):
    """
    """

    dois = validate_dois(list_of_dois)
    valid_dois = dois['valid']

    get_personal_token()

    for valid_doi in valid_dois:
        try:
            metadata = get_output_metadata(valid_doi)
        except ValueError as ex:
            logger.error(f"No metadata found for doi {valid_doi}. Message: {ex}")
        else:
            output: ArticleMetadata = parse_metadata(metadata, valid_doi)
            result = upload_article_to_memgraph(output, graph)
            if result:
                logger.info("Upload successful")
            else:
                logger.info("Upload failed")

    return True


def entry_point():

    if len(argv[1:]) == 1:
        file_path = argv[1]
    else:
        raise ValueError("No file path provided to the list of dois.")

    list_of_dois = []
    with open(file_path, 'r') as csv_file:
        for line in csv_file:
            list_of_dois.append(line.strip())

    MG_HOST = environ.get("MG_HOST", "127.0.0.1")
    MG_PORT = int(environ.get("MG_PORT", 7687))

    logger.info(f"Connecting to Memgraph at {MG_HOST}:{MG_PORT}")
    graph = Memgraph(host=MG_HOST, port=MG_PORT)
    graph.drop_database()

    result = main(list_of_dois, graph)

    return result


if __name__ == "__main__":

    # Read in a list of DOIs from a csv file
    file_path = 'list_of_doi.csv'

    list_of_dois = []
    with open(file_path, 'r') as csv_file:
        for line in csv_file:
            list_of_dois.append(line.strip())

    MG_HOST = environ.get("MG_HOST", "127.0.0.1")
    MG_PORT = int(environ.get("MG_PORT", 7687))

    logger.info(f"Connecting to Memgraph at {MG_HOST}:{MG_PORT}")
    graph = Memgraph(host=MG_HOST, port=MG_PORT)
    graph.drop_database()

    result = main(list_of_dois, graph)
