import discord
import datetime
import time
import random
import json
import asyncpg

from discord.ext import commands

try:
    from commands.Events.config import YES_EMOTE
except ImportError as e:
    YES_EMOTE = "✅"

from commands.Events.config import QUEST_TYPES, QUEST_GOAL_PRESETS, QUEST_DESCRIPTIONS, QUEST_XP_REWARDS, QUEST_BONUS_XP

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
    return int(next_sunday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

def get_next_monthly_reset():
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.month == 12:
        next_month = now.replace(year=now.year+1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month+1, day=1)
    return int(next_month.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

def generate_quests(duration: str) -> dict:
    num_quests = 2 if duration == "daily" else 3
    available_types = [q for q in QUEST_TYPES if duration in QUEST_GOAL_PRESETS.get(q, {})]
    selected = random.sample(available_types, num_quests)
    quests = {}
    for q in selected:
        goal = random.choice(QUEST_GOAL_PRESETS[q][duration])
        quests[q] = {"current": 0, "goal": goal}
    return quests

async def ensure_quests_table(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
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
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_quests_user ON minigame_quests(user_id)")

async def get_quest_data(pool: asyncpg.Pool, guildID: int, userID: int) -> dict:
    # Read-only. Does NOT perform resets (that's update_quest(..., refresh_only=True))
    await ensure_quests_table(pool)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT cycle_type, end_time, quest_name, current_progress, goal_progress, completed, bonus_awarded, extra_data "
            "FROM minigame_quests WHERE guild_id = $1 AND user_id = $2",
            str(guildID), str(userID)
        )

    quest_data = {}
    for r in rows:
        duration = r["cycle_type"]
        dur_data = quest_data.setdefault(duration, {"quests": {}, "completed": {}, "end_time": r["end_time"], "bonus_awarded": False})
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

async def update_quest(userID: int, guildID: int, channelID: int, quest_dict, client, refresh_only=False):
    pool = client.pool
    await ensure_quests_table(pool)

    gid_s, uid_s = str(guildID), str(userID)
    now = time.time()
    total_xp = 0
    messages = []

    from commands.Events.helperFunctions import get_xp_boost
    xp_boost = await get_xp_boost(client.pool, guildID, userID)

    for duration in ["daily", "weekly", "monthly"]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT quest_name, current_progress, goal_progress, completed, bonus_awarded, extra_data, end_time "
                "FROM minigame_quests WHERE guild_id = $1 AND user_id = $2 AND cycle_type = $3",
                gid_s, uid_s, duration
            )

        end_time = rows[0]["end_time"] if rows else 0

        if now >= end_time:
            if duration == "daily":
                new_end = get_next_daily_reset()
            elif duration == "weekly":
                new_end = get_next_weekly_reset()
            else:
                new_end = get_next_monthly_reset()

            new_quests = generate_quests(duration)

            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "DELETE FROM minigame_quests WHERE guild_id = $1 AND user_id = $2 AND cycle_type = $3",
                        gid_s, uid_s, duration
                    )
                    for q_name, q in new_quests.items():
                        await conn.execute(
                            """
                            INSERT INTO minigame_quests
                                (guild_id, user_id, cycle_type, end_time, quest_name,
                                 current_progress, goal_progress, completed, bonus_awarded, extra_data)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, FALSE, NULL)
                            """,
                            gid_s, uid_s, duration, new_end, q_name, q["current"], q["goal"]
                        )
                rows = await conn.fetch(
                    "SELECT quest_name, current_progress, goal_progress, completed, bonus_awarded, extra_data, end_time "
                    "FROM minigame_quests WHERE guild_id = $1 AND user_id = $2 AND cycle_type = $3",
                    gid_s, uid_s, duration
                )

        if refresh_only:
            continue

        quests = {}
        completed = {}
        bonus_already_awarded = False
        for r in rows:
            extra = {}
            if r["extra_data"]:
                try:
                    extra = json.loads(r["extra_data"])
                except (TypeError, ValueError):
                    extra = {}
            quests[r["quest_name"]] = {"current": r["current_progress"], "goal": r["goal_progress"], "extra_data": extra}
            if r["completed"]:
                completed[r["quest_name"]] = True
            if r["bonus_awarded"]:
                bonus_already_awarded = True

        updated_names = set()

        for q_type, amount in quest_dict.items():
            if q_type in quests and q_type not in completed:
                if q_type == "gift_mora_unique":
                    extra = quests[q_type]["extra_data"]
                    gifted = extra.get("gifted_users", [])
                    if str(amount) not in [str(x) for x in gifted]:
                        gifted.append(str(amount))
                        extra["gifted_users"] = gifted
                        quests[q_type]["extra_data"] = extra
                        quests[q_type]["current"] = len(gifted)
                        updated_names.add(q_type)
                else:
                    quests[q_type]["current"] += amount
                    updated_names.add(q_type)

                after = quests[q_type]["current"]

                if after >= quests[q_type]["goal"]:
                    completed[q_type] = True
                    updated_names.add(q_type)
                    xp_reward = QUEST_XP_REWARDS[duration]

                    if xp_boost > 0:
                        xp_reward = int(xp_reward * (1 + xp_boost / 100))

                    total_xp += xp_reward
                    messages.append(
                        f"{YES_EMOTE} **{QUEST_DESCRIPTIONS[q_type]}** ({duration}): "
                        f"`{quests[q_type]['goal']}` ‎ <:fastforward:1351972114433048719> ‎ `+{xp_reward}` XP"
                    )

        if updated_names:
            async with pool.acquire() as conn:
                for q_name in updated_names:
                    extra = quests[q_name]["extra_data"]
                    await conn.execute(
                        """
                        UPDATE minigame_quests
                        SET current_progress = $1, completed = $2, extra_data = $3
                        WHERE guild_id = $4 AND user_id = $5 AND cycle_type = $6 AND quest_name = $7
                        """,
                        quests[q_name]["current"],
                        q_name in completed,
                        json.dumps(extra) if extra else None,
                        gid_s, uid_s, duration, q_name
                    )

        if len(quests) > 0:
            all_completed = True
            for q in quests:
                if q not in completed:
                    all_completed = False
                    break

            if all_completed and not bonus_already_awarded:
                bonus = QUEST_BONUS_XP[duration]
                if xp_boost > 0:
                    bonus = int(bonus * (1 + xp_boost / 100))
                total_xp += bonus
                messages.append(
                    f"<a:legacy:1345876714240213073> *Completed all {duration} quests* ‎ <:fastforward:1351972114433048719> ‎ `+{bonus}` XP"
                )
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE minigame_quests SET bonus_awarded = TRUE WHERE guild_id = $1 AND user_id = $2 AND cycle_type = $3",
                        gid_s, uid_s, duration
                    )

    if total_xp > 0:
        from commands.Events.event import add_xp
        from commands.Events.trackData import check_tier_rewards
        from commands.Events.helperFunctions import TierRewardsView

        tier, old_xp, new_xp = await add_xp(userID, guildID, total_xp, client)
        channel = client.get_channel(channelID)
        if channel:
            free_embed, elite_embed = await check_tier_rewards(
                guild_id=guildID,
                user_id=userID,
                old_xp=old_xp,
                new_xp=new_xp,
                channel=channel,
                client=client,
                pool=client.pool
            )
            desc = "\n".join(messages) + f"\n\n**Total XP earned:** `{total_xp}` XP"
            await channel.send(
                content=f"<@{userID}>",
                embed=discord.Embed(
                    title="🎉 Quests Completed!",
                    description=desc,
                    color=0x22d65e
                ),
                view=TierRewardsView(free_embed, elite_embed)
            )
        
async def setup(bot: commands.Bot) -> None:
    await ensure_quests_table(bot.pool)