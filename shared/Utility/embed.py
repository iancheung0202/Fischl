"""The embed editor: /embed, /editembed and the Edit Embed message menu, with saved templates."""

import asyncio
import datetime
import uuid

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, ChannelSelect, Modal, Select, TextInput, View
from firebase_admin import db

YES = "<:yes:1036811164891480194>"
NO = "<:no:1036810470860013639>"
SERVER_TEMPLATE_LIMIT = 25
USER_TEMPLATE_LIMIT = 4
EDITOR_TIMEOUT = 3600
# One announcement channel where the owner's posts always ping its two roles.
PING_CHANNEL = 1396565294582857738
PING_AUTHOR = 692254240290242601
PING_CONTENT = "<@&1391181456822501426> <@&792207033763758081>"
POST_PROMPT = (
    "### 📤 Choose where to post your embed.\n<:reply:1036792837821435976> If you want"
    " to save the embed as a template, you can go back and do so! Posting an embed does"
    " not automatically save it as a template."
)
NEW_TEMPLATE_HINT = (
    "Select a template from the list below. You can only edit your own templates, but"
    " can view others' templates and save as your own."
)
EDIT_TEMPLATE_HINT = (
    "Select a template from the list below. The template content will be applied to"
    " edit the selected message."
)


def now() -> datetime.datetime:
    """Gives the current time in UTC."""
    return datetime.datetime.now(datetime.timezone.utc)


def templates_ref(guild_id, template_id=None):
    """Gives where a server's templates, or one of them, are kept."""
    path = f"Embed Templates/{guild_id}"
    return db.reference(f"{path}/{template_id}" if template_id else path)


async def count_templates(interaction: discord.Interaction):
    """Gives how many templates the server has and how many are the member's."""
    templates = await asyncio.to_thread(templates_ref(interaction.guild_id).get)
    owners = [data.get("template_owner") for data in (templates or {}).values()]
    return len(owners), owners.count(interaction.user.id)


def link_emoji(text: str):
    """Reads a link's emoji text; nothing when it is empty or cannot be read."""
    try:
        return discord.PartialEmoji.from_str(text) if text else None
    except Exception:
        return None


def links_view(links, emojis=None) -> View:
    """Gives a view of link buttons; with `emojis`, an emoji written as a bare name is looked up there first."""
    view = View()
    for link in links:
        emoji = link["emoji"]
        if emojis is None:
            emoji = link_emoji(emoji)
        elif emoji:
            emoji = discord.utils.get(emojis, name=emoji) or emoji
        view.add_item(
            Button(
                label=link["label"],
                url=link["url"],
                emoji=emoji or None,
                style=discord.ButtonStyle.link,
            )
        )
    return view


def text_input(label, placeholder, default=None, **options) -> TextInput:
    """Gives one optional text box of a modal."""
    options.setdefault("required", False)
    return TextInput(label=label, placeholder=placeholder, default=default, **options)


class EmbedEditor:
    """One message being built: its embed, its link buttons and the template or message it came from."""

    def __init__(self, user_id, guild_id, edit_mode=False, message_to_edit=None):
        self.user_id = user_id
        self.guild_id = guild_id
        self.edit_mode = edit_mode
        self.message_to_edit = message_to_edit
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
        self.template_id = None
        self.template_owner = None

    def to_embed(self):
        """Gives the embed as built so far, or nothing when it has no content."""
        if self.is_empty():
            return None
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

    def preview(self) -> discord.Embed:
        """Gives the embed to show in the editor, with a hint when there is no content yet."""
        return self.to_embed() or discord.Embed(
            title="No Content Yet",
            description="Use the buttons below to start building your embed!",
            color=discord.Color.light_gray(),
        )

    def is_empty(self) -> bool:
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

    def to_dict(self) -> dict:
        """Gives the record a template is saved as."""
        return {
            "message_content": self.message_content,
            "embed_data": self.embed_data,
            "button_links": self.button_links,
            "template_owner": self.template_owner or self.user_id,
        }

    @classmethod
    def from_dict(cls, user_id, guild_id, data, template_id=None):
        """Gives an editor filled from a saved template."""
        editor = cls(user_id, guild_id)
        editor.message_content = data.get("message_content", "")
        for key, value in data.get("embed_data", {}).items():
            if isinstance(value, dict) and isinstance(editor.embed_data.get(key), dict):
                editor.embed_data[key].update(value)
            else:
                editor.embed_data[key] = value
        editor.button_links = data.get("button_links", [])
        editor.template_owner = data.get("template_owner")
        editor.template_id = template_id
        return editor

    @classmethod
    def from_embed(cls, user_id, guild_id, message: discord.Message):
        """Gives an editor filled from a posted message, set to edit that message."""
        editor = cls(user_id, guild_id, edit_mode=True, message_to_edit=message)
        editor.message_content = message.content or ""
        if not message.embeds:
            return editor
        embed, data = message.embeds[0], editor.embed_data
        data["title"] = embed.title or ""
        data["description"] = embed.description or ""
        if embed.color:
            data["color"] = embed.color.value
        if embed.footer:
            data["footer"]["text"] = embed.footer.text or ""
            data["footer"]["icon_url"] = embed.footer.icon_url or ""
        if embed.author:
            data["author"]["name"] = embed.author.name or ""
            data["author"]["icon_url"] = embed.author.icon_url or ""
        data["thumbnail"] = embed.thumbnail.url if embed.thumbnail else ""
        data["image"] = embed.image.url if embed.image else ""
        data["fields"] = [
            {"name": field.name, "value": field.value, "inline": field.inline}
            for field in embed.fields
        ]
        data["timestamp"] = embed.timestamp is not None
        return editor


