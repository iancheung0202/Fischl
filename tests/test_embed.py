"""The embed editor under shared/Utility: its screens, templates, posting and editing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands

from shared.Utility import embed as module
from shared.Utility.embed import (
    ButtonLinkModal,
    ButtonLinksEditorView,
    EmbedEditor,
    EmbedMainView,
    EmbedModal,
    FieldModal,
    FieldsEditorView,
    MediaModal,
    PostEmbedView,
    SaveModal,
    StartView,
    TemplateSelectView,
)

GUILD = 5
AMY = 7
BEN = 8


def press(**changes):
    """An interaction by Amy in the server."""
    it = MagicMock()
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.response.send_modal = AsyncMock()
    it.response.defer = AsyncMock()
    it.edit_original_response = AsyncMock()
    it.followup.send = AsyncMock()
    it.guild_id = GUILD
    it.user = SimpleNamespace(id=AMY)
    it.client.emojis = []
    it.client.get_user = lambda user_id: f"user{user_id}"
    it.data = {}
    for name, value in changes.items():
        setattr(it, name, value)
    return it


def said(it) -> str:
    """Gives the text of the last answer to an interaction."""
    call = it.response.send_message.call_args
    return call.args[0] if call.args else call.kwargs["content"]


def editor(**parts) -> EmbedEditor:
    """An editor of Amy's with a title, plus the given embed parts."""
    made = EmbedEditor(AMY, GUILD)
    made.embed_data.update({"title": "Hello", **parts})
    return made


def typed(modal, *values):
    """Fills a modal's boxes as if the member typed the values."""
    for box, value in zip(modal.children, values):
        box._value = value
    return modal


@pytest.fixture
def modals(monkeypatch):
    """Makes every modal answer at once."""
    monkeypatch.setattr(discord.ui.Modal, "wait", AsyncMock())


def labels(view):
    """Gives the labels of a view's buttons."""
    return [c.label for c in view.children if isinstance(c, discord.ui.Button)]


def test_an_editor_with_no_content_gives_no_embed_but_a_hint_to_preview():
    blank = EmbedEditor(AMY, GUILD)
    assert blank.is_empty() and blank.to_embed() is None
    assert blank.preview().title == "No Content Yet"
    blank.embed_data["footer"]["text"] = "foot"
    assert not blank.is_empty() and blank.preview().footer.text == "foot"


def test_an_editor_draws_every_part_and_survives_a_round_trip_as_a_template():
    full = editor(
        description="text",
        color=0x123456,
        footer={"text": "foot", "icon_url": "https://f"},
        author={"name": "me", "icon_url": ""},
        thumbnail="https://t",
        image="https://i",
        fields=[{"name": "a", "value": "b", "inline": False}],
        timestamp=True,
    )
    full.button_links = [{"label": "go", "url": "https://x", "emoji": ""}]
    full.message_content = "hi"
    drawn = full.to_embed()
    assert (drawn.title, drawn.description, drawn.color.value) == (
        "Hello",
        "text",
        0x123456,
    )
    assert (drawn.footer.text, drawn.footer.icon_url) == ("foot", "https://f")
    assert (drawn.author.name, drawn.author.icon_url) == ("me", None)
    assert (drawn.thumbnail.url, drawn.image.url) == ("https://t", "https://i")
    assert drawn.fields[0].inline is False and drawn.timestamp is not None
    saved = full.to_dict()
    assert saved["template_owner"] == AMY and set(saved) == {
        "message_content",
        "embed_data",
        "button_links",
        "template_owner",
    }
    again = EmbedEditor.from_dict(BEN, GUILD, saved, template_id="abc")
    assert again.to_dict() == saved and again.template_id == "abc"
    assert again.user_id == BEN and again.template_owner == AMY


def test_a_template_missing_parts_keeps_the_defaults():
    part = {"embed_data": {"title": "T", "footer": {"text": "f"}}}
    made = EmbedEditor.from_dict(AMY, GUILD, part)
    assert made.embed_data["footer"] == {"text": "f", "icon_url": ""}
    assert made.embed_data["fields"] == [] and made.button_links == []
    assert made.template_owner is None and made.message_content == ""


