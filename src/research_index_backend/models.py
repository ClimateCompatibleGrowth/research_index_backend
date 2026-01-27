"""This module describes the data model of the backend application

This module defines the graph data model including nodes,
representing various entities,
and edges, representing relationships between those entities.

"""

from logging import DEBUG, basicConfig, getLogger
from typing import Optional
from uuid import UUID, uuid4

from neo4j import Driver
from neo4j.exceptions import ClientError
from pydantic import UUID4, BaseModel, Field, HttpUrl

from research_index_backend.session import connect_to_db

logger = getLogger(__name__)
basicConfig(
    filename="research_index_backend.log",
    filemode="w",
    encoding="utf-8",
    level=DEBUG,
)


class AnonymousAuthor(BaseModel):
    """An author with no id"""

    first_name: str
    last_name: str
    orcid: Optional[HttpUrl] = None
    rank: Optional[int] = None

    @connect_to_db
    def match_orcid(self, db):
        """Return author who matches the orcid id"""
        query = """
                MATCH (a:Author)
                WHERE a.orcid = $orcid
                RETURN a.uuid as uuid
                LIMIT 1
                """
        results, _, _ = db.execute_query(query, orcid=str(self.orcid))
        if results:
            return results[0].data()["uuid"]
        else:
            return None

    @connect_to_db
    def match_name(self, db):
        """Return author who matches the first and last names"""
        query = """
                MATCH (a:Author)
                WHERE a.first_name + ' ' + a.last_name = $name
                RETURN a.uuid as uuid
                LIMIT 1
                """
        results, _, _ = db.execute_query(
            query, name=f"{self.first_name} {self.last_name}"
        )
        if results:
            return results[0].data()["uuid"]
        else:
            return None


class Author(AnonymousAuthor):
    """Represents the author of an output"""

    uuid: UUID4
    openalex: Optional[str] = None

    @connect_to_db
    def save(self, db):
        if self.orcid:
            author_uuid = self.match_orcid()
            if author_uuid:
                logger.info(f"Author {author_uuid} already exists")
            else:
                query = """CREATE (a:Author {uuid: $uuid,
                                        first_name: $first_name,
                                        last_name: $last_name,
                                        orcid: $orcid,
                                        openalex: $openalex})
                            RETURN a.uuid as uuid
                    """
        else:
            author_uuid = self.match_name()
            if author_uuid:
                logger.info(f"Author {author_uuid} already exists")
            else:
                query = """CREATE (a:Author {uuid: $uuid,
                                    first_name: $first_name,
                                    last_name: $last_name,
                                    openalex: $openalex})
                            RETURN a.uuid as uuid
                        """

        try:
            results, summary, _ = db.execute_query(
                query,
                uuid=str(self.uuid),
                first_name=self.first_name,
                last_name=self.last_name,
                orcid=str(self.orcid),
                openalex=self.openalex,
            )
        except ClientError as ex:
            logger.error(
                f"Warning with {str(ex)} for record {self.model_dump()}"
            )
        else:
            logger.info(
                f"Created author nodes for {self.first_name} {self.last_name}"
            )
            return results[0].data()["uuid"]


class author_of(BaseModel):
    author: UUID4
    article: UUID4
    rank: int

    @connect_to_db
    def save(self, db):
        query = """MATCH (a:Author {uuid: $author_uuid}),
                         (b:Output {uuid: $article_uuid})
                   MERGE (a)-[r:author_of {rank: $rank}]-> (b)
                   RETURN a, r, b"""
        results, _, _ = db.execute_query(
            query,
            author_uuid=str(self.author),
            article_uuid=str(self.article),
            rank=self.rank,
        )


class AnonymousArticle(BaseModel):
    doi: str = Field(pattern=r"^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$")
    title: str
    abstract: Optional[str] = ""
    authors: list[AnonymousAuthor]
    journal: str = ""
    issue: Optional[int] = None
    volume: Optional[int] = None
    publication_year: Optional[int] = None
    publication_month: Optional[int] = None
    publication_day: Optional[int] = None
    publisher: str = ""
    result_type: Optional[str] = None
    resource_type: Optional[str] = None
    openalex: Optional[str] = None
    cited_by_count: Optional[int] = None
    cited_by_count_date: Optional[int] = None
    counts_by_year: Optional[dict] = None


