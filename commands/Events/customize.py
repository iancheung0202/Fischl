import discord
import os
import re

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from PIL import Image, ImageEnhance
from commands.Events.createProfileCard import createProfileCard
from commands.Events.quests import update_quest

MORA_EMOTE = "<:MORA:1364030973611610205>"

async def pin_title_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    ref = db.reference("/User Events Inventory")
    inventories = ref.get()
    items_set = set()
    items_list = []

    if inventories:
        for key, val in inventories.items():
            if val["User ID"] == interaction.user.id:
                try:
                    for item in val["Items"]:
                        role = None
                        try:
                            role = interaction.guild.get_role(int(item[0]))
                        except Exception:
                            pass
                        if (
                            len(item) > 3
                            and item[3] == interaction.guild.id
                            and item[2] != 0
                            and (
                                current.lower() in str(item[0]).lower()
                                or (
                                    isinstance(item[0], int)
                                    or item[0].isdigit()
                                    and role
                                    and current.lower() in role.name.lower()
                                )
                            )
                        ):
                            if item[0] not in items_set:
                                items_set.add(item[0])
                                if isinstance(item[0], int) or str(item[0]).isdigit():
                                    items_list.append(
                                        app_commands.Choice(
                                            name=f"Role: {role.name}", value=item[0]
                                        )
                                    )
                                else:
                                    items_list.append(
                                        app_commands.Choice(
                                            name=f"Title: {item[0]}", value=item[0]
                                        )
                                    )
                except Exception as e:
                    print(e)

    items_list.insert(
        0, app_commands.Choice(name=f"Unpin my current item only", value="unpin")
    )
    return items_list[:25]

async def global_title_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    ref = db.reference(f"/Global User Titles/{interaction.user.id}/global_titles")
    titles = ref.get() or {}
    choices = []
    
    for key, title in titles.items():
        title_name = title["name"]
        guild_id = title["guild_id"]
        guild = interaction.client.get_guild(int(guild_id))
        guild_name = guild.name if guild else f"Server {guild_id}"
        
        is_animated = "<a:" in title_name
        display_name = f"{title_name} (from {guild_name})"
        
        if is_animated:
            display_name = re.sub(r"<a:[a-zA-Z]+:\d+>", "", display_name).strip()
            display_name += " (Animated)"
        
        if current.lower() in display_name.lower():
            choices.append(
                app_commands.Choice(name=display_name, value=key)
            )
    
    choices.insert(0, app_commands.Choice(
        name="Unset global title", value="unset"
    ))
    return choices[:25]

async def animated_bg_autocomplete(interaction: discord.Interaction, current: str):
    ref = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/animated_backgrounds")
    bgs = ref.get() or []
    return [
        app_commands.Choice(name=bg, value=bg)
        for bg in bgs
        if current.lower() in bg.lower()
    ][:25]

async def frame_autocomplete(interaction: discord.Interaction, current: str):
    ref = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/profile_frames")
    frames = ref.get() or []
    choices = []
    for frame in frames:
        base_name = frame.split('.')[0]
        display_name = f"{base_name} (Animated)" if frame.lower().endswith('.gif') else base_name
        if current.lower() in display_name.lower():
            choices.append(app_commands.Choice(name=display_name, value=frame))
    return choices[:25]

async def all_frames_autocomplete(interaction: discord.Interaction, current: str):
    frames_dir = "./assets/Profile Frame"
    choices = []
    
    if os.path.exists(frames_dir):
        files = os.listdir(frames_dir)
        for file in files:
            if file.startswith('.') or os.path.isdir(os.path.join(frames_dir, file)):
                continue
            
            if current.lower() in file.lower():
                base_name = file.split('.')[0]
                display_name = f"{base_name} (Animated)" if file.lower().endswith('.gif') else base_name
                choices.append(app_commands.Choice(name=display_name, value=file))
    
    choices.sort(key=lambda x: x.name.lower())
    
    return choices[:25]

