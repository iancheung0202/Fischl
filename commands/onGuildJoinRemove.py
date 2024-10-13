import discord, datetime, time
from discord import app_commands
from discord.ext import commands

class ServerLeaveButton(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Leave', style=discord.ButtonStyle.red, custom_id='leaveserver')
  async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.defer(thinking=True)
    try:
      serverID = int(interaction.message.embeds[0].description.split("**")[4])
      server = interaction.client.get_guild(serverID)
      await server.leave()
      await interaction.followup.send(f":door::man_running: <-- {server.name}.")
      await interaction.message.delete()
    except Exception as e:
      await interaction.followup.send(f"Sorry, something went wrong. Please see the following error: \n`{e}`")

class OnGuild(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_guild_join(self, guild):
    print(guild.name)
    user = guild.get_member(self.client.user.id)
    SERVER = self.client.get_guild(717029019270381578)
    ian = SERVER.get_member(692254240290242601)
    embed = discord.Embed(title="[INVITED] Basic Server Information", description=f"""
    **Server Name:** {guild.name}
    **Server ID:** {guild.id}
    **Members Count:** {len(guild.members)}
    **Joined:** <t:{int(float(time.mktime(user.joined_at.timetuple())))}:R>
    """, colour=0x008000)
    try:
      embed.set_footer(icon_url=guild.icon.url, text=guild.name)
    except Exception:
      pass
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    try:
      server_invite = await guild.text_channels[0].create_invite(max_age = 604800, max_uses = 0)
      await ian.send(f"{server_invite}", embeds=[embed], view=ServerLeaveButton())
    except Exception as e:
      print(e)
      await ian.send(f"`SERVER DISABLED INVITE CREATION`", embeds=[embed], view=ServerLeaveButton())
    await ian.send("Use `-removefischlinvites`")
  
  @commands.Cog.listener() 
  async def on_guild_remove(self, guild):
    print(guild.name)
    user = guild.get_member(self.client.user.id)
    SERVER = self.client.get_guild(717029019270381578)
    ian = SERVER.get_member(692254240290242601)
    embed = discord.Embed(title="[LEFT] Basic Server Information", description=f"""
    **Server Name:** {guild.name}
    **Server ID:** {guild.id}
    **Members Count:** {len(guild.members)}
    **Joined:** <t:{int(float(time.mktime(user.joined_at.timetuple())))}:R>
    """, colour=0xFF0000)
    try:
      embed.set_footer(icon_url=guild.icon.url, text=guild.name)
    except Exception:
      pass
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    try:
      server_invite = await guild.text_channels[0].create_invite(max_age = 604800, max_uses = 0)
      await ian.send(f"{server_invite}", embeds=[embed])
    except Exception as e:
      print(e)
      await ian.send(f"`SERVER DISABLED INVITE CREATION`", embeds=[embed])
    
      
  

async def setup(bot): 
  await bot.add_cog(OnGuild(bot))