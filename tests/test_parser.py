import os
from datetime import datetime
from json import load
from typing import Final, Generator
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture

from research_index_backend.models import AnonymousArticle, AnonymousAuthor
from research_index_backend.parser import (
    parse_author,
    parse_metadata,
    parse_result_type,
)

JAN_31: Final[datetime] = datetime(2023, 1, 31, 0, 0, 0)


@pytest.fixture
def datetime_fixture(mocker: MockFixture) -> Generator[MagicMock, None, None]:
    mocked_datetime = mocker.patch(
        "research_index_backend.parser.datetime",
    )
    mocked_datetime.datetime.today.return_value = JAN_31
    yield mocked_datetime


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
            "@rank": "1",
            "@name": "Lucy",
            "@surname": "Allington",
            "@orcid_pending": "0000-0003-1801-899x",
            "$": "Allington, Lucy",
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
            "@rank": "5",
            "@name": "Will",
            "@surname": "Usher",
            "@orcid": "0000-0001-9367-1791",
            "$": "Usher, Will",
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
            "@rank": "5",
            "@name": "Will",
            "@surname": "Usher",
            "$": "Usher, Will",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid=None, last_name="Usher", first_name="Will", rank=5
        )
        assert actual == expected

    def test_author_orcid_no_name(self):
        fixture = {
            "@rank": "5",
            "@name": "Will",
            "@surname": "Usher",
            "$": "Usher, Will",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid=None, last_name="Usher", first_name="Will", rank=5
        )
        assert actual == expected

    def test_author_name_poorly_formed(self):
        fixture = {
            "@rank": "13",
            "@surname": "Stephanie Hirmer",
            "@orcid_pending": "0000-0001-7628-9259",
            "$": "null Stephanie Hirmer",
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
        fixture = {"@rank": "13", "$": "not a name"}
        actual = parse_author(fixture)
        expected = None
        assert actual == expected

    def test_author_no_first_name(self):
        fixture = {
            "@rank": "1",
            "@name": "Antoinette",
            "@surname": "HABINSHUTI Antoinette",
            "$": "HABINSHUTI Antoinette",
        }
        actual = parse_author(fixture)
        expected = AnonymousAuthor(
            orcid=None, last_name="Habinshuti", first_name="Antoinette", rank=1
        )
        assert actual == expected


class TestResearchProduct:

    argnames = "fixture,expected"
    argvalues = [
        (
            {
                "resulttype": {
                    "@classid": "dataset",
                    "@classname": "dataset",
                    "@schemeid": "dnet:result_typologies",
                    "@schemename": "dnet:result_typologies",
                }
            },
            "dataset",
        ),
        (
            {
                "resulttype": {
                    "@classid": "software",
                    "@classname": "software",
                    "@schemeid": "dnet:result_typologies",
                    "@schemename": "dnet:result_typologies",
                }
            },
            "software",
        ),
        (
            {
                "resulttype": {
                    "@classid": "other",
                    "@classname": "other",
                    "@schemeid": "dnet:result_typologies",
                    "@schemename": "dnet:result_typologies",
                }
            },
            "other",
        ),
        (
            {
                "resulttype": {
                    "@classid": "publication",
                    "@classname": "publication",
                    "@schemeid": "dnet:result_typologies",
                    "@schemename": "dnet:result_typologies",
                }
            },
            "publication",
        ),
    ]

    @pytest.mark.parametrize(argnames, argvalues)
    def test_result_type(self, fixture, expected):
        """Tests parsing of the result type from the OpenAire metadata.

        Result type is described by the dnet:result_typologies vocabulary entry
        https://api.openaire.eu/vocabularies/dnet:result_typologies

        Sub types are then identified by the ResourceType:

        - dataset
            - 0021 Dataset
            - 0022 Collection
            - 0024 Film
            - 0025 Image
        - other
            - 0010 Lecture
            - 0023 Event
        - publication
            - 0001 Article
            - 0002 Book
            - 0004 Conference object
            - 0016 Preprint
            - 0017 Report
            - 0031 Data Paper
            - 0032 Software Paper
            - 0034 Project Deliverable
            - 0035 Project Milestone
            - 0036 Project Proposal
            - 0045 Data Management Plan
            - 0050 Presentation
        - software
            - 0029 Software
            - 0049 Other software type

        """
        actual = parse_result_type(fixture)
        assert actual == expected

    def test_parse_metadata(self, datetime_fixture: MagicMock):
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
                "resource_type": None,
                "cited_by_count_date": datetime(2023, 1, 31, 0, 0, 0),
            }

            expected = [AnonymousArticle(**article)]

            print(datetime_fixture.mock_calls)

            assert actual == expected
