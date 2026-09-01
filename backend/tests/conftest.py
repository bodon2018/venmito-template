import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

DATA = pathlib.Path(__file__).resolve().parents[2] / "recommendations" / "raw_data"


@pytest.fixture(scope="session")
def source_files() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in DATA.iterdir() if p.is_file()}
