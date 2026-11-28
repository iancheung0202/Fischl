"""Tickets: panels members open tickets from, the ticket channels, transcripts and /ticket."""

import asyncio
import contextlib
import copy
import datetime
import hashlib
import io
import re
import time
import uuid
from collections import defaultdict

import discord
from assets.secret import GROQ_API_KEY
from discord import app_commands
from discord.ext import commands
from discord.ui import (
    Button,
    ChannelSelect,
    Modal,
    RoleSelect,
    Select,
    TextInput,
    UserSelect,
    View,
)
from firebase_admin import db

YES = "<:yes:1036811164891480194>"
NO = "<:no:1036810470860013639>"
REPLY = "<:reply:1036792837821435976>"
CLOSE_COMMAND = "</ticket close:1254927191129456641>"
CLOSE_HINT = (
    f"You can use {CLOSE_COMMAND} or click the red button below to close this ticket."
)
CLOSED_MARK = ":no_entry_sign:"
# Fischl's own channel that hears about every ticket; other bots cannot see it.
GLOBAL_LOG = 1417408712980697099
MISSING_PERMISSIONS = (
    f"{NO} **I'm missing permissions to create or edit text channels!** \nPlease make"
    " sure my role has `MANAGE_CHANNELS` permissions."
)
PANEL_LIMIT = 25
OPTION_LIMIT = 25
BUTTON_LIMIT = 5
SNIPPET_LIMIT = 25
EDITOR_TIMEOUT = 3600
SETTINGS_TIMEOUT = 1800
DEFAULT_AVATAR = "https://discord.com/assets/5d6a5e9d7d77ac29116e.png"
BUTTON_STYLES = {
    "green": discord.ButtonStyle.green,
    "blue": discord.ButtonStyle.blurple,
    "red": discord.ButtonStyle.red,
    "grey": discord.ButtonStyle.gray,
}
# Servers whose ticket channels are named after the topic: words in it -> name ending.
LUMINE_MAINS = 1094228164324114493
LUMINE_ENDINGS = {"general": "support", "role": "role", "partner": "partner"}
SPLIT_SERVER = 1197491630807199834
SPLIT_PARTNER_CATEGORY = 1253988610194018384
SPLIT_PARTNER_LOG = 1235251162056495226
SPLIT_ENDINGS = {"help": "support", "rule": "report"}
CLUB_SERVER = 791534106919305226
CLUB_TOPIC = "Club/Clan Applications"
CLUB_ROLE = 1429160134084661429
STAFF_PING_SERVER = 1281655927791030293
STAFF_PING = "[ <@&1309928108312498227> ]"
# Members whose ticket is being made right now, so a double press makes one.
opening = set()
# Tickets being closed right now, so two confirmations close one once.
closing = set()


def now() -> datetime.datetime:
    """Gives the current time in UTC."""
    return datetime.datetime.now(datetime.timezone.utc)


async def read(path: str):
    """Gives what Firebase holds at a path, without pausing the bot."""
    return await asyncio.to_thread(db.reference(path).get)


async def write(path: str, value) -> None:
    """Saves a value at a Firebase path, without pausing the bot."""
    await asyncio.to_thread(db.reference(path).set, value)


async def remove(path: str) -> None:
    """Deletes a Firebase path, without pausing the bot."""
    await asyncio.to_thread(db.reference(path).delete)


async def server_config(guild_id: int):
    """Gives a server's ticket settings and their key, or (None, None) with tickets off."""
    for key, value in (await read("/Tickets") or {}).items():
        if value.get("Server ID") == guild_id:
            return key, value
    return None, None


async def log_channel(guild: discord.Guild):
    """Gives the channel a server's ticket logs go to, or None."""
    _, config = await server_config(guild.id)
    return guild.get_channel(config["Log Channel ID"]) if config else None


def ask_groq(prompt: str) -> str:
    """Gives Groq's answer to a prompt; this waits on the network."""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY, timeout=30, max_retries=0)
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-120b",
    )
    return chat.choices[0].message.content


async def generate(prompt: str) -> str:
    """Gives the AI's answer to a prompt, without pausing the bot."""
    return await asyncio.to_thread(ask_groq, prompt)


def stamped(embed: discord.Embed) -> discord.Embed:
    """Gives the embed back with the current time on it."""
    embed.timestamp = now()
    return embed


def with_author(embed: discord.Embed, name: str, avatar) -> discord.Embed:
    """Puts a name on the embed, with the avatar when there is one."""
    if avatar:
        return embed.set_author(name=name, icon_url=avatar.url)
    return embed.set_author(name=name)


def link_view(label: str, url: str, emoji=None) -> View:
    """Gives a view holding one link button."""
    view = View()
    view.add_item(
        Button(style=discord.ButtonStyle.link, label=label, url=url, emoji=emoji)
    )
    return view


def ticket_link(channel, label="View Ticket", emoji=None) -> View:
    """Gives a link button to a ticket channel."""
    url = f"https://discord.com/channels/{channel.guild.id}/{channel.id}"
    return link_view(label, url, emoji)


async def send_global_log(client, embed: discord.Embed, **kwargs) -> None:
    """Posts to Fischl's own ticket log, when this bot can see it."""
    channel = client.get_channel(GLOBAL_LOG)
    if channel:
        await channel.send(embed=embed, **kwargs)


def not_enabled(text: str) -> discord.Embed:
    """Gives the notice that the server has not set tickets up."""
    return stamped(
        discord.Embed(
            title="Ticket not enabled!",
            description=(
                "This server doesn't have a ticket category or a log channel."
                f" {text}"
            ),
            colour=0xFF0000,
        )
    )


def owner_of(channel):
    """Gives the member ID an open ticket channel belongs to, or None."""
    topic = getattr(channel, "topic", None) or ""
    return int(topic) if topic.isdigit() else None


def is_closed(channel) -> bool:
    """Says whether the channel is a closed ticket."""
    return CLOSED_MARK in (getattr(channel, "topic", None) or "")


def closed_owner_of(channel):
    """Gives the member ID a closed ticket belonged to, or None."""
    if not is_closed(channel):
        return None
    try:
        return int(channel.topic.split(":")[2].strip())
    except Exception:
        return None


def ticket_of(category, user_id: int):
    """Gives the member's open ticket in the category, or None."""
    for channel in category.channels:
        if str(channel.topic) == str(user_id):
            return channel
    return None


def user_fields(embed: discord.Embed, member, channel) -> discord.Embed:
    """Adds the six facts about a ticket's member to its first embed."""
    facts = {
        "User Mention": member.mention,
        "User ID": member.id,
        "Highest Role": member.roles[-1].mention,
        "Ticket Created": f"<t:{int(channel.created_at.timestamp())}:R>",
        "Server Joined": f"<t:{int(member.joined_at.timestamp())}:R>",
        "Account Created": f"<t:{int(member.created_at.timestamp())}:R>",
    }
    for name, value in facts.items():
        embed.add_field(name=name, value=f"{value}", inline=True)
    return embed


async def open_channel(guild, category, member, name: str):
    """Makes a ticket channel only its member and the staff can see."""
    channel = await guild.create_text_channel(name, category=category)
    await channel.edit(topic=member.id)
    await channel.set_permissions(
        member, send_messages=True, read_messages=True, attach_files=True
    )
    return channel


async def legacy_topic(interaction: discord.Interaction):
    """Reads the topic off an old panel, with the server's instructions embed for it."""
    try:
        shown = interaction.message.embeds[0]
        if "Are you sure you want to make a ticket" in shown.description:
            topic = shown.description.split("**")[1]
        else:
            topic = f"{shown.title}"
        instructions = await read(f"/Ticket Instructions/{interaction.guild.id}")
        for name, info in (instructions or {}).items():
            if name.strip().lower() == topic.strip().lower():
                return topic, discord.Embed(
                    title=info.get("title", ""),
                    description=info.get("description", ""),
                    color=int(info.get("color", "#5865F2").lstrip("#"), 16),
                )
        return topic, None
    except Exception:
        return "", None


def routed(guild, topic: str, category, log):
    """Gives the channel-name ending, category and log a server's own rules pick."""
    words = topic.lower()
    if guild.id == LUMINE_MAINS:
        endings = [end for word, end in LUMINE_ENDINGS.items() if word in words]
        return (endings[0] if endings else None), category, log
    if guild.id == SPLIT_SERVER:
        if "partner" in words:
            category = guild.get_channel(SPLIT_PARTNER_CATEGORY)
            return None, category, guild.get_channel(SPLIT_PARTNER_LOG)
        endings = [end for word, end in SPLIT_ENDINGS.items() if word in words]
        return (endings[0] if endings else None), category, log
    return None, category, log


async def refusal(interaction: discord.Interaction, config, category):
    """Gives why the member may not open a ticket now, or None."""
    guild, user = interaction.guild, interaction.user
    existing = ticket_of(category, user.id)
    if existing:
        return f"{NO} You already had your ticket created at <#{existing.id}>."
    if await read(f"/Ticket Blacklist/{guild.id}/{user.id}"):
        return f"{NO} You are blacklisted from creating tickets in **{guild.name}**."
    last = await read(f"/Tickets Cooldown/{guild.id}/users/{user.id}/last_created")
    left = (config.get("Cooldown") or 0) - (time.time() - (last or 0))
    if last and left > 0:
        return (
            f"{NO} You are on a cooldown! Try again in"
            f" **{int(left // 3600)}h {int((left % 3600) // 60)}m**."
        )
    return None


