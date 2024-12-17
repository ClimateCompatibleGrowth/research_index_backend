"""Create graphs of authors, outputs and organisational units

- Authors - people who have contributed to the project by producing outputs
- Outputs - papers, reports, presentations, etc
- Units - organisational units, such as work streams, work packages, partners

"""

from abc import ABC
from os.path import join
from typing import Dict

import pandas as pd
from neo4j import Driver

from .db.session import connect_to_db
from .models import (
    AnonymousAuthor,
    Article,
    Author,
    Country,
    Partner,
    Workstream,
    author_of,
    member_of,
    unit_of,
)
from .utils import split_names


class GraphAbstract(ABC):
    def add_work_streams(self, df):
        """Add work_streams to the graph"""
        raise NotImplementedError()

    def add_authors(self, df):
        """Add authors to the graph"""
        raise NotImplementedError()

    def add_papers(self, df):
        """Add papers to the graph"""
        raise NotImplementedError()

    def add_partners(self, df):
        """Add partners to the graph"""
        raise NotImplementedError()

    def add_sub_work_streams(self, df):
        """Add sub work streams to the graph

        Sub work streams describe how workstreams are broken down into smaller
        units of work
        """
        raise NotImplementedError()

    def add_work_package_members(self, df):
        """Add work package members

        Add the relationships between authors and work packages
        """
        raise NotImplementedError()

    def add_affiliations(self, df):
        """Add work package members

        Add the relationships between authors and consortium partners
        """
        raise NotImplementedError()

    def add_authorship_relation(self, df):
        """Adds the authorship links between author and paper"""
        raise NotImplementedError()

    def add_countries(self, df):
        """Add countries"""
        raise NotImplementedError()


