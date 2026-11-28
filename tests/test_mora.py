import asyncio
import datetime
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events import config, helperFunctions, mora, quests

GUILD, USER, OTHER, CHANNEL = 10, 20, 21, 30
NO = config.NO_EMOTE
MORA = config.MORA_EMOTE
TODAY = datetime.datetime.now(datetime.timezone.utc).date()


class Role:
    def __init__(self, id):
        self.id, self.mention = id, f"<@&{id}>"


class Member:
    def __init__(self, guild, id, roles=(), bot=False):
        self.guild, self.id, self.bot = guild, id, bot
        self.display_name, self.mention = f"Name{id}", f"<@{id}>"
        self.roles = list(roles)

    def __eq__(self, other):
        return self.id == other.id


class Sent:
    """What one interaction answered with."""

    def __init__(self, game, user, custom_id=None):
        self.user, self.guild, self.client = user, game.guild, game
        self.channel = SimpleNamespace(id=CHANNEL)
        self.data = {"custom_id": custom_id}
        self.said, self.edits, self.modals, self.followups = [], [], [], []
        self.response = SimpleNamespace(
            defer=AsyncMock(),
            send_message=self.say,
            edit_message=self.edit,
            send_modal=self.open,
        )
        self.followup = SimpleNamespace(send=self.follow)

    async def say(self, text, ephemeral=False):
        self.said.append(text)

    async def edit(self, **shown):
        self.edits.append(shown)

    async def open(self, modal):
        self.modals.append(modal)

    async def follow(self, content=None, **shown):
        self.followups.append((content, shown))
        return SimpleNamespace(edit=AsyncMock())


@pytest.fixture
async def game(pool, monkeypatch, tmp_path):
    """A bot on an empty database with the minigame tables, one server and two members."""
    bot = MagicMock(pool=pool)
    bot.add_cog = AsyncMock()
    await helperFunctions.setup(bot)
    await quests.setup(bot)
    monkeypatch.setattr(helperFunctions, "delayed_check_milestones", AsyncMock())
    bot.roles = {501: Role(501), 502: Role(502)}
    bot.guild = SimpleNamespace(
        id=GUILD,
        name="Server",
        get_role=bot.roles.get,
        get_channel=lambda id: SimpleNamespace(name="general"),
    )
    bot.me = Member(bot.guild, USER)
    bot.friend = Member(bot.guild, OTHER)
    bot.user = SimpleNamespace(id=999)
    bot.images = []

    async def send(file):
        bot.images.append(file)
        return SimpleNamespace(
            attachments=[SimpleNamespace(proxy_url=f"link/{file.filename}")]
        )

    bot.get_channel = lambda id: SimpleNamespace(send=send)
    bot.get_cog = lambda name: None
    bot.cards = []

    async def draw(user, *numbers, **look):
        bot.cards.append((numbers, look))
        card = io.BytesIO(b"card")
        card.name = "card.png"
        return card

    monkeypatch.setattr(mora, "createProfileCard", draw)
    monkeypatch.setattr(
        mora, "draw_earnings", lambda history, name: io.BytesIO(b"graph")
    )
    bot.cog = mora.Mora(bot)
    return bot


async def earn(pool, user, amount, guild=GUILD, when=1_700_000_000):
    await pool.execute(
        "INSERT INTO minigame_mora (uid, gid, cid, timestamp, count) VALUES ($1, $2, $3, $4, $5)",
        user,
        guild,
        CHANNEL,
        when,
        amount,
    )


async def balance(pool, user):
    return await helperFunctions.get_guild_mora(pool, user, GUILD)


async def chests(pool, streak, longest, last, user=USER):
    await pool.execute(
        "INSERT INTO minigame_chests (gid, uid, streak, max_streak, last_claimed, counts) VALUES ($1, $2, $3, $4, $5, $6)",
        GUILD,
        user,
        streak,
        longest,
        last,
        [3, 1],
    )


async def progress(pool, user=USER, **columns):
    await helperFunctions.ensure_progression_user(pool, GUILD, user)
    for column, value in columns.items():
        await pool.execute(
            f"UPDATE minigame_progression SET {column} = $1 WHERE gid = $2 AND uid = $3",
            value,
            GUILD,
            user,
        )


async def open_mora(game, target=None, user=None):
    """Runs /mora and gives the interaction, its embed and its view."""
    sent = Sent(game, user or game.me)
    await game.cog.mora.callback(game.cog, sent, target)
    shown = sent.followups[0][1]
    return sent, shown["embed"], shown["view"]


