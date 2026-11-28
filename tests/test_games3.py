import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from commands.Events import chat, chests, helperFunctions
from commands.Events.config import NO_EMOTE
from tests.games import GUILD, Channel, Message, client, member, mora, press, won

# --- Daily chests ---

LINES = [
    "the weather is lovely today",
    "has anyone seen my other sock",
    "i think pancakes beat waffles",
    "what a strange little afternoon",
    "nobody expects the ninth line",
    "one more thought before dinner",
    "and yet another idea appears",
]


@pytest.fixture
def cog(client, monkeypatch):
    """A cog stand-in whose chest system has no cooldown between messages."""
    from commands.Events.event import UserFlags

    monkeypatch.setattr(chests, "COOLDOWN", 0)
    monkeypatch.setattr(chests, "update_quest", helperFunctions_quest(client))
    system = chests.DailyChestSystem(UserFlags(client.pool))
    return SimpleNamespace(client=client, pending_chests=set(), chest_system=system)


def helperFunctions_quest(client):
    async def update_quest(uid, gid, cid, quest, bot, **_):
        client.quests.append((uid, quest))

    return update_quest


async def said(cog, channel, uid: int, lines) -> None:
    for line in lines:
        await cog.chest_system.process_message(Message(channel, member(uid), line), cog)


@pytest.mark.parametrize(
    "content, last, counts",
    [
        ("short", "", False),
        ("ha ha ha ha ha ha", "", False),
        ("yessssss indeed", "", False),
        ("a perfectly fine sentence", "", True),
        ("a perfectly fine sentence", "a perfectly fine sentence!", False),
    ],
)
def test_which_messages_count_towards_a_chest(content, last, counts):
    assert chests.is_effortful(content, last) is counts


def test_next_reset_is_the_coming_midnight_utc():
    reset = datetime.datetime.fromtimestamp(chests.get_next_reset_unix(), datetime.timezone.utc)  # fmt: skip
    now = datetime.datetime.now(datetime.timezone.utc)
    assert (
        reset.time() == datetime.time() and 0 < (reset - now).total_seconds() <= 86400
    )


async def test_chest_spawns_once_after_enough_messages(client, cog, monkeypatch):
    monkeypatch.setattr(chests.random, "randint", lambda low, high: high)
    channel = Channel()
    await said(cog, channel, 5, LINES[:5])
    assert channel.sent == []
    await said(cog, channel, 5, LINES[5:])
    assert len(channel.sent) == 1 and cog.pending_chests == {(5, GUILD)}
    chest = channel.last
    assert chest.content.startswith("<@5>, claim this chest <t:")
    assert (
        chest.embed.title == "Daily Mora Chest Unlocked! <a:tada:1227425729654820885>"
    )
    assert "**Common Chest** - *" in chest.embed.description and "`2,500`" in chest.embed.description  # fmt: skip
    assert "**Messages counted:** `6`" in chest.embed.description
    assert chest.embed.footer.text == "This chest spawned after you sent 6 effortful messages in minigame channels today"  # fmt: skip
    assert [child.label for child in chest.view.children] == ["Upgrade", "Claim", "What is this?"]  # fmt: skip


async def test_chest_state_survives_a_restart(client, cog, monkeypatch):
    monkeypatch.setattr(chests.random, "randint", lambda low, high: high)
    channel = Channel()
    await said(cog, channel, 5, LINES[:5])
    cog.chest_system.reset_daily_states()
    await said(cog, channel, 5, LINES[5:6])
    assert len(channel.sent) == 1
    cog.chest_system.reset_daily_states()
    await said(cog, channel, 5, LINES[:6])
    assert len(channel.sent) == 1


async def test_messages_at_the_same_moment_give_one_chest(client, cog, monkeypatch):
    monkeypatch.setattr(chests.random, "randint", lambda low, high: 1)
    channel = Channel()
    system = cog.chest_system
    await asyncio.gather(*(system.process_message(Message(channel, member(5), line), cog) for line in LINES))  # fmt: skip
    assert len(channel.sent) == 1 and system.counting == set()


async def test_member_who_turned_chests_off_gets_none(client, cog, monkeypatch):
    monkeypatch.setattr(chests.random, "randint", lambda low, high: 1)
    await helperFunctions.upsert_user_minigame_setting(client.pool, GUILD, 5, "chest_disabled", True)  # fmt: skip
    channel = Channel()
    await said(cog, channel, 5, LINES)
    assert channel.sent == []
    await helperFunctions.upsert_user_minigame_setting(client.pool, GUILD, 5, "chest_disabled", False)  # fmt: skip
    cog.chest_system.invalidate_flag_cache(GUILD, 5)
    await said(cog, channel, 5, LINES[:1])
    assert len(channel.sent) == 1


