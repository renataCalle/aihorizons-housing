"""Zoning Board of Adjustment cases: agendas + decisions -> one row per case.

    uv run python -m navigator_pipeline.zba     # data/manual/zba/ -> data/clean/zba_cases.parquet

Reads the PDFs saved by `navigator_pipeline.zba_download`. Decisions carry a fixed header (Date
of Hearing, Date of Decision, Zone Case, Address, Lot and Block, Zoning District, Ward,
Neighborhood, Request, Application, the approvals requested with code sections) and end with
"Decision: ... is hereby APPROVED / DENIED". Agendas list every case heard, so cases without a
posted decision (pending, continued, withdrawn) are kept too.

Parsing is deterministic (regular expressions); nothing is guessed. Names of applicants,
owners, witnesses and board members are never read into the table.
"""

import argparse
import logging
import re
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pypdf import PdfReader

from navigator_pipeline.settings import CLEAN, FEATURES, MANUAL

ZBA = MANUAL / "zba"
OUT = CLEAN / "zba_cases.parquet"

RELIEF = (
    r"(Use Variance|Variance|Special Exception|Administrator Exception|Appeal|Conditional Use)s?"
)
DATE = r"([A-Z][a-z]+\.? \d{1,2}, ?\d{4})"
# Where one request starts: no capture groups (re.split would return them), and "Variance"
# inside "Use Variance" is not a second request.
SPLIT = re.compile(
    r"(?=(?:Use Variance|(?<!Use )Variance|Special Exception|Administrator Exception|Appeal"
    r"|Conditional Use)s?\b)"
)
SECTION = re.compile(r"\b9\d\d\.\d\d(?:\.[A-Za-z0-9]+)*")
# Outcomes that decide an approval, for the model; the others did not rule on one.
DECIDED = {"granted", "granted_with_conditions", "partial", "denied"}

logging.getLogger("pypdf").setLevel(logging.ERROR)  # city PDFs have harmless xref warnings


def text_of(pdf: Path) -> str:
    """Whole document as one line of text."""
    pages = PdfReader(pdf).pages
    return " ".join(" ".join((p.extract_text() or "") for p in pages).split())


def _date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.replace(".", "").replace(", ", ",").replace(",", ", ")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _field(t: str, label: str, nxt: str) -> str | None:
    m = re.search(rf"{label}:\s*(.*?)\s+{nxt}:", t)
    return m.group(1).strip() if m else None


def block_lots(s: str | None) -> list[str]:
    """'9-M-97, 9-M-99-A and 9-M-100' -> ['9-M-97', '9-M-99-A', '9-M-100']."""
    return re.findall(r"\b\d{1,4}-[A-Z]-\d{1,4}(?:-[A-Z0-9]{1,3})?\b", s or "")


def reliefs(block: str) -> list[dict]:
    """Approvals requested, each with its code sections and description."""
    out = []
    parts = re.split(SPLIT, block)
    for part in parts:
        m = re.match(RELIEF, part)
        if not m:
            continue
        rest = part[m.end() :]
        out.append(
            {
                "type": m.group(1).lower().replace(" ", "_"),
                "sections": SECTION.findall(rest),
                "description": rest.strip(" :")[:300],
            }
        )
    return out


def outcome(t: str) -> str:
    """granted | granted_with_conditions | partial | denied | withdrawn | nonconforming (the use
    may continue, no approval needed) | no_relief_needed | unknown."""
    tail = re.split(r"(?<!Date of )Decision:", t)[-1]
    tail = tail.split(" s/")[0].split("RECUSED")[0]
    up = tail.upper()
    granted = bool(re.search(r"\b(APPROVED|GRANTED)\b", up))
    denied = bool(re.search(r"\bDENIED\b", up))
    if granted and denied:
        return "partial"
    if denied:  # "one sign withdrawn, the other denied" is a denial
        return "denied"
    if re.search(r"\bWITHDRAWN\b|\bDISMISSED\b", up) and not granted:
        return "withdrawn"
    if granted:
        return "granted_with_conditions" if re.search(r"SUBJECT TO|CONDITION", up) else "granted"
    if "LEGALLY NONCONFORMING" in up:
        return "nonconforming"
    if re.search(r"NO (ADDITIONAL )?RELIEF IS REQUIRED|ALLOWED BY-RIGHT|ALLOWED BY RIGHT", up):
        return "no_relief_needed"
    return "unknown"