async def create_ticket(
    interaction, topic=None, custom_opening_message=None, closing_message=None
):
    """Opens a ticket channel for the member who pressed a panel."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    await start_ticket(interaction, topic, custom_opening_message, closing_message)


async def start_ticket(
    interaction, topic=None, custom_opening_message=None, closing_message=None
):
    """Opens a ticket channel once the press has been acknowledged."""
    guild, user = interaction.guild, interaction.user
    _, config = await server_config(guild.id)
    if not config:
        hint = "Please ask the server moderator to use `/ticket settings` to setup tickets!"
        await interaction.followup.send(embed=not_enabled(hint), ephemeral=True)
        return
    key = (guild.id, user.id)
    if key in opening:
        return await interaction.followup.send(
            f"{NO} Your ticket is already being created.", ephemeral=True
        )
    opening.add(key)
    try:
        await open_ticket(
            interaction, config, topic, custom_opening_message, closing_message
        )
    finally:
        opening.discard(key)


async def open_ticket(interaction, config, topic, opening_message, closing_message):
    """Checks the member may open a ticket, then makes it and tells everyone."""
    guild, user = interaction.guild, interaction.user
    category = guild.get_channel(config["Category ID"])
    refused = await refusal(interaction, config, category)
    if refused:
        return await interaction.followup.send(refused, ephemeral=True)
    log = guild.get_channel(config["Log Channel ID"])
    special = None
    if topic is None:
        topic, special = await legacy_topic(interaction)
    ending, category, log = routed(guild, topic, category, log)
    welcome = f"**{user.mention}, welcome!**"
    try:
        name = f"{user.name}-{ending}" if ending else f"{user.name}"
        channel = await open_channel(guild, category, user, name)
        club = guild.id == CLUB_SERVER and CLUB_TOPIC in topic
        role = guild.get_role(CLUB_ROLE) if club else None
        if role:
            await channel.set_permissions(
                role, send_messages=True, read_messages=True, attach_files=True
            )
            welcome = (
                f"<@&{CLUB_ROLE}> A new club/clan application has been created by"
                f" {user.mention}."
            )
    except Exception:
        return await interaction.followup.send(MISSING_PERMISSIONS, ephemeral=True)
    embed = discord.Embed(
        title="Ticket created",
        description=(
            f"**{user.mention}** created a new ticket"
            f" <t:{int(now().timestamp())}:R>!"
        ),
        color=discord.Colour.green(),
    )
    if topic:
        embed.add_field(name="Ticket Topic", value=topic)
    stamped(with_author(embed, user.name, user.avatar))
    embed.set_footer(text=f"Ticket ID: {channel.id}")
    await log.send(embed=embed, view=ticket_link(channel))
    embed.title = f"Ticket created in {guild.name}"
    await send_global_log(interaction.client, embed)
    first = discord.Embed(
        title=topic if topic else "New Ticket",
        description=f"Type your message here in this channel!\n{CLOSE_HINT}",
        color=discord.Colour.gold(),
    )
    if opening_message:
        first.description = f"> {opening_message}\n\n{CLOSE_HINT}"
    ping_role = config.get("Ping Role ID")
    ping = f"||<@&{ping_role}>||" if ping_role is not None else ""
    await channel.send(
        f"{welcome} {ping}",
        embed=user_fields(stamped(first), user, channel),
        view=CloseTicketButton(),
    )
    if special is not None:
        await channel.send(embed=special)
    await interaction.followup.send(
        f"{YES} Ticket created at <#{channel.id}>", ephemeral=True
    )
    if closing_message:
        await write(f"/Ticket Closing Messages/{channel.id}", closing_message)
    await write(
        f"/Tickets Cooldown/{guild.id}/users/{user.id}/last_created", time.time()
    )


def blank_embed() -> dict:
    """Gives the embed settings a new panel starts with."""
    return {
        "title": "",
        "description": "",
        "color": discord.Color.blurple().value,
        "footer": {"text": "", "icon_url": ""},
        "author": {"name": "", "icon_url": ""},
        "thumbnail": "",
        "image": "",
        "fields": [],
        "timestamp": False,
    }


class TicketPanelEditor:
    """One panel being built: its embed and the options or buttons that open tickets."""

    def __init__(
        self, user_id, guild_id, panel_type, panel_id=None, existing_data=None
    ):
        self.user_id = user_id
        self.guild_id = guild_id
        self.panel_type = panel_type
        self.panel_id = panel_id
        self.embed_data = blank_embed()
        self.options = []
        self.buttons = []
        self.message_id = None
        self.channel_id = None
        self.name = ""
        if existing_data:
            self.load_from_dict(existing_data)

    @property
    def path(self) -> str:
        """Gives where this panel's type is kept for its server."""
        return f"Ticket Panels/{self.guild_id}/{self.panel_type}"

    @property
    def choices(self) -> list:
        """Gives the options of a dropdown panel or the buttons of a button panel."""
        return self.options if self.panel_type == "dropdown" else self.buttons

    def load_from_dict(self, data):
        """Fills the editor from a saved panel."""
        self.embed_data = {**blank_embed(), **data.get("embed", {})}
        self.options = data.get("options", [])
        self.buttons = data.get("buttons", [])
        for choice in self.options + self.buttons:
            choice.setdefault("closing_message", "")
        self.message_id = data.get("message_id")
        self.channel_id = data.get("channel_id")
        self.name = data.get("name", "")

    def to_dict(self):
        """Gives the panel the way it is saved."""
        return {
            "embed": self.embed_data,
            "options": self.options,
            "buttons": self.buttons,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "type": self.panel_type,
        }

    def is_empty(self):
        """Says whether the embed has nothing to show yet."""
        data = self.embed_data
        return not (
            data["title"]
            or data["description"]
            or data["image"]
            or data["thumbnail"]
            or data["fields"]
            or data["author"]["name"]
            or data["footer"]["text"]
        )

    def to_embed(self):
        """Builds the panel's embed."""
        data = self.embed_data
        embed = discord.Embed(
            title=data["title"] or None,
            description=data["description"] or None,
            color=data["color"],
        )
        if data["footer"]["text"]:
            embed.set_footer(
                text=data["footer"]["text"], icon_url=data["footer"]["icon_url"] or None
            )
        if data["author"]["name"]:
            embed.set_author(
                name=data["author"]["name"], icon_url=data["author"]["icon_url"] or None
            )
        if data["thumbnail"]:
            embed.set_thumbnail(url=data["thumbnail"])
        if data["image"]:
            embed.set_image(url=data["image"])
        for field in data["fields"]:
            embed.add_field(
                name=field["name"], value=field["value"], inline=field["inline"]
            )
        if data["timestamp"]:
            embed.timestamp = now()
        return embed

    def shown(self, title: str, description: str) -> discord.Embed:
        """Gives the panel's embed, or a grey placeholder while it is empty."""
        if not self.is_empty():
            return self.to_embed()
        return discord.Embed(
            title=title, description=description, color=discord.Color.light_gray()
        )


def text(label, placeholder, default="", long=False, required=False, max_length=None):
    """Gives one text box of a modal."""
    return TextInput(
        label=label,
        placeholder=placeholder,
        default=default,
        max_length=max_length,
        required=required,
        style=discord.TextStyle.paragraph if long else discord.TextStyle.short,
    )


class EditorModal(Modal):
    """A modal that changes the editor and leaves the redraw to the view that opened it."""

    def __init__(self, title: str, editor: TicketPanelEditor, *boxes):
        super().__init__(title=title)
        self.editor = editor
        for box in boxes:
            self.add_item(box)

    @property
    def values(self) -> list:
        """Gives what was typed into each box, in order."""
        return [box.value for box in self.children]


class EmbedModal(EditorModal):
    """Edits the embed's texts and colour."""

    def __init__(self, editor: TicketPanelEditor):
        data = editor.embed_data
        super().__init__(
            "Edit Embed",
            editor,
            text("Title", "Panel title", data["title"], max_length=256),
            text(
                "Description",
                "Panel description",
                data["description"],
                long=True,
                max_length=4000,
            ),
            text("Color (Hex)", "#FF0000", f"#{data['color']:06x}", max_length=7),
            text("Footer Text", "Footer text", data["footer"]["text"], max_length=2048),
            text("Author Name", "Author name", data["author"]["name"], max_length=256),
        )

    async def on_submit(self, interaction: discord.Interaction):
        data = self.editor.embed_data
        data["title"], data["description"], color, footer, author = self.values
        color = color.strip()
        if color.startswith("#"):
            try:
                data["color"] = int(color[1:], 16)
            except ValueError:
                pass
        data["footer"]["text"] = footer
        data["author"]["name"] = author
        await interaction.response.defer()


class MediaModal(EditorModal):
    """Edits the embed's image links."""

    def __init__(self, editor: TicketPanelEditor):
        data = editor.embed_data
        super().__init__(
            "Edit Media",
            editor,
            text("Image URL", "Main image/banner URL", data["image"]),
            text("Thumbnail URL", "Thumbnail image URL", data["thumbnail"]),
            text("Author Icon URL", "Author icon URL", data["author"]["icon_url"]),
            text("Footer Icon URL", "Footer icon URL", data["footer"]["icon_url"]),
        )

    async def on_submit(self, interaction: discord.Interaction):
        data = self.editor.embed_data
        image, thumbnail, author_icon, footer_icon = self.values
        data["image"], data["thumbnail"] = image, thumbnail
        data["author"]["icon_url"] = author_icon
        data["footer"]["icon_url"] = footer_icon
        await interaction.response.defer()


class ItemModal(EditorModal):
    """Adds one item to a list of the editor, or replaces the item at `index`."""

    limit = None
    limit_text = ""

    def __init__(self, title, editor, items, index, *boxes):
        super().__init__(title, editor, *boxes)
        self.items = items
        self.index = index

    def item(self) -> dict:
        """Gives the item the typed values describe."""
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction):
        if self.index is None and self.limit and len(self.items) >= self.limit:
            return await interaction.response.send_message(
                self.limit_text, ephemeral=True
            )
        if self.index is not None:
            self.items[self.index] = self.item()
        else:
            self.items.append(self.item())
        await interaction.response.defer()


class FieldModal(ItemModal):
    """Adds or edits one field of the embed."""

    def __init__(self, editor: TicketPanelEditor, field_index=None):
        fields = editor.embed_data["fields"]
        field = {"name": "", "value": "", "inline": True}
        if field_index is not None:
            field = fields[field_index]
        super().__init__(
            "Edit Field" if field_index is not None else "Add Field",
            editor,
            fields,
            field_index,
            text("Field Name", "Field title", field["name"], False, True, 256),
            text("Field Value", "Field content", field["value"], True, True, 1024),
            text(
                "Inline (Y/N)",
                "Y for inline, N for not inline",
                "Y" if field["inline"] else "N",
                required=True,
                max_length=1,
            ),
        )

    def item(self) -> dict:
        name, value, inline = self.values
        return {"name": name, "value": value, "inline": inline.upper() == "Y"}


def message_boxes(choice: dict) -> tuple:
    """Gives the opening and closing message boxes of an option or button."""
    return (
        text(
            "Opening Message",
            "Message sent when ticket is created",
            choice["opening_message"],
            long=True,
        ),
        text(
            "Closing Message",
            "Message sent when ticket is closed",
            choice["closing_message"],
            long=True,
        ),
    )


EMOJI_HINT = "Format: <:name:id> or unicode emoji"


class DropdownOptionModal(ItemModal):
    """Adds or edits one option of a dropdown panel."""

    limit = OPTION_LIMIT
    limit_text = f"Dropdown panels can have a maximum of {OPTION_LIMIT} options."

    def __init__(self, editor: TicketPanelEditor, option_index=None):
        option = dict.fromkeys(
            ["label", "description", "emoji", "opening_message", "closing_message"], ""
        )
        if option_index is not None:
            option = editor.options[option_index]
        super().__init__(
            "Edit Option" if option_index is not None else "Add Option",
            editor,
            editor.options,
            option_index,
            text(
                "Option Label",
                "Text shown in dropdown",
                option["label"],
                False,
                True,
                100,
            ),
            text(
                "Description",
                "Optional description",
                option["description"],
                max_length=100,
            ),
            text("Emoji", EMOJI_HINT, option["emoji"]),
            *message_boxes(option),
        )

    def item(self) -> dict:
        label, description, emoji, opening_message, closing_message = self.values
        return {
            "label": label,
            "value": label,
            "description": description,
            "emoji": emoji,
            "opening_message": opening_message,
            "closing_message": closing_message,
        }


class ButtonOptionModal(ItemModal):
    """Adds or edits one button of a button panel."""

    limit = BUTTON_LIMIT
    limit_text = f"Button panels can have a maximum of {BUTTON_LIMIT} buttons."

    def __init__(self, editor: TicketPanelEditor, button_index=None):
        button = dict.fromkeys(
            ["label", "emoji", "opening_message", "closing_message"], ""
        )
        button["color"] = "grey"
        if button_index is not None:
            button = editor.buttons[button_index]
        super().__init__(
            "Edit Button" if button_index is not None else "Add Button",
            editor,
            editor.buttons,
            button_index,
            text(
                "Button Label", "Text shown on button", button["label"], False, True, 80
            ),
            text("Emoji", EMOJI_HINT, button["emoji"]),
            text("Color", "green, blue, red, or grey", button["color"], required=True),
            *message_boxes(button),
        )

    def item(self) -> dict:
        label, emoji, color, opening_message, closing_message = self.values
        color = color.lower()
        return {
            "label": label,
            "emoji": emoji,
            "color": color,
            "style": BUTTON_STYLES.get(color, discord.ButtonStyle.grey).value,
            "opening_message": opening_message,
            "closing_message": closing_message,
        }


class SaveModal(Modal):
    """Asks for the panel's name and saves it."""

    def __init__(self, editor: TicketPanelEditor, is_save_as=False):
        super().__init__(title="Save As New Panel" if is_save_as else "Save Panel")
        self.editor = editor
        self.is_new = is_save_as or not editor.panel_id
        keep_name = editor.panel_id and not is_save_as
        self.add_item(
            text(
                "Panel Name",
                "Give this panel a name",
                editor.name if keep_name else "",
                required=True,
                max_length=100,
            )
        )

    async def refusal(self):
        """Gives why the panel cannot be saved, or None."""
        editor = self.editor
        if editor.panel_type == "dropdown" and len(editor.options) > OPTION_LIMIT:
            return DropdownOptionModal.limit_text
        if editor.panel_type == "button" and len(editor.buttons) > BUTTON_LIMIT:
            return ButtonOptionModal.limit_text
        if self.is_new and len(await read(editor.path) or {}) >= PANEL_LIMIT:
            return (
                f"Server {editor.panel_type} panel limit reached ({PANEL_LIMIT})."
                " Cannot save new panel."
            )
        return None

    async def on_submit(self, interaction: discord.Interaction):
        editor = self.editor
        refused = await self.refusal()
        if refused:
            return await interaction.response.send_message(refused, ephemeral=True)
        panel_id = str(uuid.uuid4())[:8] if self.is_new else editor.panel_id
        editor.name = self.children[0].value
        data = {
            **editor.to_dict(),
            "name": editor.name,
            "created_at": now().isoformat(),
        }
        await write(f"{editor.path}/{panel_id}", data)
        editor.panel_id = panel_id
        await interaction.response.send_message(
            f"{YES} Panel saved as **{editor.name}** (ID: `{panel_id}`)",
            ephemeral=True,
        )


