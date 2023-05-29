import discord
from discord import app_commands
from discord.ext import commands

class OnCommand(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_app_command_completion(self, interaction, command):
    channel = self.client.get_channel(1030892842308091987)
      
    await channel.send(f"**/{command.name}** is used in <#{interaction.channel.id}>")
    
      
  

async def setup(bot): 
  await bot.add_cog(OnCommand(bot))