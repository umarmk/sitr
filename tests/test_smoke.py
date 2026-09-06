"""Install smoke test: the package imports and the pinned name model loads with no extra step."""

import spacy

import sitr


def test_version() -> None:
    assert sitr.__version__


def test_name_model_ships_with_install() -> None:
    nlp = spacy.load("en_core_web_sm")
    assert "ner" in nlp.pipe_names
