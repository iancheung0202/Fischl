import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events import (
    config,
    domain,
    eliteTrack,
    expeditionReminders,
    helperFunctions,
    quests,
    seasons,
    social,
)

GUILD, USER, CHANNEL = 10, 20, 30
NOW = 1_800_000_000  # Friday 2027-01-15 08:00 UTC
DAY, WEEK, MONTH = 1_800_057_600, 1_800_144_000, 1_801_440_000
FORWARD = "<:fastforward:1351972114433048719>"


@pytest.fixture
async def game(pool, monkeypatch):
    """A bot on an empty database with the minigame tables, and a frozen clock."""
    bot = MagicMock(pool=pool)
    bot.wait_until_ready = AsyncMock()
    for module in (helperFunctions, quests, social, expeditionReminders):
        monkeypatch.setattr(bot, "add_cog", AsyncMock())
        monkeypatch.setattr(expeditionReminders.tasks.Loop, "start", MagicMock())
        await module.setup(bot)
    monkeypatch.setattr(quests.time, "time", lambda: NOW)
    clock = MagicMock(wraps=quests.datetime.datetime)
    clock.now = lambda tz=None: quests.datetime.datetime.fromtimestamp(NOW, tz)
    monkeypatch.setattr(quests.datetime, "datetime", clock)
    bot.channel = MagicMock(id=CHANNEL)
    bot.channel.send = AsyncMock()
    bot.get_channel = lambda channel_id: bot.channel if channel_id == CHANNEL else None
    return bot


@pytest.fixture
def xp(monkeypatch):
    """Stands in for the XP track; gives the mock that is asked to add XP."""
    from commands.Events import trackData
    from commands.Events.games import common

    add = AsyncMock(return_value=(1, 100, 350))
    monkeypatch.setattr(common, "add_xp", add)
    monkeypatch.setattr(
        trackData, "check_tier_rewards", AsyncMock(return_value=("free", "elite"))
    )
    return add


async def saved(pool, cycle=None):
    """Gives the stored quests as {(cycle, name): (current, goal, completed, bonus, extra)}."""
    rows = await pool.fetch(
        "SELECT * FROM minigame_quests ORDER BY cycle_type, quest_name"
    )
    return {
        (row["cycle_type"], row["quest_name"]): (
            row["current_progress"],
            row["goal_progress"],
            row["completed"],
            row["bonus_awarded"],
            row["extra_data"],
        )
        for row in rows
        if cycle in (None, row["cycle_type"])
    }


async def give(pool, cycle, name, current, goal, end=NOW + 1, done=False, extra=None):
    """Stores one quest for the test member."""
    await pool.execute(
        "INSERT INTO minigame_quests VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9)",
        str(GUILD),
        str(USER),
        cycle,
        end,
        name,
        current,
        goal,
        done,
        extra,
    )


async def test_first_update_hands_out_quests_for_each_cycle(game, xp):
    await quests.update_quest(USER, GUILD, CHANNEL, {}, game, refresh_only=True)
    rows = await game.pool.fetch("SELECT * FROM minigame_quests")
    by_cycle = {}
    for row in rows:
        by_cycle.setdefault(row["cycle_type"], []).append(row)
        assert (row["guild_id"], row["user_id"]) == (str(GUILD), str(USER))
        assert (
            row["goal_progress"]
            in config.QUEST_GOAL_PRESETS[row["quest_name"]][row["cycle_type"]]
        )
        assert (row["current_progress"], row["completed"]) == (0, False)
        assert (row["bonus_awarded"], row["extra_data"]) == (False, None)
    assert {cycle: len(found) for cycle, found in by_cycle.items()} == {
        "daily": 2,
        "weekly": 3,
        "monthly": 3,
    }
    ends = {
        cycle: {row["end_time"] for row in found} for cycle, found in by_cycle.items()
    }
    assert ends == {"daily": {DAY}, "weekly": {WEEK}, "monthly": {MONTH}}
    before = await saved(game.pool)
    await quests.update_quest(USER, GUILD, CHANNEL, {}, game, refresh_only=True)
    assert await saved(game.pool) == before
    xp.assert_not_awaited()
    game.channel.send.assert_not_awaited()


@pytest.mark.parametrize(
    "stamp, day, week, month",
    [
        (1_800_144_000 - 1, 1_800_144_000, 1_800_144_000, MONTH),  # Saturday night
        (1_800_144_000, 1_800_230_400, 1_800_748_800, MONTH),  # Sunday 00:00
        (1_798_761_599, 1_798_761_600, 1_798_934_400, 1_798_761_600),  # 31 December
    ],
)
def test_reset_times(monkeypatch, stamp, day, week, month):
    clock = MagicMock(wraps=quests.datetime.datetime)
    clock.now = lambda tz=None: quests.datetime.datetime.fromtimestamp(stamp, tz)
    monkeypatch.setattr(quests.datetime, "datetime", clock)
    assert quests.get_next_daily_reset() == day
    assert quests.get_next_weekly_reset() == week
    assert quests.get_next_monthly_reset() == month


async def test_progress_is_counted_and_saved_without_a_message(game, xp):
    await give(game.pool, "daily", "win_minigames", 1, 5)
    await give(game.pool, "daily", "hug_user", 0, 2)
    await give(game.pool, "weekly", "win_minigames", 4, 9, extra='{"kept": 1}')
    await give(game.pool, "monthly", "earn_mora", 0, 9)
    await quests.update_quest(
        USER, GUILD, CHANNEL, {"win_minigames": 2, "unknown": 5}, game
    )
    assert await saved(game.pool) == {
        ("daily", "hug_user"): (0, 2, False, False, None),
        ("daily", "win_minigames"): (3, 5, False, False, None),
        ("monthly", "earn_mora"): (0, 9, False, False, None),
        ("weekly", "win_minigames"): (6, 9, False, False, '{"kept": 1}'),
    }
    xp.assert_not_awaited()
    game.channel.send.assert_not_awaited()


