"""Outcome-driven blueprint optimizer.

The optimizer turns measured client outcomes into proposed blueprint changes.
It does not silently rewrite active production blueprints; promotion remains an
explicit operator/client decision.
"""
from __future__ import annotations

def _delta(before, after):
    if before is None or after is None: return None
    return float(after)-float(before)

def propose(metric_name, before, after, target=None, service=None, blueprint_version=1):
    delta=_delta(before,after)
    direction="improved" if target is not None and after is not None and float(after)>=float(target) else "needs_review"
    if delta is not None and target is None:
        direction="improved" if delta>0 else ("declined" if delta<0 else "flat")
    recommendation={
        "metric":metric_name,"before":before,"after":after,"delta":delta,
        "target":target,"service":service,"blueprint_version":blueprint_version,
        "direction":direction,
    }
    if delta is None:
        recommendation["action"]="collect_more_measurements"
    elif direction=="improved":
        recommendation["action"]="preserve_pattern_and_test_reuse"
    else:
        recommendation["action"]="generate_experiment"
    return recommendation

def batch_proposals(metrics):
    return [propose(**metric) for metric in metrics]
