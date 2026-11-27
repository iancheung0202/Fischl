import datetime

import discord
from discord import app_commands
from discord.ext import commands

from commands.Sticky import stickyStore as store
from utils.commands import SlashCommand


async def refresh(bot):
    """Has the listener read the watched channels again; a failure is only printed."""
    try:
        await bot.get_cog("StickyHandler").load()
    except Exception as e:
        print(f"[Sticky] Failed to reload the watched channels: {e}")


async def unstick(bot, channel):
    """Forgets the channel's oldest stuck message and deletes it; False if none."""
    message_id = await store.take(bot.pool, channel.id)
    if message_id is None:
        return False
    try:
        old = await channel.fetch_message(message_id)
        await old.delete()
    except Exception:
        pass
    return True


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
        """Sticks a message to a channel, in place of its oldest one."""
        if channel is None:
            channel = interaction.channel

        await unstick(self.bot, channel)
        msg = await channel.send(message)
        await store.add(self.bot.pool, channel.id, msg.id, message)

        embed = discord.Embed(
            title="Sticky message enabled!",
            description=f"<:yes:1036811164891480194> This function allows a message to always stick to the bottom of the channel, which means no matter what, and how many messages are sent in the channel, this message is always going to be the last message in the channel. This is especially useful when you would like members to be notified what (not) to do in a channel instantly.\n\nIf you update the message content, you could use {SlashCommand('sticky enable')} again. If you no longer wish to use this function, use {SlashCommand('sticky disable')}.",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await store.enable(self.bot.pool, channel.id)
        await refresh(self.bot)

    @sticky_enable.error
    async def sticky_enable_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        """Shows the user why enabling failed."""
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
        """Removes the channel's oldest stuck message."""
        if channel is None:
            channel = interaction.channel

        if await unstick(self.bot, channel):
            embed = discord.Embed(
                title="Sticky message disabled!",
                description=f"Sad to see you go. If you change your mind at anytime, you could use {SlashCommand('sticky enable')} to enable sticky messages again.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await store.leave(self.bot.pool, channel.id)
            await refresh(self.bot)
        else:
            embed = discord.Embed(
                title="Sticky message is not enabled!",
                description=f"What are you thinking? Sticky message is currently not even enabled in this channel. To enable the function, use {SlashCommand('sticky enable')}.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @sticky_disable.error
    async def sticky_disable_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        """Shows the user why disabling failed."""
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sticky(bot))
