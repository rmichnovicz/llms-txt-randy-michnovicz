ALTER TABLE projects ADD COLUMN decisions_revision bigint NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN generation_input jsonb;
ALTER TABLE jobs ADD COLUMN replace_draft boolean NOT NULL DEFAULT false;
ALTER TABLE document_versions ALTER COLUMN job_id DROP NOT NULL;
ALTER TABLE document_versions ADD COLUMN manually_edited boolean NOT NULL DEFAULT false;
ALTER TABLE document_versions ADD COLUMN decisions_revision bigint NOT NULL DEFAULT 0;
CREATE TABLE decisions (
    id text PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('preference', 'fact')),
    statement text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX decisions_project ON decisions(project_id);
CREATE TABLE decision_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    decision jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE questions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    topic text NOT NULL,
    data jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'answered', 'dismissed')),
    decision_id text REFERENCES decisions(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (snapshot_id, project_id) REFERENCES crawl_snapshots(id, project_id)
);
CREATE UNIQUE INDEX pending_question_topic ON questions(project_id, topic) WHERE status = 'pending';
