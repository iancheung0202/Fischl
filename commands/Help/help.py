import discord, firebase_admin, sys, platform, psutil
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from firebase_admin import credentials, db
from replit import db as replit_db

class Select(discord.ui.Select):
    def __init__(self, list):
      self.list = list
      utility = ""
      ticket = ""
      topic = ""
      sticky = ""
      welcome = ""
      
      for command in self.list:
        if "ticket" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              ticket = f"{ticket}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
            else:
              ticket = f"{ticket}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "welcome" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              welcome = f"{welcome}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
            else:
              welcome = f"{welcome}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        # elif "topic" in command.name:
        #   for subcommand in command.options:
        #     if subcommand.type == discord.AppCommandOptionType.subcommand:
        #       topic = f"{topic}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
        #       for sub_command in subcommand.options:
        #         topic = f"{topic}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
        #     else:
        #       topic = f"{topic}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "sticky" in command.name:
          for subcommand in command.options:
            if subcommand.type == discord.AppCommandOptionType.subcommand:
              sticky = f"{sticky}\n\n</{command.name} {subcommand.name}:{command.id}>\n<:reply:1036792837821435976> {subcommand.description}"
              for sub_command in subcommand.options:
                sticky = f"{sticky}\n<:blank:1036792889121980426><:reply:1036792837821435976> `{sub_command.name}` - {sub_command.description}"
            else:
              sticky = f"{sticky}\n\n<:blank:1036792889121980426><:reply:1036792837821435976> `{subcommand.name}` - {subcommand.description}"
              
        elif "partnership" not in command.name and "team" not in command.name and "ask" not in command.name:
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
          [ticket, "Ticket System", "🎫", "The following commands are used to setup and deal with tickets. To start using tickets instantly, use </ticket setup:1036382520033415195> and the bot will guide you through the procedures of setting up your ticket mailbox! Note that these commands are only available to members with Administrator permission, meaning only Admins can close/delete tickets."],
          ["To use this chatbot function, you can simply ping <@732422232273584198> with your question!\n> e.g. `@Fischl give me statistics of diluc in genshin impact.`\n\n</ask:1049488388354478141>\n<:reply:1036792837821435976> Asks the bot anything from writing a story, an essay, to answering complicated questions\n<:blank:1036792889121980426><:reply:1036792837821435976> `query` - The query to be passed to the bot", "Q&A with Fischl", "🙋", "This is live chatbot feature that you could easily integrate in your server, powered by Google Bard. It is a powerful tool that can answer members' questions based on its own (Google's) knowledge. The answers provided by the bot are just for reference purposes and may not fully accurate. \n\n"],
          # [topic, "Topic Commands", "🗣️", "The following commands are used to keep your server chat engaged and active by issuing random Genshin Impact topics to chat on! You could also contribute to our bot's topic database!"],
          [sticky, "Sticky Messages", "🫧", "The following slash commands are for setting up sticky messages in different channels. Sticky messages will be stayed at the bottom of the channel no matter what messages are sent afterwards. This function is especially useful when you need give your members a heads up on how to use this chat channel or what they need to know before going ahead and sending any messages. To setup sticky messages, you may need Administrator permissions."],
          [welcome, "Welcome Messages", "👋", "The following slash commands are for setting up welcome messages in a server. If enabled, the bot will automatically greet new server members in a designated text channel. You can customize your own greetings to tailor to your server's needs. To setup welcome messages, you may need Administrator permissions."]
        ]
        options = []
        for item in self.lyst:
          options.append(discord.SelectOption(label=item[1], emoji=item[2]))
          
        super().__init__(placeholder="Browse Commands",max_values=1,min_values=1,options=options, custom_id="browsecommands")
    async def callback(self, interaction: discord.Interaction):
      for item in self.lyst:
        if self.values[0] == item[1]:
          intro = discord.Embed(title=f"{item[2]} {item[1]}", description=item[3], color=0xFFFF00)
          embed = discord.Embed(description=item[0], color=discord.Color.blurple())
          await interaction.response.edit_message(embeds=[intro, embed], view=HelpPanel(self.list))
          break

