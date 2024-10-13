import discord, firebase_admin, asyncio, datetime
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db

class OnStatusUpdate(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_presence_update(self, before, after):
    if after.guild.id == 717029019270381578:
      chn = self.client.get_channel(1083804717886488686)
      role = after.guild.get_role(996707492853710888)
      if ("discord.gg/traveler" not in str(after.activity) or "gg/traveler" not in str(after.activity)) and (("discord.gg/traveler" in str(before.activity) or "gg/traveler" in str(before.activity))) and role in after.roles:
        if str(after.status) == "offline":
          embed = discord.Embed(description=f":yellow_circle: {after.mention} went offline.")
        else:
          await after.remove_roles(role)
          embed = discord.Embed(description=f":red_circle: {after.mention} has **removed** vanity link from their status.")
          embed.set_footer(text="Role removed")
        await chn.send(embed=embed)
      
      # Added vanity, go offline, removed vanity, go back online
      if ("discord.gg/traveler" not in str(after.activity) or "gg/traveler" not in str(after.activity)) and str(before.status) == "offline" and role in after.roles:
        chn = self.client.get_channel(1083804717886488686)
        await after.remove_roles(role)
        embed = discord.Embed(description=f":red_circle: {after.mention} has **removed** vanity link from their status.")
        embed.set_footer(text="Role removed")
        await chn.send(embed=embed)
       
      if ("discord.gg/traveler" in str(after.activity) or "gg/traveler" in str(after.activity)) and role not in after.roles:
        await after.add_roles(role)
        if ("discord.gg/traveler" not in str(before.activity) or "gg/traveler" not in str(before.activity)):
          if str(before.status) == "offline":
            embed = discord.Embed(description=f":white_circle: {after.mention} went back online.")
          else:
            embed = discord.Embed(description=f":green_circle: {after.mention} has **added** vanity link to their status.")
            embed.set_footer(text="Role added")
          await chn.send(embed=embed)
      
      
    
  

async def setup(bot): 
  await bot.add_cog(OnStatusUpdate(bot))