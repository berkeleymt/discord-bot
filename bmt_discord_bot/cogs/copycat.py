from collections import defaultdict
from discord.ext import commands

from bmt_discord_bot import Bot

DEFAULT_THRESHOLD = 3


class Copycat(commands.Cog):
    """Repeats a message after it's been sent multiple times in a row."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.thresholds: dict[int, int] = {}
        self.history: dict[int, tuple[str, set[int]]] = defaultdict(lambda: ("", set()))

    async def cog_load(self):
        rows = await self.bot.database.pool.fetch("SELECT guild_id, threshold FROM copycat_settings")
        for row in rows:
            self.thresholds[row["guild_id"]] = row["threshold"]

    def get_threshold(self, guild_id: int) -> int:
        return self.thresholds.get(guild_id, DEFAULT_THRESHOLD)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        channel_id = message.channel.id
        last_content, users = self.history[channel_id]
        if message.content == last_content:
            users.add(message.author.id)
        else:
            last_content = message.content
            users = {message.author.id}
        self.history[channel_id] = (last_content, users)
        if len(users) >= self.get_threshold(message.guild.id):
            await message.channel.send(last_content)
            self.history[channel_id] = ("", set())

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def copycat(self, ctx, threshold: int = DEFAULT_THRESHOLD):
        """Set how many repeated messages trigger the bot to copy it."""
        if threshold < 2:
            await ctx.send("Threshold must be at least 2.", ephemeral=True)
            return
        await self.bot.database.pool.execute(
            """
            INSERT INTO copycat_settings (guild_id, threshold) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET threshold = $2
            """,
            ctx.guild.id,
            threshold,
        )
        self.thresholds[ctx.guild.id] = threshold
        await ctx.send(f"Copycat threshold set to **{threshold}**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Copycat(bot))
