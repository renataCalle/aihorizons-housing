"""Where site data comes from. The API above this interface never knows mock from real."""

from typing import Literal, Protocol

from navigator_api.models import (
    EvidenceDetail,
    Examples,
    MapFeatureCollection,
    ParcelFeatureCollection,
    ParcelSummary,
)
from navigator_contracts import SiteAnalysis
from navigator_contracts.site_analysis import Versions


class SiteSource(Protocol):
    """Analyses are precomputed by the engine for now (docs/06-mock-data.md, stage 2).

    When the engine moves to navigator_engine, `analysis` can call it live on SiteContext.
    """

    name: Literal["mock", "pipeline"]

    def versions(self) -> Versions: ...

    def illustrative(self) -> bool: ...

    def summaries(self) -> list[ParcelSummary]: ...

    def summary(self, parcel_id: str) -> ParcelSummary | None: ...

    def analysis(self, parcel_id: str) -> SiteAnalysis | None: ...

    def parcels_geojson(self) -> ParcelFeatureCollection: ...

    def map_features(self) -> MapFeatureCollection: ...

    def evidence(self, evidence_id: str) -> EvidenceDetail | None: ...

    def examples(self) -> Examples: ...
