-- Public release is an explicit scope decision, independent of cultural verification.
CREATE TABLE catalog_releases (
 manifest_sha256 TEXT PRIMARY KEY CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
 decision JSONB NOT NULL,
 snapshot_sha256 TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE elements ADD COLUMN public_release_sha256 TEXT REFERENCES catalog_releases(manifest_sha256);
CREATE OR REPLACE VIEW approved_element_files AS
SELECT e.id,e.code,e.name_ru,e.motif_class,e.motif_identity,e.is_fixture,
       e.artifact_id,a.code AS artifact_code,s.id AS source_id,
       f.id AS file_id,f.path,f.content_sha256,af.path AS source_path,af.frame,
       af.content_sha256 AS source_sha256,e.provenance,f.quality_acceptance,
       e.local_use_approved,
       (r.decision->>'approved'='true' AND r.decision->>'scope'='public_flat_catalog') AS public_use_approved
FROM elements e
JOIN artifacts a ON a.id=e.artifact_id
JOIN sources s ON s.id=a.source_id AND s.id=e.source_id
JOIN element_files f ON f.element_id=e.id
JOIN artifact_files af ON af.id=f.source_file_id AND af.artifact_id=a.id
LEFT JOIN catalog_releases r ON r.manifest_sha256=e.public_release_sha256
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
