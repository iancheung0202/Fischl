import asyncio
import contextlib
import datetime
import math
import time
from typing import Optional

import asyncpg
import discord

from commands.Events.config import (
    CONFUSED_EMOTE,
    CURRENCY_INFO,
    MORA_CHEST_UPGRADE_TIMES,
    NO_EMOTE,
    XP_QUEST_EMBED,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS minigame_settings (
    channel_id BIGINT PRIMARY KEY,
    mora_multiplier NUMERIC(4,2) DEFAULT 1.00,
    minigames_enabled BOOLEAN DEFAULT TRUE,
    minigames_list TEXT[] DEFAULT '{}',
    minigames_frequency INTEGER DEFAULT 50,
    chests_enabled BOOLEAN DEFAULT FALSE,
    chat_enabled BOOLEAN DEFAULT FALSE,
    chat_range INTEGER[] DEFAULT ARRAY[19,25],
    chat_boosted_roles TEXT[] DEFAULT '{}',
    chat_msg_range INTEGER[] DEFAULT ARRAY[15,20]
);
CREATE TABLE IF NOT EXISTS minigame_progression (
    gid BIGINT NOT NULL,
    uid BIGINT NOT NULL,
    xp INTEGER DEFAULT 0,
    prestige INTEGER DEFAULT 0,
    bonus_tier INTEGER DEFAULT 0,
    kingdom_schloss INTEGER DEFAULT 0,
    kingdom_theater INTEGER DEFAULT 0,
    kingdom_bibliothek INTEGER DEFAULT 0,
    kingdom_garten INTEGER DEFAULT 0,
    mora_boost INTEGER DEFAULT 0,
    chest_upgrades INTEGER DEFAULT 4,
    gift_tax INTEGER,
    minigame_summons INTEGER DEFAULT 0,
    shop_discount INTEGER DEFAULT 0,
    domain_discount INTEGER DEFAULT 0,
    express_daily_chests BOOLEAN DEFAULT FALSE,
    chest_disabled BOOLEAN DEFAULT FALSE,
    minigame_disabled BOOLEAN DEFAULT FALSE,
    sigils_disabled BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (gid, uid)
);
CREATE TABLE IF NOT EXISTS minigame_mora (
    uid BIGINT NOT NULL,
    gid BIGINT NOT NULL,
    cid BIGINT NOT NULL,
    timestamp BIGINT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (gid, uid, cid, timestamp)
);
CREATE TABLE IF NOT EXISTS minigame_inventory (
    uid BIGINT NOT NULL,
    gid BIGINT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    cost INTEGER DEFAULT 0,
    timestamp BIGINT DEFAULT 0,
    pinned BOOLEAN DEFAULT FALSE,
    link TEXT DEFAULT NULL,
    PRIMARY KEY (gid, uid, timestamp)
);
CREATE TABLE IF NOT EXISTS minigame_guild_settings (
    gid BIGINT PRIMARY KEY,
    chests_base_upgrade_chances INTEGER DEFAULT 4,
    chests_tier_names TEXT[] DEFAULT ARRAY['Common','Exquisite','Precious','Luxurious'],
    chests_tier_rewards INTEGER[] DEFAULT ARRAY[2500,7500,15000,30000],
    chests_upgrade_chances NUMERIC(5,2)[] DEFAULT ARRAY[0.30,0.15,0.20],
    chests_streak_bonus INTEGER DEFAULT 100,
    chests_max_streak_bonus INTEGER DEFAULT 10000,
    chests_spawn_req INTEGER[] DEFAULT ARRAY[4,6],
    chests_emotes TEXT[] DEFAULT ARRAY['<a:common:1371641883121680465>','<a:exquisite:1371641856344985620>','<a:precious:1371641871452995689>','<a:luxurious:1371641841338023976>'],
    chests_icons TEXT[] DEFAULT ARRAY['https://i.imgur.com/2kOfLSC.png','https://i.imgur.com/DBPQSAu.png','https://i.imgur.com/zxOlrCo.png','https://i.imgur.com/5nWwRdc.png'],
    chat_max_cap INTEGER DEFAULT 60
);
CREATE TABLE IF NOT EXISTS minigame_elite (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    server_name TEXT DEFAULT '',
    expires_at BIGINT NOT NULL,
    activated_at BIGINT DEFAULT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP),
    order_id TEXT DEFAULT '',
    pending_processed BOOLEAN DEFAULT FALSE,
    claimed_tiers INTEGER[] DEFAULT '{}',
    PRIMARY KEY (user_id, guild_id)
);
CREATE TABLE IF NOT EXISTS minigame_chests (
    gid BIGINT NOT NULL,
    uid BIGINT NOT NULL,
    chest_triggered BOOLEAN DEFAULT FALSE,
    chest_date TEXT DEFAULT '',
    last_message_content TEXT DEFAULT '',
    last_message_time BIGINT DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    threshold INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0,
    last_claimed TEXT DEFAULT NULL,
    counts INTEGER[] DEFAULT '{}',
    PRIMARY KEY (gid, uid)
);
CREATE TABLE IF NOT EXISTS minigame_cosmetics (
    gid BIGINT NOT NULL,
    uid BIGINT NOT NULL,
    titles TEXT[][] DEFAULT '{}',
    backgrounds TEXT[] DEFAULT '{}',
    frames TEXT[] DEFAULT '{}',
    embed_color BOOLEAN DEFAULT FALSE,
    selected_title TEXT,
    selected_custom_title TEXT,
    selected_animated_background TEXT,
    selected_profile_frame TEXT,
    selected_font TEXT,
    selected_embed_color_hex TEXT,
    selected_animated_background_unlocked BOOLEAN DEFAULT FALSE,
    selected_font_unlocked BOOLEAN DEFAULT FALSE,
    selected_custom_title_unlocked BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (gid, uid)
);
CREATE TABLE IF NOT EXISTS minigame_rewards (
    id SERIAL PRIMARY KEY,
    gid BIGINT NOT NULL,
    item_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    cost TEXT DEFAULT '0',
    multiple BOOLEAN DEFAULT FALSE,
    stock INTEGER DEFAULT -1,
    threshold BIGINT,
    pending_stock_change TEXT,
    pending_scheduled_time DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    currency_type TEXT DEFAULT 'guild_mora'
);
CREATE TABLE IF NOT EXISTS minigame_sigils (
    uid BIGINT NOT NULL,
    gid BIGINT NOT NULL,
    date TEXT NOT NULL,
    earnings INTEGER DEFAULT 0,
    PRIMARY KEY (uid, gid, date)
);
CREATE INDEX IF NOT EXISTS idx_rewards_gid_type ON minigame_rewards (gid, item_type);
CREATE INDEX IF NOT EXISTS idx_rewards_pending ON minigame_rewards (pending_scheduled_time)
    WHERE pending_scheduled_time IS NOT NULL;
