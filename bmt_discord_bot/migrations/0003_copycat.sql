CREATE TABLE copycat_settings (
    guild_id BIGINT PRIMARY KEY,
    threshold INT NOT NULL DEFAULT 3
);
