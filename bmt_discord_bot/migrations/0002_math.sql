CREATE TYPE math_renderer AS ENUM ('tex', 'typst');

CREATE TABLE math_settings (
    user_id BIGINT PRIMARY KEY,
    default_renderer math_renderer
);
