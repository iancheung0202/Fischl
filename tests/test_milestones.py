from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events import config, milestones

GUILD = 10
MORA = config.CURRENCY_INFO["guild_mora"]["emoji"]
NO = config.NO_EMOTE


class Store:
    """Stands in for the stored milestones and the holder checks; `calls` lists what was asked."""

    def __init__(self):
        self.rows = []
        self.calls = []
        self.result = {"awarded": 0, "revoked": 0}

    def row(self, name):
        return next((row for row in self.rows if str(row[1]) == name), None)

    async def get_milestones_list(self, pool, gid):
        return [list(row) for row in self.rows]

    async def get_milestone_by_name(self, pool, gid, name):
        row = self.row(name)
        return list(row) if row else None

    async def add_milestone(self, pool, gid, name, description, threshold, currency):
        self.rows.append([description, name, threshold, currency])

    async def update_milestone_field(self, pool, gid, name, field, value):
        self.calls.append(("field", name, field, value))
        place = {"description": 0, "name": 1, "currency_type": 3}[field]
        if self.row(name):
            self.row(name)[place] = value

    async def update_milestone_threshold(self, pool, gid, name, value):
        self.calls.append(("threshold", name, value))
        self.row(name)[2] = value

    async def migrate_milestone_reward(self, pool, guild, old, new):
        self.calls.append(("migrate", old, new))

    async def remove_milestone_by_name(self, pool, gid, name):
        self.rows = [row for row in self.rows if str(row[1]) != name]

    async def revoke_all_milestone_holders(self, pool, guild, name):
        self.calls.append(("revoke", name))
        return self.result["revoked"]

    async def sync_milestone_holders(self, pool, guild, milestone):
        self.calls.append(("sync", list(milestone)))
        return dict(self.result)


@pytest.fixture
def store(monkeypatch):
    store = Store()
    for name in dir(Store):
        if not name.startswith("_") and hasattr(milestones, name):
            monkeypatch.setattr(milestones, name, getattr(store, name))
    monkeypatch.setattr(milestones.time, "time", lambda: 1234.5)
    return store


AUTHOR = SimpleNamespace(id=20, guild_permissions=SimpleNamespace(administrator=True))
ROLE = SimpleNamespace(id=500, name="Knight", mention="<@&500>")


def press(user=AUTHOR, admin=True):
    """Gives an interaction from an admin in a server that has one role."""
    interaction = MagicMock()
    interaction.guild.id = GUILD
    interaction.guild.name = "Mondstadt"
    interaction.guild.get_role = lambda role_id: ROLE if role_id == 500 else None
    interaction.user = user
    user.guild_permissions.administrator = admin
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock(return_value="message")
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock(return_value="message")
    interaction.message.edit = AsyncMock()
    return interaction


async def opened(store, admin=True):
    """Runs /milestones; gives the interaction, the embed and the view."""
    interaction = press(admin=admin)
    cog = milestones.Milestones(MagicMock())
    await cog.milestones.callback(cog, interaction)
    sent = interaction.followup.send.await_args.kwargs
    return interaction, sent["embed"], sent["view"]


def child(view, kind):
    return next(item for item in view.children if isinstance(item, kind))


def labels(view):
    return [
        getattr(item, "label", None) or item.placeholder for item in view.children[4:]
    ]


async def detail(store, name):
    """Opens one milestone the way the admin menu does; gives its view and embed."""
    _, _, view = await opened(store)
    menu = child(view, milestones.MilestoneItemSelect)
    menu._values = [name]
    interaction = press()
    await menu.callback(interaction)
    edited = interaction.response.edit_message.await_args.kwargs
    return edited["view"], edited["embed"], interaction


async def submit(view, field, text, interaction=None):
    """Types into one of the three edit boxes and sends it."""
    button = next(i for i in view.children if getattr(i, "field_name", "") == field)
    first = press()
    await button.callback(first)
    modal = first.response.send_modal.await_args.args[0]
    modal.input._value = text
    interaction = interaction or press()
    await modal.on_submit(interaction)
    return interaction, modal