async def test_chest_in_a_channel_the_bot_cannot_post_in(client, cog, monkeypatch):
    monkeypatch.setattr(chests.random, "randint", lambda low, high: 1)
    channel = Channel()

    async def refuse(*_, **__):
        raise discord.Forbidden(SimpleNamespace(status=403, reason="no"), "no")

    channel.send = refuse
    await said(cog, channel, 5, LINES[:1])
    assert cog.pending_chests == set()


async def chest(client, cog, monkeypatch, streak_from=None):
    """Gives member 5 a chest at once; gives its message."""
    monkeypatch.setattr(chests.random, "randint", lambda low, high: 1)
    if streak_from:
        await helperFunctions.upsert_chest_streaks(client.pool, GUILD, 5, 3, 7, streak_from.isoformat())  # fmt: skip
    channel = Channel()
    await said(cog, channel, 5, LINES[:1])
    return channel.last


async def test_claim_pays_base_and_streak_once(client, cog, monkeypatch):
    yesterday = chests.today() - datetime.timedelta(days=1)
    game = await chest(client, cog, monkeypatch, yesterday)
    view = game.view
    assert "`4` day" in game.embed.description and "`+400`" in game.embed.description
    assert (await press(client, game, 6, label="Claim")).said == [f"{NO_EMOTE} This isn't your chest!"]  # fmt: skip
    monkeypatch.setattr(chests.random, "random", lambda: 0.99)
    first = await press(client, game, 5, label="Claim")
    game.view = view
    second = await press(client, game, 5, label="Claim")
    assert second.deferred and second.said == []
    late = await press(client, game, 5, label="Upgrade")
    assert late.deferred and "Claimed!" in game.embed.title
    assert await mora(client.pool) == {5: 2900}
    assert game.content == "<@5>" and "Common Chest Claimed!" in game.embed.title
    assert "-# Base: " in game.embed.fields[0].value and "Realm Bonus" not in game.embed.fields[0].value  # fmt: skip
    assert "📦 **Total:** `1`" in game.embed.fields[2].value
    assert cog.pending_chests == set()
    assert won(client, 5) == [{"collect_chests": 1, "earn_mora": 2900}]
    streaks = await helperFunctions.get_chest_streaks(client.pool, GUILD, 5)
    assert (streaks["streak"], streaks["max_streak"]) == (4, 7)
    assert await helperFunctions.get_chest_counts(client.pool, GUILD, 5) == [1, 0, 0, 0]
    assert len(first.said) == 1


async def test_streak_starts_over_after_a_missed_day(client, cog, monkeypatch):
    game = await chest(client, cog, monkeypatch, chests.today() - datetime.timedelta(days=2))  # fmt: skip
    assert "`1` day " in game.embed.description and "`+100`" in game.embed.description


async def test_upgrades_move_the_tier_until_they_run_out(client, cog, monkeypatch):
    game = await chest(client, cog, monkeypatch)
    view = game.view
    rolls = iter([0.0, 0.99, 0.0, 0.0])
    monkeypatch.setattr(chests, "random", SimpleNamespace(random=lambda: next(rolls)))
    tiers = []
    for _ in range(view.clicks_remaining):
        await press(client, game, 5, label="Upgrade")
        tiers.append(view.tier)
    assert tiers == ["Exquisite", "Exquisite", "Precious", "Luxurious"]
    assert game.embed.title == "Daily Mora Chest 🎁 (Luxurious)"
    assert "Upgrades left: `0`" in game.embed.description
    assert [child.label for child in view.children] == ["Claim", "What is this?"]
    explained = await press(client, game, 5, label="What is this?")
    assert "***Next reset at** <t:" in explained.said[0].description
    monkeypatch.setattr(chests, "random", SimpleNamespace(random=lambda: 0.99))
    await press(client, game, 5, label="Claim")
    assert await mora(client.pool) == {5: 30100}
    assert await helperFunctions.get_chest_counts(client.pool, GUILD, 5) == [0, 0, 0, 1]


