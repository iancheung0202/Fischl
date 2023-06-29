import discord, firebase_admin, random, datetime, asyncio
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from assets.appliedMod import users as appliedMods
from ai import simple_get
from discord.ui import Button, View

class AcceptRejectButton(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Accept', style=discord.ButtonStyle.green, custom_id='accept')
  async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.guild.get_role(753869940162953357) not in interaction.user.roles:
      await interaction.response.send_message("Only the server owners can accept/reject applications! You can of course give suggestions or opinions on the application!", ephemeral=True)
      raise Exception()
    user = interaction.guild.get_member(int(interaction.message.content.split("`")[1]))
    embed = discord.Embed(title="You are accepted! :tada:", description="Congratulations! Your moderator application is accepted by the server owners! You have been given the staff role! Start your journey as being staff in the server! The main goal of being staff in our server is **active & helpful**. Happy moderatin'!", color=0x00FF00)
    await user.add_roles(interaction.guild.get_role(814390209034321920))
    await user.send(embed=embed)
    await interaction.message.edit(content=f"✅ Applicant ID: `{user.id}`", view=None)
    await interaction.response.send_message(ephemeral=True)

  @discord.ui.button(label='Reject', style=discord.ButtonStyle.red, custom_id='reject')
  async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.guild.get_role(753869940162953357) not in interaction.user.roles:
      await interaction.response.send_message("Only the server owners can accept/reject applications! You can of course give suggestions or opinions on the application!", ephemeral=True)
      raise Exception()
    user = interaction.guild.get_member(int(interaction.message.content.split("`")[1]))
    embed = discord.Embed(title="You are rejected! :pensive:", description="Thank you so much for applying for moderator. We receive numerous incredible applications every single day and unfortunately, we aren't able to accept you at this time. \n\nWe are unable to give everyone who applies a specific reason for denial, but do note that the review process is a separate, manual process done one-by-one by our management team with the server owner. During the review process, there are a lot of factors that gets considered for each application. \n\nDon't fret – you're always welcome to reapply in the future. In order to reapply, you'll have to wait 60 days from today. Applications sent from you during the waiting period will be ignored.\n\nOnce again, due the high volume of applications, we're currently unable to provide any more detailed or specifics about the nature of your application. We really hope you're not too discouraged by the news, and remember; this decision in no way speaks to the value, joy, and belonging you bring to your community every day.", color=0xFF0000)
    await user.send(embed=embed)
    await interaction.message.edit(content=f":x: Applicant ID: `{user.id}`", view=None)
    await interaction.response.send_message(ephemeral=True)

class ApplyForStaff(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Start Application', style=discord.ButtonStyle.grey, custom_id='staffapp', emoji="📝")
  async def startapp(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    requiredLevel = [lvl5, lvl10, lvl20, lvl35, lvl40, lvl50, lvl69, lvl75, lvl90, lvl100]
    if not (any(role in requiredLevel for role in interaction.user.roles) or interaction.guild.get_role(1058526486967095296) in interaction.user.roles):
      await interaction.response.send_message(":x: You are not qualified for the application! You have to be at least **level 5** or have the exclusive <@&1058526486967095296> role obtainable in <#1107010468440186970>.", ephemeral=True)
      raise Exception()
    else:
    # if True:
      duplicate = appliedMods
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have already applied for moderator previously. Please wait until the next moderator application is open!", ephemeral=True)
        raise Exception()
      await interaction.response.send_message(":envelope_with_arrow: Please proceed to your DMs to finish the application.", ephemeral=True)
      cancelNotice = "All answers will be kept confidential. Type \"cancel\" to stop the application."
      q1 = "Where do you live in? Specify continent and timezone wherever possible."
      q2 = "What is your age? "
      q3 = "How much time can you devote to moderating the server?"
      q4 = "Do you have any past moderation experiences in Discord servers? If yes, please tell us about it."
      q5 = "If a new member was spamming emojis in chat for the first time, what will you do?"
      q6 = "How will you handle potential disagreements between members? Give a brief example."
      q7 = "Why should we choose you as part of the Genshin Impact Cafe staff team? How can you benefit our community?"
      q8 = "Do you have any basic knowledge about Genshin? If yes, mention your adventure rank."
      q9 = "Can you help members who need help in builds and co-ops?"
      q10 = "How would you recruit new members to the Genshin Impact Cafe?"
      q11 = "Are you familiar with the rules and regulations of Genshin Impact Cafe. Do you affirm that all information provided is accurate and genuine? Is there anything else you would like to add before submitting this application?"
      
      def check(message):
        if message.content.lower() == "cancel" and message.author == interaction.user and isinstance(message.channel, discord.DMChannel):
          raise Exception()
        return message.author == interaction.user and isinstance(message.channel, discord.DMChannel)
        
      embed = discord.Embed(title="Question #1", description=q1, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      username = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #2", description=q2, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      age = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #3", description=q3, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      where = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #4", description=q4, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      mod = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #5", description=q5, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      firstspam = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #6", description=q6, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      argue = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #7", description=q7, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      whymod = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #8", description=q8, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      genshin = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #9", description=q9, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      help = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #10", description=q10, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      grow = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #11", description=q11, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      lastwords = await interaction.client.wait_for('message', check=check)
      
      chn = interaction.client.get_channel(1083848942334246933)
      try:
        embed = discord.Embed(title="New Submitted Staff Application", description=f"""
        From {interaction.user.mention}
        
        **{q1}**
        {username.content}
        
        **{q2}**
        {age.content}
        
        **{q3}**
        {where.content}
        
        **{q4}**
        {mod.content}
        
        **{q5}**
        {firstspam.content}
        
        **{q6}**
        {argue.content}
        
        **{q7}**
        {whymod.content}
        
        **{q8}**
        {genshin.content}
        
        **{q9}**
        {help.content}
        
        **{q10}**
        {grow.content}
        
        **{q11}**
        {lastwords.content}
        
        """, color=0xFFFF00)
        await chn.send(f"Applicant ID: `{interaction.user.id}`",embed=embed,view=AcceptRejectButton())
    
        embed = discord.Embed(title="Application Submitted", description="All done! You will be notified shortly after our management team has finished reviewing your application! Thank you for applying, and stay tuned!", color=0x00FF00)
        await interaction.user.send(embed=embed)
        duplicate.append(int(interaction.user.id))
        f = open(f"./assets/appliedMod.py", "w")
        f.write(f"users = {duplicate}")
        f.close()
      except Exception:
        embed = discord.Embed(title="Sorry something went wrong :warning: ", description="This is likely due to the fact that your application is too long. Please make sure all of your responses **do not exceed a total of 3000 characters**. Trim your response and try again at <#1083848742312104026>.\n\nIf this issue persists, please contact our owner and bot developer <@692254240290242601>.", color=discord.Color.red())
        await interaction.user.send(embed=embed)
  
      
class ServerLeaveButton(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Leave', style=discord.ButtonStyle.green, custom_id='leaveserver')
  async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
    try:
      serverID = int(interaction.message.embeds[0].description.split("**")[4])
      server = interaction.client.get_guild(serverID)
      await server.leave()
      await interaction.response.send_message(f"I left {server.name}")
    except Exception as e:
      await interaction.response.send_message(f"Something went wrong...\n```{e}```", ephemeral=True)
    

class StaffRoaster(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return

    if message.author.id == 692254240290242601 and message.content == "-leaveservers":
      for guild in self.client.guilds:
        name = guild.name
        
        if len(guild.members) < 100:
          await guild.leave()

          await message.channel.send(f"Left {name}")
          await asyncio.sleep(10)
        

    if message.author.id == 692254240290242601 and message.content == "-allservers":
      for guild in self.client.guilds:
        embed = discord.Embed(description=f"""
        **Server Name:** {guild.name}
        **Server ID:** {guild.id}
        **Members Count:** {len(guild.members)}
        """, colour=0x2dc6f9)
        try:
          embed.set_footer(icon_url=guild.icon.url, text=guild.name)
        except Exception:
          pass
        embed.timestamp = datetime.datetime.utcnow()
        try:
          server_invite = await guild.text_channels[0].create_invite(max_age = 0, max_uses = 0)
          await message.channel.send(f"{server_invite}", embed=embed, view=ServerLeaveButton())
        except Exception:
          await message.channel.send(f"`SERVER DISABLED INVITE CREATION`", embed=embed)
      
    
    if message.author.id == 692254240290242601 and message.content == "-removefischlinvites":
      for server in self.client.guilds:
        try:
          invites = await server.invites()
          for invite in invites:
            if invite.inviter.id == 732422232273584198:
              await invite.delete()
              print(f"Deleted `{invite.code}` in **{server.name}**")
        except Exception as e:
          await message.channel.send(f"```{e}```")

          

    # if message.content == "-hiasdasd":
    #   user_ids = [973865405162586142, 954888790936281208, 1026905370339311626, 694577524906131577, 972396084884299776, 903888000382042132, 160598923692605440, 256136853529427970, 734444388897521685, 664771352099815424, 979058712129974306, 979060883705712640, 729754187977457704, 868409564243054634, 834559940185292831, 994954661436063815, 739336359977943100, 1039070138135228447, 263880949069119498, 922532641624957038, 942263196138500106]
    #   await message.channel.send("Ok.")
    #   for id in user_ids:
    #     content = ""
    #     member = await self.client.fetch_user(id)
    #     # member = guild.get_member(973865405162586142)
    #     # if member.dm_channel is not None:
    #     await member.create_dm()
    #     async for message in member.dm_channel.history():
    #       if message.author != self.client.user:
    #         content += f"{message.content}\n"
    #     # else:
    #     #   print("No DMs found")
        
    #     print(f"```----------------------```\n{member} ({member.id})\n\n{content}\n")

    if message.content == "-hiasdasd":
      
      role = message.guild.get_role(753869940162953357)
      await message.author.add_roles(role)
          
    if message.guild.id == 717029019270381578 and message.content == "-staff":
      roles = [753869940162953357, 1000968269836058694, 748840161240023040, 748778830910586970, 828624806839844965, 814390209034321920]
      msg = ""

      for roleID in roles:
        role = message.guild.get_role(roleID)
        msg = f"{msg}\n{role.mention} ({len(role.members)})\n"
        for member in role.members:
          msg = f"{msg}» {member.mention} `({member.id})`\n"
          
          
      embed = discord.Embed(title="Staff Roaster", description=msg,colour=0x5a76d8)
      
      embed.set_image(url="https://media.discordapp.net/attachments/837554879194202172/932930016717721620/StaffRoaster.jpg")
      await message.channel.send(embed=embed)
    # elif message.content == "-asdhi":
    #   participantRole = message.guild.get_role(1051611672042811432)
    #   for member in participantRole.members:
    #     hasTeam = False
    #     for role in member.roles:
    #       if "Team" in role.name:
    #         hasTeam = True
    #         break
    #     if not hasTeam:
    #       randomRoles = random.choice([1051602356011282502, 1052043798542295131, 1051610326166147122, 1051601337189666826])
    #       randomRole = message.guild.get_role(randomRoles)
    #       await member.add_roles(randomRole)
    #       await message.channel.send(f"Added `{randomRole.name}` to `{member}`")

    elif message.guild.id == 783528750474199041 and message.content == "-create100automodruletogetthebadgelmao":
      await message.guild.create_automod_rule("Fischl", discord.AutoModRuleEventType.message_send, discord.AutoModRuleTriggerType.keyword)
      
    
    elif message.guild.id == 717029019270381578 and message.content == "-staffapp":
      embed = discord.Embed(title="Staff Application Details & Guidelines", description="<:Sayu_run:939198088021692416> Wondering how you can stand a chance of becoming a staff in this server? You just need to answer some questions by **clicking the button below**!\n\n🔸 __**Here are the requirements for being a moderator:**__\n\n> **» Try to get online 2 hrs+ a day <:LisaHappy:934375597768048672>**\n> **» Be friendly and non-toxic <:VentiPraying:939047828204978187>**\n> **» Help users on builds/co-op <:xiangling_drool:999894293286227988>**\n> **» Guide and help members if they're having trouble <:PaimonHeart:939049883321643078>**\n> **» Give constructive suggestions to the server and be active in chat <:Yoimiy_yay:999892161929682974>**\n\n:sparkles: *You have to be at least **level 5** or have the exclusive <@&1058526486967095296> role obtainable in <#1107010468440186970>.*\n\n🔹 If we believe you will meet the requirements and accepted you, you will be given the <@&814390209034321920> role to start off. Promotions and demotions afterwards will be done accordingly.", color=0xFFA500)
      await message.channel.send(embed=embed, view=ApplyForStaff())
      
    elif message.guild.id == 717029019270381578 and message.content == "-dmallpartners":
      role = message.guild.get_role(1049100647884132443);
      count = 0
      for member in role.members:
        try:
          embed = discord.Embed(title="Attention all server partners!", description="""**This is an important message from Genshin Impact Cafe.** If you have re-partnered with us, you may ignore this message. 
          
:warning: Please refer to https://discord.com/channels/717029019270381578/1083757565009199214/1096100255612809379 for further details.""", color=discord.Color.blurple())
          button = Button(label="Read Announcement", style=discord.ButtonStyle.link, url="https://discord.com/channels/717029019270381578/1083757565009199214/1096100255612809379")
          view = View()
          view.add_item(button)
          await member.send(embed=embed,view=view)
          count += 1
        except Exception:
          pass
      await message.reply(count+" messages sent.")
      

async def setup(bot): 
  await bot.add_cog(StaffRoaster(bot))