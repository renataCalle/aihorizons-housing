"""Render a SiteAnalysis (from engine_v0) as the one-page report (spec: UI > Report blocks).

    uv run python -m sandbox.report 0055A00137000000     # after sandbox.navigator ran it
    (sandbox.navigator also writes the HTML next to the JSON)

Every value on the page comes from the navigator's JSON: site_context (facts) and
site_analysis (judgments). The renderer only formats; it reads no data layers or engine code,
so the web app can reproduce this page from the same JSON.
"""

import html
import json
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"
OUT = DATA / "output"

SEVERITY = {  # flag severity -> (chip label, css class)
    "high": ("Deal risk", "risk"),
    "medium": ("Caution", "caution"),
    "low": ("Minor", "minor"),
    "unknown": ("Unknown", "unknown"),
}
BAND = {
    "fast_track": "Fast track",
    "feasible_with_conditions": "Feasible with conditions",
    "high_risk": "High risk",
    "not_scored": "Not scored",
}
RELIEF = {
    "administrator_exception": "Administrator exception",
    "special_exception": "Special exception",
    "variance": "Variance",
    "use_variance": "Use variance",
    "conditional_use": "Conditional use",
    "rezoning": "Rezoning",
    "subdivision": "Subdivision",
}
PRODUCT = {
    "single_family": "Single-family home",
    "duplex": "Duplex",
    "triplex": "Triplex",
    "townhome": "attached townhomes",
    "walkup": "unit walk-up",
}

e = html.escape


def money(x: float, k: bool = True) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if k and x >= 1000:
        return f"{sign}${x / 1000:,.0f}k"
    return f"{sign}${x:,.0f}"


def rng(lo: float, hi: float, fmt=money) -> str:
    return f"{fmt(lo)}–{fmt(hi)}" if fmt(lo) != fmt(hi) else fmt(lo)


def product_title(o: dict) -> str:
    if o["product_type"] == "walkup":
        return f"{o['units']}-unit walk-up"
    if o["product_type"] == "townhome":
        return f"{o['units']} attached townhomes"
    return PRODUCT[o["product_type"]]


def relief_names(o: dict) -> list[str]:
    return [RELIEF.get(r.split(" (")[0], r) for r in o["relief"]]


# ---------------------------------------------------------------- page


