import asyncio
import asyncpg
import discord
import os

from .database import Database
from . import Bot


async def main():
    discord.utils.setup_logging()

    DB_URI = os.environ["DB_URI"]
    BOT_TOKEN = os.environ["BOT_TOKEN"]

    async with asyncpg.create_pool(DB_URI, command_timeout=60) as pool:
        database = Database(pool)
        await database.migrate()

        async with Bot(database) as bot:
            await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