async def test_unclaimed_chest_times_out(client, cog, monkeypatch):
    game = await chest(client, cog, monkeypatch)
    await game.view.on_timeout()
    assert game.embed.description.startswith(
        "⏳ <@5> did not claim their chest in time."
    )
    assert isinstance(game.view, chests.PersistentChestInfoView)
    assert cog.pending_chests == set() and await mora(client.pool) == {}


async def test_buttons_left_under_a_chest(client):
    channel = Channel()
    game = await channel.send("<@5>", view=chests.PersistentChestInfoView())
    ids = [getattr(child, "custom_id", None) for child in game.view.children]
    assert ids[:2] == ["persistent_chest_info_view", "persistent_chest_delete"]
    explained = await press(client, game, 6, index=0)
    assert "Next reset at" in explained.said[0].description
    assert (await press(client, game, 6, index=1)).said == [f"{NO_EMOTE} This isn't your chest!"]  # fmt: skip
    await press(client, game, 5, index=1)
    assert game.deleted


# --- Sigils for chatting ---


@pytest.mark.parametrize(
    "content, last, counts",
    [
        ("hey", "", False),
        ("<:a:1> <a:b:2>", "", False),
        ("look at https://example.com", "", False),
        ("join discord.gg/abc now", "", False),
        ("a real message", "", True),
        ("A Real Message", "a real message", False),
    ],
)
def test_which_messages_count_towards_sigils(content, last, counts):
    assert chat.is_effortful(content, last) is counts


async def chatted(system, channel, author, lines, settings, client) -> None:
    for line in lines:
        await system.process_chat_sigils(Message(channel, author, line), settings, client)  # fmt: skip


async def test_sigils_paid_after_enough_messages_up_to_the_cap(client, monkeypatch):
    monkeypatch.setattr(chat, "COOLDOWN", 0)
    system = chat.DailySigilSystem(client.pool)
    channel = Channel()
    settings = {"chat_msg_range": [2], "chat_range": [40]}
    await chatted(system, channel, member(5), LINES[:1], settings, client)
    assert channel.sent == []
    await chatted(system, channel, member(5), LINES[1:2], settings, client)
    assert "<@5> earned" in channel.last.content
    assert "**40 " in channel.last.content and "*(Daily Cap: `40/60`)*" in channel.last.content  # fmt: skip
    await chatted(system, channel, member(5), LINES[2:4], settings, client)
    assert "**20 " in channel.last.content and "`60/60`" in channel.last.content
    await chatted(system, channel, member(5), LINES[4:6], settings, client)
    assert len(channel.sent) == 2
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    assert await helperFunctions.get_daily_sigils(client.pool, 5, GUILD, today) == {"earnings": 60}  # fmt: skip


async def test_sigil_counts_are_kept_per_server(client, monkeypatch):
    monkeypatch.setattr(chat, "COOLDOWN", 0)
    system = chat.DailySigilSystem(client.pool)
    here, there = Channel(), Channel()
    there.guild = SimpleNamespace(id=11, name="Other")
    settings = {"chat_msg_range": [2], "chat_range": [5]}
    for channel in (here, there):
        message = Message(channel, member(5), LINES[0])
        message.guild = channel.guild
        await system.process_chat_sigils(message, settings, client)
    assert here.sent == there.sent == []
    system.forget()
    assert (
        system.cooldowns == system.last_messages == {} and len(system.msg_counts) == 2
    )
    system.msg_counts[(GUILD, 5)] = 0
    system.forget()
    assert list(system.msg_counts) == [(11, 5)]


async def test_roles_raise_the_sigil_cap(client):
    system = chat.DailySigilSystem(client.pool)
    booster = member(5)
    booster.roles = [SimpleNamespace(id=70), SimpleNamespace(id=71), SimpleNamespace(id=72)]  # fmt: skip
    settings = {"chat_boosted_roles": ["70:+15", "71:100", "72:oops", "99:+500"]}
    assert await system.calculate_max_sigils(booster, 60, settings) == 100
    assert await system.calculate_max_sigils(booster, 60, {"chat_boosted_roles": ["71:50", "70:+15"]}) == 75  # fmt: skip
    assert await system.calculate_max_sigils(member(6), 60, settings) == 60


async def test_cooldown_skips_messages_sent_too_soon(client):
    system = chat.DailySigilSystem(client.pool)
    channel = Channel()
    settings = {"chat_msg_range": [2], "chat_range": [5]}
    await chatted(system, channel, member(5), LINES[:4], settings, client)
    assert channel.sent == [] and system.msg_counts[(GUILD, 5)] == 1