@pytest.mark.parametrize(
    "text, number",
    [
        ("1500", 1500),
        ("2.5k", 2500),
        (" 3M ", 3_000_000),
        ("1b", 10**9),
        ("2t", 2 * 10**12),
        ("1e3", 1000),
        ("0.4", 0),
    ],
)
def test_thresholds_read_suffixes(text, number):
    assert milestones.parse_threshold(text) == number


@pytest.mark.parametrize("text", ["", "k", "abc"])
def test_thresholds_that_are_not_numbers_raise(text):
    with pytest.raises(ValueError):
        milestones.parse_threshold(text)


def test_an_unknown_currency_shows_server_mora():
    assert milestones.get_currency_display("nope") == MORA
    assert (
        milestones.get_currency_display("global_sigils")
        == config.CURRENCY_INFO["global_sigils"]["emoji"]
    )


async def test_no_milestones(store):
    interaction, embed, view = await opened(store)
    interaction.response.defer.assert_awaited_once_with(thinking=True)
    assert embed.title == "This server has no milestones set up yet."
    assert embed.footer.text == "Page 1 of 1"
    assert labels(view) == [
        "Add Milestone",
        "Choose the Sorting",
        "Filter by currency...",
    ]
    assert view.message == "message" and view.timeout == 300


async def test_the_list_is_paged_by_five_highest_first(store):
    store.rows = [[f"d{i}", f"Title {i}", i * 100, "guild_mora"] for i in range(1, 7)]
    store.rows.append(["knighted", "500", 50, "global_mora"])
    store.rows.append(["lost", "501", 1_000_000, "guild_sigils"])
    _, embed, view = await opened(store)
    assert embed.title == "Mondstadt's Server Milestones"
    assert embed.color == discord.Color.pink()
    assert "all milestones cost `0`" in embed.description
    assert embed.footer.text == (
        "Page 1 of 2 • Sorted by Threshold in Descending order"
    )
    sigil = config.CURRENCY_INFO["guild_sigils"]["emoji"]
    assert [(f.name, f.value, f.inline) for f in embed.fields][:2] == [
        (
            f"1ㅤ {sigil} 1,000,000 • Unknown Role",
            "> **Role:** Unknown\n> **Description:** lost",
            False,
        ),
        (f"2ㅤ {MORA} 600 • Title 6", "> **Description:** d6", False),
    ]
    assert len(embed.fields) == 5 and len(view.pages[1].fields) == 3
    assert view.pages[1].fields[-1].value == (
        "> **Role:** <@&500>\n> **Description:** knighted"
    )
    menu = child(view, milestones.MilestoneItemSelect)
    assert menu.row == 3
    assert menu.placeholder == "Select a milestone to edit (page 1)..."
    assert [(o.label, o.value) for o in menu.options][:2] == [
        ("1,000,000 • Unknown Role", "501"),
        ("600 • Title 6", "Title 6"),
    ]
    add = child(view, milestones.MilestoneAddButton)
    assert (add.label, add.style, add.row) == (
        "Add Milestone",
        discord.ButtonStyle.green,
        0,
    )


async def test_turning_the_page_swaps_the_edit_menu(store):
    store.rows = [["d", f"T{i}", i + 1, "guild_mora"] for i in range(7)]
    _, _, view = await opened(store)
    interaction = press()
    await view.next_button.callback(interaction)
    menu = child(view, milestones.MilestoneItemSelect)
    assert menu.placeholder == "Select a milestone to edit (page 2)..."
    assert [o.value for o in menu.options] == ["T1", "T0"]
    assert labels(view)[2:] == [menu.placeholder, "Add Milestone"]


async def test_members_get_no_edit_controls(store):
    store.rows = [["d", "Title", 5, "guild_mora"]]
    _, _, view = await opened(store, admin=False)
    assert labels(view) == ["Choose the Sorting", "Filter by currency..."]


