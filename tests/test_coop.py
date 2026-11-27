from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.CoOp import coOpCelestial
from commands.CoOp import coOpStore as store
from commands.CoOp import coOpSystem
from commands.Help import help as help_page

GUILD, CHANNEL, MEMBER = 10, 20, 50
NA, EU, ASIA, SAR = 1, 2, 3, 4
LIYUE, CARRY = 1073116154798809098, 1145946099270549535


@pytest.fixture
async def cog(pool):
    bot = MagicMock()
    bot.pool = pool
    found = coOpSystem.CoOp(bot)
    await found.cog_load()
    return found


def role(role_id):
    found = MagicMock()
    found.id = role_id
    found.mention = f"<@&{role_id}>"
    return found


def interaction(pool, guild=GUILD, roles=()):
    found = MagicMock()
    found.client.pool = pool
    found.user.id = MEMBER
    found.user.name = "fischl"
    found.user.mention = f"<@{MEMBER}>"
    found.user.roles = [role(role_id) for role_id in roles]
    found.guild.id = guild
    found.guild.name = "Teyvat"
    found.guild.get_role = role
    found.guild.fetch_channel = AsyncMock()
    found.channel.id = CHANNEL
    found.channel.send = AsyncMock()
    found.channel.fetch_message = AsyncMock()
    found.response.send_message = AsyncMock()
    found.response.send_modal = AsyncMock()
    found.message.edit = AsyncMock()
    return found


def answer(found):
    call = found.response.send_message.await_args
    return call.kwargs.get("embed") or call.args[0], call.kwargs.get("ephemeral", False)


async def enable(pool, guild=GUILD):
    return await store.enable(pool, guild, CHANNEL, NA, EU, ASIA, SAR)


async def setup(cog, found):
    await coOpSystem.CoOp.coop_setup.callback(
        cog, found, role(CHANNEL), role(NA), role(EU), role(ASIA), role(SAR)
    )


def test_commands_look_the_same():
    assert coOpSystem.CoOp.__cog_group_name__ == "co-op"
    commands = {
        "disable": "Disable co-op system in this server",
        "panel": "Creates a customized co-op request panel",
        "setup": "Setup co-op system in the server",
        "reputation": "Enable, manage, or disable reputation system in the server",
    }
    found = {
        command.name: command.description
        for command in coOpSystem.CoOp.__cog_app_commands__
    }
    assert found == commands


async def test_buttons_keep_their_ids():
    ids = lambda view: [(item.custom_id, item.label) for item in view.children]
    assert ids(coOpSystem.CoOpButtonViewSystem()) == [
        ("nasystem", "NA"),
        ("eusystem", "EU"),
        ("asiasystem", "Asia"),
        ("sarsystem", "SAR"),
    ]
    assert [found[0] for found in ids(coOpSystem.CoOpView())][:2] == [
        "accepthelpsystem",
        "closehelpsystem",
    ]


async def test_store_keeps_one_of_each(pool):
    await store.create(pool)
    assert await store.server(pool, GUILD) is None
    assert await enable(pool)
    assert not await store.enable(pool, GUILD, 9, 9, 9, 9, 9)
    assert tuple(await store.server(pool, GUILD))[1:] == (GUILD, CHANNEL, 1, 2, 3, 4)
    assert await store.disable(pool, GUILD)
    assert not await store.disable(pool, GUILD)

    assert await store.take_panel(pool, CHANNEL) is None
    await store.stick_panel(pool, CHANNEL, 7)
    await store.stick_panel(pool, CHANNEL, 8)
    assert await store.take_panel(pool, CHANNEL) == 8
    assert await store.take_panel(pool, CHANNEL) is None

    assert await store.uid(pool, MEMBER) is None
    await store.save_uid(pool, MEMBER, "800000001")
    await store.save_uid(pool, MEMBER, "not a uid")
    assert await store.uid(pool, MEMBER) == "not a uid"