class HelpPanel(discord.ui.View):
  def __init__(self, list=None):
    self.list = list
    super().__init__(timeout=None)
    inviteButton = Button(label="Add to Server", style=discord.ButtonStyle.link, url="https://discord.com/api/oauth2/authorize?client_id=732422232273584198&permissions=8&scope=bot%20applications.commands")
    self.add_item(inviteButton)
    websiteButton = Button(label="Visit Website", style=discord.ButtonStyle.link, url="https://fischlbot.web.app/")
    self.add_item(websiteButton)
    self.add_item(Select(self.list))

  @discord.ui.button(label='Overview', style=discord.ButtonStyle.blurple, custom_id='overview')
  async def overview(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Fischl Help", description=f"""Fischl is a Genshin-based Discord bot with lots of functions for Genshin Impact servers, namely a convenient ticket system and a random Genshin conversation starter. The bot also comes with a lot of utility-based features such as implementing sticky messages, generating welcome cards, or even creating customized Genshin-font texts.
    """, color=0x1DBCEB)
    embed.add_field(name="<:gi_cafe:1103720959950725190> Support Server", value=f"Head over to our [support server](https://discord.gg/traveler) if you have any suggestions, questions or bug reports! :writing_hand:", inline=True)
    embed.add_field(name="<:slash:1037445915348324505> Command Usage", value=f"This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` to see the list of available bot commands.", inline=True)
    await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list))

  @discord.ui.button(label='Statistics', style=discord.ButtonStyle.blurple, custom_id='statistics')
  async def statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Fischl Discord Bot Statistics", color=0x1DBCEB)
    mem_usage = psutil.virtual_memory()
    embed.add_field(name="<:info:1037445870469267638> Package Info", value=f"```OS - {platform.system()}\nPython - {platform.python_version()}\ndiscord.py - {discord.__version__}\nGoogle Firebase - {firebase_admin.__version__}\nGoogle Bard - 1.3.0```", inline=False)
    embed.add_field(name="<:dev:1037445830749204624> Bot Metadata", value=f"""> Application ID: `{interaction.client.application_id}`
> Last Reboot: <t:{replit_db['ready_time']}:R>
> Servers Count: `{len(interaction.client.guilds)}`
> API/Bot Latency: `{int(round(interaction.client.latency * 1000, 1))}ms`""", inline=True)
    embed.add_field(name="📊 Bot Process Data", value=f"> CPU Usage: `{psutil.cpu_percent(0.1)}%`\n> RAM Usage: `{psutil.virtual_memory()[3]/1000000000:.2f} GB`\n> Memory:  `{mem_usage.used/(1024**3):.2f}/{mem_usage.total/(1024**3):.2f} GB ({100-mem_usage.percent}%)`", inline=True)
    await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list))

  @discord.ui.button(label='View Server Configuration', style=discord.ButtonStyle.blurple, custom_id='serverconfig')
  async def tutorial(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Server Configuration", description=f"You could view the server settings of the bot in this page instantly. The configuration for **{interaction.guild.name}** is as follows:", color=0x1DBCEB)
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
      embed.add_field(name="Welcome Messages", value="<:no:1036810470860013639> Disabled", inline=False)
    else:
      x = f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Welcome Channel:** <#{welcomeChannel}>\n"
      if welcomeImageEnabled:
        x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** `Uploaded`\n"
      else:
        x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** ` Not uploaded`\n"
      embed.add_field(name="Welcome Messages", value=x, inline=False)
    
        
    await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list))
    

class Help(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "help",
    description = "View all the bot's commands"
  )
  async def help(
    self,
    interaction: discord.Interaction
  ) -> None:
    await interaction.response.defer(ephemeral=True)
    list = await self.bot.tree.fetch_commands()
    
    embed = discord.Embed(title="Fischl Help", description=f"""Fischl is a Genshin-based Discord bot with lots of functions for Genshin Impact servers, namely a convenient ticket system and a random Genshin conversation starter. The bot also comes with a lot of utility-based features such as implementing sticky messages, generating welcome cards, or even creating customized Genshin-font texts.
    """, color=0x1DBCEB)
    embed.add_field(name="<:gi_cafe:1103720959950725190> Support Server", value=f"Head over to our [support server](https://discord.gg/traveler) if you have any suggestions, questions or bug reports! :writing_hand:", inline=True)
    embed.add_field(name="<:slash:1037445915348324505> Command Usage", value=f"This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` to see the list of available bot commands.", inline=True)

    await interaction.followup.send(embed=embed, view=HelpPanel(list))

# class OnCommand(commands.Cog): 
#   def __init__(self, bot):
#     self.client = bot
  
#   @commands.Cog.listener() 
#   async def on_app_command_completion(self, interaction, command):
#     chn = self.client.get_channel(1030892842308091987)
#     embed = discord.Embed(description=f"""Slash command: """)
#     await chn.send(interaction.user.mention)
#     await chn.send(command.name)

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Help(bot))
  # await bot.add_cog(OnCommand(bot))