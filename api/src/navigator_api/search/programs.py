"""What a lot is scored on in a search: the searched building type, or the engine's pick.

The engine scores every candidate for each building type; the results bundle keeps one row per
lot and type in `summaries.csv` (the largest unit count the zoning rules allow, else the
smallest tested). A search for a building type ranks lots by that type's row; a search without
one ranks by the engine's pick, which is the lot's summary. Nothing is judged here.
"""

import csv
import io
from pathlib import Path

from navigator_api.models import ParcelSummary, ProductFilter, ScoredProgram
from navigator_api.sources.bundle import ProgramRows, read_text
from navigator_contracts import Range


def _range(row: dict, prefix: str) -> Range | None:
    values = [row.get(f"{prefix}_p{q}", "") for q in (10, 50, 90)]
    if any(v == "" for v in values):
        return None
    p10, p50, p90 = map(float, values)
    return Range(p10=p10, p50=p50, p90=p90)


def _outcome(path: str) -> tuple[str, list[str]]:
    """summaries.csv `approval_path` -> outcome and relief types."""
    if path in ("by_right", "not_covered"):
        return path, []
    if path == "not_allowed":
        return "rejected", []
    return "needs_approval", path.split("+")


def load_program_rows(path: Path) -> ProgramRows:
    rows: ProgramRows = {}
    for row in csv.DictReader(io.StringIO(read_text(path))):
        score = _range(row, "score")
        outcome, relief = _outcome(row["approval_path"])
        rows.setdefault(row["parcel_id"], {})[row["product"]] = ScoredProgram(
            product_type=row["product"],
            units=int(row["units"]) if row["units"] else None,  # None: zoning not covered
            basis="up_to",
            score=round(score.p50) if score else None,
            band=row["band"] or None,
            outcome=outcome,
            relief_types=relief,
            months_to_permit=_range(row, "months"),
            max_land_price=_range(row, "max_land"),
        )
    return rows


def pick(s: ParcelSummary) -> ScoredProgram:
    """The engine's pick, as the summary (and the report) show it."""
    lead = s.lead_option
    relief = [r.split(" (")[0].strip() for r in lead.relief] if lead else []
    return ScoredProgram(
        product_type=lead.product_type if lead else None,
        units=lead.units if lead else None,
        basis="pick",
        score=s.score,
        band=s.band,
        outcome=("needs_approval" if relief else "by_right") if lead else None,
        relief_types=relief,
        months_to_permit=s.months_to_permit,
        max_land_price=s.max_land_price,
    )


def scored_for(
    s: ParcelSummary, rows: dict[str, ScoredProgram], product: ProductFilter | None
) -> ScoredProgram:
    """The searched type's row: "exact" when its unit count is the one searched, else "up to"
    the largest the rules allow. Without a type, or without rows (mock data): the pick."""
    if not product or not product.type or product.type not in rows:
        return pick(s)
    row = rows[product.type]
    exact = row.units == product.units
    return row.model_copy(update={"basis": "exact" if exact else "up_to"})


def better_fit(s: ParcelSummary, scored: ScoredProgram) -> ScoredProgram | None:
    """The engine's pick, when the lot is scored on another building type."""
    best = pick(s)
    if scored.basis == "pick" or best.product_type in (None, scored.product_type):
        return None
    return best