class EditorView(View):
    """A screen of the panel editor; it redraws the message the editor was opened in."""

    def __init__(self, cog, editor, original_interaction, timeout=EDITOR_TIMEOUT):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction

    def screen(self) -> dict:
        """Gives the content and embed this screen shows."""
        raise NotImplementedError

    async def update_message(self, interaction: discord.Interaction = None):
        """Redraws the screen, as the answer to a press when one is given."""
        if interaction:
            await interaction.response.edit_message(**self.screen(), view=self)
        else:
            await self.original_interaction.edit_original_response(
                **self.screen(), view=self
            )

    async def ask(self, interaction: discord.Interaction, modal: Modal):
        """Shows a modal and waits until it is closed."""
        await interaction.response.send_modal(modal)
        await modal.wait()

    async def to_main(self, interaction: discord.Interaction):
        """Goes back to the editor's first screen."""
        view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)


def press(view, label, style, emoji, row, callback) -> None:
    """Adds a button to a view."""
    button = Button(label=label, style=style, emoji=emoji, row=row)
    button.callback = callback
    view.add_item(button)


class ItemsView(EditorView):
    """Lists some items of the editor and lets one be added, edited or removed."""

    noun = ""
    modal = None
    nothing_selected = ""
    follows_changes = True
    select_id = None

    def __init__(self, cog, editor, original_interaction):
        super().__init__(cog, editor, original_interaction)
        self.selected_index = 0 if self.items else None
        self.build()

    @property
    def items(self) -> list:
        """Gives the list this screen manages."""
        raise NotImplementedError

    def option(self, index: int, item: dict) -> discord.SelectOption:
        """Gives the select entry of one item."""
        raise NotImplementedError

    def build(self) -> None:
        """Puts the select and the buttons on the view."""
        self.clear_items()
        if self.items:
            select = Select(
                placeholder=f"Select {self.article} {self.noun.lower()} to edit{self.dots}",
                options=[self.option(i, item) for i, item in enumerate(self.items)],
                row=0,
                **({"custom_id": self.select_id} if self.select_id else {}),
            )
            select.callback = self.select
            self.add_item(select)
        style = discord.ButtonStyle
        press(self, f"Add {self.noun}", style.success, "➕", 1, self.add)
        press(self, f"Edit {self.noun}", style.primary, "✏️", 1, self.edit)
        press(self, f"Remove {self.noun}", style.danger, "🗑️", 1, self.remove)
        self.more_buttons()
        press(self, "Back", style.gray, "↩️", 2, self.to_main)

    def more_buttons(self) -> None:
        """Adds the buttons only some lists have."""

    async def update_message(self, interaction: discord.Interaction = None):
        self.build()
        await super().update_message(interaction)

    async def missing(self, interaction: discord.Interaction) -> bool:
        """Answers and says True when no item is selected."""
        if self.selected_index is None:
            await interaction.response.send_message(
                self.nothing_selected, ephemeral=True
            )
        return self.selected_index is None

    async def select(self, interaction: discord.Interaction):
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)

    async def add(self, interaction: discord.Interaction):
        await self.ask(interaction, self.modal(self.editor))
        if self.follows_changes:
            self.selected_index = len(self.items) - 1 if self.items else None
        await self.update_message()

    async def edit(self, interaction: discord.Interaction):
        if await self.missing(interaction):
            return
        await self.ask(interaction, self.modal(self.editor, self.selected_index))
        await self.update_message()

    async def remove(self, interaction: discord.Interaction):
        if await self.missing(interaction):
            return
        self.items.pop(self.selected_index)
        last = len(self.items) - 1
        keep = self.follows_changes and self.items
        self.selected_index = min(self.selected_index, last) if keep else None
        await self.update_message(interaction)


class FieldsEditorView(ItemsView):
    """Manages the embed's fields."""

    noun, article, dots = "Field", "a", ""
    modal = FieldModal
    nothing_selected = "Please select a field first!"
    follows_changes = False

    @property
    def items(self) -> list:
        return self.editor.embed_data["fields"]

    def option(self, index, field):
        label = field["name"][:50] if field["name"] else f"Field {index + 1}"
        return discord.SelectOption(label=label, value=str(index))

    def more_buttons(self) -> None:
        style = discord.ButtonStyle.secondary
        press(self, "Move Up", style, "⬆️", 2, self.move_up)
        press(self, "Move Down", style, "⬇️", 2, self.move_down)

    def screen(self) -> dict:
        embed = self.editor.shown(
            "Fields Editor", "Add and manage embed fields for your ticket panel."
        )
        return {"content": None, "embed": embed}

    async def move(self, interaction: discord.Interaction, step: int, way: str):
        """Swaps the selected field with its neighbour."""
        here = self.selected_index
        there = None if here is None else here + step
        if there is None or not 0 <= there < len(self.items):
            return await interaction.response.send_message(
                f"Cannot move this field {way}!", ephemeral=True
            )
        self.items[here], self.items[there] = self.items[there], self.items[here]
        self.selected_index = there
        await self.update_message(interaction)

    async def move_up(self, interaction: discord.Interaction):
        await self.move(interaction, -1, "up")

    async def move_down(self, interaction: discord.Interaction):
        await self.move(interaction, 1, "down")


class ChoicesView(ItemsView):
    """Manages what a panel offers: its dropdown options or its buttons."""

    article, dots = "an", "..."
    title = description = field_name = ""

    @property
    def items(self) -> list:
        return self.editor.choices

    def line(self, index: int, choice: dict) -> str:
        """Gives one choice as it is listed in the embed."""
        raise NotImplementedError

    def screen(self) -> dict:
        embed = discord.Embed(
            title=self.title, description=self.description, color=discord.Color.blue()
        )
        if self.items:
            lines = "\n".join(self.line(i, item) for i, item in enumerate(self.items))
            if len(lines) > 1024:
                lines = lines[:1021] + "..."
            embed.add_field(name=self.field_name, value=lines, inline=False)
        return {"embed": embed}


class DropdownOptionsView(ChoicesView):
    """Manages the options of a dropdown panel."""

    noun = "Option"
    modal = DropdownOptionModal
    nothing_selected = f"{NO} No option selected!"
    select_id = "options_select"
    title = "Dropdown Options Manager"
    description = "Manage the options for your dropdown ticket panel."
    field_name = "Current Options"

    def option(self, index, option):
        return discord.SelectOption(
            label=option["label"][:100],
            value=str(index),
            description=option["description"][:100] or "No description",
            default=index == self.selected_index,
        )

    def line(self, index, option):
        line = f"**{index + 1}. {option['label']}**\n- Value: `{option['value']}`"
        if option["description"]:
            line += f"\n- Description: {option['description']}"
        if option["emoji"]:
            line += f"\n- Emoji: {option['emoji']}"
        return line + f"\n- Opening: {option['opening_message']}"


class ButtonOptionsView(ChoicesView):
    """Manages the buttons of a button panel."""

    noun, article = "Button", "a"
    modal = ButtonOptionModal
    nothing_selected = f"{NO} No button selected!"
    select_id = "buttons_select"
    title = "Button Options Manager"
    description = "Manage the buttons for your ticket panel."
    field_name = "Current Buttons"

    def option(self, index, button):
        return discord.SelectOption(
            label=button["label"][:100],
            value=str(index),
            description=f"Color: {button['color']}",
            default=index == self.selected_index,
        )

    def line(self, index, button):
        line = f"**{index + 1}. {button['label']}** ({button['color']})"
        if button["emoji"]:
            line += f" {button['emoji']}"
        return line + f"\n- Opening: {button['opening_message']}"


class TicketPanelMainView(EditorView):
    """The editor's first screen: every part of a panel and what to do with it."""

    def __init__(self, cog, editor, original_interaction):
        super().__init__(cog, editor, original_interaction)
        style = discord.ButtonStyle
        manage = (
            "Manage Options" if editor.panel_type == "dropdown" else "Manage Buttons"
        )
        press(self, "Embed", style.secondary, "📝", None, self.edit_embed)
        press(self, "Media", style.secondary, "🖼️", None, self.edit_media)
        press(self, "Fields", style.secondary, "📋", None, self.edit_fields)
        press(self, manage, style.primary, "⚙️", None, self.manage_options)
        press(self, "Save", style.success, "💾", 1, self.save_panel)
        press(self, "Save As", style.success, "📁", 1, self.save_as_panel)
        press(self, "Post Panel", style.green, "📤", 1, self.post_panel)
        press(self, "Update Posted", style.blurple, "🔄", 1, self.update_posted)
        if editor.panel_id:
            press(self, "Delete Panel", style.danger, "🗑️", 1, self.delete_panel)

    def screen(self) -> dict:
        embed = self.editor.shown(
            "No Content Yet",
            "Use the buttons below to start building your ticket panel!",
        )
        return {"content": None, "embed": embed}

    async def edit_embed(self, interaction: discord.Interaction):
        await self.ask(interaction, EmbedModal(self.editor))
        await self.update_message()

    async def edit_media(self, interaction: discord.Interaction):
        await self.ask(interaction, MediaModal(self.editor))
        await self.update_message()

    async def edit_fields(self, interaction: discord.Interaction):
        view = FieldsEditorView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

    async def manage_options(self, interaction: discord.Interaction):
        dropdown = self.editor.panel_type == "dropdown"
        screen = DropdownOptionsView if dropdown else ButtonOptionsView
        view = screen(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

    async def save_panel(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SaveModal(self.editor))

    async def save_as_panel(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SaveModal(self.editor, is_save_as=True))

    async def post_panel(self, interaction: discord.Interaction):
        view = PostPanelView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

    async def posted_message(self, interaction: discord.Interaction):
        """Fetches the panel's posted message, looking here when its channel is unknown."""
        channel = interaction.guild.get_channel(self.editor.channel_id or 0)
        channel = channel or self.original_interaction.channel
        return await channel.fetch_message(self.editor.message_id)

    async def update_posted(self, interaction: discord.Interaction):
        if not self.editor.message_id:
            return await interaction.response.send_message(
                f"{NO} This panel hasn't been posted yet!", ephemeral=True
            )
        try:
            message = await self.posted_message(interaction)
            view = panel_view(self.editor)
            await message.edit(embed=self.editor.to_embed(), view=view)
            posted[message.id] = copy.deepcopy(self.editor.choices)
            answer = f"{YES} Posted panel updated!"
        except Exception as error:
            answer = f"{NO} Failed to update panel: {error}"
        await interaction.response.send_message(answer, ephemeral=True)

    async def delete_panel(self, interaction: discord.Interaction):
        editor = self.editor
        try:
            was_posted = bool(editor.message_id)
            if was_posted:
                with contextlib.suppress(discord.NotFound):
                    await (await self.posted_message(interaction)).delete()
                posted.pop(editor.message_id, None)
            await remove(f"{editor.path}/{editor.panel_id}")
            editor.panel_id = editor.message_id = editor.channel_id = None
            await interaction.response.send_message(
                f"{YES} Panel deleted!"
                f" {'Posted message is also removed.' if was_posted else ''}",
                ephemeral=True,
            )
            view = TicketPanelMainView(self.cog, editor, self.original_interaction)
            await view.update_message()
        except Exception as error:
            await interaction.response.send_message(
                f"{NO} Failed to delete panel: {error}", ephemeral=True
            )


class PostPanelView(EditorView):
    """Asks which channel the panel goes to and posts it there."""

    PROMPT = (
        f"### 📤 Choose where to post your ticket panel.\n{REPLY} If you want to save"
        " the panel as a template, you can go back and do so! Posting a panel does not"
        " automatically save it as a template."
    )

    def __init__(self, cog, editor, original_interaction):
        super().__init__(cog, editor, original_interaction, timeout=1800)
        self.selected_channel = None
        self.channel_select = ChannelSelect(placeholder="Select channel to post...")
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)
        style = discord.ButtonStyle
        press(self, "Post Panel", style.green, "📤", 1, self.post_panel)
        press(self, "Back", style.gray, "↩️", 1, self.to_main)

    def screen(self) -> dict:
        return {"content": self.PROMPT, "embed": self.editor.to_embed()}

    async def select_channel(self, interaction: discord.Interaction):
        chosen = self.channel_select.values[0]
        self.selected_channel = interaction.guild.get_channel(chosen.id)
        await interaction.response.defer()

    async def post_panel(self, interaction: discord.Interaction):
        editor = self.editor
        if not self.selected_channel:
            return await interaction.response.send_message(
                "Please select a channel first!", ephemeral=True
            )
        view = panel_view(editor)
        if not view:
            return await interaction.response.send_message(
                f"{NO} Cannot post panel: no options/buttons configured!",
                ephemeral=True,
            )
        try:
            message = await self.selected_channel.send(
                embed=editor.to_embed(), view=view
            )
        except Exception as error:
            return await interaction.response.send_message(
                f"{NO} Failed to post panel: {error}", ephemeral=True
            )
        posted[message.id] = copy.deepcopy(editor.choices)
        editor.message_id, editor.channel_id = message.id, message.channel.id
        saved = f"{editor.path}/{editor.panel_id}"
        if editor.panel_id and await read(saved):
            where = {"message_id": message.id, "channel_id": message.channel.id}
            await asyncio.to_thread(db.reference(saved).update, where)
        await self.to_main(interaction)
        await interaction.followup.send(
            f"{YES} Panel posted! [View Message]({message.jump_url})", ephemeral=True
        )


