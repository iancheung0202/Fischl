import discord, firebase_admin, datetime, asyncio, time, aiohttp
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

# async def postServers(interaction):
#   mutual_servers = interaction.user.mutual_guilds
#   # x = ""
#   view = View()
#   for server in mutual_servers:
#     user = server.get_member(interaction.user.id) 
#     if server.id != 717029019270381578:
#       # invite = await server.text_channels[0].create_invite(max_age=0, max_uses=0)
#       # name = server.name
#       # x = f"{x}• [{name}]({invite}
#       partners = db.reference('/Partners').get()
#       found = False
#       for key, val in partners.items():
#           if val['Server ID'] == server.id:
#             found = True
#             break
      
#       if found:
#         view.add_item(ServerButton(serverName=server.name, serverID=server.id, style=discord.ButtonStyle.red, disabled=True))
#       elif server.member_count < 100 or user.guild_permissions.administrator == False: #
#         view.add_item(ServerButton(serverName=server.name, serverID=server.id, style=discord.ButtonStyle.grey, disabled=True))
  
#       elif user == server.owner:
#         view.add_item(ServerButton(serverName=server.name, serverID=server.id, style=discord.ButtonStyle.green, disabled=False))
#       elif user.guild_permissions.administrator:
#         view.add_item(ServerButton(serverName=server.name, serverID=server.id, style=discord.ButtonStyle.grey, disabled=False))
#   view.add_item(RefreshButton())
#   embed = discord.Embed(title="(Partnership) Select a server to get started!", description=f":warning: If the button for your server is **disabled**, it means that you are **missing `Administrator` permissions** in that server **_or_** it has **less than 100 members**. Only servers with 100+ members can partner and you must be an `Administrator` of that server to partner that server with us!\n\n:green_circle: A **green button** means that **you own that server**! You would definitely want to partner it with us, though note that all servers with their buttons enabled can be partnered!\n\n:red_circle: A **red button** means that **we have already partnered with that server**. Please [contact the bot developer via DMs](https://discord.com/users/692254240290242601) if you think it is a mistake.\n\n:grey_question: If you don't see your server, **[invite me to that server](https://discord.com/api/oauth2/authorize?client_id=732422232273584198&permissions=8&scope=bot%20applications.commands) and click the `Refresh` button below.**\n\n:telephone: The bot can only display 24 servers at once. If you still cannot see your server, please [contact the bot developer via DMs](https://discord.com/users/692254240290242601).", color=discord.Color.blurple())
#   return embed, view
  
# class PartnershipButton(discord.ui.Button):
#     def __init__(self):
#         super().__init__(label='Become a Partner', style=discord.ButtonStyle.blurple, custom_id='partner', emoji="🤝")
#     async def callback(self, interaction: discord.Interaction):
#       await interaction.response.defer(ephemeral=True, thinking=True)
#       content = await postServers(interaction)
#       try:
#         msg = await interaction.user.send(embed=content[0], view=content[1])
#         button = Button(style=discord.ButtonStyle.link, label="Jump to DM", url=msg.jump_url)
#         view2 = View()
#         view2.add_item(button)
#         embed = discord.Embed(description=":envelope_with_arrow: Head over to your DMs to finish the partnership process!", color=discord.Color.blurple())
#         await interaction.followup.send(embed=embed, view=view2)
#       except Exception:
#         await interaction.followup.send(embed=content[0], view=content[1])

# class PartnerView(discord.ui.View):
#     def __init__(self, timeout = None):
#         super().__init__(timeout=timeout)
#         self.add_item(PartnershipButton())

# class RefreshButton(discord.ui.Button):
#     def __init__(self):
#         super().__init__(label="Refresh", 
#  style=discord.ButtonStyle.blurple, custom_id="refresh", emoji="<:refresh:1048779043287351408>")
#     async def callback(self, interaction: discord.Interaction):
#       content = await postServers(interaction)
#       await interaction.response.edit_message(embed=content[0], view=content[1])

