import copy
from types import SimpleNamespace

import discord
import pytest

from commands.Events import config, eventSystem, helperFunctions

GUILD, CHANNEL = 10, 30
NO = config.NO_EMOTE
SIGILS = config.SIGIL_CURRENCY_NAME


class Store:
    """Stands in for the saved channel and server settings; `saves` lists the writes."""

    def __init__(self):
        self.channel, self.guild, self.saves = {}, {}, []

    async def get_channel_settings(self, pool, channel_id):
        fallback = copy.deepcopy(helperFunctions.SETTINGS_FALLBACK)
        return {**fallback, "channel_id": channel_id, **copy.deepcopy(self.channel)}

    async def get_guild_settings(self, pool, guild_id):
        fallback = copy.deepcopy(helperFunctions.GUILD_SETTINGS_FALLBACK)
        return {**fallback, **copy.deepcopy(self.guild)}

    async def upsert_channel_settings(self, pool, channel_id, **values):
        self.saves.append(("channel", channel_id, values))
        self.channel.update(values)

    async def upsert_guild_settings(self, pool, guild_id, **values):
        self.saves.append(("server", guild_id, values))
        self.guild.update(values)


class Admin:
    """Presses and types as an admin would, keeping the panel that is shown."""

    def __init__(self):
        self.cleared = 0
        cache = SimpleNamespace(invalidate_all=self.clear)
        self.client = SimpleNamespace(
            pool=None, get_cog=lambda name: SimpleNamespace(cache=cache)
        )
        self.role = SimpleNamespace(
            id=501, mention="<@&501>", color=discord.Color(0x123456)
        )
        self.channel = SimpleNamespace(
            id=CHANNEL, mention=f"<#{CHANNEL}>", guild=SimpleNamespace(id=GUILD)
        )
        self.guild = SimpleNamespace(
            id=GUILD,
            get_channel=lambda id: self.channel,
            get_role=lambda id: self.role,
        )
        self.embed = self.view = self.modal = self.side = None
        self.said, self.refreshed = [], 0

    def clear(self):
        self.cleared += 1

    def interaction(self, side=False):
        async def send_message(content=None, embed=None, view=None, ephemeral=False):
            assert ephemeral
            if view is None:
                self.said.append(content or embed.description)
            elif embed.title == "Role Boost":
                self.side = SimpleNamespace(embed=embed, view=view, content=None)
            else:
                self.embed, self.view = embed, view

        async def edit_message(content=None, embed=None, view=None):
            if side:
                self.side = SimpleNamespace(embed=embed, view=view, content=content)
            else:
                self.embed, self.view = embed, view

        async def send_modal(modal):
            self.modal = modal

        async def edit_original_response(embed, view):
            self.embed, self.view = embed, view
            self.refreshed += 1

        return SimpleNamespace(
            guild=self.guild,
            client=self.client,
            channel=self.channel,
            message=SimpleNamespace(embeds=[self.embed]),
            response=SimpleNamespace(
                send_message=send_message,
                edit_message=edit_message,
                send_modal=send_modal,
            ),
            edit_original_response=edit_original_response,
        )

    async def open(self, channel=None):
        cog = eventSystem.EventSystem(SimpleNamespace())
        await cog.events_settings.callback(cog, self.interaction(), channel)

    def item(self, label, view=None):
        return next(
            child
            for child in (view or self.view).children
            if getattr(child, "label", None) == label
        )

    async def press(self, label):
        await self.item(label).callback(self.interaction())

    async def type(self, text, side=False):
        self.modal.children[0]._value = text
        await self.modal.on_submit(self.interaction(side))

    def labels(self):
        return [
            getattr(child, "label", None) or type(child).__name__
            for child in self.view.children
        ]


@pytest.fixture
def store(monkeypatch):
    store = Store()
    for name in vars(Store):
        if not name.startswith("_"):
            monkeypatch.setattr(eventSystem, name, getattr(store, name))
    return store


