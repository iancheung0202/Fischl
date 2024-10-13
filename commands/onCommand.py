import discord, datetime, time
from discord import app_commands
from discord.ext import commands

class OnCommand(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_app_command_completion(self, interaction, command):
    channel = self.client.get_channel(1030892842308091987)

    #try:
      #server_invite = await interaction.channel.create_invite(max_age=604800, max_uses=0)
    #except Exception:
    server_invite = "https://iancheung.dev"
    embed = discord.Embed(description=f"""
    **Slash Command:** `/{command.name}`
    **Used at:** <t:{int(interaction.created_at.timestamp())}:R>
    
    **User Name:** {interaction.user.name}
    **User ID:** `{interaction.user.id}`
    **User Created:** <t:{int(interaction.user.created_at.timestamp())}:R>
    
    **Guild Name:** [{interaction.guild.name}]({server_invite})
    **Guild ID:** `{interaction.guild.id}`
    **Guild Member Count:** {interaction.guild.member_count}
    
    **Channel Name:** [#{interaction.channel.name}]({server_invite})
    **Channel ID:** `{interaction.channel.id}`
    """, colour=discord.Color.blurple())
    # print(interaction.data)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await channel.send(embed=embed)
    
      
  

async def setup(bot): 
  await bot.add_cog(OnCommand(bot))