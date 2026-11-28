"""Daily, weekly and monthly quests: handing them out, counting progress and paying XP."""

import asyncio
import datetime
import json
import random
import time
import weakref

import asyncpg
import discord
from discord.ext import commands

from commands.Events.config import (
    QUEST_BONUS_XP,
    QUEST_DESCRIPTIONS,
    QUEST_GOAL_PRESETS,
    QUEST_TYPES,
    QUEST_XP_REWARDS,
    YES_EMOTE,
)
from commands.Events.helperFunctions import TierRewardsView, get_xp_boost

FORWARD = "<:fastforward:1351972114433048719>"
ROWS = (
    "SELECT cycle_type, quest_name, current_progress, goal_progress, completed, bonus_awarded, extra_data, end_time "
    "FROM minigame_quests WHERE guild_id = $1 AND user_id = $2"
)
CLEAR = "DELETE FROM minigame_quests WHERE guild_id = $1 AND user_id = $2 AND cycle_type = $3"
ADD = """
    INSERT INTO minigame_quests
        (guild_id, user_id, cycle_type, end_time, quest_name,
         current_progress, goal_progress, completed, bonus_awarded, extra_data)
    VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, FALSE, NULL)
"""
SAVE = """
    UPDATE minigame_quests
    SET current_progress = $1, completed = $2, extra_data = $3
    WHERE guild_id = $4 AND user_id = $5 AND cycle_type = $6 AND quest_name = $7
"""
PAID = "UPDATE minigame_quests SET bonus_awarded = TRUE WHERE guild_id = $1 AND user_id = $2 AND cycle_type = $3"


