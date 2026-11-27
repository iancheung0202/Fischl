import datetime
import re

import discord
from discord import app_commands
from discord.ext import commands

from commands.Vanity import vanityStore as store

LINK_PATTERN = re.compile(r"^[\w.-]+\.[a-zA-Z]{2,}/.+$")


async def refresh(bot):
    """Has the listener read the settings again; a failure is only printed."""
    try:
        await bot.get_cog("OnStatusUpdate").load()
    except Exception as e:
        print(f"[Vanity] Failed to reload the vanity settings: {e}")


class embed_modal(discord.ui.Modal, title="Setup Vanity Roles Thank You Message"):
    msg = discord.ui.TextInput(
        label="Message Content",
        style=discord.TextStyle.paragraph,
        placeholder="Visit fischl.app/variables for all dynamic variables",
        max_length=2000,
        required=False,
    )
    embedtitle = discord.ui.TextInput(
        label="Embed Title",
        style=discord.TextStyle.paragraph,
        placeholder="Visit fischl.app/variables for all dynamic variables",
        max_length=256,
        required=False,
    )
    description = discord.ui.TextInput(
        label="Embed Description",
        style=discord.TextStyle.paragraph,
        placeholder="Visit fischl.app/variables for all dynamic variables",
        max_length=4000,
        required=False,
    )
    color = discord.ui.TextInput(
        label="Embed Color",
        style=discord.TextStyle.short,
        placeholder="Use hex code (e.g. #ff0000)",
        max_length=7,
        required=False,
    )
    image = discord.ui.TextInput(
        label="Embed Image",
        style=discord.TextStyle.paragraph,
        placeholder="Put a permanent image link",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Saves the message and confirms where it will be sent."""
        pool = interaction.client.pool
        try:
            await store.set_message(
                pool,
                interaction.guild.id,
                self.msg.value,
                self.embedtitle.value,
                self.description.value,
                self.color.value,
                self.image.value,
            )
        except Exception as e:
            print(
                f"[Vanity] Failed to save Vanity Thanks Message for guild {interaction.guild.id}: {e}"
            )
            await interaction.response.send_message(
                ":x: Something went wrong saving your thank-you message. Please try again.",
                ephemeral=True,
            )
            return

        thanks = await store.thanks(pool, interaction.guild.id)
        if thanks is None:
            thankyouChannel = "the configured channel"
        else:
            thankyouChannel = "DM" if thanks["dm"] else f'<#{thanks["channel_id"]}>'

        embed = discord.Embed(
            title="✅ Vanity Role Thank You Message Enabled!",
            description=f"Congratulations! The bot will now send a thank-you message in **{thankyouChannel}** whenever a user adds your server invite link to their status!\n\n*Note: The thank-you message will only be sent if the user has not added the invite link to their status in the past 24 hours.*",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.guild_only()
class VanityCommands(commands.GroupCog, name="vanity"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="migrate",
        description="Migrate vanity role configuration from Fischl Vanity to Fischl",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_migrate(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Starts watching a server that was set up with Fischl Vanity."""
        try:
            await store.enable(self.bot.pool, interaction.guild.id)
        except Exception as e:
            print(
                f"[MIGRATION ERROR] Failed to enable guild {interaction.guild.id}: {e}"
            )
            await interaction.response.send_message(
                ":x: Something went wrong migrating your server. Please try again or contact support.",
                ephemeral=True,
            )
            return
        await refresh(self.bot)

        embed = discord.Embed(
            title="Vanity roles migrated successfully!",
            description="Your vanity role configuration has been successfully migrated from Fischl Vanity to Fischl. You can now manage your vanity roles using the commands in Fischl.\n\n*Note: If you had thank-you messages enabled, your settings have also been migrated.*\n\nYou should now kick Fischl Vanity from your server to avoid duplicate functionality.",
            colour=0x00FFBB,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="enable", description="Enable vanity roles in the server"
    )
    @app_commands.describe(
        link="Your Discord server invite link (Format: discord.gg/traveler)",
        role="The role to give when a user put the link in their status",
        log_channel="The log channel for all actions related to vanity roles",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_enable(
        self,
        interaction: discord.Interaction,
        link: str,
        role: discord.Role,
        log_channel: discord.TextChannel,
    ) -> None:
        """Saves the link, role and log channel, then gives the role to who has the link."""
        if not LINK_PATTERN.match(link):
            await interaction.response.send_message(
                ":x: That doesn't look like a valid invite link. Expected format: `discord.gg/yourinvite`.",
                ephemeral=True,
            )
            return

        try:
            await store.set_roles(
                self.bot.pool, interaction.guild.id, link, role.id, log_channel.id
            )
        except Exception as e:
            print(
                f"[Vanity] Failed to save Vanity Roles entry for guild {interaction.guild.id}: {e}"
            )
            await interaction.response.send_message(
                ":x: Something went wrong enabling vanity roles. Please try again.",
                ephemeral=True,
            )
            return

        link_slug = link.split(".")[1]
        embed = discord.Embed(
            title="Vanity roles enabled!",
            description=f"Whenever a member includes `{link_slug}` in their **status**, they receive {role.mention} as long as it remains there.\n\n> **All vanity role actions are logged in {log_channel.mention} for transparency.**\n\n*Note: The bot does not remove roles from users who go offline but had the link in their status. It verifies eligibility when they come back online.*\n## Make sure to put my bot role above the vanity role!\nIf you wish to send an **automatic thank-you message** to members when they put your link on their status, use `/vanity thanks`.",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            await store.enable(self.bot.pool, interaction.guild.id)
        except Exception as e:
            print(
                f"[Vanity] Failed to enable guild {interaction.guild.id} after saving: {e}"
            )
        await refresh(self.bot)

        embed = discord.Embed(
            title="What is this?",
            description="This channel logs all role addition and removal as a result of activity changes of a member.",
            colour=discord.Color.blurple(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        try:
            await log_channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            print(
                f"[Vanity] Could not send intro message to log channel {log_channel.id} in guild {interaction.guild.id}: {e}"
            )

        await self.give_to_holders(interaction.guild, link_slug, role, log_channel)

    async def give_to_holders(self, guild, link_slug, role, log_channel):
        """Gives the role to the loaded members who already show the link."""
        for member in guild.members:
            if (link_slug in str(member.activity)) and role not in member.roles:
                try:
                    await member.add_roles(role)
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(
                        f"[Vanity] Failed to add role to {member} in guild {guild.id}: {e}"
                    )
                    continue
                embed = discord.Embed(
                    description=f":green_circle: {member.mention} has **added** vanity link to their status."
                )
                embed.set_footer(text="Role added")
                try:
                    await log_channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(
                        f"[Vanity] Failed to send role-added log for {member} in guild {guild.id}: {e}"
                    )

    @app_commands.command(
        name="disable", description="Disable vanity roles in the server"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Forgets the server's vanity settings and its thank-you."""
        await interaction.response.defer(ephemeral=True)

        try:
            found = await store.disable(self.bot.pool, interaction.guild.id)
        except Exception as e:
            print(
                f"[Vanity] Error while cleaning up DB entries for guild {interaction.guild.id} on disable: {e}"
            )
            found = False
        await refresh(self.bot)

        if found:
            embed = discord.Embed(
                title="Vanity roles disabled!",
                description="Sad to see you go. If you change your mind at anytime, you could use `/vanity enable` to enable vanity roles again. \n\n*If you had thank-you messages enabled, your settings have been deleted from our database.*",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)

        else:
            embed = discord.Embed(
                title="Vanity roles is not enabled!",
                description="What are you thinking? Vanity roles aren't currently enabled in this server! To enable the function, use `/vanity enable`.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="thanks", description="Toggle thank you channel/message for vanity roles"
    )
    @app_commands.describe(
        dm="Whether thank you message is sent DM (default: False)",
        channel="The thank you channel (leave blank if enabling DM message or disabling thank you message)",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_thanks(
        self,
        interaction: discord.Interaction,
        dm: bool = False,
        channel: discord.TextChannel = None,
    ) -> None:
        """Turns the thank-you off, or sets where it goes and asks for its message."""
        pool = self.bot.pool
        if not await store.has_roles(pool, interaction.guild.id):
            await interaction.response.send_message(
                ":x: Vanity roles is not currently enabled in this server!",
                ephemeral=True,
            )
            return

        try:
            was_on = await store.stop_thanks(pool, interaction.guild.id)
        except Exception as e:
            print(
                f"[Vanity] Error checking existing Vanity Thanks for guild {interaction.guild.id}: {e}"
            )
            was_on = False
        if was_on and channel is None and not dm:
            await interaction.response.send_message(
                ":white_check_mark: Thank you message **disabled**! *Vanity roles function is still enabled though!*",
                ephemeral=True,
            )
            return

        if channel is None and not dm:
            await interaction.response.send_message(
                ":x: Please either specify the channel *or* specify `dm` as `True` to enable thank you message.",
                ephemeral=True,
            )
            return

        if channel is not None and dm:
            await interaction.response.send_message(
                f":x: You specified both {channel.mention} and DM. \nWhere do you actually want to send the thank you message? Specify one only!",
                ephemeral=True,
            )
            return

        try:
            await store.set_thanks(
                pool, interaction.guild.id, channel.id if channel else None, dm
            )
        except Exception as e:
            print(
                f"[Vanity] Failed to save Vanity Thanks config for guild {interaction.guild.id}: {e}"
            )
            await interaction.response.send_message(
                ":x: Something went wrong saving that setting. Please try again.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(embed_modal())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VanityCommands(bot))
