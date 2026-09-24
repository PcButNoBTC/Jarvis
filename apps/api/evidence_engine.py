"""Evidence and claim provenance primitives.

Evidence is observable input; claims are interpretations backed by evidence.
The engine deliberately avoids pretending model confidence is factual certainty.
"""
from __future__ import annotations
from datetime import datetime, timezone

STRENGTH = {"weak":25.0,"moderate":50.0,"strong":75.0,"direct":95.0}

def evidence_strength(items):
    values=[]
    for item in items or []:
        if isinstance(item,dict):
            values.append(float(item.get("strength_score") or STRENGTH.get(item.get("strength"),50)))
    return round(sum(values)/len(values),2) if values else 0.0

def build_claim(claim, evidence, *, alternatives=None, verified_at=None):
    score=evidence_strength(evidence)
    return {
        "claim":claim,
        "evidence_ids":[e.get("id") for e in evidence if isinstance(e,dict) and e.get("id")],
        "evidence_strength":score,
        "alternatives":alternatives or [],
        "verified_at":verified_at or datetime.now(timezone.utc).isoformat(),
    }

def classify_strength(observation, source_url=None, direct=False):
    if direct: return "direct", 95.0
    if source_url and observation: return "strong", 75.0
    return "moderate", 50.0