async def test_completing_quests_pays_xp_and_the_cycle_bonus(game, xp, monkeypatch):
    await give(game.pool, "daily", "win_minigames", 4, 5)
    await give(game.pool, "daily", "hug_user", 2, 2, done=True)
    await give(game.pool, "weekly", "win_minigames", 4, 9)
    await give(game.pool, "weekly", "hug_user", 0, 1)
    await give(game.pool, "monthly", "earn_mora", 0, 9)
    await quests.update_quest(
        USER, GUILD, CHANNEL, {"hug_user": 1, "win_minigames": 3}, game
    )
    assert await saved(game.pool) == {
        ("daily", "hug_user"): (2, 2, True, True, None),
        ("daily", "win_minigames"): (7, 5, True, True, None),
        ("monthly", "earn_mora"): (0, 9, False, False, None),
        ("weekly", "hug_user"): (1, 1, True, False, None),
        ("weekly", "win_minigames"): (7, 9, False, False, None),
    }
    xp.assert_awaited_once_with(USER, GUILD, 250 + 500 + 500, game)
    from commands.Events import trackData

    trackData.check_tier_rewards.assert_awaited_once_with(
        guild_id=GUILD,
        user_id=USER,
        old_xp=100,
        new_xp=350,
        channel=game.channel,
        client=game,
        pool=game.pool,
    )
    (), sent = game.channel.send.call_args
    assert set(sent) == {"content", "embed", "view"}
    assert sent["content"] == f"<@{USER}>"
    assert isinstance(sent["view"], helperFunctions.TierRewardsView)
    assert sent["embed"].to_dict() == {
        "type": "rich",
        "flags": 0,
        "title": "🎉 Quests Completed!",
        "color": 0x22D65E,
        "description": (
            f"{config.YES_EMOTE} **{config.QUEST_DESCRIPTIONS['win_minigames']}** (daily): `5` ‎ {FORWARD} ‎ `+250` XP\n"
            f"<a:legacy:1345876714240213073> *Completed all daily quests* ‎ {FORWARD} ‎ `+500` XP\n"
            f"{config.YES_EMOTE} **{config.QUEST_DESCRIPTIONS['hug_user']}** (weekly): `1` ‎ {FORWARD} ‎ `+500` XP\n\n"
            "**Total XP earned:** `1250` XP"
        ),
    }
    # A paid bonus and finished quests are not paid again.
    xp.reset_mock()
    await quests.update_quest(
        USER, GUILD, CHANNEL, {"hug_user": 1, "win_minigames": 1}, game
    )
    xp.assert_not_awaited()
    assert (await saved(game.pool, "daily"))[("daily", "win_minigames")][0] == 7
    assert (await saved(game.pool, "weekly"))[("weekly", "win_minigames")][0] == 8


async def test_updates_at_the_same_moment_all_count(game, xp):
    await give(game.pool, "daily", "win_minigames", 0, 99)
    await give(game.pool, "weekly", "win_minigames", 0, 99)
    await give(game.pool, "monthly", "win_minigames", 0, 99)
    await asyncio.gather(
        *(
            quests.update_quest(USER, GUILD, CHANNEL, {"win_minigames": 1}, game)
            for _ in range(20)
        )
    )
    assert {row[0] for row in (await saved(game.pool)).values()} == {20}
    assert not quests.LOCKS


async def test_library_levels_boost_quest_xp(game, xp):
    await game.pool.execute(
        "INSERT INTO minigame_progression (gid, uid, kingdom_bibliothek) VALUES ($1, $2, 70)",
        GUILD,
        USER,
    )
    await give(game.pool, "monthly", "hug_user", 0, 1)
    await give(game.pool, "daily", "earn_mora", 0, 9)
    await give(game.pool, "weekly", "earn_mora", 0, 9)
    await quests.update_quest(USER, GUILD, CHANNEL, {"hug_user": 1}, game)
    xp.assert_awaited_once_with(USER, GUILD, 2250 + 6750, game)
    lines = game.channel.send.call_args[1]["embed"].description.split("\n")
    assert lines[0].endswith("`+2250` XP") and lines[1].endswith("`+6750` XP")


async def test_xp_is_paid_without_a_message_when_the_channel_is_unknown(game, xp):
    await give(game.pool, "daily", "hug_user", 0, 1)
    await give(game.pool, "weekly", "earn_mora", 0, 9)
    await give(game.pool, "monthly", "earn_mora", 0, 9)
    await quests.update_quest(USER, GUILD, 999, {"hug_user": 1}, game)
    xp.assert_awaited_once_with(USER, GUILD, 750, game)
    game.channel.send.assert_not_awaited()


async def test_gifting_counts_each_member_once(game, xp):
    await give(
        game.pool, "daily", "gift_mora_unique", 1, 3, extra='{"gifted_users": ["7"]}'
    )
    await give(game.pool, "daily", "earn_mora", 0, 9)
    await give(game.pool, "weekly", "gift_mora_unique", 0, 2, extra="not json")
    await give(game.pool, "monthly", "earn_mora", 0, 9)
    for gifted in (7, 8, 8):
        await quests.update_quest(
            USER, GUILD, CHANNEL, {"gift_mora_unique": gifted}, game
        )
    stored = await saved(game.pool)
    assert stored[("daily", "gift_mora_unique")][:3] == (2, 3, False)
    assert json.loads(stored[("daily", "gift_mora_unique")][4]) == {
        "gifted_users": ["7", "8"]
    }
    assert stored[("weekly", "gift_mora_unique")][:3] == (2, 2, True)
    assert json.loads(stored[("weekly", "gift_mora_unique")][4]) == {
        "gifted_users": ["7", "8"]
    }
    xp.assert_awaited_once_with(USER, GUILD, 500 + 1500, game)


async def test_an_ended_cycle_is_replaced_before_counting(game, xp, monkeypatch):
    await give(game.pool, "daily", "hug_user", 1, 2, end=NOW)
    await give(game.pool, "weekly", "hug_user", 1, 9)
    await give(game.pool, "monthly", "hug_user", 1, 9, end=NOW + 5)
    monkeypatch.setattr(
        quests,
        "generate_quests",
        lambda duration: {
            "hug_user": {"current": 0, "goal": 4},
            "earn_mora": {"current": 0, "goal": 7},
        },
    )
    await quests.update_quest(USER, GUILD, CHANNEL, {"hug_user": 1}, game)
    assert await saved(game.pool) == {
        ("daily", "earn_mora"): (0, 7, False, False, None),
        ("daily", "hug_user"): (1, 4, False, False, None),
        ("monthly", "hug_user"): (2, 9, False, False, None),
        ("weekly", "hug_user"): (2, 9, False, False, None),
    }
    ends = await game.pool.fetch(
        "SELECT DISTINCT end_time FROM minigame_quests WHERE cycle_type = 'daily'"
    )
    assert [row["end_time"] for row in ends] == [DAY]


async def test_quest_data_for_the_quest_page(game):
    assert await quests.get_quest_data(game.pool, GUILD, USER) == {}
    await give(
        game.pool, "daily", "hug_user", 2, 2, done=True, extra='{"gifted_users": ["7"]}'
    )
    await give(game.pool, "daily", "earn_mora", 1, 9, extra="not json")
    await give(game.pool, "weekly", "earn_mora", 0, 9, end=5)
    await game.pool.execute(
        "UPDATE minigame_quests SET bonus_awarded = TRUE WHERE cycle_type = 'weekly'"
    )
    assert await quests.get_quest_data(game.pool, GUILD, USER) == {
        "daily": {
            "quests": {
                "hug_user": {"current": 2, "goal": 2, "gifted_users": ["7"]},
                "earn_mora": {"current": 1, "goal": 9},
            },
            "completed": {"hug_user": True},
            "end_time": NOW + 1,
            "bonus_awarded": False,
        },
        "weekly": {
            "quests": {"earn_mora": {"current": 0, "goal": 9}},
            "completed": {},
            "end_time": 5,
            "bonus_awarded": True,
        },
    }


