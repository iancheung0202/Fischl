"""`/help`: the command list by category, bot statistics and a server's settings."""

import platform

import discord
import firebase_admin
import psutil
from discord import app_commands
from discord.ext import commands
from firebase_admin import db

from commands.Birthday import birthdayStore
from commands.CoOp import coOpStore
from commands.Sticky import stickyStore
from utils.commands import SlashCommand

BLANK = "<:blank:1036792889121980426>"
REPLY = "<:reply:1036792837821435976>"
YES = "<:yes:1036811164891480194>"
NO = "<:no:1036810470860013639>"
COLOR = 0x1DBCEB
SUBCOMMAND = discord.AppCommandOptionType.subcommand
NOT_AUTHOR = f"{NO} You are not the author of this command"
DISABLED = f"{NO} Disabled"
CATEGORY_COLOR = 0xFFFF00
LOADING = "<a:loading:1026905298088243240>  Loading Server Configuration"
LINKS = (
    (
        "Invite Bot",
        "https://discord.com/api/oauth2/authorize?client_id=732422232273584198",
        "<a:robot:1366940845697400935>",
    ),
    ("Support Server", "https://discord.gg/kaycd3fxHh", "<a:join:1366940843088543775>"),
    ("Website", "https://fischl.app/", "<a:globe:1366940841829994557>"),
)
PLAIN_MINIGAMES = (
    "customize",
    "mora",
    "buy",
    "shop",
    "milestones",
    "gift",
    "summon",
    "chest",
    "preview",
)
MINIGAMES = (*PLAIN_MINIGAMES, "events")
NOT_UTILITY = (
    "reload",
    "update_rewards",
    "send-leaderboard",
    "Edit Embed",
    "emotes",
    "database",
)


def named(*words):
    """Gives a check for commands whose name holds one of the words."""
    return lambda command: any(word in command.name for word in words)


def is_minigame(command):
    """Says if a command belongs to the chat minigames."""
    board = "leaderboard" in command.name and "send" not in command.name
    return board or named(*MINIGAMES)(command)


def is_utility(command):
    """Says if a command no other category took may be listed as a utility."""
    return not named(*NOT_UTILITY)(command)


def option_line(option):
    """Gives the indented line for one option."""
    return f"\n{BLANK}{REPLY} `{option.name}` - {option.description}"


def subcommand_line(command, sub):
    """Gives a subcommand's mention with what it does underneath."""
    return f"</{command.name} {sub.name}:{command.id}>\n{REPLY} {sub.description}"


def brief(command):
    """Lists a command's subcommands without their options."""
    return "".join(
        (
            f"\n\n{subcommand_line(command, sub)}"
            if sub.type == SUBCOMMAND
            else f"\n{option_line(sub)}"
        )
        for sub in command.options
    )


def full(command):
    """Lists a command's subcommands, each with its options."""
    return "".join(
        (
            f"\n\n{subcommand_line(command, sub)}"
            + "".join(map(option_line, sub.options))
            if sub.type == SUBCOMMAND
            else f"\n{option_line(sub)}"
        )
        for sub in command.options
    )


def headed(command):
    """Names the command itself."""
    return f" \n\n{command.mention}\n{REPLY} {command.description}"


def utility(command):
    """Names the command, then lists its subcommands and options closely."""
    return headed(command) + "".join(
        (
            f"\n{subcommand_line(command, sub)}"
            + "".join(map(option_line, sub.options))
            if sub.type == SUBCOMMAND
            else option_line(sub)
        )
        for sub in command.options
    )


def minigame(command):
    """Names a single minigame command, or lists the subcommands of a group."""
    return headed(command) if command.name in PLAIN_MINIGAMES else full(command)


