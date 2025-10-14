import discord
import datetime

from firebase_admin import db
from discord import app_commands
from discord.ext import commands


@app_commands.guild_only()
class Sticky(commands.GroupCog, name="sticky"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="enable", description="Enable sticky messages in a channel"
    )
    @app_commands.describe(
        message="The message content to be stuck",
        channel="The channel to enable sticky messages in (Current channel if not provided)",
    )
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sticky_enable(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None,
    ) -> None:
        if channel is None:
            channel = interaction.channel

        ref = db.reference("/Sticky Messages")
        stickies = ref.get()

        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                try:
                    oldMsg = await channel.fetch_message(val["Message ID"])
                    await oldMsg.delete()
                except Exception:
                    pass
                db.reference("/Sticky Messages").child(key).delete()
                break

        msg = await interaction.channel.send(message)

        data = {
            channel.id: {
                "Channel ID": channel.id,
                "Message ID": msg.id,
                "Message Content": message,
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        embed = discord.Embed(
            title="Sticky message enabled!",
            description=f"<:yes:1036811164891480194> This function allows a message to always stick to the bottom of the channel, which means no matter what, and how many messages are sent in the channel, this message is always going to be the last message in the channel. This is especially useful when you would like members to be notified what (not) to do in a channel instantly.\n\nIf you update the message content, you could use </sticky enable:1254927190915551254> again. If you no longer wish to use this function, use </sticky disable:1254927190915551254>.",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        with open("./commands/Sticky/enabledChannels.py", "r") as file:
            lines = file.readlines()
        for i, line in enumerate(lines):
            if line.startswith("enabledChannels ="):
                existing_ids = eval(line.split("=")[1].strip())
                if channel.id not in existing_ids:
                    existing_ids.append(channel.id)
                lines[i] = f"enabledChannels = {existing_ids}\n"
                break
        with open("./commands/Sticky/enabledChannels.py", "w") as file:
            file.writelines(lines)
    @sticky_enable.error
    async def sticky_enable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="disable", description="Disable sticky messages in a channel"
    )
    @app_commands.describe(
        channel="The channel to disable sticky messages in (Current channel if not provided)"
    )
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sticky_disable(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ) -> None:
        if channel is None:
            channel = interaction.channel

        ref = db.reference("/Sticky Messages")
        stickies = ref.get()

        found = False
        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                try:
                    oldMsg = await channel.fetch_message(val["Message ID"])
                    await oldMsg.delete()
                except Exception:
                    pass
                db.reference("/Sticky Messages").child(key).delete()
                found = True
                break

        if found:
            embed = discord.Embed(
                title="Sticky message disabled!",
                description=f"Sad to see you go. If you change your mind at anytime, you could use </sticky enable:1254927190915551254> to enable sticky messages again.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            with open("./commands/Sticky/enabledChannels.py", "r") as file:
                lines = file.readlines()
            for i, line in enumerate(lines):
                if line.startswith("enabledChannels ="):
                    existing_ids = eval(line.split("=")[1].strip())
                    existing_ids.remove(channel.id)
                    lines[i] = f"enabledChannels = {existing_ids}\n"
                    break
            with open("./commands/Sticky/enabledChannels.py", "w") as file:
                file.writelines(lines)
        else:
            embed = discord.Embed(
                title="Sticky message is not enabled!",
                description=f"What are you thinking? Sticky message is currently not even enabled in this channel. To enable the function, use </sticky enable:1254927190915551254>.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @sticky_disable.error
    async def sticky_disable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sticky(bot))
