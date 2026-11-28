"""Booster roles: the thank-you message, custom roles and auto responses of server boosters."""

import asyncio
import contextlib
import io
import logging
import re
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, Modal, TextInput, View
from firebase_admin import db

YES = "<:yes:1036811164891480194>"
NO = "<:no:1036810470860013639>"
ROOT = "Booster Role"
LOADING = "<a:loading:1026905298088243240>"
# Fischl's channel for files that need a lasting link; other bots cannot see it.
MEDIA_CHANNEL = 1026968305208131645
# This server lets every member use the booster commands, with its own base role.
OPEN_SERVER = 783528750474199041
OPEN_SERVER_BASE_ROLE = 1377445878876471447
# Discord's answers for a member who left and for a deleted account.
GONE_CODES = (10007, 10013)
CACHE_SECONDS = 300
PANEL_TIMEOUT = 180
CONFIRM_TIMEOUT = 60
SWEEP_MINUTES = 60
SWEEP_DELAY = 300
MEDIA_HEIGHT = 150
RESPONSE_LENGTH = 300
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/114.0.0.0 Safari/537.36"
)
VARIABLES = "Use variables: {mention}, {server}, {user}, {boost}"
NOT_ENABLED = f"{NO} Booster system is not enabled on this server!"
NOT_BOOSTING = f"{NO} You must be an active server booster to use this command!"
NO_LOG = f"{NO} Log channel not configured! Contact server staff."
LOG_GONE = f"{NO} Log channel not found! Contact server staff."
EXPIRED_LINK = (
    f"{NO} Your linked attachment(s) have expired or are invalid.\n"
    "-# If you're using a Discord file link, note that Discord attachments link expire"
    " after 24 hours.\n"
    "-# Please re-upload the file elsewhere and provide the updated link within that"
    " timeframe."
)

log = logging.getLogger(__name__)
# Every server's settings and when they were read; messages that mention someone ask for them.
cache = {"at": None, "servers": {}, "writes": 0}
refreshing = asyncio.Lock()
# Request messages a staff member is answering right now, against a double press.
handling = set()


async def read(path: str = ""):
    """Gives what Firebase holds under the booster settings, without pausing the bot."""
    return await asyncio.to_thread(db.reference(f"{ROOT}/{path}".rstrip("/")).get)


async def write(path: str, value) -> None:
    """Saves a value under the booster settings and forgets the kept copy."""
    await asyncio.to_thread(db.reference(f"{ROOT}/{path}").set, value)
    forget()


async def merge(path: str, values: dict) -> None:
    """Saves some keys under the booster settings, leaving the others."""
    await asyncio.to_thread(db.reference(f"{ROOT}/{path}").update, values)
    forget()


async def remove(path: str) -> None:
    """Deletes a path under the booster settings and forgets the kept copy."""
    await asyncio.to_thread(db.reference(f"{ROOT}/{path}").delete)
    forget()


def forget() -> None:
    """Drops the kept settings, also for a read that is under way."""
    cache["at"] = None
    cache["writes"] += 1


async def servers(fresh: bool = False) -> dict:
    """Gives every server's settings, read at most every few minutes."""
    async with refreshing:
        stale = cache["at"] is None or time.monotonic() - cache["at"] > CACHE_SECONDS
        if fresh or stale:
            writes = cache["writes"]
            cache["servers"] = await read() or {}
            cache["at"] = time.monotonic() if writes == cache["writes"] else None
    return cache["servers"]


def parse_color(text: str) -> discord.Color:
    """Gives the colour of a 3 or 6 digit hex code, or pink."""
    code = (text or "").lstrip("#").lower()
    if len(code) in (3, 6) and all(digit in "0123456789abcdef" for digit in code):
        if len(code) == 3:
            code = "".join(digit * 2 for digit in code)
        return discord.Color(int(code, 16))
    return discord.Color.pink()


def script(string: str, user, guild) -> str:
    """Fills the variables of a thank-you text."""
    return (
        string.replace("{mention}", user.mention)
        .replace("{server}", guild.name)
        .replace("{user}", user.name)
        .replace("{boost}", str(guild.premium_subscription_count))
    )


def resized(content: bytes, max_height: int) -> io.BytesIO:
    """Gives an image or GIF shrunk to a height, as a PNG or GIF."""
    from PIL import Image, ImageSequence

    def shrunk(picture):
        width, height = picture.size
        new_height = min(height, max_height)
        return picture.resize(
            (int((new_height / height) * width), new_height), Image.LANCZOS
        )

    out = io.BytesIO()
    with Image.open(io.BytesIO(content)) as image:
        if image.format == "GIF":
            frames = [frame.copy() for frame in ImageSequence.Iterator(image)]
            durations = [frame.info.get("duration", 100) for frame in frames]
            frames = [shrunk(frame) for frame in frames]
            frames[0].save(
                out,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
            )
        else:
            shrunk(image).save(out, format="PNG")
    out.seek(0)
    return out


