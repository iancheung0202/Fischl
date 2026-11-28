"""Booster roles under shared/: thank-you message, custom roles, auto responses and cleanup."""

import asyncio
import io
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from PIL import Image

from shared.Boosters import booster as module
from shared.Boosters.booster import (
    NOT_BOOSTING,
    NOT_ENABLED,
    AutoResponseApprovalView,
    AutoResponsePanelView,
    BoosterEmbedModal,
    BoosterRole,
    RoleApprovalView,
    SettingsPanelView,
    parse_color,
    resized,
    script,
)

GUILD, AMY, BEN = 5, 7, 8
SYSTEM, PUBLIC, LOG, BASE = 50, 51, 52, 60
CONFIG = {"base_role": BASE, "system_channel": SYSTEM, "channel": PUBLIC, "log": LOG}


@pytest.fixture(autouse=True)
def fresh(firebase):
    """Empties the kept settings and gives each test its own lock."""
    module.cache.update(at=None, servers={}, writes=0)
    module.refreshing = asyncio.Lock()
    module.handling.clear()
    return firebase


def person(user_id=AMY, boosting=True, guild=None):
    """A member, boosting or not."""
    made = MagicMock()
    made.id, made.name, made.mention = user_id, f"user{user_id}", f"<@{user_id}>"
    made.premium_since = "2024" if boosting else None
    made.guild = guild or MagicMock(id=GUILD)
    made.roles = []
    made.send, made.add_roles = AsyncMock(), AsyncMock()
    return made


def server(members=(), roles=(), guild_id=GUILD):
    """A server with its three channels, some roles and members."""
    made = MagicMock()
    made.id, made.name, made.premium_subscription_count = guild_id, "Mondstadt", 3
    made.premium_tier = 2
    made.channels = {}
    for channel_id in (SYSTEM, PUBLIC, LOG):
        channel = MagicMock(id=channel_id, mention=f"<#{channel_id}>")
        channel.send = AsyncMock()
        made.channels[channel_id] = channel
    made.get_channel = made.channels.get
    found = {role.id: role for role in roles}
    made.roles = list(roles) or [MagicMock()]
    made.get_role = found.get
    here = {one.id: one for one in members}
    for one in members:
        one.guild = made

    async def fetch_member(user_id):
        if user_id not in here:
            raise discord.NotFound(
                MagicMock(status=404), {"code": 10007, "message": "Unknown Member"}
            )
        return here[user_id]

    made.fetch_member = fetch_member
    made.create_role = AsyncMock()
    made.edit_role_positions = AsyncMock()
    return made


def role(role_id, name="Shiny"):
    """A role that can be deleted."""
    made = MagicMock(id=role_id, position=4)
    made.name = name
    made.delete, made.edit = AsyncMock(), AsyncMock()
    return made


def press(guild=None, user=None, message=None):
    """An interaction in the server."""
    it = MagicMock()
    for name in ("send_message", "edit_message", "send_modal", "defer"):
        setattr(it.response, name, AsyncMock())
    it.response.is_done = MagicMock(return_value=False)
    it.followup.send = AsyncMock()
    it.guild = guild or server()
    it.guild_id = it.guild.id
    it.user = user or person()
    it.user.guild = it.guild
    it.client.get_guild = lambda guild_id: it.guild
    it.client.get_channel = lambda channel_id: None
    if message:
        it.message = message
    return it


def request(embed, message_id=900):
    """A request message in the log channel."""
    made = MagicMock(id=message_id, embeds=[embed])
    made.edit = AsyncMock()
    return made


def cog():
    bot = MagicMock()
    bot.is_closed.return_value = False
    made = BoosterRole.__new__(BoosterRole)
    made.bot, made.unloading = bot, False
    return made


def said(mock):
    """Gives the text of the last message a mock was asked to send."""
    call = mock.call_args
    return call.args[0] if call.args else call.kwargs.get("content")


def logged(guild):
    return [
        (c.kwargs["embed"].title, c.kwargs["embed"].description)
        for c in guild.channels[LOG].send.call_args_list
    ]


