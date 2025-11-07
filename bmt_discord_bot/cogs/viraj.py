import re
import random
import discord
from discord.ext import commands

PATTERN = re.compile(
    r"\b(\w*)(ise|isation|isations|ising|ised|ises|iser|isers)\b",
    re.IGNORECASE,
)

IGNORED_CATEGORY_IDS = [
    1031955833371758754,
]


class Viraj(commands.Cog):
    """For correcting Viraj."""

    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return ctx.guild.id == 786701065856221205

    def _correct_text(self, match):
        prefix, suffix = match.groups()
        return f"*{prefix}{suffix.replace('is', 'iz')}"

    def _should_ignore_channel(self, channel):
        """Check if a channel should be ignored based on its category."""
        category_id = getattr(channel, "category_id", None)
        if category_id in IGNORED_CATEGORY_IDS:
            return True

        parent = getattr(channel, "parent", None)
        if parent and parent is not channel:
            return self._should_ignore_channel(parent)

        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if self._should_ignore_channel(message.channel):
            return

        if "proctor" in message.content.casefold() and random.random() < 0.05:
            await message.channel.send("*invigilator")
        for match in PATTERN.finditer(message.content):
            await message.channel.send(self._correct_text(match))


async def setup(bot):
    await bot.add_cog(Viraj(bot))