def categories():
    """Gives each category's title, emoji, intro, command check and way to list one."""
    return (
        (
            "Tickets",
            "🎫",
            f"The following slash commands are used to setup and deal with tickets. To start using tickets instantly, use {SlashCommand('ticket settings')} and the bot will guide you through the procedures of setting up your ticket system!",
            named("ticket"),
            brief,
        ),
        (
            "Co-op System",
            "🎮",
            f"The following commands are used to setup co-op system in your server. Use {SlashCommand('co-op setup')} to starting setting up the co-op system, and the bot will guide you through the procedures!",
            named("co-op"),
            full,
        ),
        (
            "Partnership Panels",
            "🤝",
            f"The following slash commands are for managing your server’s partnerships. When a user requests for partnership, a private thread is created, just like a ticket. Server representatives can be invited into the thread, and admins can easily add/remove partnered servers to the customizable and auto-updating partnership panels. Use {SlashCommand('partner setup')} to get started!",
            named("partner"),
            brief,
        ),
        (
            "Sticky Messages",
            "🫧",
            f"The following slash commands are for setting up sticky messages in different channels. Sticky messages will be stayed at the bottom of the channel no matter what messages are sent afterwards. This function is especially useful when you need give your members a heads up on how to use this chat channel or what they need to know before going ahead and sending any messages. Use {SlashCommand('sticky enable')} to setup sticky messages in a channel.",
            named("sticky"),
            full,
        ),
        (
            "Welcomer",
            "👋",
            f"The following slash commands are for setting up welcome messages in a server. If enabled, the bot will automatically greet new server members in a designated text channel. You can customize your own greetings to tailor to your server's needs. Use {SlashCommand('welcome settings')} to setup welcome messages.",
            named("welcome"),
            full,
        ),
        (
            "Birthday Wishes",
            "🎂",
            f"The following slash commands are for wishing users in your server a happy birthday. Member will receive personalized birthday wishes from their favorite characters in servers that have this system enabled. Use {SlashCommand('birthday enable')} to setup birthday wishes in the server.",
            named("birthday"),
            full,
        ),
        (
            "Chat Minigames",
            "🎉",
            f"The following slash commands are dedicated to random events that appear in a chat channel. Servers that have random events enabled will have exciting mini-games randomly spawned to the chat based on the chat activity and frequency you provided. Use {SlashCommand('events settings')} to setup and configure random chat events in the server.",
            is_minigame,
            minigame,
        ),
        (
            "Booster Roles",
            "💎",
            f"The following slash commands are for rewarding your server boosters with customizable roles and thank-you messages. When a member boosts the server, the bot will automatically send a personalized thank-you message in a designated channel, and the booster can create a custom role. Use {SlashCommand('boosterrole setup')} to setup booster roles in your server.",
            named("boosterrole"),
            full,
        ),
        (
            "Vanity/Tag Roles",
            "👤",
            "We also offer features for vanity roles and tag roles. If enabled, the bot will reward your members with an exclusive role for advertising your server in their status *or* for equipping your server tag.",
            named("vanity", "tag"),
            full,
        ),
        (
            "Utility Commands",
            "🛠️",
            "The following slash commands are used for basic functions that many bots offer. These commands are accessible to everyone in the server.",
            is_utility,
            utility,
        ),
    )


def pages(listed):
    """Sorts the commands into the first category that takes each: {title: page}."""
    sorted_ = categories()
    lists = {title: "" for title, *_ in sorted_}
    for command in listed:
        for title, _, _, takes, written in sorted_:
            if takes(command):
                lists[title] += written(command)
                break
    return {title: (emoji, intro, lists[title]) for title, emoji, intro, *_ in sorted_}


def overview():
    """Gives the embed that opens `/help`."""
    embed = discord.Embed(
        title="Fischl Help",
        description="> <a:hoyoverse:1366950037728530472> Fischl is a powerful utility Discord bot **designed with all Hoyoverse communities in mind**. Trusted by numerous large servers, Fischl makes server management effortless with **easy-to-use systems** for *tickets, co-op matchmaking, partnerships, welcomes, birthdays, and fun minigames*. <:HuTaoWow:1253167030748840067>",
        color=COLOR,
    )
    embed.add_field(
        name="<:genshin_impact:1103720959950725190> Support Server",
        value="Head over to our **[support server](https://discord.gg/kaycd3fxHh)** if you have any suggestions, questions or bug reports! :writing_hand:",
        inline=True,
    )
    embed.add_field(
        name="<:slash:1037445915348324505> Command Usage",
        value="This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` or **select a category** below to see the list of available bot commands.",
        inline=True,
    )
    return embed


def statistics(client):
    """Gives the embed with the bot's packages, uptime and machine load."""
    embed = discord.Embed(
        title="Fischl Discord Bot Statistics <a:server:1366940847093841961>",
        color=COLOR,
    )
    memory = psutil.virtual_memory()
    embed.add_field(
        name="<:info:1037445870469267638> Package Info",
        value=(
            f"```OS - {platform.system()}\n"
            f"Python - {platform.python_version()}\n"
            f"discord.py - {discord.__version__}\n"
            f"Google Firebase - {firebase_admin.__version__}```"
        ),
        inline=False,
    )
    uptime = next(iter(db.reference("/Uptime").get().values()))["Uptime"]
    embed.add_field(
        name="<:dev:1037445830749204624>  Bot Metadata",
        value=(
            f"> App ID: `{client.application_id}`"
            f"\n> Last Reboot: <t:{uptime}:R>"
            f"\n> Servers Count: `{len(client.guilds)}`"
            f"\n> API/Bot Latency: `{int(round(client.latency * 1000, 1))}ms`"
        ),
        inline=True,
    )
    embed.add_field(
        name="📊  Bot Process Data",
        value=(
            f"> CPU Usage: `{psutil.cpu_percent(0.1)}%`"
            f"\n> RAM Usage: `{memory.used/1000000000:.2f} GB`"
            f"\n> Memory:  `{memory.used/(1024**3):.2f}/{memory.total/(1024**3):.2f} GB ({(memory.percent):.2f}%)`"
        ),
        inline=True,
    )
    return embed


