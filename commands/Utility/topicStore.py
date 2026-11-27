"""The chat topics `/topic` picks from, kept in Postgres."""

TABLE = """CREATE TABLE IF NOT EXISTS topics (
    id BIGSERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    suggester_id BIGINT NOT NULL
)"""


async def create(pool):
    """Creates the table if it is not there yet."""
    await pool.execute(TABLE)


async def add(pool, query, suggester_id):
    """Saves a topic and who suggested it."""
    await pool.execute(
        "INSERT INTO topics (query, suggester_id) VALUES ($1, $2)", query, suggester_id
    )


async def has(pool, query):
    """Says whether a topic with exactly this text is saved."""
    return await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM topics WHERE query = $1)", query
    )


async def pick(pool):
    """Gives the text of one topic, chosen at random."""
    return await pool.fetchval("SELECT query FROM topics ORDER BY random() LIMIT 1")


async def queries(pool):
    """Gives the text of every topic, oldest first."""
    rows = await pool.fetch("SELECT query FROM topics ORDER BY id")
    return [row["query"] for row in rows]


async def setup(bot):
    pass
