import discord, datetime
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class SendCodes(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "sendcodes",
    description = "Sends a message for Genshin redemption codes with links and buttons."
  )
  @app_commands.describe(
    codes = "The redemption codes you wish to send, each separated by a comma",
    role = "The role you would like to ping alongside this message",
  )
  async def sendcode(
    self,
    interaction: discord.Interaction,
    codes: str,
    role: discord.Role = None
  ) -> None:
    listOfCodes = codes.split(",")
    codeString = ""
    view = View()
    for code in listOfCodes:
      c = code.strip()
      codeString += f"<:yes:1036811164891480194> `{c}` | **[Direct Link](https://genshin.hoyoverse.com/en/gift?code={c})**\n"
      button = Button(label=c, style=discord.ButtonStyle.link, emoji="<:PRIMOGEM:939086760296738879>", url=f"https://genshin.hoyoverse.com/en/gift?code={c}")
      view.add_item(button)
    
    embed = discord.Embed(title="Latest Genshin Impact Redemption Codes", description=f"""<:link:943068848058413106> ***[Redeem by clicking on the buttons below!](https://genshin.mihoyo.com/en/gift)***
<:Keqing_note:945209842975531008> **Note:** Codes expire quickly, so make sure to redeem them as soon as possible!

<:code1:1108803434141982751><:code2:1108803491171934218><:code3:1108803565331431454>
{codeString}""", color=discord.Color.blurple())
    embed.set_image(url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png")
    embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    embed.timestamp = datetime.datetime.utcnow()
    if role is not None:
      await interaction.channel.send(f"<:blurplemic:1108805037230129302> {role.mention} **• Redeemable Codes**", embed=embed, view=view)
    else:
      await interaction.channel.send(f"<:blurplemic:1108805037230129302> **• Redeemable Codes**", embed=embed, view=view)
    await interaction.response.send_message("<:yes:1036811164891480194> Sent!", ephemeral=True)
      
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(SendCodes(bot))