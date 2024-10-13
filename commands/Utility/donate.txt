import discord, time, datetime, firebase_admin
from discord import app_commands
from discord.ext import commands
from firebase_admin import db

### --- ADD MORA TO USER --- ###

async def addMora(userID, addedMora):
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  
  ogmora = 0
  try:
    for key, val in randomevents.items():
      if val['User ID'] == userID:
        ogmora = val['Mora']
        db.reference('/Random Events').child(key).delete()
        break
  except Exception:
    pass

  newmora = ogmora + addedMora
  data = {
    "Random Event Participant": {
      "User ID": userID,
      "Mora": newmora,
    }
  }

  for key, value in data.items():
    ref.push().set(value)

class DonateMora(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "donate",
    description = "Donate your mora to another user."
  )
  @app_commands.describe(
    user = "Specify the user you wish to donate to",
    mora = "The amount of mora you wish to donate"
  )
  async def mora(
    self, 
    interaction: discord.Interaction,
    user: discord.Member,
    mora: int
  ) -> None:
    id = interaction.user.id
    if mora == 0:
      await interaction.response.send_message("Donate _something_, not 0 mora...", ephemeral=True)
      raise Exception
    elif mora < 0:
      await interaction.response.send_message("You can't donate negative mora. Nice try though.", ephemeral=True)
      raise Exception
    ref = db.reference("/Random Events")
    randomevents = ref.get()
    
    ogmora = 0
    try:
      for key, val in randomevents.items():
        if val['User ID'] == id:
          ogmora = val['Mora']
          break
    except Exception:
      pass

    if mora > ogmora:
      mora = ogmora
    if ogmora <= 0:
      await interaction.response.send_message("You can't do this because you have no mora left.", ephemeral=True)
      raise Exception
    await addMora(user.id, mora)
    await addMora(id, -mora)
    embed = discord.Embed(title="A kind donation just occurred! <:FischlComfy:993432749203537990>", description=f"<@{id}> just **donated** <:MORA:953918490421641246> {mora} to {user.mention}!", color=discord.Color.gold())
    
    if interaction.guild.id != 717029019270381578:
      content = "This command is for the event happening in **Genshin Impact Cafe♡**: discord.gg/traveler"
      await interaction.response.send_message(content =content)
    else:
      await interaction.response.send_message(embed=embed)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(DonateMora(bot))