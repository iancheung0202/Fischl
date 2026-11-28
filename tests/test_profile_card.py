"""The profile card image of /mora and /customize."""

import asyncio
import io
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image, ImageFont

from commands.Events import createProfileCard as cards

FONT = "web/static/world/ja-jp.ttf"
NUMBERS = ("15,702,790", 3, "0", "N/A", "17,441,950.5", 12, "40", None)
RED, BLUE, GREEN = (200, 0, 0, 255), (0, 0, 200, 255), (0, 200, 0, 255)


def picture(path, color, size=(720, 256)):
    """Saves a one-colour picture and gives its path."""
    Image.new("RGBA", size, color).save(path)
    return str(path)


def moving(path, colors, size=(720, 256), durations=(40, 70, 90)):
    """Saves a GIF with one frame per colour and gives its path."""
    frames = [Image.new("RGB", size, color[:3]) for color in colors]
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=list(durations[: len(frames)]),
        loop=0,
    )
    return str(path)


def member(avatar=True):
    """A member whose avatar is a green square, or who has none."""
    data = io.BytesIO()
    Image.new("RGBA", (128, 128), GREEN).save(data, format="PNG")
    asset = SimpleNamespace(read=AsyncMock(return_value=data.getvalue()))
    asset.with_static_format = lambda kind: asset
    asset.with_size = lambda size: asset
    return SimpleNamespace(
        avatar=asset if avatar else None, display_name="Fischl", name="fischl"
    )


