import logging

import discord
from discord.ext import commands

from bmt_discord_bot import Bot, Context
from bmt_discord_bot.lib import formats


Target = discord.TextChannel | discord.CategoryChannel


class Threads(commands.Cog):
    """Auto-subscribe to new threads in channels."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _resolve_target(guild: discord.Guild, target: Target | None) -> tuple[str, int, str]:
        if target is None:
            return "server", guild.id, "this server"
        elif isinstance(target, discord.CategoryChannel):
            return "category", target.id, f"category **{target.name}**"
        else:
            return "channel", target.id, target.mention

    @commands.hybrid_group(fallback="list")
    @commands.guild_only()
    async def threads(self, ctx: Context):
        """List your thread subscriptions."""

        subscriptions = await ctx.bot.database.pool.fetch(
            """
                SELECT scope_type, scope_id, excluded, created_at
                FROM thread_subscriptions
                WHERE user_id = $1 AND guild_id = $2
                ORDER BY
                    CASE scope_type
                        WHEN 'server' THEN 0
                        WHEN 'category' THEN 1
                        WHEN 'channel' THEN 2
                    END,
                    created_at
            """,
            ctx.author.id,
            ctx.guild.id,
        )

        if not subscriptions:
            return await ctx.send("You have no thread subscriptions in this server.")

        lines = []
        for sub in subscriptions:
            prefix = "\N{HEAVY CHECK MARK}" if not sub["excluded"] else "\N{HEAVY MULTIPLICATION X}"
            scope_type = sub["scope_type"]
            scope_id = sub["scope_id"]
            if scope_type == "server":
                label = "Entire server"
            elif scope_type == "category":
                category = ctx.guild.get_channel(scope_id)
                label = (
                    f"Category: **{category.name}**"
                    if category
                    else f"Category: *unknown* ({scope_id})"
                )
            else:
                label = f"<#{scope_id}>"
            lines.append(f"{prefix} {label}")

        embed = discord.Embed(
            title="Thread Subscriptions",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"{formats.plural(len(subscriptions)):rule}")
        await ctx.send(embed=embed)

    @threads.command()
    @commands.guild_only()
    async def subscribe(self, ctx: Context, *, target: Target | None = None):
        """Subscribe to new threads. Pass a channel or category, or nothing for the whole server."""

        scope_type, scope_id, label = self._resolve_target(ctx.guild, target)

        result = await ctx.bot.database.pool.execute(
            """
                INSERT INTO thread_subscriptions (user_id, guild_id, scope_type, scope_id, excluded)
                VALUES ($1, $2, $3, $4, FALSE)
                ON CONFLICT (user_id, scope_type, scope_id)
                DO UPDATE SET excluded = FALSE
            """,
            ctx.author.id,
            ctx.guild.id,
            scope_type,
            scope_id,
        )

        if result == "INSERT 0 1":
            await ctx.send(f"You were already subscribed to {label}.")
        else:
            await ctx.send(f"Subscribed to threads in {label}.")

    @threads.command()
    @commands.guild_only()
    async def unsubscribe(self, ctx: Context, *, target: Target | None = None):
        """Unsubscribe from threads. Pass a channel or category, or nothing for the whole server."""

        scope_type, scope_id, label = self._resolve_target(ctx.guild, target)

        existing = await ctx.bot.database.pool.fetchrow(
            """
                SELECT excluded
                FROM thread_subscriptions
                WHERE user_id = $1 AND scope_type = $2 AND scope_id = $3
            """,
            ctx.author.id,
            scope_type,
            scope_id,
        )

        if existing is not None and not existing["excluded"]:
            await ctx.bot.database.pool.execute(
                """
                    DELETE FROM thread_subscriptions
                    WHERE user_id = $1 AND scope_type = $2 AND scope_id = $3
                """,
                ctx.author.id,
                scope_type,
                scope_id,
            )
            await ctx.send(f"Removed subscription for {label}.")
            return

        if existing is not None and existing["excluded"]:
            await ctx.send(f"You already have an exclusion for {label}.")
            return

        has_parent = await ctx.bot.database.pool.fetchval(
            """
                SELECT EXISTS (
                    SELECT 1 FROM thread_subscriptions
                    WHERE user_id = $1 AND guild_id = $2 AND excluded = FALSE
                    AND (
                        (scope_type = 'server')
                        OR (scope_type = 'category' AND $3 = 'channel')
                    )
                )
            """,
            ctx.author.id,
            ctx.guild.id,
            scope_type,
        )

        if has_parent:
            await ctx.bot.database.pool.execute(
                """
                    INSERT INTO thread_subscriptions (user_id, guild_id, scope_type, scope_id, excluded)
                    VALUES ($1, $2, $3, $4, TRUE)
                    ON CONFLICT (user_id, scope_type, scope_id)
                    DO UPDATE SET excluded = TRUE
                """,
                ctx.author.id,
                ctx.guild.id,
                scope_type,
                scope_id,
            )
            await ctx.send(f"Excluded {label} from your subscriptions.")
        else:
            await ctx.send(f"You're not subscribed to {label}.")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.guild is None:
            return
        if thread.parent is None:
            return
        if not isinstance(thread.parent, discord.TextChannel):
            return

        category_id = thread.parent.category_id

        scope_ids = [thread.parent.id]
        scope_types = ["channel"]
        if category_id is not None:
            scope_ids.append(category_id)
            scope_types.append("category")
        scope_ids.append(thread.guild.id)
        scope_types.append("server")

        subscribers = await self.bot.database.pool.fetch(
            """
                SELECT DISTINCT ts.user_id
                FROM thread_subscriptions ts
                WHERE ts.guild_id = $1
                    AND ts.excluded = FALSE
                    AND ts.scope_type = ANY($2::subscription_scope[])
                    AND ts.scope_id = ANY($3::bigint[])
                    AND NOT EXISTS (
                        SELECT 1 FROM thread_subscriptions ex
                        WHERE ex.user_id = ts.user_id
                            AND ex.guild_id = $1
                            AND ex.excluded = TRUE
                            AND (
                                (ex.scope_type = 'channel' AND ex.scope_id = $4)
                                OR (ex.scope_type = 'category' AND ex.scope_id = $5)
                            )
                    )
            """,
            thread.guild.id,
            scope_types,
            scope_ids,
            thread.parent.id,
            category_id or 0,
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
