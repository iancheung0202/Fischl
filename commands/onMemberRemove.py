import discord, firebase_admin, asyncio, datetime
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db

class OnMemberRemove(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_member_remove(self, user):
    if user.guild.id == 862842816571768852:
      channel = self.client.get_channel(862842816571768854)
      member_count = 0;
      for member in user.guild.members:
        member_count += 1
      
      embed = discord.Embed(title="Some traveler just left us :(", description=f"""
  Just when I was busy entertaining the other **{member_count}** travelers, I looked over my shoulder and found **{user.mention}** has left our community! What a pity!
  """, color=0xF4EE61)
      embed.set_author(name=user.name, icon_url=user.avatar.url)
      embed.set_thumbnail(url="https://c.tenor.com/6N0ddNG9OE0AAAAC/hutao-genshin-impact.gif")
      embed.set_image(url="https://wallpaperforu.com/wp-content/uploads/2021/07/Wallpaper-Genshin-Impact-Anime-Boys-Zhongli-Genshin-Imp152048x1152.jpg")
      embed.set_footer(text=f"ID: {user.id}")
      embed.timestamp = datetime.datetime.utcnow()
      await channel.send(embed=embed)
    # if member.guild.id == 783528750474199041:
    #   channel = self.client.get_channel(783528750704492596)
    #   msg = f"{member.name} left our server! Only **{len(member.guild.members)} members** left!"
    #   await channel.send(msg)
  

async def setup(bot): 
  await bot.add_cog(OnMemberRemove(bot))