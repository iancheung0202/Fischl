from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Birthday import birthdayStore
from commands.CoOp import coOpStore
from commands.Events.helperFunctions import ensure_minigame_settings_table
from commands.Help import help as help_page
from commands.Sticky import stickyStore

YES, NO = "<:yes:1036811164891480194>", "<:no:1036810470860013639>"
REPLY, BLANK = "<:reply:1036792837821435976>", "<:blank:1036792889121980426>"
SUB = discord.AppCommandOptionType.subcommand
TEXT = discord.AppCommandOptionType.string
GUILD = 10
NOT_AUTHOR = f"{NO} You are not the author of this command"
OVERVIEW = {
    "title": "Fischl Help",
    "description": "> <a:hoyoverse:1366950037728530472> Fischl is a powerful utility Discord bot **designed with all Hoyoverse communities in mind**. Trusted by numerous large servers, Fischl makes server management effortless with **easy-to-use systems** for *tickets, co-op matchmaking, partnerships, welcomes, birthdays, and fun minigames*. <:HuTaoWow:1253167030748840067>",
    "color": 0x1DBCEB,
    "fields": [
        {
            "name": "<:genshin_impact:1103720959950725190> Support Server",
            "value": "Head over to our **[support server](https://discord.gg/kaycd3fxHh)** if you have any suggestions, questions or bug reports! :writing_hand:",
            "inline": True,
        },
        {
            "name": "<:slash:1037445915348324505> Command Usage",
            "value": "This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` or **select a category** below to see the list of available bot commands.",
            "inline": True,
        },
    ],
    "type": "rich",
    "flags": 0,
}
CATEGORIES = [
    ("Tickets", "🎫"),
    ("Co-op System", "🎮"),
    ("Partnership Panels", "🤝"),
    ("Sticky Messages", "🫧"),
    ("Welcomer", "👋"),
    ("Birthday Wishes", "🎂"),
    ("Chat Minigames", "🎉"),
    ("Booster Roles", "💎"),
    ("Vanity/Tag Roles", "👤"),
    ("Utility Commands", "🛠️"),
]


@pytest.fixture(autouse=True)
def mentions(monkeypatch):
    """Makes command mentions the same whether or not assets/commands.json is there."""
    monkeypatch.setattr(help_page, "SlashCommand", lambda name: f"</{name}:1>")


def option(name, kind=TEXT, options=()):
    return SimpleNamespace(
        name=name, description=f"about {name}", type=kind, options=list(options)
    )


def command(name, command_id, *options):
    return SimpleNamespace(
        name=name,
        id=command_id,
        description=f"about {name}",
        mention=f"</{name}:{command_id}>",
        options=list(options),
    )


def interaction(user="amy"):
    found = MagicMock()
    found.user = user
    found.guild.id = GUILD
    found.guild.name = "Mondstadt"
    found.client.application_id = 77
    found.client.guilds = [1, 2, 3]
    found.client.latency = 0.0456
    found.response.send_message = AsyncMock()
    found.response.edit_message = AsyncMock()
    found.response.defer = AsyncMock()
    found.followup.send = AsyncMock()
    found.message.edit = AsyncMock()
    found.edit_original_response = AsyncMock()
    return found


def button(panel, custom_id):
    return next(c for c in panel.children if getattr(c, "custom_id", None) == custom_id)


def shown(found):
    """Gives the embed and checks the fresh panel sent with it."""
    (), sent = found.response.edit_message.call_args
    assert set(sent) == {"embed", "view"}
    assert isinstance(sent["view"], help_page.HelpPanel)
    assert sent["view"].initial_author == "amy"
    return sent["embed"].to_dict()


