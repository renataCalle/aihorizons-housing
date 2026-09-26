"""Every data source the pipeline pulls, keyed by a short name.

Wave numbers follow the spec's ingestion order. `feeds` says which engine module or
SiteContext field the source serves.
"""

import os
from dataclasses import dataclass, field

# Overridable so tests (and outage drills) can point at another host.
WPRDC = os.environ.get("NAVIGATOR_WPRDC_URL", "https://data.wprdc.org")
DEP_EXTERNAL = "https://gis.dep.pa.gov/depgisprd/rest/services/emappa/eMapPA_External/MapServer"
DEP_EXTRACT = (
    "https://gis.dep.pa.gov/depgisprd/rest/services/emappa/eMapPA_External_Extraction/MapServer"
)
FEMA_NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
HUD = "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"

# Allegheny County bounding box (lon/lat), padded; layers are clipped to the county in build.
ALLEGHENY_BBOX = (-80.37, 40.19, -79.68, 40.68)


@dataclass(frozen=True)
class Source:
    key: str
    wave: int
    feeds: str
    kind: str  # wprdc | arcgis | legistar | wprdc_latest
    dataset: str | None = None  # WPRDC dataset slug
    resource_id: str | None = None  # WPRDC resource, when a dataset has several
    fmt: str | None = None  # preferred WPRDC resource format
    url: str | None = None  # ArcGIS layer URL
    where: str = "1=1"
    notes: str = ""
    extra: dict = field(default_factory=dict)


