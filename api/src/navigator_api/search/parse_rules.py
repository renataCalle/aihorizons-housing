"""Rule-based parser: plain-language text to SearchFilters, with no AI (docs/05, "Fallback").

It must always work, so the demo never breaks without an API key. It only sets filters for
phrases it recognizes and reports what it couldn't map; it never guesses numbers.
"""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from navigator_api.models import Reading
from navigator_api.search.vocabulary import (
    ALIASES,
    FLAT_MAX_STEEP_PCT,
    NEIGHBORHOODS,
    PUBLIC_OWNERS,
    QUARTER_MILE_FT,
    VARIANCES_OK,
    money,
)

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a pair of": 2,
}  # fmt: skip

# Building types the engine evaluates, and the words people use for them.
PRODUCT_WORDS = {
    "townhome": ["townhomes", "townhome", "townhouses", "townhouse", "rowhouses", "rowhouse"],
    "duplex": ["duplexes", "duplex", "two-family", "two family"],
    "triplex": ["triplexes", "triplex", "three-family", "three family"],
    "walkup": ["walk-ups", "walk-up", "walkups", "walkup", "apartment building", "apartments"],
    "single_family": ["single-family", "single family", "houses", "house"],
}
GENERIC_HOMES = r"homes|units|houses"

# Places people might name that the city's zoning rules don't cover.
OUTSIDE_CITY = [
    "Mt Lebanon", "Mt. Lebanon", "Mount Lebanon", "Wilkinsburg", "Dormont", "Bethel Park",
    "Upper St. Clair", "Penn Hills", "Monroeville", "McKeesport", "Sewickley", "Bellevue",
    "Millvale", "Etna", "Sharpsburg", "Homestead", "Munhall", "West Mifflin", "Baldwin",
    "Brentwood", "Whitehall", "Crafton", "Carnegie", "Ross", "Shaler", "Cranberry",
]  # fmt: skip

# Things people ask for that are not filters in v1: they go to "not understood".
UNSUPPORTED = [
    r"good schools?", r"school quality", r"\bcrime\b", r"\bsafe(?:ty)?\b", r"\bviews?\b",
    r"\bquiet\b", r"\brental\b", r"\bfor rent\b", r"\bfor sale\b", r"\bcondos?\b",
    r"\badus?\b", r"granny flats?", r"carriage houses?", r"accessory dwelling units?",
]  # fmt: skip


@dataclass
class Parsed:
    updates: dict = field(default_factory=dict)
    readings: list[Reading] = field(default_factory=list)
    not_understood: list[str] = field(default_factory=list)

    def set(self, key: str, value, phrase: str, meaning: str) -> None:
        self.updates[key] = value
        self.readings.append(Reading(phrase=phrase.strip(), interpreted_as=meaning))


def _number(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def _amount(number: str, suffix: str | None) -> float:
    value = float(number.replace(",", ""))
    suffix = (suffix or "").lower()
    if suffix in ("k", "grand", "thousand"):
        value *= 1_000
    elif suffix in ("m", "million"):
        value *= 1_000_000
    return value


MONEY = r"\$?\s?(\d[\d,]*(?:\.\d+)?)\s?(k|grand|thousand|m|million)?\b"
NUM = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"


def _products(text: str, out: Parsed) -> None:
    lower = text.lower()
    found_type = None
    phrase = ""
    for product, words in PRODUCT_WORDS.items():
        for word in words:
            m = re.search(rf"\b{re.escape(word)}\b", lower)
            if m:
                found_type, phrase = product, m.group(0)
                break
        if found_type:
            break
    if not found_type:
        # Typos: "towhnomes" -> townhomes.
        vocab = {w: p for p, ws in PRODUCT_WORDS.items() for w in ws if len(w) > 5}
        for token in re.findall(r"[a-z-]{6,}", lower):
            hit = process.extractOne(token, list(vocab), scorer=fuzz.ratio, score_cutoff=80)
            if hit:
                found_type, phrase = vocab[hit[0]], token
                break
    type_words = "|".join(re.escape(w) for ws in PRODUCT_WORDS.values() for w in ws)
    units = None
    unit_phrase = ""
    # "3 or 4 townhomes", "3-4 units": the lower bound.
    m = re.search(
        rf"\b{NUM}\s*(?:or|to|-)\s*{NUM}\s+(?:\w+\s+)?({type_words}|{GENERIC_HOMES})\b", lower
    )
    if m:
        units, unit_phrase = _number(m.group(1)), m.group(0)
        out.readings.append(
            Reading(phrase=m.group(0), interpreted_as=f"At least {units} units (the lower bound)")
        )
    else:
        m = re.search(
            rf"\b{NUM}[\s-]*(?:unit\s+)?(?:\w+\s+)?({type_words}|{GENERIC_HOMES}|units?)\b",
            lower,
        )
        if m and _number(m.group(1)):
            units, unit_phrase = _number(m.group(1)), m.group(0)
    if found_type or units:
        value = {"type": found_type, "units": units}
        label = (found_type or "any building type").replace("_", " ")
        meaning = f"{label}, at least {units} units" if units else label
        out.set("product", value, unit_phrase or phrase, meaning.capitalize())


def _areas(text: str, out: Parsed) -> None:
    lower = text.lower()
    areas: list[str] = []
    phrases: list[str] = []
    # Exact names first ("Squirrel Hill South"), then nicknames ("Squirrel Hill").
    for name in sorted(NEIGHBORHOODS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name.lower())}\b", lower):
            if name not in areas:
                areas.append(name)
            phrases.append(name)
            lower = lower.replace(name.lower(), " ")
    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            areas += [a for a in ALIASES[alias] if a not in areas]
            phrases.append(alias)
            lower = lower.replace(alias, " ")
    # Typos: one- and two-word spans close to a neighborhood name ("hazlewood").
    words = re.findall(r"[a-z.'-]+", lower)
    spans = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
    names = [n.lower() for n in NEIGHBORHOODS]
    for span in spans:
        if len(span) < 5:
            continue
        hit = process.extractOne(span, names, scorer=fuzz.ratio, score_cutoff=88)
        if hit:
            name = NEIGHBORHOODS[hit[2]]
            if name not in areas:
                areas.append(name)
                phrases.append(span)
    if areas:
        out.set("areas", areas, ", ".join(phrases), "In " + ", ".join(areas))