def test_parse_color():
    assert parse_color("#FF0000").value == 0xFF0000
    assert parse_color("0f0").value == 0x00FF00
    assert parse_color("nope") == discord.Color.pink()
    assert parse_color("") == discord.Color.pink()
    assert parse_color(None) == discord.Color.pink()


def test_script():
    assert (
        script("{mention} {user} {server} {boost}", person(), server())
        == "<@7> user7 Mondstadt 3"
    )


def test_resized_png_and_gif():
    stored = io.BytesIO()
    Image.new("RGB", (600, 300), "red").save(stored, "PNG")
    out = Image.open(resized(stored.getvalue(), 150))
    assert out.size == (300, 150) and out.format == "PNG"
    frames = [Image.new("P", (40, 20), n) for n in range(3)]
    stored = io.BytesIO()
    frames[0].save(stored, "GIF", save_all=True, append_images=frames[1:], duration=80)
    out = Image.open(resized(stored.getvalue(), 10))
    assert out.size == (20, 10) and out.format == "GIF"


async def test_boost_message_sends_the_thank_you(firebase):
    firebase(f"Booster Role/{GUILD}").set(
        {
            **CONFIG,
            "embed": {
                "message": "Thanks {mention}",
                "title": "{user}",
                "description": "{server} has {boost}",
                "color": "#00ff00",
                "image": "https://x/y.png",
            },
        }
    )
    guild = server()
    message = MagicMock(guild=guild, content="")
    message.author = person(guild=guild)
    message.author.__class__ = discord.Member
    message.author.bot = False
    message.type = discord.MessageType.premium_guild_subscription
    message.channel.id = SYSTEM
    await cog().on_message(message)
    send = guild.channels[PUBLIC].send
    assert said(send) == "Thanks <@7>"
    embed = send.call_args.kwargs["embed"]
    assert (embed.title, embed.description) == ("user7", "Mondstadt has 3")
    assert embed.color.value == 0x00FF00 and embed.image.url == "https://x/y.png"
    message.channel.id = PUBLIC
    await cog().on_message(message)
    assert send.call_count == 1


def chat(guild, content, author):
    message = MagicMock(guild=guild, content=content, author=author)
    message.author.bot = False
    message.type = discord.MessageType.default
    message.channel.send = AsyncMock()
    return message


async def test_mention_gets_the_auto_response(firebase, monkeypatch):
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "autoresponses": {str(AMY): {"response": "hi!"}}}
    )
    amy, ben = person(AMY), person(BEN, boosting=False)
    guild = server([amy, ben])
    message = chat(guild, f"hello <@!{AMY}>", ben)
    await cog().on_message(message)
    message.channel.send.assert_awaited_once_with("hi!")
    own = chat(guild, f"<@{AMY}>", amy)
    await cog().on_message(own)
    own.channel.send.assert_not_called()
    amy.premium_since = None
    message = chat(guild, f"<@{AMY}>", ben)
    await cog().on_message(message)
    message.channel.send.assert_not_called()


async def test_messages_read_firebase_once(firebase, monkeypatch):
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    reads = []
    real = module.read

    async def counted(path=""):
        reads.append(path)
        return await real(path)

    monkeypatch.setattr(module, "read", counted)
    guild = server()
    await cog().on_message(chat(guild, "no mention", person()))
    assert reads == []
    for _ in range(5):
        await cog().on_message(chat(guild, "<@1>", person()))
    assert reads == [""]
    await module.write(f"{GUILD}/autoresponses/1", {"response": "x"})
    message = chat(server([person(1)]), "<@1>", person())
    await cog().on_message(message)
    assert reads == ["", ""]
    message.channel.send.assert_awaited_once_with("x")


async def test_setup_keeps_roles_and_responses(firebase):
    firebase(f"Booster Role/{GUILD}").set(
        {
            **CONFIG,
            "roles": {"7": 70},
            "autoresponses": {"7": {"response": "a"}},
            "embed": {"message": "m", "title": "t"},
        }
    )
    it = press()
    it.guild.premium_subscriber_role = MagicMock(id=61)
    channels = [MagicMock(id=n) for n in (1, 2, 3)]
    await BoosterRole.setup.callback(cog(), it, *channels)
    modal = it.response.send_modal.call_args.args[0]
    assert modal.msg.default == "m" and modal.embed_title.default == "t"
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert saved["roles"] == {"7": 70} and saved["autoresponses"]
    assert (saved["base_role"], saved["system_channel"]) == (61, 1)
    assert (saved["channel"], saved["log"]) == (2, 3)


