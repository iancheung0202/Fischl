import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Vanity import vanityCommands, vanityEvent
from commands.Vanity import vanityStore as store

GUILD, ROLE, LOG_CHANNEL, THANKS_CHANNEL, USER = 111, 222, 333, 444, 5


def channel(channel_id):
    found = MagicMock()
    found.id = channel_id
    found.mention = f"<#{channel_id}>"
    found.send = AsyncMock()
    return found


class Guild:
    id = GUILD
    name = "Guild"

    def __init__(self):
        self.role = MagicMock(spec=discord.Role)
        self.role.id = ROLE
        self.role.mention = "<@&222>"
        self.role.name = "Vain"
        self.role.members = [1, 2, 3]
        self.channels = {c: channel(c) for c in (LOG_CHANNEL, THANKS_CHANNEL)}
        self.log = self.channels[LOG_CHANNEL]
        self.members = []
        self.chunk = AsyncMock()

    def get_role(self, role_id):
        return self.role if role_id == ROLE else None

    def get_channel(self, channel_id):
        return self.channels.get(channel_id)

    get_channel_or_thread = get_channel


def member(guild, status_text="", status="online", has_role=False):
    """A member with a custom status, as a presence update gives it."""
    found = MagicMock()
    found.id = USER
    found.guild = guild
    found.mention = f"<@{USER}>"
    found.name = "u"
    found.status = status
    found.activities = [discord.CustomActivity(name=status_text)] if status_text else []
    found.activity = found.activities[0] if status_text else None
    found.roles = [guild.role] if has_role else []
    found.add_roles = AsyncMock()
    found.remove_roles = AsyncMock()
    found.send = AsyncMock()
    return found


@pytest.fixture
async def env(pool):
    await store.create(pool)
    guild = Guild()
    bot = MagicMock()
    bot.pool = pool
    bot.master = channel(1)
    bot.get_channel = lambda channel_id: (
        bot.master
        if channel_id == vanityEvent.MASTER_LOG_CHANNEL
        else guild.get_channel(channel_id)
    )
    bot.get_guild = lambda guild_id: guild if guild_id == GUILD else None
    bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    await store.set_roles(pool, GUILD, "discord.gg/traveler", ROLE, LOG_CHANNEL)
    await store.enable(pool, GUILD)
    cog = vanityEvent.OnStatusUpdate(bot)
    bot.get_cog = lambda name: cog if name == "OnStatusUpdate" else None
    await cog.cog_load()
    return types.SimpleNamespace(bot=bot, guild=guild, pool=pool, cog=cog)


def said(mock):
    """What a channel was sent: (content, embed description, embed footer)."""
    args, kwargs = mock.send.call_args
    embed = kwargs.get("embed")
    return (
        args[0] if args else None,
        embed and embed.description,
        embed and embed.footer.text,
    )


async def update(env, before, after):
    await env.cog.on_presence_update(member(env.guild, **before), after)
    return after


async def test_adding_the_link_gives_the_role_and_logs(env):
    after = member(env.guild, "join gg/traveler now")
    await update(env, {}, after)
    after.add_roles.assert_awaited_once_with(env.guild.role)
    text = f":green_circle: <@{USER}> has **added** vanity link to their status."
    assert said(env.guild.log) == (None, text, "Role added")
    assert said(env.bot.master)[1:] == (text, "Role added")
    master = env.bot.master.send.call_args.kwargs["embed"]
    assert (master.fields[0].name, master.fields[0].value) == ("Guild", "Guild (111)")
    assert env.guild.log.send.call_args.kwargs["embed"].fields == []


async def test_coming_back_online_with_the_link(env):
    after = member(env.guild, "gg/traveler")
    await update(env, {"status": "offline"}, after)
    after.add_roles.assert_awaited_once()
    text = f":white_circle: <@{USER}> went back online."
    assert said(env.guild.log) == (None, text, None)


async def test_role_given_quietly_if_the_link_was_already_there(env):
    after = member(env.guild, "gg/traveler")
    await update(env, {"status_text": "gg/traveler"}, after)
    after.add_roles.assert_awaited_once()
    env.guild.log.send.assert_not_awaited()


