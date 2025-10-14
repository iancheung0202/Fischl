import discord
import datetime

from discord.ext import commands

class OnGuild(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        channel = self.client.get_channel(1417408752876916829)
        embed = discord.Embed(
            title="Guild Joined",
            description=f"{guild.name} ({guild.id})",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if guild.member_count:
            embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
        if guild.owner:
            embed.add_field(name="Owner", value=f"{guild.owner.mention} ({guild.owner_id})", inline=True)
        embed.add_field(name="Total Bot Guilds", value=str(len(self.client.guilds)), inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        channel = self.client.get_channel(1417408752876916829)
        embed = discord.Embed(
            title="Guild Left",
            description=f"{guild.name} ({guild.id})",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if guild.member_count:
            embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
        if guild.owner:
            embed.add_field(name="Owner", value=f"{guild.owner.mention} ({guild.owner_id})", inline=True)
        embed.add_field(name="Total Bot Guilds", value=str(len(self.client.guilds)), inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(OnGuild(bot))