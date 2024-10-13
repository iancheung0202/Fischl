import discord, firebase_admin, datetime, asyncio, time, emoji, random, re, aiohttp
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

async def closeCoOpRequest(interaction):
  match = re.search(r'<@(\d+)>', interaction.message.content)
  if match:
      userID = match.group(1)
  else:
      userID = " "
  if str(userID) == str(interaction.user.id) or interaction.user.guild_permissions.administrator:
    embed = interaction.message.embeds[0]
    content = interaction.message.content
    emote_pattern = r'<:[^:]+:[0-9]+>'
    modifiedContent = re.sub(emote_pattern, '✅', content)
    modifiedContent = re.sub(r'is requesting for.*', 'no longer needs co-op help.', modifiedContent)
    modifiedContent = modifiedContent.replace("**", "")
    await interaction.response.edit_message(content=modifiedContent, embed=embed, view=CoOpViewResolved())
  else:
    await interaction.response.send_message(":x: Only the user who requested for this help can perform this action.", ephemeral=True)

class CoOpHelpModal(discord.ui.Modal, title="Request Co-op Help"):

  uid = discord.ui.TextInput(label="Your UID", style=discord.TextStyle.short, placeholder="Your UID", required=True)
  wl = discord.ui.TextInput(label="Your World Level", style=discord.TextStyle.short, placeholder="Your world level", required=True)
  request = discord.ui.TextInput(label="Your Help Request", style=discord.TextStyle.long, placeholder="What do you need help on?", required=True)

  async def on_submit(self, interaction:discord.Interaction):
    ref = db.reference("/Co-Op")
    coop = ref.get()
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        CO_OP_CHANNEL_ID = value["Co-op Channel ID"]
        NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
        EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
        ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
        SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
        break
        
    coop_channel = interaction.client.get_channel(CO_OP_CHANNEL_ID)
    if "NA" in self.title:
      helperRole = interaction.guild.get_role(NA_HELPER_ROLE_ID)
      embedTitle = "NA Region Co-op Request"
      embedColor = 0x6161F9
    elif "EU" in self.title:
      helperRole = interaction.guild.get_role(EU_HELPER_ROLE_ID)
      embedTitle = "EU Region Co-op Request"
      embedColor = 0x50C450
    elif "Asia" in self.title:
      helperRole = interaction.guild.get_role(ASIA_HELPER_ROLE_ID)
      embedTitle = "Asia Region Co-op Request"
      embedColor = 0xF96262
    elif "SAR" in self.title:
      helperRole = interaction.guild.get_role(SAR_HELPER_ROLE_ID)
      embedTitle = "SAR Region Co-op Request"
      embedColor = 0xF7D31A
    
    embed=discord.Embed(title=embedTitle, description=f"### Reminders <:GanyuNote:945363905809621052>\n- Coordinate with each other in the **thread** below\n- **ONLY** click on **`Claim`** if **you are __100% sure__ you are helping**. \n- If you are the requester and **no longer need help**, click on **`Close`** to indicate that.", color=embedColor)
    embed.add_field(name="UID", value=str(self.uid), inline=True)
    embed.add_field(name="World Level", value=str(self.wl), inline=True)
    embed.add_field(name="Request", value=str(self.request))
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    emote = random.choice(["<:Caelus_wotagei:1201045083038957710>", "<:LittleHelper:950048975464042576>", "<:GanyuNote:945363905809621052>", "<:MonaObserve_:999895139029897256>", "<:Lumine_hello:1067352181990248509>", "<:Yae_hi:1227139070631874633>"])
    msg = await coop_channel.send(content=f"**{emote} {interaction.user.mention} is requesting for co-op** - {helperRole.mention}", embed=embed, view=CoOpView())
    await msg.create_thread(name=f"{interaction.user.name} - {embedTitle}", auto_archive_duration=1440)
    await interaction.response.send_message(f"[Co-op Request Sent ✅]({msg.jump_url})", ephemeral=True)
    #################
    """
    async for msg in interaction.channel.history(limit=5):
      if msg.author == interaction.client.user and "Welcome to Genshin Impact co-op!" in msg.embeds[0].title:
        await msg.delete()
    embed=discord.Embed(title="Welcome to Genshin Impact co-op! 🎉", description=f"### Select a region below to start requesting for co-op. \n\n*Type `-giverep @user (# of reps)` in the threads to thank the user who helped you. Click below to learn more about the reputation system.*", color=0x09AEC5)
    embed.set_image(url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png")
    embed.set_footer(text=f"{interaction.guild.name} • #{interaction.channel.name}", icon_url=interaction.guild.icon.url)
    await interaction.channel.send(embed=embed, view=CoOpButtonViewSystem())
    """
    #################
    
