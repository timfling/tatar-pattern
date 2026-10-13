ALTER TABLE users ADD COLUMN profile jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE generations ADD COLUMN deleted_at timestamptz;
CREATE INDEX generations_trash_idx ON generations(user_id,deleted_at) WHERE deleted_at IS NOT NULL;
