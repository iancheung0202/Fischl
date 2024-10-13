import discord, firebase_admin, datetime, asyncio, time, emoji, random
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont, ImageColor

maxlimit = 250
teams = ["Team Mondstadt", "Team Liyue", "Team Inazuma", "Team Sumeru", "Team Fontaine", "Team Natlan"]
leaderRoles = ["Grand Master", "Tianshu", "Shogun", "Grand Sage", "Chief Justice", "Tribal Overlord"]
leaders = [1073849551116582952, 1105340054743814204, 846134937529614368, 973865405162586142, 954888790936281208, 868069540062449704]
teamchannels = [1083867546962370730, 1083867653803888722, 1083867759982682183, 1083867870200602734, 1106654299582386310, 1277096795154939936]

moraShowerEvent = True

class UnDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Unable To Defend', style=discord.ButtonStyle.grey, custom_id='undefend', emoji="❌", disabled=True)
  async def defend(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass
        
class Defend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.blurple, custom_id='defend', emoji="⚔️")
  async def defend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(5, 8), random.randint(4, 6), random.randint(4, 5), random.randint(3, 4), random.randint(-6, -4), 0])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    if plusCredits > 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion.", color=0x23AE37))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
    
    elif plusCredits < 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      await addCredits(opposingTeam, plusCredits-1)
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Our mansion defended and struck back!", "Successful defense and counterattack!", "Mansion secured, and enemies damaged!", "Defended with style, dealt damage too!", "Counteroffensive success!", "Guardians defended and retaliated!", "Strong defense, effective counter!", "Protected home, inflicted damage!", "Our mansion stands, theirs crumbles!", "Survived the attack, hit back harder!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and dealt **{abs(plusCredits-1) * 2} damage** on their Mansion! :tada:\n{team.replace('Team ', '')} also regained **{abs(plusCredits) * 2} HP** for the Mansion.", color=0x18C7E7))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(description=f"**{team}** counterattacked and dealt **{abs(plusCredits-1) * 2}** damage to the Mansion!", color=0xFF0000))
      await interaction.response.send_message(f"[Defense and counterattack success!]({msg.jump_url})", ephemeral=True)
        
    elif plusCredits == 0:
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion breached!", "Defense compromised!", "Intruders infiltrated!", "Security breached!", "Mansion under attack!", "Defense faltered!", "Intruders prevailed!", "Mansion vulnerable!", "Guardians defeated!", "Defense failed!"]), description=f"{interaction.user.mention} failed to defend the [attack]({interaction.message.jump_url}) from **{opposingTeam}**!", color=0x968CAD))
      await interaction.response.send_message(f"[Defense failed!]({msg.jump_url})", ephemeral=True)
    await interaction.message.edit(embed=embed, view=Defend())
    
class CollapseDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.green, custom_id='collapsedefend', emoji="⚔️")
  async def collapsedefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(60, 90), random.randint(50, 65), random.randint(45, 60), random.randint(40, 50), random.randint(-60, -40), random.randint(-90, -50), random.randint(-40, -35)])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    if plusCredits > 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion.", color=0x23AE37))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
    
    elif plusCredits < 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      await addCredits(opposingTeam, plusCredits-1)
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Our mansion defended and struck back!", "Successful defense and counterattack!", "Mansion secured, and enemies damaged!", "Defended with style, dealt damage too!", "Counteroffensive success!", "Guardians defended and retaliated!", "Strong defense, effective counter!", "Protected home, inflicted damage!", "Our mansion stands, theirs crumbles!", "Survived the attack, hit back harder!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and dealt **{abs(plusCredits-1) * 2} damage** on their Mansion! :tada:\n{team.replace('Team ', '')} also regained **{abs(plusCredits) * 2} HP** for the Mansion.", color=0x18C7E7))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(description=f"**{team}** counterattacked and dealt **{abs(plusCredits-1) * 2}** damage to the Mansion!", color=0xFF0000))
      await interaction.response.send_message(f"[Defense and counterattack success!]({msg.jump_url})", ephemeral=True)
    await interaction.message.edit(embed=embed, view=CollapseDefend())
    
class ShadowRealmDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.grey, custom_id='shadowrealmdefend', emoji="⚔️")
  async def shadowrealmdefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(5, 8), random.randint(4, 6), random.randint(4, 5), random.randint(3, 4), 0, 0])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    if plusCredits > 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion.", color=0x23AE37))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
        
    elif plusCredits == 0:
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion breached!", "Defense compromised!", "Intruders infiltrated!", "Security breached!", "Mansion under attack!", "Defense faltered!", "Intruders prevailed!", "Mansion vulnerable!", "Guardians defeated!", "Defense failed!"]), description=f"{interaction.user.mention} failed to defend the [attack]({interaction.message.jump_url}) from **{opposingTeam}**!", color=0x968CAD))
      await interaction.response.send_message(f"[Defense failed!]({msg.jump_url})", ephemeral=True)
    await interaction.message.edit(embed=embed, view=ShadowRealmDefend())
    
class ReverbDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.blurple, custom_id='reverbdefend', emoji="⚔️")
  async def reverbdefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(5, 8), random.randint(4, 6), random.randint(4, 5), random.randint(-5, -2), random.randint(-8, -3)])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    if plusCredits > 0:
      await addCredits(team, abs(plusCredits))
      await addCredits(opposingTeam, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion. Since *Reverb* is active, **{opposingTeam}** also gained **{plusCredits * 2} HP** for their own Mansion", color=0x23AE37))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(description=f"**{team}** defended an attack. However, since *Reverb* is used, your Mansion regained **{abs(plusCredits) * 2}** HP too!", color=0x00FF00))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
    
    elif plusCredits < 0:
      await addCredits(team, plusCredits)
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Defended unsuccessful, self-inflicted damage!", "Attempted defense, ended in disaster!", "Mansion defense failed, caught on fire!", "Counterattack backfired, we're hurt!", "Misfire during defense, we're in trouble!", "Defense faltered, suffered self-damage!", "Guardians' error, we hit ourselves!", "Failed defense, damaged our own team!"]), description=f"{interaction.user.mention} tries counterattacking the [attack]({interaction.message.jump_url}) from **{opposingTeam}**, but ended up dealing **{abs(plusCredits) * 2} damage** on **your own** Mansion instead!", color=0xEF00E4))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(description=f"**{team}** tried to counterattack and but *Reverb* reflected it! They ended up dealing **{abs(plusCredits) * 2}** damage to their own Mansion!", color=0x00FF00))
      await interaction.response.send_message(f"[Counterattack failed!]({msg.jump_url})", ephemeral=True)
        
    await interaction.message.edit(embed=embed, view=ReverbDefend())

class SabotageDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.blurple, custom_id='sabotagedefend', emoji="⚔️")
  async def sabotageDefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(5, 8), random.randint(4, 6), random.randint(-4, -3), random.randint(-8, -4), random.randint(-6, -4), 0])
    realOpposingTeam = interaction.message.embeds[0].description.split('**')[1]
    teamsCopyList = teams.copy()
    teamsCopyList.remove(team.strip())
    teamsCopyList.remove(realOpposingTeam.strip())
    opposingTeam = random.choice(teamsCopyList)
    if plusCredits > 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{realOpposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion.", color=0x23AE37))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
    
    elif plusCredits < 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      await addCredits(opposingTeam, plusCredits-1)
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Our mansion defended and struck back!", "Successful defense and counterattack!", "Mansion secured, and enemies damaged!", "Defended with style, dealt damage too!", "Counteroffensive success!", "Guardians defended and retaliated!", "Strong defense, effective counter!", "Protected home, inflicted damage!", "Our mansion stands, theirs crumbles!", "Survived the attack, hit back harder!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{realOpposingTeam}**. \nHowever, {realOpposingTeam} SABOTAGED **{opposingTeam}**, and the counterattack dealt **{abs(plusCredits-1) * 2} damage** on {opposingTeam.replace('Team ', '')}'s Mansion instead! 🤯\n{team.replace('Team ', '')} also regained **{abs(plusCredits) * 2} HP** for the Mansion.", color=0x18C7E7))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(title=f"🤯 Sabotaged by {realOpposingTeam}", description=f"**{team}** counterattacked on an attack originally by {realOpposingTeam}, but your team received that **{abs(plusCredits-1) * 2}** damage instead!", color=0xFF0000))
      await interaction.client.get_channel(team_channel_dict[realOpposingTeam]).send(embed=discord.Embed(title=f"Successfully sabotaged {opposingTeam}", description=f"**{team}** counterattacked on an attack, but {opposingTeam.replace('Team ', '')}'s Mansion received **{abs(plusCredits-1) * 2}** damage for you!", color=0x00FF00))
      await interaction.response.send_message(f"[Defense and (sabotaged) counterattack success!]({msg.jump_url})", ephemeral=True)
        
    elif plusCredits == 0:
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion breached!", "Defense compromised!", "Intruders infiltrated!", "Security breached!", "Mansion under attack!", "Defense faltered!", "Intruders prevailed!", "Mansion vulnerable!", "Guardians defeated!", "Defense failed!"]), description=f"{interaction.user.mention} failed to defend the [attack]({interaction.message.jump_url}) from **{opposingTeam}**!", color=0x968CAD))
      await interaction.response.send_message(f"[Defense failed!]({msg.jump_url})", ephemeral=True)
    await interaction.message.edit(embed=embed, view=SabotageDefend())
    
class MalaiseDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.grey, custom_id='malaisedefend', emoji="⚔️")
  async def malaiseDefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(3, 5), random.randint(2, 4), random.randint(1, 3), random.randint(-3, -2), 0, 0])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    if plusCredits > 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion.", color=0x23AE37))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
    
    elif plusCredits < 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      await addCredits(opposingTeam, plusCredits-1)
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Our mansion defended and struck back!", "Successful defense and counterattack!", "Mansion secured, and enemies damaged!", "Defended with style, dealt damage too!", "Counteroffensive success!", "Guardians defended and retaliated!", "Strong defense, effective counter!", "Protected home, inflicted damage!", "Our mansion stands, theirs crumbles!", "Survived the attack, hit back harder!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and dealt **{abs(plusCredits-1) * 2} damage** on their Mansion! :tada:\n{team.replace('Team ', '')} also regained **{abs(plusCredits) * 2} HP** for the Mansion.", color=0x18C7E7))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(description=f"**{team}** counterattacked and dealt **{abs(plusCredits-1) * 2}** damage to the Mansion!", color=0xFF0000))
      await interaction.response.send_message(f"[Defense and counterattack success!]({msg.jump_url})", ephemeral=True)
        
    elif plusCredits == 0:
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion breached!", "Defense compromised!", "Intruders infiltrated!", "Security breached!", "Mansion under attack!", "Defense faltered!", "Intruders prevailed!", "Mansion vulnerable!", "Guardians defeated!", "Defense failed!"]), description=f"{interaction.user.mention} failed to defend the [attack]({interaction.message.jump_url}) from **{opposingTeam}**!", color=0x968CAD))
      await interaction.response.send_message(f"[Defense failed!]({msg.jump_url})", ephemeral=True)
    await interaction.message.edit(embed=embed, view=MalaiseDefend())
    
class QuotaDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.grey, custom_id='quotadefend', emoji="⚔️")
  async def quotaDefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    newAttemptsLeft = int(interaction.message.content.split("**")[1]) - 1
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(5, 8), random.randint(4, 6), random.randint(4, 5), random.randint(3, 4), random.randint(-6, -4), 0])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    if plusCredits > 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion secure!", "Defense victorious!", "Intruders repelled!", "Mansion defended!", "Security triumph!", "Successful defense!", "Intruders thwarted!", "Mansion protected!", "Guardians stand strong!", "Defense success!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and regained **{plusCredits * 2} HP** for the Mansion.", color=0x23AE37))
      await interaction.response.send_message(f"[Defense success!]({msg.jump_url})", ephemeral=True)
    
    elif plusCredits < 0:
      totalCredits = await addCredits(team, abs(plusCredits))
      await addCredits(opposingTeam, plusCredits-1)
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Our mansion defended and struck back!", "Successful defense and counterattack!", "Mansion secured, and enemies damaged!", "Defended with style, dealt damage too!", "Counteroffensive success!", "Guardians defended and retaliated!", "Strong defense, effective counter!", "Protected home, inflicted damage!", "Our mansion stands, theirs crumbles!", "Survived the attack, hit back harder!"]), description=f"{interaction.user.mention} defended the [attack]({interaction.message.jump_url}) from **{opposingTeam}** and dealt **{abs(plusCredits-1) * 2} damage** on their Mansion! :tada:\n{team.replace('Team ', '')} also regained **{abs(plusCredits) * 2} HP** for the Mansion.", color=0x18C7E7))
      team_channel_dict = dict(zip(teams, teamchannels))
      await interaction.client.get_channel(team_channel_dict[opposingTeam]).send(embed=discord.Embed(description=f"**{team}** counterattacked and dealt **{abs(plusCredits-1) * 2}** damage to the Mansion!", color=0xFF0000))
      await interaction.response.send_message(f"[Defense and counterattack success!]({msg.jump_url})", ephemeral=True)
        
    elif plusCredits == 0:
      msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion breached!", "Defense compromised!", "Intruders infiltrated!", "Security breached!", "Mansion under attack!", "Defense faltered!", "Intruders prevailed!", "Mansion vulnerable!", "Guardians defeated!", "Defense failed!"]), description=f"{interaction.user.mention} failed to defend the [attack]({interaction.message.jump_url}) from **{opposingTeam}**!", color=0x968CAD))
      await interaction.response.send_message(f"[Defense failed!]({msg.jump_url})", ephemeral=True)
    # --- Defense Attempts --- #
    if newAttemptsLeft != 0:
      messageContent = f":warning: <@&1200241691798536345> *Only **{newAttemptsLeft}** more defense attempts are allowed since `Guardian Quota` is active.*"
      await interaction.message.edit(content=messageContent, embed=embed, view=QuotaDefend())
    else: # No more attempts
      messageContent = f":warning: <@&1200241691798536345> **No** more defense attempts are allowed since `Guardian Quota` is active.*"
      await interaction.message.edit(content=messageContent, embed=embed, view=UnDefend())
    
    
