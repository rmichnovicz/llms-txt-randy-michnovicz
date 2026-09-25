CREATE TABLE discovery_frontiers (
 project_id uuid PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
 payload bytea NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now()
);