MINIGAME_CHANNELS = "SELECT channel_id FROM minigame_settings WHERE minigames_enabled = TRUE AND channel_id = ANY($1::bigint[])"
# Leaves room in a 1024-character field for the "more" line.
FIELD_ROOM = 1024 - 16


async def stuck_channels(pool, guild):
    """Gives the server's channel ids once per message stuck there, in channel order."""
    stuck = await stickyStore.channels(pool)
    places = [*guild.text_channels, *guild.threads]
    return [place.id for place in places for _ in range(stuck.count(place.id))]


def of_server(path, guild):
    """Gives the first record under a Firebase path that is for this server, or None."""
    records = db.reference(path).get().values()
    return next((found for found in records if found["Server ID"] == guild.id), None)


def enabled(*lines):
    """Gives a field that says a system is on, one line per setting."""
    return "\n".join([f"{YES} Enabled", *(f"{REPLY} {line}" for line in lines)])


def tickets(guild):
    """Gives the ticket field, or None with tickets off."""
    found = of_server("/Tickets", guild)
    return found and enabled(
        f"**Category:** <#{found['Category ID']}>",
        f"**Log Channel:** <#{found['Log Channel ID']}>",
    )


async def coop(pool, guild):
    """Gives the co-op field, or None with co-op off."""
    found = await coOpStore.server(pool, guild.id)
    return found and enabled(
        f"**Co-op Channel:** <#{found['channel_id']}>",
        f"**NA Helper Role:** <@&{found['na_role_id']}>",
        f"**EU Helper Role:** <@&{found['eu_role_id']}>",
        f"**Asia Helper Role:** <@&{found['asia_role_id']}>",
        f"**SAR Helper Role:** <@&{found['sar_role_id']}>",
    )


async def birthday(pool, guild):
    """Gives the birthday field, or None with wishes off."""
    found = await birthdayStore.server(pool, guild.id)
    return found and enabled(
        f"**Channel:** <#{found['channel_id']}>",
        f"**Birthday Role:** <@&{found['role_id']}>",
    )


async def sticky(pool, guild):
    """Gives the field listing channels with a stuck message, or nothing."""
    stuck = await stuck_channels(pool, guild)
    return stuck and enabled(*(f"<#{channel_id}>" for channel_id in stuck)) + "\n"


async def minigames(pool, guild):
    """Gives the field listing channels with chat minigames on, or nothing."""
    places = [place.id for place in guild.text_channels]
    found = {row["channel_id"] for row in await pool.fetch(MINIGAME_CHANNELS, places)}
    lines = [f"{REPLY} <#{place}>\n" for place in places if place in found]
    value, extra = f"{YES} Enabled\n", 0
    for line in lines:
        if len(value) + len(line) > FIELD_ROOM:
            extra += 1
        else:
            value += line
    return lines and value + (f"... *({extra} more)*" if extra else "")


def welcome(guild):
    """Gives the welcome field, or None with welcomes off."""
    found = of_server("/Welcome", guild)
    if not found:
        return None
    channel = f"**Welcome Channel:** <#{found['Welcome Channel ID']}>"
    image = "Uploaded" if found["Welcome Image Enabled"] else "Not uploaded"
    return enabled(channel, f"**Custom Image Background:** `{image}`") + "\n"


def partnership(guild):
    """Gives the partnership field, or None with partnerships off."""
    found = db.reference(f"/Partner/config/{guild.id}").get()
    return found and enabled(
        f"**Request Channel:** <#{found.get('request_channel')}>",
        f"**Panel Channel:** <#{found.get('panel_channel')}>",
        f"**Log Channel:** <#{found.get('log_channel')}>",
        f"**Partner Role:** <@&{found.get('partner_role')}>",
    )


def boosters(guild):
    """Gives the booster role field, or nothing with booster roles off."""
    found = db.reference(f"Booster Role/{guild.id}").get()
    return (
        found
        and "base_role" in found
        and enabled(
            f"**Base Role:** <@&{found.get('base_role')}>",
            f"**System Channel:** <#{found.get('system_channel')}>",
            f"**Public Channel:** <#{found.get('channel')}>",
            f"**Log Channel:** <#{found.get('log')}>",
        )
    )


