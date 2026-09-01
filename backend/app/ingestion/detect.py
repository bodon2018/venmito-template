"""Work out what an uploaded file is, from its bytes rather than its name.

Filenames are not trustworthy on an upload endpoint, so the extension is only
used as a tie-breaker. Entity detection is by field signature: the four source
files have distinct column sets.
"""
from __future__ import annotations

import csv
import io
import json

SUPPORTED_FORMATS = ("json", "yaml", "csv", "xml")
ENTITIES = ("people", "promotions", "transactions", "transfers")

# A file is this entity if it has every field in the set.
ENTITY_SIGNATURES = {
    "promotions": {"client_email", "telephone", "promotion", "responded"},
    "transfers": {"sender_id", "recipient_id", "amount", "date"},
    "people": {"id"},  # checked last; people files vary the most between formats
}


def detect_format(content: bytes, filename: str = "") -> str:
    """Return one of SUPPORTED_FORMATS, or raise ValueError."""
    head = content.lstrip()[:2048]
    text = head.decode("utf-8", errors="replace")

    if text.startswith("<?xml") or text.startswith("<"):
        return "xml"
    if text.startswith("{") or text.startswith("["):
        return "json"
    # A YAML list of maps opens with "- key:"; CSV opens with a delimited header.
    if text.startswith("- ") or text.startswith("---"):
        return "yaml"

    try:
        dialect = csv.Sniffer().sniff(text.split("\n\n")[0][:1024])
        if dialect.delimiter in ",;\t|":
            return "csv"
    except csv.Error:
        pass

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("yml", "yaml"):
        return "yaml"
    if ext in SUPPORTED_FORMATS:
        return ext
    raise ValueError(f"unrecognised file format for {filename!r}")


def detect_entity(content: bytes, file_format: str, filename: str = "") -> str:
    """Return one of ENTITIES, or raise ValueError."""
    if file_format == "xml":
        # transactions.xml is the only XML source.
        return "transactions"

    fields: set[str] = set()
    text = content.decode("utf-8", errors="replace")

    if file_format == "csv":
        reader = csv.reader(io.StringIO(text))
        fields = set(next(reader, []))
    elif file_format == "json":
        data = json.loads(text)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            fields = set(data[0])
    elif file_format == "yaml":
        # Read keys off the first block without a YAML parser (see readers.py).
        for line in text.splitlines():
            stripped = line.lstrip("- ").strip()
            if line.startswith("- ") and fields:
                break
            if ":" in stripped:
                fields.add(stripped.split(":", 1)[0].strip())

    for entity, signature in ENTITY_SIGNATURES.items():
        if signature <= fields:
            return entity

    # Fall back to the filename only when the content is genuinely ambiguous.
    lowered = filename.lower()
    for entity in ENTITIES:
        if entity[:-1] in lowered or entity in lowered:
            return entity
    raise ValueError(f"cannot determine entity for {filename!r} (fields: {sorted(fields)})")