async def press(game, view, custom_id, user=None, choice=None):
    """Presses a button or picks from the menu of a view, as Discord would."""
    sent = Sent(game, user or game.me, custom_id)
    item = next(child for child in view.children if child.custom_id == custom_id)
    if await view.interaction_check(sent):
        if choice:
            item._values = [choice]
        await item.callback(sent)
    return sent


def fields(embed):
    return {field.name: field.value for field in embed.fields}


async def test_standing_counts_a_members_total_and_place(game):
    await earn(game.pool, USER, 500)
    await earn(game.pool, USER, 200, when=5)
    await earn(game.pool, USER, 1000, guild=11)
    await earn(game.pool, OTHER, 900)
    assert await mora.standing(game.pool, "minigame_mora", "count", USER) == (1700, 1)
    assert await mora.standing(game.pool, "minigame_mora", "count", USER, GUILD) == (
        700,
        2,
    )
    assert await mora.standing(game.pool, "minigame_mora", "count", 5) == (0, "N/A")
    assert await mora.standing(game.pool, "minigame_sigils", "earnings", USER) == (
        0,
        "N/A",
    )


async def test_mora_of_a_new_member_shows_no_totals_and_a_tip(game):
    sent, embed, view = await open_mora(game)
    assert embed.title == "Name20's Inventory in Server"
    assert fields(embed) == {
        "Guild Inventory": "No `/shop` items purchased yet",
        "Guild Milestones": "No `/milestones` earned yet",
    }
    assert embed.image.url == "link/card.png"
    assert game.cards == [
        (
            ("0", "N/A", "0", "N/A", "0", "N/A", "0", "N/A"),
            {"accent_color_hex": None, "font_name": None},
        )
    ]
    assert sent.followups[1][0].startswith("💡 Tip: Customize your inventory")
    assert [child.label for child in view.children] == [
        "Inventory",
        "Stats",
        "Track",
        "Quests",
        config.KINGDOM_NAME,
        config.SIGIL_CURRENCY_NAME,
        "Settings",
        "Earn Daily Rewards",
        "Elite Track",
    ]


async def test_mora_shows_totals_items_milestones_title_and_kingdom(game):
    pool = game.pool
    await earn(pool, USER, 2500)
    await earn(pool, OTHER, 9000)
    await pool.execute(
        "INSERT INTO minigame_sigils VALUES ($1, $2, '2026-01-01', 40)", USER, GUILD
    )
    for title, cost, when, pinned in (
        ("501", 100, 50, False),
        ("501", 100, 40, False),
        ("Hat", 300, 60, True),
        ("Winner", 0, 70, False),
    ):
        await helperFunctions.add_inventory_item(
            pool, USER, GUILD, title, "about", cost, when, pinned
        )
    await pool.execute(
        "INSERT INTO minigame_rewards (gid, item_type, name, description, threshold) VALUES ($1, 'milestone', 'Winner', 'd', 2000), ($1, 'milestone', 'Later', 'd', 9999)",
        GUILD,
    )
    await pool.execute(
        "INSERT INTO minigame_cosmetics (gid, uid, titles, selected_title, selected_profile_frame, selected_font, selected_embed_color_hex) VALUES ($1, $2, $3, '7', 'gold', 'Fancy', 'ff0000')",
        GUILD,
        USER,
        [["7", "Liyue Harbor"]],
    )
    await progress(pool, kingdom_schloss=2)

    sent, embed, view = await open_mora(game, game.me, user=game.friend)

    assert embed.description == "### <:rank:1364439165189488854>Liyue Harbor\n"
    assert fields(embed) == {
        "Server": f"{config.GUILD_MORA_EMOTE} Mora: **`2,500`**\n{config.GUILD_SIGIL_EMOTE} Sigils: **`40`**",
        "Global": f"{config.GLOBAL_MORA_EMOTE} Mora: **`2,500`**\n{config.GLOBAL_SIGIL_EMOTE} Sigils: **`40`**",
        "Guild Inventory": "📌 **Pinned:** Hat - *Acquired <t:60:R>*\n- <@&501> **(x2)** - *First acquired <t:40:R>*",
        "Guild Milestones": f"- Winner - *Earned at {MORA} `2,000` <t:70:R>*\n",
    }
    assert embed.footer.text.startswith(f"{config.KINGDOM_NAME} Rank: ")
    assert embed.color == discord.Color.gold()  # the colour and font are Elite only
    numbers, look = game.cards[0]
    assert numbers == ("2,500", 2, "40", 1, "2,500", 2, "40", 1)
    assert look == {
        "accent_color_hex": None,
        "font_name": None,
        "bg": f"{config.INVENTORY_BG_PATH}/{USER}.png",
        "profile_frame": "gold",
    }
    assert len(sent.followups) == 1  # no tip for a customized inventory