async def configuration(pool, guild):
    """Gives the embed that says which systems the server has on, and where."""
    embed = discord.Embed(
        title="Server Configuration <a:config:1366940834628505650>",
        description=f"You could view the server settings of the bot in this page instantly. The configuration for **{guild.name}** is as follows:",
        color=COLOR,
    )
    systems = {
        "Ticket System": tickets(guild),
        "Co-op System": await coop(pool, guild),
        "Birthday Wishes": await birthday(pool, guild),
        "Sticky Messages": await sticky(pool, guild),
        "Chat Minigames": await minigames(pool, guild),
        "Welcome Messages": welcome(guild),
        "Partnership System": partnership(guild),
        "Booster Roles": boosters(guild),
    }
    for name, value in systems.items():
        embed.add_field(name=name, value=value or DISABLED, inline=True)
    return embed


async def is_stranger(author, interaction):
    """Tells anyone but the member who ran `/help` that the panel is not theirs."""
    if author != interaction.user:
        await interaction.response.send_message(NOT_AUTHOR, ephemeral=True)
    return author != interaction.user


class Select(discord.ui.Select):
    """The menu that shows one category's commands."""

    def __init__(self, list, initial_author):
        self.list, self.initial_author = list, initial_author
        self.pages = pages(list)
        super().__init__(
            placeholder="Browse All Commands",
            max_values=1,
            min_values=1,
            options=[
                discord.SelectOption(label=title, emoji=emoji)
                for title, (emoji, _, _) in self.pages.items()
            ],
            custom_id="browsecommands",
        )

    async def callback(self, interaction: discord.Interaction):
        if await is_stranger(self.initial_author, interaction):
            return
        title = self.values[0]
        emoji, intro, commands_ = self.pages[title]
        await interaction.response.edit_message(
            embeds=[
                discord.Embed(
                    title=f"{emoji} {title}", description=intro, color=CATEGORY_COLOR
                ),
                discord.Embed(description=commands_, color=discord.Color.blurple()),
            ],
            view=HelpPanel(self.list, self.initial_author),
        )


class HelpPanel(discord.ui.View):
    """The buttons and category menu under `/help`, for the member who ran it."""

    def __init__(self, list=None, initial_author=None):
        self.list = list
        self.initial_author = initial_author
        super().__init__(timeout=300)
        for label, url, emoji in LINKS:
            self.add_item(
                discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.link,
                    url=url,
                    row=1,
                    emoji=emoji,
                )
            )
        self.add_item(Select(self.list, self.initial_author))

    async def on_timeout(self) -> None:
        for child in self.children:
            if getattr(child, "style", None) == discord.ButtonStyle.link:
                continue
            child.disabled = True
            if isinstance(child, Select):
                child.add_option(
                    label="Disabled due to timeout", value="X", emoji=NO, default=True
                )
        if hasattr(self, "message"):
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
        self.stop()

    def fresh(self):
        """Gives a new panel for the same member, so the timeout starts over."""
        return HelpPanel(self.list, self.initial_author)

    @discord.ui.button(
        label="Overview",
        style=discord.ButtonStyle.blurple,
        custom_id="overview",
        row=0,
        emoji="<a:memo:1366940844300701714>",
    )
    async def overview(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if await is_stranger(self.initial_author, interaction):
            return
        await interaction.response.edit_message(embed=overview(), view=self.fresh())

    @discord.ui.button(
        label="Statistics",
        style=discord.ButtonStyle.blurple,
        custom_id="statistics",
        row=0,
        emoji="<a:server:1366940847093841961>",
    )
    async def statistics(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if await is_stranger(self.initial_author, interaction):
            return
        await interaction.response.edit_message(
            embed=statistics(interaction.client), view=self.fresh()
        )

    @discord.ui.button(
        label="View Server Configuration",
        style=discord.ButtonStyle.blurple,
        custom_id="serverconfig",
        row=0,
        emoji="<a:config:1366940834628505650>",
    )
    async def tutorial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if await is_stranger(self.initial_author, interaction):
            return
        await interaction.response.send_message(LOADING, ephemeral=True)
        embed = await configuration(interaction.client.pool, interaction.guild)
        await interaction.message.edit(content=None, embed=embed, view=self.fresh())
        await interaction.edit_original_response(
            content=f"{YES} Loaded Server Configuration"
        )


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="View all the bot's commands")
    @app_commands.guild_only()
    async def help(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        view = HelpPanel(await self.bot.tree.fetch_commands(), interaction.user)
        view.message = await interaction.followup.send(embed=overview(), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
