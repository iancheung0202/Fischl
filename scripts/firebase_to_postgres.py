"""Copies a system's data from Firebase to Postgres, once, at the move.

Run from the repo root, with the bot stopped and the old enabled file already
moved out of the repo:
    TAG_ENABLED_FILE=/path/to/tagEnabledGuilds.py python3 scripts/firebase_to_postgres.py tag
    VANITY_ENABLED_FILE=/path/to/enabledGuilds.py python3 scripts/firebase_to_postgres.py vanity
Firebase is only read, so the old copy stays as it was. Each system saves what
it read to `<system>-export.json` next to that file, checks every row it wrote
and refuses to run once its tables hold data."""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())


def by_server(records):
    """Gives {server id: record}, keeping the first record as the bot did."""
    found = {}
    for record in (records or {}).values():
        if found.setdefault(record["Server ID"], record) is not record:
            print(f"skipped a later record the bot never read: {record}")
    return found


def read_list(path, name):
    """Reads the `name = [...]` list from a file the bot used to rewrite."""
    with open(path) as file:
        for line in file:
            if line.startswith(f"{name} ="):
                items = line.split("=")[1].strip(" []\n").split(",")
                return [int(item) for item in items if item.strip()]
    raise SystemExit(f"{path} has no {name} list")


def running(cooldowns, now, cooldown):
    """Gives {(server, member): time thanked} for cooldowns still running."""
    live = {}
    for record in (cooldowns or {}).values():
        key = (record["Guild"], record["User"])
        if now - record["Timestamp"] < cooldown:
            live[key] = max(live.get(key, 0), record["Timestamp"])
    return live


TAG_PATHS = ("Tag Roles", "Tag Thanks", "Tag Thanks Message", "Tag Thanks Cooldown")
TAG_TABLES = ("tag_enabled", "tag_roles", "tag_thanks", "tag_thanks_cooldown")
MESSAGE = ("Message Content", "Title", "Description", "Color", "Image Link")


def export(folder, name, db, paths, **extra):
    """Reads the paths from Firebase and saves them, as read, to a file."""
    data = {path: db.reference(f"/{path}").get() or {} for path in paths}
    with open(os.path.join(folder, f"{name}-export.json"), "w") as file:
        json.dump({**data, **extra}, file)
    for path, records in data.items():
        print(f"{path}: {len(records)} records in Firebase")
    return data


async def tag(pool, db, enabled_file=None):
    """Tag roles: enabled servers, role settings, thank-you settings, cooldowns."""
    from commands.Tag import tagStore as store
    from utils.config import THANKS_COOLDOWN

    await store.create(pool)
    for table in TAG_TABLES:
        if await pool.fetchval(f"SELECT count(*) FROM {table}"):
            raise SystemExit(f"{table} already has rows; Postgres is the live copy")
    enabled_file = enabled_file or os.environ["TAG_ENABLED_FILE"]
    enabled = set(read_list(enabled_file, "enabledGuilds"))
    data = export(
        os.path.dirname(enabled_file), "tag", db, TAG_PATHS, enabled=sorted(enabled)
    )
    roles, thanks, messages = (by_server(data[path]) for path in TAG_PATHS[:3])
    live = running(data[TAG_PATHS[3]], time.time(), THANKS_COOLDOWN)
    for guild_id in set(messages) - set(thanks):
        print(f"skipped a thank-you message the bot never read, server {guild_id}")
        del messages[guild_id]
    whole_ids(roles, thanks, live)

    for guild_id in enabled:
        await store.enable(pool, guild_id)
    for guild_id, record in roles.items():
        await store.set_roles(
            pool,
            guild_id,
            record.get("Tag Server ID"),
            record.get("Role ID"),
            record.get("Log Channel ID"),
        )
    for guild_id, record in thanks.items():
        await store.set_thanks(pool, guild_id, record.get("Channel ID"), record["DM"])
    for guild_id, record in messages.items():
        await store.set_message(
            pool, guild_id, *(record.get(field, "") for field in MESSAGE)
        )
    await pool.executemany(
        """INSERT INTO tag_thanks_cooldown (guild_id, user_id, thanked_at)
        VALUES ($1, $2, $3)""",
        [(*key, at) for key, at in live.items()],
    )
    await check_tag(pool, enabled, roles, thanks, messages, live)


