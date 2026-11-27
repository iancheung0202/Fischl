import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.Partnership import partnershipSystem as partner

GUILD, MEMBER, BOT = 77, 42, 999
LOG, PANEL, REQUESTS = 1, 2, 3
INVITES = {
    "good": (
        200,
        {
            "guild": {"id": "900", "name": "Good", "icon": "abc"},
            "approximate_member_count": 55,
            "expires_at": None,
        },
    ),
    "short": (200, {"guild": {"id": "901", "name": "Short"}, "expires_at": "2030"}),
    "known": (200, {"guild": {"id": "111", "name": "Known"}, "expires_at": None}),
    "gone": (404, {"message": "Unknown Invite"}),
}


def channel(channel_id):
    found = MagicMock()
    found.id = channel_id
    found.mention = f"<#{channel_id}>"
    found.sent = []
    found.messages = {}

    async def send(content=None, **options):
        message = MagicMock()
        message.id = 1000 + len(found.sent)
        message.jump_url = f"jump/{message.id}"
        message.edit = AsyncMock()
        message.delete = AsyncMock()
        found.messages[message.id] = message
        found.sent.append((content, options))
        return message

    async def fetch_message(message_id):
        if message_id not in found.messages:
            raise discord.NotFound(MagicMock(status=404, reason="gone"), "gone")
        return found.messages[message_id]

    found.send = send
    found.fetch_message = fetch_message
    return found


def thread(thread_id, server_id):
    found = MagicMock()
    found.mention = f"<#{thread_id}>"
    found.jump_url = f"jump/{thread_id}"
    found.send = AsyncMock()
    found.add_user = AsyncMock()
    first = MagicMock()
    first.author.id = BOT
    first.edit = AsyncMock()
    embed = discord.Embed(title="New Partnership Request")
    embed.add_field(name="Server ID", value=str(server_id))
    first.embeds = [embed]
    found.first = first

    async def history(**options):
        yield first

    found.history = history
    return found


@pytest.fixture
def server(firebase):
    """A server with its three channels, one open thread and a fake Discord invite API."""
    channels = {number: channel(number) for number in (LOG, PANEL, REQUESTS)}
    requests = channels[REQUESTS]
    requests.threads = [thread(500, "111")]

    async def archived_threads():
        yield thread(501, "222")

    requests.archived_threads = archived_threads
    requests.create_thread = AsyncMock(return_value=thread(600, "900"))
    bot = MagicMock()
    bot.user.id = BOT
    bot.get_channel = channels.get

    async def fetch_invite(code, **params):
        fetch_invite.asked.append((code, params))
        return INVITES.get(code, INVITES["gone"])

    fetch_invite.asked = []
    with patch.object(partner, "fetch_invite", fetch_invite), patch.object(
        partner, "SlashCommand", lambda name: f"/{name}"
    ):
        found = MagicMock()
        found.bot, found.channels, found.firebase = bot, channels, firebase
        found.cog = partner.Partner(bot)
        found.invites = fetch_invite.asked
        yield found


def interaction(server, member=MEMBER):
    found = MagicMock()
    found.client = server.bot
    found.guild.id = GUILD
    found.guild.get_channel = server.channels.get
    found.user.id = member
    found.user.mention = f"<@{member}>"
    found.user.display_avatar.url = "https://cdn/avatar.png"
    found.channel = server.channels[LOG]
    found.response.send_message = AsyncMock()
    found.response.send_modal = AsyncMock()
    found.response.defer = AsyncMock()
    found.followup.send = AsyncMock()
    return found


def said(found):
    """Gives what the bot answered, and whether only the member saw it."""
    call = found.response.send_message.await_args or found.followup.send.await_args
    return call.args[0] if call.args else call.kwargs["embed"], call.kwargs.get(
        "ephemeral", False
    )


def run(server, name, *args, member=MEMBER):
    found = interaction(server, member)
    command = getattr(partner.Partner, name).callback
    return found, command(server.cog, found, *args)


async def setup(server, cooldown="0m", manager=None):
    def mentionable(found_id):
        found = MagicMock()
        found.id = found_id
        found.mention = f"<@&{found_id}>"
        return found

    found, call = run(
        server,
        "partner_setup",
        server.channels[LOG],
        mentionable(71),
        server.channels[REQUESTS],
        server.channels[PANEL],
        manager and mentionable(manager),
        cooldown,
    )
    await call
    return found


