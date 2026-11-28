"""Welcome: the message new members are greeted with, its editor and /welcome."""

import asyncio
import collections
import contextlib
import copy
import io
import os
import tempfile
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, ChannelSelect, Modal, Select, View
from firebase_admin import db

from ..Utility.embed import link_emoji, now, text_input

YES = "<:yes:1036811164891480194>"
NO = "<:no:1036810470860013639>"
# Fischl's own channel that hosts the drawn cards; other bots cannot see it.
CARD_LOG = 1026904121237831700
# Servers whose new members also get the welcome message in a DM.
DM_COPY_SERVERS = {791534106919305226, 1363145981235036360}
BACKGROUNDS = "./assets/Welcome Image Background"
DEFAULT_ICON = "./assets/DefaultIcon.png"
CARD_SIZE = (1024, 576)
CARD_NAME = "welcome.png"
CARD_DIMMING = 0.6
EDITOR_TIMEOUT = 3600
ENABLE_TIMEOUT = 1800
LEGACY_CACHE_SECONDS = 300
COLOR_API = "https://www.thecolorapi.com/id"
HEX_DIGITS = set("0123456789abcdefABCDEF")
NOT_ENABLED = (
    "This server does not have welcome message enabled! Use `/welcome settings` to"
    " enable first."
)
# Why a welcome message was not sent: half set up, turned off, or its channel is gone.
UNSET, OFF, GONE = "unset", "off", "gone"
# The old `/Welcome` list and when it was read; joins in servers without a welcome ask for it.
legacy_cache = {"at": 0.0, "settings": None}
saving = collections.defaultdict(asyncio.Lock)
# What The Color API made of each odd colour text.
api_colors = {}


async def read(path: str):
    """Gives what Firebase holds at a path, without pausing the bot."""
    return await asyncio.to_thread(db.reference(path).get)


async def write(path: str, value) -> None:
    """Saves a value at a Firebase path, without pausing the bot."""
    await asyncio.to_thread(db.reference(path).set, value)


async def remove(path: str) -> None:
    """Deletes a Firebase path, without pausing the bot."""
    await asyncio.to_thread(db.reference(path).delete)


def of_server(records, guild_id: int):
    """Gives the key and record of a server in an old list, or (None, None)."""
    for key, value in (records or {}).items():
        if value.get("Server ID") == guild_id:
            return key, value
    return None, None


async def legacy_settings(guild_id: int):
    """Gives a server's key and record in the old `/Welcome` list, read at most every few minutes."""
    if time.monotonic() - legacy_cache["at"] > LEGACY_CACHE_SECONDS:
        legacy_cache["settings"] = await read("/Welcome")
        legacy_cache["at"] = time.monotonic()
    return of_server(legacy_cache["settings"], guild_id)


async def legacy_content(guild_id: int):
    """Gives a server's key and record in the old `/Welcome Content` list."""
    return of_server(await read("/Welcome Content"), guild_id)


def keys_of_server(records, guild_id: int) -> list:
    """Gives the key of every record a server has in an old list."""
    return [
        key
        for key, value in (records or {}).items()
        if value.get("Server ID") == guild_id
    ]


async def mirror(path: str, key, record: dict) -> None:
    """Saves a server's record in an old list, in place when it has one."""
    if key:
        return await write(f"{path}/{key}", record)
    await asyncio.to_thread(lambda: db.reference(path).push().set(record))


def background(guild_id: int) -> str:
    """Gives where a server's card background is kept."""
    return f"{BACKGROUNDS}/{guild_id}.png"


def font(size: int, fallback_size: int):
    """Gives the card font and whether it is the fallback one."""
    from PIL import ImageFont

    try:
        return ImageFont.truetype("./assets/ja-jp.ttf", size), False
    except Exception:
        return ImageFont.truetype("./assets/LilitaOne-Regular.ttf", fallback_size), True


def draw_card(avatar, name: str, bg: str) -> bytes:
    """Draws the welcome card: the round avatar, "Welcome" and the name on the background."""
    from PIL import Image, ImageDraw

    card = Image.open(bg)
    try:
        face = Image.open(io.BytesIO(avatar))
    except Exception:
        face = Image.open(DEFAULT_ICON)
    bigsize = (face.size[0] * 3, face.size[1] * 3)
    mask = Image.new("L", bigsize, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + bigsize, fill=255)
    face.putalpha(mask.resize(face.size, Image.LANCZOS))
    card.paste(face, (384, 50), face.convert("RGBA"))
    draw, white = ImageDraw.Draw(card), (255, 255, 255)
    heading, fallback = font(75, 90)
    draw.text(
        (330, 330) if fallback else (325, 320), "Welcome", font=heading, fill=white
    )
    small, small_fallback = font(35, 50)
    fallback = fallback or small_fallback
    width, top = (24, 430) if fallback else (20, 410)
    draw.text((1024 / 2 - width * (len(name) / 2), top), name, font=small, fill=white)
    out = io.BytesIO()
    card.save(out, "PNG")
    return out.getvalue()


