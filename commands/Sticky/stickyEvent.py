import discord, firebase_admin, asyncio
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db
from discord.ui import Button, View
from commands.Tickets.tickets import CreateTicketButton

class OnMessage(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user: 
        return

    # ----- STICKY MESSAGE ----- #
    ref = db.reference("/Sticky Messages")
    stickies = ref.get()

    for key, val in stickies.items():
      if val['Channel ID'] == message.channel.id:
        messageContent = val["Message Content"]
        oldMsg = await message.channel.fetch_message(val["Message ID"])
        await oldMsg.delete()
        await asyncio.sleep(2)
        if message.channel.id == 1051748060616736789:
          view = View()
          view.add_item(CreateTicketButton("Submit Answer", "✍️", discord.ButtonStyle.blurple))
          msg = await message.channel.send(messageContent, view=view)
        else:
          msg = await message.channel.send(messageContent)
        db.reference('/Sticky Messages').child(key).delete()
        data = {
          message.channel.id: {
            "Channel ID": message.channel.id,
            "Message ID": msg.id,
            "Message Content": messageContent
          }
        }
    
        for key, value in data.items():
          ref.push().set(value)
        break
  

async def setup(bot): 
  await bot.add_cog(OnMessage(bot))