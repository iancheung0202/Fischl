import discord
import datetime
import re

from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageColor

class Text(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "text",
    description = "Generates texts with Genshin-styled font"
  )
  @app_commands.describe(
    color = "The hex code of the color of the text (Format: #ffffff)",
    phrase = "Words to be written"
  )
  async def text(
    self,
    interaction: discord.Interaction,
    color: str,
    phrase: str
  ) -> None:
    await interaction.response.defer(ephemeral=True)
    if (len(phrase) > 30):
      embed = discord.Embed(title="Too long!", description=":warning: Your text length must not be longer than **30 characters** or else in most cases we cannot fit your text in the image! Please try again by separating your text and do the command multiple times!", colour=0x93a7ed)
      embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      embed.set_footer(text="Action terminated")
      await interaction.followup.send(embed=embed, ephemeral=True)
      raise Exception()

    if (str(color)[0]!="#"):
      color = "#" + color
    if re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
      pass
    else:
      embed = discord.Embed(title="⚠️ Invalid hex code", description="Hey! It looks like you have given me an invalid hex code. \n\nHex code uses the letters A-F, in addition to the digits 0-9, for a total of 16 symbols. If you have trouble finding the hex code, you could visit [this website](https://https://htmlcolorcodes.com/) to get help.", color=discord.Color.red())
      embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      embed.set_footer(text="Action terminated")
      await interaction.followup.send(embed=embed, ephemeral=True)
      raise Exception()
    
    color = ImageColor.getcolor(color, "RGB")

    if color == "#000001":
      img = Image.new('RGB', (3500, 250), color=(0, 0, 0))
    else:
      img = Image.new('RGB', (3500, 250), color=(0, 0, 1))
    font = ImageFont.truetype("./assets/ja-jp.ttf", 200)
    d = ImageDraw.Draw(img)
    d.text((20,0), phrase, font=font, fill=color)
    img.save(f"./assets/text.png")
    img = Image.open(f"./assets/text.png")
    rgba = img.convert("RGBA")
    datas = rgba.getdata()
  
    newData = []
    for item in datas:
      if color == "#000001":
        if item[0] == 0 and item[1] == 0 and item[2] == 0: 
          newData.append((255, 255, 255, 0))
        else:
          newData.append(item)
      else:
        if item[0] == 0 and item[1] == 0 and item[2] == 1: 
          newData.append((255, 255, 255, 0))
        else:
          newData.append(item)
      
    rgba.putdata(newData)
    rgba.save(f"./assets/text.png", "PNG")

    await interaction.followup.send(file=discord.File("./assets/text.png"))

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Text(bot))