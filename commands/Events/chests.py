import datetime
import logging
import random
import re
import time
from difflib import SequenceMatcher

import discord

from commands.Events.announcements import announcement_embed
from commands.Events.config import (
    EMOTE_BLANK,
    EMOTE_MAX_STREAK,
    EMOTE_STREAK,
    MONEYDANCE_EMOTE,
    MORA_CHEST_NAME,
    MORA_CHEST_TIMEOUT,
    MORA_EMOTE,
    NO_EMOTE,
    build_chest_description,
    profile_link_button,
)
from commands.Events.helperFunctions import (
    addMora,
    get_channel_chest_config,
    get_chest_bonus_chance,
    get_chest_counts,
    get_chest_progress,
    get_chest_streaks,
    get_chest_upgrades,
    get_express_daily_chests,
    get_guild_settings,
    upsert_chest_counts,
    upsert_chest_progress,
    upsert_chest_streaks,
)
from commands.Events.quests import update_quest

COOLDOWN = 5
ADD_SUMMON = """
    UPDATE minigame_progression
    SET minigame_summons = minigame_summons + 1, updated_at = CURRENT_TIMESTAMP
    WHERE gid = $1 AND uid = $2
"""


def today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def get_next_reset_unix() -> int:
    """Gives the time of the next midnight UTC, when chests and Sigils reset."""
    midnight = datetime.datetime.combine(
        today() + datetime.timedelta(days=1), datetime.time(), datetime.timezone.utc
    )
    return int(midnight.timestamp())


def days(count: int) -> str:
    return f"`{count}` day{'s' if count > 1 else ''}"


def flame(streak: int) -> str:
    return EMOTE_STREAK if streak > 1 else ""


def explanation(settings: dict) -> discord.Embed:
    """Gives the embed explaining daily chests under a server's settings."""
    reset = get_next_reset_unix()
    return discord.Embed(
        description=f"{build_chest_description(settings)}\n\n***Next reset at** <t:{reset}:f> (<t:{reset}:R>)*",
        color=discord.Color.random(),
    )


def is_effortful(content: str, last_content: str) -> bool:
    """Says whether a message counts towards a chest: long enough, not repetitive, not a near copy of the last."""
    content = content.strip()
    words = content.lower().split()
    if len(content) < 7 or (len(set(words)) <= 2 and len(words) > 5):
        return False
    if re.search(r"(.)\1{4,}", content):
        return False
    return (
        not last_content or SequenceMatcher(None, last_content, content).ratio() <= 0.9
    )


class UpgradeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Upgrade", style=discord.ButtonStyle.blurple, emoji="🔼")

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view.completed:
            return await interaction.response.defer()
        if view.clicks_remaining <= 0:
            return await interaction.response.send_message(
                "No upgrades left!", ephemeral=True
            )
        view.clicks_remaining -= 1
        upgraded = view.upgrade()
        embed = interaction.message.embeds[0]
        embed.title = f"{MORA_CHEST_NAME} 🎁 ({view.tier})"
        embed.description = (
            f"Upgrades left: `{view.clicks_remaining}`\n\n"
            f"**Tier:** {view.tier} Chest ({MORA_EMOTE} `{view.base()}`)\n"
            f"**Streak:** {flame(view.streak)} {days(view.streak)} (`+{view.streak_bonus()}` {MORA_EMOTE})\n"
            f"**Total:** {MORA_EMOTE} `{view.base() + view.streak_bonus()}`"
        )
        embed.color = discord.Color.gold() if upgraded else discord.Color.random()
        embed.set_thumbnail(url=view.icon())
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)


class ClaimButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Claim", style=discord.ButtonStyle.green, emoji="💰")

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view.completed:
            return await interaction.response.defer()
        view.completed = True
        view.stop()
        try:
            await view.claim(interaction)
        finally:
            view.cog.pending_chests.discard((view.user_id, view.guild_id))


class WhatIsItButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="What is this?", style=discord.ButtonStyle.secondary, emoji="❓"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=explanation(self.view.settings), ephemeral=True
        )


class MoraChestView(discord.ui.View):
    """A member's chest for the day: they may try to upgrade its tier, then claim it."""

    def __init__(self, cog, user_id, guild_id, streak, clicks_remaining, settings):
        super().__init__(timeout=MORA_CHEST_TIMEOUT)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.streak = streak
        self.clicks_remaining = clicks_remaining
        self.settings = settings
        self.tiers = settings["chests_tier_names"]
        self.tier = self.tiers[0]
        self.completed = False
        self.message = None
        self.update_buttons()

    def of_tier(self, setting: str, default):
        """Gives this tier's entry of a per-tier list in the settings, or a default when the list is short."""
        values = self.settings[setting]
        index = self.tiers.index(self.tier)
        return values[index] if index < len(values) else default

    def base(self) -> int:
        return self.of_tier("chests_tier_rewards", 0)

    def icon(self) -> str:
        return self.of_tier("chests_icons", "")

    def streak_bonus(self) -> int:
        return min(
            self.streak * self.settings["chests_streak_bonus"],
            self.settings["chests_max_streak_bonus"],
        )

    def upgrade(self) -> bool:
        """Moves the chest up one tier with that tier's chance; says whether it moved."""
        index = self.tiers.index(self.tier)
        if index == len(self.tiers) - 1:
            return False
        if random.random() >= float(self.of_tier("chests_upgrade_chances", 0)):
            return False
        self.tier = self.tiers[index + 1]
        return True

    def update_buttons(self) -> None:
        self.clear_items()
        if self.clicks_remaining > 0:
            self.add_item(UpgradeButton())
        self.add_item(ClaimButton())
        self.add_item(WhatIsItButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            f"{NO_EMOTE} This isn't your chest!", ephemeral=True
        )
        return False

    async def on_timeout(self):
        if self.completed or not self.message:
            return
        self.cog.pending_chests.discard((self.user_id, self.guild_id))
        try:
            await self.message.edit(
                content=f"<@{self.user_id}>",
                view=PersistentChestInfoView(),
                embed=discord.Embed(
                    description=f"⏳ <@{self.user_id}> did not claim their chest in time. You can earn a new chest tomorrow!",
                    color=discord.Color.light_grey(),
                ),
            )
        except discord.HTTPException:
            pass

    async def realm_bonus(self, pool) -> bool:
        """Gives the member a summon with their garden's chance; says whether it did."""
        chance = await get_chest_bonus_chance(pool, self.guild_id, self.user_id)
        if random.random() * 100 >= chance:
            return False
        await pool.execute(ADD_SUMMON, self.guild_id, self.user_id)
        return True

    def inventory(self, counts: list, best: int) -> str:
        """Gives the member's chests per tier, their total and both streaks, as shown after a claim."""
        emotes = self.settings["chests_emotes"]
        per_tier = "".join(
            f"{emotes[i] if i < len(emotes) else EMOTE_BLANK} `{counts[i]}` {EMOTE_BLANK}"
            for i in range(len(self.tiers))
        )
        return (
            f"{per_tier}\n📦 **Total:** `{sum(counts)}` {EMOTE_BLANK}"
            f"{EMOTE_STREAK} {days(self.streak)} {EMOTE_BLANK}"
            f"{EMOTE_MAX_STREAK} {days(best)}"
        )

    async def claim(self, interaction: discord.Interaction) -> None:
        """Pays the chest, shows what was earned and saves the streak and the count of this tier."""
        client, pool = interaction.client, interaction.client.pool
        bonus = await self.realm_bonus(pool)
        streaks = await get_chest_streaks(pool, self.guild_id, self.user_id)
        best = max(streaks.get("max_streak", 0), self.streak)
        counts = await get_chest_counts(pool, self.guild_id, self.user_id)
        counts += [0] * (len(self.tiers) - len(counts))
        counts[self.tiers.index(self.tier)] += 1
        await upsert_chest_streaks(
            pool, self.guild_id, self.user_id, self.streak, best, today().isoformat()
        )
        await upsert_chest_counts(pool, self.guild_id, self.user_id, counts)
        text, earned = await addMora(
            pool,
            self.user_id,
            self.base() + self.streak_bonus(),
            interaction.channel.id,
            self.guild_id,
            client,
        )
        self.cog.pending_chests.discard((self.user_id, self.guild_id))

        embed = discord.Embed(
            title=f"{MONEYDANCE_EMOTE} {self.tier} {MORA_CHEST_NAME.split(' ')[-1]} Claimed! {MONEYDANCE_EMOTE}",
            description=f"{MORA_EMOTE} `{text}` is **added** to your inventory!",
            color=discord.Color.green(),
        )
        breakdown = f"-# Base: {MORA_EMOTE} `{self.base()}` \n-# Streak Bonus: {MORA_EMOTE} `{self.streak_bonus()}` {flame(self.streak)}"
        if bonus:
            breakdown += "\n-# 🌹 **Realm Bonus:** +1 Summon!"
        embed.add_field(name="Reward Breakdown", value=breakdown, inline=True)
        reset = get_next_reset_unix()
        embed.add_field(
            name="Next Claim Available",
            value=f"-# <t:{reset}:f> (<t:{reset}:R>)",
            inline=True,
        )
        embed.add_field(
            name="Your Inventory", value=self.inventory(counts, best), inline=False
        )
        embed.set_thumbnail(url=self.icon())
        await interaction.response.edit_message(
            content=interaction.user.mention,
            embed=embed,
            view=PersistentChestInfoView(),
        )
        logging.info(
            f"{interaction.user.name} ({interaction.user.id}) has claimed a {self.tier} Chest in {interaction.guild.name} ({interaction.guild.id})"
        )
        await update_quest(
            self.user_id,
            self.guild_id,
            interaction.channel.id,
            {"collect_chests": 1, "earn_mora": earned},
            client,
        )
        await interaction.followup.send(embed=announcement_embed, ephemeral=True)


