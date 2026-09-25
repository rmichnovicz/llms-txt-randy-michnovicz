ALTER TABLE projects ADD COLUMN published_version_id uuid;
ALTER TABLE projects ADD COLUMN published_at timestamptz;
ALTER TABLE projects ADD COLUMN publication_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE;
ALTER TABLE projects ADD COLUMN existing_guide_check jsonb;
ALTER TABLE projects ADD CONSTRAINT publication_ownership
    FOREIGN KEY (published_version_id, id) REFERENCES document_versions(id, project_id);