def parse_decision(t: str) -> dict | None:
    """Structured fields of one decision; None when the document is not a board decision.

    A decision opens with its header; staff reports and applications that quote an older
    decision further down are not decisions of this hearing."""
    head = t[:1500]
    if "Date of Hearing" not in head or "Date of Decision" not in head or "Zone Case" not in head:
        return None
    case = re.search(r"Zone Case:\s*(\d+)\s*of\s*(\d{4})", t)
    if not case:
        return None
    request_block = t.split("Application:", 1)[-1].split("Appearances:", 1)[0]
    application = re.match(r"\s*(\S+)", request_block)
    return {
        "case_id": f"{int(case.group(1))} of {case.group(2)}",
        "hearing_date": _date((re.search(rf"Date of Hearing:\s*{DATE}", t) or [None, None])[1]),
        "decision_date": _date((re.search(rf"Date of Decision:\s*{DATE}", t) or [None, None])[1]),
        "address": _field(t, "Address", "Lot and Block"),
        "block_lots": block_lots(_field(t, "Lot and Block", r"Zoning Districts?")),
        "district": _field(t, r"Zoning Districts?", "Ward"),
        "neighborhood": _field(t, "Neighborhood", "Request"),
        "request": _field(t, "Request", "Application"),
        "application": application.group(1) if application else None,
        "reliefs": reliefs(request_block),
        "opposition": None
        if "oppos" not in t.lower()
        else not bool(re.search(r"no one appeared (at the hearing )?to oppose", t, re.I)),
        "outcome": outcome(t),
    }


def parse_agenda(t: str, hearing: date | None) -> list[dict]:
    """Cases on one hearing agenda."""
    out = []
    for chunk in re.split(r"(?=Zone Case:)", t)[1:]:
        case = re.search(r"Zone Case:\s*(\d+)\s*of\s*(\d{4})", chunk)
        if not case:
            continue
        body = chunk[case.end() :]
        district = re.search(r"Zoning District:\s*(\S+)", body)
        neighborhood = re.search(r"Neighborhood:\s*(.*?)\s+(?:" + RELIEF + r"|[A-Z]{3}-)", body)
        address = body.strip().split(" Zoning District:")[0].strip()
        out.append(
            {
                "case_id": f"{int(case.group(1))} of {case.group(2)}",
                "agenda_hearing_date": hearing,
                "agenda_address": address[:120],
                "agenda_district": district.group(1) if district else None,
                "agenda_neighborhood": neighborhood.group(1) if neighborhood else None,
                "agenda_reliefs": reliefs(body.split("Page ")[0]),
            }
        )
    return out


STREET_ABBR = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "DRIVE": "DR",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "PLACE": "PL",
    "COURT": "CT",
    "LANE": "LN",
    "TERRACE": "TER",
}


def _norm_address(a: str | None) -> str | None:
    """'1715- 1717 Cliff Street' -> '1715 CLIFF ST' (first house number, standard suffix)."""
    if not isinstance(a, str) or not a.strip():
        return None
    words = re.sub(r"[^A-Z0-9 ]", " ", a.upper()).split()
    if words and words[0].isdigit():
        while len(words) > 1 and words[1].isdigit():  # '1715 1717 Cliff' -> '1715 Cliff'
            words.pop(1)
    return " ".join(STREET_ABBR.get(w, w) for w in words) or None


