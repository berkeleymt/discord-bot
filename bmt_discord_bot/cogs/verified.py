import logging

import discord
from discord.ext import commands, tasks

from bmt_discord_bot import Bot

logger = logging.getLogger(__name__)

GUILD_ID = 786701065856221205
LOG_CHANNEL_ID = 1471399531580100670

VERIFIED_ROLE_NAME = "Verified"
TRIGGER_ROLE_NAMES = {"Logistics", "Problem Writing"}


class Verified(commands.Cog):
    """Auto-grants the Verified role when Logistics or Problem Writing is added."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.sync_verified_roles.start()

    def cog_unload(self):
        self.sync_verified_roles.cancel()

    def _get_roles(self, guild: discord.Guild):
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        trigger_roles = [r for r in guild.roles if r.name in TRIGGER_ROLE_NAMES]
        return verified_role, trigger_roles

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.guild.id != GUILD_ID:
            return

        added_roles = set(after.roles) - set(before.roles)
        trigger_added = [r for r in added_roles if r.name in TRIGGER_ROLE_NAMES]
        if not trigger_added:
            return

        verified_role, _ = self._get_roles(after.guild)
        if verified_role is None:
            logger.warning("Verified role not found in guild")
            return

        if verified_role in after.roles:
            return

        await after.add_roles(verified_role, reason="Auto-granted: member received a trigger role")

        moderator: discord.Member | discord.User | None = None
        try:
            async for entry in after.guild.audit_log(
                action=discord.AuditLogAction.member_role_update,
                limit=10,
            ):
                if entry.target and entry.target.id == after.id:
                    if any(r.name in TRIGGER_ROLE_NAMES for r in entry.changes.after.roles):
                        moderator = entry.user
                        break
        except (discord.Forbidden, discord.HTTPException):
            pass

        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if channel is None or not isinstance(channel, discord.abc.Messageable):
            return

        role_names = ", ".join(f"**{r.name}**" for r in trigger_added)
        mod_text = f" by {moderator.mention}" if moderator else ""
        await channel.send(
            f"{after.mention} was granted **Verified** after receiving {role_names}{mod_text}."
        )

    @tasks.loop(hours=1)
    async def sync_verified_roles(self):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return

        verified_role, trigger_roles = self._get_roles(guild)
        if verified_role is None or not trigger_roles:
            return

        channel = self.bot.get_channel(LOG_CHANNEL_ID)

        for member in guild.members:
            has_trigger = any(r in member.roles for r in trigger_roles)
            if has_trigger and verified_role not in member.roles:
                await member.add_roles(
                    verified_role, reason="Periodic sync: member has a trigger role"
                )
                logger.info(f"Sync: granted Verified to {member} ({member.id})")
                if channel is not None and isinstance(channel, discord.abc.Messageable):
                    trigger_names = ", ".join(
                        f"**{r.name}**" for r in trigger_roles if r in member.roles
                    )
                    await channel.send(
                        f"{member.mention} was granted **Verified** during periodic sync "
                        f"(has {trigger_names})."
                    )

    @sync_verified_roles.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()


async def setup(bot: Bot):
    await bot.add_cog(Verified(bot))