async def test_nothing_said_when_the_role_cannot_be_given(env):
    after = member(env.guild, "gg/traveler")
    after.add_roles.side_effect = discord.Forbidden(MagicMock(), "no")
    await update(env, {}, after)
    env.guild.log.send.assert_not_awaited()


async def test_removing_the_link_takes_the_role(env):
    after = member(env.guild, "", has_role=True)
    await update(env, {"status_text": "gg/traveler"}, after)
    after.remove_roles.assert_awaited_once_with(env.guild.role)
    text = f":red_circle: <@{USER}> has **removed** vanity link from their status."
    assert said(env.guild.log) == (None, text, "Role removed")


async def test_going_offline_keeps_the_role(env):
    after = member(env.guild, "", status="offline", has_role=True)
    await update(env, {"status_text": "gg/traveler"}, after)
    after.remove_roles.assert_not_awaited()
    assert said(env.guild.log) == (
        None,
        f":yellow_circle: <@{USER}> went offline.",
        None,
    )


async def test_back_online_without_the_link_takes_the_role(env):
    after = member(env.guild, "", has_role=True)
    await update(env, {"status": "offline"}, after)
    after.remove_roles.assert_awaited_once()
    assert said(env.guild.log)[2] == "Role removed"


@pytest.mark.parametrize(
    "before, after",
    [
        ({}, {}),
        ({}, {"status_text": "gg/traveler", "has_role": True}),
        ({"status_text": "gg/traveler"}, {}),
        ({"status": "offline"}, {}),
    ],
)
async def test_nothing_to_change(env, before, after):
    after = member(env.guild, **after)
    await update(env, before, after)
    after.add_roles.assert_not_awaited()
    after.remove_roles.assert_not_awaited()
    env.guild.log.send.assert_not_awaited()


async def test_server_that_is_not_enabled_is_ignored(env):
    await env.pool.execute("DELETE FROM vanity_enabled")
    await env.cog.load()
    after = member(env.guild, "gg/traveler")
    await update(env, {}, after)
    after.add_roles.assert_not_awaited()


@pytest.mark.parametrize("link", ["bro", None])
async def test_link_without_a_dot_is_skipped(env, link):
    await store.set_roles(env.pool, GUILD, link, ROLE, LOG_CHANNEL)
    await env.cog.load()
    after = member(env.guild, "bro")
    await update(env, {}, after)
    after.add_roles.assert_not_awaited()


async def test_deleted_role_turns_the_server_off_but_keeps_thanks(env):
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await store.set_roles(env.pool, GUILD, "discord.gg/traveler", 9, LOG_CHANNEL)
    await env.cog.load()
    await update(env, {}, member(env.guild, "gg/traveler"))
    args, kwargs = env.guild.log.send.call_args
    assert args == ("# Custom vanity role has been deleted by someone else.",)
    assert kwargs["embed"].title == "Vanity roles disabled!"
    assert kwargs["embed"].colour.value == 0xFF0000
    assert env.bot.master.send.await_count == 1
    assert env.cog.watched == {}
    assert not await store.has_roles(env.pool, GUILD)
    assert await store.enabled(env.pool) == []
    assert await store.thanks(env.pool, GUILD) is not None


async def test_log_channel_is_fetched_when_not_cached(env):
    await store.set_roles(env.pool, GUILD, "discord.gg/traveler", ROLE, 777)
    await env.cog.load()
    fetched = channel(777)
    env.bot.fetch_channel = AsyncMock(return_value=fetched)
    await update(env, {}, member(env.guild, "gg/traveler"))
    fetched.send.assert_awaited_once()


async def test_ian_activity_is_saved(env, firebase):
    after = member(env.guild, "hello")
    after.id = vanityEvent.IAN
    after.activities = [MagicMock(to_dict=lambda: {"name": "x", "id": 5, "l": [1]})]
    await env.cog.on_presence_update(member(env.guild), after)
    assert firebase("/Ian Activity").get() == [{"name": "x", "id": "5", "l": ["1"]}]


