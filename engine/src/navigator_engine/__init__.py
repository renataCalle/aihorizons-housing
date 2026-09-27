"""Feasibility engine: SiteContext in, SiteAnalysis out.

A pure library: no network calls and no database reads. Everything arrives in SiteContext
or lives in versioned config inside this package (rules tables in config/rules/).

    from navigator_engine import analyze
    analysis = analyze(context_dict, overrides={"hard_cost_psf": 230}, program=None)
"""

from navigator_engine.analyze import ENGINE_VERSION, analyze

__all__ = ["ENGINE_VERSION", "analyze"]
