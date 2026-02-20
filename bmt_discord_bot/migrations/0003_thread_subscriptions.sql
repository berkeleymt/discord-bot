CREATE TYPE subscription_scope AS ENUM ('server', 'category', 'channel');

CREATE TABLE thread_subscriptions (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    scope_type subscription_scope NOT NULL,
    scope_id BIGINT NOT NULL,
    excluded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW () AT TIME ZONE 'UTC'),
    UNIQUE (user_id, scope_type, scope_id)
);
