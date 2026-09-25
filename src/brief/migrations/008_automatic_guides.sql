ALTER TABLE projects ADD COLUMN auto_guides_planned boolean NOT NULL DEFAULT false;
ALTER TABLE projects ADD COLUMN auto_reason text;
ALTER TABLE projects ADD COLUMN auto_cancelled boolean NOT NULL DEFAULT false;
-- Existing workspaces retain their structure until their next explicit generation.
