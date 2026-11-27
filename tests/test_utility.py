import hashlib
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageFont

from commands.Utility import (
    color,
    database,
    emotes,
    invite,
    sendcodes,
    sendwebevent,
    text,
)

OWNER, IMAGE_CHANNEL = 692254240290242601, 1026968305208131645
YES, NO = "<:yes:1036811164891480194>", "<:no:1036810470860013639>"


def cog_of(module, bot=None):
    """Builds the one cog a module holds."""
    kinds = [
        found
        for found in vars(module).values()
        if isinstance(found, type)
        and issubclass(found, commands.Cog)
        and found.__module__ == module.__name__
    ]
    assert len(kinds) == 1
    return kinds[0](bot or MagicMock())


def command_of(cog, name):
    """Finds a cog's slash command by the name members type."""
    return next(found for found in cog.walk_app_commands() if found.name == name)


async def run(cog, name, *args, **kwargs):
    """Runs a slash command the way Discord would."""
    return await command_of(cog, name).callback(cog, *args, **kwargs)


def interaction(user=5, may_ping=True):
    found = MagicMock()
    found.user.id = user
    found.user.name = "amy"
    found.user.avatar.url = "https://cdn/amy.png"
    found.user.guild_permissions.mention_everyone = may_ping
    found.guild.name = "Mondstadt"
    found.guild.icon.url = "https://cdn/icon.png"
    found.response.send_message = AsyncMock()
    found.response.edit_message = AsyncMock()
    found.response.defer = AsyncMock()
    found.followup.send = AsyncMock()
    found.channel.send = AsyncMock()
    return found


def no_stamp(embed):
    """Gives an embed as a dict, after checking and dropping its timestamp."""
    found = embed.to_dict()
    assert found.pop("timestamp")
    return found


def buttons(view):
    return [
        (child.label, child.url, str(child.emoji), child.style)
        for child in view.children
    ]


def options(command):
    return {found.name: found.description for found in command.parameters}


GAMES = [
    ("Genshin Impact", "genshin"),
    ("Honkai: Star Rail", "hsr"),
    ("Zenless Zone Zero", "zzz"),
]


def game_choices(command):
    choices = next(
        found for found in command.parameters if found.name == "game"
    ).choices
    return [(found.name, found.value) for found in choices]


def game(index):
    return app_commands.Choice(name=GAMES[index][0], value=GAMES[index][1])


def attachment(found):
    """An uploaded picture, and the storage channel that hands back its link."""
    picture = MagicMock()
    picture.save = AsyncMock()
    stored = MagicMock()
    stored.attachments = [MagicMock(proxy_url="https://media/stored.png")]
    channel = MagicMock()
    channel.send = AsyncMock(return_value=stored)
    found.client.get_channel = MagicMock(return_value=channel)
    return picture, channel


@pytest.fixture
def no_files(monkeypatch):
    """Lets a command build a discord.File without a real file behind it."""
    monkeypatch.setattr(discord, "File", lambda *args, **kwargs: (args, kwargs))


# /invite


async def test_invite():
    bot = MagicMock()
    bot.user.id = 77
    cog, found = cog_of(invite, bot), interaction()
    said = command_of(cog, "invite")
    assert (said.name, said.description) == ("invite", "Invite the bot to your server")
    await run(cog, "invite", found)
    (), sent = found.response.send_message.call_args
    assert list(sent) == ["view"]
    assert sent["view"].to_components() == [
        {
            "type": 17,
            "accent_color": 0x7289DA,
            "spoiler": False,
            "components": [
                {
                    "type": 9,
                    "components": [
                        {
                            "type": 10,
                            "content": "🤖 Fischl is a multi-function Genshin-based bot with ticket system with a lot of utility-based slash commands.",
                        }
                    ],
                    "accessory": {
                        "type": 2,
                        "style": 5,
                        "disabled": False,
                        "label": "Invite Me",
                        "url": "https://discord.com/oauth2/authorize?client_id=77",
                        "emoji": {"id": 943068848058413106, "name": "link"},
                    },
                }
            ],
        }
    ]


# /text


@pytest.fixture
def font(monkeypatch):
    """Points the drawing code at the copy of the font kept in the repository."""
    real = ImageFont.truetype
    monkeypatch.setattr(
        text.ImageFont,
        "truetype",
        lambda path, size: real("web/static/world/ja-jp.ttf", size),
    )


def picture(sent):
    """Opens the picture a command sent, whether from disk or from memory."""
    file = sent["file"]
    assert file.filename == "text.png"
    file.fp.seek(0)
    return Image.open(file.fp)


def test_text_command():
    said = command_of(cog_of(text), "text")
    assert said.description == "Generates texts with Genshin-styled font"
    assert options(said) == {
        "color": "The hex code of the color of the text (Format: #ffffff)",
        "phrase": "Words to be written",
    }


@pytest.mark.parametrize(
    "colour, phrase, digest",
    [
        ("#ff0000", "Fischl", "RED"),
        ("0f0", "Oz!", "GREEN"),
        ("#000001", "night", "BLUE"),
        ("#000000", "ink", "BLACK"),
    ],
)
async def test_text_picture(font, colour, phrase, digest):
    cog, found = cog_of(text), interaction()
    await run(cog, "text", found, colour, phrase)
    found.response.defer.assert_awaited_once_with(ephemeral=True)
    (), sent = found.followup.send.call_args
    assert list(sent) == ["file"]
    drawn = picture(sent)
    assert (drawn.mode, drawn.size) == ("RGBA", (3500, 250))
    assert drawn.getpixel((3499, 249)) == (255, 255, 255, 0)
    assert hashlib.sha256(drawn.tobytes()).hexdigest() == TEXT_DIGESTS[digest]


