import hashlib
import io
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from PIL import Image, ImageFont

from commands.Custom import bulletin, celestial, levelUp
from commands.Custom import winnerStore as store

BULLETIN, CELESTIAL, JINHSI = (
    1281655927791030293,
    1168706427435622410,
    1197491630807199834,
)
WINNER, LAST = 42, 748745444527570945
MORA = """CREATE TABLE minigame_mora (uid BIGINT, gid BIGINT, cid BIGINT,
    timestamp BIGINT, count INTEGER, PRIMARY KEY (gid, uid, cid, timestamp))"""
LEAKS = [
    ("Genshin Leaks", "genshinleaksaccesscelestial"),
    ("HSR Leaks", "hsrleaksaccesscelestial"),
    ("WuWa Leaks", "wuwaleaksaccesscelestial"),
    ("ZZZ Leaks", "zzzleaksaccesscelestial"),
]


def role(id, name="role", members=()):
    found = MagicMock(id=id, mention=f"<@&{id}>", members=list(members))
    found.name = name
    return found


def member(id, roles=(), name="ian"):
    found = MagicMock(id=id, mention=f"<@{id}>", roles=list(roles), bot=False)
    found.name = name
    found.color = discord.Colour(0xE91E63)
    found.add_roles, found.remove_roles = AsyncMock(), AsyncMock()
    return found


def guild(id, roles=(), channels=()):
    found = MagicMock(id=id, roles=list(roles))
    found.get_role = lambda wanted: next((r for r in roles if r.id == wanted), None)
    found.get_channel = lambda wanted: next(
        (c for c in channels if c.id == wanted), None
    )
    found.chunk, found.invites, found.fetch_member = (
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
    )
    return found


def channel(id, category=1):
    found = MagicMock(id=id, mention=f"<#{id}>", send=AsyncMock())
    found.category.id = category
    return found


def message(guild, content, author=None, channel_id=5, category=1):
    found = MagicMock(content=content, guild=guild, author=author or member(7))
    found.channel = channel(channel_id, category)
    found.delete, found.publish = AsyncMock(), AsyncMock()
    return found


def interaction(guild, user=None, pool=None):
    found = MagicMock(guild=guild, user=user)
    found.client.pool = pool
    found.response.send_message = AsyncMock()
    found.followup.send = AsyncMock()
    found.message.edit = AsyncMock()
    return found


# ---- Meropide Bulletin: /send-leaderboard ----


@pytest.fixture
async def board(pool):
    """The cog, the server, the winner role and the leaderboard channel."""
    await pool.execute(MORA)
    bot = MagicMock(pool=pool)
    cog = bulletin.CustomCommands(bot)
    await cog.cog_load()
    prize, post = role(1313053449549512704), channel(1312858564695687310)
    server = guild(BULLETIN, [prize])
    found = interaction(server, pool=pool)
    found.client.get_channel = lambda id: post if id == post.id else None
    return cog, found, prize, post


async def test_send_leaderboard_looks_the_same():
    command = bulletin.CustomCommands.send_leaderboard
    assert (command.name, command.description, command.guild_only) == (
        "send-leaderboard",
        "Posts the weekly leaderboard (Meropide Bulletin only)",
        True,
    )
    assert [(p.name, p.description, p.required) for p in command.parameters] == [
        ("text_user", "User with the most messages", True),
        ("link", "The link of the leaderboard image", True),
    ]
    with pytest.raises(discord.app_commands.MissingPermissions):
        command.checks[0](MagicMock(permissions=discord.Permissions.none()))
    assert command.checks[0](
        MagicMock(permissions=discord.Permissions(administrator=True))
    )