class CoOpClaimedView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Claimed', style=discord.ButtonStyle.green, custom_id='accepthelpsystem', disabled=True)
  async def accepthelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass

  @discord.ui.button(label='Close', style=discord.ButtonStyle.red, custom_id='closehelpsystem')
  async def closehelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    await closeCoOpRequest(interaction)

  @discord.ui.button(label='Copy Raw UID', style=discord.ButtonStyle.grey, custom_id='copyrawuidsystem')
  async def copyrawuid(self, interaction: discord.Interaction, button: discord.ui.Button):
    uid = ''.join([char for char in str(interaction.message.embeds[0].fields[0]) if char.isdigit()])
    await interaction.response.send_message(uid, ephemeral=True)
    
class CoOpView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Claim', style=discord.ButtonStyle.green, custom_id='accepthelpsystem')
  async def accepthelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    thread = await interaction.guild.fetch_channel(interaction.message.id)
    match = re.search(r'<@(\d+)>', interaction.message.content)
    if match:
        userID = match.group(1)
    else:
        userID = " "
    if str(userID) == str(interaction.user.id):
      await interaction.response.send_message("You want to help yourself? :joy:", ephemeral=True)
      raise Exception("Helping yourself in co-op")
    if str(interaction.user.id) in interaction.message.embeds[0].description:
      await interaction.response.send_message("You already claimed the request, smh.", ephemeral=True)
      raise Exception("Already claimed request")
        
    ref = db.reference("/Co-Op")
    coop = ref.get()
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
        EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
        ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
        SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
        break
        
    correct = False
    if "NA" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == NA_HELPER_ROLE_ID:
          correct = True
          break
    elif "EU" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == EU_HELPER_ROLE_ID:
          correct = True
          break
    elif "Asia" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == ASIA_HELPER_ROLE_ID:
          correct = True
          break
    elif "SAR" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == SAR_HELPER_ROLE_ID:
          correct = True
          break
    if not(correct):
      await interaction.response.send_message("**:warning: Warning:** You don't have the corresponding region co-op helper role, but you can still coordinate with the member in the thread.", ephemeral=True)
      raise Exception("Don't have corresponding region co-op role")
    
    await thread.send(f"Request claimed by {interaction.user.mention}. ")
    embed = interaction.message.embeds[0]
    newEmbedDescription = f":star: *Claimed by {interaction.user.mention}* \n{embed.description}"
    embed.description = newEmbedDescription
    content = interaction.message.content
    if newEmbedDescription.count("Claimed by") >= 3:
      await interaction.message.edit(content=content, embed=embed, view=CoOpClaimedView())
    else:
      await interaction.message.edit(content=content, embed=embed, view=CoOpView())
    await interaction.response.send_message()

  @discord.ui.button(label='Close', style=discord.ButtonStyle.red, custom_id='closehelpsystem')
  async def closehelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    await closeCoOpRequest(interaction)

  @discord.ui.button(label='Copy Raw UID', style=discord.ButtonStyle.grey, custom_id='copyrawuidsystem')
  async def copyrawuid(self, interaction: discord.Interaction, button: discord.ui.Button):
    uid = ''.join([char for char in str(interaction.message.embeds[0].fields[0]) if char.isdigit()])
    await interaction.response.send_message(uid, ephemeral=True)
    
