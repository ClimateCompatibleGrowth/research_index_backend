from typing import List
from logging import getLogger
from datetime import datetime

from re import split


from .utils import clean_html
from .models import ArticleMetadata, AuthorMetadata

logger = getLogger(__name__)


def parse_author(metadata: str) -> AuthorMetadata:
    """Parses the JSON for an author

    Arguments
    ---------
    metadata
    """
    orcid = metadata.get('@orcid', None)
    if not orcid:
        orcid = metadata.get('@orcid_pending', None)

    first_name = metadata.get('@name', "")
    last_name = metadata.get('@surname', "")
    if not first_name and not last_name:
        name = metadata.get('$').split()
        if len(name) == 2:
            first_name = name[0]
            last_name = name[1]
        else:
            first_name = None
            last_name = None
    if last_name and not first_name:
        last_name = clean_html(last_name)
        names = last_name.split(u"\u202f")
        if len(names) == 1:
            names = last_name.split(" ")
        if len(names) == 2:
            first_name = names[0]
            last_name = names[1]
        elif len(names) > 2:
            first_name = names[0]
            last_name = " ".join(names[1:])
        else:
            logger.debug(f"Split name produced {names}")
            first_name = None
            last_name = None

    rank = int(metadata.get('@rank', 1))
    logger.info(f"Creating author metadata: {first_name} {last_name} {orcid} {rank}")
    if first_name and last_name:
        return AuthorMetadata(orcid, last_name, first_name, rank)
    else:
        return None


def parse_result_type(metadata: str) -> str:
    """Extracts the result type from the metadata and returns one of four types

    The four types are:
    - dataset
    - software
    - publication
    - other
    """
    result_type = metadata.get('resulttype', None)
    if result_type and (result_type['@schemeid'] == "dnet:result_typologies"):
        result_type = result_type.get('@classid')
    else:
        logger.debug(f"Could not identify result type from {result_type}")
        result_type = None

    return result_type


def parse_metadata(metadata: str, valid_doi: str) -> ArticleMetadata:
    """Parses the response from the OpenAire Graph API

    Notes
    -----
    For now, this assumes all outputs are journal papers
    """
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
        logger.info(f"Parsing output {title}")

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

        authors = entity.get('creator', None)

        all_authors: List[AuthorMetadata] = []
        if isinstance(authors, list):
            for x in authors:
                author = parse_author(x)
                if author:
                    all_authors.append(author)
        else:
            author = parse_author(authors)
            if author:
                all_authors.append(author)

        doi = valid_doi

        result_type = parse_result_type(entity)
        logger.info(f"Resource {doi} is a {result_type}")

        resource_type = entity.get("resourcetype", None)
        if resource_type and (resource_type['@schemeid'] == "dnet:result_typologies"):
            resource_type = resource_type.get('@classid')
        else:
            logger.debug(f"Could not identify result type from {resource_type}")
            resource_type = None

        issue = None
        volume = None

        # Get the acceptance date:
        date_of_acceptance = entity.get('dateofacceptance', None)
        if date_of_acceptance:
            date = date_of_acceptance.get('$', None)
            if date:

                date_parts = date.split('-')
                publication_year = int(date_parts[0])
                publication_month = int(date_parts[1])
                publication_day = int(date_parts[-1])

        return ArticleMetadata(doi, title, abstract,
                               all_authors, journal, issue, volume,
                               publication_year, publication_month,
                               publication_day, publisher, result_type, resource_type)
