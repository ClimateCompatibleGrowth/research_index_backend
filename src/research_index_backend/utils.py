from re import compile, sub, IGNORECASE
from html import unescape
from unicodedata import normalize
from codecs import decode

CLEANR = compile('<.*?>')

def clean_html(raw_html):
    """Remove HTML markup from a string and normalize UTF8
    """
    cleantext = sub(CLEANR, '', raw_html)
    return unescape(normalize('NFC', cleantext))