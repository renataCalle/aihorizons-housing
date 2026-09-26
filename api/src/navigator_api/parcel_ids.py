"""Allegheny County parcel IDs: the canonical form is dashed, e.g. `0088-B-00044-0000-00`.

Users also type the compact form (`0088B00044000000`). The city block-lot (`16-E-25`) is a
separate identifier and is resolved by lookup, not here.
"""

import re

_COUNTY_ID = re.compile(r"^(\d{4})-?([A-Z])-?(\d{5})-?(\d{4})-?(\d{2})$")


def normalize_county_id(text: str) -> str | None:
    """Return the dashed county parcel ID, or None if `text` is not a complete one."""
    match = _COUNTY_ID.match(text.strip().upper())
    return "-".join(match.groups()) if match else None
