-- Additive migration. No deletion or replacement of catalog/user records.
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
ALTER TABLE sources ADD COLUMN import_key TEXT UNIQUE;
ALTER TABLE artifacts ADD COLUMN reviewed_by TEXT;
ALTER TABLE artifacts ADD COLUMN reviewed_at TIMESTAMPTZ;
ALTER TABLE elements ADD COLUMN is_fixture BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE elements ADD COLUMN motif_identity TEXT;
-- Explicitly identify the five historical demonstration seeds, preserving all data.
UPDATE elements SET is_fixture = true WHERE code IN
 ('TP-TULIP-001','TP-BUD-001','TP-PALMETTE-001','TP-VINE-001','TP-BORDER-001');
CREATE UNIQUE INDEX idx_elements_real_identity ON elements(artifact_id, motif_identity)
 WHERE NOT is_fixture AND motif_identity IS NOT NULL;
ALTER TABLE element_files ADD COLUMN content_sha256 TEXT;
ALTER TABLE element_files ADD COLUMN reviewed_by TEXT;
ALTER TABLE element_files ADD COLUMN reviewed_at TIMESTAMPTZ;
ALTER TABLE element_files ADD COLUMN source_file_id BIGINT REFERENCES artifact_files(id);
ALTER TABLE element_files ADD COLUMN file_available BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE element_files ADD COLUMN file_checked_at TIMESTAMPTZ;
ALTER TABLE generations ADD COLUMN error JSONB;
CREATE TABLE catalog_imports (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_sha256 TEXT NOT NULL,
    reviewed_by TEXT NOT NULL,
    report JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE VIEW approved_element_files AS
SELECT e.id, e.code, e.name_ru, e.motif_class, e.motif_identity, e.is_fixture,
       e.artifact_id, a.code AS artifact_code, s.id AS source_id,
       f.id AS file_id, f.path, f.content_sha256,
       af.path AS source_path, af.frame
FROM elements e
JOIN artifacts a ON a.id=e.artifact_id
JOIN sources s ON s.id=a.source_id AND s.id=e.source_id
JOIN element_files f ON f.element_id=e.id
JOIN artifact_files af ON af.id=f.source_file_id AND af.artifact_id=a.id
WHERE e.status='верифицировано' AND length(trim(e.verified_by))>0
  AND length(trim(e.motif_identity))>0
  AND a.review_status='проверено' AND a.origin='татарское'
  AND a.usage_scope='рид_и_обучение'
  AND a.rights IN ('некоммерческое_mvp','разрешение_получено','публичное_место')
  AND length(trim(s.legal_basis))>0
  AND f.file_type='flat_png' AND f.content_sha256 ~ '^[0-9a-f]{64}$'
  AND length(trim(f.reviewed_by))>0 AND f.reviewed_at IS NOT NULL
  AND af.file_type IN ('raw','proxy') AND length(trim(af.frame))>0;
