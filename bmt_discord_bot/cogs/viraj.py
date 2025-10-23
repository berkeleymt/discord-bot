import re
import random
from discord.ext import commands

PATTERN = re.compile(
    r"\b(\w*)(ise|isation|isations|ising|ised|ises|iser|isers)\b",
    re.IGNORECASE,
)


class Viraj(commands.Cog):
    """For correcting Viraj."""

    def __init__(self, bot):
        self.bot = bot
        
    def cog_check(self, ctx):
        return ctx.guild.id == 786701065856221205

    def _correct_text(self, match):
        prefix, suffix = match.groups()
        return f"*{prefix}{suffix.replace('is', 'iz')}"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if "proctor" in message.content.casefold() and random.random() < 0.05: 
            await message.channel.send("*invigilator")
        for match in PATTERN.finditer(message.content):
            await message.channel.send(self._correct_text(match))


async def setup(bot):
    await bot.add_cog(Viraj(bot))
