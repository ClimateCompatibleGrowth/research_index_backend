# Initial data files

## countries.csv

This file contains all countries of the world and is used under the Open Data Commons Open Database License v1.0 from https://mledoze.github.io/countries/

## roles.csv

The possible roles within the programme (e.g. job role or position within the programme)

## subws.csv



## workstream.csv



## wp_members.csv

## authors.csv

Contains the list of authors to populate the database:

uuid
    A unique identifier for the author. This can be randomly generated using Python uuid.uuid4()
first_name
    The first (given) name/s of the author
last_name
    The surname or family name of the author
ORCID
    The Open Researcher ID in format https://orcid.org/0000-0000-0000-0000
google_scholar
    The URL for the google scholar id e.g. https://scholar.google.co.uk/citations?hl=en&user=Fd7CJmoAAAAJ
pubmed
institution_url
    URL to the personal or institutional profile page for the researcher
gender
    The author's gender

## partner_members.csv

Links authors to project partners:

id
    Foreign id of the project partner (found in `project_partners.csv`)
name
    Full name of the author
orcid
    ORCID of the author

## project_partners.csv

List of project partners (institutions) linked to CCG:

id
    Unique identifier
name
    Full name of the institution
dbpedia
    Full URL to dbpedia entry
ror
    The [ROR id](https://ror.org/) of the institution