async def test_mora_of_an_elite_member_uses_their_colour_and_font(game):
    await game.pool.execute(
        "INSERT INTO minigame_cosmetics (gid, uid, selected_font, selected_embed_color_hex) VALUES ($1, $2, 'Fancy', 'ff0000')",
        GUILD,
        USER,
    )
    await game.pool.execute(
        "INSERT INTO minigame_elite (user_id, guild_id, expires_at) VALUES ($1, $2, 99999999999)",
        USER,
        GUILD,
    )
    _, embed, view = await open_mora(game)
    assert embed.color.value == 0xFF0000
    assert game.cards[0][1] == {"accent_color_hex": "ff0000", "font_name": "Fancy"}
    assert view.children[-1].label == "Elite Patron"


def test_inventory_text_is_cut_to_one_field():
    items = [(f"Item {n:03}", "", 5, GUILD, n, False, None) for n in range(60)]
    text = mora.inventory_text(items)
    assert len(text) <= 1024
    shown = text.count("Acquired")
    assert text.endswith(f"*({60 - shown} more...)*")
    assert text.startswith("- Item 000 - *Acquired <t:0:R>*\n- Item 001")


def test_title_line_prefers_the_custom_title():
    titles = [["1", "Plain"], ["2", "<a:x:1> Moving"]]
    assert mora.title_line({}) is None
    assert mora.title_line({"selected_custom_title": "Mine"}) == "### Mine"
    assert (
        mora.title_line({"titles": titles, "selected_title": "1"})
        == "### <:rank:1364439165189488854>Plain"
    )
    assert (
        mora.title_line({"titles": titles, "selected_title": "2"})
        == "### <a:x:1> Moving"
    )
    assert mora.title_line({"titles": titles, "selected_title": "9"}) is None
    assert mora.title_line({"titles": None, "selected_title": "9"}) is None


def test_streak_state_breaks_after_a_missed_day():
    day = datetime.timedelta(days=1)
    saved = {"streak": 4, "max_streak": 9, "last_claimed": (TODAY - day).isoformat()}
    assert mora.streak_state(saved) == (4, 9, False)
    saved["last_claimed"] = TODAY - 2 * day
    assert mora.streak_state(saved) == (0, 9, True)
    assert mora.streak_state({}) == (0, 0, True)
    assert mora.days(0) == "`0` days" and mora.days(1) == "`1` day"


async def test_only_the_caller_uses_the_tabs_but_anyone_opens_elite(game):
    _, embed, view = await open_mora(game)
    sent = await press(game, view, "settings", user=game.friend)
    assert sent.said == ["You can't use this button!"] and view.state == "home"

    buy = view.children[-1]
    buy.callback = AsyncMock()
    await press(game, view, buy.custom_id, user=game.friend)
    buy.callback.assert_awaited_once()


async def test_tabs_mark_the_open_one_and_home_returns(game):
    _, home, view = await open_mora(game)
    sent = await press(game, view, "track")
    assert sent.edits[0]["embed"].title == "Name20's Progression Track in Server"
    assert [child.custom_id for child in view.children if child.disabled] == ["track"]
    sent = await press(game, view, "home")
    assert sent.edits[0]["embed"] is home
    assert [child.custom_id for child in view.children if child.disabled] == ["home"]


async def test_stats_tab_needs_earnings_then_posts_the_graph(game):
    _, _, view = await open_mora(game)
    sent = await press(game, view, "graph")
    assert sent.said == ["No data available! Start playing to see your stats."]

    await earn(game.pool, USER, 500)
    await chests(game.pool, 0, 0, None)
    sent = await press(game, view, "graph")
    embed = sent.edits[0]["embed"]
    assert embed.title == "Name20's Player Statistics in Server"
    assert embed.image.url == f"link/{USER}.png"
    assert game.images[-1].fp.read() == b"graph"
    chest_line = embed.fields[0]
    assert chest_line.inline is False and embed.fields[1].inline is True
    assert chest_line.value.endswith(
        f"\n**Total:** `4` {config.EMOTE_BLANK}{config.EMOTE_STREAK} `0` days {config.EMOTE_BLANK}{config.EMOTE_MAX_STREAK} `0` days"
    )
    assert fields(embed)["`✌️` Minigame Wins"] == "`-3` total wins"


