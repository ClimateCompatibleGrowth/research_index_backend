from html import unescape
from re import compile, sub
from unicodedata import normalize

CLEANR = compile("<.*?>")


def clean_html(raw_html):
    """Remove HTML markup from a string and normalize UTF8"""
    cleantext = (
        sub(CLEANR, "", raw_html)
        .replace("\xa0", " ")
        .replace("�", " ")
        .replace("&amp;", "&")
        .replace("\u202f", " ")
    )
    return unescape(normalize("NFC", cleantext))