async def test_help_command():
    bot = MagicMock()
    bot.tree.fetch_commands = AsyncMock(return_value=[command("ping", 1)])
    cog = help_page.Help(bot)
    assert (cog.help.name, cog.help.description, cog.help.guild_only) == (
        "help",
        "View all the bot's commands",
        True,
    )
    found = interaction()
    await cog.help.callback(cog, found)
    found.response.defer.assert_awaited_once_with()
    (), sent = found.followup.send.call_args
    assert set(sent) == {"embed", "view"}
    assert sent["embed"].to_dict() == OVERVIEW
    panel = sent["view"]
    assert panel.message is found.followup.send.return_value
    assert (panel.timeout, panel.initial_author) == (300, "amy")
    assert [
        (c.label, c.style, c.custom_id, c.url, str(c.emoji), c.row)
        for c in panel.children
        if isinstance(c, discord.ui.Button)
    ] == [
        (
            "Overview",
            discord.ButtonStyle.blurple,
            "overview",
            None,
            "<a:memo:1366940844300701714>",
            0,
        ),
        (
            "Statistics",
            discord.ButtonStyle.blurple,
            "statistics",
            None,
            "<a:server:1366940847093841961>",
            0,
        ),
        (
            "View Server Configuration",
            discord.ButtonStyle.blurple,
            "serverconfig",
            None,
            "<a:config:1366940834628505650>",
            0,
        ),
        (
            "Invite Bot",
            discord.ButtonStyle.link,
            None,
            "https://discord.com/api/oauth2/authorize?client_id=732422232273584198",
            "<a:robot:1366940845697400935>",
            1,
        ),
        (
            "Support Server",
            discord.ButtonStyle.link,
            None,
            "https://discord.gg/kaycd3fxHh",
            "<a:join:1366940843088543775>",
            1,
        ),
        (
            "Website",
            discord.ButtonStyle.link,
            None,
            "https://fischl.app/",
            "<a:globe:1366940841829994557>",
            1,
        ),
    ]
    menu = panel.children[-1]
    assert isinstance(menu, discord.ui.Select)
    assert (menu.placeholder, menu.min_values, menu.max_values, menu.custom_id) == (
        "Browse All Commands",
        1,
        1,
        "browsecommands",
    )
    assert [(o.label, str(o.emoji), o.value, o.description) for o in menu.options] == [
        (title, emoji, title, None) for title, emoji in CATEGORIES
    ]


async def pick(commands, title, user="amy"):
    """Chooses a category from the menu and gives what the message becomes."""
    menu = help_page.HelpPanel(commands, "amy").children[-1]
    menu._values = [title]
    found = interaction(user)
    await menu.callback(found)
    return found


async def page(commands, title):
    found = await pick(commands, title)
    (), sent = found.response.edit_message.call_args
    assert set(sent) == {"embeds", "view"}
    assert isinstance(sent["view"], help_page.HelpPanel)
    assert sent["view"].list is commands
    intro, listing = (embed.to_dict() for embed in sent["embeds"])
    emoji = dict(CATEGORIES)[title]
    assert (intro["title"], intro["color"]) == (f"{emoji} {title}", 0xFFFF00)
    assert listing.get("color") == discord.Color.blurple().value
    assert set(listing) <= {"description", "color", "type", "flags"}
    return intro["description"], listing.get("description")


async def test_menu_is_for_the_author_only():
    found = await pick([], "Tickets", user="bob")
    found.response.send_message.assert_awaited_once_with(NOT_AUTHOR, ephemeral=True)
    found.response.edit_message.assert_not_awaited()


async def test_category_intros():
    intros = {title: (await page([], title))[0] for title, _ in CATEGORIES}
    assert intros == {
        "Tickets": "The following slash commands are used to setup and deal with tickets. To start using tickets instantly, use </ticket settings:1> and the bot will guide you through the procedures of setting up your ticket system!",
        "Co-op System": "The following commands are used to setup co-op system in your server. Use </co-op setup:1> to starting setting up the co-op system, and the bot will guide you through the procedures!",
        "Partnership Panels": "The following slash commands are for managing your server’s partnerships. When a user requests for partnership, a private thread is created, just like a ticket. Server representatives can be invited into the thread, and admins can easily add/remove partnered servers to the customizable and auto-updating partnership panels. Use </partner setup:1> to get started!",
        "Sticky Messages": "The following slash commands are for setting up sticky messages in different channels. Sticky messages will be stayed at the bottom of the channel no matter what messages are sent afterwards. This function is especially useful when you need give your members a heads up on how to use this chat channel or what they need to know before going ahead and sending any messages. Use </sticky enable:1> to setup sticky messages in a channel.",
        "Welcomer": "The following slash commands are for setting up welcome messages in a server. If enabled, the bot will automatically greet new server members in a designated text channel. You can customize your own greetings to tailor to your server's needs. Use </welcome setup:1> to setup welcome messages.",
        "Birthday Wishes": "The following slash commands are for wishing users in your server a happy birthday. Member will receive personalized birthday wishes from their favorite characters in servers that have this system enabled. Use </birthday enable:1> to setup birthday wishes in the server.",
        "Chat Minigames": "The following slash commands are dedicated to random events that appear in a chat channel. Servers that have random events enabled will have exciting mini-games randomly spawned to the chat based on the chat activity and frequency you provided. Use </events settings:1> to setup and configure random chat events in the server.",
        "Booster Roles": "The following slash commands are for rewarding your server boosters with customizable roles and thank-you messages. When a member boosts the server, the bot will automatically send a personalized thank-you message in a designated channel, and the booster can create a custom role. Use </boosterrole setup:1> to setup booster roles in your server.",
        "Vanity/Tag Roles": "We also offer features for vanity roles and tag roles. If enabled, the bot will reward your members with an exclusive role for advertising your server in their status *or* for equipping your server tag.",
        "Utility Commands": "The following slash commands are used for basic functions that many bots offer. These commands are accessible to everyone in the server.",
    }


