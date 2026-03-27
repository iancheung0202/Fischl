import discord
import asyncio
import time
import datetime
import asyncpg

from typing import Optional
from firebase_admin import db


MORA_EMOTE = "<:MORA:1364030973611610205>"

async def get_total_mora(pool: asyncpg.Pool, uid: int) -> int:
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COALESCE(SUM(count), 0) FROM minigame_mora WHERE uid = $1",
            uid
        )
    return result or 0

async def get_guild_mora(pool: asyncpg.Pool, uid: int, gid: int) -> int:
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COALESCE(SUM(count), 0) FROM minigame_mora WHERE uid = $1 AND gid = $2",
            uid, gid
        )
    return result or 0

async def get_global_leaderboard(pool: asyncpg.Pool, limit: int = 50) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT uid, SUM(count) as total
            FROM minigame_mora
            GROUP BY uid
            ORDER BY total DESC
            LIMIT $1
        """, limit)
    return [(row['uid'], row['total']) for row in rows]

async def get_guild_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = 50) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT uid, SUM(count) as total
            FROM minigame_mora
            WHERE gid = $1
            GROUP BY uid
            ORDER BY total DESC
            LIMIT $2
        """, gid, limit)
    return [(row['uid'], row['total']) for row in rows]

async def get_users_by_mora_threshold(pool: asyncpg.Pool, gid: int, threshold: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT uid, SUM(count) as total
            FROM minigame_mora
            WHERE gid = $1
            GROUP BY uid
            HAVING SUM(count) >= $2
            ORDER BY total DESC
        """, gid, threshold)
    return [(row['uid'], row['total']) for row in rows]

async def get_user_mora_history(
    pool: asyncpg.Pool,
    uid: int,
    gid: int,
    limit: Optional[int] = None
) -> list:
    query = """
        SELECT timestamp, count
        FROM minigame_mora
        WHERE uid = $1 AND gid = $2
        ORDER BY timestamp ASC
    """
    params = [uid, gid]

    if limit:
        query += " LIMIT $3"
        params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [(row['timestamp'], row['count']) for row in rows]


async def get_mora_stats(pool: asyncpg.Pool, uid: int, gid: int) -> dict:
    async with pool.acquire() as conn:
        # Get total mora
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(count), 0) FROM minigame_mora WHERE uid = $1 AND gid = $2",
            uid, gid
        ) or 0

        # Earliest timestamp
        first_ts = await conn.fetchval(
            "SELECT MIN(timestamp) FROM minigame_mora WHERE uid = $1 AND gid = $2",
            uid, gid
        )
        
        # Daily breakdown
        daily_stats = await conn.fetch("""
            SELECT 
                DATE(TO_TIMESTAMP(timestamp)) as date,
                SUM(count) as daily_total,
                COUNT(*) as entries
            FROM minigame_mora
            WHERE uid = $1 AND gid = $2
            GROUP BY DATE(TO_TIMESTAMP(timestamp))
            ORDER BY daily_total DESC
        """, uid, gid)
        
        # Number of entries (mora earnings)
        entry_count = await conn.fetchval(
            "SELECT COUNT(*) FROM minigame_mora WHERE uid = $1 AND gid = $2 AND count > 0",
            uid, gid
        )
        
        # Largest single earning
        largest_single = await conn.fetchval(
            "SELECT MAX(count) FROM minigame_mora WHERE uid = $1 AND gid = $2 AND count > 0",
            uid, gid
        )
    
    largest_daily = daily_stats[0]['daily_total'] if daily_stats else 0
    largest_daily_date = int(time.mktime(daily_stats[0]['date'].timetuple())) if daily_stats else None
    
    first_played = first_ts or int(time.time())
    total_days = (datetime.datetime.now(datetime.timezone.utc).date() - 
                  datetime.datetime.fromtimestamp(first_played, datetime.timezone.utc).date()).days + 1
    days_active = len(daily_stats)
    average_daily = total / total_days if total_days > 0 else 0
    
    return {
        'first_played': first_played,
        'days_active': days_active,
        'total_days': total_days,
        'average_daily': int(average_daily),
        'largest_daily': largest_daily,
        'largest_daily_date': largest_daily_date,
        'entry_count': entry_count or 0,
        'largest_single': largest_single or 0,
        'daily_breakdown': daily_stats
    }

async def addMora(pool: asyncpg.Pool, userID: int, addedMora: int, channelID: int, guildID: int, client=None):
    baseMora = addedMora 
    boost = 0
    
    if addedMora > 0:
        stats_ref = db.reference(f"/User Events Stats/{guildID}/{userID}")
        stats = stats_ref.get() or {}
        boost = stats.get("mora_boost", 0)
        addedMora = int(addedMora * (1 + boost / 100))

    timestamp = int(time.time())
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO minigame_mora (uid, gid, cid, timestamp, count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (gid, uid, cid, timestamp)
            DO UPDATE SET count = $5
        """, userID, guildID, channelID, timestamp, addedMora)

    asyncio.create_task(delayed_check_milestones(pool, userID, guildID, channelID, client))

    if addedMora > 10000 and client:
        from commands.Events.quests import update_quest
        await update_quest(userID, guildID, channelID, {"earn_big_mora": 1}, client)

    if baseMora > 0 and boost > 0:
        return f"{baseMora} + {addedMora - baseMora} ({boost}% boost)", addedMora
    return abs(addedMora), addedMora