TEXT_DIGESTS = {
    "RED": "37cda52e0c43db484d58a3bae11f9b5ddefd568925d0379d946001d21dfc7a6e",
    "GREEN": "e56d1876abbeb221f370099ee586dfe04e6a96211a1ac0dadff971578d2f9fd7",
    "BLUE": "e8a5d628536d213466c0889beb937238e3e9b36cfc3df5bb79628505498cc79e",
    "BLACK": "3b2e957064da4bbf808649694f573cbdf79c06a4f1a22d24e85819b88b464615",
}


async def test_text_too_long():
    cog, found = cog_of(text), interaction()
    with pytest.raises(Exception):
        await run(cog, "text", found, "#fff", "x" * 31)
    (), sent = found.followup.send.call_args
    assert sent["ephemeral"] is True
    assert no_stamp(sent["embed"]) == {
        "title": "Too long!",
        "description": ":warning: Your text length must not be longer than **30 characters** or else in most cases we cannot fit your text in the image! Please try again by separating your text and do the command multiple times!",
        "color": 0x93A7ED,
        "author": {"name": "amy", "icon_url": "https://cdn/amy.png"},
        "footer": {"text": "Action terminated"},
        "type": "rich",
        "flags": 0,
    }


@pytest.mark.parametrize("colour", ["#ggg", "ff00", "#12345", "red", "#ff00001"])
async def test_text_bad_colour(colour):
    cog, found = cog_of(text), interaction()
    with pytest.raises(Exception):
        await run(cog, "text", found, colour, "x" * 30)
    (), sent = found.followup.send.call_args
    assert sent["ephemeral"] is True
    assert no_stamp(sent["embed"]) == {
        "title": "⚠️ Invalid hex code",
        "description": "Hey! It looks like you have given me an invalid hex code. \n\nHex code uses the letters A-F, in addition to the digits 0-9, for a total of 16 symbols. If you have trouble finding the hex code, you could visit [this website](https://https://htmlcolorcodes.com/) to get help.",
        "color": discord.Color.red().value,
        "author": {"name": "amy", "icon_url": "https://cdn/amy.png"},
        "footer": {"text": "Action terminated"},
        "type": "rich",
        "flags": 0,
    }


# /emotes all


def emoji(number, animated=False):
    found = MagicMock()
    found.animated, found.name, found.id = animated, f"e{number}", number
    found.__str__ = lambda self: f"<{'a' if animated else ''}:e{number}:{number}>"
    return found


async def test_emotes_pages_and_buttons():
    cog, found = cog_of(emotes), interaction()
    group = cog.__cog_app_commands_group__
    assert (group.name, group.description, group.guild_only) == ("emotes", "…", True)
    assert command_of(cog, "all").description == "Shows all the emojis in the server"
    found.guild.emojis = [emoji(n, animated=n == 2) for n in range(1, 52)]
    await run(cog, "all", found)
    (), sent = found.response.send_message.call_args
    pages = [
        "".join(
            f"<{'a' if n == 2 else ''}:e{n}:{n}> `<{'a' if n == 2 else ''}:e{n}:{n}>`\n"
            for n in group
        )
        for group in (range(1, 26), range(26, 51), range(51, 52))
    ]
    assert sent["embed"].to_dict() == {
        "title": "Emotes in Mondstadt",
        "description": pages[0],
        "footer": {"text": "Page 1 of 3"},
        "type": "rich",
        "flags": 0,
    }
    view = sent["view"]
    assert [
        (child.custom_id, str(child.emoji), child.style) for child in view.children
    ] == [
        (
            "super_prev",
            "<:fastbackward:1351972112696479824>",
            discord.ButtonStyle.blurple,
        ),
        ("prev", "<:backarrow:1351972111010369618>", discord.ButtonStyle.blurple),
        ("next", "<:rightarrow:1351972116819480616>", discord.ButtonStyle.blurple),
        (
            "super_next",
            "<:fastforward:1351972114433048719>",
            discord.ButtonStyle.blurple,
        ),
    ]
    first, back, forward, last = view.children
    for button, page in [
        (back, 3),
        (forward, 1),
        (forward, 2),
        (last, 3),
        (forward, 1),
        (last, 3),
        (first, 1),
        (back, 3),
        (back, 2),
    ]:
        press = interaction()
        await button.callback(press)
        (), shown = press.response.edit_message.call_args
        assert list(shown) == ["embed"]
        assert shown["embed"].to_dict() == {
            "title": "Emotes in Mondstadt",
            "description": pages[page - 1],
            "footer": {"text": f"Page {page} of 3"},
            "type": "rich",
            "flags": 0,
        }


async def test_emotes_exactly_one_full_page():
    cog, found = cog_of(emotes), interaction()
    found.guild.emojis = [emoji(n) for n in range(1, 26)]
    await run(cog, "all", found)
    assert (
        found.response.send_message.call_args[1]["embed"].footer.text == "Page 1 of 1"
    )


