import discord
import datetime
import aiohttp
import os

from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageEnhance
from commands.Welcome.createWelcomeMsg import createWelcomeMsg, script

class WelcomeEditor:
    def __init__(self, user_id, guild_id, existing_data=None):
        self.user_id = user_id
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
            "timestamp": False
        }
        self.button_links = []
        
        if existing_data:
            self.load_from_dict(existing_data)
    
    def load_from_dict(self, data):
        self.channel_id = data.get('channel_id')
        self.welcome_image_enabled = data.get('welcome_image_enabled', False)
        self.message_content = data.get('message_content', '')
        
        if 'embed' in data:
            self.embed_data = {**self.embed_data, **data['embed']}
        else:
            # Legacy welcome content structure
            self.embed_data['title'] = data.get('title', '')
            self.embed_data['description'] = data.get('description', '')
            color = data.get('color', '')
            if color and color.startswith('#'):
                try:
                    self.embed_data['color'] = int(color[1:], 16)
                except:
                    pass
        
        self.button_links = data.get('button_links', [])
    
    def to_dict(self):
        return {
            'channel_id': self.channel_id,
            'welcome_image_enabled': self.welcome_image_enabled,
            'message_content': self.message_content,
            'embed': self.embed_data,
            'button_links': self.button_links
        }
    
    def to_legacy_dict(self):
        return {
            'Server ID': self.guild_id,
            'Message Content': self.message_content,
            'Title': self.embed_data['title'],
            'Description': self.embed_data['description'],
            'Color': f"#{self.embed_data['color']:06x}"
        }
    
    def to_embed(self, user=None, guild=None):
        if self.is_embed_empty():
            return None
        
        embed = discord.Embed(
            title=script(self.embed_data["title"], user, guild) if self.embed_data["title"] else None,
            description=script(self.embed_data["description"], user, guild) if self.embed_data["description"] else None,
            color=self.embed_data["color"]
        )
        
        if self.embed_data["footer"]["text"]:
            footer_text = script(self.embed_data["footer"]["text"], user, guild) if user and guild else self.embed_data["footer"]["text"]
            embed.set_footer(
                text=footer_text,
                icon_url=self.embed_data["footer"]["icon_url"] or None
            )
        
        if self.embed_data["author"]["name"]:
            author_name = script(self.embed_data["author"]["name"], user, guild) if user and guild else self.embed_data["author"]["name"]
            embed.set_author(
                name=author_name,
                icon_url=self.embed_data["author"]["icon_url"] or None
            )
        
        if self.embed_data["thumbnail"]:
            embed.set_thumbnail(url=self.embed_data["thumbnail"])
        
        if self.embed_data["image"]:
            embed.set_image(url=self.embed_data["image"])
        
        for field in self.embed_data["fields"]:
            field_name = script(field["name"], user, guild) if user and guild else field["name"]
            field_value = script(field["value"], user, guild) if user and guild else field["value"]
            embed.add_field(
                name=field_name,
                value=field_value,
                inline=field["inline"]
            )
        
        if self.embed_data["timestamp"]:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            
        return embed
    
    def is_empty(self):
        return (
            not self.embed_data["title"] and
            not self.embed_data["description"] and
            not self.message_content and
            not self.embed_data["image"] and
            not self.embed_data["thumbnail"] and
            not self.embed_data["fields"] and
            not self.embed_data["author"]["name"] and
            not self.embed_data["footer"]["text"]
        )
    
    def is_embed_empty(self):
        return (
            not self.embed_data["title"] and
            not self.embed_data["description"] and
            not self.embed_data["image"] and
            not self.embed_data["thumbnail"] and
            not self.embed_data["fields"] and
            not self.embed_data["author"]["name"] and
            not self.embed_data["footer"]["text"]
        )
    
    async def save(self, guild_id):
        ref = db.reference(f"/WelcomeV2/{guild_id}")
        ref.set(self.to_dict())
        
        # Also save to legacy structure for backward compatibility
        legacy_ref = db.reference("/Welcome")
        welcome_data = legacy_ref.get() or {}
        
        for key, val in welcome_data.items():
            if val.get("Server ID") == guild_id:
                legacy_ref.child(key).delete()
                break
        
        legacy_data = {
            "Server ID": guild_id,
            "Welcome Channel ID": self.channel_id,
            "Welcome Image Enabled": self.welcome_image_enabled
        }
        legacy_ref.push().set(legacy_data)
        
        content_ref = db.reference("/Welcome Content")
        welcome_content = content_ref.get() or {}
        
        for key, val in welcome_content.items():
            if val.get("Server ID") == guild_id:
                content_ref.child(key).delete()
                break
        
        legacy_content = self.to_legacy_dict()
        content_ref.push().set(legacy_content)