async def test_ready_loads_members_of_enabled_servers_once(env):
    await store.enable(env.pool, 12345)
    await env.cog.on_ready()
    await env.cog.on_ready()
    env.guild.chunk.assert_awaited_once()


@pytest.fixture
async def thanks(env, monkeypatch):
    """Thanks in a channel, with every placeholder in the message."""
    monkeypatch.setattr(
        vanityEvent, "embed_color", AsyncMock(return_value=discord.Color(0xFF8800))
    )
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await store.set_message(
        env.pool,
        GUILD,
        "{mention} {server} {user} {count} {count-th} {role} {rolename} {link}",
        "T {user}",
        "",
        "#ff8800",
        "",
    )
    return env.guild.channels[THANKS_CHANNEL]


async def test_thanks_in_channel_fills_placeholders(env, thanks):
    await update(env, {}, member(env.guild, "gg/traveler"))
    args, kwargs = thanks.send.call_args
    assert args == ("<@5> Guild u 3 3rd <@&222> Vain discord.gg/traveler",)
    assert (kwargs["embed"].title, kwargs["embed"].description) == ("T u", "")
    assert kwargs["embed"].colour.value == 0xFF8800
    vanityEvent.embed_color.assert_awaited_once_with("ff8800", GUILD)
    assert env.bot.master.send.await_count == 2
    assert env.bot.master.send.call_args.args == args


async def test_thanks_once_a_day(env, thanks, monkeypatch):
    now = 1_000_000
    monkeypatch.setattr(vanityEvent.time, "time", lambda: now)
    await update(env, {}, member(env.guild, "gg/traveler"))
    now += 86400
    await update(env, {}, member(env.guild, "gg/traveler"))
    assert thanks.send.await_count == 1
    now += 1
    await update(env, {}, member(env.guild, "gg/traveler"))
    assert thanks.send.await_count == 2


async def test_thanks_by_dm_without_embed(env, thanks):
    await store.set_thanks(env.pool, GUILD, None, True)
    await store.set_message(env.pool, GUILD, "hi", "", "", "", "")
    after = await update(env, {}, member(env.guild, "gg/traveler"))
    after.send.assert_awaited_once_with("hi", embed=None)
    thanks.send.assert_not_awaited()


async def test_thanks_embed_with_image_only(env, thanks):
    await store.set_message(env.pool, GUILD, "", "", "", "", "https://i/x.png")
    await update(env, {}, member(env.guild, "gg/traveler"))
    args, kwargs = thanks.send.call_args
    assert args == ("",)
    assert kwargs["embed"].image.url == "https://i/x.png"


async def test_thanks_without_a_message_sends_an_empty_one(env):
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await update(env, {}, member(env.guild, "gg/traveler"))
    env.guild.channels[THANKS_CHANNEL].send.assert_awaited_once_with("", embed=None)


@pytest.mark.parametrize("setup", ["none", "off", "missing channel"])
async def test_no_thanks_starts_no_cooldown(env, setup):
    if setup == "off":
        await store.set_message(env.pool, GUILD, "hi", "", "", "", "")
    if setup == "missing channel":
        await store.set_thanks(env.pool, GUILD, 987, False)
    await update(env, {}, member(env.guild, "gg/traveler"))
    assert env.bot.master.send.await_count == 1
    assert await env.pool.fetchval("SELECT count(*) FROM vanity_thanks_cooldown") == 0


async def test_thanks_still_sent_when_the_cooldown_cannot_be_read(
    env, thanks, monkeypatch
):
    monkeypatch.setattr(store, "claim_thanks", AsyncMock(side_effect=OSError))
    await update(env, {}, member(env.guild, "gg/traveler"))
    thanks.send.assert_awaited_once()


async def test_embed_color(monkeypatch):
    assert await vanityEvent.embed_color("", GUILD) == discord.Color.blurple()

    def failing(*args, **kwargs):
        raise vanityEvent.aiohttp.ClientError()

    monkeypatch.setattr(vanityEvent.aiohttp.ClientSession, "get", failing)
    assert await vanityEvent.embed_color("zz", GUILD) == discord.Color.blurple()


