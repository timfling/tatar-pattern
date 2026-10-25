-- Additive guest zone. No users, fake emails or shared account.
CREATE TABLE guest_processes (
 id UUID PRIMARY KEY,
 token_hash TEXT UNIQUE NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 expires_at TIMESTAMPTZ NOT NULL,
 CHECK (expires_at > created_at AND expires_at <= created_at + interval '24 hours')
);
ALTER TABLE generations ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE generations ADD COLUMN guest_process_id UUID REFERENCES guest_processes(id);
ALTER TABLE generations ADD COLUMN guest_expires_at TIMESTAMPTZ;
ALTER TABLE generations ADD COLUMN guest_request_id UUID;
ALTER TABLE generations ADD COLUMN guest_fingerprint TEXT;
ALTER TABLE generations ADD CONSTRAINT generation_owner CHECK (
 (user_id IS NOT NULL AND guest_process_id IS NULL AND guest_expires_at IS NULL AND guest_request_id IS NULL)
 OR (user_id IS NULL AND project_id IS NULL AND guest_process_id IS NOT NULL AND guest_expires_at IS NOT NULL AND guest_request_id IS NOT NULL)
);
CREATE UNIQUE INDEX guest_request_once ON generations(guest_process_id,guest_request_id) WHERE guest_process_id IS NOT NULL;
CREATE INDEX guest_expiry ON generations(guest_expires_at) WHERE guest_process_id IS NOT NULL;
ALTER TABLE ai_jobs ADD COLUMN provider_request_id UUID NOT NULL DEFAULT gen_random_uuid();
CREATE TABLE guest_reconciliations (
 provider_request_id UUID PRIMARY KEY,
 generation_id BIGINT NOT NULL,
 provider TEXT NOT NULL,
 provider_job_id TEXT,
 submit_uncertain BOOLEAN NOT NULL,
 expires_at TIMESTAMPTZ NOT NULL,
 confirmation_ref TEXT
);
CREATE TABLE guest_budget (
 key TEXT PRIMARY KEY,
 used BIGINT NOT NULL CHECK(used>=0)
);
