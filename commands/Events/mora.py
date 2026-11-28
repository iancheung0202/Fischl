"""/mora and its tabs (stats, track, quests, kingdom, sigils, settings), /gift, and chest streaks."""

import asyncio
import datetime
import io
import os
import time

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select

from commands.Events.config import (
    ANIMATED_INVENTORY_BG_PATH,
    BALANCE_COMMAND,
    CURRENCY_NAME,
    DEFAULT_CHAT_MAX_CAP,
    DEFAULT_CHAT_MSG_RANGE,
    DOT_EMOTE,
    EMOTE_BLANK,
    EMOTE_MAX_STREAK,
    EMOTE_STREAK,
    GLOBAL_MORA_EMOTE,
    GLOBAL_SIGIL_EMOTE,
    GUILD_MORA_EMOTE,
    GUILD_SIGIL_EMOTE,
    INVENTORY_BG_PATH,
    KINGDOM_NAME,
    MORA_CHEST_NAME,
    MORA_CHEST_TIERS,
    MORA_EMOTE,
    NO_EMOTE,
    NO_EMOTE_2,
    PRESTIGE_EMOTE,
    REPLY_EMOTE,
    RESOLVED_EMOTE,
    SEASONS,
    SIGIL_CURRENCY_NAME,
    SIGIL_EMOTE,
    TRACK_EMOTE,
    UNRESOLVED_EMOTE,
    VIEW_FULL_TRACK,
    YES_EMOTE,
    YES_EMOTE_2,
    PurchaseEliteTrack,
    ThanksEliteTrack,
    profile_link_button,
)
from commands.Events.createProfileCard import createProfileCard
from commands.Events.domain import (
    BUILDINGS,
    calculate_cost,
    get_kingdom_embed,
    get_rank_title,
    upgrade_building,
)
from commands.Events.helperFunctions import (
    addMora,
    apply_discount,
    get_channel_settings,
    get_chest_counts,
    get_chest_streaks,
    get_cosmetics,
    get_daily_sigils,
    get_domain_discount,
    get_guild_mora,
    get_guild_settings,
    get_kingdom_buildings,
    get_milestones_list,
    get_mora_stats,
    get_progression_data,
    get_sigils_balance,
    get_user_inventory,
    get_user_minigame_settings,
    get_user_mora_history,
    get_user_stats,
    parse_boosted_roles,
    spend_mora,
    upsert_chest_streaks,
    upsert_user_minigame_setting,
)
from commands.Events.quests import (
    QUEST_BONUS_XP,
    QUEST_DESCRIPTIONS,
    QUEST_XP_REWARDS,
    get_quest_data,
    update_quest,
)
from commands.Events.seasons import get_current_season
from commands.Events.shop import is_role
from commands.Events.trackData import get_current_track, is_elite_active
from utils.commands import SlashCommand

FIXSTREAK_OWNER_ID = 692254240290242601
STREAK_RESTORE_COST_PER_DAY = 10000
# Images are sent here so an embed can show them by link.
IMAGE_CHANNEL = 1026968305208131645
LAST_TIER = 31
BONUS_TIER_XP = 2500
FIELD_LIMIT = 1024
# Room kept in the inventory field for the "(n more...)" line.
MORE_LINE_ROOM = 15
TABS = ("home", "graph", "track", "quests", "domain", "sigils", "settings")
# What each settings choice turns on or off: its column, its name in the menu and in the answer.
SETTINGS = {
    "toggle_chest_spawn": (
        "chest_disabled",
        "Daily Chest Spawning",
        "Daily chest spawning",
    ),
    "toggle_minigame_spawn": (
        "minigame_disabled",
        "Minigame Spawning",
        "Minigame spawning",
    ),
    "toggle_sigils_spawn": (
        "sigils_disabled",
        f"{SIGIL_CURRENCY_NAME} Chat Earning",
        f"{SIGIL_CURRENCY_NAME} chat earning",
    ),
}
STREAK_TIP = "Tip: Claim your chest at the same time each day to keep your streak!"
BOLD_DIGITS = dict(zip("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"))
RANK = """
    SELECT total, place FROM (
        SELECT uid, SUM({amount}) AS total,
               ROW_NUMBER() OVER (ORDER BY SUM({amount}) DESC, uid) AS place
        FROM {table} {where} GROUP BY uid
    ) ranked WHERE uid = $1
"""
# pyplot draws one figure at a time.
GRAPH_LOCK = asyncio.Lock()


def days(count: int) -> str:
    """Gives a number of days as shown in embeds, such as `3` days."""
    return f"`{count}` day{'s' if count != 1 else ''}"


def streak_state(saved: dict) -> tuple[int, int, bool]:
    """Gives the streak as it counts today, the longest streak, and whether the streak is broken."""
    last = saved.get("last_claimed") if saved else None
    if isinstance(last, str):
        last = datetime.datetime.fromisoformat(last).date()
    elif isinstance(last, datetime.datetime):
        last = last.date()
    elif not isinstance(last, datetime.date):
        last = None
    today = datetime.datetime.now(datetime.timezone.utc).date()
    broken = not (last and (today - last).days <= 1)
    stored = saved.get("streak", 0) if saved else 0
    longest = saved.get("max_streak", stored) if saved else 0
    return (0 if broken else stored), longest, broken


async def chest_counts_text(pool, guild_id: int, user_id: int) -> tuple[str, int]:
    """Gives the line of chests a member opened per tier, and how many in all."""
    settings = await get_guild_settings(pool, guild_id)
    names = settings.get("chests_tier_names", MORA_CHEST_TIERS)
    emotes = dict(zip(names, settings.get("chests_emotes", [])))
    counts = await get_chest_counts(pool, guild_id, user_id)
    text = ""
    for index, name in enumerate(names):
        count = counts[index] if index < len(counts) else 0
        text += f"{emotes.get(name, EMOTE_BLANK)} `{count}` {EMOTE_BLANK}"
    return text, sum(counts)


