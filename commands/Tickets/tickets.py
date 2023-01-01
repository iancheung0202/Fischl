import discord, firebase_admin, datetime, asyncio, time, emoji
from ai import request
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class Select(discord.ui.Select):
    def __init__(self, placeholder, options):
        # options=options
        super().__init__(placeholder=placeholder,max_values=1,min_values=1,options=options, custom_id="ticketcreation")
    async def callback(self, interaction: discord.Interaction):
        
      selectedValue = self.values[0]
      embed = discord.Embed(title="Confirm Ticket",description=f"Are you sure you want to make a ticket about **{selectedValue}**?",colour=0x4F545B)
      embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
      embed.set_footer(icon_url=interaction.guild.icon.url, text=f"{interaction.guild.name} • #{interaction.channel.name}")
      await interaction.response.send_message(embed=embed, view=CreateTicketButtonView(), ephemeral=True)

class SelectView(discord.ui.View):
    def __init__(self, placeholder=None, options=None, *, timeout = None):
        super().__init__(timeout=timeout)
        self.add_item(Select(placeholder, options))


class CreateTicketButton(discord.ui.Button):
    def __init__(self, title, emoji, color):
        super().__init__(label=title, emoji=emoji, 
 style=color, custom_id="create")
    async def callback(self, interaction: discord.Interaction):
      await interaction.response.defer(ephemeral=True, thinking=True)
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
        embed = discord.Embed(title="Ticket not enabled!", description=f'This server doesn\'t have a ticket category or a log channel. Please ask the server admin to use </ticket setup:1033188985587109910> to setup tickets!', colour=0xFF0000)
        embed.timestamp = datetime.datetime.utcnow()
        await interaction.followup.send(embed=embed, ephemeral=True)
        raise Exception("Category/log channel not found")
      
      category = interaction.guild.get_channel(CATEGORY_ID)
          
      for channel in category.channels:
        if str(channel.topic) == str(interaction.user.id):
          await interaction.followup.send(content=f"You already had your ticket created at <#{channel.id}>.", ephemeral=True)
          raise Exception()
  
      chn = await interaction.guild.create_text_channel(f"{interaction.user.name}#{interaction.user.discriminator}", category=category)
      await chn.edit(topic=interaction.user.id)
      await chn.set_permissions(interaction.user, send_messages=True, read_messages=True, attach_files=True)
      log = interaction.guild.get_channel(LOGCHANNEL_ID)
      embed = discord.Embed(title="Ticket created", description=f"**{interaction.user.mention} created a new ticket <t:{int(float(time.mktime(chn.created_at.timetuple())))}:R>!**", color=discord.Colour.green())
      embed.set_author(name=f"{interaction.user.name}#{interaction.user.discriminator}", icon_url=interaction.user.avatar.url)
      embed.timestamp = datetime.datetime.utcnow()
      embed.set_footer(text=f"User ID: {interaction.user.id}")
      
      button = Button(style=discord.ButtonStyle.link, label="View Ticket",  url=f"https://discord.com/channels/{interaction.guild.id}/{chn.id}")
      view = View()
      view.add_item(button)
      await log.send(embed=embed, view=view)
  
      roles = interaction.user.roles
      roles.reverse()
      
      try:
        embed = interaction.message.embeds[0]
        x = f"({embed.description.split('**')[1]})"
      except Exception:
        x = " "
  
      embed = discord.Embed(title=f"New Ticket {x}", description=f"Type your message here in this channel!\nYou can use </ticket close:1033188985587109910> or click the red button below in order to close this ticket.", color=discord.Colour.gold())
      embed.timestamp = datetime.datetime.utcnow()
      embed.add_field(name="User Mention", value=f"{interaction.user.mention}", inline=True)
      embed.add_field(name="User ID", value=f"{interaction.user.id}", inline=True)
      embed.add_field(name="Highest Role", value=f"{roles[0].mention}", inline=True)
      embed.add_field(name="Ticket Created", value=f"<t:{int(float(time.mktime(chn.created_at.timetuple())))}:R>", inline=True)
      embed.add_field(name="Server Joined", value=f"<t:{int(float(time.mktime(interaction.user.joined_at.timetuple())))}:R>", inline=True)
      embed.add_field(name="Account Created", value=f"<t:{int(float(time.mktime(interaction.user.created_at.timetuple())))}:R>", inline=True)
      await chn.send(f"**{interaction.user.mention}, welcome!**", embed=embed, view=CloseTicketButton())
      await interaction.followup.send(content=f"Ticket created at <#{chn.id}>", ephemeral=True)

      def check(message):
        if message.content.lower() == "cancel":
          raise Exception()
        return message.channel == chn and message.content != ""

      if "question" in x.lower():
        embed = discord.Embed(title="What do you need help for?", description=f"You are now talking with an automatic AI chatbot. Describe your question in a detained manner. Include punctuation when you finish your sentence to minimize misunderstanding.\n\n_The answers provided by the bot are just for reference purposes and may not fully accurate._", color=0xADD8E6)
        embed.set_footer(text="If you believe that the bot cannot help you with what you want, type \"quit\" to terminate automatic response and get help from our staff member instead.")
        await chn.send(embed=embed)
  
        while True:
          answer = await interaction.client.wait_for('message', check=check)
          if answer.content.lower() == "quit":
            await answer.delete()
            await asyncio.sleep(1)
            await chn.send(":x: Stopped automatic response")
            break
          else:
            await chn.send(request(answer.content, interaction.guild.id))
      
      elif "role application" in x.lower() and interaction.guild.id == 717029019270381578:
        
        embed = discord.Embed(title="What role are you applying for?", description=f"<@&943486837559791618> \n> - Must have 100+ followers/subscribers on Twitch/YouTube\n> Send channel link for verification\n\n<@&815132429189644318> \n> - Demonstrate excellent talent in drawing or painting, digital or not\n> - Send 5 pieces of your work to showcase your artistic talent\n\n<@&1049100647884132443>\n> - Please close this ticket and head over to <#1049118482987499540> instead. ", color=0xADD8E6)
        await chn.send(embed=embed)
      
      elif "rule" in x.lower() and interaction.guild.id == 717029019270381578:
        
        embed = discord.Embed(title="Oh no, someone has been caught in 4K!", description=f"Please send screenshots of rule-breaking actions, link potential channels or users to speed up our investigation!", color=0xADD8E6)
        await chn.send(embed=embed)
      
      elif "perk" in x.lower() and interaction.guild.id == 717029019270381578:
        
        embed = discord.Embed(title="", description=f"Please send screenshots of rule-breaking actions, link potential channels or users to speed up our investigation!", color=0xADD8E6)
        await chn.send(embed=embed)


