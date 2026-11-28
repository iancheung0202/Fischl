import datetime

import discord
from discord.ext import commands

GUILD_LOG_CHANNEL = 1417408752876916829


def guild_embed(guild, title: str, color: discord.Color, total: int) -> discord.Embed:
    """Gives the log entry for a server the bot joined or left."""
    embed = discord.Embed(
        title=title,
        description=f"{guild.name} ({guild.id})",
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    if guild.member_count:
        embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
    if guild.owner:
        embed.add_field(
            name="Owner", value=f"{guild.owner.mention} ({guild.owner_id})", inline=True
        )
    embed.add_field(name="Total Bot Guilds", value=str(total), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


class OnGuild(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    async def log(self, guild, title: str, color: discord.Color) -> None:
        """Posts a joined or left server in the log channel, if the bot can see it."""
        channel = self.client.get_channel(GUILD_LOG_CHANNEL)
        if channel:
            total = len(self.client.guilds)
            await channel.send(embed=guild_embed(guild, title, color, total))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Logs a server the bot was added to."""
        await self.log(guild, "Guild Joined", discord.Color.green())

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Logs a server the bot was removed from."""
        await self.log(guild, "Guild Left", discord.Color.red())


async def setup(bot):
    await bot.add_cog(OnGuild(bot))