# --- The cog that drops minigames, and /summon ---


@pytest.fixture
def events(client, no_loops, monkeypatch):
    """The minigame cog with instant drops; `ran` lists the channels a minigame started in."""
    from commands.Events import event

    cog = event.TheEventItself(client)
    cog.ran = []

    async def game(channel, bot):
        cog.ran.append(channel.id)

    game.__name__ = "defeatTheBoss"
    monkeypatch.setattr(event, "LETTER_TO_EVENT", {"A": game})
    monkeypatch.setattr(event.asyncio, "sleep", real_sleep_none())
    event.active_channels.clear()
    return cog


def real_sleep_none():
    sleep = asyncio.sleep

    async def instant(seconds):
        await sleep(0)

    return instant


async def channel_settings(pool, **columns) -> None:
    names = ", ".join(["channel_id", *columns])
    places = ", ".join(f"${place}" for place in range(1, len(columns) + 2))
    await pool.execute(f"INSERT INTO minigame_settings ({names}) VALUES ({places})", 30, *columns.values())  # fmt: skip


def heard(
    channel, uid: int = 5, text: str = "a perfectly ordinary message", number: int = 100
):
    message = Message(channel, member(uid), text)
    message.id = number
    return message


def test_event_letters_and_names_are_unchanged():
    from commands.Events import event
    from commands.Events.config import LETTER_LIST

    names = [game.__name__ for game in event.EVENTS]
    assert len(names) == 26 and names[0] == "defeatTheBoss" and names[-1] == "ticTacTok"
    assert event.LETTER_TO_EVENT[LETTER_LIST[4]].__name__ == "splitOrSteal"
    assert event.LETTER_TO_EVENT[LETTER_LIST[23]].__name__ == "bankHeist"
    shown = {game.__name__: event.display_name(game) for game in event.EVENTS}
    assert shown["defeatTheBoss"] == "Defeat the Boss"
    assert shown["matchThePFP"] == "Match the PFP"
    assert shown["hsrEmojiRiddle"] == "HSR Emoji Riddle"
    assert shown["pickUpTheWatermelon"] == "Pick Up the Watermelon"
    assert shown["twoTruthsAndALie"] == "Two Truths And A Lie"
    assert shown["ticTacTok"] == "Tic Tac Tok"


async def test_extension_adds_both_cogs(client, no_loops):
    from commands.Events import event

    await event.setup(client)
    added = [call.args[0] for call in client.add_cog.await_args_list]
    assert [type(cog).__name__ for cog in added] == ["TheEventItself", "Summon"]


async def test_minigame_drops_on_the_right_message_only(client, events):
    await channel_settings(client.pool, minigames_list=["A"], minigames_frequency=50)
    channel = Channel()
    await events.on_message(heard(channel, number=101))
    assert channel.sent == [] and events.ran == []
    await events.on_message(heard(channel, number=100))
    assert "dropping a random event in `3 seconds`" in channel.sent[0].embed.description
    assert events.ran == [30]


@pytest.mark.parametrize(
    "columns",
    [
        {"minigames_list": [], "minigames_frequency": 50},
        {"minigames_list": ["?"], "minigames_frequency": 50},
        {"minigames_list": ["A"], "minigames_frequency": 0},
        {
            "minigames_list": ["A"],
            "minigames_frequency": 50,
            "minigames_enabled": False,
        },
    ],
)
async def test_nothing_drops_when_the_channel_has_nothing_to_drop(
    client, events, columns
):
    await channel_settings(client.pool, **columns)
    channel = Channel()
    await events.on_message(heard(channel))
    assert channel.sent == [] and events.ran == []


async def test_nothing_drops_without_settings_for_bots_or_in_dms(client, events):
    channel = Channel()
    await events.on_message(heard(channel))
    await channel_settings(client.pool, minigames_list=["A"], minigames_frequency=50)
    events.cache.invalidate_all()
    bot = heard(channel)
    bot.author.bot = True
    await events.on_message(bot)
    direct = heard(channel)
    direct.guild = None
    await events.on_message(direct)
    from commands.Events import event

    await events.on_message(heard(channel, uid=event.IGNORED_MEMBER))
    assert channel.sent == [] and events.ran == []


