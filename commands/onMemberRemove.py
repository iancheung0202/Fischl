import discord, firebase_admin, asyncio, datetime
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db

class OnMemberRemove(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_member_remove(self, user):
    if user.guild.id == 775815873775665173:
      channel = self.client.get_channel(1072145807924547594)
      await channel.send(f"**{user.name}#{user.discriminator}** just left the server")
  

async def setup(bot): 
  await bot.add_cog(OnMemberRemove(bot))