async def group(server, name="Genshin", **options):
    found, call = run(server, "partner_add_group", name)
    (
        await getattr(partner.Partner, "partner_add_group").callback(
            server.cog, found, name, **options
        )
        if options
        else await call
    )
    return found


def add(server, name, invite, category="Genshin"):
    server.firebase(f"Partner/partners/{GUILD}").push(
        {"name": name, "invite": invite, "category": category}
    )


async def test_commands_and_button_keep_their_names():
    commands = {command.name for command in partner.Partner.__cog_app_commands__}
    assert partner.Partner.__cog_group_name__ == "partner"
    assert commands == {
        "status",
        "invite",
        "create",
        "blacklist",
        "unblacklist",
        "edit-panel",
        "disable",
        "send-panel",
        "update-panel",
        "add-group",
        "edit-group",
        "remove-group",
        "setup",
        "mass-add-partner",
        "add-partner",
        "remove-partner",
    }
    button = partner.PartnerRequestButton()
    assert (button.label, button.custom_id) == (
        "Request Partnership",
        "partner_request",
    )
    assert partner.PartnerRequestButtonView().timeout is None


@pytest.mark.parametrize(
    "name, permissions",
    [
        ("partner_invite", set()),
        ("partner_status", {"manage_webhooks", "manage_channels"}),
        ("add_partner", {"manage_webhooks", "manage_channels", "manage_messages"}),
    ],
)
def test_who_may_use_a_command(name, permissions):
    checks = getattr(partner.Partner, name).checks
    found = set()
    for check in checks:
        found |= set(check.__closure__[0].cell_contents)
    assert found == permissions


async def test_any_command_error_is_shown_to_the_member(server):
    found = interaction(server)
    await server.cog.cog_app_command_error(found, RuntimeError("no permission"))
    assert said(found) == ("```no permission```", True)


async def test_setup_saves_settings_and_posts_three_messages(server):
    found = await setup(server, "3d12h45m", manager=72)
    assert server.firebase(f"Partner/config/{GUILD}").get() == {
        "log_channel": LOG,
        "partner_role": 71,
        "request_channel": REQUESTS,
        "panel_channel": PANEL,
        "user_cooldown": 3 * 86400 + 12 * 3600 + 45 * 60,
        "partner_manager_role_id": "72",
        "enabled": True,
    }
    embed, ephemeral = said(found)
    assert embed.title == f"{partner.YES} Partnership System Setup Complete!"
    assert not ephemeral
    assert [field.value for field in embed.fields] == [
        "<#1>",
        "<#3>",
        "<#2>",
        "<@&71>",
        "<@&72>",
        "3 days, 12 hours, 45 minutes",
    ]
    assert server.firebase(f"Partner/panels/{GUILD}").get() == {
        "message_id": 1000,
        "channel_id": PANEL,
    }
    panel = server.channels[PANEL].sent[0][1]
    assert [embed.title for embed in panel["embeds"]] == [
        "Server Partner List",
        "Instructions",
    ]
    assert panel["view"].children[0].custom_id == "partner_request"
    assert "jump/1000" in server.channels[REQUESTS].sent[0][1]["embed"].fields[0].value
    assert len(server.channels[LOG].sent) == 1


@pytest.mark.parametrize(
    "cooldown, pretty", [("0m", "None"), ("", "None"), ("1h", "1 hour")]
)
async def test_setup_cooldown_wording(server, cooldown, pretty):
    found = await setup(server, cooldown)
    assert said(found)[0].fields[-1].value == pretty
    assert said(found)[0].fields[-2].value == "None"
    assert (
        server.firebase(f"Partner/config/{GUILD}").get()["partner_manager_role_id"]
        == ""
    )


async def test_setup_refuses_a_bad_cooldown(server):
    found = await setup(server, "soon")
    assert said(found) == (
        "⚠️ Invalid cooldown format. Use something like `3d12h45m`, `5h`, or `30m`.",
        True,
    )
    assert server.firebase(f"Partner/config/{GUILD}").get() is None


