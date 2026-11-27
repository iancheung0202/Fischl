from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events import config, shop

GUILD = 10
INFO = config.CURRENCY_INFO
MORA = INFO["guild_mora"]["emoji"]
NO = config.NO_EMOTE
REPLY = config.REPLY_EMOTE
HEAD = (
    f"{REPLY} *To check your balances and inventory, use `/mora`.*\n"
    f"{REPLY} *To purchase an item, use `/buy`.*\n"
    f"{REPLY} *A 🔄 emoji indicates that the title can be purchased multiple times.*\n"
)
PLACES = {"name": 0, "description": 1, "multiple": 3, "currency_type": 5}


class Store:
    """Stands in for the stored rewards; `calls` lists every write that was asked for."""

    def __init__(self):
        self.rows = []
        self.calls = []
        self.due = 0
        self.reads = 0

    def add(self, name, description="perk", cost=100, multiple=False, stock=-1, **more):
        currency = more.get("currency", "guild_mora")
        self.rows.append(
            [name, description, cost, multiple, stock, currency, None, None]
        )

    def row(self, name):
        return next((row for row in self.rows if str(row[0]) == name), None)

    async def get_shop_items(self, pool, gid):
        self.reads += 1
        return [list(row) for row in self.rows]

    async def get_shop_item_by_name(self, pool, gid, name):
        row = self.row(name)
        return list(row) if row else None

    async def add_shop_item(self, pool, gid, *values):
        self.calls.append(("add", pool, gid, *values))
        self.rows.append([*values, None, None])

    async def update_shop_item_field(self, pool, gid, name, field, value):
        self.calls.append(("field", pool, gid, name, field, value))
        if self.row(name):
            self.row(name)[PLACES[field]] = value

    async def update_shop_item_cost(self, pool, gid, name, value):
        self.calls.append(("cost", pool, gid, name, value))
        self.row(name)[2] = value

    async def update_shop_item_stock_by_name(self, pool, gid, name, value):
        self.calls.append(("stock", pool, gid, name, value))
        self.row(name)[4] = value

    async def add_pending_edit(self, pool, gid, name, change, when):
        self.calls.append(("pending", pool, gid, name, change, when))
        self.row(name)[6:8] = [change, when]

    async def remove_shop_item_by_name(self, pool, gid, name):
        self.calls.append(("remove", pool, gid, name))
        self.rows = [row for row in self.rows if str(row[0]) != name]

    async def process_pending_stock_edits(self, pool, gid):
        self.calls.append(("process", pool, gid))
        return self.due


@pytest.fixture
def store(monkeypatch):
    store = Store()
    for name in dir(Store):
        if not name.startswith("_") and hasattr(shop, name):
            monkeypatch.setattr(shop, name, getattr(store, name))
    monkeypatch.setattr(shop.time, "time", lambda: 1234.5)
    return store


AUTHOR = SimpleNamespace(id=20, guild_permissions=SimpleNamespace(administrator=True))
ROLE = SimpleNamespace(id=500, name="Knight", mention="<@&500>")


def press(user=AUTHOR, admin=True):
    """Gives an interaction from a member of a server that has one role."""
    interaction = MagicMock()
    interaction.guild.id = GUILD
    interaction.guild.name = "Mondstadt"
    interaction.guild.get_role = lambda role_id: ROLE if role_id == 500 else None
    interaction.client.pool = "pool"
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
    """Runs /shop; gives the interaction, the embed and the view."""
    interaction = press(admin=admin)
    cog = shop.Shop(MagicMock())
    await cog.shop.callback(cog, interaction)
    sent = interaction.followup.send.await_args.kwargs
    return interaction, sent["embed"], sent["view"]


def child(view, kind):
    return next(item for item in view.children if isinstance(item, kind))


def button(view, label):
    return next(item for item in view.children if getattr(item, "label", "") == label)


def labels(view):
    return [
        getattr(item, "label", None) or getattr(item, "placeholder", None)
        for item in view.children
    ]


