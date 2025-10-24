import logging
import os

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        load_dotenv()

        self.mg_host: str = os.getenv("MG_HOST", "127.0.0.1")
        self.mg_port: int = int(os.getenv("MG_PORT", 7687))
        self.mg_port_alt: int = int(os.getenv("MG_PORT_ALT", 7444))
        self.mg_user: str = os.getenv("MG_USER")
        self.mg_pass: str = os.getenv("MG_PASS")

        self.orcid_name_similarity_threshold: float = float(
            os.getenv("ORCID_NAME_SIMILARITY_THRESHOLD", 0.8)
        )
        self.name_similarity_threshold: float = float(
            os.getenv("NAME_SIMILARITY_THRESHOLD", 0.8)
        )

        self.openaire_api: str = os.getenv(
            "OPENAIRE_API", "https://api.openaire.eu/graph/v2"
        )
        self.openaire_service: str = os.getenv(
            "OPENAIRE_SERVICE", "https://services.openaire.eu"
        )

        self.openaire_token_endpoint = f"{self.openaire_service}/uoa-user-management/api/users/getAccessToken"
        self._refresh_token: str = ""
        self._token: str = ""
        self._validate()

    @property
    def refresh_token(self):
        if self._refresh_token:
            return self._refresh_token
        else:
            self._refresh_token = os.getenv("REFRESH_TOKEN", None)
            if self._refresh_token:
                return self._refresh_token
            else:
                raise ValueError("No refresh token provided")

    @property
    def token(self):
        if self._token:
            return self._token
        else:
            self._token = self._get_personal_token()
            return self._token

    def _validate(self):
        if not 0 <= self.orcid_name_similarity_threshold <= 1:
            raise ValueError(
                "ORCID_NAME_SIMILARITY_THRESHOLD must be between 0 and 1"
            )
        if not 0 <= self.name_similarity_threshold <= 1:
            raise ValueError(
                "NAME_SIMILARITY_THRESHOLD must be between 0 and 1"
            )

    def _get_personal_token(self) -> str:
        """Get personal token by providing a refresh token"""
        if refresh_token := os.getenv("REFRESH_TOKEN"):
            logger.info("Found refresh token. Obtaining personal token.")
            query = f"?refreshToken={refresh_token}"
            try:
                response = requests.get(self.openaire_token_endpoint + query)
                logger.info(f"Status code: {response.status_code}")
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                if 400 <= response.status_code < 500:
                    raise ValueError(
                        "OpenAire refresh token is invalid or expired. Please update token and try again."
                    )
                elif 500 <= response.status_code < 600:
                    raise
                else:
                    raise
            else:
                try:
                    response_json = response.json()
                    logger.debug(response_json)
                    return response_json["access_token"]
                except requests.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON response: {e}")
                    raise ValueError(
                        "Failed to obtain personal token due to JSON decode error"
                    )
                except Exception as e:
                    msg = str(e)
                    logger.error(f"{msg}")
                    raise
        else:
            raise ValueError(
                "No refresh token found, could not obtain personal token"
            )


config = Config()
