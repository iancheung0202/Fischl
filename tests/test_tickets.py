"""Tickets under shared/Tickets: panels, opening, closing, transcripts, /ticket and its settings."""

import asyncio
import datetime
import hashlib
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from shared.Tickets import tickets as module
from shared.Tickets.tickets import (
    BlacklistView,
    ButtonOptionModal,
    ButtonOptionsView,
    CloseTicketButton,
    ClosingMessageModal,
    ConfirmCloseTicketButtons,
    ConfirmDisableView,
    CooldownModal,
    CreateTicketButtonView,
    EnableSystemButton,
    ExtraTicketButton,
    PanelSelectView,
    PostPanelView,
    RoleAccessView,
    SelectView,
    SnippetModal,
    SnippetsView,
    Ticket,
    TicketAdminButtons,
    TicketPanelEditor,
    TicketPanelMainView,
    TicketSettingsView,
    cooldown_parts,
    cooldown_seconds,
    create_ticket,
    get_transcript,
    panel_view,
    perform_ticket_close,
    shortened,
)

GUILD = 5
CATEGORY = 50
LOG = 60
AMY = 7
STAFF = 9
WHEN = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)


class Person(SimpleNamespace):
    """A user or member; one person is one dictionary key."""

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.id == getattr(other, "id", None)

    def __ne__(self, other):
        return not self == other


class Channel(discord.Object):
    """A text channel that remembers what was sent to it."""

    created_at = WHEN

    def __init__(self, guild, channel_id, name="general", topic=None):
        super().__init__(channel_id, type=discord.TextChannel)
        self.guild, self.name, self.topic = guild, name, topic
        self.sent, self.messages, self.permissions = [], [], {}
        self.deleted = False
        self.mention = f"<#{channel_id}>"
        self.channels = []
        guild.channels[channel_id] = self

    async def send(self, content=None, **parts):
        message = MagicMock(id=1000 + len(self.sent), channel=self)
        message.jump_url = (
            f"https://discord.com/channels/{GUILD}/{self.id}/{message.id}"
        )
        message.delete, message.edit = AsyncMock(), AsyncMock()
        if "embed" in parts:
            parts["embed"] = parts["embed"].copy()
        self.sent.append(SimpleNamespace(content=content, message=message, **parts))
        return message

    async def edit(self, **changes):
        self.topic = str(changes.get("topic", self.topic))

    async def set_permissions(self, target, **permissions):
        self.permissions[target.id] = permissions

    async def delete(self):
        self.deleted = True

    async def fetch_message(self, message_id):
        return next(s.message for s in self.sent if s.message.id == message_id)

    def history(self, limit=None, oldest_first=False):
        async def walk():
            ordered = self.messages if oldest_first else self.messages[::-1]
            for message in ordered[:limit]:
                yield message

        return walk()


class Guild:
    """A server with a ticket category and a log channel."""

    def __init__(self, guild_id=GUILD):
        self.id, self.name, self.icon = guild_id, "Teyvat", None
        self.channels, self.next_id = {}, 100
        self.default_role = SimpleNamespace(id=guild_id, mention="@everyone")
        self.roles = [self.default_role]
        self.category = Channel(self, CATEGORY, "Tickets")
        self.log = Channel(self, LOG, "ticket-logs")

    def get_channel(self, channel_id):
        return self.channels.get(channel_id)

    def get_role(self, role_id):
        return next((role for role in self.roles if role.id == role_id), None)

    async def create_text_channel(self, name, category=None):
        self.next_id += 1
        channel = Channel(self, self.next_id, name)
        if category:
            category.channels.append(channel)
        return channel

    async def create_category(self, name):
        self.next_id += 1
        return Channel(self, self.next_id, name)


def member(user_id=AMY, name="amy"):
    """A member who accepts DMs."""
    return Person(
        id=user_id,
        name=name,
        mention=f"<@{user_id}>",
        avatar=None,
        bot=False,
        color="#ffffff",
        roles=[SimpleNamespace(mention="@everyone"), SimpleNamespace(mention="<@&3>")],
        joined_at=WHEN,
        created_at=WHEN,
        send=AsyncMock(),
    )


def press(guild, user=None, channel=None, **changes):
    """An interaction by a member in the server."""
    it = MagicMock()
    for name in ("send_message", "edit_message", "send_modal", "defer"):
        setattr(it.response, name, AsyncMock())
    it.response.is_done = lambda: any(
        getattr(it.response, name).await_count
        for name in ("send_message", "edit_message", "send_modal", "defer")
    )
    it.edit_original_response = AsyncMock()
    it.followup.send = AsyncMock()
    it.message.delete = AsyncMock()
    it.guild, it.guild_id = guild, guild.id
    it.user = user or member()
    it.channel = channel or Channel(guild, 70)
    people = {AMY: member(), STAFF: member(STAFF, "staff")}
    people[it.user.id] = it.user

    async def fetch_user(user_id):
        if user_id not in people:
            raise discord.NotFound(MagicMock(status=404), "unknown")
        return people[user_id]

    it.client.fetch_user = fetch_user
    it.client.user = Person(id=1, name="fischl")
    it.client.get_channel = lambda channel_id: None
    it.data = {}
    for name, value in changes.items():
        setattr(it, name, value)
    return it


def said(it) -> str:
    """Gives the text of the last direct answer to an interaction."""
    call = it.response.send_message.call_args
    return call.args[0] if call.args else call.kwargs.get("content")


def followed(it) -> str:
    """Gives the text of the last follow-up to an interaction."""
    call = it.followup.send.call_args
    return call.args[0] if call.args else call.kwargs.get("content")


def labelled(view, label):
    """Gives the view's button with this label."""
    return next(i for i in view.children if getattr(i, "label", None) == label)


def typed(modal, *values):
    """Fills a modal's boxes as if the member typed the values."""
    for box, value in zip(modal.children, values):
        box._value = value
    return modal


def choice(label, **parts):
    """A panel button or option as it is saved."""
    base = {"label": label, "emoji": "", "opening_message": "", "closing_message": ""}
    return {**base, **parts}


@pytest.fixture
def guild(firebase, monkeypatch):
    """A server with tickets on and no AI to call."""
    firebase("/Tickets/abc").set(
        {
            "Server ID": GUILD,
            "Server Name": "Teyvat",
            "Category ID": CATEGORY,
            "Log Channel ID": LOG,
            "Cooldown": 0,
        }
    )
    firebase("/Tickets/other").set({"Server ID": 999, "Category ID": 1})
    monkeypatch.setattr(module, "ask_groq", lambda prompt: "A short summary.")
    module.posted.clear()
    module.opening.clear()
    module.closing.clear()
    return Guild()