async def test_setup_needs_a_booster_role(firebase):
    it = press()
    it.guild.premium_subscriber_role = None
    await BoosterRole.setup.callback(cog(), it, *[MagicMock(id=n) for n in (1, 2, 3)])
    assert "must have a booster role" in said(it.response.send_message)
    assert firebase("Booster Role").get() is None


async def test_embed_modal_saves(firebase):
    modal = BoosterEmbedModal({"message": "old"})
    for item, value in (
        (modal.msg, "m"),
        (modal.embed_title, "t"),
        (modal.embed_desc, "d"),
        (modal.color, "#fff"),
        (modal.image, ""),
    ):
        item._value = value
    it = press()
    await modal.on_submit(it)
    assert firebase(f"Booster Role/{GUILD}/embed").get() == {
        "message": "m",
        "title": "t",
        "description": "d",
        "color": "#fff",
        "image": "",
    }
    assert "configured" in said(it.followup.send)


async def test_create_asks_the_staff(firebase):
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    it = press()
    it.user.guild_permissions.administrator = False
    await BoosterRole.create.callback(cog(), it, "#ff0000", "Shiny")
    assert firebase(f"Booster Role/{GUILD}/pending_roles/{AMY}").get() == {
        "name": "Shiny",
        "color": "#ff0000",
    }
    sent = it.guild.channels[LOG].send.call_args.kwargs
    assert sent["embed"].footer.text == f"Guild ID: {GUILD} | User ID: {AMY}"
    assert isinstance(sent["view"], RoleApprovalView)
    assert it.followup.send.call_args.kwargs["embed"].title.endswith("Submitted")
    again = press()
    await BoosterRole.create.callback(cog(), again, "#00ff00", "Other")
    assert again.followup.send.call_args.kwargs["embed"].title == (
        "⏳ Pending Role Request"
    )


async def test_create_refusals(firebase):
    it = press(user=person(boosting=False))
    await BoosterRole.create.callback(cog(), it, "#f00", "x")
    assert said(it.followup.send) == NOT_ENABLED
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    it = press(user=person(boosting=False))
    await BoosterRole.create.callback(cog(), it, "#f00", "x")
    assert said(it.followup.send) == NOT_BOOSTING
    it = press()
    it.user.guild_permissions.administrator = False
    await BoosterRole.create.callback(cog(), it, "#f00", "x", None, person(BEN))
    assert "cannot create booster roles for others" in said(it.response.send_message)
    firebase(f"Booster Role/{GUILD}/roles/{AMY}").set(70)
    it = press(guild=server(roles=[role(70)]))
    await BoosterRole.create.callback(cog(), it, "#f00", "x")
    assert "already have your custom role" in said(it.followup.send)


def role_request(name="Shiny", color="#ff0000", icon="None"):
    embed = discord.Embed(title="⏳ Custom Role Request - Pending Approval")
    embed.add_field(name="Name", value=name)
    embed.add_field(name="Color", value=color)
    embed.add_field(name="Icon", value=icon)
    embed.set_footer(text=f"Guild ID: {GUILD} | User ID: {AMY}")
    return embed


async def test_approve_role(firebase):
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "pending_roles": {str(AMY): {"name": "Shiny"}}, "roles": {"9": 90}}
    )
    amy, base, new = person(), role(BASE), role(71)
    guild = server([amy], [base])
    guild.create_role.return_value = new
    it = press(guild, message=request(role_request()))
    view = RoleApprovalView()
    await view.approve.callback(it)
    guild.create_role.assert_awaited_once()
    assert guild.create_role.call_args.kwargs["name"] == "Shiny"
    guild.edit_role_positions.assert_awaited_once_with(positions={new: 5})
    amy.add_roles.assert_awaited_once_with(new)
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert saved["roles"] == {"9": 90, str(AMY): 71}
    assert "pending_roles" not in saved
    assert it.message.edit.call_args.kwargs["view"] is None
    assert "approved" in said(amy.send)
    assert said(it.followup.send) == "Role created successfully!"
    assert not module.handling