async def test_stopping_thanks_keeps_the_message(env):
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    await store.set_message(env.pool, GUILD, "hi", "t", "d", "#fff", "i")
    assert await store.stop_thanks(env.pool, GUILD)
    assert not await store.stop_thanks(env.pool, GUILD)
    assert await store.thanks(env.pool, GUILD) is None
    await store.set_thanks(env.pool, GUILD, None, True)
    assert tuple(await store.thanks(env.pool, GUILD)) == (
        GUILD,
        None,
        True,
        "hi",
        "t",
        "d",
        "#fff",
        "i",
    )


async def test_store_disable(env):
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    assert await store.disable(env.pool, GUILD)
    assert await store.watched(env.pool) == []
    assert await store.enabled(env.pool) == []
    assert await store.thanks(env.pool, GUILD) is None
    await store.enable(env.pool, GUILD)
    await store.set_thanks(env.pool, GUILD, THANKS_CHANNEL, False)
    assert not await store.disable(env.pool, GUILD)
    assert await store.enabled(env.pool) == [GUILD]
    assert await store.thanks(env.pool, GUILD) is None


@pytest.fixture
def interaction(env):
    found = MagicMock()
    found.guild = env.guild
    found.client = env.bot
    found.response.send_message = AsyncMock()
    found.response.send_modal = AsyncMock()
    found.response.defer = AsyncMock()
    found.followup.send = AsyncMock()
    return found


def sent(call):
    """What an interaction was answered with: (text, title, colour, ephemeral)."""
    embed = call.kwargs.get("embed")
    return (
        call.args[0] if call.args else None,
        embed and embed.title,
        embed and embed.colour.value,
        call.kwargs.get("ephemeral"),
    )


def commands(env):
    cog = vanityCommands.VanityCommands(env.bot)
    return types.SimpleNamespace(
        **{
            name: getattr(cog, f"vanity_{name}").callback.__get__(cog)
            for name in ("migrate", "enable", "disable", "thanks")
        }
    )


async def test_enable_command(env, interaction):
    await env.pool.execute("DELETE FROM vanity_roles; DELETE FROM vanity_enabled")
    await env.cog.load()
    run = commands(env)
    await run.enable(interaction, "nolink", env.guild.role, env.guild.log)
    text = ":x: That doesn't look like a valid invite link. Expected format: `discord.gg/yourinvite`."
    assert sent(interaction.response.send_message.call_args) == (text, None, None, True)
    assert env.cog.watched == {}

    has_link = member(env.guild, "gg/liyue")
    env.guild.members = [has_link, member(env.guild, "gg/liyue", has_role=True)]
    await run.enable(interaction, "discord.gg/liyue", env.guild.role, env.guild.log)
    answer = interaction.response.send_message.call_args
    assert sent(answer) == (None, "Vanity roles enabled!", 0x00FF00, True)
    assert "includes `gg/liyue` in" in answer.kwargs["embed"].description
    assert tuple(env.cog.watched[GUILD]) == (
        GUILD,
        "discord.gg/liyue",
        ROLE,
        LOG_CHANNEL,
    )
    has_link.add_roles.assert_awaited_once_with(env.guild.role)
    logs = [call.kwargs["embed"] for call in env.guild.log.send.call_args_list]
    assert [log.title for log in logs] == ["What is this?", None]
    assert logs[1].footer.text == "Role added"


async def test_enable_again_changes_the_settings_at_once(env, interaction):
    await commands(env).enable(interaction, "x.gg/new", env.guild.role, env.guild.log)
    assert env.cog.watched[GUILD]["link"] == "x.gg/new"


async def test_enable_command_answers_when_the_database_fails(
    env, interaction, monkeypatch
):
    monkeypatch.setattr(store, "set_roles", AsyncMock(side_effect=OSError))
    await commands(env).enable(interaction, "a.gg/b", env.guild.role, env.guild.log)
    text = ":x: Something went wrong enabling vanity roles. Please try again."
    assert sent(interaction.response.send_message.call_args) == (text, None, None, True)
    env.guild.log.send.assert_not_awaited()