async def detail(store, name):
    """Opens the screen of one reward; gives the interaction, the embed and the view."""
    _, _, view = await opened(store)
    select = child(view, shop.ShopItemSelect)
    select._values = [name]
    interaction = press()
    await select.callback(interaction)
    shown = interaction.response.edit_message.await_args.kwargs
    return interaction, shown["embed"], shown["view"]


async def submit(store, name, field, text, when=None):
    """Types `text` into the box of one field and sends it; gives the interaction."""
    _, _, view = await detail(store, name)
    opener = press()
    await button(view, shop.FIELDS[field][0]).callback(opener)
    modal = opener.response.send_modal.await_args.args[0]
    modal.input._value = text
    if when is not None:
        modal.time_input._value = when
    interaction = press()
    await modal.on_submit(interaction)
    return interaction


def refusal(interaction):
    """Gives the text and title of the red embed the member was sent."""
    call = interaction.response.send_message.await_args
    embed = call.kwargs["embed"]
    assert call.kwargs["ephemeral"] is True
    assert embed.color == discord.Color.red()
    return embed.description, embed.title


# The small helpers


@pytest.mark.parametrize(
    "text, cost",
    [("1500", 1500), ("1.5k", 1500), (" 2M ", 2_000_000), ("1b", 10**9), ("3t", 3 * 10**12), ("0.4", 0), ("-5", -5), ("1e3", 1000)],  # fmt: skip
)
def test_a_cost_is_read_with_its_letter(text, cost):
    assert shop.parse_cost(text) == cost


@pytest.mark.parametrize("text, error", [("", IndexError), (" ", IndexError), ("k", ValueError), ("abc", ValueError), ("inf", OverflowError)])  # fmt: skip
def test_a_cost_that_cannot_be_read_raises(text, error):
    with pytest.raises(error):
        shop.parse_cost(text)


def test_an_unknown_currency_shows_as_mora():
    assert shop.get_currency_display("global_sigils") == INFO["global_sigils"]["emoji"]
    assert shop.get_currency_display("gems") == MORA


def test_the_command_keeps_its_name_and_description():
    command = shop.Shop.shop
    assert command.name == "shop"
    assert command.description == "View the guild shop (Admins can edit here too)"
    assert command.parameters == []


# The list


async def test_an_empty_shop_says_so(store):
    interaction, embed, view = await opened(store)
    interaction.response.defer.assert_awaited_once_with(thinking=True)
    assert embed.to_dict() == {
        "title": "This server has no purchasable items.",
        "footer": {"text": "Page 1 of 1"},
        "type": "rich",
        "flags": 0,
    }
    assert view.message == "message"
    assert labels(view)[4:] == ["Add Reward", "Choose the Sorting", "Filter by currency..."]  # fmt: skip


async def test_the_list_shows_each_kind_of_reward(store):
    store.add("Hero", "a title", 2500, True, 3)
    store.add("500", "a role", "90", False, 0, currency="global_sigils")
    store.add("999", "gone", 10)
    _, embed, view = await opened(store)
    sigil = INFO["global_sigils"]["emoji"]
    assert embed.title == "Mondstadt's Server Shop"
    assert embed.description == HEAD
    assert embed.color == discord.Color.gold()
    assert embed.footer.text == "Page 1 of 1 • Sorted by Cost in Descending order"
    assert [(f.name, f.value, f.inline) for f in embed.fields] == [
        (f"1ㅤ {MORA} 2,500 • Hero 🔄", "> **Description:** a title\n> **Remaining:** `3`", False),  # fmt: skip
        (f"2ㅤ {sigil} 90 • Knight ", f"> **Role:** <@&500>\n> **Description:** a role\n> **Remaining:** {config.NO_STOCK_EMOTE} `0`", False),  # fmt: skip
        (f"3ㅤ {MORA} 10 • Unknown Role ", "> **Role:** N/A\n> **Description:** gone", False),  # fmt: skip
    ]
    assert view.timeout == 300


async def test_the_list_holds_five_rewards_a_page(store):
    for number in range(11):
        store.add(f"Item{number:02}", cost=number + 1)
    _, embed, view = await opened(store)
    assert [len(page.fields) for page in view.pages] == [5, 5, 1]
    assert embed.fields[0].name == f"1ㅤ {MORA} 11 • Item10 "
    assert view.pages[2].fields[0].name == f"11ㅤ {MORA} 1 • Item00 "
    assert view.pages[1].footer.text == "Sorted by Cost in Descending order"