# Opening


async def test_a_ticket_is_opened_logged_and_answered(guild, firebase):
    it = press(guild)
    await create_ticket(it, topic="Billing", closing_message="Bye!")
    channel = guild.category.channels[0]
    assert channel.name == "amy" and channel.topic == str(AMY)
    assert channel.permissions[AMY] == {
        "send_messages": True,
        "read_messages": True,
        "attach_files": True,
    }
    first = channel.sent[0]
    assert first.content == "**<@7>, welcome!** "
    assert first.embed.title == "Billing"
    assert first.embed.description.startswith("Type your message here in this channel!")
    assert [field.name for field in first.embed.fields] == [
        "User Mention",
        "User ID",
        "Highest Role",
        "Ticket Created",
        "Server Joined",
        "Account Created",
    ]
    assert first.embed.fields[2].value == "<@&3>"
    assert isinstance(first.view, CloseTicketButton)
    logged = guild.log.sent[0].embed
    assert logged.title == "Ticket created" and logged.fields[0].value == "Billing"
    assert logged.footer.text == f"Ticket ID: {channel.id}"
    assert followed(it) == f"{module.YES} Ticket created at <#{channel.id}>"
    assert firebase(f"/Ticket Closing Messages/{channel.id}").get() == "Bye!"
    assert firebase(f"/Tickets Cooldown/{GUILD}/users/{AMY}/last_created").get()


async def test_an_opening_message_and_ping_role_are_shown(guild, firebase):
    firebase("/Tickets/abc/Ping Role ID").set(44)
    await create_ticket(press(guild), topic="Help", custom_opening_message="Say hi")
    first = guild.category.channels[0].sent[0]
    assert first.content == "**<@7>, welcome!** ||<@&44>||"
    assert first.embed.description == f"> Say hi\n\n{module.CLOSE_HINT}"


async def test_no_ticket_without_settings(firebase):
    module.opening.clear()
    it = press(Guild(guild_id=123))
    await create_ticket(it, topic="Help")
    embed = it.followup.send.call_args.kwargs["embed"]
    assert embed.title == "Ticket not enabled!"
    assert "`/ticket settings`" in embed.description


async def test_a_second_ticket_is_refused(guild):
    await create_ticket(press(guild), topic="Help")
    it = press(guild)
    await create_ticket(it, topic="Help")
    channel = guild.category.channels[0]
    assert followed(it) == (
        f"{module.NO} You already had your ticket created at <#{channel.id}>."
    )
    assert len(guild.category.channels) == 1


async def test_two_presses_at_once_open_one_ticket(guild):
    first, second = press(guild), press(guild)
    await asyncio.gather(
        create_ticket(first, topic="Help"), create_ticket(second, topic="Help")
    )
    assert len(guild.category.channels) == 1
    assert not module.opening


async def test_blacklisted_and_cooling_members_are_refused(guild, firebase):
    firebase(f"/Ticket Blacklist/{GUILD}/{AMY}").set(True)
    it = press(guild)
    await create_ticket(it, topic="Help")
    assert "blacklisted" in followed(it)
    firebase(f"/Ticket Blacklist/{GUILD}/{AMY}").delete()
    firebase("/Tickets/abc/Cooldown").set(7200)

    firebase(f"/Tickets Cooldown/{GUILD}/users/{AMY}/last_created").set(time.time())
    it = press(guild)
    await create_ticket(it, topic="Help")
    assert followed(it).endswith("Try again in **1h 59m**.")
    assert not guild.category.channels


async def test_missing_permissions_are_explained(guild):
    guild.create_text_channel = AsyncMock(side_effect=RuntimeError("no"))
    it = press(guild)
    await create_ticket(it, topic="Help")
    assert followed(it) == module.MISSING_PERMISSIONS


# Panels


def button_editor(*labels, panel_id=None):
    made = TicketPanelEditor(STAFF, GUILD, "button", panel_id)
    made.embed_data["title"] = "Support"
    colors = ["green", "red", "blue", "grey", "green"]
    for label, color in zip(labels, colors):
        made.buttons.append(choice(label, color=color))
    return made


async def test_every_panel_button_gets_its_own_id_and_style():
    view = panel_view(button_editor("A", "B", "C"))
    assert [item.custom_id for item in view.children] == [
        "create",
        "create:1",
        "create:2",
    ]
    styles = [getattr(item, "item", item).style for item in view.children]
    assert styles == [
        discord.ButtonStyle.green,
        discord.ButtonStyle.red,
        discord.ButtonStyle.blurple,
    ]
    assert view.is_persistent()


async def test_a_dropdown_panel_lists_its_options():
    made = TicketPanelEditor(STAFF, GUILD, "dropdown")
    made.options.append(choice("Help", description="Get help"))
    made.options.append(choice("Report", description=""))
    view = panel_view(made)
    select = view.children[0]
    assert isinstance(view, SelectView) and select.custom_id == "ticketcreation"
    assert select.placeholder == "Select a ticket category..."
    assert [(o.label, o.value, o.description) for o in select.options] == [
        ("Help", "Help", "Get help"),
        ("Report", "Report", None),
    ]


async def test_a_panel_with_nothing_to_offer_has_no_view():
    assert panel_view(TicketPanelEditor(STAFF, GUILD, "button")) is None


async def test_the_views_registered_at_startup_take_no_arguments():
    for view in (
        CloseTicketButton,
        TicketAdminButtons,
        ConfirmCloseTicketButtons,
        CreateTicketButtonView,
        SelectView,
    ):
        assert view().is_persistent()


def row(*buttons):
    """A message's component row holding (custom_id, label) buttons."""
    children = [SimpleNamespace(custom_id=cid, label=label) for cid, label in buttons]
    return [SimpleNamespace(children=children)]


async def test_a_posted_button_opens_its_own_topic_with_its_messages(guild):
    made = button_editor("Help", "Report")
    made.buttons[1].update(opening_message="What happened?", closing_message="Thanks")
    it = press(guild, user=member(STAFF, "staff"))
    view = PostPanelView(None, made, it)
    view.selected_channel = guild.get_channel(LOG)
    await view.post_panel(it)
    panel = guild.log.sent[0].message
    assert made.message_id == panel.id and made.channel_id == LOG
    assert followed(it).startswith(f"{module.YES} Panel posted! [View Message](")
    it.response.send_message.assert_not_called()

    click = press(guild, data={"custom_id": "create:1"})
    click.message.id = panel.id
    click.message.components = row(("create", "Help"), ("create:1", "Report"))
    button = view_button(panel_view(made), 1)
    await button.callback(click)
    channel = guild.category.channels[0]
    assert channel.sent[0].embed.title == "Report"
    assert channel.sent[0].embed.description.startswith("> What happened?")