def test_generated_quests(monkeypatch):
    for duration, count in (("daily", 2), ("weekly", 3), ("monthly", 3)):
        found = quests.generate_quests(duration)
        assert len(found) == count
        for name, quest in found.items():
            assert quest["current"] == 0
            assert quest["goal"] in config.QUEST_GOAL_PRESETS[name][duration]


# Expeditions


async def run(pool, uid, gid, character, ends, mora=100, summons=1, claimed=False):
    await pool.execute(
        "INSERT INTO web_expeditions (uid, gid, slot, character, hours, started_at, ends_at, mora, summons, claimed) "
        "VALUES ($1, $2, 1, $3, 4, 0, $4, $5, $6, $7)",
        uid,
        gid,
        character,
        ends,
        mora,
        summons,
        claimed,
    )


async def test_returned_expeditions_are_dmed_once(game, monkeypatch):
    monkeypatch.setattr(expeditionReminders.time, "time", lambda: 1000)
    pool = game.pool
    await run(pool, 1, 5, "Fischl", 900, mora=1500, summons=1)
    await run(pool, 1, 5, "Oz", 1000, mora=500, summons=1)
    await run(pool, 1, 6, "Mona", 999, mora=7, summons=1)
    await run(pool, 2, 5, "Late", 1001)
    await run(pool, 2, 5, "Claimed", 1, claimed=True)
    await run(pool, 3, 5, "Closed", 1)
    users = {1: MagicMock(send=AsyncMock()), 3: MagicMock()}
    users[3].send = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(status=403), "no")
    )
    game.fetch_user = AsyncMock(side_effect=lambda uid: users[uid])
    game.get_guild = lambda gid: SimpleNamespace(name="Castle") if gid == 5 else None
    cog = expeditionReminders.ExpeditionReminders(game)
    await cog.notify.coro(cog)
    sent = [call[1]["embed"].to_dict() for call in users[1].send.call_args_list]
    assert sent == [
        {
            "type": "rich",
            "flags": 0,
            "title": "🧭 Your expedition has returned!",
            "color": 0xFA0ADD,
            "description": (
                f"**Fischl, Oz** came back from **Castle** with {config.MORA_EMOTE} **2,000** mora and **2** summons waiting.\n"
                "[Collect rewards & send them out again](https://fischl.app/profile/5)"
            ),
        },
        {
            "type": "rich",
            "flags": 0,
            "title": "🧭 Your expedition has returned!",
            "color": 0xFA0ADD,
            "description": (
                f"**Mona** came back from **your realm** with {config.MORA_EMOTE} **7** mora and **1** summon waiting.\n"
                "[Collect rewards & send them out again](https://fischl.app/profile/6)"
            ),
        },
    ]
    users[3].send.assert_awaited_once()
    flagged = await pool.fetch(
        "SELECT character FROM web_expeditions WHERE notified ORDER BY 1"
    )
    assert [row["character"] for row in flagged] == ["Closed", "Fischl", "Mona", "Oz"]
    await cog.notify.coro(cog)
    assert users[1].send.await_count == 2


async def test_expedition_check_survives_a_database_failure(capsys):
    bot = MagicMock()
    bot.pool.fetch = AsyncMock(side_effect=RuntimeError("down"))
    bot.pool.acquire = MagicMock(side_effect=RuntimeError("down"))
    expeditionReminders.tasks.Loop.start, kept = (
        MagicMock(),
        expeditionReminders.tasks.Loop.start,
    )
    try:
        cog = expeditionReminders.ExpeditionReminders(bot)
        cog.notify.start.assert_called_once_with()
    finally:
        expeditionReminders.tasks.Loop.start = kept
    await cog.notify.coro(cog)
    assert capsys.readouterr().out == "Expedition reminder error: down\n"
    assert cog.notify.minutes == 1
    bot.wait_until_ready = AsyncMock()
    await cog.notify._before_loop(cog)
    bot.wait_until_ready.assert_awaited_once_with()


# Seasons


def season(number, start, end):
    return config.Season(number, f"Season {number}", start, end, [])


class Stop(Exception):
    pass


async def monitor(monkeypatch, capsys, times, found):
    """Runs the season monitor over the given clock readings; gives its prints and resets."""
    monkeypatch.setattr(seasons, "SEASONS", found)
    readings = iter(times)
    monkeypatch.setattr(seasons.time, "time", lambda: next(readings))
    naps = []

    async def nap(seconds):
        naps.append(seconds)
        if len(naps) == len(times):
            raise Stop

    monkeypatch.setattr(seasons.asyncio, "sleep", nap)
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.is_closed = lambda: False
    cog = seasons.SeasonCog(bot)
    bot.loop.create_task.call_args[0][0].close()
    cog.reset_season_data = AsyncMock(side_effect=lambda: print("RESET"))
    with pytest.raises(Stop):
        await cog.season_monitor()
    assert naps == [60] * len(times)
    return capsys.readouterr().out.splitlines()


async def test_season_monitor_resets_on_change_and_end(monkeypatch, capsys):
    found = [season(1, 0, 10), season(2, 10, 20), season(3, 30, 40)]
    assert await monitor(
        monkeypatch, capsys, [50, 5, 9, 10, 19, 20, 25, 30, 45], found
    ) == [
        "No season active yet.",
        "Season changed from season 1 to season 2",
        "RESET",
        "Season 2 ended, no new season started yet.",
        "RESET",
        "No season active yet.",
        "Season 3 ended, no new season started yet.",
        "RESET",
    ]


def test_current_season(monkeypatch):
    found = [season(1, 0, 10), season(2, 10, 20)]
    monkeypatch.setattr(seasons, "SEASONS", found)
    for now, expected in (
        (0, found[0]),
        (9.9, found[0]),
        (10, found[1]),
        (20, None),
        (-1, None),
    ):
        monkeypatch.setattr(seasons.time, "time", lambda: now)
        assert seasons.get_current_season() is expected