class CreateNewButton(Button):
    """Starts an empty panel."""

    def __init__(self, cog, panel_type):
        super().__init__(
            label="Create New Panel", style=discord.ButtonStyle.primary, emoji="➕"
        )
        self.cog = cog
        self.panel_type = panel_type

    async def callback(self, interaction: discord.Interaction):
        editor = TicketPanelEditor(
            interaction.user.id, interaction.guild_id, self.panel_type
        )
        view = TicketPanelMainView(self.cog, editor, interaction)
        await view.update_message(interaction)


class PanelSelectView(View):
    """Lists a server's saved panels of one type, to edit one or start a new one."""

    def __init__(self, cog, panel_type):
        super().__init__(timeout=60)
        self.cog = cog
        self.panel_type = panel_type
        self.panel_data = {}

    async def load_panels(self, guild_id):
        """Reads the saved panels and puts the select and button on the view."""
        try:
            path = f"Ticket Panels/{guild_id}/{self.panel_type}"
            self.panel_data = await read(path) or {}
        except Exception as error:
            return print(f"Error loading panels: {error}")
        options = [
            discord.SelectOption(
                label=data.get("name", f"Panel {panel_id}")[:100],
                value=panel_id,
                description=f"ID: {panel_id}",
            )
            for panel_id, data in self.panel_data.items()
        ]
        if options:
            select = Select(placeholder="Choose a panel...", options=options)
            select.callback = self.select_panel
        else:
            select = Select(
                placeholder="No panels available",
                options=[discord.SelectOption(label="No panels", value="none")],
                disabled=True,
            )
        self.add_item(select)
        self.add_item(CreateNewButton(self.cog, self.panel_type))

    async def select_panel(self, interaction: discord.Interaction):
        panel_id = interaction.data["values"][0]
        editor = TicketPanelEditor(
            interaction.user.id,
            interaction.guild_id,
            self.panel_type,
            panel_id,
            self.panel_data[panel_id],
        )
        view = TicketPanelMainView(self.cog, editor, interaction)
        await view.update_message(interaction)


# What panels posted since the bot started offer, by message ID; saved panels are read
# from Firebase when they are not here.
posted = {}


async def panel_choices(guild_id: int, message_id: int) -> list:
    """Gives the options or buttons of the posted panel with this message ID."""
    if message_id in posted:
        return posted[message_id]
    saved = await read(f"Ticket Panels/{guild_id}") or {}
    for panels in saved.values():
        for panel in panels.values():
            if panel.get("message_id") == message_id:
                return panel.get("options") or panel.get("buttons") or []
    return []


def labelled(choices: list, label: str):
    """Gives the option or button with this label, or None."""
    return next((one for one in choices if one.get("label") == label), None)


async def open_from_button(interaction: discord.Interaction, index: int = 0):
    """Opens the ticket the panel's button at this place stands for."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    choices = await panel_choices(interaction.guild.id, interaction.message.id)
    choice = choices[index] if index < len(choices) else {}
    await start_ticket(
        interaction,
        topic=choice.get("label") if len(choices) > 1 else None,
        custom_opening_message=choice.get("opening_message"),
        closing_message=choice.get("closing_message"),
    )


class CreateTicketButton(Button):
    """A panel's first button, and the confirm button of prompts sent before a restart."""

    def __init__(self, title, emoji, color):
        super().__init__(label=title, emoji=emoji, style=color, custom_id="create")

    async def callback(self, interaction: discord.Interaction):
        await open_from_button(interaction)


class ExtraTicketButton(
    discord.ui.DynamicItem[Button], template=r"create:(?P<index>[0-9]+)"
):
    """A panel's second to fifth button; Discord wants every button's ID different."""

    def __init__(self, title, emoji, color, index: int):
        super().__init__(
            Button(label=title, emoji=emoji, style=color, custom_id=f"create:{index}")
        )
        self.index = index

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(item.label, item.emoji, item.style, int(match["index"]))

    async def callback(self, interaction: discord.Interaction):
        await open_from_button(interaction, self.index)


class ConfirmTicketButton(
    discord.ui.DynamicItem[Button], template=r"confirm:(?P<panel>[0-9]+)"
):
    """Confirms a dropdown choice; its ID names the panel the choice was made on."""

    def __init__(self, panel: int):
        super().__init__(
            Button(label="Create Ticket", emoji="🎫", custom_id=f"confirm:{panel}")
        )
        self.panel = panel

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["panel"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        topic, _ = await legacy_topic(interaction)
        choices = await panel_choices(interaction.guild.id, self.panel)
        option = labelled(choices, topic) or {}
        await start_ticket(
            interaction,
            custom_opening_message=option.get("opening_message"),
            closing_message=option.get("closing_message"),
        )


class CreateTicketButtonView(View):
    """Holds one button that opens a ticket."""

    def __init__(
        self,
        title="Create Ticket",
        emoji="🎫",
        color=discord.ButtonStyle.grey,
        *,
        timeout=None,
    ):
        super().__init__(timeout=timeout)
        self.add_item(CreateTicketButton(title, emoji, color))


class PanelSelect(Select):
    """A panel's dropdown: choosing a topic asks the member to confirm it."""

    def __init__(self, placeholder, options):
        super().__init__(
            placeholder=placeholder,
            max_values=1,
            min_values=1,
            options=options,
            custom_id="ticketcreation",
        )

    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        embed = discord.Embed(
            title="Confirm Ticket",
            description=f"Are you sure you want to make a ticket about **{chosen}**?",
            colour=0x4F545B,
        )
        with_author(embed, interaction.user.name, interaction.user.avatar)
        icon = interaction.guild.icon
        embed.set_footer(
            icon_url=icon.url if icon else None,
            text=f"{interaction.guild.name} • #{interaction.channel.name}",
        )
        view = View(timeout=None)
        view.add_item(ConfirmTicketButton(interaction.message.id))
        # A stopped view is sent but not kept, so its expiry cannot unregister the button.
        view.stop()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SelectView(View):
    """Holds a panel's dropdown."""

    def __init__(self, placeholder=None, options=None, *, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(PanelSelect(placeholder, options or []))


def panel_view(editor: TicketPanelEditor):
    """Gives the view a posted panel carries, or None with nothing to offer."""
    if not editor.choices:
        return None
    if editor.panel_type == "dropdown":
        options = [
            discord.SelectOption(
                label=option["label"][:100],
                value=option["label"],
                description=option["description"][:100] or None,
                emoji=option["emoji"] or None,
            )
            for option in editor.options
        ]
        return SelectView("Select a ticket category...", options)
    view = View(timeout=None)
    for index, button in enumerate(editor.buttons):
        style = BUTTON_STYLES.get(button["color"], discord.ButtonStyle.grey)
        kind = ExtraTicketButton if index else CreateTicketButton
        extra = (index,) if index else ()
        view.add_item(kind(button["label"], button["emoji"] or None, style, *extra))
    return view


class CloseTicketButton(View):
    """The red button under a ticket's first message."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close",
        emoji="🔒",
    )
    async def close(self, interaction: discord.Interaction, button: Button):
        await ask_to_close(interaction, None, offer_message=True)


def notice(title: str, description: str) -> discord.Embed:
    """Gives a red embed with the current time on it."""
    return stamped(discord.Embed(title=title, description=description, color=0xFF0000))


async def ask_to_close(interaction, closing_message, offer_message=False):
    """Asks whether to close the ticket, when the channel is an open one."""
    channel = interaction.channel
    if is_closed(channel):
        embed = notice(
            f"Ticket already closed {CLOSED_MARK}", "This ticket is already closed."
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    owner = owner_of(channel)
    if owner is None:
        embed = notice(
            "Invalid Action", "This command can only be used in ticket channels."
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    if closing_message and interaction.user.id == owner:
        return await interaction.response.send_message(
            "Only staff can override the closing message.", ephemeral=True
        )
    view = ConfirmCloseTicketButtons(
        override_closing_message=closing_message,
        ticket_owner_id=owner if offer_message else None,
        interaction_user_id=interaction.user.id,
    )
    embed = notice(
        "Are you sure about that?",
        "Only moderators and administrators can reopen the ticket.",
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def delete_soon(channel) -> None:
    """Deletes a ticket channel after five seconds."""
    await asyncio.sleep(5)
    await channel.delete()
    await remove(f"/Ticket Closing Messages/{channel.id}")


DELETING = ("Deleting Ticket...", "Ticket will be deleted in 5 seconds")


class TicketAdminButtons(View):
    """The staff's buttons under a closed ticket."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Reopen Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="reopen",
        emoji="🔓",
    )
    async def reopen(self, interaction: discord.Interaction, button: Button):
        channel, staff = interaction.channel, interaction.user
        try:
            user = await interaction.client.fetch_user(closed_owner_of(channel))
        except Exception:
            return await interaction.response.send_message(
                "Unable to fetch the user. They probably left the server.",
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        await channel.edit(topic=user.id)
        await channel.set_permissions(
            user, send_messages=True, read_messages=True, attach_files=True
        )
        embed = discord.Embed(title="Ticket Reopened", color=0xFFFF00)
        embed.add_field(name="Ticket Owner", value=f"{user.mention}", inline=True)
        embed.add_field(name="Reopened By", value=f"{staff.mention}", inline=True)
        stamped(with_author(embed, user.name, user.avatar))
        embed.set_footer(text=f"Ticket ID: {channel.id}")
        log = await log_channel(interaction.guild)
        if log:
            await log.send(embed=embed, view=ticket_link(channel))
        embed = discord.Embed(
            title="Ticket Reopened",
            description=f"Your ticket is reopened by {staff.mention}.",
            color=0xE44D41,
        )
        try:
            view = ticket_link(channel, "Head over to your ticket", "🎫")
            await user.send(embed=stamped(embed), view=view)
        except Exception:
            pass
        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=(
                f"Ticket reopened by {staff.mention} and is visible to"
                f" {user.mention} again."
            ),
            color=0xFFFF00,
        )
        await interaction.message.delete()
        await channel.send(embed=stamped(embed), view=CloseTicketButton())
        await interaction.followup.send("Ticket is reopened.", ephemeral=True)

    @discord.ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="delete",
        emoji="✉️",
    )
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.message.delete()
        await interaction.channel.send(embed=notice(*DELETING))
        await delete_soon(interaction.channel)


async def mention_names(interaction, text: str, names: dict) -> str:
    """Swaps user mentions in transcript text for the users' names."""
    result, last_end = "", 0
    for match in re.finditer(r"<@!?([0-9]+)>", text):
        uid = int(match.group(1))
        if uid not in names:
            try:
                names[uid] = (await interaction.client.fetch_user(uid)).name
            except Exception:
                names[uid] = f"user:{uid}"
        result += text[last_end : match.start()]
        result += f"<span class='mention'>@{names[uid]}</span>"
        last_end = match.end()
    return result + text[last_end:]


