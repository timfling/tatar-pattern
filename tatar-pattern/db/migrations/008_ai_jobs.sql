-- Durable local queue; no speculative cloud API or automatic GPU resubmission.
CREATE TABLE ai_jobs (
 generation_id BIGINT PRIMARY KEY REFERENCES generations(id),
 state TEXT NOT NULL CHECK(state IN ('queued','submitting','polling','done','failed')),
 provider TEXT NOT NULL,
 provider_job_id TEXT,
 model_version TEXT NOT NULL,
 payload JSONB NOT NULL,
 deadline TIMESTAMPTZ NOT NULL,
 next_poll_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 poll_errors INTEGER NOT NULL DEFAULT 0,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ai_jobs_ready ON ai_jobs(next_poll_at) WHERE state IN ('queued','polling');
