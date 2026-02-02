import pytest

from research_index_backend.doi import DOIManager

valid_dois = [
    "10.5281/zenodo.8140241",
    "10.5281/ZENODO.8140241",
    "10.5281/zenodo.8141555",
    "10.5281/zenodo.8140100",
    "10.5281/zenodo.8140153",
    "10.5281/zenodo.8139242",
    "10.5281/zenodo.8140226",
    "10.5281/zenodo.8140289",
]

invalid_dois = [
    "",
    "non_empty_string",
    "10.5281zenodo.8140226",
    "10.5281/zenodo",
]

raw_dois = [
    "10.1371/journal.pclm.0000331",
    "doi.org/10.5281/zenodo.11395843",
    "doi.org/10.5281/zenodo.11396572",
    "10.5281/zenodo.11396370",
    "https://doi.org/10.5281/zenodo.11395518",
    "10.5281/zenodo.11395518.",
    "  10.5281/zenodo.11395519  ",
]

cleaned_dois = [
    "10.1371/journal.pclm.0000331",
    "10.5281/zenodo.11395843",
    "10.5281/zenodo.11396572",
    "10.5281/zenodo.11396370",
    "10.5281/zenodo.11395518",
    "10.5281/zenodo.11395518",
    "10.5281/zenodo.11395519",
]


def test_valid_dois():
    """Test that valid DOI patterns are correctly identified."""
    doi_manager = DOIManager(
        valid_dois, limit=len(valid_dois), update_metadata=False
    )
    doi_manager.pattern_check()
    for doi in doi_manager.doi_tracker:
        assert doi_manager.doi_tracker[doi].valid_pattern


def test_invalid_dois():
    """Test that invalid DOI patterns are correctly identified."""
    doi_manager = DOIManager(
        invalid_dois, limit=len(invalid_dois), update_metadata=False
    )
    doi_manager.pattern_check()
    for doi in doi_manager.doi_tracker:
        assert not doi_manager.doi_tracker[doi].valid_pattern


def test_mixed_dois():
    """Test processing of mixed valid and invalid DOIs."""
    doi_manager = DOIManager(
        valid_dois + invalid_dois,
        limit=len(valid_dois + invalid_dois),
        update_metadata=False,
    )
    doi_manager.pattern_check()
    valid_count = sum(
        1 for doi in doi_manager.doi_tracker.values() if doi.valid_pattern
    )
    invalid_count = sum(
        1 for doi in doi_manager.doi_tracker.values() if not doi.valid_pattern
    )

    assert valid_count == len(valid_dois)
    assert invalid_count == len(invalid_dois)


def test_doi_objects():
    """Test DOI object initialization and default values."""
    doi_manager = DOIManager(
        valid_dois, limit=len(valid_dois), update_metadata=False
    )
    doi_manager.pattern_check()

    for doi in doi_manager.doi_tracker:
        doi_obj = doi_manager.doi_tracker[doi]
        assert doi_obj.doi == doi, "DOI string mismatch"
        assert doi_obj.valid_pattern, "Pattern should be valid"
        assert not doi_obj.already_exists, "Should not exist by default"
        assert (
            not doi_obj.openalex_metadata
        ), "Should not have OpenAlex metadata"
        assert (
            not doi_obj.openaire_metadata
        ), "Should not have OpenAire metadata"
        assert not doi_obj.ingestion_success, "Should not be ingested"


def test_pattern_cleaner():
    """Test DOI pattern cleaning functionality."""
    doi_manager = DOIManager(
        raw_dois, limit=len(raw_dois), update_metadata=False
    )
    assert doi_manager.list_of_dois == cleaned_dois, "DOI cleaning failed"


def test_case_insensitive_pattern():
    """Test that DOI pattern matching is case insensitive."""
    doi_manager = DOIManager(
        ["10.5281/zenodo.8140241", "10.5281/ZENODO.8140241"],
        limit=2,
        update_metadata=False,
    )
    doi_manager.pattern_check()
    assert all(doi.valid_pattern for doi in doi_manager.doi_tracker.values())


def test_invalid_limit():
    """Test that providing an invalid (negative) limit raises a ValueError."""
    with pytest.raises(ValueError):
        # Expect DOIManager to raise an error upon invalid limit input.
        doi_manager = DOIManager(
            ["10.5281/zenodo.8140241"], limit=-5, update_metadata=False
        )
        doi_manager.validate_dois()


def test_wrong_type_for_doi_list():
    """Test that providing a wrong type (non-iterable) for DOI list raises a TypeError."""
    with pytest.raises(TypeError):
        # Passing a single string instead of a list should raise a TypeError.
        DOIManager("10.5281/zenodo.8140241", limit=1, update_metadata=False)


def test_wrong_tyoe_for_update_metadata():
    """Test that providing a wrong type for update_metadata raises a TypeError."""
    with pytest.raises(TypeError):
        # Passing a string instead of a boolean should raise a TypeError.
        DOIManager(
            ["10.5281/zenodo.8140241"], limit=1, update_metadata="False"
        )


# TODO: should the elements of the list of DOIs be checked for type or this is handled in the entry point?
