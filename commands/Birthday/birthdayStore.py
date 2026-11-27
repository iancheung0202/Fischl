"""Birthdays and the servers that wish them, kept in Postgres.

`display_utc_date` is the start of the birthday in UTC, written `MM-DD HH:MM`;
the wishes go out when the clock reads exactly that. A member's newest record
gets the highest id, so setting a birthday again moves it to the end, as it
did in the old list."""

import contextlib

TABLES = (
    """CREATE TABLE IF NOT EXISTS birthdays (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL UNIQUE,
        month INT NOT NULL,
        day INT NOT NULL,
        timezone TEXT NOT NULL,
        display_utc_date TEXT NOT NULL,
        fav_character TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS birthdays_date
        ON birthdays (display_utc_date text_pattern_ops)""",
    """CREATE TABLE IF NOT EXISTS birthday_servers (
        id BIGSERIAL PRIMARY KEY,
        server_id BIGINT NOT NULL UNIQUE,
        channel_id BIGINT NOT NULL,
        webhook_id BIGINT NOT NULL,
        role_id BIGINT NOT NULL,
        create_thread BOOLEAN NOT NULL
    )""",
)


async def create(pool):
    """Creates the tables that are not there yet."""
    for table in TABLES:
        await pool.execute(table)


@contextlib.asynccontextmanager
async def locked(pool, key):
    """Gives a connection in a transaction that holds the member or server until it ends."""
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock($1)", key)
        yield connection


async def save(pool, user_id, month, day, timezone, display_utc_date, character):
    """Saves a member's birthday in place of the one they had."""
    async with locked(pool, user_id) as connection:
        await connection.execute("DELETE FROM birthdays WHERE user_id = $1", user_id)
        await connection.execute(
            """INSERT INTO birthdays
            (user_id, month, day, timezone, display_utc_date, fav_character)
            VALUES ($1, $2, $3, $4, $5, $6)""",
            user_id,
            month,
            day,
            timezone,
            display_utc_date,
            character,
        )


async def find(pool, user_id):
    """Gives a member's birthday, or None."""
    return await pool.fetchrow("SELECT * FROM birthdays WHERE user_id = $1", user_id)


async def remove(pool, user_id):
    """Forgets a member's birthday; False if there was none."""
    return await pool.execute("DELETE FROM birthdays WHERE user_id = $1", user_id) != (
        "DELETE 0"
    )


async def everyone(pool):
    """Gives every birthday, oldest record first."""
    return await pool.fetch("SELECT * FROM birthdays ORDER BY id")


async def due(pool, starting, started):
    """Gives the birthdays starting at one of the `MM-DD HH:MM` or started in one of the hours `MM-DD HH:`."""
    return await pool.fetch(
        """SELECT * FROM birthdays
        WHERE display_utc_date = ANY($1::text[]) OR display_utc_date LIKE ANY($2::text[])
        ORDER BY id""",
        starting,
        [hour + "%" for hour in started],
    )


async def enable(pool, server_id, channel_id, webhook_id, role_id, create_thread):
    """Saves where and how a server wishes, in place of what it had."""
    async with locked(pool, server_id) as connection:
        await connection.execute(
            "DELETE FROM birthday_servers WHERE server_id = $1", server_id
        )
        await connection.execute(
            """INSERT INTO birthday_servers
            (server_id, channel_id, webhook_id, role_id, create_thread)
            VALUES ($1, $2, $3, $4, $5)""",
            server_id,
            channel_id,
            webhook_id,
            role_id,
            create_thread,
        )


async def disable(pool, server_id):
    """Turns a server's wishes off; False if they were not on."""
    return await pool.execute(
        "DELETE FROM birthday_servers WHERE server_id = $1", server_id
    ) != ("DELETE 0")


async def server(pool, server_id):
    """Gives a server's wish settings, or None."""
    return await pool.fetchrow(
        "SELECT * FROM birthday_servers WHERE server_id = $1", server_id
    )


async def servers(pool):
    """Gives every server's wish settings, oldest first."""
    return await pool.fetch("SELECT * FROM birthday_servers ORDER BY id")


async def setup(bot):
    pass
