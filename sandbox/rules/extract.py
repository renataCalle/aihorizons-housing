"""Draft rules-table rows from the zoning code PDFs saved in sandbox/data/manual/zoning_code/.

    uv run python -m sandbox.rules.extract

Writes sandbox/rules/residential_draft.csv: one row per district and standard, each with
its code section, effective date, source page, and the verbatim source line. Every row
ships with reviewed_by empty; a person checks each one against the PDF before it moves
into engine config (spec: "a person reviews every row before it ships").

Covers what these chapters contain: minimum lot size, setbacks, height, stories, and the
Hillside disturbance limit. Use permissions (911.02), parking (914), and coverage and
contextual rules (925) come from chapters not yet downloaded; see GAPS.
"""

import csv
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "data" / "manual" / "zoning_code"
OUT = Path(__file__).parent / "residential_draft.csv"

USE_SUBDISTRICTS = ["R1D", "R1A", "R2", "R3", "RM"]
DEV_SUBDISTRICTS = {  # heading in 903.03 -> map suffix, sub-section letter
    "Very-Low Density Subdistrict": ("VL", "A"),
    "Low Density Subdistrict": ("L", "B"),
    "Moderate Density Subdistrict": ("M", "C"),
    "High Density Subdistrict": ("H", "D"),
    "Very-High Density Subdistrict": ("VH", "E"),
}
EFFECTIVE_903_03 = "2025-05-07"  # Ord. No. 10-2025, the latest amendment cited in 903.03
EFFECTIVE_905_02 = "2005-12-30"  # Ord. 40-2005, the latest amendment cited in 905.02

STANDARDS = {  # table label -> (standard key, unit)
    "Minimum Lot Size": ("min_lot_size", "sqft"),
    "Minimum Front Setback": ("min_front_setback", "ft"),
    "Minimum Rear Setback": ("min_rear_setback", "ft"),
    "Minimum Exterior Sideyard Setback": ("min_exterior_side_setback", "ft"),
    "Minimum Interior Sideyard Setback": ("min_interior_side_setback", "ft"),
    "Maximum Height": ("max_height", "ft"),
}

GAPS = [  # (standard, section, status note)
    (
        "permitted_residential_uses",
        "911.02",
        "RESOLVED in use_permissions_draft.csv (read from the use table page image)",
    ),
    ("parking_per_unit", "914.02 / 914.04 / 914.11.B.4", "RESOLVED in standards_draft.csv"),
    ("environmental_performance", "915.02", "RESOLVED in standards_draft.csv"),
    (
        "lot_area_per_unit",
        "925.03",
        "NOT A STANDARD: the code defines density but sets no per-district limit; units follow "
        "the use subdistrict (R2=2, R3=3) and, for RM, setbacks + height + stories",
    ),
    ("max_lot_coverage", "925", "NOT A STANDARD in residential districts (none found)"),
    (
        "min_frontage",
        "925.02",
        "NOT A STANDARD: lot width is defined but no residential minimum is set",
    ),
    (
        "overlay_undermined_floodplain",
        "906",
        "RESOLVED in standards_draft.csv (906.02 FP-O floodplain, 906.05 UM-O undermined)",
    ),
    (
        "contextual_setbacks_heights",
        "925.06 / 925.07",
        "GAP: downloaded, not yet extracted (can lower required setbacks/heights to neighbors)",
    ),
    (
        "residential_compatibility",
        "916.02",
        "GAP: downloaded, not yet extracted (H/VH near residential only)",
    ),
]


def pages(pdf: Path) -> list[str]:
    text = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    return text.split("\f")


def _value(raw: str, unit: str) -> tuple[float | None, str]:
    """Parse '30 ft.', '6,000 s.f.', '40 ft. (not to exceed 3 stories)', 'none'."""
    raw = raw.strip()
    if raw.lower() == "none":
        return 0.0, ""
    m = re.match(r"([\d,]+)", raw)
    if not m:
        return None, raw
    return float(m.group(1).replace(",", "")), raw


def _applies(label: str) -> list[str]:
    """'R1D, R1A, R2 & R3 Subdistricts' -> ['R1D', 'R1A', 'R2', 'R3']."""
    return [u for u in USE_SUBDISTRICTS if re.search(rf"\b{u}\b", label)]