"""
KINGDOM = {
    "schloss": "kingdom_schloss",
    "theater": "kingdom_theater",
    "bibliothek": "kingdom_bibliothek",
    "garten": "kingdom_garten",
}
KINGDOM_TOTAL = " + ".join(KINGDOM.values())
# Where each currency a milestone can count is kept: table, column, and whether it is per server.
CURRENCIES = {
    "guild_mora": ("minigame_mora", "count", True),
    "global_mora": ("minigame_mora", "count", False),
    "guild_sigils": ("minigame_sigils", "earnings", True),
    "global_sigils": ("minigame_sigils", "earnings", False),
}
MEMBER = "WHERE gid = $1 AND uid = $2"


def get_currency_display(currency_type: str) -> str:
    """Gives the emoji of a currency, Mora for one that is not known."""
    info = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])
    return f"{info['emoji']}"


async def upsert(pool, table: str, key: dict, values: dict) -> None:
    """Saves the given columns of the row with this key, adding the row if it is missing."""
    columns = [*key, *values]
    places = ", ".join(f"${place}" for place in range(1, len(columns) + 1))
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in values)
    await pool.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({places}) "
        f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates}",
        *key.values(),
        *values.values(),
    )


# Progression


async def ensure_progression_user(pool: asyncpg.Pool, gid: int, uid: int) -> None:
    """Adds a member's progression row if they have none."""
    await pool.execute(
        """
        INSERT INTO minigame_progression
        (gid, uid, kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten,
         xp, prestige, bonus_tier, mora_boost, chest_upgrades, gift_tax, minigame_summons,
         shop_discount, domain_discount, express_daily_chests)
        VALUES ($1, $2, 0, 0, 0, 0, 0, 0, 0, 0, 4, NULL, 0, 0, 0, FALSE)
        ON CONFLICT (gid, uid) DO NOTHING
        """,
        gid,
        uid,
    )


async def progression(pool, gid: int, uid: int, columns: str, create: bool = False):
    """Gives the named columns of a member's progression row, or None without one; `create` adds it first."""
    if create:
        await ensure_progression_user(pool, gid, uid)
    return await pool.fetchrow(
        f"SELECT {columns} FROM minigame_progression {MEMBER}", gid, uid
    )


async def set_progression(pool, gid: int, uid: int, column: str, value) -> None:
    """Saves one column of a member's progression row, adding the row first."""
    await ensure_progression_user(pool, gid, uid)
    await pool.execute(
        f"UPDATE minigame_progression SET {column} = $3, updated_at = CURRENT_TIMESTAMP {MEMBER}",
        gid,
        uid,
        value,
    )


async def get_progression_data(pool: asyncpg.Pool, gid: int, uid: int) -> dict:
    """Gives a member's XP, prestige and bonus tier."""
    row = await progression(pool, gid, uid, "xp, prestige, bonus_tier")
    return dict(row) if row else {"xp": 0, "prestige": 0, "bonus_tier": 0}


