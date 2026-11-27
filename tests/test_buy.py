import asyncio
import datetime
import time
from types import SimpleNamespace

import discord
import pytest
from discord import app_commands

from commands.Events import buy, config, event, quests, trackData

GUILD = 10
USER = 555
MORA = config.CURRENCY_INFO["guild_mora"]["emoji"]
SIGILS = config.CURRENCY_INFO["guild_sigils"]["emoji"]


class Shop:
    """Stands in for the shop, balances and inventory; `calls` lists what was asked."""

    def __init__(self):
        self.items = []
        self.calls = []
        self.discount = 0
        self.balance = 10**6
        self.inventory = []
        self.pending = 0
        self.history = []
        self.queries = []

    def add(self, name, cost=100, multiple=True, stock=-1, currency="guild_mora"):
        self.items.append([name, "about", cost, multiple, stock, currency, None, None])

    async def get_shop_items(self, pool, gid):
        return [list(item) for item in self.items]

    async def get_shop_item_by_name(self, pool, gid, name):
        return next((list(item) for item in self.items if item[0] == name), None)

    async def get_shop_discount(self, pool, gid, uid):
        return self.discount

    async def balance_of(self, *args):
        self.calls.append(("balance", args[1:]))
        return self.balance

    async def subtract(self, *args):
        self.calls.append(("pay", args[1:]))
        return True

    async def get_user_inventory(self, pool, uid, gid):
        return self.inventory

    async def add_inventory_item(self, pool, *args, **kwargs):
        self.calls.append(("item", args, kwargs))

    async def update_shop_item_stock_by_name(self, pool, gid, name, stock):
        self.calls.append(("stock", name, stock))

    async def process_pending_stock_edits(self, pool, gid):
        return self.pending

    async def update_quest(self, uid, gid, channel, progress, client):
        self.calls.append(("quest", progress))

    async def add_xp(self, uid, gid, xp, client):
        self.calls.append(("xp", xp))
        return 1, 5, 5 + xp

    async def check_tier_rewards(self, **kwargs):
        self.calls.append(("tiers", kwargs["old_xp"], kwargs["new_xp"]))
        return discord.Embed(title="free"), None


class Conn:
    def __init__(self, shop):
        self.shop = shop

    async def fetch(self, query, *args):
        self.shop.queries.append((query, args))
        return self.shop.history

    async def execute(self, query, *args):
        self.shop.queries.append((query, args))
        self.shop.calls.append(("link", args))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class TierView(discord.ui.View):
    def __init__(self, free, elite):
        super().__init__()
        self.embeds = (free, elite)


@pytest.fixture
def shop(monkeypatch):
    shop = Shop()
    for name in (
        "get_shop_items",
        "get_shop_item_by_name",
        "get_shop_discount",
        "get_user_inventory",
        "add_inventory_item",
        "update_shop_item_stock_by_name",
        "process_pending_stock_edits",
    ):
        monkeypatch.setattr(buy, name, getattr(shop, name))
    for name in (
        "get_guild_mora",
        "get_total_mora",
        "get_sigils_balance",
        "get_global_sigils_balance",
    ):
        monkeypatch.setattr(buy, name, shop.balance_of)
    for name in (
        "subtractGuildMora",
        "subtract_global_mora",
        "subtract_guild_sigils",
        "subtract_global_sigils",
    ):
        monkeypatch.setattr(buy, name, shop.subtract)
    monkeypatch.setattr(buy, "TierRewardsView", TierView)
    monkeypatch.setattr(quests, "update_quest", shop.update_quest)
    monkeypatch.setattr(event, "add_xp", shop.add_xp)
    monkeypatch.setattr(trackData, "check_tier_rewards", shop.check_tier_rewards)
    monkeypatch.setattr(buy, "global_purchase_queue", asyncio.Queue())
    return shop


