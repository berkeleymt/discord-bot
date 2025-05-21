import logging
import discord
from discord.ext import commands

from .database import Database


class Context(commands.Context["Bot"]):
    pass


class Bot(commands.Bot):
    COGS = [
        "core",
        "math",
        "reminders",
    ]

    def __init__(self, database: Database):
        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False)
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            allowed_mentions=allowed_mentions,
            intents=intents,
            command_prefix="?",
        )

        self.database = database
        self.logger = logging.getLogger(__name__)

    async def setup_hook(self):
        await self.load_extension("jishaku")

        for cog in self.COGS:
            self.logger.info(f"Loading cog {cog}...")
            await self.load_extension(f"{__name__}.cogs.{cog}")

    def get_context(self, *args, **kwargs):
        return super().get_context(cls=Context, *args, **kwargs)
