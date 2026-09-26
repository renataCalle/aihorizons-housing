# 05 · AI search: plain language to filters

## Principle

**The model only fills in `SearchFilters`.** It never searches, scores or ranks, which keeps it within the root CLAUDE.md rule that LLMs only extract data and write narrative. The query engine is deterministic, and the user sees exactly how their sentence was read, as editable chips, before running it.

## Flow

```
omnibox text
  └─ detect.py ── county ID or city block-lot? ──▶ GET /api/lookup   (never sent to the model)
               ── address?   ──▶ GET /api/lookup   (never sent to the model)
               ── otherwise  ──▶ POST /api/search/parse
                                   ├─ parse_ai.py    Claude, tool use, forced tool call
                                   │    └─ on error or no API key ──▶ parse_rules.py
                                   ├─ validate with SearchFilters (Pydantic)
                                   ├─ normalize: aliases, thresholds, clamp ranges
                                   └─ ParseResult { filters, readings, not_understood, detected }
UI: "How we read it" chips ──▶ user edits ──▶ POST /api/search
```

## Detection (`api/src/navigator_api/search/detect.py`, mirrored in `web/src/search/detect.ts` for instant feedback)

- **County parcel ID** (canonical): dashed or compact. Accept partials of 6+ characters for autocomplete.
  `^\d{4}-?[A-Z]-?\d{0,5}(-?\d{0,4}(-?\d{0,2})?)?$` (case-insensitive)
- **City block-lot** (stored alongside): `^\d{1,3}-[A-Z]-\d{1,4}[A-Z]?$`, e.g. `16-E-25`.
- **Address:** a house number followed by words that include a street suffix within the first six words: `^\d+[A-Z]?\s+(\w+\s+){0,4}(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|way|ln|lane|pl|place|ct|court|ter|terrace|pkwy|hwy|way)\b` (case-insensitive). "3 townhomes in Hazelwood" starts with a number but has no suffix, so it's a description. If the text is ambiguous, call `/lookup` first and fall back to AI parsing when it returns nothing.
- **Description:** everything else.

## The tool

Force a single tool call so the output is always structured.

```python
tool = {
    "name": "apply_filters",
    "description": "Translate the user's description of the site they want into search filters. "
                   "Only use values allowed by the schema. Put anything you cannot express as a filter in not_understood.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filters": SEARCH_FILTERS_SCHEMA,   # SearchFilters.model_json_schema(), $refs inlined
            "readings": {"type": "array", "items": {"type": "object",
                "properties": {"phrase": {"type": "string"}, "interpreted_as": {"type": "string"}},
                "required": ["phrase", "interpreted_as"]}},
            "not_understood": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["filters", "readings", "not_understood"],
    },
}

response = client.messages.create(
    model=settings.AI_SEARCH_MODEL,          # claude-haiku-4-5-20251001
    max_tokens=800,
    system=SYSTEM_PROMPT,
    tools=[tool],
    tool_choice={"type": "tool", "name": "apply_filters"},
    messages=[{"role": "user", "content": user_block}],
)
tool_input = next(b.input for b in response.content if b.type == "tool_use")
```

Inline the schema's `$refs` before sending (Pydantic puts nested models under `$defs`). Put the enum of canonical neighborhood names directly on `areas.items` so the model can only pick real names.

`user_block` contains the text and the current filters as JSON, so missing details keep their current values:

```
Current filters: {...}
User request: "3 townhomes in Hazelwood under $25k, no hearing"
```

## System prompt

```
You translate a real estate developer's request into search filters for a site-screening tool
that covers the City of Pittsburgh.

Rules:
- Call apply_filters exactly once.
- Only set fields the user asked about. Keep every other field from the current filters.
- Use only neighborhood names from the allowed list. Expand nicknames using the alias table.
- Map vague words to the thresholds in the vocabulary table. Never invent other numbers.
- "Cheap" or "cheapest" sets sort=cheapest. It does not create a price cap.
- Prices like "under $25k" mean max_land_price (land only), not total project cost.
- If the user names a place outside Pittsburgh, a feature the schema can't express
  (school quality, crime, views, rental vs. for-sale), or anything else you can't map,
  add the phrase to not_understood and do not guess.
- For every filter you set, add a reading: the user's phrase and a short plain-English
  description of the filter, e.g. {"phrase": "no hearing", "interpreted_as": "By-right only"}.
- The request may be in any language. Readings are always in English.

Vocabulary: {VOCABULARY_TABLE}
Neighborhood aliases: {ALIAS_TABLE}
```

