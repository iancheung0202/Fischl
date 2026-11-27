"""Profile card looks: /customize with its preview and confirm step, and /preview for frames."""

import os
import re

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageEnhance, ImageOps, ImageSequence

from commands.Events.config import (
    ANIMATED_INVENTORY_BG_PATH,
    DEFAULT_BG_PATH,
    FONT_PRESETS,
    FRAMES_DIRECTORY,
    HMM_EMOTE,
    INVENTORY_BG_PATH,
    NO_EMOTE,
    YES_EMOTE,
)
from commands.Events.createProfileCard import createProfileCard
from commands.Events.helperFunctions import (
    get_cosmetics,
    get_pinned_item,
    get_user_inventory,
    pin_item,
    unpin_all_items,
    upsert_cosmetics,
)
from commands.Events.quests import update_quest
from commands.Events.trackData import is_elite_active

PREVIEW_CHANNEL = 1026968305208131645
CARD_SIZE = (720, 256)
# The numbers a preview card shows in place of the member's own.
SAMPLE = ("69,420", "69", "6,767", "67") * 2


def resolve_animated_background_path(animated_background: str | None) -> str | None:
    """Finds a stored animated background by path or by name, with or without `.gif`."""
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


async def process_animated_background_upload(
    attachment: discord.Attachment, output_path: str
):
    """Saves an uploaded GIF at `output_path`, each frame cut to the card's size and dimmed."""
    temp_path = f"{output_path}.upload"
    await attachment.save(temp_path)
    frames, durations, disposals = [], [], []
    with Image.open(temp_path) as image:
        for frame in ImageSequence.Iterator(image):
            fitted = ImageOps.fit(
                frame.convert("RGBA"),
                CARD_SIZE,
                method=Image.LANCZOS,
                centering=(0.5, 0.5),
            )
            frames.append(ImageEnhance.Brightness(fitted).enhance(0.4))
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
    remove(temp_path)


def save_static_background(path):
    """Cuts the picture at `path` to the card's shape from its middle, saves it, then dims it."""
    image = Image.open(path)
    width, height = image.size
    shape = CARD_SIZE[0] / CARD_SIZE[1]
    if width / height > shape:
        offset = (width - int(shape * height)) / 2
        box = (offset, 0, width - offset, height)
    else:
        offset = (height - int(width / shape)) / 2
        box = (0, offset, width, height - offset)
    card = image.crop(box).resize(CARD_SIZE, Image.LANCZOS)
    card.save(path)
    ImageEnhance.Brightness(card).enhance(0.4).save(path)


def remove(path):
    """Deletes a file if it can."""
    try:
        os.remove(path)
    except Exception:
        pass


def mention(item):
    """Gives an inventory item as shown to members: a role mention for a role ID."""
    return f"<@&{item}>" if str(item).isdigit() else item


def frame_label(file):
    """Gives a frame's name without its ending, marked when it moves."""
    name = file.split(".")[0]
    return f"{name} (Animated)" if file.lower().endswith(".gif") else name


async def cosmetics_of(interaction):
    """Gives the member's stored cosmetics, {} when there are none."""
    return (
        await get_cosmetics(
            interaction.client.pool, interaction.guild.id, interaction.user.id
        )
        or {}
    )


async def elite(interaction):
    """Says whether the member's Elite Track is running."""
    return await is_elite_active(
        interaction.client.pool, interaction.user.id, interaction.guild.id
    )


async def pin_title_autocomplete(interaction: discord.Interaction, current: str):
    """Offers the member's bought inventory items to pin, after the unpin choice."""
    try:
        items = await get_user_inventory(
            interaction.client.pool, interaction.user.id, interaction.guild.id
        )
    except Exception as e:
        print(f"Error fetching inventory: {e}")
        items = []
    seen = set()
    choices = [app_commands.Choice(name="Unpin my current item only", value="unpin")]
    for title, _, cost, *_ in items:
        if cost == 0:
            continue
        try:
            role = interaction.guild.get_role(int(title))
        except Exception:
            role = None
        if title in seen or not (
            current.lower() in str(title).lower()
            or (role and current.lower() in role.name.lower())
        ):
            continue
        seen.add(title)
        if isinstance(title, int) or str(title).isdigit():
            name = f"Role: {role.name}" if role else f"Role: {title}"
        else:
            name = f"Title: {title}"
        choices.append(app_commands.Choice(name=name, value=str(title)))
    return choices[:25]


