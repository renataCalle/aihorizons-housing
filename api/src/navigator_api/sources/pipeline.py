"""Real parcels: the pipeline's results bundle in results/ (see results/README.md).

The bundle is published by `navigator_pipeline.publish`. It holds a summary for every parcel in
scope, and for each candidate its stored SiteContext and the engine's SiteAnalysis. Candidate
summaries are rebuilt here from those two with `summarize`, so search gets every field it
filters on (program fits, hazard shares, transit distance) whatever the publisher wrote.
`summaries.csv` adds the engine's result for every building type, so a search for one building
type ranks lots by that type (search/programs.py).
"""

import json
import re
from pathlib import Path
from typing import Literal

from navigator_api.models import ParcelSummary
from navigator_api.search.programs import load_program_rows
from navigator_api.sources.bundle import SUMMARIES, SiteBundle, exists, read_text
from navigator_api.summaries import summarize
from navigator_contracts import SiteAnalysis, SiteContext


def tidy_name(name: str) -> str:
    """ "2Nd Ave" -> "2nd Ave": title-casing capitalizes ordinal suffixes. Fixed in
    navigator_pipeline.publish; kept for bundles published before that fix."""
    return re.sub(r"\b(\d+)(St|Nd|Rd|Th)\b", lambda m: m.group(1) + m.group(2).lower(), name)


def _jsonl(path: Path) -> dict[str, dict]:
    rows = (json.loads(line) for line in read_text(path).splitlines() if line.strip())
    return {row["parcel_id"]: row for row in rows}


class PipelineSiteSource(SiteBundle):
    name: Literal["pipeline"] = "pipeline"

    def __init__(self, results_dir: Path) -> None:
        published = SUMMARIES.validate_json(read_text(results_dir / "summaries.json"))
        _, geometry, features = self.load_files(results_dir, summaries=False)
        contexts = {
            pid: SiteContext.model_validate(row["context"])
            for pid, row in _jsonl(results_dir / "site_context.jsonl").items()
        }
        analyses = {
            pid: SiteAnalysis.model_validate(row["analysis"])
            for pid, row in _jsonl(results_dir / "site_analysis.jsonl").items()
        }
        summaries: list[ParcelSummary] = []
        for s in published:
            name = tidy_name(s.display_name)
            context, analysis = contexts.get(s.parcel_id), analyses.get(s.parcel_id)
            if s.candidate and context and analysis:
                s = summarize(
                    context,
                    analysis,
                    display_name=name,
                    centroid=s.centroid,
                    candidate=True,
                    illustrative=s.illustrative,
                    assembly_id=s.assembly_id,
                )
            else:
                s = s.model_copy(update={"display_name": name})
            summaries.append(s)
        rows_file = results_dir / "summaries.csv"
        rows = load_program_rows(rows_file) if exists(rows_file) else {}
        super().__init__(
            summaries, geometry, features, analyses, contexts=contexts, program_rows=rows
        )