async def test_approve_role_twice_makes_one_role(firebase):
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    guild = server([person()], [role(BASE)])
    guild.create_role.return_value = role(71)
    message = request(role_request())
    first, second = press(guild, message=message), press(guild, message=message)
    view = RoleApprovalView()
    await asyncio.gather(view.approve.callback(first), view.approve.callback(second))
    assert guild.create_role.await_count == 1
    assert "already being handled" in said(second.response.send_message)


async def test_approve_role_when_the_member_left(firebase):
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    it = press(server(roles=[role(BASE)]), message=request(role_request()))
    await RoleApprovalView().approve.callback(it)
    assert said(it.followup.send) == "User not found"
    it.guild.create_role.assert_not_called()


async def test_reject_role(firebase):
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "pending_roles": {str(AMY): {"name": "Shiny"}}}
    )
    it = press(server(), message=request(role_request()))
    await RoleApprovalView().reject.callback(it)
    assert "pending_roles" not in firebase(f"Booster Role/{GUILD}").get()
    assert said(it.followup.send) == "Request rejected!"
    assert it.message.edit.call_args.kwargs["embed"].title.endswith("Rejected")


def response_request(text="hi!"):
    embed = discord.Embed(title="⏳ Auto Response Pending Approval")
    embed.add_field(name="Trigger Phrase", value="Mention Only")
    embed.add_field(name="Response", value=text)
    embed.set_footer(text=f"Guild ID: {GUILD} | User ID: {AMY}")
    return embed


async def test_approve_and_reject_auto_response(firebase):
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "pending_autoresponses": {str(AMY): {"response": "hi!"}}}
    )
    amy = person()
    it = press(server([amy]), message=request(response_request()))
    await AutoResponseApprovalView().approve.callback(it)
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert saved["autoresponses"] == {str(AMY): {"response": "hi!"}}
    assert "pending_autoresponses" not in saved
    assert said(it.followup.send) == "Approved!" and "approved" in said(amy.send)
    firebase(f"Booster Role/{GUILD}/pending_autoresponses/{AMY}").set({"response": 1})
    it = press(server(), message=request(response_request()))
    await AutoResponseApprovalView().reject.callback(it)
    assert "pending_autoresponses" not in firebase(f"Booster Role/{GUILD}").get()
    assert said(it.followup.send) == "Rejected!"


async def test_panel_submit_and_reset(firebase):
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    view = AutoResponsePanelView(AMY, "not_set")
    assert not view.setup_button.disabled and view.reset_button.disabled
    view.message = MagicMock(edit=AsyncMock())
    it = press()
    await view.submit(it, "hello there")
    assert firebase(f"Booster Role/{GUILD}/pending_autoresponses/{AMY}").get() == {
        "response": "hello there"
    }
    assert view.status == "pending" and view.setup_button.disabled
    sent = it.guild.channels[LOG].send.call_args.kwargs
    assert sent["embed"].fields[1].value == "hello there"
    assert "submitted" in said(it.followup.send)
    firebase(f"Booster Role/{GUILD}/autoresponses/{AMY}").set({"response": "x"})
    it = press()
    await view.reset_button.callback(it)
    it.response.defer.assert_awaited_once()
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert "autoresponses" not in saved and "pending_autoresponses" not in saved
    assert view.status == "not_set"


async def test_panel_submit_without_log_channel(firebase):
    view = AutoResponsePanelView(AMY, "not_set")
    it = press()
    await view.submit(it, "hello")
    assert said(it.followup.send) == module.NO_LOG
    assert firebase("Booster Role").get() is None