class Interaction:
    """A member's command or button press; `out` lists what the bot answered."""

    def __init__(self, shop, user_id=USER, guild_id=GUILD, age=0):
        self.out = []
        self.roles = {777: SimpleNamespace(id=777, name="Knight", mention="<@&777>")}
        self.client = SimpleNamespace(pool=SimpleNamespace(acquire=lambda: Conn(shop)))
        self.guild = SimpleNamespace(id=guild_id, name="G", get_role=self.roles.get)
        self.user = SimpleNamespace(
            id=user_id,
            name="bob",
            mention=f"<@{user_id}>",
            roles=[],
            add_roles=self.add_roles,
        )
        self.channel = SimpleNamespace(id=42)
        self.response = SimpleNamespace(
            defer=self.defer, send_message=self.send_message
        )
        self.followup = SimpleNamespace(send=self.send)
        self.message = SimpleNamespace(delete=self.delete)
        self.created_at = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(seconds=age)

    async def add_roles(self, role):
        self.user.roles.append(role)
        self.out.append(("role", role.id))

    async def defer(self, **kwargs):
        self.out.append(("defer", kwargs))

    async def send_message(self, *args, **kwargs):
        self.out.append(("send", args, kwargs))

    async def send(self, **kwargs):
        self.out.append(("followup", kwargs))
        return SimpleNamespace(id=9)

    async def edit_original_response(self, **kwargs):
        self.out.append(("edit", kwargs))

    async def original_response(self):
        return SimpleNamespace(jump_url="http://jump")

    async def delete(self):
        self.out.append(("delete",))

    def embeds(self):
        sent = [o[1] for o in self.out if o[0] in ("edit", "followup")]
        return [kwargs["embed"] for kwargs in sent if "embed" in kwargs]


async def ask(shop, item, **kwargs):
    """Runs /buy and gives the interaction with the confirmation view it sent."""
    interaction = Interaction(shop, **kwargs)
    await buy.Buy.buy.callback(buy.Buy(SimpleNamespace()), interaction, item)
    return interaction, interaction.out[-1][1].get("view")


async def purchase(shop, item, **kwargs):
    """Confirms a purchase without the queue and gives the interaction."""
    interaction = Interaction(shop, **kwargs)
    await buy.ConfirmPurchaseView(item, USER).process_purchase(interaction)
    return interaction


def test_the_command_is_unchanged():
    command = buy.Buy.buy
    assert command.name == "buy"
    assert command.description == "Purchase an item from the guild shop"
    (option,) = command.parameters
    assert (option.name, option.description, option.required) == (
        "item",
        "The item you wish to purchase",
        True,
    )


def test_a_discount_strikes_the_old_price():
    assert buy.format_discounted_price(1000, 900, 10) == (
        f"{MORA} ~~**1,000**~~ ➜ **900** (-10%)"
    )
    assert buy.format_discounted_price(1000, 1000, 0) == f"{MORA} **1,000**"
    assert buy.format_discounted_price(1, 1, 10) == f"{MORA} **1**"
    assert buy.format_discounted_price(5, 5, 0, "what") == f"{MORA} **5**"


async def test_autocomplete_matches_item_and_role_names(shop):
    shop.add("Hero", 1500)
    shop.add("777", 20, currency="guild_sigils")
    shop.add("888")
    sigils = config.CURRENCY_INFO["guild_sigils"]["label"]
    mora = config.CURRENCY_INFO["guild_mora"]["label"]

    async def suggest(text):
        choices = await buy.purchase_autocomplete(Interaction(shop), text)
        return [(choice.name, choice.value) for choice in choices]

    assert await suggest("HER") == [(f"Hero (1500 {mora})", "Hero")]
    assert await suggest("knig") == [(f"Role: Knight (20 {sigils})", "777")]
    assert await suggest("8") == [(f"Unknown Role (100 {mora})", "888")]
    assert len(await suggest("")) == 3
    assert await suggest("zz") == []


async def test_autocomplete_gives_25_short_choices(shop):
    for number in range(30):
        shop.add(f"{number} " + "x" * 120)
    choices = await buy.purchase_autocomplete(Interaction(shop), "")
    assert len(choices) == 25
    assert all(len(choice.name) == 100 for choice in choices)


async def test_an_unknown_item_is_refused(shop):
    interaction, view = await ask(shop, "Nope")
    assert interaction.out[0] == ("defer", {"thinking": True})
    kind, sent = interaction.out[1]
    assert sent["ephemeral"] is True and view is None
    assert sent["embed"].title == "Error"
    assert sent["embed"].description == f"<@{USER}>, **Nope** is not a valid item!"
    assert sent["embed"].color == discord.Color.red()


