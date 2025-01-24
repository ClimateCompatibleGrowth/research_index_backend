from json import JSONDecodeError, dump
from logging import DEBUG, basicConfig, getLogger
from os import makedirs
from typing import Dict

import requests
import requests_cache

from .config import config

class MetadataFetcher:
    def __init__(self, session: requests_cache.CachedSession, token: str = None):
        self.session = session
        self.token = token or config.token
        self.logger = getLogger(__name__)
        basicConfig(
            filename="research_index_backend.log",
            filemode="w",
            encoding="utf-8",
            level=DEBUG,
        )

    def _save_json_response(self, response, directory: str, doi: str) -> None:
        """Helper method to save JSON responses"""
        clean_doi = doi.replace("/", "")
        makedirs(directory, exist_ok=True)
        
        with open(f"{directory}/{clean_doi}.json", "w") as json_file:
            try:
                dump(response.json(), json_file)
            except JSONDecodeError as ex:
                self.logger.error(str(ex))

    def get_metadata_from_openaire(self, doi: str) -> Dict:
        """Gets metadata from OpenAire"""
        query = f"?format=json&doi={doi}"
        headers = {"Authorization": f"Bearer {self.token}"}
        api_url = f"{config.openaire_api}/search/researchProducts"

        response = self.session.get(api_url + query, headers=headers)

        self.logger.debug(f"Response code: {response.status_code}")
        response.raise_for_status()

        if error := response.json().get("error"):
            raise ValueError(error)

        self._save_json_response(response, "data/json/openaire", doi)

        if response.json()["response"]["results"]:
            return response.json()
        else:
            raise ValueError(f"DOI {doi} returned no results")

    def get_metadata_from_openalex(self, doi: str) -> Dict:
        """Gets metadata from OpenAlex"""
        self.logger.info(f"Requesting {doi} from OpenAlex")
        query = f"doi:{doi}?mailto=wusher@kth.se"
        api_url = "https://api.openalex.org/works/"
        
        response = self.session.get(api_url + query)
        
        try:
            response.raise_for_status()
            self._save_json_response(response, "data/json/openalex", doi)
        except requests.exceptions.HTTPError as err:
            self.logger.error(str(err))

        if response.json():
            return response.json()
        else:
            raise ValueError(f"DOI {doi} returned no results")

    def get_output_metadata(self, doi: str, source: str = "OpenAire") -> Dict:
        """Request metadata from specified source"""
        if source == "OpenAire":
            return self.get_metadata_from_openaire(doi)
        elif source == "OpenAlex":
            return self.get_metadata_from_openalex(doi)
        else:
            raise ValueError("Incorrect argument for output metadata source")