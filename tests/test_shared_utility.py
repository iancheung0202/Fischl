"""The small commands and logs under shared/Utility, which the other bots load too."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands

from shared.Utility import onCommand, onGuild, ping, server, user

WHEN = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
STAMP = int(WHEN.timestamp())


def guild(**changes):
    """A server with an owner, an icon and 12 members."""
    made = SimpleNamespace(
        id=5,
        name="Tavern",
        description="A place",
        member_count=12,
        owner=SimpleNamespace(mention="<@9>"),
        owner_id=9,
        icon=SimpleNamespace(url="icon.png"),
        banner=None,
        text_channels=[1, 2],
        voice_channels=[1],
        emojis=[1, 2, 3],
        emoji_limit=50,
        stickers=[],
        sticker_limit=5,
        created_at=WHEN,
        default_role=SimpleNamespace(id=5),
    )
    made.__dict__.update(changes)
    return made


def press(**changes):
    """An interaction in a channel of the server, used by member 7."""
    it = MagicMock()
    it.response.send_message = AsyncMock()
    it.edit_original_response = AsyncMock()
    it.guild = guild()
    it.channel = SimpleNamespace(id=30, name="general", mention="<#30>")
    it.channel_id = 30
    it.user = SimpleNamespace(id=7, name="amy", created_at=WHEN)
    it.created_at = WHEN
    it.command_failed = False
    it.data = {}
    for name, value in changes.items():
        setattr(it, name, value)
    return it


def fields(embed):
    """Gives an embed's fields as (name, value, inline)."""
    return [(f.name, f.value, f.inline) for f in embed.fields]


def bot(guilds=3):
    """A bot in some servers whose log channel records what is sent."""
    made = MagicMock(guilds=[None] * guilds, latency=0.0424)
    made.room = SimpleNamespace(send=AsyncMock())
    made.get_channel = MagicMock(return_value=made.room)
    return made


async def test_ping_answers_then_shows_the_latency():
    it = press()
    await ping.Ping(bot()).ping.callback(ping.Ping(bot()), it)
    it.response.send_message.assert_awaited_once_with("Pong!")
    it.edit_original_response.assert_awaited_once_with(content="Pong! Latency: 42ms")


@pytest.mark.parametrize(
    "event, title, color",
    [
        ("on_guild_join", "Guild Joined", discord.Color.green()),
        ("on_guild_remove", "Guild Left", discord.Color.red()),
    ],
)
async def test_joined_and_left_servers_are_logged(event, title, color):
    client = bot()
    await getattr(onGuild.OnGuild(client), event)(guild())
    client.get_channel.assert_called_once_with(1417408752876916829)
    embed = client.room.send.await_args.kwargs["embed"]
    assert (embed.title, embed.description, embed.color) == (title, "Tavern (5)", color)
    assert embed.thumbnail.url == "icon.png" and embed.timestamp is not None
    assert fields(embed) == [
        ("Member Count", "12", True),
        ("Owner", "<@9> (9)", True),
        ("Total Bot Guilds", "3", True),
    ]


async def test_a_server_log_leaves_out_what_is_unknown():
    client = bot()
    bare = guild(member_count=None, owner=None, icon=None)
    await onGuild.OnGuild(client).on_guild_remove(bare)
    embed = client.room.send.await_args.kwargs["embed"]
    assert fields(embed) == [("Total Bot Guilds", "3", True)]
    assert embed.thumbnail.url is None


async def test_server_shows_the_servers_details():
    it = press()
    it.guild.banner = SimpleNamespace(url="banner.png")
    cog = server.Server(bot())
    await cog.server.callback(cog, it)
    embed = it.response.send_message.await_args.kwargs["embed"]
    assert (embed.title, embed.description) == ("Tavern", "A place")
    assert embed.color == discord.Color.blurple() and embed.timestamp is not None
    assert (embed.thumbnail.url, embed.image.url) == ("icon.png", "banner.png")
    assert fields(embed) == [
        ("Server Name", "Tavern", True),
        ("Server ID", "`5`", True),
        ("Members Count", "12", True),
        ("Text Channels", "2", True),
        ("Voice channels", "1", True),
        ("Created At", f"<t:{STAMP}:R>", True),
        ("Owner", "<@9>", True),
        ("Emojis", "3/50", True),
        ("Stickers", "0/5", True),
    ]