async def test_groups_need_a_plain_new_name(server):
    await setup(server)
    assert said(await group(server, "two words"))[0].startswith(partner.NO)
    found = await group(server)
    assert said(found) == (
        f"{partner.YES} Group 'Genshin' created! To delete a group, use /partner remove-group.",
        True,
    )
    saved = server.firebase(f"Partner/categories/{GUILD}/Genshin").get()
    assert {**saved, "created_at": 0} == {
        "title": "Genshin",
        "color": "#5865F2",
        "prefix": "-",
        "suffix": "",
        "created_at": 0,
    }
    assert (
        said(await group(server, "genshin"))[0] == f"{partner.NO} Group already exists!"
    )
    log = server.channels[LOG].sent[-1][1]["embed"]
    assert log.title == "Group Created"
    assert [field.value for field in log.fields] == [
        "Genshin",
        "Genshin",
        "#5865F2",
        "-",
        "None",
        "None",
    ]


async def test_panel_lists_partners_by_letter(server):
    await setup(server)
    server.firebase(f"Partner/categories/{GUILD}/Genshin").set(
        {"title": "Genshin Servers", "color": "#ff0000", "prefix": ">", "suffix": "<"}
    )
    server.firebase(f"Partner/categories/{GUILD}/Empty").set({"title": "Empty"})
    add(server, "beta", "bbb")
    add(server, "Alpha", "aaa")
    add(server, "Botty", "123456")
    add(server, "Elsewhere", "eee", "Other")
    header, listed, footer = await partner._build_panel_embeds(GUILD)
    assert (listed.title, listed.color.value) == ("Genshin Servers", 0xFF0000)
    assert [(field.name, field.value) for field in listed.fields] == [
        (
            "A - Z",
            "> [Alpha](https://discord.gg/aaa) <\n> [beta](https://discord.gg/bbb) <\n"
            "> [Botty](https://discord.com/oauth2/authorize?client_id=123456) <",
        )
    ]
    assert (
        header.description
        == "Use /partner edit-panel and select `Header` to edit this embed!"
    )
    assert (
        footer.description
        == "Use /partner edit-panel and select `Footer` to edit this embed!"
    )
    assert footer.footer.text == "⚡ Panel automatically updated • Powered by Fischl"


async def test_long_groups_split_into_fields_embeds_and_messages(server):
    await setup(server)
    server.firebase(f"Partner/categories/{GUILD}/Genshin").set({"title": "G"})
    for number in range(260):
        add(
            server, f"{chr(65 + number % 26)}{'n' * 40}{number}", "c" * 30 + str(number)
        )
    embeds = await partner._build_panel_embeds(GUILD)
    fields = [field for embed in embeds[1:-1] for field in embed.fields]
    assert all(len(field.value) <= 1024 for field in fields)
    assert sum(field.value.count("\n") + 1 for field in fields) == 260
    assert fields[0].name.startswith("A - ") and fields[-1].name.endswith(" - Z")
    assert all(len(embed.fields) <= 25 for embed in embeds)
    messages = partner._group_embeds_by_message_limit(embeds)
    assert len(messages) > 1
    assert [embed for message in messages for embed in message] == embeds
    assert all(
        len(message) == 1
        or sum(partner._calculate_embed_size(embed) for embed in message) <= 6000
        for message in messages
    )

    found, call = run(server, "partner_send_panel")
    await call
    panel = server.firebase(f"Partner/panels/{GUILD}").get()
    assert len(panel["message_ids"]) == len(messages)
    views = [options["view"] for _, options in server.channels[PANEL].sent[1:]]
    assert [view is not None for view in views] == [False] * (len(messages) - 1) + [
        True
    ]
    assert said(found)[0].startswith(
        f"{partner.YES} Partnership panel sent! ({len(messages)} messages, {len(embeds)} embeds)"
    )


async def test_update_edits_in_place_sends_what_is_missing_and_deletes_extras(server):
    await setup(server)
    panel = server.channels[PANEL]
    extra = await panel.send()
    server.firebase(f"Partner/panels/{GUILD}").set(
        {"message_ids": [1000, extra.id, 5], "channel_id": PANEL}
    )
    assert await partner._update_panel(GUILD, server.bot) == (
        f"{partner.YES} Panel updated! (1 message)"
    )
    panel.messages[1000].edit.assert_awaited_once()
    extra.delete.assert_awaited_once()
    assert server.firebase(f"Partner/panels/{GUILD}/message_ids").get() == [1000]

    del panel.messages[1000]
    await partner._update_panel(GUILD, server.bot)
    assert server.firebase(f"Partner/panels/{GUILD}/message_ids").get() == [1002]


