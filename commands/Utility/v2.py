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

    # Add a clickable button inside the container in a new section that responds when clicked (not a link button)
    class ClickableButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Click Me!", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("You clicked the button inside the container!", ephemeral=True)

    button_section = discord.ui.Section(
        "Section with a custom clickable button",
        accessory=ClickableButton()
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

# -------------------------------------------------------------- #

class StoreContainer(discord.ui.Container):
    class PurchaseButton(discord.ui.Button):
        def __init__(self, item: str):
            super().__init__(label=f"Purchase {item}", style=discord.ButtonStyle.primary) # {later use dictionary to change label based on item key}
            self.item = item

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message(f"Purchased {self.item}", ephemeral=True)

    button_section = discord.ui.Section(
        "### Star Drop\n*<:reply:1036792837821435976> Cost: 800*\n> A mysterious drop that contains random rewards. You can buy up to 10 every 24 hours. View the chances at </rates:1418097816458494003>! Use </stardrop:1418097816458494002> to open them.",
        accessory=PurchaseButton(item="stardrop")
    )

    separator = discord.ui.Separator(
        visible = True,
        spacing = discord.SeparatorSpacing.small
    )

    button_section2 = discord.ui.Section(
        "### XP Boost\n*<:reply:1036792837821435976> Cost: 3500*\n> A mysterious relic from the far reaches of the cosmos, pulsing with otherworldly energy. When unleashed, it detonates in a radiant burst of alien light, flooding you with 115,000 XP in an instant. Legends say the bomb was crafted...",
        accessory=PurchaseButton(item="xpboost")
    )

class Store(discord.ui.LayoutView):
    container = StoreContainer(accent_color = 0x7289da)

    action_row = discord.ui.ActionRow()

    @action_row.button(label = "Previous")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Clicked previous!", ephemeral = True)

    @action_row.button(label = "Next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Clicked next!", ephemeral = True)

class MyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name = "layout",
        description = "Display a Discord Components V2 layout example."
    )
    async def layout(self, interaction: discord.Interaction):
        # layout_view = Layout()
        # await interaction.response.send_message(view=layout_view)

        store_view = Store()
        await interaction.response.send_message(view=store_view)

async def setup(bot):
    await bot.add_cog(MyCog(bot))