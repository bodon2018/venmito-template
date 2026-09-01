"""Readers and detection. No database involved."""
import pytest

from app.ingestion import detect_entity, detect_format, read_file

EXPECTED = {
    "people.json":      ("json", "people",       933),
    "people.yml":       ("yaml", "people",       297),
    "promotions.csv":   ("csv",  "promotions",   236),
    "transactions.xml": ("xml",  "transactions", 189),
    "transfers.csv":    ("csv",  "transfers",    614),
}


@pytest.mark.parametrize("filename", list(EXPECTED))
def test_detects_format_and_entity(source_files, filename):
    fmt, entity, _ = EXPECTED[filename]
    content = source_files[filename]
    assert detect_format(content, filename) == fmt
    assert detect_entity(content, fmt, filename) == entity


@pytest.mark.parametrize("filename", list(EXPECTED))
def test_reads_all_rows_without_error(source_files, filename):
    fmt, entity, count = EXPECTED[filename]
    result = read_file(source_files[filename], fmt, entity)
    assert len(result.records) == count
    assert result.errors == []


def test_detection_ignores_a_misleading_filename(source_files):
    """Filenames are not trustworthy on an upload endpoint."""
    content = source_files["transfers.csv"]
    fmt = detect_format(content, "totally_wrong_name.txt")
    assert detect_entity(content, fmt, "totally_wrong_name.txt") == "transfers"


def test_xml_nesting_is_not_double_counted(source_files):
    """<item> contains a child also named <item>; a .//item XPath would
    report twice the real line count."""
    result = read_file(source_files["transactions.xml"], "xml", "transactions")
    assert sum(len(r["items"]) for r in result.records) == 360
