"""

These tests call the OpenAire API and require a REFREST_TOKEN to be defined in the environment variables.

Obtain a refresh token from https://develop.openaire.eu/personal-token
"""
import pytest
from unittest.mock import patch, MagicMock
from requests import Session

from research_index_backend.create_graph_from_doi import get_output_metadata, get_personal_token


@patch.object(Session, 'get')
def test_broken_doi(mock_get):
    """An incorrect DOI should raise an error
    """
    data = MagicMock()
    data.json = """{"response": {"header": {"query": {"$": "(oaftype exact result) and ((pidclassid exact \"doi\" and pid exact \"10.1016/j.envsoft.2021\"))"}, "locale": {"$": "en_US"}, "size": {"$": 10}, "page": {"$": 1}, "total": {"$": "0"}, "fields": null}, "results": null, "browseResults": null}}"""
    mock_get.return_value = data

    broken_doi = "10.1016/j.envsoft.2021"
    with pytest.raises(ValueError) as ex:
        get_output_metadata(mock_get, broken_doi)
    expected = "DOI 10.1016/j.envsoft.2021 returned no results"
    assert str(ex.value) == expected

