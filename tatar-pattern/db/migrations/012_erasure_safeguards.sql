-- Infrastructure only. No new retention periods or legal grounds are asserted.
ALTER TABLE users ADD COLUMN access_blocked BOOLEAN NOT NULL DEFAULT false;
CREATE TABLE erasure_tombstones (
 generation_id BIGINT PRIMARY KEY,
 user_id BIGINT,
 reason TEXT NOT NULL CHECK(reason IN ('trash_expired','account_closure','restore_replay')),
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE storage_deletions (
 path TEXT PRIMARY KEY,
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','done')),
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- No payload, credentials, prompts or images. Provider IDs are kept only for reconciliation.
CREATE TABLE provider_deletions (
 generation_id BIGINT PRIMARY KEY,
 provider TEXT NOT NULL,
 provider_job_id TEXT,
 submit_uncertain BOOLEAN NOT NULL,
 state TEXT NOT NULL DEFAULT 'manual_required' CHECK(state IN ('manual_required','confirmed')),
 confirmation_ref TEXT,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Operator workflow preparation; no automatic closure or unapproved calendar.
CREATE TABLE privacy_operations (
 operation_ref TEXT PRIMARY KEY,
 user_id BIGINT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('blocked','local_erased','provider_pending')),
 decision_ref TEXT NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
