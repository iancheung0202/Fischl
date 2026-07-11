import discord
import os
import re

from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageEnhance, ImageOps, ImageSequence
from commands.Events.createProfileCard import createProfileCard
from commands.Events.quests import update_quest
from commands.Events.helperFunctions import get_user_inventory, unpin_all_items, get_cosmetics, upsert_cosmetics
from commands.Events.trackData import is_elite_active

from commands.Events.config import FRAMES_DIRECTORY, INVENTORY_BG_PATH, ANIMATED_INVENTORY_BG_PATH, DEFAULT_BG_PATH, YES_EMOTE, NO_EMOTE, HMM_EMOTE, FONT_PRESETS, FONT_PATH

def resolve_font_path(font_name: str | None) -> str:
    if not font_name:
        return FONT_PATH
    font_path = FONT_PRESETS.get(font_name, FONT_PATH)
    return font_path if os.path.exists(font_path) else FONT_PATH

def resolve_animated_background_path(animated_background: str | None) -> str | None:
    if not animated_background:
        return None
    if os.path.exists(animated_background):
        return animated_background

    candidate = f"{ANIMATED_INVENTORY_BG_PATH}/{animated_background}"
    if os.path.exists(candidate):
        return candidate

    if not animated_background.lower().endswith(".gif"):
        candidate = f"{candidate}.gif"
        if os.path.exists(candidate):
            return candidate

    return None

def resolve_active_cosmetic_values(selected: dict, elite_active: bool) -> dict:
    return {
        "animated_background": selected.get("selected_animated_background") if elite_active else None,
        "embed_color_hex": selected.get("selected_embed_color_hex") if elite_active else None,
        "font": selected.get("selected_font") if elite_active else None,
    }

async def process_animated_background_upload(attachment: discord.Attachment, output_path: str):
    temp_path = f"{output_path}.upload"
    await attachment.save(temp_path)

    with Image.open(temp_path) as image:
        frames = []
        durations = []
        disposals = []

        for frame in ImageSequence.Iterator(image):
            frame_rgba = frame.convert("RGBA")
            fitted = ImageOps.fit(frame_rgba, (720, 256), method=Image.LANCZOS, centering=(0.5, 0.5))
            dimmed = ImageEnhance.Brightness(fitted).enhance(0.4)
            frames.append(fitted)
            frames[-1] = dimmed
            durations.append(frame.info.get("duration", 100))
            disposals.append(frame.info.get("disposal", 2))

    if not frames:
        raise ValueError("Animated background must contain at least one frame")

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=disposals,
        optimize=False,
    )

    try:
        os.remove(temp_path)
    except Exception:
        pass

async def pin_title_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    try:
        items = await get_user_inventory(interaction.client.pool, interaction.user.id, interaction.guild.id)
    except Exception as e:
        print(f"Error fetching inventory: {e}")
        items = []
    
    items_set = set()
    items_list = []

    for item in items:
        # item = (title, desc, cost, gid, timestamp, pinned)
        title = item[0]
        cost = item[2]
        
        if cost == 0:
            continue # Skip free items and filter to this guild
        
        role = None
        try: # Try to get role name if title is numeric (role ID)
            role = interaction.guild.get_role(int(title))
        except Exception:
            pass
        
        # Check if title matches current search
        if (current.lower() in str(title).lower() or (role and current.lower() in role.name.lower())):
            if title not in items_set:
                items_set.add(title)
                if isinstance(title, int) or str(title).isdigit():
                    items_list.append(app_commands.Choice(name=f"Role: {role.name}" if role else f"Role: {title}", value=str(title)))
                else:
                    items_list.append(app_commands.Choice(name=f"Title: {title}", value=str(title)))

    items_list.insert(0, app_commands.Choice(name=f"Unpin my current item only", value="unpin"))
    return items_list[:25]

async def title_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
    titles = cosmetics["titles"] if cosmetics else []
    choices = []
    
    for entry in titles:
        if len(entry) < 2:
            continue
        timestamp = entry[0]
        title_name = entry[1]
        
        if not title_name:
            continue
        
        display_name = title_name
        is_animated = "<a:" in title_name
        
        if is_animated:
            display_name = re.sub(r"<a:[a-zA-Z]+:\d+>", "", display_name).strip()
            display_name += " (Animated)"
        
        if current.lower() in display_name.lower():
            choices.append(app_commands.Choice(name=display_name, value=timestamp))
    
    choices.insert(0, app_commands.Choice(name="Unset title", value="unset"))
    return choices[:25]

