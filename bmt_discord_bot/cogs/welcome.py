import discord
from discord.ext import commands

from bmt_discord_bot import Bot, Context


class EditWelcomeModal(discord.ui.Modal, title="Edit Welcome Message"):
    message = discord.ui.TextInput(
        label="Welcome Message",
        style=discord.TextStyle.paragraph,
        placeholder="Enter the welcome message to send to new members...",
        required=False,
        max_length=2000,
    )

    def __init__(self, current_message: str | None, cog: "Welcome", guild_id: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        if current_message:
            self.message.default = current_message

    async def on_submit(self, interaction: discord.Interaction):
        new_message = self.message.value.strip() if self.message.value else None

        if new_message:
            await self.cog.bot.database.pool.execute(
                """
                    INSERT INTO welcome_settings (guild_id, welcome_message)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id) DO UPDATE SET welcome_message = EXCLUDED.welcome_message
                """,
                self.guild_id,
                new_message,
            )
            await interaction.response.send_message(
                "Welcome message updated successfully.", ephemeral=True
            )
        else:
            await self.cog.bot.database.pool.execute(
                """
                    DELETE FROM welcome_settings
                    WHERE guild_id = $1
                """,
                self.guild_id,
            )
            await interaction.response.send_message(
                "Welcome message has been disabled.", ephemeral=True
            )


class WelcomeView(discord.ui.View):
    def __init__(self, cog: "Welcome", guild_id: int, current_message: str | None):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id
        self.current_message = current_message

    @discord.ui.button(label="Edit Message", style=discord.ButtonStyle.primary)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditWelcomeModal(self.current_message, self.cog, self.guild_id)
        await interaction.response.send_modal(modal)


class Welcome(commands.Cog):
    """Welcome new members with a direct message."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def get_welcome_message(self, guild_id: int) -> str | None:
        return await self.bot.database.pool.fetchval(
            """
                SELECT welcome_message
                FROM welcome_settings
                WHERE guild_id = $1
            """,
            guild_id,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        welcome_message = await self.get_welcome_message(member.guild.id)
        if not welcome_message:
            return

        try:
            await member.send(welcome_message)
        except discord.Forbidden:
            pass

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx: Context):
        """View and edit the welcome message for new members."""

        assert ctx.guild is not None
        current_message = await self.get_welcome_message(ctx.guild.id)

        if current_message:
            embed = discord.Embed(
                title="Current Welcome Message",
                description=current_message,
                color=discord.Color.blue(),
            )
        else:
            embed = discord.Embed(
                title="Welcome Message",
                description="No welcome message is currently set for this server.",
                color=discord.Color.greyple(),
            )

        view = WelcomeView(self, ctx.guild.id, current_message)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
