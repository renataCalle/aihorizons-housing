"""Mock site data: the golden parcels plus generated illustrative lots, validated when loaded.

- `fixtures/golden/`: real parcels, SiteContext and SiteAnalysis paired by file name.
- `fixtures/mock/generated/`: output of `api/scripts/generate_mock_sites.py` (summaries,
  EPSG:4326 geometry, map features, and engine analyses of the synthetic candidates).
- `fixtures/mock/ui-draft/`: the mockups' zoning board cases, served in the evidence drawer
  for generated lots only (real lots show that decisions are unavailable).
"""

import json
from pathlib import Path
from typing import Literal

from navigator_api.models import Case, Examples, Precedent
from navigator_api.sources.bundle import SiteBundle
from navigator_contracts import SiteAnalysis, SiteContext


class MockSiteSource(SiteBundle):
    name: Literal["mock"] = "mock"

    def __init__(self, golden_dir: Path, generated_dir: Path, evidence_dir: Path) -> None:
        summaries, geometry, features = self.load_files(generated_dir)
        analyses: dict[str, SiteAnalysis] = {}
        contexts: dict[str, SiteContext] = {}
        for path in sorted((golden_dir / "site_analysis").glob("*.json")):
            context = SiteContext.model_validate_json(
                (golden_dir / "site_context" / path.name).read_bytes()
            )
            pid = context.parcels[0].parcel_id
            contexts[pid] = context
            analyses[pid] = SiteAnalysis.model_validate_json(path.read_bytes())
        for path in sorted((generated_dir / "site_analysis").glob("*.json")):
            analyses[path.stem] = SiteAnalysis.model_validate_json(path.read_bytes())
        super().__init__(
            summaries,
            geometry,
            features,
            analyses,
            mock_precedent(evidence_dir / "ev-variance-4-townhomes.evidence.json"),
            contexts,
        )

    def examples(self) -> Examples:
        # The mockups' examples: Sample lot A and its address.
        return Examples(
            parcel_id="0000-X-00000",
            address="123 Sample St",
            prompt="3 townhomes in Hazelwood under $25k",
        )


def mock_precedent(path: Path) -> Precedent:
    """The mockups' zoning board cases (docs/design/screens/05-evidence.png)."""
    draft = json.loads(path.read_text())
    return Precedent(
        status="illustrative",
        granted=draft["precedent_granted"],
        total=draft["precedent_total"],
        median_months=draft["median_months"],
        cases=[
            Case(
                case_id=c["case_id"],
                area=c["neighborhood"],
                request=c["request"],
                outcome=c["outcome"],
                months_to_decision=c["months_to_decision"],
                source_url=c["source_url"],
            )
            for c in draft["cases"]
        ],
        ai_extracted=draft["ai_extracted"],
    )
