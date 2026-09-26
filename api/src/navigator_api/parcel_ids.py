"""Allegheny County parcel IDs: the canonical form is compact, e.g. `0055A00137000000`.

Users also type the dashed form (`0055-A-00137-0000-00`). The city block-lot (`55-A-137`) is a
separate identifier and is resolved by lookup, not here.
"""

import re

_COUNTY_ID = re.compile(r"^(\d{4})-?([A-Z])-?(\d{5})-?(\d{4})-?(\d{2})$")


def normalize_county_id(text: str) -> str | None:
    """Return the compact county parcel ID, or None if `text` is not a complete one."""
    match = _COUNTY_ID.match(text.strip().upper())
    return "".join(match.groups()) if match else None
