"""Welcome under shared/: the join message, old and new records, the editor and /welcome."""

import asyncio
import io
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from firebase_admin import db
from PIL import Image, ImageFont

from shared.Welcome import welcome as module
from shared.Welcome.welcome import (
    GONE,
    OFF,
    UNSET,
    OnWelcomeMemberJoin,
    Welcome,
    WelcomeButtonLinkModal,
    WelcomeButtonLinksEditorView,
    WelcomeEditor,
    WelcomeEmbedModal,
    WelcomeEnableView,
    WelcomeFieldModal,
    WelcomeFieldsEditorView,
    WelcomeSettingsView,
    greet,
    legacy_color,
    ordinal,
    plain_color,
    saved_editor,
    script,
)

GUILD = 5
CHANNEL = 50
AMY = 7


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    """Empties the caches and keeps backgrounds in a folder of the test."""
    module.legacy_cache.update(at=None, settings=None)
    module.api_colors.clear()
    module.saving.clear()
    monkeypatch.setattr(module, "BACKGROUNDS", str(tmp_path))
    icon = tmp_path / "icon.png"
    Image.new("RGB", (256, 256), "white").save(icon)
    monkeypatch.setattr(module, "DEFAULT_ICON", str(icon))
    plain = ImageFont.load_default()
    monkeypatch.setattr(module, "font", lambda size, fallback_size: (plain, False))
    return tmp_path


def guild():
    """A server of 21 members with one channel."""
    made = MagicMock()
    made.id, made.name, made.member_count = GUILD, "Mondstadt", 21
    made.__str__ = lambda self: "Mondstadt"
    made.get_channel = lambda channel_id: discord.Object(
        channel_id, type=discord.abc.GuildChannel
    )
    return made


def member(guild_id=GUILD):
    """Amy, in the server."""
    made = MagicMock()
    made.id, made.name, made.mention = AMY, "amy", "<@7>"
    made.guild = guild()
    made.guild.id = guild_id
    made.avatar.with_static_format.return_value.with_size.return_value.read = AsyncMock(
        side_effect=RuntimeError("no avatar")
    )
    made.send = AsyncMock()
    return made


def client(card_log=True):
    """A bot that sees the welcome channel and, for Fischl, the card channel."""
    channel = MagicMock()
    channel.id, channel.mention = CHANNEL, "<#50>"
    channel.send = AsyncMock()
    log = MagicMock()
    posted = MagicMock()
    posted.attachments = [SimpleNamespace(proxy_url="https://cdn/card.png")]
    log.send = AsyncMock(return_value=posted)
    channels = {CHANNEL: channel}
    if card_log:
        channels[module.CARD_LOG] = log
    bot = MagicMock()
    bot.get_channel = channels.get
    bot.channel, bot.log = channel, log
    return bot


def press(**changes):
    """An interaction by Amy in the server."""
    it = MagicMock()
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.response.send_modal = AsyncMock()
    it.response.defer = AsyncMock()
    it.response.is_done = MagicMock(return_value=False)
    it.edit_original_response = AsyncMock()
    it.followup.send = AsyncMock()
    it.guild_id = GUILD
    it.guild = guild()
    it.user = member()
    it.data = {}
    for name, value in changes.items():
        setattr(it, name, value)
    return it


def modern(**parts):
    """A saved new-style record."""
    made = WelcomeEditor(GUILD)
    made.channel_id = CHANNEL
    made.message_content = "Hi {mention}"
    made.embed_data.update({"title": "Welcome to {server}", **parts})
    return made.to_dict()


def old_records(color="#ff0000", title="Hello {user}", image=False):
    """Puts a server's records in the two old lists."""
    db.reference("/Welcome").push().set(
        {"Server ID": 99, "Welcome Channel ID": 1, "Welcome Image Enabled": False}
    )
    db.reference("/Welcome").push().set(
        {
            "Server ID": GUILD,
            "Welcome Channel ID": CHANNEL,
            "Welcome Image Enabled": image,
        }
    )
    db.reference("/Welcome Content").push().set(
        {
            "Server ID": GUILD,
            "Message Content": "Hey {mention}",
            "Title": title,
            "Description": "You are the {count-th}",
            "Color": color,
        }
    )


def with_background(folder):
    """Saves a background for the server."""
    Image.new("RGB", module.CARD_SIZE, "navy").save(f"{folder}/{GUILD}.png")


