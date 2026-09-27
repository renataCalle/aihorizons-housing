"""Where the pipeline keeps its data.

`NAVIGATOR_DATA_DIR` overrides the default `<repo>/data` (gitignored). Layout:

    raw/<source>/        downloads + _manifest.json (url, source as-of, fetched/checked, sha256)
    clean/<table>.parquet   cleaned tables, EPSG:2272
    features/            per-parcel facts
    manual/              inputs that cannot be fetched automatically (zoning code PDFs)
    scores/              every city parcel scored once (navigator_pipeline.score_all)
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("NAVIGATOR_DATA_DIR", REPO_ROOT / "data"))
RAW = DATA_DIR / "raw"
CLEAN = DATA_DIR / "clean"
FEATURES = DATA_DIR / "features"
MANUAL = DATA_DIR / "manual"
SCORES = DATA_DIR / "scores"