async def rehosted(client, text: str):
    """Gives a response with its image links moved to lasting ones, or None when a link is dead."""
    channel = client.get_channel(MEDIA_CHANNEL)
    async with aiohttp.ClientSession(headers={"User-Agent": BROWSER}) as session:
        for url in re.findall(r"https?://[^\s]+", text):
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    kind = response.headers.get("Content-Type", "")
                    if not kind.startswith("image/") or not channel:
                        continue
                    data = await response.read()
                media = await asyncio.to_thread(resized, data, MEDIA_HEIGHT)
                name = "response_media.gif" if "gif" in kind else "response_media.png"
                posted = await channel.send(file=discord.File(media, filename=name))
                text = text.replace(url, posted.attachments[0].url)
            except Exception:
                continue
    return text


async def member_of(guild, user_id: int):
    """Gives a member of a server, or None when they left."""
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound as error:
        if error.code not in GONE_CODES:
            raise
    return None


async def tell(member, text: str) -> None:
    """Sends a member a DM, when they take DMs."""
    with contextlib.suppress(discord.HTTPException):
        await member.send(text)


async def log_action(guild, config: dict, content: str, title: str) -> None:
    """Posts an entry in a server's booster log channel."""
    channel = guild.get_channel((config or {}).get("log") or 0)
    if channel:
        embed = discord.Embed(
            title=title, description=content, color=discord.Color.blue()
        )
        with contextlib.suppress(discord.HTTPException):
            await channel.send(embed=embed)


def request_of(interaction: discord.Interaction):
    """Gives the request embed under a pressed button, with its server and member IDs."""
    embed = interaction.message.embeds[0]
    server, member = embed.footer.text.split("|")
    return embed, int(server.split(":")[1]), int(member.split(":")[1])


def field(embed: discord.Embed, name: str):
    """Gives the value of an embed's field, or None."""
    return next((item.value for item in embed.fields if item.name == name), None)


async def claim(interaction: discord.Interaction) -> bool:
    """Marks a request as being answered; False when someone already is."""
    if interaction.message.id in handling:
        await interaction.response.send_message(
            "This request is already being handled.", ephemeral=True
        )
        return False
    handling.add(interaction.message.id)
    try:
        await interaction.response.defer(ephemeral=True)
    except BaseException:
        handling.discard(interaction.message.id)
        raise
    return True


async def close_request(interaction, embed, title: str, color) -> None:
    """Marks a request message as answered and removes its buttons."""
    embed.title, embed.color = title, color
    await interaction.message.edit(embed=embed, view=None)


def icon_fields(embed: discord.Embed, icon_url) -> None:
    """Adds a role request's icon to an embed."""
    if icon_url:
        embed.add_field(name="Icon", value=f"[View Icon]({icon_url})", inline=False)
        embed.set_thumbnail(url=icon_url)
    else:
        embed.add_field(name="Icon", value="None", inline=False)


def is_booster(member) -> bool:
    """Tells whether a member may use the booster commands in their server."""
    return bool(member.premium_since) or member.guild.id == OPEN_SERVER


class ConfirmDisableView(View):
    """Asks before the booster system of a server is removed."""

    def __init__(self):
        super().__init__(timeout=CONFIRM_TIMEOUT)
        self.confirmed = False

    @discord.ui.button(
        label="Confirm Disable", style=discord.ButtonStyle.danger, emoji="⚠️"
    )
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content="System disable cancelled.", embed=None, view=None
        )
        self.stop()