async def test_emotes_in_a_server_with_none_fails_as_before():
    cog, found = cog_of(emotes), interaction()
    found.guild.emojis = []
    with pytest.raises(IndexError):
        await run(cog, "all", found)
    found.response.send_message.assert_not_awaited()


# the colour lookup both /color and /send-webevent use


class Answer:
    def __init__(self, status, body):
        self.status, self.body = status, body

    async def json(self):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error):
        return False


class Web:
    """Stands in for aiohttp: records each lookup and gives the planned answer."""

    def __init__(self, status=200, body=None, error=None):
        self.status, self.body, self.error = status, body, error
        self.asked, self.closed = [], False

    def __call__(self):
        return self

    def get(self, url, params=None):
        self.asked.append((url, params))
        if self.error:
            raise self.error
        return Answer(self.status, self.body)

    async def close(self):
        self.closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error):
        return False


def web(monkeypatch, module, **planned):
    found = Web(**planned)
    monkeypatch.setattr(module.aiohttp, "ClientSession", found)
    return found


# /send-webevent


def test_webevent_command():
    said = command_of(cog_of(sendwebevent), "send-webevent")
    assert said.description == "Sends a message for web event in embed"
    assert said.guild_only is True
    assert game_choices(said) == GAMES
    assert options(said) == {
        "game": "The game that the web event belongs",
        "link": "Link to the event",
        "role": "The role you would like to ping alongside this message",
        "title": "Event title",
        "details": "Event description/details",
        "image": "Embed image",
        "color": "Embed color in hex code format (e.g. #FFF000)",
    }


async def test_webevent_plain():
    cog, found = cog_of(sendwebevent), interaction()
    await run(cog, "send-webevent", found, game(1), "https://e.vent")
    (said,), sent = found.channel.send.call_args
    assert (
        said
        == "<:blurplemic:1108805037230129302> **• New Honkai: Star Rail Web Event**"
    )
    assert no_stamp(sent["embed"]) == {
        "url": "https://e.vent",
        "color": discord.Color.blurple().value,
        "footer": {"text": "Mondstadt", "icon_url": "https://cdn/icon.png"},
        "type": "rich",
        "flags": 0,
    }
    assert buttons(sent["view"]) == [
        (None, "https://e.vent", "<:link:943068848058413106>", discord.ButtonStyle.link)
    ]
    found.response.send_message.assert_awaited_once_with(f"{YES} Sent!", ephemeral=True)


async def test_webevent_with_everything(monkeypatch, no_files):
    asked = web(monkeypatch, sendwebevent, body={"hex": {"clean": "FFF000"}})
    cog, found = cog_of(sendwebevent), interaction()
    found.guild.icon = None
    picture, channel = attachment(found)
    role = MagicMock(mention="<@&9>")
    await run(
        cog,
        "send-webevent",
        found,
        game(0),
        "https://e.vent",
        role,
        "Lantern Rite",
        "Fun",
        picture,
        "#FFF000",
    )
    assert asked.asked == [("https://www.thecolorapi.com/id", {"hex": "FFF000"})]
    picture.save.assert_awaited_once_with("./assets/webevent.png")
    found.client.get_channel.assert_called_once_with(IMAGE_CHANNEL)
    assert channel.send.call_args == ((), {"file": (("./assets/webevent.png",), {})})
    (said,), sent = found.channel.send.call_args
    assert (
        said
        == "<:blurplemic:1108805037230129302> <@&9> **• New Genshin Impact Web Event**"
    )
    assert no_stamp(sent["embed"]) == {
        "title": "Lantern Rite",
        "description": "Fun",
        "url": "https://e.vent",
        "color": 0xFFF000,
        "image": {"url": "https://media/stored.png"},
        "footer": {"text": "Mondstadt"},
        "type": "rich",
        "flags": 0,
    }
    assert buttons(sent["view"]) == [
        (
            "Lantern Rite",
            "https://e.vent",
            "<:link:943068848058413106>",
            discord.ButtonStyle.link,
        )
    ]
    found.response.send_message.assert_awaited_once_with(f"{YES} Sent!", ephemeral=True)


async def test_webevent_colour_the_lookup_cannot_read_is_blurple(monkeypatch):
    web(monkeypatch, sendwebevent, body={"hex": {}})
    cog, found = cog_of(sendwebevent), interaction()
    await run(cog, "send-webevent", found, game(2), "https://e.vent", color="zzz")
    assert found.channel.send.call_args[1]["embed"].color == discord.Color.blurple()


async def test_webevent_fails_when_the_colour_lookup_is_down(monkeypatch):
    web(monkeypatch, sendwebevent, status=503)
    cog, found = cog_of(sendwebevent), interaction()
    with pytest.raises(NameError):
        await run(cog, "send-webevent", found, game(2), "https://e.vent", color="fff")
    found.channel.send.assert_not_awaited()
    found.response.send_message.assert_not_awaited()


async def test_webevent_ping_needs_permission(no_files):
    cog, found = cog_of(sendwebevent), interaction(may_ping=False)
    picture, channel = attachment(found)
    await run(
        cog,
        "send-webevent",
        found,
        game(0),
        "https://e.vent",
        MagicMock(),
        image=picture,
    )
    channel.send.assert_awaited_once()
    found.channel.send.assert_not_awaited()
    found.response.send_message.assert_awaited_once_with(
        f"{NO} You don't have permissions to mention `@everyone`, `@here`, or other roles!",
        ephemeral=True,
    )