def test_draw_earnings_gives_a_png():
    image = mora.draw_earnings([(1_700_000_000, 50), (1_700_090_000, 2_000_000)], "Me")
    assert image.read(8) == b"\x89PNG\r\n\x1a\n"


async def test_track_tab_shows_tier_progress_and_perks(game, monkeypatch):
    track = [
        {
            "tier": n,
            "xp_req": 100,
            "cumulative_xp": 100 * n,
            "free": f"F{n}",
            "elite": "Title | x",
        }
        for n in range(1, 7)
    ]
    season = SimpleNamespace(id=6, name="Test", end_ts=99)
    monkeypatch.setattr(mora, "get_current_track", lambda: track)
    monkeypatch.setattr(mora, "get_current_season", lambda: season)
    await progress(game.pool, xp=250, prestige=2, gift_tax=15)
    embed = await mora.track_embed(game.pool, game.me, None)
    assert (
        "+ Current Tier: 2 (250 total XP)\n- Status: Free Track Only\n\n Next Tier: 50 / 100 XP\n"
        in embed.description
    )
    assert f" 𝟐 {'━' * 10}{'-' * 10} 𝟑\n" in embed.description
    assert "\u001b[1;37m 2\u001b[0m  ✅  F2" in embed.description
    assert "\u001b[1;37m 3\u001b[0m  🔄  F3" in embed.description
    assert "\u001b[1;37m 5\u001b[0m  🔐  F5" in embed.description
    assert "... (1 more)\n```" in embed.description
    assert "\u001b[1;2m\u001b[1;36mTitle\u001b[0m\u001b[0m" in embed.description
    shown = fields(embed)
    assert shown[":gift: Gift Tax"] == "`15%`"
    assert shown[f"{config.PRESTIGE_EMOTE} Prestige"] == "`2`"
    assert shown["🎨 Custom Accent Color"] == "`Not unlocked`"
    assert mora.tier_reached(track, 99) == 0 and mora.tier_reached(track, 9999) == 6


async def test_quests_tab_without_quests_names_no_past_season(game, monkeypatch):
    monkeypatch.setattr(mora, "update_quest", AsyncMock())
    monkeypatch.setattr(mora, "SEASONS", [SimpleNamespace(start_ts=5)])
    embed = await mora.quests_embed(game, game.me, CHANNEL, None)
    assert embed.description == "No active quests."
    monkeypatch.setattr(mora, "SEASONS", [SimpleNamespace(start_ts=9_999_999_999)])
    embed = await mora.quests_embed(game, game.me, CHANNEL, None)
    assert (
        embed.description
        == "No active quests. The next season starts <t:9999999999:R>."
    )


async def test_sigils_tab_is_about_the_member_shown(game):
    pool = game.pool
    game.friend.roles = [game.roles[501], game.roles[502]]
    await pool.execute(
        "INSERT INTO minigame_settings (channel_id, chat_boosted_roles, chat_msg_range) VALUES ($1, $2, $3)",
        CHANNEL,
        ["501:102", "502:+5", "777:900"],
        [7],
    )
    await pool.execute(
        "INSERT INTO minigame_sigils VALUES ($1, $2, $3, 12)",
        OTHER,
        GUILD,
        TODAY.isoformat(),
    )
    _, _, view = await open_mora(game, game.friend)
    sent = await press(game, view, "sigils")
    embed = sent.edits[0]["embed"]
    assert embed.title == "Name21's Sigils in Server"
    shown = fields(embed)
    assert shown["Daily Chat Progress"] == "`12/107` Sigils earned"
    assert shown["Role Bonuses to Max Sigils"] == (
        f"{config.DOT_EMOTE} <@&501>: `102` {config.YES_EMOTE}\n"
        f"{config.DOT_EMOTE} <@&502>: `+5` {config.YES_EMOTE}"
    )
    assert "sending 7 messages" in embed.footer.text


