CREATE TABLE sites (id uuid PRIMARY KEY, url text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE projects ADD COLUMN site_id uuid REFERENCES sites(id) ON DELETE CASCADE;
ALTER TABLE projects ADD COLUMN guide_path text NOT NULL DEFAULT '/';
ALTER TABLE projects ADD COLUMN guide_name text NOT NULL DEFAULT 'Site overview';
ALTER TABLE projects ADD COLUMN guide_purpose text NOT NULL DEFAULT '';
INSERT INTO sites(id,url) SELECT id,substring(site_url from '^https?://[^/]+') || '/' FROM projects;
UPDATE projects SET site_id=id, guide_path=coalesce(nullif(substring(site_url from '^https?://[^/]+(.*)$'),''),'/');
UPDATE projects SET guide_path=regexp_replace(guide_path, '[?#].*$', '');
UPDATE projects SET guide_path=CASE
 WHEN split_part(regexp_replace(guide_path, '^.*/', ''), '.', 2) <> ''
 THEN regexp_replace(guide_path, '[^/]*$', '')
 ELSE rtrim(guide_path, '/') || '/' END;
-- Existing projects have deferred snapshot/document foreign keys. Flush their
-- update checks before altering the populated table in this same transaction.
SET CONSTRAINTS ALL IMMEDIATE;
ALTER TABLE projects ALTER COLUMN site_id SET NOT NULL;
SET CONSTRAINTS ALL DEFERRED;
CREATE UNIQUE INDEX guide_scope ON projects(site_id,guide_path);
CREATE TABLE page_cache (
 site_id uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
 url text NOT NULL, etag text, last_modified text, source jsonb NOT NULL,
 links jsonb NOT NULL, extraction_version text NOT NULL,
 checked_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(site_id,url)
);
