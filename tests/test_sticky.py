import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands as ext

from commands.Help import help as help_page
from commands.Sticky import stickyCommand, stickyEvent
from commands.Sticky import stickyStore as store

CHANNEL, OTHER = 111, 222


def channel(channel_id=CHANNEL):
    """A channel that remembers what it was sent and what was deleted in it."""
    found = MagicMock()
    found.id = channel_id
    found.deleted = []
    found.next_id = channel_id * 10

    async def fetch_message(message_id):
        if message_id in found.deleted:
            raise discord.NotFound(MagicMock(status=404), "gone")
        old = MagicMock()
        old.delete = AsyncMock(side_effect=lambda: found.deleted.append(message_id))
        return old

    async def send(content):
        found.next_id += 1
        msg = MagicMock()
        msg.id, msg.channel, msg.content = found.next_id, found, content
        msg.delete = AsyncMock(side_effect=lambda: found.deleted.append(msg.id))
        return msg

    found.fetch_message = fetch_message
    found.send = AsyncMock(side_effect=send)
    return found


@pytest.fixture
async def env(pool, monkeypatch):
    monkeypatch.setattr(stickyEvent, "DELAY", 0.05)
    bot = MagicMock()
    bot.pool = pool
    cog = stickyEvent.StickyHandler(bot)
    bot.get_cog = lambda name: cog if name == "StickyHandler" else None
    await cog.cog_load()
    return types.SimpleNamespace(bot=bot, pool=pool, cog=cog, channel=channel())


async def stuck(pool):
    rows = await pool.fetch(
        "SELECT channel_id, message_id, content FROM sticky_messages ORDER BY id"
    )
    return [tuple(row) for row in rows]


async def watch(env, *messages):
    """Turns the channel on with these (message id, content) stuck to it."""
    for message_id, content in messages:
        await store.add(env.pool, CHANNEL, message_id, content)
    await store.enable(env.pool, CHANNEL)
    await env.cog.load()


async def message(env, author=None):
    found = MagicMock()
    found.author = author or MagicMock()
    found.channel = env.channel
    await env.cog.on_message(found)
    return env.cog.waiting.get(CHANNEL)


async def test_message_is_sent_again_after_the_channel_goes_quiet(env):
    await watch(env, (5, "rules"))
    await (await message(env))
    env.channel.send.assert_awaited_once_with("rules")
    assert env.channel.deleted == [5]
    assert await stuck(env.pool) == [(CHANNEL, 1111, "rules")]


async def test_every_new_message_starts_the_wait_again(env):
    await watch(env, (5, "rules"))
    first = await message(env)
    second = await message(env)
    await asyncio.gather(first, second, return_exceptions=True)
    assert env.channel.send.await_count == 1


async def test_the_bots_own_message_and_other_channels_start_nothing(env):
    await watch(env, (5, "rules"))
    assert await message(env, author=env.bot.user) is None
    env.channel.id = OTHER
    assert await message(env) is None


async def test_channel_with_a_message_but_not_watched_stays_quiet(env):
    await store.add(env.pool, CHANNEL, 5, "rules")
    await env.cog.load()
    assert await message(env) is None


async def test_watched_channel_without_a_message_sends_nothing(env):
    await store.enable(env.pool, CHANNEL)
    await env.cog.load()
    await (await message(env))
    env.channel.send.assert_not_awaited()


async def test_old_message_already_gone_is_still_replaced(env):
    await watch(env, (5, "rules"))
    env.channel.deleted.append(5)
    await (await message(env))
    assert await stuck(env.pool) == [(CHANNEL, 1111, "rules")]


async def test_several_messages_in_one_channel_take_turns(env):
    await watch(env, (5, "one"), (6, "two"))
    await (await message(env))
    assert await stuck(env.pool) == [(CHANNEL, 6, "two"), (CHANNEL, 1111, "one")]
    await (await message(env))
    assert await stuck(env.pool) == [(CHANNEL, 1111, "one"), (CHANNEL, 1112, "two")]
    assert env.channel.deleted == [5, 6]


