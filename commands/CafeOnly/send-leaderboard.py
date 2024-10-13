import discord, firebase_admin, datetime, asyncio, time, emoji, aiohttp
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
    

class TravelerOfTheWeek(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "send-leaderboard",
    description = "Posts the weekly leaderboard for Traveler of the Week role"
  )
  @app_commands.describe(
    text_user = "User with the most messages",
    voice_user = "User with the most voicee time",
    link = "The link of the leaderboard image"
  )
  @app_commands.checks.has_permissions(administrator=True)
  @app_commands.guild_only()
  async def send_leaderboard(
    self,
    interaction: discord.Interaction,
    text_user: discord.Member,
    voice_user: discord.Member,
    link: str
  ) -> None:
    if interaction.guild.id == 717029019270381578:
        chn = interaction.client.get_channel(1110998569466474716)
        embed1 = discord.Embed(title="Weekly Leaderboard", description="This leaderboard will be refreshed every week on Monday. The member(s) who attains the **top position in the text messages and/or voice leaderboard** will be awarded the esteemed <@&1111002520442110052> role throughout the entire week, which **includes the following rewards**:\n\n- Access to <#1141416403090546728>\n- Ability to pin any messages in chat channels\n\n> To access the current leaderboard, you can use the </top:1025501230044286983> command. Alternatively, use </me:1025501230044286978> to see your personal stats.\n\nHere is this week's leaderboard:", color=0x00ffaf)
        embed2 = discord.Embed(color=0x00ffaf)
        embed2.add_field(name="Top Message User", value=text_user.mention, inline=True)
        embed2.add_field(name="Top Voice User", value=voice_user.mention, inline=True)
        embed2.set_image(url=link)
        await chn.send(embeds=[embed1, embed2])
        for user in interaction.guild.get_role(1111002520442110052).members:
          await user.remove_roles(interaction.guild.get_role(1111002520442110052))
        await text_user.add_roles(interaction.guild.get_role(1111002520442110052))
        await voice_user.add_roles(interaction.guild.get_role(1111002520442110052))
        await interaction.response.send_message(content="The following embed is sent to <#1110998569466474716>:", embeds=[embed1, embed2])

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(TravelerOfTheWeek(bot))