async def subtractGuildMora(pool: asyncpg.Pool, userID: int, subtractMora: int, channelID: int, guildID: int) -> int | bool:
    total_available = await get_guild_mora(pool, userID, guildID)

    if subtractMora > total_available:
        return False

    timestamp = int(time.time())
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO minigame_mora (uid, gid, cid, timestamp, count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (gid, uid, cid, timestamp)
            DO UPDATE SET count = $5
        """, userID, guildID, channelID, timestamp, -subtractMora)

    return total_available - subtractMora

def get_minigame_list(channel_id):
    """Get list of minigames enabled in a channel."""
    ref = db.reference(f"/Chat Minigames System/{channel_id}")
    data = ref.get() or {}
    return data.get("events", [])

async def delayed_check_milestones(pool: asyncpg.Pool, userID, guildID, channelID, client):
    """Delay milestone check to allow database consistency."""
    await asyncio.sleep(1)
    await check_milestones(pool, userID, guildID, channelID, client)

    
async def check_milestones(pool: asyncpg.Pool, user_id, guild_id, channel_id, client):
    """Check and award milestones for a user when mora threshold is reached."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        channel_id = None
    
    total_mora = await get_guild_mora(pool, user_id, guild_id)

    milestones_ref = db.reference(f"/Chat Minigames Rewards/{guild_id}/milestones")
    milestones = milestones_ref.get() or []
    
    inventory_ref = db.reference("/User Events Inventory")
    inventories = inventory_ref.get()
    user_items = []
    if inventories:
        for key, val in inventories.items():
            if val["User ID"] == user_id:
                user_items = [item[0] for item in val.get("Items", []) 
                              if len(item) > 3 and item[3] == guild_id]
                break
    
    for milestone in milestones:
        if not isinstance(milestone, list) or len(milestone) < 3:
            continue
        description = milestone[0]  # index 0
        reward = milestone[1]  # index 1
        threshold = milestone[2]  # index 2
        
        if reward in user_items or total_mora < threshold:
            continue
        
        item_data = [
            reward, 
            description,
            0,  # cost is 0 because it's a milestone
            guild_id,
            int(time.time())
        ]
        
        found = False
        if inventories:
            for key, val in inventories.items():
                if val["User ID"] == user_id:
                    items = val.get("Items", [])
                    items.append(item_data)
                    inventory_ref.child(key).update({"Items": items})
                    found = True
                    break
        
        if not found:
            data = {"User ID": user_id, "Items": [item_data]}
            inventory_ref.push().set(data)
        
        if isinstance(reward, int) or str(reward).isdigit():
            guild = client.get_guild(guild_id)
            if guild:
                member = await guild.fetch_member(user_id)
                role = guild.get_role(int(reward))
                if member and role:
                    try:
                        await member.add_roles(role)
                    except:
                        pass
        
        channel = client.get_channel(channel_id)
        if channel:
            if isinstance(reward, int) or str(reward).isdigit():
                reward_display = f"<@&{reward}>"
            else:
                reward_display = reward
            
            from commands.Events.event import userAndTitle

            await channel.send(
                embed=discord.Embed(
                    title="🏆 Milestone Achieved!",
                    description=(
                        f"Congratulations, {userAndTitle(user_id, guild_id)}! \n"
                        f"You've reached {MORA_EMOTE} `{threshold}` and earned **{reward_display}**\n"
                    ),
                    color=discord.Color.gold()
                )
            )

class PersistentXPQuestInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="What is this?",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_xp_quest_info_view",
        emoji="<:PinkConfused:1204614149628498010>",
    )
    async def persistentXPQuestInfoView(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="What Are XP & Quests? <:AlbedoQuestion:1191574408544923799>",
            color=discord.Color.random()
        )
        embed.add_field(
            name="<:NingguangStonks:1265470501707321344> Quests ➜ XP",
            value="-# Complete daily, weekly, and monthly quests to **earn XP** just by playing, winning, or gifting!",
            inline=True
        )
        embed.add_field(
            name="<:CharlotteHeart:1191594476263702528> XP ➜ Rewards",
            value="-# Earning XP moves you up the Progression Track to **unlock Mora boosts, chest upgrades, animated backgrounds**, and more!",
            inline=True
        )
        embed.add_field(
            name="<:MelonBread_KeqingNote:1342924552392671254> Track in One Place",
            value="-# Use </mora:1339721187953082543> to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
            inline=True
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_info_delete",
        emoji="<a:delete:1372423674640207882>",
    )
    async def persistent_info_delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content and str(interaction.user.id) not in interaction.message.embeds[0].description:
            await interaction.response.send_message("❌ This isn't your notification!", ephemeral=True)
        else:
            await interaction.message.delete()
        
