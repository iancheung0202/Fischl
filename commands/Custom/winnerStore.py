"""Each server's current weekly leaderboard winner, kept in Postgres."""

TABLE = """CREATE TABLE IF NOT EXISTS weekly_winners (
    server_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL
)"""


async def create(pool):
    """Creates the table if it is not there yet."""
    await pool.execute(TABLE)


async def winner(pool, server_id):
    """Gives the id of the server's current winner, or None."""
    return await pool.fetchval(
        "SELECT user_id FROM weekly_winners WHERE server_id = $1", server_id
    )


async def crown(pool, server_id, user_id):
    """Saves the server's new winner in place of the old one."""
    await pool.execute(
        """INSERT INTO weekly_winners (server_id, user_id) VALUES ($1, $2)
        ON CONFLICT (server_id) DO UPDATE SET user_id = $2""",
        server_id,
        user_id,
    )


async def setup(bot):
    pass