def whole_ids(roles, thanks, live):
    """Stops if an id is not a whole number; a float would be rounded."""
    for record in roles.values():
        if isinstance(record.get("Tag Server ID"), str):
            record["Tag Server ID"] = int(record["Tag Server ID"])
    ids = [
        record.get(field)
        for records, fields in (
            (roles, ("Server ID", "Tag Server ID", "Role ID", "Log Channel ID")),
            (thanks, ("Server ID", "Channel ID")),
        )
        for record in records.values()
        for field in fields
    ]
    ids += [value for key in live for value in key]
    bad = [value for value in ids if value is not None and type(value) is not int]
    if bad:
        raise SystemExit(f"ids that are not whole numbers: {bad}")


async def same(pool, query, expected, what):
    """Stops unless the query gives exactly the expected rows."""
    if {tuple(row) for row in await pool.fetch(query)} != set(expected):
        raise SystemExit(f"{what} differ from Firebase")


async def check_tag(pool, enabled, roles, thanks, messages, live):
    """Reads every row back and stops if one differs from Firebase."""
    await same(
        pool,
        "SELECT guild_id FROM tag_enabled",
        [(guild_id,) for guild_id in enabled],
        "enabled servers",
    )
    await same(
        pool,
        "SELECT guild_id, tag_guild_id, role_id, log_channel_id FROM tag_roles",
        [
            (
                guild_id,
                r.get("Tag Server ID"),
                r.get("Role ID"),
                r.get("Log Channel ID"),
            )
            for guild_id, r in roles.items()
        ],
        "role settings",
    )
    await same(
        pool,
        """SELECT guild_id, channel_id, dm, content, title, description, color, image
        FROM tag_thanks""",
        [
            (
                guild_id,
                t.get("Channel ID"),
                t["DM"],
                *(
                    messages[guild_id].get(field, "") if guild_id in messages else None
                    for field in MESSAGE
                ),
            )
            for guild_id, t in thanks.items()
        ],
        "thank-you settings",
    )
    await same(
        pool,
        "SELECT guild_id, user_id, thanked_at FROM tag_thanks_cooldown",
        [(*key, float(at)) for key, at in live.items()],
        "cooldowns",
    )
    print(
        f"tag: {len(enabled)} enabled, {len(roles)} role settings, {len(thanks)} "
        f"thank-you settings ({len(messages)} with a message), {len(live)} cooldowns "
        "still running; every row matches Firebase"
    )


VANITY_PATHS = ("Vanity Roles", "Vanity Thanks", "Vanity Thanks Message", "Vanity User")
VANITY_TABLES = (
    "vanity_enabled",
    "vanity_roles",
    "vanity_thanks",
    "vanity_thanks_cooldown",
)
VANITY_IDS = (
    ("Server ID", "Role ID", "Log Channel ID"),
    ("Server ID", "Channel ID"),
    ("Server ID",),
)


async def vanity(pool, db, enabled_file=None):
    """Vanity roles: enabled servers, role settings, thank-you settings, cooldowns."""
    from commands.Vanity import vanityStore as store
    from utils.config import THANKS_COOLDOWN

    await store.create(pool)
    for table in VANITY_TABLES:
        if await pool.fetchval(f"SELECT count(*) FROM {table}"):
            raise SystemExit(f"{table} already has rows; Postgres is the live copy")
    enabled_file = enabled_file or os.environ["VANITY_ENABLED_FILE"]
    enabled = set(read_list(enabled_file, "enabledGuilds"))
    data = export(
        os.path.dirname(enabled_file),
        "vanity",
        db,
        VANITY_PATHS,
        enabled=sorted(enabled),
    )
    roles, thanks, messages = (by_server(data[path]) for path in VANITY_PATHS[:3])
    live = thanked(data[VANITY_PATHS[3]], int(time.time()), THANKS_COOLDOWN)
    whole_vanity_ids((roles, thanks, messages), live)

    for guild_id in enabled:
        await store.enable(pool, guild_id)
    for guild_id, record in roles.items():
        await store.set_roles(
            pool,
            guild_id,
            record.get("Link"),
            record.get("Role ID"),
            record.get("Log Channel ID"),
        )
    for guild_id, record in thanks.items():
        await store.set_thanks(
            pool, guild_id, record.get("Channel ID"), record.get("DM", False)
        )
    for guild_id, record in messages.items():
        await store.set_message(
            pool, guild_id, *(record.get(field, "") for field in MESSAGE)
        )
    await pool.executemany(
        """INSERT INTO vanity_thanks_cooldown (guild_id, user_id, thanked_at)
        VALUES ($1, $2, $3)""",
        [(*key, at) for key, at in live.items()],
    )
    await check_vanity(pool, enabled, roles, thanks, messages, live)


