"""SiteContext: facts about one site, built by the backend, consumed by the engine.

Facts only: measurable from data without assumptions. Shares are fractions of lot area (0-1),
distances are feet, money is USD. `None` means unknown (reason in `provenance`), never zero.
Geometry is GeoJSON in PA State Plane South, US survey feet (EPSG:2272).
"""

from datetime import date
from typing import Literal

from pydantic import Field

from navigator_contracts.common import Contract, Source

Share = float  # fraction of lot area, 0-1

OwnerType = Literal["private", "city", "land_bank", "ura", "other_public"]
FrontageType = Literal["street", "alley", "steps", "none"]


class Parcel(Contract):
    parcel_id: str  # canonical 16-character county id, e.g. 0055A00137000000
    block_lot: str  # dashed city form, e.g. 55-A-137
    municipality: str
    address: str
    geometry: dict  # GeoJSON geometry, EPSG:2272
    lot_area_sqft: float
    frontage_ft: float | None  # not computed yet
    current_use: str
    has_structure: bool
    assessed_land: float | None
    assessed_total: float | None
    owner_type: OwnerType


class ZoningShare(Contract):
    code: str  # district (e.g. RM-M) or overlay (HISTORIC, HEIGHT, GREENWAY, ...)
    kind: Literal["district", "overlay"]
    share: Share = Field(ge=0, le=1)


class FloodShare(Contract):
    code: str  # FEMA zone: A, AE, FLOODWAY, X500 (0.2% annual chance)
    share: Share = Field(ge=0, le=1)


class Physical(Contract):
    steep_slope_share: Share | None  # >= 25% grade; city layer (None outside the city)
    landslide_prone_share: Share | None  # city layer
    undermined_share: Share | None  # city UM-O overlay map
    deep_mined_share: Share | None  # PA DEP digitized deep mines (countywide)
    aml_share: Share | None  # PA DEP abandoned mine lands (countywide)
    flood_zones: list[FloodShare]  # only zones present on the lot
    observed_landslides_within_500ft: int | None


class NearbySite(Contract):
    site_type: str  # land_recycling_act2 | storage_tank_active | storage_tank_inactive
    site_id: str
    name: str | None
    distance_ft: float  # PA DEP records within 1,000 ft


class Infra(Contract):
    combined_sewershed: bool | None  # proxy: pipe capacity is not public
    frontage_type: FrontageType | None  # best access within 60 ft of the lot
    water_provider: str | None


class Access(Contract):
    frequent_transit_distance_ft: float | None  # stop with >= 64 weekday trips


class AdjacentParcel(Contract):
    """Neighbours sharing a lot line; contextual setbacks (925.06.C) need built neighbours."""

    parcel_id: str
    address: str | None
    has_structure: bool | None
    shared_edge_ft: float


class Permit(Contract):
    permit_id: str
    permit_type: str | None
    work_type: str | None
    issue_date: date | None
    status: str | None


class Title(Contract):
    tax_lien_total_usd: float
    condemned: bool
    city_inventory_status: str | None  # city-owned inventory, e.g. "Available for Sale"
    pending_transfer_to: Literal["land_bank", "ura"] | None
    recent_permits: list[Permit] = Field(default_factory=list)  # newest first, up to 20


class Area(Contract):
    neighborhood: str | None  # city neighbourhood (None outside the city)
    mva_market_type: str | None  # URA Market Value Analysis 2021 type
    in_qct: bool  # HUD LIHTC Qualified Census Tract
    in_opportunity_zone: bool


class Sale(Contract):
    parcel_id: str
    sale_date: date
    price: float
    lot_area_sqft: float | None
    building_sqft: float | None
    property_class: str | None
    year_built: float | None
    sale_code: str | None  # county validation code; only arm's-length sales are included
    distance_ft: float


class RentBenchmark(Contract):
    source: str  # "HUD SAFMR"
    geography: str  # ZIP
    bedrooms: int
    monthly_rent: float
    as_of: date | None


class Market(Contract):
    sales: list[Sale]  # arm's-length, within comps_radius_ft, last comps_years
    rent_benchmarks: list[RentBenchmark]
    comps_radius_ft: float
    comps_years: int


class ZbaCase(Contract):
    case_id: str
    decision_date: date | None
    relief_types: list[str]
    district: str | None
    outcome: Literal[
        "approved", "approved_with_conditions", "denied", "withdrawn", "continued", "unknown"
    ]
    days_to_decision: int | None
    distance_ft: float | None = None
    url: str | None = None


class SiteContext(Contract):
    schema_version: str
    parcels: list[Parcel] = Field(min_length=1)  # several for an assemblage
    zoning: list[ZoningShare]  # empty = zoning not covered (outside the city in v1)
    physical: Physical
    environmental: list[NearbySite]
    infrastructure: Infra
    access: Access
    adjacent: list[AdjacentParcel]
    title: Title
    area: Area
    market: Market
    zba_cases_nearby: list[ZbaCase] | None  # None = not available (see provenance)
    provenance: dict[str, Source]  # layer -> source, url, as-of date, note