async def test_update_needs_setup_and_a_panel(server):
    found, call = run(server, "partner_update_panel")
    await call
    assert said(found)[0] == f"{partner.NO} Partnership system not enabled!"
    assert await partner._update_panel(GUILD, server.bot) is None
    await setup(server)
    server.firebase(f"Partner/panels/{GUILD}").delete()
    found, call = run(server, "partner_update_panel")
    await call
    assert (
        said(found)[0]
        == f"{partner.NO} No panel found! Use `/partner send-panel` first."
    )


async def test_add_partner_checks_the_invite(server):
    await setup(server)
    await group(server)
    found, call = run(
        server, "add_partner", "Nope", "https://discord.gg/good", "Missing"
    )
    await call
    assert said(found)[0].startswith(f"{partner.NO} Invalid group!")
    found, call = run(
        server, "add_partner", "Gone", "https://discord.gg/gone", "Genshin"
    )
    await call
    assert said(found)[0] == f"{partner.NO} Invalid invite link!"
    found, call = run(
        server, "add_partner", "Short", "https://discord.gg/short", "Genshin"
    )
    await call
    assert said(found)[0] == f"{partner.NO} Invite link is not permanent."
    assert server.firebase(f"Partner/partners/{GUILD}").get() is None

    rep = MagicMock()
    rep.add_roles = AsyncMock()
    found, call = run(
        server, "add_partner", "Good", "https://discord.gg/good", "Genshin", rep
    )
    await call
    assert said(found) == (f"{partner.YES} Partner server added!", True)
    rep.add_roles.assert_awaited_once()
    (saved,) = server.firebase(f"Partner/partners/{GUILD}").get().values()
    assert {**saved, "created_at": 0} == {
        "name": "Good",
        "invite": "good",
        "member_count": 55,
        "staff_id": MEMBER,
        "created_at": 0,
        "category": "Genshin",
    }
    assert server.invites[-1] == (
        "good",
        {"with_counts": "true", "with_expiration": "true"},
    )
    assert server.channels[LOG].sent[-1][1]["embed"].title == "Partner Added"
    assert server.channels[PANEL].messages[1000].edit.await_count == 1


async def test_add_partner_takes_a_bot_id_without_asking_discord(server):
    await setup(server)
    await group(server)
    found, call = run(server, "add_partner", "Botty", "123456", "Genshin")
    await call
    assert said(found)[0] == f"{partner.YES} Bot partner added!"
    (saved,) = server.firebase(f"Partner/partners/{GUILD}").get().values()
    assert (saved["invite"], saved["member_count"]) == ("123456", "N/A")
    assert server.invites == []
    assert server.channels[LOG].sent[-1][1]["embed"].title == "Bot Partner Added"


async def test_add_partner_stops_when_the_role_cannot_be_given(server):
    await setup(server)
    await group(server)
    rep = MagicMock()
    rep.add_roles = AsyncMock(side_effect=RuntimeError)
    found, call = run(
        server, "add_partner", "Good", "https://discord.gg/good", "Genshin", rep
    )
    await call
    assert said(found)[0].startswith(f"{partner.NO} Invalid partner role.")
    assert server.firebase(f"Partner/partners/{GUILD}").get() is None


