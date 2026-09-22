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


# --- Revenue-focused outreach (evidence → reply → meeting) ---

FACTOR_PLAIN = {
    "site_error": "the site returned an error when we loaded it",
    "no_https_observed": "the site was not served over HTTPS",
    "no_mobile_viewport_observed": "the homepage is missing a mobile viewport tag",
    "no_contact_form_observed": "there was no clear contact or quote form on the site",
    "no_phone_link_observed": "there was no click-to-call phone link",
    "no_clear_cta_observed": "there was no clear call-to-action (book, quote, or contact)",
    "no_email_or_contact_form_observed": "there was no email link or contact form",
    "slow_response_observed": "the page took several seconds to respond",
}

SERVICE_OUTCOME = {
    "AI Website": "a conversion-focused site that makes it easier for visitors to take action",
    "Lead Capture System": "a simple lead intake and follow-up flow so inquiries do not sit unanswered",
    "AI Receptionist": "coverage for inbound calls so fewer jobs are lost to voicemail or missed rings",
    "Appointment Automation": "booking and reminder automation that reduces no-shows and back-and-forth",
    "Review Automation": "a light post-job review request flow that builds proof over time",
    "Video Walkthrough": "a short walkthrough video that builds trust before the first call",
    "Custom Automation": "a scoped workflow tied to one measurable bottleneck",
}

INDUSTRY_HOOK = {
    "dental": "new patient inquiries",
    "dentist": "new patient inquiries",
    "medical": "new patient or appointment requests",
    "clinic": "new patient or appointment requests",
    "hvac": "emergency and estimate calls",
    "plumber": "service and estimate calls",
    "plumbing": "service and estimate calls",
    "electrician": "service and estimate calls",
    "contractor": "project and estimate inquiries",
    "roofing": "estimate and storm-lead calls",
    "law": "intake calls and consultation requests",
    "attorney": "intake calls and consultation requests",
    "legal": "intake calls and consultation requests",
    "restaurant": "reservations and reputation",
    "salon": "bookings and rebooking",
    "spa": "bookings and rebooking",
    "real estate": "buyer and seller inquiries",
    "realtor": "buyer and seller inquiries",
    "auto": "service appointments and quotes",
    "veterinary": "appointment and urgent-care calls",
    "vet": "appointment and urgent-care calls",
}


def _plain_observations(evidence: list, limit: int = 2) -> list[str]:
    lines = []
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        factor = item.get("factor")
        plain = FACTOR_PLAIN.get(factor)
        if plain and plain not in lines:
            lines.append(plain)
        if len(lines) >= limit:
            break
    return lines


def _industry_hook(industry: str | None) -> str:
    if not industry:
        return "leads and follow-up"
    text = industry.lower()
    for key, hook in INDUSTRY_HOOK.items():
        if key in text:
            return hook
    return "leads and follow-up"


def build_outreach_sequence(opportunity: dict) -> dict:
    """
    Build a 3-touch email sequence (Day 1 / 3 / 7) from opportunity evidence.
    All drafts stay status=draft until a human approves — nothing auto-sends.
    """
    business = opportunity.get("business_name") or "your business"
    service = opportunity.get("service_name") or "Custom Automation"
    industry = opportunity.get("industry")
    evidence = opportunity.get("problem_evidence") or []
    observations = _plain_observations(evidence, limit=2)
    outcome = SERVICE_OUTCOME.get(service, SERVICE_OUTCOME["Custom Automation"])
    hook = _industry_hook(industry)

    if observations:
        obs_sentence = "I noticed " + (" and ".join(observations)) + "."
    else:
        obs_sentence = (
            "I reviewed the site and saw a few areas that often affect "
            + hook
            + "."
        )

    # Day 1 — observation + soft ask (highest leverage)
    day1_subject = f"Quick note on {business}'s site"
    if service == "AI Receptionist":
        day1_subject = f"Missed calls at {business}?"
    elif service == "Lead Capture System":
        day1_subject = f"{business} — lead intake on the site"
    elif service == "Appointment Automation":
        day1_subject = f"Booking friction at {business}"
    elif service == "Review Automation":
        day1_subject = f"Reviews for {business}"

    day1_body = (
        f"Hi,\n\n"
        f"I took a quick look at {business}'s website — not a sales scrape, "
        f"just the public pages. {obs_sentence}\n\n"
        f"For many {industry or 'local'} teams, that kind of gap can quietly cost "
        f"{hook}. I am not assuming it is a problem for you; I only wanted to "
        f"share what I saw.\n\n"
        f"If helpful, I can send a one-page note on {outcome}, written in plain "
        f"language, with a clear price range. No long deck. Would that be useful?\n\n"
        f"Best,\nLuma"
    )

    # Day 3 — short bump
    day3_subject = f"Re: {day1_subject}"
    day3_body = (
        f"Hi,\n\n"
        f"Just checking in on my note about {business}. "
        f"If the timing is wrong, no need to reply — I will not keep chasing. "
        f"If a short one-pager would help, say the word and I will send it.\n\n"
        f"Best,\nLuma"
    )

    # Day 7 — value + close loop
    day7_subject = f"One idea for {business}"
    day7_body = (
        f"Hi,\n\n"
        f"Last note from me so your inbox stays clear. "
        f"The simplest first step, based only on what I observed, is usually "
        f"{outcome}.\n\n"
        f"Happy to jump on a 10-minute call or send the one-pager. "
        f"If it is not relevant, feel free to ignore this — no hard feelings.\n\n"
        f"Best,\nLuma"
    )

    return {
        "service": service,
        "observations": observations,
        "touches": [
            {"day": 1, "channel": "email", "subject": day1_subject, "body": day1_body},
            {"day": 3, "channel": "email", "subject": day3_subject, "body": day3_body},
            {"day": 7, "channel": "email", "subject": day7_subject, "body": day7_body},
        ],
    }


