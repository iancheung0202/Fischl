import asyncio
import functools
import io
import os
import re

import aiohttp
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageSequence

from commands.Events.config import (
    DEFAULT_BG_PATH,
    FONT_PATH,
    FONT_PRESETS,
    FRAMES_DIRECTORY,
    GLOBAL_MORA_EMOTE,
    GLOBAL_SIGIL_EMOTE,
    GUILD_MORA_EMOTE,
    GUILD_SIGIL_EMOTE,
    PROFILE_CARD_PATH,
)

EMOTE = re.compile(r"<a?:\w+:(\d+)>")
ASSETS_DIRECTORY = "assets"
CARD_NAME = os.path.splitext(os.path.basename(PROFILE_CARD_PATH))[0]

# The four icons of the currency panel, in the order they are drawn: server column, then global.
CURRENCY_EMOTE_ASSETS = {
    "guild_mora": GUILD_MORA_EMOTE,
    "guild_sigils": GUILD_SIGIL_EMOTE,
    "global_mora": GLOBAL_MORA_EMOTE,
    "global_sigils": GLOBAL_SIGIL_EMOTE,
}

DRAW_LOCK = asyncio.Lock()  # one drawing at a time keeps memory flat
AVATAR_AT = (40, 30)
AVATAR_SIZE = 128
NAME_AT = (200, 45)
USERNAME_AT = (200, 100)
NAME_COLOR = (255, 255, 255)
USERNAME_COLOR = (225, 225, 225)
VALUE_COLOR = (233, 253, 255)
BLANK_SIZE = (720, 256)

# The currency panel: server on the left, global on the right, Mora above Sigils.
GRID_ICON_SIZE = 34
GRID_MARGIN_X = 34
GRID_COLUMN_GAP = 36
GRID_BOTTOM_PADDING = 13
GRID_ROW_HEIGHT = 36
GRID_TEXT_GAP = 12
GRID_FONT_SIZE = 22

# The rank pill: the card behind it, blurred, under a dark tint.
PILL_TEXT_COLOR = (205, 205, 210)
PILL_PAD_X = 9
PILL_PAD_Y = 4
PILL_GAP = 10
PILL_BLUR_RADIUS = 6
PILL_TINT_COLOR = (20, 20, 24)
PILL_TINT_ALPHA = 190
PILL_TEXT_SIZE_SHRINK = 6


async def ensure_emote_asset(emote_str: str, asset_name: str) -> str | None:
    """Gives the path of an emote's picture under assets/, downloading it from Discord the first time."""
    asset_path = os.path.join(ASSETS_DIRECTORY, f"{asset_name}.png")
    if os.path.exists(asset_path):
        return asset_path
    match = EMOTE.search(emote_str or "")
    if not match:
        print(f"Could not parse emote id from {emote_str!r} for asset {asset_name}")
        return None
    # The .png render has clean transparency even for animated emotes.
    url = f"https://cdn.discordapp.com/emojis/{match.group(1)}.png?size=128"
    try:
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            if resp.status != 200:
                print(
                    f"Failed to download emote asset {asset_name} from {url}: HTTP {resp.status}"
                )
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
    """Gives the picture path of each currency icon, by its name."""
    return {
        asset_name: await ensure_emote_asset(emote_str, asset_name)
        for asset_name, emote_str in CURRENCY_EMOTE_ASSETS.items()
    }


@functools.lru_cache(maxsize=None)
def currency_icon(path: str, size: int) -> Image.Image:
    """Gives a currency icon at the size it is drawn, read from disk once."""
    return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)


def load_currency_icon(path: str | None, size: int):
    """Gives a currency icon ready to paste, or None when its picture is missing."""
    if not path or not os.path.exists(path):
        return None
    return currency_icon(path, size)


def resolve_font_path(font_name: str | None) -> str:
    """Gives the font file of a preset, or the default font when the preset or its file is missing."""
    font_path = FONT_PRESETS.get(font_name, FONT_PATH) if font_name else FONT_PATH
    return font_path if os.path.exists(font_path) else FONT_PATH


def resolve_text_color(base_color, accent_color, strength: float):
    """Blends a text colour toward the accent colour, lightened when the result is too dark to read."""
    if not accent_color:
        return base_color
    blended = tuple(
        int(base_color[i] * (1 - strength) + accent_color[i] * strength)
        for i in range(3)
    )
    if sum(blended) / 3 < 110:
        blended = tuple(int(part * 0.75 + 255 * 0.25) for part in blended)
    return blended