class PersistentChestInfoView(discord.ui.View):
    """The buttons left under a chest once it is claimed or wasted; they work after a restart."""

    def __init__(self):
        super().__init__(timeout=None)
        link = profile_link_button()
        link.row = 0
        self.add_item(link)

    @discord.ui.button(
        label="What is this?",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_chest_info_view",
        emoji="❓",
        row=0,
    )
    async def persistentChestInfoView(self, interaction: discord.Interaction, button):
        settings = await get_guild_settings(
            interaction.client.pool, interaction.guild_id
        )
        await interaction.response.send_message(
            embed=explanation(settings), ephemeral=True
        )

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_chest_delete",
        emoji="<a:delete:1372423674640207882>",
        row=0,
    )
    async def persistent_chest_delete(self, interaction: discord.Interaction, button):
        if str(interaction.user.id) in interaction.message.content:
            return await interaction.message.delete()
        await interaction.response.send_message(
            f"{NO_EMOTE} This isn't your chest!", ephemeral=True
        )


class DailyChestSystem:
    """Counts each member's effortful messages in chest channels and gives one chest a day."""

    def __init__(self, flags):
        self.flags = flags
        self.user_states = {}
        self.claimed_today = set()
        self.counting = set()

    async def state(self, pool, key: tuple) -> dict:
        """Gives a member's count for today, from memory, else the database, else a new one."""
        date = today().isoformat()
        state = self.user_states.get(key)
        if state and state["current_date"] == date:
            return state
        state = await get_chest_progress(pool, *key)
        if not state or state["current_date"] != date:
            state = {
                "message_count": 0,
                "last_time": 0,
                "last_content": "",
                "current_date": date,
                "threshold": None,
                "chest_triggered": False,
            }
        self.user_states[key] = state
        return state

    async def process_message(self, message, cog) -> None:
        """Counts a message in a chest channel towards its author's chest and sends the chest when it is due."""
        key = (message.guild.id, message.author.id)
        if key in self.claimed_today or key in self.counting:
            return
        self.counting.add(key)
        try:
            await self.count(message, cog, key)
        finally:
            self.counting.discard(key)

    async def count(self, message, cog, key: tuple) -> None:
        """Counts one message; a member's messages are counted one at a time, so a chest is sent once."""
        if (await self.flags.get(*key)).get("chest_disabled", False):
            return
        pool = cog.client.pool
        state = await self.state(pool, key)
        if state["chest_triggered"]:
            return self.claimed_today.add(key)
        now = time.time()
        if now - state["last_time"] < COOLDOWN:
            return
        if not is_effortful(message.content, state["last_content"]):
            return
        settings = await get_channel_chest_config(
            pool, message.guild.id, message.channel.id
        )
        if await get_express_daily_chests(pool, *key):
            state["threshold"] = 1
        elif state["threshold"] is None:
            needed = settings["chests_spawn_req"]
            state["threshold"] = random.randint(needed[0], needed[-1])
        state["message_count"] += 1
        state["last_time"] = now
        state["last_content"] = message.content
        due = state["message_count"] >= state["threshold"]
        if due and key[::-1] not in cog.pending_chests:
            state["chest_triggered"] = True
            self.claimed_today.add(key)
        await upsert_chest_progress(pool, *key, state)
        if state["chest_triggered"]:
            await self.trigger_chest(message, cog, settings)

    def invalidate_flag_cache(self, guild_id: int, user_id: int) -> None:
        self.flags.invalidate(guild_id, user_id)

    def reset_daily_states(self) -> None:
        """Forgets every member's count and claim, for the new day."""
        self.claimed_today.clear()
        self.user_states.clear()

    async def trigger_chest(self, message, cog, settings: dict) -> None:
        """Sends a member their chest for today, with their streak one longer when they claimed yesterday."""
        gid, uid = message.guild.id, message.author.id
        pool = cog.client.pool
        streaks = await get_chest_streaks(pool, gid, uid)
        last = streaks.get("last_claimed")
        if isinstance(last, str):
            last = datetime.date.fromisoformat(last[:10])
        claimed_yesterday = last and (today() - last).days == 1
        streak = streaks.get("streak", 0) + 1 if claimed_yesterday else 1
        clicks = await get_chest_upgrades(pool, gid, uid)
        view = MoraChestView(cog, uid, gid, streak, clicks, settings)
        state = self.user_states[(gid, uid)]
        embed = discord.Embed(
            title=f"{MORA_CHEST_NAME} Unlocked! <a:tada:1227425729654820885>",
            description=(
                f"**{view.tier} Chest** - *{MORA_EMOTE} `{view.base():,}`*\n"
                f"**Click to upgrade** (`{clicks}` chances left)\n"
                f"**Messages counted:** `{state['message_count']}`\n"
                f"**Streak:** {flame(streak)} {days(streak)} ({MORA_EMOTE} `+{view.streak_bonus()}`)"
            ),
            color=discord.Color.random(),
        )
        embed.set_thumbnail(url=view.icon())
        embed.set_footer(
            text=f"This chest spawned after you sent {state['threshold']} effortful messages in minigame channels today"
        )
        try:
            view.message = await message.channel.send(
                content=f"{message.author.mention}, claim this chest <t:{int(time.time()) + MORA_CHEST_TIMEOUT}:R>!",
                embed=embed,
                view=view,
            )
        except discord.Forbidden:
            return view.stop()
        logging.warning(
            f"{message.author.name} ({message.author.id}) is currently claiming a chest in {message.guild.name} ({message.guild.id})"
        )
        cog.pending_chests.add((uid, gid))


async def setup(bot) -> None:
    pass
