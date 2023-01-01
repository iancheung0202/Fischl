import discord, time, datetime, aiohttp
from discord import app_commands
from discord.ext import commands

class modal(discord.ui.Modal, title = "Setup Embed Message"):
  
  msg = discord.ui.TextInput(label="Normal message content", style=discord.TextStyle.paragraph, placeholder="", max_length=2000, required=False)
  
  embedtitle = discord.ui.TextInput(label="Title of the embed", style=discord.TextStyle.paragraph, placeholder="", max_length=256, required=False)
  
  description = discord.ui.TextInput(label="Description of the embed", style=discord.TextStyle.paragraph, placeholder="", max_length=4000, required=False)
  
  color = discord.ui.TextInput(label="Color of the embed", style=discord.TextStyle.short, placeholder="Use hex code (e.g. #ff0000)", max_length=7, required=False)

  async def on_submit(self, interaction:discord.Interaction):
    tit = str(self.embedtitle)
    desc = str(self.description)
    color = discord.Color.blurple()
    if str(self.color) != "":
      hex = str(self.color)
      if hex.startswith('#'):
        hex = hex[1:]
      async with aiohttp.ClientSession() as session:
        async with session.get('https://www.thecolorapi.com/id', params={"hex": hex}) as server:
          if server.status == 200:
            
            js = await server.json()
            try:
              color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
            except:
              color = discord.Color.blurple()

    if self.embedtitle == None and self.description == None:
      embed = None
    else:
      embed = discord.Embed(title=tit, description=desc, color=color)
    await interaction.channel.send(str(self.msg), embed=embed)

    embed = discord.Embed(title="", description=f'**Custom embed message sent**', colour=0x00FF00)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.response.send_message(embed=embed, ephemeral=True)

class Embed(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "embed",
    description = "Creates a custom embed message"
  )
  async def embed(
    self,
    interaction: discord.Interaction
  ) -> None:
    await interaction.response.send_modal(modal())
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Embed(bot))