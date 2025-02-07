from datetime import datetime
from logging import getLogger
from typing import Dict, List

from .models import AnonymousArticle, AnonymousAuthor
from .utils import clean_html

logger = getLogger(__name__)


def parse_author(metadata: Dict) -> AnonymousAuthor | None:
    """Parses the JSON for an author

    Arguments
    ---------
    metadata
    """
    orcid = metadata.get("@orcid", None)
    if not orcid:
        orcid = metadata.get("@orcid_pending", None)

    first_name = metadata.get("@name", "").title()
    last_name = metadata.get("@surname", "").title()
    if first_name in last_name:
        last_name = last_name.replace(first_name, "").strip()
    if last_name in first_name:
        first_name = first_name.replace(last_name, "").strip()

    if not first_name and not last_name:
        name = metadata.get("$")
        if name:
            name = name.split()
            if len(name) == 2:
                first_name = name[0]
                last_name = name[1]
            else:
                first_name = None
                last_name = None
    if last_name and not first_name:
        last_name = clean_html(last_name)
        names = last_name.split("\u202f")
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

    rank = int(metadata.get("@rank", 1))
    logger.info(
        f"Creating author metadata: {first_name} {last_name} {orcid} {rank}"
    )
    if first_name and last_name:
        return AnonymousAuthor(
            first_name=first_name,
            last_name=last_name,
            orcid=f"https://orcid.org/{orcid}" if orcid else None,
            rank=rank,
        )
    else:
        return None


def parse_result_type(metadata: Dict) -> str:
    """Extracts the result type from the metadata and returns one of four types

    The four types are:
    - dataset
    - software
    - publication
    - other
    """
    result_type = metadata.get("resulttype", None)
    if result_type and (result_type["@schemeid"] == "dnet:result_typologies"):
        result_type = result_type.get("@classid")
    else:
        logger.debug(f"Could not identify result type from {result_type}")
        result_type = None

    return result_type


def parse_metadata(
    metadata: Dict, valid_doi: str, openalex_metadata: Dict
) -> List[AnonymousArticle]:
    """Parses the response from the OpenAire Graph API

    Notes
    -----
    For now, this assumes all outputs are journal papers
    """

    length = len(metadata["response"]["results"]["result"])
    logger.info(f"There are {length} results")

    articles_metadata = []

    for result in metadata["response"]["results"]["result"]:

        entity = result["metadata"]["oaf:entity"]["oaf:result"]

        title_meta = entity["title"]
        if isinstance(title_meta, list):
            count = 0
            for x in title_meta:
                count += 1
                if x["@classid"] == "main title":
                    title = clean_html(x["$"])
                    break
                else:
                    pass
        else:
            title = clean_html(title_meta["$"])
        logger.info(f"Parsing output {title}")

        publisher = entity.get("publisher", None)
        if publisher:
            publisher = publisher["$"]
        else:
            publisher = None

        journal_meta = entity.get("journal", "")
        if journal_meta:
            journal = journal_meta.get("$", "")
            if journal:
                journal = clean_html(journal)
            else:
                logger.debug(f"Journal not empty: {journal_meta}")
        else:
            journal = ""

        abstract = entity.get("description", None)
        if abstract:
            if isinstance(abstract, list):
                abstract = abstract[0]
            if "$" in abstract.keys():
                abstract = clean_html(abstract["$"])

        authors = entity.get("creator", None)

        all_authors: List[AnonymousAuthor] = []
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
        if resource_type and (
            resource_type["@schemeid"] == "dnet:result_typologies"
        ):
            resource_type = resource_type.get("@classname")
        elif resource_type and (
            resource_type["@schemeid"] == "dnet:publication_resource"
        ):
            resource_type = resource_type.get("@classname")
        else:
            logger.debug(
                f"Could not identify instance type from {resource_type}"
            )
            resource_type = None

        issue = None
        volume = None
        publication_year = None
        publication_month = None
        publication_day = None

        # Get the acceptance date:
        date_of_acceptance = entity.get("dateofacceptance", None)
        if date_of_acceptance:
            date = date_of_acceptance.get("$", None)
            if date:

                date_parts = date.split("-")
                publication_year = int(date_parts[0])
                publication_month = int(date_parts[1])
                publication_day = int(date_parts[-1])

        article_object = AnonymousArticle(
            doi=doi,
            title=clean_html(title),
            abstract=abstract,
            authors=all_authors,
            journal=journal,
            issue=issue,
            volume=volume,
            publication_year=publication_year,
            publication_month=publication_month,
            publication_day=publication_day,
            publisher=publisher,
            result_type=result_type,
            resource_type=resource_type,
            openalex=openalex_metadata.get("id"),
            cited_by_count=openalex_metadata.get("cited_by_count"),
            cited_by_count_date=datetime.now().year,
            counts_by_year=None,
        )
        articles_metadata.append(article_object)

    return articles_metadata
