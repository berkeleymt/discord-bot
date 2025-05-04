import discord
from discord.ext import commands

from .database import Database

COGS = [
    # Essential
    "core",
    "help",
    "database",
    "reaction_roles",
    "reminders",
]


class Bot(commands.Bot):
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

    async def setup_hook(self):
        pass