def group(name, command_id):
    """A command with a subcommand that has an option, and a plain option."""
    return command(
        name, command_id, option("setup", SUB, [option("channel")]), option("loose")
    )


async def test_empty_category_has_no_list():
    assert (await page([group("ticket", 1)], "Welcomer"))[1] is None


@pytest.mark.parametrize(
    "name, title",
    [("ticket", "Tickets"), ("partner", "Partnership Panels")],
)
async def test_simple_lists_leave_out_subcommand_options(name, title):
    assert (await page([group(name, 4)], title))[1] == (
        f"\n\n</{name} setup:4>\n{REPLY} about setup"
        f"\n\n{BLANK}{REPLY} `loose` - about loose"
    )


@pytest.mark.parametrize(
    "name, title",
    [
        ("co-op", "Co-op System"),
        ("sticky", "Sticky Messages"),
        ("welcome", "Welcomer"),
        ("birthday", "Birthday Wishes"),
        ("events", "Chat Minigames"),
        ("boosterrole", "Booster Roles"),
        ("vanity", "Vanity/Tag Roles"),
        ("tag", "Vanity/Tag Roles"),
    ],
)
async def test_full_lists_show_subcommand_options(name, title):
    assert (await page([group(name, 4)], title))[1] == (
        f"\n\n</{name} setup:4>\n{REPLY} about setup"
        f"\n{BLANK}{REPLY} `channel` - about channel"
        f"\n\n{BLANK}{REPLY} `loose` - about loose"
    )


async def test_utility_list_names_each_command():
    assert (await page([group("color", 4), command("invite", 5)], "Utility Commands"))[
        1
    ] == (
        f" \n\n</color:4>\n{REPLY} about color"
        f"\n</color setup:4>\n{REPLY} about setup"
        f"\n{BLANK}{REPLY} `channel` - about channel"
        f"\n{BLANK}{REPLY} `loose` - about loose"
        f" \n\n</invite:5>\n{REPLY} about invite"
    )


async def test_minigame_list():
    plain = [
        "customize",
        "mora",
        "buy",
        "shop",
        "milestones",
        "gift",
        "summon",
        "chest",
        "preview",
    ]
    listed = [group(name, number) for number, name in enumerate(plain, 1)]
    listed += [group("leaderboard", 20), group("moral", 21), group("lb", 22)]
    assert (await page(listed, "Chat Minigames"))[1] == "".join(
        f" \n\n</{name}:{number}>\n{REPLY} about {name}"
        for number, name in enumerate(plain, 1)
    ) + "".join(
        f"\n\n</{name} setup:{number}>\n{REPLY} about setup"
        f"\n{BLANK}{REPLY} `channel` - about channel"
        f"\n\n{BLANK}{REPLY} `loose` - about loose"
        for name, number in [("leaderboard", 20), ("moral", 21)]
    )


async def test_each_command_goes_to_the_first_category_that_fits():
    names = {
        "ticket-partner": "Tickets",
        "co-op-sticky": "Co-op System",
        "partner-tag": "Partnership Panels",
        "sticky-shop": "Sticky Messages",
        "welcome-gift": "Welcomer",
        "birthday-chest": "Birthday Wishes",
        "boosterrole-buy": "Chat Minigames",
        "send-leaderboard": None,
        "boosterrole-x": "Booster Roles",
        "stage": "Vanity/Tag Roles",
        "reload": None,
        "update_rewards": None,
        "Edit Embed": None,
        "emotes": None,
        "database": None,
        "Database": "Utility Commands",
    }
    listed = [command(name, 1) for name in names]
    for title, _ in CATEGORIES:
        text = (await page(listed, title))[1] or ""
        mine = [name for name, home in names.items() if home == title]
        if title == "Utility Commands":
            assert [n for n in names if f"</{n}:1>" in text] == mine
        elif title == "Chat Minigames":
            assert text == ""
        else:
            assert text == ""
            assert mine
    # Commands with no options add nothing outside the utility list, so check with one.
    listed = [group(name, 1) for name in names]
    for title, _ in CATEGORIES:
        text = (await page(listed, title))[1] or ""
        mine = [name for name, home in names.items() if home == title]
        assert [n for n in names if f"</{n} setup:1>" in text] == mine