async def test_the_menus_are_built_as_before(store):
    store.add("Hero")
    _, _, view = await opened(store)
    sort = child(view, shop.SortSelection)
    assert sort.custom_id == "sortselection"
    assert sort.placeholder == "Choose the Sorting"
    assert [(o.label, str(o.emoji), o.default) for o in sort.options] == [
        (label, emoji, label == "sort by cost (high to low)")
        for label, emoji in config.SHOP_SORT_OPTIONS
    ]
    currency = child(view, shop.CurrencyFilterSelect)
    assert currency.custom_id == "currencyfilter"
    assert currency.placeholder == "Filter by currency..."
    assert [(o.label, str(o.emoji), o.default) for o in currency.options] == [
        ("All currencies", config.SHOP_CURRENCY_FILTERS[0][1], True),
        *[(info["filter_label"], info["emoji"], False) for info in INFO.values()],
    ]


@pytest.mark.parametrize(
    "choice, names, footer",
    [
        ("sort by cost (low to high)", ["beta", "Knight", "Cat"], "Cost in Ascending"),
        ("sort by cost (high to low)", ["Cat", "Knight", "beta"], "Cost in Descending"),
        ("sort by name (a-z)", ["beta", "Cat", "Knight"], "Name in Ascending"),
        ("sort by name (z-a)", ["Knight", "Cat", "beta"], "Name in Descending"),
        ("something else", ["Cat", "Knight", "beta"], "Cost in Descending"),
    ],
)  # fmt: skip
async def test_sorting_reorders_the_list(store, choice, names, footer):
    store.add("Cat", cost=300)
    store.add("beta", cost="20")
    store.add("500", cost=100)
    _, _, view = await opened(store)
    view.currency_filter = "guild_mora"
    interaction = press()
    interaction.data = {"values": [choice]}
    await child(view, shop.SortSelection).callback(interaction)
    shown = interaction.response.edit_message.await_args.kwargs
    assert [f.name.split("• ")[1].strip() for f in shown["embed"].fields] == names
    assert shown["embed"].footer.text == f"Page 1 of 1 • Sorted by {footer} order"
    assert shown["view"].message == "message"
    assert shown["view"].currency_filter == "guild_mora"
    picked = [o.label for o in child(shown["view"], shop.SortSelection).options if o.default]  # fmt: skip
    assert picked == ([choice] if choice in shop.SORTS else [])


async def test_filtering_keeps_one_currency_and_resets_the_sort(store):
    store.add("Hero", cost=5)
    store.add("Gem", cost=7, currency="guild_sigils")
    _, _, view = await opened(store)
    select = child(view, shop.CurrencyFilterSelect)
    select._values = [INFO["guild_sigils"]["filter_label"]]
    interaction = press()
    await select.callback(interaction)
    shown = interaction.response.edit_message.await_args.kwargs
    assert [f.name for f in shown["embed"].fields] == [f"1ㅤ {INFO['guild_sigils']['emoji']} 7 • Gem "]  # fmt: skip
    assert shown["view"].currency_filter == "guild_sigils"
    assert shown["view"].message == "message"
    assert [o.default for o in child(shown["view"], shop.CurrencyFilterSelect).options] == [False, False, False, True, False]  # fmt: skip
    assert [r[0] for r in shown["view"].items] == ["Gem"]

    select._values = [INFO["global_mora"]["filter_label"]]
    interaction = press()
    await select.callback(interaction)
    shown = interaction.response.edit_message.await_args.kwargs
    assert shown["embed"].title == f"No items found costing {INFO['global_mora']['emoji']}."  # fmt: skip
    assert shown["view"].items == []

    select._values = ["All currencies"]
    interaction = press()
    await select.callback(interaction)
    assert interaction.response.edit_message.await_args.kwargs["view"].currency_filter == "all"  # fmt: skip


