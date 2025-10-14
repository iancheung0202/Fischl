import discord

from discord import app_commands
from discord.ext import commands


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Check the bot's latency"
    )
    async def ping(
        self,
        interaction: discord.Interaction
    ) -> None:
        await interaction.response.send_message(f"Pong!")
        await interaction.edit_original_response(content=f"Pong! Latency: {round(self.bot.latency * 1000)}ms")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))