async def test_send_leaderboard_is_for_meropide_bulletin_only(board):
    cog, found, prize, post = board
    found.guild = guild(5)
    winner = member(WINNER)
    await cog.send_leaderboard.callback(cog, found, winner, "https://x/y.png")
    found.response.send_message.assert_awaited_once_with(
        content="This command can only be used in the **Meropide Bulletin** server.",
        ephemeral=True,
    )
    post.send.assert_not_awaited()
    winner.add_roles.assert_not_awaited()
    assert await store.winner(found.client.pool, 5) is None


async def test_send_leaderboard_posts_crowns_and_pays(board):
    cog, found, prize, post = board
    pool = found.client.pool
    await store.crown(pool, BULLETIN, LAST)
    last, winner = member(LAST, [prize]), member(WINNER)
    found.guild.fetch_member.return_value = last
    await cog.send_leaderboard.callback(cog, found, winner, "https://x/y.png")

    about, week = post.send.call_args.kwargs["embeds"]
    assert (about.title, about.colour.value) == ("Weekly Leaderboard", 0x00FFAF)
    assert about.description == (
        "The leaderboard will be updated every Saturday. The member who secures the top position in the **text message leaderboard** will be granted the prestigious <@&1313053449549512704> role for the entire week, along with the following generous reward:\n\n- The role comes with its own category and autorespond GIF\n- Members will be able to mention your role any time (flex)\n\n> To view the current leaderboard, please use </stats message:1025501230044286982>. Alternatively, you can check your personal statistics by using </me:1025501230044286978>."
    )
    assert week.to_dict() == {
        "type": "rich",
        "flags": 0,
        "description": "***Presenting this week's leaderboard...***",
        "color": 0x00FFAF,
        "fields": [
            {
                "name": "🏆 Top Message User",
                "value": "<:reply:1036792837821435976> <@42>",
                "inline": True,
            }
        ],
        "image": {"url": "https://x/y.png"},
    }
    found.guild.fetch_member.assert_awaited_once_with(LAST)
    last.remove_roles.assert_awaited_once_with(prize)
    winner.add_roles.assert_awaited_once_with(prize)
    assert await store.winner(pool, BULLETIN) == WINNER
    found.response.send_message.assert_awaited_once_with(
        content="The following embed is sent to <#1312858564695687310>:",
        embeds=[about, week],
    )
    rows = await pool.fetch("SELECT uid, gid, cid, count FROM minigame_mora")
    assert [tuple(row) for row in rows] == [(WINNER, BULLETIN, 10, 100000)]
    found.followup.send.assert_awaited_once_with(
        "<:yes:1036811164891480194> Added exactly <:MORA:1364030973611610205> `100,000` to <@42>'s inventory. \n-# This is not boosted and doesn't count towards quest progression.",
        ephemeral=True,
    )


async def test_first_winner_and_a_last_winner_without_the_role(board):
    cog, found, prize, post = board
    winner = member(WINNER)
    await cog.send_leaderboard.callback(cog, found, winner, "l")
    found.guild.fetch_member.assert_not_awaited()
    winner.add_roles.assert_awaited_once_with(prize)

    found.guild.fetch_member.return_value = winner
    await cog.send_leaderboard.callback(cog, found, member(8), "l")
    winner.remove_roles.assert_not_awaited()
    assert await store.winner(found.client.pool, BULLETIN) == 8


async def test_a_last_winner_who_left_stops_the_command(board):
    cog, found, prize, post = board
    await store.crown(found.client.pool, BULLETIN, LAST)
    found.guild.fetch_member.side_effect = discord.NotFound(
        MagicMock(status=404), "gone"
    )
    winner = member(WINNER)
    with pytest.raises(discord.NotFound):
        await cog.send_leaderboard.callback(cog, found, winner, "l")
    post.send.assert_awaited_once()
    winner.add_roles.assert_not_awaited()
    assert await store.winner(found.client.pool, BULLETIN) == LAST


# ---- Meropide Bulletin: chat rules ----


