import discord, firebase_admin, datetime, asyncio, time, emoji, random, re
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont, ImageColor

CO_OP_CHANNEL_ID = 1083737900623085608
#CO_OP_CHANNEL_ID = 1083650021351751700

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
    coop_channel = interaction.client.get_channel(CO_OP_CHANNEL_ID)
    if "NA" in self.title:
      helperRole = interaction.guild.get_role(950655921003036682)
      embedTitle = "NA Region Co-op Request"
      embedColor = 0x6161F9
    elif "EU" in self.title:
      helperRole = interaction.guild.get_role(950655926518562828)
      embedTitle = "EU Region Co-op Request"
      embedColor = 0x50C450
    elif "Asia" in self.title:
      helperRole = interaction.guild.get_role(950655925033775114)
      embedTitle = "Asia Region Co-op Request"
      embedColor = 0xF96262
    elif "SAR" in self.title:
      helperRole = interaction.guild.get_role(950655922760470569)
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
    await interaction.response.send_message("Co-op Request Sent ✅", ephemeral=True)
    async for msg in interaction.channel.history(limit=5):
      if msg.author == interaction.client.user and "Welcome to Genshin Impact co-op!" in msg.embeds[0].title:
        await msg.delete()
    embed=discord.Embed(title="Welcome to Genshin Impact co-op! 🎉", description=f"### Select a region below to start requesting for co-op. \n\n*Type `-giverep @user (# of reps)` in the threads to thank the user who helped you. Click below to learn more about the reputation system.*", color=0x09AEC5)
    embed.set_image(url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png")
    embed.set_footer(text=f"{interaction.guild.name} • #{interaction.channel.name}", icon_url=interaction.guild.icon.url)
    await interaction.channel.send(embed=embed, view=CoOpButtonView())
    
class CoOpClaimedView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Claimed', style=discord.ButtonStyle.green, custom_id='accepthelp', disabled=True)
  async def accepthelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass

  @discord.ui.button(label='Close', style=discord.ButtonStyle.red, custom_id='closehelp')
  async def closehelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    await closeCoOpRequest(interaction)

  @discord.ui.button(label='Copy Raw UID', style=discord.ButtonStyle.grey, custom_id='copyrawuid')
  async def copyrawuid(self, interaction: discord.Interaction, button: discord.ui.Button):
    uid = ''.join([char for char in str(interaction.message.embeds[0].fields[0]) if char.isdigit()])
    await interaction.response.send_message(uid, ephemeral=True)
    
class CoOpView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Claim', style=discord.ButtonStyle.green, custom_id='accepthelp')
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
    correct = False
    if "NA" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == 950655921003036682:
          correct = True
          break
    elif "EU" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == 950655926518562828:
          correct = True
          break
    elif "Asia" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == 950655925033775114:
          correct = True
          break
    elif "SAR" in interaction.message.embeds[0].title:
      for role in interaction.user.roles:
        if role.id == 950655922760470569:
          correct = True
          break
    if not(correct):
      await interaction.response.send_message("**:warning: Warning:** You don't have the corresponding region co-op helper role, but you can still coordinate with the member. You can obtain the **region co-op helper roles** at <id:customize> if you haven't already done so!", ephemeral=True)
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

  @discord.ui.button(label='Close', style=discord.ButtonStyle.red, custom_id='closehelp')
  async def closehelp(self, interaction: discord.Interaction, button: discord.ui.Button):
    await closeCoOpRequest(interaction)

  @discord.ui.button(label='Copy Raw UID', style=discord.ButtonStyle.grey, custom_id='copyrawuid')
  async def copyrawuid(self, interaction: discord.Interaction, button: discord.ui.Button):
    uid = ''.join([char for char in str(interaction.message.embeds[0].fields[0]) if char.isdigit()])
    await interaction.response.send_message(uid, ephemeral=True)
    
class CoOpViewResolved(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)
  @discord.ui.button(label='Co-op Resolved', style=discord.ButtonStyle.grey, custom_id='closehelp', disabled=True)
  async def resolved(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass

class CoOpButtonView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='NA', style=discord.ButtonStyle.blurple, custom_id='nacoop')
  async def na(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))

  @discord.ui.button(label='EU', style=discord.ButtonStyle.blurple, custom_id='eucoop')
  async def eu(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))
    
  @discord.ui.button(label='Asia', style=discord.ButtonStyle.blurple, custom_id='asiacoop')
  async def asia(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))
    
  @discord.ui.button(label='SAR', style=discord.ButtonStyle.blurple, custom_id='sarcoop')
  async def sar(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_modal(CoOpHelpModal(title=f"Request Co-op Help - {str(button.label)}"))
    
  @discord.ui.button(label='Reputation System', style=discord.ButtonStyle.grey, custom_id='repsystemcoop')
  async def howToUseCoOp(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="", description="### **After someone helps you in co-op, be sure to thank them by giving them Rep Points!**\n\n\nTo give rep use the following command:\n```-giverep @(user) (rep points)```\n> Example:  -giverep <@716976882062458940>  2\n### Point System:\n> 1 rep ~ 5 domain runs\n> 1 rep ~ 5 leylines\n> 1 rep ~ 4 Boss runs\n> 1 rep ~ Weekly bosses\n> 1 rep ~ Weekly Reputation Bounties\n> 1 rep ~ Daily commissions\n> 1 rep ~ Farming mobs\n\n*Please **round up** if your number of runs is 1 or 2 away from the next number (i.e. 2 rep for 8-9 domain runs).*\n\n**__Example:__**\n8 domain runs (2 rep) + daily commissions (1 rep) + 3 boss runs (1 rep) = **4 reps**\n\n*You can use **`-rep`** to check your current rep points.*", color=0x1DC220)
    await interaction.response.send_message(embed=embed, ephemeral=True)
        
    
    
class CoOpSendView(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.content == "-cooppanel":
      embed=discord.Embed(title="Welcome to Genshin Impact co-op! 🎉", description=f"### Select a region below to start requesting for co-op. \n\n*Type `-giverep @user (# of reps)` in the threads to thank the user who helped you. Click below to learn more about the reputation system.*", color=0x09AEC5)
      embed.set_image(url="https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png")
      embed.set_footer(text=f"{message.guild.name} • #{message.channel.name}", icon_url=message.guild.icon.url)
      await message.channel.send(embed=embed, view=CoOpButtonView())

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(CoOpSendView(bot))