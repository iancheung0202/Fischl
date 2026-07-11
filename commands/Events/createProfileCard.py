import io
import os
import re

import aiohttp
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageSequence

from commands.Events.config import (
    FRAMES_DIRECTORY,
    DEFAULT_BG_PATH,
    FONT_PATH,
    FONT_PRESETS,
    PROFILE_CARD_PATH,
    GUILD_MORA_EMOTE,
    GLOBAL_MORA_EMOTE,
    GUILD_SIGIL_EMOTE,
    GLOBAL_SIGIL_EMOTE,
)

# Matches Discord's custom emote format: <:name:id> or <a:name:id>
DISCORD_EMOTE_PATTERN = re.compile(r"<(a?):(\w+):(\d+)>")

ASSETS_DIRECTORY = "assets"

# Maps the on-disk asset name to the emote constant it's derived from, so the
# emote id is always parsed live from config rather than hardcoded here.
CURRENCY_EMOTE_ASSETS = {
    "guild_mora": GUILD_MORA_EMOTE,
    "guild_sigils": GUILD_SIGIL_EMOTE,
    "global_mora": GLOBAL_MORA_EMOTE,
    "global_sigils": GLOBAL_SIGIL_EMOTE,
}


async def ensure_emote_asset(emote_str: str, asset_name: str) -> str | None:
    """Make sure the image for a Discord emote exists at assets/{asset_name}.png,
    downloading it from Discord's CDN if needed. The emote id is parsed directly
    out of the emote string (as configured), never hardcoded.

    We always request the .png render (Discord's CDN returns a clean static
    frame with proper alpha even for animated emotes) rather than decoding a
    .gif ourselves, since manually grabbing frame 0 of a gif can leave a black
    matte where the transparency wasn't preserved correctly.
    """
    asset_path = os.path.join(ASSETS_DIRECTORY, f"{asset_name}.png")
    if os.path.exists(asset_path):
        return asset_path

    match = DISCORD_EMOTE_PATTERN.search(emote_str or "")
    if not match:
        print(f"Could not parse emote id from {emote_str!r} for asset {asset_name}")
        return None

    _animated, _name, emote_id = match.groups()
    url = f"https://cdn.discordapp.com/emojis/{emote_id}.png?size=128"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"Failed to download emote asset {asset_name} from {url}: HTTP {resp.status}")
                    return None
                data = await resp.read()

        os.makedirs(ASSETS_DIRECTORY, exist_ok=True)
        with Image.open(io.BytesIO(data)) as im:
            im.convert("RGBA").save(asset_path)
        return asset_path
    except Exception as e:
        print(f"Error downloading emote asset {asset_name}: {e}")
        return None


async def ensure_all_currency_assets() -> dict[str, str | None]:
    return {
        asset_name: await ensure_emote_asset(emote_str, asset_name)
        for asset_name, emote_str in CURRENCY_EMOTE_ASSETS.items()
    }


def load_currency_icon(path: str | None, size: int):
    # No circular mask here: these are badge/icon glyphs (already shaped by
    # their own artwork), not avatars, so forcing a circular crop just clips
    # their corners and can expose a matte ring. Keep native alpha as-is.
    if not path or not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)


def resolve_font_path(font_name: str | None) -> str:
    if not font_name:
        return FONT_PATH
    font_path = FONT_PRESETS.get(font_name, FONT_PATH)
    return font_path if os.path.exists(font_path) else FONT_PATH

def resolve_text_color(base_color, accent_color, strength: float):
    if not accent_color:
        return base_color

    blended = tuple(
        int(base_color[index] * (1 - strength) + accent_color[index] * strength)
        for index in range(3)
    )

    if sum(blended) / 3 < 110:
        blended = tuple(int(blended[index] * 0.75 + 255 * 0.25) for index in range(3))

    return blended


