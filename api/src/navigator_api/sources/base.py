"""Where site data comes from. The API above this interface never knows mock from real."""

from typing import Literal, Protocol

from navigator_api.models import (
    EvidenceDetail,
    Examples,
    MapFeatureCollection,
    ParcelFeatureCollection,
    ParcelSummary,
)
from navigator_contracts import SiteAnalysis, SiteContext
from navigator_contracts.site_analysis import Versions


class SiteSource(Protocol):
    """Analyses of the engine's pick are precomputed. `context` returns the stored facts, so
    the API can run navigator_engine live for another building type (routes/parcels.py).
    """

    name: Literal["mock", "pipeline"]

    def versions(self) -> Versions: ...

    def illustrative(self) -> bool: ...

    def summaries(self) -> list[ParcelSummary]: ...

    def summary(self, parcel_id: str) -> ParcelSummary | None: ...

    def analysis(self, parcel_id: str) -> SiteAnalysis | None: ...

    def context(self, parcel_id: str) -> SiteContext | None: ...

    def parcels_geojson(self) -> ParcelFeatureCollection: ...

    def map_features(self) -> MapFeatureCollection: ...

    def evidence(self, evidence_id: str) -> EvidenceDetail | None: ...

    def examples(self) -> Examples: ...
