from fastapi import APIRouter

from navigator_api.models import MapFeatureCollection, ParcelFeatureCollection
from navigator_api.routes.deps import Source

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/parcels")
def map_parcels(source: Source) -> ParcelFeatureCollection:
    """Every parcel's geometry (EPSG:4326) with its band and score. Ranks arrive with search."""
    return source.parcels_geojson()


@router.get("/features")
def map_features(source: Source) -> MapFeatureCollection:
    """Transit stops, parks, schools and neighborhood outlines (EPSG:4326)."""
    return source.map_features()