async def welcome_card(user, guild_id: int):
    """Gives a member's card as a file, or None when it cannot be drawn, as with no background."""
    if not os.path.exists(background(guild_id)):
        return None
    try:
        avatar = await user.avatar.with_static_format("png").with_size(256).read()
    except Exception:
        avatar = None
    try:
        card = await asyncio.to_thread(
            draw_card, avatar, f"{user.name}", background(guild_id)
        )
    except Exception:
        return None
    return discord.File(io.BytesIO(card), filename=CARD_NAME)


async def hosted(client, card: discord.File, guild):
    """Posts a card in Fischl's card channel and gives its link, or None when the channel is out of reach."""
    channel = client.get_channel(CARD_LOG)
    if not channel:
        return None
    message = await channel.send(f"**Guild Name:** {guild}", file=card)
    return message.attachments[0].proxy_url


def save_background(image: bytes, path: str) -> None:
    """Crops an uploaded image to the card's shape, dims it and saves it."""
    from PIL import Image, ImageEnhance

    os.makedirs(os.path.dirname(path), exist_ok=True)
    picture = Image.open(io.BytesIO(image))
    if picture.mode not in ("RGB", "RGBA", "L", "LA"):
        picture = picture.convert("RGB")
    width, height = picture.size
    ideal = CARD_SIZE[0] / float(CARD_SIZE[1])
    if width / float(height) > ideal:
        offset = (width - int(ideal * height)) / 2
        box = (offset, 0, width - offset, height)
    else:
        offset = (height - int(width / ideal)) / 2
        box = (0, offset, width, height - offset)
    picture = picture.crop(box).resize(CARD_SIZE, Image.LANCZOS)
    stored = io.BytesIO()
    picture.save(stored, "PNG")
    dimmed = ImageEnhance.Brightness(Image.open(stored)).enhance(CARD_DIMMING)
    handle, draft = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(handle, "wb") as file:
        dimmed.save(file, "PNG")
    os.chmod(draft, 0o644)
    os.replace(draft, path)


def ordinal(n: int) -> str:
    """Gives a number with its ending, as in 1st, 2nd, 3rd, 11th."""
    if 4 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def script(string: str, user, guild) -> str:
    """Fills the variables of a welcome text in for a member."""
    values = {
        "{mention}": lambda: user.mention,
        "{server}": lambda: guild.name,
        "{user}": lambda: user.name,
        "{count}": lambda: guild.member_count,
        "{count-th}": lambda: ordinal(guild.member_count),
    }
    for variable, value in values.items():
        if variable in string:
            string = string.replace(variable, f"{value()}")
    return string


def plain_color(text: str):
    """Reads a colour written as six hex digits, with or without `#`; None for anything else."""
    digits = text[1:] if text.startswith("#") else text
    if len(digits) == 6 and set(digits) <= HEX_DIGITS:
        return int(digits, 16)
    return None


async def legacy_color(text: str) -> discord.Color:
    """Gives the colour of an old record; odd spellings are read by The Color API, blurple when it cannot."""
    color = plain_color(text)
    if color is not None:
        return discord.Color(color)
    if text not in api_colors:
        digits = text[1:] if text.startswith("#") else text
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(COLOR_API, params={"hex": digits}) as answer:
                    found = await answer.json()
        except Exception:
            return discord.Color.blurple()
        try:
            api_colors[text] = discord.Color(int(found["hex"]["clean"], 16))
        except Exception:
            api_colors[text] = discord.Color.blurple()
    return api_colors[text]


def links_view(links, user, guild):
    """Gives a view of the link buttons filled in for a member, or None without links."""
    if not links:
        return None
    view = View()
    for link in links:
        view.add_item(
            Button(
                label=script(link["label"], user, guild),
                url=script(link["url"], user, guild),
                emoji=link_emoji(link["emoji"]),
                style=discord.ButtonStyle.link,
            )
        )
    return view