# /sendcodes

NOTE = "<:MelonBread_KeqingNote:1342924552392671254> **Note:** Codes expire quickly, so make sure to redeem them as soon as possible!"
BANNER = "<:code1:1108803434141982751><:code2:1108803491171934218><:code3:1108803565331431454>"
STOCK_IMAGE = "https://media.discordapp.net/attachments/957252297501577276/965133143365550090/unknown.png"
SITES = [
    (
        "Genshin Impact",
        "https://genshin.mihoyo.com/en/gift",
        "https://genshin.hoyoverse.com/en/gift?code={}",
        "<:PRIMOGEM:1364031230357540894>",
    ),
    (
        "Honkai: Star Rail",
        "https://hsr.hoyoverse.com/gift?lang=en-us",
        "https://hsr.hoyoverse.com/gift?code={}&lang=en-us",
        "<:Jade:1222617029815832657>",
    ),
    (
        "Zenless Zone Zero",
        "https://zenless.hoyoverse.com/redemption",
        "https://zenless.hoyoverse.com/redemption?code={}",
        "<:Polychrome:1316607903939035236>",
    ),
]


def test_sendcodes_command():
    said = command_of(cog_of(sendcodes), "sendcodes")
    assert (
        said.description
        == "Sends a message for redemption codes with links and buttons."
    )
    assert said.guild_only is True
    assert game_choices(said) == GAMES
    assert options(said) == {
        "game": "The game that the codes belong",
        "codes": "The redemption codes you wish to send, each separated by a comma",
        "role": "The role you would like to ping alongside this message",
        "reward": "Optional description the rewards, each separated by a comma",
        "separate_msg": "Whether to send separate messages afterwards for copy & pasting (default: False)",
        "image": "One optional image of the reward, inserted in the embed",
    }


@pytest.mark.parametrize("index", [0, 1, 2])
async def test_sendcodes_plain(index):
    name, page, link, icon = SITES[index]
    cog, found = cog_of(sendcodes), interaction()
    await run(cog, "sendcodes", found, game(index), "AAA, BBB ,AAA")
    (said,), sent = found.channel.send.call_args
    assert said == "<:blurplemic:1108805037230129302> **• Redeemable Codes**"
    lines = "".join(
        f"{YES} `{code}` | **[Direct Link]({link.format(code)})**\n"
        for code in ("AAA", "BBB", "AAA")
    )
    assert no_stamp(sent["embed"]) == {
        "title": f"Latest {name} Redemption Codes",
        "description": f"<:link:943068848058413106> ***[Redeem by clicking on the buttons below!]({page})***\n{NOTE}\n\n{BANNER}\n{lines}",
        "color": discord.Color.blurple().value,
        "image": {"url": STOCK_IMAGE},
        "footer": {"text": "Mondstadt", "icon_url": "https://cdn/icon.png"},
        "type": "rich",
        "flags": 0,
    }
    assert buttons(sent["view"]) == [
        (code, link.format(code), icon, discord.ButtonStyle.link)
        for code in ("AAA", "BBB", "AAA")
    ]
    found.channel.send.assert_awaited_once()
    found.response.send_message.assert_awaited_once_with(f"{YES} Sent!", ephemeral=True)


@pytest.mark.parametrize("index", [0, 1, 2])
async def test_sendcodes_with_everything(no_files, index):
    name, page, link, icon = SITES[index]
    cog, found = cog_of(sendcodes), interaction()
    found.guild.icon = None
    picture, channel = attachment(found)
    role = MagicMock(mention="<@&9>")
    await run(
        cog,
        "sendcodes",
        found,
        game(index),
        "AAA, BBB,AAA",
        role,
        "60 gems , , again",
        True,
        picture,
    )
    picture.save.assert_awaited_once_with("./assets/sendcodes.png")
    found.client.get_channel.assert_called_once_with(IMAGE_CHANNEL)
    assert channel.send.call_args == ((), {"file": (("./assets/sendcodes.png",), {})})
    first, *rest = found.channel.send.call_args_list
    assert first[0] == (
        "<:blurplemic:1108805037230129302> <@&9> **• Redeemable Codes**",
    )
    lines = (
        f"{YES} **60 gems:** `AAA` | **[Direct Link]({link.format('AAA')})**\n"
        f"{YES} **:** `BBB` | **[Direct Link]({link.format('BBB')})**\n"
        f"{YES} **60 gems:** `AAA` | **[Direct Link]({link.format('AAA')})**\n"
    )
    assert no_stamp(first[1]["embed"]) == {
        "title": f"Latest {name} Redemption Codes",
        "description": f"<:link:943068848058413106> ***[Redeem by clicking on the buttons below!]({page})***\n{NOTE}\n\n{BANNER}\n{lines}",
        "color": discord.Color.blurple().value,
        "image": {"url": "https://media/stored.png"},
        "footer": {"text": "Mondstadt"},
        "type": "rich",
        "flags": 0,
    }
    assert buttons(first[1]["view"]) == [
        ("60 gems", link.format("AAA"), icon, discord.ButtonStyle.link),
        ("BBB", link.format("BBB"), icon, discord.ButtonStyle.link),
        ("60 gems", link.format("AAA"), icon, discord.ButtonStyle.link),
    ]
    assert [call[0] for call in rest] == [
        ("-# <:BunnyNerd:1224838490743767121> For copy and pasting ⬇️",),
        ("AAA",),
        ("BBB",),
        ("AAA",),
    ]
    found.response.send_message.assert_awaited_once_with(f"{YES} Sent!", ephemeral=True)