class CreateTicketButtonView(discord.ui.View):
    def __init__(self, title="Create Ticket", emoji="🎫", color=discord.ButtonStyle.green, *, timeout = None):
        super().__init__(timeout=timeout)
        self.add_item(CreateTicketButton(title, emoji, color))


class CloseTicketButton(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.red, custom_id='close', emoji="🔒")
  async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
    if ":no_entry_sign:" in interaction.channel.topic:
      embed = discord.Embed(title="Ticket already closed :no_entry_sign:", description="This ticket is already closed.", color=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)
      raise Exception("Ticket already closed")
    embed = discord.Embed(title="Are you sure about that?", description="Only moderators and administrators can reopen the ticket.", color=0xFF0000)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.response.send_message(embed=embed, view=ConfirmCloseTicketButtons())
    # await interaction.response.(ephemeral=True)

class TicketAdminButtons(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Reopen Ticket', style=discord.ButtonStyle.grey, custom_id='reopen', emoji="🔓")
  async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
    user = interaction.guild.get_member(int(interaction.channel.topic.split(":")[2].strip()))
    await interaction.channel.edit(topic=user.id)
    await interaction.channel.set_permissions(user, send_messages=True, read_messages=True, attach_files=True)
    
    ref = db.reference("/Tickets")
    tickets = ref.get()
    for key, value in tickets.items():
      if (value["Server ID"] == interaction.guild.id):
        LOGCHANNEL_ID = value["Log Channel ID"]
        break
    log = interaction.guild.get_channel(LOGCHANNEL_ID)
    
    embed = discord.Embed(title="Ticket reopened", description=f"Ticket created by {user.mention} is reopened by {interaction.user.mention}", color=0xFFFF00)
    embed.set_author(name=f"{user.name}#{user.discriminator}", icon_url=user.avatar.url)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text=f"User ID: {user.id}")
    button = Button(style=discord.ButtonStyle.link, label="View Ticket",  url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}")
    view = View()
    view.add_item(button)
    await log.send(embed=embed, view=view)
    embed = discord.Embed(title="Ticket reopened", description=f"Your ticket is reopened.", color=0xE44D41)
    embed.timestamp = datetime.datetime.utcnow()
    button = Button(style=discord.ButtonStyle.link, label="Head over to your ticket", emoji="🎫", url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}")
    view = View()
    view.add_item(button)
    try:
      await user.send(embed=embed, view=view)
    except Exception:
      pass
    embed = discord.Embed(title="🔓 Ticket Reopened", description="Ticket is again visible to the member.", color=0xFFFF00)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.message.delete()
    await interaction.channel.send(embed=embed, view=CloseTicketButton())
    await interaction.response.send_message("Ticket is reopened.", ephemeral=True)

  @discord.ui.button(label='Delete Ticket', style=discord.ButtonStyle.grey, custom_id='delete', emoji="✉️")
  async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Deleting Ticket...", description="Ticket will be deleted in 5 seconds", color=0xFF0000)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.message.delete()
    await interaction.channel.send(embed=embed)
    await asyncio.sleep(5)
    await interaction.channel.delete()