class CoOpViewResolved(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)
  @discord.ui.button(label='Co-op Resolved', style=discord.ButtonStyle.grey, custom_id='closehelpsystem', disabled=True)
  async def resolved(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass



class CoOpButtonViewSystem(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='NA', style=discord.ButtonStyle.blurple, custom_id='nasystem')
  async def na(self, interaction: discord.Interaction, button: discord.ui.Button):
    ref = db.reference("/Co-Op")
    coop = ref.get()
    found = False
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        found = True
        break
    if not found:
      embed = discord.Embed(title="Co-op system not enabled!", description=f'This server doesn\'t have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1246163431912898582> to setup the system!', colour=0xFF0000)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.followup.send(embed=embed, ephemeral=True)
      raise Exception("Category/log channel not found")
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))

  @discord.ui.button(label='EU', style=discord.ButtonStyle.blurple, custom_id='eusystem')
  async def eu(self, interaction: discord.Interaction, button: discord.ui.Button):
    ref = db.reference("/Co-Op")
    coop = ref.get()
    found = False
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        found = True
        break
    if not found:
      embed = discord.Embed(title="Co-op system not enabled!", description=f'This server doesn\'t have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1246163431912898582> to setup the system!', colour=0xFF0000)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.followup.send(embed=embed, ephemeral=True)
      raise Exception("Category/log channel not found")
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))
    
  @discord.ui.button(label='Asia', style=discord.ButtonStyle.blurple, custom_id='asiasystem')
  async def asia(self, interaction: discord.Interaction, button: discord.ui.Button):
    ref = db.reference("/Co-Op")
    coop = ref.get()
    found = False
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        found = True
        break
    if not found:
      embed = discord.Embed(title="Co-op system not enabled!", description=f'This server doesn\'t have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1246163431912898582> to setup the system!', colour=0xFF0000)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.followup.send(embed=embed, ephemeral=True)
      raise Exception("Category/log channel not found")
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))
    
  @discord.ui.button(label='SAR', style=discord.ButtonStyle.blurple, custom_id='sarsystem')
  async def sar(self, interaction: discord.Interaction, button: discord.ui.Button):
    ref = db.reference("/Co-Op")
    coop = ref.get()
    found = False
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        found = True
        break
    if not found:
      embed = discord.Embed(title="Co-op system not enabled!", description=f'This server doesn\'t have the co-op system enabled yet. Please ask the server admin to use </co-op setup:1246163431912898582> to setup the system!', colour=0xFF0000)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.followup.send(embed=embed, ephemeral=True)
      raise Exception("Category/log channel not found")
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))
    
    
@app_commands.guild_only()
class CoOp(commands.GroupCog, name="co-op"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "disable",
    description = "Disable co-op system in this server"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def coop_disable(
    self,
    interaction: discord.Interaction
  ) -> None:
    coop = db.reference('/Co-Op').get()
    found = False
    for key, val in coop.items():
        if val['Server ID'] == interaction.guild.id:
          db.reference('/Co-Op').child(key).delete()
          found = True
          break
    if found:
      embed = discord.Embed(title="Co-op system successfully disabled", description=f'You can use </co-op setup:1246163431912898582> at anytime to setup the co-op system again.', colour=0xFFFF00)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.response.send_message(embed=embed)
    else:
      embed = discord.Embed(title="We could not find your server", description=f'Maybe you have already disabled the co-op system in your server, or you have never enabled co-op system in the first place. Anyways, no records found in our system.', colour=0xFF0000)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.response.send_message(embed=embed, ephemeral=True)

    
  @app_commands.command(
    name = "panel",
    description = "Creates a customized co-op request panel (make sure it's separate from the co-op channel)"
  )
  @app_commands.describe(
    message = "The content of the message",
    title = "Makes the title of the embed",
    description = "Makes the description of the embed",
    color = "Sets the color of the embed",
    thumbnail = "Please provide a URL for the thumbnail of the embed (upper-right hand corner image)",
    image = "Please provide a URL for the image of the embed (appears at the bottom of the embed)",
    footer = "Sets the footer of the embed that appears at the bottom of the embed as small texts",
    footer_time = "Shows the time of the embed being sent?",
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def coop_panel(
    self,
    interaction: discord.Interaction,
    message: str = None,
    title: str = None,
    description: str = None,
    color: str = None,
    thumbnail: str = None,
    image: str = None,
    footer: str = None,
    footer_time: bool = None,
  ) -> None:
    # Converting color
    if color is not None:
      try:
        color = await commands.ColorConverter().convert(interaction, color)
      except:
        color = None
    if color is None:
      color = discord.Color.default()
    embed = discord.Embed(color=color)
    if title is not None:
      embed.title = title
    if description is not None:
      embed.description = description
    if thumbnail is not None:
      embed.set_thumbnail(url=thumbnail)
    if image is not None:
      embed.set_image(url=image)
    if footer is not None:
      embed.set_footer(text=footer)
    if footer_time is not None or footer_time == True:
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    msgContent = ""
    if message is not None:
      msgContent = message
    await interaction.channel.send(content=msgContent, embed=embed, view=CoOpButtonViewSystem())

    embed = discord.Embed(title="", description=f'**✅ Custom Co-op Panel Sent!** Make sure that the panel is correctly sent in a separate channel from the co-op request channel. Otherwise, the panel will get lost in the sea of requests. \n\n*Sent in the wrong channel? Delete the panel and use </co-op panel:1246163431912898582> in the correct channel!*', colour=0x00FF00)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
  @app_commands.command(
    name = "setup",
    description = "Setup co-op system in the server"
  )
  @app_commands.describe(
    co_op_channel = "The channel for all co-op requests (preferably separate from the request panel)",
    na_helper_role = "Co-Op NA Helper role",
    eu_helper_role = "Co-Op EU Helper role",
    asia_helper_role = "Co-Op Asia Helper role",
    sar_helper_role = "Co-Op SAR Helper role",
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def coop_setup(
    self,
    interaction: discord.Interaction,
    co_op_channel: discord.TextChannel,
    na_helper_role: discord.Role,
    eu_helper_role: discord.Role,
    asia_helper_role: discord.Role,
    sar_helper_role: discord.Role,
  ) -> None:
    ref = db.reference("/Co-Op")
    coop = ref.get()
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        embed = discord.Embed(title="Co-Op System already enabled!", description=f'Your co-op channel is already set as <#{value["Co-op Channel ID"]}> `({value["Co-op Channel ID"]})`\n\nPlease use </co-op panel:1246163431912898582> to create your own customized co-op panel.\n\nIf you wish to disable the co-op system, please use </co-op disable:1246163431912898582>.', colour=0xFF0000)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        raise Exception("Already existed!")

    data = {
      interaction.guild.name: {
          "Server Name": interaction.guild.name,
          "Server ID": interaction.guild.id,
          "Co-op Channel ID": co_op_channel.id,
          "NA Helper Role ID": na_helper_role.id,
          "EU Helper Role ID": eu_helper_role.id,
          "Asia Helper Role ID": asia_helper_role.id,
          "SAR Helper Role ID": sar_helper_role.id,
        }
    }

    for key, value in data.items():
    	ref.push().set(value)
    
    embed = discord.Embed(title="Co-op system successfully enabled!", description=f'The co-op channel is set as <#{co_op_channel.id}> `({co_op_channel.id})`. \n\n**All administrators can by default close any co-op requests for moderation purposes.** \n\nNow, please use </co-op panel:1246163431912898582> to create your own customized co-op panel.', colour=0x00FF00)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await interaction.response.send_message(embed=embed)
    
async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(CoOp(bot))