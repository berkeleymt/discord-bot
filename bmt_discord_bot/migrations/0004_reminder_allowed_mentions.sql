ALTER TABLE reminders
    ADD COLUMN mention_everyone BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN mention_role_ids BIGINT[] NOT NULL DEFAULT '{}';