async def test_sweep(firebase):
    amy, ben = person(AMY), person(BEN, boosting=False)
    kept, expired, orphan = role(70), role(80), role(90)
    amy.roles = []
    guild = server([amy, ben], [kept, expired, orphan])
    firebase(f"Booster Role/{GUILD}").set(
        {
            **CONFIG,
            "roles": {str(AMY): 70, str(BEN): 80, "9": 90, "10": 100},
            "autoresponses": {str(BEN): {"response": "x"}, str(AMY): {"response": "y"}},
            "pending_autoresponses": {str(BEN): {"response": "x"}},
            "pending_roles": {str(BEN): {"name": "a"}, str(AMY): {"name": "b"}},
        }
    )
    made = cog()
    made.bot.get_guild = lambda guild_id: guild
    await made.cleanup_all()
    amy.add_roles.assert_awaited_once_with(kept)
    kept.delete.assert_not_called()
    expired.delete.assert_awaited_once()
    orphan.delete.assert_awaited_once()
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert saved["roles"] == {str(AMY): 70}
    assert saved["autoresponses"] == {str(AMY): {"response": "y"}}
    assert "pending_autoresponses" not in saved
    assert saved["pending_roles"] == {str(AMY): {"name": "b"}}
    titles = [title for title, _ in logged(guild)]
    assert titles == [
        "Role Assignment Fix",
        "Expired Booster Cleanup",
        "Auto Response Cleanup",
        "Pending Auto Response Cleanup",
        "Expired Booster Cleanup",
        "Database Cleanup",
    ]
    assert logged(guild)[1][1] == (
        "🗑️ Deleted role `Shiny` (ID: `80`) for <@8> (ID: `8`) - No longer boosting"
    )
    assert logged(guild)[4][1] == (
        "🗑️ Deleted role `Shiny` (ID: `90`) for user who left the server (ID: `9`)"
    )


async def test_sweep_keeps_roles_when_discord_fails(firebase):
    kept = role(70)
    guild = server(roles=[kept])
    guild.fetch_member = AsyncMock(
        side_effect=discord.HTTPException(MagicMock(status=500), "down")
    )
    firebase(f"Booster Role/{GUILD}").set({**CONFIG, "roles": {str(AMY): 70}})
    made = cog()
    made.bot.get_guild = lambda guild_id: guild
    await made.cleanup_all()
    kept.delete.assert_not_called()
    assert firebase(f"Booster Role/{GUILD}/roles").get() == {str(AMY): 70}


async def test_open_server_keeps_roles_of_members_who_do_not_boost(firebase):
    ben, kept = person(BEN, boosting=False), role(70)
    guild = server([ben], [kept], guild_id=module.OPEN_SERVER)
    ben.roles = [kept]
    firebase(f"Booster Role/{module.OPEN_SERVER}").set(
        {**CONFIG, "roles": {str(BEN): 70}, "pending_roles": {str(BEN): {"name": "a"}}}
    )
    made = cog()
    made.bot.get_guild = lambda guild_id: guild
    await made.cleanup_all()
    kept.delete.assert_not_called()
    saved = firebase(f"Booster Role/{module.OPEN_SERVER}").get()
    assert saved["roles"] and saved["pending_roles"]


async def test_cleanup_command(firebase):
    it = press()
    await BoosterRole.cleanup.callback(cog(), it)
    assert said(it.followup.send) == NOT_ENABLED
    firebase(f"Booster Role/{GUILD}").set({**CONFIG, "roles": {"9": 90}})
    it = press(server(roles=[role(1)]))
    await BoosterRole.cleanup.callback(cog(), it)
    assert "Cleanup completed" in said(it.followup.send)
    assert "roles" not in firebase(f"Booster Role/{GUILD}").get()


async def test_remove_command(firebase):
    firebase(f"Booster Role/{GUILD}").set({**CONFIG, "roles": {str(AMY): 70}})
    it = press()
    await BoosterRole.remove.callback(cog(), it)
    assert "no booster role" in said(it.followup.send)
    mine = role(70)
    it = press(server(roles=[mine]))
    await BoosterRole.remove.callback(cog(), it)
    mine.delete.assert_awaited_once()
    assert "roles" not in firebase(f"Booster Role/{GUILD}").get()
    assert "has been deleted" in said(it.followup.send)
    assert logged(it.guild)[0][0] == "Booster Role Removed"


