"""Sticky messages in Postgres: which channels are on and what is stuck where.

A channel can hold more than one message; the oldest one (lowest id) is sent
again next. `times` is how often the old list named a channel: each disable
takes one off, as it did when the list was a file."""

import contextlib

TABLES = (
    """CREATE TABLE IF NOT EXISTS sticky_enabled (
        channel_id BIGINT PRIMARY KEY,
        times INT NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS sticky_messages (
        id BIGSERIAL PRIMARY KEY,
        channel_id BIGINT NOT NULL,
        message_id BIGINT NOT NULL,
        content TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS sticky_messages_channel
        ON sticky_messages (channel_id, id)""",
)
OLDEST = "SELECT min(id) FROM sticky_messages WHERE channel_id = $1"


async def create(pool):
    """Creates the tables that are not there yet."""
    for table in TABLES:
        await pool.execute(table)


@contextlib.asynccontextmanager
async def locked(pool, channel_id):
    """Gives a connection in a transaction that holds the channel until it ends."""
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock($1)", channel_id)
        yield connection


async def enable(pool, channel_id):
    """Has the bot start watching a channel's messages."""
    async with locked(pool, channel_id) as connection:
        await connection.execute(
            """INSERT INTO sticky_enabled (channel_id) VALUES ($1)
            ON CONFLICT DO NOTHING""",
            channel_id,
        )


async def leave(pool, channel_id):
    """Takes a channel off the watched list once."""
    async with locked(pool, channel_id) as connection:
        await connection.execute(
            "UPDATE sticky_enabled SET times = times - 1 WHERE channel_id = $1",
            channel_id,
        )
        await connection.execute(
            "DELETE FROM sticky_enabled WHERE channel_id = $1 AND times <= 0",
            channel_id,
        )


async def enabled(pool):
    """Gives the ids of the watched channels."""
    rows = await pool.fetch("SELECT channel_id FROM sticky_enabled")
    return {row["channel_id"] for row in rows}


async def add(pool, channel_id, message_id, content):
    """Saves a message as the newest one stuck to a channel."""
    await pool.execute(
        """INSERT INTO sticky_messages (channel_id, message_id, content)
        VALUES ($1, $2, $3)""",
        channel_id,
        message_id,
        content,
    )


async def oldest(pool, channel_id):
    """Gives the channel's message that is sent again next, or None."""
    return await pool.fetchrow(
        f"SELECT id, message_id, content FROM sticky_messages WHERE id = ({OLDEST})",
        channel_id,
    )


async def take(pool, channel_id):
    """Forgets the channel's oldest message; gives its message id, or None."""
    async with locked(pool, channel_id) as connection:
        return await connection.fetchval(
            f"DELETE FROM sticky_messages WHERE id = ({OLDEST}) RETURNING message_id",
            channel_id,
        )


async def move(pool, row_id, channel_id, message_id, content):
    """Saves where a message was sent again; False if it was taken meanwhile."""
    async with locked(pool, channel_id) as connection:
        return bool(
            await connection.fetchval(
                """WITH gone AS (
                    DELETE FROM sticky_messages WHERE id = $1 RETURNING 1
                )
                INSERT INTO sticky_messages (channel_id, message_id, content)
                SELECT $2, $3, $4 FROM gone RETURNING TRUE""",
                row_id,
                channel_id,
                message_id,
                content,
            )
        )


async def channels(pool):
    """Gives the channel id of every stuck message, oldest first."""
    rows = await pool.fetch("SELECT channel_id FROM sticky_messages ORDER BY id")
    return [row["channel_id"] for row in rows]


async def setup(bot):
    pass