async def test_sigils_tab_counts_a_role_gained_since_the_command(game):
    await game.pool.execute(
        "INSERT INTO minigame_settings (channel_id, chat_boosted_roles) VALUES ($1, $2)",
        CHANNEL,
        ["501:+10"],
    )
    _, _, view = await open_mora(game, game.me)
    now = Member(game.guild, USER, roles=[game.roles[501]])
    embed = (await press(game, view, "sigils", user=now)).edits[0]["embed"]
    assert fields(embed)["Daily Chat Progress"] == "`0/70` Sigils earned"


async def test_settings_tab_turns_a_feature_off_and_on(game):
    flags = []
    game.get_cog = lambda name: SimpleNamespace(
        chest_system=SimpleNamespace(
            invalidate_flag_cache=lambda guild, user: flags.append((guild, user))
        )
    )
    _, _, view = await open_mora(game)
    sent = await press(game, view, "settings")
    assert sent.edits[0]["embed"].fields[1].name == "#general (Current Channel)"
    assert [option.value for option in view.select.options] == list(mora.SETTINGS)

    sent = await press(game, view, "settings_select", choice="toggle_sigils_spawn")
    assert (
        sent.followups[0][0]
        == f"{config.YES_EMOTE} Sigils chat earning is now **disabled**!"
    )
    own = await helperFunctions.get_user_minigame_settings(game.pool, GUILD, USER)
    assert own == {
        "chest_disabled": False,
        "minigame_disabled": False,
        "sigils_disabled": True,
    }
    assert flags == [(GUILD, USER)]
    assert config.NO_EMOTE_2 in sent.edits[0]["embed"].fields[0].value

    sent = await press(game, view, "settings_select", choice="toggle_sigils_spawn")
    assert sent.followups[0][0].endswith("is now **enabled**!")


async def test_someone_elses_kingdom_and_settings_are_read_only(game):
    _, _, view = await open_mora(game, game.friend)
    await press(game, view, "domain")
    assert (
        view.select.disabled
        and view.select.custom_id == "kingdom_upgrade_select_disabled"
    )
    await press(game, view, "settings")
    assert view.select.disabled and view.select.custom_id == "settings_select_disabled"
    await press(game, view, "home")
    assert view.select is None and len(view.children) == 9


async def test_kingdom_tab_lists_upgrades_with_the_discount(game):
    await progress(game.pool, kingdom_schloss=1, domain_discount=10)
    _, _, view = await open_mora(game)
    await press(game, view, "domain")
    first = view.select.options[0]
    cost = mora.calculate_cost(1)
    assert first.value == "upgrade_schloss"
    assert (
        first.description
        == f"Lv. 1 ➜ Lv. 2 | Cost: {mora.apply_discount(cost, 10):,} (discounted)"
    )
    assert (
        view.select.options[1].description
        == f"Lv. 0 ➜ Lv. 1 | Cost: {mora.apply_discount(mora.calculate_cost(0), 10):,} (discounted)"
    )


async def test_timeout_greys_the_tabs_but_not_the_next_views_link(game):
    _, _, view = await open_mora(game)
    await view.on_timeout()
    assert all(child.disabled for child in view.children)
    view.message.edit.assert_awaited_once_with(view=view)
    _, _, later = await open_mora(game)
    assert later.children[7].label == "Earn Daily Rewards"
    assert not later.children[7].disabled


async def gift(game, target, amount):
    sent = Sent(game, game.me)
    await game.cog.gift.callback(game.cog, sent, target, amount)
    return sent.followups[0]


async def test_gift_refuses_what_cannot_be_given(game):
    assert (await gift(game, game.friend, 500))[0].startswith(
        "⏳ You haven't unlocked gifting"
    )
    await progress(game.pool, gift_tax=20)
    assert (await gift(game, game.friend, 0))[
        0
    ] == f"{NO} Amount must be positive and non-zero!"
    assert (await gift(game, game.friend, 99))[
        0
    ] == f"{NO} The minimum amount to gift is {MORA} `100`!"
    assert (await gift(game, game.me, 500))[
        0
    ] == f"{NO} You can't gift {MORA} to yourself!"
    robot = Member(game.guild, 77, bot=True)
    assert (await gift(game, robot, 500))[0].endswith("on a non-human being?")
    await earn(game.pool, USER, 599)
    assert (await gift(game, game.friend, 500))[0] == (
        f"You need {MORA} `600` (500 + 20% tax) to make this gift! \n-# You currently only have {MORA} `599`."
    )
    assert await balance(game.pool, OTHER) == 0


