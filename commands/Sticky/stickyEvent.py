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

    if message.content == "!-lm":
      ref = db.reference("/Sticky Messages")
      stickies = ref.get()
  
      for key, val in stickies.items():
        channelID = val['Channel ID']
        try:
          channel = self.client.get_channel(channelID)
          if "<:sticky:1100214185197043772>" not in channel.topic:
            await channel.edit(topic=str(channel.topic)+" <:sticky:1100214185197043772>")
            print("DONE")
        except Exception as e:
          await message.channel.send(str(channelID)+"\n"+str(e))
        
    if type(message.channel) == discord.channel.TextChannel:
      if message.channel.topic != None and "<:sticky:1100214185197043772>" in message.channel.topic:
        print(True)
    # print(f"In {message.guild.name} by {message.author.name} sent {message.content}")

    # ----- STICKY MESSAGE ----- #
      ref = db.reference("/Sticky Messages")
      stickies = ref.get()
  
      for key, val in stickies.items():
        if val['Channel ID'] == message.channel.id:
          messageContent = val["Message Content"]
          # try:
          # await asyncio.sleep(2)
          oldMsg = await message.channel.fetch_message(val["Message ID"])
          await oldMsg.delete()
          # except Exception:
          #   pass
          # await asyncio.sleep(2)
          # if message.channel.id == 1051748060616736789:
          #   view = View()
          #   view.add_item(CreateTicketButton("Submit Answer", "✍️", discord.ButtonStyle.blurple))
          #   msg = await message.channel.send(messageContent, view=view)
          # else:
          if True:
            
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