import discord, firebase_admin, random, datetime, asyncio, time, re
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View

class BetaOnMessage(commands.Cog): 
  def __init__(self, bot):
    self.client = bot

  @commands.Cog.listener() 
  async def on_message(self, message):
    
    if message.content == "-FischlBeta":
      await message.reply("This is working!")


async def setup(bot): 
  await bot.add_cog(BetaOnMessage(bot))