from collections import defaultdict
from discord.ext import commands

DEFAULT_THRESHOLD = 3


class Copycat(commands.Cog):
    """Repeats a message after it's been sent multiple times in a row."""

    def __init__(self, bot):
        self.bot = bot
        self.threshold = DEFAULT_THRESHOLD
        self.history: dict[int, tuple[str, set[int]]] = defaultdict(lambda: ("", set()))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        channel_id = message.channel.id
        last_content, users = self.history[channel_id]
        if message.content == last_content:
            users.add(message.author.id)
        else:
            last_content = message.content
            users = {message.author.id}
        self.history[channel_id] = (last_content, users)
        if len(users) >= self.threshold:
            await message.channel.send(last_content)
            self.history[channel_id] = ("", set())

    @commands.hybrid_command()
    @commands.has_permissions(manage_guild=True)
    async def copycat(self, ctx, threshold: int = DEFAULT_THRESHOLD):
        """Set how many repeated messages trigger the bot to copy it."""
        if threshold < 2:
            await ctx.send("Threshold must be at least 2.", ephemeral=True)
            return
        self.threshold = threshold
        await ctx.send(f"Copycat threshold set to **{threshold}**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Copycat(bot))
