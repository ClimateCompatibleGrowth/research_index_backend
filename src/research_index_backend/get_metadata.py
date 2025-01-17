from json import JSONDecodeError, dump
from logging import DEBUG, basicConfig, getLogger
from os import makedirs

import requests
import requests_cache

from .config import config

logger = getLogger(__name__)
basicConfig(
    filename="research_index_backend.log",
    filemode="w",
    encoding="utf-8",
    level=DEBUG,
)


def get_metadata_from_openaire(
    session: requests_cache.CachedSession, doi: str, token
):
    """Gets metadata from OpenAire

    Arguments
    ---------
    session: CachedSession
    doi: str

    Returns
    -------
    """
    query = f"?format=json&doi={doi}"
    headers = {"Authorization": f"Bearer {token}"}
    api_url = f"{config.openaire_api}/search/researchProducts"

    response = session.get(api_url + query, headers=headers)

    logger.debug(f"Response code: {response.status_code}")
    response.raise_for_status()

    if error := response.json().get("error"):
        raise ValueError(error)

    clean_doi = doi.replace("/", "")
    directory = "data/json/openaire"
    makedirs(directory, exist_ok=True)

    with open(f"data/json/openaire/{clean_doi}.json", "w") as json_file:
        try:
            dump(response.json(), json_file)
        except JSONDecodeError as ex:
            logger.error(str(ex))
    if response.json()["response"]["results"]:
        return response.json()
    else:
        raise ValueError(f"DOI {doi} returned no results")


def get_metadata_from_openalex(session, doi):
    """Gets metadata from OpenAlex

    Arguments
    ---------
    session: CachedSession
    doi: str

    Returns
    -------
    """

    logger.info(f"Requesting {doi} from OpenAlex")
    query = f"doi:{doi}?mailto=wusher@kth.se"
    api_url = "https://api.openalex.org/works/"
    response = session.get(api_url + query)
    directory = "data/json/openalex"
    makedirs(directory, exist_ok=True)
    try:
        response.raise_for_status()
        clean_doi = doi.replace("/", "")
        with open(f"data/json/openalex/{clean_doi}.json", "w") as json_file:
            try:
                dump(response.json(), json_file)
            except JSONDecodeError as ex:
                logger.error(str(ex))
    except requests.exceptions.HTTPError as err:
        logger.error(str(err))

    if response.json():
        return response.json()
    else:
        raise ValueError(f"DOI {doi} returned no results")
