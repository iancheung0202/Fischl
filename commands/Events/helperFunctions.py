import discord
import asyncio
import time
import datetime
import math
import asyncpg

from typing import Optional
from firebase_admin import db

from commands.Events.config import MORA_EMOTE, NO_EMOTE, MORA_CHEST_UPGRADE_TIMES, CONFUSED_EMOTE, XP_QUEST_EMBED

# Progression helper functions

async def ensure_progression_user(pool: asyncpg.Pool, gid: int, uid: int) -> None:
    async with pool.acquire() as conn:
        for col in ["chest_disabled BOOLEAN DEFAULT FALSE", "minigame_disabled BOOLEAN DEFAULT FALSE"]:
            await conn.execute(f"ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS {col}")
        await conn.execute("ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS shop_discount INTEGER DEFAULT 0")
        await conn.execute("ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS domain_discount INTEGER DEFAULT 0")
        await conn.execute("ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS express_daily_chests BOOLEAN DEFAULT FALSE")
        await conn.execute("""
            INSERT INTO minigame_progression 
            (gid, uid, kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten,
             xp, prestige, bonus_tier, mora_boost, chest_upgrades, gift_tax, minigame_summons,
             shop_discount, domain_discount, express_daily_chests)
            VALUES ($1, $2, 0, 0, 0, 0, 0, 0, 0, 0, 4, NULL, 0, 0, 0, FALSE)
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
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mora_boost, chest_upgrades, gift_tax, minigame_summons, shop_discount, domain_discount, express_daily_chests FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    if not row:
        return {"mora_boost": 0, "chest_upgrades": 4, "gift_tax": None, "minigame_summons": 0, "shop_discount": 0, "domain_discount": 0, "express_daily_chests": False}
    return dict(row)

def apply_discount(amount: int, discount_percent: int) -> int:
    discount_percent = max(0, min(50, int(discount_percent or 0)))
    discounted = amount * (100 - discount_percent) / 100
    return max(0, math.ceil(discounted))

async def get_shop_discount(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT shop_discount FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return min(50, val or 0)

async def update_shop_discount(pool: asyncpg.Pool, gid: int, uid: int, value: int) -> None:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_progression SET shop_discount = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
            gid, uid, min(50, max(0, value))
        )

async def get_domain_discount(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT domain_discount FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return min(50, val or 0)

async def update_domain_discount(pool: asyncpg.Pool, gid: int, uid: int, value: int) -> None:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_progression SET domain_discount = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
            gid, uid, min(50, max(0, value))
        )

async def get_express_daily_chests(pool: asyncpg.Pool, gid: int, uid: int) -> bool:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT express_daily_chests FROM minigame_progression WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return bool(val)

async def update_express_daily_chests(pool: asyncpg.Pool, gid: int, uid: int, value: bool) -> None:
    await ensure_progression_user(pool, gid, uid)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_progression SET express_daily_chests = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
            gid, uid, bool(value)
        )

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
    return val if val is not None else MORA_CHEST_UPGRADE_TIMES

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

async def addMora(pool: asyncpg.Pool, userID: int, addedMora: int, channelID: int, guildID: int, client=None, bypass_boost=False):
    baseMora = addedMora 
    boost = 0
    
    if addedMora > 0 and not bypass_boost:
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
                "SELECT title, description, cost, gid, timestamp, pinned, link FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND cost != $3 ORDER BY timestamp ASC",
                uid, gid, exclude_cost
            )
    else:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT title, description, cost, gid, timestamp, pinned, link FROM minigame_inventory WHERE uid = $1 AND gid = $2 ORDER BY timestamp ASC",
                uid, gid
            )
    return [(row['title'], row['description'], row['cost'], row['gid'], row['timestamp'], row['pinned'], row['link']) for row in rows]

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

async def add_inventory_item(pool: asyncpg.Pool, uid: int, gid: int, title, description: str, cost: int, timestamp: int, pinned: bool = False, link: str = None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO minigame_inventory (uid, gid, title, description, cost, timestamp, pinned, link) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            uid, gid, str(title), description, cost, timestamp, pinned, link
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

async def ensure_minigame_settings_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_settings (
                channel_id          BIGINT PRIMARY KEY,
                mora_multiplier     NUMERIC(4,2) DEFAULT 1.00,
                minigames_enabled   BOOLEAN DEFAULT TRUE,
                minigames_list      TEXT[] DEFAULT '{}',
                minigames_frequency INTEGER DEFAULT 50,
                chests_enabled      BOOLEAN DEFAULT FALSE
            )
        """)
        await conn.execute("ALTER TABLE minigame_settings ADD COLUMN IF NOT EXISTS mora_multiplier NUMERIC(4,2) DEFAULT 1.00")
        await conn.execute("ALTER TABLE minigame_settings ADD COLUMN IF NOT EXISTS chests_enabled BOOLEAN DEFAULT FALSE")