async def test_message_whose_sticky_was_taken_meanwhile_is_deleted(env):
    await watch(env, (5, "rules"))
    send = env.channel.send.side_effect

    async def disabled_meanwhile(content):
        await store.take(env.pool, CHANNEL)
        return await send(content)

    env.channel.send.side_effect = disabled_meanwhile
    await (await message(env))
    assert await stuck(env.pool) == []
    assert env.channel.deleted == [5, 1111]


async def test_new_place_is_saved_even_when_the_wait_is_cancelled(env):
    await watch(env, (5, "rules"))
    send = env.channel.send.side_effect
    saving = asyncio.Event()
    move = store.move

    async def slow_move(*args):
        saving.set()
        await asyncio.sleep(0.05)
        return await move(*args)

    env.channel.send.side_effect = send
    stickyEvent.store = types.SimpleNamespace(**{**vars(store), "move": slow_move})
    try:
        task = await message(env)
        await saving.wait()
        task.cancel()
        await asyncio.sleep(0.2)
    finally:
        stickyEvent.store = store
    assert await stuck(env.pool) == [(CHANNEL, 1111, "rules")]


def interaction(env, here=None):
    found = MagicMock()
    found.client = env.bot
    found.channel = here or env.channel
    found.response.send_message = AsyncMock()
    return found


def commands(env):
    cog = stickyCommand.Sticky(env.bot)
    return types.SimpleNamespace(
        enable=cog.sticky_enable.callback.__get__(cog),
        disable=cog.sticky_disable.callback.__get__(cog),
        cog=cog,
    )


def answer(found):
    embed = found.response.send_message.call_args.kwargs["embed"]
    return embed.title, embed.colour.value


async def test_enable_sticks_the_message_and_watches_the_channel(env):
    found = interaction(env)
    await commands(env).enable(found, "rules")
    env.channel.send.assert_awaited_once_with("rules")
    assert await stuck(env.pool) == [(CHANNEL, 1111, "rules")]
    assert env.cog.enabled == {CHANNEL}
    assert answer(found) == ("Sticky message enabled!", 0x00FF00)
    assert found.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_enable_again_replaces_the_oldest_message(env):
    await watch(env, (5, "one"), (6, "two"))
    await commands(env).enable(interaction(env), "three")
    assert env.channel.deleted == [5]
    assert await stuck(env.pool) == [(CHANNEL, 6, "two"), (CHANNEL, 1111, "three")]
    assert await env.pool.fetchval("SELECT times FROM sticky_enabled") == 1


async def test_enable_for_another_channel_posts_where_the_command_was_used(env):
    here = channel(OTHER)
    await commands(env).enable(interaction(env, here), "rules", env.channel)
    here.send.assert_awaited_once_with("rules")
    env.channel.send.assert_not_awaited()
    assert await stuck(env.pool) == [(CHANNEL, 2221, "rules")]
    assert env.cog.enabled == {CHANNEL}


async def test_enable_answers_even_when_the_reload_fails(env, monkeypatch):
    monkeypatch.setattr(env.cog, "load", AsyncMock(side_effect=OSError))
    found = interaction(env)
    await commands(env).enable(found, "rules")
    assert answer(found) == ("Sticky message enabled!", 0x00FF00)


async def test_disable_removes_the_oldest_message_and_stops_watching(env):
    await watch(env, (5, "rules"))
    found = interaction(env)
    await commands(env).disable(found)
    assert env.channel.deleted == [5]
    assert await stuck(env.pool) == []
    assert env.cog.enabled == set()
    assert answer(found) == ("Sticky message disabled!", 0xFF0000)


async def test_disable_without_a_message_says_not_enabled(env):
    await store.enable(env.pool, CHANNEL)
    await env.cog.load()
    found = interaction(env)
    await commands(env).disable(found)
    assert answer(found) == ("Sticky message is not enabled!", 0xFFFF00)
    assert env.cog.enabled == {CHANNEL}