def view_button(view, index):
    return view.children[index]


async def test_a_saved_panel_keeps_its_messages_after_a_restart(guild, firebase):
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(
        {
            "name": "Main",
            "message_id": 4242,
            "buttons": [
                choice("Help", color="green"),
                choice("Report", color="red", closing_message="Thanks"),
            ],
        }
    )
    click = press(guild, data={"custom_id": "create:1"})
    click.message.id = 4242
    click.message.components = row(("create", "Help"), ("create:1", "Report"))
    item = SimpleNamespace(label="Report", emoji=None, style=discord.ButtonStyle.red)
    button = await ExtraTicketButton.from_custom_id(click, item, {"index": "1"})
    await button.callback(click)
    channel = guild.category.channels[0]
    assert channel.sent[0].embed.title == "Report"
    assert firebase(f"/Ticket Closing Messages/{channel.id}").get() == "Thanks"


async def test_a_dropdown_choice_is_confirmed_then_opened(guild, firebase):
    firebase(f"/Ticket Panels/{GUILD}/dropdown/p1").set(
        {
            "name": "Main",
            "message_id": 4242,
            "options": [choice("Help", description="", opening_message="Welcome in")],
        }
    )
    pick = press(guild)
    pick.message.id = 4242
    select = SelectView().children[0]
    select._values = ["Help"]
    await select.callback(pick)
    sent = pick.response.send_message.call_args.kwargs
    assert sent["embed"].title == "Confirm Ticket"
    assert sent["embed"].description == (
        "Are you sure you want to make a ticket about **Help**?"
    )
    assert sent["ephemeral"] is True
    confirm = sent["view"]
    assert confirm.children[0].custom_id == "confirm:4242"
    assert confirm.children[0].item.label == "Create Ticket"
    click = press(guild)
    click.message.embeds = [sent["embed"]]
    await confirm.children[0].callback(click)
    channel = guild.category.channels[0]
    assert channel.sent[0].embed.title == "Help"
    assert channel.sent[0].embed.description.startswith("> Welcome in")


async def test_posting_needs_a_channel_and_something_to_offer(guild):
    it = press(guild)
    view = PostPanelView(None, button_editor(), it)
    await view.post_panel(it)
    assert said(it) == "Please select a channel first!"
    view.selected_channel = guild.log
    await view.post_panel(it)
    assert said(it) == f"{module.NO} Cannot post panel: no options/buttons configured!"


async def test_deleting_a_posted_panel_says_the_message_went_too(guild, firebase):
    made = button_editor("Help", panel_id="p1")
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(made.to_dict())
    it = press(guild, channel=guild.log)
    poster = PostPanelView(None, made, it)
    poster.selected_channel = guild.log
    await poster.post_panel(it)
    elsewhere = press(guild)
    view = TicketPanelMainView(None, made, elsewhere)
    await view.delete_panel(elsewhere)
    assert said(elsewhere) == (
        f"{module.YES} Panel deleted! Posted message is also removed."
    )
    guild.log.sent[0].message.delete.assert_awaited_once()
    assert firebase(f"/Ticket Panels/{GUILD}/button/p1").get() is None
    assert made.panel_id is None and made.message_id is None


async def test_updating_a_panel_that_was_never_posted_is_refused(guild):
    it = press(guild)
    view = TicketPanelMainView(None, button_editor("Help"), it)
    await view.update_posted(it)
    assert said(it) == f"{module.NO} This panel hasn't been posted yet!"


async def test_the_main_screen_has_the_same_buttons_as_before(guild):
    it = press(guild)
    view = TicketPanelMainView(None, button_editor("Help", panel_id="p1"), it)
    assert [(item.label, item.row) for item in view.children] == [
        ("Embed", None),
        ("Media", None),
        ("Fields", None),
        ("Manage Buttons", None),
        ("Save", 1),
        ("Save As", 1),
        ("Post Panel", 1),
        ("Update Posted", 1),
        ("Delete Panel", 1),
    ]
    dropdown = TicketPanelMainView(None, TicketPanelEditor(1, GUILD, "dropdown"), it)
    assert [item.label for item in dropdown.children][3:5] == ["Manage Options", "Save"]


async def test_saved_panels_are_listed_to_pick_from(guild, firebase):
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(button_editor("A").to_dict())
    view = PanelSelectView(None, "button")
    await view.load_panels(GUILD)
    select, create = view.children
    assert select.placeholder == "Choose a panel..."
    assert [option.value for option in select.options] == ["p1"]
    assert create.label == "Create New Panel"
    empty = PanelSelectView(None, "dropdown")
    await empty.load_panels(GUILD)
    assert empty.children[0].disabled


async def test_at_most_five_buttons(guild):
    it = press(guild)
    made = button_editor("A", "B", "C", "D", "E")
    await typed(ButtonOptionModal(made), "F", "", "red", "", "").on_submit(it)
    assert said(it) == "Button panels can have a maximum of 5 buttons."
    assert len(made.buttons) == 5


# Closing


def ticket(guild, owner=AMY, closed=False):
    """A ticket channel with its first message and two more."""
    topic = f":no_entry_sign: {owner}" if closed else str(owner)
    channel = Channel(guild, 80, "amy", topic)
    amy, staff = member(), member(STAFF, "staff")
    bot = Person(id=1, name="fischl", avatar=None, bot=True)
    first = SimpleNamespace(
        author=bot,
        content="",
        attachments=[],
        embeds=[discord.Embed(title="Billing", description="Type here")],
    )
    hello = SimpleNamespace(
        author=amy, content="**hi** <@9>", attachments=[], embeds=[]
    )
    reply = SimpleNamespace(author=staff, content="hello", attachments=[], embeds=[])
    again = SimpleNamespace(author=staff, content="bye", attachments=[], embeds=[])
    channel.messages = [first, hello, reply, again]
    return channel


async def test_the_close_button_asks_first(guild):
    channel = ticket(guild)
    owner = press(guild, channel=channel)
    await CloseTicketButton().children[0].callback(owner)
    sent = owner.response.send_message.call_args.kwargs
    assert sent["embed"].title == "Are you sure about that?"
    assert [item.label for item in sent["view"].children] == ["Yes", "No"]
    staff = press(guild, user=member(STAFF, "staff"), channel=channel)
    await CloseTicketButton().children[0].callback(staff)
    view = staff.response.send_message.call_args.kwargs["view"]
    assert [item.label for item in view.children] == [
        "Yes",
        "No",
        "Set Closing Message",
    ]


