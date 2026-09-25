ALTER TABLE jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_kind_check CHECK (kind IN ('initial_crawl','refresh','generate','evaluate'));
CREATE TABLE guide_test_suites (
 id uuid PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 snapshot_id uuid NOT NULL,
 sources jsonb NOT NULL,
 guides jsonb NOT NULL,
 questions jsonb NOT NULL,
 writer_metadata jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,project_id),
 FOREIGN KEY(snapshot_id,project_id) REFERENCES crawl_snapshots(id,project_id)
);
CREATE TABLE guide_test_runs (
 id uuid PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 suite_id uuid NOT NULL,
 version_id uuid NOT NULL,
 job_id uuid NOT NULL UNIQUE,
 reader_model text NOT NULL,
 report jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(suite_id,project_id) REFERENCES guide_test_suites(id,project_id),
 FOREIGN KEY(version_id,project_id) REFERENCES document_versions(id,project_id),
 FOREIGN KEY(job_id,project_id) REFERENCES jobs(id,project_id)
);