async def test_setup_saves_once_and_disable_forgets(cog, pool):
    found = interaction(pool)
    await setup(cog, found)
    embed, private = answer(found)
    assert embed.title == "Co-op System Enabled Successfully!"
    assert tuple(await store.server(pool, GUILD))[1:] == (GUILD, CHANNEL, 1, 2, 3, 4)

    found = interaction(pool)
    await setup(cog, found)
    embed, private = answer(found)
    assert (embed.title, embed.colour.value, private) == (
        "Co-Op System already enabled!",
        0xFF0000,
        True,
    )
    assert embed.description.startswith(
        f"Your co-op channel is already set as <#{CHANNEL}> `({CHANNEL})`\n\n"
    )

    found = interaction(pool)
    await coOpSystem.CoOp.coop_disable.callback(cog, found)
    assert answer(found)[0].title == "Co-op system successfully disabled"
    assert await store.server(pool, GUILD) is None
    found = interaction(pool)
    await coOpSystem.CoOp.coop_disable.callback(cog, found)
    assert answer(found) == (answer(found)[0], True)
    assert answer(found)[0].title == "We could not find your server"


async def test_sticky_panel_replaces_the_old_one(cog, pool):
    found = interaction(pool)
    found.channel.send.return_value.id = 100
    await coOpSystem.CoOp.coop_panel.callback(cog, found, True, message="hi")
    found.channel.fetch_message.assert_not_awaited()
    assert await pool.fetchval("SELECT message_id FROM coop_panels") == 100

    found = interaction(pool)
    found.channel.send.return_value.id = 101
    found.channel.fetch_message.side_effect = discord.NotFound(
        MagicMock(status=404), "gone"
    )
    await coOpSystem.CoOp.coop_panel.callback(cog, found, True)
    found.channel.fetch_message.assert_awaited_once_with(100)
    assert [tuple(row) for row in await pool.fetch("SELECT * FROM coop_panels")] == [
        (CHANNEL, 101)
    ]

    found = interaction(pool)
    found.channel.send.return_value.id = 102
    await coOpSystem.CoOp.coop_panel.callback(cog, found, False)
    assert await pool.fetchval("SELECT message_id FROM coop_panels") == 101


@pytest.mark.parametrize(
    "label, helper, colour",
    [("NA", NA, 0x6161F9), ("EU", EU, 0x50C450), ("Asia", ASIA, 0xF96262)]
    + [("SAR", SAR, 0xF7D31A)],
)
async def test_request_goes_to_the_region_helpers(cog, pool, label, helper, colour):
    await enable(pool)
    await store.stick_panel(pool, CHANNEL, 100)
    found = interaction(pool)
    channel = MagicMock()
    channel.send = AsyncMock()
    channel.send.return_value.jump_url = "https://jump"
    channel.send.return_value.create_thread = AsyncMock()
    found.client.get_channel.return_value = channel
    panel = found.channel.fetch_message.return_value
    panel.delete = AsyncMock()
    panel.content, panel.embeds = "panel", [discord.Embed(title="old")]
    found.channel.send.return_value.id = 200

    modal = coOpSystem.CoOpHelpModal(title=f"Request Co-op Help - {label}")
    modal.uid._value, modal.wl._value = " 800000001 ", "8"
    modal.runs._value, modal.request._value = "2", "boss"
    await modal.on_submit(found)

    found.client.get_channel.assert_called_once_with(CHANNEL)
    sent = channel.send.await_args.kwargs
    assert sent["content"].endswith(
        f" <@{MEMBER}> is requesting for co-op** - <@&{helper}>"
    )
    embed = sent["embed"]
    assert embed.colour.value == colour
    assert embed.description.startswith(f"### {label} Region Co-op Request\n-# - ")
    assert [(field.name, field.value) for field in embed.fields] == [
        ("UID", ">  800000001 "),
        ("World Level", "> WL8"),
        ("Runs", "> 2 runs"),
        ("Request", "> boss"),
    ]
    assert isinstance(sent["view"], coOpSystem.CoOpView)
    assert answer(found) == (
        "<:yes:1036811164891480194> [Co-op Request Sent](https://jump)",
        True,
    )
    channel.send.return_value.create_thread.assert_awaited_once_with(
        name=f"fischl - {label} Region Co-op Request", auto_archive_duration=1440
    )
    assert await store.uid(pool, MEMBER) == "800000001"

    found.channel.fetch_message.assert_awaited_once_with(100)
    panel.delete.assert_awaited_once()
    again = found.channel.send.await_args
    assert again.args == ("panel",) and again.kwargs["embed"].title == "old"
    assert await pool.fetchval("SELECT message_id FROM coop_panels") == 200