async def test_buy_asks_to_confirm(shop):
    shop.add("Hero", 1500)
    interaction, view = await ask(shop, "Hero")
    embed = interaction.embeds()[0]
    assert embed.title == f"{config.THINK_EMOTE} Confirm Purchase"
    assert embed.description == (
        f"Are you sure you want to purchase **Hero** for {MORA} **1,500**?"
    )
    assert embed.color == discord.Color.gold()
    assert embed.footer.text == "Purchase buttons will timeout in 30 seconds"
    assert view.timeout == 30 and view.message.id == 9
    assert [(b.label, b.style, b.custom_id) for b in view.children][1] == (
        "Cancel",
        discord.ButtonStyle.grey,
        "cancelbuy",
    )
    assert (view.children[0].label, view.children[0].style) == (
        "Purchase Item",
        discord.ButtonStyle.green,
    )


async def test_buy_shows_a_role_and_a_discount(shop):
    shop.add("777", 1000, currency="guild_sigils")
    shop.discount = 10
    interaction, _ = await ask(shop, "777")
    assert interaction.embeds()[0].description == (
        f"Are you sure you want to purchase **<@&777>** for {SIGILS} ~~**1,000**~~ ➜ **900** (-10%)?"
    )


async def test_cooldown_and_other_errors_are_answered(shop):
    cog = buy.Buy(SimpleNamespace())
    interaction = Interaction(shop)
    error = app_commands.CommandOnCooldown(app_commands.Cooldown(1, 10), 3.14159)
    await cog.buy_error(interaction, error)
    _, _, sent = interaction.out[0]
    assert sent["ephemeral"] is True and sent["embed"].title == "Cooldown"
    assert sent["embed"].description == (
        "You're on cooldown. Please try this command again in 3.14 seconds."
    )
    interaction = Interaction(shop)
    with pytest.raises(ValueError):
        await cog.buy_error(interaction, ValueError("x"))
    assert interaction.out[0][2]["embed"].description == (
        "An unexpected error occurred. Please try again later."
    )


async def test_only_the_buyer_can_press(shop):
    shop.add("Hero")
    _, view = await ask(shop, "Hero")
    for button in view.children:
        other = Interaction(shop, user_id=1)
        await button.callback(other)
        assert other.out == [
            ("send", ("You can't perform this action.",), {"ephemeral": True})
        ]


async def test_cancel_deletes_the_message(shop):
    shop.add("Hero")
    _, view = await ask(shop, "Hero")
    press = Interaction(shop)
    await view.cancelItem.callback(press)
    assert press.out == [("delete",)]


async def test_pressing_purchase_goes_through_the_queue(shop):
    shop.add("Hero", 200)
    _, view = await ask(shop, "Hero")
    worker = asyncio.create_task(buy.purchase_worker())
    press = Interaction(shop)
    await view.purchaseItem.callback(press)
    worker.cancel()
    assert press.out[0] == ("defer", {})
    assert press.out[1] == ("edit", {"view": None})
    waiting = press.out[2][1]["embed"]
    assert waiting.title == "Processing Purchase"
    assert waiting.description == f"Validating your purchase {config.LOADING_EMOTE}"
    assert waiting.color == discord.Color.gold()
    assert press.embeds()[-1].title == f"{config.HAPPY_EMOTE} Successful Purchase"


async def test_a_busy_queue_is_announced_and_errors_reach_the_press(shop):
    shop.add("Hero")
    _, view = await ask(shop, "Hero")

    async def earlier(interaction):
        raise RuntimeError("first")

    first = asyncio.get_running_loop().create_future()
    await buy.global_purchase_queue.put((None, first, earlier))
    worker = asyncio.create_task(buy.purchase_worker())
    press = Interaction(shop)
    await view.purchaseItem.callback(press)
    worker.cancel()
    with pytest.raises(RuntimeError):
        await first
    waiting = press.out[2][1]["embed"]
    assert waiting.title == "Purchase Queued"
    assert waiting.description == (
        f"Your purchase is in queue. Please wait while we validate your purchase {config.LOADING_EMOTE}"
    )
    assert waiting.color == discord.Color.orange()


