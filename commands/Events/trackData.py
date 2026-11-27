"""The season track: paying a tier's reward and saying what was unlocked."""

import os
import time
from collections import namedtuple
from functools import partial

import discord

from commands.Events.config import (
    CURRENCY_NAME,
    MORA_EMOTE,
    PRESTIGE_EMOTE,
    REWARD_TYPES,
)
from commands.Events.dropPack import create_drop_pack
from commands.Events.helperFunctions import (
    add_background_to_cosmetics,
    add_frame_to_cosmetics,
    add_title_to_cosmetics,
    get_chest_upgrades,
    get_domain_discount,
    get_mora_boost,
    get_shop_discount,
    get_user_stats,
    update_domain_discount,
    update_express_daily_chests,
    update_mora_boost,
    update_shop_discount,
    upsert_cosmetics,
)
from commands.Events.seasons import get_current_season
from utils.commands import SlashCommand

BONUS_XP = 2500  # XP between two bonus drop packs once the track is finished
NO_STATS = {"gift_tax": None}
CLAIMED = (
    "SELECT claimed_tiers FROM minigame_elite WHERE user_id = $1 AND guild_id = $2"
)
CLAIM = "UPDATE minigame_elite SET claimed_tiers = array_append(claimed_tiers, $1) WHERE user_id = $2 AND guild_id = $3"
EXPIRES = "SELECT expires_at FROM minigame_elite WHERE user_id = $1 AND guild_id = $2"
PRESTIGE = "UPDATE minigame_progression SET prestige = prestige + 1, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2"
CHESTS = "UPDATE minigame_progression SET chest_upgrades = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2"
GIFTING = "UPDATE minigame_progression SET gift_tax = 30, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2"
TAX = "UPDATE minigame_progression SET gift_tax = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2"
SUMMONS = "UPDATE minigame_progression SET minigame_summons = minigame_summons + $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2 RETURNING minigame_summons"

# One reward being paid: who gets it, the reward text of the track, and where it is announced.
Grant = namedtuple("Grant", "pool guild user text tier channel elite client stats kind")


def get_current_track():
    """Gives the tiers of the running season, or nothing between seasons."""
    season = get_current_season()
    return season.track_data if season else []


def member(grant):
    """Gives what the stored-data helpers ask for first: the pool, the server and the member."""
    return (grant.pool, grant.guild, grant.user)


def head(grant):
    """Gives the start of an elite reward's title."""
    return "Elite Reward: " if grant.elite else ""


def part(grant):
    """Gives the second part of the reward text, the file or name after the bar."""
    return grant.text.split("|")[1].strip()


async def drop_pack(grant):
    """Drops a pack in the channel and counts it toward the member's quests."""
    bonus = grant.tier == "Bonus"
    message = await create_drop_pack(
        grant.guild,
        grant.user,
        grant.channel,
        grant.elite,
        bonus,
        grant.tier,
        grant.client,
    )
    if grant.client:
        from commands.Events.quests import update_quest  # quests imports this file

        await update_quest(
            grant.user,
            grant.guild,
            grant.channel.id,
            {"unlock_drop_packs": 1},
            grant.client,
        )
    if bonus:
        title = f"{'Elite ' if grant.elite else ''}New Bonus Drop Pack"
        description = "**Bonus:** "
    else:
        title = f"{head(grant)}New Drop Pack"
        description = f"**Tier `{grant.tier}`:** "
    return (
        title,
        description + f"You can claim your drop pack [here]({message.jump_url})!",
    )


async def animated_background(grant):
    """Unlocks the animated inventory background named in the reward."""
    name = f"{part(grant).split('/')[2].split('.')[0].strip()}"
    await add_background_to_cosmetics(*member(grant), name)
    return (
        f"{head(grant)} Animated Inventory Background Unlocked 🖼️",
        f"**Tier `{grant.tier}`:** You have unlocked **{name}**! Use {SlashCommand('customize')} to equip it in this server!",
    )


