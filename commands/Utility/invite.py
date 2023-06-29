import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

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
    link = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(title="Sharing is caring", description=f"Fischl is a multi-function Genshin-based bot with ticket system with a lot more utility-based slash commands. 🤖\n\n **[Invite me to your server!]({link})**", color=discord.Color.blurple())
    button = Button(label="Invite Me", style=discord.ButtonStyle.link, emoji="<:link:943068848058413106>", url=link)
    view = View()
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Invite(bot))