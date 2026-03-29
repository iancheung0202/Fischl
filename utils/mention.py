import discord

from discord.ext import commands

class SlashCommandMention:
    def __init__(self, bot_or_ctx, command_name: str, subcommand_name: str = None, subcommand_group: str = None):
        if isinstance(bot_or_ctx, commands.Bot) or isinstance(bot_or_ctx, commands.AutoShardedBot):
            self.bot = bot_or_ctx
        elif isinstance(bot_or_ctx, discord.Interaction):
            self.bot = bot_or_ctx.client
        else:
            raise TypeError(
                f"bot_or_ctx must be a Bot, AutoShardedBot, or Interaction instance, not {type(bot_or_ctx)}"
            )
        
        self.command_name = command_name
        self.subcommand_name = subcommand_name
        self.subcommand_group = subcommand_group
    
    def __str__(self) -> str:
        command = discord.utils.get(self.bot.tree.get_commands(), name=self.command_name)
        
        if command is None:
            raise ValueError(
                f"Slash command '{self.command_name}' not found. "
                f"Available commands: {[cmd.name for cmd in self.bot.tree.get_commands()]}"
            )
        
        if self.subcommand_name is None:
            return command.mention
        
        if self.subcommand_group:
            return f"</{self.command_name} {self.subcommand_group} {self.subcommand_name}:{command.id}>"
        else:
            return f"</{self.command_name} {self.subcommand_name}:{command.id}>"
    
    def __repr__(self) -> str:
        return f"SlashCommandMention('{self.command_name}', subcommand='{self.subcommand_name}')"