async def ensure_minigame_guild_chest_settings_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_guild_chest_settings (
                gid                         BIGINT PRIMARY KEY,
                chests_base_upgrade_chances INTEGER DEFAULT 4,
                chests_tier_names           TEXT[] DEFAULT ARRAY['Common','Exquisite','Precious','Luxurious'],
                chests_tier_rewards         INTEGER[] DEFAULT ARRAY[2500,7500,15000,30000],
                chests_upgrade_chances      NUMERIC(5,2)[] DEFAULT ARRAY[0.30,0.15,0.20],
                chests_streak_bonus         INTEGER DEFAULT 100,
                chests_max_streak_bonus     INTEGER DEFAULT 10000,
                chests_spawn_req            INTEGER[] DEFAULT ARRAY[4,6],
                chests_emotes               TEXT[] DEFAULT ARRAY['<a:common:1371641883121680465>','<a:exquisite:1371641856344985620>','<a:precious:1371641871452995689>','<a:luxurious:1371641841338023976>'],
                chests_icons                TEXT[] DEFAULT ARRAY['https://i.imgur.com/2kOfLSC.png','https://i.imgur.com/DBPQSAu.png','https://i.imgur.com/zxOlrCo.png','https://i.imgur.com/5nWwRdc.png']
            )
        """)
        await conn.execute("ALTER TABLE minigame_guild_chest_settings ADD COLUMN IF NOT EXISTS chests_emotes TEXT[] DEFAULT ARRAY['<a:common:1371641883121680465>','<a:exquisite:1371641856344985620>','<a:precious:1371641871452995689>','<a:luxurious:1371641841338023976>']")
        await conn.execute("ALTER TABLE minigame_guild_chest_settings ADD COLUMN IF NOT EXISTS chests_icons TEXT[] DEFAULT ARRAY['https://i.imgur.com/2kOfLSC.png','https://i.imgur.com/DBPQSAu.png','https://i.imgur.com/zxOlrCo.png','https://i.imgur.com/5nWwRdc.png']")

async def ensure_minigame_progression_columns(pool):
    async with pool.acquire() as conn:
        for col in ["chest_disabled BOOLEAN DEFAULT FALSE", "minigame_disabled BOOLEAN DEFAULT FALSE"]:
            await conn.execute(f"ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS {col}")

async def ensure_minigame_elite_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_elite (
                user_id             BIGINT NOT NULL,
                guild_id            BIGINT NOT NULL,
                server_name         TEXT DEFAULT '',
                expires_at          BIGINT NOT NULL,
                activated_at        BIGINT DEFAULT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP),
                order_id            TEXT DEFAULT '',
                pending_processed    BOOLEAN DEFAULT FALSE,
                claimed_tiers       INTEGER[] DEFAULT '{}',
                PRIMARY KEY (user_id, guild_id)
            )
        """)

async def ensure_minigame_inventory_columns(pool):
    async with pool.acquire() as conn:
        await conn.execute("ALTER TABLE minigame_inventory ADD COLUMN IF NOT EXISTS link TEXT DEFAULT NULL")

