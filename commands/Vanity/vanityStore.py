"""Vanity role settings in Postgres: who is watched, the role, the thank-you.

A `vanity_thanks` row whose `dm` is NULL is a message kept while thanks are off."""

TABLES = (
    "CREATE TABLE IF NOT EXISTS vanity_enabled (guild_id BIGINT PRIMARY KEY)",
    """CREATE TABLE IF NOT EXISTS vanity_roles (
        guild_id BIGINT PRIMARY KEY,
        link TEXT,
        role_id BIGINT,
        log_channel_id BIGINT
    )""",
    """CREATE TABLE IF NOT EXISTS vanity_thanks (
        guild_id BIGINT PRIMARY KEY,
        channel_id BIGINT,
        dm BOOLEAN,
        content TEXT,
        title TEXT,
        description TEXT,
        color TEXT,
        image TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS vanity_thanks_cooldown (
        guild_id BIGINT,
        user_id BIGINT,
        thanked_at BIGINT NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    )""",
)


async def create(pool):
    """Creates the tables that are not there yet."""
    for table in TABLES:
        await pool.execute(table)


async def enable(pool, guild_id):
    """Has the bot start watching a server's statuses."""
    await pool.execute(
        "INSERT INTO vanity_enabled (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
        guild_id,
    )


async def enabled(pool):
    """Gives the ids of the enabled servers, with or without role settings."""
    rows = await pool.fetch("SELECT guild_id FROM vanity_enabled")
    return [row["guild_id"] for row in rows]


async def set_roles(pool, guild_id, link, role_id, log_channel_id):
    """Saves which link earns which role, and where it is logged."""
    await pool.execute(
        """INSERT INTO vanity_roles (guild_id, link, role_id, log_channel_id)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (guild_id) DO UPDATE SET link = $2, role_id = $3,
            log_channel_id = $4""",
        guild_id,
        link,
        role_id,
        log_channel_id,
    )


async def has_roles(pool, guild_id):
    """Says whether a server has role settings, enabled or not."""
    return await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM vanity_roles WHERE guild_id = $1)", guild_id
    )


async def watched(pool):
    """Gives the role settings of every enabled server that has them."""
    return await pool.fetch(
        """SELECT guild_id, link, role_id, log_channel_id
        FROM vanity_enabled JOIN vanity_roles USING (guild_id)"""
    )


async def drop_roles(pool, guild_id):
    """Stops watching a server whose role is gone; its thank-you is kept."""
    await pool.execute(
        """WITH roles AS (DELETE FROM vanity_roles WHERE guild_id = $1)
        DELETE FROM vanity_enabled WHERE guild_id = $1""",
        guild_id,
    )


async def disable(pool, guild_id):
    """Forgets a server's settings; False if it had no role settings."""
    return await pool.fetchval(
        """WITH roles AS (DELETE FROM vanity_roles WHERE guild_id = $1 RETURNING 1),
            thanks AS (DELETE FROM vanity_thanks WHERE guild_id = $1),
            enabled AS (
                DELETE FROM vanity_enabled WHERE guild_id = $1 AND EXISTS (TABLE roles)
            )
        SELECT EXISTS (TABLE roles)""",
        guild_id,
    )


async def set_thanks(pool, guild_id, channel_id, dm):
    """Saves where the thank-you goes, keeping any message already written."""
    await pool.execute(
        """INSERT INTO vanity_thanks (guild_id, channel_id, dm) VALUES ($1, $2, $3)
        ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, dm = $3""",
        guild_id,
        channel_id,
        dm,
    )


async def stop_thanks(pool, guild_id):
    """Turns the thank-you off, keeping its message; False if it was not on."""
    return bool(
        await pool.fetchval(
            """UPDATE vanity_thanks SET channel_id = NULL, dm = NULL
            WHERE guild_id = $1 AND dm IS NOT NULL RETURNING TRUE""",
            guild_id,
        )
    )


async def set_message(pool, guild_id, content, title, description, color, image):
    """Saves a server's thank-you message, whether or not thanks are on."""
    await pool.execute(
        """INSERT INTO vanity_thanks
            (guild_id, content, title, description, color, image)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (guild_id) DO UPDATE SET content = $2, title = $3,
            description = $4, color = $5, image = $6""",
        guild_id,
        content,
        title,
        description,
        color,
        image,
    )


async def thanks(pool, guild_id):
    """Gives a server's thank-you settings, or None if thanks are off."""
    return await pool.fetchrow(
        """SELECT guild_id, channel_id, dm, content, title, description, color, image
        FROM vanity_thanks WHERE guild_id = $1 AND dm IS NOT NULL""",
        guild_id,
    )


async def claim_thanks(pool, guild_id, user_id, now, cooldown):
    """Starts a member's cooldown; False if they were thanked within it."""
    return bool(
        await pool.fetchval(
            """INSERT INTO vanity_thanks_cooldown (guild_id, user_id, thanked_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET thanked_at = $3
                WHERE vanity_thanks_cooldown.thanked_at < $3 - $4::bigint
            RETURNING TRUE""",
            guild_id,
            user_id,
            now,
            cooldown,
        )
    )


async def setup(bot):
    pass
