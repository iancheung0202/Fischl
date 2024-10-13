import discord, firebase_admin, random, datetime, asyncio, time, re
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View

class BuildPanel(discord.ui.View):
  def __init__(self):
    self.list = list
    super().__init__(timeout=None)
    x = Button(label="Genshin Build Coordination", style=discord.ButtonStyle.link, url="https://discord.com/channels/717029019270381578/1167272897870569592")
    self.add_item(x)
    y = Button(label="HSR Build Coordination", style=discord.ButtonStyle.link, url="https://discord.com/channels/717029019270381578/1226640558341099590")
    self.add_item(y)

  @discord.ui.button(label='Overseers', style=discord.ButtonStyle.green, custom_id='buildoverseers')
  async def overseers(self, interaction: discord.Interaction, button: discord.ui.Button):
    roles = [1167237629637570571, 1227716082178068530]
    msg = ""
    for roleID in roles:
      role = interaction.guild.get_role(roleID)
      roleMention = role.mention
      msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
      for member in role.members:
        msg = f"{msg}- {member.mention} `({member.id})`\n"
      
    embed = discord.Embed(title="Build Experts Overseers List", description=f"**The following list consists of all our build experts overseers:**\n{msg}", color=0xa0cde4)
    await interaction.response.edit_message(embed=embed, view=BuildPanel())

  @discord.ui.button(label='Experts', style=discord.ButtonStyle.blurple, custom_id='buildexperts')
  async def experts(self, interaction: discord.Interaction, button: discord.ui.Button):
    roles = [987249271403343893, 1196992769584025640]
    msg = ""
    for roleID in roles:
      role = interaction.guild.get_role(roleID)
      roleMention = role.mention
      msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
      for member in role.members:
        msg = f"{msg}- {member.mention} `({member.id})`\n"
      
    embed = discord.Embed(title="Build Experts List", description=f"**The following list consists of all our build experts:**\n{msg}", color=0xa0cde4)
    await interaction.response.edit_message(embed=embed, view=BuildPanel())

  @discord.ui.button(label='Training', style=discord.ButtonStyle.grey, custom_id='buildexpertsintraining')
  async def training(self, interaction: discord.Interaction, button: discord.ui.Button):
    roles = [1167496178645078178, 1233135427981021206]
    msg = ""
    for roleID in roles:
      role = interaction.guild.get_role(roleID)
      roleMention = role.mention
      msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
      for member in role.members:
        msg = f"{msg}- {member.mention} `({member.id})`\n"
      
    embed = discord.Embed(title="Build Experts in Training List", description=f"**The following list consists of all our build experts in training:**\n{msg}", color=0xa0cde4)
    await interaction.response.edit_message(embed=embed, view=BuildPanel())
    

async def toggleRoles(message, member, role, removeOnly=False):
  if removeOnly: # NO MESSAGE!
    await member.remove_roles(role)
    return
  alreadyHave = False
  for x in member.roles:
    if role.name.lower() in x.name.lower():
      alreadyHave = True
  if alreadyHave:
    await member.remove_roles(role)
    await message.channel.send(f"Removed **{role.name}** from **{member.name}**")
  else:
    await member.add_roles(role)
    await message.channel.send(f"Added **{role.name}** to **{member.name}**")