# Currency panel layout: two columns (guild currencies on the left, global on
# the right), each with two stacked rows (mora, then sigils). Spans the full
# card width, stays fully transparent aside from the small rank pill.
GRID_ICON_SIZE = 34
GRID_MARGIN_X = 34
GRID_COLUMN_GAP = 36
GRID_BOTTOM_PADDING = 13
GRID_ROW_HEIGHT = 36

PILL_TEXT_COLOR = (205, 205, 210)  # muted gray-white so it doesn't compete with the value text
PILL_PAD_X = 9
PILL_PAD_Y = 4
PILL_GAP = 10  # space between the value text and the rank pill
PILL_BLUR_RADIUS = 6
PILL_TINT_COLOR = (20, 20, 24)  # dark blackish-gray tint over the blurred glass
PILL_TINT_ALPHA = 190  # high opacity so the pill actually reads against busy art
PILL_TEXT_SIZE_SHRINK = 6  # how much smaller the pill's own text renders vs. the sizing font


def format_currency_value(value: str) -> str:
    # Mirrors the original convention of dropping anything after a "."
    return str(value).split(".")[0]


def measure_pill_size(text, sizing_font):
    # Pill box size is based on the value font size so it stays visually
    # consistent, even though the text drawn inside it uses a smaller font.
    bbox = sizing_font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    return text_w + PILL_PAD_X * 2, text_h + PILL_PAD_Y * 2


def draw_glass_pill(card_image, draw, x, y, w, h, text, text_font):
    """Glassmorphism pill: no border, just a blurred sample of whatever's
    behind it (clipped to a rounded-rect) with a dark translucent tint on top
    for contrast, and small centered text.
    """
    x0, y0 = max(int(x), 0), max(int(y), 0)
    x1, y1 = min(int(x + w), card_image.width), min(int(y + h), card_image.height)

    if x1 > x0 and y1 > y0:
        region = card_image.crop((x0, y0, x1, y1))
        blurred = region.filter(ImageFilter.GaussianBlur(PILL_BLUR_RADIUS))
        rounded_mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(rounded_mask).rounded_rectangle([0, 0, x1 - x0, y1 - y0], radius=h / 2, fill=255)
        card_image.paste(blurred, (x0, y0), rounded_mask)

        tint = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ImageDraw.Draw(tint).rounded_rectangle(
            [0, 0, x1 - x0, y1 - y0], radius=h / 2, fill=(*PILL_TINT_COLOR, PILL_TINT_ALPHA)
        )
        card_image.paste(tint, (x0, y0), tint)

    text_bbox = text_font.getbbox(text)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    text_x = x + (w - text_w) / 2 - text_bbox[0]
    text_y = y + (h - text_h) / 2 - text_bbox[1]
    draw.text((text_x, text_y), text, font=text_font, fill=PILL_TEXT_COLOR)


def draw_currency_panel(card_image, draw, guild_entries, global_entries, value_font, pill_text_font, accent_color):
    """Draws the currency panel as two columns spanning the full card width:

        [icon] 15,702,790  #3      [icon] 17,441,950  #3
        [icon] 0  N/A               [icon] 0  N/A

    guild_entries / global_entries: each a 2-item list of (icon, value, rank),
    mora first then sigils.
    """
    width, height = card_image.size

    panel_height = GRID_ROW_HEIGHT * 2
    top_y = height - panel_height - GRID_BOTTOM_PADDING

    col_width = (width - GRID_MARGIN_X * 2 - GRID_COLUMN_GAP) / 2
    columns = [
        (GRID_MARGIN_X, guild_entries),
        (GRID_MARGIN_X + col_width + GRID_COLUMN_GAP, global_entries),
    ]

    value_color = resolve_text_color((233, 253, 255), accent_color, 0.4)

    for col_x, entries in columns:
        for row_index, (icon, value, rank) in enumerate(entries):
            row_y = top_y + row_index * GRID_ROW_HEIGHT
            icon_y = row_y + (GRID_ROW_HEIGHT - GRID_ICON_SIZE) / 2
            if icon:
                card_image.paste(icon, (int(col_x), int(icon_y)), icon)

            value_text = format_currency_value(value)
            text_x = col_x + GRID_ICON_SIZE + 12
            value_bbox = value_font.getbbox(value_text)
            value_w = value_bbox[2] - value_bbox[0]
            value_h = value_bbox[3] - value_bbox[1]
            text_y = row_y + (GRID_ROW_HEIGHT - value_h) / 2 - value_bbox[1]
            draw.text((text_x, text_y), value_text, font=value_font, fill=value_color)

            rank_display = f"#{rank}" if rank not in (None, "N/A") else "N/A"
            pill_w, pill_h = measure_pill_size(rank_display, value_font)
            pill_x = text_x + value_w + PILL_GAP
            pill_y = row_y + (GRID_ROW_HEIGHT - pill_h) / 2
            draw_glass_pill(card_image, draw, pill_x, pill_y, pill_w, pill_h, rank_display, pill_text_font)