@pytest.fixture
def chat():
    """The cog and the server, with one invite of its own and the two staff roles."""
    log = channel(1288400196220227594)
    staff = [role(1282396278071890086), role(1282395927168159876)]
    server = guild(BULLETIN, staff, [log])
    server.invites.return_value = [MagicMock(code="own1"), MagicMock(code="own2")]
    return bulletin.CustomCommands(MagicMock()), server, log, staff


async def test_an_invite_to_another_server_is_deleted_and_logged(chat):
    cog, server, log, staff = chat
    said = message(server, "join discord.gg/other now", channel_id=9)
    await cog.on_message(said)
    said.delete.assert_awaited_once_with()
    said.channel.send.assert_awaited_once_with(
        "<@7>, no invite links!", delete_after=300
    )
    assert log.send.call_args.kwargs["embed"].to_dict() == {
        "type": "rich",
        "flags": 0,
        "title": "Auto Moderation - External Server Invites",
        "color": discord.Color.red().value,
        "fields": [
            {"name": "User:", "value": "<@7> `(7)`", "inline": False},
            {"name": "Channel(s):", "value": "<#9>", "inline": False},
            {
                "name": "Message Content",
                "value": "join discord.gg/other now",
                "inline": False,
            },
        ],
        "footer": {"text": "Message deleted"},
    }


@pytest.mark.parametrize(
    "text", ["discord.com/invite/x", "discord.gg/x", "https://discordapp.com/invite/x"]
)
async def test_every_kind_of_invite_link_counts(chat, text):
    cog, server, log, staff = chat
    said = message(server, text)
    await cog.on_message(said)
    said.delete.assert_awaited_once_with()


async def test_invites_that_may_stay(chat):
    cog, server, log, staff = chat
    allowed = [
        message(server, "discord.gg/own2"),
        message(server, "DISCORD.GG/x"),
        message(server, "discord.com/channels/1/2"),
        message(server, "discord.gg/x", category=1281655927791030302),
        message(server, "discord.gg/x", category=1299725218767568997),
        message(server, "discord.gg/x", category=1281690196357808240),
        message(server, "discord.gg/x", category=1301601587059490836),
        message(server, "discord.gg/x", author=member(7, [staff[0]])),
        message(server, "discord.gg/x", author=member(7, [staff[1]])),
        message(guild(5), "discord.gg/x"),
    ]
    bot = message(server, "discord.gg/x")
    bot.author.bot = True
    for said in allowed + [bot]:
        await cog.on_message(said)
        said.delete.assert_not_awaited()
        said.channel.send.assert_not_awaited()
    log.send.assert_not_awaited()


async def test_a_server_with_no_invites_deletes_nothing(chat):
    cog, server, log, staff = chat
    server.invites.return_value = []
    said = message(server, "discord.gg/x")
    await cog.on_message(said)
    said.delete.assert_not_awaited()


async def test_a_direct_message_is_ignored(chat):
    cog = chat[0]
    said = message(None, "discord.gg/x -r1")
    await cog.on_message(said)
    said.channel.send.assert_not_awaited()


@pytest.fixture
def rules(chat):
    """The cog, the server, and the rules message with three rules."""
    cog, server, log, staff = chat
    place = MagicMock()
    place.fetch_message = AsyncMock(
        return_value=MagicMock(embeds=[discord.Embed(title=f"Rule {n}") for n in "123"])
    )
    cog.client.get_channel = MagicMock(return_value=place)
    cog.client.fetch_channel = AsyncMock(return_value=place)
    return cog, server, place


@pytest.mark.parametrize(
    "text, title", [("-r1", "Rule 1"), ("-R3", "Rule 3"), ("-r02", "Rule 2")]
)
async def test_a_rule_is_shown(rules, text, title):
    cog, server, place = rules
    said = message(server, text)
    await cog.on_message(said)
    cog.client.get_channel.assert_called_once_with(1281655927971250305)
    place.fetch_message.assert_awaited_once_with(1297054467107328000)
    assert said.channel.send.call_args.kwargs["embed"].title == title
    said.channel.send.assert_awaited_once()


