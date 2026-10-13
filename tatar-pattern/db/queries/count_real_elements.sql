-- First refresh physical-file availability with scripts.catalog_audit.
-- PostgreSQL cannot inspect backend filesystem. checked_at identifies the audit.
-- One human motif identity per artifact. Byte duplicates collapse across artifacts.
WITH candidates AS (
    SELECT DISTINCT v.id, v.artifact_id, v.motif_identity, v.content_sha256
    FROM approved_element_files v
    JOIN element_files f ON f.id=v.file_id
    WHERE NOT v.is_fixture AND f.file_available AND f.file_checked_at IS NOT NULL
), unique_masks AS (
    SELECT DISTINCT ON(content_sha256) * FROM candidates ORDER BY content_sha256,id
), unique_origins AS (
    SELECT DISTINCT ON(artifact_id,motif_identity) * FROM unique_masks
    ORDER BY artifact_id,motif_identity,id
)
SELECT count(*) AS real_unique_elements_with_files_and_provenance FROM unique_origins;

SELECT e.code, e.artifact_code, e.motif_identity, e.path, e.source_path, e.frame,
       e.content_sha256, f.file_available, f.file_checked_at
FROM approved_element_files e JOIN element_files f ON f.id=e.file_id
WHERE NOT e.is_fixture ORDER BY e.code;