def _money(text: str, out: Parsed) -> None:
    lower = text.lower()
    site = re.search(
        rf"(site work|site costs?|site premium)[^$\d]{{0,30}}(?:under|below|less than|<)\s*{MONEY}",
        lower,
    )
    if site:
        value = _amount(site.group(2), site.group(3))
        out.set("max_site_cost_premium", value, site.group(0), f"Site costs at most {money(value)}")
        lower = lower.replace(site.group(0), " ")
    land = re.search(
        r"(?:land\s+(?:is\s+)?(?:worth\s+)?|price\s+)?"
        rf"(?:under|below|less than|max|<|up to)\s*{MONEY}",
        lower,
    )
    if land and ("$" in land.group(0) or land.group(2)):
        value = _amount(land.group(1), land.group(2))
        out.set(
            "max_land_price",
            value,
            land.group(0),
            f"Max land price {money(value)}, not total project cost",
        )


def _measures(text: str, out: Parsed) -> None:
    lower = text.lower()
    lot = re.search(
        r"(bigger than|larger than|over|at least|more than|under|smaller than|less than)\s*"
        r"(\d[\d,]*)\s*(?:sq\.?\s*ft|square feet|sf)\b",
        lower,
    )
    if lot:
        value = float(lot.group(2).replace(",", ""))
        at_least = lot.group(1) in ("bigger than", "larger than", "over", "at least", "more than")
        key = "lot_min_sqft" if at_least else "lot_max_sqft"
        out.set(key, value, lot.group(0), f"Lot {'at least' if at_least else 'at most'} "
                f"{value:,.0f} sq ft")  # fmt: skip
    margin = re.search(
        r"margin\s*(?:of\s*)?(?:at least|above|over|>=?)?\s*(\d+(?:\.\d+)?)\s*%", lower
    )
    if margin:
        value = float(margin.group(1))
        out.set("min_margin_pct", value, margin.group(0), f"Margin at least {value:g}%")
    score = re.search(r"score\s*(?:above|over|at least|>=?)\s*(\d+)", lower)
    if score:
        value = int(score.group(1))
        out.set("min_score", value, score.group(0), f"Score at least {value}")
    months = re.search(r"(?:under|within|less than|in under)\s*(\d+)\s*months?", lower)
    if months:
        value = int(months.group(1))
        out.set(
            "max_months_to_permit",
            value,
            months.group(0),
            f"Permit-ready in {value} months or less",
        )


