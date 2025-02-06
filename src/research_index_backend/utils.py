from html import unescape
from re import compile, sub
from unicodedata import normalize

CLEANR = compile("<.*?>")


def clean_html(raw_html):
    """Remove HTML markup from a string and normalize UTF8"""
    cleantext = (
        sub(CLEANR, "", raw_html)
        .replace("\n", " ")
        .replace("\xa0", " ")
        .replace("\u00ad", " ")
        .replace("�", " ")
        .replace("&amp;", "&")
        .replace("\u202f", " ")
        .replace("    ", " ")
        .replace("   ", " ")
        .replace("  ", " ")
        .strip()
    )
    return unescape(normalize("NFC", cleantext))


def split_names(name) -> tuple[str, str]:
    """Split names semi-intelligently"""
    names = name.split(" ")
    if len(names) == 1:
        return ("", names)
    if len(names) <= 2:
        return (names[0], names[1])
    if len(names) > 2:
        return (names[0], " ".join(names[1:]))
    else:
        raise ValueError("Could not determine how to split {names}")
