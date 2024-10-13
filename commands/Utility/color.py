import discord, aiohttp
from discord import app_commands
from discord.ext import commands

class Color(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "color",
    description = "Visualize a hex color"
  )
  @app_commands.describe(
    hex = "The hex code of the color you want to visualize",
  )
  async def color(
    self,
    interaction: discord.Interaction,
    hex: str
  ) -> None:
    if hex.startswith('#'):
      hex = hex[1:]
    async with aiohttp.ClientSession() as session:
      async with session.get('https://www.thecolorapi.com/id', params={"hex": hex}) as server:
        if server.status == 200:
          js = await server.json()
          if (js['hex']['clean'] == '000000' and str(hex).lower() != '000000') or (js['name']['exact_match_name'] is False and js['name']['distance'] is None):
            
            embed = discord.Embed(title="⚠️ Invalid hex code", description="Hey! It looks like you have given me an invalid hex code. \n\nHex code uses the letters A-F, in addition to the digits 0-9, for a total of 16 symbols. If you have trouble finding the hex code, you could visit [this website](https://https://htmlcolorcodes.com/) to get help.", color=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
          embed = discord.Embed(title=f"Information about {js['name']['value'].lower()}", description=f"**HEX:** {js['hex']['value']}\n**RGB:** {js['rgb']['value']}\n**HSV:** {js['hsv']['value']}\n**HSL:** {js['hsl']['value']}\n**CMYK:** {js['cmyk']['value']}\n**XYZ:** {js['XYZ']['value']}\nContrasts with {'black' if js['contrast']['value'] == '#000000' else 'white'}.")
          try:
            embed.color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
          except:
            pass
          embed.set_image(url=f"https://colorhexa.com/{js['hex']['clean']}.png")
          await interaction.response.send_message(embed=embed)
        else:
          await interaction.response.send_message(f'Something went wrong when trying to get the data! Status code: {server.status}', ephemeral=True)

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Color(bot))