@pytest.mark.parametrize(
    "n, text",
    [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (12, "12th")]
    + [(13, "13th"), (21, "21st"), (22, "22nd"), (101, "101st"), (111, "111th")],
)
def test_ordinal(n, text):
    assert ordinal(n) == text


def test_script_fills_every_variable():
    text = "{mention} {user} {server} {count} {count-th} {other}"
    assert script(text, member(), guild()) == "<@7> amy Mondstadt 21 21st {other}"


@pytest.mark.parametrize(
    "text, value",
    [("#ff0000", 0xFF0000), ("00008b", 0x8B), ("#FFF", None), ("blue", None)]
    + [("", None), ("#dd one", None), ("+12345", None)],
)
def test_plain_color(text, value):
    assert plain_color(text) == value


async def test_odd_legacy_color_falls_back_to_blurple_when_the_api_fails(monkeypatch):
    monkeypatch.setattr(
        module.aiohttp, "ClientSession", MagicMock(side_effect=OSError("down"))
    )
    assert await legacy_color("blue") == discord.Color.blurple()
    assert "blue" not in module.api_colors
    assert await legacy_color("#00ff00") == discord.Color(0x00FF00)


async def test_join_sends_the_modern_message(firebase):
    db.reference(f"/WelcomeV2/{GUILD}").set(
        modern(
            description="No. {count}",
            fields=[{"name": "A {user}", "value": "B", "inline": True}],
            footer={"text": "bye {user}", "icon_url": ""},
            image="https://img/x.png",
        )
        | {"button_links": [{"label": "Go {user}", "url": "https://x.y", "emoji": ""}]}
    )
    bot = client()
    await OnWelcomeMemberJoin(bot).on_member_join(member())
    sent = bot.channel.send.call_args.kwargs
    assert sent["content"] == "Hi <@7>"
    embed = sent["embed"]
    assert (embed.title, embed.description) == ("Welcome to Mondstadt", "No. 21")
    assert embed.fields[0].name == "A amy" and embed.footer.text == "bye amy"
    assert embed.image.url == "https://img/x.png"
    assert sent["view"].children[0].label == "Go amy"
    assert sent["files"] == []
    bot.log.send.assert_not_called()


async def test_join_with_text_only_sends_no_embed(firebase):
    db.reference(f"/WelcomeV2/{GUILD}").set(modern(title=""))
    bot = client()
    assert await greet(bot, member()) is bot.channel
    sent = bot.channel.send.call_args.kwargs
    assert sent["embed"] is None and sent["view"] is None


@pytest.mark.parametrize(
    "record, why",
    [
        (modern() | {"channel_id": None}, UNSET),
        (modern() | {"channel_id": 51}, GONE),
        (modern(title="") | {"message_content": ""}, UNSET),
        ({"welcome_channel_id": CHANNEL, "embed_data": {}, "updated_at": 1}, UNSET),
    ],
)
async def test_join_sends_nothing_for_an_unusable_record(firebase, record, why):
    db.reference(f"/WelcomeV2/{GUILD}").set(record)
    bot = client()
    assert await greet(bot, member()) == why
    bot.channel.send.assert_not_called()


async def test_join_in_a_server_without_welcomes(firebase):
    db.reference("/Welcome").push().set({"Server ID": 99, "Welcome Channel ID": 1})
    bot = client()
    assert await greet(bot, member()) == OFF
    bot.channel.send.assert_not_called()


async def test_card_is_hosted_in_the_card_channel(firebase, fresh):
    with_background(fresh)
    db.reference(f"/WelcomeV2/{GUILD}").set(
        modern(image="https://img/x.png") | {"welcome_image_enabled": True}
    )
    bot = client()
    await greet(bot, member())
    assert bot.log.send.call_args.args == ("**Guild Name:** Mondstadt",)
    card = bot.log.send.call_args.kwargs["file"]
    assert Image.open(card.fp).size == module.CARD_SIZE
    sent = bot.channel.send.call_args.kwargs
    assert sent["embed"].image.url == "https://cdn/card.png" and sent["files"] == []


async def test_card_is_attached_where_the_card_channel_is_out_of_reach(firebase, fresh):
    with_background(fresh)
    db.reference(f"/WelcomeV2/{GUILD}").set(
        modern(title="") | {"welcome_image_enabled": True}
    )
    bot = client(card_log=False)
    await greet(bot, member())
    sent = bot.channel.send.call_args.kwargs
    assert sent["embed"].image.url == "attachment://welcome.png"
    assert sent["files"][0].filename == "welcome.png"


