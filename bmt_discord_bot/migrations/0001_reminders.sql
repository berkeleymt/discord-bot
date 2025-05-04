CREATE TABLE reminders (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL,
    event TEXT,
    guild_id BIGINT,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    is_failed BOOLEAN NOT NULL DEFAULT FALSE
);