async def title_autocomplete(interaction: discord.Interaction, current: str):
    """Offers the titles the member owns, after the unset choice."""
    cosmetics = await get_cosmetics(
        interaction.client.pool, interaction.guild.id, interaction.user.id
    )
    choices = [app_commands.Choice(name="Unset title", value="unset")]
    for entry in cosmetics["titles"] if cosmetics else []:
        if len(entry) < 2 or not entry[1]:
            continue
        name = entry[1]
        if "<a:" in name:
            name = re.sub(r"<a:[a-zA-Z]+:\d+>", "", name).strip() + " (Animated)"
        if current.lower() in name.lower():
            choices.append(app_commands.Choice(name=name, value=entry[0]))
    return choices[:25]


async def font_autocomplete(interaction: discord.Interaction, current: str):
    """Offers the font presets."""
    return [
        app_commands.Choice(
            name=font if font == "Default" else f"{font} (Elite Track)", value=font
        )
        for font in FONT_PRESETS
        if current.lower() in font.lower()
    ][:25]


async def frame_autocomplete(interaction: discord.Interaction, current: str):
    """Offers the profile frames the member owns."""
    cosmetics = await get_cosmetics(
        interaction.client.pool, interaction.guild.id, interaction.user.id
    )
    return [
        app_commands.Choice(name=frame_label(frame), value=frame)
        for frame in (list(cosmetics["frames"]) if cosmetics else [])
        if current.lower() in frame_label(frame).lower()
    ][:25]


async def all_frames_autocomplete(interaction: discord.Interaction, current: str):
    """Offers every profile frame file there is, by name."""
    if not os.path.exists(FRAMES_DIRECTORY):
        return []
    choices = [
        app_commands.Choice(name=frame_label(file), value=file)
        for file in os.listdir(FRAMES_DIRECTORY)
        if not file.startswith(".")
        and not os.path.isdir(os.path.join(FRAMES_DIRECTORY, file))
        and current.lower() in file.lower()
    ]
    return sorted(choices, key=lambda choice: choice.name.lower())[:25]


class ConfirmCustomizationView(discord.ui.View):
    """Confirm and Cancel under a preview; the uploads wait in temporary files until then."""

    def __init__(
        self,
        user_id,
        guild_id,
        static_bg_provided=False,
        animated_bg_path=None,
        profile_frame=None,
        font_name=None,
    ):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.guild_id = guild_id
        self.static_bg_provided = static_bg_provided
        self.animated_bg_path = animated_bg_path
        self.profile_frame = profile_frame
        self.font_name = font_name

    def discard(self):
        """Deletes the uploads that were waiting."""
        if self.static_bg_provided:
            remove(f"{INVENTORY_BG_PATH}/{self.user_id}-temp.png")
        if self.animated_bg_path:
            remove(self.animated_bg_path)

    async def on_timeout(self) -> None:
        self.discard()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        uid = interaction.user.id
        if uid != self.user_id:
            return await interaction.response.send_message(
                f"{NO_EMOTE} You can't confirm this customization!", ephemeral=True
            )
        if self.static_bg_provided:
            remove(f"{INVENTORY_BG_PATH}/{uid}.png")
            try:
                os.rename(
                    f"{INVENTORY_BG_PATH}/{uid}-temp.png",
                    f"{INVENTORY_BG_PATH}/{uid}.png",
                )
            except Exception as e:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Failed to save background: {e}", ephemeral=True
                )

        pool = interaction.client.pool
        current = await get_cosmetics(pool, self.guild_id, uid) or {}
        animated = current.get("selected_animated_background")
        if self.static_bg_provided:
            animated = None
        elif self.animated_bg_path:
            animated = f"{uid}.gif"
            remove(f"{ANIMATED_INVENTORY_BG_PATH}/{animated}")
            try:
                os.rename(
                    self.animated_bg_path, f"{ANIMATED_INVENTORY_BG_PATH}/{animated}"
                )
            except Exception as e:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Failed to save animated background: {e}",
                    ephemeral=True,
                )
        await upsert_cosmetics(
            pool,
            self.guild_id,
            uid,
            selected_animated_background=animated,
            selected_profile_frame=self.profile_frame
            or current.get("selected_profile_frame"),
            selected_font=self.font_name or current.get("selected_font"),
        )

        changes = []
        if self.static_bg_provided:
            changes.append("static background")
        if self.animated_bg_path:
            changes.append("animated background upload")
        if self.profile_frame:
            changes.append(f"profile frame to **{self.profile_frame.split('.')[0]}**")
        if self.font_name:
            changes.append(f"font to **{self.font_name}**")
        description = (
            f"{interaction.user.mention}, your customization has been confirmed!"
        )
        if changes:
            description += "\n\nChanges applied:\n- " + "\n- ".join(changes)
        else:
            description += " (No visual changes were made)"
        await update_quest(
            self.user_id,
            self.guild_id,
            interaction.channel.id,
            {"customize_profile": 1},
            interaction.client,
        )
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"{YES_EMOTE} Customization Complete",
                description=description,
                color=discord.Color.green(),
            ),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                f"{NO_EMOTE} You can't cancel this customization!", ephemeral=True
            )
        self.discard()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"{NO_EMOTE} Customization Cancelled",
                description=f"{interaction.user.mention}, no changes were applied.",
                color=discord.Color.red(),
            ),
            view=None,
        )


