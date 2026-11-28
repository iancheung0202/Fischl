import datetime

import discord
from discord import app_commands
from discord.ext import commands


class Server(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="server", description="Shows the details of the current server"
    )
    @app_commands.guild_only()
    async def server(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        embed = discord.Embed(
            title=guild.name,
            description=guild.description,
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        fields = {
            "Server Name": guild.name,
            "Server ID": f"`{guild.id}`",
            "Members Count": guild.member_count,
            "Text Channels": len(guild.text_channels),
            "Voice channels": len(guild.voice_channels),
            "Created At": f"<t:{int(guild.created_at.timestamp())}:R>",
            "Owner": f"<@{guild.owner_id}>",
            "Emojis": f"{len(guild.emojis)}/{guild.emoji_limit}",
            "Stickers": f"{len(guild.stickers)}/{guild.sticker_limit}",
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Server(bot))
