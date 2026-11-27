import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs import presenceFilter
from commands.Tag import tagCommands, tagEvent
from commands.Tag import tagStore as store

GUILD, ROLE, LOG_CHANNEL, TAG_SERVER = 111, 222, 333, 999


def payload(user_id, tag_guild, roles, guild_id=GUILD):
    """A member as Discord sends it in a join or update event."""
    return {
        "guild_id": str(guild_id),
        "roles": [str(role) for role in roles],
        "joined_at": "2024-01-01T00:00:00+00:00",
        "flags": 0,
        "user": {
            "id": str(user_id),
            "username": "u",
            "discriminator": "0",
            "avatar": None,
            "primary_guild": {
                "identity_guild_id": str(tag_guild) if tag_guild else None,
                "identity_enabled": bool(tag_guild),
                "tag": "TAG" if tag_guild else None,
                "badge": None,
            },
        },
    }


class Guild:
    id = GUILD
    name = "Guild"

    def __init__(self, state):
        self._state = state
        self._members = {}
        self.role = MagicMock(spec=discord.Role)
        self.role.id = ROLE
        self.role.__ge__ = lambda a, b: False
        self.role.__lt__ = lambda a, b: False
        self.default_role = MagicMock()
        self.default_role.id = GUILD
        self.default_role.__lt__ = lambda a, b: True
        self.log = MagicMock()
        self.log.id = LOG_CHANNEL
        self.log.send = AsyncMock()
        self.me = MagicMock()
        self.me.guild_permissions.manage_roles = True
        self.scans = 0
        self.members = []

    def get_role(self, role_id):
        return self.role if role_id == ROLE else None

    def get_channel(self, channel_id):
        return self.log if channel_id == LOG_CHANNEL else None

    def get_member(self, member_id):
        return self._members.get(member_id)

    def fetch_members(self, limit=None):
        self.scans += 1

        async def members():
            for data in self.members:
                yield discord.Member(data=data, guild=self, state=self._state)

        return members()


@pytest.fixture
def discord_side(monkeypatch, no_loops):
    """A bot with one server, and a record of what reaches discord.py."""
    parsed = []
    state = MagicMock()
    state.store_user = lambda data, cache=True: discord.User(state=state, data=data)
    state.raw_presence_flag = False
    events = ("GUILD_MEMBER_ADD", "GUILD_MEMBER_UPDATE", "PRESENCE_UPDATE")
    original = {
        event: (lambda data, event=event: parsed.append((event, data)))
        for event in events
    }
    state.parsers = dict(original)
    guild = Guild(state)
    state._get_guild = lambda guild_id: guild if guild_id == GUILD else None
    bot = MagicMock()
    bot._connection = state
    bot.get_guild = state._get_guild
    master = MagicMock()
    master.send = AsyncMock()
    bot.get_channel = lambda channel_id: master
    bot.wait_until_ready = AsyncMock()
    add, remove = AsyncMock(), AsyncMock()
    monkeypatch.setattr(discord.Member, "add_roles", add)
    monkeypatch.setattr(discord.Member, "remove_roles", remove)
    return types.SimpleNamespace(
        state=state,
        guild=guild,
        bot=bot,
        master=master,
        add=add,
        remove=remove,
        parsed=parsed,
        original=original,
    )


@pytest.fixture
async def env(discord_side, pool):
    """The same, with the server set up for tag roles in Postgres."""
    discord_side.bot.pool = discord_side.pool = pool
    await store.create(pool)
    await store.set_roles(pool, GUILD, TAG_SERVER, ROLE, LOG_CHANNEL)
    await store.enable(pool, GUILD)
    return discord_side


async def start(env):
    cog = tagEvent.TagRoleHandler(env.bot)
    await cog.tag_check.coro(cog)
    return cog


async def settle(cog):
    while cog._tasks:
        await asyncio.gather(*cog._tasks)


async def send(env, cog, event, data):
    env.state.parsers[event](data)
    await settle(cog)


async def test_scans_once_at_start(env):
    env.guild.members = [payload(1, TAG_SERVER, [])]
    cog = await start(env)
    assert env.guild.scans == 1 and env.add.await_count == 1
    await cog.tag_check.coro(cog)
    assert env.guild.scans == 1