class BreachDefend(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Defend', style=discord.ButtonStyle.grey, custom_id='breachdefend', emoji="⚔️")
  async def breachDefend(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = interaction.message.embeds[0]
    mc = embed.description
    failedAttemptsLeft = int(interaction.message.content.split("**")[1]) - 1
    if str(interaction.user.id) in mc:
      await interaction.response.send_message("You already defended this attack!", ephemeral=True)
      raise Exception("Defended this attack")
    else:
      if mc[-1] == "*":
        embed.description = f"{mc}\n\n> **Defenders:**\n- <@{interaction.user.id}>"
      else:
        embed.description = f"{mc}\n- <@{interaction.user.id}>"
    if (int(time.mktime(interaction.created_at.timetuple())) - int(float(time.mktime(interaction.message.created_at.timetuple())))) > 3600 * 2:
      await interaction.response.send_message("You can only defend attacks initiated within the last 2 hours!", ephemeral=True)
      raise Exception("Attempting to defend an attack too long ago")
    team = teams[teamchannels.index(interaction.channel.id)]
    plusCredits = random.choice([random.randint(5, 8), random.randint(4, 6), random.randint(4, 5), random.randint(3, 4), random.randint(-6, -4), 0])
    opposingTeam = interaction.message.embeds[0].description.split('**')[1]
    msg = await interaction.channel.send(embed=discord.Embed(title=random.choice(["Mansion breached!", "Defense compromised!", "Intruders infiltrated!", "Security breached!", "Mansion under attack!", "Defense faltered!", "Intruders prevailed!", "Mansion vulnerable!", "Guardians defeated!", "Defense failed!"]), description=f"{interaction.user.mention} failed to defend the [attack]({interaction.message.jump_url}) from **{opposingTeam}**!", color=0x968CAD))
    await interaction.response.send_message(f"[Defense failed!]({msg.jump_url})", ephemeral=True)
    # --- Guaranteed Failed Attempts --- #
    if failedAttemptsLeft != 0:
      messageContent = f":warning: <@&1200241691798536345> *The next **{failedAttemptsLeft}** defenses will be a guaranteed fail since `Breach` is active.*"
      await interaction.message.edit(content=messageContent, embed=embed, view=BreachDefend())
    else: # No more guaranted failed attempts
      messageContent = f"<@&1200241691798536345>"
      await interaction.message.edit(content=messageContent, embed=embed, view=Defend())
    
async def joingang(interaction, gang):
  lvl3 = interaction.guild.get_role(949337290969350304)
  lvl5 = interaction.guild.get_role(949336411255996416)
  lvl10 = interaction.guild.get_role(752763116894421072)
  lvl20 = interaction.guild.get_role(752874966919151666)
  lvl35 = interaction.guild.get_role(879629862627835954)
  lvl40 = interaction.guild.get_role(949336415563579522)
  lvl50 = interaction.guild.get_role(759223538779160608)
  lvl69 = interaction.guild.get_role(879629784718663750)
  lvl75 = interaction.guild.get_role(879629786455097344)
  lvl90 = interaction.guild.get_role(949339134273679420)
  lvl100 = interaction.guild.get_role(765485751680892958)
  requiredLevel = [lvl3, lvl5, lvl10, lvl20, lvl35, lvl40, lvl50, lvl69, lvl75, lvl90, lvl100]
  if not any(role in requiredLevel for role in interaction.user.roles):
    await interaction.response.send_message(":x: You are not qualified to join a team yet! You have to be at least **level 3**. \nBe active in chat and you will be level 3 in no time!", ephemeral=True)
    raise Exception()
    
  #if datetime.datetime.now().day >= 15:
    #await interaction.response.send_message(embed=discord.Embed(title="Button disabled until Team Challenge is over", description="You cannot join, switch or leave teams while a Team Challenge is occurring."), ephemeral=True)
    #raise Exception()

  gangRole = discord.utils.get(interaction.guild.roles,name=gang)
  if len(gangRole.members) >= maxlimit:
    await interaction.response.send_message(embed=discord.Embed(title="Team full!", description=f"A team can only consist of **{maxlimit}** members! Right now **{gang}** is already full. Consider joining other teams with available slots! \n\nIf all teams are full, please create a ticket at <#1083745974402420846> and let us know!"), ephemeral=True)
    raise Exception()
    
  msg = "You joined the"
  title = "🎉 Congratulations!"
  alreadyin = False
  for role in interaction.user.roles:
    if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
      if gang.lower() == role.name.lower():
        msg = "You are already in"
        title = "Oops!"
        alreadyin = True
      else:
        await interaction.user.remove_roles(role)
        leavechannel = teamchannels[teams.index(role.name)]
        chn = interaction.client.get_channel(leavechannel)
        await chn.send(embed=discord.Embed(description=f":red_square: {interaction.user.mention} **left** the team. Goodbye~ :wave:", color=0xFF0000))
        msg = f"You left the **{role}** and joined"
        title = "☑ Done!"

  if not alreadyin:
    await interaction.user.add_roles(gangRole)
    joinchannel = teamchannels[teams.index(gangRole.name)]
    chn = interaction.client.get_channel(joinchannel)
    await chn.send(embed=discord.Embed(description=f":green_square: {interaction.user.mention} **joined** the team! Welcome! :hugging:\nMake sure to check out <#1083866771376844881> and say hi to everyone!", color=0x00FF00))
    if datetime.datetime.now().year == 2023 and datetime.datetime.now().month == 1:
      await interaction.user.add_roles(interaction.guild.get_role(1058145940868960256))
  embed=discord.Embed(title=title, description=f"{msg} **{gang}**!\nYou can use `/team leave` to leave your team at anytime!", color=0x0674db)
  embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
  await interaction.response.send_message(embed=embed, ephemeral=True)

    

class TeamSelectionButtons(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Team Mondstadt', style=discord.ButtonStyle.blurple, custom_id='mondstadt')
  async def mondstadt(self, interaction: discord.Interaction, button: discord.ui.Button):
    await joingang(interaction, button.label)

  @discord.ui.button(label='Team Liyue', style=discord.ButtonStyle.blurple, custom_id='liyue')
  async def liyue(self, interaction: discord.Interaction, button: discord.ui.Button):
    await joingang(interaction, button.label)
    
  @discord.ui.button(label='Team Inazuma', style=discord.ButtonStyle.blurple, custom_id='inazuma')
  async def inazuma(self, interaction: discord.Interaction, button: discord.ui.Button):
    await joingang(interaction, button.label)
    
  @discord.ui.button(label='Team Sumeru', style=discord.ButtonStyle.blurple, custom_id='sumeru')
  async def sumeru(self, interaction: discord.Interaction, button: discord.ui.Button):
    await joingang(interaction, button.label)
    
  @discord.ui.button(label='Team Fontaine', style=discord.ButtonStyle.blurple, custom_id='fontaine')
  async def fontaine(self, interaction: discord.Interaction, button: discord.ui.Button):
    await joingang(interaction, button.label)
    
  @discord.ui.button(label='Team Natlan', style=discord.ButtonStyle.blurple, custom_id='natlan')
  async def fontaine(self, interaction: discord.Interaction, button: discord.ui.Button):
    await joingang(interaction, button.label)
  
    
  @discord.ui.button(label='Check my Team', style=discord.ButtonStyle.grey, custom_id='checkteam')
  async def checkteam(self, interaction: discord.Interaction, button: discord.ui.Button):
    for role in interaction.user.roles:
      if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
        embed=discord.Embed(title=f"{role.name} Information", description="You can use `/team join` to join a team!", color=0x0674db)
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Created At", value=f"<t:{int(float(time.mktime(role.created_at.timetuple())))}:R>", inline=True)
        ref = db.reference("/Team Trophy")
        teamtrophy = ref.get()
    
        for key, val in teamtrophy.items():
          if val['Team Name'] == role.name:
            trophy = val['Team Trophy']
            break

        embed.add_field(name="Team Trophy", value=trophy, inline=True)

        leader = leaders[teams.index(role.name)]
        leaderRole = leaderRoles[teams.index(role.name)]
        embed.add_field(name="Leader", value=f"<@{leader}>", inline=True)
        embed.add_field(name="Leader's Role", value=leaderRole, inline=True)

        # desc = ""
        # for member in role.members:
        #   desc = f"{desc}- {member.mention} `({member.id})`\n"
        # memberlist=discord.Embed(title=f"List of members", description=desc, color=0x0674db)
        # memberlist.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embeds=[embed], ephemeral=True)
        raise Exception()
        
    await interaction.response.send_message(f"You aren't in a team! Click the blue buttons to join a team first!", ephemeral=True)
        
    
  @discord.ui.button(label='Become a Mansion Protector', style=discord.ButtonStyle.green, custom_id='mansionprotector')
  async def mansionprotector(self, interaction: discord.Interaction, button: discord.ui.Button):
    
    team = None
    alreadyHave = False
    for role in interaction.user.roles:
      if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
        team = role.name
      if "mansion protector" in role.name.lower():
        alreadyHave = True
    
    if team is None:
      await interaction.response.send_message(f"You aren't in a team! Join a team first by clicking on the respective blue button!", ephemeral=True)
      raise Exception("Not in team")
    
    role = discord.utils.get(interaction.guild.roles,name="Mansion Protector")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You have **removed** the <@&1200241691798536345> role, and you will no longer be notified for attacks and reminded for dailies.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1200241691798536345> role, and you will be notified for every attack initiated on your Team, as well as reminded for getting daily rewards for your Team!", ephemeral=True)

async def check(interaction, check_date=False):
  pass
  lvl3 = interaction.guild.get_role(949337290969350304)
  lvl5 = interaction.guild.get_role(949336411255996416)
  lvl10 = interaction.guild.get_role(752763116894421072)
  lvl20 = interaction.guild.get_role(752874966919151666)
  lvl35 = interaction.guild.get_role(879629862627835954)
  lvl40 = interaction.guild.get_role(949336415563579522)
  lvl50 = interaction.guild.get_role(759223538779160608)
  lvl69 = interaction.guild.get_role(879629784718663750)
  lvl75 = interaction.guild.get_role(879629786455097344)
  lvl90 = interaction.guild.get_role(949339134273679420)
  lvl100 = interaction.guild.get_role(765485751680892958)
  requiredLevel = [lvl3, lvl5, lvl10, lvl20, lvl35, lvl40, lvl50, lvl69, lvl75, lvl90, lvl100]
  if interaction.guild.id != 717029019270381578:
    await interaction.response.send_message(embed=discord.Embed(title="Command unavailable in this server", description="Join our [support server](https://discord.gg/traveler) and use it there!"), ephemeral=True)
    raise Exception()
  elif not any(role in requiredLevel for role in interaction.user.roles):
    await interaction.response.send_message(":x: You are not qualified to join a team yet! You have to be at least **level 3**. \nBe active in chat and you will be level 3 in no time! When you are ready, you can join a team at <#1083866201773588571>.", ephemeral=True)
    raise Exception()
  #elif datetime.datetime.now().day >= 15 and check_date:
    #await interaction.response.send_message(embed=discord.Embed(title="Command disabled until Team Challenge is over", description="You cannot join, switch or leave teams while a Team Challenge is occurring."), ephemeral=True)
    #raise Exception()
    
async def addMora(userID, addMora):
  ref = db.reference("/Team Mora")
  randomevents = ref.get()
  
  ogmora = 0
  try:
    for key, val in randomevents.items():
      if val['User ID'] == userID:
        ogmora = val['Mora']
        db.reference('/Team Mora').child(key).delete()
        break
  except Exception:
    pass
  newmora = ogmora + addMora
  data = {
    "Data": {
      "User ID": userID,
      "Mora": newmora,
    }
  }

  for key, value in data.items():
    ref.push().set(value)
  
  return newmora

async def hasWeaponWhenUse(interaction, target):
  weap = db.reference("/Team Weapons")
  weaponDatabase = weap.get()
  hasWeapon = False
  for key, val in weaponDatabase.items():
    if val['User ID'] == interaction.user.id:
      try:
        x = val['Weapons'].index(target)
        quantity = val['Quantity'][x]
        if quantity >= 1:
          hasWeapon = True
      except Exception:
        pass
  return hasWeapon
    
async def addCredits(team, addCredits):
  ref2 = db.reference("/Team Credits")
  randomevents = ref2.get()
  
  ogcredits = 0
  try:
    for key, val in randomevents.items():
      if val['Team'] == team:
        ogcredits = val['Credits']
        db.reference('/Team Credits').child(key).delete()
        break
  except Exception:
    pass
  newcredits = ogcredits + addCredits
  if newcredits <= 0:
    newcredits = 0
  data = {
    "Data": {
      "Team": team,
      "Credits": newcredits,
    }
  }

  for key, value in data.items():
    ref2.push().set(value)
  
  return newcredits

# First item is Level 1, last item is Level 50
creditsRequiredForEachLevelItself = [0, 20, 23, 26, 30, 34, 40, 46, 53, 61, 70, 80, 93, 107, 123, 141, 162, 187, 215, 247, 284, 327, 376, 432, 497, 572, 658, 757, 870, 1001, 1151, 1324, 1522, 1751, 2013, 2316, 2663, 3063, 3522, 4050, 4658, 5357, 6160, 7084, 8147, 9369, 10775, 12391, 14250, 16388]
totalCreditsRequiredForEachLevel = [
    0, 20, 43, 69, 99, 133, 173, 219, 272, 333,
    403, 483, 576, 683, 806, 947, 1109, 1296, 1511, 1758,
    2042, 2369, 2745, 3177, 3674, 4246, 4904, 5661, 6531, 7532,
    8683, 10007, 11529, 13280, 15293, 17609, 20272, 23335, 26857,
    30907, 35565, 40922, 47082, 54166, 62313, 71682, 82457, 94848,
    109098, 125486
]
HPGainForEachLevel = [0, 40, 46, 52, 60, 68, 80, 92, 106, 122, 140, 160, 186, 214, 246, 282, 324, 374, 430, 494, 568, 654, 752, 864, 994, 1144, 1316, 1514, 1740, 2002, 2302, 2648, 3044, 3502, 4026, 4632, 5326, 6126, 7044, 8100, 9316, 10714, 12320, 14168, 16294, 18738, 21550, 24782, 28500, 32776] # *2 of creditsRequiredForEachLevelItself
TotalHPOfEachLevel = [50, 90, 136, 188, 248, 316, 396, 488, 594, 716, 856, 1016, 1202, 1416, 1662, 1944, 2268, 2642, 3072, 3566, 4134, 4788, 5540, 6404, 7398, 8542, 9858, 11372, 13112, 15114, 17416, 20064, 23108, 26610, 30636, 35268, 40594, 46720, 53764, 61864, 71180, 81894, 94214, 108382, 124676, 143414, 164964, 189746, 218246, 251022] # TotalHPOfEachLevel - 50 = totalCreditsRequiredForEachLevel * 2

def get_level(total_credits):
    # Find the level corresponding to the total credits
    for level, credits_required in enumerate(totalCreditsRequiredForEachLevel):
        if total_credits < credits_required:
            return level  # Return the previous level since total_credits are not yet reached the next level

    # If the total_credits are greater than or equal to the last level, return the last level
    return len(totalCreditsRequiredForEachLevel)

#def are_same_utc_days(timestamp1, timestamp2):
    #date1 = datetime.datetime.utcfromtimestamp(timestamp1).replace(tzinfo=datetime.timezone.utc).date()
    #date2 = datetime.datetime.utcfromtimestamp(timestamp2).replace(tzinfo=datetime.timezone.utc).date()
    #return date1 == date2
def is_same_day_in_utc(timestamp1, timestamp2):
    # Convert timestamps to datetime objects in UTC
    dt1_utc = datetime.datetime.utcfromtimestamp(timestamp1).replace(tzinfo=datetime.timezone.utc)
    dt2_utc = datetime.datetime.utcfromtimestamp(timestamp2).replace(tzinfo=datetime.timezone.utc)

    # Check if both datetimes have the same date
    return dt1_utc.date() == dt2_utc.date()

def next_utc_midnight():
    current_utc_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).date()
    next_midnight = datetime.datetime(current_utc_date.year, current_utc_date.month, current_utc_date.day, 0, 0, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=1)
    return int(next_midnight.timestamp())

async def weapon_purchase_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    allWeapons = [["Especial Fates", 5000], ["Shadow Realm", 10000], ["50% Boost", 20000], ["Malaise", 20000], ["Breach", 25000], ["Sabotage", 25000], ["Guardian Quota", 30000], ["Vengeance", 30000], ["Silent Enemies", 50000], ["Reverb", 60000], ["Complete Collapse", 80000]]
    
    ref = db.reference("/Team Mora")
    teammora = ref.get()
    mora = 0
    for key, val in teammora.items():
      if val['User ID'] == interaction.user.id:
        mora = val['Mora']
        break
    availableWeapons = []
    for xweapon in [["Especial Fates", 5000], ["Shadow Realm", 10000], ["50% Boost", 20000], ["Malaise", 20000], ["Breach", 25000], ["Sabotage", 25000], ["Guardian Quota", 30000], ["Vengeance", 30000], ["Silent Enemies", 50000], ["Reverb", 60000], ["Complete Collapse", 80000]]:
      if xweapon[1] <= mora:
        availableWeapons.append(xweapon)
    
    print(availableWeapons)
        
    return [
        app_commands.Choice(name=f"{availableWeapon[0]} ({availableWeapon[1]} Mora)", value=availableWeapon[0])
        for availableWeapon in availableWeapons if current.lower() in availableWeapon[0].lower()
    ]

async def weapon_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    ref = db.reference("/Team Weapons")
    daily = ref.get()
    weapons = []
    for key, val in daily.items():
      if val['User ID'] == interaction.user.id:
        #print(val['Weapons'])
        try:
          for x in range(len(val['Weapons'])):
            weapons.append([val['Weapons'][x], val['Quantity'][x]])
        except Exception:
          pass
        
    return [
        app_commands.Choice(name=f"{weapon[0]} ({weapon[1]} left)", value=weapon[0])
        for weapon in weapons if current.lower() in weapon[0].lower()
    ]


@app_commands.guild_only()
class Team(commands.GroupCog, name="team"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "daily",
    description = "Gets daily reward of a team"
  )
  async def team_daily(
    self,
    interaction: discord.Interaction
  ) -> None:
    allWeapons = [["Especial Fates", 5000], ["Shadow Realm", 10000], ["50% Boost", 20000], ["Malaise", 20000], ["Breach", 25000], ["Sabotage", 25000], ["Guardian Quota", 30000], ["Vengeance", 30000], ["Silent Enemies", 50000], ["Reverb", 60000], ["Complete Collapse", 80000]]
    await interaction.response.defer()
    
    team = None
    if interaction.guild.id == 717029019270381578:
      for role in interaction.user.roles:
        if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
          team = role.name
    else:
      await interaction.followup.send(embed=discord.Embed(title="Command unavailable in this server", description="Join our [support server](https://discord.gg/traveler) and use it there!"), ephemeral=True)
      raise Exception()
    
    if team is None:
      await interaction.followup.send(f"You aren't in a team! Join a team first!", ephemeral=True)
      raise Exception("Not in team")
        
    ref = db.reference("/Team Daily")
    daily = ref.get()
  
    ogtimestamp = 1
    for key, val in daily.items():
      if val['User ID'] == interaction.user.id:
        ogtimestamp = val['Timestamp']
        #t = int(float(time.mktime(interaction.created_at.timetuple())))
        t = int(time.mktime(datetime.datetime.now().timetuple()))
        #print(ogtimestamp)
        #print(t)
        if is_same_day_in_utc(ogtimestamp, t):
          embed = discord.Embed(description=f"You already got your daily rewards! Try again <t:{next_utc_midnight()}:R>.", color=0x1DBCEB)
          await interaction.followup.send(embed=embed)
          raise Exception("Daily rewards already obtained.")

        db.reference('/Team Daily').child(key).delete()
        break
    
    data = {
      "Data": {
        "User ID": interaction.user.id,
        "Timestamp": int(time.mktime(datetime.datetime.now().timetuple())),
      }
    }

    for key, value in data.items():
      ref.push().set(value)
    
    mora = random.randint(4000, 6000)
    newmora = await addMora(interaction.user.id, mora)
    credits = random.randint(20, 30)
    newcredits = await addCredits(team, credits)
    message = ""
    #if True:
    if random.randint(1, 100) in [3, 6, 23, 44, 98]: # 5% Chance of Getting a Random Weapon
      weaponsList = allWeapons
      weaponsList.pop(0)
      allWeapon = random.choice(weaponsList)
      weapon = allWeapon[0]
      #cost = allWeapon[1]
      ref = db.reference("/Team Weapons")
      daily = ref.get()
      weapons = []
      for key, val in daily.items():
        if val['User ID'] == interaction.user.id:
          try:
            for i in range(len(val['Weapons'])):
              weapons.append([val['Weapons'][i], val['Quantity'][i]])
          except Exception:
            pass
          db.reference('/Team Weapons').child(key).delete()
      #print(weapons)
      found = False
      for xweapon in weapons:
        if xweapon[0] == weapon:
          xweapon[1] = xweapon[1] + 1
          found = True
      if not(found):
        weapons.append([weapon, 1])
      y = []
      z = []
      for i in weapons:
        y.append(i[0])
        z.append(i[1])
      data = {
        "Data": {
          "User ID": interaction.user.id,
          "Weapons": y,
          "Quantity": z
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      message = f"### <a:tada:1227425729654820885> It's your lucky day! \n## You got **`{weapon}`** for **FREE**! <a:moneydance:1227425759077859359>\nYou can use the weapon in </team attack:1254927191037317148> at anytime!\n\n"
    
    earningFate = random.choices([1, 2, 3, 0], [0.50, 0.15, 0.05, 0.30])
    earningFate = earningFate[0]
    ref = db.reference("/Team Fates")
    teamfates = ref.get()
    ogfate = 0
    try:
      for key, val in teamfates.items():
        if val['User ID'] == interaction.user.id:
          ogfate = val['Especial Fates']
          db.reference('/Team Fates').child(key).delete()
          break
    except Exception:
      pass
    newfate = ogfate + earningFate
    data = {
      "Data": {
        "User ID": interaction.user.id,
        "Especial Fates": newfate,
      }
    }
    for key, value in data.items():
      ref.push().set(value)
    if earningFate != 0:
      fateMsg = f"\n*By the way, the sky dropped <:especial_fates:1256349040761769985> **{earningFate}** for you.*"
    else:
      fateMsg = ""
    
    embed = discord.Embed(title="Daily Reward", description=f"{message}<:MORA:953918490421641246> **{mora}** was added to your inventory.\nYou also obtained <:PRIMOGEM:939086760296738879> **{credits}** for your team!{fateMsg}", color=0x1DBCEB)
    embed.add_field(name="Current Mora", value=f"<:MORA:953918490421641246> {newmora}")
    embed.add_field(name=f"{team}'s Credits", value=f"<:PRIMOGEM:939086760296738879> {newcredits}")
    embed.add_field(name=f"Mansion Level", value=f":house: Lvl {get_level(newcredits)}")
    newWeapon = ""
    weapons = []
    ref = db.reference("/Team Weapons")
    daily = ref.get()
    for key, val in daily.items():
      if val['User ID'] == interaction.user.id:
        #print(val['Weapons'])
        try:
          for x in range(len(val['Weapons'])):
            weapons.append([val['Weapons'][x], val['Quantity'][x]])
        except Exception:
          pass
    for weapon in weapons:
      newWeapon = f"{newWeapon}<:Reply:950301070456942622> {weapon[0]} ({weapon[1]} left)\n"
    if newWeapon != "":
      embed.add_field(name="Your Weapon Inventory", value=newWeapon)
    else:
      embed.add_field(name="Your Weapon Inventory", value="Empty *(Use </team purchase:1254927191037317148> to buy some)*")
    
    embed.add_field(name="Total Fates", value=f"<:especial_fates:1256349040761769985> {newfate}")
    
    try:
      embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url, url=f"https://discord.com/users/{interaction.user.id}")
    except Exception:
      embed.set_author(name=interaction.user.name, url=f"https://discord.com/users/{interaction.user.id}")
    embed.set_footer(text=random.choice(["Reminder: Use /team purchase to strengthen your attack!", "Tip: You can attack a mansion every 12 hours.", "Tip: You cannot attack the same team consecutively.", "Tip: The weapon Malaise weakens the opposing team's defense.", "Tip: You can only use your weapon once. Make sure to refill your inventory afterwards!", "Tip: One wish requires 3 Especial Fates."]))
    await interaction.followup.send(embed=embed)

  @app_commands.command(
    name = "wish",
    description = "Wishes for a weapon"
  )
  async def team_wish(
    self,
    interaction: discord.Interaction,
  ) -> None:
    allWeapons = [["Especial Fates", 5000], ["Shadow Realm", 10000], ["50% Boost", 20000], ["Malaise", 20000], ["Breach", 25000], ["Sabotage", 25000], ["Guardian Quota", 30000], ["Vengeance", 30000], ["Silent Enemies", 50000], ["Reverb", 60000], ["Complete Collapse", 80000]]
    #await interaction.response.defer()
    team = None
    if interaction.guild.id == 717029019270381578:
      for role in interaction.user.roles:
        if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
          team = role.name
    else:
      await interaction.followup.send(embed=discord.Embed(title="Command unavailable in this server", description="Join our [support server](https://discord.gg/traveler) and use it there!"), ephemeral=True)
      raise Exception()
    
    ref = db.reference("/Team Pity")
    teampity = ref.get()
    ogpity = newpity = 0
    try:
      for key, val in teampity.items():
        if val['User ID'] == interaction.user.id:
          ogpity = val['Pity']
          break
    except Exception:
      pass
    
    ref = db.reference("/Team Fates")
    teamfates = ref.get()
    ogfate = 0
    try:
      for key, val in teamfates.items():
        if val['User ID'] == interaction.user.id:
          ogfate = val['Especial Fates']
          break
    except Exception:
      pass

    if ogfate >= 3:
      randomColor = discord.Colour.random()
      embed = discord.Embed(color=randomColor)
      embed.set_image(url="https://media.discordapp.net/attachments/1026968305208131645/1256356714240802936/wish.gif")
      await interaction.response.send_message(embed=embed)
      
      try:
        for key, val in teamfates.items():
          if val['User ID'] == interaction.user.id:
            db.reference('/Team Fates').child(key).delete()
            break
      except Exception:
        pass
      newfate = ogfate - 3
      data = {
        "Data": {
          "User ID": interaction.user.id,
          "Especial Fates": newfate,
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      drop_rates = {
        0: [("Big Mora Drop", 0.45), ("Mega Mora Drop", 0.30), ("Mystic Weapons", 0.20), ("Celestial Weapons", 0.04), ("Radiant Weapons", 0.01)],
        1: [("Big Mora Drop", 0.42), ("Mega Mora Drop", 0.28), ("Mystic Weapons", 0.22), ("Celestial Weapons", 0.06), ("Radiant Weapons", 0.02)],
        2: [("Big Mora Drop", 0.40), ("Mega Mora Drop", 0.26), ("Mystic Weapons", 0.24), ("Celestial Weapons", 0.07), ("Radiant Weapons", 0.03)],
        3: [("Big Mora Drop", 0.38), ("Mega Mora Drop", 0.24), ("Mystic Weapons", 0.26), ("Celestial Weapons", 0.08), ("Radiant Weapons", 0.04)],
        4: [("Big Mora Drop", 0.36), ("Mega Mora Drop", 0.22), ("Mystic Weapons", 0.28), ("Celestial Weapons", 0.09), ("Radiant Weapons", 0.05)],
        5: [("Big Mora Drop", 0.30), ("Mega Mora Drop", 0.20), ("Mystic Weapons", 0.30), ("Celestial Weapons", 0.14), ("Radiant Weapons", 0.06)],
        6: [("Big Mora Drop", 0.25), ("Mega Mora Drop", 0.15), ("Mystic Weapons", 0.32), ("Celestial Weapons", 0.18), ("Radiant Weapons", 0.10)],
        7: [("Big Mora Drop", 0.20), ("Mega Mora Drop", 0.10), ("Mystic Weapons", 0.32), ("Celestial Weapons", 0.22), ("Radiant Weapons", 0.16)],
        8: [("Big Mora Drop", 0.17), ("Mega Mora Drop", 0.10), ("Mystic Weapons", 0.33), ("Celestial Weapons", 0.22), ("Radiant Weapons", 0.18)],
        9: [("Big Mora Drop", 0.10), ("Mega Mora Drop", 0.05), ("Mystic Weapons", 0.27), ("Celestial Weapons", 0.25), ("Radiant Weapons", 0.33)],
        10: [("Big Mora Drop", 0.05), ("Mega Mora Drop", 0.02), ("Mystic Weapons", 0.23), ("Celestial Weapons", 0.20), ("Radiant Weapons", 0.50)],
        11: [("Big Mora Drop", 0), ("Mega Mora Drop", 0), ("Mystic Weapons", 0), ("Celestial Weapons", 0), ("Radiant Weapons", 1)],
      }
      items = {
        "Big Mora Drop": f"{random.randint(1250, 1750)} Mora", # 1500
        "Mega Mora Drop": f"{random.randint(3000, 4000)} Mora", # 3500
        "Mystic Weapons": random.choice([weapon for weapon, value in allWeapons if 10000 <= value <= 20000]),
        "Celestial Weapons": random.choice([weapon for weapon, value in allWeapons if 20000 < value < 50000]),
        "Radiant Weapons": random.choice([weapon for weapon, value in allWeapons if value >= 50000]),
      }
      categories = drop_rates[ogpity]
      choices, weights = zip(*categories)
      drop = random.choices(choices, weights)[0]
      item = items[drop]
      print(drop)
      if drop == "Radiant Weapons":
        newpity = 0
      else:
        newpity = ogpity + 1
      ref = db.reference("/Team Pity")
      teampity = ref.get()
      try:
        for key, val in teampity.items():
          if val['User ID'] == interaction.user.id:
            db.reference('/Team Pity').child(key).delete()
            break
      except Exception:
        pass
      data = {
        "Data": {
          "User ID": interaction.user.id,
          "Pity": newpity,
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      if "Mora" in item:
        newmora = await addMora(interaction.user.id, int(item.split(" ")[0]))
        embed = discord.Embed(description=f"## <a:moneydance:1227425759077859359> You got **`{item}`**!", color=randomColor)
        embed.add_field(name="Current Mora", value=f"<:MORA:953918490421641246> {newmora}")
      else:
        ref = db.reference("/Team Weapons")
        daily = ref.get()
        weapons = []
        for key, val in daily.items():
          if val['User ID'] == interaction.user.id:
            try:
              for i in range(len(val['Weapons'])):
                weapons.append([val['Weapons'][i], val['Quantity'][i]])
            except Exception:
              pass
            db.reference('/Team Weapons').child(key).delete()
        #print(weapons)
        found = False
        for xweapon in weapons:
          if xweapon[0] == item:
            xweapon[1] = xweapon[1] + 1
            found = True
        if not(found):
          weapons.append([item, 1])
        y = []
        z = []
        for i in weapons:
          y.append(i[0])
          z.append(i[1])
        data = {
          "Data": {
            "User ID": interaction.user.id,
            "Weapons": y,
            "Quantity": z
          }
        }
        for key, value in data.items():
          ref.push().set(value)
        
        newWeapon = ""
        weapons = []
        ref = db.reference("/Team Weapons")
        daily = ref.get()
        for key, val in daily.items():
          if val['User ID'] == interaction.user.id:
            #print(val['Weapons'])
            try:
              for x in range(len(val['Weapons'])):
                weapons.append([val['Weapons'][x], val['Quantity'][x]])
            except Exception:
              pass
        for weapon in weapons:
          newWeapon = f"{newWeapon}<:Reply:950301070456942622> {weapon[0]} ({weapon[1]} left)\n"
    
        embed = discord.Embed(description=f"## <a:tada:1227425729654820885> You got **`{item}`**! <a:tada:1227425729654820885>", color=randomColor)
        embed.add_field(name="Your Weapon Inventory", value=f"{newWeapon}")
      await asyncio.sleep(5)
      #print("Done sleeping")
      embed.set_author(name=f"Drop: {drop}")
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.edit_original_response(embed=embed)
      print(f"--> {interaction.user.name} ({interaction.user.id}) got **{item}** (Drop: {drop}). \n*Their pity value was `{ogpity}`. It is now `{newpity}`*")
    else:
      await interaction.response.send_message("You don't have enough Fates to wish. You need at least <:especial_fates:1256349040761769985> **3** Especial Fates.\n*You can find Fates in </team daily:1254927191037317148>, or buy purchasing them using </team purchase:1254927191037317148>.*", ephemeral=True)
      raise Exception("Not enough Fates")

  @app_commands.command(
    name = "attack",
    description = "Attack a team every 12 hours!"
  )
  @app_commands.autocomplete(weapon=weapon_autocomplete)
  @app_commands.describe(
    team = "The team you want to attack",
    weapon = "Use any weapons purchased from /team purchase"
  )
  @app_commands.choices(team=[
      app_commands.Choice(name="Team Mondstadt", value="Team Mondstadt"),
      app_commands.Choice(name="Team Liyue", value="Team Liyue"),
      app_commands.Choice(name="Team Inazuma", value="Team Inazuma"),
      app_commands.Choice(name="Team Sumeru", value="Team Sumeru"),
      app_commands.Choice(name="Team Fontaine", value="Team Fontaine"),
      app_commands.Choice(name="Team Natlan", value="Team Natlan"),
  ])
  async def team_attack(
    self,
    interaction: discord.Interaction,
    team: app_commands.Choice[str],
    weapon: str = None
  ) -> None:
    allWeapons = [["Especial Fates", 5000], ["Shadow Realm", 10000], ["50% Boost", 20000], ["Malaise", 20000], ["Breach", 25000], ["Sabotage", 25000], ["Guardian Quota", 30000], ["Vengeance", 30000], ["Silent Enemies", 50000], ["Reverb", 60000], ["Complete Collapse", 80000]]
    await interaction.response.defer(ephemeral=True)
    attackFromTeam = None
    if interaction.guild.id == 717029019270381578:
      for role in interaction.user.roles:
        if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
          attackFromTeam = role.name
    else:
      await interaction.followup.send(embed=discord.Embed(title="Command unavailable in this server", description="Join our [support server](https://discord.gg/traveler) and use it there!"), ephemeral=True)
      raise Exception()
    
    if attackFromTeam is None:
      await interaction.followup.send(f"You aren't in a team! Join a team first!", ephemeral=True)
      raise Exception("Not in team")
    
    attackToTeam = discord.utils.get(interaction.guild.roles,name=str(team.value)).name
    if (attackToTeam == attackFromTeam):
      embed = discord.Embed(description=f"Why would you attack your own team smh", color=0xFF0000)
      await interaction.followup.send(embed=embed)
      raise Exception("Attack their own team smh")
    
    dmgInTermsOfCredits = random.randint(20,30)
    silentEnemies = malaise = guardianQuota = sabotage = reverb = shadowRealm = breach = completecollapse = False
    if weapon == "50% Boost":
      hasWeapon = await hasWeaponWhenUse(interaction, "50% Boost")
      if hasWeapon:
        dmgInTermsOfCredits = int(dmgInTermsOfCredits * 1.5)
    elif weapon == "Shadow Realm":
      hasWeapon = await hasWeaponWhenUse(interaction, "Shadow Realm")
      if hasWeapon:
        shadowRealm = True
    elif weapon == "Silent Enemies":
      hasWeapon = await hasWeaponWhenUse(interaction, "Silent Enemies")
      if hasWeapon:
        silentEnemies = True
    elif weapon == "Malaise":
      hasWeapon = await hasWeaponWhenUse(interaction, "Malaise")
      if hasWeapon:
        malaise = True
    elif weapon == "Guardian Quota":
      hasWeapon = await hasWeaponWhenUse(interaction, "Guardian Quota")
      if hasWeapon:
        guardianQuota = True
    elif weapon == "Breach":
      hasWeapon = await hasWeaponWhenUse(interaction, "Breach")
      if hasWeapon:
        breach = True
    elif weapon == "Vengeance":
      hasWeapon = await hasWeaponWhenUse(interaction, "Vengeance")
      if hasWeapon:
        ref = db.reference("/Team Attack")
        daily = ref.get()
        ogtimestamp = 1
        found = False
        for key, val in daily.items():
          correctTeam = False
          thisMember = interaction.guild.get_member(val['User ID'])
          if thisMember == None:
            continue
          for memberRole in thisMember.roles:
            if memberRole.name == attackToTeam:
              correctTeam = True
              break
          ogtimestamp = val['Timestamp']
          timeNow = int(time.mktime(datetime.datetime.now().timetuple()))
          if val['Last Attack To'] == attackFromTeam and correctTeam and (timeNow - ogtimestamp) <= (7200): # 2 hours
            found = True
            print(val['User ID']) # <-----------
            break
          else:
            continue
        if found:
          dmgInTermsOfCredits = int(dmgInTermsOfCredits * 2)
        else:
          embed = discord.Embed(title="Warning", description=f"You attempted to use `Vengeance` in an attack, but `{attackToTeam}` did not attack your team for the past 2 hours. We have terminated the attack for you to prevent you from wasting your weapon.", color=0xFFFF00)
          await interaction.followup.send(embed=embed)
          raise Exception("Wrong usage of Vengeance weapon.")
    elif weapon == "Sabotage":
      hasWeapon = await hasWeaponWhenUse(interaction, "Sabotage")
      if hasWeapon:
        sabotage = True
    elif weapon == "Reverb":
      hasWeapon = await hasWeaponWhenUse(interaction, "Reverb")
      if hasWeapon:
        reverb = True
    elif weapon == "Complete Collapse":
      hasWeapon = await hasWeaponWhenUse(interaction, "Complete Collapse")
      if hasWeapon:
        completecollapse = True
        ref2 = db.reference("/Team Credits")
        credits = ref2.get()
        ogcredits = 0
        try:
          for key, val in credits.items():
            if val['Team'] == attackToTeam:
              ogcredits = val['Credits']
              break
        except Exception:
          pass
        currentLevel = get_level(ogcredits)
        print(currentLevel)
        currentHP = ogcredits * 2
        print(currentHP)
        levelBaseHP = TotalHPOfEachLevel[currentLevel - 1]
        print(levelBaseHP)
        dmgInTermsOfCredits = int((currentHP - levelBaseHP) / 2)
        print(dmgInTermsOfCredits)
    
    dmgInTermsOfHP = dmgInTermsOfCredits * 2
    print(dmgInTermsOfHP)
    team_channel_dict = dict(zip(teams, teamchannels))
    
    #print(f"{dmgInTermsOfCredits} deducted from {attackToTeam}")
    embed = discord.Embed(title=':door: Attack Incoming!', description=f"### {attackToTeam.replace('Team ', '')} is under attack by **{attackFromTeam}**\n*Your Team Mansion has lost **{dmgInTermsOfHP} HP**, but you can defend to regain HP!*", color=0xFFD700)
    if weapon != None:
      legit = False
      for allWeapon in allWeapons:
        if allWeapon[0] == weapon:
          legit = True
      if legit and hasWeapon:
        embed.add_field(name=f"Add-ons Used by {attackFromTeam.replace('Team ', '')}", value=weapon)
      elif not(legit):
        await interaction.followup.send("Invalid weapon!")
        raise Exception("Invalid weapon")
        
    ref = db.reference("/Team Attack")
    daily = ref.get()
    ogtimestamp = 1
    for key, val in daily.items():
      if val['User ID'] == interaction.user.id:
        ogtimestamp = val['Timestamp']
        t = int(time.mktime(datetime.datetime.now().timetuple()))
        if ((t - ogtimestamp) < (3600*12)):
          embed = discord.Embed(description=f"You already attacked a team in the last 12 hours! Try again <t:{ogtimestamp + (3600*12)}:R>.", color=0x1DBCEB)
          await interaction.followup.send(embed=embed)
          raise Exception("Already attacked.")
        if (val['Last Attack To'] == attackToTeam):
          embed = discord.Embed(description=f":x: You cannot attack the **{attackToTeam}** consecutively! \nAttack other teams instead! <:Ayato_sword:999900050350153789>", color=0xFF0000)
          await interaction.followup.send(embed=embed)
          raise Exception("Attacking Same Team")
        db.reference('/Team Attack').child(key).delete()
        break
    data = {
      "Data": {
        "User ID": interaction.user.id,
        "Timestamp": int(time.mktime(datetime.datetime.now().timetuple())),
        "Last Attack To": attackToTeam
      }
    }
    for key, value in data.items():
      ref.push().set(value)
    
    deductedCredits = await addCredits(attackToTeam, -dmgInTermsOfCredits)
    embed.add_field(name=f"Mansion Level", value=f":house: Lvl {get_level(deductedCredits)}")
    if silentEnemies:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content="*:warning: You cannot defend this attack since `Silent Enemies` is active.*", embed=embed, view=UnDefend())
    elif malaise:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content=":warning: <@&1200241691798536345> *Defenses are weaker than usual since `Malaise` is active.*", embed=embed, view=MalaiseDefend())
    elif guardianQuota:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content=":warning: <@&1200241691798536345> *Only **3** more defense attempts are allowed since `Guardian Quota` is active.*", embed=embed, view=QuotaDefend())
    elif breach:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content=":warning: <@&1200241691798536345> *The next **3** defenses will be a guaranteed fail since `Breach` is active.*", embed=embed, view=BreachDefend())
    elif sabotage:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content="<@&1200241691798536345>", embed=embed, view=SabotageDefend())
    elif reverb:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content="<@&1200241691798536345>", embed=embed, view=ReverbDefend())
    elif shadowRealm:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content=":warning: <@&1200241691798536345> *No counterattacks can be made since `Shadow Realm` is active.*", embed=embed, view=ShadowRealmDefend())
    elif completecollapse:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content="🚨 <@&1200241691798536345> *Your team is in critical condition since `Complete Collapse` is active. **Your defenses, however, will be `x10` stronger. ***", embed=embed, view=CollapseDefend())
    else:
      await interaction.client.get_channel(team_channel_dict[attackToTeam]).send(content="<@&1200241691798536345>", embed=embed, view=Defend())
    
    embed = discord.Embed(title=':crossed_swords: Attack Launched! :crossed_swords:', description=f"{interaction.user.mention} attacked **{attackToTeam}** and dealt **{dmgInTermsOfHP} damage** on their Mansion HP.", color=0xCC5500)
    embed.add_field(name=f"Add-ons Used", value=weapon)
    embed.add_field(name=f"{attackToTeam.replace('Team ', '')}'s Mansion Level", value=f"Lvl {get_level(deductedCredits)}")
    
    if weapon != None:
      ref = db.reference("/Team Weapons")
      daily = ref.get()
      weapons = []
      for key, val in daily.items():
        if val['User ID'] == interaction.user.id:
          #print(val['Weapons'])
          for x in range(len(val['Weapons'])):
            weapons.append([val['Weapons'][x], val['Quantity'][x]])
          db.reference('/Team Weapons').child(key).delete()
      #print(weapons)
      remove = None
      for xweapon in weapons:
        if xweapon[0] == weapon: # If weapon name is weapon
          xweapon[1] = xweapon[1] - 1 # Remove 1 from quantity
          if xweapon[1] == 0: # If then none left, remove weapon
            remove = xweapon
          break
      if remove is not None:
        weapons.remove(remove)
        #print(f"Removed {remove}")
        
      y = []
      z = []
      for x in weapons:
        y.append(x[0])
        z.append(x[1])
      data = {
        "Data": {
          "User ID": interaction.user.id,
          "Weapons": y,
          "Quantity": z
        }
      }

      for key, value in data.items():
        ref.push().set(value)
    
    ref = db.reference("/Team Weapons")
    weaponsData = ref.get()
    newWeapons = ""
    for key, val in weaponsData.items():
      if val['User ID'] == interaction.user.id:
        #print(val['Weapons'])
        try:
          for x in range(len(val['Weapons'])):
            newWeapons = f"{newWeapons}<:Reply:950301070456942622> {val['Weapons'][x]} ({val['Quantity'][x]} left)\n"
        except Exception:
          pass
    if newWeapons != "":
      embed.add_field(name=f"Weapons Remaining", value=f"{newWeapons}")
    msg = await interaction.client.get_channel(team_channel_dict[attackFromTeam]).send(embed=embed)
    await interaction.followup.send(f'[Attack initiated!]({msg.jump_url})')

  @app_commands.command(
    name = "info",
    description = "Shows info of any team!"
  )
  @app_commands.describe(
    team = "The team you wish to get information of"
  )
  @app_commands.choices(team=[
      app_commands.Choice(name="Team Mondstadt", value="Team Mondstadt"),
      app_commands.Choice(name="Team Liyue", value="Team Liyue"),
      app_commands.Choice(name="Team Inazuma", value="Team Inazuma"),
      app_commands.Choice(name="Team Sumeru", value="Team Sumeru"),
      app_commands.Choice(name="Team Fontaine", value="Team Fontaine"),
      app_commands.Choice(name="Team Natlan", value="Team Natlan"),
  ])
  async def team_info(
    self,
    interaction: discord.Interaction,
    team: app_commands.Choice[str]
  ) -> None:
    await check(interaction)
    gangRole = discord.utils.get(interaction.guild.roles,name=str(team.value))

    embed=discord.Embed(title=f"{gangRole.name} Information", description="You can use `/team join` to join a team!", color=0x0674db)
    embed.add_field(name="Name", value=gangRole.name, inline=True)
    embed.add_field(name="Members", value=len(gangRole.members), inline=True)
    embed.add_field(name="Created At", value=f"<t:{int(float(time.mktime(gangRole.created_at.timetuple())))}:R>", inline=True)
    
    ref = db.reference("/Team Trophy")
    teamtrophy = ref.get()

    for key, val in teamtrophy.items():
      if val['Team Name'] == gangRole.name:
        trophy = val['Team Trophy']
        break

    embed.add_field(name="Team Trophy", value=trophy, inline=True)

    leader = leaders[teams.index(gangRole.name)]
    leaderRole = leaderRoles[teams.index(gangRole.name)]
    embed.add_field(name="Leader", value=f"<@{leader}>", inline=True)
    embed.add_field(name="Leader's Role", value=leaderRole, inline=True)
    
    desc = ""
    for member in gangRole.members:
      desc = f"{desc}- {member.mention} `({member.id})`\n"
    memberlist=discord.Embed(title=f"List of members", description=desc, color=0x0674db)
    
    memberlist.timestamp = datetime.datetime.now(datetime.timezone.utc)
    try:
      await interaction.response.send_message(embeds=[embed,memberlist])
    except Exception:
      await interaction.response.send_message(embeds=[embed])

    
  @app_commands.command(
    name = "join",
    description = "Join your favourite team"
  )
  @app_commands.describe(
    team = "The team you wish to join"
  )
  @app_commands.choices(team=[
      app_commands.Choice(name="Team Mondstadt", value="Team Mondstadt"),
      app_commands.Choice(name="Team Liyue", value="Team Liyue"),
      app_commands.Choice(name="Team Inazuma", value="Team Inazuma"),
      app_commands.Choice(name="Team Sumeru", value="Team Sumeru"),
      app_commands.Choice(name="Team Fontaine", value="Team Fontaine"),
      app_commands.Choice(name="Team Natlan", value="Team Natlan"),
  ])
  async def team_join(
    self,
    interaction: discord.Interaction,
    team: app_commands.Choice[str]
  ) -> None:
    await check(interaction, True)
    await joingang(interaction, team.value)
  
  @app_commands.command(
    name = "purchase",
    description = "Purchase a weapon/an item!"
  )
  @app_commands.autocomplete(item=weapon_purchase_autocomplete)
  @app_commands.describe(
    item = "The item you want to buy using mora"
  )
  async def team_purchase(
    self,
    interaction: discord.Interaction,
    item: str
  ) -> None:
    allWeapons = [["Especial Fates", 5000], ["Shadow Realm", 10000], ["50% Boost", 20000], ["Malaise", 20000], ["Breach", 25000], ["Sabotage", 25000], ["Guardian Quota", 30000], ["Vengeance", 30000], ["Silent Enemies", 50000], ["Reverb", 60000], ["Complete Collapse", 80000]]
    await interaction.response.defer()
    legit = False
    cost = None
    for allWeapon in allWeapons:
      if allWeapon[0] == item:
        legit = True
        cost = allWeapon[1]
    if not(legit):
      await interaction.followup.send("That is not a valid item to purchase!")
      raise Exception()
    
    newmora = await addMora(interaction.user.id, -cost)
    if newmora < 0:
      await addMora(interaction.user.id, cost)
      await interaction.followup.send("You don't have enough mora to purchase this item!")
      raise Exception()
    
    weapon = None
    if item == "Especial Fates":
      ref = db.reference("/Team Fates")
      teamfates = ref.get()
      ogfate = 0
      try:
        for key, val in teamfates.items():
          if val['User ID'] == interaction.user.id:
            ogfate = val['Especial Fates']
            db.reference('/Team Fates').child(key).delete()
            break
      except Exception:
        pass
      newfate = ogfate + 1
      data = {
        "Data": {
          "User ID": interaction.user.id,
          "Especial Fates": newfate,
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      embed = discord.Embed(title="Purchase Success", description=f"You have purchased `{item}` for <:MORA:953918490421641246> {cost}.", color=0x6CEDFA)
      embed.add_field(name="Your Total Fates", value=f"<:especial_fates:1256349040761769985> {newfate}")
      await interaction.followup.send(embed=embed)
      raise Exception("Purchased Especial Fates")
    else:
      weapon = item
    
    ref = db.reference("/Team Weapons")
    daily = ref.get()
    weapons = []
    oldWeapons = ""
    for key, val in daily.items():
      if val['User ID'] == interaction.user.id:
        try:
          for x in range(len(val['Weapons'])):
            weapons.append([val['Weapons'][x], val['Quantity'][x]])
            oldWeapons = f"{oldWeapons}<:Reply:950301070456942622> {val['Weapons'][x]} ({val['Quantity'][x]} left)\n"
        except Exception:
          pass
        db.reference('/Team Weapons').child(key).delete()
    #print(weapons)
    found = False
    for xweapon in weapons:
      if xweapon[0] == weapon:
        xweapon[1] = xweapon[1] + 1
        found = True
        
    if not(found):
      weapons.append([weapon, 1])
    y = []
    z = []
    for x in weapons:
      y.append(x[0])
      z.append(x[1])
    data = {
      "Data": {
        "User ID": interaction.user.id,
        "Weapons": y,
        "Quantity": z
      }
    }

    for key, value in data.items():
      ref.push().set(value)
    
    embed = discord.Embed(title="Purchase Success", description=f"You have purchased `{weapon}` for <:MORA:953918490421641246> {cost}.", color=0x6CEDFA)
    newWeapons = ""
    ref = db.reference("/Team Weapons")
    daily = ref.get()
    for key, val in daily.items():
      if val['User ID'] == interaction.user.id:
        #print(val['Weapons'])
        try:
          for x in range(len(val['Weapons'])):
            newWeapons = f"{newWeapons}<:Reply:950301070456942622> {val['Weapons'][x]} ({val['Quantity'][x]} left)\n"
        except Exception:
          pass
    embed.add_field(name="Before ➡", value=oldWeapons, inline=True)
    embed.add_field(name="After", value=newWeapons, inline=True)
    await interaction.followup.send(embed=embed)
   
  @app_commands.command(
    name = "leave",
    description = "Leave your current team"
  )
  async def team_leave(
    self,
    interaction: discord.Interaction,
  ) -> None:
    await check(interaction, True)
    for role in interaction.user.roles:
      if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
        await interaction.user.remove_roles(role)
        leavechannel = teamchannels[teams.index(role.name)]
        chn = interaction.client.get_channel(leavechannel)
        await chn.send(f"{interaction.user.mention} left the team. Goodbye~")
        if datetime.datetime.now().year == 2023 and datetime.datetime.now().month == 1:
          await interaction.user.remove_roles(interaction.guild.get_role(1058145940868960256))
        embed=discord.Embed(description=f"You successfully left **{role.name}**! \nYou can always use `/team join` to join another team!", color=0x0674db)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed)
        raise Exception()

    await interaction.response.send_message(f"You aren't in a team! Use `/team join` to join one first!", ephemeral=True)
  
    
    
  @app_commands.command(
    name = "mine",
    description = "Show the stats of you and your current team"
  )
  async def team_mine(
    self,
    interaction: discord.Interaction,
  ) -> None:
    await check(interaction)
        
    for role in interaction.user.roles:
      if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
        ref = db.reference("/Team Mora")
        teammora = ref.get()
        ref2 = db.reference("/Team Credits")
        teamcredits = ref2.get()

        credits = 0
        mora = 0
        for key, val in teamcredits.items():
          if val['Team'] == role.name:
            credits = val['Credits']
            break
        for key, val in teammora.items():
          if val['User ID'] == interaction.user.id:
            mora = val['Mora']
            break
        embed=discord.Embed(description=f"{interaction.user.mention}, you are currently in **{role.name}**!", color=0x0674db)
    
        embed.add_field(name="Current Mora", value=f"<:MORA:953918490421641246> {mora}")
        embed.add_field(name=f"{role.name}'s Credits", value=f"<:PRIMOGEM:939086760296738879> {credits}")
        embed.add_field(name=f"Mansion Level", value=f":house: Lvl {get_level(credits)}")
        newWeapon = ""
        weapons = []
        ref = db.reference("/Team Weapons")
        daily = ref.get()
        for key, val in daily.items():
          if val['User ID'] == interaction.user.id:
            #print(val['Weapons'])
            try:
              for x in range(len(val['Weapons'])):
                weapons.append([val['Weapons'][x], val['Quantity'][x]])
            except Exception:
              pass
        for weapon in weapons:
          newWeapon = f"{newWeapon}<:Reply:950301070456942622> {weapon[0]} ({weapon[1]} left)\n"
        if newWeapon != "":
          embed.add_field(name="Weapons", value=newWeapon)
        
        ref = db.reference("/Team Fates")
        teamfates = ref.get()
        ogfate = 0
        try:
          for key, val in teamfates.items():
            if val['User ID'] == interaction.user.id:
              ogfate = val['Especial Fates']
              break
        except Exception:
          pass
        embed.add_field(name="Especial Fates", value=f"<:especial_fates:1256349040761769985> {ogfate}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed)
        raise Exception()

    await interaction.response.send_message(f"You aren't in a team! Use `/team join` to join one first!", ephemeral=True)

    
class AttackCooldown(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_test_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
      await interaction.response.send_message(str(error), ephemeral=True)
        
def rgb_to_hex(r, g, b):
    hex_code = "#{:02X}{:02X}{:02X}".format(r, g, b)
    return hex_code

class RefreshTeamStats(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Refresh', style=discord.ButtonStyle.grey, custom_id='refreshteamstats', emoji="<:refresh:1048779043287351408>")
  async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.defer()
    ref2 = db.reference("/Team Credits")
    teamcredits = ref2.get()
    embeds = []
    for team in teams:
      credits = 0
      for key, val in teamcredits.items():
        if val['Team'] == team:
          credits = val['Credits']
          break
      role = discord.utils.get(interaction.guild.roles,name=team)
      embed=discord.Embed(title=team, description=f"", color=role.color)
      color = rgb_to_hex(role.color.r, role.color.g, role.color.b)
      color = ImageColor.getcolor(color, "RGB")
      if get_level(credits) < 10:
        width = 230
      else:
        width = 300

      img = Image.new('RGB', (width, 230), color=(43, 44, 49))
      font = ImageFont.truetype("./assets/ja-jp.ttf", 200)
      d = ImageDraw.Draw(img)
      d.text((20,0), str(get_level(credits)), font=font, fill=color)
      img.save(f"./assets/text.png")
    
      chn = interaction.client.get_channel(1026968305208131645)
      msg = await chn.send(file=discord.File(f"./assets/text.png"))
      url = msg.attachments[0].proxy_url
      embed.set_thumbnail(url=url)
    
      embed.add_field(name=f"Mansion Level", value=f":house: Lvl {get_level(credits)}", inline=True)
      #embed.add_field(name=f"Mansion HP", value=f":heart_exclamation: {TotalHPOfEachLevel[get_level(credits)]} HP", inline=True)
      embed.add_field(name=f"Mansion HP", value=f":heart_exclamation: {credits * 2 + 50} / {TotalHPOfEachLevel[get_level(credits)]} HP", inline=True)
      #embed.add_field(name=f"Missing Credits for Next Level", value=f"<:PRIMOGEM:939086760296738879> { totalCreditsRequiredForEachLevel[get_level(credits) + 1] - credits}", inline=False)
      embed.add_field(name=f"Missing Credits for Next Level", value=f"<:PRIMOGEM:939086760296738879> {int((TotalHPOfEachLevel[get_level(credits)] - (credits * 2 + 50))/2)}", inline=False)
      embed.add_field(name=f"HP Gain for Next Level", value=f"<:BooTao_Upvote:954192269936836608> {int(TotalHPOfEachLevel[get_level(credits) + 1] - TotalHPOfEachLevel[get_level(credits)])} HP", inline=True)
      embeds.append(embed)
    await interaction.message.edit(embeds=embeds, view=RefreshTeamStats())
    await interaction.followup.send("<:refresh:1048779043287351408> The stats are refreshed. Have fun looking at them!", ephemeral=True)

    
class TimeSlots(discord.ui.Select):
    def __init__(self):
      options = []
      for x in range(1,4):
        options.append(discord.SelectOption(label=f"Session {x}"))
      super().__init__(placeholder="Choose Time Slots",max_values=3,min_values=0,options=options, custom_id="timeslotsskribblio")
    
    async def callback(self, interaction: discord.Interaction):
      await interaction.response.defer(ephemeral=True)
      list = [1227048238255706173, 1227058079753834506, 1227058108300267541]
      for item in list:
        role = interaction.guild.get_role(item)
        await interaction.user.remove_roles(role)
      if "Session 1" in self.values:
        role = interaction.guild.get_role(list[0])
        await interaction.user.add_roles(role)
      if "Session 2" in self.values:
        role = interaction.guild.get_role(list[1])
        await interaction.user.add_roles(role)
      if "Session 3" in self.values:
        role = interaction.guild.get_role(list[2])
        await interaction.user.add_roles(role)
      message = ""
      chosen = sorted(self.values)
      if len(self.values) > 0:
        message = f"{message}You have successfully signed up for "
        for value in chosen:
          if chosen[-1] == value:
            message = f"{message}**{value}**."
          else:
            message = f"{message}**{value}** & "
      else:
        message = f"{message}All the time slots have been **removed** from you and you will no longer be notified."
      await interaction.followup.send(message, ephemeral=True)
    
class TimeSlotsView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)
    self.add_item(TimeSlots())
    
class ManualTeamSelection(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return
    
    ### Team Liyue Custom Role 2023 ###
    if message.guild.id == 717029019270381578 and message.content == "-givecustomroletoliyue":
      role = message.guild.get_role(1052043798542295131)
      customRole = message.guild.get_role(1199042975158784090)
      for member in role.members:
        await member.add_roles(customRole)
        await message.channel.send(f"Custom role added to {member.mention}")
      await message.channel.send("All custom roles added to Team Liyue members. Time to manually remove them from those who joined after 2023.")
    
    ### 2024 April Skribbl.io Time Slots Sign up ###
    if message.guild.id == 717029019270381578 and message.content == "-timeslots":
      embed=discord.Embed(title="Select your available time slots", description=f"> You can select multiple options. If you select again, it will override your previous selection. \n\n1. <t:1713398400>\n2. <t:1713711600>\n3. <t:1714003200> \n\nAlthough you can sign up for multiple time slots, only one (the first one you attend) will count towards the team's total score. **Signing up is not binding - it will simply allow you to receive reminders via DM!**", color=discord.Color.gold())
      embed.set_footer(text="The time shown to you is your LOCAL time.")
      view = View()
      view.add_item(TimeSlots())
      await message.channel.send(embed=embed, view=view)
      await message.delete()
    
    ### Initiate Team Weapons ###
    #if message.guild.id == 717029019270381578 and message.content == "-thisone":
        #ref = db.reference("/Team Weapons")
        #daily = ref.get()

        #data = {
          #"Data": {
            #"User ID": message.author.id,
            #"Weapons": ["50% Boost", "Level Deduction", "Ineffective Defense"],
            #"Quantity": [3, 1, 4]
          #}
        #}

        #for key, value in data.items():
          #ref.push().set(value)
        
    ### SEND TEAM STATS PANEL ###
    if message.guild.id == 717029019270381578 and message.content == "-mansionstats":
      ref2 = db.reference("/Team Credits")
      teamcredits = ref2.get()
      embeds = []
      for team in teams:
        credits = 0
        for key, val in teamcredits.items():
          if val['Team'] == team:
            credits = val['Credits']
            break
        role = discord.utils.get(message.guild.roles,name=team)
        embed=discord.Embed(title=team, description=f"", color=role.color)
        color = rgb_to_hex(role.color.r, role.color.g, role.color.b)
        color = ImageColor.getcolor(color, "RGB")
        if get_level(credits) < 10:
          width = 230
        else:
          width = 300

        img = Image.new('RGB', (width, 230), color=(43, 44, 49))
        font = ImageFont.truetype("./assets/ja-jp.ttf", 200)
        d = ImageDraw.Draw(img)
        d.text((20,0), str(get_level(credits)), font=font, fill=color)
        img.save(f"./assets/text.png")
    
        chn = self.client.get_channel(1026968305208131645)
        msg = await chn.send(file=discord.File(f"./assets/text.png"))
        url = msg.attachments[0].proxy_url
        embed.set_thumbnail(url=url)
    
        embed.add_field(name=f"Mansion Level", value=f":house: Lvl {get_level(credits)}", inline=True)
        embed.add_field(name=f"Mansion HP", value=f":heart_exclamation: {TotalHPOfEachLevel[get_level(credits)]} HP", inline=True)
        embed.add_field(name=f"Missing Credits for Next Level", value=f"<:PRIMOGEM:939086760296738879> { totalCreditsRequiredForEachLevel[get_level(credits) + 1] - credits}", inline=False)
        embed.add_field(name=f"HP Gain for Next Level", value=f"<:BooTao_Upvote:954192269936836608> {TotalHPOfEachLevel[get_level(credits) + 1] - TotalHPOfEachLevel[get_level(credits)]} HP", inline=True)
        embeds.append(embed)
      await message.channel.send(embeds=embeds, view=RefreshTeamStats())

    ### SEND TEAM SELECTION PANEL ###
    if message.guild.id == 717029019270381578 and message.content == "-manualteamselection":
      await message.channel.send(embed=discord.Embed(title="Select your favourite team!", description=f"> **🛷 Team Mondstadt:** Led by <@{leaders[0]}>\n> **☃ Team Liyue:** Led by <@{leaders[1]}>\n> **🎄 Team Inazuma:** Led by <@{leaders[2]}>\n> **🎁 Team Sumeru:** Led by <@{leaders[3]}>\n> **🌊 Team Fontaine:** Led by <@{leaders[4]}>\n> **🔥 Team Natlan:** Led by <@{leaders[5]}>\n\n**Requirements:** \nYou must be at least <@&949337290969350304> or above.\n*But it's quite easy to obtain by actively chatting in <#1104212482312122388>!*", color=discord.Color.gold()), view=TeamSelectionButtons())
      await message.delete()

    ### SEND TEAM CHALLENGE INFO ###
    if message.guild.id == 717029019270381578 and message.content == "-teamchallengesinfo":
      await message.delete()
      embeds = [discord.Embed(title="Team Details & Challenges Info"), discord.Embed(title="`Team Selection Details`", description="Members can freely join, switch or leave teams from the start to the 15th day of the month, but no longer can switch, join or leave teams when a team challenge is happening."), discord.Embed(title="`Team Challenges Details`", description=f"""- This event occurs monthly, usually running from the **15th day to the final day of the month.**
- The objective is for team members to collaborate towards a common goal, competing against other teams to be the fastest or highest achieving.
- The winning team of the previous month's challenge earns 1 "Team Trophy" and utmost respect from everyone in the community.
- At the conclusion of the year, the team with the most "Team Trophies" will receive a special custom role for all members and an exclusive prize, which will be announced in late 2023.
- Additionally, the individual with the most "Credits" at the end of the year will be awarded an exclusive role and an exclusive prize, yet to be determined.
- The **maximum number of members allowed per team** is currently set at **{maxlimit}**.
"""), discord.Embed(title="`Team Leaders' Requirements`", description="""- Must be level 50 or above in the server.
- Must have a proven track record of positive behavior within the server.
- Must possess the ability to commit to leading the team for a long period of time.
"""), discord.Embed(title="`Team Leaders' Privilege & Restrictions`", description="""- Have the authority to voluntarily transfer their position to any team member at any given time.
- Have permissions to manage channels and messages within their team's private chat channel.
- If their team wins a challenge, the team leader may suggest the next challenge for the upcoming month. However, the proposed challenge must not breach the server's regulations or contradict the principles and objectives of team challenges. The server's owners will try to honor your request whenever feasible.
- Must not leave their team unless the team is officially disbanded, or the leadership role is transferred to another member officially.
- Must maintain a positive image and act as a role model within the server, displaying good faith and ethical behavior.
- When promoting within or outside the server, the team leader must avoid annoying others. Appropriate recruitment is acceptable.
"""), discord.Embed(title="`Team Members' Privilege`", description="""- Access to a private chat channel designated for their team's use.
- Winning a monthly challenge as a team member rewards the individual with 5 "Credits"
- Additionally, participants who rank within the top three of a monthly challenge are likely to receive extra credits as a reward.
- As a team, members may democratically decide to remove their team leader by obtaining a two-thirds majority vote. The new team leader will be determined based on the highest level or XP in Arcane before the vote if this method is used.
"""), discord.Embed(title="`Team Creation Process`", description=f"We welcome and encourage anyone in the community to establish their own teams provided that the designated team leader fulfills the necessary team leader requirements listed above."), discord.Embed(title="`Team Deletion Process`", description="Team deletion is a huge matter, especially if your team has a considerable number of members. We kindly request that you directly contact one of our owners before making the decision to leave or abandon your team. We would likely transfer your team's leadership to another team member of your choice. "), discord.Embed(title="`Owners reserve the following rights`", description="""- Remove or transfer team leadership to another individual if deemed necessary.
- Disagree with the proposed challenge suggested by the winning team leader.
- Remove credits from an individual if deemed necessary.
- Transfer an individual from one team to another in the event of an imbalanced distribution of team members, potentially leading to unfairness.
- Increase the maximum limit of team members per team at any given time.
""")]
      await message.channel.send(embeds=embeds)
    if message.guild.id == 717029019270381578 and message.content == "-teammansioninfo":
      await message.delete()
      embed = discord.Embed(title="Team Mansion | Currency & Game Info", description="""
-  **/team attack** - *attacks an ememy team* <:Raiden_blush:999899960319410237>
  - You can deal damage to the enemy mansions! Every team can defend your attack or counter-attack your attack! 
  - The cooldown of an attack is **12 hours** *(the only other rule is that you cannot attack the same team consecutively)*
- **/team daily** - *gives you mora + credits to your team mansion* <:Raiden_sip:1115959510918516746> 
  - You can use <:MORA:953918490421641246> mora to buy a weapon for attacking! More details on weapons below!
  - <:PRIMOGEM:939086760296738879> Credits are very useful!** It helps your team level up!** It even gains HP for your team! But be careful that enemy teams can lower your mansion level by attacking your team! You can check the stats of all the teams [here](https://discord.com/channels/717029019270381578/1195227139398713364).
  - You may also get some Especial Fates, which you can use to wish for weapons
  - There is also a slight chance of getting a **random FREE weapon** every time you run the command
- **/team purchase** - *it will only show you what items you can buy with your current amount of mora* 
  - Currency:
    - <:especial_fates:1256349040761769985> **Especial Fate** (5k)
  - Weapons:
    - Mystic Weapons:
      - **Shadow Realm** disables counterattacks by enemy team (10k)
      - **50% Boost** boosts attack damage by 50% (20k)
      - **Malaise** weakens any defenses the opponents made (20k)
    - Celestial Weapons:
      - **Sabotage** redirects all counterattacks to another random team (25k)
      - **Breach** guarantees the first 3 defenders to fail (25k)
      - **Guardian Quota** limits to 3 defenses (30k)
      - **Vengeance** deals 100% extra damage if the enemy team has attacked your team within the last 2 hours (35k)
    - Radiant Weapons:
      - **Silent Enemies** prevents all defenses by the opponents (50k)
      - **Reverb** allows your team to gain the same HP when the opposing team defenses, and counterattacks will bounce back to the defending team (60k)
      - **Complete Collapse** downgrades the enemy team to their level’s base HP (80k)
  - If you bought a weapon, you can use it by typing **`/team attack` and it will allow you to pick any weapon you own** <:Raiden_Read:944869587713945610>
- :new: **/team wish** - *gives you [some chance](https://docs.google.com/spreadsheets/d/1iU1hmZooVpMUWFQtvlTvyjGnjN1ypSuqh0LcfMiRzdI/edit?usp=sharing) to unlock weapons*
  - You need 3 Especial Fates for one wish
  - There is a pity system on the scale of 0-11. Your pity will increase as long as a Radiant Weapon is not obtained, and reset to 0 once you get one. Reaching 11 pity will guarantee you a Radiant Weapon.
- Every team has even ability to defend against attacks! If other teams decide to attack your team, everyone from your team can defend and help the team regain the HP it lost! 
  - You can only defend against attacks within the **past 2 hours**
  - There is a small chance of failing the defense or having a counter-attack on the enemy team *(regains HP to our mansion + does some damage to the enemy mansion)*
  - You can **[claim](https://discord.com/channels/717029019270381578/1083866201773588571/1200246414391902208) <@&1200241691798536345>** to always get pinged whenever someone attacks us! It will also send **daily reminders via DM** to obtain dailies.
 - Every team can gain a HUGE chunk of Credits for their mansions for participating in [challenges](https://discord.com/channels/717029019270381578/1083867254728433787)
""", color=0x000001)
      embed.set_footer(text="Credits to guchii from Team Inazuma for helping with this guideline!")
      await message.channel.send(embed=embed)

    ### Initiate Team Trophy & Credits for new teams ###
    if message.guild.id == 717029019270381578 and message.content == "-initteam":
      ref = db.reference("/Team Trophy")

      for team in ["Team Natlan"]:
        data = {
          message.guild.id: {
            "Team Name": team,
            "Team Trophy": 0,
          }
        }
    
        for key, value in data.items():
          ref.push().set(value)
        
      ref = db.reference("/Team Credits")

      for team in ["Team Natlan"]:
        data = {
          message.guild.id: {
            "Credits": 0,
            "Team": team,
          }
        }
    
        for key, value in data.items():
          ref.push().set(value)

    ### Give 5 credits to the entire team (e.g. -giveteamcreditsto: Team Liyue)
    if message.guild.id == 717029019270381578 and "-giveteamcreditsto:" in message.content: 
      team = message.content.split(":")[1].strip()
      teamrole = discord.utils.get(message.guild.roles,name=team)

      for member in teamrole.members:
        ref = db.reference("/Team Credits")
        teamcredits = ref.get()
        
        credits = 0
        for key, val in teamcredits.items():
          if val['User ID'] == member.id:
            credits = val['Team Credits']
            db.reference('/Team Credits').child(key).delete()
            break

        newcredits = credits + 5
        data = {
          message.guild.id: {
            "User ID": member.id,
            "Team Credits": newcredits,
          }
        }
    
        for key, value in data.items():
          ref.push().set(value)

        await message.channel.send(f"5 Team Credits added to {member} and has a total of {newcredits} Team Credits")

#     if message.guild.id == 717029019270381578 and "-getregistered" in message.content:
#       ref = db.reference("/Jan TCG Tournament Registration")
#       registration = ref.get()
      
#       for key, val in registration.items():
#         userID = int(str(val['User ID']))
#         user = message.guild.get_member(userID)
#         team = None
#         for role in user.roles:
#           if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
#             team = role.name
#         timeSlot = val['Time Slot']
#         region = val['Region']
#         ign = val['IGN']
#         ar = val['AR']
#         await message.channel.send(embed=discord.Embed(description=f"""User: {user.mention} `({userID})`\n:checkered_flag: {team}\n\nTime Slot: {timeSlot}\nRegion: {region}\nIn-game Name: {ign}\nAdventure Rank {ar}""", color=discord.Color.blurple()))

#     if message.guild.id == 717029019270381578 and message.content == "-registerforkahoot":
#       await message.channel.send("""**Calling all Genshin Impact players! Genshin Impact Cafe is proud to be hosting an online Kahoot tournament open to all <@&748778550911565825>!** 
# There would be two quizzes in total, with each round having two time slots available to let people from different timezones participate.
#  """, embed=discord.Embed(title="Register for TCG Tournament", description="""**Option 1a:** <t:1679149800:F> (<t:1679149800:R>)
# **Option 1b:** <t:1679187600:F> (<t:1679187600:R>)

# **Option 2a:** <t:1679754600:F> (<t:1679754600:R>)
# **Option 2b:** <t:1679792400:F> (<t:1679792400:R>)

# You can only participate either `a` or `b` in each option.""", color=discord.Color.blurple()), view=MarchTeamChallenge())

#     if message.guild.id == 717029019270381578 and message.content == "-getuserin2015":
#       guild = self.client.get_guild(749418356926578748)
#       for user in guild.members:
#         roles = ", ".join(
#           [f"<@&{role.id}>" for role in sorted(user.roles, key=lambda role: role.position, reverse=True) if role.id != guild.default_role.id]
#       ) if len(user.roles) > 1 else "None"
#         embed = discord.Embed(colour=user.top_role.colour.value)
#         embed.set_thumbnail(url=user.display_avatar.url)
#         embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
#         if user.banner:
#           embed.set_image(
#             url=user.banner.url
#           )
#         embed.add_field(name="Username", value=user.name, inline=True)
#         embed.add_field(name="Server Nick", value=user.nick if hasattr(user, "nick") else "None", inline=True)
#         embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
#         embed.add_field(name="Account created", value=f"<t:{int(float(time.mktime(user.created_at.timetuple())))}:R>", inline=True)
#         embed.add_field(name="Joined this server", value=f"<t:{int(float(time.mktime(user.joined_at.timetuple())))}:R>", inline=True)
#         embed.add_field(name="Roles", value=roles, inline=False)
#         if int(float(time.mktime(user.created_at.timetuple()))) <= 1451635199:
#           await message.channel.send(embed=embed)
        
      



# class modal(discord.ui.Modal, title="Modal"):

#   name = discord.ui.TextInput(label="In-game name", style=discord.TextStyle.short, placeholder="", required=True)

#   server = discord.ui.TextInput(label="Server Region", style=discord.TextStyle.short, placeholder="", required=True)

#   ar = discord.ui.TextInput(label="Adventure Rank", style=discord.TextStyle.short, placeholder="", required=True)

#   async def on_submit(self, interaction:discord.Interaction):
#     if int(str(self.ar)) < 32:
#       await interaction.response.edit_message(embed=discord.Embed(title="You are not qualified!", description=f"To unlock TCG, you must reach at least **adventure rank 32**. You also need to have already completed the Archon Quest 'Prologue: Act III - Song of the Dragon and Freedom.", color=discord.Color.red()), view=None)
#       raise Exception()

#     ref = db.reference("/Jan TCG Tournament Registration")
#     registration = ref.get()

#     ogtimeslot = None
#     try:
#       for key, val in registration.items():
#         if val['User ID'] == interaction.user.id:
#           ogtimeslot = val['Time Slot']
#           db.reference('/Jan TCG Tournament Registration').child(key).delete()
#           break
#     except Exception:
#       pass


#     data = {
#       interaction.user.id: {
#         "User ID": interaction.user.id,
#         "Time Slot": str(self.title),
#         "IGN": str(self.name),
#         "Region": str(self.server),
#         "AR": int(str(self.ar))
#       }
#     }

#     for key, value in data.items():
#       ref.push().set(value)

#     if ogtimeslot == str(self.title):
#       await interaction.response.edit_message(embed=discord.Embed(title="Time Slot Unchanged", description=f"Your original time slot is already **{ogtimeslot}**. \nYou can click on other time slots to change your time slot!", color=discord.Color.red()), view=None)
#     elif ogtimeslot is not None:
#       await interaction.response.edit_message(embed=discord.Embed(title="Registration Successful :white_check_mark:", description=f"You have **cancelled your original time slot of {ogtimeslot}** and now **successfuly registered for {str(self.title)}**.\n\nAfter registering, you should mark down this tournament in your calendar and make sure to participate when the time has come, or else it will negatively affect your entire team's performance.", color=discord.Color.blurple()), view=None)
#     else:
#       await interaction.response.edit_message(embed=discord.Embed(title="Registration Successful :white_check_mark:", description=f"You have **successfuly registered for {str(self.title)}**.\n\nAfter registering, you should mark down this tournament in your calendar and make sure to participate when the time has come, or else it will negatively affect your entire team's performance.", color=discord.Color.blurple()), view=None)

# class ChooseTime(discord.ui.View):
#   def __init__(self):
#     super().__init__(timeout=None)

#   @discord.ui.button(label='Jan 15, 11am-12pm', style=discord.ButtonStyle.green, custom_id='jan15')
#   async def jan15(self, interaction: discord.Interaction, button: discord.ui.Button):
#     await interaction.response.send_modal(modal(title=str(button.label)))

#   @discord.ui.button(label='Jan 16, 11am-12pm', style=discord.ButtonStyle.green, custom_id='jan16')
#   async def jan16(self, interaction: discord.Interaction, button: discord.ui.Button):
#     await interaction.response.send_modal(modal(title=str(button.label)))

#   @discord.ui.button(label='Jan 17, 11am-12pm', style=discord.ButtonStyle.green, custom_id='jan17')
#   async def jan17(self, interaction: discord.Interaction, button: discord.ui.Button):
#     await interaction.response.send_modal(modal(title=str(button.label)))

# class MarchTeamChallenge(discord.ui.View):
#   def __init__(self):
#     super().__init__(timeout=None)

#   @discord.ui.button(label='Option 1a', style=discord.ButtonStyle.grey, custom_id='1a')
#   async def option1a(self, interaction: discord.Interaction, button: discord.ui.Button):
#     inTeam = False
#     for role in interaction.user.roles:
#       if "team" in role.name.lower():
#         inTeam = True
#     if not inTeam:
#       await interaction.response.send_message(embed=discord.Embed(title="Oops!", description=":x: You are not yet in a team! \nHead over to <#1058148134125060226> and join your favorite team!", color=discord.Color.red()), ephemeral=True)
#     else:
#       pass

# class JanTeamChallenge(discord.ui.View):
#   def __init__(self):
#     super().__init__(timeout=None)

#   @discord.ui.button(label='Register for TCG Tournament', style=discord.ButtonStyle.grey, custom_id='participatejantourney')
#   async def participatejantourney(self, interaction: discord.Interaction, button: discord.ui.Button):
#     inTeam = False
#     for role in interaction.user.roles:
#       if "team" in role.name.lower():
#         inTeam = True
#     if not inTeam:
#       await interaction.response.send_message(embed=discord.Embed(title="Oops!", description=":x: You are not yet in a team! \nHead over to <#1058148134125060226> and join your favorite team!", color=discord.Color.red()), ephemeral=True)
#     else:
#       await interaction.response.send_message(embed=discord.Embed(title="Select a time slot to participate in", description="_These time are in Pacific Time (UTC -8)._", color=discord.Color.blurple()),view=ChooseTime(), ephemeral=True)

#   @discord.ui.button(label='Cancel Registration', style=discord.ButtonStyle.red, custom_id='cancelregistration')
#   async def cancelregistration(self, interaction: discord.Interaction, button: discord.ui.Button):
#     ref = db.reference("/Jan TCG Tournament Registration")
#     registration = ref.get()

#     found = False
#     try:
#       for key, val in registration.items():
#         if val['User ID'] == interaction.user.id:
#           db.reference('/Jan TCG Tournament Registration').child(key).delete()
#           found = True
#           break
#     except Exception:
#       pass

#     if found:
#       await interaction.response.send_message(embed=discord.Embed(title="Registration Cancelled :white_check_mark: ", description=":pensive: Sad to see you go, anyways, we have erased you from our participant list.\nIf you decide to participate again, you can register again at anytime before the deadline!", color=discord.Color.green()), ephemeral=True)
#     else:
#       await interaction.response.send_message(embed=discord.Embed(title="What are you even thinking?", description="You were never registered to this event in the first place, or you have already cancelled your registration!", color=discord.Color.yellow()), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Team(bot))
  await bot.add_cog(ManualTeamSelection(bot))
  await bot.add_cog(AttackCooldown(bot))