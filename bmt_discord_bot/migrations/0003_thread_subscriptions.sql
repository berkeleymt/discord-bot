CREATE TABLE thread_subscriptions (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW () AT TIME ZONE 'UTC'),
    UNIQUE (user_id, channel_id)
);