@pytest.fixture
def art(tmp_path, monkeypatch):
    """Stand-in assets: a red default background, a frame folder, four icons and a real font."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets").mkdir()
    (tmp_path / "frames").mkdir()
    real = ImageFont.truetype
    font = str(Path(__file__).parent.parent / FONT)
    monkeypatch.setattr(
        cards.ImageFont, "truetype", lambda path, size: real(font, size)
    )
    monkeypatch.setattr(
        cards, "DEFAULT_BG_PATH", picture(tmp_path / "default.png", RED)
    )
    monkeypatch.setattr(cards, "FRAMES_DIRECTORY", str(tmp_path / "frames"))
    monkeypatch.setattr(cards, "FONT_PATH", font)
    picture(tmp_path / "assets" / "DefaultIcon.png", BLUE, (64, 64))
    for name in cards.CURRENCY_EMOTE_ASSETS:
        picture(tmp_path / "assets" / f"{name}.png", (255, 255, 0, 255), (128, 128))
    cards.currency_icon.cache_clear()
    yield tmp_path
    cards.currency_icon.cache_clear()


async def card(user=None, **look):
    """Draws a card and gives it with its opened image."""
    made = await cards.createProfileCard(user or member(), *NUMBERS, **look)
    assert made.tell() == 0
    return made, Image.open(made)


async def test_a_still_card_is_a_png_in_memory_on_the_default_background(art):
    made, image = await card(bg=cards.DEFAULT_BG_PATH)
    assert made.name == "mora.png"
    assert image.format == "PNG" and image.size == (720, 256)
    assert image.getpixel((700, 5)) == RED
    assert image.getpixel((104, 94)) == GREEN
    assert image.getpixel((41, 31)) == RED  # the avatar is cut to a circle
    assert not list(art.glob("assets/mora*"))


async def test_a_member_without_an_avatar_gets_the_default_icon(art):
    _, image = await card(member(avatar=False))
    assert image.getpixel((104, 94)) == BLUE


async def test_an_unreadable_or_missing_background_falls_back_to_the_default(art):
    (art / "broken.png").write_bytes(b"not a picture")
    for bg in (str(art / "broken.png"), str(art / "gone.gif"), None):
        made, image = await card(bg=bg)
        assert made.name == "mora.png" and image.getpixel((700, 5)) == RED


async def test_a_gif_that_does_not_move_gives_a_still_card(art):
    (art / "broken.gif").write_bytes(b"not a picture")
    picture(art / "one.gif", GREEN, (720, 256))
    Image.new("RGB", (720, 256), GREEN).save(
        art / "same.gif",
        save_all=True,
        append_images=[Image.new("RGB", (720, 256), GREEN)],
    )
    for bg, color in (("broken.gif", RED), ("one.gif", GREEN), ("same.gif", GREEN)):
        made, image = await card(bg=str(art / bg))
        assert made.name == "mora.png" and image.format == "PNG"
        assert image.getpixel((700, 5)) == color


async def test_a_frame_is_centred_on_the_avatar(art):
    picture(art / "frames" / "Ring.png", BLUE, (140, 140))
    _, image = await card(profile_frame="Ring.png")
    assert image.getpixel((34, 24)) == BLUE and image.getpixel((173, 163)) == BLUE
    assert image.getpixel((33, 23)) == RED and image.getpixel((174, 164)) == RED


async def test_a_frame_that_was_deleted_is_left_out(art):
    made, image = await card(profile_frame="Gone.png")
    assert made.name == "mora.png" and image.getpixel((104, 94)) == GREEN


async def test_a_moving_background_gives_a_gif_with_its_frames_and_timing(art):
    bg = moving(art / "bg.gif", [RED, BLUE, GREEN])
    made, image = await card(bg=bg)
    assert made.name == "mora.gif" and image.format == "GIF"
    assert image.n_frames == 3 and image.info["loop"] == 0
    timing = []
    for index in range(3):
        image.seek(index)
        timing.append(image.info["duration"])
    assert timing == [40, 70, 90]


async def test_a_moving_frame_on_a_still_background_sets_the_frames(art):
    moving(art / "frames" / "Jade.gif", [RED, BLUE], (140, 140))
    made, image = await card(profile_frame="Jade.gif")
    assert made.name == "mora.gif" and image.n_frames == 2


async def test_a_moving_frame_repeats_over_a_longer_moving_background(art):
    bg = moving(art / "bg.gif", [RED, BLUE, GREEN])
    moving(art / "frames" / "Jade.gif", [RED, BLUE], (140, 140))
    drawn = []
    real = cards.draw_card

    def spy(frame, avatar, ring, *rest):
        drawn.append(ring.getpixel((0, 0))[:3])
        return real(frame, avatar, ring, *rest)

    cards.draw_card, old = spy, cards.draw_card
    try:
        _, image = await card(bg=bg, profile_frame="Jade.gif")
    finally:
        cards.draw_card = old
    assert image.n_frames == 3 and drawn[0] == drawn[2] != drawn[1]


async def test_the_accent_colour_tints_the_names_and_a_bad_one_is_ignored(art):
    plain = (await card())[0].getvalue()
    assert (await card(accent_color_hex="zzzzzz"))[0].getvalue() == plain
    assert (await card(accent_color_hex="#00ff00"))[0].getvalue() != plain
    assert (await card(accent_color_hex="00ff00"))[0].getvalue() == (
        await card(accent_color_hex="#00ff00")
    )[0].getvalue()


async def test_drawing_runs_off_the_event_loop_and_cards_do_not_share_a_file(art):
    threads = []
    real = cards.render

    def spy(*args):
        threads.append(threading.current_thread())
        return real(*args)

    cards.render, old = spy, cards.render
    try:
        blue = picture(art / "blue.png", BLUE)
        first, second = await asyncio.gather(card(), card(bg=blue))
    finally:
        cards.render = old
    assert all(thread is not threading.main_thread() for thread in threads)
    assert first[1].getpixel((700, 5)) == RED and second[1].getpixel((700, 5)) == BLUE


async def test_ranks_and_amounts_are_written_as_before(art, monkeypatch):
    written = []
    real = cards.ImageDraw.ImageDraw.text

    def text(self, at, words, **how):
        written.append(words)
        return real(self, at, words, **how)

    monkeypatch.setattr(cards.ImageDraw.ImageDraw, "text", text)
    await card()
    assert written == [
        "Fischl",
        "fischl",
        "15,702,790",
        "#3",
        "0",
        "N/A",
        "17,441,950",
        "#12",
        "40",
        "N/A",
    ]


def test_text_colours():
    assert cards.resolve_text_color((1, 2, 3), None, 0.5) == (1, 2, 3)
    assert cards.resolve_text_color((200, 200, 200), (100, 0, 50), 0.5) == (150, 100, 125)  # fmt: skip
    assert cards.resolve_text_color((100, 100, 100), (0, 0, 0), 0.5) == (101, 101, 101)
    assert cards.accent_of(None) is None and cards.accent_of("nope") is None
    assert cards.accent_of("#0000ff") == cards.accent_of("0000ff") == (0, 0, 255)


def test_fonts_fall_back_to_the_default(art, monkeypatch):
    monkeypatch.setattr(
        cards, "FONT_PRESETS", {"Real": cards.FONT_PATH, "Gone": "no.ttf"}
    )
    for name in (None, "", "Real", "Gone", "Unknown"):
        assert cards.resolve_font_path(name) == cards.FONT_PATH


async def test_an_icon_already_on_disk_is_not_downloaded(art, monkeypatch):
    monkeypatch.setattr(cards.aiohttp, "ClientSession", None)
    assert await cards.ensure_emote_asset("<:mora:123>", "guild_mora") == (
        "assets/guild_mora.png"
    )


async def test_an_emote_that_cannot_be_read_gives_no_icon(art, capsys):
    assert await cards.ensure_emote_asset("mora", "new") is None
    assert await cards.ensure_emote_asset(None, "new") is None
    assert "Could not parse emote id" in capsys.readouterr().out


class Web:
    """A stand-in for aiohttp that answers every request the same way."""

    def __init__(self, status, data=b""):
        self.status, self.data, self.asked = status, data, []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error):
        return False

    def get(self, url):
        self.asked.append(url)
        return self

    async def read(self):
        return self.data


async def test_a_missing_icon_is_downloaded_once_as_a_png(art, monkeypatch):
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(data, format="PNG")
    web = Web(200, data.getvalue())
    monkeypatch.setattr(cards.aiohttp, "ClientSession", web)
    assert await cards.ensure_emote_asset("<a:coin:987>", "new") == "assets/new.png"
    assert await cards.ensure_emote_asset("<a:coin:987>", "new") == "assets/new.png"
    assert web.asked == ["https://cdn.discordapp.com/emojis/987.png?size=128"]
    assert Image.open("assets/new.png").mode == "RGBA"


async def test_a_failed_icon_download_draws_the_card_without_it(art, monkeypatch):
    (art / "assets" / "guild_mora.png").unlink()
    monkeypatch.setattr(cards.aiohttp, "ClientSession", Web(404))
    _, image = await card()
    assert image.getpixel((40, 180)) == RED and image.getpixel((403, 180))[:3] == (255, 255, 0)  # fmt: skip
    monkeypatch.setattr(cards.aiohttp, "ClientSession", Web(200, b"junk"))
    assert await cards.ensure_emote_asset("<:m:1>", "guild_mora") is None