async def custom_gif_background(grant):
    """Lets the member upload their own GIF background."""
    await upsert_cosmetics(
        grant.pool,
        grant.guild,
        grant.user,
        selected_animated_background_unlocked=True,
    )
    return (
        f"{head(grant)} Custom GIF Background Unlocked 🖼️",
        f"**Tier `{grant.tier}`:** You can now upload and use a custom animated GIF background with {SlashCommand('customize')}!",
    )


async def font_unlock(grant):
    """Lets the member pick a card font."""
    await upsert_cosmetics(*member(grant), selected_font_unlocked=True)
    return (
        f"{head(grant)} Custom Card Font Unlocked 🔤",
        f"**Tier `{grant.tier}`:** You can now select an Elite Track font preset with {SlashCommand('customize')}!",
    )


async def server_title(grant):
    """Unlocks the server title named in the reward."""
    parts = grant.text.split("|")
    name = parts[1].strip() if len(parts) > 1 else grant.text
    stamp = str(int(time.time() * 1000))
    await add_title_to_cosmetics(*member(grant), stamp, name)
    return (
        f"{head(grant)} Server Title Unlocked 📍",
        f"**Tier `{grant.tier}`:** You have unlocked **{name}**! Use {SlashCommand('customize')} to equip it in this server!",
    )


async def frame(grant):
    """Unlocks the profile frame named in the reward."""
    name = os.path.basename(part(grant))
    await add_frame_to_cosmetics(*member(grant), name)
    return (
        f"{head(grant)} {'Static' if 'static' in grant.kind else '**Animated**'} Profile Frame Unlocked 👤",
        f"**Tier `{grant.tier}`:** You have unlocked **{name.split('.')[0]}**! Use {SlashCommand('customize')} to equip it in this server!",
    )


async def accent_color(grant):
    """Lets the member set their own accent color."""
    await upsert_cosmetics(*member(grant), embed_color=True)
    return (
        f"{head(grant)} Custom Accent Color Unlocked 🎨",
        f"**Tier `{grant.tier}`:** You can have a custom accent color on your inventory and profile card! Use {SlashCommand('customize')} to edit your favorite color!",
    )


async def custom_title(grant):
    """Lets the member write their own title."""
    await upsert_cosmetics(*member(grant), selected_custom_title_unlocked=True)
    return (
        f"{head(grant)} Custom Title Unlocked 📍",
        f"**Tier `{grant.tier}`:** You can now set a custom text title with {SlashCommand('customize')}!",
    )


async def express_daily_chests(grant):
    """Makes the member's daily chest spawn after one message."""
    await update_express_daily_chests(*member(grant), True)
    return (
        f"{head(grant)} Express Daily Chests ⚡",
        f"**Tier `{grant.tier}`:** Your daily chest will now spawn after **1 effortful message** in minigame channels.",
    )


async def prestige(grant):
    """Adds one prestige for finishing a track."""
    await grant.pool.execute(PRESTIGE, grant.guild, grant.user)
    return (
        f"{head(grant)} Prestige +1 {PRESTIGE_EMOTE}",
        f"You have earned `+1` prestige for **reaching the end of the {'elite' if grant.elite else 'free'} track**! Use {SlashCommand('mora')} to view your prestige count!",
    )


async def mora_boost(grant):
    """Raises the member's mora boost by 5%, or by 67% for the big reward."""
    amount = 5 if grant.kind == "mora_boost" else 67
    boost = await get_mora_boost(*member(grant)) + amount
    await update_mora_boost(*member(grant), boost)
    return (
        f"{head(grant)}{CURRENCY_NAME} Gain Boost +{amount}% {MORA_EMOTE}",
        f"**Tier `{grant.tier}`:** Your {CURRENCY_NAME} gain from all sources will now be **increased by `{boost}%`**!",
    )


