import discord
from discord import app_commands
from discord.ext import commands

ABOUT = "🤖 Fischl is a multi-function Genshin-based bot with ticket system with a lot of utility-based slash commands."


def invite_view(bot_id):
    """Builds the boxed message with the button that adds the bot to a server."""
    button = discord.ui.Button(
        label="Invite Me",
        style=discord.ButtonStyle.link,
        emoji="<:link:943068848058413106>",
        url=f"https://discord.com/oauth2/authorize?client_id={bot_id}",
    )
    box = discord.ui.Container(
        discord.ui.Section(ABOUT, accessory=button), accent_color=0x7289DA
    )
    view = discord.ui.LayoutView()
    view.add_item(box)
    return view


class Invite(commands.Cog):
    """The command that hands out the bot's invite link."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="invite", description="Invite the bot to your server")
    async def invite(self, interaction: discord.Interaction) -> None:
        """Sends the invite button."""
        await interaction.response.send_message(view=invite_view(self.bot.user.id))


async def setup(bot):
    await bot.add_cog(Invite(bot))