async def test_channel_listed_twice_needs_two_disables(env):
    await watch(env, (5, "one"), (6, "two"))
    await env.pool.execute("UPDATE sticky_enabled SET times = 2")
    await commands(env).disable(interaction(env))
    assert env.cog.enabled == {CHANNEL}
    assert await stuck(env.pool) == [(CHANNEL, 6, "two")]
    await commands(env).disable(interaction(env))
    assert env.cog.enabled == set()


async def test_disable_in_a_channel_that_was_not_listed_only_removes(env):
    await store.add(env.pool, CHANNEL, 5, "rules")
    found = interaction(env)
    await commands(env).disable(found)
    assert answer(found) == ("Sticky message disabled!", 0xFF0000)
    assert await stuck(env.pool) == []


async def test_command_errors_are_shown_to_the_user(env):
    found = interaction(env)
    cog = commands(env).cog
    await cog.sticky_enable_error(found, Exception("no"))
    await cog.sticky_disable_error(found, Exception("no"))
    found.response.send_message.assert_awaited_with("```no```", ephemeral=True)


def test_commands_look_the_same():
    group = stickyCommand.Sticky(MagicMock()).__cog_app_commands_group__
    assert group.name == "sticky" and group.guild_only
    shown = {
        c.name: (c.description, [p.name for p in c.parameters]) for c in group.commands
    }
    assert shown == {
        "enable": ("Enable sticky messages in a channel", ["message", "channel"]),
        "disable": ("Disable sticky messages in a channel", ["channel"]),
    }


@pytest.mark.parametrize("order", [("Command", "Event"), ("Event", "Command")])
async def test_commands_reach_the_listener_in_any_load_order(pool, order):
    bot = ext.Bot(command_prefix="-", intents=discord.Intents.none())
    bot.pool = pool
    for name in order:
        await bot.load_extension(f"commands.Sticky.sticky{name}")
    await store.enable(pool, CHANNEL)
    await stickyCommand.refresh(bot)
    assert bot.get_cog("StickyHandler").enabled == {CHANNEL}


async def test_leave_takes_one_off_and_forgets_at_zero(pool):
    await store.create(pool)
    await pool.execute("INSERT INTO sticky_enabled VALUES (1, 3), (2, 1)")
    await store.leave(pool, 1)
    await store.leave(pool, 2)
    await store.leave(pool, 9)
    assert [tuple(r) for r in await pool.fetch("SELECT * FROM sticky_enabled")] == [
        (1, 2)
    ]


async def test_two_takes_at_once_give_the_message_once(pool):
    await store.create(pool)
    await store.add(pool, CHANNEL, 5, "rules")
    taken = await asyncio.gather(*(store.take(pool, CHANNEL) for _ in range(10)))
    assert sorted(t for t in taken if t) == [5]


async def test_help_lists_each_stuck_message_in_channel_order(pool):
    await store.create(pool)
    for channel_id in (3, 1, 1, 7, 9):
        await store.add(pool, channel_id, 5, "rules")
    assert await store.channels(pool) == [3, 1, 1, 7, 9]
    guild = MagicMock()
    guild.text_channels = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
    guild.threads = [MagicMock(id=9)]
    assert await help_page.stuck_channels(pool, guild) == [1, 1, 3, 9]


async def test_take_during_a_save_still_finds_the_message(pool):
    await store.create(pool)
    for _ in range(40):
        await pool.execute("DELETE FROM sticky_messages")
        await store.add(pool, CHANNEL, 5, "rules")
        row = await store.oldest(pool, CHANNEL)
        moved, taken = await asyncio.gather(
            store.move(pool, row["id"], CHANNEL, 6, "rules"), store.take(pool, CHANNEL)
        )
        assert taken == (6 if moved else 5)
        assert await stuck(pool) == []


async def test_leaves_at_once_count_down_and_enable_is_not_lost(pool):
    await store.create(pool)
    await pool.execute("INSERT INTO sticky_enabled VALUES (1, 3)")
    await asyncio.gather(*(store.leave(pool, 1) for _ in range(2)))
    assert await pool.fetchval("SELECT times FROM sticky_enabled") == 1
    await asyncio.gather(store.leave(pool, 1), store.enable(pool, 1))
    await store.enable(pool, 1)
    assert await store.enabled(pool) == {1}
