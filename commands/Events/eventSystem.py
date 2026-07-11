import discord
import datetime

from discord import app_commands
from discord.ext import commands

from commands.Events.config import MORA_EMOTE, YES_EMOTE, NO_EMOTE, DOT_EMOTE, MINIGAME_TITLES, LETTER_LIST, LETTER_EMOTES, MORA_CHEST_TIERS, MORA_CHEST_REWARDS, MORA_CHEST_UPGRADE_CHANCES, MORA_CHEST_STREAK_BONUS, MORA_CHEST_MAX_STREAK_BONUS, MORA_CHEST_SPAWN_REQ, MORA_CHEST_UPGRADE_TIMES, EMOTE_STREAK, EMOTE_MAX_STREAK, SIGIL_EMOTE, SIGIL_CURRENCY_NAME, DEFAULT_CHAT_RANGE, DEFAULT_CHAT_MAX_CAP, DEFAULT_CHAT_MSG_RANGE
from commands.Events.helperFunctions import get_channel_settings, upsert_channel_settings, ensure_minigame_settings_table, ensure_minigame_guild_settings_table, get_guild_settings, upsert_guild_settings, _GUILD_SETTINGS_FALLBACK, parse_boosted_roles, serialize_boosted_roles, ensure_minigame_sigils_table

letterString = "".join(LETTER_LIST)


def parse_channel_id(interaction):
    return int(interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip())