def someone(roles=(), **changes):
    """A member with the @everyone role (id 5) and the given (id, position) roles."""
    held = [SimpleNamespace(id=5, position=0)]
    held += [SimpleNamespace(id=id, position=position) for id, position in roles]
    made = SimpleNamespace(
        id=7,
        name="amy",
        nick="Amy",
        roles=held,
        banner=None,
        created_at=WHEN,
        joined_at=WHEN,
        top_role=SimpleNamespace(colour=SimpleNamespace(value=0x123456)),
        display_avatar=SimpleNamespace(url="amy.png"),
    )
    made.__dict__.update(changes)
    return made


async def test_user_shows_a_member_and_defaults_to_the_caller():
    target = someone([(11, 1), (12, 3), (13, 2)])
    it = press(user=target)
    cog = user.User(bot())
    await cog.user.callback(cog, it)
    embed = it.response.send_message.await_args.kwargs["embed"]
    assert embed.colour.value == 0x123456 and embed.thumbnail.url == "amy.png"
    assert embed.image.url is None and embed.timestamp is not None
    assert fields(embed) == [
        ("Username", "amy", True),
        ("Server Nick", "Amy", True),
        ("User ID", "`7`", True),
        ("Account created", f"<t:{STAMP}:R>", True),
        ("Joined this server", f"<t:{STAMP}:R>", True),
        ("Roles", "<@&12>, <@&13>, <@&11>", False),
    ]
    other = someone(banner=SimpleNamespace(url="banner.png"), nick=None)
    await cog.user.callback(cog, it, other)
    embed = it.response.send_message.await_args.kwargs["embed"]
    assert embed.image.url == "banner.png"
    assert fields(embed)[1] == ("Server Nick", "None", True)
    assert fields(embed)[-1] == ("Roles", "None", False)


def test_a_long_role_list_is_cut_to_fit_one_field():
    ids = [10**18 + n for n in range(60)]
    text = user.role_list(someone([(id, n + 1) for n, id in enumerate(ids)]), 5)
    assert len(text) <= 1024 and text.endswith(" more roles)")
    shown = text.count("<@&")
    assert text.startswith(f"<@&{ids[-1]}>, <@&{ids[-2]}>")
    assert text.endswith(f" ({60 - shown} more roles)") and shown == 40
    assert user.role_list(someone(), 5) == "None"
    assert user.role_list(SimpleNamespace(), 5) == "None"


def test_options_are_written_by_their_kind_through_subcommands():
    options = [
        {
            "name": "group",
            "options": [
                {"name": "who", "type": 6, "value": 1},
                {"name": "where", "type": 7, "value": 2},
                {"name": "role", "type": 8, "value": 3},
                {"name": "any", "type": 9, "value": 4},
                {"name": "text", "type": 3, "value": "hi"},
                {"name": "plain", "value": 5},
                {"name": "empty"},
            ],
        }
    ]
    assert onCommand.extract_params(options) == [
        "who:<@1>",
        "where:<#2>",
        "role:<@&3>",
        "any:<@1>".replace("1", "4"),
        "text:hi",
        "plain:5",
    ]


def slash(name="mora"):
    """A slash command by name."""
    made = MagicMock(spec=app_commands.Command)
    made.qualified_name = name
    return made


async def logged(it, command):
    """Runs the command log and gives the description it posted."""
    client = bot()
    await onCommand.OnCommand(client).on_app_command_completion(it, command)
    client.get_channel.assert_called_once_with(1030892842308091987)
    embed = client.room.send.await_args.kwargs["embed"]
    assert embed.colour == discord.Color.blurple() and embed.timestamp is not None
    return embed.description