async def test_scans_again_after_an_hour_or_new_settings(env):
    cog = await start(env)
    settings, at = cog._last_sweep[GUILD]
    cog._last_sweep[GUILD] = (settings, at - tagEvent.SWEEP_INTERVAL - 1)
    await cog.tag_check.coro(cog)
    assert env.guild.scans == 2
    await store.set_roles(env.pool, GUILD, 555, ROLE, LOG_CHANNEL)
    await cog.tag_check.coro(cog)
    assert env.guild.scans == 3


async def test_update_gives_role_and_logs(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert env.parsed[-1][0] == "GUILD_MEMBER_UPDATE"
    assert env.add.await_count == 1 and env.remove.await_count == 0
    embed = env.guild.log.send.await_args.kwargs["embed"]
    assert "was given the tag role" in embed.description
    assert env.master.send.await_count == 1
    assert env.guild._members == {}


async def test_update_removes_role(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, None, [ROLE]))
    assert env.remove.await_count == 1 and env.add.await_count == 0


async def test_nothing_to_change(env):
    cog = await start(env)
    for data in (
        payload(5, 12345, []),
        payload(6, TAG_SERVER, [ROLE]),
        payload(7, None, []),
    ):
        await send(env, cog, "GUILD_MEMBER_UPDATE", data)
    assert env.add.await_count == 0 and env.remove.await_count == 0


async def test_join_with_tag(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_ADD", payload(8, TAG_SERVER, []))
    assert env.add.await_count == 1


async def test_other_server_ignored_and_repeat_skipped(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(9, TAG_SERVER, [], 4242))
    assert env.add.await_count == 0
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(9, TAG_SERVER, []))
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(9, TAG_SERVER, []))
    assert env.add.await_count == 1


async def test_role_above_bot_is_not_watched(env):
    env.guild.role.__ge__ = lambda a, b: True
    cog = await start(env)
    assert GUILD not in cog._active and env.guild.scans == 0
    assert env.guild.log.send.await_count == 1


async def test_unload_restores_parsers(env):
    cog = await start(env)
    cog.cog_unload()
    assert (
        env.state.parsers["GUILD_MEMBER_UPDATE"] is env.original["GUILD_MEMBER_UPDATE"]
    )


def test_presence_filter(discord_side):
    env = discord_side
    presenceFilter.PresenceFilter(env.bot)
    parse = env.state.parsers["PRESENCE_UPDATE"]
    parse({"guild_id": str(GUILD), "user": {"id": "1"}})
    parse({"guild_id": "77", "user": {"id": "1"}})
    assert env.parsed == []
    env.guild._members[1] = object()
    parse({"guild_id": str(GUILD), "user": {"id": "1"}})
    assert len(env.parsed) == 1
    env.state.raw_presence_flag = True
    parse({"guild_id": "77", "user": {"id": "1"}})
    assert len(env.parsed) == 2


THANKS_CHANNEL = 444


def thanks_channel(env):
    """Adds a channel to the server for thank-you messages and returns it."""
    channel = MagicMock()
    channel.send = AsyncMock()
    log = env.guild.get_channel
    env.guild.get_channel = lambda i: channel if i == THANKS_CHANNEL else log(i)
    return channel


async def test_thanks_in_channel_once_a_day(env):
    channel = thanks_channel(env)
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await store.set_message(
        env.pool, GUILD, "hi {mention} {user} {server} {tag}", "T", "", "#ff0000", ""
    )
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    content = channel.send.await_args.args[0]
    embed = channel.send.await_args.kwargs["embed"]
    assert content == "hi <@5> u Guild TAG"
    assert (embed.title, embed.description, embed.color.value) == ("T", "", 0xFF0000)
    assert embed.image.url is None

    cog._recent.clear()
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert env.add.await_count == 2 and channel.send.await_count == 1

    await env.pool.execute(
        "UPDATE tag_thanks_cooldown SET thanked_at = thanked_at - 86400"
    )
    cog._recent.clear()
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert channel.send.await_count == 2


async def test_thanks_by_dm_without_embed(env, monkeypatch):
    dm = AsyncMock()
    monkeypatch.setattr(discord.Member, "send", dm)
    await store.set_thanks(env.pool, GUILD, None, True)
    await store.set_message(env.pool, GUILD, "thanks", "", "", "", "")
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert dm.await_args.args == ("thanks",) and dm.await_args.kwargs == {"embed": None}


