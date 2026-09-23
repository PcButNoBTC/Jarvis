# Luma Client Trust & Regional Growth

Luma is built to profit from useful outcomes without treating local businesses as targets to be extracted from.

## Product rule

**Diagnose before selling.**

Luma should show observable evidence, explain the likely business impact, present a proportionate solution, and leave the decision with the business owner.

## Trust rules

1. **Evidence before recommendation.** Website observations and other permitted sources are recorded separately from hypotheses.
2. **Problem before product.** A service is recommended only after a documented problem and solution fit.
3. **Smallest useful solution.** Luma should not upsell a more complex service when a simpler fix addresses the evidenced problem.
4. **Why this / why not.** Recommendations can include alternatives and explicit reasons not to pursue other services.
5. **No-pressure outreach.** Declines, complaints, and do-not-contact requests suppress outreach.
6. **Human control.** External messages and consequential production actions remain approval-gated.
7. **AI transparency.** Client-facing AI should be configurable for clear disclosure and human escalation.
8. **Client data control.** Provider credentials belong in the secret-management layer; client preferences and outcomes are explicit records.
9. **Measure before expanding.** A new commercial recommendation should require a demonstrated outcome, client approval, and separately evidenced need.
10. **Protect regional reputation.** A local pilot is treated as a reputation-sensitive system. Outreach volume and follow-ups are bounded, and complaint signals stop automation.

## Opportunity-fit model

The fit engine weighs:
- evidence strength
- evidence confidence
- impact confidence
- solution fit
- intrusiveness risk

The result is one of:
- allow — evidence and fit justify human-reviewed outreach
- review — more human review is required
- suppress — do not pursue without new evidence or re-engagement

This is deliberately not a buying-probability score.

## Client outcome model

Luma can record baseline, current value, outcome type, client confirmation, measurement date, and notes.

Expansion checks require all three:
1. demonstrated value
2. client approval
3. new evidence of a separate problem

## Regional playbooks

A regional playbook records what has actually worked in a pilot: proven offers, industry patterns, outreach metrics, and client-success metrics.

A region should not be mass-launched simply because another region worked. The playbook documents evidence and operational constraints first.

## Recommended client-facing language

> We will show you what we observed, explain why it may matter, give you options, and let you decide. If we do not think automation is appropriate, we will say so.

Avoid claims of guaranteed revenue, guaranteed savings, or guaranteed business growth unless the claim is specifically supportable.

## Implementation

The policy lives in apps/api/client_trust.py and is exposed through the API for opportunity fit, outreach eligibility, client preferences, outcomes, and regional playbooks. The dashboard exposes the trust-first operating model in the Client Trust & Growth Controls section.