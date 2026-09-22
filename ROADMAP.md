# Luma Strong MVP Roadmap

The Strong MVP is complete only when the operating loop is connected end-to-end.

## Phase 1 — Delivery control plane
- [x] Service-specific project configuration
- [x] Configuration validation
- [x] Configuration → compiled requirements
- [x] Requirements persisted on project and implementation
- [x] Service adapter build-plan layer
- [ ] Provider-specific artifact generators
- [ ] Configuration-aware automated QA

## Phase 2 — Opportunity and sales intelligence
- [x] Service-specific opportunity mapping
- [x] Numeric confidence
- [x] Evidence ledger
- [x] Opportunity lifecycle endpoint
- [x] Human-approved outreach drafts
- [ ] Duplicate active-opportunity guard
- [ ] Follow-up queue and proposal versioning

## Phase 3 — Project operations
- [x] Delivery task checklist
- [x] Project milestones
- [x] Milestone status updates
- [ ] Dependencies
- [ ] Approval history
- [ ] Client review/revision loop

## Phase 4 — Build, QA, launch, handoff
- [x] Artifact generation
- [x] Automated validation
- [x] Approval gate
- [x] Static deployment target
- [x] Launch readiness
- [x] Monitoring
- [x] Handoff package
- [ ] Provider-specific deployment adapters
- [ ] Service-specific production generators

## Phase 5 — Revenue / economics
- [x] Revenue transactions
- [x] Cost records
- [x] Contribution calculation
- [x] Revenue-per-cost metric
- [x] Service performance
- [x] Billing records
- [x] Payment reconciliation
- [ ] Recurring revenue lifecycle
- [ ] Margin by project/client
- [ ] Model-token cost attribution

## Phase 6 — Automation
- [x] Workflow definitions
- [x] Workflow run persistence
- [x] Deterministic step advancement
- [x] Human approval boundary for consequential actions
- [ ] Scheduled triggers
- [ ] Retry/backoff policies
- [ ] Event-driven orchestration

## Phase 7 — Integrations
- [x] Provider registry
- [x] Connection records
- [ ] Email adapter
- [ ] Calendar adapter
- [ ] CRM adapter
- [ ] Forms adapter
- [ ] Phone/voice adapter
- [ ] Analytics adapter
- [ ] Payment provider adapter
- [ ] Hosting adapters

## Phase 8 — Security
- [x] Optional self-hosted API key
- [x] Scoped client portal tokens
- [x] Audit-log data model
- [ ] User authentication
- [ ] Roles/permissions
- [ ] Secret manager
- [ ] Security event logging
- [ ] Rate limiting

## Phase 9 — Client portal
- [x] Scoped project read view
- [x] Milestone visibility
- [ ] Requirements submission
- [ ] Client approval
- [ ] Revision requests
- [ ] Deliverable downloads
- [ ] Client messaging

## Phase 10 — Agent layer
- [x] Agent-run persistence
- [x] Tool/control-plane foundations
- [ ] Research agent
- [ ] Sales agent
- [ ] Project agent
- [ ] Build agent
- [ ] QA agent
- [ ] Launch agent
- [ ] Per-agent budgets and permissions
- [ ] Agent evaluation

## Definition of Strong MVP

Every module must have:
1. A clear job.
2. Persistent state.
3. Validation.
4. An observable outcome.
5. A safe handoff to the next module.
6. Human approval before consequential external actions.
7. Enough telemetry to measure whether it contributes to revenue.