async def test_card_is_skipped_when_the_background_is_missing(firebase):
    db.reference(f"/WelcomeV2/{GUILD}").set(modern() | {"welcome_image_enabled": True})
    bot = client()
    assert await greet(bot, member()) is bot.channel
    assert bot.channel.send.call_args.kwargs["embed"].image.url is None
    bot.log.send.assert_not_called()


async def test_two_cards_drawn_together_do_not_share_a_file(fresh):
    with_background(fresh)
    amy, ben = member(), member()
    ben.name = "a much longer name"
    one = await module.welcome_card(amy, GUILD)
    two = await module.welcome_card(ben, GUILD)
    assert one.fp.getvalue() != two.fp.getvalue()


async def test_dm_copy_goes_to_new_members_of_the_listed_servers(firebase):
    server = next(iter(module.DM_COPY_SERVERS))
    db.reference(f"/WelcomeV2/{server}").set(modern())
    bot, amy = client(), member(server)
    amy.send.side_effect = discord.Forbidden(MagicMock(status=403), "closed")
    await greet(bot, amy)
    assert amy.send.call_args.kwargs["content"] == "Hi <@7>"
    amy.send.reset_mock()
    await greet(bot, amy, dm=False)
    amy.send.assert_not_called()


async def test_join_sends_the_legacy_message(firebase):
    old_records()
    bot = client()
    assert await greet(bot, member()) is bot.channel
    sent = bot.channel.send.call_args.kwargs
    assert sent["content"] == "Hey <@7>"
    assert sent["embed"].title == "Hello amy"
    assert sent["embed"].description == "You are the 21st"
    assert sent["embed"].color.value == 0xFF0000
    assert sent["files"] == [] and "view" not in sent


async def test_legacy_card_without_an_embed_is_attached(firebase, fresh):
    with_background(fresh)
    old_records(title="", image=True)
    db.reference("/Welcome Content").get()
    key = next(iter(db.reference("/Welcome Content").get()))
    db.reference(f"/Welcome Content/{key}/Description").set("")
    bot = client()
    await greet(bot, member())
    sent = bot.channel.send.call_args.kwargs
    assert sent["embed"] is None and sent["files"][0].filename == "welcome.png"


async def test_legacy_settings_are_read_on_a_machine_that_just_started(
    firebase, monkeypatch
):
    old_records()
    monkeypatch.setattr(module.time, "monotonic", lambda: 5.0)
    bot = client()
    assert await greet(bot, member()) is bot.channel


async def test_legacy_settings_are_read_once_for_many_joins(firebase, monkeypatch):
    old_records()
    reads = []
    real = module.read

    async def counted(path):
        reads.append(path)
        return await real(path)

    monkeypatch.setattr(module, "read", counted)
    for _ in range(3):
        await greet(client(), member(99))
    assert reads.count("/Welcome") == 1


async def test_settings_opens_a_legacy_server_with_its_content(firebase):
    old_records(color="00008b")
    made = await saved_editor(GUILD)
    assert made.channel_id == CHANNEL
    assert made.message_content == "Hey {mention}"
    assert made.embed_data["title"] == "Hello {user}"
    assert made.embed_data["description"] == "You are the {count-th}"
    assert made.embed_data["color"] == 0x8B


async def test_saving_keeps_one_record_per_server_in_the_old_lists(firebase):
    old_records()
    made = await saved_editor(GUILD)
    made.embed_data["title"] = "New"
    await made.save()
    await made.save()
    assert db.reference(f"/WelcomeV2/{GUILD}").get() == made.to_dict()
    settings = db.reference("/Welcome").get()
    assert len(settings) == 2
    assert {
        "Server ID": GUILD,
        "Welcome Channel ID": CHANNEL,
        "Welcome Image Enabled": False,
    } in settings.values()
    content = db.reference("/Welcome Content").get()
    assert list(content.values()) == [
        {
            "Server ID": GUILD,
            "Message Content": "Hey {mention}",
            "Title": "New",
            "Description": "You are the {count-th}",
            "Color": "#ff0000",
        }
    ]