@pytest.fixture
def admin(store):
    return Admin()


async def test_a_new_channel_opens_on_games_turned_off(admin, store):
    await admin.open()
    assert admin.embed.title == "🎮 Minigame Configuration"
    assert (
        admin.embed.description == f"**Channel:** <#{CHANNEL}>\n**Status:** Disabled\n"
    )
    assert admin.embed.timestamp is not None
    assert admin.view.timeout == 300
    assert admin.labels() == [
        "Configure Games",
        "Configure Chests",
        f"Configure {SIGILS}",
        "Enable Games",
    ]
    assert [child.custom_id for child in admin.view.children[:3]] == [
        "tab_minigames",
        "tab_chests",
        "tab_sigils",
    ]
    assert admin.view.children[0].style == discord.ButtonStyle.primary
    assert admin.view.children[3].style == discord.ButtonStyle.green


async def test_enabling_games_turns_every_game_on_the_first_time(admin, store):
    await admin.open()
    await admin.press("Enable Games")
    assert store.saves == [
        (
            "channel",
            CHANNEL,
            {"minigames_enabled": True, "minigames_list": config.LETTER_LIST},
        )
    ]
    assert admin.cleared == 1
    assert admin.labels() == [
        "Configure Games",
        "Configure Chests",
        f"Configure {SIGILS}",
        "Disable Games",
        "Toggle Games",
        "FrequencySelect",
        "Multiplier",
    ]
    assert (
        "**Spawn Rate:** `2%`\n**Multiplier:** `x1.0`\n\n**Enabled Games:**\n > "
        in (admin.embed.description)
    )
    assert admin.embed.description.count(config.YES_EMOTE) == len(config.LETTER_LIST)

    await admin.press("Disable Games")
    await admin.press("Enable Games")
    assert store.saves[-1] == ("channel", CHANNEL, {"minigames_enabled": True})


@pytest.mark.parametrize("frequency, shown", [(2, "50"), (30, "3"), (200, "0.5")])
async def test_frequency_menu_sets_the_spawn_rate(admin, store, frequency, shown):
    store.channel = {"minigames_enabled": True}
    await admin.open()
    menu = admin.view.children[5]
    assert [(o.label, o.value, o.default) for o in menu.options][4] == (
        "Uncommon (~2%)",
        "50",
        True,
    )
    menu._values = [str(frequency)]
    await menu.callback(admin.interaction())
    assert store.channel["minigames_frequency"] == frequency
    assert f"**Spawn Rate:** `{shown}%`" in admin.embed.description


async def test_toggle_games_flips_each_letter(admin, store):
    store.channel = {"minigames_enabled": True, "minigames_list": ["A", "B"]}
    await admin.open()
    await admin.press("Toggle Games")
    assert admin.modal.title == "Toggle Events"
    await admin.type("bc")
    assert store.channel["minigames_list"] == ["A", "C"]
    await admin.type("a1")
    assert admin.said == [f"{NO} Invalid letter `1`."]
    assert store.channel["minigames_list"] == ["A", "C"]


