"""AI mode against an in-process fake OpenRouter (SPEC T-8). No test here touches the network."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sitr import model as model_mod
from sitr.boundary import process
from sitr.config import load_config, load_policy
from sitr.model import OpenRouterModel

NAME, MOBILE, EMAIL, EID = (
    "Sarah Mitchell",
    "050 123 4567",
    "sarah.mitchell@example.com",
    "784-1990-1234567-1",
)
PII = (NAME, MOBILE, EMAIL, EID)
REQUEST = (
    f"Hello, my name is {NAME}. I need a salary certificate addressed to my bank for a loan. "
    f"Emirates ID {EID}, mobile {MOBILE}, email {EMAIL}."
)
GOOD_ANSWER = {
    "request_type": "salary_certificate",
    "missing_items": [],
    "draft_reply": "Dear [NAME_1], your salary certificate is being prepared.",
}


class FakeOpenRouter:
    """Records every request; replies with whatever `reply` currently holds."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.reply: tuple[int, object] = (200, self.envelope(GOOD_ANSWER))

        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                fake.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": json.loads(raw)}
                )
                status, payload = fake.reply
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *_: object) -> None:  # keep pytest output quiet
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @staticmethod
    def envelope(answer: object) -> dict:
        content = answer if isinstance(answer, str) else json.dumps(answer)
        return {"choices": [{"message": {"role": "assistant", "content": content}}]}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake() -> Iterator[FakeOpenRouter]:
    server = FakeOpenRouter()
    yield server
    server.close()


def make_model(fake: FakeOpenRouter, key: str | None = "test-key") -> OpenRouterModel:
    policy, config = load_policy(), load_config()
    dest = policy.destinations[policy.default_destination]
    return OpenRouterModel(dest, config.model, api_key=key, base_url=fake.url)


def test_only_placeholders_leave_the_boundary(
    fake: FakeOpenRouter, caplog: pytest.LogCaptureFixture
) -> None:  # T-8
    caplog.set_level(logging.INFO)
    r = process(REQUEST, mode="ai", model=make_model(fake))

    assert (r.decision, r.request_type) == ("drafted", "salary_certificate")
    assert r.draft_reply == f"Dear {NAME}, your salary certificate is being prepared."
    assert r.destination == {
        "name": "openrouter",
        "provider": "OpenRouter",
        "region": "US",
        "approved": True,
    }

    sent = fake.requests[0]
    user_message = sent["body"]["messages"][1]["content"]
    assert all(value not in json.dumps(sent["body"]) for value in PII)
    assert "[NAME_1]" in user_message and "[EID_MASKED]" in user_message
    assert sent["body"]["model"] == "openai/gpt-4o-mini"
    assert sent["headers"]["Authorization"] == "Bearer test-key"

    left_the_boundary = caplog.text + json.dumps(r.audit) + r.outgoing_text
    assert all(value not in left_the_boundary for value in PII)
    assert "test-key" not in json.dumps(r.__dict__, default=str)  # the key never reaches a result


def test_boundary_builds_the_model_from_env_and_policy(
    fake: FakeOpenRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setattr(model_mod, "OPENROUTER_BASE_URL", fake.url)
    r = process(REQUEST, mode="ai")
    assert r.decision == "drafted"
    assert fake.requests[0]["headers"]["Authorization"] == "Bearer env-key"


def test_missing_key_means_no_request_at_all(fake: FakeOpenRouter) -> None:
    r = process(REQUEST, mode="ai", model=make_model(fake, key=None))
    assert r.reason == "model_unavailable" and fake.requests == []


def test_http_error_is_model_unavailable(fake: FakeOpenRouter) -> None:
    fake.reply = (500, {"error": "boom"})
    r = process(REQUEST, mode="ai", model=make_model(fake))
    assert (r.reason, r.reason_detail) == (
        "model_unavailable",
        "model request failed with HTTP 500",
    )


def test_connection_refused_is_model_unavailable(fake: FakeOpenRouter) -> None:
    fake.close()
    r = process(REQUEST, mode="ai", model=make_model(fake))
    assert r.reason == "model_unavailable"


@pytest.mark.parametrize(
    "content",
    [
        "Sure! Here is your answer.",
        "[1, 2, 3]",
        json.dumps({"request_type": "pizza", "missing_items": [], "draft_reply": "x"}),
    ],
)
def test_bad_answers_are_model_output_invalid(fake: FakeOpenRouter, content: str) -> None:
    fake.reply = (200, fake.envelope(content))
    r = process(REQUEST, mode="ai", model=make_model(fake))
    assert r.reason == "model_output_invalid"


def test_fenced_json_is_tolerated(fake: FakeOpenRouter) -> None:
    fake.reply = (200, fake.envelope("```json\n" + json.dumps(GOOD_ANSWER) + "\n```"))
    assert process(REQUEST, mode="ai", model=make_model(fake)).decision == "drafted"


def test_response_without_choices_is_model_unavailable(fake: FakeOpenRouter) -> None:
    fake.reply = (200, {"id": "x"})
    r = process(REQUEST, mode="ai", model=make_model(fake))
    assert r.reason == "model_unavailable"


def test_unapproved_destination_never_reaches_the_model(fake: FakeOpenRouter) -> None:
    r = process(REQUEST, mode="ai", destination="example-unapproved", model=make_model(fake))
    assert r.reason == "destination_not_approved" and fake.requests == []
