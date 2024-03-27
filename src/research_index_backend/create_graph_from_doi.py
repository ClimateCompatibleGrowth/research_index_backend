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
from html import unescape
from gqlalchemy import Memgraph, Node, Relationship, match
from typing import Optional
from gqlalchemy.query_builders.memgraph_query_builder import Operator
from uuid import uuid4
from collections import defaultdict
from dataclasses import dataclass, asdict
from json import dump
from unicodedata import normalize


logger = getLogger(__name__)
basicConfig(filename='example.log', filemode='w', encoding='utf-8', level=DEBUG)

TOKEN = environ.get('TOKEN')

# Use regex pattern from https://www.crossref.org/blog/dois-and-matching-regular-expressions/
PATTERN = compile("10.\d{4,9}\/[-._;()\/:A-Z0-9]+", IGNORECASE)
CLEANR = compile('<.*?>')


@dataclass
class AuthorMetadata():
    orcid: Optional[str]
    last_name: str
    first_name: str
    rank: int


@dataclass
class ArticleMetadata():
    doi: Optional[str]
    title: Optional[str]
    abstract: Optional[str]
    authors: List[AuthorMetadata]
    journal: Optional[str]
    issue: Optional[int]
    volume: Optional[int]
    publication_year: Optional[int]
    publication_month: Optional[int]
    publication_day: Optional[int]
    publisher: Optional[str]


class Author(Node):
    uuid: str
    first_name: Optional[str]
    last_name: Optional[str]
    orcid: Optional[str]


class Output(Node):
    uuid: str


class Article(Output):
    uuid: Optional[str]
    doi: Optional[str]
    title: Optional[str]
    abstract: Optional[str]
    journal: Optional[str]
    issue: Optional[int]
    volume: Optional[int]
    publication_year: Optional[int]
    publication_month: Optional[int]
    publication_day: Optional[int]
    publisher: Optional[str]


class author_of(Relationship):
    rank: int


def clean_html(raw_html):
    """Remove HTML markup from a string and normalize UTF8
    """
    cleantext = sub(CLEANR, '', raw_html)
    return unescape(normalize('NFKC', cleantext))


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


def get_output_metadata(doi: str):
    """Request metadata from OpenAire Graph
    """
    query = f"?format=json&doi={doi}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    api_url = "https://api.openaire.eu/search/researchProducts"
    response = requests.get(api_url + query, headers=headers)

    # Raise warning of DOI did not return a response
    if response.status_code > 200:
        logger.warning("DOI {doi} did not return a response")

    error = response.json().get('error')
    if error:
        raise ValueError(error)

    clean_doi = doi.replace("/", "")
    with open(f'data/json/{clean_doi}.json', 'w') as json_file:
        dump(response.json(), json_file)
    return response.json()


def parse_metadata(metadata: str, valid_doi: str) -> ArticleMetadata:
    """Parses the response from the OpenAire Graph API

    Notes
    -----
    For now, this assumes all outputs are journal papers
    """
    logger.info(metadata.keys())
    for result in metadata['response']['results']['result']:

        entity = result['metadata']['oaf:entity']['oaf:result']

        title_meta = entity['title']
        if isinstance(title_meta, list):
            count = 0
            for x in title_meta:
                count += 1
                print(f"{count}: {x}")
                if x['@classid'] == 'main title':
                    title = (x['$'])
                    break
                else:
                    pass
        else:
            title = title_meta['$']

        authors = entity.get('creator', None)

        publisher = entity.get('publisher', None)
        if publisher:
            publisher = publisher['$']
        else:
            publisher = None

        journal = entity.get('journal', None)
        if journal:
            journal = journal['$']
        else:
            journal = None

        abstract = entity.get('description', None)
        if abstract:
            if isinstance(abstract, list):
                abstract = abstract[0]
            if '$' in abstract.keys():
                abstract = clean_html(abstract['$'])

        try:
            all_authors: List[Author] = []
            if isinstance(authors, list):
                for x in authors:
                    orcid = x.get('@orcid', None)
                    if not orcid:
                        orcid = x.get('@orcid_pending', None)
                    first_name = x.get('@name', "")
                    last_name = x.get('@surname', "")
                    if not first_name and not last_name:
                        name = x.get('$').split()
                        first_name = name[0]
                        last_name = name[1]
                    rank = x.get('@rank', 1)
                    logger.info(f"Creating author metadata: {first_name} {last_name} {orcid} {rank}")
                    author = AuthorMetadata(orcid, last_name, first_name, rank)
                    all_authors.append(author)
            else:
                orcid = authors.get('@orcid', None)
                if not orcid:
                    orcid = authors.get('@orcid_pending', None)
                first_name = authors.get('@name', "")
                last_name = authors.get('@surname', "")
                rank = authors.get('@rank', 0)
                logger.info(f"Creating author metadata: {first_name} {last_name} {orcid} {rank}")
                author = AuthorMetadata(orcid, last_name, first_name, rank)
                all_authors.append(author)

        except TypeError as ex:
            print(authors['$'])
            raise TypeError(ex)

        doi = valid_doi
        issue = None
        volume = None
        publication_year = None
        publication_month = None
        publication_day = None

        return ArticleMetadata(doi, title, abstract,
                               all_authors, journal, issue, volume,
                               publication_year, publication_month,
                               publication_day, publisher)


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
    if author['orcid']:
        # Match the ORCID (preferred)
        orcid_url = f"https://orcid.org/{author['orcid']}"
        results = list(
                    match()
                    .node(labels="Author", variable="a")
                    .where(item="a.orcid", operator=Operator.EQUAL,
                           literal=orcid_url)
                    .return_([("a.uuid", 'uuid')])
                    .execute()
                    )
    else:
        # Try a match on full name, or create new node
        name = f"{author['first_name']} {author['last_name']}"
        results = list(
                    match()
                    .node(labels="Author", variable="a")
                    .where(item="a.first_name + ' ' + a.last_name",
                           operator=Operator.EQUAL, literal=name)
                    .return_(results=[("a.uuid", "uuid")])
                    .execute()
                    )

    if results:
        logger.info("Author {} {} exists")
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

        print(article_dict.items())

        # Create Article object
        article = Article(**article_dict)

        try:
            article_node = article.save(graph)
        except:
            logger.debug(article)
            raise

        # Check authors exists, otherwise create
        for author in author_list:
            print(author)
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

    for valid_doi in valid_dois:
        metadata = get_output_metadata(valid_doi)
        output: ArticleMetadata = parse_metadata(metadata, valid_doi)
        result = upload_article_to_memgraph(output, graph)
        if result:
            logger.info("Upload successful")
        else:
            logger.info("Upload failed")

    return True


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
