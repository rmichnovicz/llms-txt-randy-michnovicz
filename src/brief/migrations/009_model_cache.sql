CREATE TABLE model_cache (
 project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 request_hash text NOT NULL,
 payload bytea NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,request_hash)
);
