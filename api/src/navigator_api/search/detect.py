"""What did the user type into the search box? (docs/05-ai-search.md, "Detection")

Mirrored in web/src/search/detect.ts for instant feedback; both are tested against
fixtures/search/detect_cases.json.
"""

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["parcel_id", "address", "description", "empty"]
IdFormat = Literal["county", "block_lot"]

# Dashed or compact, complete or partial (autocomplete from 6 characters).
COUNTY_ID = re.compile(r"^\d{4}-?[A-Z](-?\d{0,5}(-?\d{0,4}(-?\d{0,2})?)?)?$", re.IGNORECASE)
BLOCK_LOT = re.compile(r"^\d{1,3}-[A-Z]-\d{1,4}[A-Z]?$", re.IGNORECASE)
STREET_SUFFIXES = (
    "st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|way|ln|lane|pl|place|ct|court|"
    "ter|terrace|pkwy|hwy|cir|circle"
)
# A house number, then a street suffix within the next few words.
ADDRESS = re.compile(rf"^\d+[A-Z]?\s+(\w+\s+){{0,4}}({STREET_SUFFIXES})\b", re.IGNORECASE)
MIN_ID_CHARS = 6


@dataclass(frozen=True)
class Detection:
    kind: Kind
    format: IdFormat | None = None


def detect(text: str) -> Detection:
    value = text.strip()
    if not value:
        return Detection("empty")
    if BLOCK_LOT.match(value):
        return Detection("parcel_id", "block_lot")
    if len(value) >= MIN_ID_CHARS and COUNTY_ID.match(value):
        return Detection("parcel_id", "county")
    if ADDRESS.match(value):
        return Detection("address")
    return Detection("description")