def test_an_editor_read_from_a_message_edits_that_message():
    drawn = editor(
        description="d", fields=[{"name": "a", "value": "b", "inline": True}]
    )
    message = SimpleNamespace(content="hi", embeds=[drawn.to_embed()])
    made = EmbedEditor.from_embed(AMY, GUILD, message)
    assert made.edit_mode and made.message_to_edit is message
    assert made.message_content == "hi"
    assert made.embed_data == drawn.embed_data
    bare = EmbedEditor.from_embed(AMY, GUILD, SimpleNamespace(content=None, embeds=[]))
    assert bare.is_empty() and bare.message_content == ""


async def test_the_embed_modal_keeps_texts_and_only_a_readable_colour():
    made = editor(color=1)
    modal = EmbedModal(made)
    assert [c.label for c in modal.children] == [
        "Title",
        "Description",
        "Color (Hex)",
        "Footer Text",
        "Author Name",
    ]
    assert modal.children[2].default == "#000001"
    for color, kept in (("#ff0000", 0xFF0000), ("red", 0xFF0000), ("#zz", 0xFF0000)):
        it = press()
        await typed(modal, "T", "D", color, "F", "A").on_submit(it)
        assert made.embed_data["color"] == kept
        it.response.defer.assert_awaited_once()
    data = made.embed_data
    assert (data["title"], data["description"]) == ("T", "D")
    assert (data["footer"]["text"], data["author"]["name"]) == ("F", "A")


async def test_the_media_modal_keeps_the_four_links():
    made = editor()
    await typed(MediaModal(made), "i", "t", "a", "f").on_submit(press())
    data = made.embed_data
    assert (data["image"], data["thumbnail"]) == ("i", "t")
    assert (data["author"]["icon_url"], data["footer"]["icon_url"]) == ("a", "f")


async def test_field_and_link_modals_add_or_replace_an_entry():
    made = editor()
    assert FieldModal(made).title == "Add Field"
    await typed(FieldModal(made), "n", "v", "y").on_submit(press())
    await typed(FieldModal(made), "n2", "v2", "x").on_submit(press())
    edit = FieldModal(made, 0)
    assert edit.title == "Edit Field" and edit.children[2].default == "Y"
    await typed(edit, "new", "v", "N").on_submit(press())
    assert made.embed_data["fields"] == [
        {"name": "new", "value": "v", "inline": False},
        {"name": "n2", "value": "v2", "inline": False},
    ]
    await typed(ButtonLinkModal(made), "go", "https://x", "").on_submit(press())
    edit = ButtonLinkModal(made, 0)
    assert edit.title == "Edit Link" and edit.children[1].default == "https://x"
    await typed(edit, "went", "https://y", "😀").on_submit(press())
    assert made.button_links == [{"label": "went", "url": "https://y", "emoji": "😀"}]


async def test_saving_a_template_stores_it_under_the_server(firebase):
    it = press()
    await typed(SaveModal(editor()), "Rules").on_submit(it)
    ((template_id, saved),) = firebase(f"Embed Templates/{GUILD}").get().items()
    assert len(template_id) == 8 and f"(ID: `{template_id}`)" in said(it)
    assert "Template saved as **Rules**" in said(it)
    assert saved["name"] == "Rules" and saved["template_owner"] == AMY
    assert saved["embed_data"]["title"] == "Hello" and "created_at" in saved
    assert SaveModal(editor(), is_save_as=True).title == "Save As New Template"


@pytest.mark.parametrize(
    "owners, refusal",
    [
        ([BEN] * 25, "Server template limit reached (25). Cannot save new template."),
        ([AMY] * 4, "User template limit reached (4). Cannot save new template."),
    ],
)
async def test_saving_stops_at_the_template_limits(firebase, owners, refusal):
    ref = firebase(f"Embed Templates/{GUILD}")
    ref.set({f"t{i}": {"template_owner": o} for i, o in enumerate(owners)})
    it = press()
    await typed(SaveModal(editor()), "Rules").on_submit(it)
    assert said(it) == refusal and len(ref.get()) == len(owners)


