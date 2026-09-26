"""The committed mock data matches the engine's output and the special cases in docs/06."""

import json
from pathlib import Path

from navigator_api.models import ParcelSummary
from navigator_contracts import SiteAnalysis

GENERATED = Path(__file__).resolve().parents[2] / "fixtures" / "mock" / "generated"
SUMMARIES = [
    ParcelSummary.model_validate(s) for s in json.loads((GENERATED / "summaries.json").read_text())
]


def test_summaries_copy_the_engine_verdict() -> None:
    for summary in SUMMARIES:
        path = GENERATED / "site_analysis" / f"{summary.parcel_id}.json"
        if not summary.illustrative or not summary.candidate:
            continue
        analysis = SiteAnalysis.model_validate_json(path.read_text())
        assert summary.score == analysis.verdict.score
        assert summary.band == analysis.verdict.band


def test_required_special_cases() -> None:
    by_name = {s.display_name: s for s in SUMMARIES}
    assert by_name["Sample lot A"].parcel_id == "0000X00000000000"
    assert by_name["Sample lot A"].neighborhood == "Hazelwood"
    assert sum(1 for s in SUMMARIES if s.band == "not_scored") >= 1  # outside the city
    assert sum(1 for s in SUMMARIES if s.top_flag_severity == "high") >= 1  # deal risk
    assembly = [s for s in SUMMARIES if s.assembly_id]
    assert len(assembly) == 2 and len({s.assembly_id for s in assembly}) == 1
    assert sum(1 for s in SUMMARIES if not s.illustrative) == 8  # the golden parcels


def test_only_candidates_have_analyses() -> None:
    analysed = {p.stem for p in (GENERATED / "site_analysis").glob("*.json")}
    candidates = {s.parcel_id for s in SUMMARIES if s.candidate and s.illustrative}
    assert analysed == candidates