async def test_long_names_are_cut_in_the_menu(store):
    store.rows = [["d", "x" * 100, 5, "guild_mora"]]
    _, _, view = await opened(store)
    option = child(view, milestones.MilestoneItemSelect).options[0]
    assert option.label == "5 • " + "x" * 87 + "..."
    assert option.value == "x" * 100


async def test_sorting_by_name_uses_role_names(store):
    store.rows = [
        ["d", "zeta", 1, "guild_mora"],
        ["d", "500", 2, "guild_mora"],
        ["d", "Alpha", 3, "guild_sigils"],
    ]
    _, _, view = await opened(store)
    view.currency_filter = "guild_mora"
    interaction = press()
    interaction.data = {"values": ["sort by name (a-z)"]}
    await child(view, milestones.MilestoneSort).callback(interaction)
    edited = interaction.response.edit_message.await_args.kwargs
    assert [f.name.split(" • ")[1] for f in edited["embed"].fields] == [
        "Knight",
        "zeta",
    ]
    assert (
        edited["embed"].footer.text == "Page 1 of 1 • Sorted by Name in Ascending order"
    )
    new = edited["view"]
    assert new.currency_filter == "guild_mora" and new.message == "message"
    assert [o.default for o in child(new, milestones.MilestoneSort).options] == [
        False,
        False,
        True,
        False,
    ]
    assert [
        o.default for o in child(new, milestones.MilestoneCurrencyFilterSelect).options
    ] == [False, True, False, False, False]


async def test_filtering_by_a_currency_nobody_uses(store):
    store.rows = [["d", "Title", 5, "guild_mora"]]
    _, _, view = await opened(store)
    menu = child(view, milestones.MilestoneCurrencyFilterSelect)
    assert [o.label for o in menu.options] == ["All currencies"] + [
        info["filter_label"] for info in config.CURRENCY_INFO.values()
    ]
    menu._values = [config.CURRENCY_INFO["global_sigils"]["filter_label"]]
    interaction = press()
    await menu.callback(interaction)
    edited = interaction.response.edit_message.await_args.kwargs
    sigil = config.CURRENCY_INFO["global_sigils"]["emoji"]
    assert edited["embed"].title == f"No milestones found for {sigil}."
    assert edited["view"].currency_filter == "global_sigils"
    assert child(edited["view"], milestones.MilestoneSort).options[1].default
    menu._values = ["All currencies"]
    await menu.callback(interaction)
    assert (
        interaction.response.edit_message.await_args.kwargs["view"].currency_filter
        == "all"
    )