async def test_nothing_drops_right_after_an_embed_of_the_bot_or_while_one_runs(client, events):  # fmt: skip
    from commands.Events import event

    await channel_settings(client.pool, minigames_list=["A"], minigames_frequency=50)
    channel = Channel()
    channel.past = [Message(channel, client.user, embed=discord.Embed(title="x"))]
    await events.on_message(heard(channel))
    channel.past = []
    event.active_channels.add(30)
    await events.on_message(heard(channel))
    assert channel.sent == []
    event.active_channels.clear()
    await helperFunctions.upsert_user_minigame_setting(client.pool, GUILD, 5, "minigame_disabled", True)  # fmt: skip
    events.user_flags.invalidate(GUILD, 5)
    await events.on_message(heard(channel))
    assert channel.sent == []
    await events.on_message(heard(channel, uid=6))
    assert events.ran == [30] and event.active_channels == set()


async def test_crashed_minigame_is_reported_and_frees_the_channel(client, events, monkeypatch):  # fmt: skip

    from commands.Events import event

    async def broken(channel, bot):
        raise RuntimeError("boom")

    monkeypatch.setattr(event, "LETTER_TO_EVENT", {"A": broken})
    owner = AsyncMock()
    client.fetch_user = AsyncMock(return_value=owner)
    await channel_settings(client.pool, minigames_list=["A"], minigames_frequency=50)
    channel = Channel()
    await events.on_message(heard(channel))
    assert channel.last.embed.description == "Event crashed: `boom`"
    assert channel.last.embed.footer.text == "Error has been logged and developer has been notified."  # fmt: skip
    owner.send.assert_awaited_once_with(f"Event crashed: {channel.last.jump_url}")
    assert event.active_channels == set()


async def test_channel_settings_are_read_once_a_minute(client, events):
    assert await events.cache.get_channel(30) is None
    await channel_settings(client.pool, minigames_list=["A"])
    assert await events.cache.get_channel(30) is None
    events.cache.invalidate_all()
    assert (await events.cache.get_channel(30))["minigames_list"] == ["A"]


async def test_failed_settings_read_is_tried_again(client, events):
    await channel_settings(client.pool, minigames_list=["A"])
    events.cache.pool = SimpleNamespace(fetch=AsyncMock(side_effect=OSError))
    with pytest.raises(OSError):
        await events.cache.get_channel(30)
    events.cache.pool = client.pool
    assert (await events.cache.get_channel(30))["minigames_list"] == ["A"]


async def test_messages_at_a_cold_start_all_get_settings(client, events):
    await channel_settings(client.pool, minigames_list=["A"])
    fetch = AsyncMock(side_effect=client.pool.fetch)
    events.cache.pool = SimpleNamespace(fetch=fetch)
    found = await asyncio.gather(*(events.cache.get_channel(30) for _ in range(20)))
    assert all(found) and fetch.await_count == 1


async def test_chests_and_sigils_follow_the_channel_settings(
    client, events, monkeypatch
):
    from unittest.mock import AsyncMock

    events.chest_system.process_message = AsyncMock()
    events.sigil_system.process_chat_sigils = AsyncMock()
    await channel_settings(client.pool, minigames_enabled=False, chests_enabled=True, chat_enabled=True)  # fmt: skip
    channel = Channel()
    message = heard(channel)
    await events.on_message(message)
    events.chest_system.process_message.assert_awaited_once_with(message, events)
    assert events.sigil_system.process_chat_sigils.await_count == 1
    await helperFunctions.upsert_user_minigame_setting(client.pool, GUILD, 5, "sigils_disabled", True)  # fmt: skip
    events.user_flags.invalidate(GUILD, 5)
    await events.on_message(heard(channel))
    assert events.sigil_system.process_chat_sigils.await_count == 1
    await events.daily_reset()
    assert events.user_flags.flags == {}


async def test_add_mora_is_for_its_admins_and_adds_the_exact_amount(client, events):
    from commands.Events import event

    channel = Channel()
    refused = heard(channel, text="-addMora <@7> 500")
    await events.on_message(refused)
    refused.add_reaction.assert_awaited_once_with(NO_EMOTE)
    await events.on_message(heard(channel, uid=event.OWNER, text="-addMora <@!7> 1500"))
    assert await mora(client.pool) == {7: 1500}
    assert "Added exactly" in channel.last.content and "`1,500` to <@7>'s inventory." in channel.last.content  # fmt: skip
    await events.on_message(heard(channel, text="please -addMora <@7> 500"))
    assert await mora(client.pool) == {7: 1500}


