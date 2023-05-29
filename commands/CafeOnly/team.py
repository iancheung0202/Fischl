import discord, firebase_admin, datetime, asyncio, time, emoji
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

maxlimit = 70
teams = ["Team Mondstadt", "Team Liyue", "Team Inazuma", "Team Sumeru"]
leaderRoles = ["Grand Master", "Tianshu", "Shogun", "Grand Sage"]
leaders = [954888790936281208, 1026905370339311626, 1039070138135228447, 973865405162586142]
teamchannels = [1083867546962370730, 1083867653803888722, 1083867759982682183, 1083867870200602734]

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
    
  if datetime.datetime.now().day >= 15:
    await interaction.response.send_message(embed=discord.Embed(title="Button disabled until Team Challenge is over", description="You cannot join, switch or leave teams while a Team Challenge is occurring."), ephemeral=True)
    raise Exception()

  gangRole = discord.utils.get(interaction.guild.roles,name=gang)
  if len(gangRole.members) >= maxlimit:
    await interaction.response.send_message(embed=discord.Embed(title="Team full!", description=f"A team can only consist of **{maxlimit}** members! Right now **{gang}** is already full. Consider joining other teams with available slots! \n\nIf all teams are full, please create a ticket at <#792433323045552178> and let us know!"), ephemeral=True)
    raise Exception()
    
  msg = "You joined the"
  title = "🎉 Congratulations!"
  alreadyin = False
  for role in interaction.user.roles:
    if "team" in role.name.lower():
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
    await chn.send(embed=discord.Embed(description=f":green_square: {interaction.user.mention} **joined** the team! Welcome! :hugging:", color=0x00FF00))
    if datetime.datetime.now().year == 2023 and datetime.datetime.now().month == 1:
      await interaction.user.add_roles(interaction.guild.get_role(1058145940868960256))
  embed=discord.Embed(title=title, description=f"{msg} **{gang}**!\nYou can use `/team leave` to leave your team at anytime!", color=0x0674db)
  embed.timestamp = datetime.datetime.utcnow()
  await interaction.response.send_message(embed=embed, ephemeral=True)


class modal(discord.ui.Modal, title="Modal"):
  
  name = discord.ui.TextInput(label="In-game name", style=discord.TextStyle.short, placeholder="", required=True)
  
  server = discord.ui.TextInput(label="Server Region", style=discord.TextStyle.short, placeholder="", required=True)
  
  ar = discord.ui.TextInput(label="Adventure Rank", style=discord.TextStyle.short, placeholder="", required=True)

  async def on_submit(self, interaction:discord.Interaction):
    if int(str(self.ar)) < 32:
      await interaction.response.edit_message(embed=discord.Embed(title="You are not qualified!", description=f"To unlock TCG, you must reach at least **adventure rank 32**. You also need to have already completed the Archon Quest 'Prologue: Act III - Song of the Dragon and Freedom.", color=discord.Color.red()), view=None)
      raise Exception()
    
    ref = db.reference("/Jan TCG Tournament Registration")
    registration = ref.get()
    
    ogtimeslot = None
    try:
      for key, val in registration.items():
        if val['User ID'] == interaction.user.id:
          ogtimeslot = val['Time Slot']
          db.reference('/Jan TCG Tournament Registration').child(key).delete()
          break
    except Exception:
      pass
  
    
    data = {
      interaction.user.id: {
        "User ID": interaction.user.id,
        "Time Slot": str(self.title),
        "IGN": str(self.name),
        "Region": str(self.server),
        "AR": int(str(self.ar))
      }
    }
  
    for key, value in data.items():
      ref.push().set(value)
  
    if ogtimeslot == str(self.title):
      await interaction.response.edit_message(embed=discord.Embed(title="Time Slot Unchanged", description=f"Your original time slot is already **{ogtimeslot}**. \nYou can click on other time slots to change your time slot!", color=discord.Color.red()), view=None)
    elif ogtimeslot is not None:
      await interaction.response.edit_message(embed=discord.Embed(title="Registration Successful :white_check_mark:", description=f"You have **cancelled your original time slot of {ogtimeslot}** and now **successfuly registered for {str(self.title)}**.\n\nAfter registering, you should mark down this tournament in your calendar and make sure to participate when the time has come, or else it will negatively affect your entire team's performance.", color=discord.Color.blurple()), view=None)
    else:
      await interaction.response.edit_message(embed=discord.Embed(title="Registration Successful :white_check_mark:", description=f"You have **successfuly registered for {str(self.title)}**.\n\nAfter registering, you should mark down this tournament in your calendar and make sure to participate when the time has come, or else it will negatively affect your entire team's performance.", color=discord.Color.blurple()), view=None)