async def test_the_rules_channel_is_fetched_when_not_cached(rules):
    cog, server, place = rules
    cog.client.get_channel.return_value = None
    said = message(server, "-r1")
    await cog.on_message(said)
    cog.client.fetch_channel.assert_awaited_once_with(1281655927971250305)
    assert said.channel.send.call_args.kwargs["embed"].title == "Rule 1"


@pytest.mark.parametrize("text", ["-r0", "-r11", "-r", "-r1 ", "-rule", "r1", "-r-1"])
async def test_other_text_is_not_a_rule(rules, text):
    cog, server, place = rules
    said = message(server, text)
    await cog.on_message(said)
    said.channel.send.assert_not_awaited()


async def test_a_missing_rule_is_said_and_stops_the_publish(rules):
    cog, server, place = rules
    said = message(server, "-r4", channel_id=1281673438435741696)
    await cog.on_message(said)
    said.channel.send.assert_awaited_once_with(
        "❌ That rule number doesn’t exist.", delete_after=10
    )
    said.publish.assert_not_awaited()


async def test_a_failed_rule_fetch_is_said(rules):
    cog, server, place = rules
    place.fetch_message.side_effect = RuntimeError("down")
    said = message(server, "-r1", channel_id=1281673438435741696)
    await cog.on_message(said)
    said.channel.send.assert_awaited_once_with(
        "⚠️ Failed to fetch the rule.", delete_after=10
    )
    said.publish.assert_awaited_once_with()


@pytest.mark.parametrize(
    "place",
    [
        1281673438435741696,
        1281675540511850639,
        1281675690416279633,
        1281675725216284753,
    ],
)
async def test_announcements_are_published(chat, place):
    cog, server, log, staff = chat
    said = message(server, "news", channel_id=place)
    said.publish.side_effect = RuntimeError("not a news channel")
    await cog.on_message(said)
    said.publish.assert_awaited_once_with()


async def test_other_messages_are_not_published(chat):
    cog, server, log, staff = chat
    elsewhere = message(server, "news")
    other_server = message(guild(5), "news", channel_id=1281673438435741696)
    bot = message(server, "news", channel_id=1281673438435741696)
    bot.author.bot = True
    for said in (elsewhere, other_server, bot):
        await cog.on_message(said)
        said.publish.assert_not_awaited()


# ---- Celestial ----

STAFF = celestial.STAFF_ROLES
ROSTER = (
    "**The following list consists of all our official staff members:**\n"
    f"\n<@&{STAFF[0]}> *(x2)*\n- <@1> `(1)`\n- <@2> `(2)`\n"
    f"\n<@&{STAFF[1]}> *(x0)*\n"
    f"\n<@&{STAFF[2]}> *(x0)*\n"
    f"\n<@&{STAFF[3]}> *(x0)*\n"
    f"\n<@&{STAFF[4]}> *(x0)*\n"
    f"\n`--------------------------------`\n\n<@&{STAFF[5]}> *(x1)*\n- <@3> `(3)`\n"
)


@pytest.fixture
def heaven():
    """Celestial with its six staff roles; the last one is the On Break role."""
    roles = [role(id, "Mod") for id in STAFF]
    roles[0].members = [member(1), member(2)]
    roles[5].name = "Staff On Break"
    roles[5].members = [member(3)]
    return guild(CELESTIAL, roles)


def check_roster(embed):
    assert embed.to_dict() == {
        "type": "rich",
        "flags": 0,
        "title": "Staff Roster",
        "description": ROSTER,
        "color": 0x46E1EC,
        "image": {
            "url": "https://media.discordapp.net/attachments/1152640894328127539/1199936623949926472/CelestialBanner.png"
        },
        "footer": {
            "text": 'Click "View Raw List" if text looks like <@692254240290242601>'
        },
    }