class ConfirmCloseTicketButtons(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Yes', style=discord.ButtonStyle.green, custom_id='yes')
  async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Closing Ticket...", description="Ticket will be closed in 5 seconds", color=0xFF0000)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.message.delete()
    msg = await interaction.channel.send(embed=embed)
    await asyncio.sleep(5)
    user = interaction.guild.get_member(int(interaction.channel.topic))
    
    ref = db.reference("/Tickets")
    tickets = ref.get()
    for key, value in tickets.items():
      if (value["Server ID"] == interaction.guild.id):
        LOGCHANNEL_ID = value["Log Channel ID"]
        break
    log = interaction.guild.get_channel(LOGCHANNEL_ID)
    
    embed = discord.Embed(title="Ticket closed", description=f"Ticket created by {user.mention} is closed by {interaction.user.mention}", color=0xE44D41)
    embed.set_author(name=f"{user.name}#{user.discriminator}", icon_url=user.avatar.url)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text=f"User ID: {user.id}")
    await log.send(embed=embed)
    embed = discord.Embed(title="Ticket closed", description=f"Your ticket in **{interaction.guild.name}** is now closed.", color=0xE44D41)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text=f"You can always create a new ticket for additional assistance!")
    try:
      await user.send(embed=embed)
    except Exception:
      pass
    await interaction.channel.set_permissions(user, send_messages=False, read_messages=False, attach_files=False)
    await msg.delete()
    embed = discord.Embed(title="", description="Ticket is closed and no longer visible to the member.", color=0xE44D41)
    await interaction.channel.send(embed=embed)
    embed = discord.Embed(title="", description="```ADMIN CONTROLS PANEL```", color=0xE44D41)
    await interaction.channel.send(embed=embed, view=TicketAdminButtons())
    await interaction.channel.edit(topic=f":no_entry_sign: {interaction.user.id}")

  @discord.ui.button(label='No', style=discord.ButtonStyle.red, custom_id='no')
  async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
    embed = discord.Embed(title="Action Cancelled", description=f"Alright {interaction.user.mention}! I will not close the ticket!", color=0xFF0000)
    embed.timestamp = datetime.datetime.utcnow()
    notice = await interaction.channel.send(embed=embed)
    await interaction.message.delete()
    await asyncio.sleep(7)
    await notice.delete()


