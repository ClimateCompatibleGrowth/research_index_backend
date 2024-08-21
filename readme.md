# Ingest and Natural Language Processing of Research Outputs

1. Provide a list of DOIs in a CSV file format `list_of_dois.csv`
2. Install the package `pip install research_index_backend`
3. Obtain an OpenAIRE Graph token or a refresh token and set as an environment variable

        $ export TOKEN=<paste token here>
        $ export REFRESH_TOKEN=<paste token here>

4. Provision Memgraph graph database and set up environment variables

   Once the VM is up and running, SSH into the VM, download and install memgraph

        $ curl -O https://download.memgraph.com/memgraph/v2.14.1/ubuntu-20.04/memgraph_2.14.1-1_amd64.deb
        $ sudo dpkg -i /memgraph_2.14.1-1_amd64.deb

   Then setup environment variables on the local machine to point to the memgraph VM

        $ export MG_HOST=127.168.0.1
        $ export MG_PORT=7687

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

        hatch env test
