"""Download Zoning Board of Adjustment agendas and decisions from the city's meeting pages.

    uv run python -m navigator_pipeline.zba_download                  # 2025 and 2026
    uv run python -m navigator_pipeline.zba_download --years 2025 --dry-run

Meeting pages are listed in https://www.pittsburghpa.gov/sitemap.xml under
City-Planning-Meetings/ZBA-Agendas/. From each meeting page and its Agenda / Decisions child
pages the script keeps two kinds of PDF:

    agendas/    the hearing agenda: every case, its address, district and the approvals asked
    decisions/  the board's written decision per case (posted weeks after the hearing)

Applicants' forms and presentations are skipped: they are not needed and carry personal
details. Files land in data/manual/zba/ (gitignored: decisions name applicants). Every request
uses the pipeline's client (`market-data-client/1.0`), is checked against robots.txt, and is
spaced DELAY_S apart. Re-running skips files already on disk.
"""

import argparse
import hashlib
import json
import re
import time
import urllib.robotparser
from datetime import UTC, date, datetime
from urllib.parse import unquote, urljoin, urlparse

from navigator_pipeline.http import USER_AGENT, client
from navigator_pipeline.settings import MANUAL

SITE = "https://www.pittsburghpa.gov"
MEETINGS = "/Business-Development/City-Planning/City-Planning-Meetings/ZBA-Agendas/"
OUT = MANUAL / "zba"
DELAY_S = 2.0
SKIP_CHILDREN = ("Applications", "Meeting-presentations")  # applicants' own materials
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], 1)}  # fmt: skip

HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.S | re.I)
PDF_LINK = re.compile(r'href="([^"]+\.pdf)"', re.I)


class Polite:
    """One client, robots.txt respected, requests spaced DELAY_S apart."""

    def __init__(self, delay: float) -> None:
        self.http = client(timeout=60, read=120)
        self.delay, self.last = delay, 0.0
        self.robots = urllib.robotparser.RobotFileParser()
        self.robots.parse(self._get(f"{SITE}/robots.txt").text.splitlines())

    def _get(self, url: str):
        wait = self.last + self.delay - time.time()
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            self.last = time.time()
            r = self.http.get(url, follow_redirects=True)
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(10 * (attempt + 1))  # back off when the server is busy
        r.raise_for_status()
        return r

    def get(self, url: str):
        if not self.robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallows {url}")
        return self._get(url)


def meeting_date(slug: str) -> date | None:
    """'ZBA-April-2-2026' or 'Zoning-board-of-Adjustment-June-5-2025' -> date."""
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|"
                  r"November|December)-(\d{1,2})-(\d{4})", slug)  # fmt: skip
    return date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))) if m else None


def meeting_pages(web: Polite, years: set[int]) -> dict[str, list[str]]:
    """{meeting slug: [child paths]} for meetings in `years`, from the sitemap."""
    xml = web.get(f"{SITE}/sitemap.xml").text
    out: dict[str, list[str]] = {}
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        path = urlparse(url).path
        if MEETINGS not in path:
            continue
        slug, *rest = path.split(MEETINGS, 1)[1].strip("/").split("/")
        d = meeting_date(slug)
        if d and d.year in years:
            out.setdefault(slug, [])
            if rest:
                out[slug].append("/".join(rest))
    return out


def pdf_links(html: str, page_url: str) -> list[tuple[str, str]]:
    """(absolute pdf url, nearest heading above it), in page order."""
    heads = [
        (m.start(), re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip()) for m in HEADING.finditer(html)
    ]
    out = []
    for m in PDF_LINK.finditer(html):
        above = [h for pos, h in heads if pos < m.start()]
        out.append((urljoin(page_url, m.group(1)), above[-1] if above else ""))
    return out


def kind_of(url: str, heading: str, page_path: str) -> str | None:
    """'agenda', 'decision', or None (applications, presentations, anything else)."""
    name = unquote(urlparse(url).path.rsplit("/", 1)[-1]).lower()
    if "agenda" in name:
        return "agenda"
    if (
        "decision" in name
        or re.search(r"\d+-of-20\d\d", name)
        or heading.lower() in ("minutes", "decisions")
        or "/Decisions" in page_path
    ):
        return "decision"
    return None


def collect(web: Polite, slug: str, children: list[str]) -> dict[str, str]:
    """{pdf url: kind} from the meeting page and its agenda / decision child pages."""
    pages = [""] + sorted(
        c
        for c in children
        if not c.split("/")[0].endswith(SKIP_CHILDREN) and "/Applications" not in c
    )
    found: dict[str, str] = {}
    for child in pages:
        path = MEETINGS + slug + (f"/{child}" if child else "")
        url = SITE + path
        try:
            html = web.get(url).text
        except PermissionError as e:
            print(f"    skipped: {e}")
            continue
        for pdf, heading in pdf_links(html, url):
            kind = kind_of(pdf, heading, path)
            if kind and pdf not in found:
                found[pdf] = kind
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    ap.add_argument("--delay", type=float, default=DELAY_S, help="seconds between requests")
    ap.add_argument("--dry-run", action="store_true", help="list files, download nothing")
    args = ap.parse_args()

    web = Polite(args.delay)
    meetings = meeting_pages(web, set(args.years))
    print(f"{len(meetings)} meetings in {sorted(args.years)}")
    (OUT / "agendas").mkdir(parents=True, exist_ok=True)
    (OUT / "decisions").mkdir(parents=True, exist_ok=True)
    manifest = OUT / "_manifest.jsonl"
    totals = {"agenda": 0, "decision": 0, "downloaded": 0}
    no_decisions = []
    for slug in sorted(meetings, key=meeting_date):
        d = meeting_date(slug)
        files = collect(web, slug, meetings[slug])
        n = {k: sum(v == k for v in files.values()) for k in ("agenda", "decision")}
        print(f"  {d} {slug}: {n['agenda']} agenda, {n['decision']} decisions")
        if not n["decision"]:
            no_decisions.append(str(d))
        for url, kind in files.items():
            totals[kind] += 1
            name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
            dest = OUT / f"{kind}s" / f"{d}__{name}"
            if args.dry_run or dest.exists():
                continue
            body = web.get(url).content
            dest.write_bytes(body)
            totals["downloaded"] += 1
            entry = {
                "meeting": slug,
                "meeting_date": str(d),
                "kind": kind,
                "url": url,
                "file": dest.name,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            with manifest.open("a") as f:
                f.write(json.dumps(entry) + "\n")
    print(
        f"{totals['agenda']} agendas, {totals['decision']} decisions "
        f"({totals['downloaded']} downloaded now) -> {OUT}"
    )
    if no_decisions:
        print(f"no decisions posted yet for: {', '.join(no_decisions)}")


if __name__ == "__main__":
    main()