async def test_the_first_screen_changes_with_edit_mode_and_template_ownership():
    plain = EmbedMainView(editor(), press())
    assert labels(plain) == [
        "Embed",
        "Media",
        "Fields",
        "Button Links",
        "Save",
        "Save As",
        "Post",
    ]
    assert plain.timeout == 3600
    mine = editor()
    mine.edit_mode, mine.template_id, mine.template_owner = True, "abc", AMY
    assert labels(EmbedMainView(mine, press()))[-2:] == ["Update", "Delete Template"]
    mine.template_owner = BEN
    assert "Delete Template" not in labels(EmbedMainView(mine, press()))


async def test_the_first_screen_asks_with_a_modal_and_redraws(modals):
    start = press()
    view = EmbedMainView(editor(), start)
    it = press()
    await view.edit_embed.callback(it)
    assert isinstance(it.response.send_modal.call_args.args[0], EmbedModal)
    shown = start.edit_original_response.call_args.kwargs
    assert shown["view"] is view and shown["embed"].title == "Hello"
    assert shown["content"] is None
    await view.edit_media.callback(it)
    assert isinstance(it.response.send_modal.call_args.args[0], MediaModal)
    for button, screen in (
        (view.edit_fields, FieldsEditorView),
        (view.edit_links, ButtonLinksEditorView),
        (view.save_and_post, PostEmbedView),
    ):
        it = press()
        await button.callback(it)
        opened = it.response.edit_message.call_args.kwargs["view"]
        assert type(opened) is screen and opened.original_interaction is start


async def test_save_updates_an_own_template_and_asks_a_name_otherwise(firebase):
    mine = editor()
    view = EmbedMainView(mine, press())
    it = press()
    await view.save_template.callback(it)
    assert isinstance(it.response.send_modal.call_args.args[0], SaveModal)
    await view.save_as_template.callback(it)
    assert it.response.send_modal.call_args.args[0].title == "Save As New Template"
    ref = firebase(f"Embed Templates/{GUILD}/abc")
    ref.set({"name": "Rules", "created_at": "then", "template_owner": AMY})
    mine.template_id, mine.template_owner = "abc", AMY
    it = press()
    await view.save_template.callback(it)
    saved = ref.get()
    assert saved["name"] == "Rules" and saved["created_at"] == "then"
    assert saved["embed_data"]["title"] == "Hello" and "updated_at" in saved
    assert said(it).endswith("Template (ID: `abc`) updated!")
    mine.template_owner = BEN
    it = press()
    await view.save_template.callback(it)
    it.response.send_modal.assert_awaited_once()


async def test_deleting_a_template_keeps_the_editor_open(firebase):
    firebase(f"Embed Templates/{GUILD}").set(
        {"abc": {"name": "a"}, "def": {"name": "b"}}
    )
    mine = editor()
    mine.template_id, mine.template_owner = "abc", AMY
    start, it = press(), press()
    view = EmbedMainView(mine, start)
    await view.children[-1].callback(it)
    assert list(firebase(f"Embed Templates/{GUILD}").get()) == ["def"]
    assert mine.template_id is None and mine.template_owner is None
    assert "Delete Template" not in labels(view)
    assert said(it).endswith("Template deleted successfully!")
    assert start.edit_original_response.call_args.kwargs["view"] is view