async def test_gift_moves_mora_pays_tax_and_counts_quests(game, monkeypatch):
    counted = AsyncMock()
    monkeypatch.setattr(mora, "update_quest", counted)
    await progress(game.pool, gift_tax=20)
    await progress(game.pool, user=OTHER, mora_boost=50)
    await earn(game.pool, USER, 1000)
    content, shown = await gift(game, game.friend, 500)
    assert (
        content
        == f"<@{OTHER}> has been blessed by <@{USER}>! <a:2_star:1366158196213022800>"
    )
    assert f"**Total Deducted:** {MORA} `600`" in shown["embed"].description
    assert f"collected {MORA} `100` (20%) in taxes" in shown["embed"].description
    assert await balance(game.pool, USER) == 400
    assert await balance(game.pool, OTHER) == 500  # a gift is not boosted
    assert await balance(game.pool, 999) == 100
    counted.assert_awaited_once_with(
        USER,
        GUILD,
        CHANNEL,
        {"gift_mora": 500, "gift_mora_unique": OTHER, "gift_mora_poorer": 1},
        game,
    )


async def streak(game):
    sent = Sent(game, game.me)
    await game.cog.streak.callback(game.cog, sent)
    return sent.followups[0][1]


async def test_streak_that_holds_has_nothing_to_restore(game):
    await chests(game.pool, 3, 8, TODAY.isoformat())
    shown = await streak(game)
    assert "view" not in shown
    assert fields(shown["embed"]) == {
        f"`📦` {config.MORA_CHEST_NAME}s": shown["embed"].fields[0].value,
        "Current Streak": f"{config.EMOTE_STREAK} `3` days",
        "Max Streak": f"{config.EMOTE_MAX_STREAK} `8` days",
    }
    assert shown["embed"].fields[0].value.endswith("\n**Total:** `4`")


async def test_broken_streak_is_restored_for_mora(game):
    old = (TODAY - datetime.timedelta(days=5)).isoformat()
    await chests(game.pool, 3, 8, old)
    await earn(game.pool, USER, 25_000)
    shown = await streak(game)
    assert shown["embed"].fields[3].value == (
        f"You can restore up to `8` days back towards your max streak.\n-# Costs {MORA} `10,000` per day restored."
    )
    view = shown["view"]

    stranger = Sent(game, game.friend)
    await view.restore_button.callback(stranger)
    assert stranger.said == ["You can't use this button!"]
    opened = Sent(game, game.me)
    await view.restore_button.callback(opened)
    modal = opened.modals[0]
    assert modal.days.placeholder == "Enter number of days between 1 and 8"

    async def submit(text):
        modal.days._value = text
        sent = Sent(game, game.me)
        await modal.on_submit(sent)
        return sent

    assert (await submit("two")).said == [f"{NO} Please enter a whole number!"]
    assert (await submit("0")).said == [f"{NO} You need to restore at least `1` day!"]
    assert (await submit("9")).said == [f"{NO} You can only restore up to `8` days!"]
    assert (await submit("3")).said == [
        f"{NO} Restoring `3` days costs {MORA} `30,000`, but you only have {MORA} `25,000`!"
    ]
    done = await submit("2")
    assert done.edits[0]["view"] is None
    assert done.edits[0]["embed"].description == (
        f"{config.EMOTE_STREAK} **New Streak:** `2` days\n"
        f"{config.EMOTE_MAX_STREAK} **Max Streak:** `8` days\n"
        f"{MORA} **Cost Paid:** `20,000`"
    )
    assert await balance(game.pool, USER) == 5_000
    saved = await helperFunctions.get_chest_streaks(game.pool, GUILD, USER)
    assert saved == {"streak": 2, "max_streak": 8, "last_claimed": TODAY.isoformat()}
    await earn(game.pool, USER, 10_000, when=7)
    assert (await submit("1")).said == [
        f"{NO} Your streak isn't broken anymore, there's nothing to restore!"
    ]

    assert view.is_finished()


async def test_restore_button_greys_out_when_left_alone(game):
    old = (TODAY - datetime.timedelta(days=5)).isoformat()
    await chests(game.pool, 3, 8, old)
    view = (await streak(game))["view"]
    assert not view.is_finished()
    await view.on_timeout()
    assert view.restore_button.disabled
    view.message.edit.assert_awaited_once_with(view=view)