def render(payload: dict) -> str:
    ctx, a = payload["site_context"], payload["site_analysis"]
    p = ctx["parcels"][0]
    v = a["verdict"]
    m = a["metrics"]
    districts = [z for z in ctx["zoning"] if z["kind"] == "district"]
    zoning = " / ".join(z["code"] for z in districts) or "not covered"
    dims = a["rules"].get("lot_dimensions_ft")
    ver = a["versions"]
    mk = ctx["market"]
    A = {x["key"]: x for x in a["assumptions"]}
    head_label = m["option"] if m else None
    flags = a["flags"]
    title = f"{p['address'].title()} · {p['block_lot']}"

    # ---- verdict card
    pill_cls = (
        "risk"
        if v["band"] == "high_risk" or v.get("land_risk")
        else "caution"
        if v["band"] == "feasible_with_conditions"
        else "ok"
    )
    pill = v.get("land_risk") or BAND[v["band"]]
    score_html = ""
    if v["score"] is not None:
        r = v["score_range"]
        score_html = (
            f'<div class="score"><span class="eyebrow">Development Ease Score</span>'
            f'<div class="big">{v["score"]}<span>/100</span></div>'
            f'<span class="muted small">Likely range {r["p10"]:.0f}–{r["p90"]:.0f}'
            f"</span></div>"
        )
    bars = "".join(
        f'<div class="bar"><div class="bar-top"><span>{e(c["label"])}</span>'
        f'<span class="num">{c["points"]} / {c["max_points"]}</span></div>'
        f'<div class="track"><div class="fill" style="width:{100 * c["points"] / c["max_points"]:.0f}%">'
        f'</div></div><span class="muted small">{e(c["note"])}</span></div>'
        for c in v.get("components") or []
    )
    summary = (a.get("narrative") or {}).get("summary") or v["headline"]
    verdict = f"""
    <section class="card verdict">
      <div class="verdict-top">
        <div><span class="pill {pill_cls}">{e(pill)}</span>
          <h1>{e(summary)}</h1></div>
        {score_html}
      </div>
      {f'<div class="where"><h3>Where the score comes from</h3><div class="bars">{bars}</div></div>' if bars else ""}
    </section>"""

    # ---- three key-number cards
    cards = ""
    if m:
        head = next(o for o in a["options"] if o["label"] == head_label)
        rel = relief_names(head)
        mo = head["months"]
        prem = m["site_cost_premium"]
        lo, hi = prem["low"], prem["high"]
        causes = ", ".join(prem["drivers"][:3]) or "none priced"
        ml = m["max_land_price"]
        land = m["land_basis"]["value"]
        is_asking = m["land_basis"]["source"] == "user input"
        over = ""
        if m.get("land_over_max"):
            lo_over, hi_over = m["land_over_max"]["low"], m["land_over_max"]["high"]
            over = (
                f'<span class="down">↓ {"Asking" if is_asking else "Assessed land"} '
                f"{money(land)} is {rng(lo_over, hi_over)} over</span>"
            )
        n_sales = len(ctx["market"]["sales"])
        window = (
            f"{n_sales} sales within {mk['comps_radius_ft'] / 5280:.1f} mi · "
            f"{mk['comps_years'] * 12} mo"
            if mk.get("comps_radius_ft")
            else f"{n_sales} nearby sales"
        )
        cards = f"""
    <div class="cards3">
      <section class="card mini"><span class="eyebrow">Approval path</span>
        <div class="mid">{"By-right" if not rel else e(" + ".join(rel))}</div>
        <span>{e(product_title(head))} · {mo["p10"]:.0f}–{mo["p90"]:.0f} months to permit-ready</span>
        <span class="mono">{e(ver["ruleset"])}</span></section>
      <section class="card mini"><span class="eyebrow">Site cost premium</span>
        <div class="mid">+{rng(lo, hi)}</div>
        <span>{e(causes)}</span></section>
      <section class="card mini"><span class="eyebrow">Max land price at {A["target_margin"]["value"]:.0%} margin</span>
        <div class="mid">{rng(ml["p10"], ml["p90"])}</div>
        {over}
        <span class="mono">{e(window)}</span></section>
    </div>"""

    # ---- what could kill this deal
    rows = []
    for f in flags:
        chip, cls = SEVERITY[f["severity"]]
        ev = f["evidence"][0] if f["evidence"] else {}
        src = ev.get("source") or ""
        if ev.get("as_of"):
            src += f" · {ev['as_of'][:4]}"
        sec = next((x["code_section"] for x in f["evidence"] if x.get("code_section")), None)
        cost = (
            f'<div class="amt">+{rng(*f["cost_usd"])}</div>'
            if f["cost_usd"]
            else '<div class="amt">Could end the deal</div>'
            if f["severity"] == "high"
            else ""
        )
        months = (
            f'<div class="muted small">+{f["months"][0]:g}–{f["months"][1]:g} months</div>'
            if f["months"]
            else ""
        )
        link = (
            f'<a href="{e(ev["url"])}" target="_blank" rel="noopener">See source →</a>'
            if ev.get("url")
            else ""
        )
        rows.append(f"""
        <div class="flag">
          <span class="chip {cls}">{chip}</span>
          <div class="flag-body"><div class="flag-title">{e(f["title"])}</div>
            <p>{e(f["resolution"])}</p>
            <div class="tags"><span class="tag">{e(src[:70])}</span>
              {f'<span class="tag">§ {e(sec)}</span>' if sec else ""}
              <span class="muted small">Confidence: {e(f["confidence"])}</span></div></div>
          <div class="flag-side">{cost}{months}{link}</div>
        </div>""")
    cleared = " · ".join(e(c) for c in a["cleared"]) or "none"
    kill = f"""
    <section class="block">
      <div class="block-head"><h2>What could kill this deal</h2>
        <span class="muted small">{len(flags)} findings, worst first</span></div>
      <div class="card list">{"".join(rows) or '<div class="flag"><p>No findings.</p></div>'}
        <div class="cleared"><b>✓ Cleared</b> {cleared}</div></div>
    </section>"""

    # ---- what you can build
    opts = []
    for o in a["options"]:
        lead = o["label"] == head_label
        rel = relief_names(o)
        basis = (
            "; ".join(o["entitlement_basis"])
            if o["entitlement_basis"]
            else f"By right under {ver['ruleset']}"
        )
        opts.append(f"""
        <section class="card option {"lead" if lead else ""}">
          <div class="opt-top"><span class="eyebrow">{"Best by-right" if o["label"] == "by_right" else "Best with approvals"}</span>
            {'<span class="badge">Leading option</span>' if lead else ""}</div>
          <div class="opt-name">{e(product_title(o))}</div>
          <span class="muted">{o["units"]} {"home" if o["units"] == 1 else "homes"} · about {o["unit_sqft"]:,} sq ft each</span>
          <div class="kv3">
            <div><span class="muted small">Margin</span><b>{o["margin"]["p10"]:.0%} to {o["margin"]["p90"]:.0%}</b></div>
            <div><span class="muted small">Permit-ready</span><b>{o["months"]["p10"]:.0f}–{o["months"]["p90"]:.0f} mo</b></div>
            <div><span class="muted small">Approvals</span><b>{e(", ".join(rel)) if rel else "None"}</b></div>
          </div>
          <span class="mono">{e(basis[:140])}</span>
        </section>""")
    land = m["land_basis"] if m else {"value": p.get("assessed_land") or 0, "source": ""}
    build = f"""
    <section class="block">
      <div class="block-head"><h2>What you can build</h2>
        <span class="muted small">{e((a["rules"]["scenario"] or "no") + " setbacks")}</span></div>
      <div class="cards2">{"".join(opts) or '<section class="card option"><p>Zoning is not covered for this municipality, so no program is proposed.</p></section>'}</div>
      <p class="muted small">Margins assume {money(land["value"], k=False)} for land ({e(land["source"])}), default costs and {len(ctx["market"]["sales"])} nearby sales.</p>
    </section>"""

    # ---- what to check next
    free = sum(1 for s in a["next_steps"] if s["cost_usd"][1] == 0)
    steps = "".join(
        f"""
        <tr><td class="stepn">{s["order"]}</td>
          <td><b>{e(s["action"])}</b><br><span class="muted small">{e(s["why"])}</span></td>
          <td>{e(s["who"])}</td>
          <td class="num"><b>{"Free" if s["cost_usd"][1] == 0 else rng(*s["cost_usd"])}</b></td></tr>"""
        for s in a["next_steps"]
    )
    nxt = f"""
    <section class="block">
      <div class="block-head"><h2>What to check next</h2>
        {f'<span class="ok-chip">{free} free check{"s" if free > 1 else ""} first</span>' if free else ""}</div>
      <div class="card tbl"><table><thead><tr><th>Step</th><th>Check and why</th><th>Who</th><th>Cost</th></tr></thead>
        <tbody>{steps}</tbody></table></div>
    </section>"""

    # ---- sidebar
    facts = [
        ("Parcel ID", p["parcel_id"]),
        ("Block-lot", p["block_lot"]),
        (
            "Lot",
            f"{p['lot_area_sqft']:,.0f} sq ft"
            + (f" ({dims['width']:.0f} × {dims['depth']:.0f} ft)" if dims else ""),
        ),
        ("Zoning", zoning),
        ("Current use", (p["current_use"] or "").title()),
        ("Owner type", p["owner_type"].replace("_", " ")),
        ("Assessed land", money(p.get("assessed_land") or 0, k=False)),
    ]
    fact_rows = "".join(
        f'<div class="kv"><span>{k}</span><b>{e(str(val))}</b></div>' for k, val in facts
    )
    head = next((o for o in a["options"] if o["label"] == head_label), None)
    pf_rows = [("Target margin", f"{A['target_margin']['value']:.0%}", "your default")]
    if head:
        pf_rows.append(("Sale basis", "", head["revenue_basis"]))
    pf_rows += [
        (
            "Hard cost",
            f"${A['hard_cost_psf']['min']:.0f}–${A['hard_cost_psf']['max']:.0f} / sq ft",
            A["hard_cost_psf"]["source"],
        ),
        (
            "Soft costs",
            f"{A['soft_cost_share']['min']:.0%}–{A['soft_cost_share']['max']:.0%} of hard",
            A["soft_cost_share"]["source"],
        ),
        ("Land", money(land["value"], k=False), land["source"]),
    ]
    pf_html = "".join(
        f'<div class="kv"><span>{k}<br><em>{e(note)}</em></span><b>{e(val)}</b></div>'
        for k, val, note in pf_rows
    )
    as_of = (ctx["provenance"].get("parcels") or {}).get("as_of") or "—"
    side = f"""
    <aside>
      <section class="card"><h3>Parcel</h3><div class="facts">{fact_rows}</div></section>
      <section class="card"><h3>Pro forma assumptions</h3><div class="facts">{pf_html}</div>
        <p class="muted small">Change any of them: <code>--set hard_cost_psf=200</code>, <code>--land-price 35000</code></p></section>
      <section class="card about"><h3>About this report</h3>
        <p class="small">A screening, not a zoning determination. Every finding shows its source and confidence; unknowns are never scored as clear. Costs marked placeholder are defaults, not local benchmarks.</p>
        <span class="mono">Engine {e(ver["engine"])} · {e(ver["ruleset"])} · parcels as of {e(as_of)}</span></section>
    </aside>"""

    return f"""<title>{e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>{CSS}</style>
<header class="top"><div class="brand"><span class="logo">▲</span> Buildable PGH</div>
  <div class="site"><b>{e(p["address"].title())}, {e(p["municipality"].split(" - ")[-1].title())}</b>
    <span class="mono">{e(p["parcel_id"])} · {p["lot_area_sqft"]:,.0f} sq ft · {e(zoning)}</span></div>
  <span class="tag">Engine {e(ver["engine"])}</span></header>
<main class="grid">
  <div class="main">{verdict}{cards}{kill}{build}{nxt}
    <p class="muted small foot">Screening only. This report is not a zoning determination, legal advice or an engineering assessment; confirm with the Zoning Administrator before relying on it.</p>
  </div>
  {side}
</main>"""