async def createProfileCard(
    user,
    guild_mora: str,
    guild_rank,
    guild_sigils: str,
    guild_sigils_rank,
    global_mora: str,
    global_rank,
    global_sigils: str,
    global_sigils_rank,
    bg: str = DEFAULT_BG_PATH,
    filename: str = PROFILE_CARD_PATH,
    profile_frame: str = None,
    accent_color_hex: str = None,
    font_name: str = None
):
    # Avatar
    if user.avatar is None:
        im_avatar = Image.open("assets/DefaultIcon.png").convert("RGBA").resize((128, 128))
    else:
        avatar_bytes = await user.avatar.with_static_format("png").with_size(128).read()
        im_avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    mask = Image.new("L", im_avatar.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0) + im_avatar.size, fill=255)
    im_avatar.putalpha(mask)

    # Fonts
    resolved_font = resolve_font_path(font_name)
    font_display = ImageFont.truetype(resolved_font, 45)
    font_username = ImageFont.truetype(resolved_font, 25)
    font_grid_value = ImageFont.truetype(resolved_font, 22)
    font_grid_pill = ImageFont.truetype(resolved_font, 22 - PILL_TEXT_SIZE_SHRINK)

    accent_color = None
    if accent_color_hex:
        try:
            accent_color = ImageColor.getrgb(f"#{accent_color_hex.lstrip('#')}")
        except ValueError:
            accent_color = None

    # Currency icons (downloaded from the configured Discord emotes on first use)
    currency_asset_paths = await ensure_all_currency_assets()
    guild_mora_icon = load_currency_icon(currency_asset_paths.get("guild_mora"), GRID_ICON_SIZE)
    guild_sigils_icon = load_currency_icon(currency_asset_paths.get("guild_sigils"), GRID_ICON_SIZE)
    global_mora_icon = load_currency_icon(currency_asset_paths.get("global_mora"), GRID_ICON_SIZE)
    global_sigils_icon = load_currency_icon(currency_asset_paths.get("global_sigils"), GRID_ICON_SIZE)

    guild_currency_entries = [
        (guild_mora_icon, guild_mora, guild_rank),
        (guild_sigils_icon, guild_sigils, guild_sigils_rank),
    ]
    global_currency_entries = [
        (global_mora_icon, global_mora, global_rank),
        (global_sigils_icon, global_sigils, global_sigils_rank),
    ]
    
    # Helper function for animated images
    def load_image_frames(path):
        if not os.path.exists(path):
            return None, None, None
        try:
            im = Image.open(path)
            frames = []
            durations = []
            disposals = []
            if path.lower().endswith('.gif'):
                for frame in ImageSequence.Iterator(im):
                    frames.append(frame.convert('RGBA'))
                    durations.append(frame.info.get('duration', 100))
                    disposals.append(frame.info.get('disposal', 2))
                return frames, durations, disposals
            else:
                return [im.convert('RGBA')], [100], [2]
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None, None, None

    bg_animated = bg and bg.lower().endswith('.gif') and os.path.exists(bg)
    frame_animated = profile_frame and profile_frame.lower().endswith('.gif') and os.path.exists(f"{FRAMES_DIRECTORY}/{profile_frame}")

    # Create an animated profile card
    if bg_animated or frame_animated:  
        bg_frames, bg_durations, bg_disposals = load_image_frames(bg) or ([Image.new('RGBA', (720, 256), (0, 0, 0, 255))], [100], [2])
        frame_path = f"{FRAMES_DIRECTORY}/{profile_frame}" if profile_frame else None
        frame_frames, frame_durations, frame_disposals = load_image_frames(frame_path) or ([None], [100], [2])
        
        if len(bg_frames) > 1:
            total_frames = len(bg_frames)
            durations = bg_durations
            disposals = bg_disposals
            if len(frame_frames) == 1:
                frame_frames = frame_frames * total_frames
            else:
                frame_frames = [frame_frames[i % len(frame_frames)] for i in range(total_frames)]
        else:
            total_frames = len(frame_frames)
            durations = frame_durations
            disposals = frame_disposals
            bg_frames = bg_frames * total_frames
        
        output_frames = []
        for i in range(total_frames):
            frame = bg_frames[i].copy()

            # Avatar
            frame.paste(im_avatar, (40, 30), im_avatar)

            # Profile frame
            if frame_frames[i]:
                frame_img = frame_frames[i]
                x = 40 + (128 - frame_img.width) // 2
                y = 30 + (128 - frame_img.height) // 2
                frame.paste(frame_img, (x, y), frame_img)

            # Draw text
            draw = ImageDraw.Draw(frame)
            draw.text((200, 45), user.display_name, font=font_display, fill=accent_color or (255, 255, 255))
            draw.text((200, 100), user.name, font=font_username, fill=resolve_text_color((225, 225, 225), accent_color, 0.5))
            draw_currency_panel(frame, draw, guild_currency_entries, global_currency_entries, font_grid_value, font_grid_pill, accent_color)

            output_frames.append(frame)
        
        # Save animated GIF
        if not filename.lower().endswith('.gif'):
            filename = filename.rsplit(".", 1)[0] + ".gif"

        output_frames[0].save(
            filename,
            save_all=True,
            append_images=output_frames[1:],
            duration=durations,
            loop=0,
            disposal=disposals,
            optimize=False,
        )
        return filename

    # Create a static profile card
    try:
        im_bg = Image.open(bg).convert("RGBA")
    except Exception:
        im_bg = Image.open(DEFAULT_BG_PATH).convert("RGBA")

    # Avatar
    im_bg.paste(im_avatar, (40, 30), im_avatar)
    im_profile_frame = Image.open(f"{FRAMES_DIRECTORY}/{profile_frame}").convert("RGBA") if profile_frame else None

    # Profile frame
    if im_profile_frame:
        frame_w, frame_h = im_profile_frame.size
        avatar_w, avatar_h = im_avatar.size
        center_x = 40 + avatar_w // 2
        center_y = 30 + avatar_h // 2
        paste_x = center_x - frame_w // 2
        paste_y = center_y - frame_h // 2
        im_bg.paste(im_profile_frame, (paste_x, paste_y), im_profile_frame)
        
    # Draw text
    draw = ImageDraw.Draw(im_bg)
    draw.text((200, 45), user.display_name, font=font_display, fill=accent_color or (255, 255, 255))
    draw.text((200, 100), user.name, font=font_username, fill=resolve_text_color((225, 225, 225), accent_color, 0.5))
    draw_currency_panel(im_bg, draw, guild_currency_entries, global_currency_entries, font_grid_value, font_grid_pill, accent_color)

    # Save static image
    im_bg.save(filename)
    return filename

async def setup(bot):
    pass