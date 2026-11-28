"""/events settings: the panel where admins set a channel's minigames, chests and sigils."""

import datetime
import re

import discord
from discord import app_commands
from discord.ext import commands

from commands.Events.config import (
    DEFAULT_CHAT_MAX_CAP,
    DEFAULT_CHAT_MSG_RANGE,
    DEFAULT_CHAT_RANGE,
    DOT_EMOTE,
    EMOTE_MAX_STREAK,
    EMOTE_STREAK,
    LETTER_EMOTES,
    LETTER_LIST,
    MINIGAME_TITLES,
    MORA_CHEST_MAX_STREAK_BONUS,
    MORA_CHEST_REWARDS,
    MORA_CHEST_SPAWN_REQ,
    MORA_CHEST_STREAK_BONUS,
    MORA_CHEST_TIERS,
    MORA_CHEST_UPGRADE_CHANCES,
    MORA_CHEST_UPGRADE_TIMES,
    MORA_EMOTE,
    NO_EMOTE,
    SIGIL_CURRENCY_NAME,
    SIGIL_EMOTE,
    YES_EMOTE,
)
from commands.Events.helperFunctions import (
    GUILD_SETTINGS_FALLBACK,
    get_channel_settings,
    get_guild_settings,
    parse_boosted_roles,
    serialize_boosted_roles,
    upsert_channel_settings,
    upsert_guild_settings,
)

# What chance of a game per message each frequency in the menu stands for.
FREQUENCIES = {
    2: "Annoying (~50%)",
    10: "Very Frequent (~10%)",
    20: "Frequent (~5%)",
    30: "Occasional (~3%)",
    50: "Uncommon (~2%)",
    100: "Rare (~1%)",
    200: "Very Rare (~0.5%)",
}
# Each tab: the column that turns it on and the word on its toggle button.
TABS = {
    "minigames": ("minigames_enabled", "Games"),
    "chests": ("chests_enabled", "Chests"),
    "sigils": ("chat_enabled", SIGIL_CURRENCY_NAME),
}
BOOST = re.compile(r"\+?\d+")


class Refused(Exception):
    """What was typed cannot be saved; the text is what to tell the admin."""


def numbers(text: str, kind, problem: str) -> list:
    """Reads comma-separated numbers."""
    try:
        return [kind(part.strip()) for part in text.split(",") if part.strip()]
    except ValueError:
        raise Refused(problem)


def words(least_two_of: str):
    """Gives a reader of comma-separated texts that asks for at least two."""

    def read(text: str) -> list:
        found = [part.strip() for part in text.split(",") if part.strip()]
        if len(found) < 2:
            raise Refused(f"Provide at least 2 {least_two_of}.")
        return found

    return read