CSS = """
:root{--ground:#F3F1EC;--card:#FFFFFF;--ink:#16181C;--muted:#6B6E73;--line:#E4E0D8;
--soft:#F7F5F0;--risk:#B42318;--risk-bg:#FDECEA;--warn:#9A5B00;--warn-bg:#FFF3DC;
--ok:#1F7A4D;--ok-bg:#E7F4EC;--unk-bg:#EEF0F2;--lead:#F6E7A8;--slope:#F2C4BE;--flood:#BFD9F2;
--mine:#D9CFE8;--siteFill:#FBEFC0;
--serif:"Newsreader",Georgia,"Times New Roman",serif;--sans:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--ground:#121315;--card:#1B1D20;--ink:#ECEBE7;--muted:#9EA1A6;--line:#2E3035;--soft:#222428;--risk:#F2877C;--risk-bg:#3A1F1C;--warn:#E8B465;--warn-bg:#352A17;--ok:#6CC69A;--ok-bg:#16301F;--unk-bg:#26292D;--lead:#5A4E1C;--slope:#6B3A36;--flood:#26415C;--mine:#3F3551;--siteFill:#4A421F}}
:root[data-theme="dark"]{color-scheme:dark;--ground:#121315;--card:#1B1D20;--ink:#ECEBE7;--muted:#9EA1A6;--line:#2E3035;--soft:#222428;--risk:#F2877C;--risk-bg:#3A1F1C;--warn:#E8B465;--warn-bg:#352A17;--ok:#6CC69A;--ok-bg:#16301F;--unk-bg:#26292D;--lead:#5A4E1C;--slope:#6B3A36;--flood:#26415C;--mine:#3F3551;--siteFill:#4A421F}
body{background:var(--ground);color:var(--ink);font:14px/1.5 var(--sans)}
.top{display:flex;flex-wrap:wrap;align-items:center;gap:12px 28px;padding-block:14px;padding-inline:20px;background:var(--card);border-bottom:1px solid var(--line)}
.brand{font:600 16px var(--serif);display:flex;align-items:center;gap:8px}.logo{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:6px;background:var(--ink);color:var(--lead);font-size:12px}
.site{display:grid;flex:1;min-width:220px}.site .mono{font-size:12px}
.grid{max-width:1100px;margin:0 auto;padding-inline:20px;padding-block:28px 48px;display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:24px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
.main{display:grid;gap:22px;align-content:start}aside{display:grid;gap:16px;align-content:start}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
h1{font:500 26px/1.25 var(--serif);margin:10px 0 0;text-wrap:balance;max-width:30ch}
h2{font:500 22px/1.2 var(--serif);margin:0}h3{font:600 13px var(--sans);margin:0 0 10px}
p{margin:0}.muted{color:var(--muted)}.small{font-size:12px}.num{font-variant-numeric:tabular-nums}
.mono,code{font:12px var(--mono);color:var(--muted)}
.eyebrow{font-size:12px;color:var(--muted)}
.verdict-top{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
.score{text-align:right;display:grid;justify-items:end}.big{font:500 64px/1 var(--serif)}.big span{font-size:18px;color:var(--muted)}
.pill,.chip{display:inline-block;font:500 12px var(--sans);padding:3px 10px;border-radius:999px;white-space:nowrap}
.risk{background:var(--risk-bg);color:var(--risk)}.caution{background:var(--warn-bg);color:var(--warn)}
.ok{background:var(--ok-bg);color:var(--ok)}.minor,.unknown{background:var(--unk-bg);color:var(--muted)}
.where{border-top:1px solid var(--line);margin-top:20px;padding-top:16px}
.bars{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}@media (max-width:640px){.bars{grid-template-columns:1fr}}
.bar{display:grid;gap:5px}.bar-top{display:flex;justify-content:space-between;font-size:13px}
.track{height:6px;background:var(--line);border-radius:3px}.fill{height:6px;background:var(--ink);border-radius:3px}
.cards3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}@media (max-width:760px){.cards3{grid-template-columns:1fr}}
.mini{display:grid;gap:4px;align-content:start}.mid{font:500 26px/1.2 var(--serif)}.down{color:var(--risk);font-size:13px}
.block{display:grid;gap:12px}.block-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.list{padding:0;overflow:hidden}.flag{display:grid;grid-template-columns:96px minmax(0,1fr) auto;gap:14px;padding:18px 20px;border-bottom:1px solid var(--line)}
@media (max-width:640px){.flag{grid-template-columns:1fr}}
.flag-title{font-weight:600}.flag-body{display:grid;gap:6px}.flag-body p{color:var(--muted);font-size:13px}
.tags{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.tag{font:11.5px var(--mono);background:var(--soft);border:1px solid var(--line);border-radius:4px;padding:2px 7px;color:var(--muted)}
.flag-side{text-align:right;display:grid;gap:3px;align-content:start;min-width:120px}.amt{font-weight:600}
.flag-side a{color:inherit;font-size:12.5px;font-weight:500}
.cleared{padding:12px 20px;background:var(--soft);font-size:13px;color:var(--muted)}.cleared b{color:var(--ok);margin-right:6px}
.cards2{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media (max-width:760px){.cards2{grid-template-columns:1fr}}
.option{display:grid;gap:8px;align-content:start}.option.lead{border:2px solid var(--ink)}
.opt-top{display:flex;justify-content:space-between;align-items:center;gap:8px}.badge{background:var(--lead);font-size:11.5px;padding:2px 9px;border-radius:999px}
.opt-name{font:500 24px/1.2 var(--serif)}.kv3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;border-block:1px solid var(--line);padding-block:10px;margin-block:4px}
.kv3 div{display:grid}.kv3 b{font-size:14px}
.tbl{padding:0;overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:520px}
th,td{text-align:left;vertical-align:top;padding:12px 16px;border-bottom:1px solid var(--line)}
th{font-size:12px;color:var(--muted);font-weight:500;background:var(--soft)}tr:last-child td{border-bottom:0}
.stepn{font:500 22px var(--serif);width:40px}.ok-chip{background:var(--ok-bg);color:var(--ok);font-size:12px;padding:3px 10px;border-radius:999px}
.mapcard{padding:0;overflow:hidden}.map{background:var(--soft);border-bottom:1px solid var(--line)}.map svg{display:block;width:100%;height:auto}
.m-lot{fill:var(--card);stroke:var(--muted);stroke-width:.6;stroke-opacity:.6}.m-slope{fill:var(--slope);fill-opacity:.75}
.m-flood{fill:var(--flood);fill-opacity:.75}.m-mine{fill:var(--mine);fill-opacity:.55}
.m-site{fill:var(--siteFill);fill-opacity:.55;stroke:var(--ink);stroke-width:2}
.legend{display:flex;flex-wrap:wrap;gap:12px;padding:10px 16px;font-size:12px;color:var(--muted)}
.lg::before{content:"";display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px;border:1px solid var(--ink)}
.lg-site::before{background:var(--siteFill)}.lg-slope::before{background:var(--slope);border-color:transparent}
.lg-mine::before{background:var(--mine);border-color:transparent}.lg-flood::before{background:var(--flood);border-color:transparent}
.facts{display:grid}.mapcard .facts{padding:4px 16px 12px}
.kv{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}
.kv:last-child{border-bottom:0}.kv span{color:var(--muted)}.kv em{font-style:normal;font-size:11px}.kv b{text-align:right;font-weight:500}
.about{background:var(--soft)}.about p{margin-bottom:8px}.foot{max-width:70ch}
"""


def main() -> None:
    pid = sys.argv[1]
    payload = json.loads((OUT / f"{pid}.json").read_text())
    out = OUT / f"{pid}.html"
    out.write_text(render(payload))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
