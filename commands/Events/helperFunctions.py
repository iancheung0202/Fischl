import discord
import asyncio
import time
import datetime
import asyncpg

from typing import Optional
from firebase_admin import db
from utils.commands import SlashCommand


MORA_EMOTE = "<:MORA:1364030973611610205>"

# Progression helper functions

async def ensure_progression_user(pool: asyncpg.Pool, gid: int, uid: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO minigame_progression 
            (gid, uid, kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten,
             xp, prestige, bonus_tier, mora_boost, chest_upgrades, gift_tax, minigame_summons)
            VALUES ($1, $2, 0, 0, 0, 0, 0, 0, 0, 0, 4, NULL, 0)
            ON CONFLICT (gid, uid) DO NOTHING
        """, gid, uid)

async def get_progression_data(pool: asyncpg.Pool, gid: int, uid: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xp, prestige, bonus_tier FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    if not row:
        return {"xp": 0, "prestige": 0, "bonus_tier": 0}
    return dict(row)

async def get_user_xp(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT xp FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return val or 0

async def get_kingdom_buildings(pool: asyncpg.Pool, gid: int, uid: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    if not row:
        return {"schloss": 0, "theater": 0, "bibliothek": 0, "garten": 0}
    return {
        "schloss": row['kingdom_schloss'],
        "theater": row['kingdom_theater'],
        "bibliothek": row['kingdom_bibliothek'],
        "garten": row['kingdom_garten']
    }

async def get_building_level(pool: asyncpg.Pool, gid: int, uid: int, building_key: str) -> int:
    col_mapping = {
        "schloss": "kingdom_schloss",
        "theater": "kingdom_theater",
        "bibliothek": "kingdom_bibliothek",
        "garten": "kingdom_garten"
    }
    col_name = col_mapping.get(building_key)
    if not col_name:
        return 0
    
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            f"SELECT {col_name} FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return val or 0

async def increment_building_level(pool: asyncpg.Pool, gid: int, uid: int, building_key: str) -> int:
    col_mapping = {
        "schloss": "kingdom_schloss",
        "theater": "kingdom_theater",
        "bibliothek": "kingdom_bibliothek",
        "garten": "kingdom_garten"
    }
    col_name = col_mapping.get(building_key)
    if not col_name:
        return 0
    
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        new_val = await conn.fetchval(
            f"UPDATE minigame_progression SET {col_name} = {col_name} + 1, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2 RETURNING {col_name}",
            gid, uid
        )
    return new_val or 0

async def get_user_stats(pool: asyncpg.Pool, gid: int, uid: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mora_boost, chest_upgrades, gift_tax, minigame_summons FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    if not row:
        return {"mora_boost": 0, "chest_upgrades": 4, "gift_tax": None, "minigame_summons": 0}
    return dict(row)

async def get_mora_boost(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT mora_boost FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return val or 0

async def update_mora_boost(pool: asyncpg.Pool, gid: int, uid: int, value: int) -> None:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_progression SET mora_boost = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
            gid, uid, value
        )

async def get_chest_upgrades(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT chest_upgrades FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return val if val is not None else 4

async def get_chest_bonus_chance(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    garten_level = await get_building_level(pool, gid, uid, "garten")
    return min(50, garten_level)

async def get_xp_boost(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    bib_level = await get_building_level(pool, gid, uid, "bibliothek")
    return min(50, bib_level)

async def get_encore_chance(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    theater_level = await get_building_level(pool, gid, uid, "theater")
    return min(50, theater_level)

async def get_guild_kingdom_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, 
                       (kingdom_schloss + kingdom_theater + kingdom_bibliothek + kingdom_garten) as total_level
                FROM minigame_progression
                WHERE gid = $1 
                ORDER BY total_level DESC
                LIMIT $2
            """, gid, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, 
                       (kingdom_schloss + kingdom_theater + kingdom_bibliothek + kingdom_garten) as total_level
                FROM minigame_progression
                WHERE gid = $1 
                ORDER BY total_level DESC
            """, gid)
    return [(row['uid'], row['total_level']) for row in rows]

# Mora helper functions

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

async def get_global_leaderboard(pool: asyncpg.Pool, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, SUM(count) as total
                FROM minigame_mora
                GROUP BY uid
                ORDER BY total DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, SUM(count) as total
                FROM minigame_mora
                GROUP BY uid
                ORDER BY total DESC
            """)
    return [(row['uid'], row['total']) for row in rows]

