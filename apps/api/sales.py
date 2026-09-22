import json

def build_call_prep(opportunity: dict) -> dict:
    evidence = opportunity.get("problem_evidence") or []
    return {
        "opening": "I noticed a few observable signals that may be worth discussing. I want to understand how they affect your current lead flow before suggesting anything.",
        "service": opportunity.get("service_name") or "Custom Automation",
        "evidence": [
            "- {0}: {1} points".format(x.get("factor", "observed signal"), x.get("points", 0))
            for x in evidence if isinstance(x, dict)
        ] or ["No specific issue was recorded; discovery should establish the business problem."],
        "discovery_questions": [
            "How are new leads currently captured and followed up?",
            "Where do prospects usually drop out of the process?",
            "How much time does the team spend handling this manually each week?",
            "What would a successful improvement be worth to the business?",
            "What systems or tools would this need to work with?",
        ],
        "objection_handling": [
            {"objection": "We already have a website.", "response": "The goal is not to replace something that works; it is to identify whether a measurable problem remains."},
            {"objection": "Send me information.", "response": "Absolutely. I can send a short proposal after I understand the current process and desired outcome."},
        ],
        "next_step": "Confirm the problem, desired outcome, decision process, and whether a scoped proposal is appropriate.",
    }


def build_proposal_content(business_name: str, offer: dict, opportunity: dict) -> str:
    setup = ${:,.2f}.format(offer["setup_price"]) if offer.get("setup_price") is not None else "To be confirmed"
    recurring = ${:,.2f}/month.format(offer["recurring_price"]) if offer.get("recurring_price") is not None else "None proposed"
    deliverables = offer.get("deliverables") or []
    assumptions = offer.get("assumptions") or []
    exclusions = offer.get("exclusions") or []
    lines = [
        "# Proposal: " + offer["name"], "",
        "**Client:** " + business_name,
        "**Opportunity:** " + opportunity["title"], "",
        "## Situation", opportunity.get("description") or "A business workflow improvement opportunity was identified.", "",
        "## Proposed outcome", offer.get("description") or "Implement a focused improvement tied to the validated business problem.", "",
        "## Deliverables",
    ]
    lines += ["- " + x for x in deliverables]
    lines += ["", "## Timeline", "Target delivery: approximately {} days after requirements are confirmed.".format(opportunity.get("delivery_days") or 7), "", "## Investment", "- Setup: " + setup, "- Recurring: " + recurring, "", "## Assumptions"]
    lines += ["- " + x for x in assumptions]
    lines += ["", "## Exclusions"]
    lines += ["- " + x for x in exclusions]
    lines += ["", "## Next step", "Confirm scope, requirements, pricing, and acceptance criteria before work begins."]
    return "\n".join(lines)