## Vocabulary (`vocabulary.py`)

These thresholds are shown in the chips so the user sees the number.

| Phrase | Filter | Chip text |
|---|---|---|
| flat, level | `max_steep_slope_pct = 5` | "Flat lots (under 5% steep slope)" |
| no steep slope | `max_steep_slope_pct = 0` | "No steep slope" |
| near transit, near a bus stop, walkable to transit, 5-minute walk | `near = [{transit_stop, 1320}]` | "Within ¼ mi of transit" |
| near a park / school / grocery | `near = [{…, 1320}]` | "Within ¼ mi of a park" |
| no hearing, without the zoning board, by right | `approval_paths = [by_right]` | "By-right only" |
| allow variances | `approval_paths = [by_right, special_exception, variance]` | "Variances OK" |
| fast | `sort = fastest` | "Fastest first" |
| cheap, cheapest | `sort = cheapest` | "Cheapest first" |
| public land, city-owned | `owner_types = [land_bank, ura, city]` | "Public land" |
| lots that work together | `show_assemblies = true` | "Show assemblies" |
| almost works, one rule away | `show_near_misses = true` | "Show near misses" |

Neighborhood aliases: "Lawrenceville" → Lower, Central, Upper Lawrenceville; "Homewood" → Homewood North, South, West; "the Hill", "Hill District" → Crawford-Roberts, Middle Hill, Upper Hill, Terrace Village, Bedford Dwellings; "Squirrel Hill" → Squirrel Hill North, South. The canonical list is the City of Pittsburgh's 90 neighborhoods (the mock uses a subset).

## Validation and normalization

After the model returns:
1. Validate with `SearchFilters.model_validate`. On failure, drop the invalid fields and add them to `not_understood`.
2. Expand aliases; drop unknown neighborhood names into `not_understood`.
3. Clamp numbers to schema ranges.
4. Merge with `current_filters`: fields the model didn't set keep their current values.

## Fallback parser (`parse_rules.py`)

It must work with no API key, so the demo never breaks. Keyword and regex rules for: product type and unit count, neighborhood names and aliases (fuzzy match for typos, e.g. `rapidfuzz`), `under $Nk` for land price, the vocabulary table, and sort words. When it's used, `ParseResult` gets a reading `{"phrase": "", "interpreted_as": "Basic search (AI unavailable)"}`, and the UI shows a small "basic search" tag.

## Evaluation

`fixtures/eval/nl_search_eval.jsonl` has 40 prompts with expected filters. Each `expected` object is partial: only the listed fields are checked. Some entries also check `expected_not_understood` (substring match) or `expected_detected`.

`api/tests/test_ai_search_eval.py`:
- Runs every prompt through `/search/parse` (the AI parser if a key is set, else the fallback).
- Scores per field: exact match for scalars, set equality for lists.
- Prints a table and an overall accuracy. Target: at least 90% of fields with the AI parser.
- Marked `@pytest.mark.eval` so it doesn't run on every commit (it calls the API).

Add real prompts from demo rehearsals to this file as you go. It's also a good slide for the judges.

## Performance and cost

- Debounce the omnibox (400 ms) and only call parse on Enter or after a pause.
- Cache results by `(text, current_filters)` for the session.
- A Haiku-class model answers in about a second at a fraction of a cent per query.

## When the teammate's data lands

Revisit: the allowed filter fields (only filter on fields SiteContext and the engine summaries actually provide), the vocabulary thresholds, and the neighborhood list. Update the search models in `navigator_contracts`, rerun the eval.
