# Initial data files

## countries.csv

This file contains all countries of the world and is used under the Open Data Commons Open Database License v1.0 from https://mledoze.github.io/countries/

## roles.csv

The possible roles within the programme (e.g. job role or position within the programme)

## subws.csv

Mapping between parent and child workstreams.  E.g. `oa1,ws1` means `ws1` is a workstream under `oa1`

## workstream.csv

List of workstreams

## wp_members.csv

Members of work streams

- **id**: id of work streams, taken from `workstream.csv`
- **name**: Full name of the author (used for matching if orcid not present)
- **role**: taken from `roles.csv`. Not currently used.
- **orcid**: The Open Researcher ID in format https://orcid.org/0000-0000-0000-0000
- **start**: DD-MM-YYYY that the members started their participation in CCG
- **end**: DD-MM-YYYY that the members ended their participation in CCG. Leave blank if still participating.

## authors.csv

Contains the list of authors to populate the database:

- **uuid**: A unique identifier for the author. This can be randomly generated using Python uuid.uuid4()
- **first_name**: The first (given) name/s of the author
- **last_name**: The surname or family name of the author
- **ORCID**: The Open Researcher ID in format https://orcid.org/0000-0000-0000-0000
- **google_scholar**: The URL for the google scholar id e.g. https://scholar.google.co.uk/citations?hl=en&user=Fd7CJmoAAAAJ
- **pubmed**: pubmed id
- **institution_url**: URL to the personal or institutional profile page for the researcher
- **gender**: The author's gender used only for internal monitoring. Does not appear publicly on web page or through API

## partner_members.csv

Links authors to project partners:

- **id**: id of the project partner (found in `project_partners.csv`)
- **name**: Full name of the author
- **orcid**: ORCID of the author. Note that authors are matched primarily on ORCID, and only match on names if orcid is absent.

## project_partners.csv

List of project partners (institutions) linked to CCG:

- **id**: Unique identifier
- **name**: Full name of the institution
- **dbpedia**: Full URL to dbpedia entry
- **ror**: The [ROR id](https://ror.org/) of the institution
- **openalex**: The OpenAlex id of the instititution
