"""CLI: a thin wrapper over process(); the exit code says whether a draft was produced."""

import io
import json

import pytest

from sitr.cli import main
from sitr.config import ConfigError

EID = "784-1990-1234567-1"


def _stdin(data: bytes) -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")


def test_templates_lists_ids(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["templates"]) == 0
    assert "salary-certificate" in capsys.readouterr().out


def test_run_template_prints_a_readable_result(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", "--template", "salary-certificate"])
    out = capsys.readouterr().out
    assert code == 0
    assert "decision      drafted" in out and "Dear Sarah Mitchell" in out
    assert "[EID_MASKED]" in out and EID not in out


def test_run_json(capsys: pytest.CaptureFixture[str]) -> None:
    text = "Hi, I need a salary certificate for a loan addressed to my bank. Thanks, John Smith"
    code = main(["run", "--json", text])
    body = json.loads(capsys.readouterr().out)
    assert code == 0 and body["decision"] == "drafted" and "John Smith" in body["draft_reply"]


def test_refusal_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "The weather is lovely today."]) == 1
    assert "handed_to_person (unrecognised_request" in capsys.readouterr().out


def test_unknown_template_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--template", "nope"]) == 2
    assert "unknown template" in capsys.readouterr().err


def test_reads_stdin_when_no_text_given(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", _stdin(b"Annual leave from 3 to 14 March please. Omar Hassan"))
    assert main(["run"]) == 0
    assert "leave" in capsys.readouterr().out


def test_invalid_utf8_on_stdin_is_not_a_traceback(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", _stdin(b"Annual leave from 3 to 14 March please. \xff"))
    assert main(["run"]) == 0
    assert "leave" in capsys.readouterr().out


def test_configuration_error_exits_two(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> None:
        raise ConfigError("config.yaml: malformed config")

    monkeypatch.setattr("sitr.cli.load_config", broken)
    assert main(["templates"]) == 2
    assert "configuration error: config.yaml" in capsys.readouterr().err
