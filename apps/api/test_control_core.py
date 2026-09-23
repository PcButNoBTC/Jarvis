from evidence_engine import evidence_strength, build_claim
from policy_engine import evaluate_action
from economics import unit_economics
from service_blueprints import blueprint
from action_receipts import make_receipt
from checkpoints import retry_delay

def test_evidence_strength_and_claim():
    items=[{"strength":"direct"},{"strength":"strong"}]
    assert evidence_strength(items)==85.0
    c=build_claim("form friction",items,alternatives=["phone-first"])
    assert c["evidence_strength"]==85.0

def test_policy_budget_and_approval():
    d=evaluate_action("send_message",tools=["send_message"],approval_required=True,approved=False,budget=1,spent=0,estimated_cost=.2)
    assert d.decision=="approval_required"
    d=evaluate_action("send_message",tools=["send_message"],approval_required=False,budget=.1,spent=.1,estimated_cost=.01)
    assert d.decision=="deny"

def test_unit_economics():
    e=unit_economics(1000,100)
    assert e["contribution"]==900
    assert e["revenue_per_operating_dollar"]==10.0

def test_blueprint_and_receipt():
    assert "qa" in blueprint("AI Website")
    a=make_receipt(action="read",decision="allow",actor="research")
    b=make_receipt(action="draft",decision="allow",actor="research",previous_hash=a["hash"])
    assert b["previous_hash"]==a["hash"]
    assert b["hash"]!=a["hash"]

def test_retry():
    assert retry_delay(1)==5
    assert retry_delay(4)==40