async def test_update_writes_the_message_and_its_link_buttons():
    message = SimpleNamespace(edit=AsyncMock(), jump_url="https://jump")
    mine = editor()
    mine.edit_mode, mine.message_to_edit, mine.message_content = True, message, ""
    it = press()
    await EmbedMainView(mine, press()).save_and_post.callback(it)
    sent = message.edit.call_args.kwargs
    assert sent["content"] is None and sent["embed"].title == "Hello"
    message.edit.assert_awaited_once()
    assert said(it).endswith(
        "Embed updated successfully! [Jump to Message](https://jump)"
    )
    party = SimpleNamespace(name="party", id=3)
    mine.button_links = [
        {"label": "a", "url": "https://a", "emoji": ""},
        {"label": "b", "url": "https://b", "emoji": "😀"},
    ]
    it = press()
    it.client.emojis = [party]
    await EmbedMainView(mine, press()).save_and_post.callback(it)
    buttons = message.edit.call_args.kwargs["view"].children
    assert [(b.label, b.url, b.emoji and b.emoji.name) for b in buttons] == [
        ("a", "https://a", None),
        ("b", "https://b", "😀"),
    ]
    message.edit = AsyncMock(side_effect=RuntimeError("gone"))
    it = press()
    await EmbedMainView(mine, press()).save_and_post.callback(it)
    assert said(it).endswith("Failed to update message: gone")


FIELDS = [{"name": n, "value": n * 2, "inline": True} for n in "abc"]


def menu(view):
    """Gives a list screen's menu as (label, description, default) per option."""
    (select,) = [c for c in view.children if isinstance(c, discord.ui.Select)]
    return [(o.label, o.description, o.default) for o in select.options]


async def test_the_fields_screen_selects_moves_and_removes(modals):
    made = editor(fields=[dict(f) for f in FIELDS])
    start = press()
    view = FieldsEditorView(made, start)
    assert labels(view) == [
        "Add Field",
        "Edit Field",
        "Remove Field",
        "Move Up",
        "Move Down",
        "Back",
    ]
    assert menu(view) == [("a", "aa", True), ("b", "bb", False), ("c", "cc", False)]
    names = lambda: "".join(f["name"] for f in made.embed_data["fields"])

    it = press()
    await view.move_up.callback(it)
    assert said(it).endswith("Cannot move up!") and names() == "abc"
    await view.move_down.callback(press())
    assert names() == "bac" and view.selected_index == 1
    await view.select(press(data={"values": ["2"]}))
    it = press()
    await view.move_down.callback(it)
    assert said(it).endswith("Cannot move down!")
    await view.move_up.callback(it)
    assert names() == "bca" and menu(view)[1] == ("c", "cc", True)
    assert it.response.edit_message.call_args.kwargs["view"] is view

    await view.select(press(data={"values": ["2"]}))
    await view.remove.callback(press())
    assert names() == "bc" and view.selected_index == 1
    await view.remove.callback(press())
    await view.remove.callback(press())
    assert names() == "" and view.selected_index is None
    assert not any(isinstance(c, discord.ui.Select) for c in view.children)
    for button, text in (
        (view.edit, "No field selected!"),
        (view.remove, "No field selected!"),
        (view.move_up, "Cannot move up!"),
        (view.move_down, "Cannot move down!"),
    ):
        it = press()
        await button.callback(it)
        assert said(it).endswith(text)

    made.embed_data["fields"].extend(dict(f) for f in FIELDS[:2])
    it = press()
    await view.add.callback(it)
    assert it.response.send_modal.call_args.args[0].title == "Add Field"
    assert view.selected_index == 1 and menu(view)[1][2]
    await view.edit.callback(it)
    assert it.response.send_modal.call_args.args[0].title == "Edit Field"
    assert start.edit_original_response.await_count == 2
    await view.go_back.callback(it)
    assert type(it.response.edit_message.call_args.kwargs["view"]) is EmbedMainView


async def test_an_unnamed_field_or_link_gets_a_numbered_label():
    made = editor(fields=[{"name": "", "value": "", "inline": True}])
    made.button_links = [{"label": "", "url": "https://x", "emoji": ""}]
    assert menu(FieldsEditorView(made, press())) == [("Field 1", "No content", True)]
    assert menu(ButtonLinksEditorView(made, press())) == [("Link 1", "https://x", True)]