async def test_season_reset_keeps_prestige_and_summons(game, capsys):
    pool = game.pool
    await pool.execute(
        "INSERT INTO minigame_progression (gid, uid, kingdom_schloss, xp, prestige, bonus_tier, mora_boost, "
        "chest_upgrades, gift_tax, minigame_summons, shop_discount, domain_discount, express_daily_chests) "
        "VALUES (1, 2, 3, 4000, 5, 6, 7, 8, 9, 10, 11, 12, TRUE)"
    )
    await pool.execute(
        "INSERT INTO minigame_elite (user_id, guild_id, expires_at, claimed_tiers) VALUES (2, 1, 5, '{1,2}')"
    )
    await pool.execute(
        "INSERT INTO minigame_cosmetics (uid, gid, embed_color, selected_embed_color_hex) VALUES (2, 1, TRUE, 'ff0000')"
    )
    cog = seasons.SeasonCog(game)
    game.loop.create_task.call_args[0][0].close()
    await cog.reset_season_data()
    row = dict(await pool.fetchrow("SELECT * FROM minigame_progression"))
    row.pop("updated_at", None)
    kept = {
        "gid": 1,
        "uid": 2,
        "kingdom_schloss": 3,
        "prestige": 5,
        "minigame_summons": 10,
    }
    reset = {
        "xp": 0,
        "bonus_tier": 0,
        "mora_boost": 0,
        "chest_upgrades": 4,
        "gift_tax": None,
    }
    reset.update(shop_discount=0, domain_discount=0, express_daily_chests=False)
    assert {key: row[key] for key in {**kept, **reset}} == {**kept, **reset}
    assert await pool.fetchval("SELECT claimed_tiers FROM minigame_elite") == []
    cosmetics = await pool.fetchrow(
        "SELECT embed_color, selected_embed_color_hex FROM minigame_cosmetics"
    )
    assert tuple(cosmetics) == (False, None)
    assert capsys.readouterr().out == "Season user data reset successfully!\n"
    game.pool = None
    await cog.reset_season_data()
    assert (
        capsys.readouterr().out
        == "ERROR: Database pool not available for season reset!\n"
    )


# Hugs, kingdom, leaderboard, elite track


def member(uid):
    return SimpleNamespace(id=uid, mention=f"<@{uid}>", display_name=f"M{uid}")


def press(game, uid):
    """An interaction by the member in the test channel, recording what it sends."""
    interaction = MagicMock(client=game, user=member(uid))
    interaction.guild = SimpleNamespace(id=GUILD, name="Castle", icon=None)
    interaction.channel = game.channel
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.original_response = AsyncMock(return_value=MagicMock(edit=AsyncMock()))
    return interaction


async def test_hug_and_hug_back(game, monkeypatch):
    monkeypatch.setattr(social.os, "listdir", lambda path: ["a.gif", "notes.txt"])
    monkeypatch.setattr(social.discord, "File", lambda path, filename: (path, filename))
    quest = AsyncMock()
    monkeypatch.setattr(social, "update_quest", quest)
    cog = social.Hug(game)
    first = press(game, 1)
    await cog.hug.callback(cog, first, member(1))
    first.response.send_message.assert_awaited_once_with(
        "I appreciate your self love, but you can't hug yourself!", ephemeral=True
    )
    game.channel.send.assert_not_awaited()

    for times in ("That's the first time!", "That's `2` times now!"):
        hug = press(game, 1)
        await cog.hug.callback(cog, hug, member(2))
        sent = game.channel.send.call_args[1]
        assert sent["content"] == "<@2>"
        assert sent["file"] == ("assets/hugs/a.gif", "hug.gif")
        assert (
            sent["embed"].description == f":people_hugging: <@1> hugged <@2>! {times}"
        )
        assert sent["embed"].image.url == "attachment://hug.gif"
        assert sent["embed"].color.value == 0xD596C4
        hug.response.send_message.assert_awaited_once_with(
            content="Hug sent!", ephemeral=True
        )
        quest.assert_awaited_with(1, GUILD, CHANNEL, {"hug_user": 1}, game)
    view = sent["view"]
    assert view.timeout == 120 and view.message is hug.original_response.return_value

    stranger = press(game, 1)
    await view.hug_back.callback(stranger)
    stranger.response.send_message.assert_awaited_once_with(
        "Only the hugged user can hug back!", ephemeral=True
    )
    back = press(game, 2)
    await view.hug_back.callback(back)
    sent = game.channel.send.call_args[1]
    assert set(sent) == {"content", "embed", "file"} and sent["content"] == "<@1>"
    assert (
        sent["embed"].description
        == ":people_hugging: <@2> hugged <@1>! That's the first time!"
    )
    back.response.send_message.assert_awaited_once_with(
        content="Hug sent back!", ephemeral=True
    )
    view.message.edit.assert_awaited_once_with(view=view)
    assert view.hug_back.disabled
    quest.assert_awaited_with(2, GUILD, CHANNEL, {"hug_user": 1}, game)
    rows = await game.pool.fetch("SELECT * FROM hugs ORDER BY hugger_id")
    assert [tuple(row) for row in rows] == [(2, 1, 2), (1, 2, 1)]

    monkeypatch.setattr(social.os, "listdir", lambda path: ["notes.txt"])
    none = press(game, 1)
    await cog.hug.callback(cog, none, member(2))
    none.response.send_message.assert_awaited_once_with(
        "Hug GIF `None` not found!", ephemeral=True
    )
    none = press(game, 2)
    await view.hug_back.callback(none)
    none.response.send_message.assert_awaited_once_with(
        "Hug GIFs not found!", ephemeral=True
    )


async def test_upgrading_a_building(game, monkeypatch):
    quest = AsyncMock()
    monkeypatch.setattr(domain, "update_quest", quest)
    interaction = press(game, USER)
    castle, other = list(config.BUILDINGS)[:2]
    names = [config.BUILDINGS[key]["name"] for key in (castle, other)]
    assert await domain.upgrade_building(USER, GUILD, other, interaction) == (
        False,
        f"**{names[1]}** cannot exceed {names[0]} Level (0)! Upgrade your {names[0]} first.",
    )
    cost = config.calculate_cost(0)
    assert await domain.upgrade_building(USER, GUILD, castle, interaction) == (
        False,
        f"Insufficient balance! You need at least {config.MORA_EMOTE} `{cost:,}` to upgrade!",
    )
    quest.assert_not_awaited()
    await game.pool.execute(
        "INSERT INTO minigame_mora (uid, gid, cid, timestamp, count) VALUES ($1, $2, $3, 1, $4)",
        USER,
        GUILD,
        CHANNEL,
        cost + 5,
    )
    assert await domain.upgrade_building(USER, GUILD, castle, interaction) == (
        True,
        f"Upgraded **{names[0]}** to Level 1!\nYou now have {config.MORA_EMOTE} `5` remaining.",
    )
    quest.assert_awaited_once_with(USER, GUILD, CHANNEL, {"upgrade_buildings": 1}, game)
    assert await helperFunctions.get_building_level(game.pool, GUILD, USER, castle) == 1

    embed = await domain.get_kingdom_embed(member(USER), GUILD, pool=game.pool)
    assert embed.title == f"🏰 M{USER}'s {config.DOMAIN_NAME}"
    assert embed.description == (
        f"**Rank**: `Subject`\n**Total Level**: `1`\n-# *{config.DOMAIN_DESCRIPTION}*"
    )
    assert embed.footer.text == "+1% per level • Max rewards capped at Lv. 50"
    assert embed.color == discord.Color.purple()
    assert [field.inline for field in embed.fields] == [False] + [True] * (
        len(config.BUILDINGS) - 1
    )
    does, perk = config.perk_info(castle, 1)
    assert (embed.fields[0].name, embed.fields[0].value) == (
        f"{config.BUILDINGS[castle]['emoji']} {names[0]} `Lv. 1`",
        f"-# {does}: {perk}\nNext: {config.MORA_EMOTE} `{config.calculate_cost(1):,}`",
    )
    blank = await domain.get_kingdom_embed(member(USER), GUILD, custom_color=0x123456)
    assert blank.color.value == 0x123456 and "`0`" in blank.description


