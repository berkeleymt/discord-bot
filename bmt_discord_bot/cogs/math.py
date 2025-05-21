import io
from typing import Optional
import typst
import re
from pathlib import Path
import subprocess

import discord
from discord.ext import commands
from jishaku.functools import executor_function
from pylatex import Document, NoEscape, Package
from PIL import Image, ImageOps
import pymupdf
from abc import ABC, abstractmethod
from tempfile import TemporaryDirectory

from bmt_discord_bot import Bot, Context


DEFAULT_DEFAULT_RENDERER = "tex"
MAX_LINES_FOR_ERROR_SHOWN_BY_DEFAULT = 10
RENDER_DPI = 600
MIN_IMAGE_WIDTH = 1500


class CompileError(Exception):
    pass


class MathRenderer(ABC):
    name: str
    key: str
    aliases: list[str]

    @abstractmethod
    def compile_source(self, output_path: Path, source: str):
        pass

    @executor_function
    def render(self, source: str):
        def process_page(im: Image.Image):
            im = im.convert("RGBA")
            im = ImageOps.crop(im, 1)
            width, height = im.size
            im = ImageOps.pad(
                im,
                (max(MIN_IMAGE_WIDTH, width), height),
                color=(255, 255, 255, 0),
                centering=(0, 0.5),
            )
            buffer = io.BytesIO()
            im.save(buffer, "PNG")
            buffer.seek(0)
            return buffer

        with TemporaryDirectory() as dir:
            pdf_output_path = Path(dir) / "output.pdf"
            self.compile_source(pdf_output_path, source)
            doc = pymupdf.open(pdf_output_path)
            return [process_page(page.get_pixmap(dpi=RENDER_DPI).pil_image()) for page in doc]


class LatexRenderer(MathRenderer):
    name = "TeX"
    key = "tex"
    aliases = ["latex"]

    def compile_source(self, output_path: Path, source: str):
        document = Document(
            default_filepath=str(output_path).removesuffix(".pdf"),
            documentclass="standalone",
            document_options="border=8pt,crop,varwidth=256pt",
        )
        document.append(NoEscape(source))
        document.preamble.append(Package("amsmath"))
        try:
            document.generate_pdf(compiler="texfot", compiler_args=["--quiet", "pdflatex"])
        except subprocess.CalledProcessError as e:
            raise CompileError(e.output.decode())


class TypstRenderer(MathRenderer):
    name = "Typst"
    key = "typst"
    aliases = []

    def compile_source(self, output_path: Path, source: str):
        source_bytes = f"""
            #set page(width: auto, height: auto, margin: 8pt)
            {source}
        """.encode("utf-8")
        try:
            typst.compile(source_bytes, output_path, format="pdf")
        except RuntimeError as e:
            raise CompileError(str(e))


