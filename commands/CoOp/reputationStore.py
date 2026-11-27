"""Reputation settings, role rewards and members' points, kept in Postgres."""

TABLES = (
    """CREATE TABLE IF NOT EXISTS reputation_servers (
        guild_id BIGINT PRIMARY KEY,
        max_rep BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS reputation_roles (
        guild_id BIGINT,
        role_id BIGINT,
        cost BIGINT NOT NULL,
        PRIMARY KEY (guild_id, role_id)
    )""",
    """CREATE TABLE IF NOT EXISTS reputation_points (
        guild_id BIGINT,
        user_id BIGINT,
        points BIGINT NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    )""",
)
GIVE = """INSERT INTO reputation_points (guild_id, user_id, points) VALUES ($1, $2, $3)
    ON CONFLICT (guild_id, user_id)
    DO UPDATE SET points = reputation_points.points + EXCLUDED.points
    RETURNING points"""


async def create(pool):
    """Creates the tables that are not there yet."""
    for table in TABLES:
        await pool.execute(table)


async def max_rep(pool, guild_id):
    """Gives the most reps a member can give at once, or None with the system off."""
    return await pool.fetchval(
        "SELECT max_rep FROM reputation_servers WHERE guild_id = $1", guild_id
    )


async def enable(pool, guild_id, most):
    """Turns the system on or changes its limit; False if it was on already."""
    return await pool.fetchval(
        """INSERT INTO reputation_servers (guild_id, max_rep) VALUES ($1, $2)
        ON CONFLICT (guild_id) DO UPDATE SET max_rep = EXCLUDED.max_rep
        RETURNING xmax = 0""",
        guild_id,
        most,
    )


async def disable(pool, guild_id):
    """Turns the system off and drops its role rewards; False if it was not on."""
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(
            "DELETE FROM reputation_roles WHERE guild_id = $1", guild_id
        )
        return await connection.execute(
            "DELETE FROM reputation_servers WHERE guild_id = $1", guild_id
        ) != ("DELETE 0")


async def rewards(pool, guild_id):
    """Gives a server's role rewards as {role id: cost}, cheapest first."""
    rows = await pool.fetch(
        "SELECT role_id, cost FROM reputation_roles WHERE guild_id = $1 ORDER BY cost, role_id",
        guild_id,
    )
    return {row["role_id"]: row["cost"] for row in rows}


async def add_reward(pool, guild_id, role_id, cost):
    """Saves a role reward; False if the role was one already."""
    return (
        await pool.execute(
            """INSERT INTO reputation_roles (guild_id, role_id, cost) VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING""",
            guild_id,
            role_id,
            cost,
        )
        != ("INSERT 0 0")
    )


async def remove_reward(pool, guild_id, role_id):
    """Drops a role reward; False if the role was not one."""
    return await pool.execute(
        "DELETE FROM reputation_roles WHERE guild_id = $1 AND role_id = $2",
        guild_id,
        role_id,
    ) != ("DELETE 0")


async def points(pool, guild_id, user_id):
    """Gives a member's reps in a server, 0 if they have none."""
    return (
        await pool.fetchval(
            "SELECT points FROM reputation_points WHERE guild_id = $1 AND user_id = $2",
            guild_id,
            user_id,
        )
        or 0
    )


async def give(pool, guild_id, user_id, amount):
    """Adds reps to a member in one step and gives their new total."""
    return await pool.fetchval(GIVE, guild_id, user_id, amount)


async def top(pool, guild_id, count):
    """Gives a server's members with the most reps as (user id, points) rows."""
    return await pool.fetch(
        """SELECT user_id, points FROM reputation_points WHERE guild_id = $1
        ORDER BY points DESC, user_id LIMIT $2""",
        guild_id,
        count,
    )


async def setup(bot):
    pass
