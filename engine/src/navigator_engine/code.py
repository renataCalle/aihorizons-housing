"""Zoning code references: where each cited section comes from, its date, and what it says.

The rules tables were read from the Pittsburgh Zoning Code (Title Nine) as published on
eCode360 and downloaded on CODE_AS_OF. `config/rules/code_sections.csv` holds one row per cited
section: title, latest amendment date, a one-line plain-language summary (drafted from the
code text, `reviewed_by` empty until a person checks it) and a link.
"""

import csv
import io
import re
from datetime import date
from importlib.resources import files

CODE_SOURCE = "Pittsburgh Zoning Code (Title Nine)"
CODE_URL = "https://ecode360.com/PI6865"  # the code on eCode360, as cited on every page
CODE_AS_OF = date(2026, 9, 26)  # "Downloaded from https://ecode360.com/PI6865 on 2026-09-26"

# 903.03, 906.02.F.2.a, 911.04.A.69A, 911.04.A.69(a)(1), 925.06.C
SECTION = re.compile(
    r"\b9\d\d\.\d\d"  # chapter.section
    r"(?:\.[A-Z](?:\.\d+[A-Z]?(?:\.[a-z]{1,2})?)?)?"  # .F.2.a / .A.69A
    r"(?:\([a-z0-9]+\))*"  # (a)(1)
)


def _load() -> dict[str, dict]:
    text = (files("navigator_engine") / "config" / "rules" / "code_sections.csv").read_text()
    return {r["section"]: r for r in csv.DictReader(io.StringIO(text))}


SECTIONS = _load()


def sections_in(text: str | None) -> list[str]:
    """Section numbers cited in a string such as '906.05.B.2 / 913.02.B'."""
    return SECTION.findall(text or "")


def _parents(section: str) -> list[str]:
    """906.02.F.2.a -> 906.02.F.2.a, 906.02.F.2, 906.02.F, 906.02 (most specific first)."""
    out, s = [section], section
    while True:
        cut = max(s.rfind("."), s.rfind("("))
        if cut <= 3:  # stop at NNN.NN (its only dot is at index 3)
            return out
        s = s[:cut]
        out.append(s)


def lookup(section: str) -> dict:
    """Glossary fields for a section: each taken from the most specific of the section and its
    parents that has it (a subsection often has a summary but inherits the section's date)."""
    rows = [SECTIONS[s] for s in _parents(section) if s in SECTIONS]
    fields = ("title", "summary", "url", "effective_date")
    return {f: next((r[f] for r in rows if r.get(f)), None) for f in fields}


def evidence(section: str) -> dict:
    """Evidence for a finding that rests on a code rule (not on a map layer)."""
    row = lookup(section)
    return {
        "source": CODE_SOURCE,
        "as_of": CODE_AS_OF.isoformat(),
        "layer": "rules",
        "code_section": section,
        "url": row.get("url") or CODE_URL,
    }


def glossary(cited: list[str]) -> list[dict]:
    """One CodeSection per distinct cited section, in first-cited order."""
    out = []
    for section in dict.fromkeys(cited):
        row = lookup(section)
        out.append(
            {
                "section": section,
                "title": row["title"],
                "summary": row["summary"],
                "url": row["url"] or CODE_URL,
                "as_of": CODE_AS_OF.isoformat(),
                "effective": row["effective_date"],
            }
        )
    return out
