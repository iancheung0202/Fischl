import discord
import datetime
import uuid

from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput, ChannelSelect
from firebase_admin import db

class EmbedEditor:
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
            "timestamp": False
        }
        self.button_links = []
        self.template_id = None
        self.template_owner = None
    
    def to_embed(self):
        if self.is_empty():
            return None
            
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
    
    def to_dict(self):
        return {
            "message_content": self.message_content,
            "embed_data": self.embed_data,
            "button_links": self.button_links,
            "template_owner": self.template_owner or self.user_id
        }
    
    @classmethod
    def from_dict(cls, user_id, guild_id, data, template_id=None):
        editor = cls(user_id, guild_id)
        editor.message_content = data.get("message_content", "")
        
        default_embed_data = editor.embed_data.copy()
        loaded_embed_data = data.get("embed_data", {})
        editor.embed_data = default_embed_data
        for key, value in loaded_embed_data.items():
            if isinstance(value, dict) and key in editor.embed_data and isinstance(editor.embed_data[key], dict):
                editor.embed_data[key].update(value)
            else:
                editor.embed_data[key] = value
        
        editor.button_links = data.get("button_links", [])
        editor.template_owner = data.get("template_owner")
        editor.template_id = template_id
        return editor
    
    @classmethod
    def from_embed(cls, user_id, guild_id, message: discord.Message):
        editor = cls(user_id, guild_id, edit_mode=True, message_to_edit=message)
        editor.message_content = message.content or ""
        
        if message.embeds:
            embed = message.embeds[0]
            editor.embed_data["title"] = embed.title or ""
            editor.embed_data["description"] = embed.description or ""
            editor.embed_data["color"] = embed.color.value if embed.color else discord.Color.blurple().value
            
            if embed.footer:
                editor.embed_data["footer"]["text"] = embed.footer.text or ""
                editor.embed_data["footer"]["icon_url"] = embed.footer.icon_url or ""
            
            if embed.author:
                editor.embed_data["author"]["name"] = embed.author.name or ""
                editor.embed_data["author"]["icon_url"] = embed.author.icon_url or ""
            
            editor.embed_data["thumbnail"] = embed.thumbnail.url if embed.thumbnail else ""
            editor.embed_data["image"] = embed.image.url if embed.image else ""
            
            editor.embed_data["fields"] = [
                {"name": field.name, "value": field.value, "inline": field.inline}
                for field in embed.fields
            ]
            
            editor.embed_data["timestamp"] = embed.timestamp is not None
        
        return editor

