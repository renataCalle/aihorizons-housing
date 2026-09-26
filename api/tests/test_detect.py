import json
from pathlib import Path

import pytest

from navigator_api.search.detect import detect

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "search" / "detect_cases.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: repr(c["text"]))
def test_detection_matches_shared_cases(case: dict) -> None:
    result = detect(case["text"])
    assert result.kind == case["kind"]
    assert result.format == case.get("format")
