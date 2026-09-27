"""Plain-language text to a ParseResult (docs/05-ai-search.md, "Flow").

IDs and addresses never reach a parser. Descriptions go to the AI parser when it's available
(an API key is set and the call succeeds), else to the rule-based parser. Either way the
result is validated as SearchFilters and merged with the current filters: fields the parser
didn't set keep their current values.
"""

from dataclasses import replace

from pydantic import ValidationError

from navigator_api.models import FilterChip, ParseResult, SearchFilters
from navigator_api.search.detect import detect
from navigator_api.search.parse_ai import AIParser
from navigator_api.search.parse_rules import Parsed, parse_rules
from navigator_api.search.vocabulary import chip_labels


def merge(parsed: Parsed, current: SearchFilters | None) -> tuple[SearchFilters, list[str]]:
    """Apply the parser's updates to the current filters; invalid fields go to not_understood."""
    base = (current or SearchFilters()).model_dump()
    updates = dict(parsed.updates)
    product = updates.get("product")
    if isinstance(product, dict):
        # A copy: the AI parser caches its answers, which must not change here.
        product = updates["product"] = dict(product)
    if product and not product.get("type") and base.get("product"):
        # "3 homes": keep the building type already chosen, change only the unit count.
        product["type"] = base["product"]["type"]
    rejected: list[str] = []
    for key, value in updates.items():
        try:
            SearchFilters.model_validate({**base, key: value})
            base[key] = value
        except ValidationError:
            rejected.append(key)
    return SearchFilters.model_validate(base), rejected


def result(filters: SearchFilters, **fields) -> ParseResult:
    chips = [FilterChip(key=k, label=v) for k, v in chip_labels(filters)]
    return ParseResult(filters=filters, chips=chips, **fields)


def parse(text: str, current: SearchFilters | None, ai: AIParser | None = None) -> ParseResult:
    detection = detect(text)
    if detection.kind in ("parcel_id", "address"):
        # Handled by the lookup, never parsed (and never sent to a model).
        return result(current or SearchFilters(), detected=detection.kind, parser="rules")
    parsed = ai.parse(text, current) if ai else None
    parser = "ai" if parsed else "rules"
    if parsed is None:
        parsed = parse_rules(text)
    else:
        # What the rules know is never a filter (places outside the city, school quality,
        # rentals …) is always reported, even when the model leaves it out.
        missed = [
            phrase
            for phrase in parse_rules(text).not_understood
            if not any(phrase.lower() in n.lower() for n in parsed.not_understood)
        ]
        if missed:
            parsed = replace(parsed, not_understood=parsed.not_understood + missed)
    filters, rejected = merge(parsed, current)
    return result(
        filters,
        readings=parsed.readings,
        not_understood=parsed.not_understood + rejected,
        parser=parser,
    )