async def test_settings_and_its_buttons(firebase):
    it = press()
    await BoosterRole.settings.callback(cog(), it)
    assert said(it.followup.send) == NOT_ENABLED
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    it = press(server(roles=[role(BASE)]))
    await BoosterRole.settings.callback(cog(), it)
    sent = it.followup.send.call_args.kwargs
    assert "**Public Channel:** <#51>" in sent["embed"].fields[0].value
    view = sent["view"]
    assert isinstance(view, SettingsPanelView)
    it = press()
    await view.view_autoresponses.callback(it)
    assert "No autoresponses configured" in said(it.followup.send)
    it.response.send_message.assert_not_called()
    await view.view_custom_roles.callback(it)
    assert "No booster roles found" in said(it.followup.send)
    firebase(f"Booster Role/{GUILD}/roles").set({"7": 70})
    firebase(f"Booster Role/{GUILD}/autoresponses").set({"9": {"response": "x"}})
    await view.view_custom_roles.callback(it)
    assert it.followup.send.call_args.kwargs["embed"].description == "<@7> - <@&70>"
    await view.view_autoresponses.callback(it)
    shown = it.followup.send.call_args.kwargs["embed"].fields[0]
    assert shown.name == "Unknown (9) (`9`)"


async def test_disable(firebase, monkeypatch):
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "roles": {"7": 70, "8": 80}, "autoresponses": {"7": {}}}
    )
    firebase("Booster Role/6").set(CONFIG)
    gone, stuck = role(70), role(80)
    stuck.delete.side_effect = RuntimeError("no")
    it = press(server(roles=[gone, stuck]))

    async def confirmed(self):
        self.confirmed = True

    monkeypatch.setattr(module.ConfirmDisableView, "wait", confirmed)
    await BoosterRole.disable.callback(cog(), it)
    gone.delete.assert_awaited_once()
    assert firebase("Booster Role").get() == {"6": CONFIG}
    final = it.followup.send.call_args.kwargs["embed"]
    assert [f.value for f in final.fields] == ["1", "1", "Removed from database"]
    assert logged(it.guild)[-1][0] == "System Disabled"


async def test_disable_cancelled(firebase, monkeypatch):
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    monkeypatch.setattr(module.ConfirmDisableView, "wait", AsyncMock())
    await BoosterRole.disable.callback(cog(), press())
    assert firebase(f"Booster Role/{GUILD}").get() == CONFIG


async def test_autoresponse_command(firebase):
    it = press(user=person(boosting=False))
    await BoosterRole.autoresponse.callback(cog(), it)
    assert said(it.response.send_message) == NOT_BOOSTING
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "autoresponses": {str(AMY): {"response": "yo"}}}
    )
    it = press()
    await BoosterRole.autoresponse.callback(cog(), it)
    sent = it.followup.send.call_args.kwargs
    assert sent["view"].status == "active"
    assert sent["embed"].fields[1].value == "yo"


async def test_command_error_after_defer():
    it = press()
    it.response.is_done.return_value = True
    await cog().cog_app_command_error(it, RuntimeError("boom"))
    assert said(it.followup.send) == "```boom```"


async def test_setup_registers_the_approval_buttons():
    bot = MagicMock(add_cog=AsyncMock())
    await module.setup(bot)
    kinds = [type(c.args[0]) for c in bot.add_view.call_args_list]
    assert kinds == [AutoResponseApprovalView, RoleApprovalView]


async def test_failed_defer_frees_the_request(firebase):
    it = press(server(), message=request(role_request()))
    it.response.defer.side_effect = discord.NotFound(MagicMock(status=404), "gone")
    with pytest.raises(discord.NotFound):
        await RoleApprovalView().reject.callback(it)
    assert not module.handling


async def test_unknown_guild_is_not_a_member_who_left(firebase):
    kept = role(70)
    guild = server(roles=[kept])
    guild.fetch_member = AsyncMock(
        side_effect=discord.NotFound(
            MagicMock(status=404), {"code": 10004, "message": "Unknown Guild"}
        )
    )
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "roles": {str(AMY): 70}, "pending_roles": {str(AMY): {"name": "a"}}}
    )
    made = cog()
    made.bot.get_guild = lambda guild_id: guild
    await made.cleanup_all()
    kept.delete.assert_not_called()
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert saved["roles"] and saved["pending_roles"]