async def test_buttons_are_for_the_author_only():
    panel = help_page.HelpPanel([], "amy")
    for custom_id in ("overview", "statistics", "serverconfig"):
        found = interaction("bob")
        await button(panel, custom_id).callback(found)
        found.response.send_message.assert_awaited_once_with(NOT_AUTHOR, ephemeral=True)
        found.response.edit_message.assert_not_awaited()
        found.message.edit.assert_not_awaited()


async def test_overview_button():
    found = interaction()
    await button(help_page.HelpPanel([], "amy"), "overview").callback(found)
    assert shown(found) == OVERVIEW


async def test_statistics_button(firebase, monkeypatch):
    firebase("/Uptime").set({"a": {"Uptime": 1700000000}, "b": {"Uptime": 5}})
    memory = type(
        "Memory", (tuple,), {"used": 3 * 1024**3, "total": 4 * 1024**3, "percent": 75.0}
    )
    memory = memory((0, 0, 0, 3 * 1024**3))
    monkeypatch.setattr(help_page.psutil, "virtual_memory", lambda: memory)
    monkeypatch.setattr(help_page.psutil, "cpu_percent", lambda wait: {0.1: 12.5}[wait])
    monkeypatch.setattr(help_page.platform, "system", lambda: "Linux")
    monkeypatch.setattr(help_page.platform, "python_version", lambda: "3.10.1")
    monkeypatch.setattr(help_page.discord, "__version__", "2.6.0")
    monkeypatch.setattr(help_page.firebase_admin, "__version__", "6.0.0")
    found = interaction()
    await button(help_page.HelpPanel([], "amy"), "statistics").callback(found)
    assert shown(found) == {
        "title": "Fischl Discord Bot Statistics <a:server:1366940847093841961>",
        "color": 0x1DBCEB,
        "fields": [
            {
                "name": "<:info:1037445870469267638> Package Info",
                "value": "```OS - Linux\nPython - 3.10.1\ndiscord.py - 2.6.0\nGoogle Firebase - 6.0.0```",
                "inline": False,
            },
            {
                "name": "<:dev:1037445830749204624>  Bot Metadata",
                "value": "> App ID: `77`\n> Last Reboot: <t:1700000000:R>\n> Servers Count: `3`\n> API/Bot Latency: `45ms`",
                "inline": True,
            },
            {
                "name": "📊  Bot Process Data",
                "value": "> CPU Usage: `12.5%`\n> RAM Usage: `3.22 GB`\n> Memory:  `3.00/4.00 GB (75.00%)`",
                "inline": True,
            },
        ],
        "type": "rich",
        "flags": 0,
    }


async def config(found):
    """Presses View Server Configuration and gives the embed the message becomes."""
    listed = []
    await button(help_page.HelpPanel(listed, "amy"), "serverconfig").callback(found)
    found.response.send_message.assert_awaited_once_with(
        "<a:loading:1026905298088243240>  Loading Server Configuration", ephemeral=True
    )
    found.response.edit_message.assert_not_awaited()
    (), sent = found.message.edit.call_args
    assert set(sent) == {"content", "embed", "view"} and sent["content"] is None
    assert isinstance(sent["view"], help_page.HelpPanel)
    assert sent["view"].list is listed and sent["view"].initial_author == "amy"
    found.edit_original_response.assert_awaited_once_with(
        content=f"{YES} Loaded Server Configuration"
    )
    embed = sent["embed"].to_dict()
    assert all(field["inline"] is True for field in embed["fields"])
    assert {k: v for k, v in embed.items() if k != "fields"} == {
        "title": "Server Configuration <a:config:1366940834628505650>",
        "description": "You could view the server settings of the bot in this page instantly. The configuration for **Mondstadt** is as follows:",
        "color": 0x1DBCEB,
        "type": "rich",
        "flags": 0,
    }
    return [(field["name"], field["value"]) for field in embed["fields"]]


