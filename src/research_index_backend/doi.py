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
from pydantic import BaseModel

from .session import connect_to_db

logger = getLogger(__name__)

DOI_PATTERN = "10\\.\\d{4,9}/[-._;()/:A-Z0-9]+$"
class DOI(BaseModel):
    doi: str
    valid_pattern: bool = False
    already_exists: bool = False
    openalex_metadata: bool = False
    openaire_metadata: bool = False
    ingestion_success: bool = False


class DOITracker(DOI):
    doi_tracker: Dict[str, DOI]


class DOIManager:
    def __init__(
        self, list_of_dois: List[str], limit: int, update_metadata=True
    ) -> None:

        if not list_of_dois:
            raise ValueError("DOI list cannot be empty")
        if (limit <= 0) or (limit > len(list_of_dois)):
            raise ValueError(
                "Limit must be positive and less than the number of DOIs"
            )

        self.list_of_dois = [
            doi.strip()
            .rstrip(".")
            .replace("doi.org/", "")
            .replace("https://doi.org/", "")
            for doi in list_of_dois
        ]
        self.limit = limit
        self.update_metadata = update_metadata
        self.doi_tracker = {
            doi: DOI(doi=doi) for doi in self.list_of_dois[: self.limit]
        }
        self.PATTERN = compile(DOI_PATTERN, IGNORECASE)

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
    def search_dois(self, db: Driver):
        if not self.valid_pattern_dois:
            msg = "No DOIs have passed the pattern check and make sure to run pattern check first."
            logger.warning(msg)
            raise ValueError(msg)
        query = """
            UNWIND $dois as doi
            OPTIONAL MATCH (o:Output {doi: doi})
            RETURN doi, COUNT(o) > 0 as exists"""
        try:
            results, _, _ = db.execute_query(
                query, dois=self.valid_pattern_dois
            )
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
            self.num_existing_new_dois = len(self.existing_dois)

        except Exception as e:
            logger.error(f"Error whilst searching for DOIs: {e}")
            raise

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
            "existing_dois": self.num_existing_new_dois,
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