class BoosterEmbedModal(Modal, title="Booster Embed Setup"):
    """Asks for the thank-you message of a server."""

    msg = TextInput(
        label="Message Content",
        style=discord.TextStyle.paragraph,
        placeholder=VARIABLES,
        required=False,
    )
    embed_title = TextInput(
        label="Embed Title", max_length=256, required=False, placeholder=VARIABLES
    )
    embed_desc = TextInput(
        label="Embed Description",
        style=discord.TextStyle.paragraph,
        placeholder=VARIABLES,
        required=False,
    )
    color = TextInput(
        label="Embed Color",
        placeholder="Enter a hex color code (e.g. #FF0000)",
        max_length=7,
        required=False,
    )
    image = TextInput(label="Image URL", required=False)

    def __init__(self, current=None):
        super().__init__()
        current = current or {}
        self.msg.default = current.get("message", "")
        self.embed_title.default = current.get("title", "")
        self.embed_desc.default = current.get("description", "")
        self.color.default = current.get("color", "")
        self.image.default = current.get("image", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await write(
            f"{interaction.guild.id}/embed",
            {
                "message": self.msg.value,
                "title": self.embed_title.value,
                "description": self.embed_desc.value,
                "color": self.color.value,
                "image": self.image.value,
            },
        )
        await interaction.followup.send(
            f"{YES} Booster roles system configured! **Make sure my bot role is above"
            " the base booster role!**",
            ephemeral=True,
        )


class AutoResponseSetupModal(Modal, title="Auto Response Setup"):
    """Asks a booster for their auto response."""

    response = TextInput(
        label="Response Content",
        style=discord.TextStyle.paragraph,
        placeholder="Enter text, image URL, or GIF URL",
        required=True,
        max_length=RESPONSE_LENGTH,
    )

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.panel.submit(interaction, self.response.value)


class AutoResponseApprovalView(View):
    """The staff buttons under an auto response request."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.green,
        custom_id="approveAutoResponse",
    )
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not await claim(interaction):
            return
        try:
            embed, guild_id, user_id = request_of(interaction)
            if not await read(f"{guild_id}/log"):
                return await interaction.followup.send(NOT_ENABLED, ephemeral=True)
            await remove(f"{guild_id}/pending_autoresponses/{user_id}")
            await write(
                f"{guild_id}/autoresponses/{user_id}",
                {"response": field(embed, "Response")},
            )
            await close_request(
                interaction,
                embed,
                f"{YES} Auto Response Approved",
                discord.Color.green(),
            )
            guild = interaction.client.get_guild(guild_id)
            booster = guild and await member_of(guild, user_id)
            if booster:
                await tell(
                    booster,
                    f"{YES} Your auto response in **{guild.name}** has been approved!\n"
                    "You may view or reset it using `/boosterrole autoresponse`.",
                )
            await interaction.followup.send("Approved!", ephemeral=True)
        finally:
            handling.discard(interaction.message.id)

    @discord.ui.button(
        label="Reject", style=discord.ButtonStyle.red, custom_id="rejectAutoResponse"
    )
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not await claim(interaction):
            return
        try:
            embed, guild_id, user_id = request_of(interaction)
            await remove(f"{guild_id}/pending_autoresponses/{user_id}")
            await close_request(
                interaction, embed, f"{NO} Auto Response Rejected", discord.Color.red()
            )
            guild = interaction.client.get_guild(guild_id)
            booster = guild and await member_of(guild, user_id)
            if booster:
                await tell(
                    booster,
                    f"{NO} Your auto response in **{guild.name}** was rejected by"
                    " staff.\nYou may submit a new one using `/boosterrole"
                    " autoresponse`.",
                )
            await interaction.followup.send("Rejected!", ephemeral=True)
        finally:
            handling.discard(interaction.message.id)


class AutoResponsePanelView(View):
    """A booster's own auto response: its state, with Setup and Reset."""

    def __init__(self, user_id: int, status: str, config=None):
        super().__init__(timeout=PANEL_TIMEOUT)
        self.user_id = user_id
        self.status = status  # "not_set", "pending" or "active"
        self.config = config or {}
        self.message = None
        self.update_button_states()

    def update_button_states(self) -> None:
        """Enables Setup with nothing set and Reset with an active response."""
        self.setup_button.disabled = self.status != "not_set"
        self.reset_button.disabled = self.status != "active"

    def create_embed(self) -> discord.Embed:
        """Gives the panel for the current state."""
        embed = discord.Embed(
            title="🎭 Auto Response Configuration",
            description=(
                "Set up a custom response that triggers when members mention you "
                "or use a specific phrase.\n\n"
                "**How it works:**\n"
                "1. When someone mentions you in a message\n"
                "2. OR when someone uses your custom trigger phrase\n"
                "3. AND you're still boosting the server\n"
                "4. THEN the bot will send your configured response\n\n"
                "You can use text, image URLs, or GIF URLs in your response!\n\n"
                "**All responses require staff approval**"
            ),
            color=discord.Color.blue(),
        )
        status = {
            "not_set": f"{NO} Not set up",
            "pending": "🟡 Pending approval",
            "active": f"{YES} Active",
        }[self.status]
        embed.add_field(name="Current Status", value=status, inline=False)
        if self.status != "not_set":
            embed.add_field(
                name="Response Preview", value=self.config["response"], inline=False
            )
        if self.status == "pending":
            embed.add_field(
                name="Note",
                value=(
                    "Your response is pending staff approval. You cannot edit it until"
                    " it's approved or rejected."
                ),
                inline=False,
            )
        embed.set_footer(text="This panel will expire in 3 minutes")
        return embed

    async def redraw(self, status: str, config: dict) -> None:
        """Shows the panel in a new state."""
        self.status, self.config = status, config
        self.update_button_states()
        await self.message.edit(embed=self.create_embed(), view=self)

    async def submit(self, interaction: discord.Interaction, text: str) -> None:
        """Sends a booster's response to the staff for approval."""
        response = await rehosted(interaction.client, text)
        if response is None:
            return await interaction.followup.send(EXPIRED_LINK, ephemeral=True)
        guild, booster = interaction.guild, interaction.user
        config = await read(str(guild.id)) or {}
        if not config.get("log"):
            return await interaction.followup.send(NO_LOG, ephemeral=True)
        log_channel = guild.get_channel(config["log"])
        if not log_channel:
            return await interaction.followup.send(LOG_GONE, ephemeral=True)
        pending = {"response": response}
        await write(f"{guild.id}/pending_autoresponses/{booster.id}", pending)
        await self.redraw("pending", pending)
        embed = discord.Embed(
            title="⏳ Auto Response Pending Approval",
            description=f"Booster: {booster.mention} (`{booster.id}`)",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Trigger Phrase", value="Mention Only", inline=False)
        embed.add_field(name="Response", value=response, inline=False)
        embed.set_footer(text=f"Guild ID: {guild.id} | User ID: {booster.id}")
        await log_channel.send(embed=embed, view=AutoResponseApprovalView())
        await interaction.followup.send(
            f"{YES} Auto response submitted for staff approval!", ephemeral=True
        )

    @discord.ui.button(label="Setup", style=discord.ButtonStyle.green)
    async def setup_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AutoResponseSetupModal(self))

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red)
    async def reset_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        await remove(f"{guild_id}/autoresponses/{self.user_id}")
        await remove(f"{guild_id}/pending_autoresponses/{self.user_id}")
        await self.redraw("not_set", {})
        await interaction.followup.send(
            f"{YES} Auto response configuration reset!", ephemeral=True
        )

    async def on_timeout(self) -> None:
        with contextlib.suppress(discord.HTTPException, AttributeError):
            await self.message.delete()


