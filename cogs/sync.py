"""Saves each slash command's id, so messages can mention commands."""

import json

import discord
from discord.ext import commands

GROUPED = (
    discord.AppCommandOptionType.subcommand,
    discord.AppCommandOptionType.subcommand_group,
)


def ids(listed):
    """Gives {name: id} for every command and each of its subcommands."""
    found = {}
    for command in listed:
        found[command.name] = str(command.id)
        for option in command.options:
            if option.type in GROUPED:
                found[f"{command.name} {option.name}"] = str(command.id)
    return found


class CommandSync(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            found = ids(await self.bot.tree.fetch_commands())
            with open("assets/commands.json", "w") as file:
                json.dump(found, file, indent=4)
            print("Successfully updated & synced assets/commands.json")
        except Exception as e:
            print(f"Failed to fetch application commands: {e}")


async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(CommandSync(bot))