class WelcomeEmbedModal(discord.ui.Modal, title="Edit Welcome Embed"):
    def __init__(self, editor: WelcomeEditor):
        super().__init__()
        self.editor = editor
        
        self.add_item(discord.ui.TextInput(
            label="Title",
            placeholder="Welcome embed title",
            default=editor.embed_data["title"],
            max_length=256,
            required=False
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Description", 
            placeholder="Welcome embed description",
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

class WelcomeMediaModal(discord.ui.Modal, title="Edit Welcome Media"):
    def __init__(self, editor: WelcomeEditor):
        super().__init__()
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

class WelcomeFieldModal(discord.ui.Modal, title="Edit Welcome Field"):
    def __init__(self, editor: WelcomeEditor, field_index=None):
        super().__init__()
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

class WelcomeButtonLinkModal(discord.ui.Modal, title="Edit Welcome Button Link"):
    def __init__(self, editor: WelcomeEditor, link_index=None):
        super().__init__()
        self.editor = editor
        self.link_index = link_index
        
        link_data = editor.button_links[link_index] if link_index is not None else {"label": "", "url": "", "emoji": ""}
        
        self.add_item(discord.ui.TextInput(
            label="Button Label",
            placeholder="Text shown on button",
            default=link_data["label"],
            max_length=80,
            required=True
        ))
        
        self.add_item(discord.ui.TextInput(
            label="URL",
            placeholder="https://example.com",
            default=link_data["url"],
            required=True
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Emoji (optional)",
            placeholder="Format: <:name:id> or unicode emoji",
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

class WelcomeMessageContentModal(discord.ui.Modal, title="Edit Welcome Message Content"):
    def __init__(self, editor: WelcomeEditor):
        super().__init__()
        self.editor = editor
        
        self.add_item(discord.ui.TextInput(
            label="Message Content",
            placeholder="Normal message content (appears above embed)",
            default=editor.message_content,
            max_length=2000,
            required=False,
            style=discord.TextStyle.paragraph
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        self.editor.message_content = self.children[0].value
        await interaction.response.defer()

class WelcomeFieldsEditorView(discord.ui.View):
    def __init__(self, cog, editor: WelcomeEditor, original_interaction: discord.Interaction):
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
        embed = self.editor.to_embed(interaction.user, interaction.guild) if interaction else self.editor.to_embed()
        
        if not embed:
            embed = discord.Embed(
                title="Fields Editor",
                description="Add and manage embed fields for your welcome message.",
                color=discord.Color.light_gray()
            )
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
    
    async def select_field(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeFieldModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.editor.save(self.original_interaction.guild_id)
        await self.update_message()
    
    @discord.ui.button(label="Edit Field", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("Please select a field first!", ephemeral=True)
            return
        modal = WelcomeFieldModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.editor.save(self.original_interaction.guild_id)
        await self.update_message()
    
    @discord.ui.button(label="Remove Field", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("Please select a field first!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        self.editor.embed_data["fields"].pop(self.selected_index)
        self.selected_index = None
        await self.editor.save(self.original_interaction.guild_id)
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        view = WelcomeSettingsView(self.cog, self.editor, self.original_interaction)
        await view.update_message()

class WelcomeButtonLinksEditorView(discord.ui.View):
    def __init__(self, cog, editor: WelcomeEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        self.selected_index = 0 if editor.button_links else None
        self.update_select()
    
    def update_select(self):
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        
        if self.editor.button_links:
            options = []
            for i, link in enumerate(self.editor.button_links):
                label = link["label"][:50] if link["label"] else f"Link {i+1}"
                options.append(discord.SelectOption(label=label, value=str(i)))
            
            select = discord.ui.Select(placeholder="Select a link to edit", options=options)
            select.callback = self.select_link
            self.add_item(select)
    
    async def update_message(self, interaction: discord.Interaction = None):
        self.update_select()
        embed = self.editor.to_embed(interaction.user, interaction.guild) if interaction else self.editor.to_embed()
        
        if not embed:
            embed = discord.Embed(
                title="Button Links Editor",
                description="Add and manage button links for your welcome message.",
                color=discord.Color.light_gray()
            )
        
        preview_view = discord.ui.View()
        for link in self.editor.button_links:
            try:
                emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
            except:
                emoji = None
            button = discord.ui.Button(
                label=link["label"],
                url=link["url"],
                emoji=emoji,
                style=discord.ButtonStyle.link
            )
            preview_view.add_item(button)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
            if self.editor.button_links:
                await interaction.followup.send("**Button Preview:**", view=preview_view, ephemeral=True)
        else:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
    
    async def select_link(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.selected_index = int(interaction.data["values"][0])
        await self.update_message(interaction)
    
    @discord.ui.button(label="Add Link", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeButtonLinkModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.editor.save(self.original_interaction.guild_id)
        await self.update_message()
    
    @discord.ui.button(label="Edit Link", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("Please select a link first!", ephemeral=True)
            return
        modal = WelcomeButtonLinkModal(self.editor, self.selected_index)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.editor.save(self.original_interaction.guild_id)
        await self.update_message()
    
    @discord.ui.button(label="Remove Link", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_index is None:
            await interaction.response.send_message("Please select a link first!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        self.editor.button_links.pop(self.selected_index)
        self.selected_index = None
        await self.editor.save(self.original_interaction.guild_id)
        await self.update_message(interaction)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        view = WelcomeSettingsView(self.cog, self.editor, self.original_interaction)
        await view.update_message()

class WelcomeSettingsView(discord.ui.View):
    def __init__(self, cog, editor: WelcomeEditor, original_interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.cog = cog
        self.editor = editor
        self.original_interaction = original_interaction
        
        default_channels = []
        if self.editor.channel_id:
            channel = self.original_interaction.guild.get_channel(self.editor.channel_id)
            if channel:
                default_channels = [channel]
        
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Select welcome channel...",
            channel_types=[discord.ChannelType.text],
            default_values=default_channels
        )
        self.channel_select.callback = self.select_channel
        self.add_item(self.channel_select)
        
        for child in self.children:
            if hasattr(child, 'label'):
                if child.label == "Toggle Custom Image":
                    child.label = "Disable Custom Image" if self.editor.welcome_image_enabled else "Enable Custom Image"
                    child.style = discord.ButtonStyle.danger if self.editor.welcome_image_enabled else discord.ButtonStyle.success
    
    async def save_settings(self):
        await self.editor.save(self.original_interaction.guild_id)
    
    async def update_message(self, interaction: discord.Interaction = None):
        default_channels = []
        if self.editor.channel_id:
            channel = self.original_interaction.guild.get_channel(self.editor.channel_id)
            if channel:
                default_channels = [channel]
        
        self.channel_select.default_values = default_channels
        
        content = self.editor.message_content if self.editor.message_content else None
        embed = self.editor.to_embed(interaction.user, interaction.guild) if interaction else self.editor.to_embed(self.original_interaction.user, self.original_interaction.guild)
        
        if not content and not embed:
            content = None
            embed = discord.Embed(
                title="Welcome Message Settings",
                description="Configure your server's welcome message using the options below. Right now, no welcome message is set up.",
                color=discord.Color.blue()
            )
        
        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(content=content, embed=embed, view=self)
            else:
                await interaction.response.send_message(content=content, embed=embed, view=self, ephemeral=True)
        else:
            await self.original_interaction.edit_original_response(content=content, embed=embed, view=self)
    
    async def select_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id = int(interaction.data["values"][0])
        self.editor.channel_id = channel_id
        await self.save_settings()
        await self.update_message(interaction)

    @discord.ui.button(label="Message", style=discord.ButtonStyle.secondary, emoji="💬", row=0)
    async def edit_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeMessageContentModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.save_settings()
        await self.update_message()
    
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.secondary, emoji="🖼️", row=0)
    async def edit_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeEmbedModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.save_settings()
        await self.update_message()
    
    @discord.ui.button(label="Media", style=discord.ButtonStyle.secondary, emoji="📷", row=0)
    async def edit_media(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeMediaModal(self.editor)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.save_settings()
        await self.update_message()
    
    @discord.ui.button(label="Fields", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def edit_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = WelcomeFieldsEditorView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    
    @discord.ui.button(label="Link Buttons", style=discord.ButtonStyle.secondary, emoji="🔗", row=0)
    async def edit_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = WelcomeButtonLinksEditorView(self.cog, self.editor, self.original_interaction)
        await view.update_message(interaction)
    

    @discord.ui.button(label="Toggle Custom Image", style=discord.ButtonStyle.secondary, emoji="🖼️", row=1)
    async def toggle_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        bg_path = f"./assets/Welcome Image Background/{interaction.guild_id}.png"
        
        if not os.path.exists(bg_path):
            await interaction.response.send_message(
                "<:no:1036810470860013639> No custom background image found! Use `/welcome upload` to add one first.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        self.editor.welcome_image_enabled = not self.editor.welcome_image_enabled
        button.label = "Disable Custom Image" if self.editor.welcome_image_enabled else "Enable Custom Image"
        button.style = discord.ButtonStyle.danger if self.editor.welcome_image_enabled else discord.ButtonStyle.success
        await self.save_settings()
        await self.update_message(interaction)
    
    @discord.ui.button(label="Variable Guide", style=discord.ButtonStyle.blurple, emoji="❓", row=1)
    async def show_guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Welcome Message Variables",
            description="Use these variables in your welcome message to display dynamic content:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Available Variables",
            value=(
                "`{mention}` - Mentions the new user\n"
                "`{user}` - Displays the username\n"
                "`{server}` - Displays the server name\n"
                "`{count}` - Shows the member count\n"
                "`{count-th}` - Shows the member count with ordinal (1st, 2nd, 3rd, etc.)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Example",
            value="Welcome {mention} to {server}! You are our {count-th} member!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Disable System", style=discord.ButtonStyle.danger, row=1)
    async def disable_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Remove from new database structure
        ref = db.reference(f"/WelcomeV2/{interaction.guild_id}")
        ref.delete()
        
        # Remove from legacy structure
        legacy_ref = db.reference("/Welcome")
        welcome_data = legacy_ref.get() or {}
        
        for key, val in welcome_data.items():
            if val.get("Server ID") == interaction.guild_id:
                legacy_ref.child(key).delete()
                break
        
        # Remove legacy content
        content_ref = db.reference("/Welcome Content")
        welcome_content = content_ref.get() or {}
        
        for key, val in welcome_content.items():
            if val.get("Server ID") == interaction.guild_id:
                content_ref.child(key).delete()
                break
        
        embed = discord.Embed(
            title="Welcome System Disabled",
            description="The welcome system has been disabled for this server.",
            color=discord.Color.red()
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        await interaction.response.edit_message(embed=embed, view=None)

class WelcomeEnableView(discord.ui.View):
    def __init__(self, cog, interaction: discord.Interaction):
        super().__init__(timeout=1800)
        self.cog = cog
        self.interaction = interaction
    
    @discord.ui.button(label="Enable System", style=discord.ButtonStyle.green, emoji="✅")
    async def enable_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        editor = WelcomeEditor(interaction.user.id, interaction.guild_id)
        view = WelcomeSettingsView(self.cog, editor, interaction)
        await view.update_message(interaction)

@app_commands.guild_only()
class Welcome(commands.GroupCog, name="welcome"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="settings", 
        description="Configure the welcome message with an advanced editor"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_settings(self, interaction: discord.Interaction) -> None:
        try:
            ref = db.reference(f"/WelcomeV2/{interaction.guild_id}")
            welcome_data = ref.get()
            
            if welcome_data:
                editor = WelcomeEditor(interaction.user.id, interaction.guild_id, welcome_data)
                view = WelcomeSettingsView(self, editor, interaction)
                await view.update_message(interaction)
            else:
                # Check legacy database structure
                legacy_ref = db.reference("/Welcome")
                legacy_data = legacy_ref.get() or {}
                
                found = False
                for key, val in legacy_data.items():
                    if val.get("Server ID") == interaction.guild_id:
                        # Convert legacy data to new format
                        editor = WelcomeEditor(interaction.user.id, interaction.guild_id)
                        editor.channel_id = val.get("Welcome Channel ID")
                        editor.welcome_image_enabled = val.get("Welcome Image Enabled", False)
                        
                        # Load legacy content if it exists
                        content_ref = db.reference("/Welcome Content")
                        content_data = content_ref.get() or {}
                        for content_key, content_val in content_data.items():
                            if content_val.get("Server ID") == interaction.guild_id:
                                editor.load_from_dict(content_val)
                                break
                        
                        # Show settings even if no content exists (use defaults)
                        view = WelcomeSettingsView(self, editor, interaction)
                        await view.update_message(interaction)
                        found = True
                        break
                
                if not found:
                    embed = discord.Embed(
                        title="Welcome System",
                        description="The welcome system is currently disabled. Enable it to welcome new members with custom messages!",
                        color=discord.Color.orange()
                    )
                    
                    view = WelcomeEnableView(self, interaction)
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    @welcome_settings.error
    async def welcome_settings_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="upload",
        description="Upload a custom background image for welcome messages"
    )
    @app_commands.describe(
        background_image="The background image for welcome messages (will be cropped to 1024x576)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_upload(
        self,
        interaction: discord.Interaction,
        background_image: discord.Attachment
    ) -> None:
        if not background_image.content_type.startswith('image/'):
            await interaction.response.send_message(
                "<:no:1036811164891480194> Please upload a valid image file!",
                ephemeral=True
            )
            return
        
        path = f"./assets/Welcome Image Background/{interaction.guild.id}.png"
        await background_image.save(path)
        
        image = Image.open(path)
        width = image.size[0]
        height = image.size[1]
        aspect = width / float(height)
        
        ideal_width = 1024
        ideal_height = 576
        ideal_aspect = ideal_width / float(ideal_height)
        
        if aspect > ideal_aspect:
            new_width = int(ideal_aspect * height)
            offset = (width - new_width) / 2
            resize = (offset, 0, width - offset, height)
        else:
            new_height = int(width / ideal_aspect)
            offset = (height - new_height) / 2
            resize = (0, offset, width, height - offset)
            
        thumb = image.crop(resize).resize((ideal_width, ideal_height), Image.LANCZOS)
        thumb.save(path)
        
        image = Image.open(path)
        enhancer = ImageEnhance.Brightness(image)
        im_output = enhancer.enhance(0.6)
        im_output.save(path)
        
        ref = db.reference(f"/WelcomeV2/{interaction.guild_id}")
        welcome_data = ref.get()
        
        if welcome_data:
            welcome_data['welcome_image_enabled'] = True
            ref.set(welcome_data)
        
        embed = discord.Embed(
            title="<:yes:1036811164891480194> Background Uploaded!",
            description="Custom background image has been uploaded and processed successfully.",
            color=discord.Color.green()
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @welcome_upload.error
    async def welcome_upload_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="sample", 
        description="Sends a sample welcome message to the configured channel"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_sample(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        
        ref = db.reference(f"/WelcomeV2/{interaction.guild_id}")
        welcome_data = ref.get()
        
        if welcome_data:
            editor = WelcomeEditor(interaction.user.id, interaction.guild_id, welcome_data)
            
            if not editor.channel_id:
                await interaction.followup.send(
                    "<:no:1036810470860013639> Welcome system is not properly configured! Use `/welcome settings` first.",
                    ephemeral=True
                )
                return
            
            channel = self.bot.get_channel(editor.channel_id)
            if not channel:
                await interaction.followup.send(
                    "<:no:1036810470860013639> Welcome channel not found! It may have been deleted.",
                    ephemeral=True
                )
                return
            
            embed = editor.to_embed(interaction.user, interaction.guild)
            message_content = script(editor.message_content, interaction.user, interaction.guild)
            
            view = discord.ui.View()
            for link in editor.button_links:
                try:
                    emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
                except:
                    emoji = None
                button = discord.ui.Button(
                    label=script(link["label"], interaction.user, interaction.guild),
                    url=script(link["url"], interaction.user, interaction.guild),
                    emoji=emoji,
                    style=discord.ButtonStyle.link
                )
                view.add_item(button)
            
            if editor.welcome_image_enabled:
                filename = await createWelcomeMsg(
                    interaction.user,
                    bg=f"./assets/Welcome Image Background/{interaction.guild.id}.png",
                )
                chn = self.bot.get_channel(1026904121237831700)
                msg = await chn.send(file=discord.File(filename))
                url = msg.attachments[0].proxy_url
                embed.set_image(url=url)
            
            await channel.send(content=message_content or None, embed=embed, view=view if editor.button_links else None)
            
            embed = discord.Embed(
                description=f"<:yes:1036811164891480194> Sample message sent to {channel.mention}",
                colour=0x00FF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        else:
            # Fall back to legacy system
            ref = db.reference("/Welcome")
            welcome = ref.get()
            
            welcomeChannel = False
            for key, val in welcome.items():
                if val["Server ID"] == interaction.guild.id:
                    welcomeChannel = val["Welcome Channel ID"]
                    welcomeImageEnabled = val["Welcome Image Enabled"]
                    break

            if not welcomeChannel:
                embed = discord.Embed(
                    title="Welcome message not enabled!",
                    description="This server does not have welcome message enabled! Use `/welcome settings` to enable first.",
                    colour=0xFF0000,
                )
                embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            ref2 = db.reference("/Welcome Content")
            welcomecontent = ref2.get()
            
            file = embed = None
            for key, val in welcomecontent.items():
                if val["Server ID"] == interaction.guild.id:
                    if val["Title"] != "" or val["Description"] != "":
                        hex = val["Color"]
                        if hex.startswith("#"):
                            hex = hex[1:]
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                "https://www.thecolorapi.com/id", params={"hex": hex}
                            ) as server:
                                if server.status == 200:
                                    js = await server.json()
                                    try:
                                        color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
                                    except:
                                        color = discord.Color.blurple()

                        embed = discord.Embed(
                            title=script(val["Title"], interaction.user, interaction.guild),
                            description=script(val["Description"], interaction.user, interaction.guild),
                            color=color,
                        )
                        if welcomeImageEnabled:
                            filename = await createWelcomeMsg(
                                interaction.user,
                                bg=f"./assets/Welcome Image Background/{interaction.guild.id}.png",
                            )
                            chn = self.bot.get_channel(1026904121237831700)
                            msg = await chn.send(file=discord.File(filename))
                            url = msg.attachments[0].proxy_url
                            embed.set_image(url=url)
                    elif val["Title"] == "" and val["Description"] == "":
                        if welcomeImageEnabled:
                            filename = await createWelcomeMsg(
                                interaction.user,
                                bg=f"./assets/Welcome Image Background/{interaction.guild.id}.png",
                            )
                            file = discord.File(filename)
                    
                    channel = self.bot.get_channel(welcomeChannel)
                    await channel.send(
                        script(val["Message Content"], interaction.user, interaction.guild),
                        embed=embed,
                        file=file,
                    )
                    embed = discord.Embed(
                        description=f"<:yes:1036811164891480194> Sample message sent to <#{welcomeChannel}>",
                        colour=0x00FF00,
                    )
                    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            embed = discord.Embed(
                title="Welcome message not enabled!",
                description="This server does not have welcome message enabled! Use `/welcome settings` to enable first.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @welcome_sample.error
    async def welcome_sample_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        except:
            await interaction.followup.send(f"```{str(error)}```", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))