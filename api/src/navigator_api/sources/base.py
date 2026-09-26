"""Where site data comes from. The API above this interface never knows mock from real."""

from typing import Literal, Protocol

from navigator_api.models import Evidence, SiteAnalysis, Versions


class SiteSource(Protocol):
    """Stage 1 of docs/06-mock-data.md: analyses are prebuilt.

    When the engine lands, `analysis` moves to `navigator_engine.analyze(site_context(id))`
    and sources provide SiteContext facts instead.
    """

    name: Literal["mock", "pipeline"]
    illustrative: bool

    def versions(self) -> Versions: ...

    def analysis(self, parcel_id: str) -> SiteAnalysis | None: ...

    def evidence(self, evidence_id: str) -> Evidence | None: ...
