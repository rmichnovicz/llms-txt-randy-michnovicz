CREATE TABLE projects (
    id uuid PRIMARY KEY,
    site_url text NOT NULL,
    management_token_hash text NOT NULL,
    revision bigint NOT NULL DEFAULT 0,
    latest_snapshot_id uuid,
    monitor_enabled boolean NOT NULL DEFAULT false,
    next_check_at timestamptz NOT NULL DEFAULT now() + interval '1 day',
    last_checked_at timestamptz,
    last_check_status text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('initial_crawl', 'refresh')),
    idempotency_key text NOT NULL UNIQUE,
    expected_revision bigint NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'superseded')),
    attempt integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_token uuid,
    lease_expires_at timestamptz,
    error text,
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (id, project_id)
);
CREATE UNIQUE INDEX one_active_job_per_project ON jobs(project_id) WHERE status IN ('pending', 'running');
CREATE INDEX job_dispatch ON jobs(available_at, created_at) WHERE status IN ('pending', 'running');
CREATE INDEX monitor_due ON projects(next_check_at) WHERE monitor_enabled;

CREATE TABLE crawl_snapshots (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id uuid NOT NULL,
    attempt integer NOT NULL,
    status text NOT NULL CHECK (status IN ('complete', 'partial', 'failed')),
    extraction_version text NOT NULL,
    sources jsonb NOT NULL,
    page_state jsonb NOT NULL,
    observations jsonb NOT NULL,
    changes jsonb NOT NULL,
    coverage jsonb NOT NULL,
    warnings jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, project_id),
    UNIQUE (job_id, attempt),
    FOREIGN KEY (job_id, project_id) REFERENCES jobs(id, project_id)
);
ALTER TABLE projects ADD CONSTRAINT latest_snapshot_ownership
    FOREIGN KEY (latest_snapshot_id, id) REFERENCES crawl_snapshots(id, project_id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX snapshot_history ON crawl_snapshots(project_id, created_at DESC);