async def test_first_save_adds_the_server_to_the_old_lists(firebase):
    made = WelcomeEditor(GUILD)
    made.channel_id = CHANNEL
    await made.save()
    assert len(db.reference("/Welcome").get()) == 1
    assert len(db.reference("/Welcome Content").get()) == 1


def test_editor_merges_an_older_record_with_the_defaults():
    made = WelcomeEditor(GUILD, {"embed": {"title": "T", "footer": {"text": "f"}}})
    assert made.embed_data["footer"] == {"text": "f", "icon_url": ""}
    assert made.embed_data["fields"] == [] and made.button_links == []


async def test_settings_command_opens_the_editor(firebase):
    db.reference(f"/WelcomeV2/{GUILD}").set(modern())
    it = press()
    it.response.is_done.return_value = True
    await Welcome.welcome_settings.callback(Welcome(client()), it)
    it.response.defer.assert_awaited_once_with(ephemeral=True)
    shown = it.edit_original_response.call_args.kwargs
    assert shown["content"] == "Hi {mention}"
    assert shown["embed"].title == "Welcome to Mondstadt"
    assert isinstance(shown["view"], WelcomeSettingsView)


async def test_settings_command_offers_to_enable(firebase):
    it = press()
    await Welcome.welcome_settings.callback(Welcome(client()), it)
    sent = it.followup.send.call_args.kwargs
    assert sent["embed"].title == "Welcome System"
    assert isinstance(sent["view"], WelcomeEnableView)


async def test_enable_opens_an_empty_editor_and_saves_nothing(firebase):
    it = press()
    view = WelcomeEnableView()
    await view.enable_system.callback(it)
    shown = it.response.edit_message.call_args.kwargs
    assert shown["embed"].title == "Welcome Message Settings"
    assert db.reference(f"/WelcomeV2/{GUILD}").get() is None


async def test_selecting_a_channel_saves_and_redraws_once(firebase):
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    it = press(data={"values": [str(CHANNEL)]})
    it.response.defer.side_effect = lambda **_: it.response.is_done.configure_mock(
        return_value=True
    )
    await view.select_channel(it)
    assert db.reference(f"/WelcomeV2/{GUILD}/channel_id").get() == CHANNEL
    it.edit_original_response.assert_awaited_once()
    it.response.edit_message.assert_not_called()


async def test_toggle_image_needs_a_background(firebase, fresh):
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    it = press()
    await view.toggle_image.callback(it)
    assert (
        "No custom background image found" in it.response.send_message.call_args[0][0]
    )
    assert not view.editor.welcome_image_enabled
    with_background(fresh)
    it = press()
    await view.toggle_image.callback(it)
    assert view.editor.welcome_image_enabled
    assert view.toggle_image.label == "Disable Custom Image"
    assert view.toggle_image.style == discord.ButtonStyle.danger


async def test_disable_removes_only_this_server(firebase):
    old_records()
    db.reference(f"/WelcomeV2/{GUILD}").set(modern())
    db.reference("/WelcomeV2/99").set(modern())
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    it = press()
    await view.disable_system.callback(it)
    assert db.reference(f"/WelcomeV2/{GUILD}").get() is None
    assert db.reference("/WelcomeV2/99").get()
    left = list(db.reference("/Welcome").get().values())
    assert [record["Server ID"] for record in left] == [99]
    assert not db.reference("/Welcome Content").get()
    shown = it.edit_original_response.call_args.kwargs
    assert shown["embed"].title == "Welcome System Disabled" and shown["view"] is None
    assert await greet(client(), member()) == OFF


async def test_embed_modal_saves_and_ignores_a_bad_color(firebase):
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    modal = WelcomeEmbedModal(view)
    for child, value in zip(modal.children, ["T", "D", "red", "F", "A"]):
        child._value = value
    it = press()
    it.response.is_done.return_value = True
    await modal.on_submit(it)
    saved = db.reference(f"/WelcomeV2/{GUILD}/embed").get()
    assert (saved["title"], saved["description"]) == ("T", "D")
    assert saved["color"] == discord.Color.blurple().value
    assert saved["footer"]["text"] == "F" and saved["author"]["name"] == "A"
    it.response.defer.assert_awaited_once()
    assert it.edit_original_response.call_args.kwargs["embed"].title == "T"
    modal.children[2]._value = "#00ff00"
    await modal.on_submit(press())
    assert db.reference(f"/WelcomeV2/{GUILD}/embed/color").get() == 0x00FF00


