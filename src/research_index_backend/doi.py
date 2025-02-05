"""DOI (Digital Object Identifier) validation and management module.

This module handles:
1. DOI pattern validation
2. Database existence checks
3. Metadata validation
4. Batch processing with limits: TODO
"""

import time
from logging import getLogger
from re import IGNORECASE, compile
from typing import Dict, List

from neo4j import Driver
from neo4j.exceptions import ServiceUnavailable, Neo4jError # https://neo4j.com/docs/api/python-driver/current/api.html#errors
from pydantic import BaseModel

from .session import connect_to_db

logger = getLogger(__name__)

# Use regex pattern from
# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
DOI_PATTERN = r"10\.\d{4,9}/(?=.*\d)[-._;()/:A-Z0-9]+$"

class DOI(BaseModel):
    doi: str
    valid_pattern: bool = False
    already_exists: bool = False
    openalex_metadata: bool = False
    openaire_metadata: bool = False
    ingestion_success: bool = False


class DOITracker(BaseModel):
    doi_tracker: Dict[str, DOI]


class DOIManager:
    """Manages the validation and ingestion tracking of Digital Object Identifiers (DOIs).

    This class handles DOI validation, database existence checks, and metadata tracking.
    It processes DOIs up to a specified limit and can optionally update metadata
    for existing entries.

    Parameters
    ----------
    list_of_dois : List[str]
        List of DOI strings to process
    limit : int
        Maximum number of DOIs to process from the list
    update_metadata : bool, optional
        Whether to update metadata for existing DOIs (default is True)

    Attributes
    ----------
    doi_tracker : Dict[str, DOI]
        Dictionary tracking the state of each processed DOI
    valid_pattern_dois : List[str]
        DOIs that match the valid pattern
    invalid_pattern_dois : List[str]
        DOIs that don't match the valid pattern
    existing_dois : List[str]
        DOIs that already exist in the database
    new_dois : List[str]
        DOIs that are not yet in the database

    Methods
    -------
    validate_dois()
        Performs pattern validation and database existence checks
    ingestion_metrics()
        Returns metrics about the ingestion process
    pattern_check()
        Validates DOI patterns against the standard format
    search_dois()
        Checks database for existing DOIs

    Raises
    ------
    ValueError
        If DOI list is empty or limit is invalid
    """
    def __init__(
        self, list_of_dois: List[str], limit: int, update_metadata: bool = True
    ) -> None:

        self._validate_inputs(list_of_dois, limit, update_metadata)
        self.list_of_dois = [
            doi.strip()
            .rstrip(".")
            .replace("https://doi.org/", "")
            .replace("doi.org/", "")
            for doi in list_of_dois
        ]
        self.limit = limit if limit < len(self.list_of_dois) else len(self.list_of_dois) 
        self.update_metadata = update_metadata
        self.doi_tracker: DOITracker = {
            doi: DOI(doi=doi) for doi in self.list_of_dois[: self.limit]
        }
        self.PATTERN = compile(DOI_PATTERN, IGNORECASE)

    def _validate_inputs(self, dois: List[str], limit: int, update_metadata: bool) -> None:
        if not isinstance(dois, list):
            raise TypeError("DOIs must be provided as a list")
        if not dois:
            raise ValueError("DOI list cannot be empty")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("Limit must be a positive integer")
        if not isinstance(update_metadata, bool):
            raise TypeError("update_metadata must be a boolean")           

    def start_ingestion(self):
        self.start_time = time.time()

    def end_ingestion(self):
        self.end_time = time.time()
        
    def pattern_check(self):
        try:
            self.valid_pattern_dois = []
            self.invalid_pattern_dois = []

            for doi in self.doi_tracker:
                if search := self.PATTERN.search(doi):
                    logger.debug(f"Valid DOI pattern: {search.group()}")
                    self.doi_tracker[doi].valid_pattern = True
                    self.valid_pattern_dois.append(doi)
                else:
                    logger.warning(f"Invalid DOI pattern: {doi}")
                    self.invalid_pattern_dois.append(doi)
            self.num_valid_pattern_dois = len(self.valid_pattern_dois)
            self.num_invalid_pattern_dois = len(self.invalid_pattern_dois)
        except Exception as e:
            logger.error(f"Error whilst checking DOI pattern: {e}")
            raise

    @connect_to_db
    def search_dois(self, db: Driver) -> None:
        if not self.valid_pattern_dois:
            msg = "None of the provided DOIs match the valid pattern."
            logger.warning(msg)
            raise ValueError(msg)
        query = """
            UNWIND $dois as doi
            OPTIONAL MATCH (o:Output {doi: doi})
            RETURN doi, COUNT(o) > 0 as exists"""
        try:
            results, _, _ = db.execute_query(query, dois=self.valid_pattern_dois)
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            raise
        except Neo4jError as e:
            logger.error(f"Neo4j error occurred during query execution: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error whilst searching for DOIs: {e}")
            raise

        self.existing_dois = [
            record["doi"] for record in results if record["exists"]
        ]
        self.new_dois = [
            record["doi"] for record in results if not record["exists"]
        ]
        for doi in self.doi_tracker:
            if doi in self.existing_dois:
                self.doi_tracker[doi].already_exists = True

        self.num_new_dois = len(self.new_dois)
        self.num_existing_dois = len(self.existing_dois)
        
        logger.info(f"Found {self.num_existing_dois} existing and {self.num_new_dois} new DOIs")


    def validate_dois(self) -> Dict[str, List[str]]:
        try:
            self.pattern_check()
            self.search_dois()
            return self.doi_tracker
        except Exception as e:
            logger.error(f"DOI validation failed: {e}")
            raise

    def ingestion_metrics(self) -> Dict[str, int]:
        total_time = self.end_time - self.start_time

        processed_dois = (
            self.valid_pattern_dois if self.update_metadata else self.new_dois
        )

        metadata_pass = [
            doi
            for doi in self.doi_tracker
            if self.doi_tracker[doi].ingestion_success
            and doi in processed_dois
        ]
        metadata_failure = [
            doi
            for doi in self.doi_tracker
            if not self.doi_tracker[doi].ingestion_success
            and doi in processed_dois
        ]

        self.ingested_dois = [
            doi
            for doi in self.doi_tracker
            if self.doi_tracker[doi].ingestion_success
        ]

        openalex_success = [
            doi
            for doi in processed_dois
            if self.doi_tracker[doi].openalex_metadata
        ]
        openaire_success = [
            doi
            for doi in processed_dois
            if self.doi_tracker[doi].openaire_metadata
        ]
        metrics = {
            "submitted_dois": len(self.list_of_dois),
            "processed_dois": len(processed_dois),
            "new_dois": self.num_new_dois,
            "existing_dois": self.num_existing_dois,
            "ingested_dois": len(self.ingested_dois),
            "metadata_pass": len(metadata_pass),
            "metadata_failure": len(metadata_failure),
            "valid_pattern_dois": self.num_valid_pattern_dois,
            "invalid_pattern_dois": self.num_invalid_pattern_dois,
            "openalex_success": len(openalex_success),
            "openaire_success": len(openaire_success),
            "total_time_seconds": round(total_time, 3),
        }

        doi_states = {
            "submitted_dois": self.list_of_dois,
            "processed_dois": processed_dois,
            "new_dois": self.new_dois,
            "existing_dois": self.existing_dois,
            "ingested_dois": self.ingested_dois,
            "metadata_pass": metadata_pass,
            "metadata_failure": metadata_failure,
            "openalex_success": openalex_success,
            "openaire_success": openaire_success,
            "valid_pattern_dois": self.valid_pattern_dois,
            "invalid_pattern_dois": self.invalid_pattern_dois,
        }
        return metrics, doi_states
