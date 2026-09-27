"""Mock site data: the golden parcels plus generated illustrative lots, validated when loaded.

- `fixtures/golden/`: real parcels, SiteContext and SiteAnalysis paired by file name.
- `fixtures/mock/generated/`: output of `api/scripts/generate_mock_sites.py` (summaries,
  EPSG:4326 geometry, map features, and engine analyses of the synthetic candidates).
- `fixtures/mock/ui-draft/`: evidence drawer content, illustrative until zoning board
  decisions are available.
"""

from pathlib import Path
from typing import Literal

from navigator_api.models import EvidenceDetail
from navigator_api.sources.bundle import SiteBundle
from navigator_contracts import SiteAnalysis, SiteContext


class MockSiteSource(SiteBundle):
    name: Literal["mock"] = "mock"

    def __init__(self, golden_dir: Path, generated_dir: Path, evidence_dir: Path) -> None:
        summaries, geometry, features = self.load_files(generated_dir)
        analyses: dict[str, SiteAnalysis] = {}
        for path in sorted((golden_dir / "site_analysis").glob("*.json")):
            context = SiteContext.model_validate_json(
                (golden_dir / "site_context" / path.name).read_bytes()
            )
            analyses[context.parcels[0].parcel_id] = SiteAnalysis.model_validate_json(
                path.read_bytes()
            )
        for path in sorted((generated_dir / "site_analysis").glob("*.json")):
            analyses[path.stem] = SiteAnalysis.model_validate_json(path.read_bytes())
        evidence = {
            e.id: e
            for e in (
                EvidenceDetail.model_validate_json(p.read_bytes())
                for p in sorted(evidence_dir.glob("*.evidence.json"))
            )
        }
        super().__init__(summaries, geometry, features, analyses, evidence)