async def standing(pool, table: str, amount: str, user_id: int, guild_id: int = None):
    """Gives a member's total in a table and their place among everyone; 0 and "N/A" with no entries."""
    scope = ("WHERE gid = $2", guild_id) if guild_id else ("",)
    statement = RANK.format(table=table, amount=amount, where=scope[0])
    row = await pool.fetchrow(statement, user_id, *scope[1:])
    return (row["total"] or 0, row["place"]) if row else (0, "N/A")


def short_amount(value, _) -> str:
    """Writes an axis value as 1.5M, 20K or 300."""
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:.0f}"


def draw_earnings(history: list, display_name: str) -> io.BytesIO:
    """Draws a member's running Mora total over time as a PNG."""
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.dates import DateFormatter

    timestamps, amounts = zip(*history)
    df = pd.DataFrame(
        {"timestamp": pd.to_datetime(list(timestamps), unit="s"), "mora": list(amounts)}
    ).sort_values("timestamp")

    plt.style.use("seaborn-v0_8-darkgrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    df["cumulative"] = df["mora"].cumsum()
    df["smooth"] = df["cumulative"].rolling(7, min_periods=1).mean()
    ax.plot(
        df["timestamp"],
        df["smooth"],
        color="#FFD700",
        linewidth=3,
        solid_capstyle="round",
    )
    ax.yaxis.set_major_formatter(plt.FuncFormatter(short_amount))
    ax.set_title(
        f"{display_name}'s {CURRENCY_NAME} Earnings History",
        fontsize=20,
        pad=20,
        fontweight="bold",
        color="#f5d8ff",
    )
    ax.set_ylabel(f"Total {CURRENCY_NAME}", fontsize=14, labelpad=16, color="white")
    ax.xaxis.set_major_formatter(DateFormatter("%b %d"))
    ax.tick_params(axis="both", which="major", labelsize=15, colors="white")
    ax.grid(True, alpha=1, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    image = io.BytesIO()
    plt.savefig(image, format="png", bbox_inches="tight", dpi=120, transparent=True)
    plt.close()
    image.seek(0)
    return image


async def generate_mora_graph(pool, user_id: int, guild_id: int, display_name: str):
    """Gives a member's earnings graph and the fields of their statistics, or None with no earnings."""
    history = await get_user_mora_history(pool, user_id, guild_id)
    if not history:
        return None

    numbers = await get_mora_stats(pool, user_id, guild_id)
    chests, total_chests = await chest_counts_text(pool, guild_id, user_id)
    current, longest, _ = streak_state(await get_chest_streaks(pool, guild_id, user_id))
    chests += (
        f"\n**Total:** `{total_chests}` {EMOTE_BLANK}"
        f"{EMOTE_STREAK} {days(current)} {EMOTE_BLANK}"
        f"{EMOTE_MAX_STREAK} {days(longest)}"
    )
    stats = {
        f"`📦` {MORA_CHEST_NAME}s": chests,
        "`📅` First Played": f"<t:{numbers['first_played']}:D>",
        "`💰` Largest Day Earning": f"<t:{numbers['largest_daily_date']}:D>\n({MORA_EMOTE} `{numbers['largest_daily']:,}`)",
        f"`📈` Average Daily {CURRENCY_NAME}": f"{MORA_EMOTE} `{numbers['average_daily']:,}`",
        "`✌️` Minigame Wins": f"`{numbers['entry_count'] - total_chests}` total wins",
        "`😎` Active Days": f"`{numbers['days_active']}` different day(s)",
    }
    async with GRAPH_LOCK:
        image = await asyncio.to_thread(draw_earnings, history, display_name)
    return discord.File(image, filename=f"{user_id}.png"), stats


async def image_link(client, file: discord.File) -> str:
    """Posts an image in the image channel and gives its link."""
    message = await client.get_channel(IMAGE_CHANNEL).send(file=file)
    return message.attachments[0].proxy_url


def tier_reached(track: list, xp: int) -> int:
    """Gives the highest tier of a track that this much XP reaches."""
    reached = 0
    for tier in track:
        if xp < tier["cumulative_xp"]:
            break
        reached = tier["tier"]
    return reached


def reward_text(text: str) -> str:
    """Colours a track reward: cosmetics cyan, prestige red."""
    lower = text.lower()
    if any(k in lower for k in ["title", "frame", "background", "custom", "express"]):
        return f"\u001b[1;2m\u001b[1;36m{text}\u001b[0m\u001b[0m"
    if "prestige" in lower:
        return f"\u001b[1;2m\u001b[1;31m{text}\u001b[0m\u001b[0m"
    return text


def track_table(track: list, current_tier: int) -> str:
    """Gives the code block listing the tiers up to two past the member's own."""
    table = "```ansi\n\u001b[2;34mTier    Free Track\u001b[0m              \u001b[2;33mElite Track (Patrons)\u001b[0m\n"
    table += "------------------------------------------------------\n"
    last_shown = min(len(track), current_tier + 2)
    visible = track[: last_shown + 1]
    for tier in visible:
        if tier["tier"] <= current_tier:
            status = "✅"
        elif tier["tier"] == current_tier + 1:
            status = "🔄"
        else:
            status = "🔐"
        free = reward_text(tier["free"].split("|")[0].strip()[:22].ljust(24))
        elite = reward_text(tier["elite"].split("|")[0].strip()[:22])
        table += (
            f"\u001b[1;37m{tier['tier']:2d}\u001b[0m  {status.ljust(2)} {free}{elite}\n"
        )
    if last_shown < len(track) - 1:
        table += f"... ({len(track) - (last_shown + 1)} more)\n"
    if any(tier["tier"] == LAST_TIER for tier in visible):
        table += f"Earn Bonus Drop Packs for every {BONUS_TIER_XP} XP gained!"
    return table + "```"


def progress_bar(fraction: float) -> str:
    """Gives a 20-character bar filled to a fraction."""
    filled = int(max(0, min(fraction, 1)) * 20)
    return "━" * filled + "-" * (20 - filled)


def bold_number(number: int) -> str:
    """Writes a number in bold digits."""
    return "".join(BOLD_DIGITS[digit] for digit in str(number))


async def track_embed(pool, member: discord.Member, custom_color) -> discord.Embed:
    """Gives the embed of a member's season track: tier, progress, the tiers ahead and their perks."""
    guild = member.guild
    data = await get_progression_data(pool, guild.id, member.id)
    xp = data["xp"]
    track = get_current_track()
    current_tier = tier_reached(track, xp)
    start_xp = track[current_tier - 1]["cumulative_xp"] if current_tier > 0 else 0
    xp_in_tier = xp - start_xp
    tier_xp = track[current_tier]["xp_req"] if current_tier < len(track) else 0

    if current_tier == LAST_TIER:
        tier_display = f"{LAST_TIER} + {data.get('bonus_tier', 0)} Bonus"
        past_last = (xp - track[-1]["cumulative_xp"]) % BONUS_TIER_XP
        next_tier = f"Next Bonus Tier: {past_last} / {BONUS_TIER_XP} XP"
    else:
        tier_display = str(current_tier)
        next_tier = f"\n Next Tier: {xp_in_tier} / {tier_xp} XP"
    bar = ""
    if current_tier < LAST_TIER:
        bar = f" {bold_number(current_tier)} {progress_bar(xp_in_tier / tier_xp if tier_xp else 0)} {bold_number(current_tier + 1)}\n"
    elite = await is_elite_active(pool, member.id, guild.id)

    season = get_current_season()
    embed = discord.Embed(
        title=f"{member.display_name}'s Progression Track in {guild.name}",
        description=(
            f"### [Season {season.id}: **{season.name}**](https://fischl.app/profile) {TRACK_EMOTE}\n-# <a:clock:1382887924273774754> *Season ends <t:{int(season.end_ts)}:R>* {VIEW_FULL_TRACK}\n-# {REPLY_EMOTE} **Earn XP** by purchasing in the shop and completing quests.\n"
            f"```diff\n"
            f"+ Current Tier: {tier_display} ({xp} total XP)\n"
            f"- Status: {'Elite Track Activated' if elite else 'Free Track Only'}\n"
            f"{next_tier}\n"
            f"{bar}"
            f"```\n"
            f"{track_table(track, current_tier)}\n"
            "`✅` = Tier reached     `🔄` = In progress     `🔐` = Locked\n"
        ),
        color=custom_color or discord.Color.purple(),
    )

    stats = await get_user_stats(pool, guild.id, member.id)
    gift_tax = stats.get("gift_tax", "Not unlocked")
    percent = "%" if gift_tax != "Not unlocked" and gift_tax is not None else ""
    cosmetics = await get_cosmetics(pool, guild.id, member.id)
    color = "`Not unlocked`"
    if cosmetics and cosmetics["embed_color"]:
        chosen = cosmetics.get("selected_embed_color_hex")
        color = f"`{chosen}`" if chosen else "`Unlocked but not set`"
    perks = {
        f"{MORA_EMOTE} {CURRENCY_NAME} Boost": f"`+{stats.get('mora_boost', 0)}%`",
        ":arrow_up_small: Daily Chest Upgrades": f"`{stats.get('chest_upgrades', 4)}`",
        ":gift: Gift Tax": f"`{gift_tax}{percent}`",
        "🧲 Minigame Summons": f"`{stats.get('minigame_summons', 0)}`",
        "🏷️ Shop Discount": f"`{stats.get('shop_discount', 0)}%`",
        f"🏰 {KINGDOM_NAME} Discount": f"`{stats.get('domain_discount', 0)}%`",
        "🎨 Custom Accent Color": color,
    }
    for name, value in perks.items():
        embed.add_field(name=name, value=value, inline=True)
    embed.add_field(
        name=f"{PRESTIGE_EMOTE} Prestige", value=f"`{data.get('prestige', 0)}`"
    )
    embed.set_footer(text="Tip: XP Progression is tracked separately per server.")
    return embed


async def quests_embed(client, member: discord.Member, channel_id: int, custom_color):
    """Gives the embed of a member's daily, weekly and monthly quests, renewed first when they ran out."""
    guild = member.guild
    await update_quest(member.id, guild.id, channel_id, 0, client, refresh_only=True)
    saved = await get_quest_data(client.pool, guild.id, member.id)

    lines = []
    for duration in ["daily", "weekly", "monthly"]:
        cycle = saved.get(duration, {})
        quests = cycle.get("quests", {})
        if not quests:
            continue
        end_time = cycle.get("end_time", 0)
        reset = f"<t:{end_time}:R>" if end_time else "Unknown"
        lines.append(
            f"### {duration.capitalize()} Quests - `{QUEST_XP_REWARDS[duration]}` XP each *(resets {reset})*"
        )
        for quest, progress in quests.items():
            status = f"`{progress['current']}/{progress['goal']}`"
            if quest in cycle.get("completed", {}):
                status += f" {YES_EMOTE}"
            lines.append(f"- {QUEST_DESCRIPTIONS.get(quest, quest)}: {status}")
        if cycle.get("bonus_awarded"):
            lines.append(
                f"-# {REPLY_EMOTE} *`{QUEST_BONUS_XP[duration]}` XP bonus already claimed! {RESOLVED_EMOTE}*"
            )
        else:
            lines.append(
                f"-# {REPLY_EMOTE} *Complete all for `+{QUEST_BONUS_XP[duration]}` XP bonus! {UNRESOLVED_EMOTE}*"
            )
    if not lines:
        starts = [s.start_ts for s in SEASONS if s.start_ts > time.time()]
        lines = ["No active quests."]
        if starts:
            lines[0] += f" The next season starts <t:{int(min(starts))}:R>."

    embed = discord.Embed(
        title=f"{member.display_name}'s Quests in {guild.name}",
        description="\n".join(lines),
        color=custom_color or discord.Color.green(),
    )
    embed.set_footer(text="Tip: Quests reset at the same time chests do")
    return embed


async def sigils_embed(pool, member: discord.Member, channel, custom_color):
    """Gives the embed of a member's sigils: balance, today's chat earnings and the roles that raise the cap."""
    guild = member.guild
    now = datetime.datetime.now(datetime.timezone.utc)
    balance = await get_sigils_balance(pool, member.id, guild.id)
    today = await get_daily_sigils(pool, member.id, guild.id, now.strftime("%Y-%m-%d"))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    reset = midnight + datetime.timedelta(days=1)

    guild_settings = await get_guild_settings(pool, guild.id)
    cap = int(guild_settings.get("chat_max_cap", DEFAULT_CHAT_MAX_CAP))
    settings = await get_channel_settings(pool, channel.id) if channel else {}
    bonuses = []
    for role_id, bonus in await parse_boosted_roles(
        settings.get("chat_boosted_roles", [])
    ):
        role = guild.get_role(role_id)
        if not role:
            continue
        if role not in member.roles:
            bonuses.append(f"-# {DOT_EMOTE} {role.mention}: `{bonus}`")
            continue
        if str(bonus).startswith("+"):
            cap += int(str(bonus).lstrip("+"))
        else:
            cap = max(cap, int(bonus))
        bonuses.append(f"{DOT_EMOTE} {role.mention}: `{bonus}` {YES_EMOTE}")

    embed = discord.Embed(
        title=f"{member.display_name}'s {SIGIL_CURRENCY_NAME} in {guild.name}",
        color=custom_color or discord.Color.purple(),
    )
    embed.add_field(name=f"{SIGIL_EMOTE} Balance", value=f"`{balance}`", inline=True)
    embed.add_field(
        name="Daily Chat Progress",
        value=f"`{today.get('earnings', 0)}/{cap}` {SIGIL_CURRENCY_NAME} earned",
        inline=True,
    )
    embed.add_field(
        name="Reset Time", value=f"<t:{int(reset.timestamp())}:R>", inline=True
    )
    if bonuses:
        embed.add_field(
            name="Role Bonuses to Max Sigils", value="\n".join(bonuses), inline=False
        )
    messages = settings.get("chat_msg_range", list(DEFAULT_CHAT_MSG_RANGE))
    embed.set_footer(
        text=f"Tip: Earn a batch of {SIGIL_CURRENCY_NAME} by sending {'-'.join(str(count) for count in messages[:2])} messages in enabled channels."
    )
    return embed


async def settings_embed(pool, member: discord.Member, channel, custom_color):
    """Gives the embed of what a member turned off for themselves beside what the channel has on."""
    guild = member.guild
    own = await get_user_minigame_settings(pool, guild.id, member.id)
    here = await get_channel_settings(pool, channel.id) if channel else {}
    features = (
        ("Daily Chest Spawning", "chest_disabled", "chests_enabled"),
        ("Minigame Spawning", "minigame_disabled", "minigames_enabled"),
        (f"{SIGIL_CURRENCY_NAME} Chat Earning", "sigils_disabled", "chat_enabled"),
    )
    embed = discord.Embed(
        title=f"{member.display_name}'s Settings in {guild.name}",
        description="A feature works only when both **you** and a **channel** both have it enabled.",
        color=custom_color or discord.Color.blurple(),
    )
    embed.add_field(
        name="Your Server Preferences",
        value=" \n".join(
            f"-# {DOT_EMOTE} {name}: {NO_EMOTE_2 if own[off] else YES_EMOTE_2}"
            for name, off, _ in features
        ),
        inline=True,
    )
    shown = guild.get_channel(channel.id) if channel else None
    embed.add_field(
        name=f"#{shown.name} (Current Channel)" if shown else "Current Channel",
        value=" \n".join(
            f"-# {DOT_EMOTE} {name}: {YES_EMOTE if here.get(on, False) else NO_EMOTE}"
            for name, _, on in features
        ),
        inline=True,
    )
    embed.set_footer(text="Tip: You can toggle your server preferences at any time.")
    return embed


class RestoreStreakModal(discord.ui.Modal, title="Restore Your Streak"):
    """Asks how many days of a broken streak to buy back."""

    days = discord.ui.TextInput(
        label="Days to restore",
        placeholder="Enter a number of days",
        required=True,
        max_length=5,
    )

    def __init__(self, button_view: discord.ui.View):
        super().__init__()
        self.button_view = button_view
        self.guild_id = button_view.guild_id
        self.user_id = button_view.user_id
        self.max_restorable = button_view.max_restorable
        self.days.placeholder = (
            f"Enter number of days between 1 and {self.max_restorable}"
        )

    async def on_submit(self, interaction: discord.Interaction):
        pool = interaction.client.pool
        raw = str(self.days.value).strip().replace(",", "")
        if not raw.isdigit():
            return await interaction.response.send_message(
                f"{NO_EMOTE} Please enter a whole number!", ephemeral=True
            )
        restored = int(raw)
        if restored <= 0:
            return await interaction.response.send_message(
                f"{NO_EMOTE} You need to restore at least `1` day!", ephemeral=True
            )
        if restored > self.max_restorable:
            return await interaction.response.send_message(
                f"{NO_EMOTE} You can only restore up to {days(self.max_restorable)}!",
                ephemeral=True,
            )

        cost = restored * STREAK_RESTORE_COST_PER_DAY
        balance = await get_guild_mora(pool, self.user_id, self.guild_id)
        short = (
            f"{NO_EMOTE} Restoring {days(restored)} costs {MORA_EMOTE} `{cost:,}`, "
            f"but you only have {MORA_EMOTE} `{int(balance):,}`!"
        )
        if balance < cost:
            return await interaction.response.send_message(short, ephemeral=True)

        current, longest, broken = streak_state(
            await get_chest_streaks(pool, self.guild_id, self.user_id)
        )
        if not broken or longest <= current:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Your streak isn't broken anymore, there's nothing to restore!",
                ephemeral=True,
            )

        streak = min(current + restored, longest)
        paid = await spend_mora(
            pool,
            self.user_id,
            cost,
            interaction.channel.id,
            self.guild_id,
            interaction.client,
        )
        if not paid:
            return await interaction.response.send_message(short, ephemeral=True)
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        await upsert_chest_streaks(
            pool, self.guild_id, self.user_id, streak, longest, today
        )

        embed = discord.Embed(
            title=f"{YES_EMOTE} Streak Restored!",
            description=(
                f"{EMOTE_STREAK} **New Streak:** {days(streak)}\n"
                f"{EMOTE_MAX_STREAK} **Max Streak:** {days(longest)}\n"
                f"{MORA_EMOTE} **Cost Paid:** `{cost:,}`"
            ),
            color=discord.Color.green(),
        )
        self.button_view.stop()
        await interaction.response.edit_message(embed=embed, view=None)


class RestoreStreakView(discord.ui.View):
    """The button under /streak that opens the restore box."""

    def __init__(self, guild_id: int, user_id: int, max_restorable: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id
        self.max_restorable = max_restorable
        self.message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Restore Streak", style=discord.ButtonStyle.green, emoji="✨"
    )
    async def restore_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You can't use this button!", ephemeral=True
            )
            return
        await interaction.response.send_modal(RestoreStreakModal(self))