class ChooseTime(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Jan 15, 11am-12pm', style=discord.ButtonStyle.green, custom_id='jan15')
  async def jan15(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(modal(title=str(button.label)))

  @discord.ui.button(label='Jan 16, 11am-12pm', style=discord.ButtonStyle.green, custom_id='jan16')
  async def jan16(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(modal(title=str(button.label)))

  @discord.ui.button(label='Jan 17, 11am-12pm', style=discord.ButtonStyle.green, custom_id='jan17')
  async def jan17(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(modal(title=str(button.label)))

class MarchTeamChallenge(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Option 1a', style=discord.ButtonStyle.grey, custom_id='1a')
  async def option1a(self, interaction: discord.Interaction, button: discord.ui.Button):
    inTeam = False
    for role in interaction.user.roles:
      if "team" in role.name.lower():
        inTeam = True
    if not inTeam:
      await interaction.response.send_message(embed=discord.Embed(title="Oops!", description=":x: You are not yet in a team! \nHead over to <#1058148134125060226> and join your favorite team!", color=discord.Color.red()), ephemeral=True)
    else:
      pass

class JanTeamChallenge(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Register for TCG Tournament', style=discord.ButtonStyle.grey, custom_id='participatejantourney')
  async def participatejantourney(self, interaction: discord.Interaction, button: discord.ui.Button):
    inTeam = False
    for role in interaction.user.roles:
      if "team" in role.name.lower():
        inTeam = True
    if not inTeam:
      await interaction.response.send_message(embed=discord.Embed(title="Oops!", description=":x: You are not yet in a team! \nHead over to <#1058148134125060226> and join your favorite team!", color=discord.Color.red()), ephemeral=True)
    else:
      await interaction.response.send_message(embed=discord.Embed(title="Select a time slot to participate in", description="_These time are in Pacific Time (UTC -8)._", color=discord.Color.blurple()),view=ChooseTime(), ephemeral=True)

  @discord.ui.button(label='Cancel Registration', style=discord.ButtonStyle.red, custom_id='cancelregistration')
  async def cancelregistration(self, interaction: discord.Interaction, button: discord.ui.Button):
    ref = db.reference("/Jan TCG Tournament Registration")
    registration = ref.get()

    found = False
    try:
      for key, val in registration.items():
        if val['User ID'] == interaction.user.id:
          db.reference('/Jan TCG Tournament Registration').child(key).delete()
          found = True
          break
    except Exception:
      pass

    if found:
      await interaction.response.send_message(embed=discord.Embed(title="Registration Cancelled :white_check_mark: ", description=":pensive: Sad to see you go, anyways, we have erased you from our participant list.\nIf you decide to participate again, you can register again at anytime before the deadline!", color=discord.Color.green()), ephemeral=True)
    else:
      await interaction.response.send_message(embed=discord.Embed(title="What are you even thinking?", description="You were never registered to this event in the first place, or you have already cancelled your registration!", color=discord.Color.yellow()), ephemeral=True)

    

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
  
    
  @discord.ui.button(label='Check my Team', style=discord.ButtonStyle.grey, custom_id='checkteam')
  async def checkteam(self, interaction: discord.Interaction, button: discord.ui.Button):
    for role in interaction.user.roles:
      if "team" in role.name.lower():
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

        desc = ""
        for member in role.members:
          desc = f"{desc}- {member.mention} `({member.id})`\n"
        memberlist=discord.Embed(title=f"List of members", description=desc, color=0x0674db)
        memberlist.timestamp = datetime.datetime.utcnow()
        await interaction.response.send_message(embeds=[embed,memberlist], ephemeral=True)
        raise Exception()
        
    await interaction.response.send_message(f"You aren't in a team! Click the blue buttons to join a team first!", ephemeral=True)
        
    

async def check(interaction, check_date=False):
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
    await interaction.response.send_message(embed=discord.Embed(title="Command unavailable in this server", description="Join our [support server](https://discord.gg/DKJj3GRbhb) and use it there!"), ephemeral=True)
    raise Exception()
  elif not any(role in requiredLevel for role in interaction.user.roles):
    await interaction.response.send_message(":x: You are not qualified to join a team yet! You have to be at least **level 3**. \nBe active in chat and you will be level 3 in no time!", ephemeral=True)
    raise Exception()
  elif datetime.datetime.now().day >= 15 and check_date:
    await interaction.response.send_message(embed=discord.Embed(title="Command disabled until Team Challenge is over", description="You cannot join, switch or leave teams while a Team Challenge is occurring."), ephemeral=True)
    raise Exception()
    

class Team(commands.GroupCog, name="team"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "info",
    description = "Shows info of any team!"
  )
  @app_commands.describe(
    team = "The team you wish to get information of"
  )
  @app_commands.choices(team=[
      app_commands.Choice(name="Team Mondstat", value="Team Mondstadt"),
      app_commands.Choice(name="Team Liyue", value="Team Liyue"),
      app_commands.Choice(name="Team Inazuma", value="Team Inazuma"),
      app_commands.Choice(name="Team Sumeru", value="Team Sumeru"),
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
    
    memberlist.timestamp = datetime.datetime.utcnow()
    await interaction.response.send_message(embeds=[embed,memberlist])

    
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
  ])
  async def team_join(
    self,
    interaction: discord.Interaction,
    team: app_commands.Choice[str]
  ) -> None:
    await check(interaction, True)
    await joingang(interaction, team.value)
    
    
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
      if "team" in role.name.lower():
        await interaction.user.remove_roles(role)
        leavechannel = teamchannels[teams.index(role.name)]
        chn = interaction.client.get_channel(leavechannel)
        await chn.send(f"{interaction.user.mention} left the team. Goodbye~")
        if datetime.datetime.now().year == 2023 and datetime.datetime.now().month == 1:
          await interaction.user.remove_roles(interaction.guild.get_role(1058145940868960256))
        embed=discord.Embed(description=f"You successfully left **{role.name}**! \nYou can always use `/team join` to join another team!", color=0x0674db)
        embed.timestamp = datetime.datetime.utcnow()
        await interaction.response.send_message(embed=embed)
        raise Exception()

    await interaction.response.send_message(f"You aren't in a team! Use `/team join` to join one first!", ephemeral=True)

    
  @app_commands.command(
    name = "mine",
    description = "Show your current team and team credits"
  )
  async def team_mine(
    self,
    interaction: discord.Interaction,
  ) -> None:
    await check(interaction)
    ref = db.reference("/Team Credits")
    teamcredits = ref.get()

    credits = 0
    for key, val in teamcredits.items():
      if val['User ID'] == interaction.user.id:
        credits = val['Team Credits']
        break
        
    for role in interaction.user.roles:
      if "team" in role.name.lower():
        embed=discord.Embed(description=f"{interaction.user.mention}, you are currently in **{role.name}**!\n\nYou have a total of **{credits}** Team Credits. \nTo leave a team, use `/team leave`.", color=0x0674db)
        embed.timestamp = datetime.datetime.utcnow()
        await interaction.response.send_message(embed=embed)
        raise Exception()

    await interaction.response.send_message(f"You aren't in a team! Use `/team join` to join one first!", ephemeral=True)

  @app_commands.command(
    name = "add-credits",
    description = "Adds credits to a member (Admin only)"
  )
  @app_commands.describe(
    user = "The user to add credits to",
    credits = "The amount of credits to be added"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def team_add_credits(
    self,
    interaction: discord.Interaction,
    user: discord.Member,
    credits: int
  ) -> None:
    await check(interaction)
    ref = db.reference("/Team Credits")
    teamcredits = ref.get()
    
    ogcredits = 0
    for key, val in teamcredits.items():
      if val['User ID'] == user.id:
        ogcredits = val['Team Credits']
        db.reference('/Team Credits').child(key).delete()
        break

    newcredits = ogcredits + credits
    data = {
      interaction.guild.id: {
        "User ID": user.id,
        "Team Credits": newcredits,
      }
    }

    for key, value in data.items():
      ref.push().set(value)

    await interaction.response.send_message(embed=discord.Embed(description=f"**{credits}** Team Credits added to {user.mention}\nUser now has a total of **{newcredits}** Team Credits", color=0xFFFF00))


class ManualTeamSelection(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return
    if message.guild.id == 717029019270381578 and message.content == "-manualteamselection":
      await message.channel.send(embed=discord.Embed(title="Select your favourite team!", description="> **🛷 Team Mondstadt:** Led by <@954888790936281208>\n> **☃ Team Liyue:** Led by <@1026905370339311626>\n> **🎄 Team Inazuma:** Led by <@1039070138135228447>\n> **🎁 Team Sumeru:** Led by <@973865405162586142>\n\n**Requirements:** \nYou must be at least <@&949337290969350304> or above\nBut it's quite easy to obtain by actively chatting in <#1104212482312122388>"), view=TeamSelectionButtons())
      await message.delete()
      
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
#       await message.channel.send(embed=discord.Embed(title="Team Details & Challenges Info"))
#       await message.channel.send(embed=discord.Embed(title="`Team Selection Details`", description="Members can freely join, switch or leave teams from the start to the 15th day of the month, but no longer can switch, join or leave teams when a team challenge is happening."))
#       await message.channel.send(embed=discord.Embed(title="`Team Challenges Details`", description=f"""- This event occurs monthly, usually running from the **15th day to the final day of the month.**
# - The objective is for team members to collaborate towards a common goal, competing against other teams to be the fastest or highest achieving.
# - The winning team of the previous month's challenge earns 1 "Team Trophy" and utmost respect from everyone in the community.
# - At the conclusion of the year, the team with the most "Team Trophies" will receive a special custom role for all members and an exclusive prize, which will be announced in late 2023.
# - Additionally, the individual with the most "Credits" at the end of the year will be awarded an exclusive role and an exclusive prize, yet to be determined.
# - The **maximum number of members allowed per team** is currently set at **{maxlimit}**.
# """))
#       leader = await message.channel.send(embed=discord.Embed(title="`Team Leaders' Requirements`", description="""- Must be level 50 or above in the server.
# - Must have a proven track record of positive behavior within the server.
# - Must possess the ability to commit to leading the team for a long period of time.
# """))
#       await message.channel.send(embed=discord.Embed(title="`Team Leaders' Privilege & Restrictions`", description="""- Have the authority to voluntarily transfer their position to any team member at any given time.
# - Have permissions to manage channels and messages within their team's private chat channel.
# - If their team wins a challenge, the team leader may suggest the next challenge for the upcoming month. However, the proposed challenge must not breach the server's regulations or contradict the principles and objectives of team challenges. The server's owners will try to honor your request whenever feasible.
# - Must not leave their team unless the team is officially disbanded, or the leadership role is transferred to another member officially.
# - Must maintain a positive image and act as a role model within the server, displaying good faith and ethical behavior.
# - When promoting within or outside the server, the team leader must avoid annoying others. Appropriate recruitment is acceptable.
# """))
#       await message.channel.send(embed=discord.Embed(title="`Team Members' Privilege`", description="""- Access to a private chat channel designated for their team's use.
# - Winning a monthly challenge as a team member rewards the individual with 5 "Credits"
# - Additionally, participants who rank within the top three of a monthly challenge are likely to receive extra credits as a reward.
# - As a team, members may democratically decide to remove their team leader by obtaining a two-thirds majority vote. The new team leader will be determined based on the highest level or XP in Arcane before the vote if this method is used.
# """))
      # await message.channel.send(embed=discord.Embed(title="`Team Creation Process`", description=f"We welcome and encourage anyone in the community to establish their own teams provided that the designated team leader fulfills the necessary team leader requirements listed above."))
#       await message.channel.send(embed=discord.Embed(title="`Team Deletion Process`", description="Team deletion is a huge matter, especially if your team has a considerable number of members. We kindly request that you directly contact one of our owners before making the decision to leave or abandon your team. We would likely transfer your team's leadership to another team member of your choice. "))
#       await message.channel.send(embed=discord.Embed(title="`Owners reserve the following rights`", description="""- Remove or transfer team leadership to another individual if deemed necessary.
# - Disagree with the proposed challenge suggested by the winning team leader.
# - Remove credits from an individual if deemed necessary.
# - Transfer an individual from one team to another in the event of an imbalanced distribution of team members, potentially leading to unfairness.
# - Increase the maximum limit of team members per team at any given time.
# """))

    if message.guild.id == 717029019270381578 and message.content == "-registerforkahoot":
      await message.channel.send("""**Calling all Genshin Impact players! Genshin Impact Cafe is proud to be hosting an online Kahoot tournament open to all <@&748778550911565825>!** 
There would be two quizzes in total, with each round having two time slots available to let people from different timezones participate.
 """, embed=discord.Embed(title="Register for TCG Tournament", description="""**Option 1a:** <t:1679149800:F> (<t:1679149800:R>)
**Option 1b:** <t:1679187600:F> (<t:1679187600:R>)

**Option 2a:** <t:1679754600:F> (<t:1679754600:R>)
**Option 2b:** <t:1679792400:F> (<t:1679792400:R>)

You can only participate either `a` or `b` in each option.""", color=discord.Color.blurple()), view=MarchTeamChallenge())
    
    # if message.guild.id == 717029019270381578 and message.content == "-initteamtrophy":
    #   ref = db.reference("/Team Trophy")
    #   teamtrophy = ref.get()

    #   for team in ["Team Mondstadt", "Team Liyue", "Team Inazuma", "Team Sumeru"]:
    #     data = {
    #       message.guild.id: {
    #         "Team Name": team,
    #         "Team Trophy": 0,
    #       }
    #     }
    
    #     for key, value in data.items():
    #       ref.push().set(value)
    
    if message.guild.id == 717029019270381578 and "-giveteamcreditsto:" in message.content: # GIVE 5 CREDITS TO THE ENTIRE TEAM
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

    if message.guild.id == 717029019270381578 and "-give2023roleto:" in message.content: # GIVE MEMBERS IN A TEAM THE 2023 HAPPY NEW YEAR
      team = message.content.split(":")[1].strip()
      teamrole = discord.utils.get(message.guild.roles,name=team)

      for member in teamrole.members:
        await member.add_roles(message.guild.get_role(1058145940868960256))

        await message.channel.send(f"{member} role added")

    if message.guild.id == 717029019270381578 and "-getregistered" in message.content:
      ref = db.reference("/Jan TCG Tournament Registration")
      registration = ref.get()
      
      for key, val in registration.items():
        userID = int(str(val['User ID']))
        user = message.guild.get_member(userID)
        team = None
        for role in user.roles:
          if "team" in role.name.lower():
            team = role.name
        timeSlot = val['Time Slot']
        region = val['Region']
        ign = val['IGN']
        ar = val['AR']
  #       await message.channel.send(embed=discord.Embed(description=f"""User: {user.mention} `({userID})`\n:checkered_flag: {team}\n\nTime Slot: {timeSlot}\nRegion: {region}\nIn-game Name: {ign}\nAdventure Rank {ar}""", color=discord.Color.blurple()))
        
  #   if message.content == "-transfer":
  #     ref = db.reference("/Tickets")
  #     registration = ref.get()
      
  #     data = {
  #   "-NEOHW1HKpPRCO4ErpmC": {
  #     "Category ID": 996646343621738500,
  #     "Log Channel ID": 975293245846343700,
  #     "Server ID": 938575150968893400,
  #     "Server Name": "/narukami"
  #   },
  #   "-NESE1oZGH8dIM0Kpx9r": {
  #     "Category ID": 1030933287499202700,
  #     "Log Channel ID": 1030933288321290200,
  #     "Server ID": 862842816571768800,
  #     "Server Name": "Snezhnaya"
  #   },
  #   "-NES_kZcGI2TRXJlVMhc": {
  #     "Category ID": 1030656754205339800,
  #     "Log Channel ID": 1030656755086135300,
  #     "Server ID": 783528750474199000,
  #     "Server Name": "Coding Central"
  #   },
  #   "-NEdlP79ku5q7zqsXcLX": {
  #     "Category ID": 1030024011708649500,
  #     "Log Channel ID": 1031813883410796500,
  #     "Server ID": 995710617535127800,
  #     "Server Name": "Kiaioplayz Tavern"
  #   },
  #   "-NEfq1UD6fqtIynbTQKP": {
  #     "Category ID": 997974274059026600,
  #     "Log Channel ID": 1026213315329929200,
  #     "Server ID": 944600602841874400,
  #     "Server Name": "•TsukkiTown•"
  #   },
  #   "-NEhbjXKU6yj7F_sXjtW": {
  #     "Category ID": 983506983367868400,
  #     "Log Channel ID": 984516875746680800,
  #     "Server ID": 749418356926578700,
  #     "Server Name": "Travel Guides of Teyvat"
  #   },
  #   "-NEpByQd3OFqaf8djY-b": {
  #     "Category ID": 874179870035439600,
  #     "Log Channel ID": 947052684882612200,
  #     "Server ID": 874162522134052900,
  #     "Server Name": "Xceleratians"
  #   },
  #   "-NEs4WOeWXkv2MrCzARv": {
  #     "Category ID": 1032784221938384900,
  #     "Log Channel ID": 1032822780548370400,
  #     "Server ID": 1031983989877125100,
  #     "Server Name": "Resource Impact"
  #   },
  #   "-NFoEZ5su1VR8Px_sFcV": {
  #     "Category ID": 1037055947090169900,
  #     "Log Channel ID": 1037055948004528100,
  #     "Server ID": 863261036609142800,
  #     "Server Name": "emotetest"
  #   },
  #   "-NH1uT2dIwJOYSTly2YR": {
  #     "Category ID": 1042591883148394500,
  #     "Log Channel ID": 1042591884259889300,
  #     "Server ID": 957702955635712000,
  #     "Server Name": "Genshin Society™ • Genshin • Gaming • Social 🎁"
  #   },
  #   "-NI3fnETjCgPtvyZ1g_k": {
  #     "Category ID": 1047220091860815900,
  #     "Log Channel ID": 1047220092531900500,
  #     "Server ID": 1006746652851318800,
  #     "Server Name": "˃ᗜ˂﹕@xiallous"
  #   },
  #   "-NIj5dZcBaqWHJGxbUc5": {
  #     "Category ID": 1050204878728867800,
  #     "Log Channel ID": 1050204959725060200,
  #     "Server ID": 1048519584505929700,
  #     "Server Name": "unholy court"
  #   },
  #   "-NJspZxgb1nbm_hRhPyi": {
  #     "Category ID": 1053925337270067200,
  #     "Log Channel ID": 1053926749819387900,
  #     "Server ID": 1051828511477866500,
  #     "Server Name": "୨୧ vae’s shop !"
  #   },
  #   "-NMcZNx_KwiI7Vhq12vM": {
  #     "Category ID": 914563885653168300,
  #     "Log Channel ID": 949416779099304100,
  #     "Server ID": 914563885653168300,
  #     "Server Name": "Test"
  #   },
  #   "-NOXsMSsGhI9hAQrdco7": {
  #     "Category ID": 1022286019845951500,
  #     "Log Channel ID": 1022286652514783200,
  #     "Server ID": 1022286019845951500,
  #     "Server Name": "DERT"
  #   },
  #   "-NO_GpJk3Jyx7NKySyTs": {
  #     "Category ID": 1076513934774911000,
  #     "Log Channel ID": 884122369776578700,
  #     "Server ID": 755418695362281500,
  #     "Server Name": "Aincrad Genshin Community"
  #   },
  #   "-NPsm2lmpU7NakaAaD-4": {
  #     "Category ID": 1082406288794861700,
  #     "Log Channel ID": 1082411196076003300,
  #     "Server ID": 1081186835285414000,
  #     "Server Name": "🌙 ,         ; constellations  <   .   ‹𝟹hearts + RVMP!"
  #   },
  #   "-NQB4hWlcYFcqeENIPS3": {
  #     "Category ID": 1083741321073791000,
  #     "Log Channel ID": 1083745698614366500,
  #     "Server ID": 717029019270381600,
  #     "Server Name": "Genshin Impact Cafe ♡"
  #   },
  #   "-NSFKWXWCFTjomaukcV9": {
  #     "Category ID": 1093053525304545400,
  #     "Log Channel ID": 1074838945730408600,
  #     "Server ID": 1074838945730408600,
  #     "Server Name": "✧ The Holy Lyre┊Server decor • Genshin • Social • SFW"
  #   }
  # }
    
  #     for key, value in data.items():
  #       ref.push().set(value)
      


async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Team(bot))
  await bot.add_cog(ManualTeamSelection(bot))