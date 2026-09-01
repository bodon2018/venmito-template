"""One reader per format. Each returns the same shape, so everything
downstream is blind to what the file looked like on disk.

Deliberately no cleaning here: a negative price or a duplicate id is read
faithfully and dealt with in the conform stage, where the decision is visible.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET


@dataclass
class ReadResult:
    entity: str
    file_format: str
    records: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def rows_read(self) -> int:
        return len(self.records) + len(self.errors)


def read_file(content: bytes, file_format: str, entity: str) -> ReadResult:
    if entity == "transactions":
        return _read_transactions_xml(content)
    if file_format == "json":
        return _read_people_json(content)
    if file_format == "yaml":
        return _read_people_yaml(content)
    if file_format == "csv":
        return _read_csv(content, entity)
    raise ValueError(f"no reader for format={file_format!r} entity={entity!r}")


# --------------------------------------------------------------------- people
def _read_people_json(content: bytes) -> ReadResult:
    """people.json: nested location, devices array, zero-padded string ids."""
    result = ReadResult(entity="people", file_format="json")
    for i, person in enumerate(json.loads(content.decode("utf-8"))):
        try:
            location = person.get("location") or {}
            result.records.append({
                "source_row": i + 1,
                "id": person["id"],
                "first_name": person.get("first_name"),
                "last_name": person.get("last_name"),
                "email": person.get("email"),
                "phone": person.get("telephone"),
                "city": location.get("City"),
                "country": location.get("Country"),
                "dob": person.get("dob"),
                "devices": list(person.get("devices") or []),
            })
        except (KeyError, TypeError) as exc:
            result.errors.append({"source_row": i + 1, "reason": str(exc), "payload": person})
    return result


_YAML_KEY = re.compile(r"\s+([A-Za-z_]+):\s*(.*)$")
_YAML_DEVICES = ("Android", "Desktop", "Iphone")


def _read_people_yaml(content: bytes) -> ReadResult:
    """people.yml: flat maps, "First Last" name, "City, Country", 0/1 device columns.

    Hand-parsed rather than via PyYAML on purpose. The file has records whose
    quoting and date format differ from the rest, and a permissive parser
    normalises exactly the anomalies we need to see.
    """
    result = ReadResult(entity="people", file_format="yaml")
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in content.decode("utf-8").splitlines():
        if line.startswith("- "):
            current = {}
            blocks.append(current)
            line = " " + line[1:]
        match = _YAML_KEY.match(line)
        if match and current is not None:
            current[match.group(1)] = match.group(2)

    for i, block in enumerate(blocks):
        try:
            result.records.append({
                "source_row": i + 1,
                "id": _unquote(block.get("id")),
                "name": _unquote(block.get("name")),
                "email": _unquote(block.get("email")),
                "phone": _unquote(block.get("phone")),
                "city_country": _unquote(block.get("city")),
                "dob": _unquote(block.get("dob")),
                "devices": [d for d in _YAML_DEVICES if _unquote(block.get(d)) == "1"],
            })
        except Exception as exc:  # noqa: BLE001 - record and continue
            result.errors.append({"source_row": i + 1, "reason": str(exc), "payload": block})
    return result


def _unquote(value: str | None) -> str | None:
    return value.strip().strip('"').strip() if isinstance(value, str) else value


# ------------------------------------------------------------------- csv rows
def _read_csv(content: bytes, entity: str) -> ReadResult:
    """promotions.csv and transfers.csv. Blanks stay as empty strings so
    'missing' is one concept rather than two (None vs '')."""
    result = ReadResult(entity=entity, file_format="csv")
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    for i, row in enumerate(reader):
        cleaned = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        cleaned["source_row"] = i + 2  # +2: header line plus 1-indexing
        result.records.append(cleaned)
    return result


# -------------------------------------------------------------- transactions
def _read_transactions_xml(content: bytes) -> ReadResult:
    """transactions.xml.

    Note the nesting: each <item> holds another <item> carrying the product
    name. Iterating children of <items> is correct; a .//item XPath would
    double-count every line.
    """
    result = ReadResult(entity="transactions", file_format="xml")
    root = ET.fromstring(content)

    for i, node in enumerate(root):
        try:
            items = []
            for line_no, line in enumerate(node.find("items") or []):
                items.append({
                    "line_no": line_no,
                    "item": line.findtext("item"),
                    "price_reported": line.findtext("price"),
                    "price_per_item": line.findtext("price_per_item"),
                    "quantity": line.findtext("quantity"),
                })
            result.records.append({
                "source_row": i + 1,
                "transaction_id": node.get("id"),
                "phone": (node.findtext("phone") or "").strip(),
                "store": node.findtext("store"),
                "date": node.findtext("date"),
                "items": items,
            })
        except Exception as exc:  # noqa: BLE001
            result.errors.append({"source_row": i + 1, "reason": str(exc),
                                  "payload": ET.tostring(node, encoding="unicode")})
    return result