async def test_migrate_and_disable_commands(env, interaction):
    await env.pool.execute("DELETE FROM vanity_enabled")
    await env.cog.load()
    run = commands(env)
    await run.migrate(interaction)
    answer = sent(interaction.response.send_message.call_args)
    assert answer == (None, "Vanity roles migrated successfully!", 0x00FFBB, True)
    assert GUILD in env.cog.watched

    await run.disable(interaction)
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    answer = sent(interaction.followup.send.call_args)
    assert answer == (None, "Vanity roles disabled!", 0xFF0000, True)
    assert env.cog.watched == {}

    await run.disable(interaction)
    answer = sent(interaction.followup.send.call_args)
    assert answer == (None, "Vanity roles is not enabled!", 0xFFFF00, True)


async def test_disable_command_answers_when_the_database_fails(
    env, interaction, monkeypatch
):
    monkeypatch.setattr(store, "disable", AsyncMock(side_effect=OSError))
    await commands(env).disable(interaction)
    assert (
        sent(interaction.followup.send.call_args)[1] == "Vanity roles is not enabled!"
    )


async def test_thanks_command_and_modal(env, interaction):
    run = commands(env)
    place = env.guild.channels[THANKS_CHANNEL]
    answer = interaction.response.send_message

    await run.thanks(interaction, False, None)
    text = ":x: Please either specify the channel *or* specify `dm` as `True` to enable thank you message."
    assert sent(answer.call_args) == (text, None, None, True)

    await run.thanks(interaction, True, place)
    assert sent(answer.call_args)[0].startswith(":x: You specified both <#444> and DM.")
    assert await store.thanks(env.pool, GUILD) is None

    await run.thanks(interaction, False, place)
    interaction.response.send_modal.assert_awaited_once()
    modal = interaction.response.send_modal.call_args.args[0]
    for field, value in zip(
        (modal.msg, modal.embedtitle, modal.description, modal.color, modal.image),
        ("hi", "t", "d", "#fff", "i"),
    ):
        field._value = value
    await modal.on_submit(interaction)
    title = "✅ Vanity Role Thank You Message Enabled!"
    assert sent(answer.call_args) == (None, title, 0x00FF00, True)
    assert "in **<#444>** whenever" in answer.call_args.kwargs["embed"].description
    saved = await store.thanks(env.pool, GUILD)
    assert tuple(saved) == (GUILD, THANKS_CHANNEL, False, "hi", "t", "d", "#fff", "i")

    await run.thanks(interaction, True, place)
    assert await store.thanks(env.pool, GUILD) is None

    await run.thanks(interaction, True, None)
    await modal.on_submit(interaction)
    assert "in **DM** whenever" in answer.call_args.kwargs["embed"].description

    await run.thanks(interaction, False, None)
    text = ":white_check_mark: Thank you message **disabled**! *Vanity roles function is still enabled though!*"
    assert sent(answer.call_args) == (text, None, None, True)
    await modal.on_submit(interaction)
    described = answer.call_args.kwargs["embed"].description
    assert "in **the configured channel** whenever" in described


async def test_thanks_command_needs_role_settings(env, interaction):
    await env.pool.execute("DELETE FROM vanity_roles")
    await commands(env).thanks(interaction, True, None)
    text = ":x: Vanity roles is not currently enabled in this server!"
    assert sent(interaction.response.send_message.call_args) == (text, None, None, True)


async def test_modal_answers_when_the_database_fails(env, interaction, monkeypatch):
    monkeypatch.setattr(store, "set_message", AsyncMock(side_effect=OSError))
    await vanityCommands.embed_modal().on_submit(interaction)
    text = ":x: Something went wrong saving your thank-you message. Please try again."
    assert sent(interaction.response.send_message.call_args) == (text, None, None, True)