# class ServerButton(discord.ui.Button):
#     def __init__(self, serverName=None, serverID=None, style=discord.ButtonStyle.grey, disabled=False):
#         super().__init__(label=serverName, 
#  style=style, custom_id=str(serverID), disabled=disabled)
#     async def callback(self, interaction: discord.Interaction):
#       guild = interaction.client.get_guild(int(self.custom_id))
#       cafe = interaction.client.get_guild(717029019270381578)
#       embed = discord.Embed(title="Confirm Server", description=f"Are you sure you want to partner **{guild.name}** with **{cafe.name}**?", color=0xFF0000) 
#       await interaction.response.edit_message(embed=embed, view=ConfirmView(int(self.custom_id)))


# class ConfirmView(discord.ui.View):
#   def __init__(self, serverID=None):
#     super().__init__(timeout=None)
#     self.serverID = serverID

#   @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple, custom_id='goback')
#   async def goback(self, interaction: discord.Interaction, button: discord.ui.Button):
#     content = await postServers(interaction)
#     await interaction.response.edit_message(embed=content[0], view=content[1])

#   @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='confirmpartner')
#   async def confirmpartner(self, interaction: discord.Interaction, button: discord.ui.Button):
#     guild = interaction.client.get_guild(self.serverID) 
#     options = []
#     for category in guild.categories:
#       options.append(discord.SelectOption(label=category.name, value=category.id, emoji="#️⃣"))
#     view = View()
#     view.add_item(CategorySelect(options, self.serverID))
#     view.add_item(ChannelSelect(options, self.serverID, disabled=True))
#     await interaction.response.edit_message(embed=discord.Embed(description=f"Choose the **category** of the channel that you want **our partner announcement to be posted**.", color=discord.Color.blurple()), view=view)

# class CategorySelect(discord.ui.Select):
#     def __init__(self, options=None, serverID=None):
#         self.serverID = serverID
#         super().__init__(placeholder="Select a category",max_values=1,min_values=1,options=options, custom_id="categoryselect")
#     async def callback(self, interaction: discord.Interaction):
#         selectedValue = self.values[0]
#         Category = interaction.client.get_channel(int(selectedValue))
#         guild = interaction.client.get_guild(self.serverID) 
#         options = []
#         for category in guild.categories:
#           if category == Category:
#             options.append(discord.SelectOption(label=category.name, value=category.id, emoji="#️⃣", default=True))
#           else:
#             options.append(discord.SelectOption(label=category.name, value=category.id, emoji="#️⃣"))
#         options2 = []
#         for channel in Category.text_channels:
#           options2.append(discord.SelectOption(label=channel.name, value=channel.id, emoji="#️⃣"))
#         view = View()
#         view.add_item(CategorySelect(options, self.serverID))
#         view.add_item(ChannelSelect(options2, self.serverID, int(selectedValue)))
#         await interaction.response.edit_message(embed=discord.Embed(description=f"You have chosen {Category.mention} `({Category.id})`.\n\nNow, choose a **channel** from the aforementioned category that you want **our partner announcement to be posted**.", color=discord.Color.blurple()), view=view)

# class ChannelSelect(discord.ui.Select):
#     def __init__(self, options=None, serverID=None, categoryID=None, disabled=False):
#         self.serverID = serverID
#         self.categoryID = categoryID
#         super().__init__(placeholder="Select a channel from the above category",max_values=1,min_values=1,options=options, custom_id="channelselect", disabled=disabled)
#     async def callback(self, interaction: discord.Interaction):
#         selectedValue = self.values[0]
#         chn = interaction.client.get_channel(int(selectedValue))