async def test_fixstreak_is_for_the_owner(game):
    await earn(game.pool, USER, 500)
    stranger = Sent(game, game.friend)
    await game.cog.fixstreak.callback(game.cog, stranger, game.me, 5, 9, 100)
    assert stranger.followups == [] and await balance(game.pool, USER) == 500

    owner = SimpleNamespace(id=mora.FIXSTREAK_OWNER_ID)

    async def fix(*values):
        sent = Sent(game, owner)
        await game.cog.fixstreak.callback(game.cog, sent, game.me, *values)
        return sent.followups[0]

    assert (await fix(-1, 2))[0] == f"{NO} Streak values can't be negative!"
    assert (await fix(1, 2, -5))[0] == f"{NO} Mora to deduct can't be negative!"
    assert (await fix(1, 2, 501))[0].startswith(f"{NO} <@{USER}> only has {MORA} `500`")
    _, shown = await fix(5, 9, 100)
    assert shown["embed"].description == (
        f"**User:** <@{USER}>\n"
        f"{config.EMOTE_STREAK} **New Streak:** `5` days\n"
        f"{config.EMOTE_MAX_STREAK} **New Max Streak:** `9` days\n"
        f"{MORA} **Mora Deducted:** `100`"
    )
    assert await balance(game.pool, USER) == 400
    saved = await helperFunctions.get_chest_streaks(game.pool, GUILD, USER)
    assert (saved["streak"], saved["max_streak"]) == (5, 9)


async def test_two_earnings_in_one_second_are_both_kept(game, monkeypatch):
    monkeypatch.setattr(helperFunctions.time, "time", lambda: 1_700_000_000)
    await helperFunctions.addMora(game.pool, USER, 30, CHANNEL, GUILD)
    await helperFunctions.addMora(game.pool, USER, 12, CHANNEL, GUILD)
    assert await balance(game.pool, USER) == 42


async def test_two_gifts_at_once_cannot_spend_the_same_mora(game, monkeypatch):
    monkeypatch.setattr(mora, "update_quest", AsyncMock())
    await progress(game.pool, gift_tax=0)
    await earn(game.pool, USER, 1000)
    first, second = await asyncio.gather(
        gift(game, game.friend, 700), gift(game, game.friend, 700)
    )
    refused = [content for content, _ in (first, second) if "You need" in content]
    assert len(refused) == 1
    assert await balance(game.pool, USER) == 300
    assert await balance(game.pool, OTHER) == 700


async def test_spending_rechecks_milestones_and_refuses_too_much(game):
    await earn(game.pool, USER, 100)
    spend = helperFunctions.spend_mora
    assert await spend(game.pool, USER, 101, CHANNEL, GUILD, game) is False
    helperFunctions.delayed_check_milestones.assert_not_called()
    assert await spend(game.pool, USER, 100, CHANNEL, GUILD, game) is True
    helperFunctions.delayed_check_milestones.assert_called_once_with(
        game.pool, USER, GUILD, CHANNEL, game
    )
    assert await balance(game.pool, USER) == 0


async def test_server_spend_gives_what_is_left(game):
    await earn(game.pool, USER, 100)
    await earn(game.pool, USER, 900, guild=11)
    take = helperFunctions.subtractGuildMora
    assert await take(game.pool, USER, 101, CHANNEL, GUILD) is False
    assert await take(game.pool, USER, 100, CHANNEL, GUILD) == 0
    assert await helperFunctions.get_total_mora(game.pool, USER) == 900


async def test_global_spend_empties_this_server_first(game):
    await earn(game.pool, USER, 100)
    await earn(game.pool, USER, 900, guild=11)
    await earn(game.pool, USER, -50, guild=12)
    take = helperFunctions.subtract_global_mora
    assert await take(game.pool, USER, 951, CHANNEL, GUILD) is False
    assert await helperFunctions.get_total_mora(game.pool, USER) == 950
    assert await take(game.pool, USER, 400, CHANNEL, GUILD) is True
    assert await balance(game.pool, USER) == 0
    assert await helperFunctions.get_guild_mora(game.pool, USER, 11) == 600
    assert await helperFunctions.get_guild_mora(game.pool, USER, 12) == -50