async def get_guild_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, SUM(count) as total
                FROM minigame_mora
                WHERE gid = $1
                GROUP BY uid
                ORDER BY total DESC
                LIMIT $2
            """, gid, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, SUM(count) as total
                FROM minigame_mora
                WHERE gid = $1
                GROUP BY uid
                ORDER BY total DESC
            """, gid)
    return [(row['uid'], row['total']) for row in rows]

async def get_global_items_leaderboard(pool: asyncpg.Pool, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as item_count
                FROM minigame_inventory
                GROUP BY uid
                ORDER BY item_count DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as item_count
                FROM minigame_inventory
                GROUP BY uid
                ORDER BY item_count DESC
            """)
    return [(row['uid'], row['item_count']) for row in rows]

async def get_global_kingdom_leaderboard(pool: asyncpg.Pool, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, 
                       SUM(kingdom_schloss + kingdom_theater + kingdom_bibliothek + kingdom_garten) as total_level
                FROM minigame_progression
                GROUP BY uid
                ORDER BY total_level DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, 
                       SUM(kingdom_schloss + kingdom_theater + kingdom_bibliothek + kingdom_garten) as total_level
                FROM minigame_progression
                GROUP BY uid
                ORDER BY total_level DESC
            """)
    return [(row['uid'], row['total_level']) for row in rows]

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
        boost = await get_mora_boost(pool, guildID, userID)
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

# Inventory helper functions

async def get_user_inventory(pool: asyncpg.Pool, uid: int, gid: int, exclude_cost: int = None) -> list:
    if exclude_cost is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT title, description, cost, gid, timestamp, pinned FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND cost != $3 ORDER BY timestamp ASC",
                uid, gid, exclude_cost
            )
    else:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT title, description, cost, gid, timestamp, pinned FROM minigame_inventory WHERE uid = $1 AND gid = $2 ORDER BY timestamp ASC",
                uid, gid
            )
    return [(row['title'], row['description'], row['cost'], row['gid'], row['timestamp'], row['pinned']) for row in rows]

async def count_user_inventory(pool: asyncpg.Pool, uid: int, gid: int, exclude_cost: int = None) -> int:
    if exclude_cost is not None:
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT COUNT(*) FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND cost != $3",
                uid, gid, exclude_cost
            )
    else:
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT COUNT(*) FROM minigame_inventory WHERE uid = $1 AND gid = $2",
                uid, gid
            )
    return val or 0

async def add_inventory_item(pool: asyncpg.Pool, uid: int, gid: int, title, description: str, cost: int, timestamp: int, pinned: bool = False) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO minigame_inventory (uid, gid, title, description, cost, timestamp, pinned) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            uid, gid, str(title), description, cost, timestamp, pinned
        )

async def get_pinned_item(pool: asyncpg.Pool, uid: int, gid: int) -> Optional[str]:
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT title FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND pinned = true LIMIT 1",
            uid, gid
        )
    return val

async def unpin_all_items(pool: asyncpg.Pool, uid: int, gid: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_inventory SET pinned = false WHERE uid = $1 AND gid = $2",
            uid, gid
        )

async def pin_item(pool: asyncpg.Pool, uid: int, gid: int, title) -> bool:
    await unpin_all_items(pool, uid, gid)
    
    async with pool.acquire() as conn:
        # Pin all items with this title
        result = await conn.execute(
            "UPDATE minigame_inventory SET pinned = true WHERE uid = $1 AND gid = $2 AND title = $3",
            uid, gid, str(title)
        )
        return result != "UPDATE 0"

async def get_guild_items_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as item_count
                FROM minigame_inventory
                WHERE gid = $1
                GROUP BY uid
                ORDER BY item_count DESC
                LIMIT $2
            """, gid, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as item_count
                FROM minigame_inventory
                WHERE gid = $1
                GROUP BY uid
                ORDER BY item_count DESC
            """, gid)
    return [(row['uid'], row['item_count']) for row in rows]

