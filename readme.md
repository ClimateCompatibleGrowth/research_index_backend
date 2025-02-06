# Ingest and Natural Language Processing of Research Outputs

The package is not yet deployed to PyPI. Only an editable (development) install is possible.

1. Provide a list of DOIs in a CSV file format `list_of_dois.csv`
2. Clone the repository `git clonehttps://github.com/ClimateCompatibleGrowth/research_index_backend.git`
3. Change directory `cd research_index_backend`
4. Install the package `pip install -e .` as an editable package (development install)
5. Obtain an OpenAIRE Graph refresh token and create a .env file with the following parameters: 
   ```MG_HOST=
      MG_PORT=
      MG_PORT_ALT=
      MG_USER=
      MG_PASS=
      ORCID_NAME_SIMILARITY_THRESHOLD=
      NAME_SIMILARITY_THRESHOLD=
      OPENAIRE_API="https://api.openaire.eu"
      OPENAIRE_SERVICE="https://services.openaire.eu"
      REFRESH_TOKEN=
   ```

6. Provision Memgraph graph database and set up environment variables

   Once the VM is up and running, SSH into the VM, download and install memgraph

        $ curl -O https://download.memgraph.com/memgraph/v2.14.1/ubuntu-20.04/memgraph_2.14.1-1_amd64.deb
        $ sudo dpkg -i /memgraph_2.14.1-1_amd64.deb

7. Run the backend:

        research_index --help
        usage: research_index [-h] [-i] [-l LIMIT] [-u] list_of_dois
        
        positional arguments:
          list_of_dois          Path to CSV file containing list of DOIs

        options:
          -h, --help            Show this help message and exit
          -i, --initialise      Delete existing data and create new database
          -l, --limit N         Limit number of DOIs to process (default: 50)
          -u, --update-metadata Update metadata for existing DOIs
          -w, --write-metadata  Save JSON responses to disk 

        Examples:
          -> Process 10 DOIs from file:
          $ research_index list_of_dois.csv -l 10  # Process 10 DOIs from file

          -> Update metadata for existing DOIs and save metadata
          $ research_index list_of_dois.csv --update-metadata --write-metadata

# Development

The package is maintained using hatch.

To run the tests run:

        hatch test