async def test_the_links_screen_sends_a_preview_of_the_buttons(modals):
    made = editor()
    made.button_links = [
        {"label": "a", "url": "https://a", "emoji": "<:party:1036811164891480194>"},
        {"label": "b", "url": "https://b", "emoji": ""},
    ]
    start = press()
    view = ButtonLinksEditorView(made, start)
    assert labels(view)[:3] == ["Add Link", "Edit Link", "Remove Link"]
    it = press()
    await view.move_down.callback(it)
    args, kwargs = it.followup.send.call_args
    assert args == ("**Button Preview:**",) and kwargs["ephemeral"] is True
    shown = [(b.label, b.emoji and b.emoji.id) for b in kwargs["view"].children]
    assert shown == [("b", None), ("a", 1036811164891480194)]

    it = press()
    await view.add.callback(it)
    it.followup.send.assert_not_awaited()
    start.followup.send.assert_awaited_once()
    await view.edit.callback(it)
    assert start.followup.send.await_count == 2

    for _ in range(2):
        it = press()
        await view.remove.callback(it)
    it.followup.send.assert_not_awaited()
    it = press()
    await view.remove.callback(it)
    assert said(it).endswith("No link selected!")


def channel(channel_id=30):
    """A channel the bot can post in."""
    return SimpleNamespace(
        id=channel_id,
        mention=f"<#{channel_id}>",
        send=AsyncMock(),
        create_webhook=AsyncMock(),
    )


async def test_posting_needs_a_channel_and_then_sends_the_embed():
    made = editor()
    made.message_content = "hi"
    start = press()
    view = PostEmbedView(made, start)
    assert view.timeout == 1800
    await view.update_message(start)
    shown = start.response.edit_message.call_args.kwargs
    assert shown["content"] == module.POST_PROMPT and shown["embed"].title == "Hello"

    it = press()
    await view.post_embed.callback(it)
    assert said(it).endswith("Please select a channel first!")

    view.selected_channel = SimpleNamespace(id=30)
    it = press()
    it.guild.get_channel = lambda channel_id: None
    await view.post_embed.callback(it)
    assert said(it).endswith("Channel not found!")

    room = channel()
    it.guild.get_channel = lambda channel_id: room
    await view.post_embed.callback(it)
    sent = room.send.call_args.kwargs
    assert sent["content"] == "hi" and sent["view"] is None
    assert sent["embed"].title == "Hello"
    assert said(it).endswith("Embed posted in <#30>!")
    back = start.edit_original_response.call_args.kwargs
    assert type(back["view"]) is EmbedMainView and back["content"] is None


async def test_posting_sends_link_buttons_and_reports_failures():
    made = editor()
    made.button_links = [{"label": "a", "url": "https://a", "emoji": "not an emoji"}]
    view = PostEmbedView(made, press())
    view.selected_channel = room = channel()
    await view.post_embed.callback(press())
    (button,) = room.send.call_args.kwargs["view"].children
    assert (button.label, button.url) == ("a", "https://a")
    assert room.send.call_args.kwargs["content"] is None

    for error, text in (
        (discord.Forbidden(MagicMock(status=403), "no"), "I don't have permission"),
        (RuntimeError("boom"), "Error posting embed: boom"),
    ):
        room.send = AsyncMock(side_effect=error)
        it = press()
        await view.post_embed.callback(it)
        assert text in said(it)
        it.response.send_message.assert_awaited_once()


async def test_posting_through_a_webhook_uses_the_given_name(modals):
    made = editor()
    view = PostEmbedView(made, press())
    view.selected_channel = room = channel()
    it = press()
    await view.toggle_webhook.callback(it)
    assert it.followup.send.call_args.args[0].endswith("Webhook settings saved!")
    await view.post_embed.callback(press())
    room.send.assert_awaited_once()

    view.webhook_data = {"username": "Paimon", "avatar_url": ""}
    await view.post_embed.callback(press())
    room.create_webhook.assert_awaited_once_with(name="Embed Bot")
    hook = room.create_webhook.return_value
    sent = hook.send.call_args.kwargs
    assert sent["username"] == "Paimon" and sent["avatar_url"] is None
    hook.delete.assert_awaited_once()
    room.send.assert_awaited_once()


