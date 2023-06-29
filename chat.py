import discord, firebase_admin, asyncio, datetime, os, openai
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db
from Bard import Chatbot

class MessageCommands(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user: 
        return

    ### --- FISCHL AI --- ###
    if "<@732422232273584198>" in message.content and not(message.content == "<@732422232273584198>"):
      async with message.channel.typing():
        token = os.environ['BARD_KEY']
        chatbot = Chatbot(token)
        
        # response = chatbot.ask(message.content.replace("<@732422232273584198>", f"You are now a Discord bot named Fischl, talking in the server named {message.guild.name}. A member of the server named {message.author.name} prompts you with the following question/phrase in the chat. Wrap your response to the question/phrase with the $ symbol."))['content']
        try:
          response = chatbot.ask(message.content.replace("<@732422232273584198>", ""))['content']
          print(response)
          await message.reply(response)
        except Exception:
          msg = await message.reply(embed=discord.Embed(title="Oops!", description="An error occurred. Please check back later.", color=discord.Color.red()))
          await asyncio.sleep(5)
          await msg.delete()

async def setup(bot): 
  await bot.add_cog(MessageCommands(bot))