def link_parcels(
    cases: pd.DataFrame, clean: Path = CLEAN, features: Path = FEATURES
) -> pd.DataFrame:
    """Add the county parcel(s) each case is about, their location and the facts the model
    uses. Match on the decision's lot-and-block, then its base lot (9-M-99-A -> 9-M-99), then
    the street address."""
    parcels = gpd.read_parquet(
        clean / "parcels.parquet", columns=["parcel_id", "block_lot", "address", "geometry"]
    )
    by_bl = parcels.set_index("block_lot")["parcel_id"].to_dict()
    by_addr = (
        parcels.dropna(subset=["address"])
        .drop_duplicates("address")
        .set_index("address")["parcel_id"]
        .to_dict()
    )
    facts = pd.read_parquet(
        features / "parcel_facts.parquet",
        columns=["parcel_id", "lot_area_sqft_gis", "mva_market_type", "zoning_primary"],
    ).set_index("parcel_id")
    centroid = parcels.set_index("parcel_id").geometry.centroid

    def match(row) -> tuple[list[str], str]:
        found, how = [], None
        for bl in row["block_lots"] if isinstance(row.get("block_lots"), (list, tuple)) else []:
            pid = by_bl.get(bl) or by_bl.get("-".join(bl.split("-")[:3]))
            if pid:
                found.append(pid)
                how = how or ("block_lot" if bl in by_bl else "base_lot")
        if not found:
            addresses = [
                a for a in (row.get("address"), row.get("agenda_address")) if isinstance(a, str)
            ]
            pid = next((by_addr[n] for a in addresses if (n := _norm_address(a)) in by_addr), None)
            if pid:
                found, how = [pid], "address"
        return list(dict.fromkeys(found)), how or "unmatched"

    matched = cases.apply(match, axis=1, result_type="expand")
    cases = cases.assign(parcel_ids=matched[0], parcel_match=matched[1])
    cases["parcel_id"] = cases["parcel_ids"].map(lambda ids: ids[0] if ids else None)
    known = [ids for ids in cases["parcel_ids"]]
    cases["lot_area_sqft"] = [
        float(facts.reindex(ids)["lot_area_sqft_gis"].sum()) if ids else None for ids in known
    ]
    first = facts.reindex(cases["parcel_id"])
    cases["mva_market_type"] = first["mva_market_type"].to_numpy()
    cases["zoning_primary"] = first["zoning_primary"].to_numpy()
    pts = centroid.reindex(cases["parcel_id"])
    cases["x"], cases["y"] = pts.x.to_numpy(), pts.y.to_numpy()
    return cases


def _file_date(path: Path) -> date | None:
    """Downloaded files are named '<hearing date>__<original name>'."""
    try:
        return date.fromisoformat(path.name.split("__", 1)[0])
    except ValueError:
        return None


def build(zba_dir: Path = ZBA) -> pd.DataFrame:
    decisions, skipped = {}, 0
    for pdf in sorted((zba_dir / "decisions").glob("*.pdf")):
        if re.search(r"staff[-_ ]?report|zba[-_ ]request", pdf.name, re.I):
            skipped += 1
            continue
        row = parse_decision(text_of(pdf))
        if row is None:
            skipped += 1
            continue
        row["source_file"] = pdf.name
        prev = decisions.get(row["case_id"])
        if prev is None or (row["decision_date"] or date.min) > (prev["decision_date"] or date.min):
            decisions[row["case_id"]] = row  # a case decided twice keeps the latest decision
    agenda_rows = []
    for pdf in sorted((zba_dir / "agendas").glob("*.pdf")):
        agenda_rows += parse_agenda(text_of(pdf), _file_date(pdf))
    agendas = pd.DataFrame(agenda_rows)
    heard = (
        agendas.groupby("case_id")
        .agg(
            times_on_agenda=("agenda_hearing_date", "size"),
            first_hearing=("agenda_hearing_date", "min"),
            last_hearing=("agenda_hearing_date", "max"),
            agenda_address=("agenda_address", "last"),
            agenda_district=("agenda_district", "last"),
            agenda_neighborhood=("agenda_neighborhood", "last"),
            agenda_reliefs=("agenda_reliefs", "last"),
        )
        .reset_index()
        if len(agendas)
        else pd.DataFrame(columns=["case_id"])
    )
    cases = pd.DataFrame(list(decisions.values()))
    cases = heard.merge(cases, on="case_id", how="outer") if len(cases) else heard
    cases["outcome"] = cases["outcome"].fillna("no_decision_posted")
    cases = link_parcels(cases)
    cases.attrs["skipped_documents"] = skipped
    return cases.sort_values("case_id").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ZBA)
    args = ap.parse_args()
    cases = build(args.dir)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cases.to_parquet(OUT, index=False)
    print(f"wrote {OUT}: {len(cases)} cases; outcomes {cases['outcome'].value_counts().to_dict()}")
    print(f"skipped {cases.attrs['skipped_documents']} documents that are not board decisions")
    print(f"parcel match: {cases['parcel_match'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
