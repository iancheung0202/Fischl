import discord
import datetime

from discord import app_commands
from discord.ext import commands

def extract_params(options):
    params = []
    for opt in options:
        if 'options' in opt:
            params.extend(extract_params(opt['options'])) # nested subcommands
        elif 'value' in opt:
            raw_value = opt['value']
            param_type = opt.get('type', 3)
            if param_type == 6:  # user
                formatted = f"<@{raw_value}>"
            elif param_type == 7:  # channel
                formatted = f"<#{raw_value}>"
            elif param_type == 8:  # role
                formatted = f"<@&{raw_value}>"
            elif param_type == 9:  # mentionable
                formatted = f"<@{raw_value}>"
            else:
                formatted = str(raw_value)
            params.append(f"{opt['name']}:{formatted}")

    return params

class OnCommand(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        print(interaction.data)  # Debugging prints as requested
        channel = self.client.get_channel(1030892842308091987)
        if isinstance(command, app_commands.Command):  # Slash command
            options = interaction.data.get('options', [])
            full_command = f"/{command.qualified_name}"
            params_list = extract_params(options)
            if params_list:
                full_command += " " + " ".join(params_list)
        else:  # Context menu command
            target_id = interaction.data.get('target_id', '')
            if command.type == discord.AppCommandType.user: 
                full_command = f"{command.qualified_name} (User: <@{target_id}>)"
            else:
                full_command = f"{command.qualified_name} (Message ID: {target_id})"

        full_command = full_command.replace('\n', ' ').replace('`', '\'')
        if len(full_command) > 1000:
            full_command = full_command[:1000] + "..."

        link = "https://fischl.app"

        embed = discord.Embed(
            description=(
                f"**Command:** `{full_command}`\n"
                f"**Used at:** <t:{int(interaction.created_at.timestamp())}:R>\n"
                f"**Status:** {'<:no:1036810470860013639> Failed' if interaction.command_failed else '<:yes:1036811164891480194> Success'}\n\n"
                f"**User Name:** {interaction.user.name}\n"
                f"**User ID:** `{interaction.user.id}`\n"
                f"**User Created:** <t:{int(interaction.user.created_at.timestamp())}:R>\n\n"
                f"**Guild Name:** [{interaction.guild.name}]({link})\n"
                f"**Guild ID:** `{interaction.guild.id}`\n"
                f"**Guild Member Count:** {interaction.guild.member_count}\n"
                f"**Guild Created:** <t:{int(interaction.guild.created_at.timestamp())}:R>\n\n"
                f"**Channel Name:** [#{interaction.channel.name}]({link})\n"
                f"**Channel ID:** `{interaction.channel.id}`\n"
                f"**Channel Mention:** {interaction.channel.mention}"
            ),
            colour=discord.Color.blurple(),
        )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(OnCommand(bot))