class Customize(commands.Cog):
    """The /customize and /preview commands."""

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
        say = interaction.followup.send
        instant = (custom_accent_color, profile_title, pin_inventory, profile_font)
        previewed = (background, animated_background, profile_frame, profile_font)
        if not any(instant + previewed):
            return await say(
                f"{NO_EMOTE} Please specify at least one customization option!"
            )
        if background and animated_background:
            return await say(
                f"{NO_EMOTE} You can't set both a static and animated background at the same time!"
            )
        cosmetics = await cosmetics_of(interaction)

        if profile_font:
            if profile_font not in FONT_PRESETS:
                return await say(
                    f"{NO_EMOTE} Invalid font preset. Choose one of the available presets."
                )
            if profile_font != "Default" and not (
                await elite(interaction) and cosmetics.get("selected_font_unlocked")
            ):
                return await say(
                    f"{NO_EMOTE} You have not unlocked **custom font preset** on the Elite Track!"
                )

        if custom_accent_color:
            if not (cosmetics["embed_color"] if cosmetics else False):
                return await say(
                    f"{NO_EMOTE} You have not unlocked **custom accent color** on the Elite Track!"
                )
            hex_color = custom_accent_color.strip().lstrip("#")
            if len(hex_color) != 6:
                return await say(
                    f"{NO_EMOTE} Invalid hex format! Use 6-digit hex code (e.g. #ff0000)"
                )
            try:
                color = int(hex_color, 16)
            except ValueError:
                return await say(
                    f"{NO_EMOTE} Invalid hex characters! Use 0-9 and A-F only"
                )
            await upsert_cosmetics(
                interaction.client.pool,
                interaction.guild.id,
                interaction.user.id,
                selected_embed_color_hex=hex_color,
            )
            await say(
                embed=discord.Embed(
                    title=f"{YES_EMOTE} Custom Accent Color Updated",
                    description=f"{interaction.user.mention}, your accent color has been set to `#{hex_color}`!",
                    color=color,
                )
            )

        if profile_title:
            await self.process_title(interaction, profile_title, cosmetics)
        pinned = False
        if pin_inventory:
            pinned = await self.process_pin_item(interaction, pin_inventory)
        if any(previewed):
            await self.process_visual_customizations(
                interaction,
                background,
                animated_background,
                profile_frame,
                pinned,
                profile_font,
            )
        if any(instant):
            await update_quest(
                interaction.user.id,
                interaction.guild.id,
                interaction.channel.id,
                {"customize_profile": 1},
                interaction.client,
            )

    async def process_pin_item(
        self, interaction: discord.Interaction, pin_inventory: str
    ):
        """Pins an inventory item, or unpins the current one; False when the item is not owned."""
        who = (interaction.client.pool, interaction.user.id, interaction.guild.id)
        if pin_inventory == "unpin":
            unpinned = await get_pinned_item(*who)
            if unpinned is None:
                embed = discord.Embed(
                    title=f"{HMM_EMOTE} No Pinned Item",
                    description=f"{interaction.user.mention}, you don't have any items pinned!",
                    color=discord.Color.blue(),
                )
            else:
                await unpin_all_items(*who)
                embed = discord.Embed(
                    title="📌 Item Unpinned",
                    description=f"**{mention(unpinned)}** is now unpinned!",
                    color=discord.Color.green(),
                )
            await interaction.followup.send(embed=embed)
            return True
        inventory = await get_user_inventory(*who)
        if not any(item[0] == str(pin_inventory) for item in inventory):
            await interaction.followup.send(
                embed=discord.Embed(
                    title=f"{NO_EMOTE} Invalid Item",
                    description=f"**{mention(pin_inventory)}** isn't in your inventory!",
                    color=discord.Color.red(),
                )
            )
            return False
        await pin_item(*who, pin_inventory)
        await interaction.followup.send(
            embed=discord.Embed(
                title="📌 Item Pinned",
                description=f"**{mention(pin_inventory)}** is now pinned! It will appear alongside your name every time you win a game.",
                color=discord.Color.green(),
            )
        )
        return True

    async def process_title(
        self, interaction: discord.Interaction, title_value: str, cosmetics: dict
    ):
        """Unsets the title, picks an owned one, or sets a custom one on the Elite Track."""
        pool, gid, uid = (
            interaction.client.pool,
            interaction.guild.id,
            interaction.user.id,
        )
        titles = cosmetics["titles"] if cosmetics else []
        if title_value == "unset":
            chosen, custom = None, None
            message = "Your title has been unset."
        elif title_value in {entry[0] for entry in titles if len(entry) >= 2}:
            chosen, custom = title_value, None
            name = next(entry[1] for entry in titles if entry[0] == title_value)
            message = f"Title set to: **{name}**"
        elif cosmetics.get("selected_custom_title_unlocked") and await is_elite_active(
            pool, uid, gid
        ):
            chosen, custom = None, title_value.strip()
            if not custom:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Custom title cannot be empty!", ephemeral=True
                )
            message = f"Custom title set to: **{custom}**"
        else:
            return await interaction.followup.send(
                f"{NO_EMOTE} You cannot use custom titles, as you haven't unlocked them on the Elite Track. You can still select owned titles from the autocomplete.",
                ephemeral=True,
            )
        await upsert_cosmetics(
            pool, gid, uid, selected_title=chosen, selected_custom_title=custom
        )
        await interaction.followup.send(
            embed=discord.Embed(description=message, color=discord.Color.green()),
            ephemeral=True,
        )

    async def process_visual_customizations(
        self,
        interaction: discord.Interaction,
        background: discord.Attachment,
        animated_background: discord.Attachment,
        profile_frame: str,
        pin_processed: bool,
        font: str = None,
    ):
        """Draws a preview of the new background, frame or font and asks to confirm it."""
        uid = interaction.user.id

        async def refuse(text):
            await interaction.followup.send(f"{NO_EMOTE} {text}", ephemeral=True)

        # Read again: the accent colour may have been saved a moment ago.
        cosmetics = await cosmetics_of(interaction)
        elite_active = await elite(interaction)

        if animated_background:
            if not (
                elite_active and cosmetics.get("selected_animated_background_unlocked")
            ):
                return await refuse(
                    "You have not unlocked **custom animated GIF background** on the Elite Track!"
                )
            if not animated_background.filename.lower().endswith(".gif"):
                return await refuse(
                    "Animated backgrounds must be uploaded as GIF files!"
                )
            animated = f"{ANIMATED_INVENTORY_BG_PATH}/{uid}-temp.gif"
            await process_animated_background_upload(animated_background, animated)
        else:
            stored = (
                cosmetics.get("selected_animated_background") if elite_active else None
            )
            animated = resolve_animated_background_path(stored)
            if stored and animated is None:
                return await refuse("Animated background file not found!")

        if profile_frame:
            name = profile_frame.split(".")[0]
            if profile_frame not in list(cosmetics.get("frames", [])):
                return await refuse(f"You don't own **{name}** profile frame!")
            if not os.path.exists(f"{FRAMES_DIRECTORY}/{profile_frame}"):
                return await refuse(f"File for **{name}** not found!")

        static = None
        if background:
            static = f"{INVENTORY_BG_PATH}/{uid}-temp.png"
            try:
                await background.save(static)
                save_static_background(static)
            except Exception as e:
                return await interaction.followup.send(
                    f"{NO_EMOTE} Background processing failed: {e}"
                )
        saved = f"{INVENTORY_BG_PATH}/{uid}.png"
        filename = await createProfileCard(
            interaction.user,
            *SAMPLE,
            bg=static
            or animated
            or (saved if os.path.exists(saved) else DEFAULT_BG_PATH),
            profile_frame=profile_frame
            or cosmetics.get("selected_profile_frame")
            or None,
            accent_color_hex=(
                cosmetics.get("selected_embed_color_hex") if elite_active else None
            ),
            font_name=font
            or (cosmetics.get("selected_font") if elite_active else None),
        )
        preview = await self.bot.get_channel(PREVIEW_CHANNEL).send(
            file=discord.File(filename)
        )
        embed = discord.Embed(
            title="🎨 Customization Preview",
            description=f"Final preview for {interaction.user.mention}'s customization:",
            color=discord.Color.gold(),
        ).set_image(url=preview.attachments[0].proxy_url)
        if pin_processed:
            embed.set_footer(text="Note: Your pin changes were already applied")
        await interaction.followup.send(
            embed=embed,
            view=ConfirmCustomizationView(
                user_id=uid,
                guild_id=interaction.guild.id,
                static_bg_provided=bool(background),
                animated_bg_path=animated if animated_background else None,
                profile_frame=profile_frame,
                font_name=font,
            ),
        )

    @app_commands.command(
        name="preview", description="Preview a profile frame on your profile card"
    )
    @app_commands.describe(
        profile_frame="The profile frame to preview (e.g., 'Golden Ring.png')"
    )
    @app_commands.autocomplete(profile_frame=all_frames_autocomplete)
    async def preview(
        self, interaction: discord.Interaction, profile_frame: str
    ) -> None:
        await interaction.response.defer(thinking=True)
        name = profile_frame.split(".")[0]
        if not os.path.exists(f"{FRAMES_DIRECTORY}/{profile_frame}"):
            return await interaction.followup.send(
                f"{NO_EMOTE} Profile frame **{name}** not found!"
            )
        cosmetics = await cosmetics_of(interaction)
        elite_active = await elite(interaction)
        background = f"{INVENTORY_BG_PATH}/{interaction.user.id}.png"
        if not os.path.exists(background):
            stored = (
                cosmetics.get("selected_animated_background") if elite_active else None
            )
            background = f"{ANIMATED_INVENTORY_BG_PATH}/{stored}.gif"
            if not stored or not os.path.exists(background):
                background = DEFAULT_BG_PATH
        try:
            filename = await createProfileCard(
                interaction.user, *SAMPLE, bg=background, profile_frame=profile_frame
            )
            channel = self.bot.get_channel(PREVIEW_CHANNEL)
            if channel:
                sent = await channel.send(file=discord.File(filename))
                kind = (
                    "(Animated)"
                    if profile_frame.lower().endswith(".gif")
                    else "(Static)"
                )
                embed = discord.Embed(
                    title="🖼️ Profile Frame Preview",
                    description=f"Preview of **{name} {kind}** on {interaction.user.mention}'s profile card",
                    color=discord.Color.blue(),
                )
                embed.set_image(url=sent.attachments[0].proxy_url)
                embed.set_footer(text="This is just a preview with placeholder values")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"{NO_EMOTE} Preview of **{name}** frame:",
                    file=discord.File(filename),
                )
            remove(filename)
        except Exception as e:
            await interaction.followup.send(
                f"{NO_EMOTE} Failed to generate preview: {e}"
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Customize(bot))
