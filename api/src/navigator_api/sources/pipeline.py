"""Real parcels: the results bundle built from the pipeline's store (results/README.md).

The bundle holds every parcel in scope (for the map and lookup) and the engine's analysis of
each candidate, computed from stored facts. Live per-parcel lookups at report time
(`navigator_pipeline.site_context.build(..., live=True)`) come later: they need the engine to
be importable from navigator_engine.
"""

import json
from pathlib import Path
from typing import Literal

from navigator_api.sources.bundle import SiteBundle, read_text
from navigator_contracts import SiteAnalysis


class PipelineSiteSource(SiteBundle):
    name: Literal["pipeline"] = "pipeline"

    def __init__(self, results_dir: Path) -> None:
        summaries, geometry, features = self.load_files(results_dir)
        analyses = {}
        for line in read_text(results_dir / "site_analysis.jsonl").splitlines():
            if line.strip():
                row = json.loads(line)
                analyses[row["parcel_id"]] = SiteAnalysis.model_validate(row["analysis"])
        super().__init__(summaries, geometry, features, analyses)
