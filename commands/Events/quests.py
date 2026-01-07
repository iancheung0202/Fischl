import discord
import datetime
import time
import random

from firebase_admin import db
from discord.ext import commands

QUEST_TYPES = ["participate_minigames", "win_minigames", "win_1v1_minigames", "earn_mora", "gift_mora", "collect_chests", "earn_big_mora", "gift_mora_unique", "summon_minigame", "customize_profile", "purchase_items", "unlock_drop_packs"]
QUEST_GOAL_PRESETS = {
    "participate_minigames": {
        "daily": [4, 5],
        "weekly": [14, 16, 18],
        "monthly": [60, 70, 80]
    },
    "win_minigames": {
        "daily": [2, 3],
        "weekly": [8, 9, 10],
        "monthly": [25, 30, 35]
    },
    "win_1v1_minigames": {
        "daily": [1],
        "weekly": [4, 5, 6],
        "monthly": [10, 15, 20]
    },
    "earn_mora": {
        "daily": [15000, 17500, 20000],
        "weekly": [50000, 60000, 70000],
        "monthly": [250000, 275000, 300000]
    },
    "gift_mora": {
        "daily": [1000, 2000, 3000],
        "weekly": [10000, 15000, 20000],
        "monthly": [50000, 75000, 100000]
    },
    "collect_chests": {
        "daily": [1],
        "weekly": [5, 6, 7],
        "monthly": [20, 22, 24]
    },
    "earn_big_mora": {
        "daily": [1, 2],
        "weekly": [5, 7],
        "monthly": [20, 25]
    },
    "gift_mora_unique": {
        "daily": [2, 3],
        "weekly": [5, 7],
        "monthly": [15, 20]
    },
    "summon_minigame": {
        "daily": [1],
        "weekly": [3, 4, 5, 6],
        "monthly": [15, 20]
    },
    "customize_profile": {
        "daily": [1],
        "weekly": [2, 3],
        "monthly": [5, 6]
    },
    "purchase_items": {
        "monthly": [1, 2, 3]
    },
    "unlock_drop_packs": {
        "weekly": [1],
        "monthly": [2, 3]
    }
}
QUEST_DESCRIPTIONS = {
    "participate_minigames": "Participate in minigames",
    "win_minigames": "Win minigames",
    "win_1v1_minigames": "Win 1v1 minigames",
    "earn_mora": "Earn Mora",
    "gift_mora": "Gift Mora",
    "collect_chests": "Collect chests",
    "earn_big_mora": "Earn 10k+ Mora in one go",
    "gift_mora_unique": "Gift Mora to different users",
    "summon_minigame": "</summon:1382148690155802656> a minigame",
    "customize_profile": "</customize:1339721187953082544> your profile",
    "purchase_items": "Purchase </shop:1345883946105311383> items with </buy:1345883946105311382>",
    "unlock_drop_packs": "Unlock Mora Drop packs"
}
QUEST_XP_REWARDS = {
    "daily": 250,
    "weekly": 500,
    "monthly": 1500
}
QUEST_BONUS_XP = {
    "daily": 500,
    "weekly": 1500,
    "monthly": 4500
}

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

async def update_quest(userID: int, guildID: int, channelID: int, quest_dict, client, refresh_only=False):
    ref = db.reference(f"/Global User Quests/{userID}/{guildID}")
    quest_data = ref.get() or {}
    now = time.time()
    total_xp = 0
    messages = []
    
    for duration in ["daily", "weekly", "monthly"]:
        dur_data = quest_data.get(duration, {})
        end_time = dur_data.get("end_time", 0)
        
        if now >= end_time:
            if duration == "daily":
                new_end = get_next_daily_reset()
            elif duration == "weekly":
                new_end = get_next_weekly_reset()
            else:
                new_end = get_next_monthly_reset()
                
            dur_data = {
                "quests": generate_quests(duration),
                "end_time": new_end,
                "completed": {}
            }
            quest_data[duration] = dur_data
            ref.child(duration).set(dur_data)
        
        if not(refresh_only):
            quests = dur_data.get("quests", {})
            completed = dur_data.get("completed", {})
            updated = False
            all_completed = True

            for q_type, amount in quest_dict.items():
                if q_type in quests and q_type not in completed:
                    before = quests[q_type]["current"]
                    
                    if q_type == "gift_mora_unique":
                        gifted = quests[q_type].get("gifted_users", [])
                        if str(amount) not in [str(x) for x in gifted]:
                            gifted.append(str(amount))
                            quests[q_type]["gifted_users"] = gifted
                            quests[q_type]["current"] = len(gifted)
                            updated = True
                    else:
                        quests[q_type]["current"] += amount
                        updated = True
                    
                    after = quests[q_type]["current"]

                    if after >= quests[q_type]["goal"]:
                        completed[q_type] = True
                        xp_reward = QUEST_XP_REWARDS[duration]
                        total_xp += xp_reward
                        messages.append(
                            f"<:yes:1036811164891480194> **{QUEST_DESCRIPTIONS[q_type]}** ({duration}): "
                            f"`{quests[q_type]['goal']}` ‎ <:fastforward:1351972114433048719> ‎ `+{xp_reward}` XP"
                        )

            if len(quests) > 0:
                for q in quests:
                    if q not in completed:
                        all_completed = False
                        break

                if all_completed and "bonus_awarded" not in dur_data:
                    bonus = QUEST_BONUS_XP[duration]
                    total_xp += bonus
                    dur_data["bonus_awarded"] = True
                    messages.append(
                        f"<a:legacy:1345876714240213073> *Completed all {duration} quests* ‎ <:fastforward:1351972114433048719> ‎ `+{bonus}` XP"
                    )
                    updated = True

            if updated:
                dur_data["quests"] = quests
                dur_data["completed"] = completed
                ref.child(duration).set(dur_data)

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
                client=client
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
    pass