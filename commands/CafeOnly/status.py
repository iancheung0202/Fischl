import discord, firebase_admin, random, datetime
from discord import app_commands
from discord.ext import commands
from firebase_admin import db


class Status(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_member_update(self, memberbefore, memberafter):
    guil = self.client.get_guild(717029019270381578)
    role = discord.utils.get(guil.roles, id=996707492853710888)
    chn = self.client.get_channel(951387966058659850)  
    if memberafter.name != 'Fischl' and memberbefore.discriminator != '8536':
      if memberafter.activity != memberbefore.activity:
          if memberafter.activity != None : 
            if 'gg/traveler' in str(memberafter.activity) or 'gg/traveler' in str(memberafter.activity):
              await memberafter.remove_roles(role)
              embed=discord.Embed(color=discord.Color.red())
              embed.set_author(name='Vanity Info', url = memberafter.avatar_url)
              embed.set_thumbnail(url = memberafter.avatar_url)
              embed.add_field(name='User Name - ', value=f'{memberafter.name} `<@{memberafter.id}>`', inline=False)
              embed.add_field(name='Role Info', value=f'{memberafter.name} has lost vanity role .',inline=False)
              embed.add_field(name='User Status', value=f'{memberafter.activity}')
              end = datetime.datetime.now()
              embed.set_footer(text=end, icon_url= guil.icon_url)
              await chn.send(embed=embed)
              await chn.send('================')
  
            if role not in memberafter.roles:
              if 'gg/traveler' in str(memberafter.activity):  
                await memberafter.add_roles(role)
                embed=discord.Embed(color=discord.Color.green())
                embed.set_author(name='Vanity Info', url = memberafter.avatar_url)
                embed.set_thumbnail(url = memberafter.avatar_url)
                embed.add_field(name='User Name - ', value=f'{memberafter.name} `<@{memberafter.id}>`', inline=False)
                embed.add_field(name='Role Info', value=f'{memberafter.name}  got Vanity role by having vanity on status',inline=False)
                embed.add_field(name='User Status', value=f'{memberafter.activity}')
                end = datetime.now()
                embed.set_footer(text=end, icon_url= guil.icon_url)
                await chn.send(embed=embed)
                await chn.send('================')
              else:
                await memberafter.remove_roles(role)
            else:
              if 'gg/traveler' not in str(memberafter.activity): 
                await memberafter.remove_roles(role)
                embed=discord.Embed(color=discord.Color.red())
                embed.set_author(name='Vanity Info', url = memberafter.avatar_url)
                embed.set_thumbnail(url = memberafter.avatar_url)
                embed.add_field(name='User Name - ', value=f'{memberafter.name} `<@{memberafter.id}>`', inline=False)
                embed.add_field(name='Role Info', value=f'{memberafter.name} has lost vanity role .',inline=False)
                embed.add_field(name='User Status', value=f'{memberafter.activity}')
                end = datetime.now()
                embed.set_footer(text=end, icon_url= guil.icon_url)
                await chn.send(embed=embed)
                await chn.send('================')

async def setup(bot): 
  await bot.add_cog(Status(bot))