def test_discounted_price():
    assert (
        domain.format_domain_cost(1000, 900, 10)
        == f"{config.MORA_EMOTE} ~~`1,000`~~ ➜ `900`"
    )
    assert domain.format_domain_cost(1000, 1000, 10) == f"{config.MORA_EMOTE} `1,000`"
    assert domain.format_domain_cost(1000, 900, 0) == f"{config.MORA_EMOTE} `1,000`"


async def test_leaderboard_pages(game, monkeypatch, capsys):
    from commands.Events import leaderboard

    rows = [(uid, 1000 - uid) for uid in range(1, 13)]
    board = dict(
        leaderboard.BOARDS["kingdom"],
        rankings=(
            AsyncMock(return_value=rows),
            AsyncMock(side_effect=RuntimeError("down")),
        ),
    )
    monkeypatch.setitem(leaderboard.BOARDS, "kingdom", board)
    monkeypatch.setattr(leaderboard, "BasePaginationView", lambda pages: pages)
    cog = leaderboard.Leaderboard(game)
    interaction = press(game, 12)
    choice = lambda value: SimpleNamespace(value=value)
    await cog.lb.callback(cog, interaction, choice("kingdom"), choice("global"))
    interaction.response.defer.assert_awaited_once_with(thinking=True)
    pages = interaction.followup.send.call_args[1]["view"]
    assert interaction.followup.send.call_args[1]["embed"] is pages[0]
    assert [page.footer.text for page in pages] == [
        "Your Rank: #12 (Page 2)",
        "Your Rank: #12",
    ]
    assert pages[0].title == "Global Kingdom Rankings"
    assert pages[0].description.startswith(
        "An all-time ranking of users across all servers based on their total Kingdom Level.\n\n"
        "1. <@1> - 🏰 `999` *(Emperor)*\n"
    )
    assert pages[1].description.endswith(
        "\n\n11. <@11> - 🏰 `989` *(Emperor)*\n12. <@12> - 🏰 `988` *(Emperor)* <:you:1339737311319162890>"
    )
    capsys.readouterr()
    await cog.lb.callback(cog, interaction, choice("kingdom"), choice("server"))
    (page,) = interaction.followup.send.call_args[1]["view"]
    assert (page.title, page.description, page.color.value) == (
        "Castle's Kingdom Rankings",
        "No data available",
        0x999999,
    )
    assert capsys.readouterr().out.startswith("[lb error] down\n")


async def test_add_sub_command(game, monkeypatch):
    grant = AsyncMock(return_value=["Tier 1", "Tier 2"])
    monkeypatch.setattr(eliteTrack, "grant_elite_rewards_up_to_tier", grant)
    user = MagicMock(send=AsyncMock())
    game.fetch_user = AsyncMock(return_value=user)
    game.fetch_guild = AsyncMock(return_value=SimpleNamespace(name="Castle"))
    cog = eliteTrack.EliteTrack(game)
    for call in game.loop.create_task.call_args_list:
        call[0][0].close()

    def said(content, author=eliteTrack.IAN, bot=False):
        return MagicMock(
            content=content,
            channel=game.channel,
            author=SimpleNamespace(id=author, bot=bot),
        )

    for message, reply in (
        (
            said("-addSub 1 2 3", author=5),
            f"{config.NO_EMOTE} You don't have permission to use this command.",
        ),
        (
            said("-addSub 1 2"),
            f"{config.NO_EMOTE} Usage: `-addSub userID serverID timestamp`",
        ),
        (
            said("-addSub a 2 3"),
            f"{config.NO_EMOTE} Invalid arguments. Make sure IDs are numbers and timestamp is a float.",
        ),
    ):
        await cog.on_message(message)
        game.channel.send.assert_awaited_with(reply)
    await cog.on_message(said("-addSub 1 2 3", bot=True))
    await cog.on_message(said("hello"))
    assert game.channel.send.await_count == 3

    await cog.on_message(said(f"-addSub {USER} {GUILD} 1900000000.5"))
    row = await game.pool.fetchrow(
        "SELECT user_id, guild_id, expires_at, pending_processed FROM minigame_elite"
    )
    assert tuple(row) == (USER, GUILD, 1900000000, True)
    grant.assert_awaited_once_with(
        GUILD, USER, game.channel, 0, client=game, pool=game.pool
    )
    assert user.send.call_args[1]["embed"].to_dict() == {
        "type": "rich",
        "flags": 0,
        "title": f"{config.MONEYDANCE_EMOTE} Elite Track Activated!",
        "color": 0xFA0ADD,
        "description": (
            "🎉 You now have sweet perks in **Castle**! Enjoy friend!\n"
            "⏰ Expires on <t:1900000000> (<t:1900000000:R>)\n\n"
            "***You've also automatically received these elite rewards from previous tiers:***\n\nTier 1\nTier 2"
        ),
    }
    game.channel.send.assert_awaited_with(
        f"{config.YES_EMOTE} Subscription added for <@{USER}> in server `{GUILD}`"
    )


async def test_website_subscriptions_are_paid_once(game, monkeypatch, capsys):
    grant = AsyncMock(return_value=["Tier 1"])
    monkeypatch.setattr(eliteTrack, "grant_elite_rewards_up_to_tier", grant)
    await game.pool.execute(
        "INSERT INTO minigame_elite (user_id, guild_id, expires_at, pending_processed) VALUES ($1, $2, 9e12, FALSE), (7, $2, 1, FALSE)",
        USER,
        GUILD,
    )
    await game.pool.execute(
        "INSERT INTO minigame_settings (channel_id, minigames_enabled) VALUES ($1, TRUE)",
        CHANNEL,
    )
    await game.pool.execute(
        "INSERT INTO minigame_progression (gid, uid, xp) VALUES ($1, $2, 500)",
        GUILD,
        USER,
    )
    closed, allowed = MagicMock(id=CHANNEL), game.channel
    closed.permissions_for.return_value.send_messages = False
    allowed.permissions_for.return_value.send_messages = True
    guild = MagicMock(text_channels=[MagicMock(id=1), closed, allowed])
    guild.name = "Castle"
    game.fetch_guild = AsyncMock(return_value=guild)
    user = MagicMock(
        send=AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no"))
    )
    game.fetch_user = AsyncMock(return_value=user)
    game.is_closed = MagicMock(side_effect=[False, True])
    monkeypatch.setattr(eliteTrack.asyncio, "sleep", AsyncMock())
    cog = eliteTrack.EliteTrack(game)
    for call in game.loop.create_task.call_args_list:
        call[0][0].close()
    await cog.process_pending_activations()
    assert [call[0][0] for call in eliteTrack.asyncio.sleep.call_args_list] == [10, 60]
    grant.assert_awaited_once_with(
        GUILD, USER, allowed, 500, client=game, pool=game.pool
    )
    assert user.send.call_args[1]["embed"].description == (
        "Your elite rewards have been processed for **Castle**!\n\n"
        "***You've received these elite rewards from previous tiers:***\n\nTier 1"
    )
    pending = await game.pool.fetch(
        "SELECT user_id FROM minigame_elite WHERE NOT pending_processed"
    )
    assert [row["user_id"] for row in pending] == [7]
    assert (
        capsys.readouterr().out
        == f"Processed pending elite activation for user {USER} in guild {GUILD}\n"
    )