def default_offer_scope(service_name: str, business_name: str) -> dict:
    """Concrete deliverables that make proposals easier to accept."""
    scopes = {
        "AI Website": {
            "name": f"AI Website — {business_name}",
            "description": (
                "Conversion-focused website improvements with clear lead paths "
                "and mobile-ready layout."
            ),
            "deliverables": [
                "Homepage and key landing page conversion review",
                "Mobile + form/CTA implementation in agreed scope",
                "Lead capture connected to agreed inbox or CRM",
                "Handoff checklist and basic training",
            ],
            "assumptions": [
                "Client provides brand assets, copy, and domain/hosting access.",
                "Scope is limited to agreed pages and forms.",
            ],
            "exclusions": [
                "Ongoing ad spend or third-party SaaS fees.",
                "Custom software outside the agreed page/form work.",
            ],
        },
        "Lead Capture System": {
            "name": f"Lead Capture System — {business_name}",
            "description": (
                "Structured lead intake, routing, and first-response workflow "
                "so inquiries are not lost."
            ),
            "deliverables": [
                "Lead form or intake path on the site or landing page",
                "Routing rules to email/CRM/SMS as agreed",
                "Basic auto-acknowledgment to the lead",
                "Handoff and owner training on the queue",
            ],
            "assumptions": [
                "Client names who owns lead response and preferred tools.",
                "Existing CRM/email access is provided when required.",
            ],
            "exclusions": [
                "Paid ads or list buying.",
                "Full CRM migration outside agreed fields.",
            ],
        },
        "AI Receptionist": {
            "name": f"AI Receptionist — {business_name}",
            "description": (
                "AI-assisted inbound call handling for after-hours and overflow "
                "so fewer opportunities hit voicemail only."
            ),
            "deliverables": [
                "Call flow design (greet, qualify, book or take message)",
                "Integration with agreed calendar or notification channel",
                "Test calls and script refinements",
                "Go-live checklist and owner handoff",
            ],
            "assumptions": [
                "Client provides phone number routing options and business hours rules.",
                "Booking calendars or notification endpoints are available.",
            ],
            "exclusions": [
                "Carrier fees and phone number purchase unless agreed.",
                "Outbound cold-calling campaigns.",
            ],
        },
        "Appointment Automation": {
            "name": f"Appointment Automation — {business_name}",
            "description": (
                "Booking, confirmation, and reminder flow to cut no-shows "
                "and scheduling back-and-forth."
            ),
            "deliverables": [
                "Online booking path or improved CTA to book",
                "Confirmation and reminder messages (email and/or SMS)",
                "Calendar sync as agreed",
                "Owner training on the booking queue",
            ],
            "assumptions": [
                "Client provides calendar access and reminder preferences.",
                "SMS provider credentials provided if SMS is in scope.",
            ],
            "exclusions": [
                "SMS carrier fees unless included in the offer.",
                "Multi-location complex routing beyond agreed scope.",
            ],
        },
        "Review Automation": {
            "name": f"Review Automation — {business_name}",
            "description": (
                "Post-job review request workflow to collect more consistent "
                "public proof."
            ),
            "deliverables": [
                "Trigger rules after completed jobs or visits",
                "Review request message templates",
                "Links to preferred review platforms",
                "Simple reporting on request volume",
            ],
            "assumptions": [
                "Client defines when a job is 'complete' and who is eligible.",
            ],
            "exclusions": [
                "Buying or incentivizing fake reviews.",
                "Reputation crisis management.",
            ],
        },
        "Custom Automation": {
            "name": f"Custom Automation — {business_name}",
            "description": (
                "Scoped automation tied to one measurable workflow bottleneck."
            ),
            "deliverables": [
                "Discovery and written process map for the target workflow",
                "Configured automation within agreed tools",
                "Test run and acceptance checklist",
                "Owner handoff",
            ],
            "assumptions": [
                "Client provides access to the systems involved.",
                "Scope remains limited to the agreed workflow.",
            ],
            "exclusions": [
                "Open-ended development without a written scope.",
                "Third-party license fees unless listed.",
            ],
        },
    }
    return scopes.get(
        service_name,
        {
            "name": f"{service_name} — {business_name}",
            "description": f"Scoped implementation of {service_name}.",
            "deliverables": [
                "Discovery and requirements confirmation",
                "Configured implementation of the agreed scope",
                "Basic testing and handoff",
            ],
            "assumptions": [
                "Client provides required access, content, and approvals.",
                "Scope remains within the agreed deliverables.",
            ],
            "exclusions": [
                "Unscoped third-party licenses or usage fees.",
                "Material scope changes after approval.",
            ],
        },
    )