BOXES = [
    # tab, button, title, label, placeholder, filled with, typed, saved as
    ("minigames", "Multiplier", "Set Mora Multiplier", "Multiplier (e.g. 1.0 = 1x, 2.0 = 2x)", "1.0", "1.0", "2.5", ("channel", "mora_multiplier", 2.5)),
    ("chests", "Base Upgrade Chances", "Base Upgrade Chances", "Number of upgrade chances", "4", "4", "0", ("server", "chests_base_upgrade_chances", 0)),
    ("chests", "Spawn Requirement", "Chest Spawn Requirement", "Exact OR min, max (effortful messages)", "4, 6", "4, 6", "5", ("server", "chests_spawn_req", [5])),
    ("chests", "Streak Bonus", "Streak Bonus", "Streak bonus per day", "100", "100", "150", ("server", "chests_streak_bonus", 150)),
    ("chests", "Max Streak Bonus", "Streak Bonus", "Maximum streak bonus", "10000", "10000", "0", ("server", "chests_max_streak_bonus", 0)),
    ("chests", "Tier Names", "Chest Tier Names", "Tier names (comma-separated)", "Common, Exquisite, Precious, Luxurious", "Common, Exquisite, Precious, Luxurious", " A ,B,, ", ("server", "chests_tier_names", ["A", "B"])),
    ("chests", "Tier Rewards", "Chest Tier Rewards", "Rewards (comma-separated integers)", "2500, 7500, 15000, 30000", "2500, 7500, 15000, 30000", "1, 2", ("server", "chests_tier_rewards", [1, 2])),
    ("chests", "Tier Upgrade Chances", "Chest Upgrade Chances", "Chances (comma-separated decimals 0-1)", "0.30, 0.15, 0.20", "0.30, 0.15, 0.20", "0.5,1", ("server", "chests_upgrade_chances", [0.5, 1.0])),
    ("chests", "Tier Emotes", "Chest Emotes", "Emotes (comma-separated)", "<a:common:1371641883121680465>, <a:exquisite:1371641856344985620>, ...", None, "x, y", ("server", "chests_emotes", ["x", "y"])),
    ("chests", "Tier Icons", "Chest Icons", "Icon URLs (comma-separated)", "https://i.imgur.com/2kOfLSC.png, https://i.imgur.com/DBPQSAu.png, ...", None, "x, y", ("server", "chests_icons", ["x", "y"])),
    ("sigils", "Earning Range", "Sigil Earning Range", f"Exact OR min, max ({SIGILS} per batch)", "19, 25", "19, 25", "3, 9", ("channel", "chat_range", [3, 9])),
    ("sigils", "Messages per Batch", "Messages per Batch", "Exact OR min, max (messages per batch)", "15, 20", "15, 20", "8", ("channel", "chat_msg_range", [8])),
    ("sigils", "Max Daily Cap (Server)", f"Max Daily {SIGILS}", f"Maximum Daily {SIGILS} (server-wide)", "60", "60", "1", ("server", "chat_max_cap", 1)),
]  # fmt: skip


@pytest.mark.parametrize("tab, button, title, label, hint, filled, typed, saved", BOXES)
async def test_each_setting_opens_its_box_and_saves(
    admin, store, tab, button, title, label, hint, filled, typed, saved
):
    store.channel = {"minigames_enabled": True, "chests_enabled": True, "chat_enabled": True}  # fmt: skip
    await admin.open()
    await admin.press({"minigames": "Configure Games", "chests": "Configure Chests", "sigils": f"Configure {SIGILS}"}[tab])  # fmt: skip
    await admin.press(button)
    box = admin.modal.children[0]
    assert (admin.modal.title, box.label, box.placeholder) == (title, label, hint)
    if filled:
        assert box.default == filled
    await admin.type(typed)
    place, column, value = saved
    assert store.saves == [(place, CHANNEL if place == "channel" else GUILD, {column: value})]  # fmt: skip
    assert admin.cleared == 1 and admin.said == []
    assert admin.item(button)  # the same tab is shown again


