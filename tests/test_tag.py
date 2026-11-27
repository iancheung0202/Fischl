import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs import presenceFilter
from commands.Tag import tagEvent

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
def env(monkeypatch, firebase, no_loops):
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
    monkeypatch.setattr(tagEvent, "enabledGuilds", [GUILD])
    monkeypatch.setattr(tagEvent, "check_reload", lambda: None)
    firebase("/Tag Roles/k").set(
        {
            "Server ID": GUILD,
            "Role ID": ROLE,
            "Log Channel ID": LOG_CHANNEL,
            "Tag Server ID": TAG_SERVER,
        }
    )
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
        firebase=firebase,
    )


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


@pytest.mark.asyncio
async def test_scans_once_at_start(env):
    env.guild.members = [payload(1, TAG_SERVER, [])]
    cog = await start(env)
    assert env.guild.scans == 1 and env.add.await_count == 1
    await cog.tag_check.coro(cog)
    assert env.guild.scans == 1


@pytest.mark.asyncio
async def test_scans_again_after_an_hour_or_new_settings(env):
    cog = await start(env)
    settings, at = cog._last_sweep[GUILD]
    cog._last_sweep[GUILD] = (settings, at - tagEvent.SWEEP_INTERVAL - 1)
    await cog.tag_check.coro(cog)
    assert env.guild.scans == 2
    env.firebase("/Tag Roles/k/Tag Server ID").set(555)
    await cog.tag_check.coro(cog)
    assert env.guild.scans == 3


@pytest.mark.asyncio
async def test_update_gives_role_and_logs(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, TAG_SERVER, []))
    assert env.parsed[-1][0] == "GUILD_MEMBER_UPDATE"
    assert env.add.await_count == 1 and env.remove.await_count == 0
    embed = env.guild.log.send.await_args.kwargs["embed"]
    assert "was given the tag role" in embed.description
    assert env.master.send.await_count == 1
    assert env.guild._members == {}


@pytest.mark.asyncio
async def test_update_removes_role(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(5, None, [ROLE]))
    assert env.remove.await_count == 1 and env.add.await_count == 0


@pytest.mark.asyncio
async def test_nothing_to_change(env):
    cog = await start(env)
    for data in (
        payload(5, 12345, []),
        payload(6, TAG_SERVER, [ROLE]),
        payload(7, None, []),
    ):
        await send(env, cog, "GUILD_MEMBER_UPDATE", data)
    assert env.add.await_count == 0 and env.remove.await_count == 0


@pytest.mark.asyncio
async def test_join_with_tag(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_ADD", payload(8, TAG_SERVER, []))
    assert env.add.await_count == 1


@pytest.mark.asyncio
async def test_other_server_ignored_and_repeat_skipped(env):
    cog = await start(env)
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(9, TAG_SERVER, [], 4242))
    assert env.add.await_count == 0
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(9, TAG_SERVER, []))
    await send(env, cog, "GUILD_MEMBER_UPDATE", payload(9, TAG_SERVER, []))
    assert env.add.await_count == 1


@pytest.mark.asyncio
async def test_role_above_bot_is_not_watched(env):
    env.guild.role.__ge__ = lambda a, b: True
    cog = await start(env)
    assert GUILD not in cog._active and env.guild.scans == 0
    assert env.guild.log.send.await_count == 1


@pytest.mark.asyncio
async def test_unload_restores_parsers(env):
    cog = await start(env)
    cog.cog_unload()
    assert (
        env.state.parsers["GUILD_MEMBER_UPDATE"] is env.original["GUILD_MEMBER_UPDATE"]
    )


def test_presence_filter(env):
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