async def test_thanks_embed_defaults_to_blurple_with_image(env):
    channel = thanks_channel(env)
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await store.set_message(env.pool, GUILD, "", "", "", "", "https://x/y.png")
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    embed = channel.send.await_args.kwargs["embed"]
    assert embed.color == discord.Color.blurple()
    assert embed.image.url == "https://x/y.png"


async def test_no_thanks_set_up_starts_no_cooldown(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert await env.pool.fetchval("SELECT count(*) FROM tag_thanks_cooldown") == 0


async def test_removal_sends_no_thanks(env):
    channel = thanks_channel(env)
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, None, [ROLE]))
    embed = env.guild.log.send.await_args.kwargs["embed"]
    assert embed.description == "❌ <@5> had tag role removed"
    assert embed.fields[0].value == f"Guild ({GUILD})"
    assert channel.send.await_count == 0


async def test_incomplete_or_disabled_settings_are_not_watched(env):
    await env.pool.execute("UPDATE tag_roles SET tag_guild_id = NULL")
    cog = await start(env)
    assert cog._active == {}
    await store.set_roles(env.pool, GUILD, TAG_SERVER, ROLE, LOG_CHANNEL)
    await env.pool.execute("DELETE FROM tag_enabled")
    await cog.tag_check.coro(cog)
    assert cog._active == {} and env.guild.scans == 0


async def test_store_disable(env):
    await store.set_thanks(env.pool, GUILD, None, True)
    assert await store.disable(env.pool, GUILD) is True
    assert await store.watched(env.pool) == []
    assert await store.thanks(env.pool, GUILD) is None
    await store.enable(env.pool, GUILD)
    assert await store.disable(env.pool, GUILD) is False
    assert await env.pool.fetchval("SELECT count(*) FROM tag_enabled") == 1


async def test_set_thanks_keeps_the_message(env):
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await store.set_message(env.pool, GUILD, "c", "t", "d", "#000000", "i")
    await store.set_thanks(env.pool, GUILD, None, True)
    row = dict(await store.thanks(env.pool, GUILD))
    assert row == {
        "guild_id": GUILD,
        "channel_id": None,
        "dm": True,
        "content": "c",
        "title": "t",
        "description": "d",
        "color": "#000000",
        "image": "i",
    }


def interaction(env):
    """A slash command run in the test server."""
    run = MagicMock()
    run.guild = env.guild
    run.client = env.bot
    run.response.send_message = AsyncMock()
    run.response.send_modal = AsyncMock()
    run.response.defer = AsyncMock()
    run.followup.send = AsyncMock()
    return run


def sent(call):
    """The embed a command answered with, as (title, description, colour)."""
    embed = call.await_args.kwargs["embed"]
    assert call.await_args.kwargs["ephemeral"] is True
    return embed.title, embed.description, embed.colour.value


async def test_enable_command(env):
    await env.pool.execute("DELETE FROM tag_roles; DELETE FROM tag_enabled")
    cog = tagCommands.TagCommands(env.bot)
    run = interaction(env)
    user = MagicMock()
    user.primary_guild.id, user.primary_guild.tag = TAG_SERVER, "TAG"
    role, log = MagicMock(), MagicMock()
    role.id, role.mention, log.id, log.mention = ROLE, "<@&222>", LOG_CHANNEL, "<#333>"
    holder = MagicMock()
    holder.primary_guild.id, holder.primary_guild.tag = TAG_SERVER, "TAG"
    holder.roles, holder.mention, holder.add_roles = [], "<@7>", AsyncMock()
    log.send = AsyncMock()
    env.guild.members = [holder]
    await cog.tag_enable.callback(cog, run, user, role, log)
    assert sent(run.response.send_message) == (
        "✅ Tag Roles Enabled!",
        "Users with the tag **TAG** `999` will receive <@&222>.\n"
        "All actions will be logged in <#333>.",
        0x00FF00,
    )
    assert [tuple(row) for row in await store.watched(env.pool)] == [
        (GUILD, TAG_SERVER, ROLE, LOG_CHANNEL)
    ]
    holder.add_roles.assert_awaited_once_with(role)
    assert (
        log.send.await_args.kwargs["embed"].description
        == "✅ <@7> was given the tag role (initial setup)"
    )


