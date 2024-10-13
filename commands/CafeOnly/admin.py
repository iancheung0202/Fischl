import discord, firebase_admin, random, datetime, asyncio, time, re
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View
from commands.CafeOnly.createLevelImage import createLevelImage
from commands.CafeOnly.createLevelImageTevyatTimes import createLevelImageTevyatTimes
import pandas as pd

class ServerLeaveButton(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Leave', style=discord.ButtonStyle.red, custom_id='leaveserver')
  async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.defer(thinking=True)
    try:
      serverID = int(interaction.message.embeds[0].description.split("**")[4])
      server = interaction.client.get_guild(serverID)
      await server.leave()
      await interaction.followup.send(f":door::man_running: <-- {server.name}.")
      await interaction.message.delete()
    except Exception as e:
      await interaction.followup.send(f"Sorry, something went wrong. Please see the following error: \n`{e}`")

class LeaksAccessTT(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Genshin Leaks', style=discord.ButtonStyle.red, custom_id='genshinleaksaccesstt')
  async def genshinleaksaccesstt(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "Genshin Leaks" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="Genshin Leaks")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You **no longer** have the <@&1264025814933049457> role, and you can no longer access Genshin Impact leaks.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1264025814933049457> role. You can now access Genshin Impact leaks at <#1217789786094440530> and discuss them at <#1137343583813378078>!", ephemeral=True)

  @discord.ui.button(label='HSR Leaks', style=discord.ButtonStyle.red, custom_id='hsrleaksaccesstt')
  async def hsrleaksaccesstt(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "HSR Leaks" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="HSR Leaks")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You **no longer** have the <@&1264025834587557972> role, and you can no longer access Honkai: Star Rail leaks.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1264025834587557972> role. You can now access Honkai: Star Rail leaks at <#1217790706236522529> and discuss them at <#1191019220125892648>!", ephemeral=True)

  @discord.ui.button(label='WuWa Leaks', style=discord.ButtonStyle.red, custom_id='wuwaleaksaccesstt')
  async def wuwaleaksaccesstt(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "WuWa Leaks" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="WuWa Leaks")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You **no longer** have the <@&1264025847317397605> role, and you can no longer access Wuthering Waves leaks.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1264025847317397605> role. You can now access Wuthering Waves leaks at <#1243045967889170464> and discuss them at <#1243046360488345721>!", ephemeral=True)

  @discord.ui.button(label='ZZZ Leaks', style=discord.ButtonStyle.red, custom_id='zzzleaksaccesstt')
  async def zzzleaksaccesstt(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "ZZZ Leaks" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="ZZZ Leaks")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You **no longer** have the <@&1264026568234369145> role, and you can no longer access Zenless Zone Zero leaks.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1264026568234369145> role. You can now access Zenless Zone Zero leaks at <#1259404045718650941> and discuss them at <#1259404070532153344>!", ephemeral=True)

class LeaksAccess(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

 
  @discord.ui.button(label='Genshin Leaks', style=discord.ButtonStyle.red, custom_id='genshinleaksaccess')
  async def genshinleaksaccess(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "Genshin Leaks" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="Genshin Leaks")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      hasLeakAnnouncementRole = False
      for x in interaction.user.roles:
        if "Genshin Leaks Announcement" == x.name:
          hasLeakAnnouncementRole = True
      if hasLeakAnnouncementRole:
        await interaction.user.remove_roles(discord.utils.get(interaction.guild.roles,name="Genshin Leaks Announcement"))
        await interaction.response.send_message("You **no longer** have the <@&1209662193918804128> and <@&1254822637029425254> role, and you can no longer access Genshin Impact leaks.", ephemeral=True)
      else:
        await interaction.response.send_message("You **no longer** have the <@&1209662193918804128> role, and you can no longer access Genshin Impact leaks.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1209662193918804128> role. You can now access Genshin Impact leaks at <#1227871884364877824> and discuss them at <#1181785348452384768>!\n\n*<:Zhongli_read:939199615117447248> Tip: You can also get pinged for important leaks announcement by clicking on `Genshin Leaks Announcement`*", ephemeral=True)
        
  @discord.ui.button(label='HSR Leaks', style=discord.ButtonStyle.red, custom_id='hsrleaksaccess')
  async def hsrleaksaccess(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "HSR Leaks" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="HSR Leaks")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      hasLeakAnnouncementRole = False
      for x in interaction.user.roles:
        if "HSR Leaks Announcement" == x.name:
          hasLeakAnnouncementRole = True
      if hasLeakAnnouncementRole:
        await interaction.user.remove_roles(discord.utils.get(interaction.guild.roles,name="HSR Leaks Announcement"))
        await interaction.response.send_message("You **no longer** have the <@&1209662255227084881> and <@&1254822679718924408> role, and you can no longer access Honkai: Star Rail leaks.", ephemeral=True)
      else:
        await interaction.response.send_message("You **no longer** have the <@&1209662255227084881> role, and you can no longer access Honkai: Star Rail leaks.", ephemeral=True)
    else:
      await interaction.user.add_roles(role)
      await interaction.response.send_message("You have **obtained** the <@&1209662255227084881> role. You can now access Honkai: Star Rail leaks at <#1227872005370548394> and discuss them at <#1196982949783011338>!\n\n*<:Zhongli_read:939199615117447248> Tip: You can also get pinged for important leaks announcement by clicking on `HSR Leaks Announcement`*", ephemeral=True)

 
  @discord.ui.button(label='Genshin Leaks Announcement', style=discord.ButtonStyle.grey, custom_id='genshinleaksannouncement')
  async def genshinleaksannouncement(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "Genshin Leaks Announcement" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="Genshin Leaks Announcement")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You **no longer** have the <@&1254822637029425254> role, and you will not be notified for important Genshin Impact leaks.", ephemeral=True)
    else:
      hasLeakRole = False
      for x in interaction.user.roles:
        if "Genshin Leaks" == x.name:
          hasLeakRole = True
      if hasLeakRole:
        await interaction.user.add_roles(role)
        await interaction.response.send_message("You have **obtained** the <@&1254822637029425254> role. You will now be **pinged** for important Genshin Impact leaks at <#1227871884364877824>!", ephemeral=True)
      else:
        await interaction.response.send_message(embed=discord.Embed(title="Attention Required :x:", description="You must first obtain the `Genshin Leaks` role before performing this action.", color=0xFF0000), ephemeral=True)
        
        
  @discord.ui.button(label='HSR Leaks Announcement', style=discord.ButtonStyle.grey, custom_id='hsrleaksannouncement')
  async def hsrleaksannouncement(self, interaction: discord.Interaction, button: discord.ui.Button):
    alreadyHave = False
    for role in interaction.user.roles:
      if "HSR Leaks Announcement" == role.name:
        alreadyHave = True
    role = discord.utils.get(interaction.guild.roles,name="HSR Leaks Announcement")
    if alreadyHave:
      await interaction.user.remove_roles(role)
      await interaction.response.send_message("You **no longer** have the <@&1254822679718924408> role, and you will not be notified for important Honkai: Star Rail leaks.", ephemeral=True)
    else:
      hasLeakRole = False
      for x in interaction.user.roles:
        if "HSR Leaks" == x.name:
          hasLeakRole = True
      if hasLeakRole:
        await interaction.user.add_roles(role)
        await interaction.response.send_message("You have **obtained** the <@&1254822679718924408> role. You will now be **pinged** for important Honkai: Star Rail leaks at <#1227872005370548394>!", ephemeral=True)
      else:
        await interaction.response.send_message(embed=discord.Embed(title="Attention Required :x:", description="You must first obtain the `HSR Leaks` role before performing this action.", color=0xFF0000), ephemeral=True)

class OnMemberUpdate(commands.Cog): 
  def __init__(self, bot):
    self.client = bot

  @commands.Cog.listener() 
  async def on_member_update(self, before, after):
    if after.guild.id == 717029019270381578 and discord.utils.get(after.guild.roles,name="Level 1 - Slime") in after.roles and discord.utils.get(after.guild.roles,name="Level 1 - Slime") not in before.roles:
      levelRole = discord.utils.get(after.guild.roles,name="Level 0 - Newbie")
      await after.remove_roles(levelRole)
        
        

class AdminPower(commands.Cog): 
  def __init__(self, bot):
    self.client = bot

  @commands.Cog.listener() 
  async def on_message(self, message):
        
    if message.content == "-tableofcontents" and message.guild.id == 717029019270381578:
      await message.delete()
      messages = [msg async for msg in message.channel.history(limit=None, oldest_first=True)]
      tableOfContent = ""
      for msg in messages:
        msgContent = msg.content
        try:
          tableOfContent = f"{tableOfContent}- [{msgContent.split('**')[1]}]({msg.jump_url})\n"
        except Exception:
          pass
        
      embed = discord.Embed(title=message.channel.name, description=tableOfContent, color=discord.Color.default())
      await message.channel.send(embed=embed)
        
    if message.content == "-notifyevent" and message.author.id == 692254240290242601:
      event = await message.guild.fetch_scheduled_event(1254943111927566366)
      users = [user async for user in event.users(limit=None)]
      print(users)
      print(len(users))
      print(event.user_count)
      numbers = [142665031543291904, 169462312128872448, 184784169904242688, 218339761234903040, 229639858082021376, 230541476323524609, 236890234938195969, 244933438598021121, 257557528726994944, 258199562542383104, 262633351482048515, 270293528154865666, 293328050307727362, 298409568822755339, 302004779297669120, 308790501568544768, 315568206427455488]

      embed1 = discord.Embed(description="""*So, here's the thing: someone went and tinkered with my Synesthesia Beacon, so now every time you muddle-fudgers hear me chinwaggin' with those shirtbags, it's all a bunch of "fudge this" and "fork that..." See what I'm sayin'?*

═════════ ⋆★⋆ ═════════""", color=0x651f19)
      embed1.set_author(name="Boothill", icon_url="https://pbs.twimg.com/media/F9WqCYpbkAAJIIx.jpg")
      embed1.set_footer(text="discord.gg/traveler • Andrew Russell", icon_url="https://discord.do/wp-content/uploads/2023/08/Genshin-Impact-Cafe-%E2%99%A1.jpg")
      embed2 = discord.Embed(description="""✪ ***Hoyo's Café*** is pleased to announce the arrival of a talk with **Andrew Russell**, the voice of **Boothill in Honkai: Star Rail**!

✪ We present you with a  once-in-a-lifetime chance for Boothill fans and the rest of the Honkai: Star Rail community to interact with one of the beloved Hoyoverse casts!

✪ **Event Time**: The event will occur on **<t:1720962000>** and will last for around an hour.""", color=0x651f19)
      embed2.set_footer(text="You received this message because you indicated that you are interested in the event.")
      ian = message.guild.get_member(692254240290242601)
      await ian.send("## Event happening <t:1720962000:R>\nhttps://discord.gg/r8yjUsXQue?event=1254943111927566366", embeds=[embed1, embed2])
      #raise Exception()
      for u in users:
        try:
          if u == None or u.id in numbers:
            continue
          await u.send("## Event happening <t:1720962000:R>\nhttps://discord.gg/r8yjUsXQue?event=1254943111927566366", embeds=[embed1, embed2])
          print(u.id)
        except Exception as e:
          print(e)

        
    if message.content.startswith("-getchannelcontent") and message.author.id == 692254240290242601:
      chnid = int(message.content.split(" ")[1])
      CHANNEL = self.client.get_channel(chnid)
      messages = [message async for message in CHANNEL.history(limit=None)]
      f = open(f"./assets/channelcontent.html", "w")
      f.write(f"<title>{CHANNEL.name}</title><body style='background-color: #303338; color: white; font-family: sans-serif, Arial; padding: 10px;'>")
      lastUser = None
      for msg in reversed(messages):
        try:
          avatarURL = msg.author.avatar.url
        except Exception:
          avatarURL = 'https://discord.com/assets/5d6a5e9d7d77ac29116e.png'
        if lastUser != msg.author.id or lastUser == None:
          avatar = f"<img src='{avatarURL}' height='50px' style='border-radius: 50%'> <span style='position: relative;top: -30px;color:{msg.author.color};'>{msg.author.name} <code>({msg.author.id})</code></span>"
        else:
          avatar = ""
        if msg.content != "":
          f = open(f"./assets/channelcontent.html", "a+")
          f.write(f"""{avatar}<p style='position: relative;left: 54px;top:-37px;'>{msg.content}</p>""")
          f.close()
        for attachment in msg.attachments:
          f = open(f"./assets/channelcontent.html", "a+")
          if ".png" in attachment.proxy_url or ".jpg" in attachment.proxy_url or ".gif" in attachment.proxy_url:
            f.write(f"""{avatar}<p style='position: relative;left: 50px;'><img src='{attachment.proxy_url}' width='25%'></p>""")
            f.close()
          elif ".mp4" in attachment.proxy_url or ".mov" in attachment.proxy_url or ".wmv" in attachment.proxy_url or ".mp3" in attachment.proxy_url or ".m4a" in attachment.proxy_url or ".wav" in attachment.proxy_url or ".wma" in attachment.proxy_url:
            f.write(f"""{avatar}<br><br><div style='background-color: #a9a9a9;padding: 6px;border-radius: 2px;width:20%;vertical-align:middle;position: relative;left: 50px;'><a href='{attachment.proxy_url}' download style='color: white;text-decoration:none'><img src='https://i.pinimg.com/originals/d0/78/22/d078228e50c848f289e39872dcadf49d.png' height='20px'>&nbsp;&nbsp;&nbsp;&nbsp;{attachment.filename}</a></div>""")
            f.close()
          else:
            f.write(f"""{avatar}<p style='position: relative;left: 50px;'><i>Attachment with unsupported file format</i></p>""")
            f.close()
        for embed in msg.embeds:
          f = open(f"./assets/channelcontent.html", "a+")
          if embed.title != None or embed.description != None:
            f.write(f"""{avatar}""")
          if embed.title != None:
            f.write(f"""<p style='position: relative;left: 50px;border-left: 8px solid {embed.color};padding-left:4px;'><b>{embed.title}</b></p>""")
          if embed.description != None:
            f.write(f"""<p style='position: relative;left: 50px;border-left: 8px solid {embed.color};padding-left:4px;'><small>{embed.description}</small></p>""")
        # if embed.title != None or embed.description != None:
        #   f.write(f"""</span>""")
          f.close()
        lastUser = msg.author.id
          
      embed = discord.Embed(title=f"**Transcript** of #**{CHANNEL.name}**", color=discord.Color.blurple())
      await message.channel.send(embed=embed, file=discord.File(f"./assets/channelcontent.html"))
        
    if message.content == "-tgotrole" and message.guild.id == 717029019270381578:
      count = 0
      list = []
      role = message.guild.get_role(1258916464002465954)
      for member in message.guild.members:
        tgot = self.client.get_guild(749418356926578748)
        tgot_member = tgot.get_member(member.id)
        if tgot_member == None:
          continue
        else:
          if int(tgot_member.joined_at.timestamp()) < 1720940400 and role not in member.roles and not(member.bot):
            print(count)
            count += 1
            #list.append({"id": member.id, "name": member.name, "joined_cafe": member.joined_at.timestamp(), "joined_tgot": tgot_member.joined_at.timestamp()})
            await member.add_roles(role)
      #df = pd.DataFrame(list)
      #await message.channel.send(df.head(10))
      await message.channel.send(f"{count} users added.")
    
    ### CAFE LEVELLING UP CARD ###
    if message.author.id == 437808476106784770 and message.channel.id == 1229161238274244749 and "has reached" in message.content:
      #member = message.author
      id = int(message.content.split("**")[1].replace("<@", "").replace(">", ""))
      member = message.guild.get_member(id)
      level = int(message.content.split("**")[3])
      for role in member.roles:
        if "Level" in role.name:
          levelRole = role
          break
    
      filename = await createLevelImage(member, level, levelRole)
      chn = message.guild.get_channel(1229165255318569011)
      await chn.send(message.content, file=discord.File(filename))
    
    ### TEVYAT TIMES LEVELLING UP CARD ###
    if message.channel.id == 1253526260844335124: #  and message.author.id == 989173789482975262
      #member = message.author
      id = int(message.content.replace("<@", "").replace(">", ""))
      member = message.guild.get_member(id)
      level = int(message.embeds[0].description.split("to ")[1].replace("!", "").strip())
      method = message.embeds[0].description.split("from")[1].split("level")[0].strip()
      for role in member.roles:
        if "Level" in role.name:
          levelRole = role
          break
    
      filename = await createLevelImageTevyatTimes(member, level, levelRole, method)
      chn = message.guild.get_channel(1206124237513957416)
      roles = { 100: "Zhongli - Level 100", 90: "Neuvillette - Level 90", 75: "Xiao - Level 75", 69: "Wanderer - Level 69", 45: "Hu Tao - Level 45", 35: "Kazuha - Level 35", 20: "Lynette - Level 20", 10: "Xingqiu - Level 10", 5: "Barbara - Level 5", 3: "Amber - Level 3", }
      try:
        roleName = roles[int(level)]
        await chn.send(f"{message.content} has reached level **{level}** in {method}! GG!\nYou've earned the `{roleName}` role!", file=discord.File(filename))
      except KeyError:
        await chn.send(f"{message.content} has reached level **{level}** in {method}! GG!", file=discord.File(filename))
        
    if message.author == self.client.user or message.author.bot == True: 
        return
    
    if "-webhook" in message.content:
      webhook = await self.client.fetch_webhook(1201759841916289036)
      msg = await webhook.send("Hmmm", embed=discord.Embed(color=discord.Colour.random(), description="HMMM"), wait=True)
      await message.channel.send(msg.jump_url)
      #await msg.create_thread(name="Happy bday")
        
    ### ADD LEVEL 0 TO THOSE WHO DOES NOT HAVE A LEVEL ROLE ###
    if message.content == "-addlevel0toall":
      members = message.guild.members
      levelRole = discord.utils.get(message.guild.roles,name="Level 0 - Newbie")
      for member in members:
        hasALevel = False
        for role in member.roles:
          if "Level " in role.name:
            hasALevel = True
            break
        if not hasALevel:
          await member.add_roles(levelRole)
          print(member.name)
    
    ### LEAKS ACCESS REACTION ROLE ###
    if message.guild.id == 717029019270381578 and message.content == "-leaksaccess":
      await message.delete()
      embed = discord.Embed(title="<:Raidenjoy:995502902271545407> Select below to gain access to leaks-related channels!", description="By selecting the button(s), you acknowledge that leaked content remains unverified, subject to changes, and is against Hoyoverse's Terms of Service. We kindly request maintaining a respectful manner when discussing leaks. Please do not spread misinformation or share any unauthorized leaks, as it may result in a permanent removal of your access to the leaks channel.\n\n> **If you wish to remove your access to the leaks channel, you can simply click on the button(s) again.**\n\n*You can get an optional role for getting pinged for important leaks announcement after getting the respective leaks role.*", color=0x2B2C31)
      await message.channel.send(embed=embed, view=LeaksAccess())
    
    ### TEVYAT TIMES LEAKS ACCESS REACTION ROLE ###
    if message.guild.id == 1137341346504519680 and message.content == "-leaksaccess":
      await message.delete()
      embed = discord.Embed(title="<:Raidenjoy:995502902271545407> Select below to gain access to leaks-related channels!", description="By selecting the button(s), you acknowledge that leaked content remains unverified, subject to changes, and is against each games' Terms of Service. We kindly request maintaining a respectful manner when discussing leaks. Please do not spread misinformation or share any unauthorized leaks, as it may result in a permanent removal of your access to the leaks channel.\n\n> **If you wish to remove your access to the leaks channel, you can simply click on the button(s) again.**", color=0x2B2C31)
      await message.channel.send(embed=embed, view=LeaksAccessTT())

    ### LEAVE SERVERS THAT ARE BELOW 100 MEMBERS ###
    if message.author.id == 692254240290242601 and message.content == "-leaveservers":
      for guild in self.client.guilds:
        name = guild.name

        if len(guild.members) < 100:
          await guild.leave()

          await message.channel.send(f"Left {name}")
          await asyncio.sleep(10)

    ###
    if message.author.id == 692254240290242601 and message.content == "-serversid":
      list = []
      for guild in self.client.guilds:
        list.append(guild.id)
      await message.channel.send(list)


    if message.author.id == 692254240290242601 and message.content == "-allservers":
      for guild in self.client.guilds:
        print(guild.name)
        user = guild.get_member(self.client.user.id)
        embed = discord.Embed(title="Basic Server Information", description=f"""
        **Server Name:** {guild.name}
        **Server ID:** {guild.id}
        **Members Count:** {len(guild.members)}
        **Joined:** <t:{int(float(time.mktime(user.joined_at.timetuple())))}:R>
        """, colour=0x2dc6f9)
        try:
          embed.set_footer(icon_url=guild.icon.url, text=guild.name)
        except Exception:
          pass
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        config = discord.Embed(title="Server Configuration", description=f"The configuration for **{guild.name}** is as follows:", color=0x1DBCEB)
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
          if (value["Server ID"] == guild.id):
            CATEGORY_ID = value["Category ID"]
            LOGCHANNEL_ID = value["Log Channel ID"]
            found = True
            break
        if not found:
          config.add_field(name="Ticket System", value="<:no:1036810470860013639> Disabled", inline=True)
        else:
          config.add_field(name="Ticket System", value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Category:** <#{CATEGORY_ID}>\n<:reply:1036792837821435976> **Log Channel:** <#{LOGCHANNEL_ID}>", inline=True)
        ref = db.reference("/Co-Op")
        coop = ref.get()
        found = False
        for key, value in coop.items():
          if (value["Server ID"] == guild.id):
            CO_OP_CHANNEL_ID = value["Co-op Channel ID"]
            NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
            EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
            ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
            SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
            found = True
            break

        if not found:
          config.add_field(name="Co-op System", value="<:no:1036810470860013639> Disabled", inline=True)
        else:
          config.add_field(name="Co-op System", value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Co-op Channel:** <#{CO_OP_CHANNEL_ID}>\n<:reply:1036792837821435976> **NA Helper Role:** <@&{NA_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **EU Helper Role:** <@&{EU_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **Asia Helper Role:** <@&{ASIA_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **SAR Helper Role:** <@&{SAR_HELPER_ROLE_ID}>", inline=True)
        ref = db.reference("/Sticky Messages")
        stickies = ref.get()
        found = False
        stickiedchannels = []
        for channel in guild.text_channels:
          for key, val in stickies.items():
            if val['Channel ID'] == channel.id:
              stickiedchannels.append(channel.id)
              found = True
        if not found:
          config.add_field(name="Sticky Messages", value="<:no:1036810470860013639> Disabled", inline=True)
        else:
          x = "<:yes:1036811164891480194> Enabled\n"
          for chn in stickiedchannels:
            x = f"{x}<:reply:1036792837821435976> <#{chn}>\n"
          config.add_field(name="Sticky Messages", value=x, inline=True)
        ref = db.reference("/Welcome")
        welcome = ref.get()
        found = False
        for key, val in welcome.items():
          if val['Server ID'] == guild.id:
            welcomeChannel = val["Welcome Channel ID"]
            welcomeImageEnabled = val["Welcome Image Enabled"]
            found = True
            break
        if not found:
          config.add_field(name="Welcome Messages", value="<:no:1036810470860013639> Disabled", inline=False)
        else:
          x = f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Welcome Channel:** <#{welcomeChannel}>\n"
          if welcomeImageEnabled:
            x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** `Uploaded`\n"
          else:
            x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** ` Not uploaded`\n"
          config.add_field(name="Welcome Messages", value=x, inline=False)
        try:
          server_invite = await guild.text_channels[0].create_invite(max_age = 604800, max_uses = 0)
          await message.channel.send(f"{server_invite}", embeds=[embed,config], view=ServerLeaveButton())
        except Exception as e:
          print(e)
          await message.channel.send(f"`SERVER DISABLED INVITE CREATION`", embeds=[embed,config], view=ServerLeaveButton())


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



    if message.author.id == 692254240290242601 and "-getDMs" in message.content:
      user_ids = [int(message.content.split(" ")[1])]
      await message.channel.send("Ok.")
      for id in user_ids:
        content = ""
        member = await self.client.fetch_user(id)
        # member = guild.get_member(973865405162586142)
        if member.dm_channel is not None:
          await member.create_dm()
          async for message in member.dm_channel.history():
            if message.author != self.client.user:
              content += f"{message.content}\n"
        else:
          print("No DMs found")
          raise Exception()

        await message.channel.send(f"```----------------------```\n{member} ({member.id})\n\n{content}\n")



    if message.author.id == 692254240290242601 and message.guild.id == 717029019270381578 and message.content == "-2024":
      embed = discord.Embed(color=0xfebe98, title="2024 Happy New Year", description="""Time flies! Can you believe it's 2024 already?! Our cafe staff, management, and ownership team would like to express our heartfelt gratitude to our wonderful community for making the past year memorable. 

> To celebrate that like last year, we are offering all of you the exclusive <@&1191109570450432060> role **for a limited period of time**! *You will no longer be able to obtain this role <t:1706774340:R>.*
### Along with this New Year gift for all of you, we have added the following to our server:
- Introduced <#1191073948088143994> for our <@&943486837559791618>
- <#1117479725120630915> is back! You can now :star: your favorite messages!
- [Ban appeal form](https://forms.gle/yajGFJnVj9oASiv6A) has been created!
- Added brand new level perks listed [here](https://discord.com/channels/717029019270381578/1136074090550153307/1191103741244477470)
- More perks for being <@&1111002520442110052> in <#1110998569466474716>
- Automatic partnership feature in [tickets](https://discord.com/channels/717029019270381578/1083745974402420846)

*We hope you enjoy our latest server update! Feel free to leave any <#1107010468440186970> for us if have any! Stay tuned for future <#1083634013287219240> :eyes:. *

Wish you a fantastic and splendid new year ahead! :calendar_spiral: 

> ## React :tada: below to get the limited exclusive <@&1191109570450432060> role!""")
      embed.set_image(url="https://media.discordapp.net/attachments/1113863279803117648/1191129721187074170/Untitled572_20231230042034.png")

      embed.set_footer(icon_url=message.guild.icon.url, text=f"{message.guild.name} • #{message.channel.name}")

      await message.delete()
      await message.channel.send(content="**Happy New Year, <@&1083687810340507668>!** No matter where you are, Genshin Impact Cafe would like to extend heartfelt New Year wishes to you, your family and friends a happy New Year. May your journey be filled with excitement and success through the unfolding chapters of 2024! :calendar_spiral::sparkles:", embed=embed)

    if message.guild.id == 717029019270381578 and message.content == "-loyalpaimon":
      role = message.guild.get_role(996707492853710888)
      for member in message.guild.members:
        if ("discord.gg/traveler" in str(member.activity) or "gg/traveler" in str(member.activity)) and role not in member.roles:
          await member.add_roles(role)
          embed = discord.Embed(description=f":green_circle: {after.mention} has **added** vanity link to their status.")
          embed.set_footer(text="Role added")
          chn = self.client.get_channel(1083804717886488686)
          await chn.send(embed=embed)
          await message.channel.send(f"**{member.name}** ({member.id}) now has the role.")
        
    if message.guild.id == 717029019270381578 and message.author.id == 692254240290242601 and message.content == "-dmallpartners":
      role = message.guild.get_role(1227058079753834506);
      count = 0
      for member in role.members:
        try:
          embed = discord.Embed(title="Attention travelers!", description="""**Session 2** of the skribbl.io Team Challenge is happening right now!""", color=discord.Color.blurple())
          button = Button(label="Visit Announcement Channel", style=discord.ButtonStyle.link, url="https://discord.com/channels/717029019270381578/1083867254728433787")
          view = View()
          view.add_item(button)
          await member.send(embed=embed,view=view)
          count += 1
        except Exception:
          pass
      await message.reply(f"{count} messages sent.")


async def setup(bot): 
  await bot.add_cog(AdminPower(bot))
  await bot.add_cog(OnMemberUpdate(bot))