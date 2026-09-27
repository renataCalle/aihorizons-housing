"""Zoning Board decision and agenda parsing (synthetic text; no real names)."""

from datetime import date

from navigator_pipeline import zba

HEADER = (
    "Division of Development Administration and Review City of Pittsburgh ZONING BOARD OF "
    "ADJUSTMENT Date of Hearing: January 2, 2025 Date of Decision: February 10, 2025 "
    "Zone Case: 012 of 2025 Address: 100 Example Street Lot and Block: 9-M-99-A and 9-M-100 "
    "Zoning Districts: R1D-M Ward: 20 Neighborhood: Sample Hill Request: Two-unit dwelling "
    "Application: BDA-2025-00001 Variance Section 903.03.C.2 3,000 sf minimum lot size per unit; "
    "1,500 sf requested Special Exception Section 911.02 Two-unit residential "
    "Appearances: Applicant: A. Person Findings of Fact: 1. No one appeared at the hearing to "
    "oppose the request. "
)


def test_decision_header_is_parsed() -> None:
    row = zba.parse_decision(HEADER + "Decision: The request is hereby APPROVED. s/Chair")
    assert row["case_id"] == "12 of 2025"
    assert row["hearing_date"] == date(2025, 1, 2) and row["decision_date"] == date(2025, 2, 10)
    assert row["block_lots"] == ["9-M-99-A", "9-M-100"]
    assert row["district"] == "R1D-M" and row["neighborhood"] == "Sample Hill"
    assert row["application"] == "BDA-2025-00001"
    assert [r["type"] for r in row["reliefs"]] == ["variance", "special_exception"]
    assert row["reliefs"][0]["sections"] == ["903.03.C.2"]
    assert row["opposition"] is False
    assert "Person" not in str(row)  # names are never read into the row


def test_outcomes() -> None:
    cases = {
        "is hereby APPROVED.": "granted",
        "is hereby APPROVED, subject to the condition that": "granted_with_conditions",
        "is DENIED.": "denied",
        "is hereby APPROVED, and the request for signs is DENIED.": "partial",
        "is legally nonconforming and may continue.": "nonconforming",
        "is allowed by-right, and no additional relief is required.": "no_relief_needed",
        "is WITHDRAWN.": "withdrawn",
        "for sign 1 is WITHDRAWN and for sign 2 is DENIED.": "denied",
        "was continued.": "unknown",
    }
    for text, expected in cases.items():
        assert zba.outcome(HEADER + "Decision: The request " + text + " s/Chair") == expected


def test_documents_that_quote_a_decision_are_not_decisions() -> None:
    staff_report = "Staff report for a new application. " + "x " * 800 + HEADER
    assert zba.parse_decision(staff_report + "Decision: APPROVED.") is None


def test_agenda_cases() -> None:
    agenda = (
        "Page 2 of 5 Date of Hearing: August 20, 2026 Zone Case: 80 of 2026 411 Example Street "
        "Zoning District: R2-VH Ward: 8 Council District: 7 Neighborhood: Sampleton Subdivision "
        "DCP-LOT-2026-00132 Variance: Section 926.129 Street frontage is required "
        "Zone Case: 108 of 2026 1 Sample Way Zoning District: UI Ward: 5 Neighborhood: Mill "
        "Special Exception: Section 911.02 Use Variance: Section 916.02.B height"
    )
    rows = zba.parse_agenda(agenda, date(2026, 8, 20))
    assert [r["case_id"] for r in rows] == ["80 of 2026", "108 of 2026"]
    assert rows[0]["agenda_district"] == "R2-VH"
    assert [r["type"] for r in rows[1]["agenda_reliefs"]] == ["special_exception", "use_variance"]


def test_plural_request_headings() -> None:
    block = "BDA-1 Special Exceptions Variances Sections 911.02/916.04.A 50' setback required"
    assert [r["type"] for r in zba.reliefs(block)] == ["special_exception", "variance"]


def test_addresses_normalize_for_matching() -> None:
    assert zba._norm_address("1715- 1717 Cliff Street") == "1715 CLIFF ST"
    assert zba._norm_address("4560 Friendship Avenue") == "4560 FRIENDSHIP AVE"
    assert zba._norm_address(None) is None
