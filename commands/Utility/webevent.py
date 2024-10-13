import discord, datetime
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class WebEvent(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "send-webevent",
    description = "Sends a message for web event in embed"
  )
  @app_commands.choices(game=[
      app_commands.Choice(name="Genshin Impact", value="genshin"),
      app_commands.Choice(name="Honkai: Star Rail", value="hsr"),
  ])
  @app_commands.describe(
    game = "The game that the web event belongs",
    link = "Link to the event",
    role = "The role you would like to ping alongside this message",
    title = "Event title",
    details = "Event description/details",
    image = "Embed image"
  )
  @app_commands.guild_only()
  async def webevent(
    self,
    interaction: discord.Interaction,
    game: app_commands.Choice[str],
    link: str,
    role: discord.Role = None,
    title: str = None,
    details: str = None,
    image: discord.Attachment = None,
  ) -> None:
    view = View()
    if title is None:
      embed = discord.Embed()
    else:
      embed = discord.Embed(title=title)
    if details is not None:
      embed.description = details
    embed.url = link
    if image is not None:
      path = f"./assets/webevent.png"
      await image.save(path)
      chn = interaction.client.get_channel(1026968305208131645)
      msg = await chn.send(file=discord.File(path))
      url = msg.attachments[0].proxy_url 
      embed.set_image(url=url)
    
    button = Button(label=title, style=discord.ButtonStyle.link, emoji="<:link:943068848058413106>", url=link)
    view.add_item(button)
    
    embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    if game.value == "genshin":
      if role is not None:
        await interaction.channel.send(f"<:blurplemic:1108805037230129302> {role.mention} **• New Genshin Impact Web Event**", embed=embed, view=view)
      else:
        await interaction.channel.send(f"<:blurplemic:1108805037230129302> **• New Genshin Impact Web Event**", embed=embed, view=view)
    elif game.value == "hsr":
      if role is not None:
        await interaction.channel.send(f"<:blurplemic:1108805037230129302> {role.mention} **• New Honkai: Star Rail Web Event**", embed=embed, view=view)
      else:
        await interaction.channel.send(f"<:blurplemic:1108805037230129302> **• New Honkai: Star Rail Web Event**", embed=embed, view=view)
    await interaction.response.send_message("<:yes:1036811164891480194> Sent!", ephemeral=True)
      
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(WebEvent(bot))