MINIGAME = (
    "INSERT INTO minigame_settings (channel_id, minigames_enabled) VALUES ($1, $2)"
)


async def test_server_configuration_cuts_a_long_minigame_list(pool, firebase):
    found = await stores(pool)
    firebase("/Tickets").set({"a": {"Server ID": 99}})
    firebase("/Welcome").set({"a": {"Server ID": 99}})
    ids = [10**18 + number for number in range(40)]
    found.guild.text_channels = [MagicMock(id=number) for number in ids]
    for channel_id in ids:
        await pool.execute(MINIGAME, channel_id, True)
    value = dict(await config(found))["Chat Minigames"]
    lines = value.split("\n")
    assert lines[0] == f"{YES} Enabled" and lines[1] == f"{REPLY} <#{ids[0]}>"
    kept = len(lines) - 2
    assert lines[-1] == f"... *({40 - kept} more)*" and 0 < kept < 40
    assert len(value) <= 1024


async def stores(pool):
    for store in (coOpStore, birthdayStore, stickyStore):
        await store.create(pool)
    await ensure_minigame_settings_table(pool)
    found = interaction()
    found.client.pool = pool
    found.guild.text_channels = [MagicMock(id=number) for number in (1, 2, 3)]
    found.guild.threads = [MagicMock(id=9)]
    return found


async def test_server_configuration_with_everything_off(pool, firebase):
    found = await stores(pool)
    firebase("/Tickets").set(
        {"a": {"Server ID": 99, "Category ID": 1, "Log Channel ID": 2}}
    )
    firebase("/Welcome").set({"a": {"Server ID": 99}})
    firebase("Booster Role/10").set({"channel": 5})
    assert await config(found) == [
        (name, f"{NO} Disabled")
        for name in (
            "Ticket System",
            "Co-op System",
            "Birthday Wishes",
            "Sticky Messages",
            "Chat Minigames",
            "Welcome Messages",
            "Partnership System",
            "Booster Roles",
        )
    ]


async def test_server_configuration_with_everything_on(pool, firebase):
    found = await stores(pool)
    firebase("/Tickets").set(
        {
            "a": {"Server ID": 99, "Category ID": 1, "Log Channel ID": 2},
            "b": {"Server ID": GUILD, "Category ID": 31, "Log Channel ID": 32},
            "c": {"Server ID": GUILD, "Category ID": 41, "Log Channel ID": 42},
        }
    )
    await coOpStore.enable(pool, GUILD, 50, 51, 52, 53, 54)
    await birthdayStore.enable(pool, GUILD, 60, 61, 62, True)
    for channel_id in (3, 1, 1, 9, 777):
        await stickyStore.add(pool, channel_id, channel_id * 10, "rules")
    for channel_id, on in ((3, True), (1, True), (2, False), (777, True)):
        await pool.execute(MINIGAME, channel_id, on)
    firebase("/Welcome").set(
        {
            "a": {
                "Server ID": GUILD,
                "Welcome Channel ID": 70,
                "Welcome Image Enabled": True,
            },
            "b": {
                "Server ID": GUILD,
                "Welcome Channel ID": 71,
                "Welcome Image Enabled": False,
            },
        }
    )
    firebase("/Partner/config/10").set(
        {"request_channel": 80, "panel_channel": 81, "log_channel": 82}
    )
    firebase("Booster Role/10").set(
        {"base_role": 90, "system_channel": 91, "channel": 92}
    )
    assert await config(found) == [
        (
            "Ticket System",
            f"{YES} Enabled\n{REPLY} **Category:** <#31>\n{REPLY} **Log Channel:** <#32>",
        ),
        (
            "Co-op System",
            f"{YES} Enabled\n{REPLY} **Co-op Channel:** <#50>\n{REPLY} **NA Helper Role:** <@&51>\n{REPLY} **EU Helper Role:** <@&52>\n{REPLY} **Asia Helper Role:** <@&53>\n{REPLY} **SAR Helper Role:** <@&54>",
        ),
        (
            "Birthday Wishes",
            f"{YES} Enabled\n{REPLY} **Channel:** <#60>\n{REPLY} **Birthday Role:** <@&62>",
        ),
        (
            "Sticky Messages",
            f"{YES} Enabled\n{REPLY} <#1>\n{REPLY} <#1>\n{REPLY} <#3>\n{REPLY} <#9>\n",
        ),
        ("Chat Minigames", f"{YES} Enabled\n{REPLY} <#1>\n{REPLY} <#3>\n"),
        (
            "Welcome Messages",
            f"{YES} Enabled\n{REPLY} **Welcome Channel:** <#70>\n{REPLY} **Custom Image Background:** `Uploaded`\n",
        ),
        (
            "Partnership System",
            f"{YES} Enabled\n{REPLY} **Request Channel:** <#80>\n{REPLY} **Panel Channel:** <#81>\n{REPLY} **Log Channel:** <#82>\n{REPLY} **Partner Role:** <@&None>",
        ),
        (
            "Booster Roles",
            f"{YES} Enabled\n{REPLY} **Base Role:** <@&90>\n{REPLY} **System Channel:** <#91>\n{REPLY} **Public Channel:** <#92>\n{REPLY} **Log Channel:** <#None>",
        ),
    ]


