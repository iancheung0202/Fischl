import discord

from discord.ext import commands
from discord import app_commands, SelectOption

class MyContainer(discord.ui.Container):
    text = discord.ui.TextDisplay("This appears inside a box!")
    
    separator = discord.ui.Separator(
        visible = True,
        spacing = discord.SeparatorSpacing.large
    )
    
    section = discord.ui.Section(
        "Text content with a button inside a box",
        accessory = discord.ui.Button(label = "Link", style = discord.ButtonStyle.link, url = "https://example.com")
    )

class Layout(discord.ui.LayoutView):
    text = discord.ui.TextDisplay("Hello, Components V2!")
    container = MyContainer(accent_color = 0x7289da)

    action_row = discord.ui.ActionRow()
    action_row2 = discord.ui.ActionRow()

    @action_row.button(label = "A Click Button")
    async def a_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Clicked!", ephemeral = True)

    @action_row2.select(placeholder = "A Select Menu", options = [
        SelectOption(label = "Option 1", value = "1"),
        SelectOption(label = "Option 2", value = "2"),
        SelectOption(label = "Option 3", value = "3"),
    ])
    async def a_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(f"Selected {select.values[0]}!", ephemeral = True)

    section = discord.ui.Section(
        "Text content with a thumbnail",
        accessory = discord.ui.Thumbnail("https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=1024")
    )
    section2 = discord.ui.Section(
        "Another ext content with a button",
        accessory = discord.ui.Button(label = "Another Link", style = discord.ButtonStyle.link, url = "https://example.com")
    )

class MyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name = "layout",
        description = "Display a Discord Components V2 layout example."
    )
    async def layout(self, interaction: discord.Interaction):
        layout_view = Layout()
        await interaction.response.send_message(view=layout_view)

async def setup(bot):
    await bot.add_cog(MyCog(bot))