async def test_due_stock_changes_are_applied_first_and_printed(store, capsys):
    store.due = 2
    await opened(store)
    assert store.calls == [("process", "pool", GUILD)]
    assert capsys.readouterr().out == "Processed 2 scheduled stock edits for guild 10\n"
    store.due = 0
    await opened(store)
    assert capsys.readouterr().out == ""


async def test_members_get_no_edit_controls(store):
    store.add("Hero")
    _, _, view = await opened(store, admin=False)
    assert labels(view)[4:] == ["Choose the Sorting", "Filter by currency..."]
    assert view.is_admin is False


async def test_admins_pick_from_the_rewards_on_the_page(store):
    store.add("x" * 91, cost=9000, stock=4)
    store.add("500", cost=800, currency="global_mora")
    store.add("999", cost=70)
    for number in range(4):
        store.add(f"Item{number}", cost=number + 1)
    _, _, view = await opened(store)
    select = child(view, shop.ShopItemSelect)
    assert (select.placeholder, select.row) == ("Select an item to edit (page 1)...", 3)
    assert [(o.label, o.description, str(o.emoji), o.value) for o in select.options[:3]] == [
        (f"9,000 • {'x' * 87}...", "Stock: 4", MORA, "x" * 91),
        ("800 • Knight", "Stock: ∞", INFO["global_mora"]["emoji"], "500"),
        ("70 • Unknown Role", "Stock: ∞", MORA, "999"),
    ]  # fmt: skip
    assert len(select.options) == 5
    add = button(view, "Add Reward")
    assert (add.style, add.row) == (discord.ButtonStyle.green, 0)

    interaction = press()
    await view.next_button.callback(interaction)
    select = child(view, shop.ShopItemSelect)
    assert select.placeholder == "Select an item to edit (page 2)..."
    assert [o.value for o in select.options] == ["Item1", "Item0"]
    assert labels(view).count("Add Reward") == 1


async def test_someone_else_cannot_use_the_list(store):
    _, _, view = await opened(store)
    other = press(SimpleNamespace(id=21, guild_permissions=SimpleNamespace()))
    assert await view.interaction_check(other) is False
    other.response.send_message.assert_awaited_once_with(
        f"{NO} You are not the author of this command", ephemeral=True
    )
    assert await view.interaction_check(press()) is True


# One reward


async def test_picking_a_reward_opens_its_screen(store):
    store.add("Hero", "a title", "2500", True, 3, currency="global_sigils")
    interaction, embed, view = await detail(store, "Hero")
    assert embed.to_dict() == {
        "title": "Reward: Hero",
        "description": "> **Description:** a title",
        "color": discord.Color.gold().value,
        "fields": [
            {"name": "Cost", "value": f"{INFO['global_sigils']['emoji']} `2,500`", "inline": True},
            {"name": "Stock", "value": "`3`", "inline": True},
            {"name": "Multiple Purchases", "value": "Yes 🔄", "inline": True},
        ],
        "type": "rich",
        "flags": 0,
    }  # fmt: skip
    assert view.timeout == 300
    assert view.parent_message is interaction.message
    assert [(labels(view)[i], item.row) for i, item in enumerate(view.children)] == [
        ("Edit Name", 0),
        ("Edit Description", 0),
        ("Edit Cost", 0),
        ("Select a currency...", 1),
        ("Toggle Allow Multiple", 2),
        ("Edit Stock", 2),
        ("Delete Reward", 2),
        ("Back to Shop", 2),
    ]
    styles = [item.style for item in view.children if isinstance(item, discord.ui.Button)]  # fmt: skip
    grey, red, blue = discord.ButtonStyle.secondary, discord.ButtonStyle.danger, discord.ButtonStyle.blurple  # fmt: skip
    assert styles == [grey, grey, grey, grey, grey, red, blue]
    select = child(view, shop.ShopItemCurrencySelect)
    assert [(o.label, o.value, str(o.emoji), o.default) for o in select.options] == [
        (info["label"], key, info["emoji"], key == "global_sigils")
        for key, info in INFO.items()
    ]


