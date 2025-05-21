import logging
import asyncpg
from pathlib import Path


class Migration:
    MIGRATIONS_DIR = Path(__file__).parent / "migrations"

    def __init__(self, *, name: str, up: str, down: str):
        self.name = name
        self.up = up
        self.down = down

    @classmethod
    def from_files(cls, name: str):
        with open(cls.MIGRATIONS_DIR / f"{name}.sql") as f:
            up = f.read()
        with open(cls.MIGRATIONS_DIR / f"{name}_down.sql") as f:
            down = f.read()
        return cls(name=name, up=up, down=down)


class Database:
    MIGRATIONS = [
        Migration.from_files("0001_reminders"),
    ]

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.logger = logging.getLogger(__name__)

    async def migrate(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                    name TEXT,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT (NOW () AT TIME ZONE 'UTC')
                )
            """)
            migrations = await conn.fetch("SELECT * FROM migrations")
            needed_migrations = iter(self.MIGRATIONS)

            for migration in migrations:
                needed_migration = next(needed_migrations)
                if migration["name"] != needed_migration.name:
                    raise ValueError(f"Unexpected migration in database: {migration['name']}")

            for needed_migration in needed_migrations:
                self.logger.info(f"Applying {needed_migration.name}...")
                async with conn.transaction():
                    await conn.execute(needed_migration.up)
                    await conn.execute(
                        "INSERT INTO migrations (name) VALUES ($1)",
                        needed_migration.name,
                    )