REFUSALS = [
    ("minigames", "Multiplier", "x", "Invalid number."),
    ("minigames", "Multiplier", "0.001", "Multiplier must be between 0.01 and 99.99."),
    ("minigames", "Multiplier", "100", "Multiplier must be between 0.01 and 99.99."),
    ("chests", "Base Upgrade Chances", "x", "Invalid integer."),
    ("chests", "Base Upgrade Chances", "-1", "Must be non-negative."),
    ("chests", "Streak Bonus", "-1", "Must be non-negative."),
    ("chests", "Spawn Requirement", "a", "Invalid integer(s)."),
    ("chests", "Spawn Requirement", "1, 2, 3", "Provide 1 (exact) or 2 (min, max) positive integers."),
    ("chests", "Spawn Requirement", "0", "Provide 1 (exact) or 2 (min, max) positive integers."),
    ("chests", "Spawn Requirement", "6, 4", "Provide 1 (exact) or 2 (min, max) positive integers."),
    ("chests", "Tier Names", "One", "Provide at least 2 tier names."),
    ("chests", "Tier Rewards", "1, x", "Invalid integer list."),
    ("chests", "Tier Rewards", "1", "Provide at least 2 reward values."),
    ("chests", "Tier Upgrade Chances", "x", "Invalid decimal list."),
    ("chests", "Tier Upgrade Chances", "0.5, 1.1", "Each chance must be between 0 and 1."),
    ("chests", "Tier Emotes", "x", "Provide at least 2 emotes."),
    ("chests", "Tier Icons", "x", "Provide at least 2 icon URLs."),
    ("sigils", "Earning Range", "9, 3", "Provide 1 (exact) or 2 (min, max) positive integers."),
    ("sigils", "Messages per Batch", "", "Provide 1 (exact) or 2 (min, max) positive integers."),
    ("sigils", "Max Daily Cap (Server)", "0", "Must be at least 1."),
]  # fmt: skip


@pytest.mark.parametrize("tab, button, typed, problem", REFUSALS)
async def test_a_bad_value_is_refused_and_not_saved(
    admin, store, tab, button, typed, problem
):
    store.channel = {"minigames_enabled": True, "chests_enabled": True, "chat_enabled": True}  # fmt: skip
    await admin.open()
    await admin.press({"minigames": "Configure Games", "chests": "Configure Chests", "sigils": f"Configure {SIGILS}"}[tab])  # fmt: skip
    await admin.press(button)
    await admin.type(typed)
    assert admin.said == [f"{NO} {problem}"]
    assert store.saves == [] and admin.cleared == 0


async def test_chests_tab_lists_the_servers_tiers(admin, store):
    store.guild = {"chests_spawn_req": [5], "chests_tier_names": ["A", "B", "C"]}
    await admin.open()
    await admin.press("Configure Chests")
    assert admin.embed.description == f"**Channel:** <#{CHANNEL}>\n**Status:** Disabled"
    assert admin.labels()[3:] == ["Enable Chests"]
    await admin.press("Enable Chests")
    emotes = helperFunctions.GUILD_SETTINGS_FALLBACK["chests_emotes"]
    assert admin.embed.title == "📦 Chest Configuration"
    assert admin.embed.description == (
        f"**Channel:** <#{CHANNEL}>\n**Status:** Enabled"
        "\n\n> The following settings apply **server-wide** across all enabled channels.\n\n"
        "**Base Upgrade Chances:** `4`\n"
        "**Spawn Requirement:** `5` messages\n"
        f"**Streak Bonus:** {config.MORA_EMOTE} `+100` per day (max `10000`)\n\n"
        "**Tiers:**\n"
        f"{config.DOT_EMOTE} {emotes[0]} **A** — {config.MORA_EMOTE} `2,500` (upgrade to next: 30%)\n"
        f"{config.DOT_EMOTE} {emotes[1]} **B** — {config.MORA_EMOTE} `7,500` (upgrade to next: 15%)\n"
        f"{config.DOT_EMOTE} {emotes[2]} **C** — {config.MORA_EMOTE} `15,000`\n"
    )
    rows = {child.label: child.row for child in admin.view.children[4:]}
    assert rows == {
        "Base Upgrade Chances": 1,
        "Spawn Requirement": 1,
        "Streak Bonus": 1,
        "Max Streak Bonus": 1,
        "Tier Names": 2,
        "Tier Rewards": 2,
        "Tier Upgrade Chances": 2,
        "Tier Emotes": 2,
        "Tier Icons": 2,
    }