async def test_a_purchase_gives_the_item_takes_payment_and_pays_xp(shop):
    shop.add("Hero", 1000, stock=3)
    shop.discount = 10
    interaction = await purchase(shop, "Hero")
    kinds = [call[0] for call in shop.calls]
    assert kinds == ["balance", "item", "pay", "quest", "xp", "tiers", "stock", "link"]
    assert shop.calls[0] == ("balance", (USER, GUILD))
    _, args, kwargs = shop.calls[1]
    assert args[:5] == (USER, GUILD, "Hero", "about", 900) and kwargs == {
        "pinned": False
    }
    assert abs(args[5] - time.time()) < 5
    assert shop.calls[2] == ("pay", (USER, 900, 42, GUILD))
    xp = int(900 * config.MORA_TO_XP_RATIO)
    assert shop.calls[3:7] == [
        ("quest", {"purchase_items": 1}),
        ("xp", xp),
        ("tiers", 5, 5 + xp),
        ("stock", "Hero", 2),
    ]
    assert shop.calls[7] == ("link", (USER, GUILD, "http://jump", "Hero", args[5]))
    (edit,) = interaction.out
    embed = edit[1]["embed"]
    assert embed.title == f"{config.HAPPY_EMOTE} Successful Purchase"
    assert embed.description == (
        f"Congratulations! You have paid {MORA} **900** and now own **Hero**. "
        f"\n> {config.CONFUSED_EMOTE} You have also earned **`{xp:,}` XP** from this purchase!"
    )
    assert embed.color == discord.Color.green()
    assert edit[1]["view"].embeds[0].title == "free"


@pytest.mark.parametrize(
    "currency, paid",
    [
        ("guild_mora", (USER, 100, 42, GUILD)),
        ("global_mora", (USER, 100, 42, GUILD)),
        ("guild_sigils", (USER, GUILD, 100)),
        ("global_sigils", (USER, GUILD, 100)),
    ],
)
async def test_each_currency_is_checked_and_paid(shop, currency, paid):
    shop.add("Hero", 100, currency=currency)
    await purchase(shop, "Hero")
    assert ("pay", paid) in shop.calls
    ratio = config.MORA_TO_XP_RATIO if "mora" in currency else config.SIGILS_TO_XP_RATIO
    assert ("xp", int(100 * ratio)) in shop.calls
    balance = (USER,) if currency.startswith("global") else (USER, GUILD)
    assert shop.calls[0] == ("balance", balance)


async def test_an_unknown_currency_cannot_pay(shop):
    shop.add("Hero", 100, currency="gems")
    interaction = await purchase(shop, "Hero")
    assert shop.calls == []
    assert interaction.embeds()[0].title == f"{config.SHRUG_EMOTE} Insufficient {MORA}"
    assert await buy.deduct_balance(None, 1, 2, 3, 4, "gems") is False


async def test_a_role_item_gives_the_role(shop):
    shop.add("777", 100)
    interaction = await purchase(shop, "777")
    assert interaction.out[0] == ("role", 777)
    assert "now own **<@&777>**" in interaction.embeds()[-1].description


async def test_a_role_already_held_is_refused(shop):
    shop.add("777", 100)
    interaction = Interaction(shop)
    interaction.user.roles.append(interaction.roles[777])
    await buy.ConfirmPurchaseView("777", USER).process_purchase(interaction)
    (edit,) = interaction.out
    assert edit[1]["view"] is None
    assert edit[1]["embed"].title == f"{config.HMM_EMOTE} Oops!"
    assert edit[1]["embed"].description == (
        "You already have the <@&777> role. Unlike some titles, you can only purchase roles **once**."
    )
    assert shop.calls == []


async def test_a_removed_item_is_refused(shop):
    interaction = await purchase(shop, "Hero")
    embed = interaction.embeds()[0]
    assert (embed.title, embed.description) == (
        "Error",
        "This item could not be found in the shop anymore.",
    )
    assert embed.color == discord.Color.red() and shop.calls == []


async def test_an_item_out_of_stock_is_refused(shop):
    shop.add("777", 100, stock=0)
    interaction = await purchase(shop, "777")
    embed = interaction.embeds()[0]
    assert embed.title == f"{config.NO_STOCK_EMOTE} Out of Stock"
    assert embed.description == (
        "**<@&777>** has run out of stock! Ask an admin to restock."
    )
    assert shop.calls == []


