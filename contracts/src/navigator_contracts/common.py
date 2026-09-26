"""Types shared by SiteContext and SiteAnalysis."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "0.1.0"

Confidence = Literal["high", "medium", "low"]
Interval = tuple[float, float]  # (low, high); (0, 0) means free / none


class Contract(BaseModel):
    """Base for every contract model: unknown fields are an error, never silently dropped."""

    model_config = ConfigDict(extra="forbid")


class Range(Contract):
    """Every estimate ships as a range: 10th, 50th and 90th percentile of the simulation."""

    p10: float
    p50: float
    p90: float


class Source(Contract):
    """Where a layer came from. A null fact carries its reason in `note`."""

    name: str
    url: str | None = None
    as_of: date | None = None
    note: str | None = None
    # "live": fetched from the source's API for this report; "snapshot": from the refreshed
    # store (as_of is the store's source date). A failed live lookup falls back to snapshot.
    retrieved: Literal["live", "snapshot"] | None = None
    retrieved_at: datetime | None = None