async def parse_mentions(interaction, text, names=None):
    """Swaps user, role, channel and command mentions for what a browser can show."""

    def replace_role(match):
        rid = int(match.group(1))
        role = interaction.guild.get_role(rid)
        color = f"rgb{role.color.to_rgb()}" if role and role.color else "#ccc"
        name = role.name if role else f"role:{rid}"
        return f"<span style='color: {color};'>@{name}</span>"

    def replace_channel(match):
        cid = int(match.group(1))
        channel = interaction.guild.get_channel(cid)
        name = channel.name if channel else f"channel:{cid}"
        return f"<span class='mention'>#{name}</span>"

    text = await mention_names(interaction, text, {} if names is None else names)
    text = re.sub(r"<@&([0-9]+)>", replace_role, text)
    text = re.sub(r"<#([0-9]+)>", replace_channel, text)
    return re.sub(
        r"</([A-Za-z\- ]+):[0-9]+>", r"<span class='mention'>/\1</span>", text
    )


def parse_markdown(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.*?)__", r"<u>\1</u>", text)
    text = re.sub(r"[\*_](.*?)[\*_]", r"<em>\1</em>", text)
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)
    text = re.sub(r"```(.*?)```", r"<pre><code>\1</code></pre>", text, flags=re.DOTALL)
    text = re.sub(r"^#\s+(.*?)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.*?)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+(.*?)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"-#\s+(.*?)$", r"<small>\1</small>", text, flags=re.MULTILINE)
    text = re.sub(
        r"\|\|(.*?)\|\|", r'<span class="spoiler">\1</span>', text, flags=re.DOTALL
    )

    def replace_timestamp(match):
        timestamp = int(match.group(1))
        style = match.group(2) if match.group(2) else None
        return f"<span class='discord-timestamp' data-timestamp='{timestamp}' data-style='{style}'></span>"

    text = re.sub(r"<t:(\d+)(?::([a-zA-Z]))?>", replace_timestamp, text)

    lines = text.split("\n")
    in_blockquote = False
    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(">"):
            content = re.sub(r"^>\s*", "", stripped)
            if not in_blockquote:
                new_lines.append("<blockquote>")
                in_blockquote = True
            new_lines.append(content)
        else:
            if in_blockquote:
                new_lines.append("</blockquote>")
                in_blockquote = False
            new_lines.append(line)
    if in_blockquote:
        new_lines.append("</blockquote>")
    text = "\n".join(new_lines)

    return text


def transcript_head(interaction, user, messages) -> str:
    """Gives the transcript's facts block and the page up to its first message."""
    iconURL = interaction.guild.icon.url if interaction.guild.icon else DEFAULT_AVATAR
    return (
        f"""<Server-Info>
    Server: {interaction.guild.name} ({interaction.guild.id})
    Channel: #{interaction.channel.name} ({interaction.channel.id})
    Ticket Owner: {user} ({user.id if user else 'Unknown'})
    Messages: {len(messages)}
    Attachments: {sum(1 for message in messages if message.attachments)}

    """
        f"</Server-Info><!DOCTYPE html> <html> <head> <meta name='viewport' content='width=device-width, initial-scale=1.0'> <title>{user}</title> <script data-cfasync='false'> function formatDiscordTimestamps() {{ document.querySelectorAll('.discord-timestamp').forEach(element => {{ const timestamp = parseInt(element.dataset.timestamp); const style = element.dataset.style; const date = new Date(timestamp * 1000); let formatted; switch (style) {{ case 't': formatted = date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'T': formatted = date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true }}); break; case 'd': formatted = date.toLocaleDateString('en-US', {{ month: 'numeric', day: 'numeric', year: 'numeric' }}); break; case 'D': formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}); break; case 'f': formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'F': formatted = date.toLocaleDateString('en-US', {{ weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'R': const now = new Date(); const diff = now - date; const seconds = Math.floor(diff / 1000); const intervals = {{ year: 31536000, month: 2592000, week: 604800, day: 86400, hour: 3600, minute: 60, second: 1 }}; for (const [unit, secondsInUnit] of Object.entries(intervals)) {{ const count = Math.floor(seconds / secondsInUnit); if (count >= 1) {{ formatted = `${{count}} ${{unit}}${{count !== 1 ? 's' : ''}} ago`; break; }} }} break; default: formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); }} element.textContent = formatted; }}); }} function initializeSpoilers() {{ document.querySelectorAll('.spoiler').forEach(spoiler => {{ spoiler.addEventListener('click', () => {{ spoiler.classList.toggle('revealed'); }}); }}); }} window.addEventListener('DOMContentLoaded', () => {{ formatDiscordTimestamps(); initializeSpoilers(); }}); </script> <style> Server-Info {{visibility: hidden}} body {{ background-color: #2c2f33; color: white; font-family: 'Segoe UI', sans-serif; padding: 20px; }} .chat-container {{ max-width: 800px; margin: auto; }} .message {{ display: flex; gap: 12px; }} .message.grouped {{ margin-bottom: 6px; }} .message.not-grouped {{ margin: 20px 0 6px 0; }} .avatar {{ border-radius: 50%; width: 40px; height: 40px; }} .content {{ flex: 1; }} .username {{ font-weight: 600; }} .userid {{ font-size: 0.8em; color: #999; margin-left: 5px; }} .text {{ padding: 2px 0px; white-space: pre-wrap; margin-top: 2px; }} .attachment-img {{ max-width: 300px; border-radius: 6px; margin-top: 6px; }} .media-file {{ background-color: #4f545c; padding: 10px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; color: white; margin-top: 6px; text-decoration: none; }} .embed {{ background-color: #2f3136; padding: 10px 15px; border-left: 6px solid #7289da; border-radius: 8px; margin-top: 6px; }} .embed-title {{ font-weight: bold; color: white; }} .embed-description {{ color: #ccc; font-size: 0.95em; }} .header-container {{ display: flex; gap: 20px; margin-bottom: 30px; align-items: center; }} .header-container img {{ width: 80px; border-radius: 20px; }} .header-info div {{ margin-bottom: 5px; }} .app-badge {{ display: inline-flex; align-items: center; background-color: #5a5df0; color: white; font-weight: 600; font-family: sans-serif; border-radius: 5px; padding: 2px 8px; font-size: 12px; margin-left: 4px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }} .mention {{ background-color: rgb(65,68,112); color: rgb(183,195,234); padding: 2px 4px; border-radius: 3px; font-weight: 500; }} .embed-fields {{ margin-top: 10px; display: flex; flex-direction: column; gap: 10px;}} .embed-field {{ background-color: rgba(255, 255, 255, 0.05); padding: 8px 12px; border-radius: 6px; }} .embed-field-name {{ font-weight: bold; color: #fff; margin-bottom: 4px; font-size: 0.95em; }} .embed-field-value {{ color: #ccc; font-size: 0.95em; white-space: pre-wrap; }} blockquote {{ border-left: 3px solid rgb(101, 101, 108); padding-left: 10px; margin-left: 5px; color: #dcddde; }} .spoiler {{ position: relative; cursor: pointer; display: inline-block; }} .spoiler::after {{ content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(101, 101, 108); border-radius: 3px; transition: opacity 0.2s; }} .spoiler.revealed::after {{ opacity: 0; }} </style> </head> <body> <div class='chat-container'> <div class='header-container'> <img src='{iconURL}' /> <div class='header-info'> <div><strong>Server:</strong> {interaction.guild.name} ({interaction.guild.id})</div> <div><strong>Channel:</strong> #{interaction.channel.name} ({interaction.channel.id})</div> <div><strong>Ticket Owner:</strong> {user} ({user.id if user else 'Unknown'})</div> </div> </div>"
    )


IMAGE_ENDINGS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
VIDEO_ENDINGS = (".mp4", ".mov", ".webm", ".mkv")
AUDIO_ENDINGS = (".mp3", ".wav", ".ogg", ".m4a")
FILE_ICON = "https://cdn.discordapp.com/attachments/1026904121237831700/1129787805381423265/file.png"


def attachment_html(attachment) -> str:
    """Gives one attachment as the page shows it."""
    name = attachment.filename.lower()
    if name.endswith(IMAGE_ENDINGS):
        return f'<img class="attachment-img" src="{attachment.url}" />'
    if name.endswith(VIDEO_ENDINGS):
        return f'<video class="attachment-media" controls> <source src="{attachment.url}" type="video/mp4"> Your browser doesn\'t support embedded videos. </video>'
    if name.endswith(AUDIO_ENDINGS):
        return f'<audio class="attachment-media" controls> <source src="{attachment.url}" type="audio/mpeg"> Your browser doesn\'t support embedded audio. </audio>'
    return f"<a href='{attachment.url}' download class='media-file'> <img src='{FILE_ICON}' height='20'> <span>{attachment.filename}</span> </a>"


async def embed_html(interaction, embed, names) -> str:
    """Gives one embed as the page shows it; nothing for an embed without text."""
    if not (embed.title or embed.description or embed.fields):
        return ""
    color = embed.color if embed.color else "#7289da"
    html = f"<div class='embed' style='border-left-color: {color};'>"
    if embed.title:
        html += f"<div class='embed-title'>{embed.title}</div>"
    if embed.description:
        text = await parse_mentions(
            interaction, parse_markdown(embed.description), names
        )
        html += f"<div class='embed-description'>{text}</div>"
    if embed.fields:
        html += "<div class='embed-fields'>"
        for field in embed.fields:
            value = await parse_mentions(
                interaction, parse_markdown(field.value), names
            )
            html += "<div class='embed-field'>"
            html += f"<div class='embed-field-name'>{parse_markdown(field.name)}</div>"
            html += f"<div class='embed-field-value'>{value}</div>"
            html += "</div>"
        html += "</div>"
    return html + "</div>"


async def message_html(interaction, msg, grouped: bool, names) -> str:
    """Gives one message as the page shows it."""
    author = msg.author
    avatar = author.avatar.url if getattr(author, "avatar", None) else DEFAULT_AVATAR
    color = author.color if hasattr(author, "color") else "#dfe0e2"
    if grouped:
        html = "<div class='message grouped'><div style='width: 40px;'></div>"
        html += "<div class='content'>"
    else:
        html = f"<div class='message not-grouped'><img class='avatar' src='{avatar}' />"
        html += "<div class='content'>"
        html += (
            f"<div><span class='username' style='color: {color};'>{author.name}</span>"
        )
        if getattr(author, "bot", False):
            html += "<div class='app-badge' data-toggle='tooltip' title='Verified Bot'>BOT</div>"
        html += f"<code class='userid'>({author.id})</code></div>"
    if msg.content:
        text = await parse_mentions(interaction, parse_markdown(msg.content), names)
        html += f"<div class='text'>{text}</div>"
    for attachment in msg.attachments:
        html += attachment_html(attachment)
    for embed in msg.embeds:
        html += await embed_html(interaction, embed, names)
    return html + "</div></div>"


async def get_transcript(interaction, user):
    """Gives the ticket's history as a web page, who wrote in it and how often."""
    messages = [message async for message in interaction.channel.history(limit=None)]
    parts = [transcript_head(interaction, user, messages)]
    counts = defaultdict(int)
    names = {}
    last_author = None
    for msg in reversed(messages):
        if msg.author != interaction.client.user:
            counts[msg.author] += 1
        grouped = last_author == msg.author.id
        parts.append(await message_html(interaction, msg, grouped, names))
        last_author = msg.author.id
    parts.append("</div></body></html>")
    return "".join(parts), list(counts), counts


SUMMARY_PROMPT = (
    "The following is the entire history of the ticket in a Discord server for a user. "
    "Please summarise the entire interaction into 1 sentence. "
    "Only give 1 response option. Do not output additional text such as 'Here is the summary:'. "
    "Do not include any metadata or user info. Only focus on the conversation content.\n\n"
    "Full transcript:\n"
)
CONFIRMED = f"{YES} **Ticket Closure Confirmed**"


async def summary_of(page: str) -> str:
    """Gives the AI's one-sentence summary of a transcript."""
    try:
        return await generate(SUMMARY_PROMPT + page.split("<!DOCTYPE html>")[1])
    except Exception as error:
        print(error)
        return "`AI Summary Temporarily Unavailable`"


async def ticket_topic(channel):
    """Gives the title of the embed a ticket starts with."""
    async for first in channel.history(limit=1, oldest_first=True):
        return first.embeds[0].title if first.embeds else None
    return None


def closed_log(interaction, user, involved, counts) -> discord.Embed:
    """Gives the log entry for a closed ticket, before its topic, link and summary."""
    closer = interaction.user.mention
    if user:
        embed = discord.Embed(
            title="Ticket closed",
            description=f"Ticket created by {user.mention} is closed by {closer}",
            color=0xE44D41,
        )
        with_author(embed, user.name, user.avatar)
        embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
    else:
        embed = discord.Embed(
            title="Ticket closed",
            description=(
                "Ticket created by a member who has left the server is closed by"
                f" {closer}"
            ),
            color=0xE44D41,
        )
    people = "\n".join(f"- {one.mention} `({counts[one]})`" for one in involved)
    embed.add_field(name="Users Involved", value=people or "`None`", inline=True)
    return stamped(embed)


async def log_closure(interaction, embed, page: str):
    """Posts the transcript to the server's log and the global one; gives its link."""
    data = page.encode("utf-8")
    name = f"{interaction.channel.id}.html"
    summary = await summary_of(page)
    embed.add_field(name="Ticket Topic", value=await ticket_topic(interaction.channel))
    log = await log_channel(interaction.guild)
    url = None
    if log:
        sent = await log.send(embed=embed, file=discord.File(io.BytesIO(data), name))
        checksum = hashlib.sha256(data + str(log.id).encode()).hexdigest()[:20]
        url = f"https://fischl.app/logs/{log.id}-{sent.id}-{checksum}"
        embed.add_field(name="Transcript Link", value=url, inline=False)
    embed.add_field(name="Ticket Summary", value=summary)
    if log:
        await sent.edit(embed=embed)
    embed.title = f"Ticket closed in {interaction.guild.name}"
    await send_global_log(
        interaction.client, embed, file=discord.File(io.BytesIO(data), name)
    )
    return url


async def tell_owner(interaction, user, closing_message, view) -> None:
    """Tells the ticket's owner it is closed and takes the channel away from them."""
    guild = interaction.guild
    embed = discord.Embed(
        title="Ticket Closed",
        description=f"Your ticket in **{guild.name}** is now closed.",
        color=0xE44D41,
    )
    embed.set_footer(
        text="You can always create a new ticket for additional assistance!"
    )
    if closing_message:
        embed.description += f"\n\n> {closing_message}"
    try:
        await user.send(embed=stamped(embed), view=view)
    except Exception:
        pass
    try:
        await interaction.channel.set_permissions(
            user, send_messages=False, read_messages=False, attach_files=False
        )
    except Exception:
        pass


async def perform_ticket_close(interaction: discord.Interaction, closing_message=None):
    """Closes the ticket once, however many confirmations arrive together."""
    channel = interaction.channel
    if channel.id in closing or is_closed(channel):
        return
    closing.add(channel.id)
    try:
        await close_ticket(interaction, closing_message)
    finally:
        closing.discard(channel.id)


async def close_ticket(interaction: discord.Interaction, closing_message=None):
    """Closes the ticket: transcript, logs, a DM to its owner and the staff panel."""
    channel = interaction.channel
    farewell = await channel.send(
        embed=notice("Closing Ticket...", "Ticket will be closed in 3 seconds")
    )
    try:
        user = await interaction.client.fetch_user(owner_of(channel))
    except Exception:
        user = None
    page, involved, counts = await get_transcript(interaction, user)
    embed = closed_log(interaction, user, involved, counts)
    url = await log_closure(interaction, embed, page)
    if closing_message is None:
        closing_message = await read(f"/Ticket Closing Messages/{channel.id}")
    if user:
        view = link_view("Transcript Link", url, "📜") if url else View()
        await tell_owner(interaction, user, closing_message, view)
    await farewell.delete()
    closer = interaction.user.mention
    if user:
        embed = discord.Embed(
            description=(
                f"Ticket is closed by {closer} and no longer visible to {user.mention}."
            ),
            color=0xE44D41,
        )
        if closing_message:
            embed.add_field(name="Closing Message", value=closing_message, inline=False)
            embed.title = "Ticket Closed"
    else:
        embed = discord.Embed(
            description="Member left the server. Ticket is still closed.",
            color=0xE44D41,
        )
    await channel.send(embed=embed)
    embed = discord.Embed(
        title="", description="""```STAFF CONTROLS PANEL```""", color=0xE44D41
    )
    view = TicketAdminButtons()
    if url:
        view.add_item(
            Button(
                style=discord.ButtonStyle.link,
                label="Transcript Link",
                emoji="📜",
                url=url,
            )
        )
    await channel.send(embed=embed, view=view)
    await channel.edit(topic=f"{CLOSED_MARK} {channel.topic}")


def confirmed() -> discord.Embed:
    """Gives the green line shown once a closure is confirmed."""
    return discord.Embed(description=CONFIRMED, color=discord.Color.green())


class ClosingMessageModal(Modal):
    """Asks staff for the message the owner gets with the closure."""

    def __init__(self):
        super().__init__(title="Set Closing Message")
        self.add_item(
            TextInput(
                label="Closing Message",
                placeholder="Enter a message to send when closing the ticket",
                style=discord.TextStyle.paragraph,
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=confirmed(), view=None)
        await perform_ticket_close(interaction, self.children[0].value)


class SetClosingMessageButton(Button):
    """Lets staff close the ticket with a message of their own."""

    def __init__(self):
        super().__init__(label="Set Closing Message", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ClosingMessageModal())


class ConfirmCloseTicketButtons(View):
    """Asks whether the ticket should really be closed."""

    def __init__(
        self,
        override_closing_message=None,
        ticket_owner_id=None,
        interaction_user_id=None,
    ):
        super().__init__(timeout=None)
        self.override_closing_message = override_closing_message
        staff = ticket_owner_id is not None and interaction_user_id is not None
        if staff and interaction_user_id != ticket_owner_id:
            self.add_item(SetClosingMessageButton())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="yes")
    async def yes(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=confirmed(), view=None)
        await perform_ticket_close(interaction, self.override_closing_message)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, custom_id="no")
    async def red(self, interaction: discord.Interaction, button: Button):
        embed = notice(
            "Action Cancelled",
            f"Alright {interaction.user.mention}! I will not close the ticket!",
        )
        await interaction.response.edit_message(embed=embed, view=None)