async def test_mass_add_reads_links_and_reports_bad_lines(server):
    await setup(server)
    await group(server)
    lines = [
        "[Alpha](https://discord.gg/aaa)",
        "",
        "nonsense",
        "- [Beta](https://discord.com/invite/bbb/x)",
        "[Gamma](https://example.com/ccc/)",
        "[Empty](discord.gg/)",
    ] + ["bad"] * 5
    found, call = run(server, "partner_mass_add", "Genshin", "\n".join(lines))
    await call
    saved = server.firebase(f"Partner/partners/{GUILD}").get().values()
    assert [(one["name"], one["invite"], one["member_count"]) for one in saved] == [
        ("Alpha", "aaa", 0),
        ("Beta", "bbb", 0),
        ("Gamma", "ccc", 0),
    ]
    assert said(found)[0] == (
        f"{partner.YES} Added 3 partners to group `Genshin`!\n"
        f"{partner.YES} Panel updated! (1 message)\n\n**Errors:**\n"
        "Line 3: Invalid format\nLine 6: Couldn't extract invite code\n"
        "Line 7: Invalid format\nLine 8: Invalid format\nLine 9: Invalid format\n"
        "...and 2 more errors"
    )


async def test_remove_partner_by_name_or_invite(server):
    await setup(server)
    add(server, "Alpha", "aaa")
    add(server, "Beta", "bbb")
    for args, answer in (
        ((), "You must provide either server name or invite link!"),
        (("nobody",), "Partner server not found!"),
        (("alpha", "https://discord.gg/zzz"), "Server name and invite don't match!"),
    ):
        found, call = run(server, "remove_partner", *args)
        await call
        assert said(found) == (f"{partner.NO} {answer}", True)
    found, call = run(server, "remove_partner", "ALPHA")
    await call
    found, call = run(server, "remove_partner", None, "https://discord.gg/bbb")
    await call
    assert said(found)[0] == f"{partner.YES} Partner server removed!"
    assert server.firebase(f"Partner/partners/{GUILD}").get() is None
    log = server.channels[LOG].sent[-1][1]["embed"]
    assert [field.value for field in log.fields][1:] == ["Beta", "bbb"]


async def test_remove_group_takes_its_partners_with_it(server):
    await setup(server)
    await group(server)
    add(server, "Alpha", "aaa")
    add(server, "Other", "ooo", "HSR")
    found, call = run(server, "partner_remove_group", "Missing")
    await call
    assert said(found)[0] == f"{partner.NO} Group not found!"
    found, call = run(server, "partner_remove_group", "Genshin")
    await call
    assert said(found)[0] == (
        f"{partner.YES} Group 'Genshin' and its 1 partner(s) were permanently deleted!"
    )
    assert server.firebase(f"Partner/categories/{GUILD}").get() is None
    (left,) = server.firebase(f"Partner/partners/{GUILD}").get().values()
    assert left["name"] == "Other"


async def edit(server, command, name, **typed):
    found, call = run(server, command, name)
    await call
    modal = found.response.send_modal.await_args.args[0]
    for field, value in typed.items():
        getattr(modal, field)._value = value
    answer = interaction(server)
    await modal.on_submit(answer)
    return modal, answer


async def test_edit_group_renames_it_and_moves_its_partners(server):
    await setup(server)
    await group(server)
    add(server, "Alpha", "aaa")
    found, call = run(server, "partner_edit_group", "Missing")
    await call
    assert said(found)[0] == f"{partner.NO} Group not found!"

    typed = dict(title_input="", color="#00ff01", thumbnail="")
    modal, answer = await edit(
        server,
        "partner_edit_group",
        "Genshin",
        name_input="a b",
        prefix_suffix="",
        **typed,
    )
    assert modal.title == "Edit Partner Group"
    assert [(item.label, item.default) for item in modal.children] == [
        ("Unique Group Name", "Genshin"),
        ("Display Title", "Genshin"),
        ("Color (hex)", "#5865F2"),
        ("Prefix, Suffix (separated by a comma)", "-"),
        ("Thumbnail URL", ""),
    ]
    assert said(answer)[0].startswith(f"{partner.NO} Invalid group name!")

    _, answer = await edit(
        server,
        "partner_edit_group",
        "Genshin",
        name_input="GI",
        prefix_suffix=" > , < , x",
        **typed,
    )
    assert said(answer)[0] == (
        f"{partner.YES} Group updated! \n{partner.YES} Panel updated! (1 message)"
    )
    assert server.firebase(f"Partner/categories/{GUILD}").get() == {
        "GI": {"title": "GI", "color": "#00ff01", "prefix": ">", "suffix": "< , x"}
    }
    (moved,) = server.firebase(f"Partner/partners/{GUILD}").get().values()
    assert moved["category"] == "GI"


