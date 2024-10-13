import discord, firebase_admin, sys, platform, psutil
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from firebase_admin import credentials, db
# from replit import db as replit_db

class Select(discord.ui.Select):
    def __init__(self, list, hoyocafe=False):
      self.list = list
      self.hoyocafe = hoyocafe
      utility = ""
      ticket = ""
      coop = ""
      topic = ""
      sticky = ""
      welcome = ""
      team = ""
      birthday = ""
      emotes = ""
      
      for command in self.list:
        if "ticket" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              ticket = f"{ticket}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
            else:
              ticket = f"{ticket}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
        
        elif "co-op" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              coop = f"{coop}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                coop = f"{coop}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              coop = f"{coop}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "welcome" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              welcome = f"{welcome}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                welcome = f"{welcome}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              welcome = f"{welcome}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "sticky" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              sticky = f"{sticky}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                sticky = f"{sticky}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              sticky = f"{sticky}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "team" in command.name and hoyocafe == True:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              team = f"{team}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                team = f"{team}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              team = f"{team}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "birthday" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              birthday = f"{birthday}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                birthday = f"{birthday}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              birthday = f"{birthday}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "emotes" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              emotes = f"{emotes}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                emotes = f"{emotes}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              emotes = f"{emotes}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif ("partnership" not in command.name and "team" not in command.name and "send-leaderboard" not in command.name and "birthday" not in command.name and "dm" not in command.name and "emotes" not in command.name and "afk" != command.name):
          utility = f"{utility} \n\n{command.mention}\n<:reply:1036792837821435976> {command.description}"
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              utility = f"{utility}\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                utility = f"{utility}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              utility = f"{utility}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"

        self.lyst = [
          [utility, "Utility Commands", "🛠️", "The following slash commands are used for basic functions that many bots offer. These commands are accessible to everyone in the server."],
          [ticket, "Ticket System", "🎫", "The following commands are used to setup and deal with tickets. To start using tickets instantly, use </ticket setup:1033188985587109910> and the bot will guide you through the procedures of setting up your ticket system! Note that these commands are only available to members with Administrator permission, meaning only Admins can close/delete tickets."],
          [coop, "Co-op System", "🎮", "The following commands are used to setup co-op system in your server. Use </co-op setup:1246163431912898582> to starting setting up the co-op system, and the bot will guide you through the procedures! Note that these commands are only available to members with Administrator permission, meaning only Admins can setup/manage the co-op system."],
          [sticky, "Sticky Messages", "🫧", "The following slash commands are for setting up sticky messages in different channels. Sticky messages will be stayed at the bottom of the channel no matter what messages are sent afterwards. This function is especially useful when you need give your members a heads up on how to use this chat channel or what they need to know before going ahead and sending any messages. To setup sticky messages, you may need Administrator permissions."],
          [welcome, "Welcome Messages", "👋", "The following slash commands are for setting up welcome messages in a server. If enabled, the bot will automatically greet new server members in a designated text channel. You can customize your own greetings to tailor to your server's needs. To setup welcome messages, you may need Administrator permissions."],
          [birthday, "Birthday Wishes", "🎂", "The following slash commands are for wishing users in your server a happy birthday. As a normal user, you can set your birthday to receive personalized birthday wishes in servers that have this system enabled. To setup birthday wishes in your server, you may need Administrator permissions."],
          [emotes, "Emote Manager", "🆒", "The following slash commands are for managing emojis in your server."]
        ]
        if hoyocafe:
          self.lyst.append([team, "Team Commands", "🏠", "The following slash commands are exclusively for teams in **Hoyo's Café | Genshin & HSR ♡**. For more details, visit <#1083866771376844881>."])
        options = []
        for item in self.lyst:
          options.append(discord.SelectOption(label=item[1], emoji=item[2]))
        super().__init__(placeholder="Browse Commands",max_values=1,min_values=1,options=options, custom_id="browsecommands")
        
    async def callback(self, interaction: discord.Interaction):
      for item in self.lyst:
        if self.values[0] == item[1]:
          intro = discord.Embed(title=f"{item[2]} {item[1]}", description=item[3], color=0xFFFF00)
          embed = discord.Embed(description=item[0], color=discord.Color.blurple())
          if interaction.guild.id == 717029019270381578:
            await interaction.response.edit_message(embeds=[intro, embed], view=HelpPanel(self.list, True))
          else:
            await interaction.response.edit_message(embeds=[intro, embed], view=HelpPanel(self.list))
          break