class TierRewardsView(discord.ui.View):
    def __init__(self, free_embed=discord.Embed(title="This button has timed out.", color=discord.Color.red()), elite_embed=discord.Embed(color=0xFF0000)):
        super().__init__(timeout=None)
        self.free_embed = free_embed
        self.elite_embed = elite_embed

    @discord.ui.button(
        label="View Earned Tiers",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_tier_rewards_view",
    )
    async def show_tier_rewards(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.elite_embed.title is not None:
            await interaction.response.send_message(embeds=[self.free_embed, self.elite_embed], ephemeral=True)
        elif self.free_embed.title is not None:
            await interaction.response.send_message(embeds=[self.free_embed], ephemeral=True)
        else:
            await interaction.response.send_message("You did not earn any tiers from this XP gain.", ephemeral=True)
            
    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_xp_quest_info_view_new",
        emoji="<:PinkConfused:1204614149628498010>",
    )
    async def persistentXPQuestInfoViewNew(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="What Are XP & Quests? <:AlbedoQuestion:1191574408544923799>",
            color=discord.Color.random()
        )
        embed.add_field(
            name="<:NingguangStonks:1265470501707321344> Quests ➜ XP",
            value="-# Complete daily, weekly, and monthly quests to **earn XP** just by playing, winning, or gifting!",
            inline=True
        )
        embed.add_field(
            name="<:CharlotteHeart:1191594476263702528> XP ➜ Rewards",
            value="-# Earning XP moves you up the Progression Track to **unlock Mora boosts, chest upgrades, animated backgrounds**, and more!",
            inline=True
        )
        embed.add_field(
            name="<:MelonBread_KeqingNote:1342924552392671254> Track in One Place",
            value="-# Use </mora:1339721187953082543> to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
            inline=True
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_info_delete_new",
        emoji="<a:delete:1372423674640207882>",
    )
    async def persistent_info_delete_new(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content and str(interaction.user.id) not in interaction.message.embeds[0].description:
            await interaction.response.send_message("❌ This isn't your notification!", ephemeral=True)
        else:
            await interaction.message.delete()
            
async def setup(bot) -> None:
    pass