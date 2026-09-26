"""Search box lookup: parcel IDs, block-lots and addresses. Never sent to the AI model."""

import re

from navigator_api.models import LookupMatch, LookupResponse, ParcelSummary
from navigator_api.search.detect import detect

MAX_MATCHES = 8

# Normalize street suffixes so "205 Example Avenue" finds "205 Example Ave".
_SUFFIXES = {
    "street": "st",
    "avenue": "ave",
    "boulevard": "blvd",
    "road": "rd",
    "drive": "dr",
    "lane": "ln",
    "place": "pl",
    "court": "ct",
    "terrace": "ter",
    "parkway": "pkwy",
    "highway": "hwy",
    "circle": "cir",
}


def _compact_id(text: str) -> str:
    return text.replace("-", "").strip().upper()


def _address_key(text: str) -> str:
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return " ".join(_SUFFIXES.get(w, w) for w in words)


def lookup(summaries: list[ParcelSummary], text: str) -> LookupResponse:
    detection = detect(text)
    matches: list[LookupMatch] = []

    if detection.kind == "parcel_id" and detection.format == "county":
        prefix = _compact_id(text)
        matches = [
            LookupMatch(matched_on="county_id", parcel=s)
            for s in summaries
            if s.parcel_id.startswith(prefix)
        ]
    elif detection.kind == "parcel_id":
        query = text.strip().upper()
        found = [s for s in summaries if s.block_lot and s.block_lot.upper().startswith(query)]
        found.sort(key=lambda s: (s.block_lot.upper() != query, s.block_lot))
        matches = [LookupMatch(matched_on="block_lot", parcel=s) for s in found]
    elif detection.kind == "address":
        query = _address_key(text)
        scored = []
        for s in summaries:
            key = _address_key(s.address or "")
            if key.startswith(query):
                scored.append((0 if key == query else 1, s))
            elif query in key:
                scored.append((2, s))
        scored.sort(key=lambda pair: (pair[0], not pair[1].candidate, pair[1].address))
        matches = [LookupMatch(matched_on="address", parcel=s) for _, s in scored]

    return LookupResponse(
        kind=detection.kind, format=detection.format, matches=matches[:MAX_MATCHES]
    )