async def test_enable_command_rejects_user_without_tag_data(env):
    cog = tagCommands.TagCommands(env.bot)
    run = interaction(env)
    user = MagicMock()
    user.primary_guild = None
    await cog.tag_enable.callback(cog, run, user, MagicMock(), MagicMock())
    run.response.send_message.assert_awaited_once_with(
        "❌ Erroreous sample user", ephemeral=True
    )


async def test_migrate_and_disable_commands(env):
    await env.pool.execute("DELETE FROM tag_enabled")
    cog = tagCommands.TagCommands(env.bot)
    run = interaction(env)
    await cog.tag_migrate.callback(cog, run)
    assert sent(run.response.send_message)[0] == "Tag roles migrated successfully!"
    assert len(await store.watched(env.pool)) == 1

    await cog.tag_disable.callback(cog, run)
    run.response.defer.assert_awaited_once_with(ephemeral=True)
    assert sent(run.followup.send) == (
        "✅ Tag Roles Disabled",
        "Tag role functionality has been disabled for this server.",
        0xFF0000,
    )
    await cog.tag_disable.callback(cog, run)
    assert sent(run.followup.send) == (
        "⚠️ Tag Roles Not Enabled",
        "Tag roles were not enabled in this server.",
        0xFFFF00,
    )


async def test_thanks_command_and_modal(env):
    cog = tagCommands.TagCommands(env.bot)
    run = interaction(env)
    await cog.tag_thanks.callback(cog, run)
    run.response.send_message.assert_awaited_with(
        "❌ Please specify a channel or enable DM", ephemeral=True
    )
    channel = MagicMock()
    channel.id = THANKS_CHANNEL
    await cog.tag_thanks.callback(cog, run, True, channel)
    run.response.send_message.assert_awaited_with(
        "❌ Choose either DM or a channel, not both", ephemeral=True
    )
    assert await store.thanks(env.pool, GUILD) is None

    await cog.tag_thanks.callback(cog, run, False, channel)
    modal = run.response.send_modal.await_args.args[0]
    assert (await store.thanks(env.pool, GUILD))["channel_id"] == THANKS_CHANNEL
    for field, value in zip(
        (modal.msg, modal.embedtitle, modal.description, modal.color, modal.image),
        ("c", "t", "", "#00ff00", ""),
    ):
        field._value = value
    await modal.on_submit(run)
    title, description, colour = sent(run.response.send_message)
    assert title == "✅ Tag Role Thank You Message Enabled!"
    assert "in **<#444>** when users" in description and colour == 0x00FF00
    row = await store.thanks(env.pool, GUILD)
    assert tuple(row)[3:] == ("c", "t", "", "#00ff00", "")


async def test_thanks_without_a_message_sends_an_empty_one(env):
    channel = thanks_channel(env)
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    channel.send.assert_awaited_once_with("", embed=None)


async def test_thanks_still_sent_when_the_cooldown_cannot_be_read(env, monkeypatch):
    channel = thanks_channel(env)
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    cog = await start(env)
    monkeypatch.setattr(store, "claim_thanks", AsyncMock(side_effect=OSError))
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert channel.send.await_count == 1


@pytest.mark.parametrize("column", ["role_id", "log_channel_id"])
async def test_settings_missing_a_role_or_channel_are_not_watched(env, column):
    await env.pool.execute(f"UPDATE tag_roles SET {column} = NULL")
    cog = await start(env)
    assert cog._active == {}


async def test_only_one_of_many_claims_at_once_wins(env):
    claims = [store.claim_thanks(env.pool, GUILD, 5, 1000.0, 86400) for _ in range(20)]
    assert sum(await asyncio.gather(*claims)) == 1
    assert await store.claim_thanks(env.pool, GUILD, 5, 1000.0 + 86400, 86400) is True
    assert await store.claim_thanks(env.pool, GUILD, 5, 1000.0 + 86401, 86400) is False


async def test_disable_command_answers_when_the_database_fails(env, monkeypatch):
    cog = tagCommands.TagCommands(env.bot)
    run = interaction(env)
    monkeypatch.setattr(store, "disable", AsyncMock(side_effect=OSError))
    await cog.tag_disable.callback(cog, run)
    assert sent(run.followup.send)[0] == "⚠️ Tag Roles Not Enabled"
