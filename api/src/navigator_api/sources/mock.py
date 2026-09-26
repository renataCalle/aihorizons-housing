"""Illustrative site data from `fixtures/mock/ui-draft/`, validated when loaded."""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from navigator_api.models import Evidence, SiteAnalysis, Versions


class MockSiteSource:
    name: Literal["mock"] = "mock"
    illustrative = True

    def __init__(self, fixtures_dir: Path) -> None:
        self._analyses = {
            a.parcel.parcel_id: a
            for a in _load(fixtures_dir, "*.analysis.json", SiteAnalysis.model_validate_json)
        }
        self._evidence = {
            e.id: e for e in _load(fixtures_dir, "*.evidence.json", Evidence.model_validate_json)
        }
        if not self._analyses:
            raise FileNotFoundError(f"No *.analysis.json fixtures in {fixtures_dir}")

    def versions(self) -> Versions:
        # The newest data among the fixtures; engine and ruleset come from the same analysis.
        meta = max((a.meta for a in self._analyses.values()), key=lambda m: m.data_refreshed)
        return Versions(
            engine=meta.engine_version,
            ruleset=meta.rules_version,
            schema_version=meta.contract_version,
            data_as_of=meta.data_refreshed,
        )

    def analysis(self, parcel_id: str) -> SiteAnalysis | None:
        return self._analyses.get(parcel_id)

    def evidence(self, evidence_id: str) -> Evidence | None:
        return self._evidence.get(evidence_id)


def _load[T](directory: Path, pattern: str, parse: Callable[[str], T]) -> list[T]:
    return [parse(path.read_text()) for path in sorted(directory.glob(pattern))]