def accent_of(accent_color_hex: str | None):
    """Gives the accent colour as RGB, or None for no colour or one that cannot be read."""
    if not accent_color_hex:
        return None
    try:
        return ImageColor.getrgb(f"#{accent_color_hex.lstrip('#')}")
    except ValueError:
        return None


def format_currency_value(value: str) -> str:
    """Gives an amount without anything after a decimal point."""
    return str(value).split(".")[0]


def text_size(font, text: str):
    """Gives the box of a text in a font and its width and height."""
    box = font.getbbox(text)
    return box, box[2] - box[0], box[3] - box[1]


def measure_pill_size(text, sizing_font):
    """Gives the width and height of a rank pill, sized by the value font so pills match the amounts."""
    _, text_w, text_h = text_size(sizing_font, text)
    return text_w + PILL_PAD_X * 2, text_h + PILL_PAD_Y * 2


def draw_glass_pill(card_image, draw, x, y, w, h, text, text_font):
    """Draws a rank pill: the card behind it blurred, a dark tint, and small centred text."""
    x0, y0 = max(int(x), 0), max(int(y), 0)
    x1, y1 = min(int(x + w), card_image.width), min(int(y + h), card_image.height)
    if x1 > x0 and y1 > y0:
        size, shape = (x1 - x0, y1 - y0), [0, 0, x1 - x0, y1 - y0]
        blurred = card_image.crop((x0, y0, x1, y1)).filter(
            ImageFilter.GaussianBlur(PILL_BLUR_RADIUS)
        )
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(shape, radius=h / 2, fill=255)
        card_image.paste(blurred, (x0, y0), mask)
        tint = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(tint).rounded_rectangle(
            shape, radius=h / 2, fill=(*PILL_TINT_COLOR, PILL_TINT_ALPHA)
        )
        card_image.paste(tint, (x0, y0), tint)
    box, text_w, text_h = text_size(text_font, text)
    at = (x + (w - text_w) / 2 - box[0], y + (h - text_h) / 2 - box[1])
    draw.text(at, text, font=text_font, fill=PILL_TEXT_COLOR)


def draw_currency_row(card_image, draw, x, y, entry, fonts, color):
    """Draws one row of the currency panel: icon, amount and rank pill."""
    icon, value, rank = entry
    value_font, pill_font = fonts
    if icon:
        at = (int(x), int(y + (GRID_ROW_HEIGHT - GRID_ICON_SIZE) / 2))
        card_image.paste(icon, at, icon)
    value_text = format_currency_value(value)
    text_x = x + GRID_ICON_SIZE + GRID_TEXT_GAP
    box, value_w, value_h = text_size(value_font, value_text)
    text_y = y + (GRID_ROW_HEIGHT - value_h) / 2 - box[1]
    draw.text((text_x, text_y), value_text, font=value_font, fill=color)
    rank_text = f"#{rank}" if rank not in (None, "N/A") else "N/A"
    pill_w, pill_h = measure_pill_size(rank_text, value_font)
    pill_at = (text_x + value_w + PILL_GAP, y + (GRID_ROW_HEIGHT - pill_h) / 2)
    draw_glass_pill(card_image, draw, *pill_at, pill_w, pill_h, rank_text, pill_font)


def draw_currency_panel(
    card_image,
    draw,
    guild_entries,
    global_entries,
    value_font,
    pill_text_font,
    accent_color,
):
    """Draws the two currency columns along the bottom of a card; each entry is (icon, amount, rank)."""
    width, height = card_image.size
    top_y = height - GRID_ROW_HEIGHT * 2 - GRID_BOTTOM_PADDING
    col_width = (width - GRID_MARGIN_X * 2 - GRID_COLUMN_GAP) / 2
    color = resolve_text_color(VALUE_COLOR, accent_color, 0.4)
    columns = (
        (GRID_MARGIN_X, guild_entries),
        (GRID_MARGIN_X + col_width + GRID_COLUMN_GAP, global_entries),
    )
    for col_x, entries in columns:
        for row, entry in enumerate(entries):
            row_y = top_y + row * GRID_ROW_HEIGHT
            draw_currency_row(
                card_image,
                draw,
                col_x,
                row_y,
                entry,
                (value_font, pill_text_font),
                color,
            )


def round_avatar(avatar_bytes: bytes | None) -> Image.Image:
    """Gives the member's avatar cut to a circle, or the default icon for a member without one."""
    if avatar_bytes is None:
        avatar = Image.open("assets/DefaultIcon.png").convert("RGBA")
        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
    else:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + avatar.size, fill=255)
    avatar.putalpha(mask)
    return avatar