#         selectedValue = self.values[0]
#         Category = interaction.client.get_channel(int(self.categoryID))
#         guild = interaction.client.get_guild(self.serverID) 
#         options = []
#         for category in guild.categories:
#           if category == Category:
#             options.append(discord.SelectOption(label=category.name, value=category.id, emoji="#️⃣", default=True))
#           else:
#             options.append(discord.SelectOption(label=category.name, value=category.id, emoji="#️⃣"))
#         options2 = []
#         for channel in Category.text_channels:
#           if chn == channel:
#             options2.append(discord.SelectOption(label=channel.name, value=channel.id, emoji="#️⃣", default=True))
#           else:
#                         options2.append(discord.SelectOption(label=channel.name, value=channel.id, emoji="#️⃣"))
#         view = View()
#         view.add_item(CategorySelect(options, self.serverID))
#         view.add_item(ChannelSelect(options2, self.serverID, int(self.categoryID)))
#         view.add_item(ConfirmTheirChannelButton(channel=chn, guild=guild))
#         # view.add_item(SubmitServerAdButton())
      
#         await interaction.response.edit_message(embed=discord.Embed(description=f"You have selected {chn.mention} `({chn.id})` as your partnership channel.\n\nClick the following button and we will automatically send our server advertisement with @everyone ping to that channel.", color=discord.Color.blurple()), view=view)

# class SelectView(discord.ui.View):
#     def __init__(self, timeout = None):
#         super().__init__(timeout=timeout)
#         self.add_item(CategorySelect())
#         self.add_item(ChannelSelect())
#         self.add_item(SubmitServerAdButton())

# class ConfirmTheirChannelButton(discord.ui.Button):
#     def __init__(self, channel=None, guild=None):
#         self.channel = channel
#         self.guild = guild
#         super().__init__(label=f"Confirm #{self.channel.name} as partnership channel", style=discord.ButtonStyle.blurple, custom_id='confirmtheirchannelbutton', emoji="📢")
#     async def callback(self, interaction: discord.Interaction):
#       try:
#         await self.channel.send("""・・・・・**Genshin Impact Cafe ́♡** ・・・・・

# Genshin Impact Cafe is a fun place for and a community dedicated to all **Genshin impact players** with lots of exclusive and exciting roles for Genshin Impact players!!

# > ・・・・・__**OUR SPECIALITY**__・・・・・
# > ➣ **Cool & custom roles** for everyone 🍡
# > ➣ Lots of **giveaways** 🎁
# >  ➣ Experts to help in **builds & co-op** 🤝
# > ➣ **500+** custom **emojis & stickers** 😱
# > *(If you have nitro you would definitely love using them)*

#  ☙ **JOIN US!!** we'd **love** to have you here! ☙
#         ⍣ ** https://discord.gg/u2YSGBNUrg ** ⍣ ||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​|| _ _ _ _ _ _ @everyone""")
#         view = View()
#         view.add_item(SubmitServerAdButton(self.guild))
      
#         await interaction.response.edit_message(embed=discord.Embed(description=f"We have successfully sent our server advertisement to {self.channel.mention}. \n\nIt's time to enter **your server advertisement** for it to be posted on our server.", color=discord.Color.blurple()), view=view)
        
#         ref = db.reference("/Partners")
    
#         data = {
#         		self.guild.id: {
#               "Server ID": self.guild.id
#             }
#         	}
    
#         for key, value in data.items():
#         	ref.push().set(value)
#       except Exception:
#         view = View()
#         view.add_item(ConfirmTheirChannelButton(self.channel, self.guild))
#         await interaction.response.edit_message(embed=discord.Embed(description=f"Sorry something went wrong...\n\nPlease make sure I have permission to send messages + embed links in {self.channel.mention}, and try again. ", color=discord.Color.red()), view=view)

# class SubmitServerAdButton(discord.ui.Button):
#     def __init__(self, guild=None, l="Submit your server advertisement"):
#         super().__init__(label=l, style=discord.ButtonStyle.blurple, custom_id='submitserverad', emoji="✍️")
#         self.guild = guild
#     async def callback(self, interaction: discord.Interaction):
#       await interaction.response.send_modal(modal(self.guild, title="Enter your server advertisement"))

