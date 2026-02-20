import logging

import discord
from discord import app_commands
from discord.ext import commands

from bmt_discord_bot import Bot
from bmt_discord_bot.lib import formats


class Threads(commands.Cog):
    """Auto-subscribe to new threads in channels."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    threads_group = app_commands.Group(name="threads", description="Manage thread subscriptions")

    @threads_group.command(name="subscribe")
    @app_commands.describe(channel="The channel to subscribe to (defaults to the current channel)")
    async def subscribe(
        self, interaction: discord.Interaction, channel: discord.TextChannel | None = None
    ):
        """Subscribe to new threads in a channel."""

        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        channel = channel or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "You can only subscribe to text channels.", ephemeral=True
            )

        result = await self.bot.database.pool.execute(
            """
                INSERT INTO thread_subscriptions (user_id, channel_id, guild_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, channel_id) DO NOTHING
            """,
            interaction.user.id,
            channel.id,
            interaction.guild.id,
        )

        if result == "INSERT 0 0":
            await interaction.response.send_message(
                f"You're already subscribed to threads in {channel.mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Subscribed to new threads in {channel.mention}.", ephemeral=True
            )

    @threads_group.command(name="unsubscribe")
    @app_commands.describe(
        channel="The channel to unsubscribe from (defaults to the current channel)"
    )
    async def unsubscribe(
        self, interaction: discord.Interaction, channel: discord.TextChannel | None = None
    ):
        """Unsubscribe from new threads in a channel."""

        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        channel = channel or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "You can only unsubscribe from text channels.", ephemeral=True
            )

        result = await self.bot.database.pool.execute(
            """
                DELETE FROM thread_subscriptions
                WHERE user_id = $1 AND channel_id = $2
            """,
            interaction.user.id,
            channel.id,
        )

        if result == "DELETE 0":
            await interaction.response.send_message(
                f"You're not subscribed to threads in {channel.mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Unsubscribed from threads in {channel.mention}.", ephemeral=True
            )

    @threads_group.command(name="list")
    async def list_subscriptions(self, interaction: discord.Interaction):
        """List your thread subscriptions."""

        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        subscriptions = await self.bot.database.pool.fetch(
            """
                SELECT channel_id, created_at
                FROM thread_subscriptions
                WHERE user_id = $1 AND guild_id = $2
                ORDER BY created_at
            """,
            interaction.user.id,
            interaction.guild.id,
        )

        if not subscriptions:
            return await interaction.response.send_message(
                "You have no thread subscriptions in this server.", ephemeral=True
            )

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
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
