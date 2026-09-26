"""The one HTTP client for every outbound request the pipeline makes.

The identity is exactly `market-data-client/1.0`. Never add contact details, and never
disguise the client as a browser to get past a block.
"""

import json
import time
from pathlib import Path

import httpx

USER_AGENT = "market-data-client/1.0"


def client(timeout: float = 60.0, read: float = 180.0) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(timeout, read=read),
        follow_redirects=True,
    )


def get_json(http: httpx.Client, url: str, params: dict | None = None, tries: int = 4) -> object:
    for attempt in range(tries):
        try:
            r = http.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def post_json(
    http: httpx.Client,
    url: str,
    data: dict | None = None,
    json_body: dict | None = None,
    tries: int = 4,
) -> dict:
    for attempt in range(tries):
        try:
            r = http.post(url, data=data, json=json_body)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def stream(http: httpx.Client, url: str, dest: Path) -> None:
    """Download to `dest` atomically (via a .part file)."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    with http.stream("GET", url) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
