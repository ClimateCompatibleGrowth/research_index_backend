from typing import List
from logging import getLogger

from .utils import clean_html

logger = getLogger(__name__)


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