class ToggleView(discord.ui.View):
    """The tabs under /mora; `member` is whose data is shown, and only the one who ran the command may use them."""

    def __init__(
        self, original_embed, member, command_user_id, custom_color=None, is_elite=False
    ):
        super().__init__(timeout=180)
        self.original_embed = original_embed
        self.member = member
        self.command_user_id = command_user_id
        self.custom_color = custom_color
        self.message = None
        self.state = "home"
        self.select = None
        self.add_item(profile_link_button())
        self.purchase_button = ThanksEliteTrack() if is_elite else PurchaseEliteTrack()
        self.add_item(self.purchase_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if (
            interaction.user.id == self.command_user_id
            or interaction.data.get("custom_id") == self.purchase_button.custom_id
        ):
            return True
        await interaction.response.send_message(
            "You can't use this button!", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
        self.stop()

    async def show(self, interaction: discord.Interaction, state: str, embed):
        """Switches to a tab and shows its embed."""
        self.state = state
        await self.update_buttons(interaction.client.pool)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Inventory",
        style=discord.ButtonStyle.blurple,
        disabled=True,
        custom_id="home",
    )
    async def home_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.show(interaction, "home", self.original_embed)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.grey, custom_id="graph")
    async def graph_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        member = self.member
        await interaction.response.defer()  # drawing can take longer than Discord waits
        result = await generate_mora_graph(
            interaction.client.pool, member.id, member.guild.id, member.display_name
        )
        if not result:
            await interaction.followup.send(
                "No data available! Start playing to see your stats.", ephemeral=True
            )
            return

        graph, stats = result
        embed = discord.Embed(
            title=f"{member.display_name}'s Player Statistics in {member.guild.name}",
            color=self.custom_color or 0x02E6C3,
        )
        for index, (name, value) in enumerate(stats.items()):
            embed.add_field(name=name, value=value, inline=index > 0)
        embed.set_image(url=await image_link(interaction.client, graph))
        embed.set_footer(text=STREAK_TIP)
        await self.show(interaction, "graph", embed)

    @discord.ui.button(label="Track", style=discord.ButtonStyle.grey, custom_id="track")
    async def track_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = await track_embed(
            interaction.client.pool, self.member, self.custom_color
        )
        await self.show(interaction, "track", embed)

    @discord.ui.button(
        label="Quests", style=discord.ButtonStyle.grey, custom_id="quests"
    )
    async def quests_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = await quests_embed(
            interaction.client, self.member, interaction.channel.id, self.custom_color
        )
        await self.show(interaction, "quests", embed)

    @discord.ui.button(
        label=KINGDOM_NAME, style=discord.ButtonStyle.grey, custom_id="domain"
    )
    async def domain_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = await get_kingdom_embed(
            self.member,
            self.member.guild.id,
            self.custom_color,
            interaction.client.pool,
        )
        await self.show(interaction, "domain", embed)

    @discord.ui.button(
        label=SIGIL_CURRENCY_NAME, style=discord.ButtonStyle.grey, custom_id="sigils"
    )
    async def sigils_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        shown = self.member
        if interaction.user.id == shown.id:
            shown = interaction.user
        embed = await sigils_embed(
            interaction.client.pool, shown, interaction.channel, self.custom_color
        )
        await self.show(interaction, "sigils", embed)

    @discord.ui.button(
        label="Settings", style=discord.ButtonStyle.grey, custom_id="settings"
    )
    async def settings_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = await settings_embed(
            interaction.client.pool,
            self.member,
            interaction.channel,
            self.custom_color,
        )
        await self.show(interaction, "settings", embed)

    async def upgrade_select_callback(self, interaction: discord.Interaction):
        """Buys the next level of the chosen building."""
        building = self.select.values[0].replace("upgrade_", "")
        success, said = await upgrade_building(
            interaction.user.id, interaction.guild.id, building, interaction
        )
        if not success:
            return await interaction.response.send_message(
                f"{NO_EMOTE} {said}", ephemeral=True
            )
        embed = await get_kingdom_embed(
            interaction.user,
            interaction.guild.id,
            self.custom_color,
            interaction.client.pool,
        )
        await self.show(interaction, "domain", embed)
        await interaction.followup.send(f"{YES_EMOTE} {said}", ephemeral=True)

    async def settings_select_callback(self, interaction: discord.Interaction):
        """Turns the chosen feature on or off for the member."""
        pool, guild_id = interaction.client.pool, interaction.guild.id
        column, _, label = SETTINGS[self.select.values[0]]
        own = await get_user_minigame_settings(pool, guild_id, self.member.id)
        off = not own[column]
        await upsert_user_minigame_setting(pool, guild_id, self.member.id, column, off)
        chests = interaction.client.get_cog("TheEventItself")
        if chests and hasattr(chests, "chest_system"):
            chests.chest_system.invalidate_flag_cache(guild_id, self.member.id)

        embed = await settings_embed(
            pool, self.member, interaction.channel, self.custom_color
        )
        await self.show(interaction, "settings", embed)
        await interaction.followup.send(
            f"{YES_EMOTE} {label} is now **{'disabled' if off else 'enabled'}**!",
            ephemeral=True,
        )

    async def upgrade_options(self, pool) -> list:
        """Gives one choice per building with its next level and price."""
        guild_id = self.member.guild.id
        levels = await get_kingdom_buildings(pool, guild_id, self.command_user_id)
        discount = await get_domain_discount(pool, guild_id, self.command_user_id)
        options = []
        for key, info in BUILDINGS.items():
            level = levels.get(key, 0)
            cost = calculate_cost(level)
            lower = apply_discount(cost, discount)
            price = f"{cost:,}"
            if discount > 0 and lower < cost:
                price = f"{lower:,} (discounted)"
            options.append(
                discord.SelectOption(
                    label=f"{info['emoji']} {info['name']}",
                    description=f"Lv. {level} ➜ Lv. {level+1} | Cost: {price}",
                    value=f"upgrade_{key}",
                    emoji=info["emoji"],
                )
            )
        return options

    def locked_select(self, placeholder: str, reason: str, custom_id: str) -> Select:
        """Gives the greyed-out menu shown to someone looking at another member."""
        return Select(
            placeholder=placeholder,
            options=[discord.SelectOption(label=reason, value="dummy")],
            disabled=True,
            custom_id=custom_id,
            row=2,
        )

    async def update_buttons(self, pool):
        """Marks the open tab and puts that tab's menu under the buttons."""
        for child in self.children:
            if child.custom_id in TABS:
                opened = child.custom_id == self.state
                child.disabled = opened
                child.style = (
                    discord.ButtonStyle.blurple if opened else discord.ButtonStyle.grey
                )
        if self.select:
            self.remove_item(self.select)
            self.select = None

        own = self.member.id == self.command_user_id
        if self.state == "domain" and not own:
            self.select = self.locked_select(
                f"Viewing {KINGDOM_NAME} (Read Only)",
                "Only the owner can upgrade",
                "kingdom_upgrade_select_disabled",
            )
        elif self.state == "domain":
            self.select = Select(
                placeholder="Choose a building to upgrade...",
                options=await self.upgrade_options(pool),
                custom_id="kingdom_upgrade_select",
                row=2,
            )
            self.select.callback = self.upgrade_select_callback
        elif self.state == "settings" and not own:
            self.select = self.locked_select(
                "Viewing Settings (Read Only)",
                "Only the owner can edit",
                "settings_select_disabled",
            )
        elif self.state == "settings":
            self.select = Select(
                placeholder="Select a setting to modify...",
                options=[
                    discord.SelectOption(label=name, value=key)
                    for key, (_, name, _) in SETTINGS.items()
                ],
                custom_id="settings_select",
                row=2,
            )
            self.select.callback = self.settings_select_callback
        if self.select:
            self.add_item(self.select)


