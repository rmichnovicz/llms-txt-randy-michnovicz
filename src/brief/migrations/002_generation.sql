ALTER TABLE jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_kind_check CHECK (kind IN ('initial_crawl', 'refresh', 'generate'));
ALTER TABLE jobs ADD COLUMN snapshot_id uuid;
ALTER TABLE jobs ADD CONSTRAINT job_snapshot_ownership
    FOREIGN KEY (snapshot_id, project_id) REFERENCES crawl_snapshots(id, project_id);
ALTER TABLE jobs ADD CONSTRAINT generation_requires_snapshot CHECK (kind <> 'generate' OR snapshot_id IS NOT NULL);

CREATE TABLE document_versions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id uuid NOT NULL UNIQUE,
    snapshot_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('draft', 'proposal')),
    generation_input jsonb NOT NULL,
    structured_result jsonb NOT NULL,
    markdown text NOT NULL,
    model_metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, project_id),
    FOREIGN KEY (job_id, project_id) REFERENCES jobs(id, project_id),
    FOREIGN KEY (snapshot_id, project_id) REFERENCES crawl_snapshots(id, project_id)
);
ALTER TABLE projects ADD COLUMN draft_version_id uuid;
ALTER TABLE projects ADD COLUMN proposal_version_id uuid;
ALTER TABLE projects ADD CONSTRAINT draft_ownership
    FOREIGN KEY (draft_version_id, id) REFERENCES document_versions(id, project_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE projects ADD CONSTRAINT proposal_ownership
    FOREIGN KEY (proposal_version_id, id) REFERENCES document_versions(id, project_id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX document_history ON document_versions(project_id, created_at DESC);