async def test_sendcodes_counts_must_match():
    cog, found = cog_of(sendcodes), interaction()
    await run(cog, "sendcodes", found, game(0), "AAA,BBB", reward="gems")
    found.channel.send.assert_not_awaited()
    found.response.send_message.assert_awaited_once_with(
        ":x: Number of codes `(2)` and reward descriptions `(1)` do not match. Please double check.",
        ephemeral=True,
    )


async def test_sendcodes_ping_needs_permission(no_files):
    cog, found = cog_of(sendcodes), interaction(may_ping=False)
    picture, channel = attachment(found)
    await run(cog, "sendcodes", found, game(0), "AAA", MagicMock(), image=picture)
    channel.send.assert_awaited_once()
    found.channel.send.assert_not_awaited()
    found.response.send_message.assert_awaited_once_with(
        f"{NO} You don't have permissions to mention `@everyone`, `@here`, or other roles!",
        ephemeral=True,
    )


# /color

RED = {
    "hex": {"value": "#FF0000", "clean": "FF0000"},
    "rgb": {"value": "rgb(255, 0, 0)"},
    "hsl": {"value": "hsl(0, 100%, 50%)"},
    "cmyk": {"value": "cmyk(0, 100, 100, 0)"},
    "hsv": {"value": "hsv(0, 100%, 100%)"},
    "XYZ": {"value": "XYZ(41, 21, 2)"},
    "name": {"value": "Red", "exact_match_name": True},
    "contrast": {"value": "#000000"},
}


def colour_card(name, note, clean, shown, opposite, contrast):
    return {
        "title": f"Information about {name}",
        "description": f"-# *{note}: {name}*",
        "color": int(clean, 16),
        "fields": [
            {
                "name": "HEX",
                "value": f"[{shown}](https://colorhexa.com/{clean})",
                "inline": True,
            },
            {"name": "RGB", "value": "rgb(255, 0, 0)", "inline": True},
            {"name": "HSL", "value": "hsl(0, 100%, 50%)", "inline": True},
            {"name": "CMYK", "value": "cmyk(0, 100, 100, 0)", "inline": True},
            {"name": "HSV", "value": "hsv(0, 100%, 100%)", "inline": True},
            {"name": "XYZ", "value": "XYZ(41, 21, 2)", "inline": True},
            {
                "name": "Complementary",
                "value": f"[#{opposite}](https://colorhexa.com/{opposite})",
                "inline": True,
            },
            {
                "name": "Contrast",
                "value": f"Best with **{contrast}** text",
                "inline": True,
            },
        ],
        "thumbnail": {"url": f"https://dummyimage.com/200x200/{clean}/{clean}.png"},
        "type": "rich",
        "flags": 0,
    }


async def test_color_command(monkeypatch):
    web(monkeypatch, color)
    said = command_of(cog_of(color), "color")
    assert said.description == "Visualize a hex color with detailed information"
    assert options(said) == {
        "hex": "The hex code of the color (3 or 6 characters, with/without #)"
    }
    (check,) = said.checks
    found = interaction()
    found.created_at.timestamp.return_value = 1000.0
    for _ in range(3):
        assert await check(found)
    with pytest.raises(app_commands.CommandOnCooldown) as stopped:
        await check(found)
    assert stopped.value.retry_after == 30


@pytest.mark.parametrize(
    "typed, body, card",
    [
        (
            "#F00",
            RED,
            colour_card("red", "Exact match", "ff0000", "#FF0000", "00ffff", "black"),
        ),
        (
            "ff0000",
            {
                **RED,
                "name": {"value": "Red", "exact_match_name": False},
                "contrast": {"value": "#ffffff"},
            },
            colour_card(
                "red", "Closest named color", "ff0000", "#FF0000", "00ffff", "white"
            ),
        ),
        (
            "##12ab9f",
            {**RED, "contrast": {"value": "#abcdef"}},
            colour_card("red", "Exact match", "12ab9f", "#FF0000", "ed5460", "#ABCDEF"),
        ),
    ],
)
async def test_color_card(monkeypatch, typed, body, card):
    asked = web(monkeypatch, color, body=body)
    cog, found = cog_of(color), interaction()
    await run(cog, "color", found, typed)
    assert asked.asked == [
        (
            "https://www.thecolorapi.com/id",
            {"hex": card["color"].to_bytes(3, "big").hex(), "format": "json"},
        )
    ]
    (), sent = found.response.send_message.call_args
    assert list(sent) == ["embed"]
    assert sent["embed"].to_dict() == card


