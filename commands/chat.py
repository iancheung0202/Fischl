import discord, firebase_admin, asyncio, datetime, os, openai
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db
from ai import request

class MessageCommands(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if "<@732422232273584198>" in message.content and message.content != "<@732422232273584198>":
        query = message.content.replace("<@732422232273584198>", "")
        answer = request(query,message.guild.id)
        await message.reply(content=answer)

async def setup(bot): 
  await bot.add_cog(MessageCommands(bot))