async def test_a_modal_that_is_not_submitted_saves_nothing(firebase):
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    it = press()
    await view.edit_embed.callback(it)
    assert isinstance(it.response.send_modal.call_args.args[0], WelcomeEmbedModal)
    assert db.reference(f"/WelcomeV2/{GUILD}").get() is None


async def test_fields_screen_adds_edits_and_removes(firebase):
    view = WelcomeFieldsEditorView(WelcomeEditor(GUILD), guild())
    assert view.select not in view.children
    it = press()
    await view.edit.callback(it)
    assert it.response.send_message.call_args.args[0] == "Please select a field first!"
    modal = WelcomeFieldModal(view)
    for child, value in zip(modal.children, ["Name", "Value", "n"]):
        child._value = value
    await modal.on_submit(press())
    fields = view.editor.embed_data["fields"]
    assert fields == [{"name": "Name", "value": "Value", "inline": False}]
    assert view.select in view.children and view.select.options[0].label == "Name"
    await view.pick(press(data={"values": ["0"]}))
    it = press()
    await view.edit.callback(it)
    assert it.response.send_modal.call_args.args[0].children[0].default == "Name"
    await view.remove.callback(press())
    assert fields == [] and view.selected_index is None
    assert not db.reference(f"/WelcomeV2/{GUILD}/embed").get().get("fields")


async def test_links_screen_previews_the_buttons(firebase):
    made = WelcomeEditor(GUILD)
    view = WelcomeButtonLinksEditorView(made, guild())
    assert view.add.label == "Add Link" and view.remove.label == "Remove Link"
    modal = WelcomeButtonLinkModal(view)
    for child, value in zip(modal.children, ["Site", "https://x.y", "not an emoji"]):
        child._value = value
    it = press()
    await modal.on_submit(it)
    it.followup.send.assert_not_called()
    assert made.button_links == [
        {"label": "Site", "url": "https://x.y", "emoji": "not an emoji"}
    ]
    it = press(data={"values": ["0"]})
    await view.pick(it)
    assert it.followup.send.call_args.args == ("**Button Preview:**",)
    assert it.followup.send.call_args.kwargs["view"].children[0].url == "https://x.y"


async def test_back_returns_to_the_first_screen(firebase):
    view = WelcomeFieldsEditorView(WelcomeEditor(GUILD), guild())
    it = press()
    await view.go_back.callback(it)
    shown = it.response.edit_message.call_args.kwargs["view"]
    assert isinstance(shown, WelcomeSettingsView) and shown.editor is view.editor


async def test_upload_refuses_a_file_that_is_not_an_image(firebase):
    it = press()
    await Welcome.welcome_upload.callback(
        Welcome(client()), it, SimpleNamespace(content_type=None)
    )
    assert "valid image file" in it.response.send_message.call_args.args[0]


async def test_upload_crops_dims_and_turns_the_card_on(firebase, fresh):
    db.reference(f"/WelcomeV2/{GUILD}").set(modern())
    raw = io.BytesIO()
    Image.new("RGB", (2000, 500), (200, 100, 50)).save(raw, "PNG")
    upload = SimpleNamespace(
        content_type="image/png", read=AsyncMock(return_value=raw.getvalue())
    )
    it = press()
    await Welcome.welcome_upload.callback(Welcome(client()), it, upload)
    saved = Image.open(f"{fresh}/{GUILD}.png")
    assert saved.size == module.CARD_SIZE
    assert saved.convert("RGB").getpixel((5, 5)) == (120, 60, 30)
    assert db.reference(f"/WelcomeV2/{GUILD}/welcome_image_enabled").get() is True
    assert "Background Uploaded!" in it.followup.send.call_args.kwargs["embed"].title


async def test_sample_reports_each_outcome(firebase):
    cog, it = Welcome(client()), press()
    await Welcome.welcome_sample.callback(cog, it)
    embed = it.followup.send.call_args.kwargs["embed"]
    assert embed.title == "Welcome message not enabled!"
    db.reference(f"/WelcomeV2/{GUILD}").set(modern() | {"channel_id": None})
    await Welcome.welcome_sample.callback(cog, it)
    assert "not properly configured" in it.followup.send.call_args.args[0]
    db.reference(f"/WelcomeV2/{GUILD}").set(modern() | {"channel_id": 51})
    await Welcome.welcome_sample.callback(cog, it)
    assert "Welcome channel not found" in it.followup.send.call_args.args[0]
    db.reference(f"/WelcomeV2/{GUILD}").set(modern())
    await Welcome.welcome_sample.callback(cog, it)
    done = it.followup.send.call_args.kwargs["embed"].description
    assert done == f"{module.YES} Sample message sent to <#50>"
    assert cog.bot.channel.send.call_args.kwargs["content"] == "Hi <@7>"


