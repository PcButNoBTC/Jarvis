import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def ensure_delivery_schema():
    ddl = """
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
    ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,2);
    ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS rationale TEXT;
    ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS factors JSONB NOT NULL DEFAULT '[]';
    CREATE INDEX IF NOT EXISTS idx_opportunities_business_service ON opportunities(business_id, service_id);
    CREATE TABLE IF NOT EXISTS evidence_items (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
      research_report_id UUID REFERENCES research_reports(id) ON DELETE CASCADE, opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
      evidence_type TEXT NOT NULL, observation TEXT NOT NULL, source_url TEXT, source_locator TEXT,
      confidence NUMERIC(5,2), observed_at TIMESTAMPTZ NOT NULL DEFAULT now(), metadata JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_evidence_business_observed ON evidence_items(business_id, observed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_evidence_opportunity ON evidence_items(opportunity_id);
    CREATE TABLE IF NOT EXISTS project_milestones (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', sequence INT NOT NULL DEFAULT 0,
      due_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_project_milestones_project ON project_milestones(project_id, sequence);
    CREATE TABLE IF NOT EXISTS revenue_transactions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
      project_id UUID REFERENCES projects(id) ON DELETE SET NULL, proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL,
      transaction_type TEXT NOT NULL DEFAULT 'sale', status TEXT NOT NULL DEFAULT 'pending',
      amount NUMERIC(12,2) NOT NULL DEFAULT 0, recurring_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT 'USD', external_id TEXT, occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(), metadata JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_revenue_transactions_occurred ON revenue_transactions(occurred_at DESC);
    CREATE TABLE IF NOT EXISTS cost_records (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
      agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL, category TEXT NOT NULL,
      amount NUMERIC(12,6) NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'USD',
      description TEXT, occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(), metadata JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_cost_records_occurred ON cost_records(occurred_at DESC);
    CREATE TABLE IF NOT EXISTS workflow_runs (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), workflow_name TEXT NOT NULL, trigger_type TEXT NOT NULL,
      entity_type TEXT, entity_id UUID, status TEXT NOT NULL DEFAULT 'pending', current_step TEXT,
      attempts INT NOT NULL DEFAULT 0, input JSONB NOT NULL DEFAULT '{}', output JSONB NOT NULL DEFAULT '{}',
      error TEXT, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_workflow_runs_queue ON workflow_runs(status, created_at);
    CREATE TABLE IF NOT EXISTS integration_connections (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
      project_id UUID REFERENCES projects(id) ON DELETE CASCADE, provider TEXT NOT NULL, category TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', capabilities JSONB NOT NULL DEFAULT '[]', secret_ref TEXT,
      metadata JSONB NOT NULL DEFAULT '{}', connected_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_integrations_project ON integration_connections(project_id, status);
    CREATE TABLE IF NOT EXISTS audit_log (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), actor_type TEXT NOT NULL, actor_id UUID, action TEXT NOT NULL,
      entity_type TEXT, entity_id UUID, metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id, created_at DESC);
    CREATE TABLE IF NOT EXISTS billing_records (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
      project_id UUID REFERENCES projects(id) ON DELETE SET NULL, proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL,
      external_invoice_id TEXT, status TEXT NOT NULL DEFAULT 'draft', amount NUMERIC(12,2) NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT 'USD', due_at TIMESTAMPTZ, paid_at TIMESTAMPTZ, metadata JSONB NOT NULL DEFAULT '{}',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_billing_status_due ON billing_records(status, due_at);
    CREATE TABLE IF NOT EXISTS project_dependencies (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      depends_on_project_id UUID REFERENCES projects(id) ON DELETE SET NULL, dependency_type TEXT NOT NULL DEFAULT 'external',
      name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', required BOOLEAN NOT NULL DEFAULT true,
      metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_project_dependencies_project ON project_dependencies(project_id, status);
    CREATE TABLE IF NOT EXISTS approval_history (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
      entity_type TEXT NOT NULL, entity_id UUID, approval_type TEXT NOT NULL, decision TEXT NOT NULL,
      actor_type TEXT NOT NULL DEFAULT 'human', actor_id UUID, notes TEXT, metadata JSONB NOT NULL DEFAULT '{}',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_approval_history_entity ON approval_history(entity_type, entity_id, created_at DESC);
    CREATE TABLE IF NOT EXISTS revision_requests (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      implementation_id UUID REFERENCES implementations(id) ON DELETE SET NULL, requested_by TEXT NOT NULL DEFAULT 'client',
      status TEXT NOT NULL DEFAULT 'requested', summary TEXT NOT NULL, details TEXT, priority TEXT NOT NULL DEFAULT 'normal',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), resolved_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_revision_requests_project ON revision_requests(project_id, status, created_at DESC);
    CREATE TABLE IF NOT EXISTS recurring_revenue (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
      project_id UUID REFERENCES projects(id) ON DELETE SET NULL, billing_record_id UUID REFERENCES billing_records(id) ON DELETE SET NULL,
      amount NUMERIC(12,2) NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'USD', interval TEXT NOT NULL DEFAULT 'month',
      status TEXT NOT NULL DEFAULT 'active', started_at TIMESTAMPTZ NOT NULL DEFAULT now(), next_billing_at TIMESTAMPTZ,
      cancelled_at TIMESTAMPTZ, metadata JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_recurring_revenue_status_next ON recurring_revenue(status, next_billing_at);
    CREATE TABLE IF NOT EXISTS automation_schedules (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), workflow_name TEXT NOT NULL, cron_expression TEXT NOT NULL,
      enabled BOOLEAN NOT NULL DEFAULT true, input JSONB NOT NULL DEFAULT '{}', last_run_at TIMESTAMPTZ,
      next_run_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_automation_schedules_due ON automation_schedules(enabled, next_run_at);
    CREATE TABLE IF NOT EXISTS agent_policies (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), agent_name TEXT UNIQUE NOT NULL, budget_usd NUMERIC(12,4) NOT NULL DEFAULT 0,
      tools JSONB NOT NULL DEFAULT '[]', enabled BOOLEAN NOT NULL DEFAULT true, approval_required BOOLEAN NOT NULL DEFAULT true,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS agent_evaluations (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
      agent_name TEXT NOT NULL, evaluator TEXT NOT NULL DEFAULT 'human', score NUMERIC(5,2), passed BOOLEAN,
      feedback TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS secret_references (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_type TEXT NOT NULL, owner_id UUID, provider TEXT NOT NULL,
      reference TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'active', metadata JSONB NOT NULL DEFAULT '{}',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), revoked_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_secret_references_owner ON secret_references(owner_type, owner_id, status);
    CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'operator', active BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_login_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, active);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