class GraphMemGraph(GraphAbstract):
    def __init__(self) -> None:

        self.authors: Dict[str, Author] = {}
        self.outputs: Dict[str, Article] = {}
        self.work_streams: Dict[str, Workstream] = {}
        self.partners: Dict[str, Partner] = {}
        self.countries: Dict[str, Country] = {}

    def add_authors(self, df):
        def add_author(row):
            if pd.isna(row["Orcid"]):
                self.authors[row["uuid"]] = Author(
                    uuid=row["uuid"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                ).save()
            else:
                self.authors[row["uuid"]] = Author(
                    uuid=row["uuid"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    orcid=row["Orcid"],
                ).save()

        df.apply(add_author, axis=1)

    def add_countries(self, df):
        def add_country(row: pd.Series):
            print(f"Adding Country: {row['name.official']} to the database")
            dbpedia = "_".join(row["name.official"].split(" "))

            lat, lon = row["latlng"].split(",")

            country = Country(
                id=row["cca3"],
                name=row["name.common"],
                official_name=row["name.official"],
                dbpedia=dbpedia,
                latitude=lat,
                longitude=lon,
            )
            self.countries[row["name.common"]] = country.save()

        df.apply(add_country, axis=1)

    def add_papers(self, df):
        def add_paper(row):
            uuid = row["paper_uuid"]
            self.outputs[uuid] = Article(
                uuid=uuid,
                doi=row["DOI"],
                title=row["title"],
                abstract=row["Abstract"],
            ).save()

        df.apply(add_paper, axis=1)

    def add_authorship_relation(self, df):
        def add_authorship(row):
            author_uuid = row["uuid"]
            paper_uuid = row["paper_uuid"]

            loaded_author = Author(uuid=author_uuid).load()
            loaded_output = Article(uuid=paper_uuid).load()

            author_of(
                _start_node_id=loaded_author._id,
                _end_node_id=loaded_output._id,
            ).save()

        df.apply(add_authorship, axis=1)

    def add_work_streams(self, df):
        """Add work_streams to the graph"""

        def add_work_stream(row):
            self.work_streams[row["id"]] = Workstream(
                id=row["id"], name=row["name"]
            ).save()

        df.apply(add_work_stream, axis=1)

    def add_sub_work_streams(self, df):
        """Add sub work-streams to the graph"""

        def add_ws_structure(row):
            """Add work-stream structure to graph"""
            unit_of().save(child=row["child"], parent=row["parent"])

        df.apply(add_ws_structure, axis=1)

    def add_work_package_members(self, df):
        """Add work package members"""

        def add_work_package_member(row):
            """Adds work package members"""

            if pd.isna(row["orcid"]):
                first_name, last_name = split_names(row["name"])
                author = AnonymousAuthor(
                    first_name=first_name, last_name=last_name
                )
                author_uuid = author.match_name()
            else:
                first_name, last_name = split_names(row["name"])
                author = AnonymousAuthor(
                    first_name=first_name,
                    last_name=last_name,
                    orcid=row["orcid"],
                )
                author_uuid = author.match_orcid()

            if author_uuid:
                relation = member_of()
                relation.save(uuid=author_uuid, id=row["id"])
            else:
                print(f"Could not find {row['name']} in the database")

        df.apply(add_work_package_member, axis=1)

    def add_partners(self, df):
        def add_partner(row):
            """Adds consortium partner"""
            id = row["id"]
            self.partners[id] = Partner(
                id=id,
                name=row["name"],
                dbpedia=str(row.get("dbpedia", None)),
                ror=str(row.get("ror", None)),
                openalex=str(row.get("openalex", None)),
            ).save()

        df.apply(add_partner, axis=1)

    def add_affiliations(self, df):
        """Adds affiliations"""

        def add_affiliation(row):
            """Adds affiliations

            Notes
            -----
            Relationship between a consortium partner and an author
            """
            if pd.isna(row["orcid"]):
                first_name, last_name = split_names(row["name"])
                author = AnonymousAuthor(
                    first_name=first_name, last_name=last_name
                )
                results = author.match_name()
            else:
                first_name, last_name = split_names(row["name"])
                author = AnonymousAuthor(
                    first_name=first_name,
                    last_name=last_name,
                    orcid=row["orcid"],
                )
                results = author.match_orcid()

            if results:
                member_of().save(uuid=results, id=row["id"])

        df.apply(add_affiliation, axis=1)

    @connect_to_db
    def add_country_relations(self, db: Driver):
        query = """
            MATCH (c:Country)
            CALL {
            WITH c
            MATCH (o:Output)
            WHERE o.abstract CONTAINS c.name
            AND NOT exists((o:Output)-[:refers_to]->(c:Country))
            CREATE (o)-[r:refers_to]->(c)
            RETURN r
            }
            RETURN r
            """
        db.execute_query(query)

    @connect_to_db
    def create_constraints(self, db: Driver):
        query = [
            "CREATE CONSTRAINT ON (n:Output) ASSERT n.doi IS UNIQUE;",
            "CREATE CONSTRAINT ON (n:Output) ASSERT n.uuid IS UNIQUE;",
            "CREATE CONSTRAINT ON (a:Author) ASSERT a.uuid IS UNIQUE;",
            "CREATE CONSTRAINT ON (a:Author) ASSERT a.orcid IS UNIQUE;",
            "CREATE INDEX ON :Author(uuid);",
            "CREATE INDEX ON :Output(uuid);",
            "CREATE INDEX ON :Country(id);",
            "CREATE INDEX ON :Output(result_type);",
        ]
        for q in query:
            with db.session() as session:
                session.run(q)


def load_initial_data(file_path: str):
    """Loads initial data from ``file_path``

    Expects csv files:
    - workstream.csv
    - subws.csv
    - project_partners.csv
    - authors.csv
    - wp_members.csv
    - partner_members.csv
    - countries.csv
    """

    memgraph = GraphMemGraph()

    work_streams = pd.read_csv(join(file_path, "workstream.csv"))
    memgraph.add_work_streams(work_streams)

    structure = pd.read_csv(join(file_path, "subws.csv"))
    memgraph.add_sub_work_streams(structure)

    df = pd.read_csv(join(file_path, "project_partners.csv"))
    memgraph.add_partners(df)

    authors = pd.read_csv(join(file_path, "authors.csv"))
    memgraph.add_authors(authors)

    work_package_members = pd.read_csv(join(file_path, "wp_members.csv"))
    memgraph.add_work_package_members(work_package_members)

    df = pd.read_csv(join(file_path, "partner_members.csv"))
    memgraph.add_affiliations(df)

    df = pd.read_csv(join(file_path, "countries.csv"), quotechar='"')
    memgraph.add_countries(df)

    memgraph.add_country_relations()
    memgraph.create_constraints()