class HelpPanel(discord.ui.View):
  def __init__(self, list=None, hoyocafe=False):
    self.list = list
    self.hoyocafe = hoyocafe
    super().__init__(timeout=None)
    inviteButton = Button(label="Add to Server", style=discord.ButtonStyle.link, url="https://discord.com/api/oauth2/authorize?client_id=732422232273584198&permissions=8&scope=bot%20applications.commands")
    self.add_item(inviteButton)
    websiteButton = Button(label="Visit Website", style=discord.ButtonStyle.link, url="https://fischlbot.web.app/")
    self.add_item(websiteButton)
    self.add_item(Select(self.list, self.hoyocafe))

  @discord.ui.button(label='Overview', style=discord.ButtonStyle.blurple, custom_id='overview')
  async def overview(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Fischl Help", description=f"""Fischl is a Genshin-based Discord bot with lots of functions for Genshin Impact servers, namely a convenient ticket system and a random Genshin conversation starter. The bot also comes with a lot of utility-based features such as co-op system, sticky messages, welcome functions, or even customized Genshin-font texts.
    """, color=0x1DBCEB)
    embed.add_field(name="<:gi_cafe:1103720959950725190> Support Server", value=f"Head over to our [support server](https://discord.gg/traveler) if you have any suggestions, questions or bug reports! :writing_hand:", inline=True)
    embed.add_field(name="<:slash:1037445915348324505> Command Usage", value=f"This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` to see the list of available bot commands.", inline=True)
    
    if interaction.guild.id == 717029019270381578:
      await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list, True))
    else:
      await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list))

  @discord.ui.button(label='Statistics', style=discord.ButtonStyle.blurple, custom_id='statistics')
  async def statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Fischl Discord Bot Statistics", color=0x1DBCEB)
    mem_usage = psutil.virtual_memory()
    embed.add_field(name="<:info:1037445870469267638> Package Info", value=f"```OS - {platform.system()}\nPython - {platform.python_version()}\ndiscord.py - {discord.__version__}\nGoogle Firebase - {firebase_admin.__version__}```", inline=False)
    ref = db.reference('/Uptime')
    status = ref.get()
    for key, value in status.items():
      uptime = value["Uptime"]
      break
    embed.add_field(name="<:dev:1037445830749204624>  Bot Metadata", value=f"""> Application ID: `{interaction.client.application_id}`
> Last Reboot: <t:{uptime}:R>
> Servers Count: `{len(interaction.client.guilds)}`
> API/Bot Latency: `{int(round(interaction.client.latency * 1000, 1))}ms`""", inline=True)
    embed.add_field(name="📊  Bot Process Data", value=f"> CPU Usage: `{psutil.cpu_percent(0.1)}%`\n> RAM Usage: `{psutil.virtual_memory()[3]/1000000000:.2f} GB`\n> Memory:  `{mem_usage.used/(1024**3):.2f}/{mem_usage.total/(1024**3):.2f} GB ({100-mem_usage.percent}%)`", inline=True)
    embed.add_field(name="<:servers:1194042063369552013>  Bot Host", value=f"This bot is proudly hosted by **[MystiCraft](https://discord.gg/gADreNeYKT)** servers 24/7.", inline=False)
    
    if interaction.guild.id == 717029019270381578:
      await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list, True))
    else:
      await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list))

  @discord.ui.button(label='View Server Configuration', style=discord.ButtonStyle.blurple, custom_id='serverconfig')
  async def tutorial(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Server Configuration", description=f"You could view the server settings of the bot in this page instantly. The configuration for **{interaction.guild.name}** is as follows:", color=0x1DBCEB)
    ################
    ref = db.reference("/Tickets")
    tickets = ref.get()
    found = False
    for key, value in tickets.items():
      if (value["Server ID"] == interaction.guild.id):
        CATEGORY_ID = value["Category ID"]
        LOGCHANNEL_ID = value["Log Channel ID"]
        found = True
        break

    if not found:
      embed.add_field(name="Ticket System", value="<:no:1036810470860013639> Disabled", inline=True)
    else:
      embed.add_field(name="Ticket System", value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Category:** <#{CATEGORY_ID}>\n<:reply:1036792837821435976> **Log Channel:** <#{LOGCHANNEL_ID}>", inline=True)
    ################
    ref = db.reference("/Co-Op")
    coop = ref.get()
    found = False
    for key, value in coop.items():
      if (value["Server ID"] == interaction.guild.id):
        CO_OP_CHANNEL_ID = value["Co-op Channel ID"]
        NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
        EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
        ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
        SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
        found = True
        break

    if not found:
      embed.add_field(name="Co-op System", value="<:no:1036810470860013639> Disabled", inline=True)
    else:
      embed.add_field(name="Co-op System", value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Co-op Channel:** <#{CO_OP_CHANNEL_ID}>\n<:reply:1036792837821435976> **NA Helper Role:** <@&{NA_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **EU Helper Role:** <@&{EU_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **Asia Helper Role:** <@&{ASIA_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **SAR Helper Role:** <@&{SAR_HELPER_ROLE_ID}>", inline=True)
    ################
    ref = db.reference("/Birthday System")
    bs = ref.get()
    found = False
    for key, value in bs.items():
      if (value["Server ID"] == interaction.guild.id):
        CHANNEL_ID = value["Channel ID"]
        ROLE_ID = value["Role ID"]
        found = True
        break

    if not found:
      embed.add_field(name="Birthday Wishes", value="<:no:1036810470860013639> Disabled", inline=True)
    else:
      embed.add_field(name="Birthday Wishes", value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Channel:** <#{CHANNEL_ID}>\n<:reply:1036792837821435976> **Birthday Role:** <@&{ROLE_ID}>", inline=True)
	################
    ref = db.reference("/Sticky Messages")
    stickies = ref.get()

    found = False
    stickiedchannels = []
    for channel in interaction.guild.text_channels:
      for key, val in stickies.items():
        if val['Channel ID'] == channel.id:
          stickiedchannels.append(channel.id)
          found = True

    if not found:
      embed.add_field(name="Sticky Messages", value="<:no:1036810470860013639> Disabled", inline=True)
    else:
      x = "<:yes:1036811164891480194> Enabled\n"
      for chn in stickiedchannels:
        x = f"{x}<:reply:1036792837821435976> <#{chn}>\n"
      embed.add_field(name="Sticky Messages", value=x, inline=True)
	################
    ref = db.reference("/Welcome")
    welcome = ref.get()

    found = False

    for key, val in welcome.items():
      if val['Server ID'] == interaction.guild.id:
        welcomeChannel = val["Welcome Channel ID"]
        welcomeImageEnabled = val["Welcome Image Enabled"]
        found = True
        break

    if not found:
      embed.add_field(name="Welcome Messages", value="<:no:1036810470860013639> Disabled", inline=True)
    else:
      x = f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Welcome Channel:** <#{welcomeChannel}>\n"
      if welcomeImageEnabled:
        x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** `Uploaded`\n"
      else:
        x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** ` Not uploaded`\n"
      embed.add_field(name="Welcome Messages", value=x, inline=False)
    
    if interaction.guild.id == 717029019270381578:
      await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list, True))
    else:
      await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list))
    

class Help(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "help",
    description = "View all the bot's commands"
  )
  @app_commands.guild_only()
  async def help(
    self,
    interaction: discord.Interaction
  ) -> None:
    await interaction.response.defer(ephemeral=True)
    list = await self.bot.tree.fetch_commands()
    
    embed = discord.Embed(title="Fischl Help", description=f"""Fischl is a Genshin-based Discord bot with lots of functions for Genshin Impact servers, namely a convenient ticket system and a random Genshin conversation starter. The bot also comes with a lot of utility-based features such as co-op system, sticky messages, welcome functions, or even customized Genshin-font texts.
    """, color=0x1DBCEB)
    embed.add_field(name="<:gi_cafe:1103720959950725190> Support Server", value=f"Head over to our [support server](https://discord.gg/traveler) if you have any suggestions, questions or bug reports! :writing_hand:", inline=True)
    embed.add_field(name="<:slash:1037445915348324505> Command Usage", value=f"This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` to see the list of available bot commands.", inline=True)
    
    
    if interaction.guild.id == 717029019270381578:
      await interaction.followup.send(embed=embed, view=HelpPanel(list, True))
    else:
      await interaction.followup.send(embed=embed, view=HelpPanel(list))

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Help(bot))