async def test_persistent_buttons_look_the_same():
    assert STAFF == [
        1180400455105384528,
        1176357434365841518,
        1200204308570980422,
        1178303001140666488,
        1188174906060439726,
        1239907587651276930,
    ]
    view = celestial.RefreshStaffViewCelestial()
    assert view.timeout is None
    assert [(b.label, b.custom_id, b.style, str(b.emoji)) for b in view.children] == [
        ("View Raw List", "rawcelestial", discord.ButtonStyle.blurple, "🗒️"),
        (
            "Refresh",
            "refreshcelestial",
            discord.ButtonStyle.grey,
            "<:refresh:1048779043287351408>",
        ),
    ]
    view = celestial.LeaksAccessCelestial()
    assert view.timeout is None
    assert [(b.label, b.custom_id, b.style, b.emoji) for b in view.children] == [
        (label, id, discord.ButtonStyle.red, None) for label, id in LEAKS
    ]
    view = levelUp.ShowPerksBulletin()
    assert view.timeout is None
    assert [(b.label, b.custom_id, b.style, str(b.emoji)) for b in view.children] == [
        (
            "View Level Roles & Perks",
            "showPerksBulletin",
            discord.ButtonStyle.grey,
            "<:info:1037445870469267638>",
        )
    ]


async def test_staff_posts_the_roster_after_loading_members(heaven):
    cog = celestial.StaffRoster(MagicMock())
    said = message(heaven, "-staff")
    await cog.on_message(said)
    heaven.chunk.assert_awaited_once_with()
    check_roster(said.channel.send.call_args.kwargs["embed"])
    assert isinstance(
        said.channel.send.call_args.kwargs["view"], celestial.RefreshStaffViewCelestial
    )
    said.delete.assert_not_awaited()


async def test_leaksaccess_swaps_the_message_for_the_panel(heaven):
    cog = celestial.StaffRoster(MagicMock())
    said = message(heaven, "-leaksaccess")
    await cog.on_message(said)
    said.delete.assert_awaited_once_with()
    sent = said.channel.send.call_args.kwargs
    assert sent["embed"].to_dict() == {
        "type": "rich",
        "flags": 0,
        "title": "<:RaidenJam:1343391073439060028> Select below to gain access to leaks-related channels!",
        "description": "By selecting the button(s), you acknowledge that leaked content remains unverified, subject to changes, and is against Hoyoverse's and/or Kuro Games' Terms of Service. We kindly request maintaining a respectful manner when discussing leaks. Please do not spread misinformation or share any unauthorized leaks, as it may result in a permanent removal of your access to the leaks channel.\n\n> **If you wish to remove your access to the leaks channel, you can simply click on the button(s) again.**",
        "color": 0x2B2C31,
    }
    assert isinstance(sent["view"], celestial.LeaksAccessCelestial)


async def test_celestial_words_do_nothing_elsewhere(heaven):
    cog = celestial.StaffRoster(MagicMock())
    bot = message(heaven, "-staff")
    bot.author.bot = True
    quiet = [
        message(guild(5), "-staff"),
        message(guild(5), "-leaksaccess"),
        message(heaven, "-staff "),
        message(heaven, "-Staff"),
        message(None, "-staff"),
        bot,
    ]
    for said in quiet:
        await cog.on_message(said)
        said.channel.send.assert_not_awaited()
        said.delete.assert_not_awaited()


async def test_refresh_redraws_the_roster(heaven):
    view = celestial.RefreshStaffViewCelestial()
    found = interaction(heaven)
    await view.refreshtt.callback(found)
    heaven.chunk.assert_not_awaited()
    check_roster(found.message.edit.call_args.kwargs["embed"])
    assert isinstance(
        found.message.edit.call_args.kwargs["view"], celestial.RefreshStaffViewCelestial
    )
    found.response.send_message.assert_awaited_once_with(
        "<:refresh:1048779043287351408> The staff list is successfully refreshed!",
        ephemeral=True,
    )