async def test_the_owner_posting_in_the_ping_channel_pings_the_roles():
    made = editor()
    made.message_content = "hi"
    view = PostEmbedView(made, press())
    view.selected_channel = room = channel(module.PING_CHANNEL)
    await view.post_embed.callback(press())
    assert room.send.call_args.kwargs["content"] == "hi"
    await view.post_embed.callback(press(user=SimpleNamespace(id=module.PING_AUTHOR)))
    assert room.send.call_args.kwargs["content"] == module.PING_CONTENT


async def test_the_template_menu_names_each_owner_and_opens_the_pick(firebase):
    bot = MagicMock()
    bot.get_user = lambda user_id: None
    bot.fetch_user = AsyncMock(side_effect=lambda user_id: f"user{user_id}")
    view = TemplateSelectView(AMY, GUILD)
    await view.load_templates(bot)
    (select,) = view.children
    assert select.disabled and select.placeholder == "No templates available"

    firebase(f"Embed Templates/{GUILD}").set(
        {
            "a": {"name": "Mine", "template_owner": AMY},
            "b": {"name": "Theirs", "template_owner": BEN},
            "c": {"template_owner": BEN},
            "d": {"name": "Nobody's"},
            "e": {"name": "Left", "template_owner": 99},
        }
    )
    bot.fetch_user = AsyncMock(
        side_effect=lambda user_id: 1 / 0 if user_id == 99 else f"user{user_id}"
    )
    view = TemplateSelectView(AMY, GUILD, target_message="message")
    await view.load_templates(bot)
    (select,) = view.children
    assert select.placeholder == "Choose a template..." and view.timeout == 60
    assert [(o.label, o.value, o.description) for o in select.options] == [
        ("Mine (Yours)", "a", "Your template"),
        ("Theirs ", "b", "By user8"),
        ("Unnamed Template ", "c", "By user8"),
        ("Nobody's ", "d", "By Unknown"),
        ("Left ", "e", "By Unknown"),
    ]
    assert bot.fetch_user.await_count == 2

    it = press(data={"values": ["b"]})
    await select.callback(it)
    opened = it.response.edit_message.call_args.kwargs["view"]
    made = opened.editor
    assert (made.template_id, made.template_owner, made.user_id) == ("b", BEN, AMY)
    assert made.edit_mode and made.message_to_edit == "message"
    assert opened.original_interaction is it


async def test_the_start_offers_blank_or_template(firebase):
    it = press()
    await module.start(it)
    sent = it.response.send_message.call_args.kwargs
    view, shown = sent["view"], sent["embed"]
    assert sent["ephemeral"] is True and shown.title == "Embed Editor"
    assert shown.description.endswith(
        "- **Create from Template** - Use a saved template (0 total in server, 0 yours)"
    )
    assert labels(view) == ["Create New Blank Embed", "Create from Template"]
    assert view.from_template.disabled and view.timeout == 60
    await view.fresh.callback(it)
    opened = it.response.edit_message.call_args.kwargs
    assert opened["embed"].title == "No Content Yet"
    assert not opened["view"].editor.edit_mode

    firebase(f"Embed Templates/{GUILD}").set(
        {"a": {"template_owner": AMY}, "b": {"template_owner": BEN}}
    )
    message = SimpleNamespace(content="hi", embeds=[])
    it = press()
    await module.start(it, message)
    sent = it.response.send_message.call_args.kwargs
    view, shown = sent["view"], sent["embed"]
    assert shown.title == "Edit Embed" and shown.description.endswith(
        "replace the message content (2 total in server, 1 yours)"
    )
    assert labels(view) == ["Load from Existing Content", "Load from Template"]
    assert not view.from_template.disabled
    await view.fresh.callback(it)
    assert it.response.edit_message.call_args.kwargs["view"].editor.message_to_edit is (
        message
    )
    await view.from_template.callback(it)
    opened = it.response.edit_message.call_args.kwargs
    assert opened["embed"].title == "Choose a Template"
    assert opened["embed"].description == module.EDIT_TEMPLATE_HINT
    assert opened["view"].target_message is message
    assert len(opened["view"].children[0].options) == 2


