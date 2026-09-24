"""Economic controls and attribution helpers."""
from __future__ import annotations

def unit_economics(revenue=0.0, operating_cost=0.0):
    revenue=float(revenue or 0); cost=float(operating_cost or 0)
    return {
        "revenue":revenue,
        "operating_cost":cost,
        "contribution":round(revenue-cost,2),
        "revenue_per_operating_dollar": None if cost<=0 else round(revenue/cost,2),
        "margin_percent": None if revenue<=0 else round((revenue-cost)/revenue*100,2),
    }

def model_cost(input_tokens=0, output_tokens=0, input_rate=0.0, output_rate=0.0):
    return round((float(input_tokens or 0)/1000*float(input_rate or 0))+
                 (float(output_tokens or 0)/1000*float(output_rate or 0)),6)