# (pattern, field, value, meaning). First match per field wins.
PHRASES: list[tuple[str, str, object, str]] = [
    (r"no steep slopes?|not steep", "max_steep_slope_pct", 0, "No steep slope"),
    (r"\bflat\b|\blevel\b", "max_steep_slope_pct", FLAT_MAX_STEEP_PCT,
     f"Flat lots (under {FLAT_MAX_STEEP_PCT}% steep slope)"),
    (r"no hearings?|without (?:going to )?the zoning board|by[ -]right", "approval_paths",
     ["by_right"], "By-right only"),
    (r"allow(?:ing)? variances?|variances? (?:ok|okay|are fine)", "approval_paths", VARIANCES_OK,
     "Variances OK"),
    (r"\bcheap(?:est)?\b", "sort", "cheapest", "Cheapest land first (not a price cap)"),
    (r"\bfast(?:est)?\b(?![ -]track)", "sort", "fastest", "Fastest to permit first"),
    (r"headroom", "sort", "headroom_desc", "Most land-price headroom first"),
    (r"public land|publicly owned", "owner_types", PUBLIC_OWNERS, "Public land"),
    (r"\bvacant\b", "vacant_only", True, "Vacant only"),
    (r"tax[ -]delinquent|back taxes|tax liens?", "tax_delinquent_only", True, "Tax-delinquent"),
    (r"near miss(?:es)?|almost works?|one rule away", "show_near_misses", True,
     "Show near misses"),
    (r"work together|assembl(?:y|ies|e)|combine lots", "show_assemblies", True,
     "Show assemblies"),
    (r"(?:exclude|hide|no) unknowns?", "include_unknowns", False, "Hide unknowns"),
    (r"\beverything\b|include unknowns?", "include_unknowns", True, "Include unknowns"),
]  # fmt: skip

NEAR = [
    (r"bus stops?|transit|busway|\bthe t\b|light rail|minute walk|walkable",
     "transit_stop", "transit"),
    (r"near (?:a |the )?parks?|park nearby", "park", "a park"),
    (r"near (?:a |the )?schools?|school nearby", "school", "a school"),
    (r"grocer(?:y|ies)|supermarket", "grocery", "a grocery store"),
]  # fmt: skip

OWNERS = [
    (r"land bank", "land_bank"),
    (r"\bura\b", "ura"),
    (r"city[ -]owned|\bcity\b(?= owned| lots)", "city"),
]
CONSTRAINTS = [
    (r"(?:not|no|outside|avoid)[^,.]{0,12}flood", "flood_zone", "Outside flood zones"),
    (r"(?:not|no|avoid)[^,.]{0,6}undermin", "undermined", "No undermining"),
    (r"(?:avoid|no|not|outside)[^,.]{0,12}combined sewer", "combined_sewer",
     "Outside combined sewersheds"),
    (r"(?:no|avoid)[^,.]{0,6}landslide", "landslide", "No landslide-prone ground"),
]  # fmt: skip
BANDS = [
    (r"fast[ -]track", "fast_track", "Fast track only"),
    (r"high[ -]risk", "high_risk", "High risk only"),
]


def _phrases(text: str, out: Parsed) -> None:
    lower = text.lower()
    for pattern, key, value, meaning in PHRASES:
        m = re.search(pattern, lower)
        if m and key not in out.updates:
            out.set(key, value, m.group(0), meaning)
    near = []
    for pattern, feature, name in NEAR:
        m = re.search(pattern, lower)
        if m:
            near.append({"feature": feature, "within_ft": QUARTER_MILE_FT})
            out.readings.append(Reading(phrase=m.group(0), interpreted_as=f"Within ¼ mi of {name}"))
    if near:
        out.updates["near"] = near
    owners = [owner for pattern, owner in OWNERS if re.search(pattern, lower)]
    if owners and "owner_types" not in out.updates:
        out.set("owner_types", owners, ", ".join(owners), "Owned by " + ", ".join(owners))
    constraints = []
    for pattern, constraint, meaning in CONSTRAINTS:
        m = re.search(pattern, lower)
        if m:
            constraints.append(constraint)
            out.readings.append(Reading(phrase=m.group(0), interpreted_as=meaning))
    if constraints:
        out.updates["exclude_constraints"] = constraints
    bands = []
    for pattern, band, meaning in BANDS:
        m = re.search(pattern, lower)
        if m:
            bands.append(band)
            out.readings.append(Reading(phrase=m.group(0), interpreted_as=meaning))
    if bands:
        out.updates["bands"] = bands
    for pattern in UNSUPPORTED:
        m = re.search(pattern, lower)
        if m:
            out.not_understood.append(m.group(0))
    for place in OUTSIDE_CITY:
        # "Homestead" is outside the city; "New Homestead" is a city neighborhood.
        in_city = any(place.lower() in n.lower() and n.lower() in lower for n in NEIGHBORHOODS)
        if re.search(rf"\b{re.escape(place.lower())}\b", lower) and not in_city:
            out.not_understood.append(place)
            break


def parse_rules(text: str) -> Parsed:
    out = Parsed()
    _products(text, out)
    _areas(text, out)
    _money(text, out)
    _measures(text, out)
    _phrases(text, out)
    return out
