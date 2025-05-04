import logging
import discord
from discord.ext import commands

from .database import Database


class Bot(commands.Bot):
    COGS = [
        # Essential
        "core",
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
        for cog in self.COGS:
            self.logger.info(f"Loading cog {cog}...")
            await self.load_extension(f"{__name__}.cogs.{cog}")