async def test_a_reward_screen_shows_a_role_no_perk_and_a_scheduled_change(store):
    store.add("500", "", 10)
    store.rows[0][6:8] = ["25", 1700000000.9]
    embed = shop.build_reward_detail_embed(store.rows[0], guild=press().guild)
    assert embed.title == "Reward: Knight"
    assert embed.description == "> **Role:** <@&500>\n> **Description:** > **Description:** No description provided."  # fmt: skip
    assert embed.fields[1].value == "`Unlimited`\n⏰ Scheduled: `25` <t:1700000000:R>"
    assert embed.fields[2].value == "No"
    assert shop.build_reward_detail_embed(store.rows[0]).title == "Reward: 500"
    short = shop.build_reward_detail_embed(["999", "x", 5, False, 0], guild=press().guild)  # fmt: skip
    assert (short.title, short.fields[0].value, short.fields[1].value) == ("Reward: 999", f"{MORA} `5`", "`0`")  # fmt: skip
    six = shop.build_reward_detail_embed(["Hero", "x", 5, False, 0, "global_sigils"])
    assert six.fields[0].value == f"{INFO['global_sigils']['emoji']} `5`"
    timeless = shop.build_reward_detail_embed(["Hero", "x", 5, False, 3, "guild_mora", "25", None])  # fmt: skip
    assert timeless.fields[1].value == "`3`"


async def test_a_reward_that_is_gone_cannot_be_opened(store):
    store.add("Hero")
    _, _, view = await opened(store)
    store.rows.clear()
    select = child(view, shop.ShopItemSelect)
    select._values = ["Hero"]
    interaction = press()
    await select.callback(interaction)
    interaction.response.send_message.assert_awaited_once_with(f"{NO} Item not found.", ephemeral=True)  # fmt: skip


async def test_add_reward_makes_an_empty_one_and_opens_it(store):
    _, _, view = await opened(store)
    interaction = press()
    await button(view, "Add Reward").callback(interaction)
    assert store.calls[-1] == ("add", "pool", GUILD, "_new_1234", "", "0", False, -1, "guild_mora")  # fmt: skip
    shown = interaction.response.edit_message.await_args.kwargs
    assert shown["embed"].title == "Reward: _new_1234"
    assert shown["view"].parent_message is interaction.message


async def test_add_reward_says_when_nothing_was_made(store, monkeypatch):
    _, _, view = await opened(store)
    monkeypatch.setattr(shop, "add_shop_item", AsyncMock())
    interaction = press()
    await button(view, "Add Reward").callback(interaction)
    interaction.response.send_message.assert_awaited_once_with(f"{NO} Failed to create reward.", ephemeral=True)  # fmt: skip


@pytest.mark.parametrize(
    "field, title, label, longest, required, default",
    [
        ("name", "Edit Name", "Role ID / Reward Title", 50, True, "Hero"),
        ("description", "Edit Description", "Description / Perk", 150, True, "perk"),
        ("cost", "Edit Cost", "Cost of Reward", 10, True, "100"),
        ("stock", "Edit Stock", "Stock Value", 20, False, "7"),
    ],
)
async def test_each_edit_button_opens_its_box(store, field, title, label, longest, required, default):  # fmt: skip
    store.add("Hero", stock=7)
    _, _, view = await detail(store, "Hero")
    interaction = press()
    await button(view, title).callback(interaction)
    modal = interaction.response.send_modal.await_args.args[0]
    box = modal.input
    assert modal.title == title
    assert (box.label, box.max_length, box.required) == (label, longest, required)
    assert (box.default, box.placeholder, box.style) == (default, default, discord.TextStyle.short)  # fmt: skip
    if field != "stock":
        assert modal.children == [box]
        return
    when = modal.children[1]
    assert (when.label, when.placeholder) == ("Schedule Unix Timestamp (optional)", "Leave blank to apply immediately")  # fmt: skip
    assert (when.required, when.max_length, when.style) == (False, 15, discord.TextStyle.short)  # fmt: skip


async def test_an_empty_value_shows_a_hint_in_its_box(store):
    store.add("Hero", "")
    _, _, view = await detail(store, "Hero")
    for label in ("Edit Description", "Edit Stock"):
        interaction = press()
        await button(view, label).callback(interaction)
        box = interaction.response.send_modal.await_args.args[0].input
        assert (box.default, box.placeholder) == ("", "Enter new value")