class EmbedModal(Modal):
    def __init__(self, editor: EmbedEditor, title="Edit Embed"):
        super().__init__(title=title)
        self.editor = editor
        
        self.add_item(TextInput(
            label="Title",
            placeholder="Embed title",
            default=editor.embed_data["title"],
            max_length=256,
            required=False
        ))
        
        self.add_item(TextInput(
            label="Description", 
            placeholder="Embed description",
            default=editor.embed_data["description"],
            max_length=4000,
            required=False,
            style=discord.TextStyle.paragraph
        ))
        
        self.add_item(TextInput(
            label="Color (Hex)",
            placeholder="#FF0000",
            default=f"#{editor.embed_data['color']:06x}",
            max_length=7,
            required=False
        ))
        
        self.add_item(TextInput(
            label="Footer Text",
            placeholder="Footer text",
            default=editor.embed_data["footer"]["text"],
            max_length=2048,
            required=False
        ))

        self.add_item(TextInput(
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

class MediaModal(Modal):
    def __init__(self, editor: EmbedEditor):
        super().__init__(title="Edit Media")
        self.editor = editor
        
        self.add_item(TextInput(
            label="Image URL",
            placeholder="Main image/banner URL",
            default=editor.embed_data["image"],
            required=False
        ))
        
        self.add_item(TextInput(
            label="Thumbnail URL",
            placeholder="Thumbnail image URL", 
            default=editor.embed_data["thumbnail"],
            required=False
        ))
        
        self.add_item(TextInput(
            label="Author Icon URL",
            placeholder="Author icon URL",
            default=editor.embed_data["author"]["icon_url"],
            required=False
        ))
        
        self.add_item(TextInput(
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

class FieldModal(Modal):
    def __init__(self, editor: EmbedEditor, field_index=None):
        super().__init__(title="Edit Field" if field_index is not None else "Add Field")
        self.editor = editor
        self.field_index = field_index
        
        field_data = editor.embed_data["fields"][field_index] if field_index is not None else {"name": "", "value": "", "inline": True}
        
        self.add_item(TextInput(
            label="Field Name",
            placeholder="Field title",
            default=field_data["name"],
            max_length=256,
            required=True
        ))
        
        self.add_item(TextInput(
            label="Field Value",
            placeholder="Field content",
            default=field_data["value"],
            max_length=1024,
            required=True,
            style=discord.TextStyle.paragraph
        ))
        
        self.add_item(TextInput(
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

class ButtonLinkModal(Modal):
    def __init__(self, editor: EmbedEditor, link_index=None):
        super().__init__(title="Edit Link" if link_index is not None else "Add Link")
        self.editor = editor
        self.link_index = link_index
        
        link_data = editor.button_links[link_index] if link_index is not None else {"label": "", "url": "", "emoji": ""}
        
        self.add_item(TextInput(
            label="Button Label",
            placeholder="Text shown on button",
            default=link_data["label"],
            max_length=80,
            required=True
        ))
        
        self.add_item(TextInput(
            label="URL",
            placeholder="https://example.com",
            default=link_data["url"],
            required=True
        ))
        
        self.add_item(TextInput(
            label="Emoji (optional)",
            placeholder="emoji name or ID",
            default=link_data["emoji"],
            required=False
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        link_data = {
            "label": self.children[0].value,
            "url": self.children[1].value,
            "emoji": self.children[2].value
        }
        
        if self.link_index is not None:
            self.editor.button_links[self.link_index] = link_data
        else:
            self.editor.button_links.append(link_data)
        
        await interaction.response.defer()

class SaveModal(Modal):
    def __init__(self, editor: EmbedEditor, is_save_as=False):
        title = "Save As New Template" if is_save_as else "Save Template"
        super().__init__(title=title)
        self.editor = editor
        self.is_save_as = is_save_as
        
        self.add_item(TextInput(
            label="Template Name",
            placeholder="Give this template a name",
            max_length=100,
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        template_name = self.children[0].value
        
        ref_base = db.reference(f"Embed Templates/{interaction.guild_id}")
        templates = ref_base.get() or {}
        total_templates = len(templates)
        user_templates = sum(1 for data in templates.values() if data.get("template_owner") == interaction.user.id)
        
        if total_templates >= 25:
            await interaction.response.send_message("Server template limit reached (25). Cannot save new template.", ephemeral=True)
            return
        
        if user_templates >= 4:
            await interaction.response.send_message("User template limit reached (4). Cannot save new template.", ephemeral=True)
            return
        
        template_id = str(uuid.uuid4())[:8]
        
        ref = db.reference(f"Embed Templates/{interaction.guild_id}/{template_id}")
        data = self.editor.to_dict()
        data["name"] = template_name
        data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ref.set(data)
        
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> Template saved as **{template_name}** (ID: `{template_id}`)",
            ephemeral=True
        )

class WebhookModal(Modal):
    def __init__(self):
        super().__init__(title="Webhook Settings")
        
        self.add_item(TextInput(
            label="Webhook Username",
            placeholder="Custom webhook username",
            max_length=80,
            required=False
        ))
        
        self.add_item(TextInput(
            label="Webhook Avatar URL",
            placeholder="URL for webhook avatar",
            required=False
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

class EmbedMainView(View):
    def __init__(self, cog, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        
        for child in self.children:
            if hasattr(child, 'label') and child.label == "Post":
                child.label = "Update" if self.editor.edit_mode else "Post"
        
        if self.editor.template_id and self.editor.template_owner == self.editor.user_id:
            delete_button = discord.ui.Button(label="Delete Template", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
            delete_button.callback = self.delete_template
            self.add_item(delete_button)
    
    async def update_message(self, interaction: discord.Interaction = None):
        embed = self.editor.to_embed()
        content = None
        
        if self.editor.is_empty():
            embed = discord.Embed(
                title="No Content Yet",
                description="Use the buttons below to start building your embed!",
                color=discord.Color.light_gray()
            )
        
        if interaction:
            await interaction.response.edit_message(content=content, embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.secondary, emoji="📝")
    async def edit_embed(self, interaction: discord.Interaction, button: Button):
        modal = EmbedModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Media", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def edit_media(self, interaction: discord.Interaction, button: Button):
        modal = MediaModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Fields", style=discord.ButtonStyle.secondary, emoji="📋")
    async def edit_fields(self, interaction: discord.Interaction, button: Button):
        view = FieldsEditorView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Button Links", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def edit_links(self, interaction: discord.Interaction, button: Button):
        view = ButtonLinksEditorView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Save", style=discord.ButtonStyle.success, emoji="💾", row=1)
    async def save_template(self, interaction: discord.Interaction, button: Button):
        if self.editor.template_id and self.editor.template_owner == interaction.user.id:
            ref = db.reference(f"Embed Templates/{interaction.guild_id}/{self.editor.template_id}")
            data = self.editor.to_dict()
            data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            ref.update(data)
            await interaction.response.send_message(f"<:yes:1036811164891480194> Template (ID: `{self.editor.template_id}`) updated!", ephemeral=True)
        else:
            modal = SaveModal(self.editor, is_save_as=False)
            await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Save As", style=discord.ButtonStyle.success, emoji="📁", row=1)
    async def save_as_template(self, interaction: discord.Interaction, button: Button):
        modal = SaveModal(self.editor, is_save_as=True)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Post", style=discord.ButtonStyle.green, emoji="📤", row=1)
    async def save_and_post(self, interaction: discord.Interaction, button: Button):
        if self.editor.edit_mode:
            embed = self.editor.to_embed()
            try:
                await self.editor.message_to_edit.edit(content=self.editor.message_content or None, embed=embed)
                if self.editor.button_links:
                    view = View()
                    for link in self.editor.button_links:
                        try:
                            emoji = link["emoji"] or None
                            if emoji:
                                emoji = discord.utils.get(interaction.client.emojis, name=emoji) or emoji
                        except:
                            emoji = None
                        button = Button(
                            label=link["label"],
                            url=link["url"],
                            emoji=emoji,
                            style=discord.ButtonStyle.link
                        )
                        view.add_item(button)
                    await self.editor.message_to_edit.edit(view=view)
                
                await interaction.response.send_message(content=f"<:yes:1036811164891480194> Embed updated successfully! [Jump to Message]({self.editor.message_to_edit.jump_url})", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(
                    f"<:no:1036810470860013639> Failed to update message: {str(e)}",
                    ephemeral=True
                )
        else:
            view = PostEmbedView(self.cog, self.editor, self.original_interaction)
            await view.update_message(interaction)
    
    async def delete_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref = db.reference(f"Embed Templates/{interaction.guild_id}/{self.editor.template_id}")
        ref.delete()
        self.editor.template_id = None
        self.editor.template_owner = None
        self.remove_item(button)
        await interaction.response.send_message("<:yes:1036811164891480194> Template deleted successfully!", ephemeral=True)
        await self.update_message()

class FieldsEditorView(View):
    def __init__(self, cog, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_index = 0 if editor.embed_data["fields"] else None
        self.update_select()
    
    def update_select(self):
        for item in self.children:
            if isinstance(item, Select) and item.custom_id == "fields_select":
                self.remove_item(item)
                break
        
        if self.editor.embed_data["fields"]:
            options = []
            for i, field in enumerate(self.editor.embed_data["fields"]):
                options.append(discord.SelectOption(
                    label=field["name"][:100] or f"Field {i+1}",
                    value=str(i),
                    description=field["value"][:100] if field["value"] else "No content",
                    default=i == self.selected_index
                ))
            
            select = Select(
                placeholder="Select a field to edit...",
                options=options,
                custom_id="fields_select",
                row=0
            )
            select.callback = self.select_field
            self.add_item(select)
            self.children.insert(0, self.children.pop())
    
    async def update_message(self, interaction: discord.Interaction = None):
        self.update_select()
        embed = self.editor.to_embed()
        content = None
        
        if self.editor.is_empty():
            embed = discord.Embed(
                title="No Content Yet",
                description="Use the buttons below to start building your embed!",
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
    async def add_field(self, interaction: discord.Interaction, button: Button):
        modal = FieldModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.selected_index = len(self.editor.embed_data["fields"]) - 1
        await self.update_message()
    
    @discord.ui.button(label="Edit Field", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_field(self, interaction: discord.Interaction, button: Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No field selected!", ephemeral=True)
            return
        modal = FieldModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
    
    @discord.ui.button(label="Remove Field", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_field(self, interaction: discord.Interaction, button: Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No field selected!", ephemeral=True)
            return
        
        self.editor.embed_data["fields"].pop(self.selected_index)
        if self.editor.embed_data["fields"]:
            self.selected_index = min(self.selected_index, len(self.editor.embed_data["fields"]) - 1)
        else:
            self.selected_index = None
        
        await self.update_message(interaction)
    
    @discord.ui.button(label="Move Up", style=discord.ButtonStyle.secondary, emoji="⬆️", row=2)
    async def move_up(self, interaction: discord.Interaction, button: Button):
        if self.selected_index is None or self.selected_index == 0:
            await interaction.response.send_message("<:no:1036810470860013639> Cannot move up!", ephemeral=True)
            return
        
        fields = self.editor.embed_data["fields"]
        fields[self.selected_index], fields[self.selected_index - 1] = fields[self.selected_index - 1], fields[self.selected_index]
        self.selected_index -= 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Move Down", style=discord.ButtonStyle.secondary, emoji="⬇️", row=2)
    async def move_down(self, interaction: discord.Interaction, button: Button):
        fields = self.editor.embed_data["fields"]
        if self.selected_index is None or self.selected_index == len(fields) - 1:
            await interaction.response.send_message("<:no:1036810470860013639> Cannot move down!", ephemeral=True)
            return
        
        fields[self.selected_index], fields[self.selected_index + 1] = fields[self.selected_index + 1], fields[self.selected_index]
        self.selected_index += 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        view = EmbedMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class ButtonLinksEditorView(View):
    def __init__(self, cog, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_index = 0 if editor.button_links else None
        self.update_select()
    
    def update_select(self):
        for item in self.children:
            if isinstance(item, Select) and item.custom_id == "links_select":
                self.remove_item(item)
                break
        
        if self.editor.button_links:
            options = []
            for i, link in enumerate(self.editor.button_links):
                options.append(discord.SelectOption(
                    label=link["label"][:100] or f"Link {i+1}",
                    value=str(i),
                    description=link["url"][:100],
                    default=i == self.selected_index
                ))
            
            select = Select(
                placeholder="Select a link to edit...",
                options=options,
                custom_id="links_select",
                row=0
            )
            select.callback = self.select_link
            self.add_item(select)
            self.children.insert(0, self.children.pop())
    
    async def update_message(self, interaction: discord.Interaction = None):
        self.update_select()
        embed = self.editor.to_embed()
        content = None
        
        if self.editor.is_empty():
            embed = discord.Embed(
                title="No Content Yet",
                description="Use the buttons below to start building your embed!",
                color=discord.Color.light_gray()
            )
        
        preview_view = View()
        for link in self.editor.button_links:
            try:
                emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
            except:
                emoji = None
            button = Button(
                label=link["label"],
                url=link["url"],
                emoji=emoji,
                style=discord.ButtonStyle.link
            )
            preview_view.add_item(button)
        
        if interaction:
            await interaction.response.edit_message(content=content, embed=embed, view=self)
            # Send preview separately if there are buttons
            if self.editor.button_links:
                await interaction.followup.send("**Button Preview:**", view=preview_view, ephemeral=True)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    async def select_link(self, interaction: discord.Interaction):
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)
    
    @discord.ui.button(label="Add Link", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_link(self, interaction: discord.Interaction, button: Button):
        modal = ButtonLinkModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.selected_index = len(self.editor.button_links) - 1
        await self.update_message()
        if self.editor.button_links:
            preview_view = View()
            for link in self.editor.button_links:
                try:
                    emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
                except:
                    emoji = None
                btn = Button(
                    label=link["label"],
                    url=link["url"],
                    emoji=emoji,
                    style=discord.ButtonStyle.link
                )
                preview_view.add_item(btn)
            await self.original_interaction.followup.send("**Button Preview:**", view=preview_view, ephemeral=True)
    
    @discord.ui.button(label="Edit Link", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_link(self, interaction: discord.Interaction, button: Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No link selected!", ephemeral=True)
            return
        modal = ButtonLinkModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.update_message()
        if self.editor.button_links:
            preview_view = View()
            for link in self.editor.button_links:
                try:
                    emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
                except:
                    emoji = None
                btn = Button(
                    label=link["label"],
                    url=link["url"],
                    emoji=emoji,
                    style=discord.ButtonStyle.link
                )
                preview_view.add_item(btn)
            await self.original_interaction.followup.send("**Button Preview:**", view=preview_view, ephemeral=True)
    
    @discord.ui.button(label="Remove Link", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_link(self, interaction: discord.Interaction, button: Button):
        if self.selected_index is None:
            await interaction.response.send_message("<:no:1036810470860013639> No link selected!", ephemeral=True)
            return
        
        self.editor.button_links.pop(self.selected_index)
        if self.editor.button_links:
            self.selected_index = min(self.selected_index, len(self.editor.button_links) - 1)
        else:
            self.selected_index = None
        
        await self.update_message(interaction)
    
    @discord.ui.button(label="Move Up", style=discord.ButtonStyle.secondary, emoji="⬆️", row=2)
    async def move_up(self, interaction: discord.Interaction, button: Button):
        if self.selected_index is None or self.selected_index == 0:
            await interaction.response.send_message("<:no:1036810470860013639> Cannot move up!", ephemeral=True)
            return
        
        links = self.editor.button_links
        links[self.selected_index], links[self.selected_index - 1] = links[self.selected_index - 1], links[self.selected_index]
        self.selected_index -= 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Move Down", style=discord.ButtonStyle.secondary, emoji="⬇️", row=2)
    async def move_down(self, interaction: discord.Interaction, button: Button):
        links = self.editor.button_links
        if self.selected_index is None or self.selected_index == len(links) - 1:
            await interaction.response.send_message("<:no:1036810470860013639> Cannot move down!", ephemeral=True)
            return
        
        links[self.selected_index], links[self.selected_index + 1] = links[self.selected_index + 1], links[self.selected_index]
        self.selected_index += 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        view = EmbedMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class PostEmbedView(View):
    def __init__(self, cog, editor: EmbedEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=1800)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.use_webhook = False
        self.webhook_data = {"username": "", "avatar_url": ""}
        self.channel_select = ChannelSelect(placeholder="Select channel to post...")
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)
    
    async def update_message(self, interaction: discord.Interaction = None):
        content = "### 📤 Choose where to post your embed.\n<:reply:1036792837821435976> If you want to save the embed as a template, you can go back and do so! Posting an embed does not automatically save it as a template."
        embed = self.editor.to_embed()
        
        if interaction:
            await interaction.response.edit_message(content=content, embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    async def select_channel(self, interaction: discord.Interaction):
        self.selected_channel = self.channel_select.values[0]
        await interaction.response.defer()
    
    @discord.ui.button(label="Use Webhook", style=discord.ButtonStyle.secondary, emoji="🪝", row=1)
    async def toggle_webhook(self, interaction: discord.Interaction, button: Button):
        modal = WebhookModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.use_webhook = True
        self.webhook_data["username"] = modal.children[0].value
        self.webhook_data["avatar_url"] = modal.children[1].value
        await interaction.followup.send("<:yes:1036811164891480194> Webhook settings saved!", ephemeral=True)
    
    @discord.ui.button(label="Post", style=discord.ButtonStyle.green, emoji="📤", row=1)
    async def post_embed(self, interaction: discord.Interaction, button: Button):
        if not hasattr(self, 'selected_channel'):
            await interaction.response.send_message("<:no:1036810470860013639> Please select a channel first!", ephemeral=True)
            return
        
        channel = self.selected_channel
        if not hasattr(channel, 'send'):
            channel = interaction.guild.get_channel(channel.id)
            if not channel:
                await interaction.response.send_message("<:no:1036810470860013639> Channel not found!", ephemeral=True)
                return
        
        final_view = View()
        for link in self.editor.button_links:
            try:
                emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
            except:
                emoji = None
            button = Button(
                label=link["label"],
                url=link["url"],
                emoji=emoji,
                style=discord.ButtonStyle.link
            )
            final_view.add_item(button)
        
        embed = self.editor.to_embed()
        
        try:
            if self.use_webhook and self.webhook_data["username"]:
                webhook = await channel.create_webhook(name="Embed Bot")
                await webhook.send(
                    content=self.editor.message_content or None,
                    embed=embed,
                    username=self.webhook_data["username"],
                    avatar_url=self.webhook_data["avatar_url"] or None
                )
                await webhook.delete()
            else:
                await channel.send(
                    content=self.editor.message_content or None,
                    embed=embed,
                    view=final_view if self.editor.button_links else None
                )
            
            await interaction.response.send_message(f"<:yes:1036811164891480194> Embed posted in {channel.mention}!", ephemeral=True)
            
            view = EmbedMainView(self.cog, self.editor, self.original_interaction)
            await view.update_message(interaction)
            
        except discord.Forbidden:
            await interaction.response.send_message("<:no:1036810470860013639> I don't have permission to send messages in that channel!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"<:no:1036810470860013639> Error posting embed: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=1)
    async def go_back(self, interaction: discord.Interaction, button: Button):
        view = EmbedMainView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)

class TemplateSelectView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.template_data = {}
    
    async def load_templates(self):
        try:
            ref = db.reference(f"Embed Templates/{self.guild_id}")
            templates = ref.get() or {}

            options = []
            for template_id, data in templates.items():
                name = data.get("name", "Unnamed Template")
                owner_id = data.get("template_owner")
                is_owner = owner_id == self.user_id

                option_label = f"{name} {'(Yours)' if is_owner else ''}"
                try:
                    owner = await self.cog.bot.fetch_user(owner_id) if owner_id is not None else None
                    owner_display = str(owner) if owner else 'Unknown'
                except Exception:
                    owner_display = 'Unknown'

                options.append(discord.SelectOption(
                    label=option_label[:100],
                    value=template_id,
                    description=(f"By {owner_display}" if not is_owner else "Your template")
                ))
                self.template_data[template_id] = data

            if options:
                select = Select(placeholder="Choose a template...", options=options)
                select.callback = self.select_template
                self.add_item(select)
            else:
                select = Select(
                    placeholder="No templates available",
                    options=[discord.SelectOption(label="No templates", value="none")],
                    disabled=True
                )
                self.add_item(select)

        except Exception as e:
            print(f"Error loading templates: {e}")
    
    async def select_template(self, interaction: discord.Interaction):
        template_id = interaction.data["values"][0]
        template_data = self.template_data[template_id]
        
        editor = EmbedEditor.from_dict(
            self.user_id, 
            self.guild_id, 
            template_data,
            template_id=template_id
        )
        
        view = EmbedMainView(self.cog, editor, interaction)
        await view.update_message(interaction)

class EmbedCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @app_commands.command(name="embed", description="Create and customize embeds with an advanced editor")
    @app_commands.checks.has_permissions(administrator=True)
    async def embed(self, interaction: discord.Interaction) -> None:
        try:
            ref = db.reference(f"Embed Templates/{interaction.guild_id}")
            templates = ref.get() or {}
            total_templates = len(templates)
            user_templates = sum(1 for data in templates.values() if data.get("template_owner") == interaction.user.id)
        except Exception:
            total_templates = 0
            user_templates = 0
        
        class InitialView(View):
            def __init__(self, cog, total_templates, user_templates):
                super().__init__(timeout=60)
                self.cog = cog
                self.total_templates = total_templates
                self.user_templates = user_templates
                for child in self.children:
                    if isinstance(child, Button) and child.label == "Create from Template":
                        child.disabled = self.total_templates == 0
            
            @discord.ui.button(label="Create New Blank Embed", style=discord.ButtonStyle.primary)
            async def new_embed(self, inter: discord.Interaction, button: Button):
                editor = EmbedEditor(inter.user.id, inter.guild_id)
                view = EmbedMainView(self.cog, editor, inter)
                await view.update_message(inter)
            
            @discord.ui.button(label="Create from Template", style=discord.ButtonStyle.secondary)
            async def from_template(self, inter: discord.Interaction, button: Button):
                view = TemplateSelectView(self.cog, inter.user.id, inter.guild_id)
                await view.load_templates()
                await inter.response.edit_message(embed=discord.Embed(title="Choose a Template", description="Select a template from the list below. You can only edit your own templates, but can view others' templates and save as your own.", color=discord.Color.blue()), view=view)
        
        embed = discord.Embed(
            title="Embed Editor",
            description=f"Choose how you want to create your embed:\n\n"
                       f"- **Create New Blank Embed** - Start from scratch\n"
                       f"- **Create from Template** - Use a saved template ({total_templates} total in server, {user_templates} yours)",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=InitialView(self, total_templates, user_templates),
            ephemeral=True
        )
    
    @embed.error
    async def embed_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "<:no:1036810470860013639> You need administrator permissions to use this command!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"<:no:1036810470860013639> An error occurred: {str(error)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="editembed",
        description="Edits a custom embed message"
    )
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
        thread: discord.Thread = None
    ) -> None:
        if "-" in id:
            id = int(id.split("-")[1])
        else:
            id = int(id)
        msg = await (thread or channel).fetch_message(id)

        try:
            ref = db.reference(f"Embed Templates/{interaction.guild_id}")
            templates = ref.get() or {}
            total_templates = len(templates)
            user_templates = sum(1 for data in templates.values() if data.get("template_owner") == interaction.user.id)
        except Exception:
            total_templates = 0
            user_templates = 0
        
        class EditInitialView(View):
            def __init__(self, cog, total_templates, user_templates, target_message):
                super().__init__(timeout=60)
                self.cog = cog
                self.total_templates = total_templates
                self.user_templates = user_templates
                self.target_message = target_message
                for child in self.children:
                    if isinstance(child, Button) and child.label == "Load from Template":
                        child.disabled = self.total_templates == 0
            
            @discord.ui.button(label="Load from Existing Content", style=discord.ButtonStyle.primary)
            async def load_existing(self, inter: discord.Interaction, button: Button):
                editor = EmbedEditor.from_embed(inter.user.id, inter.guild_id, self.target_message)
                view = EmbedMainView(self.cog, editor, inter)
                await view.update_message(inter)
            
            @discord.ui.button(label="Load from Template", style=discord.ButtonStyle.secondary)
            async def load_template(self, inter: discord.Interaction, button: Button):
                class EditTemplateSelectView(TemplateSelectView):
                    def __init__(self, cog, user_id, guild_id, target_message):
                        super().__init__(cog, user_id, guild_id)
                        self.target_message = target_message
                    
                    async def select_template(self, interaction: discord.Interaction):
                        template_id = interaction.data["values"][0]
                        template_data = self.template_data[template_id]
                        
                        editor = EmbedEditor.from_dict(
                            self.user_id, 
                            self.guild_id, 
                            template_data,
                            template_id=template_id
                        )
                        editor.edit_mode = True
                        editor.message_to_edit = self.target_message
                        
                        view = EmbedMainView(self.cog, editor, interaction)
                        await view.update_message(interaction)
                view = EditTemplateSelectView(self.cog, inter.user.id, inter.guild_id, self.target_message)
                await view.load_templates()
                await inter.response.edit_message(embed=discord.Embed(title="Choose a Template", description="Select a template from the list below. The template content will be applied to edit the selected message.", color=discord.Color.blue()), view=view)
        
        embed = discord.Embed(
            title="Edit Embed",
            description=f"Choose how to edit the selected message:\n\n"
                       f"- **Load from Existing Content** - Edit the current content of the message\n"
                       f"- **Load from Template** - Apply a template to replace the message content ({total_templates} total in server, {user_templates} yours)",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=EditInitialView(self, total_templates, user_templates, msg),
            ephemeral=True
        )
    
    @editembed.error
    async def editembed_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "<:no:1036810470860013639> You need administrator permissions to use this command!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"<:no:1036810470860013639> An error occurred: {str(error)}",
                ephemeral=True
            )

@app_commands.context_menu(name="Edit Embed")
@app_commands.checks.has_permissions(administrator=True)
async def edit_embed_context_menu(interaction: discord.Interaction, message: discord.Message):
    if message.author != interaction.client.user:
        await interaction.response.send_message(
            "❌ You can only edit messages sent by this bot!",
            ephemeral=True
        )
        return

    cog = interaction.client.get_cog('EmbedCommand')
    
    try:
        ref = db.reference(f"Embed Templates/{interaction.guild_id}")
        templates = ref.get() or {}
        total_templates = len(templates)
        user_templates = sum(1 for data in templates.values() if data.get("template_owner") == interaction.user.id)
    except Exception:
        total_templates = 0
        user_templates = 0
    
    class EditInitialView(View):
        def __init__(self, cog, total_templates, user_templates, target_message):
            super().__init__(timeout=60)
            self.cog = cog
            self.total_templates = total_templates
            self.user_templates = user_templates
            self.target_message = target_message
            for child in self.children:
                if isinstance(child, Button) and child.label == "Load from Template":
                    child.disabled = self.total_templates == 0
        
        @discord.ui.button(label="Load from Existing Content", style=discord.ButtonStyle.primary)
        async def load_existing(self, inter: discord.Interaction, button: Button):
            editor = EmbedEditor.from_embed(inter.user.id, inter.guild_id, self.target_message)
            view = EmbedMainView(self.cog, editor, inter)
            await view.update_message(inter)
        
        @discord.ui.button(label="Load from Template", style=discord.ButtonStyle.secondary)
        async def load_template(self, inter: discord.Interaction, button: Button):
            class EditTemplateSelectView(TemplateSelectView):
                def __init__(self, cog, user_id, guild_id, target_message):
                    super().__init__(cog, user_id, guild_id)
                    self.target_message = target_message
                
                async def select_template(self, interaction: discord.Interaction):
                    template_id = interaction.data["values"][0]
                    template_data = self.template_data[template_id]
                    
                    editor = EmbedEditor.from_dict(
                        self.user_id, 
                        self.guild_id, 
                        template_data,
                        template_id=template_id
                    )
                    editor.edit_mode = True
                    editor.message_to_edit = self.target_message
                    
                    view = EmbedMainView(self.cog, editor, interaction)
                    await view.update_message(interaction)
            view = EditTemplateSelectView(self.cog, inter.user.id, inter.guild_id, self.target_message)
            await view.load_templates()
            await inter.response.edit_message(embed=discord.Embed(title="Choose a Template", description="Select a template from the list below. The template content will be applied to edit the selected message.", color=discord.Color.blue()), view=view)
    
    embed = discord.Embed(
        title="Edit Embed",
        description=f"Choose how to edit the selected message:\n\n"
                   f"- **Load from Existing Content** - Edit the current content of the message\n"
                   f"- **Load from Template** - Apply a template to replace the message content ({total_templates} total in server, {user_templates} yours)",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(
        embed=embed,
        view=EditInitialView(cog, total_templates, user_templates, message),
        ephemeral=True
    )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedCommand(bot))
    bot.tree.add_command(edit_embed_context_menu)