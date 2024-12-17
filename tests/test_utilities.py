from research_index_backend.utils import clean_html


def test_clean_html():
    """Ensure that text is cleaned of html and utf character codes"""
    text = "<jats:title>Abstract</jats:title><jats:p>Beneficiaries</jats:p>"
    expected = "AbstractBeneficiaries"
    actual = clean_html(text)

    assert actual == expected


def test_clean_utf():
    text = "renewa\u00adble"
    expected = "renewa ble"
    actual = clean_html(text)

    assert actual == expected