async def test_renaming_a_reward_saves_and_shows_it(store):
    store.add("Hero")
    interaction = await submit(store, "Hero", "name", "  Champion ")
    assert store.calls[-1] == ("field", "pool", GUILD, "Hero", "name", "Champion")
    shown = interaction.response.edit_message.await_args.kwargs
    assert shown["embed"].title == "Reward: Champion"
    assert shown["view"].parent_message is None
    assert shown["view"].initial_author is AUTHOR


async def test_an_empty_name_is_turned_down(store):
    store.add("Hero")
    interaction = await submit(store, "Hero", "name", "   ")
    assert refusal(interaction) == (f"{NO} Name cannot be empty.", None)
    assert [c for c in store.calls if c[0] != "process"] == []


async def test_a_description_may_be_emptied(store):
    store.add("Hero")
    interaction = await submit(store, "Hero", "description", " ")
    assert store.calls[-1] == ("field", "pool", GUILD, "Hero", "description", "")
    assert interaction.response.edit_message.await_count == 1


async def test_a_cost_is_saved_as_text(store):
    store.add("Hero")
    interaction = await submit(store, "Hero", "cost", "2.5k")
    assert store.calls[-1] == ("cost", "pool", GUILD, "Hero", "2500")
    assert interaction.response.edit_message.await_args.kwargs["embed"].fields[0].value == f"{MORA} `2,500`"  # fmt: skip


@pytest.mark.parametrize("text", ["0", "-5", "abc", "", "0.4", "k"])
async def test_a_bad_cost_is_turned_down(store, text):
    store.add("Hero")
    interaction = await submit(store, "Hero", "cost", text)
    assert refusal(interaction) == (f"{NO} Cost must be a valid positive integer.", None)  # fmt: skip
    assert store.row("Hero")[2] == 100


async def test_a_cost_too_large_to_read_raises(store):
    store.add("Hero")
    with pytest.raises(OverflowError):
        await submit(store, "Hero", "cost", "inf")


@pytest.mark.parametrize("text, stock", [("12", 12), ("0", 0), ("", -1), ("-1", -1), (" 4 ", 4)])  # fmt: skip
async def test_stock_is_set_at_once_without_a_time(store, text, stock):
    store.add("Hero", stock=7)
    interaction = await submit(store, "Hero", "stock", text, "  ")
    assert store.calls[-1] == ("stock", "pool", GUILD, "Hero", stock)
    shown = interaction.response.edit_message.await_args.kwargs
    assert shown["embed"].fields[1].value == ("`Unlimited`" if stock == -1 else f"`{stock}`")  # fmt: skip
    assert shown["view"].parent_message is None


@pytest.mark.parametrize("text", ["-2", "abc", "1.5"])
async def test_a_bad_stock_is_turned_down(store, text):
    store.add("Hero", stock=7)
    interaction = await submit(store, "Hero", "stock", text, "1800000000")
    assert refusal(interaction) == (f"{NO} Stock must be -1 (unlimited) or a non-negative integer.", None)  # fmt: skip
    assert [c for c in store.calls if c[0] != "process"] == []


async def test_stock_with_a_time_is_scheduled_as_typed(store):
    store.add("Hero", stock=7)
    interaction = await submit(store, "Hero", "stock", "", " 1800000000 ")
    assert store.calls[-1] == ("pending", "pool", GUILD, "Hero", "", 1800000000)
    assert store.row("Hero")[4] == 7
    interaction = await submit(store, "Hero", "stock", "25", "1800000000")
    assert store.calls[-1] == ("pending", "pool", GUILD, "Hero", "25", 1800000000)
    value = interaction.response.edit_message.await_args.kwargs["embed"].fields[1].value
    assert value == "`7`\n⏰ Scheduled: `25` <t:1800000000:R>"


@pytest.mark.parametrize("when", ["soon", "12.5"])
async def test_a_bad_time_is_turned_down(store, when):
    store.add("Hero", stock=7)
    interaction = await submit(store, "Hero", "stock", "25", when)
    assert refusal(interaction) == (f"{NO} Invalid timestamp. Provide a valid Unix timestamp.", None)  # fmt: skip
    assert [c for c in store.calls if c[0] != "process"] == []


