import discord, firebase_admin, datetime, asyncio, time, emoji
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

maxlimit = 30
teams = ["Team Mondstadt", "Team Liyue", "Team Inazuma", "Team Sumeru"]
leaderRoles = ["Grand Master", "Tianshu", "Shogun", "Grand Sage"]
leaders = [954888790936281208, 1026905370339311626, 1034670871182319667, 973865405162586142]
teamchannels = [1058137622872084510, 1058137551807979582, 1058137487786123264, 1058137351416729610]

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
      await message.channel.send(embed=discord.Embed(title="Select your favourite team!", description="> **🛷 Team Mondstadt:** Led by <@954888790936281208>\n> **☃ Team Liyue:** Led by <@1026905370339311626>\n> **🎄 Team Inazuma:** Led by <@1034670871182319667>\n> **🎁 Team Sumeru:** Led by <@973865405162586142>\n\n**Exclusive role for Jan 2023 only:** \nJoin any team to receive the exclusive <@&1058145940868960256> role!"), view=TeamSelectionButtons())
      await message.delete()
      
    if message.guild.id == 717029019270381578 and message.content == "-teamchallengesinfo":
      await message.delete()
      await message.channel.send(embed=discord.Embed(title="Team Details & Challenges Info"))
      await message.channel.send(embed=discord.Embed(title="`Team Selection Details`", description="Members can freely join, switch or leave teams from the start to the 15th day of the month, but no longer can switch, join or leave teams when a team challenge is happening."))
      await message.channel.send(embed=discord.Embed(title="`Team Challenges Details`", description=f"""- Happens once a month from the **15th day to the end of the month**.
- The goal is for team members to work collectively towards a goal (the fastest team to reach the goal/the highest or best among all the teams)
- If a team wins the challenge for the previous month, they will be awarded the title "Team of the Month" for that month as well as +1 "Team Trophy".
- At the end of the year, the team with the most "Team Trophy" will win an exclusive custom role applied to all members, as well as an exclusive prize (TBC in late 2023).
- At the end of the year, the person with the most "Credits" will get an exclusive role as well as an exclusive prize (TBC)
- The **maximum number of team members** in each team is currently **{maxlimit}**.
"""))
      await message.channel.send(embed=discord.Embed(title="`Team Leaders' Requirements`", description="""- Must be level 50+ in the server.
- Must have a good record of behavior in the server.
- Must be able to commit to leading the team for an extensive period of time.
"""))
      await message.channel.send(embed=discord.Embed(title="`Team Leaders' Privilege & Restrictions`", description="""- Can freely transfer team leadership to any team member at any given moment.
- Have manage channels and manage message permissions in his or her team's private chat channel.
- If his or her team wins a challenge, he or she can recommend the next challenge for the month. Leaders can select challenges possibly favorable to their own team as long as it does not violate the rules of the server nor violate the principles or purpose of team challenges. Server owners will try to honor your request whenever possible.
- Cannot leave their own team unless it is officially deleted/the team leadership is officially transferred.
- Must maintain as a good role model and act in good faith in the server.
- Do not annoy people when advertising within or outside the server. Appropriate recruitment is okay. 
"""))
      await message.channel.send(embed=discord.Embed(title="`Team Members' Privilege`", description="""- Access to a private team chat channel.
- If the team he or she belongs to wins a monthly challenge, he or she will win 5 extra levels in Arcane as well as 5 "Credits".
- Can collectively decide to overthrow a team leader with 90% of existing team members upvoting (the new team leader will be the one with the highest level/XP in Arcane before the vote).
"""))
      await message.channel.send(embed=discord.Embed(title="`Team Deletion Process`", description="Team deletion is a huge matter, especially if your team has a large number of team members. Please talk to one of our owners directly before leaving or abandoning your team to see if we can work things out, most likely by having you transfer your leadership to someone else. "))
      await message.channel.send(embed=discord.Embed(title="`Owners reserve the following rights`", description="""- Remove or transfer the team leadership to anyone else if deemed necessary
- Disagree with the winning team leader's suggestion for the next challenge
- Remove Credits from anyone if deemed necessary
- Move anyone from one team to another if one team has a disproportionately large number of team members and may lead to unfairness
- Increase the maximum number of team members in each team at anytime
"""))
    
    if message.guild.id == 717029019270381578 and message.content == "-initteamtrophy":
      ref = db.reference("/Team Trophy")
      teamtrophy = ref.get()

      for team in ["Team Mondstadt", "Team Liyue", "Team Inazuma", "Team Sumeru"]:
        data = {
          message.guild.id: {
            "Team Name": team,
            "Team Trophy": 0,
          }
        }
    
        for key, value in data.items():
          ref.push().set(value)
    
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

    if message.guild.id == 717029019270381578 and "-give2023roleto:" in message.content: # GIVE 5 CREDITS TO THE ENTIRE TEAM
      team = message.content.split(":")[1].strip()
      teamrole = discord.utils.get(message.guild.roles,name=team)

      for member in teamrole.members:
        await member.add_roles(message.guild.get_role(1058145940868960256))

        await message.channel.send(f"{member} role added")


async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Team(bot))
  await bot.add_cog(ManualTeamSelection(bot))