class WelcomeEditor:
    """One server's welcome message: its channel, text, embed, link buttons and card switch."""

    def __init__(self, guild_id: int, data=None):
        self.guild_id = guild_id
        self.channel_id = None
        self.welcome_image_enabled = False
        self.message_content = ""
        self.embed_data = {
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
        self.button_links = []
        if data:
            self.channel_id = data.get("channel_id")
            self.welcome_image_enabled = data.get("welcome_image_enabled", False)
            self.message_content = data.get("message_content", "")
            for key, value in (data.get("embed") or {}).items():
                if isinstance(value, dict) and isinstance(
                    self.embed_data.get(key), dict
                ):
                    self.embed_data[key].update(value)
                elif not isinstance(value, dict):
                    self.embed_data[key] = value
            self.button_links = data.get("button_links") or []

    @classmethod
    def from_legacy(cls, guild_id: int, settings: dict, content, color=None):
        """Gives an editor filled from a server's records in the two old lists."""
        editor = cls(guild_id)
        editor.channel_id = settings.get("Welcome Channel ID")
        editor.welcome_image_enabled = settings.get("Welcome Image Enabled", False)
        if content:
            editor.message_content = content.get("Message Content", "")
            editor.embed_data["title"] = content.get("Title", "")
            editor.embed_data["description"] = content.get("Description", "")
            if color is not None:
                editor.embed_data["color"] = color
        return editor

    def to_dict(self) -> dict:
        """Gives the record kept at `/WelcomeV2/<server>`."""
        return copy.deepcopy(
            {
                "channel_id": self.channel_id,
                "welcome_image_enabled": self.welcome_image_enabled,
                "message_content": self.message_content,
                "embed": self.embed_data,
                "button_links": self.button_links,
            }
        )

    def is_embed_empty(self) -> bool:
        """Says whether the embed has nothing Discord would show."""
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

    def to_embed(self, user, guild) -> discord.Embed:
        """Gives the embed filled in for a member."""
        data = self.embed_data
        embed = discord.Embed(
            title=script(data["title"], user, guild) if data["title"] else None,
            description=(
                script(data["description"], user, guild)
                if data["description"]
                else None
            ),
            color=data["color"],
        )
        if data["footer"]["text"]:
            embed.set_footer(
                text=script(data["footer"]["text"], user, guild),
                icon_url=data["footer"]["icon_url"] or None,
            )
        if data["author"]["name"]:
            embed.set_author(
                name=script(data["author"]["name"], user, guild),
                icon_url=data["author"]["icon_url"] or None,
            )
        if data["thumbnail"]:
            embed.set_thumbnail(url=data["thumbnail"])
        if data["image"]:
            embed.set_image(url=data["image"])
        for field in data["fields"]:
            embed.add_field(
                name=script(field["name"], user, guild),
                value=script(field["value"], user, guild),
                inline=field["inline"],
            )
        if data["timestamp"]:
            embed.timestamp = now()
        return embed

    def preview(self, user, guild):
        """Gives the embed to show in the editor, or None when it has no content."""
        return None if self.is_embed_empty() else self.to_embed(user, guild)

    async def greeting(self, client, member) -> dict:
        """Gives what to send for a member: text, embed with the card or image, and link buttons."""
        guild = member.guild
        embed, files = self.preview(member, guild), []
        card = self.welcome_image_enabled and await welcome_card(member, guild.id)
        if card:
            embed = embed or self.to_embed(member, guild)
            url = await hosted(client, card, guild)
            if not url:
                files, url = [card], f"attachment://{CARD_NAME}"
            embed.set_image(url=url)
        return {
            "content": script(self.message_content, member, guild) or None,
            "embed": embed,
            "view": links_view(self.button_links, member, guild),
            "files": files,
        }

    async def save(self) -> None:
        """Saves the message, and the server's records in the two old lists `/help` and older code read."""
        async with saving[self.guild_id]:
            await self.store()

    async def store(self) -> None:
        """Writes the three records; `save` keeps two of these from running at once for a server."""
        guild_id, color = self.guild_id, self.embed_data["color"]
        await write(f"/WelcomeV2/{guild_id}", self.to_dict())
        legacy_cache["at"] = 0.0
        key, _ = await legacy_settings(guild_id)
        settings = {
            "Server ID": guild_id,
            "Welcome Channel ID": self.channel_id,
            "Welcome Image Enabled": self.welcome_image_enabled,
        }
        await mirror("/Welcome", key, settings)
        key, _ = await legacy_content(guild_id)
        content = {
            "Server ID": guild_id,
            "Message Content": self.message_content,
            "Title": self.embed_data["title"],
            "Description": self.embed_data["description"],
            "Color": f"#{color:06x}",
        }
        await mirror("/Welcome Content", key, content)
        legacy_cache["at"] = 0.0


async def saved_editor(guild_id: int):
    """Gives a server's welcome message, from the old lists when it was never edited since; None with welcomes off."""
    data = await read(f"/WelcomeV2/{guild_id}")
    if data:
        return WelcomeEditor(guild_id, data)
    _, settings = await legacy_settings(guild_id)
    if not settings:
        return None
    _, content = await legacy_content(guild_id)
    color = content and (await legacy_color(content.get("Color", ""))).value
    return WelcomeEditor.from_legacy(guild_id, settings, content, color)


async def legacy_greeting(client, member, settings: dict, content: dict) -> dict:
    """Gives what to send for a member in a server still on the old records."""
    guild = member.guild
    embed, files = None, []
    card = settings["Welcome Image Enabled"] and await welcome_card(member, guild.id)
    if content["Title"] != "" or content["Description"] != "":
        embed = discord.Embed(
            title=script(content["Title"], member, guild),
            description=script(content["Description"], member, guild),
            color=await legacy_color(content["Color"]),
        )
        if card:
            url = await hosted(client, card, guild)
            if not url:
                files, url = [card], f"attachment://{CARD_NAME}"
            embed.set_image(url=url)
    elif card:
        files = [card]
    return {
        "content": script(content["Message Content"], member, guild),
        "embed": embed,
        "files": files,
    }


async def greet(client, member, dm=True):
    """Sends a member their server's welcome message; gives the channel it went to, or UNSET, OFF or GONE."""
    guild = member.guild
    data = await read(f"/WelcomeV2/{guild.id}")
    if data:
        editor = WelcomeEditor(guild.id, data)
        if not editor.channel_id:
            return UNSET
        channel = client.get_channel(editor.channel_id)
        if not channel:
            return GONE
        message = await editor.greeting(client, member)
        if not (message["content"] or message["embed"]):
            return UNSET
        await channel.send(**message)
        if dm and guild.id in DM_COPY_SERVERS:
            message["files"] = []
            with contextlib.suppress(discord.Forbidden):
                await member.send(**message)
        return channel
    _, settings = await legacy_settings(guild.id)
    _, content = await legacy_content(guild.id) if settings else (None, None)
    if not content:
        return OFF
    channel = client.get_channel(settings["Welcome Channel ID"])
    if not channel:
        return GONE
    await channel.send(**await legacy_greeting(client, member, settings, content))
    return channel


class WelcomeModal(Modal):
    """A modal of the editor; after it is filled in, the screen it came from saves and redraws."""

    def __init__(self, title: str, view: "EditorView"):
        super().__init__(title=title)
        self.view = view
        self.editor = view.editor

    def keep(self) -> None:
        """Puts what was typed into the editor."""

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.keep()
        await self.editor.save()
        await self.view.show(interaction, from_modal=True)


class WelcomeMessageContentModal(WelcomeModal):
    """Asks for the text above the embed."""

    def __init__(self, view):
        super().__init__("Edit Welcome Message Content", view)
        self.add_item(
            text_input(
                "Message Content",
                "Normal message content (appears above embed)",
                self.editor.message_content,
                max_length=2000,
                style=discord.TextStyle.paragraph,
            )
        )

    def keep(self) -> None:
        self.editor.message_content = self.children[0].value


class WelcomeEmbedModal(WelcomeModal):
    """Asks for the embed's title, description, colour, footer text and author name."""

    def __init__(self, view):
        super().__init__("Edit Welcome Embed", view)
        data = self.editor.embed_data
        self.add_item(
            text_input("Title", "Welcome embed title", data["title"], max_length=256)
        )
        self.add_item(
            text_input(
                "Description",
                "Welcome embed description",
                data["description"],
                max_length=4000,
                style=discord.TextStyle.paragraph,
            )
        )
        self.add_item(
            text_input("Color (Hex)", "#FF0000", f"#{data['color']:06x}", max_length=7)
        )
        self.add_item(
            text_input(
                "Footer Text", "Footer text", data["footer"]["text"], max_length=2048
            )
        )
        self.add_item(
            text_input(
                "Author Name", "Author name", data["author"]["name"], max_length=256
            )
        )

    def keep(self) -> None:
        """Keeps what was typed; a colour that is not `#` and hex digits is ignored."""
        data = self.editor.embed_data
        title, description, color, footer, author = (c.value for c in self.children)
        data["title"], data["description"] = title, description
        color = color.strip()
        if color.startswith("#"):
            with contextlib.suppress(ValueError):
                data["color"] = int(color[1:], 16)
        data["footer"]["text"], data["author"]["name"] = footer, author


class WelcomeMediaModal(WelcomeModal):
    """Asks for the image, thumbnail, author icon and footer icon links."""

    def __init__(self, view):
        super().__init__("Edit Welcome Media", view)
        data = self.editor.embed_data
        self.add_item(text_input("Image URL", "Main image/banner URL", data["image"]))
        self.add_item(
            text_input("Thumbnail URL", "Thumbnail image URL", data["thumbnail"])
        )
        self.add_item(
            text_input("Author Icon URL", "Author icon URL", data["author"]["icon_url"])
        )
        self.add_item(
            text_input("Footer Icon URL", "Footer icon URL", data["footer"]["icon_url"])
        )

    def keep(self) -> None:
        data = self.editor.embed_data
        image, thumbnail, author_icon, footer_icon = (c.value for c in self.children)
        data["image"], data["thumbnail"] = image, thumbnail
        data["author"]["icon_url"] = author_icon
        data["footer"]["icon_url"] = footer_icon


class WelcomeFieldModal(WelcomeModal):
    """Asks for a field's name, value and whether it is inline; adds a field when no index is given."""

    def __init__(self, view, index=None):
        super().__init__("Edit Welcome Field", view)
        self.index = index
        fields = self.editor.embed_data["fields"]
        field = {"name": "", "value": "", "inline": True}
        field = field if index is None else fields[index]
        self.add_item(
            text_input(
                "Field Name",
                "Field title",
                field["name"],
                max_length=256,
                required=True,
            )
        )
        self.add_item(
            text_input(
                "Field Value",
                "Field content",
                field["value"],
                max_length=1024,
                required=True,
                style=discord.TextStyle.paragraph,
            )
        )
        self.add_item(
            text_input(
                "Inline (Y/N)",
                "Y for inline, N for not inline",
                "Y" if field["inline"] else "N",
                max_length=1,
                required=True,
            )
        )

    def keep(self) -> None:
        name, value, inline = (c.value for c in self.children)
        field = {"name": name, "value": value, "inline": inline.upper() == "Y"}
        fields = self.editor.embed_data["fields"]
        if self.index is None:
            fields.append(field)
        else:
            fields[self.index] = field


class WelcomeButtonLinkModal(WelcomeModal):
    """Asks for a link button's label, URL and emoji; adds a link when no index is given."""

    def __init__(self, view, index=None):
        super().__init__("Edit Welcome Button Link", view)
        self.index = index
        link = {"label": "", "url": "", "emoji": ""}
        link = link if index is None else self.editor.button_links[index]
        self.add_item(
            text_input(
                "Button Label",
                "Text shown on button",
                link["label"],
                max_length=80,
                required=True,
            )
        )
        self.add_item(
            text_input("URL", "https://example.com", link["url"], required=True)
        )
        self.add_item(
            text_input(
                "Emoji (optional)", "Format: <:name:id> or unicode emoji", link["emoji"]
            )
        )

    def keep(self) -> None:
        label, url, emoji = (c.value for c in self.children)
        link = {"label": label, "url": url, "emoji": emoji}
        if self.index is None:
            self.editor.button_links.append(link)
        else:
            self.editor.button_links[self.index] = link


class EditorView(View):
    """One screen of the welcome editor."""

    def __init__(self, editor: WelcomeEditor, guild: discord.Guild):
        super().__init__(timeout=EDITOR_TIMEOUT)
        self.editor = editor
        self.guild = guild

    def shown(self, interaction: discord.Interaction) -> dict:
        """Gives what this screen shows."""
        raise NotImplementedError

    async def show(self, interaction: discord.Interaction, **_):
        """Draws this screen over the message the press came from."""
        shown = self.shown(interaction)
        if interaction.response.is_done():
            await interaction.edit_original_response(**shown)
        else:
            await interaction.response.edit_message(**shown)

    async def refuse(self, interaction: discord.Interaction, reason: str):
        """Answers a press that cannot be done."""
        await interaction.response.send_message(reason, ephemeral=True)


class ListView(EditorView):
    """A screen that adds, edits and removes the entries of one list: fields or link buttons."""

    noun = ""
    title = ""
    hint = ""
    modal = None

    def __init__(self, editor: WelcomeEditor, guild: discord.Guild):
        super().__init__(editor, guild)
        self.selected_index = 0 if self.entries() else None
        self.select = Select(placeholder=f"Select a {self.noun.lower()} to edit", row=0)
        self.select.callback = self.pick
        self.add.label = f"Add {self.noun}"
        self.edit.label = f"Edit {self.noun}"
        self.remove.label = f"Remove {self.noun}"
        self.update_select()

    def entries(self) -> list:
        """Gives the list this screen edits."""
        raise NotImplementedError

    def label(self, entry: dict) -> str:
        """Gives the text an entry is listed under."""
        raise NotImplementedError

    def update_select(self) -> None:
        """Lists the entries in the dropdown, which is left out when there are none."""
        self.remove_item(self.select)
        if not self.entries():
            return
        self.select.options = [
            discord.SelectOption(
                label=self.label(entry)[:50] or f"{self.noun} {index + 1}",
                value=str(index),
            )
            for index, entry in enumerate(self.entries())
        ]
        self.add_item(self.select)

    def shown(self, interaction: discord.Interaction) -> dict:
        self.update_select()
        embed = self.editor.preview(interaction.user, self.guild) or discord.Embed(
            title=self.title, description=self.hint, color=discord.Color.light_gray()
        )
        return {"embed": embed, "view": self}

    async def pick(self, interaction: discord.Interaction):
        """Remembers which entry Edit and Remove act on."""
        self.selected_index = int(interaction.data["values"][0])
        await self.show(interaction)

    @discord.ui.button(style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add(self, interaction: discord.Interaction, button: Button):
        """Asks for a new entry."""
        await interaction.response.send_modal(self.modal(self))

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit(self, interaction: discord.Interaction, button: Button):
        """Asks for new values of the selected entry."""
        if self.selected_index is None:
            noun = self.noun.lower()
            return await self.refuse(interaction, f"Please select a {noun} first!")
        await interaction.response.send_modal(self.modal(self, self.selected_index))

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove(self, interaction: discord.Interaction, button: Button):
        """Removes the selected entry."""
        if self.selected_index is None:
            noun = self.noun.lower()
            return await self.refuse(interaction, f"Please select a {noun} first!")
        await interaction.response.defer()
        self.entries().pop(self.selected_index)
        self.selected_index = None
        await self.editor.save()
        await self.show(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        """Returns to the first screen."""
        await WelcomeSettingsView(self.editor, self.guild).show(interaction)


class WelcomeFieldsEditorView(ListView):
    """The screen that edits the embed's fields."""

    noun = "Field"
    title = "Fields Editor"
    hint = "Add and manage embed fields for your welcome message."
    modal = WelcomeFieldModal

    def entries(self) -> list:
        return self.editor.embed_data["fields"]

    def label(self, entry: dict) -> str:
        return entry["name"]


class WelcomeButtonLinksEditorView(ListView):
    """The screen that edits the link buttons; it also shows them as they will look."""

    noun = "Link"
    title = "Button Links Editor"
    hint = "Add and manage button links for your welcome message."
    modal = WelcomeButtonLinkModal

    def entries(self) -> list:
        return self.editor.button_links

    def label(self, entry: dict) -> str:
        return entry["label"]

    async def show(self, interaction: discord.Interaction, *, from_modal=False, **_):
        await super().show(interaction)
        if from_modal or not self.editor.button_links:
            return
        preview = View()
        for link in self.editor.button_links:
            preview.add_item(
                Button(
                    label=link["label"],
                    url=link["url"],
                    emoji=link_emoji(link["emoji"]),
                    style=discord.ButtonStyle.link,
                )
            )
        with contextlib.suppress(discord.HTTPException):
            await interaction.followup.send(
                "**Button Preview:**", view=preview, ephemeral=True
            )


class WelcomeSettingsView(EditorView):
    """The editor's first screen: the channel, each part of the message, the card and Disable."""

    def __init__(self, editor: WelcomeEditor, guild: discord.Guild):
        super().__init__(editor, guild)
        self.channel_select = ChannelSelect(
            placeholder="Select welcome channel...",
            channel_types=[discord.ChannelType.text],
        )
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)

    def shown(self, interaction: discord.Interaction) -> dict:
        editor = self.editor
        channel = editor.channel_id and self.guild.get_channel(editor.channel_id)
        self.channel_select.default_values = [channel] if channel else []
        enabled = editor.welcome_image_enabled
        self.toggle_image.label = f"{'Disable' if enabled else 'Enable'} Custom Image"
        self.toggle_image.style = (
            discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success
        )
        content = editor.message_content or None
        embed = editor.preview(interaction.user, self.guild)
        if not content and not embed:
            embed = discord.Embed(
                title="Welcome Message Settings",
                description=(
                    "Configure your server's welcome message using the options below."
                    " Right now, no welcome message is set up."
                ),
                color=discord.Color.blue(),
            )
        return {"content": content, "embed": embed, "view": self}

    async def select_channel(self, interaction: discord.Interaction):
        """Sets the channel new members are welcomed in."""
        await interaction.response.defer()
        self.editor.channel_id = int(interaction.data["values"][0])
        await self.editor.save()
        await self.show(interaction)

    @discord.ui.button(
        label="Message", style=discord.ButtonStyle.secondary, emoji="💬", row=0
    )
    async def edit_message(self, interaction: discord.Interaction, button: Button):
        """Asks for the text above the embed."""
        await interaction.response.send_modal(WelcomeMessageContentModal(self))

    @discord.ui.button(
        label="Embed", style=discord.ButtonStyle.secondary, emoji="🖼️", row=0
    )
    async def edit_embed(self, interaction: discord.Interaction, button: Button):
        """Asks for the embed's texts and colour."""
        await interaction.response.send_modal(WelcomeEmbedModal(self))

    @discord.ui.button(
        label="Media", style=discord.ButtonStyle.secondary, emoji="📷", row=0
    )
    async def edit_media(self, interaction: discord.Interaction, button: Button):
        """Asks for the embed's image and icon links."""
        await interaction.response.send_modal(WelcomeMediaModal(self))

    @discord.ui.button(
        label="Fields", style=discord.ButtonStyle.secondary, emoji="📋", row=0
    )
    async def edit_fields(self, interaction: discord.Interaction, button: Button):
        """Opens the fields screen."""
        await WelcomeFieldsEditorView(self.editor, self.guild).show(interaction)

    @discord.ui.button(
        label="Link Buttons", style=discord.ButtonStyle.secondary, emoji="🔗", row=0
    )
    async def edit_links(self, interaction: discord.Interaction, button: Button):
        """Opens the link buttons screen."""
        await WelcomeButtonLinksEditorView(self.editor, self.guild).show(interaction)

    @discord.ui.button(
        label="Toggle Custom Image",
        style=discord.ButtonStyle.secondary,
        emoji="🖼️",
        row=1,
    )
    async def toggle_image(self, interaction: discord.Interaction, button: Button):
        """Turns the drawn card on or off; it needs an uploaded background."""
        if not os.path.exists(background(interaction.guild_id)):
            return await self.refuse(
                interaction,
                f"{NO} No custom background image found! Use `/welcome upload` to add"
                " one first.",
            )
        await interaction.response.defer()
        self.editor.welcome_image_enabled = not self.editor.welcome_image_enabled
        await self.editor.save()
        await self.show(interaction)

    @discord.ui.button(
        label="Variable Guide", style=discord.ButtonStyle.blurple, emoji="❓", row=1
    )
    async def show_guide(self, interaction: discord.Interaction, button: Button):
        """Lists the variables a welcome text can use."""
        embed = discord.Embed(
            title="Welcome Message Variables",
            description=(
                "Use these variables in your welcome message to display dynamic"
                " content:"
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Available Variables",
            value=(
                "`{mention}` - Mentions the new user\n"
                "`{user}` - Displays the username\n"
                "`{server}` - Displays the server name\n"
                "`{count}` - Shows the member count\n"
                "`{count-th}` - Shows the member count with ordinal (1st, 2nd, 3rd,"
                " etc.)"
            ),
            inline=False,
        )
        embed.add_field(
            name="Example",
            value="Welcome {mention} to {server}! You are our {count-th} member!",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Disable System", style=discord.ButtonStyle.danger, row=1)
    async def disable_system(self, interaction: discord.Interaction, button: Button):
        """Deletes the server's welcome message, from the old lists too."""
        await interaction.response.defer()
        guild_id = interaction.guild_id
        async with saving[guild_id]:
            paths = [f"/WelcomeV2/{guild_id}"]
            for path in ("/Welcome", "/Welcome Content"):
                keys = keys_of_server(await read(path), guild_id)
                paths += [f"{path}/{key}" for key in keys]
            await asyncio.gather(*map(remove, paths))
            legacy_cache["at"] = 0.0
        embed = discord.Embed(
            title="Welcome System Disabled",
            description="The welcome system has been disabled for this server.",
            color=discord.Color.red(),
            timestamp=now(),
        )
        await interaction.edit_original_response(content=None, embed=embed, view=None)


class WelcomeEnableView(View):
    """Offers to turn welcomes on in a server that has none."""

    def __init__(self):
        super().__init__(timeout=ENABLE_TIMEOUT)

    @discord.ui.button(
        label="Enable System", style=discord.ButtonStyle.green, emoji="✅"
    )
    async def enable_system(self, interaction: discord.Interaction, button: Button):
        """Opens an empty editor; nothing is saved until something is set."""
        editor = WelcomeEditor(interaction.guild_id)
        await WelcomeSettingsView(editor, interaction.guild).show(interaction)


async def report(interaction: discord.Interaction, error: Exception) -> None:
    """Shows a command's error to the member who ran it."""
    text = f"```{error}```"
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


@app_commands.guild_only()
class Welcome(commands.GroupCog, name="welcome"):
    """The /welcome commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    async def cog_app_command_error(self, interaction, error) -> None:
        await report(interaction, error)

    @app_commands.command(
        name="settings",
        description="Configure the welcome message with an advanced editor",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_settings(self, interaction: discord.Interaction) -> None:
        """Opens the editor, or offers to enable welcomes."""
        await interaction.response.defer(ephemeral=True)
        editor = await saved_editor(interaction.guild_id)
        if editor:
            view = WelcomeSettingsView(editor, interaction.guild)
            return await view.show(interaction)
        embed = discord.Embed(
            title="Welcome System",
            description=(
                "The welcome system is currently disabled. Enable it to welcome new"
                " members with custom messages!"
            ),
            color=discord.Color.orange(),
        )
        await interaction.followup.send(embed=embed, view=WelcomeEnableView())

    @app_commands.command(
        name="upload",
        description="Upload a custom background image for welcome messages",
    )
    @app_commands.describe(
        background_image=(
            "The background image for welcome messages (will be cropped to 1024x576)"
        )
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_upload(
        self, interaction: discord.Interaction, background_image: discord.Attachment
    ) -> None:
        """Saves the server's card background and turns the card on."""
        if not (background_image.content_type or "").startswith("image/"):
            return await interaction.response.send_message(
                f"{NO} Please upload a valid image file!", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        image = await background_image.read()
        await asyncio.to_thread(save_background, image, background(guild_id))
        async with saving[guild_id]:
            data = await read(f"/WelcomeV2/{guild_id}")
            if data and not data.get("welcome_image_enabled"):
                await write(f"/WelcomeV2/{guild_id}/welcome_image_enabled", True)
        embed = discord.Embed(
            title=f"{YES} Background Uploaded!",
            description=(
                "Custom background image has been uploaded and processed successfully."
            ),
            color=discord.Color.green(),
            timestamp=now(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="sample",
        description="Sends a sample welcome message to the configured channel",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_sample(self, interaction: discord.Interaction) -> None:
        """Welcomes the member who ran it, the way a new member would be."""
        await interaction.response.defer(ephemeral=True)
        channel = await greet(self.bot, interaction.user, dm=False)
        if channel == UNSET:
            return await interaction.followup.send(
                f"{NO} Welcome system is not properly configured! Use `/welcome"
                " settings` first."
            )
        if channel == GONE:
            return await interaction.followup.send(
                f"{NO} Welcome channel not found! It may have been deleted."
            )
        if channel == OFF:
            embed = discord.Embed(
                title="Welcome message not enabled!",
                description=NOT_ENABLED,
                colour=0xFF0000,
                timestamp=now(),
            )
            return await interaction.followup.send(embed=embed)
        embed = discord.Embed(
            description=f"{YES} Sample message sent to {channel.mention}",
            colour=0x00FF00,
            timestamp=now(),
        )
        await interaction.followup.send(embed=embed)


class OnWelcomeMemberJoin(commands.Cog):
    """Welcomes each new member."""

    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await greet(self.client, member)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
    await bot.add_cog(OnWelcomeMemberJoin(bot))
