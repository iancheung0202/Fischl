import asyncio
import random
import time

import discord

from commands.Events.config import MONEYDANCE_EMOTE, MORA_EMOTE
from commands.Events.helperFunctions import (
    addMora,
    ensure_progression_user,
    get_channel_mora_multiplier,
    get_pinned_item,
)
from commands.Events.quests import update_quest
from commands.Events.trackData import get_current_track, is_elite_active

OWNER = 692254240290242601
ADD_XP = """
    UPDATE minigame_progression
    SET xp = COALESCE(xp, 0) + $3, updated_at = CURRENT_TIMESTAMP
    WHERE gid = $1 AND uid = $2
    RETURNING xp
"""
BONUS_TIER = """
    UPDATE minigame_progression SET bonus_tier = (xp - $3) / 1500
    WHERE gid = $1 AND uid = $2
"""


async def add_xp(user_id, guild_id, xp_amount, client):
    """Adds XP in one statement, so two gains at once both count; gives (tier, old XP, new XP)."""
    pool = client.pool
    await ensure_progression_user(pool, guild_id, user_id)
    new_xp = await pool.fetchval(ADD_XP, guild_id, user_id, xp_amount)
    track = get_current_track()
    tier = max(
        (step["tier"] for step in track if new_xp >= step["cumulative_xp"]), default=0
    )
    if tier == 31:
        await pool.execute(BONUS_TIER, guild_id, user_id, track[-1]["cumulative_xp"])
    return (tier, new_xp - xp_amount, new_xp)


async def user_and_title(uid: int, gid: int, pool) -> str:
    """Gives a member's mention with their pinned title, and the Elite emote when they have Elite."""
    title = await get_pinned_item(pool, uid, gid)
    elite = MONEYDANCE_EMOTE if await is_elite_active(pool, uid, gid) else ""
    if not title:
        return f"<@{uid}> {elite}"
    if str(title).isdigit():
        title = f"<@&{title}>"
    return f"<@{uid}> **({title})** {elite}"


async def prize(client, channel, low: int, high: int) -> int:
    """Gives a random amount between two bounds, times the channel's Mora multiplier."""
    multiplier = await get_channel_mora_multiplier(client.pool, channel.id)
    return int(random.randint(low, high) * multiplier)


async def earn(client, channel, uid: int, amount: int) -> tuple:
    """Pays a member in this channel; gives the amount as shown and as counted."""
    return await addMora(client.pool, uid, amount, channel.id, channel.guild.id, client)


async def count(
    client,
    channel,
    uid: int,
    earned=None,
    since=None,
    won=True,
    joined=True,
    duel=False,
) -> None:
    """Counts a minigame in a member's quests: taking part, a win (of a duel), the Mora earned, a win inside 5 seconds."""
    quest = {}
    if joined:
        quest["participate_minigames"] = 1
    if won:
        quest["win_minigames"] = 1
    if won and duel:
        quest["win_1v1_minigames"] = 1
    if earned is not None:
        quest["earn_mora"] = earned
    if won and since is not None and time.time() - since < 5:
        quest["win_minigames_under_5s"] = 1
    await update_quest(uid, channel.guild.id, channel.id, quest, client)


async def took_part(client, channel, members, but=()) -> None:
    """Counts a minigame as played for each of the members, leaving out those in `but`."""
    for uid in members:
        if uid not in but:
            await count(client, channel, uid, won=False)


async def delete_soon(message) -> None:
    """Deletes a message three seconds from now."""
    await asyncio.sleep(3)
    try:
        await message.delete()
    except discord.NotFound:
        pass


async def report_crash(client, channel, reason) -> None:
    """Tells the channel an event crashed and sends the owner a link to that message."""
    embed = discord.Embed(description=f"Event crashed: `{reason}`")
    embed.set_footer(text="Error has been logged and developer has been notified.")
    message = await channel.send(embed=embed)
    owner = await client.fetch_user(OWNER)
    await owner.send(f"Event crashed: {message.jump_url}")


def coins(amount) -> str:
    """Gives an amount as the Mora emote and the number in a code span."""
    return f"{MORA_EMOTE} `{amount}`"


async def setup(bot) -> None:
    pass