def get_next_daily_reset():
    now = datetime.datetime.now(datetime.timezone.utc)
    next_day = now + datetime.timedelta(days=1)
    return int(next_day.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def get_next_weekly_reset():
    now = datetime.datetime.now(datetime.timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = now + datetime.timedelta(days=days_until_sunday)
    return int(
        next_sunday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )


def get_next_monthly_reset():
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    return int(
        next_month.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )


def generate_quests(duration: str) -> dict:
    num_quests = 2 if duration == "daily" else 3
    available_types = [
        q for q in QUEST_TYPES if duration in QUEST_GOAL_PRESETS.get(q, {})
    ]
    selected = random.sample(available_types, num_quests)
    quests = {}
    for q in selected:
        goal = random.choice(QUEST_GOAL_PRESETS[q][duration])
        quests[q] = {"current": 0, "goal": goal}
    return quests


async def ensure_quests_table(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS minigame_quests (
                guild_id VARCHAR(64) NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                cycle_type VARCHAR(10) NOT NULL,
                end_time BIGINT NOT NULL,
                quest_name VARCHAR(64) NOT NULL,
                current_progress INT DEFAULT 0,
                goal_progress INT NOT NULL,
                completed BOOLEAN DEFAULT FALSE,
                bonus_awarded BOOLEAN DEFAULT FALSE,
                extra_data TEXT,
                PRIMARY KEY (guild_id, user_id, cycle_type, quest_name)
            )
        """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quests_user ON minigame_quests(user_id)"
        )


async def get_quest_data(pool: asyncpg.Pool, guildID: int, userID: int) -> dict:
    """Gives the member's saved quests by cycle; `update_quest` is what renews them."""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT cycle_type, end_time, quest_name, current_progress, goal_progress, completed, bonus_awarded, extra_data "
            "FROM minigame_quests WHERE guild_id = $1 AND user_id = $2",
            str(guildID),
            str(userID),
        )

    quest_data = {}
    for r in rows:
        duration = r["cycle_type"]
        dur_data = quest_data.setdefault(
            duration,
            {
                "quests": {},
                "completed": {},
                "end_time": r["end_time"],
                "bonus_awarded": False,
            },
        )
        q_entry = {"current": r["current_progress"], "goal": r["goal_progress"]}
        if r["extra_data"]:
            try:
                q_entry.update(json.loads(r["extra_data"]))
            except (TypeError, ValueError):
                pass
        dur_data["quests"][r["quest_name"]] = q_entry
        if r["completed"]:
            dur_data["completed"][r["quest_name"]] = True
        if r["bonus_awarded"]:
            dur_data["bonus_awarded"] = True

    return quest_data


RESETS = {
    "daily": get_next_daily_reset,
    "weekly": get_next_weekly_reset,
    "monthly": get_next_monthly_reset,
}


async def renew(pool, member, duration):
    """Replaces a cycle's quests with new ones and gives them as rows."""
    end, quests = RESETS[duration](), generate_quests(duration)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(CLEAR, *member, duration)
            for name, quest in quests.items():
                await conn.execute(
                    ADD, *member, duration, end, name, quest["current"], quest["goal"]
                )
    return [
        {
            "quest_name": name,
            "current_progress": quest["current"],
            "goal_progress": quest["goal"],
            "completed": False,
            "bonus_awarded": False,
            "extra_data": None,
        }
        for name, quest in quests.items()
    ]


def extra_of(row):
    """Gives what a quest row saved beside its count, such as who was gifted."""
    try:
        return json.loads(row["extra_data"]) if row["extra_data"] else {}
    except (TypeError, ValueError):
        return {}


def count(quest, kind, amount):
    """Adds the amount to a quest and says whether it changed."""
    if kind != "gift_mora_unique":
        quest["current"] += amount
        return True
    # Here the amount is the member who was gifted; each one counts once.
    gifted = quest["extra_data"].get("gifted_users", [])
    if str(amount) in [str(user) for user in gifted]:
        return False
    gifted.append(str(amount))
    quest["extra_data"]["gifted_users"] = gifted
    quest["current"] = len(gifted)
    return True


# One lock per member, so two messages at once cannot count from the same saved rows.
LOCKS = weakref.WeakValueDictionary()


def boosted(xp, boost):
    """Raises the XP by the member's boost in percent."""
    return int(xp * (1 + boost / 100)) if boost > 0 else xp


async def advance(pool, member, duration, rows, quest_dict, boost):
    """Counts progress in one cycle; gives the XP earned and the lines saying why."""
    quests = {
        row["quest_name"]: {
            "current": row["current_progress"],
            "goal": row["goal_progress"],
            "extra_data": extra_of(row),
        }
        for row in rows
    }
    completed = {row["quest_name"] for row in rows if row["completed"]}
    paid = any(row["bonus_awarded"] for row in rows)
    changed, xp, lines = set(), 0, []

    for kind, amount in quest_dict.items():
        if kind not in quests or kind in completed:
            continue
        if count(quests[kind], kind, amount):
            changed.add(kind)
        if quests[kind]["current"] >= quests[kind]["goal"]:
            completed.add(kind)
            changed.add(kind)
            reward = boosted(QUEST_XP_REWARDS[duration], boost)
            xp += reward
            lines.append(
                f"{YES_EMOTE} **{QUEST_DESCRIPTIONS[kind]}** ({duration}): "
                f"`{quests[kind]['goal']}` ‎ {FORWARD} ‎ `+{reward}` XP"
            )

    if changed:
        async with pool.acquire() as conn:
            for name in changed:
                extra = quests[name]["extra_data"]
                await conn.execute(
                    SAVE,
                    quests[name]["current"],
                    name in completed,
                    json.dumps(extra) if extra else None,
                    *member,
                    duration,
                    name,
                )

    if quests and not paid and all(name in completed for name in quests):
        bonus = boosted(QUEST_BONUS_XP[duration], boost)
        xp += bonus
        lines.append(
            f"<a:legacy:1345876714240213073> *Completed all {duration} quests* ‎ {FORWARD} ‎ `+{bonus}` XP"
        )
        async with pool.acquire() as conn:
            await conn.execute(PAID, *member, duration)
    return xp, lines


async def announce(userID, guildID, channelID, total_xp, lines, client):
    """Pays the XP and tells the member which quests were completed."""
    from commands.Events.games.common import add_xp
    from commands.Events.trackData import check_tier_rewards

    tier, old_xp, new_xp = await add_xp(userID, guildID, total_xp, client)
    channel = client.get_channel(channelID)
    if not channel:
        return
    free_embed, elite_embed = await check_tier_rewards(
        guild_id=guildID,
        user_id=userID,
        old_xp=old_xp,
        new_xp=new_xp,
        channel=channel,
        client=client,
        pool=client.pool,
    )
    desc = "\n".join(lines) + f"\n\n**Total XP earned:** `{total_xp}` XP"
    await channel.send(
        content=f"<@{userID}>",
        embed=discord.Embed(
            title="🎉 Quests Completed!", description=desc, color=0x22D65E
        ),
        view=TierRewardsView(free_embed, elite_embed),
    )


async def update_quest(
    userID: int, guildID: int, channelID: int, quest_dict, client, refresh_only=False
):
    """Renews quests that ran out, then counts `quest_dict` ({quest: amount}) toward them."""
    pool = client.pool
    member = (str(guildID), str(userID))
    boost = await get_xp_boost(pool, guildID, userID)
    total_xp, lines = 0, []
    async with LOCKS.setdefault(member, asyncio.Lock()):
        now = time.time()
        saved = {}
        for row in await pool.fetch(ROWS, *member):
            saved.setdefault(row["cycle_type"], []).append(row)

        for duration in RESETS:
            rows = saved.get(duration, [])
            if now >= (rows[0]["end_time"] if rows else 0):
                rows = await renew(pool, member, duration)
            if refresh_only:
                continue
            xp, said = await advance(pool, member, duration, rows, quest_dict, boost)
            total_xp += xp
            lines += said

    if total_xp > 0:
        await announce(userID, guildID, channelID, total_xp, lines, client)


async def setup(bot: commands.Bot) -> None:
    await ensure_quests_table(bot.pool)