async def ensure_minigame_chests_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_chests (
                gid                  BIGINT NOT NULL,
                uid                  BIGINT NOT NULL,
                chest_triggered      BOOLEAN DEFAULT FALSE,
                chest_date           TEXT DEFAULT '',
                last_message_content TEXT DEFAULT '',
                last_message_time    BIGINT DEFAULT 0,
                message_count        INTEGER DEFAULT 0,
                threshold            INTEGER DEFAULT 0,
                streak               INTEGER DEFAULT 0,
                max_streak           INTEGER DEFAULT 0,
                last_claimed         TEXT DEFAULT NULL,
                counts               INTEGER[] DEFAULT '{}',
                PRIMARY KEY (gid, uid)
            )
        """)

async def get_chest_progress(pool, gid: int, uid: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT chest_triggered, chest_date, last_message_content, last_message_time, message_count, threshold FROM minigame_chests WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    if row:
        return {
            "chest_triggered": row["chest_triggered"],
            "current_date": row["chest_date"],
            "last_content": row["last_message_content"],
            "last_time": row["last_message_time"],
            "message_count": row["message_count"],
            "threshold": row["threshold"],
        }
    return None

async def upsert_chest_progress(pool, gid: int, uid: int, state: dict):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO minigame_chests (gid, uid, chest_triggered, chest_date, last_message_content, last_message_time, message_count, threshold)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (gid, uid) DO UPDATE SET
                chest_triggered = EXCLUDED.chest_triggered,
                chest_date = EXCLUDED.chest_date,
                last_message_content = EXCLUDED.last_message_content,
                last_message_time = EXCLUDED.last_message_time,
                message_count = EXCLUDED.message_count,
                threshold = EXCLUDED.threshold
        """, gid, uid, state["chest_triggered"], state["current_date"], state["last_content"], state["last_time"], state["message_count"], state["threshold"])

async def get_chest_streaks(pool, gid: int, uid: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT streak, max_streak, last_claimed FROM minigame_chests WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    if row:
        return {
            "streak": row["streak"] or 0,
            "max_streak": row["max_streak"] or 0,
            "last_claimed": row["last_claimed"],
        }
    return {}

async def upsert_chest_streaks(pool, gid: int, uid: int, streak: int, max_streak: int, last_claimed: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO minigame_chests (gid, uid, streak, max_streak, last_claimed)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (gid, uid) DO UPDATE SET
                streak = EXCLUDED.streak,
                max_streak = EXCLUDED.max_streak,
                last_claimed = EXCLUDED.last_claimed
        """, gid, uid, streak, max_streak, last_claimed)

async def get_chest_counts(pool, gid: int, uid: int) -> list:
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT counts FROM minigame_chests WHERE gid = $1 AND uid = $2",
            gid, uid
        )
    return list(val) if val else []

async def upsert_chest_counts(pool, gid: int, uid: int, counts: list):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO minigame_chests (gid, uid, counts)
            VALUES ($1, $2, $3)
            ON CONFLICT (gid, uid) DO UPDATE SET
                counts = EXCLUDED.counts
        """, gid, uid, counts)

# ── minigame_cosmetics ──────────────────────────────────────────────────

async def ensure_cosmetics_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_cosmetics (
                gid         BIGINT NOT NULL,
                uid         BIGINT NOT NULL,

                titles           TEXT[][] DEFAULT '{}',
                backgrounds      TEXT[]   DEFAULT '{}',
                frames           TEXT[]   DEFAULT '{}',

                embed_color      BOOLEAN DEFAULT FALSE,

                selected_title                   TEXT,
                selected_custom_title            TEXT,
                selected_animated_background     TEXT,
                selected_profile_frame           TEXT,
                selected_font                    TEXT,
                selected_embed_color_hex         TEXT,
                selected_animated_background_unlocked  BOOLEAN DEFAULT FALSE,
                selected_font_unlocked                 BOOLEAN DEFAULT FALSE,
                selected_custom_title_unlocked          BOOLEAN DEFAULT FALSE,

                PRIMARY KEY (gid, uid)
            )
        """)

async def get_cosmetics(pool, gid: int, uid: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM minigame_cosmetics WHERE gid = $1 AND uid = $2", gid, uid
        )
    if row:
        return dict(row)
    return None

async def upsert_cosmetics(pool, gid: int, uid: int, **kwargs):
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(kwargs)))
    updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in kwargs)
    vals = list(kwargs.values())
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO minigame_cosmetics (gid, uid, {cols})
            VALUES ($1, $2, {placeholders})
            ON CONFLICT (gid, uid) DO UPDATE SET {updates}
        """, gid, uid, *vals)

