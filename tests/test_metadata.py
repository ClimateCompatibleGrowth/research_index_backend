"""

These tests call the OpenAire API and require a REFRESH_TOKEN to be defined in the environment variables.

Obtain a refresh token from https://develop.openaire.eu/personal-token
"""

import pytest
from requests_cache import CachedSession

from research_index_backend.create_graph_from_doi import (
    get_output_metadata,
    score_name_similarity,
)


@pytest.mark.skip(reason="Requires access to OpenAire Graph API")
def test_broken_doi():
    """An incorrect DOI should raise an error"""
    s = CachedSession()

    broken_doi = "10.1dd016/j.envsoft.2021"
    with pytest.raises(ValueError) as ex:
        get_output_metadata(s, broken_doi)
    expected = "DOI 10.1dd016/j.envsoft.2021 returned no results"
    assert str(ex.value) == expected


def test_score_names_same():

    name1 = "Will Usher"
    name2 = "Will Usher"
    assert score_name_similarity(name1, name2) == 1.0


def test_score_names_different():

    name1 = "Will Usher"
    name2 = "1298139487(*&^)"
    assert score_name_similarity(name1, name2) == 0.0


def test_score_names_truncated():

    name1 = "Vignesh Sridha"
    name2 = "Vignesh Sridharan"
    assert score_name_similarity(name1, name2) > 0.8


def test_score_names_reversed():

    name1 = "Sridharan Vignesh"
    name2 = "Vignesh Sridharan"
    assert score_name_similarity(name1, name2) == 1.0


def test_score_names_ignore_case():

    name1 = "Sridharan Vignesh"
    name2 = "VIGNESH Sridharan"
    assert score_name_similarity(name1, name2) == 1.0


def test_score_names_similar_but_different():

    name1 = "James Sridharan"
    name2 = "Vignesh Sridharan"
    assert score_name_similarity(name1, name2) == 0.65625


def test_score_names_similar_fernandos_1():

    name1 = "Fernando Antonio Plazas"
    name2 = "Fernando Plazas-Nino"
    assert score_name_similarity(name1, name2) < 0.8


def test_score_names_similar_fernandos_2():
    name1 = "Fernando Plazas-Niño"
    name2 = "Fernando Antonio Plazas-Niño"
    assert score_name_similarity(name1, name2) > 0.8


def test_score_names_similar_fernandos_3():
    name1 = "Fernando Plazas-Niño"
    name2 = "Fernando Plazas-Nino"
    assert score_name_similarity(name1, name2) > 0.8


def test_score_names_similar_fernandos_4():
    name1 = "Fernando ANtonio Plazas"
    name2 = "Fernando Antonio Plazas Nino"
    assert score_name_similarity(name1, name2) > 0.8
