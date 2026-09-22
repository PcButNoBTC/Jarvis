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
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
