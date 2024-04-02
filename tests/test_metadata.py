"""

These tests call the OpenAire API and require a REFREST_TOKEN to be defined in the environment variables.

Obtain a refresh token from https://develop.openaire.eu/personal-token
"""
import pytest

from research_index_backend.create_graph_from_doi import get_output_metadata, get_personal_token

@pytest.fixture
def get_token():
    get_personal_token()


def test_broken_doi(get_token):
    """An incorrect DOI should raise an error
    """

    broken_doi = "10.1016/j.envsoft.2021"
    with pytest.raises(ValueError) as ex:
        get_output_metadata(broken_doi)
    expected = "DOI 10.1016/j.envsoft.2021 returned no results"
    assert str(ex.value) == expected

