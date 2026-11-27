"""Co-op settings, sticky request panels and members' game UIDs, kept in Postgres.

A UID is kept as the member typed it, so it may not be a number."""

TABLES = (
    """CREATE TABLE IF NOT EXISTS coop_servers (
        id BIGSERIAL PRIMARY KEY,
        server_id BIGINT NOT NULL UNIQUE,
        channel_id BIGINT NOT NULL,
        na_role_id BIGINT NOT NULL,
        eu_role_id BIGINT NOT NULL,
        asia_role_id BIGINT NOT NULL,
        sar_role_id BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS coop_panels (
        channel_id BIGINT PRIMARY KEY,
        message_id BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS coop_uids (
        user_id BIGINT PRIMARY KEY,
        uid TEXT NOT NULL
    )""",
)


async def create(pool):
    """Creates the tables that are not there yet."""
    for table in TABLES:
        await pool.execute(table)


async def server(pool, server_id):
    """Gives a server's co-op channel and helper roles, or None."""
    return await pool.fetchrow(
        "SELECT * FROM coop_servers WHERE server_id = $1", server_id
    )


async def enable(pool, server_id, channel_id, na, eu, asia, sar):
    """Saves a server's co-op channel and helper roles; False if it had them already."""
    return (
        await pool.execute(
            """INSERT INTO coop_servers
        (server_id, channel_id, na_role_id, eu_role_id, asia_role_id, sar_role_id)
        VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (server_id) DO NOTHING""",
            server_id,
            channel_id,
            na,
            eu,
            asia,
            sar,
        )
        != ("INSERT 0 0")
    )


async def disable(pool, server_id):
    """Turns co-op off in a server; False if it was not on."""
    return await pool.execute(
        "DELETE FROM coop_servers WHERE server_id = $1", server_id
    ) != ("DELETE 0")


async def take_panel(pool, channel_id):
    """Forgets a channel's sticky panel and gives its message, or None."""
    return await pool.fetchval(
        "DELETE FROM coop_panels WHERE channel_id = $1 RETURNING message_id",
        channel_id,
    )


async def stick_panel(pool, channel_id, message_id):
    """Saves the message that is a channel's sticky panel."""
    await pool.execute(
        """INSERT INTO coop_panels VALUES ($1, $2)
        ON CONFLICT (channel_id) DO UPDATE SET message_id = $2""",
        channel_id,
        message_id,
    )


async def uid(pool, user_id):
    """Gives the game UID a member last used, or None."""
    return await pool.fetchval("SELECT uid FROM coop_uids WHERE user_id = $1", user_id)


async def save_uid(pool, user_id, uid):
    """Saves the game UID a member used."""
    await pool.execute(
        """INSERT INTO coop_uids VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET uid = $2""",
        user_id,
        uid,
    )


async def setup(bot):
    pass
