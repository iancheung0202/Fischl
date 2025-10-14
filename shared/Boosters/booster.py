import discord
import asyncio
import re
import aiohttp

from discord import app_commands
from discord.ext import commands, tasks
from firebase_admin import db
from discord.ui import View, Button
from io import BytesIO
from PIL import Image, ImageSequence

autoresponse_refs = {}
autoresponse_updated = {}
pending_role_requests = {}

class ConfirmDisableView(View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
        self.confirmed = False
        
    @discord.ui.button(label="Confirm Disable", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="System disable cancelled.", embed=None, view=None)
        self.stop()

def parse_color(color_str: str) -> discord.Color:
    if not color_str:
        return discord.Color.pink()
    
    clean_color = color_str.lstrip('#').lower()
    
    if len(clean_color) in (3, 6) and all(c in '0123456789abcdef' for c in clean_color):
        if len(clean_color) == 3:
            clean_color = ''.join(c * 2 for c in clean_color)
        return discord.Color(int(clean_color, 16))
    return discord.Color.pink()

def script(string, user, guild):
    return string.replace("{mention}", user.mention).replace("{server}", guild.name).replace("{user}", user.name).replace("{boost}", str(guild.premium_subscription_count))

class BoosterEmbedModal(discord.ui.Modal, title="Booster Embed Setup"):
    msg = discord.ui.TextInput(
        label="Message Content",
        style=discord.TextStyle.paragraph,
        placeholder="Use variables: {mention}, {server}, {user}, {boost}",
        required=False
    )
    embed_title = discord.ui.TextInput(
        label="Embed Title",
        max_length=256,
        required=False,
        placeholder="Use variables: {mention}, {server}, {user}, {boost}"
    )
    embed_desc = discord.ui.TextInput(
        label="Embed Description",
        style=discord.TextStyle.paragraph,
        placeholder="Use variables: {mention}, {server}, {user}, {boost}",
        required=False
    )
    color = discord.ui.TextInput(
        label="Embed Color",
        placeholder="Enter a hex color code (e.g. #FF0000)",
        max_length=7,
        required=False
    )
    image = discord.ui.TextInput(
        label="Image URL",
        required=False
    )

    def __init__(self, current_data=None):
        super().__init__()
        if current_data:
            self.msg.default = current_data.get("message", "")
            self.embed_title.default = current_data.get("title", "")
            self.embed_desc.default = current_data.get("description", "")
            self.color.default = current_data.get("color", "")
            self.image.default = current_data.get("image", "")

    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference(f"Booster Role/{interaction.guild.id}/embed")
        embed_data = {
            "message": self.msg.value,
            "title": self.embed_title.value,
            "description": self.embed_desc.value,
            "color": self.color.value,
            "image": self.image.value
        }
        ref.set(embed_data)
        await interaction.response.send_message("<:yes:1036811164891480194> Booster roles system configured! **Make sure my bot role is above the base booster role!**", ephemeral=True)

async def resize_media(content: bytes, max_height: int) -> BytesIO:
    with Image.open(BytesIO(content)) as img:
        if img.format == 'GIF': # Animated GIF
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(img):
                frames.append(frame.copy())
                durations.append(frame.info.get('duration', 100))
            
            resized_frames = []
            for frame in frames:
                width, height = frame.size
                new_height = min(height, max_height)
                new_width = int((new_height / height) * width)
                resized_frame = frame.resize((new_width, new_height), Image.LANCZOS)
                resized_frames.append(resized_frame)
            
            output = BytesIO()
            resized_frames[0].save(
                output,
                format='GIF',
                save_all=True,
                append_images=resized_frames[1:],
                duration=durations,
                loop=0
            )
            output.seek(0)
            return output
        
        else: # Static image
            width, height = img.size
            new_height = min(height, max_height)
            new_width = int((new_height / height) * width)
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            output = BytesIO()
            resized_img.save(output, format='PNG')
            output.seek(0)
            return output
        
class AutoResponseSetupModal(discord.ui.Modal, title="Auto Response Setup"):
    response = discord.ui.TextInput(
        label="Response Content",
        style=discord.TextStyle.paragraph,
        placeholder="Enter text, image URL, or GIF URL",
        required=True,
        max_length=300
    )

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.callback(interaction, self.response.value)


class AutoResponseApprovalView(View):
    def __init__(self, cog=None):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approveAutoResponse")
    async def approve(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        footer = embed.footer.text
        parts = footer.split('|')
        guild_id = int(parts[0].split(':')[1].strip())
        user_id = int(parts[1].split(':')[1].strip())
        
        for field in embed.fields:
            if field.name == "Response":
                response = field.value

        db.reference(f"Booster Role/{guild_id}/pending_autoresponses/{user_id}").delete()
        
        ref = db.reference(f"Booster Role/{guild_id}/autoresponses/{user_id}")
        config = {
            "response": response
        }
        ref.set(config)
        autoresponse_updated[guild_id] = True
        
        embed.title = "<:yes:1036811164891480194> Auto Response Approved"
        embed.color = discord.Color.green()
        await interaction.message.edit(embed=embed, view=None)
        
        guild = interaction.client.get_guild(guild_id)
        if guild:
            booster = await guild.fetch_member(user_id)
            if booster:
                try:
                    await booster.send(
                        f"<:yes:1036811164891480194> Your auto response in **{guild.name}** has been approved!\n"
                        "You may view or reset it using `/boosterrole autoresponse`."
                    )
                except Exception as e:
                    print(e)
                    
        await interaction.response.send_message("Approved!", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="rejectAutoResponse")
    async def reject(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        footer = embed.footer.text
        parts = footer.split('|')
        guild_id = int(parts[0].split(':')[1].strip())
        user_id = int(parts[1].split(':')[1].strip())
        
        db.reference(f"Booster Role/{guild_id}/pending_autoresponses/{user_id}").delete()
        
        embed.title = "<:no:1036810470860013639> Auto Response Rejected"
        embed.color = discord.Color.red()
        await interaction.message.edit(embed=embed, view=None)
        
        guild = interaction.client.get_guild(guild_id)
        if guild:
            booster = await guild.fetch_member(user_id)
            if booster:
                try:
                    await booster.send(
                        f"<:no:1036810470860013639> Your auto response in **{guild.name}** was rejected by staff.\n"
                        "You may submit a new one using `/boosterrole autoresponse`."
                    )
                except Exception as e:
                    print(e)
                    
        await interaction.response.send_message("Rejected!", ephemeral=True)


class AutoResponsePanelView(View):
    def __init__(self, cog, user_id, status, config=None):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.status = status  # "not_set", "pending", "active"
        self.config = config or {}
        self.update_button_states()
        
    def update_button_states(self):
        if self.status == "not_set":
            self.setup_button.disabled = False
            self.reset_button.disabled = True
        elif self.status == "pending":
            self.setup_button.disabled = True
            self.reset_button.disabled = True
        elif self.status == "active":
            self.setup_button.disabled = True
            self.reset_button.disabled = False
        
    def create_embed(self):
        """Create the embed based on current state"""
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
            color=discord.Color.blue()
        )
        
        if self.status == "not_set":
            status_text = "<:no:1036810470860013639> Not set up"
        elif self.status == "pending":
            status_text = "🟡 Pending approval"
        elif self.status == "active":
            status_text = "<:yes:1036811164891480194> Active"
            
        embed.add_field(name="Current Status", value=status_text, inline=False)
        
        if self.status in ("pending", "active"):
            response_preview = self.config["response"]
            embed.add_field(name="Response Preview", value=response_preview, inline=False)
            
            if self.status == "pending":
                embed.add_field(
                    name="Note", 
                    value="Your response is pending staff approval. You cannot edit it until it's approved or rejected.",
                    inline=False
                )
        
        embed.set_footer(text="This panel will expire in 3 minutes")
        return embed
        
    @discord.ui.button(label="Setup", style=discord.ButtonStyle.green)
    async def setup_button(self, interaction: discord.Interaction, button: Button):
        async def setup_callback(interaction, response_content):
            if len(response_content) > 300:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> Response must be 300 characters or less!",
                    ephemeral=True
                )

            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, response_content)
            new_response = response_content
            print(new_response)

            if urls:
                for url in urls:
                    print(url)
                    try:
                        async with aiohttp.ClientSession() as session:
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
                            }
                            async with session.get(url, headers=headers) as response:
                                if response.status != 200:
                                    print(await response.text())
                                    return await interaction.followup.send(
                                        "<:no:1036810470860013639> Your linked attachment(s) have expired or are invalid.\n"
                                        "-# If you're using a Discord file link, note that Discord attachments link expire after 24 hours.\n"
                                        "-# Please re-upload the file elsewhere and provide the updated link within that timeframe.",
                                        ephemeral=True
                                    )


                                content_type = response.headers.get('Content-Type', '')
                                if not content_type.startswith('image/'):
                                    continue

                                data = await response.read()
                                resized_media = await resize_media(data, 150)

                                channel = interaction.client.get_channel(1026968305208131645)
                                if not channel:
                                    continue

                                file = discord.File(resized_media, filename="response_media.gif" if "gif" in content_type else "response_media.png")
                                msg = await channel.send(file=file)
                                new_url = msg.attachments[0].url
                                print(new_url)

                                new_response = new_response.replace(url, new_url)

                    except Exception as e:
                        print(f"Error processing media: {e}")
                        
            print(new_response)
            guild_id = interaction.guild.id
            booster = interaction.user
            
            ref = db.reference(f"Booster Role/{guild_id}")
            config = ref.get() or {}
            log_channel_id = config.get("log")
            if not log_channel_id:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> Log channel not configured! Contact server staff.",
                    ephemeral=True
                )
        
            log_channel = interaction.guild.get_channel(log_channel_id)
            if not log_channel:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> Log channel not found! Contact server staff.",
                    ephemeral=True
                )
            
            pending_ref = db.reference(f"Booster Role/{guild_id}/pending_autoresponses/{booster.id}")
            pending_config = {"response": new_response}
            pending_ref.set(pending_config)
            self.status = "pending"
            self.config = pending_config
            self.update_button_states()
            await self.message.edit(embed=self.create_embed(), view=self)
            embed = discord.Embed(
                title="⏳ Auto Response Pending Approval",
                description=f"Booster: {booster.mention} (`{booster.id}`)",
                color=discord.Color.orange()
            )
            embed.add_field(name="Trigger Phrase", value="Mention Only", inline=False)
            embed.add_field(name="Response", value=new_response, inline=False)
            embed.set_footer(text=f"Guild ID: {guild_id} | User ID: {booster.id}")
            view = AutoResponseApprovalView(self.cog) 
            await log_channel.send(embed=embed, view=view)
            await interaction.followup.send(
                "<:yes:1036811164891480194> Auto response submitted for staff approval!",
                ephemeral=True
            )
            
        await interaction.response.send_modal(
            AutoResponseSetupModal(setup_callback)
        )

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red)
    async def reset_button(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id
        active_ref = db.reference(f"Booster Role/{guild_id}/autoresponses/{self.user_id}")
        active_ref.delete()
        pending_ref = db.reference(f"Booster Role/{guild_id}/pending_autoresponses/{self.user_id}")
        pending_ref.delete()
        autoresponse_updated[guild_id] = True
        self.status = "not_set"
        self.config = {}
        self.update_button_states()
        await self.message.edit(embed=self.create_embed(), view=self)
        await interaction.followup.send(
            "<:yes:1036811164891480194> Auto response configuration reset!",
            ephemeral=True
        )
        
    async def on_timeout(self):
        try:
            if self.message.id in self.cog.active_panels:
                del self.cog.active_panels[self.message.id]
            await self.message.delete()
        except:
            pass

class PendingRequestView(discord.ui.View):
    def __init__(self, pending_data):
        super().__init__(timeout=None)
        self.pending_data = pending_data
        
    async def create_embed(self):
        embed = discord.Embed(
            title="⏳ Pending Role Request",
            description="You already have a pending role request. Please wait for staff approval.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Name", value=self.pending_data.get("name", "Not set"), inline=False)
        embed.add_field(name="Color", value=self.pending_data.get("color", "Not set"), inline=False)
        
        icon_url = self.pending_data.get("icon_url")
        if icon_url:
            embed.add_field(name="Icon", value=f"[View Icon]({icon_url})", inline=False)
            embed.set_thumbnail(url=icon_url)
        else:
            embed.add_field(name="Icon", value="None", inline=False)
            
        return embed
    
class RoleApprovalView(View):
    def __init__(self, cog=None):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approveRole")
    async def approve(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        footer = embed.footer.text
        parts = footer.split('|')
        guild_id = int(parts[0].split(':')[1].strip())
        user_id = int(parts[1].split(':')[1].strip())
        
        name = None
        color = None
        icon_url = None
        for field in embed.fields:
            if field.name == "Name":
                name = field.value
            elif field.name == "Color":
                color = field.value
            elif field.name == "Icon" and field.value != "None":
                match = re.search(r'\[View Icon\]\((.*?)\)', field.value)
                if match:
                    icon_url = match.group(1)
        
        guild = interaction.client.get_guild(guild_id)
        if not guild:
            return await interaction.response.send_message("Guild not found", ephemeral=True)

        booster = await guild.fetch_member(user_id)
        if not booster:
            return await interaction.response.send_message("User not found", ephemeral=True)
        
        ref = db.reference(f"Booster Role/{guild_id}")
        config = ref.get() or {}
        base_role_id = config.get("base_role")
        if not base_role_id:
            return await interaction.response.send_message("System not configured", ephemeral=True)
        
        base_role = guild.get_role(base_role_id)
        if not base_role:
            return await interaction.response.send_message("Base role not found", ephemeral=True)
            
        color_obj = parse_color(color)
        try:
            role = await guild.create_role(name=name, color=color_obj)
            if icon_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(icon_url) as resp:
                            if resp.status == 200:
                                icon_data = await resp.read()
                                await role.edit(display_icon=icon_data)  # Correct parameter here
                except Exception as e:
                    print(f"Error setting role icon: {e}")
                    
            new_position = base_role.position + 1
            print(new_position)
            await interaction.guild.edit_role_positions(positions={
                role: new_position
            })
            await booster.add_roles(role)
            
            ref.child("roles").update({str(user_id): role.id})
            db.reference(f"Booster Role/{guild_id}/pending_roles/{user_id}").delete()
            
            embed.title = "<:yes:1036811164891480194> Role Request Approved"
            embed.color = discord.Color.green()
            await interaction.message.edit(embed=embed, view=None)
            
            try:
                await booster.send(
                    f"<:yes:1036811164891480194> Your custom booster role in **{guild.name}** has been approved!\n"
                    f"- **Name:** {name}\n"
                    f"- **Color:** `{color}`"
                )
            except Exception:
                pass
                
            await interaction.response.send_message("Role created successfully!", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error creating role: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="rejectRole")
    async def reject(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        footer = embed.footer.text
        parts = footer.split('|')
        guild_id = int(parts[0].split(':')[1].strip())
        user_id = int(parts[1].split(':')[1].strip())
        
        db.reference(f"Booster Role/{guild_id}/pending_roles/{user_id}").delete()
        
        embed.title = "<:no:1036810470860013639> Role Request Rejected"
        embed.color = discord.Color.red()
        await interaction.message.edit(embed=embed, view=None)
        
        guild = interaction.client.get_guild(guild_id)
        if guild:
            booster = await guild.fetch_member(user_id)
            if booster:
                try:
                    await booster.send(
                        f"<:no:1036810470860013639> Your custom booster role request in **{guild.name}** was rejected by staff.\n"
                        "You may submit a new request using `/boosterrole create`."
                    )
                except Exception:
                    pass
                    
        await interaction.response.send_message("Request rejected!", ephemeral=True)
        
class SettingsPanelView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id
        
    @discord.ui.button(label="Edit Greeting", style=discord.ButtonStyle.blurple)
    async def edit_greeting(self, interaction: discord.Interaction, button: Button):
        ref = db.reference(f"Booster Role/{self.guild_id}/embed")
        current_data = ref.get() or {}
        await interaction.response.send_modal(BoosterEmbedModal(current_data))
        
    @discord.ui.button(label="View Custom Roles", style=discord.ButtonStyle.grey)
    async def view_custom_roles(self, interaction: discord.Interaction, button: Button):
        config = db.reference(f"Booster Role/{interaction.guild.id}").get() or {}

        if not config:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )
        
        ref = db.reference(f"Booster Role/{interaction.guild.id}/roles")
        data = ref.get() or {}
        if not data:
            return await interaction.response.send_message("<:no:1036810470860013639> No booster roles found.", ephemeral=True)
        msg = "\n".join([f"<@{uid}> - <@&{rid}>" for uid, rid in data.items()])
        await interaction.response.send_message(embed=discord.Embed(title="Booster Roles", description=msg), ephemeral=True)
        
    @discord.ui.button(label="View Autoresponses", style=discord.ButtonStyle.grey)
    async def view_autoresponses(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        ref = db.reference(f"Booster Role/{self.guild_id}/autoresponses")
        autoresponses = ref.get() or {}
        
        if not autoresponses:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> No autoresponses configured",
                ephemeral=True
            )
            
        embed = discord.Embed(
            title="Active Autoresponses",
            color=discord.Color.blue()
        )
        
        for user_id, config in autoresponses.items():
            member = await interaction.guild.fetch_member(int(user_id))
            name = member.display_name if member else f"Unknown ({user_id})"
            trigger = "Mention Only"
            response_preview = config["response"]
            embed.add_field(
                name=f"{name} (`{user_id}`)",
                value=f"**Trigger:** {trigger}\n**Response:** {response_preview}",
                inline=False
            )
            
        await interaction.followup.send(embed=embed, ephemeral=True)


class BoosterRole(commands.GroupCog, name="boosterrole"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_panels = {}
        self.unloading = False

    async def cog_load(self):
        self.cleanup_loop.start()
        
    async def cleanup_all(self, manual=False, interaction=None):
        if self.unloading or self.bot.is_closed():
            return

        ref = db.reference("Booster Role")
        configs = ref.get() or {}
        member_cache = {}
        
        for guild_id, config in configs.items():
            guild = self.bot.get_guild(int(guild_id))
            if not guild or "base_role" not in config:
                continue

            custom_roles = config.get("roles", {})
            users_to_process = list(custom_roles.items())

            deleted_roles = 0
            failed_deletions = 0
            cleaned_responses = 0

            for user_id_str, role_id in users_to_process:
                try:
                    if not hasattr(guild, "roles") or guild.roles is None or len(guild.roles) == 0:
                        break

                    role = guild.get_role(role_id)
                    if not role:
                        db.reference(f"Booster Role/{guild_id}/roles/{user_id_str}").delete()
                        await self.log_action(
                            guild,
                            f"🧹 Removed database entry for user <@{user_id_str}> (ID: `{user_id_str}`) - Role not found",
                            "Database Cleanup"
                        )
                        cleaned_responses += 1
                        continue

                    if not hasattr(role, "members") or role.members is None:
                        continue

                    user_id = int(user_id_str)
                    cache_key = f"{guild_id}:{user_id}"
                    
                    if cache_key in member_cache:
                        booster = member_cache[cache_key]
                    else:
                        booster = None
                        try:
                            booster = await guild.fetch_member(user_id)
                            member_cache[cache_key] = booster
                        except discord.Forbidden:
                            member_cache[cache_key] = None 
                            continue
                        except discord.HTTPException as e:
                            member_cache[cache_key] = None
                            continue
                    
                    if not booster:
                        try:
                            await role.delete()
                            deleted_roles += 1
                            await self.log_action(
                                guild,
                                f"🗑️ Deleted role `{role.name}` (ID: `{role.id}`) for user who left the server (ID: `{user_id_str}`)",
                                "Expired Booster Cleanup"
                            )
                        except discord.Forbidden:
                            failed_deletions += 1
                            await self.log_action(
                                guild,
                                f"⚠️ Failed to delete role `{role.name}` (ID: `{role.id}`) for member ID `{user_id_str}`: Insufficient permissions",
                                "Cleanup Error"
                            )
                        except discord.HTTPException as e:
                            failed_deletions += 1
                            await self.log_action(
                                guild,
                                f"⚠️ Failed to delete role `{role.name}` (ID: `{role.id}`) for member ID `{user_id_str}`: {str(e)}",
                                "Cleanup Error"
                            )
                        db.reference(f"Booster Role/{guild_id}/roles/{user_id_str}").delete()
                        cleaned_responses += 1
                        continue

                    if not hasattr(booster, "premium_since"):
                        continue

                    if not booster.premium_since:
                        try:
                            await role.delete()
                            deleted_roles += 1
                            await self.log_action(
                                guild,
                                f"🗑️ Deleted role `{role.name}` (ID: `{role.id}`) for {booster.mention} (ID: `{booster.id}`) - No longer boosting",
                                "Expired Booster Cleanup"
                            )
                        except discord.Forbidden:
                            failed_deletions += 1
                            await self.log_action(
                                guild,
                                f"⚠️ Failed to delete role `{role.name}` (ID: `{role.id}`) for {booster.mention} (ID: `{booster.id}`): Insufficient permissions",
                                "Cleanup Error"
                            )
                        except discord.HTTPException as e:
                            failed_deletions += 1
                            await self.log_action(
                                guild,
                                f"⚠️ Failed to delete role `{role.name}` (ID: `{role.id}`) for {booster.mention} (ID: `{booster.id}`): {str(e)}",
                                "Cleanup Error"
                            )
                        db.reference(f"Booster Role/{guild_id}/roles/{user_id_str}").delete()
                        cleaned_responses += 1

                        autoresponse_ref = db.reference(f"Booster Role/{guild_id}/autoresponses/{user_id_str}")
                        if autoresponse_ref.get():
                            autoresponse_ref.delete()
                            await self.log_action(
                                guild,
                                f"🧹 Removed autoresponse for user <@{user_id_str}> (ID: `{user_id_str}`)",
                                "Auto Response Cleanup"
                            )
                            cleaned_responses += 1

                        pending_ref = db.reference(f"Booster Role/{guild_id}/pending_autoresponses/{user_id_str}")
                        if pending_ref.get():
                            pending_ref.delete()
                            await self.log_action(
                                guild,
                                f"🧹 Removed pending autoresponse for user <@{user_id_str}> (ID: `{user_id_str}`)",
                                "Pending Auto Response Cleanup"
                            )
                            cleaned_responses += 1

                        pending_roles = config.get("pending_roles", {})
                        for pending_user_id_str in list(pending_roles.keys()):
                            try:
                                pending_user_id = int(pending_user_id_str)
                                pending_cache_key = f"{guild_id}:{pending_user_id}"
                                
                                if pending_cache_key in member_cache:
                                    pending_booster = member_cache[pending_cache_key]
                                else:
                                    pending_booster = None
                                    try:
                                        pending_booster = await guild.fetch_member(pending_user_id)
                                        member_cache[pending_cache_key] = pending_booster
                                    except (discord.Forbidden, discord.HTTPException):
                                        member_cache[pending_cache_key] = None
                                
                                if not pending_booster or not pending_booster.premium_since:
                                    db.reference(f"Booster Role/{guild_id}/pending_roles/{pending_user_id_str}").delete()
                                    cleaned_responses += 1
                            except Exception as e:
                                print(f"Error cleaning pending role: {e}")
                    
                    else:
                        if role not in booster.roles:
                            try:
                                await booster.add_roles(role)
                                await self.log_action(
                                    guild,
                                    f"🔧 Re-assigned role `{role.name}` (ID: `{role.id}`) to {booster.mention} (ID: `{booster.id}`) - Role was missing",
                                    "Role Assignment Fix"
                                )
                            except discord.Forbidden:
                                await self.log_action(
                                    guild,
                                    f"⚠️ Failed to re-assign role `{role.name}` (ID: `{role.id}`) to {booster.mention} (ID: `{booster.id}`): Insufficient permissions",
                                    "Cleanup Error"
                                )
                            except discord.HTTPException as e:
                                await self.log_action(
                                    guild,
                                    f"⚠️ Failed to re-assign role `{role.name}` (ID: `{role.id}`) to {booster.mention} (ID: `{booster.id}`): {str(e)}",
                                    "Cleanup Error"
                                )

                except Exception as e:
                    await self.log_action(
                        guild,
                        f"⛔ Error processing cleanup for user ID `{user_id_str}`: {str(e)}",
                        "Cleanup Error"
                    )

        if manual and interaction:
            await interaction.response.send_message("<:yes:1036811164891480194> Cleanup completed successfully!", ephemeral=True)

    def cog_unload(self):
        self.unloading = True
        self.cleanup_loop.cancel()

    @tasks.loop(minutes=60)
    async def cleanup_loop(self):
        await self.cleanup_all()
        
    @cleanup_loop.before_loop
    async def before_cleanup_loop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(300)

    async def send_booster_embed(self, guild: discord.Guild, user: discord.Member):
        ref = db.reference(f"Booster Role/{guild.id}")
        config = ref.get() or {}

        if not config.get("channel") or not config.get("embed"):
            return

        channel = guild.get_channel(config["channel"])
        if not channel:
            return

        embed_data = config["embed"]
        color = parse_color(embed_data.get("color", "#FF73FA"))
        content = script(embed_data.get("message", ""), user, guild)
        embed = discord.Embed(
            title=script(embed_data.get("title", ""), user, guild),
            description=script(embed_data.get("description", ""), user, guild),
            color=color
        )
        if image := embed_data.get("image"):
            embed.set_image(url=image)

        await channel.send(content or None, embed=embed)

    async def log_action(self, guild: discord.Guild, content: str, title: str):
        ref = db.reference(f"Booster Role/{guild.id}")
        log_channel_id = ref.get().get("log")
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        embed = discord.Embed(title=title, description=content, color=discord.Color.blue())
        await log_channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        # Boost messages
        if message.type == discord.MessageType.premium_guild_subscription:
            ref = db.reference(f"Booster Role/{message.guild.id}")
            config = ref.get() or {}

            if config.get("system_channel") == message.channel.id:
                booster = message.author
                if booster and isinstance(booster, discord.Member):
                    await self.send_booster_embed(message.guild, booster)
            return

        # Autoresponses
        guild_id = message.guild.id
        if guild_id not in autoresponse_refs or autoresponse_updated.get(guild_id, False):
            autoresponse_refs[guild_id] = db.reference(f"Booster Role/{guild_id}/autoresponses")
            autoresponse_updated[guild_id] = False

        ref = autoresponse_refs.get(guild_id)
        if ref and f"<@" in message.content and f">" in message.content:
            autoresponses = ref.get() or {}
            
            mentioned_user_ids = set()
            for user_id_str in autoresponses.keys():
                user_id = int(user_id_str)
                if f"<@{user_id}>" in message.content or f"<@!{user_id}>" in message.content:
                    mentioned_user_ids.add(user_id)
            
            if mentioned_user_ids:
                for user_id in mentioned_user_ids:
                    try:
                        booster = await message.guild.fetch_member(user_id)
                        
                        if not booster or booster == message.author or not booster.premium_since:
                            continue

                        response = autoresponses[str(user_id)]["response"]
                        await message.channel.send(response)

                    except Exception as e:
                        print(f"Error processing autoresponse for user {user_id}: {e}")
    
    @app_commands.command(name="autoresponse", description="Manage your auto response configuration")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def autoresponse(self, interaction: discord.Interaction):
        if not interaction.user.premium_since and interaction.guild.id != 783528750474199041:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> You must be an active server booster to use this command!",
                ephemeral=True
            )
        
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get() or {}
        if not config:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )
        
        active_ref = db.reference(f"Booster Role/{interaction.guild.id}/autoresponses/{interaction.user.id}")
        active_config = active_ref.get()
        
        pending_ref = db.reference(f"Booster Role/{interaction.guild.id}/pending_autoresponses/{interaction.user.id}")
        pending_config = pending_ref.get()
        
        if active_config:
            status = "active"
            config_data = active_config
        elif pending_config:
            status = "pending"
            config_data = pending_config
        else:
            status = "not_set"
            config_data = {}
        
        view = AutoResponsePanelView(self, interaction.user.id, status, config_data)
        embed = view.create_embed()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        message = await interaction.original_response()
        self.active_panels[message.id] = (interaction.user.id, interaction.guild.id)
        view.message = message

    @app_commands.command(name="create", description="Create or update your booster role")
    @app_commands.describe(
        color="Enter a hex color code for your role (e.g. #FF0000)",
        name="Enter your custom role name",
        icon_attachment="Attach a role icon if the server supports it (Optional)",
        user="The booster to create role for (Admins only)"
    )
    @app_commands.checks.bot_has_permissions(manage_roles=True, manage_guild=True)
    async def create(self, interaction: discord.Interaction, color: str, name: str, icon_attachment: discord.Attachment = None, user: discord.Member = None):
        if not(interaction.user.guild_permissions.administrator) and user is not None and user != interaction.user:
            return await interaction.response.send_message("You cannot create booster roles for others without Administrator permissions.")
        elif user is None:
            user = interaction.user
        await interaction.response.defer(ephemeral=True)
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get() or {}

        if not config:
            return await interaction.followup.send(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )

        if "base_role" not in config:
            return await interaction.followup.send("<:no:1036810470860013639> Booster system not configured in this server!", ephemeral=True)
        
        if not user.premium_since and interaction.guild.id != 783528750474199041:
            return await interaction.followup.send("<:no:1036810470860013639> You must be an active server booster to use this command!", ephemeral=True)
        
        role_id = config.get("roles", {}).get(str(user.id))
        role = interaction.guild.get_role(role_id) if role_id else None

        if role:
            return await interaction.followup.send("You already have your custom role. Use `/boosterrole remove` to remove it first then setup again.")
        
        pending_ref = db.reference(f"Booster Role/{interaction.guild.id}/pending_roles/{user.id}")
        pending_data = pending_ref.get()
        if pending_data:
            view = PendingRequestView(pending_data)
            embed = await view.create_embed()
            return await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        icon_url = None
        icon_ignored = False
        if icon_attachment:
            if interaction.guild.premium_tier <= 1:
                icon_ignored = True
            else:
                try:
                    channel = self.bot.get_channel(1026968305208131645)
                    if channel:
                        file = await icon_attachment.to_file()
                        msg = await channel.send(file=file)
                        icon_url = msg.attachments[0].url
                except Exception as e:
                    print(f"Error processing role icon: {e}")

        pending_data = {
            "name": name,
            "color": color,
            "icon_url": icon_url
        }
        pending_ref.set(pending_data)
        
        log_channel_id = config.get("log")
        if not log_channel_id:
            return await interaction.followup.send(
                "<:no:1036810470860013639> Log channel not configured! Contact server staff.",
                ephemeral=True
            )
                
        log_channel = interaction.guild.get_channel(log_channel_id)
        if not log_channel:
            return await interaction.followup.send(
                "<:no:1036810470860013639> Log channel not found! Contact server staff.",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="⏳ Custom Role Request - Pending Approval",
            description=f"Booster: {user.mention} (`{user.id}`)",
            color=discord.Color.orange()
        )
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Color", value=color, inline=False)
        
        if icon_url:
            embed.add_field(name="Icon", value=f"[View Icon]({icon_url})", inline=False)
            embed.set_thumbnail(url=icon_url)
        else:
            embed.add_field(name="Icon", value="None", inline=False)
        embed.set_footer(text=f"Guild ID: {interaction.guild.id} | User ID: {user.id}")

        view = RoleApprovalView(self)
        await log_channel.send(embed=embed, view=view)
        
        embed = discord.Embed(
            title="<:yes:1036811164891480194> Role Request Submitted",
            description="Your custom booster role request has been submitted for staff approval!",
            color=discord.Color.green()
        )
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Color", value=color, inline=False)
        
        if icon_url:
            embed.add_field(name="Icon", value=f"[View Icon]({icon_url})", inline=False)
            embed.set_thumbnail(url=icon_url)
        else:
            embed.add_field(name="Icon", value="None", inline=False)
            
        if icon_ignored:
            embed.add_field(
                name="⚠️ Note",
                value="This server doesn't have enough boosts for role icons (needs 7+ boosts).\nYour icon attachment was ignored.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    @create.error
    async def create_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="remove", description="Remove your booster role")
    @app_commands.checks.cooldown(1, 600, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def remove(self, interaction: discord.Interaction):
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get() or {}

        if not config:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )
        
        role_id = config.get("roles", {}).get(str(interaction.user.id))
        role = interaction.guild.get_role(role_id) if role_id else None
        if role:
            try:
                await role.delete()
            except discord.Forbidden:
                return await interaction.response.send_message("<:no:1036810470860013639> Bot lacks permission to delete the role.", ephemeral=True)
            db.reference(f"Booster Role/{interaction.guild.id}/roles/{interaction.user.id}").delete()
            await self.log_action(interaction.guild, f"{interaction.user.mention} (ID: {interaction.user.id}) removed their booster role named `{role.name}`.", "Booster Role Removed")
            await interaction.response.send_message(f"<:yes:1036811164891480194> Your booster role `{role.name}` has been deleted and removed!", ephemeral=True)
        else:
            await interaction.response.send_message("<:no:1036810470860013639> You have no booster role to remove.", ephemeral=True)
    @remove.error
    async def remove_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="cleanup", description="Manual cleanup of expired boosters")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def cleanup(self, interaction: discord.Interaction):
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get() or {}

        if not config:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )
        
        await self.cleanup_all(manual=True, interaction=interaction)
    @cleanup.error
    async def cleanup_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="setup", description="Configure booster system")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        system_channel="The channel where Discord sends boost messages",
        public_channel="The channel to send custom booster messages",
        log_channel="The channel that logs all booster-related actions",
    )
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def setup(self, interaction: discord.Interaction, 
                   system_channel: discord.TextChannel, 
                   public_channel: discord.TextChannel, 
                   log_channel: discord.TextChannel):
        
        booster_role = interaction.guild.premium_subscriber_role
        if interaction.guild.id == 783528750474199041:
            booster_role = interaction.guild.get_role(1377445878876471447)
        if not booster_role:
            return await interaction.response.send_message("<:no:1036810470860013639> Unfortunately, the server must have a booster role in order to enable this system. This means that this server must have been boosted previously.", ephemeral=True)

        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        ref.set({
            "base_role": booster_role.id,
            "system_channel": system_channel.id,
            "channel": public_channel.id,
            "log": log_channel.id
        })
        await interaction.response.send_modal(BoosterEmbedModal())
    @setup.error
    async def setup_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="settings", description="Manage booster system settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings(self, interaction: discord.Interaction):
        """New settings panel command replacing /view"""
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get() or {}

        if not config:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="⚙️ Booster System Settings",
            description="Use the buttons below to manage booster system settings.\n\n"
                        "**Note:** Channel setups (system, public, log) cannot be changed here. "
                        "Re-run `/boosterrole setup` to change them.",
            color=discord.Color.blue()
        )
        
        base_role = interaction.guild.get_role(config.get("base_role"))
        system_channel = interaction.guild.get_channel(config.get("system_channel"))
        public_channel = interaction.guild.get_channel(config.get("channel"))
        log_channel = interaction.guild.get_channel(config.get("log"))
        
        embed.add_field(
            name="Current Configuration",
            value=(
                f"**Base Role:** {base_role.mention if base_role else 'Not found'}\n"
                f"**System Channel:** {system_channel.mention if system_channel else 'Not found'}\n"
                f"**Public Channel:** {public_channel.mention if public_channel else 'Not found'}\n"
                f"**Log Channel:** {log_channel.mention if log_channel else 'Not found'}"
            ),
            inline=False
        )
        
        view = SettingsPanelView(self, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @settings.error
    async def settings_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="disable", description="Disable the booster system and delete all custom roles")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    async def disable(self, interaction: discord.Interaction):
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get() or {}

        if not config:
            return await interaction.response.send_message(
                "<:no:1036810470860013639> Booster system is not enabled on this server!",
                ephemeral=True
            )

        view = ConfirmDisableView(self)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Are you sure you want to disable the booster system?",
                description="This will:\n"
                "- Delete **ALL** custom booster roles *(you can use `/boosterrole settings` to view all custom roles)*\n"
                "- Remove **ALL** configuration\n"
                "- **Permanently** disable the system\n\n"
                "**This action cannot be undone!**",
                color=0xFF0000
            ),
            view=view,
            ephemeral=True
        )

        await view.wait()

        if not view.confirmed:
            return

        await interaction.followup.send("<a:loading:1026905298088243240> Disabling booster system... This may take a while.", ephemeral=True)

        custom_roles = config.get("roles", {})
        deleted_roles = 0
        failed_deletions = 0

        for user_id_str, role_id in custom_roles.items():
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await role.delete()
                    deleted_roles += 1
                    await self.log_action(
                        interaction.guild,
                        f"🗑️ Deleted role `{role.name}` (ID: `{role.id}`) during system disable",
                        "System Disable"
                    )
                except Exception as e:
                    failed_deletions += 1
                    await self.log_action(
                        interaction.guild,
                        f"⚠️ Failed to delete role ID `{role_id}`: {str(e)}",
                        "System Disable Error"
                    )

        
        autoresponse_ref = db.reference(f"Booster Role/{interaction.guild.id}/autoresponses")
        autoresponse_count = len(autoresponse_ref.get() or {})
        autoresponse_ref.delete()
        
        pending_ref = db.reference(f"Booster Role/{interaction.guild.id}/pending_autoresponses")
        pending_count = len(pending_ref.get() or {})
        pending_ref.delete()
        
        pending_roles_ref = db.reference(f"Booster Role/{interaction.guild.id}/pending_roles")
        pending_roles_count = len(pending_roles_ref.get() or {})
        pending_roles_ref.delete()

        await self.log_action(
            interaction.guild,
            f"### 🚫 Booster system **disabled** by {interaction.user.mention}\n"
            f"- Deleted roles: `{deleted_roles}`\n"
            f"- Failed deletions: `{failed_deletions}`\n"
            f"- Removed `{autoresponse_count}` autoresponses\n"
            f"- Removed `{pending_count}` pending autoresponses\n"
            f"- Removed `{pending_roles_count}` pending booster roles\n"
            f"- **Configuration cleared**",
            "System Disabled"
        )

        ref.delete()
        embed = discord.Embed(
            title="Booster System Disabled",
            description=f"The booster system has been completely disabled.",
            color=discord.Color.red()
        )
        embed.add_field(name="Roles Deleted", value=str(deleted_roles))
        embed.add_field(name="Failed Deletions", value=str(failed_deletions))
        embed.add_field(name="Configuration", value="Removed from database")
        embed.set_footer(text="You can re-enable the system with /boosterrole setup")

        await interaction.followup.send(embed=embed, ephemeral=True)
    @disable.error
    async def disable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BoosterRole(bot))