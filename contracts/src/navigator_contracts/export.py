"""Write JSON Schema for the contracts (for TypeScript generation or validation).

uv run python -m navigator_contracts.export   # -> contracts/schema/*.schema.json
"""

import json
from pathlib import Path

from navigator_contracts import SiteAnalysis, SiteContext

OUT = Path(__file__).resolve().parents[2] / "schema"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for model in (SiteContext, SiteAnalysis):
        path = OUT / f"{model.__name__}.schema.json"
        schema = model.model_json_schema(by_alias=True)
        path.write_text(json.dumps(schema, indent=2) + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
