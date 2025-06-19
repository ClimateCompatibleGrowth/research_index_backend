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
    orcid = None
    pid = metadata.get("pid", None)
    if pid:
        id = pid.get("id", None)
        if id and (id.get("scheme") == "orcid_pending"):
            orcid = id.get("value", None)

    first_name = metadata.get("name", "").title()
    last_name = metadata.get("surname", "").title()
    if first_name in last_name:
        last_name = last_name.replace(first_name, "").strip()
    if last_name in first_name:
        first_name = first_name.replace(last_name, "").strip()

    if not first_name and not last_name:
        name = metadata.get("fullName", None)
        if name:
            name = name.split()
            if len(name) == 2:
                first_name = name[0]
                last_name = name[1]
            elif len(name) > 2:
                first_name = name[0]
                last_name = " ".join(name[1:])
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

    rank = int(metadata.get("rank", 1))
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


def parse_metadata(
    metadata: list, valid_doi: str, openalex_metadata: Dict
) -> List[AnonymousArticle]:
    """Parses the response from the OpenAire Graph API

    Notes
    -----
    For now, this assumes all outputs are journal papers
    """

    length = len(metadata)
    logger.info(f"There are {length} results")

    articles_metadata = []

    for result in metadata:

        # Get the title
        title = ""
        title_meta = result.get("mainTitle")
        if title_meta:
            title = clean_html(title_meta)
        logger.info(f"Parsing output {title}")

        publisher = result.get("publisher", None)

        # Get the journal
        journal = ""
        issue = None
        volume = None
        if result["type"] == "publication":
            if container := result.get("container", None):
                journal = container.get("name", "")
                journal = clean_html(journal)
                issue = container.get("iss", None)
                volume = container.get("vol", None)

        # Get the abstract
        abstract = ""
        abstract = result.get("description", "")
        if isinstance(abstract, list):
            abstract = " ".join(abstract)
        abstract = clean_html(abstract)

        # Get the authors
        authors = result.get("author", None)
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

        result_type = result.get("type", "")
        assert result_type in [
            "publication",
            "dataset",
            "software",
            "other",
        ], f"Unknown result type {result_type}"
        logger.info(f"Resource {doi} is a {result_type}")

        if isinstance(result["instance"], list):
            for instance in result["instance"]:
                resource_type = instance.get("type", "")
                date = instance.get("publicationDate", None)
                if result_type == "publication":
                    assert resource_type in [
                        "Article",
                        "Pre-print",
                    ], f"Unknown resource type {resource_type}"
                    logger.info(f"Resource {doi} is a {resource_type}")
                    break
                elif result_type == "dataset":
                    assert resource_type in [
                        "Dataset"
                    ], f"Unknown resource type {resource_type}"
                    logger.info(f"Resource {doi} is a {resource_type}")
                    break

        publication_year = None
        publication_month = None
        publication_day = None

        # Get the publication date:
        if not date:
            date = result.get("publicationDate", None)
        date_parts = date.split("-")
        publication_year = int(date_parts[0])
        publication_month = int(date_parts[1])
        publication_day = int(date_parts[-1])

        # Get the citation count
        citations = result.get("indicators", {}).get("citationImpact", {})
        cited_by_count = citations.get(
            "citationCount", 0
        )  # Number of citations
        cited_by_count_date = datetime.now().date()

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
            cited_by_count=cited_by_count,
            cited_by_count_date=cited_by_count_date,
            counts_by_year=None,
        )
        articles_metadata.append(article_object)

    return articles_metadata
