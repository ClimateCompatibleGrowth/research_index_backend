import os
from datetime import datetime
from json import load

from research_index_backend.models import AnonymousArticle, AnonymousAuthor
from research_index_backend.parser import parse_author, parse_metadata


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
            "fullName": "Allington, Lucy",
            "name": "Lucy",
            "surname": "Allington",
            "rank": 1,
            "pid": {
                "id": {
                    "scheme": "orcid_pending",
                    "value": "0000-0003-1801-899x",
                },
                "provenance": None,
            },
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
            "fullName": "Usher, Will",
            "name": "Will",
            "surname": "Usher",
            "rank": 5,
            "pid": {
                "id": {
                    "scheme": "orcid_pending",
                    "value": "0000-0001-9367-1791",
                },
                "provenance": None,
            },
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
            "fullName": "Usher, Will",
            "name": "Will",
            "surname": "Usher",
            "rank": 5,
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid=None, last_name="Usher", first_name="Will", rank=5
        )
        assert actual == expected


class TestResearchProduct:
    """Tests parsing of research product metadata"""

    def test_parse_metadata(self):
        """ """
        file_path = os.path.join("tests", "fixtures", "zenodo.json")

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
                "publication_year": 2023,
                "publication_month": 1,
                "publication_day": 16,
                "publisher": "Zenodo",
                "result_type": "dataset",
                "resource_type": "Dataset",
                "cited_by_count_date": datetime.now().date(),
                "cited_by_count": 0,
            }

            expected = [AnonymousArticle(**article)]

            assert actual == expected
