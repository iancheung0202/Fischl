import discord
import datetime

from discord import app_commands
from discord.ext import commands


class Server(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
      self.bot = bot

    @app_commands.command(
        name="server",
        description="Shows the details of the current server"
    )
    @app_commands.guild_only()
    async def server(
        self,
        interaction: discord.Interaction
    ) -> None:
      embed = discord.Embed(title=interaction.guild.name, description=interaction.guild.description, color=discord.Color.blurple())

      if interaction.guild.icon:
          embed.set_thumbnail(url=interaction.guild.icon.url)

      if interaction.guild.banner:
          embed.set_image(url=interaction.guild.banner.url)

      embed.add_field(
          name="Server Name", 
          value=interaction.guild.name, 
          inline=True
      )

      embed.add_field(
          name="Server ID", 
          value=f"`{interaction.guild.id}`", 
          inline=True
      )

      embed.add_field(
          name="Members Count", 
          value=interaction.guild.member_count, 
          inline=True
      )

      embed.add_field(
          name="Text Channels", 
          value=len(interaction.guild.text_channels), 
          inline=True
      )

      embed.add_field(
          name="Voice channels", 
          value=len(interaction.guild.voice_channels), 
          inline=True
      )

      embed.add_field(
          name="Created At", 
          value=f"<t:{int(interaction.guild.created_at.timestamp())}:R>", 
          inline=True
      )

      embed.add_field(
          name="Owner", 
          value=f"<@{interaction.guild.owner_id}>", 
          inline=True
      )

      embed.add_field(
          name="Emojis", 
          value=f"{len(interaction.guild.emojis)}/{interaction.guild.emoji_limit}", 
          inline=True
      )

      embed.add_field(
          name="Stickers", 
          value=f"{len(interaction.guild.stickers)}/{interaction.guild.sticker_limit}", 
          inline=True
      )

      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.response.send_message(embed=embed)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Server(bot))