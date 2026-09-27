import json
from pathlib import Path

import pytest

from navigator_api.search.detect import detect, should_look_up

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "search" / "detect_cases.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: repr(c["text"]))
def test_detection_matches_shared_cases(case: dict) -> None:
    result = detect(case["text"])
    assert result.kind == case["kind"]
    assert result.format == case.get("format")


@pytest.mark.parametrize(
    "case", [c for c in CASES if "look_up" in c], ids=lambda c: repr(c["text"])
)
def test_look_up_matches_shared_cases(case: dict) -> None:
    assert should_look_up(case["text"], detect(case["text"])) == case["look_up"]
