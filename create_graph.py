"""Create a RDF graph of authors and papers
"""
# Import the requirements modules
from rdflib import Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, SDO, ORG, SKOS, OWL
from rdflib import Graph
import pandas as pd

def main():
    """
    """
    CCG = Namespace("http://climatecompatiblegrowth.com/")
    DOI = Namespace("http://doi.org/")
    DBR = Namespace("http://dbpedia.org/resource/")

    g = Graph()

    # Bind prefix to namespace to make it more readable
    g.bind('schema', SDO)
    g.bind('rdf', RDF)
    g.bind('owl', OWL)
    g.bind('skos', SKOS)
    g.bind('org', ORG)

    PROJECT = URIRef("http://climatecompatiblegrowth.com/id")
    g.add((PROJECT, RDF.type, ORG.OrganizationalCollaboration))
    g.add((PROJECT, SKOS.prefLabel, Literal("Climate Compatible Growth")))
    for oa in ['oa1', 'oa2', 'oa3']:
        g.add((PROJECT, ORG.hasUnit, CCG[f"id/{oa}"]))
        g.add((CCG[f"id/{oa}"], ORG.unitOf, PROJECT))

    def add_workstream(df):
        """Add a workstream to the graph

        Turtle should look as::

            <http://climatecompatiblegrowth.com/id>
            org:hasUnit <http://climatecompatiblegrowth.com/id/ws1> .

            <http://climatecompatiblegrowth.com/id/ws1>
            rdf:type org:OrganizationalUnit ;
            skos:prefLabel "Workstream 1: National Parterships" ;
            org:unitOf <http://climatecompatiblegrowth.com/id> .

        """
        WS = CCG[f"id/{df['id']}"]
        # g.add((PROJECT, ORG.hasUnit, WS))
        g.add((WS, RDF.type, ORG.OrganizationalUnit))
        g.add((WS, SKOS.prefLabel, Literal(df['name'])))
        # g.add((WS, ORG.unitOf, PROJECT))

    workstream = pd.read_excel('project_partners.xlsx', sheet_name='workstream')
    workstream.apply(add_workstream, axis=1)

    def add_ws_structure(row):
        """Add workstream structure to graph
        """
        PARENT = CCG[f"id/{row['parent']}"]
        CHILD = CCG[f"id/{row['child']}"]
        g.add((PARENT, ORG.hasUnit, CHILD))
        g.add((CHILD, ORG.unitOf, PARENT))

    structure = pd.read_excel('project_partners.xlsx', sheet_name='subws')
    structure.apply(add_ws_structure, axis=1)

    def add_wp_members(df):
        """Adds work package members
        """
        WS = CCG[f"id/{df['id']}"]
        if pd.isna(df['orcid']):
            pass
        else:
            g.add((WS, ORG.hasMember, URIRef(df['orcid'])))
            g.add((URIRef(df['orcid']), ORG.memberOf, WS))

    wp_members = pd.read_excel('project_partners.xlsx', sheet_name='wp_members')
    wp_members.apply(add_wp_members, axis=1)

    def add_partners(df):
        """Adds consortium partners

        Turtle should look like this::

            <http://climatecompatiblegrowth.com/id/oxford>
            rdf:type org:Organization ;
            org:memberOf <http://climatecompatiblegrowth.com/id>;
            rdf:sameAs dbr:University_of_Oxford ;
            skos:prefLabel "University of Oxford" .

        """
        PARTNER = CCG[f"id/{df['id']}"]
        ORGANISATION = URIRef("http://climatecompatiblegrowth.com/id")
        g.add((PARTNER, RDF.type, ORG.Organization))
        g.add((PARTNER, ORG.memberOf, ORGANISATION))
        if not pd.isna(df['dbpedia']):
            g.add((PARTNER, OWL.sameAs, DBR[df['dbpedia']]))
        g.add((PARTNER, SKOS.prefLabel, Literal(df['name'])))

    partners = pd.read_excel('project_partners.xlsx', sheet_name='partners')
    partners.apply(add_partners, axis=1)

    def add_affiliations(df):
        """Adds affiliations
        """
        PARTNER = CCG[f"id/{df['id']}"]
        ORGANISATION = URIRef("http://climatecompatiblegrowth.com/id")
        if pd.isna(df['orcid']):
            pass
        else:
            g.add((PARTNER, ORG.hasMember, URIRef(df['orcid'])))
            g.add((URIRef(df['orcid']), ORG.memberOf, PARTNER))
    affiliations = pd.read_excel('project_partners.xlsx', sheet_name='org_members')
    affiliations.apply(add_affiliations, axis=1)


    def add_author(df):
        """Adds the list of authors
        """

        def add_author_details(g: Graph, author_id: URIRef, df: pd.DataFrame):
            g.add((author_id, RDF.type, SDO.Person))
            g.add((author_id, SDO.givenName, Literal(df['First Name'])))
            g.add((author_id, SDO.familyName, Literal(df['Last Name'])))
            g.add((author_id, SDO.name, Literal(df['First Name'] + " " + df['Last Name'])))
            if not pd.isna(df['gender']):
                if df['gender'] == 'male':
                    g.add([author_id, SDO.gender, SDO.Male])
                elif df['gender'] == 'female':
                    g.add([author_id, SDO.gender, SDO.Female])

        if not pd.isna(df['Orcid']):
            author_id = URIRef(df['Orcid'])
            add_author_details(g, author_id, df)
        else:
            author_id = CCG[df['uuid']]
            add_author_details(g, author_id, df)

    authors = pd.read_csv('data/authors.csv')
    authors.apply(add_author, axis=1)

    def add_paper(df):
        """Adds the list of papers
        """
        PAPER = DOI[df['DOI']]
        g.add((PAPER, RDF.type, SDO.ScholarlyArticle))
        g.add((PAPER, SDO.abstract, Literal(df['Abstract'])))
        if 'title' in df.keys():
            g.add((PAPER, SDO.title, Literal(df['title'])))
        if 'license' in df.keys():
            if df['license']:
                g.add((PAPER, SDO.license, Literal(df['license'])))

    papers = pd.read_csv('data/papers.csv')
    papers.apply(add_paper, axis=1)

    def add_relations(df):
        """Adds the authorship links between author and paper
        """
        PAPER = DOI[df['DOI']]
        AUTHOR = CCG[df['uuid']]

        author = authors[authors['uuid'] == df['uuid']]['Orcid'].values[0]
        if pd.isna(author):
            g.add((PAPER, SDO.author, AUTHOR))
        else:
            g.add((PAPER, SDO.author, URIRef(author)))

    relations = pd.read_csv('data/relations.csv')
    relations.apply(add_relations, axis=1)

    return g


if __name__ == "__main__":
    g = main()
    g.serialize('authors.ttl')