# Other leaderboard helper functions

async def get_global_minigame_wins_leaderboard(pool: asyncpg.Pool, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as win_count
                FROM minigame_mora
                WHERE count > 0
                GROUP BY uid
                ORDER BY win_count DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as win_count
                FROM minigame_mora
                WHERE count > 0
                GROUP BY uid
                ORDER BY win_count DESC
            """)
    return [(row['uid'], row['win_count']) for row in rows]

async def get_guild_minigame_wins_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as win_count
                FROM minigame_mora
                WHERE gid = $1 AND count > 0
                GROUP BY uid
                ORDER BY win_count DESC
                LIMIT $2
            """, gid, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, COUNT(*) as win_count
                FROM minigame_mora
                WHERE gid = $1 AND count > 0
                GROUP BY uid
                ORDER BY win_count DESC
            """, gid)
    return [(row['uid'], row['win_count']) for row in rows]

async def get_global_active_days_leaderboard(pool: asyncpg.Pool, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, COUNT(DISTINCT DATE(TO_TIMESTAMP(timestamp))) as active_days
                FROM minigame_mora
                WHERE count > 0
                GROUP BY uid
                ORDER BY active_days DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, COUNT(DISTINCT DATE(TO_TIMESTAMP(timestamp))) as active_days
                FROM minigame_mora
                WHERE count > 0
                GROUP BY uid
                ORDER BY active_days DESC
            """)
    return [(row['uid'], row['active_days']) for row in rows]

async def get_guild_active_days_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, COUNT(DISTINCT DATE(TO_TIMESTAMP(timestamp))) as active_days
                FROM minigame_mora
                WHERE gid = $1 AND count > 0
                GROUP BY uid
                ORDER BY active_days DESC
                LIMIT $2
            """, gid, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, COUNT(DISTINCT DATE(TO_TIMESTAMP(timestamp))) as active_days
                FROM minigame_mora
                WHERE gid = $1 AND count > 0
                GROUP BY uid
                ORDER BY active_days DESC
            """, gid)
    return [(row['uid'], row['active_days']) for row in rows]

# Prestige leaderboard functions

async def get_global_prestige_leaderboard(pool: asyncpg.Pool, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, SUM(prestige) as total_prestige
                FROM minigame_progression
                GROUP BY uid
                ORDER BY total_prestige DESC
                LIMIT $1
            """, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, SUM(prestige) as total_prestige
                FROM minigame_progression
                GROUP BY uid
                ORDER BY total_prestige DESC
            """)
    return [(row['uid'], row['total_prestige']) for row in rows]

async def get_guild_prestige_leaderboard(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
    async with pool.acquire() as conn:
        if limit:
            rows = await conn.fetch("""
                SELECT uid, prestige as total_prestige
                FROM minigame_progression
                WHERE gid = $1
                ORDER BY prestige DESC
                LIMIT $2
            """, gid, limit)
        else:
            rows = await conn.fetch("""
                SELECT uid, prestige as total_prestige
                FROM minigame_progression
                WHERE gid = $1
                ORDER BY prestige DESC
            """, gid)
    return [(row['uid'], row['total_prestige']) for row in rows]

# Misc helper functions

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
    
    user_inventory = await get_user_inventory(pool, user_id, guild_id)
    user_items = [item[0] for item in user_inventory]  # item[0] is title
    
    for milestone in milestones:
        if not isinstance(milestone, list) or len(milestone) < 3:
            continue
        description = milestone[0]  # index 0
        reward = milestone[1]  # index 1
        threshold = milestone[2]  # index 2
        
        if reward in user_items or total_mora < threshold:
            continue
        
        # Award the milestone by adding it to inventory (cost = 0 for milestones)
        await add_inventory_item(pool, user_id, guild_id, reward, description, 0, int(time.time()), pinned=False)
        
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
            value=f"-# Use {SlashCommand('mora')} to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
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
            value=f"-# Use {SlashCommand('mora')} to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
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