async def add_title_to_cosmetics(pool, gid: int, uid: int, ts: str, name: str):
    row = await get_cosmetics(pool, gid, uid)
    titles = row["titles"] if row else []
    titles.append([ts, name])
    await upsert_cosmetics(pool, gid, uid, titles=titles)

async def add_background_to_cosmetics(pool, gid: int, uid: int, name: str):
    row = await get_cosmetics(pool, gid, uid)
    bgs = list(row["backgrounds"]) if row else []
    if name not in bgs:
        bgs.append(name)
    await upsert_cosmetics(pool, gid, uid, backgrounds=bgs)

async def add_frame_to_cosmetics(pool, gid: int, uid: int, name: str):
    row = await get_cosmetics(pool, gid, uid)
    frames = list(row["frames"]) if row else []
    if name not in frames:
        frames.append(name)
    await upsert_cosmetics(pool, gid, uid, frames=frames)

# ── minigame_rewards (shop items + milestones + pending edits) ──────────

async def ensure_rewards_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_rewards (
                id                      SERIAL PRIMARY KEY,
                gid                     BIGINT NOT NULL,
                item_type               TEXT NOT NULL,

                name                    TEXT NOT NULL,
                description             TEXT NOT NULL DEFAULT '',

                cost                    TEXT DEFAULT '0',
                multiple                BOOLEAN DEFAULT FALSE,
                stock                   INTEGER DEFAULT -1,

                threshold               BIGINT,

                pending_stock_change    TEXT,
                pending_scheduled_time  DOUBLE PRECISION,

                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rewards_gid_type ON minigame_rewards (gid, item_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rewards_pending ON minigame_rewards (pending_scheduled_time)
                WHERE pending_scheduled_time IS NOT NULL
        """)

async def get_shop_items(pool, gid: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, description, cost, multiple, stock FROM minigame_rewards WHERE gid = $1 AND item_type = 'shop_item' ORDER BY id",
            gid
        )
    return [[r["name"], r["description"], r["cost"], r["multiple"], r["stock"]] for r in rows]

async def set_shop_items(pool, gid: int, items: list):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM minigame_rewards WHERE gid = $1 AND item_type = 'shop_item'", gid)
            for item in items:
                name, desc, cost, multiple, stock = item[0], item[1], str(item[2]), item[3], item[4]
                await conn.execute(
                    "INSERT INTO minigame_rewards (gid, item_type, name, description, cost, multiple, stock) VALUES ($1, 'shop_item', $2, $3, $4, $5, $6)",
                    gid, name, desc, cost, multiple, stock
                )

async def get_milestones_list(pool, gid: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT description, name, threshold FROM minigame_rewards WHERE gid = $1 AND item_type = 'milestone' ORDER BY id",
            gid
        )
    return [[r["description"], r["name"], r["threshold"]] for r in rows]

async def set_milestones(pool, gid: int, milestones: list):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM minigame_rewards WHERE gid = $1 AND item_type = 'milestone'", gid)
            for ms in milestones:
                desc, reward, threshold = ms[0], ms[1], ms[2]
                await conn.execute(
                    "INSERT INTO minigame_rewards (gid, item_type, name, description, threshold) VALUES ($1, 'milestone', $2, $3, $4)",
                    gid, reward, desc, threshold
                )

async def process_pending_stock_edits(pool, gid: int) -> int:
    current_time = time.time()
    processed = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, description, cost, multiple, stock, pending_stock_change, pending_scheduled_time FROM minigame_rewards "
            "WHERE gid = $1 AND item_type = 'shop_item' AND pending_scheduled_time IS NOT NULL AND pending_scheduled_time <= $2",
            gid, current_time
        )
        for row in rows:
            current_stock = row["stock"]
            stock_change = row["pending_stock_change"]
            if stock_change.startswith(('+', '-')):
                if current_stock == -1:
                    current_stock = 0
                try:
                    change = int(stock_change)
                    new_stock = current_stock + change
                except ValueError:
                    sign = stock_change[0]
                    num_str = stock_change[1:].strip()
                    num = int(num_str) if num_str else 0
                    new_stock = current_stock + num if sign == '+' else current_stock - num
            else:
                try:
                    new_stock = int(stock_change)
                except ValueError:
                    continue
            if new_stock < 0:
                new_stock = 0
            await conn.execute(
                "UPDATE minigame_rewards SET stock = $1, pending_stock_change = NULL, pending_scheduled_time = NULL WHERE id = $2",
                new_stock, row["id"]
            )
            processed += 1
    return processed

async def get_pending_shop_edits(pool, gid: int) -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, pending_stock_change, pending_scheduled_time FROM minigame_rewards "
            "WHERE gid = $1 AND item_type = 'shop_item' AND pending_scheduled_time IS NOT NULL",
            gid
        )
    return {
        str(r["id"]): {
            "item_identifier": r["name"],
            "stock_change": r["pending_stock_change"],
            "scheduled_time": r["pending_scheduled_time"]
        }
        for r in rows
    }

async def add_shop_item(pool, gid: int, name: str, description: str, cost: str, multiple: bool, stock: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO minigame_rewards (gid, item_type, name, description, cost, multiple, stock) VALUES ($1, 'shop_item', $2, $3, $4, $5, $6)",
            gid, name, description, cost, multiple, stock
        )

async def remove_shop_item_by_name(pool, gid: int, name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM minigame_rewards WHERE gid = $1 AND item_type = 'shop_item' AND name = $2",
            gid, name
        )

async def update_shop_item_cost(pool, gid: int, name: str, new_cost: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_rewards SET cost = $1 WHERE gid = $2 AND item_type = 'shop_item' AND name = $3",
            new_cost, gid, name
        )

async def update_shop_item_stock_by_name(pool, gid: int, name: str, new_stock: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_rewards SET stock = $1 WHERE gid = $2 AND item_type = 'shop_item' AND name = $3",
            new_stock, gid, name
        )

async def add_pending_edit(pool, gid: int, name: str, stock_change: str, scheduled_time: float):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM minigame_rewards WHERE gid = $1 AND item_type = 'shop_item' AND name = $2",
            gid, name
        )
        if row:
            await conn.execute(
                "UPDATE minigame_rewards SET pending_stock_change = $1, pending_scheduled_time = $2 WHERE id = $3",
                stock_change, scheduled_time, row["id"]
            )

async def delete_pending_edit_by_name(pool, gid: int, name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE minigame_rewards SET pending_stock_change = NULL, pending_scheduled_time = NULL WHERE gid = $1 AND item_type = 'shop_item' AND name = $2",
            gid, name
        )

async def get_milestones_flat(pool, gid: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT description, name, threshold FROM minigame_rewards WHERE gid = $1 AND item_type = 'milestone' ORDER BY id",
            gid
        )
    return [[r["description"], r["name"], r["threshold"]] for r in rows]

_SETTINGS_FALLBACK = {
    "channel_id": 0,
    "mora_multiplier": 1.00,
    "minigames_enabled": False,
    "minigames_list": [],
    "minigames_frequency": 50,
    "chests_enabled": False,
}

_GUILD_CHEST_FALLBACK = {
    "chests_base_upgrade_chances": 4,
    "chests_tier_names": ["Common", "Exquisite", "Precious", "Luxurious"],
    "chests_tier_rewards": [2500, 7500, 15000, 30000],
    "chests_upgrade_chances": [0.30, 0.15, 0.20],
    "chests_streak_bonus": 100,
    "chests_max_streak_bonus": 10000,
    "chests_spawn_req": [4, 6],
    "chests_emotes": ["<a:common:1371641883121680465>", "<a:exquisite:1371641856344985620>", "<a:precious:1371641871452995689>", "<a:luxurious:1371641841338023976>"],
    "chests_icons": ["https://i.imgur.com/2kOfLSC.png", "https://i.imgur.com/DBPQSAu.png", "https://i.imgur.com/zxOlrCo.png", "https://i.imgur.com/5nWwRdc.png"],
}

async def get_channel_settings(pool, channel_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM minigame_settings WHERE channel_id = $1", channel_id)
    if row:
        return dict(row)
    return dict(_SETTINGS_FALLBACK, channel_id=channel_id)

async def get_channel_mora_multiplier(pool, channel_id: int) -> float:
    settings = await get_channel_settings(pool, channel_id)
    return float(settings.get("mora_multiplier", 1.00))

async def get_channel_minigame_list(pool, channel_id: int) -> list:
    settings = await get_channel_settings(pool, channel_id)
    raw = settings.get("minigames_list", [])
    if isinstance(raw, list):
        return raw
    return []

async def get_enabled_channels_dict(pool) -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel_id, minigames_frequency FROM minigame_settings WHERE minigames_enabled = TRUE"
        )
    return {r["channel_id"]: r["minigames_frequency"] for r in rows}

async def upsert_channel_settings(pool, channel_id: int, **kwargs):
    cols = ", ".join(kwargs.keys())
    vals = list(kwargs.values())
    placeholders = ", ".join(f"${i+2}" for i in range(len(vals)))
    updates = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs.keys()))
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO minigame_settings (channel_id, {cols})
            VALUES ($1, {placeholders})
            ON CONFLICT (channel_id) DO UPDATE SET {updates}
        """, channel_id, *vals)

async def get_guild_chest_config(pool, guild_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM minigame_guild_chest_settings WHERE gid = $1", guild_id)
    if row:
        d = dict(row)
        return {
            "chests_base_upgrade_chances": d.get("chests_base_upgrade_chances", 4),
            "chests_tier_names": list(d.get("chests_tier_names", _GUILD_CHEST_FALLBACK["chests_tier_names"])),
            "chests_tier_rewards": list(d.get("chests_tier_rewards", _GUILD_CHEST_FALLBACK["chests_tier_rewards"])),
            "chests_upgrade_chances": [float(x) for x in (d.get("chests_upgrade_chances", _GUILD_CHEST_FALLBACK["chests_upgrade_chances"]) or [])],
            "chests_streak_bonus": d.get("chests_streak_bonus", 100),
            "chests_max_streak_bonus": d.get("chests_max_streak_bonus", 10000),
            "chests_spawn_req": list(d.get("chests_spawn_req", [4, 6])),
            "chests_emotes": list(d.get("chests_emotes", _GUILD_CHEST_FALLBACK["chests_emotes"])),
            "chests_icons": list(d.get("chests_icons", _GUILD_CHEST_FALLBACK["chests_icons"])),
        }
    return dict(_GUILD_CHEST_FALLBACK)

async def upsert_guild_chest_config(pool, guild_id: int, **kwargs):
    cols = ", ".join(kwargs.keys())
    vals = list(kwargs.values())
    placeholders = ", ".join(f"${i+2}" for i in range(len(vals)))
    updates = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs.keys()))
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO minigame_guild_chest_settings (gid, {cols})
            VALUES ($1, {placeholders})
            ON CONFLICT (gid) DO UPDATE SET {updates}
        """, guild_id, *vals)

async def get_channel_chest_config(pool, guild_id: int, channel_id: int) -> dict:
    s = await get_channel_settings(pool, channel_id)
    gc = await get_guild_chest_config(pool, guild_id)
    return {
        "chests_enabled": s.get("chests_enabled", False),
        "chests_base_upgrade_chances": gc.get("chests_base_upgrade_chances", 4),
        "chests_tier_names": gc.get("chests_tier_names", _GUILD_CHEST_FALLBACK["chests_tier_names"]),
        "chests_tier_rewards": gc.get("chests_tier_rewards", _GUILD_CHEST_FALLBACK["chests_tier_rewards"]),
        "chests_upgrade_chances": gc.get("chests_upgrade_chances", _GUILD_CHEST_FALLBACK["chests_upgrade_chances"]),
        "chests_streak_bonus": gc.get("chests_streak_bonus", 100),
        "chests_max_streak_bonus": gc.get("chests_max_streak_bonus", 10000),
        "chests_spawn_req": gc.get("chests_spawn_req", [4, 6]),
        "chests_emotes": gc.get("chests_emotes", _GUILD_CHEST_FALLBACK["chests_emotes"]),
        "chests_icons": gc.get("chests_icons", _GUILD_CHEST_FALLBACK["chests_icons"]),
    }

# User minigame settings helpers (chest_disabled / minigame_disabled)

async def get_user_minigame_settings(pool, guild_id: int, user_id: int) -> dict:
    await ensure_progression_user(pool, guild_id, user_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT chest_disabled, minigame_disabled FROM minigame_progression WHERE gid = $1 AND uid = $2",
            guild_id, user_id
        )
    return {
        "chest_disabled": bool(row["chest_disabled"]) if row else False,
        "minigame_disabled": bool(row["minigame_disabled"]) if row else False,
    }

async def upsert_user_minigame_setting(pool, guild_id: int, user_id: int, column: str, value):
    await ensure_progression_user(pool, guild_id, user_id)
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE minigame_progression SET {column} = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
            guild_id, user_id, bool(value)
        )

# Legacy alias to be deleted

def get_minigame_list(channel_id):
    import warnings
    warnings.warn("sync get_minigame_list is deprecated, use async get_channel_minigame_list", DeprecationWarning)
    return []

# Misc helpers

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

    milestones = await get_milestones_flat(pool, guild_id)
    
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
        
class TierRewardsView(discord.ui.View):
    def __init__(self, free_embed=discord.Embed(title="Button expired", color=discord.Color.red()), elite_embed=discord.Embed(color=0xFF0000)):
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
            await interaction.response.send_message(embed=discord.Embed(description=f"{CONFUSED_EMOTE} You did not earn any tiers from this XP gain."), ephemeral=True)
            
    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_xp_quest_info_view_new",
        emoji=CONFUSED_EMOTE
    )
    async def persistentXPQuestInfoViewNew(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(embed=XP_QUEST_EMBED, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_info_delete_new",
        emoji="<a:delete:1372423674640207882>",
    )
    async def persistent_info_delete_new(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content and str(interaction.user.id) not in interaction.message.embeds[0].description:
            await interaction.response.send_message(embed=discord.Embed(description=f"{NO_EMOTE} This isn't your notification!", color=discord.Color.red()), ephemeral=True)
        else:
            await interaction.message.delete()
            
async def setup(bot) -> None:
    await ensure_minigame_settings_table(bot.pool)
    await ensure_minigame_progression_columns(bot.pool)
    await ensure_minigame_inventory_columns(bot.pool)
    await ensure_minigame_guild_chest_settings_table(bot.pool)
    await ensure_minigame_elite_table(bot.pool)
    await ensure_minigame_chests_table(bot.pool)
    await ensure_cosmetics_table(bot.pool)
    await ensure_rewards_table(bot.pool)