async def only_emotes(message):
    emote_with_id_pattern = r'<:\w+:\d+>'
    emote_without_id_pattern = r':\w+:'
    unicode_emoji_pattern = (
        r'[\U0001F600-\U0001F64F]|'  # Emoticons
        r'[\U0001F300-\U0001F5FF]|'  # Misc Symbols and Pictographs
        r'[\U0001F680-\U0001F6FF]|'  # Transport and Map Symbols
        r'[\U0001F700-\U0001F77F]|'  # Alchemical Symbols
        r'[\U0001F780-\U0001F7FF]|'  # Geometric Shapes Extended
        r'[\U0001F800-\U0001F8FF]|'  # Supplemental Arrows-C
        r'[\U0001F900-\U0001F9FF]|'  # Supplemental Symbols and Pictographs
        r'[\U0001FA00-\U0001FA6F]|'  # Chess Symbols
        r'[\U0001FA70-\U0001FAFF]|'  # Symbols and Pictographs Extended-A
        r'[\U00002700-\U000027BF]|'  # Dingbats
        r'[\U000024C2-\U0001F251]|'  # Enclosed characters
        r'[\U0001F1E0-\U0001F1FF]|'  # Flags
        r'[\U0001F900-\U0001F9FF]|'  # Supplemental Symbols and Pictographs
        r'[\U0001FA70-\U0001FAFF]|'  # Symbols and Pictographs Extended-A
        r'[\U0001F018-\U0001F0F5]|'  # Domino Tiles
        r'[\U0001F0A0-\U0001F0AE]|'  # Mahjong Tiles
        r'[\U0001F004-\U0001F004]|'  # Mahjong Tiles Alternate
        r'[\U0001F170-\U0001F171]|'  # Enclosed Alphanumeric Supplement
        r'[\U0001F17E-\U0001F17E]|'  # Enclosed Alphanumeric Supplement Alternate
        r'[\U0001F17F-\U0001F17F]|'  # Enclosed Alphanumeric Supplement Alternate
        r'[\U0001F18E-\U0001F18E]|'  # Enclosed Alphanumeric Supplement Alternate
        r'[\U0001F191-\U0001F19A]|'  # Enclosed Alphanumeric Supplement Alternate
        r'[\U0001F1E6-\U0001F1FF]'   # Flags
    )
    combined_pattern = f'({emote_with_id_pattern}|{emote_without_id_pattern}|{unicode_emoji_pattern}|\s)+'
    emote_regex = re.compile(combined_pattern)
    return bool(emote_regex.fullmatch(message))

async def is_link(url):
    regex = re.compile(
        r'^(https?:\/\/)?' # http:// or https://
        r'(([A-Za-z0-9$-_@.&+!*"(),])+(\:[A-Za-z0-9$-_@.&+!*"(),]+)?@)?' # user:pass@
        r'((([A-Za-z0-9][A-Za-z0-9-]{0,61})?[A-Za-z0-9]\.)+[A-Za-z]{2,6}\.?' # domain...
        r'|localhost|' # localhost...
        r'(\d{1,3}\.){3}\d{1,3})' # ...or ipv4
        r'(:\d+)?' # optional port
        r'(\/[A-Za-z0-9$-_@.&+!*"(),]*)*' # path
        r'(\?[A-Za-z0-9$-_@.&+!*"(),%=]*)?' # query string
        r'(\#[A-Za-z0-9$-_@.&+!*"(),%=]*)?$' # fragment locator
    )
    if "discord.com" in url:
        return False
    return re.match(regex, url) is not None

async def is_sticker(message):
    return len(message.stickers) > 0