async def get_user_xp(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives a member's XP."""
    row = await progression(pool, gid, uid, "xp")
    return row and row["xp"] or 0


async def get_kingdom_buildings(pool: asyncpg.Pool, gid: int, uid: int) -> dict:
    """Gives the level of each of a member's buildings."""
    row = await progression(pool, gid, uid, ", ".join(KINGDOM.values()))
    return {name: row[column] if row else 0 for name, column in KINGDOM.items()}


async def get_building_level(
    pool: asyncpg.Pool, gid: int, uid: int, building_key: str
) -> int:
    """Gives the level of one of a member's buildings, 0 for a building that does not exist."""
    column = KINGDOM.get(building_key)
    row = column and await progression(pool, gid, uid, column)
    return row and row[column] or 0


async def increment_building_level(
    pool: asyncpg.Pool, gid: int, uid: int, building_key: str
) -> int:
    """Raises one of a member's buildings by a level and gives the new level."""
    column = KINGDOM.get(building_key)
    if not column:
        return 0
    await ensure_progression_user(pool, gid, uid)
    level = await pool.fetchval(
        f"UPDATE minigame_progression SET {column} = {column} + 1, updated_at = CURRENT_TIMESTAMP "
        f"{MEMBER} RETURNING {column}",
        gid,
        uid,
    )
    return level or 0


async def get_user_stats(pool: asyncpg.Pool, gid: int, uid: int) -> dict:
    """Gives the boosts and discounts a member unlocked."""
    columns = "mora_boost, chest_upgrades, gift_tax, minigame_summons, shop_discount, domain_discount, express_daily_chests"
    return dict(await progression(pool, gid, uid, columns, create=True))


def apply_discount(amount: int, discount_percent: int) -> int:
    """Gives a price after a discount of at most 50%, rounded up."""
    discount_percent = max(0, min(50, int(discount_percent or 0)))
    return max(0, math.ceil(amount * (100 - discount_percent) / 100))


async def get_shop_discount(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives a member's shop discount in percent, at most 50."""
    row = await progression(pool, gid, uid, "shop_discount", create=True)
    return min(50, row["shop_discount"] or 0)


async def get_domain_discount(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives a member's kingdom upgrade discount in percent, at most 50."""
    row = await progression(pool, gid, uid, "domain_discount", create=True)
    return min(50, row["domain_discount"] or 0)


async def get_express_daily_chests(pool: asyncpg.Pool, gid: int, uid: int) -> bool:
    """Says whether a member unlocked express daily chests."""
    row = await progression(pool, gid, uid, "express_daily_chests", create=True)
    return bool(row["express_daily_chests"])


async def update_express_daily_chests(
    pool: asyncpg.Pool, gid: int, uid: int, value: bool
) -> None:
    """Saves whether a member unlocked express daily chests."""
    await set_progression(pool, gid, uid, "express_daily_chests", bool(value))


async def get_mora_boost(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives a member's Mora boost in percent."""
    row = await progression(pool, gid, uid, "mora_boost")
    return row and row["mora_boost"] or 0


async def get_chest_upgrades(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives how many times a member may upgrade a chest."""
    row = await progression(pool, gid, uid, "chest_upgrades")
    if row and row["chest_upgrades"] is not None:
        return row["chest_upgrades"]
    return MORA_CHEST_UPGRADE_TIMES


async def get_chest_bonus_chance(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives the chest bonus chance from a member's garden, at most 50."""
    return min(50, await get_building_level(pool, gid, uid, "garten"))


async def get_xp_boost(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives the XP boost from a member's library, at most 50."""
    return min(50, await get_building_level(pool, gid, uid, "bibliothek"))


async def get_encore_chance(pool: asyncpg.Pool, gid: int, uid: int) -> int:
    """Gives the encore chance from a member's theater, at most 50."""
    return min(50, await get_building_level(pool, gid, uid, "theater"))


async def get_user_minigame_settings(pool, guild_id: int, user_id: int) -> dict:
    """Gives which of chests, minigames and Sigils a member turned off."""
    columns = "chest_disabled, minigame_disabled, sigils_disabled"
    row = await progression(pool, guild_id, user_id, columns, create=True)
    return {column: bool(value) for column, value in row.items()}


async def upsert_user_minigame_setting(
    pool, guild_id: int, user_id: int, column: str, value
):
    """Saves whether a member turned one of chests, minigames and Sigils off."""
    await set_progression(pool, guild_id, user_id, column, bool(value))


# Balances and leaderboards


async def balance(pool, currency_type: str, uid: int, gid: int) -> int:
    """Gives how much of a currency a member has, in this server or everywhere as the currency says."""
    table, column, scoped = CURRENCIES.get(currency_type, CURRENCIES["guild_mora"])
    statement = f"SELECT COALESCE(SUM({column}), 0) FROM {table} WHERE uid = $1"
    if scoped:
        return await pool.fetchval(statement + " AND gid = $2", uid, gid) or 0
    return await pool.fetchval(statement, uid) or 0


async def get_total_mora(pool: asyncpg.Pool, uid: int) -> int:
    """Gives a member's Mora over all servers."""
    return await balance(pool, "global_mora", uid, None)


async def get_guild_mora(pool: asyncpg.Pool, uid: int, gid: int) -> int:
    """Gives a member's Mora in one server."""
    return await balance(pool, "guild_mora", uid, gid)


async def get_sigils_balance(pool, uid: int, gid: int) -> int:
    """Gives a member's Sigils in one server."""
    return await balance(pool, "guild_sigils", uid, gid)


async def get_global_sigils_balance(pool, uid: int) -> int:
    """Gives a member's Sigils over all servers."""
    return await balance(pool, "global_sigils", uid, None)


async def ranking(
    pool,
    table: str,
    amount: str,
    where: str = "",
    grouped: bool = True,
    gid: int = None,
    limit: int = None,
    least: int = None,
) -> list:
    """Gives (member, amount) pairs, highest first; of one server with `gid`, at or over `least`, the top `limit`."""
    args = []

    def place(value) -> str:
        args.append(value)
        return f"${len(args)}"

    conditions = [f"gid = {place(gid)}"] if gid is not None else []
    conditions += [where] if where else []
    statement = f"SELECT uid, {amount} AS total FROM {table}"
    if conditions:
        statement += " WHERE " + " AND ".join(conditions)
    if grouped:
        statement += " GROUP BY uid"
    if least is not None:
        statement += f" HAVING {amount} >= {place(least)}"
    statement += " ORDER BY total DESC, uid"
    if limit:
        statement += f" LIMIT {place(limit)}"
    rows = await pool.fetch(statement, *args)
    return [(row["uid"], row["total"]) for row in rows]


def leaderboard(
    table: str, server: str, everywhere: str, where: str = "", grouped=True
):
    """Gives the server and the global leaderboard of one amount."""

    async def in_server(pool: asyncpg.Pool, gid: int, limit: int = None) -> list:
        return await ranking(pool, table, server, where, grouped, gid, limit)

    async def in_all(pool: asyncpg.Pool, limit: int = None) -> list:
        return await ranking(pool, table, everywhere, where, limit=limit)

    return in_server, in_all


get_guild_leaderboard, get_global_leaderboard = leaderboard(
    "minigame_mora", "SUM(count)", "SUM(count)"
)
get_guild_sigils_leaderboard, get_global_sigils_leaderboard = leaderboard(
    "minigame_sigils", "SUM(earnings)", "SUM(earnings)"
)
get_guild_items_leaderboard, get_global_items_leaderboard = leaderboard(
    "minigame_inventory", "COUNT(*)", "COUNT(*)"
)
get_guild_minigame_wins_leaderboard, get_global_minigame_wins_leaderboard = leaderboard(
    "minigame_mora", "COUNT(*)", "COUNT(*)", "count > 0"
)
ACTIVE_DAYS = "COUNT(DISTINCT DATE(TO_TIMESTAMP(timestamp)))"
get_guild_active_days_leaderboard, get_global_active_days_leaderboard = leaderboard(
    "minigame_mora", ACTIVE_DAYS, ACTIVE_DAYS, "count > 0"
)
# A member has one progression row per server, so the server boards read it as it is.
get_guild_kingdom_leaderboard, get_global_kingdom_leaderboard = leaderboard(
    "minigame_progression", f"({KINGDOM_TOTAL})", f"SUM({KINGDOM_TOTAL})", grouped=False
)
get_guild_prestige_leaderboard, get_global_prestige_leaderboard = leaderboard(
    "minigame_progression", "prestige", "SUM(prestige)", grouped=False
)


async def get_users_by_currency_threshold(
    pool: asyncpg.Pool, gid: int, threshold: int, currency_type: str
) -> list:
    """Gives the members with at least this much of a milestone's currency, with their amounts."""
    table, column, scoped = CURRENCIES.get(currency_type, CURRENCIES["guild_mora"])
    return await ranking(
        pool, table, f"SUM({column})", gid=gid if scoped else None, least=threshold
    )


async def get_user_mora_history(
    pool: asyncpg.Pool, uid: int, gid: int, limit: Optional[int] = None
) -> list:
    """Gives a member's Mora entries in a server as (timestamp, amount), oldest first."""
    statement = "SELECT timestamp, count FROM minigame_mora WHERE uid = $1 AND gid = $2 ORDER BY timestamp ASC"
    if limit:
        rows = await pool.fetch(statement + " LIMIT $3", uid, gid, limit)
    else:
        rows = await pool.fetch(statement, uid, gid)
    return [(row["timestamp"], row["count"]) for row in rows]


MORA_DAYS = """
    SELECT DATE(TO_TIMESTAMP(timestamp)) AS date, SUM(count) AS total, MIN(timestamp) AS first,
           COUNT(*) FILTER (WHERE count > 0) AS earnings, MAX(count) FILTER (WHERE count > 0) AS largest
    FROM minigame_mora WHERE uid = $1 AND gid = $2
    GROUP BY date ORDER BY total DESC, date
"""


async def get_mora_stats(pool: asyncpg.Pool, uid: int, gid: int) -> dict:
    """Gives the numbers of a member's Mora history in a server: first day, active days, averages and records."""
    days = await pool.fetch(MORA_DAYS, uid, gid)
    first_played = min((day["first"] for day in days), default=int(time.time()))
    utc = datetime.timezone.utc
    first_day = datetime.datetime.fromtimestamp(first_played, utc).date()
    total_days = (datetime.datetime.now(utc).date() - first_day).days + 1
    total = sum(day["total"] for day in days)
    return {
        "first_played": first_played,
        "days_active": len(days),
        "total_days": total_days,
        "average_daily": int(total / total_days) if total_days > 0 else 0,
        "largest_daily": days[0]["total"] if days else 0,
        "largest_daily_date": (
            int(time.mktime(days[0]["date"].timetuple())) if days else None
        ),
        "entry_count": sum(day["earnings"] for day in days),
        "largest_single": max((day["largest"] or 0 for day in days), default=0),
    }


MORA_ENTRY = """
    INSERT INTO minigame_mora (uid, gid, cid, timestamp, count)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (gid, uid, cid, timestamp)
    DO UPDATE SET count = minigame_mora.count + EXCLUDED.count
"""
SIGILS_ENTRY = """
    INSERT INTO minigame_sigils (uid, gid, date, earnings)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (uid, gid, date)
    DO UPDATE SET earnings = minigame_sigils.earnings + EXCLUDED.earnings
    RETURNING earnings
"""
MORA_BY_SERVER = (
    "SELECT gid, SUM(count) AS balance FROM minigame_mora WHERE uid = $1 GROUP BY gid"
)
SIGILS_BY_SERVER = "SELECT gid, SUM(earnings) AS balance FROM minigame_sigils WHERE uid = $1 GROUP BY gid"


@contextlib.asynccontextmanager
async def wallet(pool: asyncpg.Pool, uid: int):
    """Gives a connection on which one member's spend is checked and paid; two spends at once wait their turn."""
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock($1)", uid)
        yield conn


def today() -> str:
    """Gives the UTC date Sigils are stored under."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


async def take(
    conn, balances: str, uid: int, gid: int, amount: int, everywhere: bool, pay
):
    """Takes an amount from this server's balance, then from the others when `everywhere`; False if short."""
    held = {
        row["gid"]: int(row["balance"] or 0) for row in await conn.fetch(balances, uid)
    }
    here = held.pop(gid, 0)
    if amount > (here + sum(held.values()) if everywhere else here):
        return False
    if not everywhere:
        await pay(conn, gid, amount)
        return here - amount
    remaining = amount
    for server, balance in [(gid, here), *held.items()]:
        part = min(balance, remaining)
        if part > 0:
            await pay(conn, server, part)
            remaining -= part
    return here - amount


async def addMora(
    pool: asyncpg.Pool,
    userID: int,
    addedMora: int,
    channelID: int,
    guildID: int,
    client=None,
    bypass_boost=False,
):
    """Adds Mora with the member's boost; gives the text shown for the gain and the amount added."""
    baseMora = addedMora
    boost = 0

    if addedMora > 0 and not bypass_boost:
        boost = await get_mora_boost(pool, guildID, userID)
        addedMora = int(addedMora * (1 + boost / 100))

    await pool.execute(
        MORA_ENTRY, userID, guildID, channelID, int(time.time()), addedMora
    )

    asyncio.create_task(
        delayed_check_milestones(pool, userID, guildID, channelID, client)
    )

    if addedMora > 10000 and client:
        from commands.Events.quests import update_quest

        await update_quest(userID, guildID, channelID, {"earn_big_mora": 1}, client)

    if baseMora > 0 and boost > 0:
        return f"{baseMora} + {addedMora - baseMora} ({boost}% boost)", addedMora
    return abs(addedMora), addedMora


async def take_mora(
    pool: asyncpg.Pool, uid: int, amount: int, cid: int, gid: int, everywhere: bool
):
    """Takes Mora in one step, so two spends at once cannot both pass; gives what is left here, or False."""

    async def pay(conn, server, part):
        await conn.execute(MORA_ENTRY, uid, server, cid, int(time.time()), -part)

    async with wallet(pool, uid) as conn:
        return await take(conn, MORA_BY_SERVER, uid, gid, amount, everywhere, pay)


async def spend_mora(
    pool: asyncpg.Pool, uid: int, amount: int, cid: int, gid: int, client=None
) -> bool:
    """Takes Mora a member pays in this server and rechecks their milestones; False if they have too little."""
    if await take_mora(pool, uid, amount, cid, gid, False) is False:
        return False
    asyncio.create_task(delayed_check_milestones(pool, uid, gid, cid, client))
    return True


async def subtractGuildMora(
    pool: asyncpg.Pool, userID: int, subtractMora: int, channelID: int, guildID: int
) -> int | bool:
    """Takes Mora from a member in this server; gives what is left, or False if they have too little."""
    return await take_mora(pool, userID, subtractMora, channelID, guildID, False)


async def subtract_global_mora(
    pool: asyncpg.Pool, userID: int, amount: int, channelID: int, guildID: int
) -> bool:
    """Takes Mora from this server first, then from the member's other servers; False if they have too little."""
    left = await take_mora(pool, userID, amount, channelID, guildID, True)
    return left is not False


# Inventory

ITEM = "title, description, cost, gid, timestamp, pinned, link"


async def get_user_inventory(
    pool: asyncpg.Pool, uid: int, gid: int, exclude_cost: int = None
) -> list:
    """Gives a member's items oldest first, as tuples in the order of ITEM; `exclude_cost` leaves that cost out."""
    statement = f"SELECT {ITEM} FROM minigame_inventory WHERE uid = $1 AND gid = $2"
    if exclude_cost is not None:
        rows = await pool.fetch(
            statement + " AND cost != $3 ORDER BY timestamp ASC", uid, gid, exclude_cost
        )
    else:
        rows = await pool.fetch(statement + " ORDER BY timestamp ASC", uid, gid)
    return [tuple(row) for row in rows]


SAME_SECOND_ITEMS = 10


async def add_inventory_item(
    pool: asyncpg.Pool,
    uid: int,
    gid: int,
    title,
    description: str,
    cost: int,
    timestamp: int,
    pinned: bool = False,
    link: str = None,
) -> int:
    """Saves an item a member got and gives its timestamp, later by a second for each item they already got then."""
    statement = "INSERT INTO minigame_inventory (uid, gid, title, description, cost, timestamp, pinned, link) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
    for taken in range(SAME_SECOND_ITEMS):
        try:
            await pool.execute(
                statement,
                uid,
                gid,
                str(title),
                description,
                cost,
                timestamp + taken,
                pinned,
                link,
            )
            return timestamp + taken
        except asyncpg.UniqueViolationError:
            if taken == SAME_SECOND_ITEMS - 1:
                raise


async def get_pinned_item(pool: asyncpg.Pool, uid: int, gid: int) -> Optional[str]:
    """Gives the title of the item a member pinned, or None."""
    return await pool.fetchval(
        "SELECT title FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND pinned = true LIMIT 1",
        uid,
        gid,
    )


async def unpin_all_items(pool: asyncpg.Pool, uid: int, gid: int) -> None:
    """Unpins every item of a member."""
    await pool.execute(
        "UPDATE minigame_inventory SET pinned = false WHERE uid = $1 AND gid = $2",
        uid,
        gid,
    )


async def pin_item(pool: asyncpg.Pool, uid: int, gid: int, title) -> bool:
    """Pins a member's items with this title and unpins the rest; False if they have none."""
    await unpin_all_items(pool, uid, gid)
    result = await pool.execute(
        "UPDATE minigame_inventory SET pinned = true WHERE uid = $1 AND gid = $2 AND title = $3",
        uid,
        gid,
        str(title),
    )
    return result != "UPDATE 0"


# Chests

CHEST_PROGRESS = {
    "chest_triggered": "chest_triggered",
    "current_date": "chest_date",
    "last_content": "last_message_content",
    "last_time": "last_message_time",
    "message_count": "message_count",
    "threshold": "threshold",
}


async def chest(pool, gid: int, uid: int, columns: str):
    """Gives the named columns of a member's chest row, or None without one."""
    return await pool.fetchrow(
        f"SELECT {columns} FROM minigame_chests {MEMBER}", gid, uid
    )


async def get_chest_progress(pool, gid: int, uid: int):
    """Gives how far a member is towards today's chest, or None before their first message."""
    row = await chest(pool, gid, uid, ", ".join(CHEST_PROGRESS.values()))
    return row and {name: row[column] for name, column in CHEST_PROGRESS.items()}


async def upsert_chest_progress(pool, gid: int, uid: int, state: dict):
    """Saves how far a member is towards today's chest."""
    values = {column: state[name] for name, column in CHEST_PROGRESS.items()}
    await upsert(pool, "minigame_chests", {"gid": gid, "uid": uid}, values)


async def get_chest_streaks(pool, gid: int, uid: int) -> dict:
    """Gives a member's chest streak, best streak and last claim; empty before their first message."""
    row = await chest(pool, gid, uid, "streak, max_streak, last_claimed")
    if not row:
        return {}
    return {
        "streak": row["streak"] or 0,
        "max_streak": row["max_streak"] or 0,
        "last_claimed": row["last_claimed"],
    }


async def upsert_chest_streaks(
    pool, gid: int, uid: int, streak: int, max_streak: int, last_claimed: str
):
    """Saves a member's chest streak, best streak and last claim."""
    values = {"streak": streak, "max_streak": max_streak, "last_claimed": last_claimed}
    await upsert(pool, "minigame_chests", {"gid": gid, "uid": uid}, values)


async def get_chest_counts(pool, gid: int, uid: int) -> list:
    """Gives how many chests of each tier a member opened."""
    row = await chest(pool, gid, uid, "counts")
    return list(row["counts"]) if row and row["counts"] else []


async def upsert_chest_counts(pool, gid: int, uid: int, counts: list):
    """Saves how many chests of each tier a member opened."""
    await upsert(pool, "minigame_chests", {"gid": gid, "uid": uid}, {"counts": counts})


# Sigils


async def get_daily_sigils(pool, uid: int, gid: int, date: str) -> dict:
    """Gives the Sigils a member earned on one day."""
    earnings = await pool.fetchval(
        "SELECT earnings FROM minigame_sigils WHERE uid = $1 AND gid = $2 AND date = $3",
        uid,
        gid,
        date,
    )
    return {"earnings": earnings if earnings is not None else 0}


async def take_sigils(pool, uid: int, gid: int, amount: int, everywhere: bool) -> bool:
    """Takes Sigils in one step, so two spends at once cannot both pass; False if the member has too little."""

    async def pay(conn, server, part):
        await conn.execute(SIGILS_ENTRY, uid, server, today(), -part)

    async with wallet(pool, uid) as conn:
        left = await take(conn, SIGILS_BY_SERVER, uid, gid, amount, everywhere, pay)
    return left is not False


async def subtract_guild_sigils(pool, uid: int, gid: int, amount: int) -> bool:
    """Takes Sigils from a member in this server; False if they have too little."""
    return await take_sigils(pool, uid, gid, amount, False)


async def subtract_global_sigils(pool, uid: int, gid: int, amount: int) -> bool:
    """Takes Sigils from this server first, then from the member's other servers; False if they have too little."""
    return await take_sigils(pool, uid, gid, amount, True)


async def add_sigils(
    pool, uid: int, gid: int, amount: int, channel_id=None, client=None
) -> int:
    """Adds Sigils to today's entry and gives the day's total."""
    earnings = await pool.fetchval(SIGILS_ENTRY, uid, gid, today(), amount)

    if amount > 0 and channel_id is not None and client is not None:
        asyncio.create_task(
            delayed_check_milestones(pool, uid, gid, channel_id, client)
        )

    return earnings


async def parse_boosted_roles(raw: list) -> list:
    """Reads saved "role:bonus" texts into [role ID, bonus] pairs, skipping what cannot be read."""
    result = []
    for entry in raw or []:
        if isinstance(entry, str) and ":" in entry:
            role, bonus = entry.split(":", 1)
            with contextlib.suppress(ValueError):
                result.append([int(role), bonus])
        elif isinstance(entry, list) and len(entry) == 2:
            result.append(entry)
    return result


async def serialize_boosted_roles(roles: list) -> list:
    """Writes [role ID, bonus] pairs as the "role:bonus" texts that are saved."""
    return [
        f"{role[0]}:{role[1]}"
        for role in roles
        if isinstance(role, list) and len(role) == 2
    ]


# Cosmetics


async def get_cosmetics(pool, gid: int, uid: int) -> dict | None:
    """Gives a member's cosmetics row, or None without one."""
    row = await pool.fetchrow(f"SELECT * FROM minigame_cosmetics {MEMBER}", gid, uid)
    return dict(row) if row else None


async def upsert_cosmetics(pool, gid: int, uid: int, **kwargs):
    """Saves the given columns of a member's cosmetics."""
    await upsert(pool, "minigame_cosmetics", {"gid": gid, "uid": uid}, kwargs)


async def add_title_to_cosmetics(pool, gid: int, uid: int, ts: str, name: str):
    """Adds a title to the ones a member owns."""
    row = await get_cosmetics(pool, gid, uid)
    titles = row["titles"] if row else []
    await upsert_cosmetics(pool, gid, uid, titles=[*titles, [ts, name]])


async def add_owned(pool, gid: int, uid: int, column: str, name: str):
    """Adds a name to one list of things a member owns, once."""
    row = await get_cosmetics(pool, gid, uid)
    owned = list(row[column]) if row else []
    if name not in owned:
        owned.append(name)
    await upsert_cosmetics(pool, gid, uid, **{column: owned})


async def add_background_to_cosmetics(pool, gid: int, uid: int, name: str):
    """Adds a background to the ones a member owns."""
    await add_owned(pool, gid, uid, "backgrounds", name)


async def add_frame_to_cosmetics(pool, gid: int, uid: int, name: str):
    """Adds a frame to the ones a member owns."""
    await add_owned(pool, gid, uid, "frames", name)


# Shop items and milestones

CURRENCY = "COALESCE(currency_type, 'guild_mora') AS currency_type"
SHOP_ITEM = f"name, description, cost, multiple, stock, {CURRENCY}, pending_stock_change, pending_scheduled_time"
MILESTONE = f"description, name, threshold, {CURRENCY}"
REWARD = "FROM minigame_rewards WHERE gid = $1 AND item_type = '{kind}'"
MILESTONE_EDITABLE_FIELDS = {"name", "description", "threshold", "currency_type"}


async def rewards(pool, gid: int, kind: str, columns: str) -> list:
    """Gives a server's shop items or milestones in the order they were added, as lists of the columns."""
    statement = f"SELECT {columns} {REWARD.format(kind=kind)} ORDER BY id"
    return [list(row) for row in await pool.fetch(statement, gid)]


async def reward(pool, gid: int, kind: str, columns: str, name: str) -> list | None:
    """Gives one shop item or milestone by name as a list of the columns, or None."""
    statement = f"SELECT {columns} {REWARD.format(kind=kind)} AND name = $2"
    row = await pool.fetchrow(statement, gid, name)
    return list(row) if row else None


async def remove_reward(pool, gid: int, kind: str, name: str) -> None:
    """Deletes a shop item or milestone by name."""
    await pool.execute(f"DELETE {REWARD.format(kind=kind)} AND name = $2", gid, name)


async def update_reward(pool, gid: int, kind: str, name: str, field: str, value):
    """Saves one column of a shop item or milestone."""
    await pool.execute(
        f"UPDATE minigame_rewards SET {field} = $1 WHERE gid = $2 AND item_type = '{kind}' AND name = $3",
        value,
        gid,
        name,
    )


async def get_shop_items(pool, gid: int) -> list:
    """Gives a server's shop items, each in the order of SHOP_ITEM."""
    return await rewards(pool, gid, "shop_item", SHOP_ITEM)


async def get_shop_item_by_name(pool, gid: int, name: str) -> list | None:
    """Gives one shop item in the order of SHOP_ITEM, or None."""
    return await reward(pool, gid, "shop_item", SHOP_ITEM, name)


async def add_shop_item(
    pool,
    gid: int,
    name: str,
    description: str,
    cost: str,
    multiple: bool,
    stock: int,
    currency_type: str = "guild_mora",
):
    """Adds an item to a server's shop."""
    await pool.execute(
        "INSERT INTO minigame_rewards (gid, item_type, name, description, cost, multiple, stock, currency_type) "
        "VALUES ($1, 'shop_item', $2, $3, $4, $5, $6, $7)",
        gid,
        name,
        description,
        cost,
        multiple,
        stock,
        currency_type,
    )


async def remove_shop_item_by_name(pool, gid: int, name: str):
    """Deletes an item from a server's shop."""
    await remove_reward(pool, gid, "shop_item", name)


async def update_shop_item_field(pool, gid: int, name: str, field: str, value):
    """Saves one column of a shop item."""
    await update_reward(pool, gid, "shop_item", name, field, value)


async def update_shop_item_cost(pool, gid: int, name: str, new_cost: str):
    """Saves the cost of a shop item."""
    await update_reward(pool, gid, "shop_item", name, "cost", new_cost)


async def update_shop_item_stock_by_name(pool, gid: int, name: str, new_stock: int):
    """Saves the stock of a shop item."""
    await update_reward(pool, gid, "shop_item", name, "stock", new_stock)


async def add_pending_edit(
    pool, gid: int, name: str, stock_change: str, scheduled_time: float
):
    """Schedules a stock change of a shop item."""
    await pool.execute(
        "UPDATE minigame_rewards SET pending_stock_change = $1, pending_scheduled_time = $2 "
        "WHERE id = (SELECT id FROM minigame_rewards WHERE gid = $3 AND item_type = 'shop_item' AND name = $4 LIMIT 1)",
        stock_change,
        scheduled_time,
        gid,
        name,
    )


def changed_stock(stock: int, change: str) -> Optional[int]:
    """Gives the stock after a scheduled change like "+5", "- 5" or "20", never under 0; None if it cannot be read."""
    relative = change.startswith(("+", "-"))
    try:
        number = int(change)
    except ValueError:
        if not relative:
            return None
        amount = int(change[1:].strip() or 0)
        number = amount if change[0] == "+" else -amount
    if relative:
        number += 0 if stock == -1 else stock
    return max(0, number)


async def process_pending_stock_edits(pool, gid: int) -> int:
    """Applies a server's scheduled stock changes that are due and gives how many it applied."""
    rows = await pool.fetch(
        "SELECT id, stock, pending_stock_change FROM minigame_rewards "
        "WHERE gid = $1 AND item_type = 'shop_item' AND pending_scheduled_time IS NOT NULL AND pending_scheduled_time <= $2",
        gid,
        time.time(),
    )
    processed = 0
    for row in rows:
        stock = changed_stock(row["stock"], row["pending_stock_change"])
        if stock is None:
            continue
        await pool.execute(
            "UPDATE minigame_rewards SET stock = $1, pending_stock_change = NULL, pending_scheduled_time = NULL WHERE id = $2",
            stock,
            row["id"],
        )
        processed += 1
    return processed


async def get_milestones_list(pool, gid: int) -> list:
    """Gives a server's milestones, each as [description, reward, threshold, currency]."""
    return await rewards(pool, gid, "milestone", MILESTONE)


async def get_milestone_by_name(pool, gid: int, name: str) -> list | None:
    """Gives one milestone as [description, reward, threshold, currency], or None."""
    return await reward(pool, gid, "milestone", MILESTONE, name)


async def add_milestone(
    pool,
    gid: int,
    name: str,
    description: str,
    threshold: int,
    currency_type: str = "guild_mora",
):
    """Adds a milestone to a server."""
    await pool.execute(
        "INSERT INTO minigame_rewards (gid, item_type, name, description, threshold, currency_type) "
        "VALUES ($1, 'milestone', $2, $3, $4, $5)",
        gid,
        name,
        description,
        threshold,
        currency_type,
    )


async def remove_milestone_by_name(pool, gid: int, name: str):
    """Deletes a milestone of a server."""
    await remove_reward(pool, gid, "milestone", name)


async def update_milestone_field(pool, gid: int, name: str, field: str, value):
    """Saves one column of a milestone; ValueError for a column that may not be edited."""
    if field not in MILESTONE_EDITABLE_FIELDS:
        raise ValueError(f"Field '{field}' is not editable on a milestone")
    await update_reward(pool, gid, "milestone", name, field, value)


async def update_milestone_threshold(pool, gid: int, name: str, new_threshold: int):
    """Saves the threshold of a milestone."""
    await update_reward(pool, gid, "milestone", name, "threshold", new_threshold)


# Who holds a milestone, kept in step with balances when an admin adds, edits or deletes one

HELD = "FROM minigame_inventory WHERE gid = $1 AND title = $2 AND cost = 0"


def reward_role(guild, reward):
    """Gives the role a milestone rewards, or None when it rewards an item."""
    return guild.get_role(int(reward)) if str(reward).isdigit() else None


async def change_roles(guild, uid: int, take=None, give=None) -> None:
    """Takes one role from a member and gives them another, skipping what Discord refuses."""
    try:
        member = await guild.fetch_member(uid)
    except discord.HTTPException:
        return
    if take and take in member.roles:
        with contextlib.suppress(discord.HTTPException):
            await member.remove_roles(take)
    if give:
        with contextlib.suppress(discord.HTTPException):
            await member.add_roles(give)


async def get_milestone_holders(pool, gid: int, name: str) -> list:
    """Gives the members of a server who hold a milestone's reward."""
    rows = await pool.fetch(f"SELECT DISTINCT uid {HELD} ORDER BY uid", gid, str(name))
    return [row["uid"] for row in rows]


async def remove_milestone_inventory_item(pool, uid: int, gid: int, name: str) -> None:
    """Takes a milestone's reward out of a member's inventory."""
    await pool.execute(f"DELETE {HELD} AND uid = $3", gid, str(name), uid)


async def migrate_milestone_reward(pool, guild, old_name: str, new_name: str) -> None:
    """Moves the holders of a renamed milestone, and their role, over to the new reward."""
    old_name, new_name = str(old_name), str(new_name)
    if old_name == new_name:
        return
    holders = await get_milestone_holders(pool, guild.id, old_name)
    await pool.execute(
        "UPDATE minigame_inventory SET title = $1 WHERE gid = $2 AND title = $3 AND cost = 0",
        new_name,
        guild.id,
        old_name,
    )
    old_role, new_role = reward_role(guild, old_name), reward_role(guild, new_name)
    if old_role == new_role:
        return
    for uid in holders:
        await change_roles(guild, uid, take=old_role, give=new_role)


async def revoke_milestone(pool, guild, uid: int, reward: str, role) -> None:
    """Takes a milestone's reward and its role back from one member."""
    await remove_milestone_inventory_item(pool, uid, guild.id, reward)
    if role:
        await change_roles(guild, uid, take=role)


async def revoke_all_milestone_holders(pool, guild, name: str) -> int:
    """Takes a deleted milestone's reward back from everyone who holds it and gives how many held it."""
    holders = await get_milestone_holders(pool, guild.id, name)
    for uid in holders:
        await revoke_milestone(pool, guild, uid, name, reward_role(guild, name))
    return len(holders)


async def sync_milestone_holders(pool, guild, milestone: list) -> dict:
    """Gives a milestone to members now over its threshold and takes it from those under it; gives both counts."""
    description, reward = milestone[0], str(milestone[1])
    currency_type = milestone[3] if len(milestone) > 3 else "guild_mora"
    try:
        threshold = int(milestone[2])
    except (TypeError, ValueError):
        threshold = 0
    if not reward or reward.startswith("_new_") or threshold <= 0:
        return {"awarded": 0, "revoked": 0}
    over = await get_users_by_currency_threshold(
        pool, guild.id, threshold, currency_type
    )
    qualifying = {uid for uid, _ in over}
    holders = set(await get_milestone_holders(pool, guild.id, reward))
    role = reward_role(guild, reward)
    for uid in qualifying - holders:
        await add_inventory_item(
            pool, uid, guild.id, reward, description, 0, int(time.time()), pinned=False
        )
        if role:
            await change_roles(guild, uid, give=role)
    for uid in holders - qualifying:
        await revoke_milestone(pool, guild, uid, reward, role)
    return {
        "awarded": len(qualifying - holders),
        "revoked": len(holders - qualifying),
    }


async def delayed_check_milestones(
    pool: asyncpg.Pool, userID, guildID, channelID, client
):
    """Checks a member's milestones a second later, once what they earned is saved."""
    await asyncio.sleep(1)
    await check_milestones(pool, userID, guildID, channelID, client)


async def check_milestones(pool: asyncpg.Pool, user_id, guild_id, channel_id, client):
    """Gives a member every milestone they reached and do not hold, with its role, and announces it."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        channel_id = None
    milestones = await get_milestones_list(pool, guild_id)
    if not milestones:
        return
    held = {item[0] for item in await get_user_inventory(pool, user_id, guild_id)}
    balances = {}
    for description, reward, threshold, currency_type in milestones:
        if reward in held:
            continue
        if currency_type not in balances:
            balances[currency_type] = await balance(
                pool, currency_type, user_id, guild_id
            )
        if balances[currency_type] < threshold:
            continue
        await add_inventory_item(
            pool, user_id, guild_id, reward, description, 0, int(time.time())
        )
        is_role = str(reward).isdigit()
        guild = client.get_guild(guild_id)
        role = guild and is_role and guild.get_role(int(reward))
        if role:
            await change_roles(guild, user_id, give=role)
        channel = client.get_channel(channel_id) if channel_id else None
        if not channel:
            continue
        from commands.Events.event import userAndTitle

        name = await userAndTitle(user_id, guild_id, pool)
        earned = f"<@&{reward}>" if is_role else reward
        await channel.send(
            embed=discord.Embed(
                title="🏆 Milestone Achieved!",
                description=(
                    f"Congratulations, {name}! \n"
                    f"You've reached {get_currency_display(currency_type)} `{threshold:,}` and earned **{earned}**\n"
                ),
                color=discord.Color.gold(),
            )
        )


# Settings

SETTINGS_FALLBACK = {
    "channel_id": 0,
    "mora_multiplier": 1.00,
    "minigames_enabled": False,
    "minigames_list": [],
    "minigames_frequency": 50,
    "chests_enabled": False,
    "chat_enabled": False,
    "chat_range": [19, 25],
    "chat_boosted_roles": [],
    "chat_msg_range": [15, 20],
}

GUILD_SETTINGS_FALLBACK = {
    "chests_base_upgrade_chances": 4,
    "chests_tier_names": ["Common", "Exquisite", "Precious", "Luxurious"],
    "chests_tier_rewards": [2500, 7500, 15000, 30000],
    "chests_upgrade_chances": [0.30, 0.15, 0.20],
    "chests_streak_bonus": 100,
    "chests_max_streak_bonus": 10000,
    "chests_spawn_req": [4, 6],
    "chests_emotes": [
        "<a:common:1371641883121680465>",
        "<a:exquisite:1371641856344985620>",
        "<a:precious:1371641871452995689>",
        "<a:luxurious:1371641841338023976>",
    ],
    "chests_icons": [
        "https://i.imgur.com/2kOfLSC.png",
        "https://i.imgur.com/DBPQSAu.png",
        "https://i.imgur.com/zxOlrCo.png",
        "https://i.imgur.com/5nWwRdc.png",
    ],
    "chat_max_cap": 60,
}
GUILD_LISTS = (
    "chests_tier_names",
    "chests_tier_rewards",
    "chests_spawn_req",
    "chests_emotes",
    "chests_icons",
)


async def get_channel_settings(pool, channel_id: int) -> dict:
    """Gives a channel's minigame settings, the defaults for a channel with none."""
    row = await pool.fetchrow(
        "SELECT * FROM minigame_settings WHERE channel_id = $1", channel_id
    )
    return dict(row) if row else dict(SETTINGS_FALLBACK, channel_id=channel_id)


async def get_channel_mora_multiplier(pool, channel_id: int) -> float:
    """Gives the Mora multiplier of a channel."""
    settings = await get_channel_settings(pool, channel_id)
    return float(settings.get("mora_multiplier", 1.00))


async def upsert_channel_settings(pool, channel_id: int, **kwargs):
    """Saves the given minigame settings of a channel."""
    await upsert(pool, "minigame_settings", {"channel_id": channel_id}, kwargs)


async def get_guild_settings(pool, guild_id: int) -> dict:
    """Gives a server's chest and chat settings, the defaults for a server with none."""
    row = await pool.fetchrow(
        "SELECT * FROM minigame_guild_settings WHERE gid = $1", guild_id
    )
    if not row:
        return dict(GUILD_SETTINGS_FALLBACK)
    settings = {key: row[key] for key in GUILD_SETTINGS_FALLBACK}
    settings.update({key: list(row[key]) for key in GUILD_LISTS})
    settings["chests_upgrade_chances"] = [
        float(chance) for chance in row["chests_upgrade_chances"] or []
    ]
    return settings


async def upsert_guild_settings(pool, guild_id: int, **kwargs):
    """Saves the given chest and chat settings of a server."""
    await upsert(pool, "minigame_guild_settings", {"gid": guild_id}, kwargs)


async def get_channel_chest_config(pool, guild_id: int, channel_id: int) -> dict:
    """Gives whether chests are on in a channel, with the server's chest settings."""
    channel = await get_channel_settings(pool, channel_id)
    config = await get_guild_settings(pool, guild_id)
    del config["chat_max_cap"]
    return {"chests_enabled": channel.get("chests_enabled", False), **config}


class TierRewardsView(discord.ui.View):
    def __init__(
        self,
        free_embed=discord.Embed(title="Button expired", color=discord.Color.red()),
        elite_embed=discord.Embed(color=0xFF0000),
    ):
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
            await interaction.response.send_message(
                embeds=[self.free_embed, self.elite_embed], ephemeral=True
            )
        elif self.free_embed.title is not None:
            await interaction.response.send_message(
                embeds=[self.free_embed], ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{CONFUSED_EMOTE} You did not earn any tiers from this XP gain."
                ),
                ephemeral=True,
            )

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_xp_quest_info_view_new",
        emoji=CONFUSED_EMOTE,
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
        if (
            str(interaction.user.id) not in interaction.message.content
            and str(interaction.user.id)
            not in interaction.message.embeds[0].description
        ):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{NO_EMOTE} This isn't your notification!",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
        else:
            await interaction.message.delete()


async def create_tables(pool) -> None:
    """Creates the minigame tables that are missing."""
    await pool.execute(SCHEMA)


async def setup(bot) -> None:
    await create_tables(bot.pool)
