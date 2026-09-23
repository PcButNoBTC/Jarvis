CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  legal_name TEXT,
  industry TEXT,
  website_url TEXT,
  phone TEXT,
  email TEXT,
  address TEXT,
  source TEXT,
  source_url TEXT,
  source_external_id TEXT,
  status TEXT NOT NULL DEFAULT 'prospect',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  name TEXT,
  title TEXT,
  email TEXT,
  phone TEXT,
  preferred_channel TEXT,
  is_primary BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS websites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  http_status INT,
  https_enabled BOOLEAN,
  mobile_friendly BOOLEAN,
  load_time_ms INT,
  cms TEXT,
  technology_stack JSONB NOT NULL DEFAULT '[]',
  last_checked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  summary TEXT,
  observed_problems JSONB NOT NULL DEFAULT '[]',
  opportunities JSONB NOT NULL DEFAULT '[]',
  evidence JSONB NOT NULL DEFAULT '[]',
  model TEXT,
  prompt_version TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  price_min NUMERIC(12,2),
  price_max NUMERIC(12,2),
  delivery_days INT,
  active BOOLEAN NOT NULL DEFAULT true,
  config JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  research_report_id UUID REFERENCES research_reports(id) ON DELETE SET NULL,
  service_id UUID REFERENCES services(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT,
  problem_evidence JSONB NOT NULL DEFAULT '[]',
  score NUMERIC(5,2),
  estimated_value_min NUMERIC(12,2),
  estimated_value_max NUMERIC(12,2),
  status TEXT NOT NULL DEFAULT 'new',
  next_action TEXT,
  next_action_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  service_id UUID REFERENCES services(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  description TEXT,
  setup_price NUMERIC(12,2),
  recurring_price NUMERIC(12,2),
  deliverables JSONB NOT NULL DEFAULT '[]',
  assumptions JSONB NOT NULL DEFAULT '[]',
  exclusions JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
  offer_id UUID REFERENCES offers(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  total_amount NUMERIC(12,2),
  recurring_amount NUMERIC(12,2),
  content TEXT,
  sent_at TIMESTAMPTZ,
  accepted_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE proposals ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID UNIQUE NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'active',
  customer_since DATE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
  service_id UUID REFERENCES services(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planning',
  agreed_price NUMERIC(12,2),
  recurring_price NUMERIC(12,2),
  start_date DATE,
  target_date DATE,
  requirements JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'todo',
  priority TEXT NOT NULL DEFAULT 'normal',
  assignee TEXT,
  due_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  subject TEXT,
  content TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
  channel TEXT NOT NULL,
  direction TEXT NOT NULL,
  subject TEXT,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  external_id TEXT,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',
  priority INT NOT NULL DEFAULT 50,
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  attempts INT NOT NULL DEFAULT 0,
  locked_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_research_business ON research_jobs(business_id) WHERE status IN ('pending','running');
CREATE INDEX IF NOT EXISTS idx_research_jobs_queue ON research_jobs(status, priority DESC, scheduled_at, created_at);

CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  model TEXT,
  prompt_version TEXT,
  input_tokens INT,
  output_tokens INT,
  estimated_cost NUMERIC(12,6),
  status TEXT NOT NULL DEFAULT 'started',
  input JSONB,
  output JSONB,
  error TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

INSERT INTO services (name, description, price_min, price_max, delivery_days) VALUES
('AI Website','Conversion-focused website with AI-assisted lead capture',750,3000,7),
('AI Receptionist','AI-assisted inbound call and appointment workflow',750,2500,7),
('Lead Capture System','Lead intake, qualification and routing workflow',500,2000,5),
('Appointment Automation','Booking, reminders and follow-up automation',500,2000,5),
('Review Automation','Review request and follow-up workflow',250,1000,3),
('Video Walkthrough','Short business/property/service walkthrough video',250,1500,5),
('Custom Automation','Custom workflow automation scoped to a measurable business problem',750,5000,14)
ON CONFLICT (name) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_status_score ON opportunities(status, score DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_opportunity_active ON opportunities(business_id, service_id) WHERE status IN ('new','qualified','contact_pending','contacted','discovery','proposal');
CREATE UNIQUE INDEX IF NOT EXISTS uq_proposal_opportunity_version ON proposals(opportunity_id, version);

CREATE INDEX IF NOT EXISTS idx_activities_opportunity_created ON activities(opportunity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_at);
CREATE INDEX IF NOT EXISTS idx_messages_outreach_queue ON messages(status, channel, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_business_source_external_id
  ON businesses(source, source_external_id)
  WHERE source IS NOT NULL AND source_external_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS implementations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'requirements',
  requirements JSONB NOT NULL DEFAULT '{}',
  generated_at TIMESTAMPTZ,
  validated_at TIMESTAMPTZ,
  validation JSONB NOT NULL DEFAULT '{}',
  preview_url TEXT,
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS delivery_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  implementation_id UUID REFERENCES implementations(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  path TEXT,
  download_url TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deployment_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  implementation_id UUID REFERENCES implementations(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  target TEXT,
  approved_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  output JSONB NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS handoffs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  package_path TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  client_approved BOOLEAN NOT NULL DEFAULT false,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_implementations_status ON implementations(status);
CREATE INDEX IF NOT EXISTS idx_deployment_runs_project ON deployment_runs(project_id, created_at DESC);


CREATE TABLE IF NOT EXISTS launch_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  settings JSONB NOT NULL DEFAULT '{}',
  ready BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_launch_settings_ready ON launch_settings(ready);

CREATE TABLE IF NOT EXISTS project_options (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  options JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_options_project ON project_options(project_id);


-- Strong-MVP operating layer: evidence, project milestones, revenue/cost,
-- automation, integrations, auditability, and client access foundations.
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,2);
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS rationale TEXT;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS factors JSONB NOT NULL DEFAULT '[]';
CREATE INDEX IF NOT EXISTS idx_opportunities_business_service ON opportunities(business_id, service_id);

CREATE TABLE IF NOT EXISTS evidence_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  research_report_id UUID REFERENCES research_reports(id) ON DELETE CASCADE,
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
  evidence_type TEXT NOT NULL,
  observation TEXT NOT NULL,
  source_url TEXT,
  source_locator TEXT,
  confidence NUMERIC(5,2),
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_evidence_business_observed ON evidence_items(business_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_opportunity ON evidence_items(opportunity_id);

CREATE TABLE IF NOT EXISTS project_milestones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  sequence INT NOT NULL DEFAULT 0,
  due_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_project_milestones_project ON project_milestones(project_id, sequence);

CREATE TABLE IF NOT EXISTS revenue_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL,
  transaction_type TEXT NOT NULL DEFAULT 'sale',
  status TEXT NOT NULL DEFAULT 'pending',
  amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  recurring_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  external_id TEXT,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_revenue_transactions_occurred ON revenue_transactions(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_revenue_transactions_project ON revenue_transactions(project_id);

CREATE TABLE IF NOT EXISTS cost_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
  category TEXT NOT NULL,
  amount NUMERIC(12,6) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  description TEXT,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cost_records_occurred ON cost_records(occurred_at DESC);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_name TEXT NOT NULL,
  trigger_type TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  status TEXT NOT NULL DEFAULT 'pending',
  current_step TEXT,
  attempts INT NOT NULL DEFAULT 0,
  input JSONB NOT NULL DEFAULT '{}',
  output JSONB NOT NULL DEFAULT '{}',
  error TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_queue ON workflow_runs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_entity ON workflow_runs(entity_type, entity_id);

CREATE TABLE IF NOT EXISTS integration_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  category TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  capabilities JSONB NOT NULL DEFAULT '[]',
  secret_ref TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  connected_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_integrations_project ON integration_connections(project_id, status);

CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_type TEXT NOT NULL,
  actor_id UUID,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS client_portal_access (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  token_hash TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_client_portal_access_client ON client_portal_access(client_id, status);

CREATE TABLE IF NOT EXISTS billing_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL,
  external_invoice_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  due_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_billing_status_due ON billing_records(status, due_at);


-- Strong-MVP completion layer: dependencies, approvals, revisions,
-- recurring revenue, scheduled automation, agent governance, and secret references.

CREATE TABLE IF NOT EXISTS project_dependencies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  depends_on_project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  dependency_type TEXT NOT NULL DEFAULT 'external',
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  required BOOLEAN NOT NULL DEFAULT true,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_project_dependencies_project ON project_dependencies(project_id, status);

CREATE TABLE IF NOT EXISTS approval_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  approval_type TEXT NOT NULL,
  decision TEXT NOT NULL,
  actor_type TEXT NOT NULL DEFAULT 'human',
  actor_id UUID,
  notes TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_approval_history_entity ON approval_history(entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS revision_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  implementation_id UUID REFERENCES implementations(id) ON DELETE SET NULL,
  requested_by TEXT NOT NULL DEFAULT 'client',
  status TEXT NOT NULL DEFAULT 'requested',
  summary TEXT NOT NULL,
  details TEXT,
  priority TEXT NOT NULL DEFAULT 'normal',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_revision_requests_project ON revision_requests(project_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS recurring_revenue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  billing_record_id UUID REFERENCES billing_records(id) ON DELETE SET NULL,
  amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  interval TEXT NOT NULL DEFAULT 'month',
  status TEXT NOT NULL DEFAULT 'active',
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  next_billing_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_recurring_revenue_status_next ON recurring_revenue(status, next_billing_at);

CREATE TABLE IF NOT EXISTS automation_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_name TEXT NOT NULL,
  cron_expression TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT true,
  input JSONB NOT NULL DEFAULT '{}',
  last_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_automation_schedules_due ON automation_schedules(enabled, next_run_at);

CREATE TABLE IF NOT EXISTS agent_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT UNIQUE NOT NULL,
  budget_usd NUMERIC(12,4) NOT NULL DEFAULT 0,
  tools JSONB NOT NULL DEFAULT '[]',
  enabled BOOLEAN NOT NULL DEFAULT true,
  approval_required BOOLEAN NOT NULL DEFAULT true,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
  agent_name TEXT NOT NULL,
  evaluator TEXT NOT NULL DEFAULT 'human',
  score NUMERIC(5,2),
  passed BOOLEAN,
  feedback TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_evaluations_agent ON agent_evaluations(agent_name, created_at DESC);

CREATE TABLE IF NOT EXISTS secret_references (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type TEXT NOT NULL,
  owner_id UUID,
  provider TEXT NOT NULL,
  reference TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_secret_references_owner ON secret_references(owner_type, owner_id, status);


-- Self-hosted user authentication and role-based access.
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'operator',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, active);


-- Client-trust and regional-growth layer.
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS fit_score NUMERIC(5,2);
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS fit_disposition TEXT NOT NULL DEFAULT 'review';
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS why_this TEXT;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS why_not JSONB NOT NULL DEFAULT '[]';
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS alternatives JSONB NOT NULL DEFAULT '[]';
CREATE INDEX IF NOT EXISTS idx_opportunities_fit ON opportunities(fit_disposition, fit_score DESC);

CREATE TABLE IF NOT EXISTS outreach_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID UNIQUE NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'normal',
  reason TEXT,
  source TEXT NOT NULL DEFAULT 'operator',
  last_contacted_at TIMESTAMPTZ,
  contact_count INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_outreach_preferences_status ON outreach_preferences(status);

CREATE TABLE IF NOT EXISTS client_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  ai_disclosure BOOLEAN NOT NULL DEFAULT true,
  data_ownership_note TEXT NOT NULL DEFAULT 'Client retains ownership of business data and deliverables, subject to the engagement agreement.',
  preferred_contact_channel TEXT NOT NULL DEFAULT 'email',
  communication_frequency TEXT NOT NULL DEFAULT 'normal',
  notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_outcomes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  outcome_type TEXT NOT NULL,
  baseline JSONB NOT NULL DEFAULT '{}',
  current_value JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'tracking',
  client_confirmed BOOLEAN NOT NULL DEFAULT false,
  notes TEXT,
  measured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_client_outcomes_project ON client_outcomes(project_id, measured_at DESC);

CREATE TABLE IF NOT EXISTS regional_playbooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_key TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pilot',
  notes TEXT,
  proven_offers JSONB NOT NULL DEFAULT '[]',
  industry_patterns JSONB NOT NULL DEFAULT '[]',
  outreach_metrics JSONB NOT NULL DEFAULT '{}',
  client_success_metrics JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_regional_playbooks_status ON regional_playbooks(status);


-- OAuth connections store metadata and a reference to the external secret manager,
-- never raw access or refresh tokens.
ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS secret_ref TEXT;
ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS scopes JSONB NOT NULL DEFAULT '[]';
ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS provider_account_id TEXT;
ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS last_health_check_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_integration_connections_secret_ref ON integration_connections(secret_ref);
\n-- Luma Control & Intelligence Core
CREATE TABLE IF NOT EXISTS evidence_claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  research_report_id UUID REFERENCES research_reports(id) ON DELETE SET NULL,
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
  claim TEXT NOT NULL,
  evidence_strength NUMERIC(5,2) NOT NULL DEFAULT 0,
  alternatives JSONB NOT NULL DEFAULT '[]',
  verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evidence_claims_opportunity ON evidence_claims(opportunity_id, verified_at DESC);

CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id UUID NOT NULL REFERENCES evidence_claims(id) ON DELETE CASCADE,
  evidence_id UUID NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
  relation TEXT NOT NULL DEFAULT 'supports',
  PRIMARY KEY (claim_id, evidence_id, relation)
);

CREATE TABLE IF NOT EXISTS agent_action_receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
  actor_type TEXT NOT NULL,
  actor_id UUID,
  action TEXT NOT NULL,
  decision TEXT NOT NULL,
  risk TEXT NOT NULL,
  reason TEXT NOT NULL,
  estimated_cost NUMERIC(12,6) NOT NULL DEFAULT 0,
  previous_hash TEXT,
  receipt_hash TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_receipts_entity ON agent_action_receipts(entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  step TEXT NOT NULL,
  state JSONB NOT NULL DEFAULT '{}',
  checkpoint_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_run ON workflow_checkpoints(workflow_run_id, created_at DESC);

CREATE TABLE IF NOT EXISTS service_blueprint_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id UUID REFERENCES services(id) ON DELETE CASCADE,
  version INT NOT NULL DEFAULT 1,
  blueprint JSONB NOT NULL DEFAULT '{}',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(service_id, version)
);

CREATE TABLE IF NOT EXISTS agent_budget_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT NOT NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  workflow_run_id UUID REFERENCES workflow_runs(id) ON DELETE SET NULL,
  agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
  amount NUMERIC(12,6) NOT NULL DEFAULT 0,
  category TEXT NOT NULL DEFAULT 'model',
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_budget_ledger_agent ON agent_budget_ledger(agent_name, occurred_at DESC);

CREATE TABLE IF NOT EXISTS client_metric_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  metric_name TEXT NOT NULL,
  value NUMERIC(14,4),
  unit TEXT,
  source TEXT,
  client_confirmed BOOLEAN NOT NULL DEFAULT false,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_client_metric_snapshots_project ON client_metric_snapshots(project_id, metric_name, captured_at DESC);

ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS checkpoint_version INT NOT NULL DEFAULT 0;
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS budget_usd NUMERIC(12,4);
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS spent_usd NUMERIC(12,6) NOT NULL DEFAULT 0;
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS waiting_for_approval BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE agent_policies ADD COLUMN IF NOT EXISTS max_tool_calls INT NOT NULL DEFAULT 100;
ALTER TABLE agent_policies ADD COLUMN IF NOT EXISTS max_tokens INT;
ALTER TABLE agent_policies ADD COLUMN IF NOT EXISTS risk_policy JSONB NOT NULL DEFAULT '{}';

-- Agent gateway, trajectory evaluation and security observability
CREATE TABLE IF NOT EXISTS agent_trajectory_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
  sequence INT NOT NULL,
  event_type TEXT NOT NULL,
  action TEXT,
  input JSONB NOT NULL DEFAULT '{}',
  output JSONB NOT NULL DEFAULT '{}',
  decision TEXT,
  latency_ms INT,
  cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_trajectory_run ON agent_trajectory_events(agent_run_id, sequence);
CREATE TABLE IF NOT EXISTS security_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_type TEXT,
  actor_id UUID,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'info',
  entity_type TEXT,
  entity_id UUID,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_security_events_created ON security_events(created_at DESC);

CREATE TABLE IF NOT EXISTS security_rate_limits (
  bucket_key TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  request_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY(bucket_key,window_start)
);
CREATE INDEX IF NOT EXISTS idx_security_rate_limits_window ON security_rate_limits(window_start);

CREATE TABLE IF NOT EXISTS blueprint_optimization_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id UUID REFERENCES services(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  source_metric TEXT NOT NULL,
  before_value NUMERIC(14,4),
  after_value NUMERIC(14,4),
  delta NUMERIC(14,4),
  recommendation JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'proposed',
  approved_by UUID,
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_blueprint_optimization_status ON blueprint_optimization_proposals(status, created_at DESC);

CREATE TABLE IF NOT EXISTS oauth_state_nonces (
  nonce TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  project_id UUID NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_oauth_state_nonces_expiry ON oauth_state_nonces(expires_at);
