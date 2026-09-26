"""SiteContext and SiteAnalysis: the only interface between the data and engine workstreams.

Additive changes are free. Renames, removals, and type changes bump SCHEMA_VERSION and need
both owners to approve. See contracts/README.md.
"""

from navigator_contracts.common import SCHEMA_VERSION, Range, Source
from navigator_contracts.site_analysis import (
    Assumption,
    Evidence,
    Flag,
    Metrics,
    ProgramOption,
    ScoreComponent,
    SiteAnalysis,
    Step,
    Verdict,
)
from navigator_contracts.site_context import Parcel, SiteContext

__all__ = [
    "SCHEMA_VERSION",
    "Assumption",
    "Evidence",
    "Flag",
    "Metrics",
    "Parcel",
    "ProgramOption",
    "Range",
    "ScoreComponent",
    "SiteAnalysis",
    "SiteContext",
    "Source",
    "Step",
    "Verdict",
]