async def test_raw_list_redraws_and_shows_what_discord_kept(heaven):
    view = celestial.RefreshStaffViewCelestial()
    found = interaction(heaven)
    found.message.edit.return_value = MagicMock(
        embeds=[discord.Embed(title="Staff Roster", description=ROSTER.strip())]
    )
    await view.refreshstaffview.callback(found)
    check_roster(found.message.edit.call_args.kwargs["embed"])
    found.response.send_message.assert_awaited_once_with(
        "Staff Roster\n**The following list consists of all our official staff members:**\n"
        f"\n<@&{STAFF[0]}> *(x2)*\n- <@1> \n- <@2> \n"
        f"\n<@&{STAFF[1]}> *(x0)*\n\n<@&{STAFF[2]}> *(x0)*\n\n<@&{STAFF[3]}> *(x0)*\n"
        f"\n<@&{STAFF[4]}> *(x0)*\n\n\n\n<@&{STAFF[5]}> *(x1)*\n- <@3> ",
        ephemeral=True,
    )


GAMES = [
    (
        0,
        "Access Genshin Leaks",
        "<@&1324391617938985023>",
        "Genshin Impact",
        "<#1261243694468698112>",
        "<#1383774520032100352>",
    ),
    (
        1,
        "Access HSR Leaks",
        "<@&1324391720040923258>",
        "Honkai: Star Rail",
        "<#1310928513876099143>",
        "<#1383774549497221261>",
    ),
    (
        2,
        "Access WuWa Leaks",
        "<@&1360288374027583580>",
        "Wuthering Waves",
        "<#1357905859791032630>",
        "<#1383774575069761547>",
    ),
    (
        3,
        "Access ZZZ Leaks",
        "<@&1428330808174841918>",
        "Zenless Zone Zero",
        "<#1428330534093983744>",
        "<#1428824981114060844>",
    ),
]


@pytest.mark.parametrize("button, name, mention, game, leaks, talk", GAMES)
async def test_a_leaks_button_gives_then_takes_the_role(
    button, name, mention, game, leaks, talk
):
    wanted, other = role(1, name), role(2, "Access Leaks")
    server = guild(CELESTIAL, [other, wanted])
    press = celestial.LeaksAccessCelestial().children[button].callback

    user = member(7, [other])
    found = interaction(server, user)
    await press(found)
    user.add_roles.assert_awaited_once_with(wanted)
    user.remove_roles.assert_not_awaited()
    found.response.send_message.assert_awaited_once_with(
        f"You have **obtained** the {mention} role. You can now access {game} leaks at {leaks} and discuss them at {talk}!",
        ephemeral=True,
    )

    user = member(7, [other, wanted])
    found = interaction(server, user)
    await press(found)
    user.remove_roles.assert_awaited_once_with(wanted)
    user.add_roles.assert_not_awaited()
    found.response.send_message.assert_awaited_once_with(
        f"You **no longer** have the {mention} role, and you can no longer access {game} leaks.",
        ephemeral=True,
    )


# ---- Level-up cards ----


class Asset:
    """A Discord picture that reads as a plain square, fails, or arrives cut off."""

    def __init__(self, size, fail=False, cut=False):
        self.size, self.fail, self.cut = size, fail, cut

    def with_static_format(self, kind):
        assert kind == "png"
        return self

    def with_size(self, size):
        assert size == 256
        return self

    async def read(self):
        if self.fail:
            raise discord.HTTPException(MagicMock(status=500), "down")
        file = io.BytesIO()
        Image.new("RGB", (self.size, self.size), (200, 30, 90)).save(file, "PNG")
        return file.getvalue()[:60] if self.cut else file.getvalue()