async def test_edit_panel_saves_only_what_changed(server):
    await setup(server)
    typed = dict(
        title_input="Partners", description=" hi ", color="", thumbnail="", image=""
    )
    modal, answer = await edit(server, "partner_edit_panel", "header", **typed)
    assert modal.title == "Edit Header Embed"
    assert [item.label for item in modal.children] == [
        "Title",
        "Description",
        "Color (hex code)",
        "Thumbnail URL",
        "Image URL",
    ]
    assert said(answer) == (f"{partner.YES} Panel updated! (1 message)", True)
    assert server.firebase(f"Partner/config/{GUILD}/embed/header").get() == {
        "title": "Partners",
        "description": "hi",
        "color": "#5865F2",
    }
    log = server.channels[LOG].sent[-1][1]["embed"]
    assert log.title == "Panel Edited (Header)"
    assert [field.name for field in log.fields] == ["title", "description", "color"]

    modal, answer = await edit(server, "partner_edit_panel", "header", **typed)
    assert modal.title_input.default == "Partners"
    assert said(answer)[0] == f"{partner.NO} No changes detected!"


async def test_blacklist_adds_lists_and_removes(server):
    found, call = run(server, "partner_blacklist")
    await call
    assert said(found) == ("No servers are blacklisted!", True)
    found, call = run(server, "partner_blacklist", "https://discord.gg/gone")
    await call
    assert said(found)[0] == f"{partner.NO} Invalid invite: 'guild'"
    found, call = run(server, "partner_blacklist", "https://discord.gg/good")
    await call
    assert said(found)[0] == f"{partner.YES} Server 900 blacklisted!"
    assert server.invites[-1] == ("good", {})
    found, call = run(server, "partner_blacklist")
    await call
    assert said(found)[0].description == "- `900`"
    found, call = run(server, "partner_unblacklist", "900")
    await call
    assert said(found)[0] == f"{partner.YES} Server 900 unblacklisted!"
    found, call = run(server, "partner_unblacklist", "900")
    await call
    assert said(found)[0] == f"{partner.NO} Server not in blacklist!"


async def request(server, link, member=MEMBER):
    modal = partner.PartnershipRequestModal()
    modal.invite_link._value = link
    found = interaction(server, member)
    await modal.on_submit(found)
    return found


async def test_request_opens_a_private_thread(server):
    await setup(server, "1h", manager=72)
    found = await request(server, "https://discord.gg/good")
    created = server.channels[REQUESTS].create_thread
    assert created.await_args.kwargs == {
        "name": "🟡 Good",
        "type": discord.ChannelType.private_thread,
    }
    opened = created.return_value
    opened.add_user.assert_awaited_once_with(found.user)
    first = opened.send.await_args.kwargs
    assert first["content"] == "<@&72> https://discord.gg/good"
    embed = first["embed"]
    assert (embed.title, embed.color.value) == ("New Partnership Request", 0xFEE75C)
    assert [(field.name, field.value) for field in embed.fields] == [
        ("Server ID", "900"),
        ("Server Name", "Good"),
        ("Members", "55"),
        ("Permanent Server Invite", f"{partner.YES} Yes"),
        ("Requester ID", str(MEMBER)),
        ("Requester Mention", f"<@{MEMBER}>"),
    ]
    assert embed.footer.text == "Status: 🟡 Pending"
    assert embed.thumbnail.url == "https://cdn.discordapp.com/icons/900/abc.png"
    assert said(found) == (f"{partner.YES} Request created in <#600>", True)
    log = server.channels[LOG].sent[-1][1]
    assert log["embed"].title == "New Partnership Request (Good)"
    assert log["view"].children[0].url == "jump/600"

    again = await request(server, "https://discord.gg/good")
    assert said(again)[0].startswith(
        f"{partner.NO} You're on cooldown! Try again in 0h 59m"
    )
    assert created.await_count == 1


async def test_request_refuses_bad_blacklisted_and_known_servers(server):
    await setup(server)
    assert (
        said(await request(server, "gone"))[0] == f"{partner.NO} Invalid invite link!"
    )
    server.firebase(f"Partner/Blacklist/{GUILD}/900").set(True)
    assert said(await request(server, "good"))[0].startswith(
        f"{partner.NO} This server is blacklisted!"
    )
    assert said(await request(server, "known"))[0] == (
        f"{partner.NO} A partnership thread for this server already exists: <#500>"
    )
    server.channels[REQUESTS].create_thread.assert_not_awaited()
    assert server.firebase(f"Partner/Cooldown/{GUILD}").get() is None


