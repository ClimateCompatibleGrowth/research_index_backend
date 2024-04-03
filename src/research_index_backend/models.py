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


class Author(Node):
    uuid: str
    first_name: Optional[str]
    last_name: Optional[str]
    orcid: Optional[str]


class Output(Node):
    uuid: Optional[str]


class Article(Output):
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


class author_of(Relationship):
    rank: int


class Country(Node):
    id: str
    name: str
    dbpedia: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]


class Unit(Node):
    id: str
    name: Optional[str]


class Workstream(Unit):
    pass


class Partner(Unit):
    dbpedia: Optional[str]


class member_of(Relationship):
    pass


class unit_of(Relationship):
    pass


class refers_to(Relationship):
    pass