async def test_sigils_tab_shows_ranges_cap_and_boosted_roles(admin, store):
    store.channel = {
        "chat_enabled": True,
        "chat_range": [7],
        "chat_boosted_roles": ["501:102", "502:+5", "odd"],
    }
    await admin.open()
    await admin.press(f"Configure {SIGILS}")
    assert admin.embed.description == (
        f"**Channel:** <#{CHANNEL}>\n**Status:** Enabled"
        f"\n**Earning Range (per-channel):** `7` {config.SIGIL_EMOTE} per batch"
        "\n**Messages per Batch (per-channel):** `15–20`"
        f"\n**Max Daily Cap (server-wide):** {config.SIGIL_EMOTE} `60`\n"
        "\n**Boosted Roles (per-channel):**\n"
        f"{config.DOT_EMOTE} <@&501>: `102`\n{config.DOT_EMOTE} <@&502>: `+5`\n"
    )
    select = admin.view.children[-1]
    assert isinstance(select, discord.ui.RoleSelect) and select.row == 1
    assert [child.row for child in admin.view.children[4:7]] == [2, 2, 2]


async def test_a_roles_boost_is_set_changed_and_removed(admin, store):
    store.channel = {"chat_enabled": True, "chat_boosted_roles": ["502:+5"]}
    await admin.open()
    await admin.press(f"Configure {SIGILS}")
    select = admin.view.children[-1]
    select._values = [admin.role]
    await select.callback(admin.interaction())
    assert (
        admin.side.embed.description
        == "**Selected:** <@&501>\nNo boost set for this role yet."
    )
    assert admin.side.embed.color.value == 0x123456

    await admin.item("Set Boost", admin.side.view).callback(admin.interaction(True))
    assert admin.modal.children[0].default == ""
    await admin.type("lots", side=True)
    await admin.type("", side=True)
    assert admin.said == [
        f"{NO} Enter a whole number such as `80`, or `+20` to add.",
        f"{NO} Value cannot be empty.",
    ]
    assert store.saves == []

    await admin.type(" +20 ", side=True)
    assert store.channel["chat_boosted_roles"] == ["502:+5", "501:+20"]
    assert admin.side.embed.description == (
        "**Selected:** <@&501>\n**Current Boost:** `+20`\n*(adds to daily cap)*"
    )
    assert admin.refreshed == 1 and "<@&501>: `+20`" in admin.embed.description

    await admin.item("Set Boost", admin.side.view).callback(admin.interaction(True))
    assert admin.modal.children[0].default == "+20"
    await admin.type("80", side=True)
    assert store.channel["chat_boosted_roles"] == ["502:+5", "501:80"]
    assert admin.side.embed.description.endswith("*(sets daily cap to this value)*")

    await admin.item("Remove Boost", admin.side.view).callback(admin.interaction(True))
    assert store.channel["chat_boosted_roles"] == ["502:+5"]
    assert (
        admin.side.content == f"{config.YES_EMOTE} Boost for <@&501> has been removed."
    )
    assert admin.side.view is None and admin.refreshed == 3
    assert "<@&501>" not in admin.embed.description


async def test_the_command_is_for_managers_and_reports_its_error(admin):
    command = eventSystem.EventSystem.events_settings
    sent = []
    interaction = SimpleNamespace(
        response=SimpleNamespace(
            send_message=lambda text, ephemeral: sent.append((text, ephemeral))
            or done()
        )
    )

    async def done():
        pass

    cog = eventSystem.EventSystem(SimpleNamespace())
    await cog.events_settings_error(interaction, Exception("no"))
    assert sent == [("```no```", True)]
    assert command.checks and command.name == "settings"


def test_a_number_that_is_not_one_is_refused():
    with pytest.raises(eventSystem.Refused, match="between 0.01 and 99.99"):
        eventSystem.multiplier("nan")
    with pytest.raises(eventSystem.Refused, match="between 0 and 1"):
        eventSystem.chances("0.5, nan")
    with pytest.raises(eventSystem.Refused, match="between 0 and 1"):
        eventSystem.chances("-0.1")