@pytest.mark.parametrize("typed", ["", "#", "ff", "ffff", "ggg", "#ff00000", "ff 0000"])
async def test_color_bad_format(monkeypatch, typed):
    asked = web(monkeypatch, color)
    cog, found = cog_of(color), interaction()
    await run(cog, "color", found, typed)
    assert asked.asked == []
    (), sent = found.response.send_message.call_args
    assert sent["ephemeral"] is True
    assert sent["embed"].to_dict() == {
        "title": "⚠️ Invalid Hex Format",
        "description": "Please use a valid 3 or 6 character hex code (e.g., `#ff0000` or `f00`).",
        "color": discord.Color.red().value,
        "type": "rich",
        "flags": 0,
    }


@pytest.mark.parametrize(
    "typed, body",
    [
        ("123456", {**RED, "hex": {"clean": "000000"}}),
        ("000000", {"hex": {"clean": "000000"}}),
        ("fff", {}),
    ],
)
async def test_color_no_such_colour(monkeypatch, typed, body):
    web(monkeypatch, color, body=body)
    cog, found = cog_of(color), interaction()
    await run(cog, "color", found, typed)
    (), sent = found.response.send_message.call_args
    assert sent["ephemeral"] is True
    assert sent["embed"].to_dict() == {
        "title": "⚠️ Invalid Color Code",
        "description": "The provided hex code doesn't match any valid color.",
        "color": discord.Color.red().value,
        "type": "rich",
        "flags": 0,
    }


async def test_color_black_is_a_colour(monkeypatch):
    web(
        monkeypatch, color, body={**RED, "hex": {"value": "#000000", "clean": "000000"}}
    )
    cog, found = cog_of(color), interaction()
    await run(cog, "color", found, "000")
    assert found.response.send_message.call_args[1]["embed"].to_dict() == colour_card(
        "red", "Exact match", "000000", "#000000", "ffffff", "black"
    )


async def test_color_lookup_down_or_broken(monkeypatch):
    web(monkeypatch, color, status=502)
    cog, found = cog_of(color), interaction()
    await run(cog, "color", found, "fff")
    found.response.send_message.assert_awaited_once_with(
        "⚠️ API Error (Status 502)", ephemeral=True
    )
    web(monkeypatch, color, error=RuntimeError("no network"))
    cog, found = cog_of(color), interaction()
    await run(cog, "color", found, "fff")
    found.response.send_message.assert_awaited_once_with(
        "⚠️ An unexpected error occurred: no network", ephemeral=True
    )


async def test_color_cooldown_and_other_errors(monkeypatch):
    web(monkeypatch, color)
    cog, found = cog_of(color), interaction()
    handler = command_of(cog, "color").on_error
    await handler(cog, found, app_commands.CommandOnCooldown(MagicMock(), 12.34))
    found.response.send_message.assert_awaited_once_with(
        "⏳ Please wait 12.3s before using this command again.", ephemeral=True
    )
    with pytest.raises(app_commands.AppCommandError):
        await handler(cog, found, app_commands.AppCommandError("other"))


async def test_color_closes_its_session(monkeypatch):
    asked = web(monkeypatch, color)
    cog = cog_of(color)
    await cog.cog_unload()
    assert asked.closed


# /database


async def ask(pool, query, user=OWNER):
    """Runs /database and gives the interaction it answered."""
    found = interaction(user)
    found.client.pool = pool
    await run(cog_of(database), "database", found, query)
    return found


def answer(found):
    (), sent = found.followup.send.call_args
    assert sent["ephemeral"] is True
    return sent["embed"].to_dict()


def test_database_command():
    said = command_of(cog_of(database), "database")
    assert said.description == "Execute raw SQL queries"
    assert options(said) == {
        "query": "minigame_inventory/mora/progression/chests/rewards/cosmetics/elite/settings/guild_settings"
    }


async def test_database_is_for_the_owner_only():
    found = await ask(MagicMock(), "SELECT 1", user=5)
    found.response.send_message.assert_awaited_once_with(
        "❌ Only the bot owner can use this command!", ephemeral=True
    )
    found.response.defer.assert_not_awaited()


async def test_database_empty_and_unknown_queries():
    found = await ask(MagicMock(), "   ")
    found.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
    found.followup.send.assert_awaited_once_with(
        "❌ Query cannot be empty!", ephemeral=True
    )
    found = await ask(MagicMock(), "  explain select 1")
    found.followup.send.assert_awaited_once_with(
        "❓ Unknown command: `EXPLAIN`\n\nSupported: SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP",
        ephemeral=True,
    )


async def test_database_select(pool):
    await pool.execute("CREATE TABLE pets (name TEXT, age BIGINT)")
    assert answer(await ask(pool, "select * from pets")) == {
        "title": "Query Result (Empty)",
        "description": "```\n(no results)\n```",
        "color": discord.Color.orange().value,
        "type": "rich",
        "flags": 0,
    }
    await pool.execute("INSERT INTO pets VALUES ('Oz', 3)")
    assert answer(await ask(pool, " select * from pets ")) == {
        "title": "Query Result (1 row)",
        "color": discord.Color.green().value,
        "fields": [
            {"name": "Columns", "value": "```\nname, age\n```", "inline": False},
            {"name": "Data", "value": "```\n1. Oz  3\n\n```", "inline": False},
            {
                "name": "Query",
                "value": "```sql\nselect * from pets\n```",
                "inline": False,
            },
        ],
        "footer": {"text": "Total rows: 1"},
        "type": "rich",
        "flags": 0,
    }


