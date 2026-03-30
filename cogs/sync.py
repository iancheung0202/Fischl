import json
import discord

from discord.ext import commands

class CommandSync(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            app_cmds = await self.bot.tree.fetch_commands()
            
            command_map = {}
            for cmd in app_cmds:
                command_map[cmd.name] = str(cmd.id)
                for option in cmd.options:
                    if option.type in (discord.AppCommandOptionType.subcommand, discord.AppCommandOptionType.subcommand_group):
                        command_map[f"{cmd.name} {option.name}"] = str(cmd.id)

            with open("assets/commands.json", "w") as f:
                json.dump(command_map, f, indent=4)
                
            print("Successfully updated & synced assets/commands.json")
        except Exception as e:
            print(f"Failed to fetch application commands: {e}")

async def setup(bot: commands.AutoShardedBot):
    await bot.add_cog(CommandSync(bot))
