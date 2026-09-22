import json

SERVICE_DISCOVERY = {
    "AI Website": [
        "Who is the primary audience landing on the site today?",
        "What action do you most want a visitor to take?",
        "Have you measured mobile vs desktop conversion?",
        "What would a successful improvement be worth to the business?",
        "What systems or tools would a new site need to work with?",
    ],
    "Lead Capture System": [
        "How are new leads currently captured and followed up?",
        "Where do prospects usually drop out of the process?",
        "How long does it take for a lead to get a first response?",
        "What would a successful improvement be worth to the business?",
        "What CRM or inbox should leads land in?",
    ],
    "AI Receptionist": [
        "How many inbound calls do you miss or leave on voicemail each week?",
        "Who handles after-hours and overflow calls today?",
        "What information must be captured on every call?",
        "What would recovering missed calls be worth monthly?",
        "Should the system book appointments, take messages, or both?",
    ],
    "Appointment Automation": [
        "How do customers book appointments today?",
        "How much time is spent on confirmations and no-show follow-up?",
        "What calendar or scheduling tool is already in use?",
        "What would fewer no-shows be worth?",
        "Should reminders go out by SMS, email, or both?",
    ],
    "Review Automation": [
        "How do you currently ask happy customers for reviews?",
        "Which review platforms matter most in your market?",
        "What percentage of jobs result in a review today?",
        "What would more consistent reviews be worth for lead flow?",
        "When in the job cycle should a review request go out?",
    ],
    "Video Walkthrough": [
        "What should a prospect see that a static page cannot show?",
        "Do you already have video assets, or would we shoot new ones?",
        "Where should the video live (homepage, landing pages, ads)?",
        "What action should someone take after watching?",
        "What would stronger trust and conversion be worth?",
    ],
    "Custom Automation": [
        "What manual process eats the most staff time each week?",
        "Where do prospects or jobs get stuck today?",
        "What systems would this need to connect to?",
        "What would a successful improvement be worth to the business?",
        "Who owns the process on your side after launch?",
    ],
}

SERVICE_OPENINGS = {
    "AI Website": (
        "I reviewed the site and saw a few technical signals that can affect "
        "conversion. I want to understand how visitors move through the funnel "
        "before suggesting any change."
    ),
    "Lead Capture System": (
        "I noticed gaps in how leads can reach you from the site. I want to "
        "understand the current intake and follow-up flow before recommending anything."
    ),
    "AI Receptionist": (
        "I saw weak phone / inbound contact signals on the site. I want to "
        "understand how calls are handled today and where volume is missed."
    ),
    "Appointment Automation": (
        "Booking and CTA signals look thin on the site. I want to understand "
        "how appointments are scheduled and confirmed today."
    ),
    "Review Automation": (
        "I want to understand how you currently collect reviews and whether a "
        "lightweight post-job request flow would help."
    ),
    "Custom Automation": (
        "I noticed a few observable signals that may be worth discussing. "
        "I want to understand the underlying workflow before suggesting anything."
    ),
}


def build_call_prep(opportunity: dict) -> dict:
    evidence = opportunity.get("problem_evidence") or []
    service = opportunity.get("service_name") or "Custom Automation"
    questions = SERVICE_DISCOVERY.get(service) or SERVICE_DISCOVERY["Custom Automation"]
    opening = SERVICE_OPENINGS.get(service) or SERVICE_OPENINGS["Custom Automation"]

    return {
        "opening": opening,
        "service": service,
        "evidence": [
            "- {0}: {1} points".format(x.get("factor", "observed signal"), x.get("points", 0))
            for x in evidence
            if isinstance(x, dict)
        ]
        or ["No specific issue was recorded; discovery should establish the business problem."],
        "discovery_questions": questions,
        "objection_handling": [
            {
                "objection": "We already have a website.",
                "response": (
                    "The goal is not to replace something that works; it is to identify "
                    "whether a measurable problem remains."
                ),
            },
            {
                "objection": "Send me information.",
                "response": (
                    "Absolutely. I can send a short proposal after I understand the "
                    "current process and desired outcome."
                ),
            },
            {
                "objection": "We are too busy right now.",
                "response": (
                    "That is often the reason these gaps stay open. A scoped change "
                    "should reduce busywork, not add to it — we can start with one workflow."
                ),
            },
        ],
        "next_step": (
            "Confirm the problem, desired outcome, decision process, and whether a "
            "scoped proposal is appropriate."
        ),
    }


def build_proposal_content(business_name: str, offer: dict, opportunity: dict) -> str:
    setup = (
        "$" + "{:,.2f}".format(offer["setup_price"])
        if offer.get("setup_price") is not None
        else "To be confirmed"
    )
    recurring = (
        "$" + "{:,.2f}/month".format(offer["recurring_price"])
        if offer.get("recurring_price") is not None
        else "None proposed"
    )
    deliverables = offer.get("deliverables") or []
    assumptions = offer.get("assumptions") or []
    exclusions = offer.get("exclusions") or []
    lines = [
        "# Proposal: " + offer["name"],
        "",
        "**Client:** " + business_name,
        "**Opportunity:** " + opportunity["title"],
        "",
        "## Situation",
        opportunity.get("description")
        or "A business workflow improvement opportunity was identified.",
        "",
        "## Proposed outcome",
        offer.get("description")
        or "Implement a focused improvement tied to the validated business problem.",
        "",
        "## Deliverables",
    ]
    lines += ["- " + x for x in deliverables]
    lines += [
        "",
        "## Timeline",
        "Target delivery: approximately {} days after requirements are confirmed.".format(
            opportunity.get("delivery_days") or 7
        ),
        "",
        "## Investment",
        "- Setup: " + setup,
        "- Recurring: " + recurring,
        "",
        "## Assumptions",
    ]
    lines += ["- " + x for x in assumptions]
    lines += ["", "## Exclusions"]
    lines += ["- " + x for x in exclusions]
    lines += [
        "",
        "## Next step",
        "Confirm scope, requirements, pricing, and acceptance criteria before work begins.",
    ]
    return "\n".join(lines)