async def test_closing_twice_or_outside_a_ticket_is_refused(guild):
    it = press(guild, channel=ticket(guild, closed=True))
    await CloseTicketButton().children[0].callback(it)
    embed = it.response.send_message.call_args.kwargs["embed"]
    assert embed.title == "Ticket already closed :no_entry_sign:"
    outside = press(guild)
    await Ticket.ticket_close.callback(None, outside, None)
    embed = outside.response.send_message.call_args.kwargs["embed"]
    assert embed.title == "Invalid Action"


async def test_only_staff_set_a_closing_message(guild):
    it = press(guild, channel=ticket(guild))
    await Ticket.ticket_close.callback(None, it, "bye")
    assert said(it) == "Only staff can override the closing message."


async def test_closing_logs_a_transcript_the_website_accepts(guild, firebase):
    channel = ticket(guild)
    firebase(f"/Ticket Closing Messages/{channel.id}").set("Thanks for asking")
    staff = member(STAFF, "staff")
    it = press(guild, user=staff, channel=channel)
    owner = await it.client.fetch_user(AMY)
    await perform_ticket_close(it)

    logged = guild.log.sent[0]
    page = logged.file.fp.read()
    assert logged.file.filename == f"{channel.id}.html"
    assert page.decode().startswith("<Server-Info>\n    Server: Teyvat (5)\n")
    assert "</Server-Info><!DOCTYPE html>" in page.decode()
    embed = logged.message.edit.call_args.kwargs["embed"]
    fields = {field.name: field.value for field in embed.fields}
    assert fields["Users Involved"] == "- <@7> `(1)`\n- <@9> `(2)`"
    assert fields["Ticket Topic"] == "Billing"
    assert fields["Ticket Summary"] == "A short summary."
    checksum = hashlib.sha256(page + str(LOG).encode()).hexdigest()[:20]
    url = f"https://fischl.app/logs/{LOG}-{logged.message.id}-{checksum}"
    assert fields["Transcript Link"] == url

    dm = owner.send.call_args.kwargs
    assert dm["embed"].title == "Ticket Closed"
    assert dm["embed"].description == (
        "Your ticket in **Teyvat** is now closed.\n\n> Thanks for asking"
    )
    assert dm["view"].children[0].url == url
    assert channel.permissions[AMY] == {
        "send_messages": False,
        "read_messages": False,
        "attach_files": False,
    }
    closing, closed, panel = channel.sent
    closing.message.delete.assert_awaited_once()
    assert closed.embed.title == "Ticket Closed"
    assert closed.embed.description == (
        "Ticket is closed by <@9> and no longer visible to <@7>."
    )
    assert panel.embed.description == "```STAFF CONTROLS PANEL```"
    assert [item.label for item in panel.view.children] == [
        "Reopen Ticket",
        "Delete Ticket",
        "Transcript Link",
    ]
    assert channel.topic == f":no_entry_sign: {AMY}"


async def test_a_member_with_closed_dms_still_loses_the_channel(guild):
    channel = ticket(guild)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    owner = await it.client.fetch_user(AMY)
    owner.send.side_effect = RuntimeError("closed")
    await perform_ticket_close(it)
    assert channel.permissions[AMY]["read_messages"] is False


async def test_closing_after_the_member_left(guild):
    channel = ticket(guild, owner=12345)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await perform_ticket_close(it)
    embed = guild.log.sent[0].embed
    assert "a member who has left the server" in embed.description
    assert channel.sent[1].embed.description == (
        "Member left the server. Ticket is still closed."
    )


async def test_a_failing_ai_does_not_stop_the_close(guild, monkeypatch):
    def broken(prompt):
        raise RuntimeError("down")

    monkeypatch.setattr(module, "ask_groq", broken)
    channel = ticket(guild)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await perform_ticket_close(it)
    embed = guild.log.sent[0].message.edit.call_args.kwargs["embed"]
    assert embed.fields[-1].value == "`AI Summary Temporarily Unavailable`"


