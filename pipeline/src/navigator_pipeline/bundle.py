"""The results bundle: the small, committed output the API can serve without the data store.

    from navigator_pipeline import bundle
    b = bundle.load()                      # results/ at the repository root, validated
    b.analyses["0029L00052000000"]         # SiteAnalysis
    b.contexts["0029L00052000000"]         # SiteContext (re-run the engine from it)

Written by `navigator_pipeline.publish`; layout and columns are documented in results/README.md.
"""

import gzip
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from navigator_contracts import SiteAnalysis, SiteContext
from navigator_pipeline.settings import REPO_ROOT

RESULTS = REPO_ROOT / "results"
MAX_BYTES = 20 * 1024 * 1024  # stay well under GitHub's 50 MB warning

FILES = {
    "readme": "README.md",
    "manifest": "manifest.json",
    "summaries": "summaries.json",
    "summaries_csv": "summaries.csv",
    "analyses": "site_analysis.jsonl.gz",
    "contexts": "site_context.jsonl.gz",
    "parcels": "parcels.geojson",
    "map_features": "map_features.geojson",
}

# The summaries.csv columns, in order: one row per candidate parcel and building type.
CSV_COLUMNS = [
    "parcel_id",
    "block_lot",
    "neighborhood",
    "zoning_district",
    "lot_area_sqft",
    "owner_type",
    "assessed_value",
    "product",
    "units",
    "lead",
    "score_p10",
    "score_p50",
    "score_p90",
    "band",
    "approval_path",
    "months_p10",
    "months_p50",
    "months_p90",
    "cost_premium_p10",
    "cost_premium_p50",
    "cost_premium_p90",
    "max_land_p10",
    "max_land_p50",
    "max_land_p90",
    "top_flag",
    "top_flag_severity",
    "unknown_flags",
    "lon",
    "lat",
]


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parcel_id: str


class AnalysisRecord(_Record):
    """One line of site_analysis.jsonl.gz."""

    analysis: SiteAnalysis


class ContextRecord(_Record):
    """One line of site_context.jsonl.gz."""

    context: SiteContext


def write_jsonl_gz(path: Path, rows: list[dict]) -> None:
    # mtime=0 keeps the file byte-identical when the content is unchanged
    with (
        path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz,
    ):
        for row in rows:
            gz.write((json.dumps(row, separators=(",", ":"), default=str) + "\n").encode())


def read_jsonl_gz(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


@dataclass
class Bundle:
    manifest: dict
    summaries: list[dict]  # ParcelSummary-shaped (navigator_api.models.ParcelSummary)
    analyses: dict[str, SiteAnalysis]
    contexts: dict[str, SiteContext]
    parcels: dict  # GeoJSON FeatureCollection, EPSG:4326
    map_features: dict  # GeoJSON FeatureCollection, EPSG:4326


def load(path: Path = RESULTS) -> Bundle:
    """Read and validate a bundle; raises on any contract violation."""
    analyses = {}
    for row in read_jsonl_gz(path / FILES["analyses"]):
        r = AnalysisRecord.model_validate(row)
        analyses[r.parcel_id] = r.analysis
    contexts = {}
    for row in read_jsonl_gz(path / FILES["contexts"]):
        r = ContextRecord.model_validate(row)
        contexts[r.parcel_id] = r.context
    return Bundle(
        manifest=json.loads((path / FILES["manifest"]).read_text()),
        summaries=json.loads((path / FILES["summaries"]).read_text()),
        analyses=analyses,
        contexts=contexts,
        parcels=json.loads((path / FILES["parcels"]).read_text()),
        map_features=json.loads((path / FILES["map_features"]).read_text()),
    )