@pytest.fixture
def cards(monkeypatch):
    """The cog with small blank backgrounds, no waiting and a recorded Mora call."""
    blank = Image.new("RGB", (1500, 600), (20, 20, 20))
    open_image = Image.open
    monkeypatch.setattr(
        levelUp.Image,
        "open",
        lambda source: blank.copy() if isinstance(source, str) else open_image(source),
    )
    font = ImageFont.load_default()
    monkeypatch.setattr(levelUp.ImageFont, "truetype", lambda path, size: font)
    monkeypatch.setattr(levelUp.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(levelUp, "addMora", AsyncMock())
    bot = MagicMock()
    return levelUp.LevelUpTrigger(bot)


def levelled(role_name, avatar=None, icon=None):
    found = member(7, [role(1, "@everyone"), role(2, role_name)])
    found.avatar = avatar or Asset(256)
    found.roles[1].icon = icon or Asset(64)
    return found


def bulletin_notice(level, method="text", who=None):
    out = channel(1281687605548945428)
    server = guild(BULLETIN, channels=[out])
    server.fetch_member.return_value = who or levelled("Furina - Level 50")
    said = message(
        server,
        "<@7>",
        author=member(989173789482975262),
        channel_id=1335828558190215259,
    )
    said.embeds = [
        discord.Embed(
            description=f"<@7> has levelled up from {method} level {level - 1} to {level}!"
        )
    ]
    return said, out


def jinhsi_notice(level, who=None):
    out = channel(1197491635710332996)
    server = guild(JINHSI, channels=[out])
    server.fetch_member.return_value = who or levelled("Elder (LV 30)")
    said = message(
        server,
        f"GG **<@7>**, you just advanced to level **{level}** and has reached a new rank!",
        author=member(437808476106784770),
        channel_id=1356789459370119371,
    )
    return said, out


async def test_bulletin_card_with_a_new_role(cards):
    said, out = bulletin_notice(10)
    await cards.on_message(said)
    said.guild.fetch_member.assert_awaited_once_with(7)
    levelUp.asyncio.sleep.assert_awaited_once_with(3)
    levelUp.addMora.assert_awaited_once_with(cards.client.pool, 7, 3000, 2, BULLETIN)
    (text,), sent = out.send.call_args
    assert text == (
        "<@7> has reached level **10** in text! GG!\n<:reply:1036792837821435976> *You've earned the **`Clorinde - Level 10`** role and <:MORA:1364030973611610205> `3000` for levelling up!*"
    )
    assert sent["file"].filename == "bulletin-levelup.png"
    assert Image.open(sent["file"].fp).size == (1500, 600)
    assert isinstance(sent["view"], levelUp.ShowPerksBulletin)


async def test_bulletin_card_without_a_new_role(cards):
    said, out = bulletin_notice(11, "voice")
    await cards.on_message(said)
    levelUp.addMora.assert_awaited_once_with(cards.client.pool, 7, 3300, 2, BULLETIN)
    assert out.send.call_args.args == (
        "<@7> has reached level **11** in voice! GG!\n<:reply:1036792837821435976> *You've earned <:MORA:1364030973611610205> `3300` for levelling up.*",
    )


@pytest.mark.parametrize(
    "who",
    [
        levelled("Member"),
        levelled("Furina - Level 50", avatar=Asset(256, fail=True)),
        levelled("Furina - Level 50", icon=Asset(64, fail=True)),
    ],
)
async def test_bulletin_card_needs_a_level_role_an_avatar_and_an_icon(cards, who):
    said, out = bulletin_notice(10, who=who)
    with pytest.raises(Exception):
        await cards.on_message(said)
    out.send.assert_not_awaited()
    levelUp.addMora.assert_not_awaited()


async def test_bulletin_tables_are_the_same():
    assert levelUp.BULLETIN_ROLES == {
        100: "Wriothesley - Level 100",
        90: "Dainsleif - Level 90",
        80: "Tsaritsa - Level 80",
        69: "Mavuika - Level 69",
        60: "Neuvillette - Level 60",
        50: "Furina - Level 50",
        40: "Nahida - Level 40",
        30: "Raiden - Level 30",
        25: "Zhongli - Level 25",
        20: "Venti - Level 20",
        15: "M - Level 15",
        10: "Clorinde - Level 10",
        5: "Sigewinne - Level 5",
        3: "Melusine - Level 3",
        1: "Slime - Level 1",
    }
    assert levelUp.BULLETIN_PERKS == {
        100: "Access to #exclusive chat & +1 entry in giveaways (6 total)",
        90: "Priority speaker in stage channels",
        80: "Request to speak in stage channels & +1 entry in giveaways (5 total)",
        69: "Ability to set custom voice channel status",
        60: "+1 entry in giveaways (4 entries total)",
        50: "Access to #xp-farm channel",
        40: "Send text-to-speech messages & +1 entry in giveaways (3 total)",
        30: "Ability to create private threads",
        25: "Ability to create public threads",
        20: "Qualified to apply for staff & +1 entry in giveaways (2 total)",
        15: "Ability to create polls",
        10: "Ability to send voice messages",
        5: "Access to embed links and GIFS in chats",
        3: "Access to upload attachments in chats",
        1: "Edit nickname & create invite",
    }


@pytest.mark.parametrize(
    "who",
    [
        None,
        levelled("Member"),
        levelled("LV 5", avatar=Asset(256, fail=True), icon=Asset(64, fail=True)),
        levelled("LV 5", icon=Asset(64, cut=True)),
    ],
)
async def test_jinhsi_card_is_sent_whatever_is_missing(cards, who):
    said, out = jinhsi_notice(12, who)
    await cards.on_message(said)
    said.guild.fetch_member.assert_awaited_once_with(7)
    levelUp.asyncio.sleep.assert_awaited_once_with(2)
    levelUp.addMora.assert_awaited_once_with(cards.client.pool, 7, 3600, 2, JINHSI)
    (text,), sent = out.send.call_args
    assert text == said.content
    assert sent["file"].filename == "jinhsi-levelup.png"
    assert Image.open(sent["file"].fp).size == (1500, 600)
    assert "view" not in sent


async def test_other_messages_draw_no_card(cards):
    wrong_author, out1 = bulletin_notice(10)
    wrong_author.author.id = 5
    wrong_place, out2 = bulletin_notice(10)
    wrong_place.channel.id = 5
    no_rank, out3 = jinhsi_notice(10)
    no_rank.content = "GG **<@7>**, level **10**"
    wrong_bot, out4 = jinhsi_notice(10)
    wrong_bot.author.id = 989173789482975262
    own, out5 = bulletin_notice(10)
    own.author = cards.client.user
    for said, out in [
        (wrong_author, out1),
        (wrong_place, out2),
        (no_rank, out3),
        (wrong_bot, out4),
        (own, out5),
    ]:
        await cards.on_message(said)
        out.send.assert_not_awaited()
    levelUp.addMora.assert_not_awaited()


async def test_perks_button_explains_the_roles():
    found = interaction(guild(BULLETIN))
    found.guild.name = "Meropide Bulletin"
    await levelUp.ShowPerksBulletin().showPerksBulletin.callback(found)
    sent = found.response.send_message.call_args.kwargs
    assert sent["ephemeral"] is True
    assert sent["embed"].title == "❤︎ Level Roles & Perks - Meropide Bulletin ❤︎"
    text = sent["embed"].description
    assert text.startswith("As you yap in this server, you gain points known as XP.")
    assert text.endswith(
        "<:reply:1036792837821435976> +1 Entry in Giveaways (6 entries total)"
    )
    assert hashlib.sha256(text.encode()).hexdigest() == (
        "196c86f448333c637fa201cfb0640beca3f5a178abee0f5db10255a001835b80"
    )
