import os
from datetime import datetime
from json import load

import pytest

from research_index_backend.models import AnonymousArticle, AnonymousAuthor
from research_index_backend.parser import (
    parse_author,
    parse_date,
    parse_metadata,
    parse_result_type,
)


class TestAuthor:
    """Tests parsing of all combinations of authors

    Note
    ----
    Dataclass for author metadata has the following fields:

        class Author():
            orcid: Optional[str]
            last_name: str
            first_name: str
            rank: int

    """

    def test_author_orcid_pending(self):

        fixture = {
            "rank": "1",
            "name": "Lucy",
            "surname": "Allington",
            "pid": {
                "id": {
                    "scheme": "orcid_pending",
                    "value": "0000-0003-1801-899x",
                },
                "provenance": "null",
            },
            "fullName": "Allington, Lucy",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid="https://orcid.org/0000-0003-1801-899x",
            last_name="Allington",
            first_name="Lucy",
            rank=1,
        )
        assert actual == expected

    def test_author_orcid(self):
        fixture = {
            "rank": "5",
            "name": "Will",
            "surname": "Usher",
            "pid": {
                "id": {"scheme": "orcid", "value": "0000-0001-9367-1791"},
                "provenance": "null",
            },
            "fullName": "Usher, Will",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid="https://orcid.org/0000-0001-9367-1791",
            last_name="Usher",
            first_name="Will",
            rank=5,
        )
        assert actual == expected

    def test_author_no_orcid(self):
        fixture = {
            "rank": "5",
            "name": "Will",
            "surname": "Usher",
            "fullName": "Usher, Will",
            "pid": {},
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid=None, last_name="Usher", first_name="Will", rank=5
        )
        assert actual == expected

    def test_author_name_poorly_formed(self):
        fixture = {
            "rank": "13",
            "surname": "Stephanie Hirmer",
            "pid": {
                "id": {
                    "scheme": "orcid_pending",
                    "value": "0000-0001-7628-9259",
                },
                "provenance": "null",
            },
            "fullName": "null Stephanie Hirmer",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid="https://orcid.org/0000-0001-7628-9259",
            last_name="Hirmer",
            first_name="Stephanie",
            rank=13,
        )
        assert actual == expected

    def test_author_no_name_no_orcid(self):
        fixture = {"rank": "13", "fullName": "not a name"}
        actual = parse_author(fixture)
        expected = None
        assert actual == expected

    def test_author_no_first_name(self):
        fixture = {
            "rank": "1",
            "name": "Antoinette",
            "surname": "HABINSHUTI Antoinette",
            "fullName": "HABINSHUTI Antoinette",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid=None, last_name="Habinshuti", first_name="Antoinette", rank=1
        )
        assert actual == expected


class TestResearchProduct:

    def test_parse_metadata(self):
        """ """
        file_path = os.path.join(
            "tests", "fixtures", "openaire_v2_simple.json"
        )

        with open(file_path, "r") as json_file:
            json = load(json_file)
            actual = parse_metadata(json, "10.5281/zenodo.4650794", {})

            author = {
                "rank": 1,
                "first_name": "Lucy",
                "last_name": "Allington",
                "orcid": "https://orcid.org/0000-0003-1801-899x",
            }

            authors = [AnonymousAuthor(**author)]

            article = {
                "title": "CCG Starter Data Kit: Liberia",
                "authors": authors,
                "doi": "10.5281/zenodo.4650794",
                "abstract": "A starter data kit for Liberia",
                "journal": "",
                "issue": None,
                "volume": None,
                "publication_year": 2021,
                "publication_month": 3,
                "publication_day": 31,
                "publisher": "Zenodo",
                "result_type": "dataset",
                "resource_type": None,
                "cited_by_count_date": datetime.now().year,
            }

            expected = [AnonymousArticle(**article)]

            assert actual == expected

    def test_parse_date(self):
        date_string = "2021-05-13"
        actual = parse_date(date_string)
        expected = (2021, 5, 13)
        assert actual == expected

    def test_parse_metadata_openaire_v2(self):

        file_path = os.path.join(
            "tests", "fixtures", "openaire_v2_simple.json"
        )

        with open(file_path, "r") as json_file:
            json = load(json_file)
            actual = parse_metadata(
                json, "10.5281/zenodo.4650794", {"source": "openaire_v2"}
            )

            author = {
                "rank": 1,
                "first_name": "Lucy",
                "last_name": "Allington",
                "orcid": "https://orcid.org/0000-0003-1801-899x",
            }

            authors = [AnonymousAuthor(**author)]

            article = {
                "title": "CCG Starter Data Kit: Liberia",
                "authors": authors,
                "doi": "10.5281/zenodo.4650794",
                "abstract": "A starter data kit for Liberia",
                "journal": "",
                "issue": None,
                "volume": None,
                "publication_year": 2021,
                "publication_month": 3,
                "publication_day": 31,
                "publisher": "Zenodo",
                "result_type": "dataset",
                "resource_type": None,
                "cited_by_count_date": datetime.now().year,
            }

            expected = [AnonymousArticle(**article)]

            assert actual == expected
