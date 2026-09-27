"""AI parser: plain-language text to SearchFilters with Claude (docs/05-ai-search.md).

The model only fills in filters through one forced tool call; it never searches, scores or
ranks. It returns just the fields the user asked about, and `parse.merge` validates them
against SearchFilters and keeps every other field from the current filters. Any failure (no
key, network, timeout, a malformed answer) returns None, and the rule-based parser answers.
"""

import copy
import json
import logging
from collections import OrderedDict

import anthropic

from navigator_api.models import Reading, SearchFilters
from navigator_api.search.parse_rules import Parsed
from navigator_api.search.vocabulary import (
    ALIASES,
    FLAT_MAX_STEEP_PCT,
    NEIGHBORHOODS,
    QUARTER_MILE_FT,
)

log = logging.getLogger(__name__)

TOOL_NAME = "apply_filters"
CACHE_SIZE = 256

NEAR = f"within_ft: {QUARTER_MILE_FT}"
VOCABULARY_ROWS = [
    ("flat, level", f"max_steep_slope_pct = {FLAT_MAX_STEEP_PCT}"),
    ("no steep slope", "max_steep_slope_pct = 0"),
    ("near transit, near a bus stop, walkable to transit, 5-minute walk",
     f"near = [{{feature: transit_stop, {NEAR}}}]"),
    ("near a park / school / grocery store",
     f"near = [{{feature: park / school / grocery, {NEAR}}}]"),
    ("no hearing, without the zoning board, by right", "approval_paths = [by_right]"),
    ("allow variances",
     "approval_paths = [by_right, administrative, special_exception, variance]"),
    ("fast, fastest", "sort = fastest"),
    ("cheap, cheapest", "sort = cheapest (never a price cap)"),
    ("most headroom", "sort = headroom_desc"),
    ("public land, city-owned", "owner_types = [land_bank, ura, city]"),
    ("vacant", "vacant_only = true"),
    ("lots that work together, assemblies", "show_assemblies = true"),
    ("almost works, one rule away, near misses", "show_near_misses = true"),
    ("starter homes", "product.type = single_family"),
    ("houses, single-family", "product.type = single_family"),
    ("townhomes, rowhouses", "product.type = townhome"),
    ("apartment building, walk-up", "product.type = walkup"),
    ("avoid flood zones / undermining / landslides / steep slope / combined sewers",
     "exclude_constraints = [flood_zone / undermined / landslide / steep_slope / "
     "combined_sewer]"),
    ('"3 townhomes", "at least 3 units"', "product.units = 3 (the lower bound of a range)"),
]  # fmt: skip
VOCABULARY = "\n".join(
    ["| Phrase | Set |", "|---|---|"] + [f"| {a} | {b} |" for a, b in VOCABULARY_ROWS]
)

ALIAS_TABLE = "\n".join(f"- {alias}: {', '.join(names)}" for alias, names in ALIASES.items())

SYSTEM_PROMPT = f"""\
You translate a real estate developer's or city planner's request into search filters for a
site-screening tool that covers the City of Pittsburgh.

Rules:
- Call {TOOL_NAME} exactly once.
- In `filters`, include only the fields the user asked about. Leave every other field out: the
  current filters keep their values.
- Use only neighborhood names from the allowed list. Expand nicknames with the alias table.
- Map vague words to the thresholds in the vocabulary table. Never invent other numbers.
- Prices like "under $25k" mean max_land_price (land only), not the total project cost.
- If the user names a place outside Pittsburgh, a feature the schema can't express (school
  quality, crime, views, rental vs. for-sale, condos, ADUs), or anything else you can't map,
  add it to not_understood and do not guess. Don't swap in a nearby filter: "good schools"
  is about quality, so it is not "near a school".
- Every word of the request is either read into a filter or listed in not_understood; never
  drop one silently. not_understood items are the user's own words, exactly as written, with
  nothing added (e.g. "rental", "Mt Lebanon").
- For every filter you set, add a reading: the user's phrase and a short plain-English
  description of the filter, e.g. {{"phrase": "no hearing", "interpreted_as": "By-right only"}}.
- The request may be in any language. Readings are always in English.

Vocabulary:
{VOCABULARY}

Neighborhood aliases:
{ALIAS_TABLE}"""