class ToggleEventModal(discord.ui.Modal, title="Toggle Events"):
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
        original = list(settings.get("minigames_list", []) or [])
        frequency = settings.get("minigames_frequency", 50)

        for ch in list(str(self.letter_input.value)):
            letter = ch.upper()
            if letter in LETTER_LIST:
                if letter in original:
                    original.remove(letter)
                else:
                    original.append(letter)
            else:
                return await interaction.response.send_message(
                    embed=discord.Embed(description=f"{NO_EMOTE} Invalid letter `{letter}`.", color=discord.Color.red()),
                    ephemeral=True
                )

        await upsert_channel_settings(pool, self.channel_id, minigames_list=original)
        cog = interaction.client.get_cog('TheEventItself')
        if cog:
            cog.cache.invalidate_channel(self.channel_id)

        channel = interaction.guild.get_channel(self.channel_id)
        new_settings = await get_channel_settings(pool, self.channel_id)
        embed = build_minigames_embed(channel, new_settings)
        view = EventSettingsView(channel, new_settings)
        view.active_tab = "minigames"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class SetMinigameRewardsModal(discord.ui.Modal, title="Set Mora Multiplier"):
    def __init__(self, channel_id: int, current: float):
        super().__init__()
        self.channel_id = channel_id
        self.add_item(discord.ui.TextInput(
            label="Multiplier (e.g. 1.0 = 1x, 2.0 = 2x)",
            style=discord.TextStyle.short,
            placeholder=str(current),
            default=str(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(self.children[0].value)
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid number.", ephemeral=True)
        if val < 0.01 or val > 99.99:
            return await interaction.response.send_message(f"{NO_EMOTE} Multiplier must be between 0.01 and 99.99.", ephemeral=True)
        await upsert_channel_settings(interaction.client.pool, self.channel_id, mora_multiplier=val)
        cog = interaction.client.get_cog('TheEventItself')
        if cog:
            cog.cache.invalidate_channel(self.channel_id)
        channel = interaction.guild.get_channel(self.channel_id)
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        embed = build_minigames_embed(channel, settings)
        view = EventSettingsView(channel, settings)
        view.active_tab = "minigames"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestTierNamesModal(discord.ui.Modal, title="Chest Tier Names"):
    def __init__(self, guild_id: int, current: list):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label="Tier names (comma-separated)",
            style=discord.TextStyle.short,
            placeholder="Common, Exquisite, Precious, Luxurious",
            default=", ".join(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        names = [x.strip() for x in self.children[0].value.split(",") if x.strip()]
        if len(names) < 2:
            return await interaction.response.send_message(f"{NO_EMOTE} Provide at least 2 tier names.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_tier_names=names)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestTierRewardsModal(discord.ui.Modal, title="Chest Tier Rewards"):
    def __init__(self, guild_id: int, current: list):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label="Rewards (comma-separated integers)",
            style=discord.TextStyle.short,
            placeholder="2500, 7500, 15000, 30000",
            default=", ".join(str(x) for x in current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vals = [int(x.strip()) for x in self.children[0].value.split(",") if x.strip()]
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer list.", ephemeral=True)
        if len(vals) < 2:
            return await interaction.response.send_message(f"{NO_EMOTE} Provide at least 2 reward values.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_tier_rewards=vals)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestUpgradeChancesModal(discord.ui.Modal, title="Chest Upgrade Chances"):
    def __init__(self, guild_id: int, current: list):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label="Chances (comma-separated decimals 0-1)",
            style=discord.TextStyle.short,
            placeholder="0.30, 0.15, 0.20",
            default=", ".join(f"{x:.2f}" for x in current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vals = [float(x.strip()) for x in self.children[0].value.split(",") if x.strip()]
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid decimal list.", ephemeral=True)
        if any(v < 0 or v > 1 for v in vals):
            return await interaction.response.send_message(f"{NO_EMOTE} Each chance must be between 0 and 1.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_upgrade_chances=vals)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestSpawnRangeModal(discord.ui.Modal, title="Chest Spawn Requirement"):
    def __init__(self, guild_id: int, current: list):
        super().__init__()
        self.guild_id = guild_id
        display = ", ".join(str(x) for x in current) if current else "4, 6"
        self.add_item(discord.ui.TextInput(
            label="Exact OR min, max (effortful messages)",
            style=discord.TextStyle.short,
            placeholder="4, 6",
            default=display,
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        parts = [x.strip() for x in self.children[0].value.split(",") if x.strip()]
        try:
            vals = [int(x) for x in parts]
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer(s).", ephemeral=True)
        if len(vals) not in (1, 2) or any(v < 1 for v in vals):
            return await interaction.response.send_message(f"{NO_EMOTE} Provide 1 (exact) or 2 (min, max) positive integers.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_spawn_req=vals)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestStreakBonusModal(discord.ui.Modal, title="Streak Bonus"):
    def __init__(self, guild_id: int, current: int, label: str, column: str):
        super().__init__()
        self.guild_id = guild_id
        self.column = column
        self.add_item(discord.ui.TextInput(
            label=label,
            style=discord.TextStyle.short,
            placeholder=str(current),
            default=str(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.children[0].value)
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer.", ephemeral=True)
        if val < 0:
            return await interaction.response.send_message(f"{NO_EMOTE} Must be non-negative.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, **{self.column: val})
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestBaseUpgradesModal(discord.ui.Modal, title="Base Upgrade Chances"):
    def __init__(self, guild_id: int, current: int):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label="Number of upgrade chances",
            style=discord.TextStyle.short,
            placeholder="4",
            default=str(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.children[0].value)
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer.", ephemeral=True)
        if val < 0:
            return await interaction.response.send_message(f"{NO_EMOTE} Must be non-negative.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_base_upgrade_chances=val)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestEmotesModal(discord.ui.Modal, title="Chest Emotes"):
    def __init__(self, guild_id: int, current: list):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label="Emotes (comma-separated)",
            style=discord.TextStyle.short,
            placeholder="<a:common:1371641883121680465>, <a:exquisite:1371641856344985620>, ...",
            default=", ".join(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        emotes = [x.strip() for x in self.children[0].value.split(",") if x.strip()]
        if len(emotes) < 2:
            return await interaction.response.send_message(f"{NO_EMOTE} Provide at least 2 emotes.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_emotes=emotes)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChestIconsModal(discord.ui.Modal, title="Chest Icons"):
    def __init__(self, guild_id: int, current: list):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label="Icon URLs (comma-separated)",
            style=discord.TextStyle.short,
            placeholder="https://i.imgur.com/2kOfLSC.png, https://i.imgur.com/DBPQSAu.png, ...",
            default=", ".join(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        icons = [x.strip() for x in self.children[0].value.split(",") if x.strip()]
        if len(icons) < 2:
            return await interaction.response.send_message(f"{NO_EMOTE} Provide at least 2 icon URLs.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chests_icons=icons)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class EventSettingsView(discord.ui.View):
    def __init__(self, channel, settings: dict, guild_config: dict = None, settings_interaction=None):
        super().__init__(timeout=300)
        self.channel = channel
        self.settings = settings
        self.guild_id = channel.guild.id
        self.guild_config = guild_config
        self.settings_interaction = settings_interaction
        self.active_tab = "minigames"
        self.selected_role_id = None
        self._build()

    def _build(self):
        self.clear_items()
        self.add_item(TabMinigamesButton(self.active_tab == "minigames"))
        self.add_item(TabChestsButton(self.active_tab == "chests"))
        self.add_item(TabSigilsButton(self.active_tab == "sigils"))

        if self.active_tab == "minigames":
            s = self.settings
            enabled = s.get("minigames_enabled", False)
            if enabled:
                self.add_item(MinigamesToggleButton(not enabled))
                self.add_item(ToggleEventsButton(self.channel.id, s))
                self.add_item(FrequencySelect(self.channel.id, s.get("minigames_frequency", 50)))
                self.add_item(SetRewardsButton(self.channel.id, s.get("mora_multiplier", 1.0)))
            else:
                self.add_item(MinigamesToggleButton(not enabled))
        elif self.active_tab == "chests":
            s = self.settings
            enabled = s.get("chests_enabled", False)
            self.add_item(ChestsToggleButton(not enabled))
            if enabled:
                self.add_item(EditBaseUpgradeButton(self.guild_id))
                self.add_item(EditSpawnRangeButton(self.guild_id))
                self.add_item(EditStreakBonusButton(self.guild_id))
                self.add_item(EditMaxStreakBonusButton(self.guild_id))
                self.add_item(EditTierNamesButton(self.guild_id))
                self.add_item(EditTierRewardsButton(self.guild_id))
                self.add_item(EditUpgradeChancesButton(self.guild_id))
                self.add_item(EditChestEmotesButton(self.guild_id))
                self.add_item(EditChestIconsButton(self.guild_id))
        else:
            s = self.settings
            enabled = s.get("chat_enabled", False)
            self.add_item(ChatToggleButton(not enabled))
            if enabled:
                self.add_item(ChatRangeButton(self.channel.id))
                self.add_item(ChatMsgRangeButton(self.channel.id))
                self.add_item(ChatBoostedRolesSelect(self.channel.id, self.settings_interaction))
                self.add_item(ChatMaxCapButton(self.guild_id))


class TabMinigamesButton(discord.ui.Button):
    def __init__(self, active: bool):
        super().__init__(
            label="Configure Games",
            style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
            custom_id="tab_minigames",
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        view = EventSettingsView(channel, settings)
        view.active_tab = "minigames"
        view._build()
        embed = build_minigames_embed(channel, settings)
        await interaction.response.edit_message(embed=embed, view=view)


class TabChestsButton(discord.ui.Button):
    def __init__(self, active: bool):
        super().__init__(
            label="Configure Chests",
            style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
            custom_id="tab_chests",
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        embed = build_chests_embed(channel, settings, guild_config)
        await interaction.response.edit_message(embed=embed, view=view)


class TabSigilsButton(discord.ui.Button):
    def __init__(self, active: bool):
        super().__init__(
            label=f"Configure {SIGIL_CURRENCY_NAME}",
            style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
            custom_id="tab_sigils",
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        view = EventSettingsView(channel, settings, guild_config, settings_interaction=interaction)
        view.active_tab = "sigils"
        view._build()
        embed = build_sigils_embed(channel, settings, guild_config)
        await interaction.response.edit_message(embed=embed, view=view)


def build_minigames_embed(channel, settings: dict) -> discord.Embed:
    enabled = bool(settings.get("minigames_enabled", False))
    events = settings.get("minigames_list", []) or []
    frequency = settings.get("minigames_frequency", 50)
    multiplier = float(settings.get("mora_multiplier", 1.0))

    desc = f"**Channel:** {channel.mention}\n**Status:** {'Enabled' if enabled else 'Disabled'}\n"
    if enabled:
        desc += f"**Spawn Rate:** `{int(100/frequency)}%`\n"
        desc += f"**Multiplier:** `x{multiplier}`\n\n"
        string = "\n> ".join(
            f"{emoji} - {title} {YES_EMOTE if letter in events else NO_EMOTE}"
            for letter, emoji, title in zip(letterString, LETTER_EMOTES, MINIGAME_TITLES)
        )
        desc += f"**Enabled Games:**\n > {string}"
    embed = discord.Embed(
        title="🎮 Minigame Configuration",
        description=desc,
        color=discord.Color.blurple(),
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    return embed


def build_chests_embed(channel, settings: dict, guild_config: dict = None) -> discord.Embed:
    enabled = bool(settings.get("chests_enabled", False))
    desc = f"**Channel:** {channel.mention}\n**Status:** {'Enabled' if enabled else 'Disabled'}"

    if enabled:
        desc += "\n\n> The following settings apply **server-wide** across all enabled channels.\n\n"
        gc = guild_config or {}
        tier_names = gc.get("chests_tier_names", MORA_CHEST_TIERS)
        tier_rewards = gc.get("chests_tier_rewards", MORA_CHEST_REWARDS)
        upgrade_chances = gc.get("chests_upgrade_chances", MORA_CHEST_UPGRADE_CHANCES)
        spawn_req = gc.get("chests_spawn_req", list(MORA_CHEST_SPAWN_REQ))
        streak_bonus = gc.get("chests_streak_bonus", MORA_CHEST_STREAK_BONUS)
        max_streak = gc.get("chests_max_streak_bonus", MORA_CHEST_MAX_STREAK_BONUS)
        base_upgrades = gc.get("chests_base_upgrade_chances", MORA_CHEST_UPGRADE_TIMES)
        emotes = gc.get("chests_emotes", _GUILD_SETTINGS_FALLBACK["chests_emotes"])

        desc += f"**Base Upgrade Chances:** `{base_upgrades}`\n"
        spawn_str = f"`{spawn_req[0]}`" if len(spawn_req) == 1 else f"`{spawn_req[0]}–{spawn_req[1]}`"
        desc += f"**Spawn Requirement:** {spawn_str} messages\n"
        desc += f"**Streak Bonus:** {MORA_EMOTE} `+{streak_bonus}` per day (max `{max_streak}`)\n\n"

        desc += "**Tiers:**\n"
        for i in range(len(tier_names)):
            name = tier_names[i] if i < len(tier_names) else "?"
            reward = tier_rewards[i] if i < len(tier_rewards) else 0
            emote = emotes[i] if i < len(emotes) else ""
            chance = f"{upgrade_chances[i]*100:.0f}%" if i < len(upgrade_chances) and i < len(tier_names) - 1 else "—"
            desc += f"{DOT_EMOTE} {emote} **{name}** — {MORA_EMOTE} `{reward:,}`"
            if chance != "—":
                desc += f" (upgrade to next: {chance})"
            desc += "\n"

    embed = discord.Embed(
        title="📦 Chest Configuration",
        description=desc,
        color=discord.Color.gold(),
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    return embed


def build_sigils_embed(channel, settings: dict, guild_config: dict = None) -> discord.Embed:
    enabled = bool(settings.get("chat_enabled", False))
    desc = f"**Channel:** {channel.mention}\n**Status:** {'Enabled' if enabled else 'Disabled'}"
    if enabled:
        gc = guild_config or {}
        chat_range = settings.get("chat_range", list(DEFAULT_CHAT_RANGE))
        chat_max_cap = gc.get("chat_max_cap", DEFAULT_CHAT_MAX_CAP)
        boosted = settings.get("chat_boosted_roles", [])

        range_str = f"`{chat_range[0]}`" if len(chat_range) == 1 else f"`{chat_range[0]}–{chat_range[1]}`"
        desc += f"\n**Earning Range (per-channel):** {range_str} {SIGIL_EMOTE} per batch"
        chat_msg_range = settings.get("chat_msg_range", list(DEFAULT_CHAT_MSG_RANGE))
        msg_range_str = f"`{chat_msg_range[0]}`" if len(chat_msg_range) == 1 else f"`{chat_msg_range[0]}–{chat_msg_range[1]}`"
        desc += f"\n**Messages per Batch (per-channel):** {msg_range_str}"
        desc += f"\n**Max Daily Cap (server-wide):** {SIGIL_EMOTE} `{chat_max_cap}`\n"

        boosted_list = boosted if isinstance(boosted, list) else []
        if boosted_list:
            desc += "\n**Boosted Roles (per-channel):**\n"
            for entry in boosted_list:
                if isinstance(entry, str) and ":" in entry:
                    parts = entry.split(":", 1)
                    rid = parts[0]
                    bonus = parts[1]
                    desc += f"{DOT_EMOTE} <@&{rid}>: `{bonus}`\n"
                elif isinstance(entry, list) and len(entry) == 2:
                    desc += f"{DOT_EMOTE} <@&{entry[0]}>: `{entry[1]}`\n"

    embed = discord.Embed(
        title=f"{SIGIL_EMOTE} {SIGIL_CURRENCY_NAME} Configuration",
        description=desc,
        color=discord.Color.purple(),
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    return embed


class MinigamesToggleButton(discord.ui.Button):
    def __init__(self, enable: bool):
        label = "Enable Games" if enable else "Disable Games"
        style = discord.ButtonStyle.green if enable else discord.ButtonStyle.red
        super().__init__(label=label, style=style)
        self.enable = enable

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        kwargs = {"minigames_enabled": self.enable}
        if self.enable:
            settings_before = await get_channel_settings(interaction.client.pool, channel_id)
            current_list = settings_before.get("minigames_list", []) or []
            if not current_list:
                kwargs["minigames_list"] = list(letterString)
        await upsert_channel_settings(interaction.client.pool, channel_id, **kwargs)
        cog = interaction.client.get_cog('TheEventItself')
        if cog:
            cog.cache.invalidate_channel(channel_id)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        embed = build_minigames_embed(channel, settings)
        view = EventSettingsView(channel, settings)
        view.active_tab = "minigames"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ToggleEventsButton(discord.ui.Button):
    def __init__(self, channel_id: int, settings: dict):
        super().__init__(label="Toggle Games", style=discord.ButtonStyle.grey, emoji="🎮", row=2)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        modal = ToggleEventModal(self.channel_id)
        await interaction.response.send_modal(modal)


class FrequencySelect(discord.ui.Select):
    def __init__(self, channel_id: int, current_frequency: int = 50):
        self.channel_id = channel_id
        options = [
            discord.SelectOption(label="Annoying (~50%)", value="2", default=current_frequency == 2),
            discord.SelectOption(label="Very Frequent (~10%)", value="10", default=current_frequency == 10),
            discord.SelectOption(label="Frequent (~5%)", value="20", default=current_frequency == 20),
            discord.SelectOption(label="Occasional (~3%)", value="30", default=current_frequency == 30),
            discord.SelectOption(label="Uncommon (~2%)", value="50", default=current_frequency == 50),
            discord.SelectOption(label="Rare (~1%)", value="100", default=current_frequency == 100),
            discord.SelectOption(label="Very Rare (~0.5%)", value="200", default=current_frequency == 200),
        ]
        super().__init__(placeholder="Select frequency...", options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        new_frequency = int(self.values[0])
        await upsert_channel_settings(interaction.client.pool, channel_id, minigames_frequency=new_frequency)
        cog = interaction.client.get_cog('TheEventItself')
        if cog:
            cog.cache.invalidate_channel(channel_id)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        embed = build_minigames_embed(channel, settings)
        view = EventSettingsView(channel, settings)
        view.active_tab = "minigames"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class SetRewardsButton(discord.ui.Button):
    def __init__(self, channel_id: int, current: float):
        super().__init__(label="Multiplier", style=discord.ButtonStyle.grey, emoji="💰", row=2)
        self.channel_id = channel_id
        self.current = current

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetMinigameRewardsModal(self.channel_id, self.current))


class ChestsToggleButton(discord.ui.Button):
    def __init__(self, enable: bool):
        label = "Enable Chests" if enable else "Disable Chests"
        style = discord.ButtonStyle.green if enable else discord.ButtonStyle.red
        super().__init__(label=label, style=style)
        self.enable = enable

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        await upsert_channel_settings(interaction.client.pool, channel_id, chests_enabled=self.enable)
        cog = interaction.client.get_cog('TheEventItself')
        if cog:
            cog.cache.invalidate_channel(channel_id)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        embed = build_chests_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "chests"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class EditTierNamesButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Tier Names", style=discord.ButtonStyle.secondary, emoji="📦", row=2)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_tier_names", MORA_CHEST_TIERS)
        await interaction.response.send_modal(ChestTierNamesModal(self.guild_id, list(current)))


class EditTierRewardsButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Tier Rewards", style=discord.ButtonStyle.secondary, emoji="💰", row=2)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_tier_rewards", MORA_CHEST_REWARDS)
        await interaction.response.send_modal(ChestTierRewardsModal(self.guild_id, list(current)))


class EditUpgradeChancesButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Tier Upgrade Chances", style=discord.ButtonStyle.secondary, emoji="🔼", row=2)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_upgrade_chances", MORA_CHEST_UPGRADE_CHANCES)
        await interaction.response.send_modal(ChestUpgradeChancesModal(self.guild_id, [float(x) for x in (current or [])]))


class EditSpawnRangeButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Spawn Requirement", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = list(gc.get("chests_spawn_req", [4, 6]))
        await interaction.response.send_modal(ChestSpawnRangeModal(self.guild_id, current))


class EditStreakBonusButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Streak Bonus", style=discord.ButtonStyle.secondary, emoji=EMOTE_STREAK, row=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_streak_bonus", MORA_CHEST_STREAK_BONUS)
        await interaction.response.send_modal(ChestStreakBonusModal(self.guild_id, current, "Streak bonus per day", "chests_streak_bonus"))


class EditMaxStreakBonusButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Max Streak Bonus", style=discord.ButtonStyle.secondary, emoji=EMOTE_MAX_STREAK, row=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_max_streak_bonus", MORA_CHEST_MAX_STREAK_BONUS)
        await interaction.response.send_modal(ChestStreakBonusModal(self.guild_id, current, "Maximum streak bonus", "chests_max_streak_bonus"))


class EditBaseUpgradeButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Base Upgrade Chances", style=discord.ButtonStyle.secondary, emoji="🔢", row=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_base_upgrade_chances", MORA_CHEST_UPGRADE_TIMES)
        await interaction.response.send_modal(ChestBaseUpgradesModal(self.guild_id, current))


class EditChestEmotesButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Tier Emotes", style=discord.ButtonStyle.secondary, emoji="🎨", row=2)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_emotes", _GUILD_SETTINGS_FALLBACK["chests_emotes"])
        await interaction.response.send_modal(ChestEmotesModal(self.guild_id, list(current)))


class EditChestIconsButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Tier Icons", style=discord.ButtonStyle.secondary, emoji="🖼️", row=2)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chests_icons", _GUILD_SETTINGS_FALLBACK["chests_icons"])
        await interaction.response.send_modal(ChestIconsModal(self.guild_id, list(current)))


class ChatToggleButton(discord.ui.Button):
    def __init__(self, enable: bool):
        label = f"Enable {SIGIL_CURRENCY_NAME}" if enable else f"Disable {SIGIL_CURRENCY_NAME}"
        style = discord.ButtonStyle.green if enable else discord.ButtonStyle.red
        super().__init__(label=label, style=style)
        self.enable = enable

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(
            interaction.message.embeds[0].description.split("<#")[1].split(">")[0].strip()
        )
        channel = interaction.guild.get_channel(channel_id)
        await upsert_channel_settings(interaction.client.pool, channel_id, chat_enabled=self.enable)
        settings = await get_channel_settings(interaction.client.pool, channel_id)
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        embed = build_sigils_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "sigils"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChatRangeModal(discord.ui.Modal, title="Sigil Earning Range"):
    def __init__(self, channel_id: int, current: list):
        super().__init__()
        self.channel_id = channel_id
        display = ", ".join(str(x) for x in current) if current else "19, 25"
        self.add_item(discord.ui.TextInput(
            label=f"Exact OR min, max ({SIGIL_CURRENCY_NAME} per batch)",
            style=discord.TextStyle.short,
            placeholder="19, 25",
            default=display,
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        parts = [x.strip() for x in self.children[0].value.split(",") if x.strip()]
        try:
            vals = [int(x) for x in parts]
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer(s).", ephemeral=True)
        if len(vals) not in (1, 2) or any(v < 1 for v in vals):
            return await interaction.response.send_message(f"{NO_EMOTE} Provide 1 (exact) or 2 (min, max) positive integers.", ephemeral=True)
        await upsert_channel_settings(interaction.client.pool, self.channel_id, chat_range=vals)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        embed = build_sigils_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "sigils"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChatMsgRangeModal(discord.ui.Modal, title="Messages per Batch"):
    def __init__(self, channel_id: int, current: list):
        super().__init__()
        self.channel_id = channel_id
        display = ", ".join(str(x) for x in current) if current else "15, 20"
        self.add_item(discord.ui.TextInput(
            label=f"Exact OR min, max ({SIGIL_CURRENCY_NAME} per batch)",
            style=discord.TextStyle.short,
            placeholder="15, 20",
            default=display,
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        parts = [x.strip() for x in self.children[0].value.split(",") if x.strip()]
        try:
            vals = [int(x) for x in parts]
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer(s).", ephemeral=True)
        if len(vals) not in (1, 2) or any(v < 1 for v in vals):
            return await interaction.response.send_message(f"{NO_EMOTE} Provide 1 (exact) or 2 (min, max) positive integers.", ephemeral=True)
        await upsert_channel_settings(interaction.client.pool, self.channel_id, chat_msg_range=vals)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        embed = build_sigils_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "sigils"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class SetBoostModal(discord.ui.Modal, title="Set Role Boost"):
    def __init__(self, channel_id: int, role_id: int, current_value: str = None,
                 settings_interaction=None):
        super().__init__()
        self.channel_id = channel_id
        self.role_id = role_id
        self.settings_interaction = settings_interaction
        self.add_item(discord.ui.TextInput(
            label=f"Boost value (e.g. +20 adds, 80 sets cap)",
            style=discord.TextStyle.short,
            placeholder="+20 or 80",
            default=current_value or "",
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        val = self.children[0].value.strip()
        if not val:
            return await interaction.response.send_message(f"{NO_EMOTE} Value cannot be empty.", ephemeral=True)
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        current = settings.get("chat_boosted_roles", [])
        parsed = await parse_boosted_roles(current)
        new_roles = [entry for entry in parsed if not (isinstance(entry, list) and len(entry) == 2 and entry[0] == self.role_id)]
        new_roles.append([self.role_id, val])
        serialized = await serialize_boosted_roles(new_roles)
        await upsert_channel_settings(interaction.client.pool, self.channel_id, chat_boosted_roles=serialized)
        channel = interaction.guild.get_channel(self.channel_id)
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        guild_config = await get_guild_settings(interaction.client.pool, channel.guild.id if channel else interaction.guild_id)
        role = interaction.guild.get_role(self.role_id)
        role_desc = f"**Selected:** {role.mention}\n**Current Boost:** `{val}`\n"
        role_desc += "*(adds to daily cap)*" if val.startswith("+") else "*(sets daily cap to this value)*"
        role_embed = discord.Embed(title="Role Boost", description=role_desc, color=role.color if role.color.value else discord.Color.purple())
        role_view = ChatBoostRoleView(self.channel_id, self.role_id, self.settings_interaction)
        await interaction.response.edit_message(embed=role_embed, view=role_view)
        if self.settings_interaction:
            settings_embed = build_sigils_embed(channel, settings, guild_config)
            settings_view = EventSettingsView(channel, settings, guild_config, settings_interaction=self.settings_interaction)
            settings_view.active_tab = "sigils"
            settings_view._build()
            await self.settings_interaction.edit_original_response(embed=settings_embed, view=settings_view)


class ChatBoostRoleView(discord.ui.View):
    def __init__(self, channel_id: int, role_id: int, settings_interaction):
        super().__init__()
        self.channel_id = channel_id
        self.role_id = role_id
        self.settings_interaction = settings_interaction

    @discord.ui.button(label="Set Boost", style=discord.ButtonStyle.primary)
    async def set_boost(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        current = settings.get("chat_boosted_roles", [])
        parsed = await parse_boosted_roles(current)
        existing = None
        for entry in parsed:
            if isinstance(entry, list) and len(entry) == 2 and entry[0] == self.role_id:
                existing = entry[1]
                break
        await interaction.response.send_modal(SetBoostModal(
            self.channel_id, self.role_id, existing, self.settings_interaction
        ))

    @discord.ui.button(label="Remove Boost", style=discord.ButtonStyle.danger)
    async def remove_boost(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        current = settings.get("chat_boosted_roles", [])
        parsed = await parse_boosted_roles(current)
        new_roles = [entry for entry in parsed if not (isinstance(entry, list) and len(entry) == 2 and entry[0] == self.role_id)]
        serialized = await serialize_boosted_roles(new_roles)
        await upsert_channel_settings(interaction.client.pool, self.channel_id, chat_boosted_roles=serialized)
        channel = interaction.guild.get_channel(self.channel_id)
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        guild_config = await get_guild_settings(interaction.client.pool, channel.guild.id if channel else interaction.guild_id)
        role = interaction.guild.get_role(self.role_id)
        await interaction.response.edit_message(
            content=f"{YES_EMOTE} Boost for {role.mention} has been removed.",
            embed=None, view=None
        )
        if self.settings_interaction:
            settings_embed = build_sigils_embed(channel, settings, guild_config)
            settings_view = EventSettingsView(channel, settings, guild_config, settings_interaction=self.settings_interaction)
            settings_view.active_tab = "sigils"
            settings_view._build()
            await self.settings_interaction.edit_original_response(embed=settings_embed, view=settings_view)


class ChatBoostedRolesSelect(discord.ui.RoleSelect):
    def __init__(self, channel_id: int, settings_interaction=None):
        super().__init__(placeholder="Select a role to boost...", min_values=1, max_values=1, row=1)
        self.channel_id = channel_id
        self.settings_interaction = settings_interaction

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        current = settings.get("chat_boosted_roles", [])
        parsed = await parse_boosted_roles(current)

        existing = None
        for entry in parsed:
            if isinstance(entry, list) and len(entry) == 2 and entry[0] == role.id:
                existing = entry[1]
                break

        desc = f"**Selected:** {role.mention}\n"
        if existing:
            desc += f"**Current Boost:** `{existing}`\n"
            if existing.startswith("+"):
                desc += "*(adds to daily cap)*"
            else:
                desc += "*(sets daily cap to this value)*"
        else:
            desc += "No boost set for this role yet."

        embed = discord.Embed(
            title="Role Boost",
            description=desc,
            color=role.color if role.color.value else discord.Color.purple()
        )

        view = ChatBoostRoleView(self.channel_id, role.id, self.settings_interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ChatMaxCapModal(discord.ui.Modal, title=f"Max Daily {SIGIL_CURRENCY_NAME}"):
    def __init__(self, guild_id: int, current: int):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(
            label=f"Maximum Daily {SIGIL_CURRENCY_NAME} (server-wide)",
            style=discord.TextStyle.short,
            placeholder=str(current),
            default=str(current),
            required=True,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.children[0].value)
        except ValueError:
            return await interaction.response.send_message(f"{NO_EMOTE} Invalid integer.", ephemeral=True)
        if val < 1:
            return await interaction.response.send_message(f"{NO_EMOTE} Must be at least 1.", ephemeral=True)
        await upsert_guild_settings(interaction.client.pool, self.guild_id, chat_max_cap=val)
        channel = interaction.guild.get_channel(parse_channel_id(interaction))
        settings = await get_channel_settings(interaction.client.pool, parse_channel_id(interaction))
        guild_config = await get_guild_settings(interaction.client.pool, self.guild_id)
        embed = build_sigils_embed(channel, settings, guild_config)
        view = EventSettingsView(channel, settings, guild_config)
        view.active_tab = "sigils"
        view._build()
        await interaction.response.edit_message(embed=embed, view=view)


class ChatRangeButton(discord.ui.Button):
    def __init__(self, channel_id: int):
        super().__init__(label="Earning Range", style=discord.ButtonStyle.secondary, emoji=SIGIL_EMOTE, row=2)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        current = list(settings.get("chat_range", [19, 25]))
        await interaction.response.send_modal(ChatRangeModal(self.channel_id, current))


class ChatMsgRangeButton(discord.ui.Button):
    def __init__(self, channel_id: int):
        super().__init__(label="Messages per Batch", style=discord.ButtonStyle.secondary, emoji="💬", row=2)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        settings = await get_channel_settings(interaction.client.pool, self.channel_id)
        current = list(settings.get("chat_msg_range", [15, 20]))
        await interaction.response.send_modal(ChatMsgRangeModal(self.channel_id, current))


class ChatMaxCapButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Max Daily Cap (Server)", style=discord.ButtonStyle.secondary, emoji="📊", row=2)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        gc = await get_guild_settings(interaction.client.pool, self.guild_id)
        current = gc.get("chat_max_cap", DEFAULT_CHAT_MAX_CAP)
        await interaction.response.send_modal(ChatMaxCapModal(self.guild_id, current))


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
        if channel is None:
            channel = interaction.channel

        await ensure_minigame_settings_table(interaction.client.pool)
        await ensure_minigame_guild_settings_table(interaction.client.pool)
        await ensure_minigame_sigils_table(interaction.client.pool)
        settings = await get_channel_settings(interaction.client.pool, channel.id)
        guild_config = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        embed = build_minigames_embed(channel, settings)
        view = EventSettingsView(channel, settings, guild_config, settings_interaction=interaction)
        view.active_tab = "minigames"
        view._build()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @events_settings.error
    async def events_settings_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventSystem(bot))