async def test_nothing_is_shown_when_the_reward_is_gone_after_an_edit(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    opener = press()
    await button(view, "Edit Description").callback(opener)
    modal = opener.response.send_modal.await_args.args[0]
    modal.input._value = "new"
    store.rows.clear()
    interaction = press()
    await modal.on_submit(interaction)
    interaction.response.edit_message.assert_not_awaited()
    interaction.response.send_message.assert_not_awaited()


async def test_the_currency_menu_saves_the_choice(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    select = child(view, shop.ShopItemCurrencySelect)
    select._values = ["global_sigils"]
    interaction = press()
    await select.callback(interaction)
    assert store.calls[-1] == ("field", "pool", GUILD, "Hero", "currency_type", "global_sigils")  # fmt: skip
    shown = interaction.response.edit_message.await_args.kwargs
    assert shown["embed"].fields[0].value == f"{INFO['global_sigils']['emoji']} `100`"
    assert shown["view"].parent_message is None


async def test_toggle_switches_multiple_purchases(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    interaction = press()
    await button(view, "Toggle Allow Multiple").callback(interaction)
    assert store.calls[-1] == ("field", "pool", GUILD, "Hero", "multiple", True)
    assert interaction.response.edit_message.await_args.kwargs["embed"].fields[2].value == "Yes 🔄"  # fmt: skip
    await button(view, "Toggle Allow Multiple").callback(press())
    assert store.calls[-1] == ("field", "pool", GUILD, "Hero", "multiple", False)


async def test_toggle_reads_the_name_off_the_screen_when_it_has_none(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    toggle = button(view, "Toggle Allow Multiple")
    toggle.item_name = None
    interaction = press()
    interaction.message.embeds = [SimpleNamespace(title="Reward: Hero")]
    await toggle.callback(interaction)
    assert store.calls[-1] == ("field", "pool", GUILD, "Hero", "multiple", True)

    interaction = press()
    interaction.message.embeds = [SimpleNamespace(title="Reward: Gone")]
    await toggle.callback(interaction)
    interaction.response.send_message.assert_awaited_once_with(f"{NO} Reward not found.", ephemeral=True)  # fmt: skip


async def test_delete_asks_first(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    interaction = press()
    await button(view, "Delete Reward").callback(interaction)
    asked = interaction.response.send_message.await_args.kwargs
    assert refusal(interaction) == ("Are you sure you want to delete **Hero**? This cannot be undone.", None)  # fmt: skip
    confirm = asked["view"]
    assert confirm.timeout == 30
    assert confirm.parent_message is interaction.message
    (yes,) = confirm.children
    assert (yes.label, yes.style) == ("Yes", discord.ButtonStyle.danger)
    assert store.row("Hero")

    delete = button(view, "Delete Reward")
    delete.item_name = None
    interaction = press()
    interaction.message.embeds = [SimpleNamespace(title="Reward: Other")]
    await delete.callback(interaction)
    assert interaction.response.send_message.await_args.kwargs["view"].item_name == "Other"  # fmt: skip


async def confirming(store):
    """Opens the Yes button for Hero; gives the confirm view and the reward's message."""
    store.add("Hero")
    store.add("Zed")
    _, _, view = await detail(store, "Hero")
    interaction = press()
    await button(view, "Delete Reward").callback(interaction)
    return interaction.response.send_message.await_args.kwargs["view"], interaction.message  # fmt: skip


async def test_yes_deletes_and_puts_the_list_back(store):
    confirm, parent = await confirming(store)
    interaction = press()
    await confirm.children[0].callback(interaction)
    assert store.calls[-1] == ("remove", "pool", GUILD, "Hero")
    interaction.response.edit_message.assert_awaited_once_with(
        content=f"{config.YES_EMOTE} Reward **Hero** has been deleted.", embed=None, view=None  # fmt: skip
    )
    put = parent.edit.await_args.kwargs
    assert [f.name for f in put["embed"].fields] == [f"1ㅤ {MORA} 100 • Zed "]
    assert isinstance(put["view"], shop.ShopView)
    assert put["view"].initial_author is AUTHOR
    assert put["view"].is_admin is True
    assert put["view"].message is None


@pytest.mark.parametrize("error", [discord.NotFound, discord.HTTPException])
async def test_yes_ignores_a_list_that_cannot_be_put_back(store, error):
    confirm, parent = await confirming(store)
    parent.edit.side_effect = error(MagicMock(status=404), "gone")
    await confirm.children[0].callback(press())
    assert store.row("Hero") is None
    confirm.parent_message = None
    await confirm.children[0].callback(press())


async def test_back_returns_to_the_list(store, capsys):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    store.due = 1
    interaction = press(admin=False)
    await button(view, "Back to Shop").callback(interaction)
    assert store.calls[-1] == ("process", "pool", GUILD)
    assert capsys.readouterr().out == "Processed 1 scheduled stock edits for guild 10\n"
    shown = interaction.response.edit_message.await_args.kwargs
    assert shown["embed"].footer.text == "Page 1 of 1 • Sorted by Cost in Descending order"  # fmt: skip
    assert shown["view"].message == "message"
    assert shown["view"].is_admin is False
    AUTHOR.guild_permissions.administrator = True


async def test_back_is_refused_while_the_reward_is_unfinished(store):
    _, _, view = await opened(store)
    interaction = press()
    await button(view, "Add Reward").callback(interaction)
    view = interaction.response.edit_message.await_args.kwargs["view"]
    store.row("_new_1234")[5] = "gems"
    interaction = press()
    await button(view, "Back to Shop").callback(interaction)
    assert refusal(interaction) == (
        f"{NO} Reward title/role ID is required\n{NO} Description is required\n"
        f"{NO} Cost must be a positive number\n{NO} Currency type is invalid",
        "Cannot return to shop yet",
    )
    assert ("process", "pool", GUILD) not in store.calls[1:]
    interaction.response.edit_message.assert_not_awaited()


@pytest.mark.parametrize(
    "row, errors",
    [
        (["Hero", "perk", "abc", False, -1, "guild_mora"], ["Cost must be a positive number"]),
        (["Hero", " ", None, False, -1], ["Description is required", "Cost must be a positive number"]),
        ([" ", "perk", "5", False, -1, "global_sigils"], ["Reward title/role ID is required"]),
        ([500, "perk", 5, False, -1, "global_mora"], []),
    ],
)  # fmt: skip
def test_what_a_reward_still_needs(row, errors):
    assert shop.missing_parts(row) == errors


async def test_back_goes_through_when_the_reward_is_gone(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    store.rows.clear()
    interaction = press()
    await button(view, "Back to Shop").callback(interaction)
    assert interaction.response.edit_message.await_args.kwargs["embed"].title == "This server has no purchasable items."  # fmt: skip


async def test_someone_else_cannot_use_a_reward_screen(store):
    store.add("Hero")
    _, _, view = await detail(store, "Hero")
    other = press(SimpleNamespace(id=21, guild_permissions=SimpleNamespace()))
    assert await view.interaction_check(other) is False
    other.response.send_message.assert_awaited_once_with(
        f"{NO} You are not the author of this command", ephemeral=True
    )
    assert await view.interaction_check(press()) is True


async def test_a_reward_screen_expires_on_the_list_message(store):
    store.add("Hero")
    interaction, _, view = await detail(store, "Hero")
    await view.on_timeout()
    (expired,) = view.children
    assert (expired.label, expired.style, expired.disabled) == ("Expired", discord.ButtonStyle.grey, True)  # fmt: skip
    assert str(expired.emoji) == "<a:clock:1382887924273774754>"
    interaction.message.edit.assert_awaited_once_with(view=view)

    interaction.message.edit.side_effect = discord.NotFound(MagicMock(status=404), "x")
    await view.on_timeout()
    view.parent_message = None
    await view.on_timeout()


async def test_the_shop_reads_its_rewards_once_per_screen(store):
    store.add("Hero")
    await detail(store, "Hero")
    assert store.reads == 1
    await submit(store, "Hero", "cost", "5")
    assert store.reads == 2
