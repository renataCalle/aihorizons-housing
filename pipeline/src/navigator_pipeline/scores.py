"""Look up stored results by parcel ID (data/scores/, written by navigator_pipeline.score_all).

    from navigator_pipeline import scores
    s = scores.load()                        # data/scores/, or scores.load("/path/to/scores")
    s.summary("0055A00225000000")            # one parcels.parquet row as a dict (or "55-A-225")
    s.analysis("0055A00225000000")           # SiteAnalysis dict, exactly as the engine returned it
    s.context("0055A00225000000")            # SiteContext dict (re-run the engine with overrides)
    s.programs("0055A00225000000")           # one dict per building type
    s.sql("SELECT band, count(*) FROM parcels GROUP BY 1")   # any SQL over the four tables

The same files work from any DuckDB client, with no Python:

    SELECT analysis FROM 'data/scores/analyses.parquet' WHERE parcel_id = '0055A00225000000';

A lookup reads one small row group (the files are sorted by parcel_id): tens of milliseconds.
"""

import json
import re
import threading
from pathlib import Path

import duckdb

from navigator_pipeline.settings import SCORES

TABLES = ("parcels", "programs", "analyses", "contexts")
COUNTY_ID = re.compile(r"^[0-9A-Z]{16}$")


class Scores:
    def __init__(self, path: Path = SCORES) -> None:
        self.path = Path(path)
        missing = [t for t in TABLES if not (self.path / f"{t}.parquet").exists()]
        if missing:
            raise FileNotFoundError(
                f"{self.path} has no {', '.join(missing)}: run "
                "`uv run python -m navigator_pipeline.score_all` first"
            )
        self._con = duckdb.connect()
        for t in TABLES:
            src = (self.path / f"{t}.parquet").as_posix()
            self._con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{src}')")
        self._lock = threading.Lock()
        manifest = self.path / "manifest.json"
        self.manifest = json.loads(manifest.read_text()) if manifest.exists() else {}

    def _rows(self, query: str, params: list | None = None) -> list[dict]:
        with self._lock:  # one DuckDB connection, used by one thread at a time
            cur = self._con.execute(query, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    def resolve(self, parcel: str) -> str | None:
        """County ID for a county ID or a dashed block-lot; None when not in the dataset."""
        key = parcel.strip().upper()
        if COUNTY_ID.match(key):
            return key
        hit = self._rows("SELECT parcel_id FROM parcels WHERE upper(block_lot) = ?", [key])
        return hit[0]["parcel_id"] if hit else None

    def summary(self, parcel: str) -> dict | None:
        pid = self.resolve(parcel)
        rows = self._rows("SELECT * FROM parcels WHERE parcel_id = ?", [pid]) if pid else []
        return rows[0] if rows else None

    def analysis(self, parcel: str) -> dict | None:
        return self._json("analyses", "analysis", parcel)

    def context(self, parcel: str) -> dict | None:
        return self._json("contexts", "context", parcel)

    def programs(self, parcel: str) -> list[dict]:
        pid = self.resolve(parcel)
        q = "SELECT * FROM programs WHERE parcel_id = ? ORDER BY product"
        return self._rows(q, [pid]) if pid else []

    def sql(self, query: str, params: list | None = None) -> list[dict]:
        return self._rows(query, params)

    def _json(self, table: str, column: str, parcel: str) -> dict | None:
        pid = self.resolve(parcel)
        if not pid:
            return None
        rows = self._rows(f"SELECT {column} FROM {table} WHERE parcel_id = ?", [pid])
        return json.loads(rows[0][column]) if rows else None


def load(path: Path | str = SCORES) -> Scores:
    return Scores(Path(path))