def pending_embed(pending: dict) -> discord.Embed:
    """Gives the notice for a booster whose role request is still waiting."""
    embed = discord.Embed(
        title="⏳ Pending Role Request",
        description=(
            "You already have a pending role request. Please wait for staff approval."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(name="Name", value=pending.get("name", "Not set"), inline=False)
    embed.add_field(name="Color", value=pending.get("color", "Not set"), inline=False)
    icon_fields(embed, pending.get("icon_url"))
    return embed


async def set_icon(role: discord.Role, icon_url: str) -> None:
    """Gives a role its icon from a link, when that works."""
    with contextlib.suppress(Exception):
        async with aiohttp.ClientSession() as session, session.get(icon_url) as resp:
            if resp.status == 200:
                await role.edit(display_icon=await resp.read())


class RoleApprovalView(View):
    """The staff buttons under a custom role request."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve", style=discord.ButtonStyle.green, custom_id="approveRole"
    )
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not await claim(interaction):
            return
        try:
            await self.create_role(interaction)
        finally:
            handling.discard(interaction.message.id)

    async def create_role(self, interaction: discord.Interaction):
        """Creates the requested role above the base role and gives it to the booster."""
        embed, guild_id, user_id = request_of(interaction)
        name, color = field(embed, "Name"), field(embed, "Color")
        icon = re.search(r"\[View Icon\]\((.*?)\)", field(embed, "Icon") or "")

        def answer(text):
            return interaction.followup.send(text, ephemeral=True)

        guild = interaction.client.get_guild(guild_id)
        if not guild:
            return await answer("Guild not found")
        booster = await member_of(guild, user_id)
        if not booster:
            return await answer("User not found")
        config = await read(str(guild_id)) or {}
        if not config.get("base_role"):
            return await answer("System not configured")
        base_role = guild.get_role(config["base_role"])
        if not base_role:
            return await answer("Base role not found")
        try:
            role = await guild.create_role(name=name, color=parse_color(color))
            if icon:
                await set_icon(role, icon.group(1))
            await guild.edit_role_positions(positions={role: base_role.position + 1})
            await booster.add_roles(role)
            await merge(f"{guild_id}/roles", {str(user_id): role.id})
            await remove(f"{guild_id}/pending_roles/{user_id}")
            await close_request(
                interaction,
                embed,
                f"{YES} Role Request Approved",
                discord.Color.green(),
            )
            await tell(
                booster,
                f"{YES} Your custom booster role in **{guild.name}** has been"
                f" approved!\n- **Name:** {name}\n- **Color:** `{color}`",
            )
            await answer("Role created successfully!")
        except Exception as error:
            await answer(f"Error creating role: {error}")

    @discord.ui.button(
        label="Reject", style=discord.ButtonStyle.red, custom_id="rejectRole"
    )
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not await claim(interaction):
            return
        try:
            embed, guild_id, user_id = request_of(interaction)
            await remove(f"{guild_id}/pending_roles/{user_id}")
            await close_request(
                interaction, embed, f"{NO} Role Request Rejected", discord.Color.red()
            )
            guild = interaction.client.get_guild(guild_id)
            booster = guild and await member_of(guild, user_id)
            if booster:
                await tell(
                    booster,
                    f"{NO} Your custom booster role request in **{guild.name}** was"
                    " rejected by staff.\nYou may submit a new request using"
                    " `/boosterrole create`.",
                )
            await interaction.followup.send("Request rejected!", ephemeral=True)
        finally:
            handling.discard(interaction.message.id)


class SettingsPanelView(View):
    """The buttons under `/boosterrole settings`."""

    def __init__(self, guild_id: int):
        super().__init__(timeout=PANEL_TIMEOUT)
        self.guild_id = guild_id

    @discord.ui.button(label="Edit Greeting", style=discord.ButtonStyle.blurple)
    async def edit_greeting(self, interaction: discord.Interaction, button: Button):
        current = await read(f"{self.guild_id}/embed")
        await interaction.response.send_modal(BoosterEmbedModal(current))

    @discord.ui.button(label="View Custom Roles", style=discord.ButtonStyle.grey)
    async def view_custom_roles(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        config = await read(str(self.guild_id))
        if not config:
            return await interaction.followup.send(NOT_ENABLED, ephemeral=True)
        roles = config.get("roles")
        if not roles:
            return await interaction.followup.send(
                f"{NO} No booster roles found.", ephemeral=True
            )
        listed = "\n".join(f"<@{user}> - <@&{role}>" for user, role in roles.items())
        await interaction.followup.send(
            embed=discord.Embed(title="Booster Roles", description=listed),
            ephemeral=True,
        )

    @discord.ui.button(label="View Autoresponses", style=discord.ButtonStyle.grey)
    async def view_autoresponses(
        self, interaction: discord.Interaction, button: Button
    ):
        await interaction.response.defer(ephemeral=True)
        responses = await read(f"{self.guild_id}/autoresponses")
        if not responses:
            return await interaction.followup.send(
                f"{NO} No autoresponses configured", ephemeral=True
            )
        embed = discord.Embed(title="Active Autoresponses", color=discord.Color.blue())
        for user_id, config in responses.items():
            member = None
            with contextlib.suppress(discord.HTTPException):
                member = await member_of(interaction.guild, int(user_id))
            name = member.display_name if member else f"Unknown ({user_id})"
            embed.add_field(
                name=f"{name} (`{user_id}`)",
                value=f"**Trigger:** Mention Only\n**Response:** {config['response']}",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def report(interaction: discord.Interaction, error: Exception) -> None:
    """Shows a command's error to the member who ran it."""
    text = f"```{error}```"
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


class BoosterRole(commands.GroupCog, name="boosterrole"):
    """The /boosterrole commands, the thank-you message and the hourly cleanup."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.unloading = False

    async def cog_load(self):
        self.cleanup_loop.start()

    def cog_unload(self):
        self.unloading = True
        self.cleanup_loop.cancel()

    async def cog_app_command_error(self, interaction, error) -> None:
        await report(interaction, error)

    @tasks.loop(minutes=SWEEP_MINUTES)
    async def cleanup_loop(self):
        await self.cleanup_all()

    @cleanup_loop.before_loop
    async def before_cleanup_loop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(SWEEP_DELAY)

    async def cleanup_all(self) -> None:
        """Cleans up the custom roles of every server this bot is in."""
        if self.unloading or self.bot.is_closed():
            return
        for guild_id, config in (await servers(fresh=True)).items():
            guild = self.bot.get_guild(int(guild_id))
            if guild and "base_role" in config:
                try:
                    await self.sweep(guild, config)
                except Exception:
                    log.exception("Booster cleanup failed in server %s", guild_id)

    async def sweep(self, guild: discord.Guild, config: dict) -> None:
        """Deletes the roles of members who left or stopped boosting, and gives back missing ones."""
        if not guild.roles:
            return
        for user_id, role_id in list(config.get("roles", {}).items()):
            try:
                await self.check_role(guild, config, user_id, role_id)
            except Exception as error:
                await log_action(
                    guild,
                    config,
                    f"⛔ Error processing cleanup for user ID `{user_id}`: {error}",
                    "Cleanup Error",
                )
        for user_id in list(config.get("pending_roles", {})):
            with contextlib.suppress(discord.HTTPException, ValueError):
                member = await member_of(guild, int(user_id))
                if not member or not is_booster(member):
                    await remove(f"{guild.id}/pending_roles/{user_id}")

    async def check_role(self, guild, config: dict, user_id: str, role_id) -> None:
        """Cleans up one booster's custom role."""
        mention = f"<@{user_id}> (ID: `{user_id}`)"
        role = guild.get_role(role_id)
        if not role:
            if await read(f"{guild.id}/roles/{user_id}") != role_id:
                return
            await remove(f"{guild.id}/roles/{user_id}")
            return await log_action(
                guild,
                config,
                f"🧹 Removed database entry for user {mention} - Role not found",
                "Database Cleanup",
            )
        named = f"role `{role.name}` (ID: `{role.id}`)"
        try:
            booster = await member_of(guild, int(user_id))
        except discord.HTTPException:
            return
        if booster and is_booster(booster):
            if role not in booster.roles:
                await self.give_back(guild, config, booster, role, named)
            return
        if booster:
            whom, why = (
                f"{booster.mention} (ID: `{booster.id}`)",
                " - No longer boosting",
            )
            failed = whom
        else:
            whom, why = f"user who left the server (ID: `{user_id}`)", ""
            failed = f"member ID `{user_id}`"
        try:
            await role.delete()
            entry = (f"🗑️ Deleted {named} for {whom}{why}", "Expired Booster Cleanup")
        except discord.Forbidden:
            entry = (
                f"⚠️ Failed to delete {named} for {failed}: Insufficient permissions",
                "Cleanup Error",
            )
        except discord.HTTPException as error:
            entry = (
                f"⚠️ Failed to delete {named} for {failed}: {error}",
                "Cleanup Error",
            )
        await log_action(guild, config, *entry)
        await remove(f"{guild.id}/roles/{user_id}")
        for path, what, title in (
            ("autoresponses", "autoresponse", "Auto Response Cleanup"),
            (
                "pending_autoresponses",
                "pending autoresponse",
                "Pending Auto Response Cleanup",
            ),
        ):
            if user_id in config.get(path, {}):
                await remove(f"{guild.id}/{path}/{user_id}")
                await log_action(
                    guild, config, f"🧹 Removed {what} for user {mention}", title
                )

    async def give_back(self, guild, config, booster, role, named: str) -> None:
        """Gives a booster their custom role again when it went missing."""
        whom = f"{booster.mention} (ID: `{booster.id}`)"
        try:
            await booster.add_roles(role)
            entry = (
                f"🔧 Re-assigned {named} to {whom} - Role was missing",
                "Role Assignment Fix",
            )
        except discord.Forbidden:
            entry = (
                f"⚠️ Failed to re-assign {named} to {whom}: Insufficient permissions",
                "Cleanup Error",
            )
        except discord.HTTPException as error:
            entry = (
                f"⚠️ Failed to re-assign {named} to {whom}: {error}",
                "Cleanup Error",
            )
        await log_action(guild, config, *entry)

    async def send_booster_embed(self, guild, user, config: dict) -> None:
        """Posts a server's thank-you message for a new boost."""
        if not config.get("channel") or not config.get("embed"):
            return
        channel = guild.get_channel(config["channel"])
        if not channel:
            return
        data = config["embed"]
        embed = discord.Embed(
            title=script(data.get("title", ""), user, guild),
            description=script(data.get("description", ""), user, guild),
            color=parse_color(data.get("color", "#FF73FA")),
        )
        if data.get("image"):
            embed.set_image(url=data["image"])
        content = script(data.get("message", ""), user, guild)
        await channel.send(content or None, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Thanks a new booster, and answers a mention of a booster with their auto response."""
        if message.guild is None or message.author.bot:
            return
        boost = message.type == discord.MessageType.premium_guild_subscription
        if not boost and not ("<@" in message.content and ">" in message.content):
            return
        config = (await servers()).get(str(message.guild.id))
        if not config:
            return
        if boost:
            if config.get("system_channel") == message.channel.id and isinstance(
                message.author, discord.Member
            ):
                await self.send_booster_embed(message.guild, message.author, config)
            return
        for user_id, saved in config.get("autoresponses", {}).items():
            if not re.search(f"<@!?{user_id}>", message.content):
                continue
            with contextlib.suppress(Exception):
                booster = await member_of(message.guild, int(user_id))
                if booster and booster != message.author and is_booster(booster):
                    await message.channel.send(saved["response"])

    @app_commands.command(
        name="autoresponse", description="Manage your auto response configuration"
    )
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def autoresponse(self, interaction: discord.Interaction):
        if not is_booster(interaction.user):
            return await interaction.response.send_message(NOT_BOOSTING, ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        config = await read(str(interaction.guild.id))
        if not config:
            return await interaction.followup.send(NOT_ENABLED, ephemeral=True)
        user = str(interaction.user.id)
        active = config.get("autoresponses", {}).get(user)
        pending = config.get("pending_autoresponses", {}).get(user)
        if active:
            view = AutoResponsePanelView(interaction.user.id, "active", active)
        elif pending:
            view = AutoResponsePanelView(interaction.user.id, "pending", pending)
        else:
            view = AutoResponsePanelView(interaction.user.id, "not_set")
        view.message = await interaction.followup.send(
            embed=view.create_embed(), view=view, ephemeral=True, wait=True
        )

    @app_commands.command(
        name="create", description="Create or update your booster role"
    )
    @app_commands.describe(
        color="Enter a hex color code for your role (e.g. #FF0000)",
        name="Enter your custom role name",
        icon_attachment="Attach a role icon if the server supports it (Optional)",
        user="The booster to create role for (Admins only)",
    )
    @app_commands.checks.bot_has_permissions(manage_roles=True, manage_guild=True)
    async def create(
        self,
        interaction: discord.Interaction,
        color: str,
        name: str,
        icon_attachment: discord.Attachment = None,
        user: discord.Member = None,
    ):
        guild = interaction.guild
        if (
            not interaction.user.guild_permissions.administrator
            and user is not None
            and user != interaction.user
        ):
            return await interaction.response.send_message(
                "You cannot create booster roles for others without Administrator"
                " permissions."
            )
        user = user or interaction.user
        await interaction.response.defer(ephemeral=True)

        def answer(text):
            return interaction.followup.send(text, ephemeral=True)

        config = await read(str(guild.id))
        if not config:
            return await answer(NOT_ENABLED)
        if "base_role" not in config:
            return await answer(f"{NO} Booster system not configured in this server!")
        if not is_booster(user):
            return await answer(NOT_BOOSTING)
        role_id = config.get("roles", {}).get(str(user.id))
        if role_id and guild.get_role(role_id):
            return await answer(
                "You already have your custom role. Use `/boosterrole remove` to"
                " remove it first then setup again."
            )
        pending = config.get("pending_roles", {}).get(str(user.id))
        if pending:
            return await interaction.followup.send(
                embed=pending_embed(pending), ephemeral=True
            )
        icon_url, icon_ignored = None, False
        if icon_attachment and guild.premium_tier <= 1:
            icon_ignored = True
        elif icon_attachment:
            channel = self.bot.get_channel(MEDIA_CHANNEL)
            with contextlib.suppress(Exception):
                posted = await channel.send(file=await icon_attachment.to_file())
                icon_url = posted.attachments[0].url
        if not config.get("log"):
            return await answer(NO_LOG)
        log_channel = guild.get_channel(config["log"])
        if not log_channel:
            return await answer(LOG_GONE)
        await write(
            f"{guild.id}/pending_roles/{user.id}",
            {"name": name, "color": color, "icon_url": icon_url},
        )
        request = discord.Embed(
            title="⏳ Custom Role Request - Pending Approval",
            description=f"Booster: {user.mention} (`{user.id}`)",
            color=discord.Color.orange(),
        )
        done = discord.Embed(
            title=f"{YES} Role Request Submitted",
            description=(
                "Your custom booster role request has been submitted for staff"
                " approval!"
            ),
            color=discord.Color.green(),
        )
        for embed in (request, done):
            embed.add_field(name="Name", value=name, inline=False)
            embed.add_field(name="Color", value=color, inline=False)
            icon_fields(embed, icon_url)
        request.set_footer(text=f"Guild ID: {guild.id} | User ID: {user.id}")
        await log_channel.send(embed=request, view=RoleApprovalView())
        if icon_ignored:
            done.add_field(
                name="⚠️ Note",
                value=(
                    "This server doesn't have enough boosts for role icons (needs 7+"
                    " boosts).\nYour icon attachment was ignored."
                ),
                inline=False,
            )
        await interaction.followup.send(embed=done, ephemeral=True)

    @app_commands.command(name="remove", description="Remove your booster role")
    @app_commands.checks.cooldown(1, 600, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def remove(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild, user = interaction.guild, interaction.user

        def answer(text):
            return interaction.followup.send(text, ephemeral=True)

        config = await read(str(guild.id))
        if not config:
            return await answer(NOT_ENABLED)
        role_id = config.get("roles", {}).get(str(user.id))
        role = guild.get_role(role_id) if role_id else None
        if not role:
            return await answer(f"{NO} You have no booster role to remove.")
        try:
            await role.delete()
        except discord.Forbidden:
            return await answer(f"{NO} Bot lacks permission to delete the role.")
        await remove(f"{guild.id}/roles/{user.id}")
        await log_action(
            guild,
            config,
            f"{user.mention} (ID: {user.id}) removed their booster role named"
            f" `{role.name}`.",
            "Booster Role Removed",
        )
        await answer(
            f"{YES} Your booster role `{role.name}` has been deleted and removed!"
        )

    @app_commands.command(
        name="cleanup", description="Manual cleanup of expired boosters"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def cleanup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = await read(str(interaction.guild.id))
        if not config:
            return await interaction.followup.send(NOT_ENABLED, ephemeral=True)
        if "base_role" in config:
            await self.sweep(interaction.guild, config)
        await interaction.followup.send(
            f"{YES} Cleanup completed successfully!", ephemeral=True
        )

    @app_commands.command(name="setup", description="Configure booster system")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        system_channel="The channel where Discord sends boost messages",
        public_channel="The channel to send custom booster messages",
        log_channel="The channel that logs all booster-related actions",
    )
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def setup(
        self,
        interaction: discord.Interaction,
        system_channel: discord.TextChannel,
        public_channel: discord.TextChannel,
        log_channel: discord.TextChannel,
    ):
        guild = interaction.guild
        booster_role = guild.premium_subscriber_role
        if guild.id == OPEN_SERVER:
            booster_role = guild.get_role(OPEN_SERVER_BASE_ROLE)
        if not booster_role:
            return await interaction.response.send_message(
                f"{NO} Unfortunately, the server must have a booster role in order to"
                " enable this system. This means that this server must have been"
                " boosted previously.",
                ephemeral=True,
            )
        current = await read(f"{guild.id}/embed")
        await interaction.response.send_modal(BoosterEmbedModal(current))
        await merge(
            str(guild.id),
            {
                "base_role": booster_role.id,
                "system_channel": system_channel.id,
                "channel": public_channel.id,
                "log": log_channel.id,
            },
        )

    @app_commands.command(name="settings", description="Manage booster system settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        config = await read(str(guild.id))
        if not config:
            return await interaction.followup.send(NOT_ENABLED, ephemeral=True)
        embed = discord.Embed(
            title="⚙️ Booster System Settings",
            description=(
                "Use the buttons below to manage booster system settings.\n\n"
                "**Note:** Channel setups (system, public, log) cannot be changed here. "
                "Re-run `/boosterrole setup` to change them."
            ),
            color=discord.Color.blue(),
        )

        def shown(found):
            return found.mention if found else "Not found"

        embed.add_field(
            name="Current Configuration",
            value=(
                f"**Base Role:** {shown(guild.get_role(config.get('base_role')))}\n"
                "**System Channel:**"
                f" {shown(guild.get_channel(config.get('system_channel')))}\n"
                f"**Public Channel:** {shown(guild.get_channel(config.get('channel')))}\n"
                f"**Log Channel:** {shown(guild.get_channel(config.get('log')))}"
            ),
            inline=False,
        )
        await interaction.followup.send(
            embed=embed, view=SettingsPanelView(guild.id), ephemeral=True
        )

    @app_commands.command(
        name="disable",
        description="Disable the booster system and delete all custom roles",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def disable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not await read(str(guild.id)):
            return await interaction.followup.send(NOT_ENABLED, ephemeral=True)
        view = ConfirmDisableView()
        await interaction.followup.send(
            embed=discord.Embed(
                title="⚠️ Are you sure you want to disable the booster system?",
                description=(
                    "This will:\n"
                    "- Delete **ALL** custom booster roles *(you can use `/boosterrole"
                    " settings` to view all custom roles)*\n"
                    "- Remove **ALL** configuration\n"
                    "- **Permanently** disable the system\n\n"
                    "**This action cannot be undone!**"
                ),
                color=0xFF0000,
            ),
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.confirmed:
            return
        await interaction.followup.send(
            f"{LOADING} Disabling booster system... This may take a while.",
            ephemeral=True,
        )
        config = await read(str(guild.id)) or {}
        deleted = failed = 0
        for role_id in config.get("roles", {}).values():
            role = guild.get_role(role_id)
            if not role:
                continue
            try:
                await role.delete()
                deleted += 1
                entry = (
                    f"🗑️ Deleted role `{role.name}` (ID: `{role.id}`) during system"
                    " disable",
                    "System Disable",
                )
            except Exception as error:
                failed += 1
                entry = (
                    f"⚠️ Failed to delete role ID `{role_id}`: {error}",
                    "System Disable Error",
                )
            await log_action(guild, config, *entry)
        await log_action(
            guild,
            config,
            f"### 🚫 Booster system **disabled** by {interaction.user.mention}\n"
            f"- Deleted roles: `{deleted}`\n"
            f"- Failed deletions: `{failed}`\n"
            f"- Removed `{len(config.get('autoresponses', {}))}` autoresponses\n"
            f"- Removed `{len(config.get('pending_autoresponses', {}))}` pending"
            " autoresponses\n"
            f"- Removed `{len(config.get('pending_roles', {}))}` pending booster"
            " roles\n"
            "- **Configuration cleared**",
            "System Disabled",
        )
        await remove(str(guild.id))
        embed = discord.Embed(
            title="Booster System Disabled",
            description="The booster system has been completely disabled.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Roles Deleted", value=str(deleted))
        embed.add_field(name="Failed Deletions", value=str(failed))
        embed.add_field(name="Configuration", value="Removed from database")
        embed.set_footer(text="You can re-enable the system with /boosterrole setup")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    bot.add_view(AutoResponseApprovalView())
    bot.add_view(RoleApprovalView())
    await bot.add_cog(BoosterRole(bot))