# class PreviewNotif(discord.ui.Button):
#     def __init__(self,):
#         super().__init__(label="Here's the preview of your partnership message", style=discord.ButtonStyle.grey, disabled=True)

# class SendServerAdButton(discord.ui.Button):
#     def __init__(self, guild, msg, tit, desc, color):
#         super().__init__(label="Confirm server advertisement", style=discord.ButtonStyle.green, custom_id='sendserverad', emoji="✅")
#         self.msg = msg
#         self.tit = tit
#         self.desc = desc
#         self.color = color
#         self.guild = guild
#     async def callback(self, interaction: discord.Interaction):
#       chn = interaction.client.get_channel(938326450208129024)
#       us = interaction.client.get_guild(717029019270381578)
#       user = us.get_member(interaction.user.id)
#       role = us.get_role(1049100647884132443)
#       await user.add_roles(role)
#       if str(self.tit) == "" and str(self.desc) == "":
#         embed = None
#       else:
#         embed = discord.Embed(title=str(self.tit), description=str(self.desc), color=self.color)
#       if self.guild.member_count >= 600 and self.guild_member_count < 1000:
#         self.msg = f"<@&759377982467866664> **Partnered by {interaction.user.mention}**\n\n{self.msg}"
#       elif self.guild.member_count >= 1000 and self.guild_member_count < 4000:
#         self.msg = f"@here **Partnered by {interaction.user.mention}**\n\n{self.msg}"
#       elif self.guild.member_count >= 4000:
#         self.msg = f"@everyone **Partnered by {interaction.user.mention}**\n\n{self.msg}"
#       else:
#         self.msg = f"**Partnered by {interaction.user.mention}**\n\n{self.msg}"
#       await chn.send(content=str(self.msg), embed=embed)
#       await interaction.response.edit_message(content=None, embed=discord.Embed(description=f"Your server advertisement has been sent to {chn.mention}! Thank you so much for taking your time to partner with us! To honor our partnership, you have been awarded the <@&1049100647884132443> role in our server! Have a great rest of your day!", color=discord.Color.green()), view=None)
      
# # class MyModal(discord.ui.Modal):
# #     def __init__(self, *args, **kwargs) -> None:
# #         super().__init__(*args, **kwargs)

# #         self.msg = self.add_item(discord.ui.InputText(label="Short Input"))
# #         self.add_item(discord.ui.InputText(label="Long Input", style=discord.InputTextStyle.long))

# #     async def callback(self, interaction: discord.Interaction):
      
# # class modal(discord.ui.Modal, title = "Enter your server advertisement!"):

# class modal(discord.ui.Modal):
#   def __init__(self, guild, title):
#     super().__init__(title=title)
#     self.guild = guild
    
#     self.msg = discord.ui.TextInput(label="Normal message content", style=discord.TextStyle.paragraph, placeholder=f"Feel free to use markdowns and links if you'd like", max_length=2000, required=False)
#     self.add_item(self.msg)
  
#     self.embedtitle = discord.ui.TextInput(label="Title of the embed", style=discord.TextStyle.paragraph, placeholder="Feel free to use markdowns and links if you'd like", max_length=256, required=False)
#     self.add_item(self.embedtitle)
  
#     self.description = discord.ui.TextInput(label="Description of the embed", style=discord.TextStyle.paragraph, placeholder="Feel free to use markdowns and links if you'd like", max_length=4000, required=False)
#     self.add_item(self.description)
  
#     self.color = discord.ui.TextInput(label="Color of the embed", style=discord.TextStyle.short, placeholder="Please enter a hex code (e.g. #ff0000)", max_length=7, required=False)
#     self.add_item(self.color)