@pytest.mark.parametrize("order", [("Commands", "Event"), ("Event", "Commands")])
async def test_commands_reach_the_listener_in_any_load_order(pool, order):
    from discord.ext import commands as ext

    bot = ext.Bot(command_prefix="-", intents=discord.Intents.none())
    bot.pool = pool
    for name in order:
        await bot.load_extension(f"commands.Vanity.vanity{name}")
    await store.set_roles(pool, GUILD, "discord.gg/traveler", ROLE, LOG_CHANNEL)
    await store.enable(pool, GUILD)
    await vanityCommands.refresh(bot)
    assert GUILD in bot.get_cog("OnStatusUpdate").watched


async def test_disable_command_answers_disabled_when_the_reload_fails(
    env, interaction, monkeypatch
):
    monkeypatch.setattr(env.cog, "load", AsyncMock(side_effect=OSError))
    await commands(env).disable(interaction)
    assert sent(interaction.followup.send.call_args)[1] == "Vanity roles disabled!"


async def test_migrate_command_answers_when_the_database_fails(
    env, interaction, monkeypatch
):
    monkeypatch.setattr(store, "enable", AsyncMock(side_effect=OSError))
    await commands(env).migrate(interaction)
    text = ":x: Something went wrong migrating your server. Please try again or contact support."
    assert sent(interaction.response.send_message.call_args) == (text, None, None, True)


async def test_deleted_role_is_announced_once(env):
    await store.set_roles(env.pool, GUILD, "discord.gg/traveler", 9, LOG_CHANNEL)
    await env.cog.load()
    updates = [update(env, {}, member(env.guild, "gg/traveler")) for _ in range(5)]
    await asyncio.gather(*updates)
    assert env.guild.log.send.await_count == 1


async def test_deleted_role_is_announced_when_the_database_fails(env, monkeypatch):
    await store.set_roles(env.pool, GUILD, "discord.gg/traveler", 9, LOG_CHANNEL)
    await env.cog.load()
    monkeypatch.setattr(store, "drop_roles", AsyncMock(side_effect=OSError))
    await update(env, {}, member(env.guild, "gg/traveler"))
    assert env.guild.log.send.await_count == 1


async def test_overlapping_loads_end_on_what_is_saved(env):
    async def flip(on):
        await (store.enable if on else store.drop_roles)(env.pool, GUILD)
        await env.cog.load()

    await asyncio.gather(*(flip(i % 2 == 0) for i in range(20)))
    await env.cog.load()
    assert list(env.cog.watched) == [
        r["guild_id"] for r in await store.watched(env.pool)
    ]


async def test_one_thanks_for_claims_at_once(env):
    claims = [store.claim_thanks(env.pool, GUILD, USER, 100, 86400) for _ in range(20)]
    assert sum(await asyncio.gather(*claims)) == 1


async def test_count_is_only_read_when_asked_for(env):
    role = MagicMock()
    type(role).members = property(lambda self: 1 / 0)
    who = member(env.guild)
    assert vanityEvent.script("hi {user}", who, role, "l") == "hi u"


async def test_unexpected_color_error_gives_blurple(monkeypatch):
    def failing(*args, **kwargs):
        raise TypeError()

    monkeypatch.setattr(vanityEvent.aiohttp.ClientSession, "get", failing)
    assert await vanityEvent.embed_color("zz", GUILD) == discord.Color.blurple()


async def test_failed_removal_is_still_logged(env):
    after = member(env.guild, "", has_role=True)
    after.remove_roles.side_effect = discord.Forbidden(MagicMock(), "no")
    await update(env, {"status_text": "gg/traveler"}, after)
    assert said(env.guild.log)[2] == "Role removed"


async def test_settings_without_a_log_channel_log_to_the_master_only(env):
    await store.set_roles(env.pool, GUILD, "discord.gg/traveler", ROLE, None)
    await env.cog.load()
    after = await update(env, {}, member(env.guild, "gg/traveler"))
    after.add_roles.assert_awaited_once()
    env.guild.log.send.assert_not_awaited()
    assert env.bot.master.send.await_count == 1
