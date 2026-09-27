"""Search box lookup: parcel IDs, block-lots and addresses. Never sent to the AI model."""

import re

from navigator_api.models import LookupMatch, LookupResponse, ParcelSummary
from navigator_api.search.detect import detect, should_look_up

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


# Numbered streets are written both ways: "Second Ave" and "2nd Ave".
_ORDINALS = {
    "first": "1st",
    "second": "2nd",
    "third": "3rd",
    "fourth": "4th",
    "fifth": "5th",
    "sixth": "6th",
    "seventh": "7th",
    "eighth": "8th",
    "ninth": "9th",
    "tenth": "10th",
}


def _compact_id(text: str) -> str:
    return text.replace("-", "").strip().upper()


def _address_key(text: str) -> str:
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return " ".join(_SUFFIXES.get(w, _ORDINALS.get(w, w)) for w in words)


# Words after the comma that say nothing about which parcel: the city, state, country, ZIP.
_ANYWHERE = {"pittsburgh", "pgh", "pa", "pennsylvania", "usa", "us"}


def _place_key(text: str) -> str:
    """ "Hazelwood, Pittsburgh, PA 15207" -> "hazelwood" """
    words = _address_key(text).split()
    return " ".join(w for w in words if w not in _ANYWHERE and not w.isdigit())


def _in_place(s: ParcelSummary, place: str) -> bool:
    """The parcel's neighbourhood or municipality starts with the typed place."""
    return any(
        _address_key(name).startswith(place) for name in (s.neighborhood, s.municipality) if name
    )


def _address_matches(summaries: list[ParcelSummary], text: str) -> list[ParcelSummary]:
    """Street address first; text after the first comma narrows to a neighbourhood when it
    names one of the matches ("356 Bigelow St, Hazelwood"), and is ignored otherwise."""
    street, _, rest = text.partition(",")
    query = _address_key(street)
    scored = []
    for s in summaries:
        key = _address_key(s.address or "")
        if key.startswith(query):
            scored.append((0 if key == query else 1, s))
        elif f" {query}" in f" {key}":  # at a word start: "kentuc" finds "12 Kentucky Ave"
            scored.append((2, s))
    place = _place_key(rest)
    if place:
        in_place = [(rank, s) for rank, s in scored if _in_place(s, place)]
        scored = in_place or scored
    scored.sort(key=lambda pair: (pair[0], not pair[1].candidate, pair[1].address))
    return [s for _, s in scored]


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
    elif should_look_up(text, detection):  # an address, or text that starts like one
        matches = [
            LookupMatch(matched_on="address", parcel=s) for s in _address_matches(summaries, text)
        ]

    return LookupResponse(
        kind=detection.kind, format=detection.format, matches=matches[:MAX_MATCHES]
    )
