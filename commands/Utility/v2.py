import discord
from discord import app_commands
from discord.ext import commands


class StoreContainer(discord.ui.Container):
    class PurchaseButton(discord.ui.Button):
        def __init__(self, item: str):
            super().__init__(
                label=f"Purchase {item}", style=discord.ButtonStyle.primary
            )  # {later use dictionary to change label based on item key}
            self.item = item

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message(
                f"Purchased {self.item}", ephemeral=True
            )

    button_section = discord.ui.Section(
        "### Star Drop\n*<:reply:1036792837821435976> Cost: 800*\n> A mysterious drop that contains random rewards. You can buy up to 10 every 24 hours. View the chances at </rates:1418097816458494003>! Use </stardrop:1418097816458494002> to open them.",
        accessory=PurchaseButton(item="stardrop"),
    )

    separator = discord.ui.Separator(
        visible=True, spacing=discord.SeparatorSpacing.small
    )

    button_section2 = discord.ui.Section(
        "### XP Boost\n*<:reply:1036792837821435976> Cost: 3500*\n> A mysterious relic from the far reaches of the cosmos, pulsing with otherworldly energy. When unleashed, it detonates in a radiant burst of alien light, flooding you with 115,000 XP in an instant. Legends say the bomb was crafted...",
        accessory=PurchaseButton(item="xpboost"),
    )


class Store(discord.ui.LayoutView):
    container = StoreContainer(accent_color=0x7289DA)

    action_row = discord.ui.ActionRow()

    @action_row.button(label="Previous")
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("Clicked previous!", ephemeral=True)

    @action_row.button(label="Next")
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("Clicked next!", ephemeral=True)


class MyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="layout", description="Display a Discord Components V2 layout example."
    )
    async def layout(self, interaction: discord.Interaction):
        store_view = Store()
        await interaction.response.send_message(view=store_view)


async def setup(bot):
    await bot.add_cog(MyCog(bot))