def owned_line(name, count: int, since: int, pinned: bool) -> str:
    """Gives the inventory line of one item or role a member bought."""
    prefix = "📌 **Pinned:** " if pinned else "- "
    shown = f"<@&{name}>" if is_role(name) else name
    if count > 1:
        return f"{prefix}{shown} **(x{count})** - *First acquired <t:{since}:R>*"
    return f"{prefix}{shown} - *Acquired <t:{since}:R>*"


def inventory_text(items: list) -> str:
    """Lists what a member bought, pinned first, cut to fit one embed field."""
    groups = {True: {}, False: {}}
    for name, _, cost, _, timestamp, pinned, *_ in items:
        if cost == 0:
            continue
        count, since = groups[bool(pinned)].get(name, (0, timestamp))
        groups[bool(pinned)][name] = (count + 1, min(since, timestamp))
    lines = [
        owned_line(name, count, since, pinned)
        for pinned in (True, False)
        for name, (count, since) in groups[pinned].items()
    ]
    if not lines:
        return f"No {SlashCommand('shop')} items purchased yet"

    text, shown = "", 0
    for line in lines:
        if len(text) + len(line) + MORE_LINE_ROOM > FIELD_LIMIT:
            break
        text += line + "\n"
        shown += 1
    if shown < len(lines):
        text += f"*({len(lines) - shown} more...)*"
    return text.strip()