def multiplier(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise Refused("Invalid number.")
    if not 0.01 <= value <= 99.99:
        raise Refused("Multiplier must be between 0.01 and 99.99.")
    return value


def rewards(text: str) -> list:
    values = numbers(text, int, "Invalid integer list.")
    if len(values) < 2:
        raise Refused("Provide at least 2 reward values.")
    return values


def chances(text: str) -> list:
    values = numbers(text, float, "Invalid decimal list.")
    if not all(0 <= value <= 1 for value in values):
        raise Refused("Each chance must be between 0 and 1.")
    return values


def span(text: str) -> list:
    """Reads one number, or a lowest and a highest."""
    values = numbers(text, int, "Invalid integer(s).")
    if (
        len(values) not in (1, 2)
        or any(value < 1 for value in values)
        or values != sorted(values)
    ):
        raise Refused("Provide 1 (exact) or 2 (min, max) positive integers.")
    return values


def whole(least: int, problem: str):
    """Gives a reader of one whole number that is at least `least`."""

    def read(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise Refused("Invalid integer.")
        if value < least:
            raise Refused(problem)
        return value

    return read


def joined(values) -> str:
    return ", ".join(str(value) for value in values)


def as_is(value) -> str:
    return str(value)


class Setting:
    """One value an admin edits in a box: where it is stored, how its button and box look, how it is read."""

    def __init__(
        self,
        *,
        tab,
        column,
        per_server,
        fallback,
        button,
        emoji,
        row,
        title,
        label,
        read,
        placeholder=None,
        shown=as_is,
        empty=None,
    ):
        self.tab, self.column, self.per_server = tab, column, per_server
        self.fallback, self.button, self.emoji, self.row = fallback, button, emoji, row
        self.title, self.label, self.read = title, label, read
        self.placeholder, self.shown, self.empty = placeholder, shown, empty

    async def current(self, pool, channel):
        """Gives the saved value, or the default one."""
        if self.per_server:
            saved = await get_guild_settings(pool, channel.guild.id)
        else:
            saved = await get_channel_settings(pool, channel.id)
        return saved.get(self.column, self.fallback)

    async def save(self, pool, channel, value):
        if self.per_server:
            await upsert_guild_settings(pool, channel.guild.id, **{self.column: value})
        else:
            await upsert_channel_settings(pool, channel.id, **{self.column: value})


SETTINGS = [
    Setting(
        tab="minigames",
        column="mora_multiplier",
        per_server=False,
        fallback=1.0,
        button="Multiplier",
        emoji="💰",
        row=2,
        title="Set Mora Multiplier",
        label="Multiplier (e.g. 1.0 = 1x, 2.0 = 2x)",
        read=multiplier,
    ),
    Setting(
        tab="chests",
        column="chests_base_upgrade_chances",
        per_server=True,
        fallback=MORA_CHEST_UPGRADE_TIMES,
        button="Base Upgrade Chances",
        emoji="🔢",
        row=1,
        title="Base Upgrade Chances",
        label="Number of upgrade chances",
        read=whole(0, "Must be non-negative."),
        placeholder="4",
    ),
    Setting(
        tab="chests",
        column="chests_spawn_req",
        per_server=True,
        fallback=[4, 6],
        button="Spawn Requirement",
        emoji="📊",
        row=1,
        title="Chest Spawn Requirement",
        label="Exact OR min, max (effortful messages)",
        read=span,
        placeholder="4, 6",
        shown=joined,
        empty="4, 6",
    ),
    Setting(
        tab="chests",
        column="chests_streak_bonus",
        per_server=True,
        fallback=MORA_CHEST_STREAK_BONUS,
        button="Streak Bonus",
        emoji=EMOTE_STREAK,
        row=1,
        title="Streak Bonus",
        label="Streak bonus per day",
        read=whole(0, "Must be non-negative."),
    ),
    Setting(
        tab="chests",
        column="chests_max_streak_bonus",
        per_server=True,
        fallback=MORA_CHEST_MAX_STREAK_BONUS,
        button="Max Streak Bonus",
        emoji=EMOTE_MAX_STREAK,
        row=1,
        title="Streak Bonus",
        label="Maximum streak bonus",
        read=whole(0, "Must be non-negative."),
    ),
    Setting(
        tab="chests",
        column="chests_tier_names",
        per_server=True,
        fallback=MORA_CHEST_TIERS,
        button="Tier Names",
        emoji="📦",
        row=2,
        title="Chest Tier Names",
        label="Tier names (comma-separated)",
        read=words("tier names"),
        placeholder="Common, Exquisite, Precious, Luxurious",
        shown=joined,
    ),
    Setting(
        tab="chests",
        column="chests_tier_rewards",
        per_server=True,
        fallback=MORA_CHEST_REWARDS,
        button="Tier Rewards",
        emoji="💰",
        row=2,
        title="Chest Tier Rewards",
        label="Rewards (comma-separated integers)",
        read=rewards,
        placeholder="2500, 7500, 15000, 30000",
        shown=joined,
    ),
    Setting(
        tab="chests",
        column="chests_upgrade_chances",
        per_server=True,
        fallback=MORA_CHEST_UPGRADE_CHANCES,
        button="Tier Upgrade Chances",
        emoji="🔼",
        row=2,
        title="Chest Upgrade Chances",
        label="Chances (comma-separated decimals 0-1)",
        read=chances,
        placeholder="0.30, 0.15, 0.20",
        shown=lambda values: ", ".join(f"{float(x):.2f}" for x in values or []),
    ),
    Setting(
        tab="chests",
        column="chests_emotes",
        per_server=True,
        fallback=GUILD_SETTINGS_FALLBACK["chests_emotes"],
        button="Tier Emotes",
        emoji="🎨",
        row=2,
        title="Chest Emotes",
        label="Emotes (comma-separated)",
        read=words("emotes"),
        placeholder="<a:common:1371641883121680465>, <a:exquisite:1371641856344985620>, ...",
        shown=joined,
    ),
    Setting(
        tab="chests",
        column="chests_icons",
        per_server=True,
        fallback=GUILD_SETTINGS_FALLBACK["chests_icons"],
        button="Tier Icons",
        emoji="🖼️",
        row=2,
        title="Chest Icons",
        label="Icon URLs (comma-separated)",
        read=words("icon URLs"),
        placeholder="https://i.imgur.com/2kOfLSC.png, https://i.imgur.com/DBPQSAu.png, ...",
        shown=joined,
    ),
    Setting(
        tab="sigils",
        column="chat_range",
        per_server=False,
        fallback=[19, 25],
        button="Earning Range",
        emoji=SIGIL_EMOTE,
        row=2,
        title="Sigil Earning Range",
        label=f"Exact OR min, max ({SIGIL_CURRENCY_NAME} per batch)",
        read=span,
        placeholder="19, 25",
        shown=joined,
        empty="19, 25",
    ),
    Setting(
        tab="sigils",
        column="chat_msg_range",
        per_server=False,
        fallback=[15, 20],
        button="Messages per Batch",
        emoji="💬",
        row=2,
        title="Messages per Batch",
        label="Exact OR min, max (messages per batch)",
        read=span,
        placeholder="15, 20",
        shown=joined,
        empty="15, 20",
    ),
    Setting(
        tab="sigils",
        column="chat_max_cap",
        per_server=True,
        fallback=DEFAULT_CHAT_MAX_CAP,
        button="Max Daily Cap (Server)",
        emoji="📊",
        row=2,
        title=f"Max Daily {SIGIL_CURRENCY_NAME}",
        label=f"Maximum Daily {SIGIL_CURRENCY_NAME} (server-wide)",
        read=whole(1, "Must be at least 1."),
    ),
]


def parse_channel_id(interaction) -> int:
    """Gives the channel a settings panel is about, read from its embed."""
    return int(
        interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
    )


def settings_changed(interaction):
    """Makes the running games read the settings again."""
    cog = interaction.client.get_cog("TheEventItself")
    if cog:
        cog.cache.invalidate_all()


def shown_span(values) -> str:
    """Writes one number, or a lowest and a highest."""
    if len(values) == 1:
        return f"`{values[0]}`"
    return f"`{values[0]}–{values[1]}`"


def panel_embed(title: str, description: str, color) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    return embed


def status(channel, enabled) -> str:
    return f"**Channel:** {channel.mention}\n**Status:** {'Enabled' if enabled else 'Disabled'}"


def build_minigames_embed(
    channel, settings: dict, guild_config: dict = None
) -> discord.Embed:
    """Gives the embed of a channel's minigames: spawn rate, multiplier and which games are on."""
    desc = status(channel, settings.get("minigames_enabled", False)) + "\n"
    if settings.get("minigames_enabled", False):
        games = settings.get("minigames_list", []) or []
        rate = 100 / settings.get("minigames_frequency", 50)
        desc += f"**Spawn Rate:** `{int(rate) if rate >= 1 else f'{rate:g}'}%`\n"
        desc += f"**Multiplier:** `x{float(settings.get('mora_multiplier', 1.0))}`\n\n"
        listed = "\n> ".join(
            f"{emoji} - {title} {YES_EMOTE if letter in games else NO_EMOTE}"
            for letter, emoji, title in zip(LETTER_LIST, LETTER_EMOTES, MINIGAME_TITLES)
        )
        desc += f"**Enabled Games:**\n > {listed}"
    return panel_embed("🎮 Minigame Configuration", desc, discord.Color.blurple())


def build_chests_embed(
    channel, settings: dict, guild_config: dict = None
) -> discord.Embed:
    """Gives the embed of a channel's chests and the server's chest tiers."""
    desc = status(channel, settings.get("chests_enabled", False))
    if settings.get("chests_enabled", False):
        gc = guild_config or {}
        names = gc.get("chests_tier_names", MORA_CHEST_TIERS)
        tier_rewards = gc.get("chests_tier_rewards", MORA_CHEST_REWARDS)
        upgrades = gc.get("chests_upgrade_chances", MORA_CHEST_UPGRADE_CHANCES)
        emotes = gc.get("chests_emotes", GUILD_SETTINGS_FALLBACK["chests_emotes"])
        desc += (
            "\n\n> The following settings apply **server-wide** across all enabled channels.\n\n"
            f"**Base Upgrade Chances:** `{gc.get('chests_base_upgrade_chances', MORA_CHEST_UPGRADE_TIMES)}`\n"
            f"**Spawn Requirement:** {shown_span(gc.get('chests_spawn_req', list(MORA_CHEST_SPAWN_REQ)))} messages\n"
            f"**Streak Bonus:** {MORA_EMOTE} `+{gc.get('chests_streak_bonus', MORA_CHEST_STREAK_BONUS)}` per day "
            f"(max `{gc.get('chests_max_streak_bonus', MORA_CHEST_MAX_STREAK_BONUS)}`)\n\n"
            "**Tiers:**\n"
        )
        for index, name in enumerate(names):
            reward = tier_rewards[index] if index < len(tier_rewards) else 0
            emote = emotes[index] if index < len(emotes) else ""
            desc += f"{DOT_EMOTE} {emote} **{name}** — {MORA_EMOTE} `{reward:,}`"
            if index < len(upgrades) and index < len(names) - 1:
                desc += f" (upgrade to next: {upgrades[index]*100:.0f}%)"
            desc += "\n"
    return panel_embed("📦 Chest Configuration", desc, discord.Color.gold())


def build_sigils_embed(
    channel, settings: dict, guild_config: dict = None
) -> discord.Embed:
    """Gives the embed of a channel's sigil earning: ranges, the server's daily cap and boosted roles."""
    desc = status(channel, settings.get("chat_enabled", False))
    if settings.get("chat_enabled", False):
        gc = guild_config or {}
        earned = settings.get("chat_range", list(DEFAULT_CHAT_RANGE))
        messages = settings.get("chat_msg_range", list(DEFAULT_CHAT_MSG_RANGE))
        desc += (
            f"\n**Earning Range (per-channel):** {shown_span(earned)} {SIGIL_EMOTE} per batch"
            f"\n**Messages per Batch (per-channel):** {shown_span(messages)}"
            f"\n**Max Daily Cap (server-wide):** {SIGIL_EMOTE} `{gc.get('chat_max_cap', DEFAULT_CHAT_MAX_CAP)}`\n"
        )
        boosted = settings.get("chat_boosted_roles", [])
        if isinstance(boosted, list) and boosted:
            desc += "\n**Boosted Roles (per-channel):**\n"
            for entry in boosted:
                if isinstance(entry, str) and ":" in entry:
                    entry = entry.split(":", 1)
                elif not (isinstance(entry, list) and len(entry) == 2):
                    continue
                desc += f"{DOT_EMOTE} <@&{entry[0]}>: `{entry[1]}`\n"
    return panel_embed(
        f"{SIGIL_EMOTE} {SIGIL_CURRENCY_NAME} Configuration",
        desc,
        discord.Color.purple(),
    )


EMBEDS = {
    "minigames": build_minigames_embed,
    "chests": build_chests_embed,
    "sigils": build_sigils_embed,
}


async def panel(interaction, tab: str, channel):
    """Gives the embed and buttons of one tab of a channel's settings, read fresh."""
    pool = interaction.client.pool
    settings = await get_channel_settings(pool, channel.id)
    guild_config = None
    if tab != "minigames":
        guild_config = await get_guild_settings(pool, channel.guild.id)
    embed = EMBEDS[tab](channel, settings, guild_config)
    return embed, EventSettingsView(channel, settings, tab, interaction)


async def show_panel(interaction, tab: str, channel_id: int = None):
    """Redraws the settings message this interaction came from."""
    channel = interaction.guild.get_channel(channel_id or parse_channel_id(interaction))
    embed, view = await panel(interaction, tab, channel)
    await interaction.response.edit_message(embed=embed, view=view)


async def refuse(interaction, problem):
    await interaction.response.send_message(f"{NO_EMOTE} {problem}", ephemeral=True)


class SettingModal(discord.ui.Modal):
    """The box one setting is typed into."""

    def __init__(self, setting: Setting, channel, current):
        super().__init__(title=setting.title)
        self.setting, self.channel = setting, channel
        shown = setting.shown(current) if current or not setting.empty else None
        self.add_item(
            discord.ui.TextInput(
                label=setting.label,
                style=discord.TextStyle.short,
                placeholder=setting.placeholder or str(current),
                default=shown or setting.empty,
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = self.setting.read(self.children[0].value)
        except Refused as problem:
            return await refuse(interaction, problem)
        await self.setting.save(interaction.client.pool, self.channel, value)
        settings_changed(interaction)
        await show_panel(interaction, self.setting.tab, self.channel.id)


class SettingButton(discord.ui.Button):
    """Opens the box of one setting, filled with its saved value."""

    def __init__(self, setting: Setting, channel):
        super().__init__(
            label=setting.button,
            style=discord.ButtonStyle.secondary,
            emoji=setting.emoji,
            row=setting.row,
        )
        self.setting, self.channel = setting, channel

    async def callback(self, interaction: discord.Interaction):
        current = await self.setting.current(interaction.client.pool, self.channel)
        await interaction.response.send_modal(
            SettingModal(self.setting, self.channel, current)
        )


class ToggleEventModal(discord.ui.Modal, title="Toggle Events"):
    """Takes the letters of the games to turn on or off in a channel."""

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
        self.letter_input = discord.ui.TextInput(
            label="The corresponding letter(s)",
            style=discord.TextStyle.short,
            placeholder="Type letters consecutively to toggle multiple games (no spaces please)",
            max_length=26,
            required=True,
        )
        self.add_item(self.letter_input)

    async def on_submit(self, interaction: discord.Interaction):
        pool = interaction.client.pool
        settings = await get_channel_settings(pool, self.channel_id)
        games = list(settings.get("minigames_list", []) or [])
        for letter in map(str.upper, str(self.letter_input.value)):
            if letter not in LETTER_LIST:
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{NO_EMOTE} Invalid letter `{letter}`.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
            if letter in games:
                games.remove(letter)
            else:
                games.append(letter)

        await upsert_channel_settings(pool, self.channel_id, minigames_list=games)
        settings_changed(interaction)
        await show_panel(interaction, "minigames", self.channel_id)


class TabButton(discord.ui.Button):
    """Switches the panel to one of its three tabs."""

    def __init__(self, tab: str, active: bool):
        names = {"minigames": "Games", "chests": "Chests"}
        super().__init__(
            label=f"Configure {names.get(tab, SIGIL_CURRENCY_NAME)}",
            style=(
                discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary
            ),
            custom_id=f"tab_{tab}",
        )
        self.tab = tab

    async def callback(self, interaction: discord.Interaction):
        await show_panel(interaction, self.tab)


class EnableButton(discord.ui.Button):
    """Turns a tab's feature on or off in the channel."""

    def __init__(self, tab: str, enable: bool):
        super().__init__(
            label=f"{'Enable' if enable else 'Disable'} {TABS[tab][1]}",
            style=discord.ButtonStyle.green if enable else discord.ButtonStyle.red,
        )
        self.tab, self.enable = tab, enable

    async def callback(self, interaction: discord.Interaction):
        pool, channel_id = interaction.client.pool, parse_channel_id(interaction)
        changes = {TABS[self.tab][0]: self.enable}
        if self.tab == "minigames" and self.enable:
            saved = await get_channel_settings(pool, channel_id)
            if not saved.get("minigames_list"):
                changes["minigames_list"] = list(LETTER_LIST)
        await upsert_channel_settings(pool, channel_id, **changes)
        settings_changed(interaction)
        await show_panel(interaction, self.tab, channel_id)


class ToggleEventsButton(discord.ui.Button):
    """Opens the box that turns single games on or off."""

    def __init__(self, channel_id: int):
        super().__init__(
            label="Toggle Games", style=discord.ButtonStyle.grey, emoji="🎮", row=2
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ToggleEventModal(self.channel_id))


class FrequencySelect(discord.ui.Select):
    """Picks how often games spawn in the channel."""

    def __init__(self, current_frequency: int = 50):
        super().__init__(
            placeholder="Select frequency...",
            options=[
                discord.SelectOption(
                    label=label,
                    value=str(frequency),
                    default=current_frequency == frequency,
                )
                for frequency, label in FREQUENCIES.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = parse_channel_id(interaction)
        await upsert_channel_settings(
            interaction.client.pool,
            channel_id,
            minigames_frequency=int(self.values[0]),
        )
        settings_changed(interaction)
        await show_panel(interaction, "minigames", channel_id)


class EventSettingsView(discord.ui.View):
    """The buttons of one tab of the settings panel."""

    def __init__(
        self, channel, settings: dict, tab: str = "minigames", settings_interaction=None
    ):
        super().__init__(timeout=300)
        for name in TABS:
            self.add_item(TabButton(name, name == tab))
        enabled = settings.get(TABS[tab][0], False)
        self.add_item(EnableButton(tab, not enabled))
        if not enabled:
            return
        if tab == "minigames":
            self.add_item(ToggleEventsButton(channel.id))
            self.add_item(FrequencySelect(settings.get("minigames_frequency", 50)))
        for setting in SETTINGS:
            if setting.tab == tab:
                self.add_item(SettingButton(setting, channel))
        if tab == "sigils":
            self.add_item(ChatBoostedRolesSelect(channel.id, settings_interaction))


async def role_boost(pool, channel_id: int, role_id: int):
    """Gives a channel's other boosted roles and this role's boost, None when it has none."""
    settings = await get_channel_settings(pool, channel_id)
    boosts = await parse_boosted_roles(settings.get("chat_boosted_roles", []))
    others = [boost for boost in boosts if boost[0] != role_id]
    own = next((boost[1] for boost in boosts if boost[0] == role_id), None)
    return others, own


def boost_embed(role, boost) -> discord.Embed:
    """Gives the embed showing one role's boost."""
    desc = f"**Selected:** {role.mention}\n"
    if not boost:
        desc += "No boost set for this role yet."
    elif boost.startswith("+"):
        desc += f"**Current Boost:** `{boost}`\n*(adds to daily cap)*"
    else:
        desc += f"**Current Boost:** `{boost}`\n*(sets daily cap to this value)*"
    return discord.Embed(
        title="Role Boost",
        description=desc,
        color=role.color if role.color.value else discord.Color.purple(),
    )


async def save_boosts(interaction, channel_id: int, boosts: list):
    """Saves a channel's boosted roles."""
    await upsert_channel_settings(
        interaction.client.pool,
        channel_id,
        chat_boosted_roles=await serialize_boosted_roles(boosts),
    )
    settings_changed(interaction)


async def redraw_sigils(settings_interaction, channel_id: int):
    """Redraws the settings panel a role's boost was opened from."""
    if settings_interaction:
        channel = settings_interaction.guild.get_channel(channel_id)
        embed, view = await panel(settings_interaction, "sigils", channel)
        await settings_interaction.edit_original_response(embed=embed, view=view)


class SetBoostModal(discord.ui.Modal, title="Set Role Boost"):
    """Takes the boost of one role."""

    def __init__(
        self,
        channel_id: int,
        role_id: int,
        current_value: str = None,
        settings_interaction=None,
    ):
        super().__init__()
        self.channel_id = channel_id
        self.role_id = role_id
        self.settings_interaction = settings_interaction
        self.add_item(
            discord.ui.TextInput(
                label="Boost value (e.g. +20 adds, 80 sets cap)",
                style=discord.TextStyle.short,
                placeholder="+20 or 80",
                default=current_value or "",
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        boost = self.children[0].value.strip()
        if not boost:
            return await refuse(interaction, "Value cannot be empty.")
        if not BOOST.fullmatch(boost):
            return await refuse(
                interaction, "Enter a whole number such as `80`, or `+20` to add."
            )
        others, _ = await role_boost(
            interaction.client.pool, self.channel_id, self.role_id
        )
        await save_boosts(
            interaction, self.channel_id, others + [[self.role_id, boost]]
        )
        await interaction.response.edit_message(
            embed=boost_embed(interaction.guild.get_role(self.role_id), boost),
            view=ChatBoostRoleView(
                self.channel_id, self.role_id, self.settings_interaction
            ),
        )
        await redraw_sigils(self.settings_interaction, self.channel_id)


class ChatBoostRoleView(discord.ui.View):
    """The buttons under one role's boost."""

    def __init__(self, channel_id: int, role_id: int, settings_interaction):
        super().__init__()
        self.channel_id = channel_id
        self.role_id = role_id
        self.settings_interaction = settings_interaction

    @discord.ui.button(label="Set Boost", style=discord.ButtonStyle.primary)
    async def set_boost(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        _, boost = await role_boost(
            interaction.client.pool, self.channel_id, self.role_id
        )
        await interaction.response.send_modal(
            SetBoostModal(
                self.channel_id, self.role_id, boost, self.settings_interaction
            )
        )

    @discord.ui.button(label="Remove Boost", style=discord.ButtonStyle.danger)
    async def remove_boost(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        others, _ = await role_boost(
            interaction.client.pool, self.channel_id, self.role_id
        )
        await save_boosts(interaction, self.channel_id, others)
        role = interaction.guild.get_role(self.role_id)
        await interaction.response.edit_message(
            content=f"{YES_EMOTE} Boost for {role.mention} has been removed.",
            embed=None,
            view=None,
        )
        await redraw_sigils(self.settings_interaction, self.channel_id)


class ChatBoostedRolesSelect(discord.ui.RoleSelect):
    """Picks the role whose boost to look at."""

    def __init__(self, channel_id: int, settings_interaction=None):
        super().__init__(
            placeholder="Select a role to boost...", min_values=1, max_values=1, row=1
        )
        self.channel_id = channel_id
        self.settings_interaction = settings_interaction

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        _, boost = await role_boost(interaction.client.pool, self.channel_id, role.id)
        await interaction.response.send_message(
            embed=boost_embed(role, boost),
            view=ChatBoostRoleView(self.channel_id, role.id, self.settings_interaction),
            ephemeral=True,
        )


@app_commands.guild_only()
class EventSystem(commands.GroupCog, name="events"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="settings",
        description="Customize the selection of random events in your server",
    )
    @app_commands.describe(
        channel="The text channel to customize event settings for (default: current channel)",
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def events_settings(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ) -> None:
        embed, view = await panel(
            interaction, "minigames", channel or interaction.channel
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @events_settings.error
    async def events_settings_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventSystem(bot))
