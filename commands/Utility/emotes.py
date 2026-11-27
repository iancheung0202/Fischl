import discord
from discord import app_commands
from discord.ext import commands


class PaginationView(discord.ui.View):
    """The four arrows under a list of pages."""

    def __init__(self, pages):
        super().__init__()
        self.page = 0
        self.pages = pages

    async def show(self, interaction, page):
        """Turns to a page, wrapping round at either end."""
        self.page = page % len(self.pages)
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page + 1} of {len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        emoji="<:fastbackward:1351972112696479824>",
        style=discord.ButtonStyle.blurple,
        custom_id="super_prev",
    )
    async def super_prev_button(self, interaction, button):
        """Goes to the first page."""
        await self.show(interaction, 0)

    @discord.ui.button(
        emoji="<:backarrow:1351972111010369618>",
        style=discord.ButtonStyle.blurple,
        custom_id="prev",
    )
    async def prev_button(self, interaction, button):
        """Goes back one page."""
        await self.show(interaction, self.page - 1)

    @discord.ui.button(
        emoji="<:rightarrow:1351972116819480616>",
        style=discord.ButtonStyle.blurple,
        custom_id="next",
    )
    async def next_button(self, interaction, button):
        """Goes forward one page."""
        await self.show(interaction, self.page + 1)

    @discord.ui.button(
        emoji="<:fastforward:1351972114433048719>",
        style=discord.ButtonStyle.blurple,
        custom_id="super_next",
    )
    async def super_next_button(self, interaction, button):
        """Goes to the last page."""
        await self.show(interaction, -1)


def written(emoji):
    """Gives an emoji next to the text a member types to use it."""
    return f"{emoji} `<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>`\n"


@app_commands.guild_only()
class Emote(commands.GroupCog, name="emotes", group_description="…"):
    """The command that lists a server's emojis."""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="all", description="Shows all the emojis in the server")
    async def emote_all(self, interaction: discord.Interaction) -> None:
        """Lists the server's emojis, 25 to a page."""
        lines = [written(emoji) for emoji in interaction.guild.emojis]
        title = f"Emotes in {interaction.guild.name}"
        pages = [
            discord.Embed(title=title, description="".join(lines[start : start + 25]))
            for start in range(0, len(lines), 25)
        ]
        pages[0].set_footer(text=f"Page 1 of {len(pages)}")
        await interaction.response.send_message(
            embed=pages[0], view=PaginationView(pages)
        )


async def setup(bot):
    await bot.add_cog(Emote(bot))