async def test_too_little_balance_is_refused(shop):
    shop.add("Hero", 100, currency="guild_sigils")
    shop.balance = 99
    interaction = await purchase(shop, "Hero")
    embed = interaction.embeds()[0]
    assert embed.title == f"{config.SHRUG_EMOTE} Insufficient {SIGILS}"
    assert embed.description.startswith(
        f"You don't have enough {SIGILS} for **Hero**. Please check your balance using "
    )
    assert [call[0] for call in shop.calls] == ["balance"]
    shop.balance = 100
    assert (await purchase(shop, "Hero")).embeds()[-1].color == discord.Color.green()


async def test_a_single_purchase_title_cannot_be_bought_twice(shop):
    shop.add("777", 100, multiple=False)
    shop.inventory = [["777", "about", 100, 1]]
    interaction = await purchase(shop, "777")
    # The role is given before the inventory is checked; kept as it was.
    assert interaction.out[0] == ("role", 777)
    embed = interaction.embeds()[0]
    assert embed.title == f"{config.HMM_EMOTE} Oops"
    assert embed.description == (
        "You already own **<@&777>**! This title does not allow multiple purchases. If you believe this is a mistake, contact a server admin."
    )
    assert [call[0] for call in shop.calls] == ["balance"]
    shop.items[0][3] = True
    await purchase(shop, "777")
    assert "pay" in [call[0] for call in shop.calls]


async def test_stock_is_only_lowered_when_limited(shop):
    shop.add("Hero", 100, stock=-1)
    await purchase(shop, "Hero")
    assert "stock" not in [call[0] for call in shop.calls]
    shop.items[0][4] = 1
    await purchase(shop, "Hero")
    assert ("stock", "Hero", 0) in shop.calls


async def test_an_old_press_expires(shop):
    shop.add("Hero")
    interaction = await purchase(shop, "Hero", age=15 * 60 - 25)
    (edit,) = interaction.out
    assert "view" not in edit[1]
    assert (edit[1]["embed"].title, edit[1]["embed"].description) == (
        "Purchase Expired",
        "Your purchase request timed out. Please try again.",
    )
    assert shop.calls == []
    await purchase(shop, "Hero", age=15 * 60 - 40)
    assert "pay" in [call[0] for call in shop.calls]


async def test_due_stock_changes_wait_a_second(shop, monkeypatch):
    slept = []

    async def sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(buy.asyncio, "sleep", sleep)
    shop.add("Hero")
    await purchase(shop, "Hero")
    assert slept == []
    shop.pending = 2
    await purchase(shop, "Hero")
    assert slept == [1]


async def test_xianyun_limits_how_often_a_prize_is_bought(shop):
    shop.add("Welkin")
    recent = int(time.time()) - 100
    shop.history = [
        {"description": "plain", "timestamp": recent},
        {"description": "A WELKIN moon", "timestamp": recent},
    ]
    interaction = await purchase(shop, "Welkin", guild_id=buy.XIANYUN)
    (edit,) = interaction.out
    assert edit[1]["view"] is None
    assert edit[1]["embed"].title == (
        "<:keksweat:1381225834110652497> Miss Xianyun wants to give someone else a chance!"
    )
    assert edit[1]["embed"].description == (
        f"You have already purchased **Welkin** recently. You can only buy this item again <t:{recent + 45 * 86400}:R>."
    )
    assert shop.calls == []
    await purchase(shop, "Welkin")
    assert "pay" in [call[0] for call in shop.calls]


@pytest.mark.parametrize(
    "description, age",
    [("plain", 100), (None, 100), ("nitro", 45 * 86400 + 5)],
)
async def test_xianyun_allows_other_and_older_purchases(shop, description, age):
    shop.add("Welkin")
    bought = datetime.datetime.fromtimestamp(time.time() - age)
    shop.history = [{"description": description, "timestamp": bought}]
    await purchase(shop, "Welkin", guild_id=buy.XIANYUN)
    assert "pay" in [call[0] for call in shop.calls]


@pytest.mark.parametrize("word", ["welkin", "pass", "voucher", "nitro"])
async def test_xianyun_limited_words(shop, word):
    shop.add("Prize")
    bought = datetime.datetime.fromtimestamp(time.time() - 60)
    shop.history = [{"description": f"a {word}", "timestamp": bought}]
    await purchase(shop, "Prize", guild_id=buy.XIANYUN)
    assert shop.calls == []


