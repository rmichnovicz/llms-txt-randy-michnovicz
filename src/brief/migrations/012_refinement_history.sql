ALTER TABLE document_versions ADD COLUMN refined_from_version_id uuid;
ALTER TABLE document_versions ADD CONSTRAINT refinement_baseline_ownership
    FOREIGN KEY (refined_from_version_id, project_id) REFERENCES document_versions(id, project_id);