async def test_add_xp_is_for_the_owner(client, events, monkeypatch):
    from unittest.mock import AsyncMock

    from commands.Events import event

    monkeypatch.setattr(event, "check_tier_rewards", AsyncMock())
    channel = Channel()
    refused = heard(channel, text="-addXP <@7> 500")
    await events.on_message(refused)
    refused.add_reaction.assert_awaited_once_with(NO_EMOTE)
    await events.on_message(heard(channel, uid=event.OWNER, text="-addXP 7 500"))
    assert channel.last.content == "Mention a user!"
    given = heard(channel, uid=event.OWNER, text="-addXP <@7> 500")
    given.mentions = [member(7)]
    await events.on_message(given)
    assert channel.last.content.startswith("Added `500` XP to <@7>. Reached tier `")
    assert event.check_tier_rewards.await_args.kwargs["old_xp"] == 0
    bad = heard(channel, uid=event.OWNER, text="-addXP <@7> lots")
    bad.mentions = [member(7)]
    await events.on_message(bad)
    assert channel.last.content.startswith("Error: ")


async def summoned(client, cog, uid: int, minigame: str):
    """Runs /summon as a member; gives the interaction."""
    from tests.games import Press

    channel = Channel()
    interaction = Press(client, Message(channel), uid)
    await cog.summon.callback(cog, interaction, minigame)
    return interaction


@pytest.fixture
def summon(client, monkeypatch):
    from unittest.mock import AsyncMock

    from commands.Events import event

    monkeypatch.setattr(event, "update_quest", AsyncMock())
    cog = event.Summon(client)
    cog.ran = []

    async def game(channel, bot):
        cog.ran.append(channel.id)

    cog.minigame_mapping["defeatTheBoss"] = game
    return cog


async def summons(pool, uid: int, count: int = None):
    if count is not None:
        await helperFunctions.ensure_progression_user(pool, GUILD, uid)
        await pool.execute("UPDATE minigame_progression SET minigame_summons = $1 WHERE gid = $2 AND uid = $3", count, GUILD, uid)  # fmt: skip
    return await pool.fetchval("SELECT minigame_summons FROM minigame_progression WHERE gid = $1 AND uid = $2", GUILD, uid)  # fmt: skip


async def test_summon_uses_one_summon_and_starts_the_minigame(client, summon):
    await summons(client.pool, 5, 2)
    done = await summoned(client, summon, 5, "defeatTheBoss")
    embed = done.said[0]
    assert embed.title == ":magnet: Minigame Summoned!"
    assert (
        embed.description
        == "<@5> successfully started the **Defeat the Boss** minigame."
    )
    assert embed.footer.text == "You have 1 summon remaining"
    assert summon.ran == [30] and await summons(client.pool, 5) == 1


async def test_summon_refuses_unknown_minigames_and_empty_pockets(client, summon):
    assert (await summoned(client, summon, 5, "nope")).said == [f"{NO_EMOTE} Invalid minigame selection!"]  # fmt: skip
    assert (await summoned(client, summon, 5, "defeatTheBoss")).said == [f"{NO_EMOTE} You don't have any minigame summons left!"]  # fmt: skip
    assert summon.ran == []


async def test_summons_at_the_same_moment_cannot_use_one_summon_twice(client, summon):
    await summons(client.pool, 5, 1)
    await asyncio.gather(
        *(summoned(client, summon, 5, "defeatTheBoss") for _ in range(5))
    )
    assert summon.ran == [30] and await summons(client.pool, 5) == 0


async def test_encore_keeps_the_summon(client, summon, monkeypatch):
    from unittest.mock import AsyncMock

    from commands.Events import event

    monkeypatch.setattr(event, "get_encore_chance", AsyncMock(return_value=80))
    monkeypatch.setattr(event.random, "random", lambda: 0.49)
    await summons(client.pool, 5, 1)
    done = await summoned(client, summon, 5, "defeatTheBoss")
    assert done.said[0].footer.text == "You have 1 summon remaining | 🎭 Encore! This summon is not consumed."  # fmt: skip
    assert await summons(client.pool, 5) == 1
    monkeypatch.setattr(event.random, "random", lambda: 0.5)
    await summoned(client, summon, 5, "defeatTheBoss")
    assert await summons(client.pool, 5) == 0


async def test_summon_autocomplete_matches_the_shown_names(client, summon):
    choices = await summon.minigame_autocomplete(None, "pfp")
    assert [(choice.name, choice.value) for choice in choices] == [("Match the PFP", "matchThePFP")]  # fmt: skip
    assert len(await summon.minigame_autocomplete(None, "")) == 25