async def test_request_without_a_manager_role_or_icon(server):
    await setup(server)
    await request(server, "https://discord.gg/short")
    first = server.channels[REQUESTS].create_thread.return_value.send.await_args.kwargs
    assert first["content"] == " https://discord.gg/short"
    assert first["embed"].thumbnail.url == partner.NO_ICON
    assert first["embed"].fields[2].value == "Unknown"
    assert first["embed"].fields[3].value == f"{partner.NO} No"


async def test_staff_create_skips_the_blacklist(server):
    await setup(server)
    server.firebase(f"Partner/Blacklist/{GUILD}/900").set(True)
    found, call = run(server, "partner_create", "https://discord.gg/good")
    await call
    opened = server.channels[REQUESTS].create_thread.return_value
    opened.add_user.assert_not_awaited()
    first = opened.send.await_args.kwargs
    assert first["content"] == "https://discord.gg/good"
    assert first["embed"].title == "Partnership Thread (initiated by Staff)"
    assert [field.name for field in first["embed"].fields][4:] == [
        "Staff ID",
        "Staff Mention",
    ]
    assert first["embed"].thumbnail.url is None
    assert server.invites[-1] == ("good", {"with_counts": "true"})
    assert said(found)[0].startswith(f"{partner.YES} Thread created: <#600>.")

    found, call = run(server, "partner_create", "https://discord.gg/known")
    await call
    assert "already exists: <#500>" in said(found)[0]


@pytest.mark.parametrize(
    "status, name, colour",
    [("accepted", "🟡 Good", 0x57F287), ("blacklisted", "🟢🔴 Good ", 0x000000)],
)
async def test_status_renames_the_thread_and_recolours_its_embed(
    server, status, name, colour
):
    await setup(server)
    found, call = run(server, "partner_status", status, "because")
    opened = thread(600, "900")
    found.channel = MagicMock(spec=discord.Thread)
    found.channel.name = name
    found.channel.history = opened.history
    found.channel.edit = AsyncMock()
    await call
    emoji = partner.STATUSES[status][0]
    found.channel.edit.assert_awaited_once_with(name=f"{emoji} Good")
    embed = opened.first.edit.await_args.kwargs["embed"]
    assert embed.color.value == colour
    assert (
        embed.footer.text == f"Status: {emoji} {status.capitalize()} | Reason: because"
    )
    assert said(found) == (f"{partner.YES} Status updated to {emoji} {status}!", True)
    assert (
        server.channels[LOG].sent[-1][1]["embed"].title
        == f"Partner Status Updated {emoji}"
    )


async def test_status_and_invite_only_work_in_threads(server):
    found, call = run(server, "partner_status", "accepted")
    await call
    assert (
        said(found)[0]
        == f"{partner.NO} This command must be used in a partnership thread!"
    )
    found, call = run(server, "partner_invite", MagicMock())
    await call
    assert said(found)[0] == (
        f"{partner.NO} This command can only be used in partnership threads!"
    )


async def test_invite_adds_a_member_to_the_thread(server):
    guest = MagicMock()
    guest.mention = "<@9>"
    found, call = run(server, "partner_invite", guest)
    found.channel = MagicMock(spec=discord.Thread)
    found.channel.add_user = AsyncMock()
    await call
    found.channel.add_user.assert_awaited_once_with(guest)
    assert said(found) == (f"{partner.YES} <@9> has been added to the thread!", True)

    found, call = run(server, "partner_invite", guest)
    found.channel = MagicMock(spec=discord.Thread)
    found.channel.add_user = AsyncMock(side_effect=RuntimeError)
    await call
    assert said(found)[0] == f"{partner.NO} Sorry, something went wrong!"


