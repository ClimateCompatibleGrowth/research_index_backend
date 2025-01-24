"""

These tests call the OpenAire API and require a REFRESH_TOKEN to be defined in the environment variables.

Obtain a refresh token from https://develop.openaire.eu/personal-token
"""

import pytest
from requests_cache import CachedSession

from research_index_backend.get_metadata import MetadataFetcher
from research_index_backend.create_graph_from_doi import score_name_similarity

@pytest.fixture
def session():
    return CachedSession()

@pytest.fixture
def fetcher(session):
    return MetadataFetcher(session)

class TestMetadataFetcher:
    @pytest.mark.skip(reason="Requires access to OpenAire Graph API")
    def test_broken_doi(self, fetcher):
        """An incorrect DOI should raise an error"""
        broken_doi = "10.1dd016/j.envsoft.2021"
        with pytest.raises(ValueError) as ex:
            fetcher.get_output_metadata(broken_doi)
        expected = "DOI 10.1dd016/j.envsoft.2021 returned no results"
        assert str(ex.value) == expected

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