async def chest_upgrade(grant):
    """Adds 1 daily chest upgrade chance, or 69 for the big reward."""
    amount = 1 if grant.kind == "chest_upgrade" else 69
    total = await get_chest_upgrades(*member(grant)) + amount
    await grant.pool.execute(CHESTS, grant.guild, grant.user, total)
    return (
        f"{head(grant)}+{amount} Chest Upgrades :arrow_up_small:",
        f"**Tier `{grant.tier}`:** Your daily chest now has a total of **`{total}` upgrade chances**!",
    )


async def unlock_gifting(grant):
    """Lets the member gift at a 30% tax, unless they already can."""
    if grant.stats.get("gift_tax") is not None:
        return (None, None)
    await grant.pool.execute(GIFTING, grant.guild, grant.user)
    return (
        f"{CURRENCY_NAME} Gifting Unlocked! :gift:",
        f"**Tier `{grant.tier}`:** You can now {SlashCommand('gift')} {CURRENCY_NAME} to others with an initial tax rate of `30%`!",
    )


async def gift_tax(grant):
    """Lowers the member's gift tax by 5%, starting from 30%."""
    now = grant.stats.get("gift_tax")
    tax = max(0, (30 if now is None else now) - 5)
    await grant.pool.execute(TAX, grant.guild, grant.user, tax)
    return (
        f"{head(grant)}Gift Tax Reduced -5% :chart_with_downwards_trend:",
        f"**Tier `{grant.tier}`:** Your gifting tax rate is now **`{tax}%`**! Use {SlashCommand('gift')} to send some love!",
    )


async def minigame_summon(grant):
    """Adds the summons named at the start of the reward."""
    amount = int(grant.text.split()[0])
    total = await grant.pool.fetchval(SUMMONS, grant.guild, grant.user, amount)
    return (
        f"{head(grant)}+{amount} Minigame Summons 🧲",
        f"**Tier `{grant.tier}`:** You have a total of **{total} minigame summons** available! Use {SlashCommand('summon')} to immediately start a minigame in a channel!",
    )


async def shop_discount(grant):
    """Raises the member's shop discount by 10%, up to 50%."""
    now = await get_shop_discount(*member(grant))
    discount = min(50, now + 10)
    await update_shop_discount(*member(grant), discount)
    return (
        f"{head(grant)} Shop Discount +10% 🏷️",
        f"**Tier `{grant.tier}`:** Your shop purchases now get a **{discount}% discount**.",
    )


async def domain_discount(grant):
    """Raises the member's kingdom discount by 10%, up to 50%."""
    now = await get_domain_discount(*member(grant))
    discount = min(50, now + 10)
    await update_domain_discount(*member(grant), discount)
    return (
        f"{head(grant)} Domain Discount +10% 🏰",
        f"**Tier `{grant.tier}`:** Your domain upgrades now get a **{discount}% discount**.",
    )


PAYERS = {
    "drop_pack": drop_pack,
    "animated_background": animated_background,
    "custom_gif_background": custom_gif_background,
    "font_unlock": font_unlock,
    "title": server_title,
    "static_frame": frame,
    "animated_frame": frame,
    "accent_color": accent_color,
    "custom_title": custom_title,
    "express_daily_chests": express_daily_chests,
    "prestige": prestige,
    "mora_boost": mora_boost,
    "mora_boost_67": mora_boost,
    "chest_upgrade": chest_upgrade,
    "chest_upgrade_69": chest_upgrade,
    "unlock_gifting": unlock_gifting,
    "gift_tax": gift_tax,
    "minigame_summon": minigame_summon,
    "minigame_summon_30": minigame_summon,
    "shop_discount": shop_discount,
    "domain_discount": domain_discount,
}


async def claim(pool, guild_id, user_id, tier):
    """Marks an elite tier as paid; False when it already was."""
    async with pool.acquire() as conn:
        if tier in (await conn.fetchval(CLAIMED, user_id, guild_id) or []):
            return False
        if tier != "Bonus":
            await conn.execute(CLAIM, tier, user_id, guild_id)
    return True


