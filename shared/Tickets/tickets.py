import discord
import datetime
import asyncio
import time
import uuid
import re
import hashlib
import os
import aiohttp

from groq import Groq
from collections import defaultdict
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput, ChannelSelect, RoleSelect, UserSelect
from assets.secret import GROQ_API_KEY

async def generate(prompt: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
    )

    return chat_completion.choices[0].message.content

async def create_ticket(interaction, topic=None, custom_opening_message=None, closing_message=None):
    await interaction.response.defer(ephemeral=True, thinking=True)
    ref = db.reference("/Tickets")
    tickets = ref.get()
    found = False
    for key, value in tickets.items():
        if value["Server ID"] == interaction.guild.id:
            CATEGORY_ID = value["Category ID"]
            LOGCHANNEL_ID = value["Log Channel ID"]
            try:
                COOLDOWN_IN_SECONDS = value["Cooldown"]
            except Exception:
                COOLDOWN_IN_SECONDS = 0
            try:
                PING_ROLE_ID = value["Ping Role ID"]
            except Exception:
                PING_ROLE_ID = None
            found = True
            break

    if not found:
        embed = discord.Embed(
            title="Ticket not enabled!",
            description=f"This server doesn't have a ticket category or a log channel. Please ask the server moderator to use `/ticket setup` to setup tickets!",
            colour=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    category = interaction.guild.get_channel(CATEGORY_ID)

    for channel in category.channels:
        if str(channel.topic) == str(interaction.user.id):
            await interaction.followup.send(
                content=f"<:no:1036810470860013639> You already had your ticket created at <#{channel.id}>.",
                ephemeral=True,
            )
            return
        
    blacklist_ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}/{interaction.user.id}").get()
    if blacklist_ref:
        await interaction.followup.send(f"<:no:1036810470860013639> You are blacklisted from creating tickets in **{interaction.guild.name}**.", ephemeral=True)
        return
    
    last_created_ref = db.reference(f"/Tickets Cooldown/{interaction.guild.id}/users/{interaction.user.id}/last_created")
    last_created = last_created_ref.get()
    if last_created and (time.time() - last_created) < COOLDOWN_IN_SECONDS:
        remaining = COOLDOWN_IN_SECONDS - (time.time() - last_created)
        await interaction.followup.send(f"<:no:1036810470860013639> You are on a cooldown! Try again in **{int(remaining // 3600)}h {int((remaining % 3600) // 60)}m**.", ephemeral=True)
        return

    log = interaction.guild.get_channel(LOGCHANNEL_ID)
    embed = discord.Embed(
        title="Ticket created",
        description=f"**{interaction.user.mention}** created a new ticket <t:{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}:R>!",
        color=discord.Colour.green(),
    )

    # LEGACY TICKET INSTRUCTIONS HANDLING
    special_embed = None
    if topic is None:
        try:
            createembed = interaction.message.embeds[0]
            if "Are you sure you want to make a ticket" in createembed.description:
                topic = f"{createembed.description.split('**')[1]}"
                embed.add_field(name="Ticket Topic", value=topic)
            else:
                topic = f"{createembed.title}"
                embed.add_field(name="Ticket Topic", value=topic)
            ref = db.reference(f"/Ticket Instructions/{interaction.guild.id}")
            instructions = ref.get()
            if instructions:
                for i, (cat, embed_info) in enumerate(instructions.items()):
                    if cat.strip().lower() == topic.strip().lower():
                        special_embed = discord.Embed(
                            title=embed_info.get("title", ""),
                            description=embed_info.get("description", ""),
                            color=int(embed_info.get("color", "#5865F2").lstrip('#'), 16)
                        )
                        break
        except Exception:
            topic = ""
    else:
        embed.add_field(name="Ticket Topic", value=topic)

    # SPECIAL TOPICS
    channel_extension = None
    if interaction.guild.id == 1094228164324114493:  # Lumine Mains
        if "general" in topic.lower():
            channel_extension = "support"
        elif "role" in topic.lower():
            channel_extension = "role"
        elif "partner" in topic.lower():
            channel_extension = "partner"
        else:
            channel_extension = None
    elif interaction.guild.id == 1197491630807199834:
        if "partner" in topic.lower():
            category = interaction.guild.get_channel(1253988610194018384)
            log = interaction.guild.get_channel(1235251162056495226)
        elif "help" in topic.lower():
            channel_extension = "support"
        elif "rule" in topic.lower():
            channel_extension = "report"

    try:
        if channel_extension is not None:
            chn = await interaction.guild.create_text_channel(
                f"{interaction.user.name}-{channel_extension}", category=category
            )
        else:
            chn = await interaction.guild.create_text_channel(
                f"{interaction.user.name}", category=category
            )

        await chn.edit(topic=interaction.user.id)
        await chn.set_permissions(
            interaction.user, send_messages=True, read_messages=True, attach_files=True
        )
        ticket_creation_message = f"**{interaction.user.mention}, welcome!**"
        if interaction.guild.id == 791534106919305226 and "Club/Clan Applications" in topic:
            club_president_role = interaction.guild.get_role(1429160134084661429)
            if club_president_role:
                await chn.set_permissions(club_president_role, send_messages=True, read_messages=True, attach_files=True)
                ticket_creation_message = f"<@&1429160134084661429> A new club/clan application has been created by {interaction.user.mention}."
    except Exception:
        await interaction.followup.send(
            content=f"<:no:1036810470860013639> **I'm missing permissions to create or edit text channels!** \nPlease make sure my role has `MANAGE_CHANNELS` permissions.", ephemeral=True
        )
        return

    try:
        embed.set_author(
            name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url
        )
    except Exception:
        embed.set_author(name=f"{interaction.user.name}")
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(text=f"Ticket ID: {chn.id}")

    button = Button(
        style=discord.ButtonStyle.link,
        label="View Ticket",
        url=f"https://discord.com/channels/{interaction.guild.id}/{chn.id}",
    )
    view = View()
    view.add_item(button)
    await log.send(embed=embed, view=view)
    embed.title = f"Ticket created in {interaction.guild.name}"
    await interaction.client.get_channel(1417408712980697099).send(embed=embed)

    roles = interaction.user.roles
    roles.reverse()

    embed = discord.Embed(
        title=topic if topic else "New Ticket",
        description=f"Type your message here in this channel!\nYou can use </ticket close:1254927191129456641> or click the red button below to close this ticket.",
        color=discord.Colour.gold(),
    )
    if custom_opening_message:
        embed.description = f"> {custom_opening_message}\n\nYou can use </ticket close:1254927191129456641> or click the red button below to close this ticket."
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.add_field(
        name="User Mention", value=f"{interaction.user.mention}", inline=True
    )
    embed.add_field(name="User ID", value=f"{interaction.user.id}", inline=True)
    embed.add_field(name="Highest Role", value=f"{roles[0].mention}", inline=True)
    embed.add_field(
        name="Ticket Created",
        value=f"<t:{int(chn.created_at.timestamp())}:R>",
        inline=True,
    )
    embed.add_field(
        name="Server Joined",
        value=f"<t:{int(interaction.user.joined_at.timestamp())}:R>",
        inline=True,
    )
    embed.add_field(
        name="Account Created",
        value=f"<t:{int(interaction.user.created_at.timestamp())}:R>",
        inline=True,
    )
    await chn.send(
        f"{ticket_creation_message} {f'||<@&{PING_ROLE_ID}>||' if PING_ROLE_ID is not None else ''}",
        embed=embed,
        view=CloseTicketButton(),
    )
    if special_embed is not None:
        await chn.send(embed=special_embed)

    await interaction.followup.send(
        content=f"<:yes:1036811164891480194> Ticket created at <#{chn.id}>", ephemeral=True
    )
    
    if closing_message:
        db.reference(f"/Ticket Closing Messages/{chn.id}").set(closing_message)
    
    last_created_ref.set(time.time())

class TicketPanelEditor:
    def __init__(self, user_id, guild_id, panel_type, panel_id=None, existing_data=None):
        self.user_id = user_id
        self.guild_id = guild_id
        self.panel_type = panel_type  # "dropdown" or "button"
        self.panel_id = panel_id
        self.embed_data = {
            "title": "",
            "description": "",
            "color": discord.Color.blurple().value,
            "footer": {"text": "", "icon_url": ""},
            "author": {"name": "", "icon_url": ""},
            "thumbnail": "",
            "image": "",
            "fields": [],
            "timestamp": False
        }
        self.options = []  # [{label, value, description, emoji, opening_message, closing_message}]
        self.buttons = []  # [{label, emoji, color, opening_message, closing_message}]
        self.message_id = None
        
        if existing_data:
            self.load_from_dict(existing_data)
    
    def load_from_dict(self, data):
        default_embed = {
            "title": "",
            "description": "",
            "color": discord.Color.blurple().value,
            "footer": {"text": "", "icon_url": ""},
            "author": {"name": "", "icon_url": ""},
            "thumbnail": "",
            "image": "",
            "fields": [],
            "timestamp": False
        }
        
        if "embed" in data:
            self.embed_data = {**default_embed, **data["embed"]}
        else:
            self.embed_data = default_embed
            
        self.options = data.get("options", [])
        for option in self.options:
            option.setdefault("closing_message", "")
        self.buttons = data.get("buttons", [])
        for button in self.buttons:
            button.setdefault("closing_message", "")
        self.message_id = data.get("message_id")
    
    def to_dict(self):
        return {
            "embed": self.embed_data,
            "options": self.options,
            "buttons": self.buttons,
            "message_id": self.message_id,
            "type": self.panel_type
        }
    
    def is_empty(self):
        return (
            not self.embed_data["title"] and
            not self.embed_data["description"] and
            not self.embed_data["image"] and
            not self.embed_data["thumbnail"] and
            not self.embed_data["fields"] and
            not self.embed_data["author"]["name"] and
            not self.embed_data["footer"]["text"]
        )
    
    def to_embed(self):
        embed = discord.Embed(
            title=self.embed_data["title"] or None,
            description=self.embed_data["description"] or None,
            color=self.embed_data["color"]
        )
        
        if self.embed_data["footer"]["text"]:
            embed.set_footer(
                text=self.embed_data["footer"]["text"],
                icon_url=self.embed_data["footer"]["icon_url"] or None
            )
        
        if self.embed_data["author"]["name"]:
            embed.set_author(
                name=self.embed_data["author"]["name"],
                icon_url=self.embed_data["author"]["icon_url"] or None
            )
        
        if self.embed_data["thumbnail"]:
            embed.set_thumbnail(url=self.embed_data["thumbnail"])

        if self.embed_data["image"]:
            embed.set_image(url=self.embed_data["image"])
        
        for field in self.embed_data["fields"]:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field["inline"]
            )
        
        if self.embed_data["timestamp"]:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            
        return embed