class EmbedModal(Modal):
    """Asks for the embed's title, description, colour, footer text and author name."""

    def __init__(self, editor: EmbedEditor, title="Edit Embed"):
        super().__init__(title=title)
        self.editor = editor
        data = editor.embed_data
        self.add_item(text_input("Title", "Embed title", data["title"], max_length=256))
        self.add_item(
            text_input(
                "Description",
                "Embed description",
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

    async def on_submit(self, interaction: discord.Interaction):
        """Keeps what was typed; a colour that is not `#` and hex digits is ignored."""
        data = self.editor.embed_data
        title, description, color, footer, author = (c.value for c in self.children)
        data["title"], data["description"] = title, description
        color = color.strip()
        if color.startswith("#"):
            try:
                data["color"] = int(color[1:], 16)
            except ValueError:
                pass
        data["footer"]["text"] = footer
        data["author"]["name"] = author
        await interaction.response.defer()


class MediaModal(Modal):
    """Asks for the image, thumbnail, author icon and footer icon links."""

    def __init__(self, editor: EmbedEditor):
        super().__init__(title="Edit Media")
        self.editor = editor
        data = editor.embed_data
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

    async def on_submit(self, interaction: discord.Interaction):
        """Keeps the four links."""
        data = self.editor.embed_data
        image, thumbnail, author_icon, footer_icon = (c.value for c in self.children)
        data["image"], data["thumbnail"] = image, thumbnail
        data["author"]["icon_url"] = author_icon
        data["footer"]["icon_url"] = footer_icon
        await interaction.response.defer()


class FieldModal(Modal):
    """Asks for a field's name, value and whether it is inline; adds a field when no index is given."""

    def __init__(self, editor: EmbedEditor, field_index=None):
        super().__init__(title="Add Field" if field_index is None else "Edit Field")
        self.fields = editor.embed_data["fields"]
        self.field_index = field_index
        field = (
            {"name": "", "value": "", "inline": True}
            if field_index is None
            else self.fields[field_index]
        )
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

    async def on_submit(self, interaction: discord.Interaction):
        """Adds the field or replaces the one being edited."""
        name, value, inline = (c.value for c in self.children)
        field = {"name": name, "value": value, "inline": inline.upper() == "Y"}
        if self.field_index is None:
            self.fields.append(field)
        else:
            self.fields[self.field_index] = field
        await interaction.response.defer()


class ButtonLinkModal(Modal):
    """Asks for a link button's label, link and emoji; adds a link when no index is given."""

    def __init__(self, editor: EmbedEditor, link_index=None):
        super().__init__(title="Add Link" if link_index is None else "Edit Link")
        self.links = editor.button_links
        self.link_index = link_index
        link = (
            {"label": "", "url": "", "emoji": ""}
            if link_index is None
            else self.links[link_index]
        )
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

    async def on_submit(self, interaction: discord.Interaction):
        """Adds the link or replaces the one being edited."""
        label, url, emoji = (c.value for c in self.children)
        link = {"label": label, "url": url, "emoji": emoji}
        if self.link_index is None:
            self.links.append(link)
        else:
            self.links[self.link_index] = link
        await interaction.response.defer()


class SaveModal(Modal):
    """Asks for a name and saves the editor as a new template of the server."""

    def __init__(self, editor: EmbedEditor, is_save_as=False):
        super().__init__(
            title="Save As New Template" if is_save_as else "Save Template"
        )
        self.editor = editor
        self.add_item(
            text_input(
                "Template Name",
                "Give this template a name",
                max_length=100,
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """Saves the template unless the server or the member already has too many."""
        name = self.children[0].value
        total, mine = await count_templates(interaction)
        for count, limit, whose in (
            (total, SERVER_TEMPLATE_LIMIT, "Server"),
            (mine, USER_TEMPLATE_LIMIT, "User"),
        ):
            if count >= limit:
                return await interaction.response.send_message(
                    f"{whose} template limit reached ({limit}). Cannot save new template.",
                    ephemeral=True,
                )
        template_id = str(uuid.uuid4())[:8]
        data = {**self.editor.to_dict(), "name": name, "created_at": now().isoformat()}
        ref = templates_ref(interaction.guild_id, template_id)
        await asyncio.to_thread(ref.set, data)
        await interaction.response.send_message(
            f"{YES} Template saved as **{name}** (ID: `{template_id}`)",
            ephemeral=True,
        )


class WebhookModal(Modal):
    """Asks for the name and avatar a webhook post should carry."""

    def __init__(self):
        super().__init__(title="Webhook Settings")
        self.add_item(
            text_input("Webhook Username", "Custom webhook username", max_length=80)
        )
        self.add_item(text_input("Webhook Avatar URL", "URL for webhook avatar"))

    async def on_submit(self, interaction: discord.Interaction):
        """Closes the modal; the view reads the two answers."""
        await interaction.response.defer()


class EditorView(View):
    """A screen of the editor, shown on the message the editor was opened in."""

    def __init__(self, editor, original_interaction, timeout=EDITOR_TIMEOUT):
        super().__init__(timeout=timeout)
        self.editor = editor
        self.original_interaction = original_interaction

    def content(self):
        """Gives the text shown above the preview."""
        return None

    def preview(self):
        """Gives the embed shown on this screen."""
        return self.editor.preview()

    async def update_message(self, interaction: discord.Interaction = None):
        """Shows this screen, answering `interaction` when one is given."""
        shown = {"content": self.content(), "embed": self.preview(), "view": self}
        if interaction:
            await interaction.response.edit_message(**shown)
        else:
            await self.original_interaction.edit_original_response(**shown)

    async def ask(self, interaction: discord.Interaction, modal: Modal):
        """Shows a modal, waits for it and redraws this screen."""
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()

    async def open(self, screen, interaction: discord.Interaction):
        """Switches to another screen of the same editor."""
        await screen(self.editor, self.original_interaction).update_message(interaction)


class EmbedMainView(EditorView):
    """The editor's first screen: edit parts, save as a template, and post or update."""

    def __init__(self, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(editor, original_interaction)
        if editor.edit_mode:
            self.save_and_post.label = "Update"
        if editor.template_id and editor.template_owner == editor.user_id:
            delete = Button(
                label="Delete Template",
                style=discord.ButtonStyle.danger,
                emoji="🗑️",
                row=1,
            )
            delete.callback = lambda interaction: self.delete_template(
                interaction, delete
            )
            self.add_item(delete)

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.secondary, emoji="📝")
    async def edit_embed(self, interaction: discord.Interaction, button: Button):
        """Asks for the embed's texts and colour."""
        await self.ask(interaction, EmbedModal(self.editor))

    @discord.ui.button(label="Media", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def edit_media(self, interaction: discord.Interaction, button: Button):
        """Asks for the embed's pictures."""
        await self.ask(interaction, MediaModal(self.editor))

    @discord.ui.button(label="Fields", style=discord.ButtonStyle.secondary, emoji="📋")
    async def edit_fields(self, interaction: discord.Interaction, button: Button):
        """Opens the fields screen."""
        await self.open(FieldsEditorView, interaction)

    @discord.ui.button(
        label="Button Links", style=discord.ButtonStyle.secondary, emoji="🔗"
    )
    async def edit_links(self, interaction: discord.Interaction, button: Button):
        """Opens the link buttons screen."""
        await self.open(ButtonLinksEditorView, interaction)

    @discord.ui.button(
        label="Save", style=discord.ButtonStyle.success, emoji="💾", row=1
    )
    async def save_template(self, interaction: discord.Interaction, button: Button):
        """Updates the member's own template, or asks for a name to save a new one."""
        editor = self.editor
        if not (editor.template_id and editor.template_owner == interaction.user.id):
            return await interaction.response.send_modal(SaveModal(editor))
        data = {**editor.to_dict(), "updated_at": now().isoformat()}
        ref = templates_ref(interaction.guild_id, editor.template_id)
        await asyncio.to_thread(ref.update, data)
        await interaction.response.send_message(
            f"{YES} Template (ID: `{editor.template_id}`) updated!", ephemeral=True
        )

    @discord.ui.button(
        label="Save As", style=discord.ButtonStyle.success, emoji="📁", row=1
    )
    async def save_as_template(self, interaction: discord.Interaction, button: Button):
        """Asks for a name to save a new template."""
        await interaction.response.send_modal(SaveModal(self.editor, is_save_as=True))

    @discord.ui.button(label="Post", style=discord.ButtonStyle.green, emoji="📤", row=1)
    async def save_and_post(self, interaction: discord.Interaction, button: Button):
        """Opens the posting screen, or in edit mode writes the changes to the message."""
        editor = self.editor
        if not editor.edit_mode:
            return await self.open(PostEmbedView, interaction)
        message = editor.message_to_edit
        try:
            await message.edit(
                content=editor.message_content or None, embed=editor.to_embed()
            )
            if editor.button_links:
                emojis = interaction.client.emojis
                await message.edit(view=links_view(editor.button_links, emojis))
        except Exception as e:
            return await interaction.response.send_message(
                f"{NO} Failed to update message: {e}", ephemeral=True
            )
        await interaction.response.send_message(
            f"{YES} Embed updated successfully! [Jump to Message]({message.jump_url})",
            ephemeral=True,
        )

    async def delete_template(self, interaction: discord.Interaction, button: Button):
        """Deletes the template this editor was loaded from and keeps the editor open."""
        ref = templates_ref(interaction.guild_id, self.editor.template_id)
        await asyncio.to_thread(ref.delete)
        self.editor.template_id = None
        self.editor.template_owner = None
        self.remove_item(button)
        await interaction.response.send_message(
            f"{YES} Template deleted successfully!", ephemeral=True
        )
        await self.update_message()


class ListEditorView(EditorView):
    """A screen that adds, edits, removes and reorders the entries of one list, picked from a menu."""

    noun = ""
    select_id = ""
    modal = None

    def __init__(self, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(editor, original_interaction)
        self.selected_index = 0 if self.entries() else None
        for button, label in (
            (self.add, f"Add {self.noun}"),
            (self.edit, f"Edit {self.noun}"),
            (self.remove, f"Remove {self.noun}"),
        ):
            button.label = label
        self.update_select()

    def entries(self) -> list:
        """Gives the list this screen edits."""
        raise NotImplementedError

    def option(self, index: int, entry: dict) -> dict:
        """Gives the label and description of one entry in the menu."""
        raise NotImplementedError

    def update_select(self):
        """Rebuilds the menu of entries; there is none while the list is empty."""
        for item in self.children:
            if isinstance(item, Select):
                self.remove_item(item)
        if not self.entries():
            return
        select = Select(
            placeholder=f"Select a {self.noun.lower()} to edit...",
            options=[
                discord.SelectOption(
                    value=str(i), default=i == self.selected_index, **self.option(i, e)
                )
                for i, e in enumerate(self.entries())
            ],
            custom_id=self.select_id,
            row=0,
        )
        select.callback = self.select
        self.add_item(select)

    async def update_message(self, interaction: discord.Interaction = None):
        """Shows this screen with a fresh menu."""
        self.update_select()
        await super().update_message(interaction)

    async def refuse(self, interaction: discord.Interaction, text: str):
        """Answers with a problem only the member sees."""
        await interaction.response.send_message(f"{NO} {text}", ephemeral=True)

    async def select(self, interaction: discord.Interaction):
        """Marks the picked entry."""
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)

    @discord.ui.button(
        label="Add", style=discord.ButtonStyle.success, emoji="➕", row=1
    )
    async def add(self, interaction: discord.Interaction, button: Button):
        """Asks for a new entry and selects the last one."""
        await interaction.response.send_modal(modal := self.modal(self.editor))
        await modal.wait()
        self.selected_index = len(self.entries()) - 1
        await self.update_message()

    @discord.ui.button(
        label="Edit", style=discord.ButtonStyle.primary, emoji="✏️", row=1
    )
    async def edit(self, interaction: discord.Interaction, button: Button):
        """Asks for new values of the selected entry."""
        if self.selected_index is None:
            return await self.refuse(interaction, f"No {self.noun.lower()} selected!")
        await self.ask(interaction, self.modal(self.editor, self.selected_index))

    @discord.ui.button(
        label="Remove", style=discord.ButtonStyle.danger, emoji="🗑️", row=1
    )
    async def remove(self, interaction: discord.Interaction, button: Button):
        """Removes the selected entry and selects its neighbour."""
        if self.selected_index is None:
            return await self.refuse(interaction, f"No {self.noun.lower()} selected!")
        entries = self.entries()
        entries.pop(self.selected_index)
        last = len(entries) - 1
        self.selected_index = min(self.selected_index, last) if entries else None
        await self.update_message(interaction)

    async def move(self, interaction: discord.Interaction, step: int):
        """Swaps the selected entry with the one `step` places away, if there is one."""
        entries, at = self.entries(), self.selected_index
        if at is None or not 0 <= at + step < len(entries):
            way = "up" if step < 0 else "down"
            return await self.refuse(interaction, f"Cannot move {way}!")
        entries[at], entries[at + step] = entries[at + step], entries[at]
        self.selected_index = at + step
        await self.update_message(interaction)

    @discord.ui.button(
        label="Move Up", style=discord.ButtonStyle.secondary, emoji="⬆️", row=2
    )
    async def move_up(self, interaction: discord.Interaction, button: Button):
        """Moves the selected entry one place earlier."""
        await self.move(interaction, -1)

    @discord.ui.button(
        label="Move Down", style=discord.ButtonStyle.secondary, emoji="⬇️", row=2
    )
    async def move_down(self, interaction: discord.Interaction, button: Button):
        """Moves the selected entry one place later."""
        await self.move(interaction, 1)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        """Goes back to the first screen."""
        await self.open(EmbedMainView, interaction)


class FieldsEditorView(ListEditorView):
    """The screen for the embed's fields."""

    noun = "Field"
    select_id = "fields_select"
    modal = FieldModal

    def entries(self) -> list:
        """Gives the embed's fields."""
        return self.editor.embed_data["fields"]

    def option(self, index: int, entry: dict) -> dict:
        """Shows a field by its name and the start of its value."""
        return {
            "label": entry["name"][:100] or f"Field {index + 1}",
            "description": entry["value"][:100] if entry["value"] else "No content",
        }


class ButtonLinksEditorView(ListEditorView):
    """The screen for the link buttons, which also sends a preview of them after each change."""

    noun = "Link"
    select_id = "links_select"
    modal = ButtonLinkModal

    def entries(self) -> list:
        """Gives the link buttons."""
        return self.editor.button_links

    def option(self, index: int, entry: dict) -> dict:
        """Shows a link by its label and the start of its address."""
        return {
            "label": entry["label"][:100] or f"Link {index + 1}",
            "description": entry["url"][:100],
        }

    async def update_message(self, interaction: discord.Interaction = None):
        """Shows this screen, then the buttons as they will look when there are any."""
        await super().update_message(interaction)
        if self.editor.button_links:
            followup = (interaction or self.original_interaction).followup
            await followup.send(
                "**Button Preview:**",
                view=links_view(self.editor.button_links),
                ephemeral=True,
            )


class PostEmbedView(EditorView):
    """The screen that posts the embed in a chosen channel, as the bot or through a webhook."""

    def __init__(self, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(editor, original_interaction, timeout=1800)
        self.selected_channel = None
        self.use_webhook = False
        self.webhook_data = {"username": "", "avatar_url": ""}
        self.channel_select = ChannelSelect(placeholder="Select channel to post...")
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)

    def content(self):
        """Gives the posting instructions."""
        return POST_PROMPT

    def preview(self):
        """Shows the embed exactly as it will be posted."""
        return self.editor.to_embed()

    async def select_channel(self, interaction: discord.Interaction):
        """Remembers the picked channel."""
        self.selected_channel = self.channel_select.values[0]
        await interaction.response.defer()

    @discord.ui.button(
        label="Use Webhook", style=discord.ButtonStyle.secondary, emoji="🪝", row=1
    )
    async def toggle_webhook(self, interaction: discord.Interaction, button: Button):
        """Asks for a webhook name and avatar to post under."""
        modal = WebhookModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.use_webhook = True
        self.webhook_data["username"] = modal.children[0].value
        self.webhook_data["avatar_url"] = modal.children[1].value
        await interaction.followup.send(
            f"{YES} Webhook settings saved!", ephemeral=True
        )

    async def send(self, channel, user_id: int):
        """Posts the message in the channel, through a short-lived webhook when a name was given."""
        editor, embed = self.editor, self.editor.to_embed()
        content = editor.message_content or None
        if self.use_webhook and self.webhook_data["username"]:
            webhook = await channel.create_webhook(name="Embed Bot")
            await webhook.send(
                content=content,
                embed=embed,
                username=self.webhook_data["username"],
                avatar_url=self.webhook_data["avatar_url"] or None,
            )
            return await webhook.delete()
        if channel.id == PING_CHANNEL and user_id == PING_AUTHOR:
            content = PING_CONTENT
        links = editor.button_links
        await channel.send(
            content=content, embed=embed, view=links_view(links) if links else None
        )

    @discord.ui.button(label="Post", style=discord.ButtonStyle.green, emoji="📤", row=1)
    async def post_embed(self, interaction: discord.Interaction, button: Button):
        """Posts the embed in the picked channel and goes back to the first screen."""
        channel = self.selected_channel
        if channel is None:
            return await interaction.response.send_message(
                f"{NO} Please select a channel first!", ephemeral=True
            )
        if not hasattr(channel, "send"):
            channel = interaction.guild.get_channel(channel.id)
        if not channel:
            return await interaction.response.send_message(
                f"{NO} Channel not found!", ephemeral=True
            )
        try:
            await self.send(channel, interaction.user.id)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{NO} I don't have permission to send messages in that channel!",
                ephemeral=True,
            )
        except Exception as e:
            return await interaction.response.send_message(
                f"{NO} Error posting embed: {e}", ephemeral=True
            )
        await interaction.response.send_message(
            f"{YES} Embed posted in {channel.mention}!", ephemeral=True
        )
        await self.open(EmbedMainView, None)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=1)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        """Goes back to the first screen."""
        await self.open(EmbedMainView, interaction)


async def owner_name(bot, owner_id) -> str:
    """Gives a template owner's name, or Unknown when they cannot be found."""
    try:
        return str(bot.get_user(owner_id) or await bot.fetch_user(owner_id))
    except Exception:
        return "Unknown"


class TemplateSelectView(View):
    """A menu of the server's templates; the picked one opens in the editor, for `target_message` if given."""

    def __init__(self, user_id, guild_id, target_message=None):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id
        self.target_message = target_message
        self.template_data = {}

    async def load_templates(self, bot):
        """Fills the menu with the server's templates and who made each."""
        try:
            ref = templates_ref(self.guild_id)
            self.template_data = await asyncio.to_thread(ref.get) or {}
            owners = {d.get("template_owner") for d in self.template_data.values()}
            owners -= {None, self.user_id}
            found = await asyncio.gather(*(owner_name(bot, o) for o in owners))
            names = dict(zip(owners, found))
            options = []
            for template_id, data in self.template_data.items():
                owner = data.get("template_owner")
                mine = owner == self.user_id
                label = f"{data.get('name', 'Unnamed Template')} {'(Yours)' if mine else ''}"
                by = "Your template" if mine else f"By {names.get(owner, 'Unknown')}"
                options.append(
                    discord.SelectOption(
                        label=label[:100], value=template_id, description=by
                    )
                )
        except Exception as e:
            return print(f"Error loading templates: {e}")
        if not options:
            none = [discord.SelectOption(label="No templates", value="none")]
            return self.add_item(
                Select(
                    placeholder="No templates available", options=none, disabled=True
                )
            )
        select = Select(placeholder="Choose a template...", options=options)
        select.callback = self.select_template
        self.add_item(select)

    async def select_template(self, interaction: discord.Interaction):
        """Opens the picked template in the editor."""
        template_id = interaction.data["values"][0]
        editor = EmbedEditor.from_dict(
            self.user_id,
            self.guild_id,
            self.template_data[template_id],
            template_id=template_id,
        )
        if self.target_message:
            editor.edit_mode = True
            editor.message_to_edit = self.target_message
        await EmbedMainView(editor, interaction).update_message(interaction)


class StartView(View):
    """The first choice: start from nothing (or the message's content), or from a template."""

    def __init__(self, total_templates: int, target_message=None):
        super().__init__(timeout=60)
        self.target_message = target_message
        self.from_template.disabled = total_templates == 0
        if target_message:
            self.fresh.label = "Load from Existing Content"
            self.from_template.label = "Load from Template"

    @discord.ui.button(
        label="Create New Blank Embed", style=discord.ButtonStyle.primary
    )
    async def fresh(self, interaction: discord.Interaction, button: Button):
        """Opens the editor empty, or filled from the message being edited."""
        ids = interaction.user.id, interaction.guild_id
        if self.target_message:
            editor = EmbedEditor.from_embed(*ids, self.target_message)
        else:
            editor = EmbedEditor(*ids)
        await EmbedMainView(editor, interaction).update_message(interaction)

    @discord.ui.button(
        label="Create from Template", style=discord.ButtonStyle.secondary
    )
    async def from_template(self, interaction: discord.Interaction, button: Button):
        """Shows the menu of templates."""
        view = TemplateSelectView(
            interaction.user.id, interaction.guild_id, self.target_message
        )
        await view.load_templates(interaction.client)
        hint = EDIT_TEMPLATE_HINT if self.target_message else NEW_TEMPLATE_HINT
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Choose a Template",
                description=hint,
                color=discord.Color.blue(),
            ),
            view=view,
        )


async def start(interaction: discord.Interaction, message: discord.Message = None):
    """Answers with the first choice, for a new embed or for editing `message`."""
    try:
        total, mine = await count_templates(interaction)
    except Exception:
        total, mine = 0, 0
    counts = f"({total} total in server, {mine} yours)"
    if message:
        title = "Edit Embed"
        description = (
            "Choose how to edit the selected message:\n\n"
            "- **Load from Existing Content** - Edit the current content of the message\n"
            "- **Load from Template** - Apply a template to replace the message content "
        )
    else:
        title = "Embed Editor"
        description = (
            "Choose how you want to create your embed:\n\n"
            "- **Create New Blank Embed** - Start from scratch\n"
            "- **Create from Template** - Use a saved template "
        )
    await interaction.response.send_message(
        embed=discord.Embed(
            title=title, description=description + counts, color=discord.Color.blue()
        ),
        view=StartView(total, message),
        ephemeral=True,
    )


async def report_error(interaction: discord.Interaction, error: Exception):
    """Tells the member they lack administrator, or what went wrong."""
    if isinstance(error, app_commands.MissingPermissions):
        text = "You need administrator permissions to use this command!"
    else:
        text = f"An error occurred: {error}"
    await interaction.response.send_message(f"{NO} {text}", ephemeral=True)


class EmbedCommand(commands.Cog):
    """The /embed and /editembed commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="embed", description="Create and customize embeds with an advanced editor"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def embed(self, interaction: discord.Interaction) -> None:
        """Opens the editor for a new embed."""
        await start(interaction)

    @app_commands.command(name="editembed", description="Edits a custom embed message")
    @app_commands.describe(
        id="The message ID of the embed",
        channel="The Discord text channel where the embed is located",
        thread="(Optional & Overrides) The thread where the embed is located",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def editembed(
        self,
        interaction: discord.Interaction,
        id: str,
        channel: discord.TextChannel,
        thread: discord.Thread = None,
    ) -> None:
        """Opens the editor for a posted message, given as its ID or as `channel-message`."""
        message_id = int(id.split("-")[1]) if "-" in id else int(id)
        await start(interaction, await (thread or channel).fetch_message(message_id))

    @embed.error
    @editembed.error
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """Tells the member why the command did not run."""
        await report_error(interaction, error)


@app_commands.context_menu(name="Edit Embed")
@app_commands.checks.has_permissions(administrator=True)
async def edit_embed_context_menu(
    interaction: discord.Interaction, message: discord.Message
):
    """Opens the editor for one of the bot's own messages."""
    if message.author != interaction.client.user:
        return await interaction.response.send_message(
            "❌ You can only edit messages sent by this bot!", ephemeral=True
        )
    await start(interaction, message)


@edit_embed_context_menu.error
async def edit_embed_context_menu_error(interaction, error):
    """Tells the member why the menu entry did not run."""
    await report_error(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedCommand(bot))
    bot.tree.add_command(edit_embed_context_menu)