INVALID_CHANNEL = f"{NO} This is not a valid ticket channel."
SETUP_HINT = "Please use `/ticket settings` to setup tickets first!"


async def snippet_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Offers the server's snippet aliases that hold what was typed."""
    snippets = await read(f"/Ticket Snippets/{interaction.guild.id}") or {}
    return [
        app_commands.Choice(name=alias, value=alias)
        for alias in snippets
        if current.lower() in alias.lower()
    ][:25]


async def panel_command(cog, interaction: discord.Interaction, panel_type: str):
    """Shows the server's saved panels of one type to edit, or start a new one."""
    view = PanelSelectView(cog, panel_type)
    await view.load_panels(interaction.guild_id)
    embed = discord.Embed(
        title=f"{panel_type.title()} Ticket Panels",
        description="Choose an existing panel to edit or create a new one.",
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def answer_error(interaction: discord.Interaction, error: Exception) -> None:
    """Shows a failed command's error to the one who used it."""
    text = f"```{str(error)}```"
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


@app_commands.guild_only()
class Ticket(commands.GroupCog, name="ticket"):
    """The /ticket commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    async def cog_app_command_error(self, interaction, error):
        await answer_error(interaction, error)

    @app_commands.command(
        name="notify",
        description="Send a DM to ticket author requiring their attention",
    )
    @app_commands.describe(message="Optional message to be included in the DMs")
    async def ticket_notify(
        self, interaction: discord.Interaction, message: str = None
    ) -> None:
        channel, guild = interaction.channel, interaction.guild
        message = " " if message is None else f"\n\n> {message}"
        try:
            user = await interaction.client.fetch_user(owner_of(channel))
        except Exception:
            return await interaction.response.send_message(
                INVALID_CHANNEL, ephemeral=True
            )
        if interaction.user.id == user.id:
            return await interaction.response.send_message(
                f"{NO} You cannot notify yourself!", ephemeral=True
            )
        embed = discord.Embed(
            title="⚠️ Notification ⚠️",
            description=(
                f"The ticket you created in **{guild.name}** needs your attention!"
                f" Please kindly respond.{message}\n\nIf you no longer need assistance"
                " or your issue has been resolved, **please still let us know in the"
                " ticket** so we can help close the ticket."
            ),
            color=0xE44D41,
        )
        try:
            view = ticket_link(channel, "Head over to your ticket", "🎫")
            await user.send(embed=stamped(embed), view=view)
        except Exception:
            return await interaction.response.send_message(
                f"{NO} Unable to DM user!", ephemeral=True
            )
        await interaction.response.send_message(
            f"{user.mention} received a DM notification."
        )

    @app_commands.command(
        name="delete", description="Deletes an existing ticket channel"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_delete(self, interaction: discord.Interaction) -> None:
        if closed_owner_of(interaction.channel) is None:
            embed = notice(
                "Invalid Action",
                "This command can only be used in ticket channels, or this ticket has"
                " not been closed.",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.response.send_message(embed=notice(*DELETING))
        await delete_soon(interaction.channel)

    @app_commands.command(
        name="close",
        description="Closes the current ticket and prevents ticket author from viewing the ticket",
    )
    @app_commands.describe(
        closing_message="Optional custom closing message (staff only)"
    )
    async def ticket_close(
        self, interaction: discord.Interaction, closing_message: str = None
    ) -> None:
        await ask_to_close(interaction, closing_message)

    @app_commands.command(
        name="dropdown",
        description="Create or edit dropdown ticket panels with advanced customization",
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_dropdown(self, interaction: discord.Interaction) -> None:
        await panel_command(self, interaction, "dropdown")

    @app_commands.command(
        name="button",
        description="Create or edit button ticket panels with advanced customization",
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_button(self, interaction: discord.Interaction) -> None:
        await panel_command(self, interaction, "button")

    @app_commands.command(
        name="add", description="Add a user to the current ticket (Mods only)"
    )
    @app_commands.describe(user="User to add to channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        channel = interaction.channel
        owner_id = owner_of(channel)
        if owner_id is None:
            return await interaction.response.send_message(
                INVALID_CHANNEL, ephemeral=True
            )
        await channel.set_permissions(user, read_messages=True, send_messages=True)
        embed = discord.Embed(
            description=f"{user.mention} has been added to this ticket.", color=0x00FF00
        )
        await interaction.response.send_message(embed=embed)
        log = await log_channel(interaction.guild)
        if not log:
            return
        try:
            owner = await interaction.client.fetch_user(owner_id)
            whose = f"{owner.mention}'s ticket."
        except Exception:
            whose = "a ticket created by someone who left the server."
        embed = discord.Embed(
            title="User Added",
            description=(
                f"{user.mention} was added by {interaction.user.mention} to {whose}"
            ),
            color=0x6B9F6B,
        )
        embed.set_footer(text=f"Ticket ID: {channel.id}")
        await log.send(embed=embed, view=ticket_link(channel))

    @app_commands.command(
        name="create",
        description="Create a ticket for a user (Mods only, bypasses cooldown & blacklist)",
    )
    @app_commands.describe(user="Specify a user")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_create(
        self, interaction: discord.Interaction, user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild, staff = interaction.guild, interaction.user
        _, config = await server_config(guild.id)
        category = guild.get_channel(config["Category ID"]) if config else None
        if not category:
            return await interaction.followup.send(
                embed=not_enabled(SETUP_HINT), ephemeral=True
            )
        existing = ticket_of(category, user.id)
        if existing:
            return await interaction.followup.send(
                content=(
                    f"{NO} {user.mention} already has their ticket created at"
                    f" <#{existing.id}>."
                ),
                ephemeral=True,
            )
        key = (guild.id, user.id)
        if key in opening:
            return await interaction.followup.send(
                f"{NO} {user.mention}'s ticket is already being created.",
                ephemeral=True,
            )
        opening.add(key)
        try:
            channel = await open_channel(guild, category, user, f"{user.name}")
        except Exception:
            return await interaction.followup.send(
                content=MISSING_PERMISSIONS, ephemeral=True
            )
        finally:
            opening.discard(key)
        embed = discord.Embed(
            title="Ticket created",
            description=(
                f"Staff {staff.mention} created a new ticket for {user.mention}"
                f" <t:{int(now().timestamp())}:R>!"
            ),
            color=discord.Colour.green(),
        )
        embed.add_field(name="Ticket Topic", value="Created by server staff")
        stamped(with_author(embed, user.name, staff.avatar))
        embed.set_footer(text=f"Ticket ID: {channel.id}")
        log = guild.get_channel(config["Log Channel ID"])
        if log:
            await log.send(embed=embed, view=ticket_link(channel))
        embed.title = f"Ticket created in {guild.name}"
        await send_global_log(interaction.client, embed)
        first = discord.Embed(
            title="New Ticket",
            description=(
                f"This ticket is created *by {staff.mention}* for {user.mention}!"
                f" \n{CLOSE_HINT}"
            ),
            color=discord.Colour.gold(),
        )
        ping = STAFF_PING if guild.id == STAFF_PING_SERVER else ""
        await channel.send(
            f"**{user.mention}, welcome!** {ping}",
            embed=user_fields(stamped(first), user, channel),
            view=CloseTicketButton(),
        )
        try:
            await user.send(
                f":warning: A staff in **{guild.name}** has created a ticket for you"
                f" and requires your attention.\n{REPLY} <#{channel.id}>"
            )
            status = "and the user is notified via DM"
        except Exception:
            status = "but I'm unable to DM the user"
        await interaction.followup.send(
            content=(
                f"{YES} Ticket for {user.mention} created at <#{channel.id}> {status}"
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="snippet", description="Send a prewritten snippet response in the ticket"
    )
    @app_commands.describe(
        alias="The snippet alias to send",
        anonymous="Remove author from the embed (default: False)",
        ping="Ping the ticket creator (default: False)",
    )
    @app_commands.autocomplete(alias=snippet_autocomplete)
    async def ticket_snippet(
        self,
        interaction: discord.Interaction,
        alias: str,
        anonymous: bool = False,
        ping: bool = False,
    ) -> None:
        channel, user = interaction.channel, interaction.user
        owner_id = owner_of(channel)
        refused = None
        if (getattr(channel, "topic", None) or "").startswith(CLOSED_MARK):
            refused = "This ticket is closed and cannot send snippets!"
        elif owner_id is None:
            refused = "This command can only be used in ticket channels!"
        elif owner_id == user.id:
            refused = "You cannot use this command in your own ticket!"
        if refused:
            return await interaction.response.send_message(refused, ephemeral=True)
        snippets = await read(f"/Ticket Snippets/{interaction.guild.id}") or {}
        response = snippets.get(alias)
        if not response:
            return await interaction.response.send_message(
                f"Snippet '{alias}' not found!", ephemeral=True
            )
        embed = discord.Embed(color=discord.Color.gold())
        if not anonymous:
            embed.set_author(
                name=f"Sent by {user.name}",
                icon_url=user.avatar.url if user.avatar else None,
            )
        content = (f"<@{owner_id}> " if ping else "") + response
        await channel.send(content=content, embed=embed)
        await interaction.response.send_message(
            f"Snippet '{alias}' sent successfully!", ephemeral=True
        )

    @app_commands.command(
        name="settings", description="Configure all ticket settings in one place"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_settings(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        _, config = await server_config(interaction.guild.id)
        view = TicketSettingsView(self.bot, interaction, config)
        await view.update_message()


UNITS = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
BAD_KEY = re.compile(r"[.$#\[\]/]")
FIELD_LIMIT = 1024
SETTINGS_INTRO = (
    "Configure all aspects of your ticket system below. "
    "Use the dropdown menus and buttons to modify settings.\n\n"
    "**Need help?** Join our [support server](https://discord.gg/BXkc8CC4uJ) for"
    " assistance!"
)
DISABLED_INTRO = (
    "The ticket system is currently **disabled**. "
    "Click the **Enable System** button below to get started! "
    "This will create the necessary category and log channel for tickets."
    "You can always change the channels and settings later."
)
PANEL_COMMANDS = (
    "- </ticket dropdown:1254927191129456641> - Create or edit dropdown ticket"
    " panels\n"
    "- </ticket button:1254927191129456641> - Create or edit button ticket panels"
)
DISABLE_WARNING = (
    "Are you sure you want to disable the ticket system? This will:\n\n"
    "- Remove all ticket configuration\n"
    "- Keep existing ticket channels (you'll need to delete them manually)\n"
    "- Clear all saved panels and settings\n\n"
    "**This action cannot be undone!**"
)
# What a server keeps besides its settings record; all of it goes when tickets are disabled.
SERVER_PATHS = (
    "Ticket Panels",
    "Ticket Blacklist",
    "Ticket Instructions",
    "Ticket Snippets",
    "Tickets Cooldown",
)


def cooldown_parts(seconds: int) -> list:
    """Splits seconds into parts like 1d, 2h, 30m and 5s, leaving out the empty ones."""
    parts = []
    for letter, size in UNITS:
        count, seconds = divmod(seconds, size)
        if count > 0:
            parts.append(f"{count}{letter}")
    return parts


def cooldown_seconds(text: str) -> int:
    """Reads a duration like 1d2h30m into seconds."""
    total = 0
    for letter, size in UNITS:
        found = re.search(rf"(\d+){letter}", text)
        if found:
            total += int(found.group(1)) * size
    return total


class TicketSettingsView(View):
    """The /ticket settings screen."""

    def __init__(self, bot, interaction: discord.Interaction, server_config=None):
        super().__init__(timeout=SETTINGS_TIMEOUT)
        self.bot = bot
        self.interaction = interaction
        self.server_config = server_config
        config, guild = server_config or {}, interaction.guild
        self.selected_category = guild.get_channel(config.get("Category ID") or 0)
        self.selected_log_channel = guild.get_channel(config.get("Log Channel ID") or 0)
        self.selected_ping_role = guild.get_role(config.get("Ping Role ID") or 0)

    def picker(self, kind, chosen, save, **options):
        """Adds a channel or role select that shows what is chosen now."""
        select = kind(**options)
        if chosen:
            select.default_values = [chosen]
        select.callback = save
        self.add_item(select)

    def fill(self) -> None:
        """Puts the controls on the view: one button with tickets off, all with them on."""
        self.clear_items()
        if not self.server_config:
            return self.add_item(EnableSystemButton())
        self.picker(
            ChannelSelect,
            self.selected_category,
            self.select_category,
            placeholder="Select ticket category...",
            channel_types=[discord.ChannelType.category],
            custom_id="category_select",
        )
        self.picker(
            ChannelSelect,
            self.selected_log_channel,
            self.select_log_channel,
            placeholder="Select log channel...",
            channel_types=[discord.ChannelType.text],
            custom_id="log_select",
        )
        self.picker(
            RoleSelect,
            self.selected_ping_role,
            self.select_ping_role,
            placeholder="Select ping role (optional)...",
            custom_id="role_select",
        )
        for button in (
            CooldownButton,
            RoleAccessButton,
            BlacklistButton,
            SnippetsButton,
            DisableSystemButton,
        ):
            self.add_item(button())

    async def update_message(self, interaction: discord.Interaction = None):
        embed = await self.create_settings_embed()
        self.fill()
        if interaction is None:
            await self.interaction.edit_original_response(embed=embed, view=self)
        elif interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def create_settings_embed(self) -> discord.Embed:
        """Gives the screen's embed: an invitation with tickets off, the settings with them on."""
        if not self.server_config:
            return discord.Embed(
                title="🎫 Ticket System Settings",
                description=DISABLED_INTRO,
                color=discord.Color.orange(),
            )
        embed = discord.Embed(
            title="🎫 Ticket System Settings",
            description=SETTINGS_INTRO,
            color=discord.Color.blue(),
        )
        guild_id = self.interaction.guild.id
        panels = await read(f"/Ticket Panels/{guild_id}") or {}
        blacklisted = await read(f"/Ticket Blacklist/{guild_id}") or {}
        category, log = self.selected_category, self.selected_log_channel
        role = self.selected_ping_role
        cooldown = self.format_cooldown(self.server_config.get("Cooldown", 0))
        embed.add_field(
            name="📁 Current Configuration",
            value=(
                f"-# - **Category:** {category.name if category else 'Not set'}\n"
                f"-# - **Log Channel:** {log.mention if log else 'Not set'}\n"
                f"-# - **Ping Role:** {role.mention if role else 'Not set'}\n"
                f"-# - **Cooldown:** {cooldown}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📊 System Stats",
            value=(
                f"-# - **Dropdown Panels:** `{len(panels.get('dropdown') or {})}`\n"
                f"-# - **Button Panels:** `{len(panels.get('button') or {})}`\n"
                f"-# - **Access Roles:** `{len(self.get_access_roles())}`\n"
                f"-# - **Blacklisted Users:** `{len(blacklisted)}`"
            ),
            inline=True,
        )
        embed.add_field(name="🔧 Panel Commands", value=PANEL_COMMANDS, inline=False)
        return embed

    def format_cooldown(self, seconds) -> str:
        """Gives a cooldown as words."""
        return ", ".join(cooldown_parts(seconds)) or "No cooldown"

    def get_access_roles(self) -> list:
        """Gives the roles that can read the ticket category."""
        category, guild = self.selected_category, self.interaction.guild
        if not category:
            return []
        return [
            role
            for role in guild.roles
            if role != guild.default_role
            and category.permissions_for(role).read_messages
        ]

    async def select_category(self, interaction: discord.Interaction):
        chosen = interaction.guild.get_channel(int(interaction.data["values"][0]))
        if not chosen:
            return await interaction.response.send_message(
                "Category not found.", ephemeral=True
            )
        self.selected_category = chosen
        await self.update_database_setting("Category ID", chosen.id)
        await self.update_message(interaction)

    async def select_log_channel(self, interaction: discord.Interaction):
        chosen = interaction.guild.get_channel(int(interaction.data["values"][0]))
        if not chosen:
            return await interaction.response.send_message(
                "Log channel not found.", ephemeral=True
            )
        self.selected_log_channel = chosen
        await self.update_database_setting("Log Channel ID", chosen.id)
        await self.update_message(interaction)

    async def select_ping_role(self, interaction: discord.Interaction):
        chosen = interaction.guild.get_role(int(interaction.data["values"][0]))
        if not chosen:
            return await interaction.response.send_message(
                "Role not found.", ephemeral=True
            )
        self.selected_ping_role = chosen
        await self.update_database_setting("Ping Role ID", chosen.id)
        await self.update_message(interaction)

    async def update_database_setting(self, name, value) -> None:
        """Saves one setting, here and in the database."""
        if not self.server_config:
            return
        self.server_config[name] = value
        key, _ = await server_config(self.interaction.guild.id)
        if key:
            await write(f"/Tickets/{key}/{name}", value)
        else:
            self.server_config = None


def push_config(data: dict) -> None:
    """Stores a new server's settings."""
    db.reference("/Tickets").push().set(data)


class EnableSystemButton(Button):
    """Makes the ticket category and log channel and turns tickets on."""

    def __init__(self):
        super().__init__(
            label="Enable System", style=discord.ButtonStyle.green, emoji="✅"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild, me = interaction.guild, interaction.client.user
        _, data = await server_config(guild.id)
        if not data:
            category = await guild.create_category("Tickets")
            log = await guild.create_text_channel("ticket-logs", category=category)
            for channel in (category, log):
                await channel.set_permissions(
                    me, read_messages=True, manage_channels=True
                )
            for channel in (category, log):
                await channel.set_permissions(guild.default_role, read_messages=False)
            data = {
                "Server Name": guild.name,
                "Server ID": guild.id,
                "Category ID": category.id,
                "Log Channel ID": log.id,
                "Ping Role ID": None,
                "Cooldown": 0,
            }
            await asyncio.to_thread(push_config, data)
        view = TicketSettingsView(self.view.bot, self.view.interaction, data)
        await view.update_message(interaction)


class CooldownModal(Modal):
    """Asks how long a member waits between two tickets."""

    def __init__(self, settings):
        super().__init__(title="Set Cooldown")
        self.settings = settings
        current = settings.server_config.get("Cooldown", 0)
        self.add_item(
            TextInput(
                label="Cooldown Duration",
                placeholder="Example: 1d2h30m (1 day, 2 hours, 30 minutes)",
                default="".join(cooldown_parts(current)),
                required=False,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        seconds = cooldown_seconds(self.children[0].value.strip())
        await self.settings.update_database_setting("Cooldown", seconds)
        await self.settings.update_message(interaction)


class CooldownButton(Button):
    """Opens the cooldown question."""

    def __init__(self):
        super().__init__(
            label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰", row=3
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CooldownModal(self.view))


class DisableSystemButton(Button):
    """Asks before turning tickets off."""

    def __init__(self):
        super().__init__(label="Disable System", style=discord.ButtonStyle.red, row=4)

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Caution", description=DISABLE_WARNING, color=discord.Color.red()
        )
        view = ConfirmDisableView(self.view)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmDisableView(View):
    """Turns tickets off for the server, or goes back."""

    def __init__(self, parent_view):
        super().__init__(timeout=60)
        self.parent_view = parent_view

    @discord.ui.button(label="Yes, Disable System", style=discord.ButtonStyle.danger)
    async def confirm_disable(self, interaction: discord.Interaction, button: Button):
        parent, guild_id = self.parent_view, interaction.guild.id
        key, _ = await server_config(guild_id)
        paths = [f"/{path}/{guild_id}" for path in SERVER_PATHS]
        if key:
            paths.append(f"/Tickets/{key}")
        await asyncio.gather(*map(remove, paths))
        view = TicketSettingsView(parent.bot, parent.interaction, None)
        await view.update_message(interaction)

    @discord.ui.button(label="No, Go Back", style=discord.ButtonStyle.secondary)
    async def cancel_disable(self, interaction: discord.Interaction, button: Button):
        await self.parent_view.update_message(interaction)


class BackToSettingsButton(Button):
    """Goes back to the settings screen."""

    def __init__(self):
        super().__init__(
            label="Back to Settings", style=discord.ButtonStyle.gray, emoji="↩️"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.parent_view.update_message(interaction)


class SubSettingsView(View):
    """A screen reached from the settings screen."""

    def __init__(self, bot, interaction, parent_view):
        super().__init__(timeout=SETTINGS_TIMEOUT)
        self.bot = bot
        self.interaction = interaction
        self.parent_view = parent_view


async def chosen_or_ask(interaction, chosen, what: str):
    """Gives what was chosen in the select; asks for a choice when nothing was."""
    if not chosen:
        await interaction.response.send_message(
            f"Please select a {what} first!", ephemeral=True
        )
    return chosen


class RoleAccessView(SubSettingsView):
    """Shows which roles see tickets, and gives or takes that access."""

    selected_role = None

    async def show_role_access(self, interaction: discord.Interaction):
        roles = self.parent_view.get_access_roles()
        embed = discord.Embed(
            title="👥 Role Access Management",
            description="Manage which roles can view and manage tickets.",
            color=discord.Color.blue(),
        )
        listed = "\n".join(f"- {role.mention}" for role in roles)
        embed.add_field(
            name="Current Access Roles",
            value=shortened(listed) or "No roles configured",
            inline=False,
        )
        self.clear_items()
        select = RoleSelect(placeholder="Select a role...")
        select.callback = self.select_role
        self.add_item(select)
        self.add_item(GrantAccessButton())
        self.add_item(RemoveAccessButton())
        self.add_item(BackToSettingsButton())
        await interaction.response.edit_message(embed=embed, view=self)

    async def select_role(self, interaction: discord.Interaction):
        role_id = int(interaction.data["values"][0])
        self.selected_role = interaction.guild.get_role(role_id)
        await interaction.response.defer()

    async def set_access(self, interaction: discord.Interaction, **permissions):
        """Changes what the chosen role may do in the ticket category."""
        role = await chosen_or_ask(interaction, self.selected_role, "role")
        if not role:
            return
        category = self.parent_view.selected_category
        if category:
            await category.set_permissions(role, **permissions)
        await self.show_role_access(interaction)


def shortened(lines: str) -> str:
    """Cuts a list at the last whole line that fits in an embed field."""
    if len(lines) <= FIELD_LIMIT:
        return lines
    return lines[: lines.rfind("\n", 0, FIELD_LIMIT - 3)] + "\n..."


class GrantAccessButton(Button):
    """Lets the chosen role see and manage tickets."""

    def __init__(self):
        super().__init__(
            label="Grant Access", style=discord.ButtonStyle.green, emoji="✅"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.set_access(
            interaction,
            read_messages=True,
            send_messages=True,
            manage_messages=True,
            read_message_history=True,
        )


class RemoveAccessButton(Button):
    """Takes the chosen role's ticket access away."""

    def __init__(self):
        super().__init__(
            label="Remove Access", style=discord.ButtonStyle.red, emoji="❌"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.set_access(interaction, read_messages=None, send_messages=None)


class RoleAccessButton(Button):
    """Opens the role access screen."""

    def __init__(self):
        super().__init__(
            label="Role Access", style=discord.ButtonStyle.secondary, emoji="👥", row=3
        )

    async def callback(self, interaction: discord.Interaction):
        view = RoleAccessView(self.view.bot, interaction, self.view)
        await view.show_role_access(interaction)


class BlacklistView(SubSettingsView):
    """Shows who may not open tickets, and adds or removes members."""

    selected_user = None

    async def show_blacklist(self, interaction: discord.Interaction):
        blacklisted = await read(f"/Ticket Blacklist/{interaction.guild.id}") or {}
        embed = discord.Embed(
            title="🚫 Blacklist Management",
            description="Manage users who are blocked from creating tickets.",
            color=discord.Color.blue(),
        )
        users = [f"- <@{user_id}> ({user_id})" for user_id in blacklisted]
        embed.add_field(
            name="Blacklisted Users",
            value="\n".join(users[:10]) or "No users blacklisted",
            inline=False,
        )
        if len(users) > 10:
            embed.add_field(
                name="...", value=f"Plus {len(users) - 10} more users", inline=False
            )
        self.clear_items()
        select = UserSelect(placeholder="Select a user...")
        select.callback = self.select_user
        self.add_item(select)
        self.add_item(BlacklistUserButton())
        self.add_item(UnblacklistUserButton())
        self.add_item(BackToSettingsButton())
        await interaction.response.edit_message(embed=embed, view=self)

    async def select_user(self, interaction: discord.Interaction):
        self.selected_user = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def set_blacklisted(self, interaction: discord.Interaction, blocked: bool):
        """Puts the chosen member on the blacklist or takes them off."""
        user_id = await chosen_or_ask(interaction, self.selected_user, "user")
        if not user_id:
            return
        path = f"/Ticket Blacklist/{interaction.guild.id}/{user_id}"
        await (write(path, True) if blocked else remove(path))
        await self.show_blacklist(interaction)


class BlacklistUserButton(Button):
    """Stops the chosen member from opening tickets."""

    def __init__(self):
        super().__init__(
            label="Blacklist User", style=discord.ButtonStyle.red, emoji="🔨"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.set_blacklisted(interaction, True)


class UnblacklistUserButton(Button):
    """Lets the chosen member open tickets again."""

    def __init__(self):
        super().__init__(
            label="Unblacklist User", style=discord.ButtonStyle.green, emoji="🔓"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.set_blacklisted(interaction, False)


class BlacklistButton(Button):
    """Opens the blacklist screen."""

    def __init__(self):
        super().__init__(
            label="Blacklist", style=discord.ButtonStyle.secondary, emoji="🚫", row=3
        )

    async def callback(self, interaction: discord.Interaction):
        view = BlacklistView(self.view.bot, interaction, self.view)
        await view.show_blacklist(interaction)


class SnippetSelect(Select):
    """Picks the snippet the edit and remove buttons act on."""

    def __init__(self, options):
        super().__init__(
            placeholder="Select a snippet to edit/remove...", options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_snippet = self.values[0]
        await interaction.response.defer()


class SnippetsView(SubSettingsView):
    """Shows the server's prewritten answers, to add, edit or remove one."""

    selected_snippet = None

    def path(self, alias: str = "") -> str:
        """Gives where the server's snippets, or one of them, are kept."""
        return f"/Ticket Snippets/{self.interaction.guild.id}/{alias}".rstrip("/")

    async def show_snippets(self, interaction: discord.Interaction):
        snippets = await read(self.path()) or {}
        embed = discord.Embed(
            title="📝 Snippet Management",
            description="Manage prewritten responses for tickets.",
            color=discord.Color.blue(),
        )
        listed = "\n".join(
            f"- **{alias}**: {response[:50]}{'...' if len(response) > 50 else ''}"
            for alias, response in snippets.items()
        )
        embed.add_field(
            name=f"Current Snippets ({len(snippets)}/{SNIPPET_LIMIT})",
            value=shortened(listed) or "No snippets configured",
            inline=False,
        )
        self.clear_items()
        if snippets:
            options = [
                discord.SelectOption(
                    label=alias, value=alias, description=response[:50]
                )
                for alias, response in list(snippets.items())[:SNIPPET_LIMIT]
            ]
            self.add_item(SnippetSelect(options))
        self.add_item(AddSnippetButton())
        if snippets:
            self.add_item(EditSnippetButton())
            self.add_item(RemoveSnippetButton())
        self.add_item(BackToSettingsButton())
        await interaction.response.edit_message(embed=embed, view=self)


class AddSnippetButton(Button):
    """Asks for a new snippet."""

    def __init__(self):
        super().__init__(
            label="Add Snippet", style=discord.ButtonStyle.green, emoji="➕"
        )

    async def callback(self, interaction: discord.Interaction):
        snippets = await read(self.view.path()) or {}
        if len(snippets) >= SNIPPET_LIMIT:
            return await interaction.response.send_message(
                "Maximum 25 snippets allowed per server!", ephemeral=True
            )
        await interaction.response.send_modal(SnippetModal(view=self.view))


class EditSnippetButton(Button):
    """Asks for the chosen snippet's new alias and text."""

    def __init__(self):
        super().__init__(
            label="Edit Snippet", style=discord.ButtonStyle.primary, emoji="✏️"
        )

    async def callback(self, interaction: discord.Interaction):
        alias = await chosen_or_ask(interaction, self.view.selected_snippet, "snippet")
        if not alias:
            return
        response = await read(self.view.path(alias)) or ""
        modal = SnippetModal(self.view, alias, response, editing=True)
        await interaction.response.send_modal(modal)


class RemoveSnippetButton(Button):
    """Removes the chosen snippet."""

    def __init__(self):
        super().__init__(
            label="Remove Snippet", style=discord.ButtonStyle.red, emoji="🗑️"
        )

    async def callback(self, interaction: discord.Interaction):
        alias = await chosen_or_ask(interaction, self.view.selected_snippet, "snippet")
        if not alias:
            return
        await remove(self.view.path(alias))
        self.view.selected_snippet = None
        await self.view.show_snippets(interaction)


class SnippetModal(Modal):
    """Asks for a snippet's alias and text and saves them."""

    def __init__(self, view=None, alias="", response="", editing=False):
        super().__init__(title="Edit Snippet" if editing else "Add Snippet")
        self.view = view
        self.old_alias = alias if editing else None
        self.add_item(
            TextInput(
                label="Alias",
                placeholder="Short name for the snippet",
                default=alias,
                max_length=50,
                required=True,
            )
        )
        self.add_item(
            TextInput(
                label="Response",
                placeholder="The prewritten response",
                default=response,
                max_length=2000,
                style=discord.TextStyle.paragraph,
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        alias = self.children[0].value.strip()
        response = self.children[1].value.strip()
        if not alias or not response:
            return await interaction.response.send_message(
                "Both alias and response are required!", ephemeral=True
            )
        if BAD_KEY.search(alias):
            return await interaction.response.send_message(
                "The alias cannot contain `.` `$` `#` `[` `]` or `/`!", ephemeral=True
            )
        if self.old_alias and self.old_alias != alias:
            await remove(self.view.path(self.old_alias))
            self.view.selected_snippet = None
        await write(self.view.path(alias), response)
        await self.view.show_snippets(interaction)


class SnippetsButton(Button):
    """Opens the snippets screen."""

    def __init__(self):
        super().__init__(
            label="Snippets", style=discord.ButtonStyle.secondary, emoji="📝", row=3
        )

    async def callback(self, interaction: discord.Interaction):
        view = SnippetsView(self.view.bot, interaction, self.view)
        await view.show_snippets(interaction)


async def setup(bot: commands.Bot) -> None:
    bot.add_dynamic_items(ExtraTicketButton, ConfirmTicketButton)
    await bot.add_cog(Ticket(bot))
