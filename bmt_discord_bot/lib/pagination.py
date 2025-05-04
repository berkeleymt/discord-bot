import discord
from discord.ext import menus


class EmbedFieldsPageSource(menus.ListPageSource):
    def __init__(self, data, title=None, format_item=lambda i, x: (i, x)):
        super().__init__(data, per_page=5)
        self.title = title
        self.format_item = format_item
        self.count = len(data)

    async def format_page(self, menu, page):
        embed = discord.Embed(
            title=self.title,
            color=discord.Color.blurple(),
        )
        start = menu.current_page * self.per_page
        i = -1
        for i, x in enumerate(page, start=start):
            embed.add_field(**self.format_item(i, x))
        footer = f"Showing entries {start + 1}–{i + 1}"
        if self.count is not None:
            footer += f" out of {self.count}"
        embed.set_footer(text=footer)
        return embed