async def font_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    for font_name in FONT_PRESETS:
        if current.lower() in font_name.lower():
            display_name = font_name if font_name == "Default" else f"{font_name} (Elite Track)"
            choices.append(app_commands.Choice(name=display_name, value=font_name))
    return choices[:25]

async def animated_bg_autocomplete(interaction: discord.Interaction, current: str):
    cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
    bgs = list(cosmetics["backgrounds"]) if cosmetics else []
    return [
        app_commands.Choice(name=bg, value=bg)
        for bg in bgs
        if current.lower() in bg.lower()
    ][:25]

async def frame_autocomplete(interaction: discord.Interaction, current: str):
    cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
    frames = list(cosmetics["frames"]) if cosmetics else []
    choices = []
    for frame in frames:
        base_name = frame.split('.')[0]
        display_name = f"{base_name} (Animated)" if frame.lower().endswith('.gif') else base_name
        if current.lower() in display_name.lower():
            choices.append(app_commands.Choice(name=display_name, value=frame))
    return choices[:25]

async def all_frames_autocomplete(interaction: discord.Interaction, current: str):
    frames_dir = FRAMES_DIRECTORY
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
    def __init__(self, user_id, guild_id, static_bg_provided=False, animated_bg_path=None, profile_frame=None, font_name=None):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.guild_id = guild_id
        self.static_bg_provided = static_bg_provided
        self.animated_bg_path = animated_bg_path
        self.profile_frame = profile_frame
        self.font_name = font_name

    async def on_timeout(self) -> None:
        if self.static_bg_provided:
            try:
                os.remove(f"{INVENTORY_BG_PATH}/{self.user_id}-temp.png")
            except Exception:
                pass
        if self.animated_bg_path:
            try:
                os.remove(self.animated_bg_path)
            except Exception:
                pass

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(f"{NO_EMOTE} You can't confirm this customization!", ephemeral=True)

        # Static background
        if self.static_bg_provided:
            try:
                try:
                    os.remove(f"{INVENTORY_BG_PATH}/{interaction.user.id}.png")
                except Exception:
                    pass
                
                os.rename(
                    f"{INVENTORY_BG_PATH}/{interaction.user.id}-temp.png",
                    f"{INVENTORY_BG_PATH}/{interaction.user.id}.png"
                )
            except Exception as e:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Failed to save background: {e}", ephemeral=True
                )

        pool = interaction.client.pool
        gid = self.guild_id
        uid = interaction.user.id

        # Read current cosmetics to preserve other selected fields
        current = await get_cosmetics(pool, gid, uid)
        selected = dict(current) if current else {}

        # Animated background
        if self.static_bg_provided:
            selected["selected_animated_background"] = None
        elif self.animated_bg_path:
            selected["selected_animated_background"] = f"{interaction.user.id}.gif"
            try:
                os.remove(f"{ANIMATED_INVENTORY_BG_PATH}/{interaction.user.id}.gif")
            except Exception:
                pass
            try:
                os.rename(self.animated_bg_path, f"{ANIMATED_INVENTORY_BG_PATH}/{interaction.user.id}.gif")
            except Exception as e:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Failed to save animated background: {e}", ephemeral=True
                )
        
        # Profile frame
        if self.profile_frame:
            selected["selected_profile_frame"] = self.profile_frame

        if self.font_name:
            selected["selected_font"] = self.font_name

        update_kwargs = {
            "selected_animated_background": selected.get("selected_animated_background"),
            "selected_profile_frame": selected.get("selected_profile_frame"),
            "selected_font": selected.get("selected_font"),
        }
        await upsert_cosmetics(pool, gid, uid, **update_kwargs)

        changes = []
        if self.static_bg_provided:
            changes.append("static background")
        if self.animated_bg_path:
            changes.append("animated background upload")
        if self.profile_frame:
            frame_name = self.profile_frame.split('.')[0]
            changes.append(f"profile frame to **{frame_name}**")
        if self.font_name:
            changes.append(f"font to **{self.font_name}**")
        
        desc = f"{interaction.user.mention}, your customization has been confirmed!"
        if changes:
            desc += "\n\nChanges applied:\n- " + "\n- ".join(changes)
        else:
            desc += " (No visual changes were made)"

        embed = discord.Embed(
            title=f"{YES_EMOTE} Customization Complete",
            description=desc,
            color=discord.Color.green()
        )
        await update_quest(self.user_id, self.guild_id, interaction.channel.id, {"customize_profile": 1}, interaction.client)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(f"{NO_EMOTE} You can't cancel this customization!", ephemeral=True)

        if self.static_bg_provided:
            try:
                os.remove(f"{INVENTORY_BG_PATH}/{interaction.user.id}-temp.png")
            except Exception:
                pass
        if self.animated_bg_path:
            try:
                os.remove(self.animated_bg_path)
            except Exception:
                pass

        embed = discord.Embed(
            title=f"{NO_EMOTE} Customization Cancelled",
            description=f"{interaction.user.mention}, no changes were applied.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class Customize(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        
    @app_commands.command(
        name="customize", description="Customize your inventory and profile"
    )
    @app_commands.describe(
        background="Your desired inventory background (auto cropped and scaled to 720x256px)",
        pin_inventory="Guild inventory reward to pin (displayed next to your name in mini-games)",
        profile_frame="Your desried inventory profile frame (static or animated)",
        profile_title="Free Track: Select owned titles from autocomplete; Elite Track: Enter any custom title",
        animated_background="Elite Track only: upload a GIF to use as your animated inventory background",
        custom_accent_color="Elite Track only: your custom accent color in hex code (e.g. #ff0000)",
        profile_font="Elite Track only: your profile card font preset",
    )
    @app_commands.autocomplete(
        pin_inventory=pin_title_autocomplete,
        profile_frame=frame_autocomplete,
        profile_title=title_autocomplete,
        profile_font=font_autocomplete,
    )
    async def customize(
        self,
        interaction: discord.Interaction,
        background: discord.Attachment = None,
        pin_inventory: str = None,
        profile_frame: str = None,
        profile_title: str = None,
        animated_background: discord.Attachment = None,
        custom_accent_color: str = None,
        profile_font: str = None,
    ) -> None:
        await interaction.response.defer(thinking=True)
        
        if not any([background, pin_inventory, animated_background, profile_frame, custom_accent_color, profile_font, profile_title]):
            return await interaction.followup.send(
                f"{NO_EMOTE} Please specify at least one customization option!"
            )

        if background and animated_background:
            return await interaction.followup.send(
                f"{NO_EMOTE} You can't set both a static and animated background at the same time!"
            )
        
        processed_pin = False
        preview_needed = any([background, animated_background, profile_frame, profile_font])
        cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
        current_selected = dict(cosmetics) if cosmetics else {}
        pending_font = None

        if profile_font:
            if profile_font not in FONT_PRESETS:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Invalid font preset. Choose one of the available presets."
                )
            if profile_font != "Default" and not (await is_elite_active(interaction.client.pool, interaction.user.id, interaction.guild.id) and current_selected.get("selected_font_unlocked")):
                return await interaction.followup.send(
                    f"{NO_EMOTE} You have not unlocked **custom font preset** on the Elite Track!"
                )
            pending_font = profile_font

        # Custom embed color
        if custom_accent_color:
            cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
            embed_color = cosmetics["embed_color"] if cosmetics else False
            if not embed_color:
                return await interaction.followup.send(
                    f"{NO_EMOTE} You have not unlocked **custom accent color** on the Elite Track!"
                )

            hex_color = custom_accent_color.strip().lstrip('#')
            if len(hex_color) != 6:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Invalid hex format! Use 6-digit hex code (e.g. #ff0000)"
                )

            try:
                int(hex_color, 16)
            except ValueError:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Invalid hex characters! Use 0-9 and A-F only"
                )

            await upsert_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id, selected_embed_color_hex=hex_color)

            color_int = int(hex_color, 16)
            await interaction.followup.send(
                embed=discord.Embed(
                    title=f"{YES_EMOTE} Custom Accent Color Updated",
                    description=f"{interaction.user.mention}, your accent color has been set to `#{hex_color}`!",
                    color=color_int
                )
            )
            
        # Server title
        if profile_title:
            await self.process_title(interaction, profile_title)
            
        # Pin item
        if pin_inventory:
            processed_pin = await self.process_pin_item(interaction, pin_inventory)
        
        # Backgrounds and profile frame
        if preview_needed:
            await self.process_visual_customizations(
                interaction,
                background,
                animated_background,
                profile_frame,
                processed_pin,
                pending_font
            )
        
        if custom_accent_color or profile_title or pin_inventory or profile_font:
             await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"customize_profile": 1}, interaction.client)

    async def process_animated_background(self, interaction: discord.Interaction, animated_background: discord.Attachment) -> str:
        if not animated_background.filename.lower().endswith(".gif"):
            raise ValueError("Animated background must be a GIF upload")

        cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
        selected = dict(cosmetics) if cosmetics else {}
        if not (await is_elite_active(interaction.client.pool, interaction.user.id, interaction.guild.id) and selected.get("selected_animated_background_unlocked")):
            raise ValueError("You have not unlocked **custom animated GIF background** on the Elite Track!")

        output_path = f"{ANIMATED_INVENTORY_BG_PATH}/{interaction.user.id}-temp.gif"
        await process_animated_background_upload(animated_background, output_path)
        return output_path

    async def process_pin_item(self, interaction: discord.Interaction, pin_inventory: str):
        pool = interaction.client.pool
        
        if pin_inventory == "unpin":
            from commands.Events.helperFunctions import get_pinned_item
            unpinned = await get_pinned_item(pool, interaction.user.id, interaction.guild.id)
            
            if unpinned is None:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title=f"{HMM_EMOTE} No Pinned Item",
                        description=f"{interaction.user.mention}, you don't have any items pinned!",
                        color=discord.Color.blue()
                    )
                )
                return True
            
            await unpin_all_items(pool, interaction.user.id, interaction.guild.id)
                
            role_mention = f"<@&{unpinned}>" if str(unpinned).isdigit() else unpinned
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📌 Item Unpinned",
                    description=f"**{role_mention}** is now unpinned!",
                    color=discord.Color.green()
                )
            )
            return True
        else:
            inventory = await get_user_inventory(pool, interaction.user.id, interaction.guild.id)
            exists = any(item[0] == str(pin_inventory) for item in inventory)
            
            if not exists:
                role_mention = f"<@&{pin_inventory}>" if str(pin_inventory).isdigit() else pin_inventory
                await interaction.followup.send(
                    embed=discord.Embed(
                        title=f"{NO_EMOTE} Invalid Item",
                        description=f"**{role_mention}** isn't in your inventory!",
                        color=discord.Color.red()
                    )
                )
                return False
            
            from commands.Events.helperFunctions import pin_item as pin_item_func
            await pin_item_func(pool, interaction.user.id, interaction.guild.id, pin_inventory)
                
            role_mention = f"<@&{pin_inventory}>" if str(pin_inventory).isdigit() else pin_inventory
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📌 Item Pinned",
                    description=f"**{role_mention}** is now pinned! It will appear alongside your name every time you win a game.",
                    color=discord.Color.green()
                )
            )
            return True
        
    async def process_title(self, interaction: discord.Interaction, title_value: str):
        pool = interaction.client.pool
        gid = interaction.guild.id
        uid = interaction.user.id
        cosmetics = await get_cosmetics(pool, gid, uid)
        selected = dict(cosmetics) if cosmetics else {}

        if title_value == "unset":
            await upsert_cosmetics(pool, gid, uid, selected_title=None, selected_custom_title=None)
            message = "Your title has been unset."
        else:
            titles = cosmetics["titles"] if cosmetics else []
            title_ts = {e[0] for e in titles if len(e) >= 2}
            
            if title_value in title_ts:
                title_name = next(e[1] for e in titles if e[0] == title_value)
                await upsert_cosmetics(pool, gid, uid, selected_title=title_value, selected_custom_title=None)
                message = f"Title set to: **{title_name}**"
            elif selected.get("selected_custom_title_unlocked") and await is_elite_active(pool, uid, gid):
                custom_title = title_value.strip()
                if not custom_title:
                    return await interaction.followup.send(
                        f"{NO_EMOTE} Custom title cannot be empty!",
                        ephemeral=True
                    )
                await upsert_cosmetics(pool, gid, uid, selected_title=None, selected_custom_title=custom_title)
                message = f"Custom title set to: **{custom_title}**"
            else:
                cosmetics_check = await get_cosmetics(pool, gid, uid)
                owned_titles = cosmetics_check["titles"] if cosmetics_check else []
                owned_ts = {e[0] for e in owned_titles if len(e) >= 2}
                if title_value and title_value not in owned_ts:
                    return await interaction.followup.send(
                        f"{NO_EMOTE} You cannot use custom titles, as you haven't unlocked them on the Elite Track. You can still select owned titles from the autocomplete.",
                        ephemeral=True
                    )
                return await interaction.followup.send(
                    f"{NO_EMOTE} You don't own this title!",
                    ephemeral=True
                )

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
        pin_processed: bool,
        font: str = None
    ):
        cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
        current_selected = dict(cosmetics) if cosmetics else {}
        elite_active = await is_elite_active(interaction.client.pool, interaction.user.id, interaction.guild.id)
        active_selected = resolve_active_cosmetic_values(current_selected, elite_active)
        accent_color_hex = active_selected["embed_color_hex"]
        font_name = font if font else active_selected["font"]
        
        # Animated background
        if animated_background:
            if not (elite_active and current_selected.get("selected_animated_background_unlocked")):
                return await interaction.followup.send(
                    f"{NO_EMOTE} You have not unlocked **custom animated GIF background** on the Elite Track!",
                    ephemeral=True
                )
            if animated_background.filename.lower().endswith(".gif"):
                anim_path = await self.process_animated_background(interaction, animated_background)
            else:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Animated backgrounds must be uploaded as GIF files!",
                    ephemeral=True
                )
        else:
            current_anim = resolve_animated_background_path(active_selected["animated_background"])
            anim_path = current_anim
            if current_anim is None and active_selected["animated_background"]:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Animated background file not found!",
                    ephemeral=True
                )

        # Profile frame
        if profile_frame:
            owned_frames = list(current_selected.get("frames", [])) if current_selected else []
            if profile_frame not in owned_frames:
                return await interaction.followup.send(
                    f"{NO_EMOTE} You don't own **{profile_frame.split('.')[0]}** profile frame!",
                    ephemeral=True
                )
            frame_path = f"{FRAMES_DIRECTORY}/{profile_frame}"
            if not os.path.exists(frame_path):
                return await interaction.followup.send(
                    f"{NO_EMOTE} File for **{profile_frame.split('.')[0]}** not found!",
                    ephemeral=True
                )

        # Static background
        temp_static_path = None
        if background:
            temp_static_path = f"{INVENTORY_BG_PATH}/{interaction.user.id}-temp.png"
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
                return await interaction.followup.send(f"{NO_EMOTE} Background processing failed: {e}")

        bg_path = None
        if background:
            bg_path = temp_static_path
        elif animated_background:
            bg_path = anim_path
        else:
            if elite_active and anim_path:
                bg_path = anim_path
            else:
                static_path = f"{INVENTORY_BG_PATH}/{interaction.user.id}.png"
                if os.path.exists(static_path):
                    bg_path = static_path

        if bg_path is None:
            bg_path = DEFAULT_BG_PATH  # Default background

        frame_path = None
        if profile_frame:
            frame_path = profile_frame
        else:
            current_frame = current_selected.get("selected_profile_frame")
            if current_frame:
                frame_path = current_frame

        filename = await createProfileCard(
            interaction.user, 
            "69,420", 
            "69", 
            "6,767", 
            "67", 
            "69,420", 
            "69", 
            "6,767", 
            "67", 
            bg=bg_path, 
            profile_frame=frame_path,
            accent_color_hex=accent_color_hex,
            font_name=font_name
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
            animated_bg_path=bg_path if animated_background else None,
            profile_frame=profile_frame,
            font_name=font
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
        
        frame_path = f"{FRAMES_DIRECTORY}/{profile_frame}"
        if not os.path.exists(frame_path):
            return await interaction.followup.send(
                f"{NO_EMOTE} Profile frame **{profile_frame.split('.')[0]}** not found!"
            )
        
        cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, interaction.user.id)
        current_selected = dict(cosmetics) if cosmetics else {}
        bg_path = None
        elite_active = await is_elite_active(interaction.client.pool, interaction.user.id, interaction.guild.id)
        
        static_path = f"{INVENTORY_BG_PATH}/{interaction.user.id}.png"
        if os.path.exists(static_path):
            bg_path = static_path
        else:
            current_anim = current_selected.get("selected_animated_background") if elite_active else None
            if current_anim:
                anim_path = f"{ANIMATED_INVENTORY_BG_PATH}/{current_anim}.gif"
                if os.path.exists(anim_path):
                    bg_path = anim_path
        
        if bg_path is None:
            bg_path = DEFAULT_BG_PATH
        
        try:
            filename = await createProfileCard(
                interaction.user,
                "69,420",
                "69",
                "6,767",
                "67",
                "69,420",
                "69",
                "6,767",
                "67",
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
                    f"{NO_EMOTE} Preview of **{profile_frame.split('.')[0]}** frame:",
                    file=discord.File(filename)
                )
                
            try:
                os.remove(filename)
            except Exception:
                pass
                
        except Exception as e:
            await interaction.followup.send(
                f"{NO_EMOTE} Failed to generate preview: {e}"
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Customize(bot))