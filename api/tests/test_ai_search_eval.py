"""AI search eval (docs/05-ai-search.md, "Evaluation"). Run with `uv run pytest -m eval -s`.

Every prompt in fixtures/eval/nl_search_eval.jsonl goes through the parse endpoint (the AI
parser when a key is set, else the rule-based fallback). Only the fields in `expected` are
scored: exact match for scalars, set equality for lists.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.models import SearchFilters
from navigator_api.settings import Settings

EVAL = Path(__file__).resolve().parents[2] / "fixtures" / "eval" / "nl_search_eval.jsonl"
CASES = [json.loads(line) for line in EVAL.read_text().splitlines() if line.strip()]
DEFAULTS = SearchFilters().model_dump()


def _same(expected, actual) -> bool:
    if isinstance(expected, list):
        key = lambda v: json.dumps(v, sort_keys=True)  # noqa: E731
        return sorted(map(key, expected)) == sorted(map(key, actual or []))
    if isinstance(expected, dict):
        actual = actual or {}
        return all(_same(v, actual.get(k)) for k, v in expected.items())
    if isinstance(expected, float | int) and isinstance(actual, float | int):
        return float(expected) == float(actual)
    return expected == actual


def _score(case: dict, body: dict) -> list[tuple[str, bool]]:
    fields = [(k, _same(v, body["filters"].get(k))) for k, v in case["expected"].items()]
    for phrase in case.get("expected_not_understood", []):
        hit = any(phrase.lower() in n.lower() for n in body["not_understood"])
        fields.append((f"not_understood:{phrase}", hit))
    if "expected_detected" in case:
        fields.append(("detected", body["detected"] == case["expected_detected"]))
    if not fields:  # nothing expected: the parser must not invent filters
        fields.append(("no_filters", body["filters"] == DEFAULTS))
    return fields


@pytest.mark.eval
def test_ai_search_eval() -> None:
    client = TestClient(create_app(Settings()))
    rows, total, correct, parser = [], 0, 0, None
    for case in CASES:
        body = client.post("/api/search/parse", json={"text": case["text"]}).json()
        if body["detected"] == "description":
            parser = body["parser"]
        fields = _score(case, body)
        total += len(fields)
        correct += sum(ok for _, ok in fields)
        misses = [name for name, ok in fields if not ok]
        rows.append((case["id"], case["text"][:48], "ok" if not misses else ", ".join(misses)))

    print(f"\nAI search eval, parser: {parser}\n")
    for cid, text, verdict in rows:
        print(f"{cid:>3}  {text:<48}  {verdict}")
    accuracy = correct / total
    print(f"\nFields correct: {correct}/{total} = {accuracy:.0%}")
    assert accuracy >= 0.9, f"Below the 90% target: {accuracy:.0%}"