async def test_only_the_author_may_press(store):
    store.rows = [["d", "Title", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Title")
    assert await view.interaction_check(press()) is True
    stranger = press(SimpleNamespace(id=99, guild_permissions=SimpleNamespace()))
    assert await view.interaction_check(stranger) is False
    stranger.response.send_message.assert_awaited_once_with(
        f"{NO} You are not the author of this command", ephemeral=True
    )


async def test_opening_a_milestone(store):
    store.rows = [["", "500", 2500, "global_mora"]]
    view, embed, _ = await detail(store, "500")
    assert embed.title == "Milestone: Knight"
    assert embed.description == (
        "> **Role:** <@&500>\n> **Description:** > **Description:** No description provided."
    )
    emoji = config.CURRENCY_INFO["global_mora"]["emoji"]
    assert [(f.name, f.value, f.inline) for f in embed.fields] == [
        ("Threshold", f"{emoji} `2,500`", True)
    ]
    assert [
        (getattr(i, "label", None) or i.placeholder, i.row) for i in view.children
    ] == [
        ("Edit Name", 0),
        ("Edit Description", 0),
        ("Edit Threshold", 0),
        ("Select a currency...", 1),
        ("Delete Milestone", 2),
        ("Back to Milestones", 2),
    ]
    assert [i.style for i in view.children if isinstance(i, discord.ui.Button)] == [
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.danger,
        discord.ButtonStyle.blurple,
    ]
    currency = child(view, milestones.MilestoneCurrencySelect)
    assert [(o.value, o.label, o.default) for o in currency.options] == [
        (key, info["label"], key == "global_mora")
        for key, info in config.CURRENCY_INFO.items()
    ]
    assert view.timeout == 300


async def test_a_title_milestone_and_a_missing_one(store):
    store.rows = [["earned", "Hero", 5, "guild_mora"]]
    view, embed, _ = await detail(store, "Hero")
    assert (embed.title, embed.description) == (
        "Milestone: Hero",
        "> **Description:** earned",
    )
    _, _, listing = await opened(store)
    menu = child(listing, milestones.MilestoneItemSelect)
    store.rows = []
    menu._values = ["Hero"]
    interaction = press()
    await menu.callback(interaction)
    interaction.response.send_message.assert_awaited_once_with(
        f"{NO} Milestone not found.", ephemeral=True
    )


async def test_the_detail_screen_expires(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, interaction = await detail(store, "Hero")
    await view.on_timeout()
    assert [(i.label, i.disabled) for i in view.children] == [("Expired", True)]
    interaction.message.edit.assert_awaited_once_with(view=view)
    interaction.message.edit.side_effect = discord.NotFound(
        MagicMock(status=404), "gone"
    )
    await view.on_timeout()


async def test_adding_a_milestone_opens_an_empty_one(store):
    _, _, view = await opened(store)
    interaction = press()
    await child(view, milestones.MilestoneAddButton).callback(interaction)
    assert store.rows == [["", "_new_1234", 0, "guild_mora"]]
    edited = interaction.response.edit_message.await_args.kwargs
    assert edited["embed"].title == "Milestone: _new_1234"
    assert edited["embed"].fields[0].value == f"{MORA} `0`"
    assert edited["view"].parent_message is interaction.message


async def test_adding_fails_when_nothing_was_stored(store, monkeypatch):
    _, _, view = await opened(store)
    monkeypatch.setattr(milestones, "add_milestone", AsyncMock())
    interaction = press()
    await child(view, milestones.MilestoneAddButton).callback(interaction)
    interaction.response.send_message.assert_awaited_once_with(
        f"{NO} Failed to create milestone.", ephemeral=True
    )


async def test_the_edit_boxes(store):
    store.rows = [["", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    shown = []
    for field in ("name", "description", "threshold"):
        _, modal = await submit(view, field, "Hero" if field != "threshold" else "5")
        box = modal.input
        shown.append(
            (
                modal.title,
                box.label,
                box.style,
                box.placeholder,
                box.default,
                box.required,
                box.max_length,
            )
        )
    short, long = discord.TextStyle.short, discord.TextStyle.paragraph
    assert shown == [
        ("Edit Name", "Role ID / Title", short, "Hero", "Hero", True, 100),
        ("Edit Description", "Description", long, "Enter new value", "", False, 200),
        ("Edit Threshold", "Mora/Sigils Threshold", short, "5", "5", True, 10),
    ]


@pytest.mark.parametrize("text", ["abc", "0", "-3", "", "0.4"])
async def test_a_bad_threshold_is_turned_down(store, text):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    interaction, _ = await submit(view, "threshold", text)
    sent = interaction.response.send_message.await_args.kwargs
    assert (
        sent["embed"].description == f"{NO} Threshold must be a valid positive integer."
    )
    assert sent["embed"].color == discord.Color.red() and sent["ephemeral"] is True
    assert store.calls == [] and store.rows[0][2] == 5
    interaction.response.edit_message.assert_not_awaited()


async def test_a_new_threshold_rechecks_holders(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    store.result = {"awarded": 2, "revoked": 3}
    view, _, _ = await detail(store, "Hero")
    interaction, _ = await submit(view, "threshold", " 2.5K ")
    assert store.calls == [
        ("threshold", "Hero", 2500),
        ("sync", ["d", "Hero", 2500, "guild_mora"]),
    ]
    edited = interaction.response.edit_message.await_args.kwargs
    assert edited["embed"].fields[0].value == f"{MORA} `2,500`"
    assert edited["view"].parent_message is None
    interaction.followup.send.assert_awaited_once_with(
        f"{config.YES_EMOTE} Milestone rechecked: awarded to 2 member(s) and removed from 3 member(s) who no longer qualify.",
        ephemeral=True,
    )


async def test_nothing_is_said_when_nobody_changed(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    interaction, _ = await submit(view, "threshold", "9")
    interaction.response.edit_message.assert_awaited_once()
    interaction.followup.send.assert_not_awaited()


async def test_a_failed_recheck_notice_is_ignored(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    store.result = {"awarded": 0, "revoked": 1}
    view, _, _ = await detail(store, "Hero")
    interaction = press()
    interaction.followup.send.side_effect = discord.HTTPException(
        MagicMock(status=500), "x"
    )
    await submit(view, "threshold", "9", interaction)
    assert interaction.followup.send.await_args.args == (
        f"{config.YES_EMOTE} Milestone rechecked: removed from 1 member(s) who no longer qualify.",
    )


@pytest.mark.parametrize(
    "text, reason",
    [
        ("  ", "Name cannot be empty."),
        ("501", "That role ID doesn't exist in this server!"),
    ],
)
async def test_a_bad_name_is_turned_down(store, text, reason):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    interaction, _ = await submit(view, "name", text)
    sent = interaction.response.send_message.await_args.kwargs
    assert sent["embed"].description == f"{NO} {reason}" and sent["ephemeral"] is True
    assert store.calls == []


async def test_renaming_carries_holders_over(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    interaction, _ = await submit(view, "name", " 500 ")
    assert store.calls == [
        ("field", "Hero", "name", "500"),
        ("migrate", "Hero", "500"),
        ("sync", ["d", "500", 5, "guild_mora"]),
    ]
    edited = interaction.response.edit_message.await_args.kwargs
    assert edited["embed"].title == "Milestone: Knight"
    assert child(edited["view"], milestones.DeleteMilestoneButton).item_name == "500"


async def test_the_description_is_saved_without_a_recheck(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    interaction, _ = await submit(view, "description", " braver ")
    await submit(view, "description", "")
    assert store.calls == [
        ("field", "Hero", "description", "braver"),
        ("field", "Hero", "description", "Reached milestone"),
    ]
    assert interaction.response.edit_message.await_args.kwargs["embed"].description == (
        "> **Description:** braver"
    )


async def test_an_edit_to_a_deleted_milestone_says_nothing(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    store.rows = []
    interaction, _ = await submit(view, "description", "x")
    interaction.response.edit_message.assert_not_awaited()
    interaction.response.send_message.assert_not_awaited()


async def test_changing_the_currency_rechecks_holders(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    menu = child(view, milestones.MilestoneCurrencySelect)
    menu._values = ["global_sigils"]
    interaction = press()
    await menu.callback(interaction)
    assert store.calls == [
        ("field", "Hero", "currency_type", "global_sigils"),
        ("sync", ["d", "Hero", 5, "global_sigils"]),
    ]
    edited = interaction.response.edit_message.await_args.kwargs
    sigil = config.CURRENCY_INFO["global_sigils"]["emoji"]
    assert edited["embed"].fields[0].value == f"{sigil} `5`"
    interaction.followup.send.assert_not_awaited()
    store.rows, store.calls = [], []
    again = press()
    await menu.callback(again)
    assert len(store.calls) == 1
    again.response.edit_message.assert_not_awaited()


async def test_deleting_asks_first_then_takes_it_from_everyone(store):
    store.rows = [["d", "Hero", 5, "guild_mora"], ["d", "Sage", 9, "guild_mora"]]
    store.result = {"awarded": 0, "revoked": 4}
    view, _, _ = await detail(store, "Hero")
    ask = press()
    await child(view, milestones.DeleteMilestoneButton).callback(ask)
    sent = ask.response.send_message.await_args.kwargs
    assert sent["embed"].description == (
        "Are you sure you want to delete this milestone? This cannot be undone."
    )
    assert sent["embed"].color == discord.Color.red() and sent["ephemeral"] is True
    confirm = sent["view"]
    assert confirm.timeout == 30
    assert [(b.label, b.style) for b in confirm.children] == [
        ("Yes", discord.ButtonStyle.danger)
    ]
    interaction = press()
    await confirm.confirm_delete.callback(interaction)
    assert [row[1] for row in store.rows] == ["Sage"]
    assert store.calls == [("revoke", "Hero")]
    interaction.response.edit_message.assert_awaited_once_with(
        content=f"{config.YES_EMOTE} Milestone has been deleted. Removed it from 4 member(s) who had it.",
        embed=None,
        view=None,
    )
    back = ask.message.edit.await_args.kwargs
    assert [f.name for f in back["embed"].fields] == [f"1ㅤ {MORA} 9 • Sage"]
    assert isinstance(back["view"], milestones.MilestoneView)


async def test_deleting_when_nobody_held_it_and_the_list_is_gone(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    ask = press()
    ask.message.edit.side_effect = discord.NotFound(MagicMock(status=404), "gone")
    await child(view, milestones.DeleteMilestoneButton).callback(ask)
    interaction = press()
    confirm = ask.response.send_message.await_args.kwargs["view"]
    await confirm.confirm_delete.callback(interaction)
    interaction.response.edit_message.assert_awaited_once_with(
        content=f"{config.YES_EMOTE} Milestone has been deleted.", embed=None, view=None
    )


async def test_an_unfinished_milestone_cannot_be_left(store):
    store.rows = [["", "_new_1234", 0, "weird"]]
    view, _, _ = await detail(store, "_new_1234")
    interaction = press()
    await child(view, milestones.BackToMilestonesButton).callback(interaction)
    sent = interaction.response.send_message.await_args.kwargs
    assert sent["embed"].title == "Cannot return to milestones yet"
    assert sent["embed"].description == (
        f"{NO} Reward title/role ID is required\n"
        f"{NO} Threshold must be a positive number\n"
        f"{NO} Currency type is invalid"
    )
    assert sent["embed"].color == discord.Color.red() and sent["ephemeral"] is True
    assert store.calls == []
    interaction.response.edit_message.assert_not_awaited()


async def test_going_back_fills_the_description_and_rechecks(store):
    store.rows = [["  ", "Hero", "7", "guild_sigils"]]
    store.result = {"awarded": 1, "revoked": 0}
    view, _, _ = await detail(store, "Hero")
    interaction = press()
    await child(view, milestones.BackToMilestonesButton).callback(interaction)
    assert store.calls == [
        ("field", "Hero", "description", "Reached milestone"),
        ("sync", ["Reached milestone", "Hero", 7, "guild_sigils"]),
    ]
    edited = interaction.response.edit_message.await_args.kwargs
    assert edited["embed"].title == "Mondstadt's Server Milestones"
    assert edited["view"].message == "message"
    interaction.followup.send.assert_awaited_once_with(
        f"{config.YES_EMOTE} Milestone saved and awarded to 1 existing qualifying member(s).",
        ephemeral=True,
    )


async def test_going_back_from_a_deleted_milestone_shows_the_list(store):
    store.rows = [["d", "Hero", 5, "guild_mora"]]
    view, _, _ = await detail(store, "Hero")
    store.rows = []
    interaction = press()
    await child(view, milestones.BackToMilestonesButton).callback(interaction)
    assert store.calls == []
    assert interaction.response.edit_message.await_args.kwargs["embed"].title == (
        "This server has no milestones set up yet."
    )
    interaction.followup.send.assert_not_awaited()