class ConfirmCustomizationView(discord.ui.View):
    def __init__(self, user_id, guild_id, static_bg_provided=False, animated_bg=None, profile_frame=None):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.guild_id = guild_id
        self.static_bg_provided = static_bg_provided
        self.animated_bg = animated_bg
        self.profile_frame = profile_frame

    async def on_timeout(self) -> None:
        if self.static_bg_provided:
            try:
                os.remove(f"./assets/Mora Inventory Background/{self.user_id}-temp.png")
            except Exception:
                pass

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("<:no:1036810470860013639> You can't confirm this customization!", ephemeral=True)

        # Static background
        if self.static_bg_provided:
            try:
                try:
                    os.remove(f"./assets/Mora Inventory Background/{interaction.user.id}.png")
                except Exception:
                    pass
                
                os.rename(
                    f"./assets/Mora Inventory Background/{interaction.user.id}-temp.png",
                    f"./assets/Mora Inventory Background/{interaction.user.id}.png"
                )
            except Exception as e:
                return await interaction.response.send_message(
                    f"<:no:1036810470860013639> Failed to save background: {e}", ephemeral=True
                )

        ref = db.reference(f"/Global Progression Rewards/{self.guild_id}/{interaction.user.id}/selected")
        selected = ref.get() or {}
        
        # Animated background
        if self.static_bg_provided:
            selected["animated_background"] = None
        elif self.animated_bg:
            selected["animated_background"] = self.animated_bg
            try:
                os.remove(f"./assets/Mora Inventory Background/{interaction.user.id}.png")
            except Exception:
                pass
        
        # Profile frame
        if self.profile_frame:
            selected["profile_frame"] = self.profile_frame

        ref.set(selected)

        changes = []
        if self.static_bg_provided:
            changes.append("static background")
        if self.animated_bg:
            changes.append(f"animated background to **{self.animated_bg}**")
        if self.profile_frame:
            frame_name = self.profile_frame.split('.')[0]
            changes.append(f"profile frame to **{frame_name}**")
        
        desc = f"{interaction.user.mention}, your customization has been confirmed!"
        if changes:
            desc += "\n\nChanges applied:\n- " + "\n- ".join(changes)
        else:
            desc += " (No visual changes were made)"

        embed = discord.Embed(
            title="<:yes:1036811164891480194> Customization Complete",
            description=desc,
            color=discord.Color.green()
        )
        await update_quest(self.user_id, self.guild_id, interaction.channel.id, {"customize_profile": 1}, interaction.client)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("<:no:1036810470860013639> You can't cancel this customization!", ephemeral=True)

        if self.static_bg_provided:
            try:
                os.remove(f"./assets/Mora Inventory Background/{interaction.user.id}-temp.png")
            except Exception:
                pass

        embed = discord.Embed(
            title="<:no:1036810470860013639> Customization Cancelled",
            description=f"{interaction.user.mention}, no changes were applied.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class Customize(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        
    @app_commands.command(
        name="customize", description="Customize your mora inventory and profile"
    )
    @app_commands.describe(
        background="Your desired inventory background (auto cropped and scaled to 720x256px)",
        pin_item="Title/role name to pin (displayed next to your name in mini-games)",
        animated_background="Your desired animated inventory background",
        profile_frame="Your desried inventory profile frame (static or animated)",
        custom_embed_color="Your desired custom embed color in hex code (e.g. #ff0000)",
        global_title="Your desired global title (static or animated) to display on your inventory"
    )
    @app_commands.autocomplete(
        pin_item=pin_title_autocomplete,
        animated_background=animated_bg_autocomplete,
        profile_frame=frame_autocomplete,
        global_title=global_title_autocomplete
    )
    async def customize(
        self,
        interaction: discord.Interaction,
        background: discord.Attachment = None,
        pin_item: str = None,
        animated_background: str = None,
        profile_frame: str = None,
        custom_embed_color: str = None,
        global_title: str = None
    ) -> None:
        await interaction.response.defer(thinking=True)
        
        if not any([background, pin_item, animated_background, profile_frame, custom_embed_color, global_title]):
            return await interaction.followup.send(
                "<:no:1036810470860013639> Please specify at least one customization option!"
            )

        if background and animated_background:
            return await interaction.followup.send(
                "<:no:1036810470860013639> You can't set both a static and animated background at the same time!"
            )
        
        processed_pin = False
        preview_needed = any([background, animated_background, profile_frame])

        # Custom embed color
        if custom_embed_color:
            ref = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/embed_color")
            embed_color = ref.get() or False
            if not embed_color:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> You have not unlocked **custom embed color** from the progression track!"
                )

            hex_color = custom_embed_color.strip().lstrip('#')
            if len(hex_color) != 6:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> Invalid hex format! Use 6-digit hex code (e.g. #ff0000)"
                )

            try:
                int(hex_color, 16)
            except ValueError:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> Invalid hex characters! Use 0-9 and A-F only"
                )

            ref_selected = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/selected")
            selected = ref_selected.get() or {}
            selected["embed_color_hex"] = hex_color
            ref_selected.set(selected)

            color_int = int(hex_color, 16)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="<:yes:1036811164891480194> Custom Embed Color Updated",
                    description=f"{interaction.user.mention}, your embed color has been set to `#{hex_color}`!",
                    color=color_int
                )
            )
            
        # Global title
        if global_title:
            await self.process_global_title(interaction, global_title)
            processed_global = True
            
        # Pin item
        if pin_item:
            processed_pin = await self.process_pin_item(interaction, pin_item)
        
        # Backgrounds and profile frame
        if preview_needed:
            await self.process_visual_customizations(
                interaction,
                background,
                animated_background,
                profile_frame,
                processed_pin
            )
        
        if custom_embed_color or global_title or pin_item:
             await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"customize_profile": 1}, interaction.client)

    async def process_pin_item(self, interaction: discord.Interaction, pin_item: str):
        """Handle pin/unpin operations and return success status"""
        ref = db.reference("/User Events Inventory")
        inventories = ref.get()
        updated = False
        unpinned = None

        if inventories:
            for key, val in inventories.items():
                if val["User ID"] == interaction.user.id:
                    inv = val["Items"].copy()
                    
                    for i, item in enumerate(inv):
                        if (item[3] == interaction.guild.id and 
                            len(item) > 5 and 
                            item[5] == "Pinned"):
                            inv[i] = item[:-1]  # Remove "Pinned"
                            unpinned = item[0]
                    
                    # Pin new item
                    if pin_item != "unpin":
                        for i, item in enumerate(inv):
                            if (item[3] == interaction.guild.id and 
                                item[0] == str(pin_item)):
                                inv[i] = item + ["Pinned"]
                                updated = True
                    
                    ref.child(key).update({"Items": inv})
                    break

        if pin_item == "unpin":
            if unpinned is None:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="ℹ️ No Pinned Item",
                        description=f"{interaction.user.mention}, you don't have any items pinned!",
                        color=discord.Color.blue()
                    )
                )
                return True
                
            role_mention = f"<@&{unpinned}>" if unpinned.isdigit() else unpinned
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📌 Item Unpinned",
                    description=f"**{role_mention}** is now unpinned!",
                    color=discord.Color.green()
                )
            )
            return True
        else:
            if not updated:
                role_mention = f"<@&{pin_item}>" if pin_item.isdigit() else pin_item
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="<:no:1036810470860013639> Invalid Item",
                        description=f"**{role_mention}** isn't in your inventory!",
                        color=discord.Color.red()
                    )
                )
                return False
                
            role_mention = f"<@&{pin_item}>" if pin_item.isdigit() else pin_item
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📌 Item Pinned",
                    description=f"**{role_mention}** is now pinned! It will appear alongside your name every time you win a game.",
                    color=discord.Color.green()
                )
            )
            return True
        
    async def process_global_title(self, interaction: discord.Interaction, global_title: str):
        ref_selected = db.reference(
            f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/selected"
        )
        selected = ref_selected.get() or {}

        if global_title == "unset":
            selected.pop("global_title", None)
            message = "Your global title has been unset."
        else:
            global_ref = db.reference(f"/Global User Titles/{interaction.user.id}/global_titles")
            titles = global_ref.get() or {}

            if global_title in titles:
                selected["global_title"] = global_title
                title_name = titles[global_title]["name"]
                message = f"Global title set to: **{title_name}**"
            else:
                return await interaction.followup.send(
                    "<:no:1036810470860013639> You don't own this global title!",
                    ephemeral=True
                )

        ref_selected.set(selected)
        await interaction.followup.send(
            embed=discord.Embed(description=message, color=discord.Color.green()),
            ephemeral=True
        )

    async def process_visual_customizations(
        self,
        interaction: discord.Interaction,
        background: discord.Attachment,
        animated_background: str,
        profile_frame: str,
        pin_processed: bool
    ):
        ref_selected = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/selected")
        current_selected = ref_selected.get() or {}
        
        # Animated background
        if animated_background:
            owned_bgs = db.reference(
                f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/animated_backgrounds"
            ).get() or []
            if animated_background not in owned_bgs:
                return await interaction.followup.send(
                    f"<:no:1036810470860013639> You don't own **{animated_background}** animated background!",
                    ephemeral=True
                )
            anim_path = f"assets/Animated Mora Inventory Background/{animated_background}.gif"
            if not os.path.exists(anim_path):
                return await interaction.followup.send(
                    f"<:no:1036810470860013639> File for **{animated_background}** not found!",
                    ephemeral=True
                )

        # Profile frame
        if profile_frame:
            owned_frames = db.reference(
                f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/profile_frames"
            ).get() or []
            if profile_frame not in owned_frames:
                return await interaction.followup.send(
                    f"<:no:1036810470860013639> You don't own **{profile_frame.split('.')[0]}** profile frame!",
                    ephemeral=True
                )
            frame_path = f"assets/Profile Frame/{profile_frame}"
            if not os.path.exists(frame_path):
                return await interaction.followup.send(
                    f"<:no:1036810470860013639> File for **{profile_frame.split('.')[0]}** not found!",
                    ephemeral=True
                )

        # Static background
        temp_static_path = None
        if background:
            temp_static_path = f"./assets/Mora Inventory Background/{interaction.user.id}-temp.png"
            try:
                await background.save(temp_static_path)
                image = Image.open(temp_static_path)
                width, height = image.size
                aspect = width / height
                ideal_width, ideal_height = 720, 256
                ideal_aspect = ideal_width / ideal_height
                
                if aspect > ideal_aspect:
                    new_width = int(ideal_aspect * height)
                    offset = (width - new_width) / 2
                    resize = (offset, 0, width - offset, height)
                else:
                    new_height = int(width / ideal_aspect)
                    offset = (height - new_height) / 2
                    resize = (0, offset, width, height - offset)
                
                thumb = image.crop(resize).resize((ideal_width, ideal_height), Image.LANCZOS)
                thumb.save(temp_static_path)
                
                enhancer = ImageEnhance.Brightness(thumb)
                im_output = enhancer.enhance(0.4)
                im_output.save(temp_static_path)
            except Exception as e:
                return await interaction.followup.send(f"<:no:1036810470860013639> Background processing failed: {e}")

        bg_path = None
        if background:
            bg_path = temp_static_path
        elif animated_background:
            bg_path = anim_path
        else:
            static_path = f"./assets/Mora Inventory Background/{interaction.user.id}.png"
            if os.path.exists(static_path):
                bg_path = static_path
            else:
                current_anim = current_selected.get("animated_background")
                if current_anim:
                    anim_path = f"assets/Animated Mora Inventory Background/{current_anim}.gif"
                    if os.path.exists(anim_path):
                        bg_path = anim_path

        if bg_path is None:
            bg_path = "./assets/mora_bg.png"  # Default background

        frame_path = None
        if profile_frame:
            frame_path = profile_frame
        else:
            current_frame = current_selected.get("profile_frame")
            if current_frame:
                frame_path = current_frame

        filename = await createProfileCard(
            interaction.user, 
            "69,420", 
            "69", 
            bg=bg_path, 
            profile_frame=frame_path
        )

        preview_channel = self.bot.get_channel(1026968305208131645)
        preview_msg = await preview_channel.send(file=discord.File(filename))
        preview_url = preview_msg.attachments[0].proxy_url

        embed = discord.Embed(
            title="🎨 Customization Preview",
            description=f"Final preview for {interaction.user.mention}'s customization:",
            color=discord.Color.gold()
        )
        embed.set_image(url=preview_url)
        
        if pin_processed:
            embed.set_footer(text="Note: Your pin changes were already applied")

        view = ConfirmCustomizationView(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            static_bg_provided=bool(background),
            animated_bg=animated_background,
            profile_frame=profile_frame
        )
        
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(
        name="preview", description="Preview a profile frame on your profile card"
    )
    @app_commands.describe(
        profile_frame="The profile frame to preview (e.g., 'Golden Ring.png')"
    )
    @app_commands.autocomplete(
        profile_frame=all_frames_autocomplete
    )
    async def preview(
        self,
        interaction: discord.Interaction,
        profile_frame: str
    ) -> None:
        await interaction.response.defer(thinking=True)
        
        frame_path = f"./assets/Profile Frame/{profile_frame}"
        if not os.path.exists(frame_path):
            return await interaction.followup.send(
                f"<:no:1036810470860013639> Profile frame **{profile_frame.split('.')[0]}** not found!"
            )
        
        ref_selected = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{interaction.user.id}/selected")
        current_selected = ref_selected.get() or {}
        bg_path = None
        
        static_path = f"./assets/Mora Inventory Background/{interaction.user.id}.png"
        if os.path.exists(static_path):
            bg_path = static_path
        else:
            current_anim = current_selected.get("animated_background")
            if current_anim:
                anim_path = f"./assets/Animated Mora Inventory Background/{current_anim}.gif"
                if os.path.exists(anim_path):
                    bg_path = anim_path
        
        if bg_path is None:
            bg_path = "./assets/mora_bg.png"
        
        try:
            filename = await createProfileCard(
                interaction.user,
                "69,420",
                "69",
                bg=bg_path,
                profile_frame=profile_frame
            )
            
            preview_channel = self.bot.get_channel(1026968305208131645)
            if preview_channel:
                preview_msg = await preview_channel.send(file=discord.File(filename))
                preview_url = preview_msg.attachments[0].proxy_url
                
                # Create embed
                frame_name = profile_frame.split('.')[0]
                is_animated = profile_frame.lower().endswith('.gif')
                frame_display = f"{frame_name} {'(Animated)' if is_animated else '(Static)'}"
                
                embed = discord.Embed(
                    title="🖼️ Profile Frame Preview",
                    description=f"Preview of **{frame_display}** on {interaction.user.mention}'s profile card",
                    color=discord.Color.blue()
                )
                embed.set_image(url=preview_url)
                embed.set_footer(text="This is just a preview with placeholder values")
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"Preview of **{profile_frame.split('.')[0]}** frame:",
                    file=discord.File(filename)
                )
                
            try:
                os.remove(filename)
            except Exception:
                pass
                
        except Exception as e:
            await interaction.followup.send(
                f"<:no:1036810470860013639> Failed to generate preview: {e}"
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Customize(bot))