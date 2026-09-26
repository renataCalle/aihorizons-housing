"""Mock site data: the golden parcels plus generated illustrative lots, validated when loaded.

- `fixtures/golden/`: real parcels, SiteContext and SiteAnalysis paired by file name.
- `fixtures/mock/generated/`: output of `api/scripts/generate_mock_sites.py` (summaries,
  EPSG:4326 geometry, map features, and engine analyses of the synthetic candidates).
- `fixtures/mock/ui-draft/`: evidence drawer content, illustrative until zoning board
  decisions are available.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from navigator_api.models import (
    EvidenceDetail,
    MapFeatureCollection,
    ParcelFeature,
    ParcelFeatureCollection,
    ParcelProperties,
    ParcelSummary,
)
from navigator_contracts import SiteAnalysis, SiteContext
from navigator_contracts.site_analysis import Versions

_SUMMARIES = TypeAdapter(list[ParcelSummary])


class MockSiteSource:
    name: Literal["mock"] = "mock"

    def __init__(self, golden_dir: Path, generated_dir: Path, evidence_dir: Path) -> None:
        self._summaries = {
            s.parcel_id: s
            for s in _SUMMARIES.validate_json((generated_dir / "summaries.json").read_bytes())
        }
        self._analyses: dict[str, SiteAnalysis] = {}
        for path in sorted((golden_dir / "site_analysis").glob("*.json")):
            context = SiteContext.model_validate_json(
                (golden_dir / "site_context" / path.name).read_bytes()
            )
            self._analyses[context.parcels[0].parcel_id] = SiteAnalysis.model_validate_json(
                path.read_bytes()
            )
        for path in sorted((generated_dir / "site_analysis").glob("*.json")):
            self._analyses[path.stem] = SiteAnalysis.model_validate_json(path.read_bytes())

        self._geometry = {
            f["properties"]["parcel_id"]: f["geometry"]
            for f in json.loads((generated_dir / "parcels.geojson").read_bytes())["features"]
        }
        self._map_features = MapFeatureCollection.model_validate_json(
            (generated_dir / "map_features.geojson").read_bytes()
        )
        self._evidence = {
            e.id: e
            for e in (
                EvidenceDetail.model_validate_json(p.read_bytes())
                for p in sorted(evidence_dir.glob("*.evidence.json"))
            )
        }

        missing = {pid for pid, s in self._summaries.items() if s.candidate} - set(self._analyses)
        if missing:
            raise ValueError(f"Candidates without an analysis: {sorted(missing)[:5]}")
        if set(self._summaries) != set(self._geometry):
            raise ValueError("summaries.json and parcels.geojson list different parcels")

    def versions(self) -> Versions:
        # Every analysis is stamped by the engine; serve the oldest data date among them.
        stamps = [a.versions for a in self._analyses.values()]
        oldest = min(stamps, key=lambda v: (v.data_as_of is None, v.data_as_of))
        return oldest

    def illustrative(self) -> bool:
        return any(s.illustrative for s in self._summaries.values())

    def summaries(self) -> list[ParcelSummary]:
        return list(self._summaries.values())

    def summary(self, parcel_id: str) -> ParcelSummary | None:
        return self._summaries.get(parcel_id)

    def analysis(self, parcel_id: str) -> SiteAnalysis | None:
        return self._analyses.get(parcel_id)

    def parcels_geojson(self) -> ParcelFeatureCollection:
        return ParcelFeatureCollection(
            features=[
                ParcelFeature(
                    geometry=self._geometry[s.parcel_id],
                    properties=ParcelProperties(
                        parcel_id=s.parcel_id,
                        display_name=s.display_name,
                        candidate=s.candidate,
                        band=s.band,
                        score=s.score,
                        assembly_id=s.assembly_id,
                    ),
                )
                for s in self._summaries.values()
            ]
        )

    def map_features(self) -> MapFeatureCollection:
        return self._map_features

    def evidence(self, evidence_id: str) -> EvidenceDetail | None:
        return self._evidence.get(evidence_id)
