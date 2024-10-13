import discord, time, datetime
from discord import app_commands
from discord.ext import commands

class User(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "user",
    description = "Shows the details of a server member"
  )
  @app_commands.describe(
    user = "Specify any user",
  )
  async def user(
    self,
    interaction: discord.Interaction,
    user: discord.Member = None
  ) -> None:
    if user is None:
      user = interaction.user

    roles = ", ".join(
      [f"<@&{role.id}>" for role in sorted(user.roles, key=lambda role: role.position, reverse=True) if role.id != interaction.guild.default_role.id]
  ) if len(user.roles) > 1 else "None"

    embed = discord.Embed(colour=user.top_role.colour.value)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    if user.banner:
      embed.set_image(
        url=user.banner.url
      )
    embed.add_field(name="Username", value=user.name, inline=True)
    embed.add_field(name="Server Nick", value=user.nick if hasattr(user, "nick") else "None", inline=True)
    embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
    embed.add_field(name="Account created", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Joined this server", value=f"<t:{int(user.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Roles", value=roles, inline=False)
    await interaction.response.send_message(embed=embed)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(User(bot))