import discord
import datetime
import time
import random

from firebase_admin import db
from discord.ext import commands
try:
    from utils.commands import SlashCommand
except ImportError:
    class SlashCommand:
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return f"`/{self.name}`"

try:
    from commands.Events.config import YES_EMOTE, QUEST_DB
except ImportError as e:
    YES_EMOTE = "✅"
    QUEST_DB = "/Chat Minigames Quests"

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

async def update_quest(userID: int, guildID: int, channelID: int, quest_dict, client, refresh_only=False):
    ref = db.reference(f"{QUEST_DB}/{guildID}/{userID}")
    quest_data = ref.get() or {}
    now = time.time()
    total_xp = 0
    messages = []

    from commands.Events.helperFunctions import get_xp_boost
    xp_boost = await get_xp_boost(client.pool, guildID, userID)
    
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
                        
                        if xp_boost > 0:
                            xp_reward = int(xp_reward * (1 + xp_boost / 100))
                            
                        total_xp += xp_reward
                        messages.append(
                            f"{YES_EMOTE} **{QUEST_DESCRIPTIONS[q_type]}** ({duration}): "
                            f"`{quests[q_type]['goal']}` ‎ <:fastforward:1351972114433048719> ‎ `+{xp_reward}` XP"
                        )

            if len(quests) > 0:
                for q in quests:
                    if q not in completed:
                        all_completed = False
                        break

                if all_completed and "bonus_awarded" not in dur_data:
                    bonus = QUEST_BONUS_XP[duration]
                    if xp_boost > 0:
                        bonus = int(bonus * (1 + xp_boost / 100))
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
    pass