class CustomCommands(commands.Cog): 
  def __init__(self, bot):
    self.client = bot

  @commands.Cog.listener() 
  async def on_message(self, message):
        
    if message.author == self.client.user or message.author.bot == True: 
      return

    ### NO TWO CONSECUTIVE MSGS BY SINGLE PERSON
    """
    if message.guild.id == 717029019270381578:
      counter = 0
      msgJumpLink = None
      async for msg in message.channel.history(limit=2):
        onlyEmotes = await only_emotes(msg.content)
        onlyLinks = await is_link(msg.content)
        onlyStickers = await is_sticker(msg)
        if msg.author == message.author and (onlyEmotes or onlyLinks or onlyStickers):
          counter += 1
          if msg != message:
            msgJumpLink = msg.jump_url
      if counter == 2:
        await message.delete()
        warning = await message.channel.send(f"{message.author.mention}, no two emotes/GIFs/links/stickers messages in a row")
        logchn = self.client.get_channel(1083644560594436178)
        if message.content != "":
          desc = message.content
        else:
          desc = f"[Sticker]({message.stickers[0].url})"
        embed = discord.Embed(title=f"**Message Blocked by Fischl**", description=desc)
        embed.set_author(name=message.author.name, url=f"https://discord.com/users/{message.author.id}", icon_url=message.author.avatar.url)
        embed.set_footer(text="Reason: Two consecutive emotes/GIFs/links/stickers")
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Previous Message", value=f"[Jump to message]({msgJumpLink})")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await logchn.send(embed=embed)
        await asyncio.sleep(3)
        await warning.delete()
    """

    ### NO MORE THAN 5 CONSECUTIVE MSGS BY MULTIPLE PERSON
    channelIDs = [1104212482312122388, 1083850546676498462, 1104556774423547964, 1181237921756487760, 1083737514944254023, 1083788035864404039, 1083738044173139999, 1196982873287311501, 1237653103772172288, 1205677453922799668, 1196990772088668160, 1196988766972281003, 1181785348452384768, 1196982949783011338]
    if message.guild.id == 717029019270381578 and message.channel.id in channelIDs:
      counter = 0
      msgJumpLink = None
      async for msg in message.channel.history(limit=6, oldest_first=True):
        onlyEmotes = await only_emotes(msg.content)
        onlyLinks = await is_link(msg.content)
        onlyStickers = await is_sticker(msg)
        if onlyEmotes or onlyLinks or onlyStickers:
          counter += 1
          if msg != message:
            msgJumpLink = msg.jump_url
      if counter == 6:
        await message.delete()
        warning = await message.channel.send(f"{message.author.mention}, too many emotes/GIFs/links/stickers in a row")
        logchn = self.client.get_channel(1083644560594436178)
        if message.content != "":
          desc = message.content
        else:
          desc = f"[Sticker]({message.stickers[0].url})"
        embed = discord.Embed(title="**Message Blocked by Fischl**", description=desc)
        embed.set_author(name=message.author.name, url=f"https://discord.com/users/{message.author.id}", icon_url=message.author.avatar.url)
        embed.set_footer(text="Reason: Too many emotes/GIFs/links/stickers in a row")
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Previous Message", value=f"[Jump to message]({msgJumpLink})")
        await asyncio.sleep(3)
        await warning.delete()

    
    if message.guild.id == 717029019270381578 and str(message.content).startswith("-artist"):
      artTeamRole = message.guild.get_role(1185149073947361462)
      artTeamLeadRole = message.guild.get_role(1185148937275986031)
      if artTeamRole in message.author.roles or artTeamLeadRole in message.author.roles:
        member = message.guild.get_member(int(message.content.split(" ")[1].replace("<@", "").replace(">", "")))
        await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="Talented Artists"))
        
    if message.guild.id == 717029019270381578 and message.content == "-experts":
      roles = [1167237629637570571, 1227716082178068530]
      msg = ""
      for roleID in roles:
        role = message.guild.get_role(roleID)
        roleMention = role.mention
        msg = f"{msg}\n{roleMention} *(x{len(role.members)})*\n"
        for member in role.members:
          msg = f"{msg}- {member.mention} `({member.id})`\n"
      
      embed = discord.Embed(title="Build Experts Overseers List", description=f"**The following list consists of all our build experts overseers:**\n{msg}", color=0xa0cde4)
      await message.channel.send(embed=embed, view=BuildPanel())
    elif message.guild.id == 717029019270381578 and str(message.content).startswith("-expert"):
      genshinOverseer = message.guild.get_role(1167237629637570571)
      hsrOverseer = message.guild.get_role(1227716082178068530)
      if genshinOverseer in message.author.roles or hsrOverseer in message.author.roles:
        member = message.guild.get_member(int(message.content.split(" ")[1].replace("<@", "").replace(">", "")))
        game = message.content.split(" ")[2].strip().lower()
        if game.startswith("g"): #Genshin
          position = message.content.split(" ")[3].strip().lower()
          if position.startswith("t"): #Training
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="✯✯ Genshin Builds Experts ✯✯"), removeOnly=True)
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="Genshin Builds Experts in Training"))
          elif position.startswith("e"): #Expert
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="Genshin Builds Experts in Training"), removeOnly=True)
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="✯✯ Genshin Builds Experts ✯✯"))
        elif game.startswith("h"): #HSR
          position = message.content.split(" ")[3].strip().lower()
          if position.startswith("t"): #Training
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="✯✯ HSR Builds Experts ✯✯"), removeOnly=True)
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="HSR Builds Experts in Training"))
          elif position.startswith("e"): #Expert
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="HSR Builds Experts in Training"), removeOnly=True)
            await toggleRoles(message, member, discord.utils.get(message.guild.roles,name="✯✯ HSR Builds Experts ✯✯"))


async def setup(bot): 
  await bot.add_cog(CustomCommands(bot))