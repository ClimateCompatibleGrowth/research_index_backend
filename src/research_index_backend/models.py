"""This module describes the data model of the backend application

This module defines the graph data model including nodes,
representing various entities,
and edges, representing relationships between those entities.

"""

from dataclasses import dataclass
from typing import List, Optional

from gqlalchemy import Node, Relationship


@dataclass
class AuthorMetadata:
    orcid: Optional[str]
    last_name: str
    first_name: str
    rank: int


@dataclass
class ArticleMetadata:
    doi: Optional[str]
    title: Optional[str]
    abstract: Optional[str]
    authors: List[AuthorMetadata]
    journal: Optional[str]
    issue: Optional[int]
    volume: Optional[int]
    publication_year: Optional[int]
    publication_month: Optional[int]
    publication_day: Optional[int]
    publisher: Optional[str]
    result_type: Optional[str]
    resource_type: Optional[str]
    openalex: Optional[str]


class Author(Node):
    """Represents an author of or contributor to an output"""

    uuid: str
    first_name: Optional[str]
    last_name: Optional[str]
    orcid: Optional[str]
    openalex: Optional[str]


class Output(Node):
    """A generic research output"""

    uuid: Optional[str]


class Article(Output):
    """Node representing a peer reviewed journal article"""

    doi: Optional[str]
    title: Optional[str]
    abstract: Optional[str]
    journal: Optional[str]
    issue: Optional[int]
    volume: Optional[int]
    publication_year: Optional[int]
    publication_month: Optional[int]
    publication_day: Optional[int]
    publisher: Optional[str]
    result_type: Optional[str]
    resource_type: Optional[str]
    openalex: Optional[str]


class author_of(Relationship):
    rank: int


class Country(Node):
    """Node representing a country"""

    id: str
    name: str
    official_name: str
    dbpedia: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]


class Unit(Node):
    """Represents an entity involved in the project"""

    id: str
    name: Optional[str]


class Workstream(Unit):
    """Represents a division of the work program"""

    pass


class Partner(Unit):
    """Represents part of whole of an institution or organisation"""

    dbpedia: Optional[str]
    openalex: Optional[str]


class member_of(Relationship):
    """The relationship between a partner and a workstream"""

    pass


class unit_of(Relationship):
    pass


class refers_to(Relationship):
    """The relationship between an output and a country or topic"""

    pass
