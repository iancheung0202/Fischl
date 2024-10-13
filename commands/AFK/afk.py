import discord, firebase_admin, datetime, asyncio, time, emoji
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

@app_commands.guild_only()
class AFK(commands.GroupCog, name="afk"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "set",
    description = "Set your presence as AFK"
  )
  @app_commands.describe(
    message = "The message to show when mentioned (Optional)",
  )
  async def afk_set(
    self,
    interaction: discord.Interaction,
    message: str = None
  ) -> None:
    ref = db.reference("/AFK")
    afks = ref.get()
    
    try:
      for key, val in afks.items():
        if val['User ID'] == interaction.user.id and val['Server ID'] == interaction.guild.id:
          db.reference('/AFK').child(key).delete()
          break
    except Exception:
      pass

    data = {
      interaction.channel.id: {
        "User ID": interaction.user.id,
        "Message": message,
        "Timestamp": f"<t:{int(interaction.created_at.timestamp())}:R>",
        "Server ID": interaction.guild.id
      }
    }

    for key, value in data.items():
      ref.push().set(value)
    
    nickname = f"[AFK] {interaction.user.nick.replace('[AFK] ', '')}"[:32]
    try:
      await interaction.user.edit(nick=nickname)
    except Exception:
      pass
    await interaction.response.send_message(f"{interaction.user.mention}, I have set your AFK{': ' + message if message is not None else ''}")

  @app_commands.command(
    name = "remove",
    description = "Remove your AFK presence"
  )
  async def afk_remove(
    self,
    interaction: discord.Interaction,
  ) -> None:
    ref = db.reference("/AFK")
    afks = ref.get()
    found = False
    try:
      for key, val in afks.items():
        if val['User ID'] == interaction.user.id and val['Server ID'] == interaction.guild.id:
          found = True
          db.reference('/AFK').child(key).delete()
          break
    except Exception:
      pass
    if found:
      try:
        await interaction.user.edit(nick=f"{nickname.replace('[AFK] ', '')}")
      except Exception:
        pass
      await interaction.response.send_message(f"Welcome back, {interaction.user.mention}. I removed your AFK.")
      await asyncio.sleep(6)
      await interaction.delete_original_response()
    else:
      await interaction.response.send_message(f"You don't have your AFK set.")
      await asyncio.sleep(6)
      await interaction.delete_original_response()
      

class OnAFKMessage(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user: 
      return

    if "?afk" in message.content and (message.guild.id == 717029019270381578):
      ref = db.reference("/AFK")
      afks = ref.get()
      try:
        for key, val in afks.items():
          if val['User ID'] == message.author.id and val['Server ID'] == message.guild.id:
            db.reference('/AFK').child(key).delete()
            break
      except Exception:
        pass
      msg = message.content.split("?afk ")[1]
      data = {
        message.channel.id: {
          "User ID": message.author.id,
          "Message": msg,
          "Timestamp": f"<t:{int(message.created_at.timestamp())}:R>",
          "Server ID": message.guild.id
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      nickname = f"[AFK] {message.author.nick.replace('[AFK] ', '')}"[:32]
      try:
        await message.author.edit(nick=nickname)
      except Exception:
        pass
      await message.channel.send(f"{message.author.mention}, I have set your AFK{': ' + msg if msg is not None else ''}\n\n:warning: *We are transitioning our AFK system away from Dyno so that we can customize this feature for our server members.* \n***Please use `-afk` or </afk set:1280696208003956807> next time.*** :robot:")
        
    if "-afk" in message.content:
      ref = db.reference("/AFK")
      afks = ref.get()
      try:
        for key, val in afks.items():
          if val['User ID'] == message.author.id and val['Server ID'] == message.guild.id:
            db.reference('/AFK').child(key).delete()
            break
      except Exception:
        pass
      msg = message.content.split("-afk ")[1]
      data = {
        message.channel.id: {
          "User ID": message.author.id,
          "Message": msg,
          "Timestamp": f"<t:{int(message.created_at.timestamp())}:R>",
          "Server ID": message.guild.id
        }
      }
      for key, value in data.items():
        ref.push().set(value)
      nickname = f"[AFK] {message.author.nick.replace('[AFK] ', '')}"[:32]
      try:
        await message.author.edit(nick=nickname)
      except Exception:
        pass
      await message.channel.send(f"{message.author.mention}, I have set your AFK{': ' + msg if msg is not None else ''}")
        
    if "<@" in message.content:
      error = False
      try:
        userMentionedID = int(message.content.split("<@")[1].split(">")[0])
      except Exception:
        error = True
      if error:
        return
      userMentioned = message.guild.get_member(userMentionedID)
      if userMentioned == message.author:
        raise Exception()
      ref = db.reference("/AFK")
      afks = ref.get()
      found = False
      msg = None
      try:
        for key, val in afks.items():
          if val['User ID'] == userMentionedID and val['Server ID'] == message.guild.id:
            found = True
            timestamp = val['Timestamp']
            msg = val['Message']
      except Exception:
        pass
      
      if found:
        await message.channel.send(f"`{userMentioned.display_name.replace('[AFK] ', '')}` is AFK{': ' + msg if msg is not None else ''} - {timestamp}")
        
    nickname = message.author.display_name
    if "[AFK] " in nickname and "?afk " not in message.content and "-afk " not in message.content:
      ref = db.reference("/AFK")
      afks = ref.get()
      found = False
      try:
        for key, val in afks.items():
          if val['User ID'] == message.author.id and val['Server ID'] == message.guild.id:
            found = True
            db.reference('/AFK').child(key).delete()
            break
      except Exception:
        pass
      if found:
        try:
          await message.author.edit(nick=f"{nickname.replace('[AFK] ', '')}")
        except Exception:
          pass
        msg = await message.reply(f"Welcome back, {message.author.mention}. I removed your AFK.")
        await asyncio.sleep(5)
        await msg.delete()
      

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(AFK(bot))
  await bot.add_cog(OnAFKMessage(bot))