async def test_a_failed_link_save_does_not_fail_the_purchase(shop, monkeypatch):
    async def execute(self, query, *args):
        raise RuntimeError("down")

    monkeypatch.setattr(Conn, "execute", execute)
    shop.add("Hero")
    interaction = await purchase(shop, "Hero")
    assert interaction.embeds()[-1].color == discord.Color.green()


class Message:
    def __init__(self, title):
        self.id = 9
        self.embeds = [discord.Embed(title=title)] if title else []
        self.channel = SimpleNamespace(fetch_message=self.fetch)
        self.edited = None

    async def fetch(self, message_id):
        return self

    async def edit(self, **kwargs):
        self.edited = kwargs


async def test_timeout_greys_out_an_unanswered_purchase(shop):
    view = buy.ConfirmPurchaseView("Hero", USER)
    view.message = Message("x Confirm Purchase")
    await view.on_timeout()
    assert view.message.edited["view"] is view
    assert view.message.edited["embed"].footer.text == (
        "Purchase cancelled due to timeout"
    )
    assert all(button.disabled for button in view.children)


@pytest.mark.parametrize("title", ["Successful Purchase", None])
async def test_timeout_leaves_a_finished_purchase(shop, title):
    view = buy.ConfirmPurchaseView("Hero", USER)
    view.message = Message(title)
    await view.on_timeout()
    assert view.message.edited is None
    assert not any(button.disabled for button in view.children)


async def test_buy_can_be_used_once_in_ten_seconds(shop):
    (check,) = buy.Buy.buy.checks
    interaction = Interaction(shop, user_id=31337)
    assert await check(interaction)
    with pytest.raises(app_commands.CommandOnCooldown) as error:
        await check(interaction)
    assert 9.9 < error.value.retry_after <= 10


@pytest.mark.parametrize(
    "currency", ["guild_mora", "global_mora", "guild_sigils", "global_sigils"]
)
async def test_an_exact_balance_is_enough(shop, currency):
    shop.balance = 100
    assert await buy.check_balance(None, USER, GUILD, 100, currency)
    assert not await buy.check_balance(None, USER, GUILD, 101, currency)


async def test_a_price_stored_as_text_is_read_as_a_number(shop):
    shop.add("Hero", "1000")
    shop.discount = 10
    interaction, _ = await ask(shop, "Hero")
    shown = str(interaction.out[-1][1]["embed"].to_dict())
    assert "~~**1,000**~~ ➜ **900** (-10%)" in shown
    await purchase(shop, "Hero")
    assert ("pay", (USER, 900, 42, GUILD)) in shop.calls


async def test_the_statements_sent_to_the_database(shop):
    shop.add("Welkin", 100)
    await purchase(shop, "Welkin", guild_id=buy.XIANYUN)
    (history, history_args), (link, link_args) = shop.queries
    assert history == (
        "SELECT title, description, timestamp FROM minigame_inventory WHERE uid = $1"
        " AND gid = $2 AND title = $3 ORDER BY timestamp DESC LIMIT 10"
    )
    assert history_args == (USER, buy.XIANYUN, "Welkin")
    assert link == (
        "UPDATE minigame_inventory SET link = $3 WHERE uid = $1 AND gid = $2"
        " AND title = $4 AND timestamp = $5"
    )
    assert link_args[:4] == (USER, buy.XIANYUN, "http://jump", "Welkin")


async def test_a_purchase_is_written_to_the_console(shop, capsys):
    shop.add("Hero", 100)
    shop.pending = 2
    await purchase(shop, "Hero")
    assert capsys.readouterr().out.splitlines() == [
        f"Processed 2 scheduled stock updates for guild {GUILD}",
        "Added 1 XP from purchase.",
        f"bob ({USER}) have paid 100 guild_mora and now own Hero in G ({GUILD}) → http://jump",
        f"Logged purchase link to minigame_inventory for user {USER} in guild {GUILD}",
    ]


async def test_two_items_in_one_second_are_both_kept(pool):
    from commands.Events import helperFunctions

    await helperFunctions.ensure_minigame_inventory_table(pool)
    for title in ("first", "second", "third"):
        await helperFunctions.add_inventory_item(pool, 1, 2, title, "", 0, 100)
    rows = await pool.fetch(
        "SELECT title, timestamp FROM minigame_inventory ORDER BY timestamp"
    )
    assert [tuple(row) for row in rows] == [
        ("first", 100),
        ("second", 101),
        ("third", 102),
    ]
