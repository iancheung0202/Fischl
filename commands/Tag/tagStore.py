"""Tag role settings, kept in Postgres."""

TABLES = (
    "CREATE TABLE IF NOT EXISTS tag_enabled (guild_id BIGINT PRIMARY KEY)",
    """CREATE TABLE IF NOT EXISTS tag_roles (
        guild_id BIGINT PRIMARY KEY,
        tag_guild_id BIGINT,
        role_id BIGINT,
        log_channel_id BIGINT
    )""",
    """CREATE TABLE IF NOT EXISTS tag_thanks (
        guild_id BIGINT PRIMARY KEY,
        channel_id BIGINT,
        dm BOOLEAN NOT NULL,
        content TEXT,
        title TEXT,
        description TEXT,
        color TEXT,
        image TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS tag_thanks_cooldown (
        guild_id BIGINT,
        user_id BIGINT,
        thanked_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    )""",
)


async def create(pool):
    """Creates the tables that are not there yet."""
    for table in TABLES:
        await pool.execute(table)


async def enable(pool, guild_id):
    """Has the minute check start watching a server."""
    await pool.execute(
        "INSERT INTO tag_enabled (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
        guild_id,
    )


async def set_roles(pool, guild_id, tag_guild_id, role_id, log_channel_id):
    """Saves which tag earns which role, and where it is logged."""
    await pool.execute(
        """INSERT INTO tag_roles (guild_id, tag_guild_id, role_id, log_channel_id)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (guild_id) DO UPDATE SET tag_guild_id = $2, role_id = $3,
            log_channel_id = $4""",
        guild_id,
        tag_guild_id,
        role_id,
        log_channel_id,
    )


async def watched(pool):
    """Gives the role settings of every enabled server that has them."""
    return await pool.fetch(
        """SELECT guild_id, tag_guild_id, role_id, log_channel_id
        FROM tag_enabled JOIN tag_roles USING (guild_id)"""
    )


async def disable(pool, guild_id):
    """Forgets a server's settings; False if it had none."""
    return await pool.fetchval(
        """WITH roles AS (DELETE FROM tag_roles WHERE guild_id = $1 RETURNING 1),
            thanks AS (DELETE FROM tag_thanks WHERE guild_id = $1 RETURNING 1),
            found AS (SELECT 1 FROM roles UNION ALL SELECT 1 FROM thanks LIMIT 1),
            enabled AS (
                DELETE FROM tag_enabled WHERE guild_id = $1 AND EXISTS (TABLE found)
            )
        SELECT EXISTS (TABLE found)""",
        guild_id,
    )


async def set_thanks(pool, guild_id, channel_id, dm):
    """Saves where the thank-you goes, keeping any message already written."""
    await pool.execute(
        """INSERT INTO tag_thanks (guild_id, channel_id, dm) VALUES ($1, $2, $3)
        ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, dm = $3""",
        guild_id,
        channel_id,
        dm,
    )


async def set_message(pool, guild_id, content, title, description, color, image):
    """Saves the thank-you message of a server that has thanks set up."""
    await pool.execute(
        """UPDATE tag_thanks SET content = $2, title = $3, description = $4,
            color = $5, image = $6 WHERE guild_id = $1""",
        guild_id,
        content,
        title,
        description,
        color,
        image,
    )


async def thanks(pool, guild_id):
    """Gives a server's thank-you settings, or None."""
    return await pool.fetchrow(
        """SELECT guild_id, channel_id, dm, content, title, description, color, image
        FROM tag_thanks WHERE guild_id = $1""",
        guild_id,
    )


async def claim_thanks(pool, guild_id, user_id, now, cooldown):
    """Starts a member's cooldown; False if they were thanked within it."""
    return bool(
        await pool.fetchval(
            """INSERT INTO tag_thanks_cooldown (guild_id, user_id, thanked_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET thanked_at = $3
                WHERE tag_thanks_cooldown.thanked_at <= $3 - $4::double precision
            RETURNING TRUE""",
            guild_id,
            user_id,
            now,
            cooldown,
        )
    )


async def setup(bot):
    await create(bot.pool)
