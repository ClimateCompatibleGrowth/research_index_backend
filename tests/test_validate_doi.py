from pytest import fixture

from research_index_backend.create_graph_from_doi import validate_dois


@fixture
def invalid():
    return [
        "10.1371/journal.pclm.0000331",
        "",
        "doi.org/10.5281/zenodo.11395843",
        "doi.org/10.5281/zenodo.11396572",
        "10.5281/zenodo.11396370",
        "https://doi.org/10.5281/zenodo.11395518",
    ]


@fixture
def expected():
    return [
        "10.1371/journal.pclm.0000331",
        "10.5281/zenodo.11395843",
        "10.5281/zenodo.11396572",
        "10.5281/zenodo.11396370",
        "10.5281/zenodo.11395518",
    ]


class TestValidateDois:

    def test_validate_dois(self, invalid, expected):

        actual = validate_dois(invalid)
        assert actual["valid"] == expected
        assert actual["invalid"] == []