async def test_closing_never_writes_a_file(guild, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("opened a file")

    monkeypatch.setattr("builtins.open", refuse)
    channel = ticket(guild)
    await perform_ticket_close(press(guild, user=member(STAFF), channel=channel))
    assert channel.topic.startswith(":no_entry_sign:")


async def test_confirm_buttons(guild):
    channel = ticket(guild)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    view = ConfirmCloseTicketButtons(override_closing_message="Custom bye")
    await view.children[1].callback(it)
    cancelled = it.response.edit_message.call_args.kwargs
    assert cancelled["embed"].title == "Action Cancelled" and cancelled["view"] is None
    await view.children[0].callback(it)
    confirmed = it.response.edit_message.call_args.kwargs["embed"]
    assert confirmed.description == f"{module.YES} **Ticket Closure Confirmed**"
    assert channel.sent[1].embed.fields[0].value == "Custom bye"


async def test_a_typed_closing_message_closes_the_ticket(guild):
    channel = ticket(guild)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await typed(ClosingMessageModal(), "See you").on_submit(it)
    it.response.edit_message.assert_awaited_once()
    assert channel.sent[1].embed.fields[0].value == "See you"


async def test_reopen_gives_the_channel_back(guild):
    channel = ticket(guild, closed=True)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await TicketAdminButtons().children[0].callback(it)
    assert channel.topic == str(AMY)
    assert channel.permissions[AMY]["read_messages"] is True
    assert guild.log.sent[0].embed.title == "Ticket Reopened"
    assert channel.sent[0].embed.title == "🔓 Ticket Reopened"
    assert isinstance(channel.sent[0].view, CloseTicketButton)
    assert followed(it) == "Ticket is reopened."


async def test_reopen_when_the_member_is_gone(guild):
    channel = ticket(guild, owner=12345, closed=True)
    it = press(guild, channel=channel)
    await TicketAdminButtons().children[0].callback(it)
    assert said(it) == "Unable to fetch the user. They probably left the server."


async def test_delete_removes_the_channel(guild, firebase, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    channel = ticket(guild, closed=True)
    firebase(f"/Ticket Closing Messages/{channel.id}").set("bye")
    await TicketAdminButtons().children[1].callback(press(guild, channel=channel))
    assert channel.deleted and channel.sent[0].embed.title == "Deleting Ticket..."
    assert firebase(f"/Ticket Closing Messages/{channel.id}").get() is None


# Transcript


async def test_the_transcript_groups_messages_and_names_mentions(guild):
    channel = ticket(guild)
    it = press(guild, channel=channel)
    page, involved, counts = await get_transcript(it, member())
    assert [user.id for user in involved] == [AMY, STAFF]
    assert list(counts.values()) == [1, 2]
    assert "<strong>hi</strong> <span class='mention'>@staff</span>" in page
    assert page.count("message grouped") == 1
    assert "Ticket Owner: amy (7)" in page
    assert page.endswith("</div></body></html>")
    assert "<div class='embed-title'>Billing</div>" in page


# Commands


async def test_notify(guild):
    channel = ticket(guild)
    staff = press(guild, user=member(STAFF, "staff"), channel=channel)
    owner = await staff.client.fetch_user(AMY)
    await Ticket.ticket_notify.callback(None, staff, "please answer")
    embed = owner.send.call_args.kwargs["embed"]
    assert "kindly respond.\n\n> please answer\n\nIf you no longer" in embed.description
    assert said(staff) == "<@7> received a DM notification."
    own = press(guild, channel=channel)
    await Ticket.ticket_notify.callback(None, own, None)
    assert said(own) == f"{module.NO} You cannot notify yourself!"
    outside = press(guild)
    await Ticket.ticket_notify.callback(None, outside, None)
    assert said(outside) == module.INVALID_CHANNEL


async def test_add_logs_who_was_added_to_whose_ticket(guild):
    channel = ticket(guild)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await Ticket.ticket_add.callback(None, it, member(11, "ben"))
    assert channel.permissions[11] == {"read_messages": True, "send_messages": True}
    assert guild.log.sent[0].embed.description == (
        "<@11> was added by <@9> to <@7>'s ticket."
    )
    outside = press(guild)
    await Ticket.ticket_add.callback(None, outside, member(11, "ben"))
    assert said(outside) == module.INVALID_CHANNEL


async def test_staff_create_a_ticket_for_a_member(guild):
    it = press(guild, user=member(STAFF, "staff"))
    amy = member()
    await Ticket.ticket_create.callback(None, it, amy)
    channel = guild.category.channels[0]
    assert channel.topic == str(AMY)
    assert channel.sent[0].embed.description.startswith(
        "This ticket is created *by <@9>* for <@7>! \nYou can use"
    )
    assert guild.log.sent[0].embed.fields[0].value == "Created by server staff"
    assert followed(it) == (
        f"{module.YES} Ticket for <@7> created at <#{channel.id}>"
        " and the user is notified via DM"
    )
    again = press(guild, user=member(STAFF, "staff"))
    await Ticket.ticket_create.callback(None, again, amy)
    assert "already has their ticket" in followed(again)


async def test_snippets_are_sent_in_other_members_tickets(guild, firebase):
    firebase(f"/Ticket Snippets/{GUILD}/hello").set("Hello there")
    channel = ticket(guild)
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await Ticket.ticket_snippet.callback(None, it, "hello", False, True)
    assert channel.sent[0].content == "<@7> Hello there"
    assert channel.sent[0].embed.author.name == "Sent by staff"
    assert said(it) == "Snippet 'hello' sent successfully!"
    await Ticket.ticket_snippet.callback(None, it, "nope", False, False)
    assert said(it) == "Snippet 'nope' not found!"
    own = press(guild, channel=channel)
    await Ticket.ticket_snippet.callback(None, own, "hello", False, False)
    assert said(own) == "You cannot use this command in your own ticket!"
    outside = press(guild)
    await Ticket.ticket_snippet.callback(None, outside, "hello", False, False)
    assert said(outside) == "This command can only be used in ticket channels!"


async def test_delete_command_needs_a_closed_ticket(guild, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    it = press(guild, channel=ticket(guild))
    await Ticket.ticket_delete.callback(None, it)
    assert it.response.send_message.call_args.kwargs["embed"].title == "Invalid Action"
    assert not it.channel.deleted


# Settings


def test_cooldowns_are_read_and_written():
    assert cooldown_parts(93784) == ["1d", "2h", "3m", "4s"]
    assert cooldown_seconds("1d2h3m4s") == 93784
    assert cooldown_seconds("") == 0 and cooldown_parts(0) == []


def test_long_lists_are_cut_at_a_whole_line():
    lines = "\n".join(f"- line {number:04d}" for number in range(200))
    cut = shortened(lines)
    assert len(cut) <= 1024 and cut.endswith("\n...")
    assert shortened("short") == "short"


async def settings(guild, it):
    _, config = await module.server_config(guild.id)
    return TicketSettingsView(None, it, config)


async def test_the_settings_screen(guild, firebase):
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set({"name": "A"})
    it = press(guild)
    view = await settings(guild, it)
    await view.update_message()
    sent = it.edit_original_response.call_args.kwargs
    assert sent["embed"].fields[0].value == (
        "-# - **Category:** Tickets\n-# - **Log Channel:** <#60>\n"
        "-# - **Ping Role:** Not set\n-# - **Cooldown:** No cooldown"
    )
    assert "**Button Panels:** `1`" in sent["embed"].fields[1].value
    assert [getattr(item, "label", item.custom_id) for item in view.children] == [
        "category_select",
        "log_select",
        "role_select",
        "Cooldown",
        "Role Access",
        "Blacklist",
        "Snippets",
        "Disable System",
    ]


async def test_a_new_cooldown_is_saved_and_shown(guild, firebase):
    it = press(guild)
    view = await settings(guild, it)
    await typed(CooldownModal(view), "1h30m").on_submit(it)
    assert firebase("/Tickets/abc/Cooldown").get() == 5400
    embed = it.response.edit_message.call_args.kwargs["embed"]
    assert "**Cooldown:** 1h, 30m" in embed.fields[0].value
    assert CooldownModal(view).children[0].default == "1h30m"


async def test_choosing_a_log_channel_saves_it(guild, firebase):
    other = Channel(guild, 61, "logs2")
    it = press(guild, data={"values": ["61"]})
    view = await settings(guild, it)
    await view.select_log_channel(it)
    assert firebase("/Tickets/abc/Log Channel ID").get() == 61
    assert view.selected_log_channel is other


async def test_disabling_clears_everything_and_offers_enable(guild, firebase):
    for path in module.SERVER_PATHS:
        firebase(f"/{path}/{GUILD}/x").set("y")
    it = press(guild)
    view = await settings(guild, it)
    await ConfirmDisableView(view).children[0].callback(it)
    assert firebase("/Tickets/abc").get() is None
    assert firebase("/Tickets/other").get()
    for path in module.SERVER_PATHS:
        assert firebase(f"/{path}/{GUILD}").get() is None
    sent = it.response.edit_message.call_args.kwargs
    assert [item.label for item in sent["view"].children] == ["Enable System"]
    assert "currently **disabled**" in sent["embed"].description


async def test_enabling_makes_the_channels_and_the_record(firebase):
    guild = Guild(guild_id=77)
    it = press(guild)
    view = TicketSettingsView(None, it, None)
    view.fill()
    await view.children[0].callback(it)
    it.response.defer.assert_awaited_once()
    key, config = await module.server_config(77)
    assert key and config["Server Name"] == "Teyvat" and config["Cooldown"] == 0
    category = guild.get_channel(config["Category ID"])
    assert category.name == "Tickets"
    assert category.permissions[77] == {"read_messages": False}
    assert guild.get_channel(config["Log Channel ID"]).name == "ticket-logs"
    assert it.edit_original_response.call_args.kwargs["embed"].fields


async def test_blacklist_screen_adds_and_removes(guild, firebase):
    for user_id in range(100, 112):
        firebase(f"/Ticket Blacklist/{GUILD}/{user_id}").set(True)
    it = press(guild, data={"values": ["555"]})
    view = BlacklistView(None, it, await settings(guild, it))
    await view.show_blacklist(it)
    embed = it.response.edit_message.call_args.kwargs["embed"]
    assert embed.fields[0].value.split("\n")[0] == "- <@100> (100)"
    assert embed.fields[1].value == "Plus 2 more users"
    block = labelled(view, "Blacklist User")
    await block.callback(it)
    assert said(it) == "Please select a user first!"
    await view.select_user(it)
    await block.callback(it)
    assert firebase(f"/Ticket Blacklist/{GUILD}/555").get() is True
    unblock = labelled(view, "Unblacklist User")
    await unblock.callback(it)
    assert firebase(f"/Ticket Blacklist/{GUILD}/555").get() is None


async def test_role_access_screen(guild):
    helper = SimpleNamespace(id=31, mention="<@&31>")
    guild.roles.append(helper)
    guild.category.permissions_for = lambda role: SimpleNamespace(
        read_messages=role.id in guild.category.permissions
        and guild.category.permissions[role.id].get("read_messages")
    )
    it = press(guild, data={"values": ["31"]})
    view = RoleAccessView(None, it, await settings(guild, it))
    await view.show_role_access(it)
    embed = it.response.edit_message.call_args.kwargs["embed"]
    assert embed.fields[0].value == "No roles configured"
    grant = labelled(view, "Grant Access")
    await grant.callback(it)
    assert said(it) == "Please select a role first!"
    await view.select_role(it)
    await grant.callback(it)
    embed = it.response.edit_message.call_args.kwargs["embed"]
    assert embed.fields[0].value == "- <@&31>"


async def test_snippets_screen(guild, firebase):
    it = press(guild)
    view = SnippetsView(None, it, await settings(guild, it))
    await view.show_snippets(it)
    assert [item.label for item in view.children] == ["Add Snippet", "Back to Settings"]
    await typed(SnippetModal(view), "hi", "Hello there").on_submit(it)
    assert firebase(f"/Ticket Snippets/{GUILD}/hi").get() == "Hello there"
    embed = it.response.edit_message.call_args.kwargs["embed"]
    assert embed.fields[0].name == "Current Snippets (1/25)"
    assert embed.fields[0].value == "- **hi**: Hello there"
    await typed(SnippetModal(view), "a/b", "x").on_submit(it)
    assert "cannot contain" in said(it)
    await typed(SnippetModal(view, "hi", "Hello there", True), "hey", "Yo").on_submit(
        it
    )
    assert firebase(f"/Ticket Snippets/{GUILD}").get() == {"hey": "Yo"}
    view.selected_snippet = "hey"
    remove = labelled(view, "Remove Snippet")
    await remove.callback(it)
    assert firebase(f"/Ticket Snippets/{GUILD}").get() is None


async def test_setup_registers_the_cog_and_extra_buttons():
    bot = MagicMock()
    bot.add_cog = AsyncMock()
    await module.setup(bot)
    bot.add_dynamic_items.assert_called_once_with(
        ExtraTicketButton, module.ConfirmTicketButton
    )
    assert isinstance(bot.add_cog.call_args.args[0], Ticket)


# Review round 1


def dropdown(firebase, *options):
    """Saves a posted dropdown panel with these options."""
    firebase(f"/Ticket Panels/{GUILD}/dropdown/p1").set(
        {"message_id": 4242, "options": list(options)}
    )


async def pick_topic(guild, topic):
    """Chooses a topic on the posted dropdown and gives the confirm prompt sent."""
    pick = press(guild)
    pick.message.id = 4242
    select = SelectView().children[0]
    select._values = [topic]
    await select.callback(pick)
    return pick.response.send_message.call_args.kwargs


async def test_a_dropdown_choice_never_reaches_another_panels_button(guild, firebase):
    dropdown(firebase, choice("Help", description="", opening_message="Welcome in"))
    await pick_topic(guild, "Help")
    plain = press(guild, data={"custom_id": "create"})
    plain.message.id = 9
    plain.message.embeds = [discord.Embed(title="Support", description="Press")]
    plain.message.components = row(("create", "Create Ticket"))
    await CreateTicketButtonView().children[0].callback(plain)
    first = guild.category.channels[0].sent[0].embed
    assert first.title == "Support"
    assert first.description.startswith("Type your message here")


async def test_two_confirm_prompts_keep_their_own_choice(guild, firebase):
    dropdown(
        firebase,
        choice("Help", description="", opening_message="Welcome in"),
        choice("Report", description="", closing_message="Thanks"),
    )
    prompts = [await pick_topic(guild, topic) for topic in ("Help", "Report")]
    for sent, user in zip(prompts, (member(), member(8, "bob"))):
        click = press(guild, user=user)
        click.message.embeds = [sent["embed"]]
        button = await module.ConfirmTicketButton.from_custom_id(
            click, None, {"panel": "4242"}
        )
        await button.callback(click)
        click.response.defer.assert_awaited_once()
    help_ticket, report = guild.category.channels[:2]
    assert help_ticket.sent[0].embed.description.startswith("> Welcome in")
    assert report.sent[0].embed.title == "Report"
    assert firebase(f"/Ticket Closing Messages/{help_ticket.id}").get() is None
    assert firebase(f"/Ticket Closing Messages/{report.id}").get() == "Thanks"


async def test_an_old_single_button_panel_keeps_its_title_and_instructions(
    guild, firebase
):
    firebase(f"/Ticket Instructions/{GUILD}/support").set(
        {"title": "Read me", "description": "Rules", "color": "#ff0000"}
    )
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(
        {"message_id": 4242, "buttons": [choice("Open", opening_message="Hi")]}
    )
    click = press(guild, data={"custom_id": "create"})
    click.message.id = 4242
    click.message.embeds = [discord.Embed(title="Support", description="Press")]
    click.message.components = row(("create", "Open"))
    await CreateTicketButtonView().children[0].callback(click)
    channel = guild.category.channels[0]
    assert channel.sent[0].embed.title == "Support"
    assert channel.sent[0].embed.description.startswith("> Hi")
    assert channel.sent[1].embed.title == "Read me"
    assert channel.sent[1].embed.color.value == 0xFF0000


async def test_a_stale_settings_screen_writes_nothing(guild, firebase):
    it = press(guild, data={"values": ["61"]})
    Channel(guild, 61, "logs2")
    view = await settings(guild, it)
    firebase("/Tickets/abc").delete()
    await view.select_log_channel(it)
    assert firebase("/Tickets").get() == {"other": {"Server ID": 999, "Category ID": 1}}
    shown = it.response.edit_message.call_args.kwargs
    assert [item.label for item in shown["view"].children] == ["Enable System"]


async def test_a_setting_follows_the_record_to_its_new_key(guild, firebase):
    it = press(guild, data={"values": ["61"]})
    Channel(guild, 61, "logs2")
    view = await settings(guild, it)
    record = firebase("/Tickets/abc").get()
    firebase("/Tickets/abc").delete()
    firebase("/Tickets/new").set(record)
    await view.select_log_channel(it)
    assert firebase("/Tickets/abc").get() is None
    assert firebase("/Tickets/new").get() == {**record, "Log Channel ID": 61}


async def test_a_stale_disable_removes_the_live_record(guild, firebase):
    it = press(guild)
    view = await settings(guild, it)
    record = firebase("/Tickets/abc").get()
    firebase("/Tickets/abc").delete()
    firebase("/Tickets/new").set(record)
    await ConfirmDisableView(view).children[0].callback(it)
    assert firebase("/Tickets").get() == {"other": {"Server ID": 999, "Category ID": 1}}


async def test_disabling_leaves_other_servers_alone(guild, firebase):
    paths = (
        "Ticket Panels",
        "Ticket Blacklist",
        "Ticket Instructions",
        "Ticket Snippets",
        "Tickets Cooldown",
    )
    for path in paths:
        firebase(f"/{path}/{GUILD}/x").set("y")
        firebase(f"/{path}/999/x").set("y")
    firebase("/Ticket Closing Messages/55").set("Bye")
    firebase(f"/Ticket Closing Messages/{GUILD}").set("Bye")
    assert module.SERVER_PATHS == paths
    it = press(guild)
    await ConfirmDisableView(await settings(guild, it)).children[0].callback(it)
    for path in paths:
        assert firebase(f"/{path}").get() == {"999": {"x": "y"}}
    assert firebase("/Ticket Closing Messages/55").get() == "Bye"
    assert firebase(f"/Ticket Closing Messages/{GUILD}").get() == "Bye"


async def test_enabling_twice_keeps_one_record(guild, firebase):
    it = press(guild)
    view = TicketSettingsView(None, it, None)
    view.fill()
    await view.children[0].callback(it)
    assert set(firebase("/Tickets").get()) == {"abc", "other"}
    assert guild.category.channels == []


async def test_posting_a_saved_panel_keeps_its_other_fields(guild, firebase):
    made = button_editor("Help", panel_id="p1")
    saved = {**made.to_dict(), "name": "Renamed since"}
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(saved)
    firebase(f"/Ticket Panels/{GUILD}/button/p2").set({"name": "Sibling"})
    it = press(guild)
    view = PostPanelView(None, made, it)
    view.selected_channel = guild.log
    await view.post_panel(it)
    message = guild.log.sent[0].message
    assert firebase(f"/Ticket Panels/{GUILD}/button/p1").get() == {
        **saved,
        "message_id": message.id,
        "channel_id": LOG,
    }
    assert firebase(f"/Ticket Panels/{GUILD}/button/p2").get() == {"name": "Sibling"}


async def test_posting_a_panel_deleted_meanwhile_does_not_bring_it_back(
    guild, firebase
):
    it = press(guild)
    view = PostPanelView(None, button_editor("Help", panel_id="gone"), it)
    view.selected_channel = guild.log
    await view.post_panel(it)
    assert firebase(f"/Ticket Panels/{GUILD}").get() is None


async def test_deleting_a_panel_keeps_its_siblings(guild, firebase):
    made = button_editor("Help", panel_id="p1")
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(made.to_dict())
    firebase(f"/Ticket Panels/{GUILD}/button/p2").set({"name": "Sibling"})
    it = press(guild)
    await TicketPanelMainView(None, made, it).delete_panel(it)
    assert firebase(f"/Ticket Panels/{GUILD}/button").get() == {
        "p2": {"name": "Sibling"}
    }


async def test_two_confirmations_close_the_ticket_once(guild):
    channel = ticket(guild)
    staff = member(STAFF, "staff")
    presses = [press(guild, user=staff, channel=channel) for _ in range(2)]
    await asyncio.gather(*map(module.perform_ticket_close, presses))
    assert len(guild.log.sent) == 1
    assert channel.topic.count(module.CLOSED_MARK) == 1
    assert module.closing == set()


async def test_firebase_and_the_ai_are_called_off_the_event_loop(guild, monkeypatch):
    threads = []
    monkeypatch.setattr(
        module, "ask_groq", lambda prompt: threads.append(threading.get_ident())
    )
    kind = type(module.db.reference("/Tickets"))
    for name in ("get", "set", "delete"):
        monkeypatch.setattr(
            kind, name, lambda self, *value: threads.append(threading.get_ident())
        )
    await module.generate("hi")
    await module.read("/Tickets/abc")
    await module.write("/Tickets/abc/Cooldown", 5)
    await module.remove("/Tickets/abc/Cooldown")
    assert len(threads) == 4 and threading.get_ident() not in threads


async def test_saving_a_panel_writes_only_that_panel(guild, firebase):
    firebase(f"/Ticket Panels/{GUILD}/button/p2").set({"name": "Sibling"})
    made = button_editor("Help", panel_id="p1")
    it = press(guild)
    await typed(module.SaveModal(made), "Front desk").on_submit(it)
    saved = firebase(f"/Ticket Panels/{GUILD}/button").get()
    assert saved["p2"] == {"name": "Sibling"}
    assert saved["p1"]["name"] == "Front desk" and saved["p1"]["type"] == "button"
    assert [button["label"] for button in saved["p1"]["buttons"]] == ["Help"]
    assert set(saved) == {"p1", "p2"}


async def test_save_as_makes_a_new_panel_up_to_the_limit(guild, firebase):
    made = button_editor("Help", panel_id="p1")
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(made.to_dict())
    it = press(guild)
    await typed(module.SaveModal(made, is_save_as=True), "Copy").on_submit(it)
    saved = firebase(f"/Ticket Panels/{GUILD}/button").get()
    assert len(saved) == 2 and made.panel_id != "p1"
    assert saved[made.panel_id]["name"] == "Copy"
    for number in range(module.PANEL_LIMIT):
        firebase(f"/Ticket Panels/{GUILD}/button/x{number}").set({"name": "x"})
    await typed(module.SaveModal(made, is_save_as=True), "More").on_submit(it)
    assert said(it) == "Server button panel limit reached (25). Cannot save new panel."
    assert len(firebase(f"/Ticket Panels/{GUILD}/button").get()) == 27


async def test_old_records_with_missing_parts_still_work(guild, firebase):
    firebase("/Tickets/broken").set({"Log Channel ID": 61})
    firebase("/Tickets/abc/Cooldown").delete()
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(
        {"message_id": 4242, "buttons": [{"label": "Open"}]}
    )
    made = module.TicketPanelEditor(AMY, GUILD, "button", "p1", {"name": "Old"})
    assert made.to_embed() is not None and made.message_id is None
    click = press(guild, data={"custom_id": "create"})
    click.message.id = 4242
    click.message.embeds = [discord.Embed(title="Support", description="Press")]
    click.message.components = row(("create", "Open"))
    await CreateTicketButtonView().children[0].callback(click)
    channel = guild.category.channels[0]
    assert channel.sent[0].embed.title == "Support"
    assert firebase(f"/Ticket Closing Messages/{channel.id}").get() is None


@pytest.mark.parametrize(
    "server, topic, name, category, log",
    [
        (module.LUMINE_MAINS, None, None, "c", "l"),
        (module.SPLIT_SERVER, "Partner request", None, "partner", "partner-log"),
        (module.SPLIT_SERVER, "Something else", None, "c", "l"),
        (GUILD, "Partner request", None, "c", "l"),
    ],
)
def test_routing_by_topic(server, topic, name, category, log):
    channels = {
        module.SPLIT_PARTNER_CATEGORY: "partner",
        module.SPLIT_PARTNER_LOG: "partner-log",
    }
    place = SimpleNamespace(id=server, get_channel=channels.get)
    if topic is None:
        word, ending = next(iter(module.LUMINE_ENDINGS.items()))
        assert module.routed(place, f"My {word.upper()}", "c", "l") == (
            ending,
            "c",
            "l",
        )
        return
    assert module.routed(place, topic, "c", "l") == (name, category, log)


async def test_buttons_sharing_a_label_keep_their_own_messages(guild, firebase):
    buttons = [
        choice("Help", opening_message="One"),
        choice("Help", opening_message="Two"),
    ]
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(
        {"message_id": 4242, "buttons": buttons}
    )
    click = press(guild, data={"custom_id": "create:1"})
    click.message.id = 4242
    item = SimpleNamespace(label="Help", emoji=None, style=discord.ButtonStyle.red)
    button = await ExtraTicketButton.from_custom_id(click, item, {"index": "1"})
    await button.callback(click)
    assert guild.category.channels[0].sent[0].embed.description.startswith("> Two")


async def test_delete_command_leaves_other_channels_alone(guild):
    channel = Channel(guild, 71, "clock")
    channel.topic = "Server time 12:30:45"
    channel.delete = AsyncMock()
    it = press(guild, user=member(STAFF, "staff"), channel=channel)
    await Ticket(MagicMock()).ticket_delete.callback(Ticket(MagicMock()), it)
    assert it.response.send_message.call_args.kwargs["embed"].title == "Invalid Action"
    channel.delete.assert_not_called()


async def test_enabling_redraws_through_the_button_press(firebase):
    guild = Guild(guild_id=77)
    opened, pressed = press(guild), press(guild)
    view = TicketSettingsView(None, opened, None)
    view.fill()
    await view.children[0].callback(pressed)
    opened.edit_original_response.assert_not_called()
    assert pressed.edit_original_response.call_args.kwargs["embed"].fields


async def test_deleting_a_panel_whose_message_is_already_gone(guild, firebase):
    made = button_editor("Help", panel_id="p1")
    made.message_id, made.channel_id = 4242, LOG
    firebase(f"/Ticket Panels/{GUILD}/button/p1").set(made.to_dict())
    gone = discord.NotFound(MagicMock(status=404), "unknown")
    guild.log.fetch_message = AsyncMock(side_effect=gone)
    it = press(guild)
    await TicketPanelMainView(None, made, it).delete_panel(it)
    assert said(it).startswith(f"{module.YES} Panel deleted!")
    assert firebase(f"/Ticket Panels/{GUILD}/button/p1").get() is None


async def test_a_confirm_prompt_is_not_kept_by_the_bot(guild, firebase):
    dropdown(firebase, choice("Help", description=""))
    sent = await pick_topic(guild, "Help")
    assert sent["view"].is_finished()
    assert [item.custom_id for item in sent["view"].children] == ["confirm:4242"]


async def test_staff_cannot_create_one_members_ticket_twice_at_once(guild):
    cog = Ticket(MagicMock())
    staff, amy = member(STAFF, "staff"), member()
    presses = [press(guild, user=staff) for _ in range(2)]
    make = guild.create_text_channel

    async def slow(name, category=None):
        await asyncio.sleep(0.05)
        return await make(name, category=category)

    guild.create_text_channel = slow
    await asyncio.gather(*(cog.ticket_create.callback(cog, it, amy) for it in presses))
    assert len(guild.category.channels) == 1
    answers = sorted(followed(it) or "" for it in presses)
    assert answers[0] == f"{module.NO} <@{AMY}>'s ticket is already being created."
    assert module.opening == set()


async def test_a_press_is_acknowledged_before_firebase_is_read(guild, monkeypatch):
    click = press(guild, data={"custom_id": "create"})
    click.message.embeds = [discord.Embed(title="Support", description="Press")]
    order = []
    click.response.defer = AsyncMock(side_effect=lambda **_: order.append("defer"))
    read = module.read

    async def watched(path):
        order.append("read")
        return await read(path)

    monkeypatch.setattr(module, "read", watched)
    await CreateTicketButtonView().children[0].callback(click)
    assert order[0] == "defer" and "read" in order
