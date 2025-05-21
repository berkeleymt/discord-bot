import asyncio
import textwrap
import discord
from typing import Annotated, NamedTuple
from asyncpg import Record
from discord.ext import commands
from discord.ext.menus.views import ViewMenuPages

from bmt_discord_bot import Bot, Context
from bmt_discord_bot.lib import formats, time
from bmt_discord_bot.lib.pagination import EmbedFieldsPageSource


class DispatchedReminder(NamedTuple):
    reminder: Record
    task: asyncio.Task


class Reminders(commands.Cog):
    """Reminders to remind you of things."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self._current: DispatchedReminder | None = None
        self.bot.loop.create_task(self.update_current())

    @commands.hybrid_group(aliases=("remind", "remindme"), usage="<when> [event]", fallback="set")
    async def reminder(
        self,
        ctx: Context,
        *,
        time_and_content: Annotated[
            time.FriendlyTimeResult,
            time.UserFriendlyTime(commands.clean_content, default="\u2026"),
        ],
    ):
        """Sets a reminder for a date or duration of time, e.g.:

        • in two hours write some problems
        • next thursday release solutions
        • 5min send meeting announcement

        Times are parsed as US Pacific Time.
        """

        reminder = await ctx.bot.database.pool.fetchrow(
            """
                INSERT INTO reminders (user_id, event, guild_id, channel_id, message_id, created_at, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, user_id, event, channel_id, message_id, created_at, expires_at
            """,
            ctx.author.id,
            time_and_content.arg,
            ctx.guild and ctx.guild.id,
            ctx.channel.id,
            ctx.message.id,
            ctx.message.created_at,
            time_and_content.dt,
        )
        self.bot.loop.create_task(self.update_current(reminder))
        await ctx.send(
            f"Alright, I'll remind you in **{time.human_timedelta(time_and_content.dt, source=ctx.message.created_at)}**: {time_and_content.arg}"
        )

    @reminder.command()
    @commands.guild_only()
    async def list(self, ctx: Context):
        """Lists future reminders set by you."""

        reminders = await ctx.bot.database.pool.fetch(
            """
                SELECT id, event, expires_at
                FROM reminders
                WHERE user_id = $1 AND NOT is_resolved
                ORDER BY expires_at
            """,
            ctx.author.id,
        )

        def format_item(i, x):
            name = f"{x['id']}. {discord.utils.format_dt(x['expires_at'], 'R')}"
            return {"name": name, "value": textwrap.shorten(x["event"], 512), "inline": False}

        if not reminders:
            return await ctx.send("No reminders found.")

        pages = ViewMenuPages(
            source=EmbedFieldsPageSource(
                reminders,
                title="Reminders",
                format_item=format_item,
            )
        )
        await pages.start(ctx)

    @reminder.command(aliases=("del",))
    @commands.guild_only()
    async def delete(self, ctx: Context, ids: commands.Greedy[int]):
        """Deletes one or more reminders."""

        result = await ctx.bot.database.pool.execute(
            """
                DELETE
                FROM reminders
                WHERE user_id = $1 AND ID = ANY($2::int[])
            """,
            ctx.author.id,
            ids,
        )
        num_deleted = int(result.removeprefix("DELETE "))
        self.clear_current()
        self.bot.loop.create_task(self.update_current())
        await ctx.send(f"Successfully deleted {formats.plural(num_deleted):reminder}.")

    async def get_next_reminder(self):
        return await self.bot.database.pool.fetchrow(
            """
            SELECT id, user_id, event, channel_id, message_id, created_at, expires_at
            FROM reminders
            WHERE NOT is_resolved
            ORDER BY expires_at
            LIMIT 1
            """
        )

    def clear_current(self):
        if self._current:
            self._current.task.cancel()
            self._current = None

    async def update_current(self, reminder=None):
        await self.bot.wait_until_ready()

        if reminder is None:
            reminder = await self.get_next_reminder()
            if reminder is None:
                return

        if self._current is not None and not self._current.task.done():
            if reminder["expires_at"] > self._current.reminder["expires_at"]:
                return
            self.clear_current()

        self._current = DispatchedReminder(
            reminder=reminder,
            task=self.bot.loop.create_task(self.dispatch_reminder(reminder)),
        )

    async def dispatch_reminder(self, reminder):
        try:
            await discord.utils.sleep_until(reminder["expires_at"])
        except asyncio.CancelledError:
            return

        await self.bot.database.pool.execute(
            "UPDATE reminders SET is_resolved = True WHERE id = $1",
            reminder["id"],
        )

        channel = self.bot.get_partial_messageable(reminder["channel_id"])
        text = f"Reminder from {discord.utils.format_dt(reminder['created_at'], 'R')}: {reminder['event']}"
        try:
            reference = await channel.fetch_message(reminder["message_id"])
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            text = f"<@{reminder['user_id']}> {text}"
            reference = None

        try:
            await channel.send(text, reference=reference)
        except (discord.NotFound, discord.Forbidden):
            return await self.bot.database.pool.execute(
                "UPDATE reminders SET is_failed = True WHERE id = $1",
                reminder.id,
            )

        self.bot.loop.create_task(self.update_current())


async def setup(bot):
    await bot.add_cog(Reminders(bot))
