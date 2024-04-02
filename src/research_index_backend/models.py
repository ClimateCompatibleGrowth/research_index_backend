from gqlalchemy import Node, Relationship
from typing import Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


@dataclass
class AuthorMetadata():
    orcid: Optional[str]
    last_name: str
    first_name: str
    rank: int


@dataclass
class ArticleMetadata():
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
    uuid: str


class Article(Output):
    uuid: Optional[str]
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
