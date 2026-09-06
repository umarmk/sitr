"""Detection quality gate: precision and recall per category on a synthetic labelled corpus.

`uv run python tests/test_quality.py` prints the numbers. THRESHOLDS are the measured values
rounded down, so a detector change that costs recall or precision fails CI instead of
passing silently. Scored on the shipped masking pipeline (all passes), exact-span: a name
half masked counts as a miss, because half a name still identifies someone.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from sitr.boundary import _mask
from sitr.detect import EID, EMAIL, NAME, PHONE
from sitr.mask import EID_PLACEHOLDER

CORPUS = Path(__file__).parent / "quality" / "corpus.yaml"
# category -> (min precision, min recall). Measured 2026-09-06, en_core_web_sm 3.8.0.
THRESHOLDS = {NAME: (0.93, 0.95), PHONE: (1.0, 1.0), EMAIL: (1.0, 1.0), EID: (1.0, 1.0)}


def cases() -> list[dict]:
    return yaml.safe_load(CORPUS.read_text(encoding="utf-8"))


def score() -> dict[str, dict[str, float]]:
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    for case in cases():
        expected = {(c, v) for c, v in case["expected"]}
        masked, masker = _mask(case["text"])
        # EID values never enter the mapping by design, so they are scored by absence.
        eids = [v for c, v in expected if c == EID]
        hit = sum(v not in masked for v in eids)
        tp[EID] += hit
        fn[EID] += len(eids) - hit
        fp[EID] += max(0, masked.count(EID_PLACEHOLDER) - hit)
        expected -= {(EID, v) for v in eids}
        found = {(ph[1 : ph.index("_")], v) for ph, v in masker.mapping.items()}
        tp.update(c for c, _ in found & expected)
        fp.update(c for c, _ in found - expected)
        fn.update(c for c, _ in expected - found)
    return {
        c: {
            "n": tp[c] + fn[c],
            "precision": tp[c] / (tp[c] + fp[c] or 1),
            "recall": tp[c] / (tp[c] + fn[c] or 1),
        }
        for c in THRESHOLDS
    }


def report() -> str:
    return "\n".join(
        f"{c:6} n={s['n']:3}  precision {s['precision']:5.1%}  recall {s['recall']:5.1%}"
        for c, s in score().items()
    )


def test_corpus_is_well_formed() -> None:
    texts = [case["text"] for case in cases()]
    assert len(texts) == len(set(texts))
    for case in cases():
        for category, value in case["expected"]:
            assert category in THRESHOLDS and value in case["text"], case["text"]


def test_detection_quality_does_not_regress() -> None:
    scores = score()
    print("\n" + report())
    for c, (min_precision, min_recall) in THRESHOLDS.items():
        assert scores[c]["precision"] >= min_precision, (c, scores[c])
        assert scores[c]["recall"] >= min_recall, (c, scores[c])


if __name__ == "__main__":
    print(report())