class Article(AnonymousArticle):
    """Node representing a peer reviewed journal article"""

    uuid: UUID4

    @connect_to_db
    def save(self, db):
        if self.match_doi():
            logger.info(f"Output {self.doi} exists.")
        else:
            # Create Article object
            logger.info(
                f"Output {self.doi} does not exist. Creating new node."
            )

            query = """
                CREATE (a:Output {uuid: $uuid,
                                doi: $doi,
                                title: $title,
                                abstract: $abstract,
                                journal: $journal,
                                issue: $issue,
                                volume: $volume,
                                publication_year: $publication_year,
                                publication_month: $publication_month,
                                publication_day: $publication_day,
                                publisher: $publisher,
                                result_type: $result_type,
                                resource_type: $resource_type,
                                openalex: $openalex,
                                cited_by_count: $cited_by_count,
                                cited_by_count_date: $cited_by_count_date,
                                counts_by_year: $counts_by_year
                                })
                RETURN a.uuid as uuid
                """
            result, _, _ = db.execute_query(
                query,
                uuid=str(self.uuid),
                doi=self.doi,
                title=self.title,
                abstract=self.abstract,
                journal=self.journal,
                issue=self.issue,
                volume=self.volume,
                publication_year=self.publication_year,
                publication_month=self.publication_month,
                publication_day=self.publication_day,
                publisher=self.publisher,
                result_type=self.result_type,
                resource_type=self.resource_type,
                openalex=self.openalex,
                cited_by_count=self.cited_by_count,
                cited_by_count_date=self.cited_by_count_date,
                counts_by_year=self.counts_by_year,
            )
            logger.debug(result)
            output_uuid = result[0].data()["uuid"]
            # Check authors exists, otherwise create

            for author in self.authors:
                if author.orcid:
                    author_uuid = author.match_orcid()
                    if author_uuid:
                        logger.info(
                            f"""Author {author.first_name} {author.last_name} matched on {author.orcid}"""
                        )
                    else:
                        author_uuid = Author(
                            uuid=uuid4(), **author.model_dump()
                        ).save()
                else:
                    author_uuid = author.match_name()
                    if author_uuid:
                        logger.info(
                            f"Author {author.first_name} {author.last_name} matched on name."
                        )
                    else:
                        author_uuid = Author(
                            uuid=uuid4(), **author.model_dump()
                        ).save()

                logger.debug(
                    f"Attempting to create rel from {author_uuid} to {output_uuid}"
                )
                author_of(
                    author=UUID(author_uuid),
                    article=UUID(output_uuid),
                    rank=author.rank,
                ).save()

    @connect_to_db
    def match_doi(self, db):
        query = """MATCH (a:Output {doi: $doi})
                   RETURN a.uuid"""
        results, _, _ = db.execute_query(query, doi=self.doi)
        return results


class Country(BaseModel):
    """Node representing a country"""

    id: str
    name: str
    official_name: str
    dbpedia: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    @connect_to_db
    def save(self, db: Driver):
        query = """CREATE (:Country {id: $id,
                                    name: $name,
                                    official_name: $official_name,
                                    dbpedia: $dbpedia,
                                    latitude: $latitude,
                                    longitude: $longitude})
                """
        results, _, _ = db.execute_query(
            query,
            id=self.id,
            name=self.name,
            official_name=self.official_name,
            dbpedia=self.dbpedia,
            latitude=self.latitude,
            longitude=self.longitude,
        )
        logger.info(f"Created country nodes for {self.name}")


class Unit(BaseModel):
    """Represents an entity involved in the project"""

    id: str
    name: Optional[str] = None

    def save(self, db):
        query = """CREATE (:Unit {id: $id,
                                  name: $name,
                                  last_name: $last_name})
                """
        results, _, _ = db.execute_query(query, id=self.id, name=self.name)
        logger.info(f"Created unit nodes for {self.name}")


class Workstream(Unit):
    """Represents a division of the work program"""

    @connect_to_db
    def save(self, db):
        query = """CREATE (:Workstream:Unit {id: $id,
                                        name: $name})
                """
        results, summary, _ = db.execute_query(
            query, id=self.id, name=self.name
        )
        logger.info(f"Created workstream nodes for {self.name}")


class Partner(Unit):
    """Represents part of whole of an institution or organisation"""

    dbpedia: Optional[str] = None
    ror: Optional[str] = None
    openalex: Optional[str] = None

    @connect_to_db
    def save(self, db):
        query = """CREATE (:Partner:Unit {id: $id,
                                    name: $name,
                                    dbpedia: $dbpedia,
                                    ror: $ror,
                                    openalex: $openalex})
                """
        results, summary, _ = db.execute_query(
            query,
            id=self.id,
            name=self.name,
            dbpedia=self.dbpedia,
            ror=self.ror,
            openalex=self.openalex,
        )
        logger.info(f"Created partner nodes for {self.name}")


class member_of(BaseModel):
    """The relationship between a partner and a workstream"""

    @connect_to_db
    def save(self, db, uuid: UUID4, id: str):
        query = """MATCH (a:Author), (p:Unit)
                WHERE a.uuid = $uuid AND p.id = $id
                MERGE (a)-[r:member_of]->(p)
                RETURN a, r, p
                """
        _, summary, _ = db.execute_query(query, uuid=str(uuid), id=id)
        logger.info(f"Created relation: ({uuid}-[:member_of]->({id})")


class unit_of(BaseModel):

    @connect_to_db
    def save(self, db: Driver, child: str, parent: str):
        query = """MATCH (a:Unit), (b:Unit)
                WHERE a.id = $child AND b.id = $parent
                MERGE (a)-[r:unit_of]->(b)
                RETURN a, r, b
                """
        _, summary, _ = db.execute_query(query, child=child, parent=parent)
        logger.info(f"Created relation: ({child})-[:unit_of]->({parent})")


class refers_to(BaseModel):
    """The relationship between an output and a country or topic"""

    pass
