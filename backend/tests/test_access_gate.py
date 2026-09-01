"""The access gate. No database required."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.security import code_is_valid, issue_token, token_is_valid


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "access_codes_raw", "TEST-CODE,OTHER-CODE")
    from app.main import app
    return TestClient(app)


def test_open_paths_need_no_code(client):
    assert client.get("/ping").status_code == 200
    assert client.get("/auth/required").json() == {"required": True}


@pytest.mark.parametrize("path", ["/analysis", "/analysis/clients", "/loads",
                                  "/loads/quarantine", "/health"])
def test_every_data_route_requires_a_code(client, path):
    """Opening a deep link directly must not reach data."""
    assert client.get(path).status_code == 401


def test_wrong_code_is_rejected(client):
    assert client.post("/auth", json={"code": "NOPE-NOPE"}).status_code == 401


def test_code_is_case_insensitive_and_trimmed(client):
    assert client.post("/auth", json={"code": " test-code "}).status_code == 200


def test_token_unlocks_the_api(client, monkeypatch):
    token = client.post("/auth", json={"code": "TEST-CODE"}).json()["token"]
    r = client.get("/analysis/sections", headers={"x-venmito-token": token})
    assert r.status_code == 200


def test_tampered_token_is_rejected(client):
    token = client.post("/auth", json={"code": "TEST-CODE"}).json()["token"]
    body, _, sig = token.partition(".")
    for bad in (token + "x", f"{body}.{sig[:-1]}A", "garbage", ""):
        assert client.get("/analysis/sections",
                          headers={"x-venmito-token": bad}).status_code == 401


def test_revoking_a_code_invalidates_its_tokens(monkeypatch):
    """A token carries the code it came from, so removing that code from the
    configuration stops it working without needing a token blacklist."""
    monkeypatch.setattr(settings, "access_codes_raw", "KEEP-CODE,DROP-CODE")
    token = issue_token("DROP-CODE")
    assert token_is_valid(token)
    monkeypatch.setattr(settings, "access_codes_raw", "KEEP-CODE")
    assert not token_is_valid(token)


def test_gate_disabled_when_no_codes_configured(monkeypatch):
    monkeypatch.setattr(settings, "access_codes_raw", "")
    assert not settings.gate_enabled
    assert not code_is_valid("anything")