class MathView(discord.ui.View):
    class RendererSelect(discord.ui.Select["MathView"]):
        def __init__(self, selected_renderer: MathRenderer, renderers: list[MathRenderer]):
            super().__init__(
                options=[
                    discord.SelectOption(label=f"Renderer: {r.name}", value=str(i))
                    for i, r in enumerate(renderers)
                ]
            )
            self.renderers = renderers
            self.update_selected(selected_renderer)

        def update_selected(self, selected_renderer: MathRenderer):
            for option, renderer in zip(self.options, self.renderers):
                option.default = renderer is selected_renderer

        async def callback(self, interaction):
            if self.view is None or interaction.message is None:
                return
            value = int(self.values[0])
            renderer = self.renderers[value]
            self.update_selected(renderer)
            await self.view.render(renderer)
            await self.view.edit(interaction.message)
            await interaction.response.defer()

    def __init__(
        self,
        ctx: Context,
        source: str,
        default_renderer: MathRenderer,
        renderers: list[MathRenderer],
    ):
        super().__init__()
        self.ctx = ctx
        self.source = source
        self.default_renderer = default_renderer
        self.renderers = renderers
        self.select_renderer = self.RendererSelect(default_renderer, renderers)

    async def render(self, renderer: MathRenderer):
        self.remove_item(self.toggle_error)
        self.remove_item(self.select_renderer)
        try:
            bufs = await renderer.render(self.source)
            self.files = [discord.File(buf, filename=f"math_{i}.png") for i, buf in enumerate(bufs)]
            self.content = None
        except CompileError as e:
            error = str(e)
            self.files = []
            self.content = f"**{self.ctx.author}**\nCompile error. Click \N{WARNING SIGN}\N{VARIATION SELECTOR-16} for more information."
            self.next_content = f"**{self.ctx.author}**\n```{error}```"
            self.toggle_error.label = "Show error"
            self.next_button_label = "Hide error"
            self.add_item(self.toggle_error)
            self.add_item(self.select_renderer)
            if len(error.splitlines()) <= MAX_LINES_FOR_ERROR_SHOWN_BY_DEFAULT:
                self._toggle_error()

    def _toggle_error(self):
        self.content, self.next_content = self.next_content, self.content
        self.toggle_error.label, self.next_button_label = (
            self.next_button_label,
            self.toggle_error.label,
        )

    @discord.ui.button(emoji="\N{WASTEBASKET}")
    async def delete(self, interaction, button):
        await interaction.message.delete()
        await interaction.response.defer()

    @discord.ui.button(emoji="\N{WARNING SIGN}")
    async def toggle_error(self, interaction, button):
        self._toggle_error()
        await self.edit(interaction.message)
        await interaction.response.defer()

    async def send(self, channel: discord.abc.Messageable):
        if not hasattr(self, "files"):
            await self.render(self.default_renderer)
        await channel.send(self.content, files=self.files, view=self)

    async def edit(self, message: discord.Message):
        await message.edit(content=self.content, attachments=self.files, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author or self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message("You can't use this!", ephemeral=True)
        return False


class Math(commands.Cog):
    """Math rendering utilities."""

    def __init__(self, bot: Bot):
        self.bot = bot
        tex = LatexRenderer()
        typst = TypstRenderer()
        self.renderers = [tex, typst]
        self.renderer_by_key = {r.key: r for r in self.renderers}
        self.renderer_by_key |= {alias: r for r in self.renderers for alias in r.aliases}

    async def get_default_renderer(self, message: discord.Message):
        default_renderer = await self.bot.database.pool.fetchval(
            """
                SELECT default_renderer
                FROM math_settings
                WHERE user_id = $1
            """,
            message.author.id,
        )
        try:
            return self.renderer_by_key[default_renderer]
        except KeyError:
            return self.renderer_by_key[DEFAULT_DEFAULT_RENDERER]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or re.search(r"\$.+\$", message.content) is None:
            return
        ctx = await self.bot.get_context(message)
        if ctx.command is not None:
            return
        renderer = await self.get_default_renderer(message)
        await self.process_math(ctx, renderer, message.clean_content)

    @commands.command(aliases=("latex",))
    async def tex(self, ctx, file: Optional[discord.Attachment], *, source: str | None = None):
        """Render TeX to an image."""
        await self.process_math_command(ctx, self.renderer_by_key["tex"], file, source)

    @commands.command()
    async def typst(self, ctx, file: Optional[discord.Attachment], *, source: str | None = None):
        """Render Typst to an image."""
        await self.process_math_command(ctx, self.renderer_by_key["typst"], file, source)

    @commands.group(invoke_without_command=True)
    async def renderer(self, ctx, renderer: str):
        """Set default math renderer."""
        try:
            math_renderer = self.renderer_by_key[renderer.lower()]
        except KeyError:
            return await ctx.send(
                f"Unknown renderer. Valid values are: {', '.join(r.key for r in self.renderers)}."
            )

        await self.bot.database.pool.execute(
            """
                INSERT INTO math_settings (user_id, default_renderer)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET default_renderer = EXCLUDED.default_renderer
            """,
            ctx.author.id,
            math_renderer.key,
        )
        await ctx.send(f"Changed your default renderer to **{math_renderer.name}**.")

    @renderer.command(name="unset")
    async def renderer_unset(self, ctx):
        await self.bot.database.pool.execute(
            """
                UPDATE math_settings
                SET default_renderer = NULL
                WHERE user_id = $1
            """,
            ctx.author.id,
        )
        await ctx.send("Unset your default renderer.")

    async def process_math_command(
        self,
        ctx: Context,
        renderer: MathRenderer,
        file: discord.Attachment | None,
        source: str | None,
    ):
        if file is not None and source is not None:
            raise commands.TooManyArguments("Cannot pass both a source string and a file!")
        elif file is not None:
            source_bytes = await file.read()
            await self.process_math(ctx, renderer, source_bytes.decode("utf-8"))
        elif source is not None:
            await self.process_math(ctx, renderer, source)
        else:
            assert ctx.command is not None
            raise commands.MissingRequiredArgument(ctx.command.clean_params["source"])

    async def process_math(self, ctx: Context, renderer: MathRenderer, source: str):
        async with ctx.typing():
            view = MathView(ctx, source, renderer, self.renderers)
            await view.send(ctx.channel)


async def setup(bot):
    await bot.add_cog(Math(bot))