SOURCES: list[Source] = [
    # Wave 1: parcel base
    Source(
        "parcels",
        1,
        "Parcel geometry, block-lot",
        "wprdc",
        "allegheny-county-parcel-boundaries1",
        "be216088-d51c-41ce-aa4a-2c315c2c7725",
    ),
    Source(
        "assessments",
        1,
        "Lot area, use, values, owner class, municipality",
        "wprdc",
        "property-assessments",
        "9a1c60bd-f9f7-4aba-aeb7-af8c3aaa44e5",
    ),
    Source(
        "assessments_dictionary",
        1,
        "Assessment field definitions",
        "wprdc",
        "property-assessments",
        "c665470c-ee72-4f0d-b772-4f09c2145f2a",
    ),
    Source(
        "address_points",
        1,
        "Search bar geocoding",
        "wprdc",
        "allegheny-county-addressing-address-points2",
        fmt="ZIP",
    ),
    Source(
        "municipalities",
        1,
        "Municipality of each parcel; city vs. suburb",
        "wprdc",
        "allegheny-county-municipal-boundaries",
        fmt="GeoJSON",
    ),
    Source(
        "neighborhoods",
        1,
        "Neighborhood for partial pooling and planner filters",
        "wprdc",
        "neighborhoods2",
        fmt="GeoJSON",
    ),
    # Wave 2: rules engine inputs and common deal-killers
    Source("zoning", 2, "Base zoning districts", "wprdc", "zoning", fmt="GeoJSON"),
    Source(
        "historic_districts",
        2,
        "Historic overlay",
        "wprdc",
        "city-designated-historic-districts",
        fmt="GeoJSON",
    ),
    Source(
        "historic_sites",
        2,
        "Individual historic sites",
        "wprdc",
        "city-designated-individual-historic-sites",
        fmt="GeoJSON",
    ),
    Source("greenways", 2, "Greenway overlay", "wprdc", "greenways", fmt="GeoJSON"),
    Source("parks", 2, "Parks", "wprdc", "parks1", fmt="GeoJSON"),
    Source("height_overlay", 2, "Height overlay", "wprdc", "pghzoningheightoverlay", fmt="GeoJSON"),
    Source(
        "parking_reduction_overlay",
        2,
        "Parking reduction overlay",
        "wprdc",
        "parking-reduction-zoning-overlay",
        fmt="GeoJSON",
    ),
    Source(
        "riverfront_overlay",
        2,
        "Riverfront overlay",
        "wprdc",
        "riverfront-zoning-overlay",
        fmt="GeoJSON",
    ),
    Source("uptown_ipod", 2, "Uptown IPOD overlay", "wprdc", "uptown-ipod-zoning", fmt="GeoJSON"),
    Source(
        "steep_slope",
        2,
        "Share of lot on >=25% slope",
        "wprdc",
        "25-or-greater-slope",
        fmt="GeoJSON",
    ),
    Source(
        "landslide_prone",
        2,
        "Landslide-prone share",
        "wprdc",
        "landslide-prone-areas",
        fmt="GeoJSON",
    ),
    Source("undermined", 2, "Undermined share", "wprdc", "undermined-areas", fmt="GeoJSON"),
    Source(
        "landslides_observed",
        2,
        "Observed landslides near the site",
        "wprdc",
        "landslides",
        fmt="GeoJSON",
    ),
    # Wave 3: rest of the report
    Source(
        "fema_flood_zones",
        3,
        "Flood flag (current NFHL, not the 2014 extract)",
        "arcgis",
        url=f"{FEMA_NFHL}/28",
        where="DFIRM_ID='42003C'",
        extra={
            "bbox": False,
            "chunk": 100,
            "params": {"maxAllowableOffset": 0.00001, "geometryPrecision": 7},
        },
        notes="Filtered by Allegheny's DFIRM id (bbox queries return 500). Geometry "
        "simplified server-side to ~1 m; raw NFHL polygons are too dense to page.",
    ),
    Source(
        "dep_land_recycling",
        3,
        "Act 2 / land recycling cleanup sites",
        "arcgis",
        url=DEP_EXTERNAL,
        extra={"sublayers": [27, 28, 29, 30, 31, 32, 33]},
        notes="Group layer 26: one sublayer per contaminated medium; a site can repeat.",
    ),
    Source(
        "dep_storage_tanks_active", 3, "Active storage tanks", "arcgis", url=f"{DEP_EXTERNAL}/171"
    ),
    Source(
        "dep_storage_tanks_inactive",
        3,
        "Inactive storage tanks",
        "arcgis",
        url=f"{DEP_EXTERNAL}/172",
    ),
    Source(
        "dep_aml_sites", 3, "Abandoned mine land inventory sites", "arcgis", url=f"{DEP_EXTRACT}/50"
    ),
    Source(
        "dep_aml_polygons", 3, "Abandoned mine land polygons", "arcgis", url=f"{DEP_EXTRACT}/51"
    ),
    Source(
        "dep_digitized_mined_area",
        3,
        "Digitized deep-mined areas",
        "arcgis",
        url=f"{DEP_EXTRACT}/47",
        extra={"chunk": 25, "params": {"maxAllowableOffset": 0.00001, "geometryPrecision": 7}},
        notes="Large polygons: small chunks, simplified server-side to ~1 m.",
    ),
    Source(
        "combined_sewershed",
        3,
        "Combined sewershed proxy",
        "wprdc",
        "combined-sewershed",
        fmt="GeoJSON",
    ),
    Source(
        "water_providers_by_parcel",
        3,
        "Water provider per parcel",
        "wprdc",
        "pa-public-water-systems",
        "e85ee57f-5231-41c3-b955-62404157bd14",
    ),
    Source(
        "street_centerlines",
        3,
        "Frontage type (walkway, stairway, alley)",
        "wprdc",
        "allegheny-county-addressing-street-centerlines",
        fmt="ZIP",
    ),
    Source(
        "city_street_centerlines",
        3,
        "City street classes incl. steps",
        "wprdc",
        "pittsburgh-street-centerlines",
        fmt="GeoJSON",
    ),
    Source(
        "city_steps",
        3,
        "Public stairways (steps-only frontage)",
        "wprdc",
        "city-steps",
        fmt="GeoJSON",
    ),
    Source(
        "sales",
        3,
        "Land comps and exit values",
        "wprdc",
        "real-estate-sales",
        "5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1",
    ),
    Source(
        "hud_safmr",
        3,
        "Rent benchmarks: Small Area FMR by ZIP and bedroom",
        "arcgis",
        url=f"{HUD}/SAFMR_Year/FeatureServer/2",
    ),
    Source(
        "hud_fmr_metro",
        3,
        "Rent benchmark fallback: metro FMR by bedroom",
        "arcgis",
        url=f"{HUD}/Fair_Market_Rents/FeatureServer/0",
    ),
    Source(
        "market_value_analysis",
        3,
        "URA Market Value Analysis 2021 (market typology)",
        "wprdc",
        "market-value-analysis-2021",
        fmt="GeoJSON",
    ),
    # Wave 4: entitlement, timelines, access
    Source(
        "pli_permits",
        4,
        "Timeline calibration, by-right validation",
        "wprdc",
        "pli-permits",
        "f4d1177a-f597-4c32-8cbf-7885f56253f6",
    ),
    Source(
        "condemned",
        4,
        "Condemned / dead-end properties (demolition cost)",
        "wprdc",
        "condemned-properties",
        "0a963f26-eb4b-4325-bbbc-3ddf6a871410",
    ),
    Source(
        "council_zoning_matters",
        4,
        "Council conditional uses and rezonings",
        "legistar",
        notes="ZBA decisions are on pittsburghpa.gov, which blocks this client (403).",
    ),
    Source(
        "transit_stops",
        4,
        "Distance to transit",
        "wprdc",
        "prt-of-allegheny-county-transit-stops",
        fmt="GeoJSON",
    ),
    Source(
        "gtfs", 4, "Stop frequency -> frequent transit", "wprdc_latest", "gtfs-archive", fmt="ZIP"
    ),
    # Wave 5: planner and financing overlays
    Source(
        "city_owned",
        5,
        "Publicly owned parcels (planner filter)",
        "wprdc",
        "city-owned-properties",
        "e1dcee82-9179-4306-8167-5891915b62a7",
    ),
    Source(
        "tax_liens",
        5,
        "Tax liens: acquisition leads, title risk",
        "wprdc",
        "allegheny-county-tax-liens-filed-and-satisfied",
        "d1e80180-5b2e-4dab-8ec3-be621628649e",
    ),
    Source(
        "hud_qct",
        5,
        "LIHTC Qualified Census Tracts 2026",
        "arcgis",
        url=f"{HUD}/QUALIFIED_CENSUS_TRACTS_2026/FeatureServer/0",
    ),
    Source(
        "hud_dda",
        5,
        "LIHTC Difficult Development Areas 2026",
        "arcgis",
        url=f"{HUD}/Difficult_Development_Areas_2026/FeatureServer/0",
    ),
    Source(
        "opportunity_zones",
        5,
        "Opportunity Zones",
        "arcgis",
        url=f"{HUD}/Opportunity_Zones/FeatureServer/13",
    ),
]

BY_KEY = {s.key: s for s in SOURCES}

# How often the scheduled refresh checks each source for new data (days). Records that change
# daily at the source are also looked up live per parcel (navigator_pipeline.live).
REFRESH_DAYS_DEFAULT = 30
REFRESH_DAYS = {
    "sales": 1,
    "pli_permits": 1,
    "condemned": 1,
    "city_owned": 1,
    "assessments": 7,
    "tax_liens": 7,
    "council_zoning_matters": 7,
    "assessments_dictionary": 365,
    "hud_safmr": 365,
    "hud_fmr_metro": 365,
    "hud_qct": 365,
    "hud_dda": 365,
    "opportunity_zones": 365,
    "market_value_analysis": 365,
}


def refresh_days(key: str) -> int:
    return REFRESH_DAYS.get(key, REFRESH_DAYS_DEFAULT)
