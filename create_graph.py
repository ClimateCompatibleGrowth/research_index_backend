"""Create graphs of authors, outputs and organisational units

- Authors - people who have contributed to the project by producing outputs
- Outputs - papers, reports, presentations, etc
- Units - organisational units, such as work streams, work packages, partners

"""
# Import the requirements modules
from rdflib import Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, SDO, ORG, SKOS, OWL
from rdflib import Graph
import pandas as pd
from abc import ABC


CCG = Namespace("http://127.0.0.1:5001/")
DOI = Namespace("http://doi.org/")
DBR = Namespace("http://dbpedia.org/resource/")


class GraphAbstract(ABC):

    def add_work_streams(self, df):
        """Add work_streams to the graph
        """
        raise NotImplementedError()

    def add_authors(self, df):
        """Add authors to the graph
        """
        raise NotImplementedError()

    def add_papers(self, df):
        """Add papers to the graph
        """
        raise NotImplementedError()

    def add_partners(self, df):
        """Add partners to the graph
        """
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
        """Adds the authorship links between author and paper
        """
        raise NotImplementedError()


class GraphRDF(GraphAbstract):

    def __init__(self) -> None:
        self.g = Graph()
        # Bind prefix to namespace to make it more readable
        self.g.bind('schema', SDO)
        self.g.bind('rdf', RDF)
        self.g.bind('owl', OWL)
        self.g.bind('skos', SKOS)
        self.g.bind('org', ORG)
        PROJECT = URIRef(CCG)
        self.g.add((PROJECT, RDF.type, ORG.OrganizationalCollaboration))
        self.g.add((PROJECT, SKOS.prefLabel, Literal("Climate Compatible Growth")))
        for oa in ['oa1', 'oa2', 'oa3']:
            self.g.add((PROJECT, ORG.hasUnit, CCG[f"unit/{oa}"]))
            self.g.add((CCG[f"unit/{oa}"], ORG.unitOf, PROJECT))

    def add_work_streams(self, df) -> None:
        """Add work_streams to the graph

        Turtle should look as::

            <http://climatecompatiblegrowth.com>
            org:hasUnit <http://climatecompatiblegrowth.com/unit/ws1> .

            <http://climatecompatiblegrowth.com/unit/ws1>
            rdf:type org:OrganizationalUnit ;
            skos:prefLabel "Workstream 1: National Parterships" ;
            org:unitOf <http://climatecompatiblegrowth.com> .

        """
        def add_work_stream(row):
            WS = CCG[f"unit/{row['id']}"]
            self.g.add((WS, RDF.type, ORG.OrganizationalUnit))
            self.g.add((WS, SKOS.prefLabel, Literal(row['name'])))

        df.apply(add_work_stream, axis=1)

    def add_authors(self, df):
        """Add authors to the graph
        """
        def add_author(row):
            """Adds the list of authors
            """

            def add_author_details(author_id: URIRef, row: pd.DataFrame):
                self.g.add((author_id, RDF.type, SDO.Person))
                self.g.add((author_id, SDO.givenName, Literal(row['First Name'])))
                self.g.add((author_id, SDO.familyName, Literal(row['Last Name'])))
                self.g.add((author_id, SDO.name, Literal(row['First Name'] + " " + row['Last Name'])))
                if not pd.isna(row['gender']):
                    if row['gender'] == 'male':
                        self.g.add([author_id, SDO.gender, SDO.Male])
                    elif row['gender'] == 'female':
                        self.g.add([author_id, SDO.gender, SDO.Female])

            author_id = CCG[f"authors/{row['uuid']}"]
            add_author_details(author_id, row)

        df.apply(add_author, axis=1)

    def add_papers(self, df):
        """Add papers to the graph
        """
        def add_paper(row):
            """Adds the list of papers
            """
            PAPER = CCG[f"outputs/{row['paper_uuid']}"]
            self.g.add((PAPER, RDF.type, SDO.ScholarlyArticle))
            self.g.add((PAPER, SDO.abstract, Literal(row['Abstract'])))
            if 'title' in row.keys():
                self.g.add((PAPER, SDO.title, Literal(row['title'])))
            if 'license' in row.keys():
                if row['license']:
                    self.g.add((PAPER, SDO.license, Literal(row['license'])))

        df.apply(add_paper, axis=1)

    def add_partners(self, df):

        def add_partner(row):
            """Adds consortium partner

            Turtle should look like this::

                <http://climatecompatiblegrowth.com/unit/oxford>
                rdf:type org:Organization ;
                org:memberOf <http://climatecompatiblegrowth.com>;
                rdf:sameAs dbr:University_of_Oxford ;
                skos:prefLabel "University of Oxford" .

            """
            PARTNER = CCG[f"unit/{row['id']}"]
            ORGANISATION = URIRef(CCG)
            self.g.add((PARTNER, RDF.type, ORG.Organization))
            self.g.add((PARTNER, ORG.memberOf, ORGANISATION))
            if not pd.isna(row['dbpedia']):
                self.g.add((PARTNER, OWL.sameAs, DBR[row['dbpedia']]))
            self.g.add((PARTNER, SKOS.prefLabel, Literal(row['name'])))

        df.apply(add_partner, axis=1)

    def add_sub_work_streams(self, df):
        """Add subwork_streams to the graph
        """
        def add_ws_structure(row):
            """Add workstream structure to graph
            """
            PARENT = CCG[f"unit/{row['parent']}"]
            CHILD = CCG[f"unit/{row['child']}"]
            self.g.add((PARENT, ORG.hasUnit, CHILD))
            self.g.add((CHILD, ORG.unitOf, PARENT))

        df.apply(add_ws_structure, axis=1)

    def add_work_package_members(self, df):
        """Add work package members
        """
        def add_work_package_member(row):
            """Adds work package members
            """
            WS = CCG[f"unit/{row['id']}"]
            if pd.isna(row['orcid']):
                pass
            else:
                self.g.add((WS, ORG.hasMember, URIRef(row['orcid'])))
                self.g.add((URIRef(row['orcid']), ORG.memberOf, WS))

        df.apply(add_work_package_member, axis=1)


    def add_affiliations(self, df):
        """Adds affiliations
        """
        def add_affiliation(row):
            """Adds affiliations

            Notes
            -----
            Relationship between a consortium partner and an author
            """
            PARTNER = CCG[f"unit/{row['id']}"]
            ORGANISATION = URIRef("http://climatecompatiblegrowth.com")
            if pd.isna(row['orcid']):
                pass
            else:
                self.g.add((PARTNER, ORG.hasMember, URIRef(row['orcid'])))
                self.g.add((URIRef(row['orcid']), ORG.memberOf, PARTNER))
        df.apply(add_affiliation, axis=1)


    def add_authorship_relation(self, df):
        def add_authorship_relation(row):
            """Adds the authorship links between author and paper
            """
            PAPER = CCG[f"outputs/{row['paper_uuid']}"]
            AUTHOR = CCG[f"authors/{row['uuid']}"]
            self.g.add((PAPER, SDO.author, AUTHOR))

        df.apply(add_authorship_relation, axis=1)

def main(graph: GraphAbstract):
    """Create the graph of authors and papers

    """
    work_streams = pd.read_excel('project_partners.xlsx', sheet_name='workstream')
    graph.add_work_streams(work_streams)

    structure = pd.read_excel('project_partners.xlsx', sheet_name='subws')
    graph.add_sub_work_streams(structure)

    work_package_members = pd.read_excel('project_partners.xlsx', sheet_name='wp_members')
    graph.add_work_package_members(work_package_members)

    df = pd.read_excel('project_partners.xlsx', sheet_name='partners')
    graph.add_partners(df)

    df = pd.read_excel('project_partners.xlsx', sheet_name='org_members')
    graph.add_affiliations(df)

    authors = pd.read_csv('data/authors.csv')
    graph.add_authors(authors)

    papers = pd.read_csv('data/papers.csv')
    graph.add_papers(papers)

    relations = pd.read_csv('data/relations.csv')
    graph.add_authorship_relation(relations)

    return graph.g


if __name__ == "__main__":
    graph = GraphRDF()
    g = main(graph)
    g.serialize('authors.ttl')