class Ticket(commands.GroupCog, name="ticket"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "reset",
    description = "Reset the settings of ticket in the server"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_reset(
    self,
    interaction: discord.Interaction
  ) -> None:
    tickets = db.reference('/Tickets').get()
    found = False
    for key, val in tickets.items():
        if val['Server ID'] == interaction.guild.id:
          db.reference('/Tickets').child(key).delete()
          found = True
          break
    if found:
      embed = discord.Embed(title="Ticket successfully reset", description=f'You can use </ticket setup:1033188985587109910> at anytime to setup the ticket function again.', colour=0xFFFF00)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed)
    else:
      embed = discord.Embed(title="We could not find your server", description=f'Maybe you have already reset the ticket function in your server, or you have never enabled ticket function. Anyways, no records found in our system.', colour=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)

    
  @app_commands.command(
    name = "setup",
    description = "Setup ticket function in the server"
  )
  @app_commands.describe(
    category = "The category to hold all the tickets (If you do not specify, we will create one for you)",
    log_channel = "The channel to log all future tickets (If you do not specify, we will create one for you)"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_setup(
    self,
    interaction: discord.Interaction,
    category: discord.CategoryChannel = None,
    log_channel: discord.TextChannel = None
  ) -> None:
    ref = db.reference("/Tickets")
    tickets = ref.get()
    for key, value in tickets.items():
      if (value["Server ID"] == interaction.guild.id):
        embed = discord.Embed(title="Ticket already enabled!", description=f'The category is already set as <#{value["Category ID"]}> `({value["Category ID"]})` and the ticket log channel is already set as <#{value["Log Channel ID"]}> `({value["Log Channel ID"]})`\n\nPlease use </ticket button:1033188985587109910> or </ticket dropdown:1033188985587109910> to create your own customized ticket panel.\n\nIf you wish to reset the settings of tickets, please use </ticket reset:1033188985587109910>.', colour=0xFF0000)
        embed.timestamp = datetime.datetime.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)
        raise Exception("Already existed!")

    if not category:
      category = await interaction.guild.create_category("Tickets")
    if not log_channel:
      log_channel = await interaction.guild.create_text_channel(f"ticket-log", category=category)

    embed = discord.Embed(title="What is this?", description=f'This channel logs all ticket deletion and creation events! It clearly provides server admins a list of past tickets. ', colour=discord.Color.blurple())
    embed.timestamp = datetime.datetime.utcnow()
    await log_channel.send(embed=embed)
    
    await category.set_permissions(interaction.guild.default_role, read_messages=False)
    await log_channel.set_permissions(interaction.guild.default_role, read_messages=False)

    data = {
    		interaction.guild.name: {
          "Server Name": interaction.guild.name,
          "Server ID": interaction.guild.id,
          "Category ID": category.id,
          "Log Channel ID": log_channel.id
        }
    	}

    for key, value in data.items():
    	ref.push().set(value)
    
    embed = discord.Embed(title="Ticket successfully enabled!", description=f'The category is set as <#{category.id}> `({category.id})` and the ticket log channel is set as <#{log_channel.id}> `({log_channel.id})`. \n\n**All administrators can by default view the tickets. If you wish to let staff without administrator permission to do so as well, please use </ticket addrole:1033188985587109910> and add roles of your own choice. Use </ticket removerole:1033188985587109910> for vice versa.**\n\nPlease use </ticket button:1033188985587109910> or </ticket dropdown:1033188985587109910> to create your own customized ticket panel.', colour=0x00FF00)
    embed.timestamp = datetime.datetime.utcnow()
  
    await interaction.response.send_message(embed=embed)

  @app_commands.command(
    name = "addrole",
    description = "Add a role that can see and manage tickets"
  )
  @app_commands.describe(
    role = "The role at your own choice that can see and manage tickets"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_addrole(
    self,
    interaction: discord.Interaction,
    role: discord.Role
  ) -> None:
    ref = db.reference("/Tickets")
    tickets = ref.get()
    found = False
    for key, value in tickets.items():
      if (value["Server ID"] == interaction.guild.id):
        CATEGORY_ID = value["Category ID"]
        LOGCHANNEL_ID = value["Log Channel ID"]
        found = True
        break

    if found:
      category = interaction.guild.get_channel(CATEGORY_ID)
      log_channel = interaction.guild.get_channel(LOGCHANNEL_ID)
      await category.set_permissions(role, read_messages=True, send_messages=True, attach_files=True, manage_channels=True, manage_messages=True, read_message_history=True)
      await log_channel.set_permissions(role, read_messages=True, send_messages=True, attach_files=True, manage_channels=True, manage_messages=True, read_message_history=True)
      for channel in category.channels:
        await channel.set_permissions(role, read_messages=True, send_messages=True, attach_files=True, manage_channels=True, manage_messages=True, read_message_history=True)
      embed = discord.Embed(title="Role Added!", description=f'{role.mention} now has the following permissions in all ticket-related channels:\n\n`- Read Messages`\n`- Send Messages`\n`- Attach Files`\n`- Manage Channels`\n`- Manage Messages`\n`- Read Message History`', colour=0x00FF00)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed)
    else:
      embed = discord.Embed(title="Ticket not enabled!", description=f'This server doesn\'t have a ticket category or a log channel. Please ask the server admin to use </ticket setup:1033188985587109910> to setup tickets!', colour=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)

  
  @app_commands.command(
    name = "removerole",
    description = "Remove a role that can see and manage tickets"
  )
  @app_commands.checks.has_permissions(administrator=True)
  @app_commands.describe(
    role = "The role at your own choice that can no longer see and manage tickets"
  )
  async def ticket_removerole(
    self,
    interaction: discord.Interaction,
    role: discord.Role
  ) -> None:
    ref = db.reference("/Tickets")
    tickets = ref.get()
    found = False
    for key, value in tickets.items():
      if (value["Server ID"] == interaction.guild.id):
        CATEGORY_ID = value["Category ID"]
        LOGCHANNEL_ID = value["Log Channel ID"]
        found = True
        break

    if found:
      category = interaction.guild.get_channel(CATEGORY_ID)
      log_channel = interaction.guild.get_channel(LOGCHANNEL_ID)
      await category.set_permissions(role, read_messages=None, send_messages=None, attach_files=None, manage_channels=None, manage_messages=None, read_message_history=None)
      await log_channel.set_permissions(role, read_messages=None, send_messages=None, attach_files=None, manage_channels=None, manage_messages=None, read_message_history=None)
      for channel in category.channels:
        await channel.set_permissions(role, read_messages=None, send_messages=None, attach_files=None, manage_channels=None, manage_messages=None, read_message_history=None)
      embed = discord.Embed(title="Role Added!", description=f'{role.mention} now has the following permissions in all ticket-related channels:\n\n`- Read Messages`\n`- Send Messages`\n`- Attach Files`\n`- Manage Channels`\n`- Manage Messages`\n`- Read Message History`', colour=0x00FF00)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed)
    else:
      embed = discord.Embed(title="Ticket not enabled!", description=f'This server doesn\'t have a ticket category or a log channel. Please ask the server admin to use </ticket setup:1033188985587109910> to setup tickets!', colour=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)

  @app_commands.command(
    name = "notify",
    description = "Send a DM to the ticket author notifying the ticket needs their attention"
  )
  @app_commands.describe(
    message = "Optional message you could include in the DMs"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_notify(
    self,
    interaction: discord.Interaction,
    message: str = None
  ) -> None:
    if message is None:
      message = " "
    else:
      message = f"\n\n> {message}"
    try:
      user = interaction.guild.get_member(int(interaction.channel.topic))
    except Exception:
      pass
    embed = discord.Embed(title="⚠️ Notification ⚠️", description=f"The ticket you previously opened in **{interaction.guild.name}** needs your attention! Please kindly respond.{message}\n\nIf you no longer need assistance or your issue has been resolved, **please still let us know in the ticket** so we can help close the ticket.", color=0xE44D41)
    embed.timestamp = datetime.datetime.utcnow()
    
    try:
      button = Button(style=discord.ButtonStyle.link, label="Head over to your ticket", emoji="🎫", url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}")
      view = View()
      view.add_item(button)
      await user.send(embed=embed, view=view)
      await interaction.response.send_message(f"{user.mention} received a DM notification.")
    except Exception:
      await interaction.response.send_message("Unable to DM user!", ephemeral=True)

  @app_commands.command(
    name = "delete",
    description = "Deletes an existing ticket channel"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_delete(
    self,
    interaction: discord.Interaction
  ) -> None:
    try:
      user = interaction.guild.get_member(int(interaction.channel.topic.split(":")[2]))
      embed = discord.Embed(title="Deleting Ticket...", description="Ticket will be deleted in 5 seconds", color=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed)
      await asyncio.sleep(5)
      await interaction.channel.delete()
    except Exception:
      embed = discord.Embed(title="Invalid Action", description="This command can only be used in ticket channels, or this ticket has not been closed.", color=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)

  
  @app_commands.command(
    name = "close",
    description = "Closes the current ticket and prevents ticket author from viewing the ticket"
  )
  async def ticket_close(
    self,
    interaction: discord.Interaction
  ) -> None:
    if ":no_entry_sign:" in interaction.channel.topic:
      embed = discord.Embed(title="Ticket already closed :no_entry_sign:", description="This ticket is already closed.", color=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)
      raise Exception("Ticket already closed")
    try:
      user = interaction.guild.get_member(int(interaction.channel.topic))
      embed = discord.Embed(title="Are you sure about that?", description="Only moderators and administrators can reopen the ticket.", color=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, view=ConfirmCloseTicketButtons())
    except Exception:
      embed = discord.Embed(title="Invalid Action", description="This command can only be used in ticket channels.", color=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)

  @app_commands.command(
    name = "button",
    description = "Creates a ticket panel with buttons"
  )
  @app_commands.describe(
    title = "Makes the title of the embed",
    description = "Makes the description of the embed",
    color = "Sets the color of the embed",
    thumbnail = "Please provide a URL for the thumbnail of the embed (upper-right hand corner image)",
    image = "Please provide a URL for the image of the embed (appears at the bottom of the embed)",
    footer = "Sets the footer of the embed that appears at the bottom of the embed as small texts",
    footer_time = "Shows the time of the embed being sent?",
    button_emoji = "Sets the emoji of the button (Supports custom emoji)",
    button_text = "Sets the text of the button",
    button_color = "Chooses a color for the button"
  )
  @app_commands.choices(button_color = [
    discord.app_commands.Choice(name="Grey", value="Grey"),
    discord.app_commands.Choice(name="Green", value="Green"),
    discord.app_commands.Choice(name="Blurple", value="Blurple"),
    discord.app_commands.Choice(name="Red", value="Red"),
  ])
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_button(
    self,
    interaction: discord.Interaction,
    title: str = None,
    description: str = None,
    color: str = None,
    thumbnail: str = None,
    image: str = None,
    footer: str = None,
    footer_time: bool = None,
    button_emoji: str = "🎫",
    button_text: str = "Create Ticket",
    button_color: str = None
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
      embed.timestamp = datetime.datetime.utcnow()
    if button_emoji != "🎫":
      button_emoji = emoji.emojize(button_emoji.strip())
    if button_color == "Grey":
      color = discord.ButtonStyle.grey
    elif button_color == "Blurple":
      color = discord.ButtonStyle.blurple
    elif button_color == "Red":
      color = discord.ButtonStyle.red
    else:
      color = discord.ButtonStyle.green

    await interaction.channel.send(embed=embed, view=CreateTicketButtonView(button_text, button_emoji, color))
    embed = discord.Embed(title="✅ Custom Ticket Panel Sent", description="All members who have access to this channel can create a ticket by clicking the button below the panel!", color=0x00FF00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @app_commands.command(
    name = "dropdown",
    description = "Creates a ticket panel with dropdown menu"
  )
  @app_commands.describe(
    title = "Makes the title of the embed",
    description = "Makes the description of the embed",
    color = "Sets the color of the embed",
    thumbnail = "Please provide a URL for the thumbnail of the embed (upper-right hand corner image)",
    image = "Please provide a URL for the image of the embed (appears at the bottom of the embed)",
    footer = "Sets the footer of the embed that appears at the bottom of the embed as small texts",
    footer_time = "Shows the time of the embed being sent?",
    dropdown_placeholder = "Sets the placeholder of the dropdown menu",
    dropdown1_emoji = "Sets the emoji of the first option",
    dropdown1_title = "Sets the title of the first option",
    dropdown1_description = "Sets the description of the first option",
    dropdown2_emoji = "Sets the emoji of the second option",
    dropdown2_title = "Sets the title of the second option",
    dropdown2_description = "Sets the description of the second option",
    dropdown3_emoji = "Sets the emoji of the third option",
    dropdown3_title = "Sets the title of the third option",
    dropdown3_description = "Sets the description of the third option",
    dropdown4_emoji = "Sets the emoji of the fourth option",
    dropdown4_title = "Sets the title of the fourth option",
    dropdown4_description = "Sets the description of the fourth option",
    dropdown5_emoji = "Sets the emoji of the fifth option",
    dropdown5_title = "Sets the title of the fifth option",
    dropdown5_description = "Sets the description of the fifth option",
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def ticket_dropdown(
    self,
    interaction: discord.Interaction,
    title: str = None,
    description: str = None,
    color: str = None,
    thumbnail: str = None,
    image: str = None,
    footer: str = None,
    footer_time: bool = None,
    dropdown_placeholder: str = "Select a Category",
    dropdown1_emoji: str = None,
    dropdown1_title: str = None,
    dropdown1_description: str = None,
    dropdown2_emoji: str = None,
    dropdown2_title: str = None,
    dropdown2_description: str = None,
    dropdown3_emoji: str = None,
    dropdown3_title: str = None,
    dropdown3_description: str = None,
    dropdown4_emoji: str = None,
    dropdown4_title: str = None,
    dropdown4_description: str = None,
    dropdown5_emoji: str = None,
    dropdown5_title: str = None,
    dropdown5_description: str = None,
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
      embed.timestamp = datetime.datetime.utcnow()

    options = []

    list = [
      [dropdown1_emoji, dropdown1_title, dropdown1_description],
      [dropdown2_emoji, dropdown2_title, dropdown2_description],
      [dropdown3_emoji, dropdown3_title, dropdown3_description],
      [dropdown4_emoji, dropdown4_title, dropdown4_description],
      [dropdown5_emoji, dropdown5_title, dropdown5_description],
    ]

    for item in list:
      if item[1] is None and (item[0] is not None or item[2] is not None): # Title missing
        embed = discord.Embed(title="Dropdown Menu Option's Title Missing", description="You must include a title for every option!", color=0xFF0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        raise Exception()
      if item[0] is not None and item[1] is not None and item[2] is not None: # Emoji + Title + Description
        emote = emoji.emojize(item[0].strip())
        title = item[1].strip()
        description = item[2].strip()
        options.append(discord.SelectOption(label=title, value=title, description=description, emoji=emote),)
      elif item[0] is None and item[1] is not None and item[2] is not None: # Title + Description
        title = item[1].strip()
        description = item[2].strip()
        options.append(discord.SelectOption(label=title, value=title, description=description),)
      elif item[0] is not None and item[1] is not None and item[2] is None: # Emoji + Title 
        emote = emoji.emojize(item[0].strip())
        title = item[1].strip()
        options.append(discord.SelectOption(label=title, value=title, emoji=emote),)
      elif item[0] is None and item[1] is not None and item[2] is None: # Title Only
        title = item[1].strip()
        options.append(discord.SelectOption(label=title, value=title),)

    await interaction.channel.send(embed=embed, view=SelectView(dropdown_placeholder, options))
    embed = discord.Embed(title="✅ Custom Ticket Panel Sent", description="All members who have access to this channel can create a ticket by selecting the dropdown menu below the panel!", color=0x00FF00)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Ticket(bot))