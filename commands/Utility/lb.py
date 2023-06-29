import discord, time, datetime, firebase_admin
from discord import app_commands
from discord.ext import commands
from firebase_admin import db

class Leaderboard(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "lb",
    description = "Check the mora leaderboard in the 2023 Cafe Summer Festival."
  )
  async def mora(
    self,
    interaction: discord.Interaction
  ) -> None:
    ref = db.reference("/Random Events")
    randomevents = ref.get()
    userIDs = []
    moras = []
    for x in range(20):
      highestMora = 0
      for key, val in randomevents.items():
        user_id = val['User ID']
        mora = val['Mora']
        if not(isinstance(user_id, int)) or not(isinstance(mora, int)):
          continue
        if mora > highestMora and mora not in moras:
          highestMora = mora
          highestUser = user_id
      userIDs.append(highestUser)
      moras.append(highestMora)
    string = ""
    for x in range(20):
      string += f"**{x+1}.**  <@{userIDs[x]}> - <:MORA:953918490421641246> `{moras[x]:,}`\n"
    embed = discord.Embed(title="Leaderboard - 2023 Cafe Summer Festival", description=f"{string}", color=discord.Color.gold())
    
    if interaction.guild.id != 717029019270381578:
      content = "This leaderboard is for the event happening in **Genshin Impact Cafe♡**: discord.gg/traveler"
    else:
      content = None
    await interaction.response.send_message(content, embed=embed)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Leaderboard(bot))