def thanked(users, now, cooldown):
    """Gives {(server, member): time thanked} for cooldowns still running.

    The bot read a member's first record for the server, so that one counts."""
    first = {}
    for record in (users or {}).values():
        key = (record["Server ID"], record["User ID"])
        first.setdefault(key, record["Last Thanked Timestamp"])
    return {key: at for key, at in first.items() if now - at <= cooldown}


def whole_vanity_ids(settings, live):
    """Stops if an id or a time is not a whole number, or a DM flag not a bool."""
    values = [
        record.get(field)
        for records, fields in zip(settings, VANITY_IDS)
        for record in records.values()
        for field in fields
    ]
    values += [value for key, at in live.items() for value in (*key, at)]
    bad = [value for value in values if value is not None and type(value) is not int]
    flags = [t.get("DM", False) for t in settings[1].values()]
    bad += [flag for flag in flags if type(flag) is not bool]
    links = [r.get("Link") for r in settings[0].values()]
    bad += [link for link in links if link is not None and type(link) is not str]
    if bad:
        raise SystemExit(f"values of the wrong kind: {bad}")


async def check_vanity(pool, enabled, roles, thanks, messages, live):
    """Reads every row back and stops if one differs from Firebase."""
    await same(
        pool,
        "SELECT guild_id FROM vanity_enabled",
        [(guild_id,) for guild_id in enabled],
        "enabled servers",
    )
    await same(
        pool,
        "SELECT guild_id, link, role_id, log_channel_id FROM vanity_roles",
        [
            (guild_id, r.get("Link"), r.get("Role ID"), r.get("Log Channel ID"))
            for guild_id, r in roles.items()
        ],
        "role settings",
    )
    await same(
        pool,
        """SELECT guild_id, channel_id, dm, content, title, description, color, image
        FROM vanity_thanks""",
        [
            (
                guild_id,
                thanks.get(guild_id, {}).get("Channel ID"),
                thanks[guild_id].get("DM", False) if guild_id in thanks else None,
                *(
                    messages[guild_id].get(field, "") if guild_id in messages else None
                    for field in MESSAGE
                ),
            )
            for guild_id in set(thanks) | set(messages)
        ],
        "thank-you settings",
    )
    await same(
        pool,
        "SELECT guild_id, user_id, thanked_at FROM vanity_thanks_cooldown",
        [(*key, at) for key, at in live.items()],
        "cooldowns",
    )
    print(
        f"vanity: {len(enabled)} enabled, {len(roles)} role settings, {len(thanks)} "
        f"thank-you settings, {len(messages)} messages "
        f"({len(set(messages) - set(thanks))} kept with thanks off), {len(live)} "
        "cooldowns still running; every row matches Firebase"
    )


SYSTEMS = {"tag": tag, "vanity": vanity}


async def main(names):
    import asyncpg
    import firebase_admin
    from assets.secret import (
        DATABASE_PASSWORD,
        DATABASE_PATH,
        DATABASE_URL,
        DATABASE_USER,
    )
    from firebase_admin import credentials, db

    firebase_admin.initialize_app(
        credentials.Certificate(DATABASE_PATH), {"databaseURL": DATABASE_URL}
    )
    pool = await asyncpg.create_pool(
        database=os.environ.get("FISCHL_DATABASE", "db"),
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host="localhost",
    )
    for name in names:
        async with pool.acquire() as connection, connection.transaction():
            await SYSTEMS[name](connection, db)
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