async def test_request_with_a_lost_panel_forgets_it(cog, pool):
    await enable(pool)
    await store.stick_panel(pool, CHANNEL, 100)
    found = interaction(pool)
    channel = found.client.get_channel.return_value
    channel.send = AsyncMock()
    channel.send.return_value.create_thread = AsyncMock()
    found.channel.fetch_message.side_effect = discord.NotFound(
        MagicMock(status=404), "gone"
    )
    modal = coOpSystem.CoOpHelpModal(title="Request Co-op Help - NA")
    modal.uid._value = modal.wl._value = modal.runs._value = modal.request._value = ""
    await modal.on_submit(found)
    found.channel.send.assert_not_awaited()
    assert await pool.fetchval("SELECT count(*) FROM coop_panels") == 0
    assert await pool.fetchval("SELECT count(*) FROM coop_uids") == 0


async def test_request_without_a_channel_says_so(cog, pool):
    await enable(pool)
    found = interaction(pool)
    found.client.get_channel.return_value = None
    modal = coOpSystem.CoOpHelpModal(title="Request Co-op Help - NA")
    modal.uid._value = ""
    await modal.on_submit(found)
    assert answer(found) == (
        "<:no:1036810470860013639> Co-op channel not found. Please ask the server admin to set up the co-op system again.",
        True,
    )


async def test_region_button_opens_the_form_with_the_saved_uid(cog, pool, monkeypatch):
    view = coOpSystem.CoOpButtonViewSystem()
    found = interaction(pool)
    await view.eu.callback(found)
    embed, private = answer(found)
    assert (embed.title, private) == ("Co-op system not enabled!", True)
    found.response.send_modal.assert_not_awaited()

    await enable(pool)
    enka = MagicMock()
    enka.load_lang = AsyncMock()
    enka.fetch_user = AsyncMock()
    enka.fetch_user.return_value.player.worldLevel = 8
    monkeypatch.setattr(coOpSystem, "Enka", lambda: enka)
    await store.save_uid(pool, MEMBER, "800000001")
    found = interaction(pool)
    await view.eu.callback(found)
    modal = found.response.send_modal.await_args.args[0]
    assert modal.title == "Request Co-op Help - EU"
    assert (modal.uid.default, modal.wl.default) == ("800000001", "8")
    enka.fetch_user.assert_awaited_once_with(800000001)

    await store.save_uid(pool, MEMBER, "my uid")
    found = interaction(pool)
    await view.sar.callback(found)
    modal = found.response.send_modal.await_args.args[0]
    assert modal.title == "Request Co-op Help - SAR"
    assert (modal.uid.default, modal.wl.default) == ("", "")


async def test_celestial_keeps_uids_in_the_same_place(pool, monkeypatch):
    await store.create(pool)
    await store.save_uid(pool, MEMBER, "x")
    found = interaction(pool)
    assert await coOpCelestial.CoOpButtonView().fetch_uid_and_wl(found) == (None, None)


def request(pool, guild, roles, region="EU"):
    found = interaction(pool, guild, roles)
    found.message.id = 300
    found.message.content = "**hi <@99> is requesting for co-op** - <@&2>"
    found.message.embeds = [
        discord.Embed(description=f"### {region} Region Co-op Request\n-# - x")
    ]
    found.guild.fetch_channel.return_value.send = AsyncMock()
    return found


@pytest.mark.parametrize(
    "guild, roles, region, claimed",
    [
        (GUILD, [EU], "EU", True),
        (GUILD, [NA, ASIA, SAR], "EU", False),
        (GUILD, [SAR], "SAR", True),
        (GUILD, [CARRY], "EU", False),
        (LIYUE, [CARRY], "EU", True),
        (LIYUE, [], "Asia", False),
        (GUILD, [EU], "Other", False),
    ],
)
async def test_claim_needs_the_region_role(cog, pool, guild, roles, region, claimed):
    await enable(pool, guild)
    found = request(pool, guild, roles, region)
    await coOpSystem.CoOpView().accepthelpsystem.callback(found)
    if claimed:
        found.guild.fetch_channel.return_value.send.assert_awaited_once_with(
            f"Request claimed by <@{MEMBER}>. "
        )
        assert found.message.edit.await_args.kwargs["embed"].description.startswith(
            f"<:yes:1036811164891480194> *Claimed by <@{MEMBER}>* \n### "
        )
    else:
        assert answer(found)[0].startswith("**<:no:1036810470860013639> Warning:**")
        found.message.edit.assert_not_awaited()


def test_help_reads_the_store():
    import inspect

    source = inspect.getsource(help_page)
    assert "coOpStore.server(interaction.client.pool" in source
    assert '"/Co-Op"' not in source
