ALTER TABLE decisions ADD COLUMN evidence_basis jsonb NOT NULL DEFAULT '[]';
ALTER TABLE decisions ADD COLUMN basis_snapshot_id uuid;
ALTER TABLE decisions ADD COLUMN needs_review boolean NOT NULL DEFAULT false;
ALTER TABLE decisions ADD CONSTRAINT decision_basis_ownership
    FOREIGN KEY (basis_snapshot_id, project_id) REFERENCES crawl_snapshots(id, project_id);
-- Legacy decisions have no claim-level provenance. Seed a conservative current
-- source baseline for facts and question answers, leaving editorial preferences alone.
UPDATE decisions d SET evidence_basis = s.sources, basis_snapshot_id = s.id
FROM projects p JOIN crawl_snapshots s ON s.id = p.latest_snapshot_id
WHERE d.project_id = p.id AND (d.kind = 'fact' OR EXISTS
    (SELECT 1 FROM questions q WHERE q.decision_id = d.id));
