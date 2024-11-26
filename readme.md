# Ingest and Natural Language Processing of Research Outputs

The package is not yet deployed to PyPI. Only an editable (development) install is possible.

1. Provide a list of DOIs in a CSV file format `list_of_dois.csv`
2. Clone the repository `git clonehttps://github.com/ClimateCompatibleGrowth/research_index_backend.git`
2. Change directory `cd research_index_backend`
2. Install the package `pip install -e .` as an editable package (development install)
3. Obtain an OpenAIRE Graph refresh token and create a .env file with the following parameters: 
   ```MG_HOST=
      MG_PORT=
      MG_PORT_ALT=
      ORCID_NAME_SIMILARITY_THRESHOLD=
      NAME_SIMILARITY_THRESHOLD=
      OPENAIRE_API="https://api.openaire.eu"
      OPENAIRE_SERVICE="https://services.openaire.eu"
      REFRESH_TOKEN=
   ```

4. Provision Memgraph graph database and set up environment variables

   Once the VM is up and running, SSH into the VM, download and install memgraph

        $ curl -O https://download.memgraph.com/memgraph/v2.14.1/ubuntu-20.04/memgraph_2.14.1-1_amd64.deb
        $ sudo dpkg -i /memgraph_2.14.1-1_amd64.deb

5. Run the backend:

        $ research_index --help
        usage: research_index [-h] [--initialise INITIALISE] list_of_dois

        positional arguments:
        list_of_dois          Provide the path to CSV file containing a list of dois

        options:
        -h, --help            show this help message and exit
        --initialise INITIALISE
                              Deletes any existing data and creates a new database

        $ research_index list_of_dois.csv --initalise

# Development

The package is maintained using hatch.

To run the tests run:

        hatch test