async def test_database_select_cuts_long_values_rows_and_queries(pool):
    await pool.execute("CREATE TABLE pets (name TEXT, age BIGINT)")
    await pool.execute(
        "INSERT INTO pets SELECT repeat('x', 40), n FROM generate_series(1, 60) n"
    )
    query = "SELECT * FROM pets ORDER BY age" + " " * 190 + "LIMIT 60 OFFSET 0"
    found = answer(await ask(pool, query))
    lines = "".join(f"{n}. {'x' * 30}  {n}\n" for n in range(1, 26))
    assert found["title"] == "Query Result (60 rows)"
    assert found["fields"][1] == {
        "name": "Data",
        "value": f"```\n{lines}\n... and 35 more rows\n```",
        "inline": False,
    }
    assert found["fields"][2]["value"] == f"```sql\n{query[:200]}...\n```"
    assert found["footer"] == {"text": "Total rows: 60"}


async def test_database_select_with_a_row_too_wide_to_show(pool):
    await pool.execute(
        "CREATE TABLE wide AS SELECT "
        + ", ".join(f"repeat('x', 30) AS c{n}" for n in range(40))
    )
    found = answer(await ask(pool, "SELECT * FROM wide"))
    assert found["fields"][1] == {
        "name": "Data",
        "value": "*(no data)*",
        "inline": False,
    }


async def test_database_changes_rows(pool):
    await pool.execute("CREATE TABLE pets (name TEXT PRIMARY KEY, age BIGINT)")
    for query, kind, count in [
        ("insert into pets values ('Oz', 3), ('Amy', 4)", "INSERT", 2),
        ("UPDATE pets SET age = 5", "UPDATE", 2),
        ("DELETE FROM pets WHERE name = 'Oz'", "DELETE", 1),
    ]:
        assert answer(await ask(pool, query)) == {
            "title": f"✅ {kind} Successful",
            "description": f"**Rows affected:** `{count}`",
            "color": discord.Color.green().value,
            "fields": [
                {"name": "Query", "value": f"```sql\n{query}\n```", "inline": False}
            ],
            "type": "rich",
            "flags": 0,
        }
    assert [tuple(row) for row in await pool.fetch("SELECT * FROM pets")] == [
        ("Amy", 5)
    ]
    long = "UPDATE pets SET age = 6 WHERE name = 'Amy'" + " " * 300 + "AND true"
    assert (
        answer(await ask(pool, long))["fields"][0]["value"]
        == f"```sql\n{long[:300]}...\n```"
    )


async def test_database_errors(pool):
    await pool.execute("CREATE TABLE pets (name TEXT PRIMARY KEY, age BIGINT)")
    await pool.execute("INSERT INTO pets VALUES ('Oz', 3)")
    for query in ("SELECT * FORM pets", "UPDATE pets SETT age = 1"):
        found = answer(await ask(pool, query))
        assert (found["title"], found["color"]) == (
            "❌ SQL Syntax Error",
            discord.Color.red().value,
        )
        assert [field["name"] for field in found["fields"]] == [
            "Error",
            "💡 SQL Syntax Help",
            "Query Attempted",
        ]
        assert found["fields"][0]["value"].startswith("```\nsyntax error at or near")
        assert found["fields"][1]["value"] == (
            "Common mistakes:\n"
            "- Missing semicolon at end: `SELECT * FROM table;`\n"
            "- Misspelled table/column name\n"
            "- Missing quotes around string values: `'value'`\n"
            "- Missing commas between columns\n"
            "- Wrong quote type (use double quotes for identifiers, single for strings)"
        )
        assert found["fields"][2] == {
            "name": "Query Attempted",
            "value": f"```sql\n{query}\n```",
            "inline": False,
        }

    assert answer(await ask(pool, "INSERT INTO pets VALUES ('Oz', 4)")) == {
        "title": "🚫 INSERT Failed: Integrity Constraint",
        "description": '```\nduplicate key value violates unique constraint "pets_pkey"\nDETAIL:  Key (name)=(Oz) already exists.\n```',
        "color": discord.Color.red().value,
        "fields": [
            {
                "name": "💡 Common Causes",
                "value": "• Foreign key constraint violation\n• Unique constraint violation\n• NOT NULL constraint violation",
                "inline": False,
            }
        ],
        "type": "rich",
        "flags": 0,
    }

    for query in ("SELECT * FROM nothing", "DELETE FROM nothing"):
        found = answer(await ask(pool, query))
        assert (found["title"], found["color"]) == (
            "❌ UndefinedTableError",
            discord.Color.red().value,
        )
        assert found["fields"][0] == {
            "name": "Error Details",
            "value": '```\nrelation "nothing" does not exist\n```',
            "inline": False,
        }
        assert found["fields"][1] == {
            "name": "Query Attempted",
            "value": f"```sql\n{query}\n```",
            "inline": False,
        }
        assert [field["name"] for field in found["fields"][2:]] in ([], ["Traceback"])

    found = answer(await ask(pool, "UPDATE pets SET age = 'old'"))
    assert found["title"] == "❌ InvalidTextRepresentationError"
    assert found["fields"][1] == {
        "name": "💡 Type Mismatch",
        "value": "The data type doesn't match the column type.\n"
        "Examples:\n"
        "• `BIGINT` expects integers: `123` (not `'123'`)\n"
        "• `VARCHAR` expects strings: `'text'` (with quotes)",
        "inline": False,
    }


