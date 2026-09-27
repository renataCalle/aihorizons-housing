"""Build a ParcelSummary from a SiteContext and the engine's SiteAnalysis.

Facts are copied from the context and judgments from the analysis, unchanged: the API picks
fields, it never scores or ranks.
"""

from navigator_api.models import LeadOption, ParcelSummary, ProgramFit
from navigator_contracts import SiteAnalysis, SiteContext


def summarize(
    context: SiteContext,
    analysis: SiteAnalysis | None,
    *,
    display_name: str,
    centroid: tuple[float, float],
    candidate: bool,
    illustrative: bool,
    assembly_id: str | None = None,
) -> ParcelSummary:
    parcel = context.parcels[0]
    physical = context.physical
    summary = ParcelSummary(
        parcel_id=parcel.parcel_id,
        block_lot=parcel.block_lot or None,
        display_name=display_name,
        address=parcel.address or None,
        municipality=parcel.municipality,
        neighborhood=context.area.neighborhood,
        zoning=[z.code for z in context.zoning if z.kind == "district"],
        lot_area_sqft=parcel.lot_area_sqft,
        current_use=parcel.current_use,
        owner_type=parcel.owner_type,
        assessed_land=parcel.assessed_land,
        centroid=centroid,
        candidate=candidate,
        illustrative=illustrative,
        assembly_id=assembly_id,
        has_structure=parcel.has_structure,
        steep_slope_share=physical.steep_slope_share,
        landslide_share=physical.landslide_prone_share,
        undermined_share=physical.undermined_share,
        flood_share=sum(z.share for z in physical.flood_zones if z.code != "X500"),
        combined_sewershed=context.infrastructure.combined_sewershed,
        transit_distance_ft=context.access.frequent_transit_distance_ft,
        tax_lien_usd=context.title.tax_lien_total_usd,
    )
    if analysis is None:
        return summary

    top = analysis.flags[0] if analysis.flags else None  # the engine orders flags worst first
    metrics = analysis.metrics
    lead = next((o for o in analysis.options if metrics and o.label == metrics.option), None)
    return summary.model_copy(
        update={
            "score": analysis.verdict.score,
            "band": analysis.verdict.band,
            "top_flag": top.title if top else None,
            "top_flag_severity": top.severity if top else None,
            "max_land_price": metrics.max_land_price if metrics else None,
            "lead_option": LeadOption(
                label=lead.label,
                product_type=lead.product_type,
                units=lead.units,
                relief=lead.relief,
                margin=lead.margin,
            )
            if lead
            else None,
            "months_to_permit": metrics.months_to_permit if metrics else None,
            "site_cost_premium": metrics.site_cost_premium if metrics else None,
            "programs": [
                ProgramFit(
                    product_type=p.product_type,
                    units=p.units,
                    outcome=p.outcome,
                    relief_types=sorted({c.relief_type for c in p.checks if c.relief_type}),
                )
                for p in (analysis.rule_checks.programs if analysis.rule_checks else [])
            ],
        }
    )