async def test_disable_deletes_the_panel_and_all_settings(server):
    found, call = run(server, "partner_disable")
    await call
    assert said(found)[0] == f"{partner.NO} Partnership system not enabled!"
    await setup(server)
    await group(server)
    add(server, "Alpha", "aaa")
    server.firebase(f"Partner/Blacklist/{GUILD}/900").set(True)
    found, call = run(server, "partner_disable")
    await call
    server.channels[PANEL].messages[1000].delete.assert_awaited_once()
    assert server.firebase("Partner").get() == {
        "Blacklist": {str(GUILD): {"900": True}}
    }
    assert said(found) == (
        f"{partner.YES} Partnership system disabled! All configurations removed.",
        True,
    )


async def test_autocomplete_suggests_matching_groups(server):
    for name in ("Genshin", "HSR", "Hangouts"):
        server.firebase(f"Partner/categories/{GUILD}/{name}").set({"title": name})
    found = await partner.category_autocomplete(interaction(server), "h")
    assert [choice.value for choice in found] == ["Genshin", "HSR", "Hangouts"]
    found = await partner.category_autocomplete(interaction(server), "hs")
    assert [choice.value for choice in found] == ["HSR"]


async def test_firebase_changes_queue_each_server_they_touch(server):
    server.bot.loop = asyncio.get_running_loop()
    listener = partner.PartnershipFirebaseListener(server.bot)
    for path, data in (
        ("/", {"5": {}, "x": {}, "6": {}}),
        ("/", None),
        ("/7", {}),
        ("/8/abc/name", "new"),
    ):
        event = MagicMock()
        event.path, event.data = path, data
        listener.changed(event)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    queued = []
    while not listener.update_queue.empty():
        queued.append(listener.update_queue.get_nowait())
    assert queued == [5, 6, 7, 8]


async def test_listener_updates_a_changed_server_once(server):
    listener = partner.PartnershipFirebaseListener(server.bot)
    listener._execute_panel_update = AsyncMock()
    for guild in (GUILD, 5, GUILD):
        listener.update_queue.put_nowait(guild)
    with patch.object(partner.asyncio, "wait_for", wraps=asyncio.wait_for) as wait_for:
        task = asyncio.create_task(listener._process_updates())
        while not listener._execute_panel_update.await_count == 2:
            await asyncio.sleep(0.05)
        task.cancel()
    assert wait_for.call_args.kwargs == {"timeout": 2.0}
    assert [call.args for call in listener._execute_panel_update.await_args_list] == [
        (GUILD,),
        (5,),
    ]


async def test_listener_skips_servers_without_a_panel(server):
    listener = partner.PartnershipFirebaseListener(server.bot)
    await listener._execute_panel_update(GUILD)
    await setup(server)
    await listener._execute_panel_update(GUILD)
    assert server.channels[PANEL].messages[1000].edit.await_count == 1


async def test_one_server_never_touches_another(server):
    other = {
        "config": {"enabled": True},
        "partners": {"a": {"name": "Alpha", "invite": "aaa", "category": "Genshin"}},
        "categories": {"Genshin": {"title": "G"}},
        "panels": {"message_ids": [1], "channel_id": 2},
        "Cooldown": {str(MEMBER): 5},
        "Blacklist": {"900": True},
    }
    for name, value in other.items():
        server.firebase(f"Partner/{name}/88").set(value)
    await setup(server, "1h")
    await request(server, "https://discord.gg/good")
    assert list(server.firebase(f"Partner/Cooldown/{GUILD}").get()) == [str(MEMBER)]
    await setup(server, "1h")
    await group(server)
    add(server, "Alpha", "aaa")
    for command, args in (
        ("partner_blacklist", ("https://discord.gg/good",)),
        ("partner_unblacklist", ("900",)),
        ("remove_partner", ("Alpha",)),
        ("partner_remove_group", ("Genshin",)),
        ("partner_disable", ()),
    ):
        _, call = run(server, command, *args)
        await call
    assert sorted(server.firebase("Partner/Cooldown").get()) == [str(GUILD), "88"]
    for name, value in other.items():
        assert server.firebase(f"Partner/{name}/88").get() == value


async def test_setup_again_keeps_the_panel_wording(server):
    await setup(server)
    server.firebase(f"Partner/config/{GUILD}/embed/header/title").set("Partners")
    await setup(server)
    assert (
        server.firebase(f"Partner/config/{GUILD}/embed/header/title").get()
        == "Partners"
    )