#   async def on_submit(self, interaction:discord.Interaction):
#     tit = str(self.embedtitle)
#     desc = str(self.description)
#     color = discord.Color.blurple()
#     if str(self.color) != "":
#       hex = str(self.color)
#       if hex.startswith('#'):
#         hex = hex[1:]
#       async with aiohttp.ClientSession() as session:
#         async with session.get('https://www.thecolorapi.com/id', params={"hex": hex}) as server:
#           if server.status == 200:
#             js = await server.json()
#             try:
#               color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
#             except:
#               color = discord.Color.blurple()

#     if tit == "" and desc == "":
#       embed = None
#     else:
#       embed = discord.Embed(title=tit, description=desc, color=color)
#     view = View()
#     view.add_item(PreviewNotif())
#     view.add_item(SubmitServerAdButton(guild=self.guild, l="Rewrite server advertisement"))
#     view.add_item(SendServerAdButton(self.guild, str(self.msg), tit, desc, color))
#     await interaction.response.edit_message(content=str(self.msg), embed=embed, view=view)
      

# class PartnershipView(discord.ui.View):
#     def __init__(self, *, timeout = None):
#       super().__init__(timeout=timeout)
#       self.add_item(RefreshButton())
#       self.add_item(ServerButton())

class Partnership(commands.GroupCog, name="partnership"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "panel",
    description = "Sends the partnership panel"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def partnership_panel(
    self,
    interaction: discord.Interaction
  ) -> None:
    if interaction.guild.id != 717029019270381578:
      await interaction.response.send_message("This command can only be used in **Genshin Impact Café ♡** and is only reversed for its staff team to use. Join https://discord.gg/DKJj3GRbhb if you haven't already!", ephemeral=True)
    else:
      embed = discord.Embed(color=0x41FF00)
      embed.set_author(name="Partnership Information", icon_url="https://static.wikia.nocookie.net/discord/images/3/31/Partner.png/")
      embed.add_field(name=":x::bell: No-ping Partnership ", value="""If your server has __at least 500 members__, you qualify for a no-ping partnership with our server. This includes your server advertisement being posted in <#938326450208129024> along with our advertisement being posted in your server's partnership channel, both without any pings!
⠀
""", inline=True)
      embed.add_field(name=":ballot_box_with_check: :bell: Normal Partnership", value=""" **100+ members**
Your advertisement posted in <#938326450208129024> with no ping. Café's advertisement posted in your server with a @everyone ping.

**600+ members**
Your advertisement posted in <#938326450208129024> with a <@&759377982467866664> ping. Café's advertisement posted in your server with a @everyone ping. (Or any equivalent )

**1000+ members**
Your advertisement posted in <#938326450208129024> with a @here ping. Café's advertisement posted in your server with a @everyone ping.

**4000+ members**
Your advertisement posted in <#938326450208129024> with a @everyone ping. Café's advertisement posted in your server with a @everyone ping.
⠀
""", inline=False)
      embed.add_field(name=":pencil: Partner Requirements ", value="""
- The server by any means must follow Discord TOS and any other applicable laws
- The server should be friendly and non-toxic overall
- The server should be SFW and suitable for all ages
- Servers that are mainly or only for "advertising" and "giveaways" are not acceptable

_If your server does not or no longer fulfills the aforementioned requirements, or your server advertisement posted in our server contains inappropriate and rule-offending contents, we reserve the right to take away you and your server's partnership status._
""", inline=False)
      embed2 = discord.Embed(title="Want to become a server partner?", description=f"Press the following button and start the partnership process immediately!", color=0x41FF00)
      view = View()
      from partnership.partnership import PartnershipButton as pb
      view.add_item(pb())
      from partnership.nopingpartnership import PartnershipButton as nppb
      view.add_item(nppb())
      await interaction.channel.send(embeds=[embed, embed2], view=view)
      await interaction.response.send_message("Sent!", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Partnership(bot))