# Left out of the tool schema to keep it small; SearchFilters checks every range after the
# call. (Strict tool use was tried: the API rejects this schema as too complex.)
UNSUPPORTED_KEYS = {
    "default", "title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "minItems", "maxItems",
}  # fmt: skip


def _tool_schema(schema: dict) -> dict:
    """Pydantic's schema for the tool: nested models inline (no $defs), no defaults or
    limits, and every object closed (`additionalProperties: false`)."""
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            out = {k: resolve(v) for k, v in node.items() if k not in UNSUPPORTED_KEYS}
            if out.get("type") == "object":
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


def filters_schema() -> dict:
    schema = _tool_schema(SearchFilters.model_json_schema())
    # Only real neighborhood names can be picked.
    schema["properties"]["areas"]["items"] = {"type": "string", "enum": NEIGHBORHOODS}
    schema["description"] = "Only the fields the user asked about."
    return schema


def tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": (
            "Translate the user's description of the sites they want into search filters. "
            "Only use values allowed by the schema. Put anything you cannot express as a "
            "filter in not_understood."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filters": filters_schema(),
                "readings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phrase": {"type": "string"},
                            "interpreted_as": {"type": "string"},
                        },
                        "required": ["phrase", "interpreted_as"],
                        "additionalProperties": False,
                    },
                },
                "not_understood": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["filters", "readings", "not_understood"],
            "additionalProperties": False,
        },
    }


def _normalize(tool_input: dict) -> Parsed:
    """The tool call as parser output: aliases expanded, unknown names set aside."""
    out = Parsed()
    updates = dict(tool_input.get("filters") or {})
    # Sometimes the model nests these in the filters; they belong at the top level.
    tool_input = {
        **tool_input,
        "readings": tool_input.get("readings") or updates.pop("readings", None),
        "not_understood": tool_input.get("not_understood") or updates.pop("not_understood", None),
    }
    updates.pop("readings", None)
    updates.pop("not_understood", None)
    if "areas" in updates:
        areas: list[str] = []
        for name in updates["areas"] or []:
            key = str(name).strip()
            matches = ALIASES.get(key.lower()) or (
                [n for n in NEIGHBORHOODS if n.lower() == key.lower()]
            )
            if matches:
                areas.extend(a for a in matches if a not in areas)
            else:
                out.not_understood.append(key)
        updates["areas"] = areas
    out.updates = updates
    out.readings = [
        Reading(phrase=str(r.get("phrase", "")), interpreted_as=str(r.get("interpreted_as", "")))
        for r in tool_input.get("readings") or []
        if isinstance(r, dict) and r.get("interpreted_as")
    ]
    out.not_understood += [str(n) for n in tool_input.get("not_understood") or []]
    return out


class AIParser:
    """Claude behind one forced tool call, with a small per-process cache."""

    def __init__(self, api_key: str, model: str, timeout: float = 10.0) -> None:
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=1)
        self.model = model
        self.tool = tool()
        self._cache: OrderedDict[str, Parsed] = OrderedDict()

    def parse(self, text: str, current: SearchFilters | None) -> Parsed | None:
        current_json = (current or SearchFilters()).model_dump_json()
        key = json.dumps([text.strip().lower(), current_json])
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[self.tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": f"Current filters: {current_json}\nUser request: {text!r}",
                    }
                ],
            )
        except anthropic.APIError as e:
            log.warning("AI search unavailable, using the rule-based parser: %s", e)
            return None
        block = next((b for b in response.content if b.type == "tool_use"), None)
        if block is None or not isinstance(block.input, dict):
            log.warning("AI search returned no tool call (stop: %s)", response.stop_reason)
            return None
        parsed = _normalize(block.input)
        self._cache[key] = parsed
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return parsed