# The season track


@pytest.fixture
async def track(game, monkeypatch):
    """The track module on a three-tier season, with drop packs and quests recorded."""
    from commands.Events import trackData

    season = SimpleNamespace(
        track_data=[
            {
                "tier": 1,
                "cumulative_xp": 100,
                "free": "Drop Pack",
                "elite": "Prestige +1",
            },
            {
                "tier": 2,
                "cumulative_xp": 200,
                "free": "Shop Discount +10%",
                "elite": "Drop Pack",
            },
            {
                "tier": 3,
                "cumulative_xp": 300,
                "free": "Nonsense",
                "elite": "Prestige +1",
            },
        ]
    )
    monkeypatch.setattr(trackData, "get_current_season", lambda: season)
    monkeypatch.setattr(trackData.time, "time", lambda: NOW)
    game.packs = AsyncMock(return_value=SimpleNamespace(jump_url="https://jump"))
    monkeypatch.setattr(trackData, "create_drop_pack", game.packs)
    game.quest = AsyncMock()
    monkeypatch.setattr(quests, "update_quest", game.quest)
    game.channel.mention = "<#30>"
    await game.pool.execute(
        "INSERT INTO minigame_progression (gid, uid) VALUES ($1, $2)", GUILD, USER
    )
    game.track = trackData
    return game


async def elite(pool, expires=NOW + 500, claimed=()):
    """Gives the test member an Elite Track."""
    await pool.execute(
        "INSERT INTO minigame_elite (user_id, guild_id, expires_at, claimed_tiers) VALUES ($1, $2, $3, $4)",
        USER,
        GUILD,
        expires,
        list(claimed),
    )


async def progress(pool, column):
    """Gives one stored value of the test member's progression."""
    return await pool.fetchval(
        f"SELECT {column} FROM minigame_progression WHERE gid = $1 AND uid = $2",
        GUILD,
        USER,
    )


def test_every_reward_type_has_a_payer():
    from commands.Events import trackData

    assert set(config.REWARD_TYPES.values()) == set(trackData.PAYERS)


async def test_track_is_empty_between_seasons(track, monkeypatch):
    monkeypatch.setattr(track.track, "get_current_season", lambda: None)
    assert track.track.get_current_track() == []


async def test_drop_pack_reward_drops_a_pack_and_counts_the_quest(track):
    said = await track.track.grant_reward(
        GUILD, USER, "Drop Pack", 4, track.channel, client=track, pool=track.pool
    )
    assert said == (
        "New Drop Pack",
        "**Tier `4`:** You can claim your drop pack [here](https://jump)!",
    )
    track.packs.assert_awaited_once_with(
        GUILD, USER, track.channel, False, False, 4, track
    )
    track.quest.assert_awaited_once_with(
        USER, GUILD, CHANNEL, {"unlock_drop_packs": 1}, track
    )


async def test_bonus_elite_pack_is_named_and_skips_the_quest_without_a_client(track):
    await elite(track.pool)
    said = await track.track.grant_reward(
        GUILD, USER, "Drop Pack", "Bonus", track.channel, True, None, track.pool
    )
    assert said == (
        "Elite New Bonus Drop Pack",
        "**Bonus:** You can claim your drop pack [here](https://jump)!",
    )
    track.quest.assert_not_awaited()
    assert await track.pool.fetchval("SELECT claimed_tiers FROM minigame_elite") == []


async def test_elite_tier_pays_only_once(track):
    await elite(track.pool)
    pay = lambda: track.track.grant_reward(  # noqa: E731
        GUILD, USER, "Prestige +1", 7, track.channel, True, track, track.pool
    )
    title, _ = await pay()
    assert title == "Elite Reward:  Prestige +1 " + config.PRESTIGE_EMOTE
    assert await pay() == (None, None)
    assert await progress(track.pool, "prestige") == 1
    assert await track.pool.fetchval("SELECT claimed_tiers FROM minigame_elite") == [7]


async def test_unknown_reward_pays_nothing_but_still_claims_the_tier(track):
    await elite(track.pool)
    said = await track.track.grant_reward(
        GUILD, USER, "Nonsense", 3, track.channel, True, track, track.pool
    )
    assert said == (None, None)
    assert await track.pool.fetchval("SELECT claimed_tiers FROM minigame_elite") == [3]


async def test_shop_discount_stops_at_fifty(track):
    await track.pool.execute("UPDATE minigame_progression SET shop_discount = 45")
    title, description = await track.track.grant_reward(
        GUILD, USER, "Shop Discount +10%", 2, track.channel, pool=track.pool
    )
    assert title == " Shop Discount +10% 🏷️"
    assert "**50% discount**" in description
    assert await progress(track.pool, "shop_discount") == 50


async def test_tiers_passed_fill_both_embeds(track):
    await elite(track.pool)
    free, paid = await track.track.check_tier_rewards(
        GUILD, USER, 50, 300, track.channel, client=track, pool=track.pool
    )
    assert free.title == "🏆 Tiers Achieved"
    assert free.description == (
        f"<@{USER}>, you have reached **`2`** new tiers and unlocked the following rewards!"
    )
    assert [field.name for field in free.fields] == [
        "New Drop Pack",
        " Shop Discount +10% 🏷️",
    ]
    assert free.fields[0].value.startswith("-# **Tier `1`:**")
    assert paid.title == "🏆 Elite Tiers Achieved"
    assert track.quest.await_count == 2
    assert len(paid.fields) == 3
    assert (free.color.value, paid.color.value) == (0xFFD700, 0xFA0ADD)
    assert await progress(track.pool, "prestige") == 2
    assert await track.pool.fetchval("SELECT claimed_tiers FROM minigame_elite") == [
        1,
        2,
        3,
    ]