async def test_upload_changes_only_the_flag(firebase, fresh):
    odd = {"embed_data": {"title": "T"}, "updated_at": 1, "welcome_channel_id": 50}
    db.reference(f"/WelcomeV2/{GUILD}").set(dict(odd))
    old_records()
    before = (db.reference("/Welcome").get(), db.reference("/Welcome Content").get())
    raw = io.BytesIO()
    Image.new("RGB", (64, 64)).save(raw, "PNG")
    upload = SimpleNamespace(
        content_type="image/png", read=AsyncMock(return_value=raw.getvalue())
    )
    await Welcome.welcome_upload.callback(Welcome(client()), press(), upload)
    saved = db.reference(f"/WelcomeV2/{GUILD}").get()
    assert saved == odd | {"welcome_image_enabled": True}
    after = (db.reference("/Welcome").get(), db.reference("/Welcome Content").get())
    assert after == before
    assert not [name for name in os.listdir(fresh) if name.endswith(".tmp")]


async def test_upload_without_a_message_creates_no_record(firebase):
    raw = io.BytesIO()
    Image.new("RGB", (64, 64)).save(raw, "PNG")
    upload = SimpleNamespace(
        content_type="image/png", read=AsyncMock(return_value=raw.getvalue())
    )
    await Welcome.welcome_upload.callback(Welcome(client()), press(), upload)
    assert db.reference("/WelcomeV2").get() is None


async def test_two_first_saves_at_once_leave_one_record_per_list(firebase):
    first, second = WelcomeEditor(GUILD), WelcomeEditor(GUILD)
    first.channel_id = second.channel_id = CHANNEL
    await asyncio.gather(first.save(), second.save())
    assert len(db.reference("/Welcome").get()) == 1
    assert len(db.reference("/Welcome Content").get()) == 1


async def test_disable_removes_duplicate_old_records(firebase):
    for path in ("/Welcome", "/Welcome Content"):
        for key in ("a", "b"):
            db.reference(f"{path}/{key}").set({"Server ID": GUILD})
        db.reference(f"{path}/c").set({"Server ID": 99})
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    await view.disable_system.callback(press())
    assert list(db.reference("/Welcome").get()) == ["c"]
    assert list(db.reference("/Welcome Content").get()) == ["c"]


async def test_disable_alongside_a_save_leaves_no_orphan(firebase):
    made = WelcomeEditor(GUILD)
    made.channel_id = CHANNEL
    view = WelcomeSettingsView(WelcomeEditor(GUILD), guild())
    await asyncio.gather(made.save(), view.disable_system.callback(press()))
    assert not db.reference("/Welcome").get()
    assert not db.reference("/Welcome Content").get()
    assert db.reference(f"/WelcomeV2/{GUILD}").get() is None


def test_editor_survives_unknown_embed_shapes():
    made = WelcomeEditor(
        GUILD, {"embed": {"odd": {"a": 1}, "title": "T"}, "button_links": None}
    )
    assert made.embed_data["title"] == "T" and "odd" not in made.embed_data
    assert made.button_links == []


async def test_old_settings_without_content_give_no_greeting(firebase):
    db.reference("/Welcome/a").set({"Server ID": GUILD, "Welcome Channel ID": CHANNEL})
    assert await greet(client(), member()) == OFF


@pytest.mark.parametrize("kind", ["P", "CMYK"])
def test_background_accepts_palette_and_print_images(fresh, kind):
    raw = io.BytesIO()
    picture = Image.new("RGB", (400, 300), (200, 100, 50)).convert(kind)
    picture.save(raw, "PNG" if kind == "P" else "JPEG")
    module.save_background(raw.getvalue(), f"{fresh}/9.png")
    saved = Image.open(f"{fresh}/9.png")
    assert saved.size == module.CARD_SIZE and saved.mode == "RGB"
    assert os.listdir(fresh).count("9.png") == 1
    assert not [name for name in os.listdir(fresh) if name.endswith(".tmp")]