async def grant_reward(
    guild_id, user_id, reward_str, tier, channel, is_elite=False, client=None, pool=None
):
    """Pays one reward and gives the (title, description) announcing it, or (None, None)."""
    if is_elite and pool and not await claim(pool, guild_id, user_id, tier):
        return (None, None)
    kind = REWARD_TYPES.get(reward_str.split("|")[0].strip(), "other")
    stats = await get_user_stats(pool, guild_id, user_id) if pool else NO_STATS
    if kind not in PAYERS:
        return (None, None)
    who = (pool, guild_id, user_id)
    return await PAYERS[kind](
        Grant(*who, reward_str, tier, channel, is_elite, client, stats, kind)
    )


def payer(guild_id, user_id, channel, client, pool):
    """Gives `grant_reward` with the member and channel filled in."""
    return partial(
        grant_reward, guild_id, user_id, channel=channel, client=client, pool=pool
    )


def add(embed, announced):
    """Adds the reward to the embed, unless nothing was paid."""
    title, description = announced
    if title is not None and description is not None:
        embed.add_field(name=title, value=f"-# {description}", inline=False)


async def check_tier_rewards(
    guild_id, user_id, old_xp, new_xp, channel, client=None, pool=None
):
    """Pays every tier passed between the two XP values; gives the free and elite embeds."""
    track = get_current_track()
    pay = payer(guild_id, user_id, channel, client, pool)
    embed = discord.Embed(color=0xFFD700)
    elite_embed = discord.Embed(color=0xFA0ADD)
    for tier in track:
        if not old_xp < tier["cumulative_xp"] <= new_xp:
            continue
        add(embed, await pay(tier["free"], tier["tier"]))
        if await is_elite_active(pool, user_id, guild_id):
            add(elite_embed, await pay(tier["elite"], tier["tier"], is_elite=True))

    count = len(embed.fields)
    if count > 0:
        embed.title = "🏆 Tiers Achieved"
        embed.description = f"<@{user_id}>, you have reached **`{count}`** new tier{'s' if count > 1 else ''} and unlocked the following reward{'s' if count > 1 else ''}!"
    if len(elite_embed.fields) > 0:
        elite_embed.title = "🏆 Elite Tiers Achieved"

    end = track[-1]["cumulative_xp"]
    if new_xp > end:
        before = max((old_xp - end) // BONUS_XP, 0)
        earned = (new_xp - end) // BONUS_XP - before
        for _ in range(earned):
            await pay("Drop Pack", "Bonus")
            if await is_elite_active(pool, user_id, guild_id):
                await pay("Drop Pack", "Bonus", is_elite=True)
    return (embed, elite_embed)


async def grant_elite_rewards_up_to_tier(
    guild_id, user_id, channel, max_xp, client=None, pool=None
):
    """Pays the elite rewards of every unpaid tier up to the XP; gives a line for each."""
    lines = []
    track = get_current_track()
    pay = payer(guild_id, user_id, channel, client, pool)
    claimed = await pool.fetchval(CLAIMED, user_id, guild_id) or []
    for tier in track:
        if tier["cumulative_xp"] <= max_xp and tier["tier"] not in claimed:
            await pay(tier["elite"], tier["tier"], is_elite=True)
            lines.append(
                f"-# - **Tier {tier['tier']}:** {tier['elite'].split('|')[0].strip()}"
            )

    end = track[-1]["cumulative_xp"]
    if max_xp > end:
        packs = (max_xp - end) // BONUS_XP
        for _ in range(packs):
            await pay("Drop Pack", "Bonus", is_elite=True)
        lines.append(
            f"-# - `x{packs}` Elite Bonus Drop Pack (dropped at {channel.mention})"
        )
    return lines


async def is_elite_active(pool, user_id, guild_id):
    """Says whether the member's Elite Track is paid for right now."""
    try:
        expires = await pool.fetchval(EXPIRES, user_id, guild_id)
        return expires is not None and time.time() < expires
    except Exception:
        return False


async def setup(bot):
    pass