async def test_a_used_command_is_logged_in_full():
    it = press(data={"options": [{"name": "text", "type": 3, "value": "a`b\nc"}]})
    assert await logged(it, slash()) == (
        "**Command:** `/mora text:a'b c`\n"
        f"**Used at:** <t:{STAMP}:R>\n"
        "**Status:** <:yes:1036811164891480194> Success\n\n"
        "**User Name:** amy\n"
        "**User ID:** `7`\n"
        f"**User Created:** <t:{STAMP}:R>\n\n"
        "**Guild Name:** [Tavern](https://fischl.app)\n"
        "**Guild ID:** `5`\n"
        "**Guild Member Count:** 12\n"
        f"**Guild Created:** <t:{STAMP}:R>\n\n"
        "**Channel Name:** [#general](https://fischl.app)\n"
        "**Channel ID:** `30`\n"
        "**Channel Mention:** <#30>"
    )


async def test_a_failed_or_long_or_bare_command_is_logged():
    it = press(command_failed=True, data={})
    text = await logged(it, slash("shop view"))
    assert "**Command:** `/shop view`\n" in text
    assert "**Status:** <:no:1036810470860013639> Failed\n" in text
    it = press(data={"options": [{"name": "text", "type": 3, "value": "x" * 2000}]})
    line = (await logged(it, slash())).split("\n")[0]
    assert line == "**Command:** `" + ("/mora text:" + "x" * 2000)[:1000] + "...`"


async def test_menu_commands_are_logged_with_their_target():
    menu = SimpleNamespace(qualified_name="Report", type=discord.AppCommandType.user)
    assert "`Report (User: <@44>)`" in await logged(press(data={"target_id": 44}), menu)
    menu.type = discord.AppCommandType.message
    text = await logged(press(data={"target_id": 44}), menu)
    assert "`Report (Message ID: 44)`" in text


async def test_a_command_used_in_dms_is_logged_without_a_server():
    text = await logged(press(guild=None, channel=None), slash())
    assert text.endswith("**Guild Name:** Direct Message\n**Channel ID:** `30`")


class Web:
    """A stand-in for aiohttp that records what was posted."""

    def __init__(self, status=200, error=None):
        self.status, self.error, self.posts = status, error, []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error):
        return False

    def post(self, url, **sent):
        if self.error:
            raise self.error
        self.posts.append((url, sent["data"]))
        return self


async def test_a_command_error_is_printed_and_sent_to_the_phone(monkeypatch, capsys):
    web = Web()
    monkeypatch.setattr(onCommand.aiohttp, "ClientSession", web)
    monkeypatch.setattr(onCommand, "NTFY_LINK", "https://ntfy/x")
    client = bot()
    cog = onCommand.OnCommand(client)
    assert client.tree.on_error == cog.on_app_command_error
    it = press()
    it.command.qualified_name = "mora"
    await cog.on_app_command_error(it, RuntimeError("b" * 600))
    assert web.posts == [("https://ntfy/x", "Command: mora\nError: " + "b" * 500)]
    assert "Error in app command: bbb" in capsys.readouterr().out
    it.command = None
    await cog.on_app_command_error(it, RuntimeError("no"))
    assert web.posts[-1][1] == "Command: Unknown\nError: no"


async def test_a_failed_phone_notice_is_only_printed(monkeypatch, capsys):
    monkeypatch.setattr(onCommand.aiohttp, "ClientSession", Web(status=500))
    await onCommand.OnCommand(bot()).on_app_command_error(press(), RuntimeError("x"))
    assert "Failed to send ntfy notification: 500" in capsys.readouterr().out
    monkeypatch.setattr(onCommand.aiohttp, "ClientSession", Web(error=OSError("down")))
    await onCommand.OnCommand(bot()).on_app_command_error(press(), RuntimeError("x"))
    assert "Error sending ntfy notification: down" in capsys.readouterr().out


async def test_logs_are_skipped_in_a_bot_that_cannot_see_the_log_channels():
    client = MagicMock()
    client.get_channel = lambda channel_id: None
    await onGuild.OnGuild(client).log(guild(), "Guild Joined", discord.Color.green())
    made = MagicMock(spec=app_commands.Command)
    made.qualified_name = "ping"
    await onCommand.OnCommand(client).on_app_command_completion(press(), made)