@pytest.mark.parametrize(
    "words, hint",
    [
        (
            "permission denied",
            (
                "💡 Permission Issue",
                "The database user might not have permission for this operation.",
            ),
        ),
        (
            "connection lost",
            (
                "💡 Connection Issue",
                "The database connection may be lost. Try again in a moment.",
            ),
        ),
        ("boom", None),
    ],
)
async def test_database_hints_for_other_errors(words, hint):
    pool = MagicMock()
    pool.acquire.side_effect = RuntimeError(words)
    found = answer(await ask(pool, "SELECT 1"))
    assert found["title"] == "❌ RuntimeError"
    assert found["fields"][0] == {
        "name": "Error Details",
        "value": f"```\n{words}\n```",
        "inline": False,
    }
    named = [(field["name"], field["value"]) for field in found["fields"][1:]]
    assert named[0] == (hint or ("Query Attempted", "```sql\nSELECT 1\n```"))
    assert all(field["inline"] is False for field in found["fields"])


async def test_database_schema_change_waits_for_a_yes(pool):
    query = "create table pets (name TEXT)"
    found = await ask(pool, query)
    (), sent = found.followup.send.call_args
    assert sent["ephemeral"] is True
    assert sent["embed"].to_dict() == {
        "title": "⚠️  CREATE Command - Proceed with Caution",
        "description": "Schema modification commands can significantly impact the database.",
        "color": discord.Color.orange().value,
        "fields": [
            {
                "name": "⚠️  Warning",
                "value": "This will modify the database schema. Make sure you know what you're doing!",
                "inline": False,
            },
            {
                "name": "Query Preview",
                "value": f"```sql\n{query}\n```",
                "inline": False,
            },
        ],
        "type": "rich",
        "flags": 0,
    }
    view = sent["view"]
    assert view.timeout == 30
    assert [(child.label, child.style) for child in view.children] == [
        ("⚠️  Execute", discord.ButtonStyle.danger),
        ("Cancel", discord.ButtonStyle.secondary),
    ]
    assert await pool.fetchval("SELECT to_regclass('pets')") is None
    yes, no = view.children

    for button in (yes, no):
        stranger = interaction(5)
        await button.callback(stranger)
        stranger.response.send_message.assert_awaited_once_with(
            "❌ You didn't initiate this command!", ephemeral=True
        )
    assert not view.is_finished()
    assert await pool.fetchval("SELECT to_regclass('pets')") is None

    press = interaction(OWNER)
    await yes.callback(press)
    (), done = press.response.send_message.call_args
    assert done["ephemeral"] is True
    assert done["embed"].to_dict() == {
        "title": "✅ CREATE Executed",
        "description": "Schema modification completed successfully.",
        "color": discord.Color.green().value,
        "fields": [
            {"name": "Query", "value": f"```sql\n{query}\n```", "inline": False}
        ],
        "type": "rich",
        "flags": 0,
    }
    assert view.is_finished()
    assert await pool.fetchval("SELECT to_regclass('pets')") is not None


async def test_database_schema_change_cancelled_or_failing(pool):
    found = await ask(pool, "DROP TABLE nothing")
    view = found.followup.send.call_args[1]["view"]
    press = interaction(OWNER)
    await view.children[1].callback(press)
    press.response.send_message.assert_awaited_once_with(
        "❌ Command cancelled.", ephemeral=True
    )
    assert view.is_finished()

    found = await ask(pool, "ALTER TABLE nothing ADD x INT")
    view = found.followup.send.call_args[1]["view"]
    press = interaction(OWNER)
    await view.children[0].callback(press)
    failed = answer(press)
    assert failed["title"] == "❌ UndefinedTableError"
    assert (
        failed["fields"][-1 if len(failed["fields"]) == 2 else -2]["name"]
        == "Query Attempted"
    )
    assert view.is_finished()


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM pets WHERE age = 3; DROP TABLE pets",
        "select 1; delete from pets;",
        "UPDATE pets SET age = 1 ;\nINSERT INTO pets VALUES ('Amy', 4)",
    ],
)
async def test_database_asks_before_running_more_than_one_statement(pool, query):
    await pool.execute("CREATE TABLE pets (name TEXT PRIMARY KEY, age BIGINT)")
    await pool.execute("INSERT INTO pets VALUES ('Oz', 3)")
    found = await ask(pool, query)
    (), sent = found.followup.send.call_args
    assert sent["embed"].title.endswith(" Command - Proceed with Caution")
    assert (
        sent["embed"].fields[0].value.startswith("This holds more than one statement")
    )
    assert [child.label for child in sent["view"].children] == [
        "⚠️  Execute",
        "Cancel",
    ]
    assert await pool.fetchval("SELECT age FROM pets") == 3


@pytest.mark.parametrize(
    "query", ["DELETE FROM pets;", "DELETE FROM pets ; \n", "select * from pets;;"]
)
async def test_database_runs_one_statement_ending_in_a_semicolon_at_once(pool, query):
    await pool.execute("CREATE TABLE pets (name TEXT PRIMARY KEY, age BIGINT)")
    found = await ask(pool, query)
    assert "view" not in found.followup.send.call_args.kwargs