async def test_log_channel_without_access_does_not_stop_the_sweep(firebase):
    first, second = server(guild_id=5), server(guild_id=6)
    first.channels[LOG].send.side_effect = discord.Forbidden(
        MagicMock(status=403), "no"
    )
    for guild_id in (5, 6):
        firebase(f"Booster Role/{guild_id}").set({**CONFIG, "roles": {"9": 90}})
    made = cog()
    made.bot.get_guild = {5: first, 6: second}.get
    await made.cleanup_all()
    assert firebase("Booster Role/5/roles").get() is None
    assert firebase("Booster Role/6/roles").get() is None


async def test_sweep_keeps_a_role_saved_during_the_sweep(firebase):
    guild = server()
    firebase(f"Booster Role/{GUILD}").set({**CONFIG, "roles": {str(AMY): 71}})
    await cog().check_role(guild, CONFIG, str(AMY), 70)
    assert firebase(f"Booster Role/{GUILD}/roles").get() == {str(AMY): 71}


async def test_write_during_a_read_is_not_cached(firebase, monkeypatch):
    firebase(f"Booster Role/{GUILD}").set(
        {**CONFIG, "autoresponses": {"1": {"response": "x"}}}
    )
    real = module.read

    async def slow(path=""):
        found = await real(path)
        if path == "":
            await module.remove(f"{GUILD}/autoresponses/1")
        return found

    monkeypatch.setattr(module, "read", slow)
    await module.servers()
    monkeypatch.setattr(module, "read", real)
    assert "autoresponses" not in (await module.servers())[str(GUILD)]


async def test_approve_after_disable_writes_nothing(firebase):
    it = press(server(), message=request(response_request()))
    await AutoResponseApprovalView().approve.callback(it)
    assert firebase("Booster Role").get() is None
    assert said(it.followup.send) == NOT_ENABLED


async def test_other_members_are_left_alone(firebase):
    other = {"9": {"response": "z"}}
    firebase(f"Booster Role/{GUILD}").set(
        {
            **CONFIG,
            "roles": {str(AMY): 70, "9": 90},
            "pending_roles": {str(AMY): {"name": "a"}, "9": {"name": "b"}},
            "autoresponses": {str(AMY): {"response": "y"}, **other},
            "pending_autoresponses": {str(AMY): {"response": "y"}, **other},
        }
    )
    await RoleApprovalView().reject.callback(
        press(server(), message=request(role_request()))
    )
    view = AutoResponsePanelView(AMY, "active", {"response": "y"})
    view.message = MagicMock(edit=AsyncMock())
    await view.reset_button.callback(press())
    await BoosterRole.remove.callback(cog(), press(server(roles=[role(70)])))
    saved = firebase(f"Booster Role/{GUILD}").get()
    assert saved["roles"] == {"9": 90}
    assert saved["pending_roles"] == {"9": {"name": "b"}}
    assert saved["autoresponses"] == other
    assert saved["pending_autoresponses"] == other


async def test_remove_when_the_bot_may_not_delete(firebase):
    firebase(f"Booster Role/{GUILD}").set({**CONFIG, "roles": {str(AMY): 70}})
    mine = role(70)
    mine.delete.side_effect = discord.Forbidden(MagicMock(status=403), "no")
    it = press(server(roles=[mine]))
    await BoosterRole.remove.callback(cog(), it)
    assert "lacks permission" in said(it.followup.send)
    assert firebase(f"Booster Role/{GUILD}/roles").get() == {str(AMY): 70}


async def test_cache_loads_right_after_the_machine_started(firebase, monkeypatch):
    monkeypatch.setattr(module.time, "monotonic", lambda: 120.0)
    firebase(f"Booster Role/{GUILD}").set(CONFIG)
    assert str(GUILD) in await module.servers()
    await module.write(f"{GUILD}/log", 9)
    assert (await module.servers())[str(GUILD)]["log"] == 9


async def test_sweep_survives_a_broken_pending_key(firebase):
    guild = server()
    config = {**CONFIG, "pending_roles": {"oops": {"name": "a"}}}
    await cog().sweep(guild, config)