def milestones_text(milestones: list, items: list) -> str:
    """Lists the milestones a member earned, lowest first."""
    earned = {name: timestamp for name, _, cost, _, timestamp, *_ in items if cost == 0}
    reached = sorted(
        (milestone for milestone in milestones if milestone[1] in earned),
        key=lambda milestone: milestone[2],
    )
    if not reached:
        return f"No {SlashCommand('milestones')} earned yet"
    return "".join(
        f"- {f'<@&{reward}>' if is_role(reward) else reward} - *Earned at {MORA_EMOTE} `{threshold:,}` <t:{earned[reward]}:R>*\n"
        for _, reward, threshold, *_ in reached
    )


def title_line(cosmetics: dict):
    """Gives the heading showing the title a member picked, or None."""
    if cosmetics.get("selected_custom_title"):
        return f"### {cosmetics['selected_custom_title']}"
    key = cosmetics.get("selected_title")
    if not key:
        return None
    for entry in cosmetics.get("titles") or []:
        if len(entry) >= 2 and entry[0] == key:
            pin = "<:rank:1364439165189488854>" if "<a:" not in entry[1] else ""
            return f"### {pin}{entry[1]}"
    return None


class Mora(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name=BALANCE_COMMAND, description=f"Check a user's {CURRENCY_NAME} inventory"
    )
    @app_commands.describe(user="Specify any user other than yourself if needed")
    async def mora(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer(thinking=True)
        user = user or interaction.user
        pool, guild = interaction.client.pool, interaction.guild

        global_total, global_rank = await standing(
            pool, "minigame_mora", "count", user.id
        )
        global_sigils, global_sigils_rank = await standing(
            pool, "minigame_sigils", "earnings", user.id
        )
        guild_total, guild_rank = await standing(
            pool, "minigame_mora", "count", user.id, guild.id
        )
        guild_sigils, guild_sigils_rank = await standing(
            pool, "minigame_sigils", "earnings", user.id, guild.id
        )

        cosmetics = await get_cosmetics(pool, guild.id, user.id) or {}
        elite = await is_elite_active(pool, user.id, guild.id)
        color_hex = cosmetics.get("selected_embed_color_hex") if elite else None
        custom_color = discord.Color(int(color_hex, 16)) if color_hex else None

        embed = discord.Embed(
            title=f"{user.display_name}'s Inventory in {guild.name}",
            description="",
            color=custom_color or discord.Color.gold(),
        )
        if guild_rank != "N/A":
            embed.add_field(
                name=guild.name,
                value=(
                    f"{GUILD_MORA_EMOTE} {CURRENCY_NAME}: **`{int(guild_total):,}`**\n"
                    f"{GUILD_SIGIL_EMOTE} {SIGIL_CURRENCY_NAME}: **`{int(guild_sigils):,}`**"
                ),
                inline=True,
            )
        if global_rank != "N/A":
            embed.add_field(
                name="Global",
                value=(
                    f"{GLOBAL_MORA_EMOTE} {CURRENCY_NAME}: **`{int(global_total):,}`**\n"
                    f"{GLOBAL_SIGIL_EMOTE} {SIGIL_CURRENCY_NAME}: **`{int(global_sigils):,}`**"
                ),
                inline=True,
            )

        items = await get_user_inventory(pool, user.id, guild.id)
        embed.add_field(
            name="Guild Inventory", value=inventory_text(items), inline=False
        )
        milestones = await get_milestones_list(pool, guild.id)
        embed.add_field(
            name="Guild Milestones",
            value=milestones_text(milestones, items),
            inline=False,
        )
        title = title_line(cosmetics)
        if title:
            embed.description = f"{title}\n{embed.description}"

        animated = cosmetics.get("selected_animated_background") if elite else None
        frame = cosmetics.get("selected_profile_frame")
        customized = (
            os.path.isfile(f"{INVENTORY_BG_PATH}/{user.id}.png")
            or bool(frame)
            or bool(animated)
        )
        look = {}
        if customized:
            background = f"{INVENTORY_BG_PATH}/{user.id}.png"
            if animated:
                background = f"{ANIMATED_INVENTORY_BG_PATH}/{animated}"
                if not os.path.exists(background) and not animated.lower().endswith(
                    ".gif"
                ):
                    background = f"{background}.gif"
            look = {"bg": background, "profile_frame": frame or None}
        card = await createProfileCard(
            user,
            f"{int(guild_total):,}",
            guild_rank,
            f"{int(guild_sigils):,}",
            guild_sigils_rank,
            f"{int(global_total):,}",
            global_rank,
            f"{int(global_sigils):,}",
            global_sigils_rank,
            accent_color_hex=color_hex,
            font_name=cosmetics.get("selected_font") if elite else None,
            **look,
        )

        levels = await get_kingdom_buildings(pool, guild.id, user.id)
        kingdom_level = sum(levels.values())
        if kingdom_level > 0:
            embed.set_footer(
                text=f"{KINGDOM_NAME} Rank: {get_rank_title(kingdom_level)} (Lv. {kingdom_level}) "
            )
        embed.set_image(url=await image_link(interaction.client, discord.File(card)))

        view = ToggleView(
            embed, user, interaction.user.id, custom_color=custom_color, is_elite=elite
        )
        view.message = await interaction.followup.send(embed=embed, view=view)
        if not customized:
            await interaction.followup.send(
                f"💡 Tip: Customize your inventory however you like (custom background, profile frame, titles) with {SlashCommand('customize')}!",
                ephemeral=True,
            )

    @app_commands.command(
        name="gift", description=f"Gift {CURRENCY_NAME} to another user"
    )
    @app_commands.describe(
        user=f"User to gift {CURRENCY_NAME} to",
        amount=f"Amount of {CURRENCY_NAME} to gift",
    )
    async def gift(
        self, interaction: discord.Interaction, user: discord.Member, amount: int
    ):
        await interaction.response.defer()
        client, pool = interaction.client, interaction.client.pool
        guild_id, channel_id = interaction.guild.id, interaction.channel.id
        donor = interaction.user

        stats = await get_user_stats(pool, guild_id, donor.id)
        problem = None
        if stats.get("gift_tax") is None:
            problem = "⏳ You haven't unlocked gifting for this season yet. Unlock it at Tier `5` in the free track!"
        elif amount <= 0:
            problem = f"{NO_EMOTE} Amount must be positive and non-zero!"
        elif amount < 100:
            problem = f"{NO_EMOTE} The minimum amount to gift is {MORA_EMOTE} `100`!"
        elif donor == user:
            problem = f"{NO_EMOTE} You can't gift {MORA_EMOTE} to yourself!"
        elif user.bot:
            problem = f"{NO_EMOTE} Why would you waste your {MORA_EMOTE} on a non-human being?"
        if problem:
            return await interaction.followup.send(problem)

        tax_rate = stats["gift_tax"]
        tax = int(amount * tax_rate / 100)
        total_cost = amount + tax
        donor_mora = await get_guild_mora(pool, donor.id, guild_id)
        recipient_mora = await get_guild_mora(pool, user.id, guild_id)
        if donor_mora < total_cost or not await spend_mora(
            pool, donor.id, total_cost, channel_id, guild_id, client
        ):
            return await interaction.followup.send(
                f"You need {MORA_EMOTE} `{total_cost}` ({amount} + {tax_rate}% tax) to make this gift! \n-# You currently only have {MORA_EMOTE} `{donor_mora}`."
            )

        await addMora(
            pool, user.id, amount, channel_id, guild_id, client, bypass_boost=True
        )
        await addMora(
            pool, client.user.id, tax, channel_id, guild_id, client, bypass_boost=True
        )

        embed = discord.Embed(
            title="<a:2_star:1366158196213022800> Gift Sent",
            description=(
                f"**Sender:** {donor.mention}\n"
                f"**Total Deducted:** {MORA_EMOTE} `{total_cost:,}`\n"
                f"-# Fischl also collected {MORA_EMOTE} `{tax:,}` ({tax_rate}%) in taxes\n\n"
                f"**Recipient:** {user.mention}\n"
                f"**Total Received:** {MORA_EMOTE} `{amount:,}`"
            ),
            color=0x2ECC71,
        )
        embed.set_footer(
            text="Sharing is caring! You just made your friend's day a little brighter!"
        )
        await interaction.followup.send(
            content=f"{user.mention} has been blessed by {donor.mention}! <a:2_star:1366158196213022800>",
            embed=embed,
        )

        quests = {"gift_mora": amount, "gift_mora_unique": user.id}
        if recipient_mora < donor_mora:
            quests["gift_mora_poorer"] = 1
        await update_quest(donor.id, guild_id, channel_id, quests, client)

    @app_commands.command(
        name="streak", description=f"Check your {MORA_CHEST_NAME} streak"
    )
    async def streak(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        pool, guild_id, user = (
            interaction.client.pool,
            interaction.guild.id,
            interaction.user,
        )
        current, longest, broken = streak_state(
            await get_chest_streaks(pool, guild_id, user.id)
        )
        chests, total_chests = await chest_counts_text(pool, guild_id, user.id)

        embed = discord.Embed(
            title=f"{user.display_name}'s {MORA_CHEST_NAME} Streak",
            description="",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name=f"`📦` {MORA_CHEST_NAME}s",
            value=f"{chests}\n**Total:** `{total_chests}`",
            inline=False,
        )
        embed.add_field(
            name="Current Streak", value=f"{EMOTE_STREAK} {days(current)}", inline=True
        )
        embed.add_field(
            name="Max Streak", value=f"{EMOTE_MAX_STREAK} {days(longest)}", inline=True
        )
        embed.set_footer(text=STREAK_TIP)

        restorable = max(0, longest - current)
        if not broken or restorable == 0:
            return await interaction.followup.send(embed=embed)
        embed.add_field(
            name="💔 Streak Broken!",
            value=(
                f"You can restore up to {days(restorable)} "
                f"back towards your max streak.\n"
                f"-# Costs {MORA_EMOTE} `{STREAK_RESTORE_COST_PER_DAY:,}` per day restored."
            ),
            inline=False,
        )
        view = RestoreStreakView(guild_id, user.id, restorable)
        view.message = await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(
        name="fixstreak", description="[Owner Only] Manually fix a user's chest streak"
    )
    @app_commands.describe(
        user="The user whose streak to fix",
        new_streak="The new current streak to set",
        new_max_streak="The new max streak to set",
        mora_to_deduct=f"Optional amount of {CURRENCY_NAME} to deduct from the user",
    )
    async def fixstreak(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        new_streak: int,
        new_max_streak: int,
        mora_to_deduct: int = None,
    ):
        if interaction.user.id != FIXSTREAK_OWNER_ID:
            return
        await interaction.response.defer(ephemeral=True)
        pool, guild_id = interaction.client.pool, interaction.guild.id

        if new_streak < 0 or new_max_streak < 0:
            return await interaction.followup.send(
                f"{NO_EMOTE} Streak values can't be negative!", ephemeral=True
            )
        if mora_to_deduct is not None and mora_to_deduct < 0:
            return await interaction.followup.send(
                f"{NO_EMOTE} Mora to deduct can't be negative!", ephemeral=True
            )
        if mora_to_deduct:
            balance = await get_guild_mora(pool, user.id, guild_id)
            if balance < mora_to_deduct:
                return await interaction.followup.send(
                    f"{NO_EMOTE} {user.mention} only has {MORA_EMOTE} `{int(balance):,}`, "
                    f"can't deduct {MORA_EMOTE} `{mora_to_deduct:,}`!",
                    ephemeral=True,
                )
            await addMora(
                pool,
                user.id,
                -mora_to_deduct,
                interaction.channel.id,
                guild_id,
                interaction.client,
                bypass_boost=True,
            )

        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        await upsert_chest_streaks(
            pool, guild_id, user.id, new_streak, new_max_streak, today
        )

        deducted = ""
        if mora_to_deduct:
            deducted = f"\n{MORA_EMOTE} **Mora Deducted:** `{mora_to_deduct:,}`"
        embed = discord.Embed(
            title=f"{YES_EMOTE} Streak Fixed",
            description=(
                f"**User:** {user.mention}\n"
                f"{EMOTE_STREAK} **New Streak:** {days(new_streak)}\n"
                f"{EMOTE_MAX_STREAK} **New Max Streak:** {days(new_max_streak)}{deducted}"
            ),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Mora(bot))
