import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

try:
    from assets.secret import DATABASE_PASSWORD, DATABASE_USER, NTFY_LINK
except ImportError:
    DATABASE_USER = ""
    DATABASE_PASSWORD = ""
    NTFY_LINK = ""


COMMAND_LOG_CHANNEL = 1030892842308091987
LINK = "https://fischl.app"
YES = "<:yes:1036811164891480194> Success"
NO = "<:no:1036810470860013639> Failed"
LOGGED_LENGTH = 1000
# How an option of each Discord type is written: user, channel, role, mentionable.
MENTIONS = {6: "<@{}>", 7: "<#{}>", 8: "<@&{}>", 9: "<@{}>"}


def extract_params(options):
    """Gives every option of a used command as name:value, reaching into subcommands."""
    params = []
    for opt in options:
        if "options" in opt:
            params.extend(extract_params(opt["options"]))
        elif "value" in opt:
            value = MENTIONS.get(opt.get("type", 3), "{}").format(opt["value"])
            params.append(f"{opt['name']}:{value}")
    return params


def command_text(interaction, command) -> str:
    """Gives a used command as one line, the way it was typed or picked from a menu."""
    if isinstance(command, app_commands.Command):
        params = extract_params(interaction.data.get("options", []))
        text = " ".join([f"/{command.qualified_name}", *params])
    else:
        target_id = interaction.data.get("target_id", "")
        kind = "User: <@{}>" if command.type == discord.AppCommandType.user else "Message ID: {}"  # fmt: skip
        text = f"{command.qualified_name} ({kind.format(target_id)})"
    text = text.replace("\n", " ").replace("`", "'")
    return text[:LOGGED_LENGTH] + "..." if len(text) > LOGGED_LENGTH else text


def where_text(interaction) -> str:
    """Gives the server and channel lines of a used command; a command used in DMs has neither."""
    guild, channel = interaction.guild, interaction.channel
    if guild is None:
        return f"**Guild Name:** Direct Message\n**Channel ID:** `{interaction.channel_id}`"
    return (
        f"**Guild Name:** [{guild.name}]({LINK})\n"
        f"**Guild ID:** `{guild.id}`\n"
        f"**Guild Member Count:** {guild.member_count}\n"
        f"**Guild Created:** <t:{int(guild.created_at.timestamp())}:R>\n\n"
        f"**Channel Name:** [#{channel.name}]({LINK})\n"
        f"**Channel ID:** `{channel.id}`\n"
        f"**Channel Mention:** {channel.mention}"
    )


class OnCommand(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self.client.tree.on_error = self.on_app_command_error

    async def on_app_command_error(self, interaction, error):
        """Prints a failed command and sends it to the owner's phone."""
        name = interaction.command.qualified_name if interaction.command else "Unknown"
        print(f"Error in app command: {error}")
        try:
            async with aiohttp.ClientSession() as session, session.post(
                NTFY_LINK,
                data=f"Command: {name}\nError: {str(error)[:500]}",
                auth=aiohttp.BasicAuth(DATABASE_USER, DATABASE_PASSWORD),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    print(f"Failed to send ntfy notification: {resp.status}")
        except Exception as e:
            print(f"Error sending ntfy notification: {e}")

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        """Posts every used command in the command log channel."""
        print(interaction.data)
        user = interaction.user
        embed = discord.Embed(
            description=(
                f"**Command:** `{command_text(interaction, command)}`\n"
                f"**Used at:** <t:{int(interaction.created_at.timestamp())}:R>\n"
                f"**Status:** {NO if interaction.command_failed else YES}\n\n"
                f"**User Name:** {user.name}\n"
                f"**User ID:** `{user.id}`\n"
                f"**User Created:** <t:{int(user.created_at.timestamp())}:R>\n\n"
                f"{where_text(interaction)}"
            ),
            colour=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        await self.client.get_channel(COMMAND_LOG_CHANNEL).send(embed=embed)


async def setup(bot):
    await bot.add_cog(OnCommand(bot))
