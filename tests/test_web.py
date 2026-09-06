"""Web layer: endpoints return what the page needs and never a secret or the mapping."""

import pytest
from fastapi.testclient import TestClient

from sitr.config import ConfigError
from sitr.web import app

client = TestClient(app)
EID = "784-1990-1234567-1"
REQUEST = (
    f"Hi, I am Sarah Mitchell, ID {EID}. "
    "I need a salary certificate addressed to my bank for a loan."
)


def test_index_serves_the_page() -> None:
    r = client.get("/")
    assert r.status_code == 200 and "<title>sitr</title>" in r.text


def test_capabilities_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    c = client.get("/api/capabilities").json()
    assert c["ai_available"] is False and "OPENROUTER_API_KEY" in c["ai_reason"]
    assert c["input_max_chars"] == 4000
    assert {d["name"] for d in c["destinations"]} >= {"openrouter", "example-unapproved"}
    assert all(set(d) == {"name", "provider", "region", "approved"} for d in c["destinations"])


def test_capabilities_never_leak_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-value")
    r = client.get("/api/capabilities")
    assert r.json()["ai_available"] is True and "sk-secret-value" not in r.text


def test_templates_are_listed_once_each() -> None:
    ids = [t["id"] for t in client.get("/api/templates").json()]
    assert "salary-certificate" in ids and len(ids) == len(set(ids))


def test_process_offline_end_to_end() -> None:
    r = client.post("/api/process", json={"text": REQUEST})
    body = r.json()
    assert r.status_code == 200 and body["decision"] == "drafted"
    assert "Sarah Mitchell" in body["draft_reply"]
    assert EID not in r.text and "mapping" not in body  # the mapping never leaves the process


def test_oversized_input_is_refused_not_rejected() -> None:
    r = client.post("/api/process", json={"text": "a" * 4001})
    assert r.status_code == 200 and r.json()["reason"] == "too_long"


def test_bad_mode_is_a_validation_error() -> None:
    assert client.post("/api/process", json={"text": "x", "mode": "turbo"}).status_code == 422


@pytest.mark.parametrize("dest", ["x" * 65, f"{EID} sarah", "a b"])
def test_destination_is_an_identifier_not_free_text(dest: str) -> None:
    body = {"text": REQUEST, "mode": "ai", "destination": dest}
    assert client.post("/api/process", json=body).status_code == 422


def test_broken_config_is_an_honest_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: object, **__: object) -> None:
        raise ConfigError("config.yaml: malformed config (KeyError('label'))")

    monkeypatch.setattr("sitr.boundary.load_config", broken)
    monkeypatch.setattr("sitr.web.load_config", broken)
    for r in (client.post("/api/process", json={"text": REQUEST}), client.get("/api/capabilities")):
        assert r.status_code == 503 and "config.yaml" in r.json()["detail"]


def test_ai_mode_without_key_is_refused_with_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    body = client.post("/api/process", json={"text": REQUEST, "mode": "ai"}).json()
    assert (body["decision"], body["reason"]) == ("handed_to_person", "model_unavailable")
    assert body["destination"]["name"] == "openrouter"
