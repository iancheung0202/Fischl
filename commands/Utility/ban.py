import discord, datetime, time
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class Ban(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "ban",
    description = "Ban a user who is in the server"
  )
  @app_commands.describe(
    user = "The user to ban",
    reason = "The reason for banning (sent to user + logged)",
    delete_message_days = "Days of chat history to purge from this user (default: 7)",
    silent = "If true, user will NOT be notified via DM"
  )
  @app_commands.checks.has_permissions(ban_members=True)
  @app_commands.guild_only()
  async def ban(
    self,
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str,
    delete_message_days: int = 7,
    silent: bool = False
  ) -> None:
    if interaction.guild.id == 717029019270381578:
      chn = interaction.client.get_channel(1084409353186050118)
    elif interaction.guild.id == 1272650514542100541:
      chn = interaction.client.get_channel(1281040797709373503)
    else:
      chn = None
      
    if user == interaction.user:
      await interaction.response.send_message("Are you crazy? Don't ban yourself!!!", ephemeral=True)
      raise Exception()
    if not silent:
      successDM = "User has been notified via DM."
      try:
        view = View()
        button = Button(label="Appeal Your Ban", style=discord.ButtonStyle.link, url="https://forms.gle/yajGFJnVj9oASiv6A")
        view.add_item(button)
        if interaction.guild.id == 717029019270381578:
          embed = discord.Embed(title=f"You were banned from **{interaction.guild.name}** indefinitely", description="If you believe this ban is a mistake, or wish to appeal you ban, please submit your appeal to this form: https://forms.gle/yajGFJnVj9oASiv6A", color=0x07afc5)
          embed.add_field(name="Reason", value=reason, inline=True)
          await user.send(embed=embed, view=view)
        elif interaction.guild.id == 1272650514542100541:
          embed = discord.Embed(title=f"You were banned from **{interaction.guild.name}** indefinitely", color=0x07afc5)
          embed.add_field(name="Reason", value=reason, inline=True)
          await user.send(embed=embed)
      except Exception as e:
        print(e)
        successDM = "User closed their DMs, and is **not** notified."
    else:
      successDM = "Moderator suppressed notification and user is **not** notified."
    await interaction.guild.ban(discord.Object(id=user.id), delete_message_days=delete_message_days, reason=reason)
    #chn = interaction.client.get_channel(1084409353186050118)
    embed = discord.Embed(title="User Banned", color=0xe42c0c)
    embed.add_field(name="__Offender__", value=f"**User Mention:** {user.mention}\n**User Name:** {user.name}\n**User ID:** `{user.id}`", inline=True)
    embed.add_field(name="__Responsible Moderator__", value=f"**User Mention:** {interaction.user.mention}\n**User Name:** {interaction.user.name}\n**Rank:** {interaction.user.roles[len(interaction.user.roles) - 1].mention}", inline=True)
    embed.add_field(name="__Ban Details__", value=f"**Reason:** {reason}\n**Timestamp:** <t:{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}:F>\n**DM Status:** {successDM}", inline=False)
    if chn is not None:
      await chn.send(embed=embed)
    await interaction.response.send_message(embed=embed)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Ban(bot))