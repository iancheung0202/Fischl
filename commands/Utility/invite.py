import discord

from discord import app_commands
from discord.ext import commands

class InviteContainer(discord.ui.Container):
    def __init__(self, bot_id: int):
        super().__init__(accent_color=0x7289da)
        link = f"https://discord.com/oauth2/authorize?client_id={bot_id}"
        
        section = discord.ui.Section(
            "🤖 Fischl is a multi-function Genshin-based bot with ticket system with a lot of utility-based slash commands.",
            accessory = discord.ui.Button(
                label="Invite Me", 
                style=discord.ButtonStyle.link,
                emoji="<:link:943068848058413106>",
                url=link
            )
        )
        self.add_item(section)

class InviteLayout(discord.ui.LayoutView):
    def __init__(self, bot_id: int):
        super().__init__()
        container = InviteContainer(bot_id)
        self.add_item(container)

class Invite(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "invite",
    description = "Invite the bot to your server"
  )
  async def invite(
    self,
    interaction: discord.Interaction
  ) -> None:
    layout_view = InviteLayout(self.bot.user.id)
    await interaction.response.send_message(view=layout_view)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Invite(bot))