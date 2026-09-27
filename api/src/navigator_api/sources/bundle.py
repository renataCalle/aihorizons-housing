"""A site source backed by precomputed files: parcel summaries, shapes, map layers, analyses.

Both sources are bundles; they differ only in where the files come from:
- MockSiteSource (sources/mock.py): the golden parcels plus generated illustrative lots.
- PipelineSiteSource (sources/pipeline.py): real parcels, built from the pipeline's store by
  api/scripts/build_results_bundle.py into results/.
"""

import gzip
import json
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from navigator_api.models import (
    EvidenceDetail,
    Examples,
    MapFeatureCollection,
    ParcelFeature,
    ParcelFeatureCollection,
    ParcelProperties,
    ParcelSummary,
)
from navigator_contracts import SiteAnalysis
from navigator_contracts.site_analysis import Versions

SUMMARIES = TypeAdapter(list[ParcelSummary])


def read_text(path: Path) -> str:
    """Read `path`, or `path.gz` when only the compressed file exists."""
    if path.exists():
        return path.read_text()
    return gzip.decompress(path.with_name(path.name + ".gz").read_bytes()).decode()


def exists(path: Path) -> bool:
    return path.exists() or path.with_name(path.name + ".gz").exists()


class SiteBundle:
    name: Literal["mock", "pipeline"]

    def __init__(
        self,
        summaries: list[ParcelSummary],
        geometry: dict[str, dict],
        map_features: MapFeatureCollection,
        analyses: dict[str, SiteAnalysis],
        evidence: dict[str, EvidenceDetail] | None = None,
    ) -> None:
        self._summaries = {s.parcel_id: s for s in summaries}
        self._geometry = geometry
        self._map_features = map_features
        self._analyses = analyses
        self._evidence = evidence or {}

        missing = {pid for pid, s in self._summaries.items() if s.candidate} - set(analyses)
        if missing:
            raise ValueError(f"Candidates without an analysis: {sorted(missing)[:5]}")
        if set(self._summaries) != set(self._geometry):
            raise ValueError("The summaries and the parcel shapes list different parcels")

    @staticmethod
    def load_files(directory: Path) -> tuple[list[ParcelSummary], dict, MapFeatureCollection]:
        summaries = SUMMARIES.validate_json(read_text(directory / "summaries.json"))
        geometry = {
            f["properties"]["parcel_id"]: f["geometry"]
            for f in json.loads(read_text(directory / "parcels.geojson"))["features"]
        }
        features = MapFeatureCollection.model_validate_json(
            read_text(directory / "map_features.geojson")
        )
        return summaries, geometry, features

    def versions(self) -> Versions:
        # Every analysis is stamped by the engine; serve the oldest data date among them.
        stamps = [a.versions for a in self._analyses.values()]
        return min(stamps, key=lambda v: (v.data_as_of is None, v.data_as_of))

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

    def examples(self) -> Examples:
        """The best-scoring candidate's ID, a real candidate address, and the busiest area."""
        scored = sorted(
            (s for s in self._summaries.values() if s.candidate and s.score is not None),
            key=lambda s: (-(s.score or 0), s.parcel_id),
        )
        best = scored[0]
        with_number = next((s for s in scored if s.address and s.address[:1].isdigit()), best)
        counts: dict[str, int] = {}
        for s in scored:
            if s.neighborhood:
                counts[s.neighborhood] = counts.get(s.neighborhood, 0) + 1
        area = max(counts, key=lambda n: counts[n]) if counts else "Hazelwood"
        pid = best.parcel_id
        return Examples(
            parcel_id=f"{pid[:4]}-{pid[4]}-{pid[5:10]}",
            address=with_number.display_name,
            prompt=f"3 townhomes in {area} under $25k",
        )
