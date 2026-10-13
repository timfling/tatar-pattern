-- Visual acceptance and local use are separate from expert provenance/rights.
ALTER TABLE elements ADD COLUMN provenance JSONB NOT NULL DEFAULT '{}';
ALTER TABLE elements ADD COLUMN local_use_approved BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE element_files ADD COLUMN quality_acceptance JSONB;
ALTER TABLE artifact_files ADD COLUMN content_sha256 TEXT;
CREATE OR REPLACE VIEW approved_element_files AS
SELECT e.id,e.code,e.name_ru,e.motif_class,e.motif_identity,e.is_fixture,
       e.artifact_id,a.code AS artifact_code,s.id AS source_id,
       f.id AS file_id,f.path,f.content_sha256,af.path AS source_path,af.frame,
       af.content_sha256 AS source_sha256,e.provenance,f.quality_acceptance,
       e.local_use_approved
FROM elements e
JOIN artifacts a ON a.id=e.artifact_id
JOIN sources s ON s.id=a.source_id AND s.id=e.source_id
JOIN element_files f ON f.element_id=e.id
JOIN artifact_files af ON af.id=f.source_file_id AND af.artifact_id=a.id
WHERE length(trim(e.motif_identity))>0
 AND f.file_type='flat_png' AND f.content_sha256 ~ '^[0-9a-f]{64}$'
 AND af.file_type IN ('raw','proxy') AND length(trim(af.frame))>0
 AND (
   (e.status='верифицировано' AND length(trim(e.verified_by))>0
    AND a.review_status='проверено' AND a.origin='татарское'
    AND a.usage_scope='рид_и_обучение'
    AND a.rights IN ('некоммерческое_mvp','разрешение_получено','публичное_место')
    AND length(trim(s.legal_basis))>0
    AND length(trim(f.reviewed_by))>0 AND f.reviewed_at IS NOT NULL)
   OR
   (e.local_use_approved AND e.status='отрисовано'
    AND e.provenance->>'evidenceStatus'='documented_unverified'
    AND e.provenance->>'externalTransferAllowed'='false'
    AND e.provenance->>'trainingAllowed'='false'
    AND length(trim(e.provenance->>'manifestSha256'))=64
    AND af.content_sha256 ~ '^[0-9a-f]{64}$'
    AND f.quality_acceptance->>'decision'='accepted_current_quality'
    AND f.quality_acceptance->>'acceptedBy'='project_owner'
    AND f.quality_acceptance->>'acceptedOn'='2026-10-08'
    AND f.quality_acceptance->>'sha256'=f.content_sha256)
 );
COMMENT ON COLUMN elements.local_use_approved IS 'Local constructor authorization only; not expert verification, public distribution, or external training permission';
