"""

These tests call the OpenAire API and require a REFRESH_TOKEN
to be defined in the environment variables.

Obtain a refresh token from https://develop.openaire.eu/personal-token
"""

import pytest
from requests.exceptions import HTTPError
from requests_cache import CachedSession

from research_index_backend.create_graph_from_doi import score_name_similarity
from research_index_backend.get_metadata import MetadataFetcher


@pytest.fixture
def session():
    return CachedSession()


@pytest.fixture
def fetcher(session):
    return MetadataFetcher(session)


def dummy_get_403(url, params, headers):
    class DummyResponse:
        status_code = 403

        def json(self):
            return {}

        def raise_for_status(self):
            http_err = HTTPError("403 Client Error: Forbidden for url: " + url)
            http_err.response = self
            raise http_err

    return DummyResponse()


class TestMetadataFetcher403:
    def test_api_403_response(self, session, monkeypatch):
        monkeypatch.setattr(session, "get", dummy_get_403)
        with pytest.raises(ValueError) as e:
            MetadataFetcher(session=session).get_metadata_from_openaire("doi")
        expected = "OpenAire refresh token is invalid or expired. \
             Please update token and try again."
        assert str(e.value) == expected


class TestNameScoring:
    def test_score_names_same(self):

        name1 = "Will Usher"
        name2 = "Will Usher"
        assert score_name_similarity(name1, name2) == 1.0

    def test_score_names_different(self):

        name1 = "Will Usher"
        name2 = "1298139487(*&^)"
        assert score_name_similarity(name1, name2) == 0.0

    def test_score_names_truncated(self):

        name1 = "Vignesh Sridha"
        name2 = "Vignesh Sridharan"
        assert score_name_similarity(name1, name2) > 0.8

    def test_score_names_reversed(self):

        name1 = "Sridharan Vignesh"
        name2 = "Vignesh Sridharan"
        assert score_name_similarity(name1, name2) == 1.0

    def test_score_names_ignore_case(self):

        name1 = "Sridharan Vignesh"
        name2 = "VIGNESH Sridharan"
        assert score_name_similarity(name1, name2) == 1.0

    def test_score_names_similar_but_different(self):

        name1 = "James Sridharan"
        name2 = "Vignesh Sridharan"
        assert score_name_similarity(name1, name2) == 0.65625

    def test_score_names_similar_fernandos_1(self):

        name1 = "Fernando Antonio Plazas"
        name2 = "Fernando Plazas-Nino"
        assert score_name_similarity(name1, name2) < 0.8

    def test_score_names_similar_fernandos_2(self):
        name1 = "Fernando Plazas-Niño"
        name2 = "Fernando Antonio Plazas-Niño"
        assert score_name_similarity(name1, name2) > 0.8

    def test_score_names_similar_fernandos_3(self):
        name1 = "Fernando Plazas-Niño"
        name2 = "Fernando Plazas-Nino"
        assert score_name_similarity(name1, name2) > 0.8

    def test_score_names_similar_fernandos_4(self):
        name1 = "Fernando ANtonio Plazas"
        name2 = "Fernando Antonio Plazas Nino"
        assert score_name_similarity(name1, name2) > 0.8