async def test_tier_already_reached_is_not_paid_again(track):
    free, paid = await track.track.check_tier_rewards(
        GUILD, USER, 100, 199, track.channel, client=track, pool=track.pool
    )
    assert (free.title, paid.title, free.fields, paid.fields) == (None, None, [], [])
    track.packs.assert_not_awaited()


async def test_expired_elite_gets_free_rewards_only(track):
    await elite(track.pool, expires=NOW)
    free, paid = await track.track.check_tier_rewards(
        GUILD, USER, 0, 100, track.channel, client=track, pool=track.pool
    )
    assert (len(free.fields), len(paid.fields)) == (1, 0)
    assert free.description.startswith(f"<@{USER}>, you have reached **`1`** new tier ")
    assert await progress(track.pool, "prestige") == 0


@pytest.mark.parametrize(
    "old, new, packs", [(300, 2799, 0), (300, 2800, 1), (2800, 7800, 2), (0, 5300, 2)]
)
async def test_bonus_packs_past_the_end_of_the_track(track, old, new, packs):
    track.packs.reset_mock()
    await track.track.check_tier_rewards(
        GUILD, USER, old, new, track.channel, client=None, pool=track.pool
    )
    bonus = [call for call in track.packs.await_args_list if call.args[4]]
    assert len(bonus) == packs


async def test_bonus_packs_are_doubled_for_elite(track):
    await elite(track.pool)
    await track.track.check_tier_rewards(
        GUILD, USER, 300, 2800, track.channel, client=None, pool=track.pool
    )
    assert [call.args[3] for call in track.packs.await_args_list] == [False, True]


async def test_elite_catch_up_pays_unclaimed_tiers_and_bonus_packs(track):
    await elite(track.pool, claimed=[1])
    lines = await track.track.grant_elite_rewards_up_to_tier(
        GUILD, USER, track.channel, 5300, client=track, pool=track.pool
    )
    assert lines == [
        "-# - **Tier 2:** Drop Pack",
        "-# - **Tier 3:** Prestige +1",
        "-# - `x2` Elite Bonus Drop Pack (dropped at <#30>)",
    ]
    assert await progress(track.pool, "prestige") == 1
    assert track.packs.await_count == 3


async def test_elite_is_active_until_it_expires(track):
    active = track.track.is_elite_active
    assert await active(track.pool, USER, GUILD) is False
    await elite(track.pool, expires=NOW + 1)
    assert await active(track.pool, USER, GUILD) is True
    await track.pool.execute("UPDATE minigame_elite SET expires_at = $1", NOW)
    assert await active(track.pool, USER, GUILD) is False
    broken = MagicMock(fetchval=AsyncMock(side_effect=OSError))
    broken.acquire.side_effect = OSError
    assert await active(broken, USER, GUILD) is False


async def test_every_known_reward_of_every_season_is_paid_and_announced(track):
    texts = sorted(
        {
            tier[side]
            for season in config.SEASONS
            for tier in season.track_data
            for side in ("free", "elite")
            if tier[side].split("|")[0].strip() in config.REWARD_TYPES
        }
    )
    assert len(texts) > 20
    texts.sort(key=lambda text: text != "Unlocks Mora Gifting")  # only pays once
    for text in texts:
        title, description = await track.track.grant_reward(
            GUILD, USER, text, 5, track.channel, client=track, pool=track.pool
        )
        assert title and description, text
    assert await progress(track.pool, "gift_tax") is not None
    assert await progress(track.pool, "mora_boost") > 0
    assert await progress(track.pool, "minigame_summons") > 0
    assert await progress(track.pool, "chest_upgrades") > 4


async def cosmetics(pool, column):
    """Gives one stored value of the test member's cosmetics."""
    return await pool.fetchval(
        f"SELECT {column} FROM minigame_cosmetics WHERE gid = $1 AND uid = $2",
        GUILD,
        USER,
    )


async def pay(track, text, elite=False):
    """Pays tier 5's reward to the test member."""
    return await track.track.grant_reward(
        GUILD, USER, text, 5, track.channel, elite, track, track.pool
    )


@pytest.mark.parametrize(
    "text, column, title",
    [
        (
            "Custom GIF Background",
            "selected_animated_background_unlocked",
            " Custom GIF Background Unlocked 🖼️",
        ),
        ("Custom Card Font", "selected_font_unlocked", " Custom Card Font Unlocked 🔤"),
        ("Custom Title", "selected_custom_title_unlocked", " Custom Title Unlocked 📍"),
        ("Custom Accent Color", "embed_color", " Custom Accent Color Unlocked 🎨"),
        ("Custom Embed Color", "embed_color", " Custom Accent Color Unlocked 🎨"),
    ],
)
async def test_unlock_rewards_set_only_their_own_flag(track, text, column, title):
    flags = "selected_animated_background_unlocked, selected_font_unlocked, selected_custom_title_unlocked, embed_color"
    assert (await pay(track, text))[0] == title
    row = await track.pool.fetchrow(f"SELECT {flags} FROM minigame_cosmetics")
    assert [name for name, on in row.items() if on] == [column]


async def test_background_title_and_frames_are_stored_by_name(track):
    said = await pay(track, "Animated Background | assets/backgrounds/Night Sky.gif")
    assert said[0] == " Animated Inventory Background Unlocked 🖼️"
    assert "You have unlocked **Night Sky**!" in said[1]
    said = await pay(track, "Server Title | Star | Gazer", elite=False)
    assert said[0] == " Server Title Unlocked 📍"
    assert "**Star**" in said[1]
    said = await pay(track, "Static Frame | assets/frames/Gold Ring.png")
    assert said[0] == " Static Profile Frame Unlocked 👤"
    assert "**Gold Ring**" in said[1]
    said = await pay(track, "Animated Frame | assets/frames/Fire.gif")
    assert said[0] == " **Animated** Profile Frame Unlocked 👤"
    assert await cosmetics(track.pool, "backgrounds") == ["Night Sky"]
    assert await cosmetics(track.pool, "titles") == [[str(NOW * 1000), "Star"]]
    assert await cosmetics(track.pool, "frames") == ["Gold Ring.png", "Fire.gif"]


async def test_express_chests_and_prestige_wording(track):
    await elite(track.pool)
    assert (await pay(track, "Express Daily Chests"))[0] == " Express Daily Chests ⚡"
    assert await progress(track.pool, "express_daily_chests") is True
    assert "end of the free track" in (await pay(track, "Prestige +1"))[1]
    assert "end of the elite track" in (await pay(track, "Prestige +1", True))[1]