def is_gif(path: str | None) -> bool:
    """Says whether a path names a GIF file that exists."""
    return bool(path) and path.lower().endswith(".gif") and os.path.exists(path)


def frames_of(path: str):
    """Gives every frame of an image with how long and how each frame is shown; a still image is one frame."""
    with Image.open(path) as image:
        if not path.lower().endswith(".gif"):
            return [image.convert("RGBA")], [100], [2]
        frames, durations, disposals = [], [], []
        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGBA"))
            durations.append(frame.info.get("duration", 100))
            disposals.append(frame.info.get("disposal", 2))
        return frames, durations, disposals


def background_frames(bg: str | None):
    """Gives the frames of a background, falling back to the default one when it cannot be read."""
    try:
        return frames_of(bg)
    except Exception:
        return frames_of(DEFAULT_BG_PATH)


def draw_card(frame, avatar, ring, names, entries, fonts, accent_color):
    """Draws the avatar, its frame, the two names and the currency panel onto one background frame."""
    frame.paste(avatar, AVATAR_AT, avatar)
    if ring:
        at = (
            AVATAR_AT[0] + (avatar.width - ring.width) // 2,
            AVATAR_AT[1] + (avatar.height - ring.height) // 2,
        )
        frame.paste(ring, at, ring)
    draw = ImageDraw.Draw(frame)
    display_font, username_font, value_font, pill_font = fonts
    draw.text(NAME_AT, names[0], font=display_font, fill=accent_color or NAME_COLOR)
    username_color = resolve_text_color(USERNAME_COLOR, accent_color, 0.5)
    draw.text(USERNAME_AT, names[1], font=username_font, fill=username_color)
    draw_currency_panel(frame, draw, *entries, value_font, pill_font, accent_color)
    return frame


def render(avatar_bytes, names, entries, bg, ring_path, accent_color, font_path):
    """Draws a whole card and gives it as a named in-memory PNG, or GIF when its frames differ."""
    fonts = tuple(
        ImageFont.truetype(font_path, size)
        for size in (45, 25, GRID_FONT_SIZE, GRID_FONT_SIZE - PILL_TEXT_SIZE_SHRINK)
    )
    avatar = round_avatar(avatar_bytes)
    backgrounds, durations, disposals = background_frames(bg)
    rings, ring_durations, ring_disposals = (
        frames_of(ring_path) if ring_path else ([None], [100], [2])
    )
    if len(backgrounds) == 1:
        durations, disposals = ring_durations, ring_disposals
    total = len(backgrounds) if len(backgrounds) > 1 else len(rings)
    cards = [
        draw_card(
            backgrounds[i % len(backgrounds)].copy(),
            avatar,
            rings[i % len(rings)],
            names,
            entries,
            fonts,
            accent_color,
        )
        for i in range(total)
    ]
    card = io.BytesIO()
    still = cards[0].tobytes()
    if len(cards) > 1 and any(other.tobytes() != still for other in cards[1:]):
        card.name = f"{CARD_NAME}.gif"
        cards[0].save(
            card,
            format="GIF",
            save_all=True,
            append_images=cards[1:],
            duration=durations,
            loop=0,
            disposal=disposals,
            optimize=False,
        )
    else:
        card.name = f"{CARD_NAME}.png"
        cards[0].save(card, format="PNG")
    card.seek(0)
    return card


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
    profile_frame: str = None,
    accent_color_hex: str = None,
    font_name: str = None,
) -> io.BytesIO:
    """Gives a member's profile card as a named in-memory image, drawn off the event loop."""
    avatar_bytes = None
    if user.avatar is not None:
        avatar_bytes = await user.avatar.with_static_format("png").with_size(128).read()
    paths = await ensure_all_currency_assets()
    icons = [load_currency_icon(path, GRID_ICON_SIZE) for path in paths.values()]
    amounts = (guild_mora, guild_sigils, global_mora, global_sigils)
    ranks = (guild_rank, guild_sigils_rank, global_rank, global_sigils_rank)
    rows = list(zip(icons, amounts, ranks))
    ring_path = f"{FRAMES_DIRECTORY}/{profile_frame}" if profile_frame else None
    async with DRAW_LOCK:
        return await asyncio.to_thread(
            render,
            avatar_bytes,
            (user.display_name, user.name),
            (rows[:2], rows[2:]),
            bg,
            ring_path if ring_path and os.path.exists(ring_path) else None,
            accent_of(accent_color_hex),
            resolve_font_path(font_name),
        )


async def setup(bot):
    pass