async def test_the_start_still_opens_when_templates_cannot_be_read(monkeypatch):
    monkeypatch.setattr(module, "templates_ref", lambda *a: 1 / 0)
    it = press()
    await module.start(it)
    shown = it.response.send_message.call_args.kwargs["embed"]
    assert "(0 total in server, 0 yours)" in shown.description


async def test_the_commands_open_the_start_and_report_errors(firebase):
    cog = module.EmbedCommand(MagicMock())
    assert [c.name for c in cog.walk_app_commands()] == ["embed", "editembed"]
    it = press()
    await cog.embed.callback(cog, it)
    assert it.response.send_message.call_args.kwargs["embed"].title == "Embed Editor"

    message = SimpleNamespace(content="", embeds=[])
    room = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    thread = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    it = press()
    await cog.editembed.callback(cog, it, "30-123", room)
    room.fetch_message.assert_awaited_once_with(123)
    assert it.response.send_message.call_args.kwargs["view"].target_message is message
    await cog.editembed.callback(cog, press(), "456", room, thread)
    thread.fetch_message.assert_awaited_once_with(456)

    for error, text in (
        (app_commands.MissingPermissions(["administrator"]), "You need administrator"),
        (RuntimeError("boom"), "An error occurred: boom"),
    ):
        it = press()
        await cog.on_error(it, error)
        assert text in said(it)


async def test_the_message_menu_only_edits_the_bots_own_messages(firebase):
    menu_entry = module.edit_embed_context_menu
    assert menu_entry.name == "Edit Embed"
    it = press()
    theirs = SimpleNamespace(author="someone", content="", embeds=[])
    await menu_entry.callback(it, theirs)
    assert said(it) == "❌ You can only edit messages sent by this bot!"
    ours = SimpleNamespace(author=it.client.user, content="", embeds=[])
    it.response.send_message.reset_mock()
    await menu_entry.callback(it, ours)
    assert it.response.send_message.call_args.kwargs["embed"].title == "Edit Embed"


async def test_setup_adds_the_cog_and_the_message_menu():
    bot = MagicMock()
    bot.add_cog = AsyncMock()
    await module.setup(bot)
    assert isinstance(bot.add_cog.call_args.args[0], module.EmbedCommand)
    bot.tree.add_command.assert_called_once_with(module.edit_embed_context_menu)


async def test_templates_are_read_and_written_off_the_event_loop(firebase, monkeypatch):
    threads = []

    async def in_thread(function, *args):
        threads.append(function.__name__)
        return function(*args)

    monkeypatch.setattr(module.asyncio, "to_thread", in_thread)
    monkeypatch.setattr(module.db, "reference", lambda path: 1 / 0)
    monkeypatch.setattr(
        module,
        "templates_ref",
        lambda *path: firebase("/".join(map(str, ("Embed Templates", *path)))),
    )
    mine = editor()
    await typed(SaveModal(mine), "Rules").on_submit(press())
    (mine.template_id,) = firebase(f"Embed Templates/{GUILD}").get()
    mine.template_owner = AMY
    view = EmbedMainView(mine, press())
    await view.save_template.callback(press())
    await TemplateSelectView(AMY, GUILD).load_templates(MagicMock())
    await module.start(press())
    await view.children[-1].callback(press())
    assert threads == ["get", "set", "update", "get", "get", "delete"]


def test_a_saved_record_does_not_share_the_editors_lists():
    mine = editor(fields=[{"name": "a", "value": "b", "inline": True}])
    saved = mine.to_dict()
    mine.embed_data["fields"][0]["name"] = "changed"
    mine.button_links.append({"label": "x", "url": "https://x", "emoji": ""})
    assert saved["embed_data"]["fields"][0]["name"] == "a"
    assert saved["button_links"] == []
