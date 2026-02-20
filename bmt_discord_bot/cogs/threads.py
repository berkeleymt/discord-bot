import logging

import discord
from discord.ext import commands

from bmt_discord_bot import Bot, Context
from bmt_discord_bot.lib import formats


class Threads(commands.Cog):
    """Auto-subscribe to new threads in channels."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @commands.hybrid_group(fallback="list")
    @commands.guild_only()
    async def threads(self, ctx: Context):
        """Manage thread subscriptions."""

        subscriptions = await ctx.bot.database.pool.fetch(
            """
                SELECT channel_id, created_at
                FROM thread_subscriptions
                WHERE user_id = $1 AND guild_id = $2
                ORDER BY created_at
            """,
            ctx.author.id,
            ctx.guild.id,
        )

        if not subscriptions:
            return await ctx.send("You have no thread subscriptions in this server.")

        lines = [
            f"<#{sub['channel_id']}> — since {discord.utils.format_dt(sub['created_at'], 'R')}"
            for sub in subscriptions
        ]
        embed = discord.Embed(
            title="Thread Subscriptions",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"{formats.plural(len(subscriptions)):subscription}")
        await ctx.send(embed=embed)

    @threads.command()
    @commands.guild_only()
    async def subscribe(self, ctx: Context, channel: discord.TextChannel | None = None):
        """Subscribe to new threads in a channel."""

        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("You can only subscribe to text channels.")

        result = await ctx.bot.database.pool.execute(
            """
                INSERT INTO thread_subscriptions (user_id, channel_id, guild_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, channel_id) DO NOTHING
            """,
            ctx.author.id,
            channel.id,
            ctx.guild.id,
        )

        if result == "INSERT 0 0":
            await ctx.send(f"You're already subscribed to threads in {channel.mention}.")
        else:
            await ctx.send(f"Subscribed to new threads in {channel.mention}.")

    @threads.command()
    @commands.guild_only()
    async def unsubscribe(self, ctx: Context, channel: discord.TextChannel | None = None):
        """Unsubscribe from new threads in a channel."""

        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("You can only unsubscribe from text channels.")

        result = await ctx.bot.database.pool.execute(
            """
                DELETE FROM thread_subscriptions
                WHERE user_id = $1 AND channel_id = $2
            """,
            ctx.author.id,
            channel.id,
        )

        if result == "DELETE 0":
            await ctx.send(f"You're not subscribed to threads in {channel.mention}.")
        else:
            await ctx.send(f"Unsubscribed from threads in {channel.mention}.")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.guild is None:
            return
        if thread.parent is None:
            return
        if not isinstance(thread.parent, discord.TextChannel):
            return

        subscribers = await self.bot.database.pool.fetch(
            """
                SELECT user_id
                FROM thread_subscriptions
                WHERE channel_id = $1 AND guild_id = $2
            """,
            thread.parent.id,
            thread.guild.id,
        )

        for sub in subscribers:
            try:
                await thread.add_user(discord.Object(sub["user_id"]))
            except (discord.Forbidden, discord.HTTPException) as e:
                self.logger.warning(
                    f"Failed to add user {sub['user_id']} to thread {thread.id}: {e}"
                )


async def setup(bot):
    await bot.add_cog(Threads(bot))