@pytest.mark.parametrize(
    "text, column, start, stored, title",
    [
        ("Mora Gain Boost +5%", "mora_boost", 10, 15, "Gain Boost +5% "),
        ("Mora Gain Boost +10%", "mora_boost", 10, 20, "Gain Boost +10% "),
        ("Mora Gain Boost +67%", "mora_boost", 10, 77, "Gain Boost +67% "),
        ("+10 Minigames Summon", "minigame_summons", 2, 12, "+10 Minigame Summons 🧲"),
        ("+1 Chest Upgrade Limit", "chest_upgrades", 6, 7, "+1 Chest Upgrades "),
        ("+69 Chest Upgrade Limit", "chest_upgrades", 6, 75, "+69 Chest Upgrades "),
        ("+3 Minigames Summon", "minigame_summons", 4, 7, "+3 Minigame Summons 🧲"),
        ("+30 Minigames Summon", "minigame_summons", 4, 34, "+30 Minigame Summons 🧲"),
        ("Shop Discount +10%", "shop_discount", 20, 30, " Shop Discount +10% 🏷️"),
        (
            "Kingdom Discount +10%",
            "domain_discount",
            20,
            30,
            " Domain Discount +10% 🏰",
        ),
        (
            "Kingdom Discount +10%",
            "domain_discount",
            45,
            50,
            " Domain Discount +10% 🏰",
        ),
        ("Mora Gift Tax -5%", "gift_tax", None, 25, "Gift Tax Reduced -5% "),
        ("Mora Gift Tax -5%", "gift_tax", 0, 0, "Gift Tax Reduced -5% "),
        ("Mora Gift Tax -5%", "gift_tax", 3, 0, "Gift Tax Reduced -5% "),
        ("Mora Gift Tax -5%", "gift_tax", 20, 15, "Gift Tax Reduced -5% "),
        ("Mora Gift Tax -10%", "gift_tax", None, 20, "Gift Tax Reduced -10% "),
        ("Mora Gift Tax -10%", "gift_tax", 5, 0, "Gift Tax Reduced -10% "),
    ],
)
async def test_number_rewards_store_the_new_total(
    track, text, column, start, stored, title
):
    await track.pool.execute(f"UPDATE minigame_progression SET {column} = $1", start)
    said = await pay(track, text)
    assert title in said[0]
    assert f"{stored}" in said[1]
    assert await progress(track.pool, column) == stored


async def test_gifting_unlocks_once_at_thirty(track):
    title, description = await pay(track, "Unlocks Mora Gifting")
    assert title.endswith(" Gifting Unlocked! :gift:")
    assert "`30%`" in description
    assert await progress(track.pool, "gift_tax") == 30
    await track.pool.execute("UPDATE minigame_progression SET gift_tax = 10")
    assert await pay(track, "Unlocks Mora Gifting") == (None, None)
    assert await progress(track.pool, "gift_tax") == 10


async def test_bonus_packs_count_from_the_end_of_the_track(track):
    for old, new in ((0, 300), (290, 300), (2799, 2800), (2800, 5299)):
        track.packs.reset_mock()
        await track.track.check_tier_rewards(
            GUILD, USER, old, new, track.channel, pool=track.pool
        )
        bonus = sum(call.args[4] for call in track.packs.await_args_list)
        assert bonus == (new == 2800), (old, new)


async def test_catch_up_bounds_and_inline_fields(track):
    await elite(track.pool)
    lines = await track.track.grant_elite_rewards_up_to_tier(
        GUILD, USER, track.channel, 200, client=track, pool=track.pool
    )
    assert lines == ["-# - **Tier 1:** Prestige +1", "-# - **Tier 2:** Drop Pack"]
    assert (
        len(
            await track.track.grant_elite_rewards_up_to_tier(
                GUILD, USER, track.channel, 300, client=track, pool=track.pool
            )
        )
        == 1
    )
    free, _ = await track.track.check_tier_rewards(
        GUILD, USER, 0, 100, track.channel, client=track, pool=track.pool
    )
    assert free.fields[0].inline is False


def test_every_reward_of_every_season_is_paid():
    from commands.Events import seasons

    jokes = {"pls", "dont", "buy"}  # the one-day April Fools track pays no elite reward
    for season in seasons.SEASONS:
        for tier in season.track_data:
            for side in ("free", "elite"):
                name = tier[side].split("|")[0].strip()
                assert name in config.REWARD_TYPES or name in jokes


async def test_an_elite_tier_reached_twice_at_once_is_paid_once(track):
    await elite(track.pool)
    pay = track.track.grant_reward
    said = await asyncio.gather(
        *(
            pay(GUILD, USER, "Prestige +1", 1, track.channel, True, pool=track.pool)
            for _ in range(8)
        )
    )
    assert sum(title is not None for title, _ in said) == 1
    assert await progress(track.pool, "prestige") == 1
    assert await track.pool.fetchval("SELECT claimed_tiers FROM minigame_elite") == [1]


async def test_an_elite_reward_without_a_stored_track_is_still_paid(track):
    pay = track.track.grant_reward
    said = await pay(
        GUILD, USER, "Prestige +1", 1, track.channel, True, pool=track.pool
    )
    assert said[0] is not None
    assert await progress(track.pool, "prestige") == 1


@pytest.mark.parametrize(
    "reward,column,total",
    [
        ("Mora Gain Boost +5%", "mora_boost", 40),
        ("+1 Chest Upgrade Limit", "chest_upgrades", 12),
        ("Mora Gift Tax -5%", "gift_tax", 0),
        ("Shop Discount +10%", "shop_discount", 50),
        ("Kingdom Discount +10%", "domain_discount", 50),
    ],
)
async def test_rewards_paid_at_the_same_moment_all_count(track, reward, column, total):
    pay = track.track.grant_reward
    await asyncio.gather(
        *(pay(GUILD, USER, reward, n, track.channel, pool=track.pool) for n in range(8))
    )
    assert await progress(track.pool, column) == total


async def test_gifting_unlocked_twice_at_once_is_announced_once(track):
    pay = track.track.grant_reward
    said = await asyncio.gather(
        *(
            pay(GUILD, USER, "Unlocks Mora Gifting", 1, track.channel, pool=track.pool)
            for _ in range(6)
        )
    )
    assert sum(title is not None for title, _ in said) == 1


async def test_xp_gained_at_the_same_moment_all_counts(track):
    from commands.Events.games import common

    client = SimpleNamespace(pool=track.pool)
    gains = await asyncio.gather(
        *(common.add_xp(USER, GUILD, 30, client) for _ in range(10))
    )
    assert await progress(track.pool, "xp") == 300
    assert sorted(old for _, old, _ in gains) == list(range(0, 300, 30))
    assert all(new - old == 30 for _, old, new in gains)
    assert max(tier for tier, _, _ in gains) == 3


async def test_xp_for_a_new_member_starts_from_zero(track):
    from commands.Events.games import common

    await track.pool.execute("DELETE FROM minigame_progression")
    gain = await common.add_xp(USER, GUILD, 150, SimpleNamespace(pool=track.pool))
    assert gain == (1, 0, 150)
