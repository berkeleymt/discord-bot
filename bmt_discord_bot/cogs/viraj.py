import re
import random
from discord.ext import commands

PATTERN = re.compile(
    r"\b(\w*)(ize|ization|izations|izing|ized|izes|izer|izers)\b",
    re.IGNORECASE,
)
IGNORED_CATEGORY_IDS = [1031955833371758754]


class Viraj(commands.Cog):
    """For correcting Viraj."""

    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return ctx.guild.id == 786701065856221205

    def _correct_text(self, match):
        prefix, suffix = match.groups()
        return f"*{prefix}{suffix.replace('iz', 'is')}"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.channel.category_id in IGNORED_CATEGORY_IDS:
            return
        if "invigilator" in message.content.casefold() and random.random() < 0.05:
            await message.channel.send("*proctor")
        for match in PATTERN.finditer(message.content):
            await message.channel.send(self._correct_text(match))


async def setup(bot):
    await bot.add_cog(Viraj(bot))
