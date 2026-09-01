"""Field-level normalisation shared by both people sources.

These exist because the two people files encode the same facts differently:
"0001" vs 1, "Jamie Bright" vs first_name+last_name, "Montreal, Canada" vs a
nested object, "05/20/2000" vs "May 20, 2000".
"""
from __future__ import annotations

import datetime as dt

DEVICES = ("Android", "Desktop", "Iphone")
_DOB_FORMATS = ("%m/%d/%Y", "%B %d, %Y")


def parse_id(value) -> int:
    """'0001' -> 1. Zero-padding is presentation, not identity."""
    return int(str(value).strip().strip('"'))


def parse_dob(value) -> dt.date | None:
    if not value:
        return None
    text = str(value).strip().strip('"')
    for fmt in _DOB_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def split_name(value: str) -> tuple[str, str]:
    """'Jamie Bright' -> ('Jamie', 'Bright'); multi-word surnames stay intact."""
    first, _, last = str(value).strip().strip('"').partition(" ")
    return first.strip(), last.strip()


def split_city(value: str) -> tuple[str, str | None]:
    """'Montreal, Canada' -> ('Montreal', 'Canada').

    Partitioned from the right so a city name containing a comma survives.
    """
    text = str(value).strip().strip('"')
    city, _, country = text.rpartition(", ")
    return (city.strip(), country.strip()) if city else (text, None)


def normalize_email(value: str | None) -> str:
    return (value or "").strip().strip('"').lower()


def normalize_phone(value: str | None) -> str:
    return (value or "").strip().strip('"')