async def test_server_configuration_without_a_welcome_image(pool, firebase):
    found = await stores(pool)
    firebase("/Tickets").set({"a": {"Server ID": 99}})
    firebase("/Welcome").set(
        {
            "a": {
                "Server ID": GUILD,
                "Welcome Channel ID": 70,
                "Welcome Image Enabled": 0,
            }
        }
    )
    fields = dict(await config(found))
    assert fields["Welcome Messages"] == (
        f"{YES} Enabled\n{REPLY} **Welcome Channel:** <#70>"
        f"\n{REPLY} **Custom Image Background:** `Not uploaded`\n"
    )


@pytest.mark.parametrize("empty", ["/Tickets", "/Welcome"])
async def test_server_configuration_fails_with_no_tickets_or_welcomes_at_all(
    pool, firebase, empty
):
    found = await stores(pool)
    for path in {"/Tickets", "/Welcome"} - {empty}:
        firebase(path).set({"a": {"Server ID": 99}})
    with pytest.raises(AttributeError):
        await button(help_page.HelpPanel([], "amy"), "serverconfig").callback(found)
    found.response.send_message.assert_awaited_once()
    found.message.edit.assert_not_awaited()


async def test_timeout_turns_off_all_but_the_links():
    panel = help_page.HelpPanel([], "amy")
    panel.message = MagicMock()
    panel.message.edit = AsyncMock()
    await panel.on_timeout()
    panel.message.edit.assert_awaited_once_with(view=panel)
    assert [child.disabled for child in panel.children] == [
        True,
        True,
        True,
        False,
        False,
        False,
        True,
    ]
    last = panel.children[-1].options[-1]
    assert (last.label, last.value, str(last.emoji), last.default) == (
        "Disabled due to timeout",
        "X",
        NO,
        True,
    )
    assert len(panel.children[-1].options) == 11
    assert panel.is_finished()


async def test_timeout_with_the_message_gone_or_never_kept():
    panel = help_page.HelpPanel([], "amy")
    await panel.on_timeout()
    assert panel.is_finished()
    panel = help_page.HelpPanel([], "amy")
    panel.message = MagicMock()
    panel.message.edit = AsyncMock(
        side_effect=discord.NotFound(MagicMock(status=404), "gone")
    )
    await panel.on_timeout()
    assert panel.is_finished()


async def test_every_press_gives_a_new_panel_so_the_timeout_starts_over(firebase):
    firebase("/Uptime").set({"a": {"Uptime": 5}})
    for custom_id in ("overview", "statistics"):
        panel = help_page.HelpPanel([], "amy")
        found = interaction()
        await button(panel, custom_id).callback(found)
        assert found.response.edit_message.call_args[1]["view"] is not panel
    panel = help_page.HelpPanel([], "amy")
    menu = panel.children[-1]
    menu._values = ["Tickets"]
    found = interaction()
    await menu.callback(found)
    assert found.response.edit_message.call_args[1]["view"] is not panel


async def test_timeout_lets_other_edit_failures_through():
    panel = help_page.HelpPanel([], "amy")
    panel.message = MagicMock()
    panel.message.edit = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(status=403), "no")
    )
    with pytest.raises(discord.Forbidden):
        await panel.on_timeout()
    assert not panel.is_finished()


async def test_server_configuration_fails_on_a_record_with_no_server(pool, firebase):
    found = await stores(pool)
    firebase("/Tickets").set({"a": {"Category ID": 1}})
    with pytest.raises(KeyError, match="Server ID"):
        await button(help_page.HelpPanel([], "amy"), "serverconfig").callback(found)