def residential_rows() -> list[dict]:
    pdf = CODE / "Residential Zoning Districts.pdf"
    rows: list[dict] = []
    dev = None
    standard = None
    for pno, page in enumerate(pages(pdf), start=1):
        for line in page.splitlines():
            s = line.strip()
            if s.startswith("Site Development Standard"):
                heading = s[len("Site Development Standard") :].strip()
                if heading in DEV_SUBDISTRICTS and DEV_SUBDISTRICTS[heading] != dev:
                    dev, standard = DEV_SUBDISTRICTS[heading], None
                continue
            if dev is None or not s:
                continue
            label = next((k for k in STANDARDS if s.startswith(k)), None)
            if label:
                standard = STANDARDS[label]
                rest = s[len(label) :].strip()
                if rest:  # single value for all use subdistricts (e.g. min lot size)
                    rows += _emit(dev, standard, USE_SUBDISTRICTS, rest, pno, s)
                continue
            if standard and "Subdistrict" in s:
                m = re.match(r"(.+?Subdistricts?)\s{2,}(.+)$", s)
                if m:
                    rows += _emit(dev, standard, _applies(m.group(1)), m.group(2), pno, s)
    return rows


def _emit(dev, standard, uses, raw, pno, line) -> list[dict]:
    suffix, letter = dev
    key, unit = standard
    value, text = _value(raw, unit)
    out = []
    for use in uses:
        district = f"{use}-{suffix}"
        out.append(
            _row(
                district,
                key,
                value,
                unit,
                f"903.03.{letter}.2",
                EFFECTIVE_903_03,
                "Residential Zoning Districts.pdf",
                pno,
                line,
            )
        )
        stories = re.search(r"(\d+)\s+stories", text)
        if key == "max_height" and stories:
            out.append(
                _row(
                    district,
                    "max_stories",
                    float(stories.group(1)),
                    "stories",
                    f"903.03.{letter}.2",
                    EFFECTIVE_903_03,
                    "Residential Zoning Districts.pdf",
                    pno,
                    line,
                )
            )
        if key == "min_interior_side_setback" and "other side" in text:
            out[-1]["notes"] = "Asymmetric: 5 ft one side, 10 ft the other"
    return out


def _row(district, key, value, unit, section, effective, source, page, line) -> dict:
    return {
        "district": district,
        "standard": key,
        "value": value,
        "unit": unit,
        "code_section": section,
        "effective_date": effective,
        "source_file": source,
        "source_page": page,
        "source_line": " ".join(line.split()),
        "notes": "",
        "reviewed_by": "",
    }


def hillside_rows() -> list[dict]:
    pdf = CODE / "Special Purpose Districts.pdf"
    rows = []
    in_h = False
    for pno, page in enumerate(pages(pdf), start=1):
        for line in page.splitlines():
            s = line.strip()
            if s.startswith("§ 905.02. H, Hillside"):
                in_h = True
            elif s.startswith("§ 905.03."):
                in_h = False
            if not in_h:
                continue
            for label, (key, unit) in STANDARDS.items():
                if s.startswith(label):
                    value, text = _value(s[len(label) :], unit)
                    rows.append(
                        _row("H", key, value, unit, "905.02.C", EFFECTIVE_905_02, pdf.name, pno, s)
                    )
                    stories = re.search(r"(\d+)\s+stories", text)
                    if key == "max_height" and stories:
                        rows.append(
                            _row(
                                "H",
                                "max_stories",
                                float(stories.group(1)),
                                "stories",
                                "905.02.C",
                                EFFECTIVE_905_02,
                                pdf.name,
                                pno,
                                s,
                            )
                        )
            m = re.match(r"Maximum Area of Disturbance:\s+(\d+)%", s)
            if m:
                rows.append(
                    _row(
                        "H",
                        "max_disturbance_share",
                        int(m.group(1)) / 100,
                        "share",
                        "905.02.C",
                        EFFECTIVE_905_02,
                        pdf.name,
                        pno,
                        s,
                    )
                )
    return rows


def main() -> None:
    rows = residential_rows() + hillside_rows()
    # Very-High density has no minimum lot size in the table: record that explicitly.
    for use in USE_SUBDISTRICTS:
        rows.append(
            _row(
                f"{use}-VH",
                "min_lot_size",
                None,
                "sqft",
                "903.03.E.2",
                EFFECTIVE_903_03,
                "Residential Zoning Districts.pdf",
                None,
                "",
            )
        )
        rows[-1]["notes"] = "Not listed in the VH table; confirm none applies"
    for key, section, why in GAPS:
        rows.append(
            {
                **_row("*", key, None, "", section, "", "", None, ""),
                "notes": why,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    districts = sorted({r["district"] for r in rows if r["district"] != "*"})
    print(f"wrote {OUT}: {len(rows)} rows, {len(districts)} districts")


if __name__ == "__main__":
    main()