async def test_sigils_are_spent_here_first_and_never_twice(game):
    await helperFunctions.add_sigils(game.pool, USER, GUILD, 10)
    assert await helperFunctions.add_sigils(game.pool, USER, GUILD, 5) == 15
    await helperFunctions.add_sigils(game.pool, USER, 11, 20)
    here, everywhere = (
        helperFunctions.subtract_guild_sigils,
        helperFunctions.subtract_global_sigils,
    )
    assert await here(game.pool, USER, GUILD, 16) is False
    paid = await asyncio.gather(*(here(game.pool, USER, GUILD, 10) for _ in range(2)))
    assert sorted(paid) == [False, True]
    assert await everywhere(game.pool, USER, GUILD, 26) is False
    assert await everywhere(game.pool, USER, GUILD, 15) is True
    assert await helperFunctions.get_sigils_balance(game.pool, USER, GUILD) == 0
    assert await helperFunctions.get_sigils_balance(game.pool, USER, 11) == 10


async def test_a_spend_waits_for_the_member_and_only_for_them(game):
    await earn(game.pool, USER, 100)
    await earn(game.pool, OTHER, 100)
    spend = helperFunctions.subtractGuildMora
    async with game.pool.acquire() as held, held.transaction():
        await held.execute("SELECT pg_advisory_xact_lock($1)", USER)
        waiting = asyncio.create_task(spend(game.pool, USER, 60, CHANNEL, GUILD))
        assert await spend(game.pool, OTHER, 60, CHANNEL, GUILD) == 40
        await asyncio.sleep(0.2)
        assert not waiting.done()
    assert await waiting == 40


def test_a_scheduled_stock_change_adds_takes_or_sets():
    changed = helperFunctions.changed_stock
    assert [changed(5, "+3"), changed(5, "-9"), changed(5, "- 2")] == [8, 0, 3]
    assert [changed(-1, "+3"), changed(-1, "7"), changed(5, "+")] == [3, 7, 5]
    assert changed(5, "soon") is None


async def test_members_with_the_same_amount_are_ranked_by_id(game):
    for member in (30, 10, 20):
        await earn(game.pool, member, 500)
    await earn(game.pool, 40, 900)
    assert await helperFunctions.get_guild_leaderboard(game.pool, GUILD, 3) == [
        (40, 900),
        (10, 500),
        (20, 500),
    ]
    assert [uid for uid, _ in await helperFunctions.get_global_leaderboard(game.pool)] == [40, 10, 20, 30]  # fmt: skip
    over = await helperFunctions.get_users_by_currency_threshold(game.pool, GUILD, 600, "guild_mora")  # fmt: skip
    assert over == [(40, 900)]


async def test_mora_numbers_come_from_the_days_played(game):
    assert (await helperFunctions.get_mora_stats(game.pool, USER, GUILD))["days_active"] == 0  # fmt: skip
    day = 86400
    for when, amount in ((10 * day, 100), (10 * day + 5, 300), (12 * day, -50), (12 * day + 1, 250)):  # fmt: skip
        await game.pool.execute("INSERT INTO minigame_mora VALUES ($1, $2, $3, $4, $5)", USER, GUILD, CHANNEL, when, amount)  # fmt: skip
    numbers = await helperFunctions.get_mora_stats(game.pool, USER, GUILD)
    assert (numbers["first_played"], numbers["days_active"]) == (10 * day, 2)
    assert (numbers["largest_daily"], numbers["largest_single"]) == (400, 300)
    assert numbers["entry_count"] == 3
    assert numbers["average_daily"] == 600 // numbers["total_days"]


async def test_a_milestone_is_still_announced_when_the_member_left(game, monkeypatch):
    from commands.Events.games import common

    monkeypatch.setattr(common, "user_and_title", AsyncMock(return_value="<@1>"))
    await helperFunctions.add_milestone(game.pool, GUILD, "501", "Rich", 100)
    await earn(game.pool, USER, 150)
    gone = discord.NotFound(MagicMock(status=404), "Unknown Member")
    game.guild.fetch_member = AsyncMock(side_effect=gone)
    game.get_guild = lambda id: game.guild
    channel = SimpleNamespace(send=AsyncMock())
    game.get_channel = lambda id: channel
    await helperFunctions.check_milestones(game.pool, USER, GUILD, CHANNEL, game)
    held = await helperFunctions.get_user_inventory(game.pool, USER, GUILD)
    assert [item[0] for item in held] == ["501"]
    embed = channel.send.call_args.kwargs["embed"]
    assert embed.title == "🏆 Milestone Achieved!"
    assert embed.description.endswith("`100` and earned **<@&501>**\n")
    await helperFunctions.check_milestones(game.pool, USER, GUILD, CHANNEL, game)
    assert channel.send.call_count == 1
