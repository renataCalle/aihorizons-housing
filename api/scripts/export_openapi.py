"""Write the API's OpenAPI schema to a file, without starting a server.

    uv run python api/scripts/export_openapi.py web/openapi.json

The web app generates `src/api/types.gen.ts` from it (`npm run gen:types` in web/).
"""

import json
import sys
from pathlib import Path

from navigator_api.main import create_app


def main() -> None:
    out = Path(sys.argv[1])
    schema = create_app().openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