def build_client_brief(opportunity: dict) -> dict:
    """
    One-page, client-friendly brief: what we noticed, why it matters,
    a simple recommended next step, and clear pricing range.
    Designed to be shared with the prospect — not internal jargon.
    """
    business = opportunity.get("business_name") or "your business"
    service = opportunity.get("service_name") or "Custom Automation"
    industry = opportunity.get("industry")
    evidence = opportunity.get("problem_evidence") or []
    observations = _plain_observations(evidence, limit=3)
    outcome = SERVICE_OUTCOME.get(service, SERVICE_OUTCOME["Custom Automation"])
    hook = _industry_hook(industry)

    price_min = opportunity.get("price_min") or opportunity.get("estimated_value_min")
    price_max = opportunity.get("price_max") or opportunity.get("estimated_value_max")
    if price_min is not None and price_max is not None:
        investment = f"${float(price_min):,.0f}–${float(price_max):,.0f} setup (typical range for this scope)"
    elif price_min is not None:
        investment = f"From ${float(price_min):,.0f} setup"
    else:
        investment = "Scoped after a short discovery call"

    if observations:
        noticed = [f"We noticed {o}." for o in observations]
    else:
        noticed = [
            f"We reviewed the public site for {business} and found a few areas "
            f"that often affect {hook}."
        ]

    why_it_matters = (
        f"For {industry or 'local'} businesses, gaps like these usually mean "
        f"fewer {hook} than the site and phones could produce — not because "
        f"the team is not working hard, but because the path for a customer "
        f"to reach you is unclear or incomplete."
    )

    recommendation = (
        f"A focused project for **{service}**: {outcome}. "
        f"We keep scope tight, show you the plan before work starts, "
        f"and only recommend what matches what we actually observed."
    )

    how_we_work = [
        "We only recommend based on what we can observe — no generic AI pitch.",
        "You approve every external message and every scope before work begins.",
        "One clear deliverable list, one price range, one owner on our side.",
        "If it is not a fit after discovery, we say so and stop.",
    ]

    next_step = (
        "A 10–15 minute call to confirm whether this is a real problem for you, "
        "what success would look like, and whether a scoped proposal makes sense. "
        "No long deck. No pressure."
    )

    markdown = "\n".join(
        [
            f"# A short look at {business}",
            "",
            "## What we noticed",
            *[f"- {line}" for line in noticed],
            "",
            "## Why it can matter",
            why_it_matters,
            "",
            "## A simple recommendation",
            recommendation,
            "",
            f"**Typical investment:** {investment}",
            "",
            "## How we work with clients",
            *[f"- {line}" for line in how_we_work],
            "",
            "## Suggested next step",
            next_step,
            "",
            "— Luma",
        ]
    )

    return {
        "business_name": business,
        "service": service,
        "title": f"A short look at {business}",
        "noticed": noticed,
        "why_it_matters": why_it_matters,
        "recommendation": recommendation,
        "investment": investment,
        "how_we_work": how_we_work,
        "next_step": next_step,
        "markdown": markdown,
    }