class EmbedModal(discord.ui.Modal):
    def __init__(self, editor: TicketPanelEditor):
        super().__init__(title="Edit Embed")
        self.editor = editor
        
        self.add_item(discord.ui.TextInput(
            label="Title",
            placeholder="Panel title",
            default=editor.embed_data["title"],
            max_length=256,
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Description", 
            placeholder="Panel description",
            default=editor.embed_data["description"],
            max_length=4000,
            required=False,
            style=discord.TextStyle.paragraph
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Color (Hex)",
            placeholder="#FF0000",
            default=f"#{editor.embed_data['color']:06x}",
            max_length=7,
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Footer Text",
            placeholder="Footer text",
            default=editor.embed_data["footer"]["text"],
            max_length=2048,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="Author Name",
            placeholder="Author name",
            default=editor.embed_data["author"]["name"],
            max_length=256,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        self.editor.embed_data["title"] = self.children[0].value
        self.editor.embed_data["description"] = self.children[1].value
        
        color_str = self.children[2].value.strip()
        if color_str and color_str.startswith("#"):
            try:
                self.editor.embed_data["color"] = int(color_str[1:], 16)
            except ValueError:
                pass
        
        self.editor.embed_data["footer"]["text"] = self.children[3].value
        self.editor.embed_data["author"]["name"] = self.children[4].value
        await interaction.response.defer()

class MediaModal(discord.ui.Modal):
    def __init__(self, editor: TicketPanelEditor):
        super().__init__(title="Edit Media")
        self.editor = editor
        
        self.add_item(discord.ui.TextInput(
            label="Image URL",
            placeholder="Main image/banner URL",
            default=editor.embed_data["image"],
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Thumbnail URL",
            placeholder="Thumbnail image URL", 
            default=editor.embed_data["thumbnail"],
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Author Icon URL",
            placeholder="Author icon URL",
            default=editor.embed_data["author"]["icon_url"],
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Footer Icon URL",
            placeholder="Footer icon URL",
            default=editor.embed_data["footer"]["icon_url"],
            required=False
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        self.editor.embed_data["image"] = self.children[0].value
        self.editor.embed_data["thumbnail"] = self.children[1].value
        self.editor.embed_data["author"]["icon_url"] = self.children[2].value
        self.editor.embed_data["footer"]["icon_url"] = self.children[3].value
        await interaction.response.defer()

class FieldModal(discord.ui.Modal):
    def __init__(self, editor: TicketPanelEditor, field_index=None):
        super().__init__(title="Edit Field" if field_index is not None else "Add Field")
        self.editor = editor
        self.field_index = field_index
        
        field_data = editor.embed_data["fields"][field_index] if field_index is not None else {"name": "", "value": "", "inline": True}
        
        self.add_item(discord.ui.TextInput(
            label="Field Name",
            placeholder="Field title",
            default=field_data["name"],
            max_length=256,
            required=True
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Field Value",
            placeholder="Field content",
            default=field_data["value"],
            max_length=1024,
            required=True,
            style=discord.TextStyle.paragraph
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Inline (Y/N)",
            placeholder="Y for inline, N for not inline",
            default="Y" if field_data["inline"] else "N",
            max_length=1,
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        inline = self.children[2].value.upper() == "Y"
        
        field_data = {
            "name": self.children[0].value,
            "value": self.children[1].value,
            "inline": inline
        }
        
        if self.field_index is not None:
            self.editor.embed_data["fields"][self.field_index] = field_data
        else:
            self.editor.embed_data["fields"].append(field_data)
        
        await interaction.response.defer()

class SaveModal(discord.ui.Modal):
    def __init__(self, editor: TicketPanelEditor, is_save_as=False):
        title = "Save As New Panel" if is_save_as else "Save Panel"
        super().__init__(title=title)
        self.editor = editor
        self.is_save_as = is_save_as
        
        default_name = ""
        if not is_save_as and self.editor.panel_id:
            try:
                ref = db.reference(f"Ticket Panels/{self.editor.guild_id}/{self.editor.panel_type}/{self.editor.panel_id}")
                data = ref.get()
                if data and "name" in data:
                    default_name = data["name"]
            except:
                pass
        
        self.add_item(discord.ui.TextInput(
            label="Panel Name",
            placeholder="Give this panel a name",
            default=default_name,
            max_length=100,
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        panel_name = self.children[0].value
        
        if self.editor.panel_type == "dropdown" and len(self.editor.options) > 25:
            await interaction.response.send_message("Dropdown panels can have a maximum of 25 options.", ephemeral=True)
            return
        
        if self.editor.panel_type == "button" and len(self.editor.buttons) > 5:
            await interaction.response.send_message("Button panels can have a maximum of 5 buttons.", ephemeral=True)
            return
        
        if self.is_save_as or not self.editor.panel_id:
            ref_base = db.reference(f"Ticket Panels/{interaction.guild_id}/{self.editor.panel_type}")
            panels = ref_base.get() or {}
            if len(panels) >= 25:
                panel_type_name = "dropdown" if self.editor.panel_type == "dropdown" else "button"
                await interaction.response.send_message(f"Server {panel_type_name} panel limit reached (25). Cannot save new panel.", ephemeral=True)
                return
        
        if self.is_save_as or not self.editor.panel_id:
            panel_id = str(uuid.uuid4())[:8]
        else:
            panel_id = self.editor.panel_id
        
        ref = db.reference(f"Ticket Panels/{interaction.guild_id}/{self.editor.panel_type}/{panel_id}")
        data = self.editor.to_dict()
        data["name"] = panel_name
        data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ref.set(data)
        
        self.editor.panel_id = panel_id
        
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> Panel saved as **{panel_name}** (ID: `{panel_id}`)",
            ephemeral=True
        )

class FieldsEditorView(discord.ui.View):
    def __init__(self, cog, editor: TicketPanelEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_index = 0 if editor.embed_data["fields"] else None
        self.update_select()
    
    def update_select(self):
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        
        if self.editor.embed_data["fields"]:
            options = []
            for i, field in enumerate(self.editor.embed_data["fields"]):
                label = field["name"][:50] if field["name"] else f"Field {i+1}"
                options.append(discord.SelectOption(label=label, value=str(i)))
            
            select = discord.ui.Select(placeholder="Select a field to edit", options=options)
            select.callback = self.select_field
            self.add_item(select)
    
    async def update_message(self, interaction: discord.Interaction = None):
        self.update_select()
        embed = self.editor.to_embed()
        content = None
        
        if self.editor.is_empty():
            embed = discord.Embed(
                title="Fields Editor",
                description="Add and manage embed fields for your ticket panel.",
                color=discord.Color.light_gray()
            )
        
        if interaction:
            await interaction.response.edit_message(content=content, embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    async def select_field(self, interaction: discord.Interaction):
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FieldModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Edit Field", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("Please select a field first!", ephemeral=True)
            return
        modal = FieldModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Remove Field", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("Please select a field first!", ephemeral=True)
            return
        self.editor.embed_data["fields"].pop(self.selected_index)
        self.selected_index = None
        await self.update_message(interaction)
    
    @discord.ui.button(label="Move Up", style=discord.ButtonStyle.secondary, emoji="⬆️", row=2)
    async def move_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None or self.selected_index == 0:
            await interaction.response.send_message("Cannot move this field up!", ephemeral=True)
            return
        self.editor.embed_data["fields"][self.selected_index], self.editor.embed_data["fields"][self.selected_index - 1] = \
            self.editor.embed_data["fields"][self.selected_index - 1], self.editor.embed_data["fields"][self.selected_index]
        self.selected_index -= 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Move Down", style=discord.ButtonStyle.secondary, emoji="⬇️", row=2)
    async def move_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None or self.selected_index == len(self.editor.embed_data["fields"]) - 1:
            await interaction.response.send_message("Cannot move this field down!", ephemeral=True)
            return
        self.editor.embed_data["fields"][self.selected_index], self.editor.embed_data["fields"][self.selected_index + 1] = \
            self.editor.embed_data["fields"][self.selected_index + 1], self.editor.embed_data["fields"][self.selected_index]
        self.selected_index += 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class DropdownOptionModal(discord.ui.Modal):
    def __init__(self, editor: TicketPanelEditor, option_index=None):
        title = "Edit Option" if option_index is not None else "Add Option"
        super().__init__(title=title)
        self.editor = editor
        self.option_index = option_index
        
        option_data = editor.options[option_index] if option_index is not None else {
            "label": "", "value": "", "description": "", "emoji": "", "opening_message": "", "closing_message": ""
        }
        
        self.add_item(discord.ui.TextInput(
            label="Option Label",
            placeholder="Text shown in dropdown",
            default=option_data["label"],
            max_length=100,
            required=True
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Description",
            placeholder="Optional description",
            default=option_data["description"],
            max_length=100,
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Emoji",
            placeholder="Format: <:name:id> or unicode emoji",
            default=option_data["emoji"],
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Opening Message",
            placeholder="Message sent when ticket is created",
            default=option_data["opening_message"],
            style=discord.TextStyle.paragraph,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="Closing Message",
            placeholder="Message sent when ticket is closed",
            default=option_data["closing_message"],
            style=discord.TextStyle.paragraph,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        if self.option_index is None and len(self.editor.options) >= 25:
            await interaction.response.send_message("Dropdown panels can have a maximum of 25 options.", ephemeral=True)
            return
        
        option_data = {
            "label": self.children[0].value,
            "value": self.children[0].value,
            "description": self.children[1].value,
            "emoji": self.children[2].value,
            "opening_message": self.children[3].value,
            "closing_message": self.children[4].value
        }
        
        if self.option_index is not None:
            self.editor.options[self.option_index] = option_data
        else:
            self.editor.options.append(option_data)
        
        await interaction.response.defer()

class ButtonOptionModal(discord.ui.Modal):
    def __init__(self, editor: TicketPanelEditor, button_index=None):
        title = "Edit Button" if button_index is not None else "Add Button"
        super().__init__(title=title)
        self.editor = editor
        self.button_index = button_index
        
        button_data = editor.buttons[button_index] if button_index is not None else {
            "label": "", "emoji": "", "color": "grey", "opening_message": "", "closing_message": ""
        }
        
        self.add_item(discord.ui.TextInput(
            label="Button Label",
            placeholder="Text shown on button",
            default=button_data["label"],
            max_length=80,
            required=True
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Emoji",
            placeholder="Format: <:name:id> or unicode emoji",
            default=button_data["emoji"],
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Color",
            placeholder="green, blue, red, or grey",
            default=button_data["color"],
            required=True
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Opening Message",
            placeholder="Message sent when ticket is created",
            default=button_data["opening_message"],
            style=discord.TextStyle.paragraph,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="Closing Message",
            placeholder="Message sent when ticket is closed",
            default=button_data["closing_message"],
            style=discord.TextStyle.paragraph,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        if self.button_index is None and len(self.editor.buttons) >= 5:
            await interaction.response.send_message("Button panels can have a maximum of 5 buttons.", ephemeral=True)
            return
        
        color_str = self.children[2].value.lower()
        color_map = {
            "green": discord.ButtonStyle.green,
            "blue": discord.ButtonStyle.blurple,
            "red": discord.ButtonStyle.red,
            "grey": discord.ButtonStyle.gray
        }
        color = color_map.get(color_str, discord.ButtonStyle.grey)
        
        button_data = {
            "label": self.children[0].value,
            "emoji": self.children[1].value,
            "color": color_str,
            "style": color.value,
            "opening_message": self.children[3].value,
            "closing_message": self.children[4].value
        }
        
        if self.button_index is not None:
            self.editor.buttons[self.button_index] = button_data
        else:
            self.editor.buttons.append(button_data)
        
        await interaction.response.defer()

class TicketPanelMainView(discord.ui.View):
    def __init__(self, cog, editor: TicketPanelEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        
        if self.editor.panel_type != "dropdown":
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.label == "Manage Options":
                    child.label = "Manage Buttons"
                    break
        
        if self.editor.panel_id:
            delete_button = discord.ui.Button(label="Delete Panel", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
            delete_button.callback = self.delete_panel
            self.add_item(delete_button)
    
    async def update_message(self, interaction: discord.Interaction = None):
        embed = self.editor.to_embed()
        content = None
        
        if self.editor.is_empty():
            embed = discord.Embed(
                title="No Content Yet",
                description="Use the buttons below to start building your ticket panel!",
                color=discord.Color.light_gray()
            )
        
        if interaction:
            await interaction.response.edit_message(content=content, embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.secondary, emoji="📝")
    async def edit_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EmbedModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Media", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def edit_media(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MediaModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Fields", style=discord.ButtonStyle.secondary, emoji="📋")
    async def edit_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = FieldsEditorView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Manage Options", 
                      style=discord.ButtonStyle.primary, emoji="⚙️")
    async def manage_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.editor.panel_type == "dropdown":
            view = DropdownOptionsView(self.cog, self.editor, self.original_interaction)
        else:
            view = ButtonOptionsView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Save", style=discord.ButtonStyle.success, emoji="💾", row=1)
    async def save_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SaveModal(self.editor, is_save_as=False)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Save As", style=discord.ButtonStyle.success, emoji="📁", row=1)
    async def save_as_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SaveModal(self.editor, is_save_as=True)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Post Panel", style=discord.ButtonStyle.green, emoji="📤", row=1)
    async def post_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PostPanelView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Update Posted", style=discord.ButtonStyle.blurple, emoji="🔄", row=1)
    async def update_posted(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.editor.message_id:
            await interaction.response.send_message(
                "<:no:1036810470860013639> This panel hasn't been posted yet!",
                ephemeral=True
            )
            return
        
        try:
            channel = self.original_interaction.channel
            message = await channel.fetch_message(self.editor.message_id)
            panel_view = await self.create_panel_view()
            
            await message.edit(embed=self.editor.to_embed(), view=panel_view)
            await interaction.response.send_message(
                f"<:yes:1036811164891480194> Posted panel updated!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"<:no:1036810470860013639> Failed to update panel: {str(e)}",
                ephemeral=True
            )
    
    async def delete_panel(self, interaction: discord.Interaction):
        button = None
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label == "Delete Panel":
                button = item
                break
        if not button:
            return
        
        try:
            if self.editor.message_id:
                channel = self.original_interaction.channel
                message = await channel.fetch_message(self.editor.message_id)
                await message.delete()
            
            ref = db.reference(f"Ticket Panels/{interaction.guild_id}/{self.editor.panel_type}/{self.editor.panel_id}")
            ref.delete()
            
            self.editor.panel_id = None
            self.editor.message_id = None
            self.remove_item(button)
            
            await interaction.response.send_message(
                f"<:yes:1036811164891480194> Panel deleted! {'Posted message is also removed.' if self.editor.message_id else ''}",
                ephemeral=True
            )
            await self.update_message()
        except Exception as e:
            await interaction.response.send_message(
                f"<:no:1036810470860013639> Failed to delete panel: {str(e)}",
                ephemeral=True
            )
    
    async def create_panel_view(self):
        if self.editor.panel_type == "dropdown":
            return await self.create_dropdown_view()
        else:
            return await self.create_button_view()
    
    async def create_dropdown_view(self):
        options = []
        for option in self.editor.options:
            options.append(discord.SelectOption(
                label=option["label"][:100],
                value=option["label"],
                description=option["description"][:100] if option["description"] else None,
                emoji=option["emoji"] or None
            ))
        
        if not options:
            return None
            
        class PanelSelect(discord.ui.Select):
            def __init__(self, options, editor):
                super().__init__(
                    placeholder="Select a ticket category...",
                    options=options,
                    custom_id="ticketcreation",
                )
                self.editor = editor
            
            async def callback(self, interaction: discord.Interaction):
                selected_value = self.values[0]
                selected_option = None
                for option in self.editor.options:
                    if option["label"] == selected_value:
                        selected_option = option
                        break
                
                embed = discord.Embed(
                    title="Confirm Ticket",
                    description=f"Are you sure you want to make a ticket about **{selected_value}**?",
                    colour=0x4F545B,
                )
                try:
                    embed.set_author(
                        name=interaction.user.name, icon_url=interaction.user.avatar.url
                    )
                except Exception:
                    embed.set_author(name=interaction.user.name)
                embed.set_footer(
                    icon_url=interaction.guild.icon.url,
                    text=f"{interaction.guild.name} • #{interaction.channel.name}",
                )
                
                view = CreateTicketButtonView()
                view.selected_option = selected_option
                view.editor = self.editor
                
                await interaction.response.send_message(
                    embed=embed, view=view, ephemeral=True
                )
        
        view = discord.ui.View()
        view.add_item(PanelSelect(options, self.editor))
        return view
    
    async def create_button_view(self):
        view = discord.ui.View()
        
        for button_data in self.editor.buttons:
            style_map = {
                "green": discord.ButtonStyle.green,
                "blue": discord.ButtonStyle.blurple, 
                "red": discord.ButtonStyle.red,
                "grey": discord.ButtonStyle.gray
            }
            style = style_map.get(button_data["color"], discord.ButtonStyle.grey)
            
            class PanelButton(discord.ui.Button):
                def __init__(self, button_data, editor):
                    super().__init__(
                        label=button_data["label"],
                        emoji=button_data["emoji"] or None,
                        style=style,
                        custom_id="create",
                    )
                    self.button_data = button_data
                    self.editor = editor
                
                async def callback(self, interaction: discord.Interaction):
                    await create_ticket(interaction, topic=self.button_data["label"], custom_opening_message=self.button_data.get('opening_message'), closing_message=self.button_data.get('closing_message'))
                    
            view.add_item(PanelButton(button_data, self.editor))
        
        return view

class DropdownOptionsView(discord.ui.View):
    def __init__(self, cog, editor: TicketPanelEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_index = 0 if editor.options else None
        self.update_select()
    
    def update_select(self):
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id == "options_select":
                self.remove_item(item)
                break
        
        if self.editor.options:
            options = []
            for i, option in enumerate(self.editor.options):
                options.append(discord.SelectOption(
                    label=option["label"][:100],
                    value=str(i),
                    description=option["description"][:100] if option["description"] else "No description",
                    default=i == self.selected_index
                ))
            
            select = discord.ui.Select(
                placeholder="Select an option to edit...",
                options=options,
                custom_id="options_select",
                row=0
            )
            select.callback = self.select_option
            self.add_item(select)
            self.children.insert(0, self.children.pop())
    
    async def update_message(self, interaction: discord.Interaction = None):
        self.update_select()
        embed = discord.Embed(
            title="Dropdown Options Manager",
            description="Manage the options for your dropdown ticket panel.",
            color=discord.Color.blue()
        )
        
        if self.editor.options:
            options_list = "\n".join([
                f"**{i+1}. {opt['label']}**\n- Value: `{opt['value']}`" +
                (f"\n- Description: {opt['description']}" if opt['description'] else "") +
                (f"\n- Emoji: {opt['emoji']}" if opt['emoji'] else "") +
                f"\n- Opening: {opt['opening_message']}"
                for i, opt in enumerate(self.editor.options)
            ])
            embed.add_field(name="Current Options", value=options_list, inline=False)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
    
    async def select_option(self, interaction: discord.Interaction):
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)
    
    @discord.ui.button(label="Add Option", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_option(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DropdownOptionModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.selected_index = len(self.editor.options) - 1
        await self.update_message()
    
    @discord.ui.button(label="Edit Option", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_option(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No option selected!", ephemeral=True)
            return
        modal = DropdownOptionModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Remove Option", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_option(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No option selected!", ephemeral=True)
            return
        
        self.editor.options.pop(self.selected_index)
        if self.editor.options:
            self.selected_index = min(self.selected_index, len(self.editor.options) - 1)
        else:
            self.selected_index = None
        
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class ButtonOptionsView(discord.ui.View):
    def __init__(self, cog, editor: TicketPanelEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_index = 0 if editor.buttons else None
        self.update_select()
    
    def update_select(self):
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id == "buttons_select":
                self.remove_item(item)
                break
        
        if self.editor.buttons:
            options = []
            for i, button in enumerate(self.editor.buttons):
                options.append(discord.SelectOption(
                    label=button["label"][:100],
                    value=str(i),
                    description=f"Color: {button['color']}",
                    default=i == self.selected_index
                ))
            
            select = discord.ui.Select(
                placeholder="Select a button to edit...",
                options=options,
                custom_id="buttons_select",
                row=0
            )
            select.callback = self.select_button
            self.add_item(select)
            self.children.insert(0, self.children.pop())
    
    async def update_message(self, interaction: discord.Interaction = None):
        self.update_select()
        embed = discord.Embed(
            title="Button Options Manager",
            description="Manage the buttons for your ticket panel.",
            color=discord.Color.blue()
        )
        
        if self.editor.buttons:
            buttons_list = "\n".join([
                f"**{i+1}. {btn['label']}** ({btn['color']})" +
                (f" {btn['emoji']}" if btn['emoji'] else "") +
                f"\n- Opening: {btn['opening_message']}"
                for i, btn in enumerate(self.editor.buttons)
            ])
            embed.add_field(name="Current Buttons", value=buttons_list, inline=False)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
    
    async def select_button(self, interaction: discord.Interaction):
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)
    
    @discord.ui.button(label="Add Button", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ButtonOptionModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.selected_index = len(self.editor.buttons) - 1
        await self.update_message()
    
    @discord.ui.button(label="Edit Button", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No button selected!", ephemeral=True)
            return
        modal = ButtonOptionModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Remove Button", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No button selected!", ephemeral=True)
            return
        
        self.editor.buttons.pop(self.selected_index)
        if self.editor.buttons:
            self.selected_index = min(self.selected_index, len(self.editor.buttons) - 1)
        else:
            self.selected_index = None
        
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class PostPanelView(discord.ui.View):
    def __init__(self, cog, editor: TicketPanelEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=1800)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_channel = None
        self.channel_select = discord.ui.ChannelSelect(placeholder="Select channel to post...")
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)
    
    async def update_message(self, interaction: discord.Interaction = None):
        content = "### 📤 Choose where to post your ticket panel.\n<:reply:1036792837821435976> If you want to save the panel as a template, you can go back and do so! Posting a panel does not automatically save it as a template."
        embed = self.editor.to_embed()
        
        if interaction:
            await interaction.response.edit_message(content=content, embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    async def select_channel(self, interaction: discord.Interaction):
        selected_channel = self.channel_select.values[0]
        self.selected_channel = interaction.guild.get_channel(selected_channel.id)
        await interaction.response.defer()
    
    @discord.ui.button(label="Post Panel", style=discord.ButtonStyle.green, emoji="📤", row=1)
    async def post_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_channel:
            await interaction.response.send_message("Please select a channel first!", ephemeral=True)
            return
        
        main_view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        panel_view = await main_view.create_panel_view()
        
        if not panel_view:
            await interaction.response.send_message(
                "<:no:1036810470860013639> Cannot post panel: no options/buttons configured!",
                ephemeral=True
            )
            return
        
        message = await self.selected_channel.send(embed=self.editor.to_embed(), view=panel_view)
        self.editor.message_id = message.id
        if self.editor.panel_id:
            ref = db.reference(f"Ticket Panels/{interaction.guild_id}/{self.editor.panel_type}/{self.editor.panel_id}")
            current_data = ref.get() or {}
            current_data["message_id"] = message.id
            ref.set(current_data)
        
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> Panel posted! [View Message]({message.jump_url})",
            ephemeral=True
        )
        
        view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=1)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketPanelMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class CreateNewButton(discord.ui.Button):
    def __init__(self, cog, panel_type):
        super().__init__(label="Create New Panel", style=discord.ButtonStyle.primary, emoji="➕")
        self.cog = cog
        self.panel_type = panel_type
    
    async def callback(self, interaction: discord.Interaction):
        editor = TicketPanelEditor(interaction.user.id, interaction.guild_id, self.panel_type)
        view = TicketPanelMainView(self.cog, editor, interaction)
        await view.update_message(interaction)

class PanelSelectView(discord.ui.View):
    def __init__(self, cog, panel_type):
        super().__init__(timeout=60)
        self.cog = cog
        self.panel_type = panel_type
        self.panel_data = {}
    
    async def load_panels(self, guild_id):
        try:
            ref = db.reference(f"Ticket Panels/{guild_id}/{self.panel_type}")
            panels = ref.get() or {}
            
            options = []
            for panel_id, data in panels.items():
                name = data.get("name", f"Panel {panel_id}")
                
                options.append(discord.SelectOption(
                    label=name[:100],
                    value=panel_id,
                    description=f"ID: {panel_id}"
                ))
                self.panel_data[panel_id] = data
            
            if options:
                select = discord.ui.Select(placeholder="Choose a panel...", options=options)
                select.callback = self.select_panel
                self.add_item(select)
                self.add_item(CreateNewButton(self.cog, self.panel_type))
            else:
                select = discord.ui.Select(
                    placeholder="No panels available",
                    options=[discord.SelectOption(label="No panels", value="none")],
                    disabled=True
                )
                self.add_item(select)
                self.add_item(CreateNewButton(self.cog, self.panel_type))
                
        except Exception as e:
            print(f"Error loading panels: {e}")
    
    async def select_panel(self, interaction: discord.Interaction):
        panel_id = interaction.data["values"][0]
        panel_data = self.panel_data[panel_id]
        
        editor = TicketPanelEditor(
            interaction.user.id,
            interaction.guild_id,
            self.panel_type,
            panel_id,
            panel_data
        )
        
        view = TicketPanelMainView(self.cog, editor, interaction)
        await view.update_message(interaction)

class CreateTicketButtonView(discord.ui.View):
    def __init__(self, title="Create Ticket", emoji="🎫", color=discord.ButtonStyle.grey, *, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(CreateTicketButton(title, emoji, color))
        self.selected_option = None
        self.editor = None

class CreateTicketButton(discord.ui.Button):
    def __init__(self, title, emoji, color):
        super().__init__(label=title, emoji=emoji, style=color, custom_id="create")
        self.custom_opening_message = None

    async def callback(self, interaction: discord.Interaction):
        opening_message = None
        closing_message = None
        topic = None
        if hasattr(self.view, 'selected_option') and self.view.selected_option:
            opening_message = self.view.selected_option.get('opening_message')
            closing_message = self.view.selected_option.get('closing_message')
        elif hasattr(self.view, 'button_data') and self.view.button_data:
            opening_message = self.view.button_data.get('opening_message')
            closing_message = self.view.button_data.get('closing_message')
            topic = self.view.button_data.get('label')
        
        await create_ticket(interaction, topic=topic, custom_opening_message=opening_message, closing_message=closing_message)

class Select(discord.ui.Select):
    def __init__(self, placeholder, options):
        super().__init__(
            placeholder=placeholder,
            max_values=1,
            min_values=1,
            options=options,
            custom_id="ticketcreation",
        )

    async def callback(self, interaction: discord.Interaction):

        selectedValue = self.values[0]
        embed = discord.Embed(
            title="Confirm Ticket",
            description=f"Are you sure you want to make a ticket about **{selectedValue}**?",
            colour=0x4F545B,
        )
        try:
            embed.set_author(
                name=interaction.user.name, icon_url=interaction.user.avatar.url
            )
        except Exception:
            embed.set_author(name=interaction.user.name)
        embed.set_footer(
            icon_url=interaction.guild.icon.url,
            text=f"{interaction.guild.name} • #{interaction.channel.name}",
        )
        await interaction.response.send_message(
            embed=embed, view=CreateTicketButtonView(), ephemeral=True
        )


class SelectView(discord.ui.View):
    def __init__(self, placeholder=None, options=None, *, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(Select(placeholder, options))


class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close",
        emoji="🔒",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ":no_entry_sign:" in interaction.channel.topic:
            embed = discord.Embed(
                title="Ticket already closed :no_entry_sign:",
                description="This ticket is already closed.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            title="Are you sure about that?",
            description="Only moderators and administrators can reopen the ticket.",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        ticket_owner_id = int(interaction.channel.topic)
        view = ConfirmCloseTicketButtons(ticket_owner_id=ticket_owner_id, interaction_user_id=interaction.user.id)
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )
        view.message = await interaction.original_response()


class TicketAdminButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Reopen Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="reopen",
        emoji="🔓",
    )
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user = await interaction.client.fetch_user(
                int(interaction.channel.topic.split(":")[2].strip())
            )
        except Exception:
            await interaction.response.send_message("Unable to fetch the user. They probably left the server.", ephemeral=True)
            return
        await interaction.channel.edit(topic=user.id)
        await interaction.channel.set_permissions(
            user, send_messages=True, read_messages=True, attach_files=True
        )

        ref = db.reference("/Tickets")
        tickets = ref.get()
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                LOGCHANNEL_ID = value["Log Channel ID"]
                break
        log = interaction.guild.get_channel(LOGCHANNEL_ID)

        embed = discord.Embed(
            title="Ticket Reopened",
            color=0xFFFF00,
        )
        embed.add_field(name="Ticket Owner", value=f"{user.mention}", inline=True)
        embed.add_field(name="Reopened By", value=f"{interaction.user.mention}", inline=True)
        try:
            embed.set_author(name=f"{user.name}", icon_url=user.avatar.url)
        except Exception:
            embed.set_author(name=f"{user.name}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
        )
        view = View()
        view.add_item(button)
        await log.send(embed=embed, view=view)
        embed = discord.Embed(
            title="Ticket Reopened",
            description=f"Your ticket is reopened by {interaction.user.mention}.",
            color=0xE44D41,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        button = Button(
            style=discord.ButtonStyle.link,
            label="Head over to your ticket",
            emoji="🎫",
            url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
        )
        view = View()
        view.add_item(button)
        try:
            await user.send(embed=embed, view=view)
        except Exception:
            pass
        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"Ticket reopened by {interaction.user.mention} and is visible to {user.mention} again.",
            color=0xFFFF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.message.delete()
        await interaction.channel.send(embed=embed, view=CloseTicketButton())
        await interaction.response.send_message("Ticket is reopened.", ephemeral=True)

    @discord.ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="delete",
        emoji="✉️",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Deleting Ticket...",
            description="Ticket will be deleted in 5 seconds",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.message.delete()
        await interaction.channel.send(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def parse_mentions(interaction, text):
    member_cache = {}

    async def replace_users_async(text):
        result = ""
        last_end = 0

        for match in re.finditer(r"<@!?([0-9]+)>", text):
            uid = int(match.group(1))
            try:
                member = await interaction.client.fetch_user(uid)
                if not member:
                    if uid in member_cache:
                        member = member_cache[uid]
                    else:
                        member = await interaction.client.fetch_user(uid)
                        member_cache[uid] = member
            except Exception:
                try:
                    member = await interaction.client.fetch_user(uid)
                    member_cache[uid] = member
                except Exception:
                    member = None
            name = member.name if member else f"user:{uid}"
            result += text[last_end:match.start()] + f"<span class='mention'>@{name}</span>"
            last_end = match.end()

        return result + text[last_end:]

    text = await replace_users_async(text)

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

    def replace_command(match):
        command_name = match.group(1)
        return f"<span class='mention'>/{command_name}</span>"

    text = re.sub(r"<@&([0-9]+)>", replace_role, text)
    text = re.sub(r"<#([0-9]+)>", replace_channel, text)
    text = re.sub(r"</([A-Za-z\- ]+):[0-9]+>", replace_command, text)

    return text

def parse_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
    text = re.sub(r'[\*_](.*?)[\*_]', r'<em>\1</em>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    text = re.sub(r'^#\s+(.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'-#\s+(.*?)$', r'<small>\1</small>', text, flags=re.MULTILINE)
    text = re.sub(r'\|\|(.*?)\|\|', r'<span class="spoiler">\1</span>', text, flags=re.DOTALL)
    
    def replace_timestamp(match):
        timestamp = int(match.group(1))
        style = match.group(2) if match.group(2) else None
        return f"<span class='discord-timestamp' data-timestamp='{timestamp}' data-style='{style}'></span>"
    text = re.sub(r'<t:(\d+)(?::([a-zA-Z]))?>', replace_timestamp, text)
    
    lines = text.split('\n')
    in_blockquote = False
    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('>'):
            content = re.sub(r'^>\s*', '', stripped)
            if not in_blockquote:
                new_lines.append('<blockquote>')
                in_blockquote = True
            new_lines.append(content)
        else:
            if in_blockquote:
                new_lines.append('</blockquote>')
                in_blockquote = False
            new_lines.append(line)
    if in_blockquote:
        new_lines.append('</blockquote>')
    text = '\n'.join(new_lines)
    
    return text

async def get_transcript(interaction, user):
    messages = [
        message async for message in interaction.channel.history(limit=None)
    ]
    f = open(f"../Fischl/shared/Tickets/{interaction.channel.id}.html", "w", encoding="utf-8")

    iconURL = interaction.guild.icon.url if interaction.guild.icon else "https://discord.com/assets/5d6a5e9d7d77ac29116e.png"
    f.write(f"""<Server-Info>
    Server: {interaction.guild.name} ({interaction.guild.id})
    Channel: #{interaction.channel.name} ({interaction.channel.id})
    Ticket Owner: {user} ({user.id if user else 'Unknown'})
    Messages: {len(messages)}
    Attachments: {sum(1 for message in messages if message.attachments)}
    
    """)
    f.write(f"</Server-Info><!DOCTYPE html> <html> <head> <meta name='viewport' content='width=device-width, initial-scale=1.0'> <title>{user}</title> <script data-cfasync='false'> function formatDiscordTimestamps() {{ document.querySelectorAll('.discord-timestamp').forEach(element => {{ const timestamp = parseInt(element.dataset.timestamp); const style = element.dataset.style; const date = new Date(timestamp * 1000); let formatted; switch (style) {{ case 't': formatted = date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'T': formatted = date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true }}); break; case 'd': formatted = date.toLocaleDateString('en-US', {{ month: 'numeric', day: 'numeric', year: 'numeric' }}); break; case 'D': formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}); break; case 'f': formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'F': formatted = date.toLocaleDateString('en-US', {{ weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'R': const now = new Date(); const diff = now - date; const seconds = Math.floor(diff / 1000); const intervals = {{ year: 31536000, month: 2592000, week: 604800, day: 86400, hour: 3600, minute: 60, second: 1 }}; for (const [unit, secondsInUnit] of Object.entries(intervals)) {{ const count = Math.floor(seconds / secondsInUnit); if (count >= 1) {{ formatted = `${{count}} ${{unit}}${{count !== 1 ? 's' : ''}} ago`; break; }} }} break; default: formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); }} element.textContent = formatted; }}); }} function initializeSpoilers() {{ document.querySelectorAll('.spoiler').forEach(spoiler => {{ spoiler.addEventListener('click', () => {{ spoiler.classList.toggle('revealed'); }}); }}); }} window.addEventListener('DOMContentLoaded', () => {{ formatDiscordTimestamps(); initializeSpoilers(); }}); </script> <style> Server-Info {{visibility: hidden}} body {{ background-color: #2c2f33; color: white; font-family: 'Segoe UI', sans-serif; padding: 20px; }} .chat-container {{ max-width: 800px; margin: auto; }} .message {{ display: flex; gap: 12px; }} .message.grouped {{ margin-bottom: 6px; }} .message.not-grouped {{ margin: 20px 0 6px 0; }} .avatar {{ border-radius: 50%; width: 40px; height: 40px; }} .content {{ flex: 1; }} .username {{ font-weight: 600; }} .userid {{ font-size: 0.8em; color: #999; margin-left: 5px; }} .text {{ padding: 2px 0px; white-space: pre-wrap; margin-top: 2px; }} .attachment-img {{ max-width: 300px; border-radius: 6px; margin-top: 6px; }} .media-file {{ background-color: #4f545c; padding: 10px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; color: white; margin-top: 6px; text-decoration: none; }} .embed {{ background-color: #2f3136; padding: 10px 15px; border-left: 6px solid #7289da; border-radius: 8px; margin-top: 6px; }} .embed-title {{ font-weight: bold; color: white; }} .embed-description {{ color: #ccc; font-size: 0.95em; }} .header-container {{ display: flex; gap: 20px; margin-bottom: 30px; align-items: center; }} .header-container img {{ width: 80px; border-radius: 20px; }} .header-info div {{ margin-bottom: 5px; }} .app-badge {{ display: inline-flex; align-items: center; background-color: #5a5df0; color: white; font-weight: 600; font-family: sans-serif; border-radius: 5px; padding: 2px 8px; font-size: 12px; margin-left: 4px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }} .mention {{ background-color: rgb(65,68,112); color: rgb(183,195,234); padding: 2px 4px; border-radius: 3px; font-weight: 500; }} .embed-fields {{ margin-top: 10px; display: flex; flex-direction: column; gap: 10px;}} .embed-field {{ background-color: rgba(255, 255, 255, 0.05); padding: 8px 12px; border-radius: 6px; }} .embed-field-name {{ font-weight: bold; color: #fff; margin-bottom: 4px; font-size: 0.95em; }} .embed-field-value {{ color: #ccc; font-size: 0.95em; white-space: pre-wrap; }} blockquote {{ border-left: 3px solid rgb(101, 101, 108); padding-left: 10px; margin-left: 5px; color: #dcddde; }} .spoiler {{ position: relative; cursor: pointer; display: inline-block; }} .spoiler::after {{ content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(101, 101, 108); border-radius: 3px; transition: opacity 0.2s; }} .spoiler.revealed::after {{ opacity: 0; }} </style> </head> <body> <div class='chat-container'> <div class='header-container'> <img src='{iconURL}' /> <div class='header-info'> <div><strong>Server:</strong> {interaction.guild.name} ({interaction.guild.id})</div> <div><strong>Channel:</strong> #{interaction.channel.name} ({interaction.channel.id})</div> <div><strong>Ticket Owner:</strong> {user} ({user.id if user else 'Unknown'})</div> </div> </div>")

    user_message_counts = defaultdict(int)
    usersInvolved = []
    lastUser = None

    async with aiohttp.ClientSession() as session:
        for msg in reversed(messages):
            if msg.author != interaction.client.user:
                user_message_counts[msg.author] += 1
                if msg.author not in usersInvolved:
                    usersInvolved.append(msg.author)

            avatarURL = msg.author.avatar.url if hasattr(msg.author, 'avatar') and msg.author.avatar else "https://discord.com/assets/5d6a5e9d7d77ac29116e.png"
            userColor = msg.author.color if hasattr(msg.author, 'color') and msg.author.color != '#000000' else '#dfe0e2'
            username = msg.author.name
            userId = msg.author.id
            isBot = msg.author.bot if hasattr(msg.author, 'bot') else False

            show_user_info = lastUser != msg.author.id
            message_class = "message not-grouped" if show_user_info else "message grouped"

            f.write(f"<div class='{message_class}'>")
            f.write(f"<img class='avatar' src='{avatarURL}' />" if show_user_info else "<div style='width: 40px;'></div>")
            f.write("<div class='content'>")

            if show_user_info:
                f.write(f"<div><span class='username' style='color: {userColor};'>{username}</span>")
                if isBot:
                    f.write("<div class='app-badge' data-toggle='tooltip' title='Verified Bot'>BOT</div>")
                f.write(f"<code class='userid'>({userId})</code></div>")

            if msg.content:
                content = await parse_mentions(interaction, parse_markdown(msg.content))
                f.write(f"<div class='text'>{content}</div>")

            for attachment in msg.attachments:
                if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    f.write(f'<img class="attachment-img" src="{attachment.url}" />')
                elif attachment.filename.lower().endswith(('.mp4', '.mov', '.webm', '.mkv')):
                    f.write(f'<video class="attachment-media" controls> <source src="{attachment.url}" type="video/mp4"> Your browser doesn\'t support embedded videos. </video>')
                elif attachment.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                    f.write(f'<audio class="attachment-media" controls> <source src="{attachment.url}" type="audio/mpeg"> Your browser doesn\'t support embedded audio. </audio>')
                else:
                    f.write(f"<a href='{attachment.url}' download class='media-file'> <img src='https://cdn.discordapp.com/attachments/1026904121237831700/1129787805381423265/file.png' height='20'> <span>{attachment.filename}</span> </a>")

            for embed in msg.embeds:
                if embed.title or embed.description or embed.fields:
                    embedColor = embed.color if embed.color else '#7289da'
                    f.write(f"<div class='embed' style='border-left-color: {embedColor};'>")
                    if embed.title:
                        f.write(f"<div class='embed-title'>{embed.title}</div>")
                    if embed.description:
                        description = await parse_mentions(interaction, parse_markdown(embed.description))
                        f.write(f"<div class='embed-description'>{description}</div>")
                    if embed.fields:
                        f.write("<div class='embed-fields'>")
                        for field in embed.fields:
                            f.write("<div class='embed-field'>")
                            f.write(f"<div class='embed-field-name'>{parse_markdown(field.name)}</div>")
                            f.write(f"<div class='embed-field-value'>{await parse_mentions(interaction, parse_markdown(field.value))}</div>")
                            f.write("</div>")
                        f.write("</div>")
                    f.write("</div>")

            f.write("</div></div>")
            lastUser = msg.author.id

        f.write("</div></body></html>")
        f.close()

        return (f, usersInvolved, user_message_counts)

async def snippet_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    snippets = db.reference(f"/Ticket Snippets/{interaction.guild.id}").get() or {}
    choices = []
    for alias in snippets.keys():
        if current.lower() in alias.lower():
            choices.append(app_commands.Choice(name=alias, value=alias))
    return choices[:25]

async def perform_ticket_close(interaction: discord.Interaction, closing_message=None):
    embed = discord.Embed(
        title="Closing Ticket...",
        description="Ticket will be closed in 3 seconds",
        color=0xFF0000,
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    msg = await interaction.channel.send(embed=embed)
    left = False
    user = None
    try:
        user = await interaction.client.fetch_user(int(interaction.channel.topic))
    except Exception:
        left = True

    ref = db.reference("/Tickets")
    tickets = ref.get()
    for key, value in tickets.items():
        if value["Server ID"] == interaction.guild.id:
            LOGCHANNEL_ID = value["Log Channel ID"]
            break
    log = interaction.guild.get_channel(LOGCHANNEL_ID)

    if not user:
        left = True

    f, usersInvolved, user_message_counts = await get_transcript(interaction, user)

    if left == False and user != None:
        embed = discord.Embed(
            title="Ticket closed",
            description=f"Ticket created by {user.mention} is closed by {interaction.user.mention}",
            color=0xE44D41,
        )
        try:
            embed.set_author(
                name=f"{user.name}", icon_url=user.avatar.url
            )
        except Exception:
            embed.set_author(name=f"{user.name}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
    else:
        embed = discord.Embed(
            title="Ticket closed",
            description=f"Ticket created by a member who has left the server is closed by {interaction.user.mention}",
            color=0xE44D41,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

    user_list = "\n".join(f"- {user.mention} `({user_message_counts[user]})`" for user in usersInvolved) if usersInvolved else "`None`"
    embed.add_field(name="Users Involved", value=user_list, inline=True)

    with open(f"../Fischl/shared/Tickets/{interaction.channel.id}.html", "r", encoding="utf-8") as f:
        try:
            summary = await generate(
                f"The following is the entire history of the ticket in a Discord server for a user. "
                "Please summarise the entire interaction into 1 or 2 sentences. "
                "Only give 1 response option. Do not output additional text such as 'Here is the summary:'. "
                f"Exclude the channel names, user IDs, server names, Fischl (bot name), or the fact that a ticket is created or closed in your response.\n\n"
                "Full transcript:\n"
                f"{f.read().split('<!DOCTYPE html>')[1]}")
        except Exception as e:
            print(e)
            summary = "`AI Summary Temporarily Unavailable`"

    first_message = [msg async for msg in interaction.channel.history(oldest_first=True)][0]
    embed.add_field(name="Ticket Topic", value=first_message.embeds[0].title)

    log_message = await log.send(
        embed=embed,
        file=discord.File(f"../Fischl/shared/Tickets/{interaction.channel.id}.html")
    )

    with open(f"../Fischl/shared/Tickets/{interaction.channel.id}.html", "rb") as f:
        file_content = f.read()

    checksum = hashlib.sha256(file_content + str(log.id).encode()).hexdigest()[:20]
    token = f"{log.id}-{log_message.id}-{checksum}"
    url = f"https://fischl.app/logs/{token}"

    embed.add_field(name="Transcript Link", value=url, inline=False)
    embed.add_field(name="Ticket Summary", value=summary)
    await log_message.edit(embed=embed)
    embed.title = f"Ticket closed in {interaction.guild.name}"
    await interaction.client.get_channel(1417408712980697099).send(
        embed=embed,
        file=discord.File(f"../Fischl/shared/Tickets/{interaction.channel.id}.html")
    )

    try:
        os.remove(f"../Fischl/shared/Tickets/{interaction.channel.id}.html")
    except Exception:
        pass

    transcript_button = Button(
        style=discord.ButtonStyle.link,
        label="Transcript Link",
        emoji="📜",
        url=url
    )
    user_view = View()
    user_view.add_item(transcript_button)

    embed = discord.Embed(
        title="Ticket Closed",
        description=f"Your ticket in **{interaction.guild.name}** is now closed.",
        color=0xE44D41,
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(
        text=f"You can always create a new ticket for additional assistance!"
    )
    
    if closing_message is None:
        closing_message = db.reference(f"/Ticket Closing Messages/{interaction.channel.id}").get()
    if closing_message:
        embed.description += f"\n\n> {closing_message}"
    
    try:
        await user.send(embed=embed, view=user_view)
        await interaction.channel.set_permissions(
            user, send_messages=False, read_messages=False, attach_files=False
        )
    except Exception:
        pass

    await msg.delete()
    if left == False:
        embed = discord.Embed(
            description=f"Ticket is closed by {interaction.user.mention} and no longer visible to {user.mention}.",
            color=0xE44D41,
        )
        if closing_message:
            embed.add_field(name="Closing Message", value=closing_message, inline=False)
            embed.title = "Ticket Closed"
    else:
        embed = discord.Embed(
            description=f"Member left the server. Ticket is still closed.",
            color=0xE44D41,
        )
    await interaction.channel.send(embed=embed)
    embed = discord.Embed(
        title="", description="""```STAFF CONTROLS PANEL```""", color=0xE44D41
    )
    view = TicketAdminButtons()
    view.add_item(transcript_button)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.channel.edit(
        topic=f":no_entry_sign: {interaction.channel.topic}"
    )

class SetClosingMessageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Set Closing Message", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        modal = ClosingMessageModal(original_message=self.view.message)
        await interaction.response.send_modal(modal)

class ClosingMessageModal(discord.ui.Modal):
    def __init__(self, original_message):
        super().__init__(title="Set Closing Message")
        self.original_message = original_message
        self.add_item(discord.ui.TextInput(
            label="Closing Message",
            placeholder="Enter a message to send when closing the ticket",
            style=discord.TextStyle.paragraph,
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        closing_message = self.children[0].value
        await self.original_message.edit(
            embed=discord.Embed(description="<:yes:1036811164891480194> **Ticket Closure Confirmed**", color=discord.Color.green()), 
            view=None
        )
        await interaction.response.defer()
        await perform_ticket_close(interaction, closing_message)

class ConfirmCloseTicketButtons(discord.ui.View):
    def __init__(self, override_closing_message=None, ticket_owner_id=None, interaction_user_id=None):
        super().__init__(timeout=None)
        self.override_closing_message = override_closing_message
        self.ticket_owner_id = ticket_owner_id
        self.interaction_user_id = interaction_user_id
        if self.ticket_owner_id is not None and self.interaction_user_id is not None and self.interaction_user_id != self.ticket_owner_id:
            self.add_item(SetClosingMessageButton())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="yes")
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(description="<:yes:1036811164891480194> **Ticket Closure Confirmed**", color=discord.Color.green()), 
            view=None
        )
        await perform_ticket_close(interaction, self.override_closing_message)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, custom_id="no")
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Action Cancelled",
            description=f"Alright {interaction.user.mention}! I will not close the ticket!",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.edit_message(embed=embed, view=None)


@app_commands.guild_only()
class Ticket(commands.GroupCog, name="ticket"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="notify",
        description="Send a DM to ticket author requiring their attention",
    )
    @app_commands.describe(message="Optional message to be included in the DMs")
    async def ticket_notify(
        self, interaction: discord.Interaction, message: str = None
    ) -> None:
        if message is None:
            message = " "
        else:
            message = f"\n\n> {message}"
        try:
            user = await interaction.client.fetch_user(int(interaction.channel.topic))
        except Exception:
            return
        if interaction.user.id == user.id:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You cannot notify yourself!", ephemeral=True
            )
            return
        embed = discord.Embed(
            title="⚠️ Notification ⚠️",
            description=f"The ticket you created in **{interaction.guild.name}** needs your attention! Please kindly respond.{message}\n\nIf you no longer need assistance or your issue has been resolved, **please still let us know in the ticket** so we can help close the ticket.",
            color=0xE44D41,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        try:
            button = Button(
                style=discord.ButtonStyle.link,
                label="Head over to your ticket",
                emoji="🎫",
                url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
            )
            view = View()
            view.add_item(button)
            await user.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"{user.mention} received a DM notification."
            )
        except Exception:
            await interaction.response.send_message(
                "<:no:1036810470860013639> Unable to DM user!", ephemeral=True
            )

    @app_commands.command(
        name="delete", description="Deletes an existing ticket channel"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_delete(self, interaction: discord.Interaction) -> None:
        try:
            user = await interaction.client.fetch_user(
                int(interaction.channel.topic.split(":")[2])
            )
            embed = discord.Embed(
                title="Deleting Ticket...",
                description="Ticket will be deleted in 5 seconds",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
            await asyncio.sleep(5)
            await interaction.channel.delete()
        except Exception:
            embed = discord.Embed(
                title="Invalid Action",
                description="This command can only be used in ticket channels, or this ticket has not been closed.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_delete.error
    async def ticket_delete_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="close",
        description="Closes the current ticket and prevents ticket author from viewing the ticket",
    )
    @app_commands.describe(closing_message="Optional custom closing message (staff only)")
    async def ticket_close(self, interaction: discord.Interaction, closing_message: str = None) -> None:
        if ":no_entry_sign:" in interaction.channel.topic:
            embed = discord.Embed(
                title="Ticket already closed :no_entry_sign:",
                description="This ticket is already closed.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        ticket_creator_id = int(interaction.channel.topic)
        if closing_message and interaction.user.id == ticket_creator_id:
            await interaction.response.send_message("Only staff can override the closing message.", ephemeral=True)
            return
        
        try:
            embed = discord.Embed(
                title="Are you sure about that?",
                description="Only moderators and administrators can reopen the ticket.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(
                embed=embed, view=ConfirmCloseTicketButtons(override_closing_message=closing_message), ephemeral=True
            )
        except Exception:
            embed = discord.Embed(
                title="Invalid Action",
                description="This command can only be used in ticket channels.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="dropdown", 
        description="Create or edit dropdown ticket panels with advanced customization"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_dropdown(self, interaction: discord.Interaction) -> None:
        view = PanelSelectView(self, "dropdown")
        await view.load_panels(interaction.guild_id)
        
        embed = discord.Embed(
            title="Dropdown Ticket Panels",
            description="Choose an existing panel to edit or create a new one.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="button", 
        description="Create or edit button ticket panels with advanced customization"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_button(self, interaction: discord.Interaction) -> None:
        view = PanelSelectView(self, "button")
        await view.load_panels(interaction.guild_id)
        
        embed = discord.Embed(
            title="Button Ticket Panels",
            description="Choose an existing panel to edit or create a new one.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="add", description="Add a user to the current ticket (Mods only)")
    @app_commands.describe(user="User to add to channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if ":no_entry_sign:" in interaction.channel.topic or not interaction.channel.topic:
            await interaction.response.send_message("<:no:1036810470860013639> This is not a valid ticket channel.", ephemeral=True)
            return
        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        embed = discord.Embed(description=f"{user.mention} has been added to this ticket.", color=0x00FF00)
        await interaction.response.send_message(embed=embed)
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                LOGCHANNEL_ID = value["Log Channel ID"]
                break
        log_channel = interaction.guild.get_channel(LOGCHANNEL_ID)
        left = False
        try:
            user = await interaction.client.fetch_user(int(interaction.channel.topic))
        except Exception:
            left = True
        log_embed = discord.Embed(
            title="User Added",
            description=(
                f"{user.mention} was added by {interaction.user.mention} to "
                f"{user.mention}'s ticket." if not left else
                "a ticket created by someone who left the server."
            ),
            color=0x6b9f6b
        )
        log_embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
        )
        view = View()
        view.add_item(button)
        await log_channel.send(embed=log_embed, view=view)
    @ticket_add.error
    async def ticket_add_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="create", description="Create a ticket for a user (Mods only, bypasses cooldown & blacklist)")
    @app_commands.describe(user="Specify a user")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_create(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                CATEGORY_ID = value["Category ID"]
                LOGCHANNEL_ID = value["Log Channel ID"]
                found = True
                break

        if not found:
            embed = discord.Embed(
                title="Ticket not enabled!",
                description=f"This server doesn't have a ticket category or a log channel. Please use `/ticket setup` to setup tickets first!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        category = interaction.guild.get_channel(CATEGORY_ID)

        for channel in category.channels:
            if str(channel.topic) == str(user.id):
                await interaction.followup.send(
                    content=f"<:no:1036810470860013639> {user.mention} already has their ticket created at <#{channel.id}>.",
                    ephemeral=True,
                )
                return

        log = interaction.guild.get_channel(LOGCHANNEL_ID)
        embed = discord.Embed(title="Ticket created", description=f"Staff {interaction.user.mention} created a new ticket for {user.mention} <t:{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}:R>!", color=discord.Colour.green())
        embed.add_field(name="Ticket Topic", value="Created by server staff")

        try:
            chn = await interaction.guild.create_text_channel(
                f"{user.name}", category=category
            )

            await chn.edit(topic=user.id)
            await chn.set_permissions(
                user, send_messages=True, read_messages=True, attach_files=True
            )
        except Exception:
            await interaction.followup.send(
                content=f"<:no:1036810470860013639> **I'm missing permissions to create or edit text channels!** \nPlease make sure my role has `MANAGE_CHANNELS` permissions.", ephemeral=True
            )
            return

        try:
            embed.set_author(
                name=f"{user.name}", icon_url=interaction.user.avatar.url
            )
        except Exception:
            embed.set_author(name=f"{user.name}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"Ticket ID: {chn.id}")

        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{chn.id}",
        )
        view = View()
        view.add_item(button)
        await log.send(embed=embed, view=view)
        embed.title = f"Ticket created in {interaction.guild.name}"
        await interaction.client.get_channel(1417408712980697099).send(embed=embed)

        roles = user.roles
        roles.reverse()

        embed = discord.Embed(
            title=f"New Ticket",
            description=f"This ticket is created *by {interaction.user.mention}* for {user.mention}! \nYou can use </ticket close:1254927191129456641> or click the red button below to close this ticket.",
            color=discord.Colour.gold(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.add_field(
            name="User Mention", value=f"{user.mention}", inline=True
        )
        embed.add_field(name="User ID", value=f"{user.id}", inline=True)
        embed.add_field(name="Highest Role", value=f"{roles[0].mention}", inline=True)
        embed.add_field(
            name="Ticket Created",
            value=f"<t:{int(chn.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Server Joined",
            value=f"<t:{int(user.joined_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(user.created_at.timestamp())}:R>",
            inline=True,
        )
        await chn.send(
            f"**{user.mention}, welcome!** {'[ <@&1309928108312498227> ]' if interaction.guild.id == 1281655927791030293 else ''}",
            embed=embed,
            view=CloseTicketButton(),
        )
        
        try:
            await user.send(f":warning: A staff in **{interaction.guild.name}** has created a ticket for you and requires your attention.\n<:reply:1036792837821435976> <#{chn.id}>")
            dm = True
        except:
            dm = False
            pass
            
        message_status = "and the user is notified via DM" if dm else "but I'm unable to DM the user"
        content = f"<:yes:1036811164891480194> Ticket for {user.mention} created at <#{chn.id}> {message_status}"

        await interaction.followup.send(
            content=content, ephemeral=True
        )
    @ticket_create.error
    async def ticket_create_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
    
    @app_commands.command(
        name="snippet",
        description="Send a prewritten snippet response in the ticket"
    )
    @app_commands.describe(
        alias="The snippet alias to send",
        anonymous="Remove author from the embed (default: False)",
        ping="Ping the ticket creator (default: False)"
    )
    @app_commands.autocomplete(alias=snippet_autocomplete)
    async def ticket_snippet(
        self, interaction: discord.Interaction, 
        alias: str, 
        anonymous: bool = False, 
        ping: bool = False
    ) -> None:
        if interaction.channel.topic.startswith(":no_entry_sign:"):
            await interaction.response.send_message("This ticket is closed and cannot send snippets!", ephemeral=True)
            return
        
        if interaction.channel.topic.isdigit():
            if int(interaction.channel.topic) == interaction.user.id:
                await interaction.response.send_message("You cannot use this command in your own ticket!", ephemeral=True)
                return
        else:
            await interaction.response.send_message("This command can only be used in ticket channels!", ephemeral=True)
            return
        
        snippets = db.reference(f"/Ticket Snippets/{interaction.guild.id}").get() or {}
        response = snippets.get(alias)
        if not response:
            await interaction.response.send_message(f"Snippet '{alias}' not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            color=discord.Color.gold()
        )
        if not anonymous:
            embed.set_author(
                name=f"Sent by {interaction.user.name}", 
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
        
        content = ""
        if ping:
            ticket_creator_id = int(interaction.channel.topic)
            content = f"<@{ticket_creator_id}> "
        
        content += response
        
        await interaction.channel.send(content=content, embed=embed)
        await interaction.response.send_message(f"Snippet '{alias}' sent successfully!", ephemeral=True)
    @ticket_snippet.error
    async def ticket_snippet_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
    
    @app_commands.command(
        name="settings",
        description="Configure all ticket settings in one place"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_settings(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        
        ref = db.reference("/Tickets")
        tickets = ref.get()
        server_config = None
        
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                server_config = value
                server_config["key"] = key
                break
        
        view = TicketSettingsView(self.bot, interaction, server_config)
        await view.update_message()
    @ticket_settings.error
    async def ticket_settings_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

class TicketSettingsView(View):
    def __init__(self, bot, interaction: discord.Interaction, server_config=None):
        super().__init__(timeout=1800)
        self.bot = bot
        self.interaction = interaction
        self.server_config = server_config
        self.selected_category = None
        self.selected_log_channel = None
        self.selected_ping_role = None
        
        if server_config:
            self.selected_category = interaction.guild.get_channel(server_config.get("Category ID"))
            self.selected_log_channel = interaction.guild.get_channel(server_config.get("Log Channel ID"))
            self.selected_ping_role = interaction.guild.get_role(server_config.get("Ping Role ID"))
    
    async def update_message(self, interaction: discord.Interaction = None):
        embed = await self.create_settings_embed()
        self.clear_items()
        
        if not self.server_config:
            self.add_item(EnableSystemButton())
        else:
            category_select = ChannelSelect(
                placeholder="Select ticket category...",
                channel_types=[discord.ChannelType.category],
                custom_id="category_select"
            )
            if self.selected_category:
                category_select.default_values = [self.selected_category]
            category_select.callback = self.select_category
            self.add_item(category_select)
            
            log_select = ChannelSelect(
                placeholder="Select log channel...",
                channel_types=[discord.ChannelType.text],
                custom_id="log_select"
            )
            if self.selected_log_channel:
                log_select.default_values = [self.selected_log_channel]
            log_select.callback = self.select_log_channel
            self.add_item(log_select)
            
            role_select = RoleSelect(
                placeholder="Select ping role (optional)...",
                custom_id="role_select"
            )
            if self.selected_ping_role:
                role_select.default_values = [self.selected_ping_role]
            role_select.callback = self.select_ping_role
            self.add_item(role_select)
            
            self.add_item(CooldownButton())
            self.add_item(RoleAccessButton())
            self.add_item(BlacklistButton())
            self.add_item(SnippetsButton())
            self.add_item(DisableSystemButton())
        
        target = interaction or self.interaction
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await target.edit_original_response(embed=embed, view=self)
    
    async def create_settings_embed(self):
        embed = discord.Embed(
            title="🎫 Ticket System Settings",
            color=discord.Color.blue() if self.server_config else discord.Color.orange()
        )
        
        if not self.server_config:
            embed.description = (
                "The ticket system is currently **disabled**. "
                "Click the **Enable System** button below to get started! "
                "This will create the necessary category and log channel for tickets." 
                "You can always change the channels and settings later."
            )
            return embed
        
        category_name = self.selected_category.name if self.selected_category else "Not set"
        log_channel_name = self.selected_log_channel.mention if self.selected_log_channel else "Not set"
        ping_role_name = self.selected_ping_role.mention if self.selected_ping_role else "Not set"
        
        cooldown = self.server_config.get("Cooldown", 0)
        cooldown_str = self.format_cooldown(cooldown)
        
        dropdown_panels = db.reference(f"/Ticket Panels/{self.interaction.guild.id}/dropdown").get() or {}
        button_panels = db.reference(f"/Ticket Panels/{self.interaction.guild.id}/button").get() or {}
        blacklisted = db.reference(f"/Ticket Blacklist/{self.interaction.guild.id}").get() or {}
        access_roles = self.get_access_roles()
        
        embed.description = (
            "Configure all aspects of your ticket system below. "
            "Use the dropdown menus and buttons to modify settings.\n\n"
            "**Need help?** Join our [support server](https://discord.gg/BXkc8CC4uJ) for assistance!"
        )
        
        embed.add_field(
            name="📁 Current Configuration",
            value=(
                f"-# - **Category:** {category_name}\n"
                f"-# - **Log Channel:** {log_channel_name}\n"
                f"-# - **Ping Role:** {ping_role_name}\n"
                f"-# - **Cooldown:** {cooldown_str}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📊 System Stats",
            value=(
                f"-# - **Dropdown Panels:** `{len(dropdown_panels)}`\n"
                f"-# - **Button Panels:** `{len(button_panels)}`\n"
                f"-# - **Access Roles:** `{len(access_roles)}`\n"
                f"-# - **Blacklisted Users:** `{len(blacklisted)}`"
            ),
            inline=True
        )

        embed.add_field(
            name="🔧 Panel Commands",
            value=(
                "- </ticket dropdown:1254927191129456641> - Create or edit dropdown ticket panels\n"
                "- </ticket button:1254927191129456641> - Create or edit button ticket panels"
            ),
            inline=False
        )

        
        return embed
    
    def format_cooldown(self, seconds):
        if seconds == 0:
            return "No cooldown"
        
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0:
            parts.append(f"{seconds}s")
        
        return ", ".join(parts)
    
    def get_access_roles(self):
        if not self.selected_category:
            return []
        
        access_roles = []
        for role in self.interaction.guild.roles:
            permissions = self.selected_category.permissions_for(role)
            if permissions.read_messages and role != self.interaction.guild.default_role:
                access_roles.append(role)
        
        return access_roles
    
    async def select_category(self, interaction: discord.Interaction):
        category_id = int(interaction.data["values"][0])
        self.selected_category = interaction.guild.get_channel(category_id)
        if self.selected_category:
            await self.update_database_setting("Category ID", self.selected_category.id)
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("Category not found.", ephemeral=True)
    
    async def select_log_channel(self, interaction: discord.Interaction):
        channel_id = int(interaction.data["values"][0])
        self.selected_log_channel = interaction.guild.get_channel(channel_id)
        if self.selected_log_channel:
            await self.update_database_setting("Log Channel ID", self.selected_log_channel.id)
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("Log channel not found.", ephemeral=True)
    
    async def select_ping_role(self, interaction: discord.Interaction):
        role_id = int(interaction.data["values"][0])
        self.selected_ping_role = interaction.guild.get_role(role_id)
        if self.selected_ping_role:
            await self.update_database_setting("Ping Role ID", self.selected_ping_role.id)
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("Role not found.", ephemeral=True)
    
    async def update_database_setting(self, key, value):
        if self.server_config:
            ref = db.reference("/Tickets")
            tickets = ref.get()
            for ticket_key, ticket_data in tickets.items():
                if ticket_data.get("Server ID") == self.interaction.guild.id:
                    ref = db.reference(f"/Tickets/{ticket_key}/{key}")
                    ref.set(value)
                    break

class EnableSystemButton(Button):
    def __init__(self):
        super().__init__(label="Enable System", style=discord.ButtonStyle.green, emoji="✅")
    
    async def callback(self, interaction: discord.Interaction):
        category = await interaction.guild.create_category("Tickets")
        log_channel = await interaction.guild.create_text_channel("ticket-logs", category=category)
        
        await category.set_permissions(interaction.client.user, read_messages=True, manage_channels=True)
        await log_channel.set_permissions(interaction.client.user, read_messages=True, manage_channels=True)
        await category.set_permissions(interaction.guild.default_role, read_messages=False)
        await log_channel.set_permissions(interaction.guild.default_role, read_messages=False)
        
        data = {
            "Server Name": interaction.guild.name,
            "Server ID": interaction.guild.id,
            "Category ID": category.id,
            "Log Channel ID": log_channel.id,
            "Ping Role ID": None,
            "Cooldown": 0
        }
        
        ref = db.reference("/Tickets")
        ref.push().set(data)
        
        view = TicketSettingsView(self.view.bot, interaction, data)
        view.server_config = data
        await view.update_message(interaction)

class CooldownButton(Button):
    def __init__(self):
        super().__init__(label="Cooldown", style=discord.ButtonStyle.secondary, emoji="⏰", row=3)
    
    async def callback(self, interaction: discord.Interaction):
        modal = CooldownModal(self.view.server_config.get("Cooldown", 0))
        await interaction.response.send_modal(modal)
        
        async def on_timeout():
            try:
                await modal.wait()
                if modal.cooldown_seconds is not None:
                    await self.view.update_database_setting("Cooldown", modal.cooldown_seconds)
                    await self.view.update_message(interaction)
            except:
                pass
        
        asyncio.create_task(on_timeout())

class DisableSystemButton(Button):
    def __init__(self):
        super().__init__(label="Disable System", style=discord.ButtonStyle.red, row=4)
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Caution",
            description="Are you sure you want to disable the ticket system? This will:\n\n"
                       "- Remove all ticket configuration\n"
                       "- Keep existing ticket channels (you'll need to delete them manually)\n"
                       "- Clear all saved panels and settings\n\n"
                       "**This action cannot be undone!**",
            color=discord.Color.red()
        )
        
        view = ConfirmDisableView(self.view)
        await interaction.response.edit_message(embed=embed, view=view)


class RoleAccessButton(Button):
    def __init__(self):
        super().__init__(label="Role Access", style=discord.ButtonStyle.secondary, emoji="👥", row=3)
    
    async def callback(self, interaction: discord.Interaction):
        view = RoleAccessView(self.view.bot, interaction, self.view)
        await view.show_role_access(interaction)

class BlacklistButton(Button):
    def __init__(self):
        super().__init__(label="Blacklist", style=discord.ButtonStyle.secondary, emoji="🚫", row=3)
    
    async def callback(self, interaction: discord.Interaction):
        view = BlacklistView(self.view.bot, interaction, self.view)
        await view.show_blacklist(interaction)

class CooldownModal(Modal):
    def __init__(self, current_cooldown=0):
        super().__init__(title="Set Cooldown")
        self.cooldown_seconds = None
        
        current_str = ""
        if current_cooldown > 0:
            days, remainder = divmod(current_cooldown, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                current_str += f"{days}d"
            if hours > 0:
                current_str += f"{hours}h"
            if minutes > 0:
                current_str += f"{minutes}m"
            if seconds > 0:
                current_str += f"{seconds}s"
        
        self.add_item(TextInput(
            label="Cooldown Duration",
            placeholder="Example: 1d2h30m (1 day, 2 hours, 30 minutes)",
            default=current_str,
            required=False
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        cooldown_str = self.children[0].value.strip()
        seconds = 0
        
        if cooldown_str:
            days = re.search(r"(\d+)d", cooldown_str)
            hours = re.search(r"(\d+)h", cooldown_str)
            minutes = re.search(r"(\d+)m", cooldown_str)
            secs = re.search(r"(\d+)s", cooldown_str)
            
            if days:
                seconds += int(days.group(1)) * 86400
            if hours:
                seconds += int(hours.group(1)) * 3600
            if minutes:
                seconds += int(minutes.group(1)) * 60
            if secs:
                seconds += int(secs.group(1))
        
        self.cooldown_seconds = seconds
        await interaction.response.defer()

class ConfirmDisableView(View):
    def __init__(self, parent_view):
        super().__init__(timeout=60)
        self.parent_view = parent_view
    
    @discord.ui.button(label="Yes, Disable System", style=discord.ButtonStyle.danger)
    async def confirm_disable(self, interaction: discord.Interaction, button: Button):
        if self.parent_view.server_config:
            ref = db.reference("/Tickets")
            tickets = ref.get()
            for ticket_key, ticket_data in tickets.items():
                if ticket_data.get("Server ID") == interaction.guild.id:
                    ref = db.reference(f"/Tickets/{ticket_key}")
                    ref.delete()
                    break
        
        db.reference(f"/Ticket Panels/{interaction.guild.id}").delete()
        db.reference(f"/Ticket Blacklist/{interaction.guild.id}").delete()
        db.reference(f"/Ticket Instructions/{interaction.guild.id}").delete()
        
        view = TicketSettingsView(self.parent_view.bot, interaction, None)
        embed = await view.create_settings_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="No, Go Back", style=discord.ButtonStyle.secondary)
    async def cancel_disable(self, interaction: discord.Interaction, button: Button):
        await self.parent_view.update_message(interaction)


class RoleAccessView(View):
    def __init__(self, bot, interaction, parent_view):
        super().__init__(timeout=1800)
        self.bot = bot
        self.interaction = interaction
        self.parent_view = parent_view
    
    async def show_role_access(self, interaction: discord.Interaction):
        access_roles = self.parent_view.get_access_roles()
        
        embed = discord.Embed(
            title="👥 Role Access Management",
            description="Manage which roles can view and manage tickets.",
            color=discord.Color.blue()
        )
        
        if access_roles:
            roles_list = "\n".join([f"- {role.mention}" for role in access_roles])
            embed.add_field(name="Current Access Roles", value=roles_list, inline=False)
        else:
            embed.add_field(name="Current Access Roles", value="No roles configured", inline=False)
        
        self.clear_items()
        
        role_select = RoleSelect(placeholder="Select a role...")
        role_select.callback = self.select_role
        self.add_item(role_select)
        
        self.add_item(GrantAccessButton())
        self.add_item(RemoveAccessButton())
        self.add_item(BackToSettingsButton())
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def select_role(self, interaction: discord.Interaction):
        role_id = int(interaction.data["values"][0])
        self.selected_role = interaction.guild.get_role(role_id)
        await interaction.response.defer()

class GrantAccessButton(Button):
    def __init__(self):
        super().__init__(label="Grant Access", style=discord.ButtonStyle.green, emoji="✅")
    
    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, 'selected_role') or not self.view.selected_role:
            await interaction.response.send_message("Please select a role first!", ephemeral=True)
            return
        
        role = self.view.selected_role
        category = self.view.parent_view.selected_category
        
        if category:
            await category.set_permissions(
                role,
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                read_message_history=True
            )
        
        await self.view.show_role_access(interaction)

class RemoveAccessButton(Button):
    def __init__(self):
        super().__init__(label="Remove Access", style=discord.ButtonStyle.red, emoji="❌")
    
    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, 'selected_role') or not self.view.selected_role:
            await interaction.response.send_message("Please select a role first!", ephemeral=True)
            return
        
        role = self.view.selected_role
        category = self.view.parent_view.selected_category
        
        if category:
            await category.set_permissions(role, read_messages=None, send_messages=None)
        
        await self.view.show_role_access(interaction)


class BlacklistView(View):
    def __init__(self, bot, interaction, parent_view):
        super().__init__(timeout=1800)
        self.bot = bot
        self.interaction = interaction
        self.parent_view = parent_view
    
    async def show_blacklist(self, interaction: discord.Interaction):
        blacklisted = db.reference(f"/Ticket Blacklist/{interaction.guild.id}").get() or {}
        
        embed = discord.Embed(
            title="🚫 Blacklist Management",
            description="Manage users who are blocked from creating tickets.",
            color=discord.Color.blue()
        )
        
        if blacklisted:
            users_list = []
            for user_id in blacklisted.keys():
                user = await interaction.client.fetch_user(int(user_id))
                if user:
                    users_list.append(f"- {user.mention} ({user_id})")
                else:
                    users_list.append(f"- Unknown User ({user_id})")
            
            embed.add_field(name="Blacklisted Users", value="\n".join(users_list[:10]), inline=False)
            if len(users_list) > 10:
                embed.add_field(name="...", value=f"Plus {len(users_list) - 10} more users", inline=False)
        else:
            embed.add_field(name="Blacklisted Users", value="No users blacklisted", inline=False)
        
        self.clear_items()
        
        user_select = UserSelect(placeholder="Select a user...")
        user_select.callback = self.select_user
        self.add_item(user_select)
        
        self.add_item(BlacklistUserButton())
        self.add_item(UnblacklistUserButton())
        self.add_item(BackToSettingsButton())
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def select_user(self, interaction: discord.Interaction):
        user_id = int(interaction.data["values"][0])
        self.selected_user = await interaction.client.fetch_user(user_id)
        if not self.selected_user:
            self.selected_user = interaction.client.get_user(user_id)
            if not self.selected_user:
                try:
                    self.selected_user = await interaction.client.fetch_user(user_id)
                except:
                    self.selected_user = None
        await interaction.response.defer()

class BlacklistUserButton(Button):
    def __init__(self):
        super().__init__(label="Blacklist User", style=discord.ButtonStyle.red, emoji="🔨")
    
    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, 'selected_user') or not self.view.selected_user:
            await interaction.response.send_message("Please select a user first!", ephemeral=True)
            return
        
        user = self.view.selected_user
        ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}/{user.id}")
        ref.set(True)
        
        await self.view.show_blacklist(interaction)

class UnblacklistUserButton(Button):
    def __init__(self):
        super().__init__(label="Unblacklist User", style=discord.ButtonStyle.green, emoji="🔓")
    
    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, 'selected_user') or not self.view.selected_user:
            await interaction.response.send_message("Please select a user first!", ephemeral=True)
            return
        
        user = self.view.selected_user
        ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}/{user.id}")
        ref.delete()
        
        await self.view.show_blacklist(interaction)

class BackToSettingsButton(Button):
    def __init__(self):
        super().__init__(label="Back to Settings", style=discord.ButtonStyle.gray, emoji="↩️")
    
    async def callback(self, interaction: discord.Interaction):
        await self.view.parent_view.update_message(interaction)

class SnippetSelect(discord.ui.Select):
    def __init__(self, options, view):
        super().__init__(placeholder="Select a snippet to edit/remove...", options=options)
        self.snippets_view = view
    
    async def callback(self, interaction: discord.Interaction):
        self.snippets_view.selected_snippet = self.values[0]
        await interaction.response.defer()

class SnippetsView(View):
    def __init__(self, bot, interaction, parent_view):
        super().__init__(timeout=1800)
        self.bot = bot
        self.interaction = interaction
        self.parent_view = parent_view
        self.selected_snippet = None
        self.message = None
    
    async def show_snippets(self, interaction: discord.Interaction = None):
        snippets = db.reference(f"/Ticket Snippets/{self.interaction.guild.id}").get() or {}
        
        embed = discord.Embed(
            title="📝 Snippet Management",
            description="Manage prewritten responses for tickets.",
            color=discord.Color.blue()
        )
        
        if snippets:
            snippets_list = "\n".join([f"- **{alias}**: {response[:50]}{'...' if len(response) > 50 else ''}" for alias, response in snippets.items()])
            embed.add_field(name=f"Current Snippets ({len(snippets)}/25)", value=snippets_list, inline=False)
        else:
            embed.add_field(name="Current Snippets (0/25)", value="No snippets configured", inline=False)
        
        self.clear_items()
        
        if snippets:
            options = [discord.SelectOption(label=alias, value=alias, description=response[:50]) for alias, response in list(snippets.items())[:25]]
            snippet_select = SnippetSelect(options, self)
            self.add_item(snippet_select)
        
        self.add_item(AddSnippetButton())
        if snippets:
            self.add_item(EditSnippetButton())
            self.add_item(RemoveSnippetButton())
        self.add_item(BackToSettingsButton())
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = await interaction.original_response()
        else:
            await self.message.edit(embed=embed, view=self)
    
    async def select_snippet(self, interaction: discord.Interaction):
        self.selected_snippet = interaction.data["values"][0]
        await interaction.response.defer()

class AddSnippetButton(Button):
    def __init__(self):
        super().__init__(label="Add Snippet", style=discord.ButtonStyle.green, emoji="➕")
    
    async def callback(self, interaction: discord.Interaction):
        snippets = db.reference(f"/Ticket Snippets/{interaction.guild.id}").get() or {}
        if len(snippets) >= 25:
            await interaction.response.send_message("Maximum 25 snippets allowed per server!", ephemeral=True)
            return
        modal = SnippetModal(view=self.view)
        await interaction.response.send_modal(modal)

class EditSnippetButton(Button):
    def __init__(self):
        super().__init__(label="Edit Snippet", style=discord.ButtonStyle.primary, emoji="✏️")
    
    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, 'selected_snippet') or not self.view.selected_snippet:
            await interaction.response.send_message("Please select a snippet first!", ephemeral=True)
            return
        snippets = db.reference(f"/Ticket Snippets/{interaction.guild.id}").get() or {}
        response = snippets.get(self.view.selected_snippet, "")
        modal = SnippetModal(view=self.view, alias=self.view.selected_snippet, response=response, editing=True)
        await interaction.response.send_modal(modal)

class RemoveSnippetButton(Button):
    def __init__(self):
        super().__init__(label="Remove Snippet", style=discord.ButtonStyle.red, emoji="🗑️")
    
    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, 'selected_snippet') or not self.view.selected_snippet:
            await interaction.response.send_message("Please select a snippet first!", ephemeral=True)
            return
        ref = db.reference(f"/Ticket Snippets/{interaction.guild.id}/{self.view.selected_snippet}")
        ref.delete()
        await self.view.show_snippets(interaction)

class SnippetModal(Modal):
    def __init__(self, view=None, alias="", response="", editing=False):
        super().__init__(title="Add Snippet" if not editing else "Edit Snippet")
        self.view = view
        self.old_alias = alias if editing else None
        self.saved = False
        
        self.add_item(TextInput(
            label="Alias",
            placeholder="Short name for the snippet",
            default=alias,
            max_length=50,
            required=True
        ))
        
        self.add_item(TextInput(
            label="Response",
            placeholder="The prewritten response",
            default=response,
            max_length=2000,
            style=discord.TextStyle.paragraph,
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        alias = self.children[0].value.strip()
        response = self.children[1].value.strip()
        
        if not alias or not response:
            await interaction.response.send_message("Both alias and response are required!", ephemeral=True)
            return
        
        if self.old_alias and self.old_alias != alias:
            ref = db.reference(f"/Ticket Snippets/{interaction.guild.id}/{self.old_alias}")
            ref.delete()
        
        ref = db.reference(f"/Ticket Snippets/{interaction.guild.id}/{alias}")
        ref.set(response)
        self.saved = True
        
        if self.view:
            await self.view.show_snippets()
        
        await interaction.response.defer()

class SnippetsButton(Button):
    def __init__(self):
        super().__init__(label="Snippets", style=discord.ButtonStyle.secondary, emoji="📝", row=3)
    
    async def callback(self, interaction: discord.Interaction):
        view = SnippetsView(self.view.bot, interaction, self.view)
        await view.show_snippets(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ticket(bot))