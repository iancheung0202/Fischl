"""Copies a system's data from Firebase to Postgres, once, at the move.

Run from the repo root, with the bot stopped and the old enabled file already
moved out of the repo:
    TAG_ENABLED_FILE=/path/to/tagEnabledGuilds.py python3 scripts/firebase_to_postgres.py tag
    VANITY_ENABLED_FILE=/path/to/enabledGuilds.py python3 scripts/firebase_to_postgres.py vanity
    STICKY_ENABLED_FILE=/path/to/enabledChannels.py python3 scripts/firebase_to_postgres.py sticky
    EXPORT_FOLDER=/path/to/folder python3 scripts/firebase_to_postgres.py topics
    EXPORT_FOLDER=/path/to/folder python3 scripts/firebase_to_postgres.py birthday
    EXPORT_FOLDER=/path/to/folder python3 scripts/firebase_to_postgres.py coop
    EXPORT_FOLDER=/path/to/folder python3 scripts/firebase_to_postgres.py winners
Firebase is only read, so the old copy stays as it was. Each system saves what
it read to `<system>-export.json` next to that file (or in EXPORT_FOLDER), checks every row it wrote
and refuses to run once its tables hold data."""

import asyncio
import collections
import json
import os
import re
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


STICKY_TABLES = ("sticky_enabled", "sticky_messages")
STUCK = ("Channel ID", "Message ID", "Message Content")
STUCK_ROWS = "SELECT channel_id, message_id, content FROM sticky_messages ORDER BY id"


async def sticky(pool, db, enabled_file=None):
    """Sticky messages: watched channels and every stuck message, in the old order."""
    from commands.Sticky import stickyStore as store

    await store.create(pool)
    for table in STICKY_TABLES:
        if await pool.fetchval(f"SELECT count(*) FROM {table}"):
            raise SystemExit(f"{table} already has rows; Postgres is the live copy")
    enabled_file = enabled_file or os.environ["STICKY_ENABLED_FILE"]
    listed = read_list(enabled_file, "enabledChannels")
    folder = os.path.dirname(enabled_file)
    data = export(folder, "sticky", db, ("Sticky Messages",), enabled=listed)
    stuck = [
        tuple(record[field] for field in STUCK)
        for record in data["Sticky Messages"].values()
    ]
    bad = [row for row in stuck if [type(value) for value in row] != [int, int, str]]
    if bad:
        raise SystemExit(f"sticky messages of the wrong kind: {bad}")

    times = collections.Counter(listed)
    await pool.executemany(
        "INSERT INTO sticky_enabled (channel_id, times) VALUES ($1, $2)", times.items()
    )
    for row in stuck:
        await store.add(pool, *row)
    await same(
        pool, "SELECT channel_id, times FROM sticky_enabled", times.items(), "channels"
    )
    if [tuple(row) for row in await pool.fetch(STUCK_ROWS)] != stuck:
        raise SystemExit("sticky messages differ from Firebase")
    print(
        f"sticky: {len(times)} channels watched ({len(listed)} list entries), "
        f"{len(stuck)} messages in {len({row[0] for row in stuck})} channels; "
        "every row matches Firebase"
    )


TOPIC = ("Topic Query", "Topic Suggester ID")
TOPIC_ROWS = "SELECT query, suggester_id FROM topics ORDER BY id"


async def topics(pool, db, folder=None):
    """Chat topics: every topic and who suggested it, in the old order."""
    from commands.Utility import topicStore as store

    await store.create(pool)
    if await pool.fetchval("SELECT count(*) FROM topics"):
        raise SystemExit("topics already has rows; Postgres is the live copy")
    data = export(folder or os.environ["EXPORT_FOLDER"], "topics", db, ("Topics",))
    saved = [
        tuple(record[field] for field in TOPIC) for record in data["Topics"].values()
    ]
    bad = [row for row in saved if [type(value) for value in row] != [str, int]]
    if bad:
        raise SystemExit(f"topics of the wrong kind: {bad}")
    for row in saved:
        await store.add(pool, *row)
    if [tuple(row) for row in await pool.fetch(TOPIC_ROWS)] != saved:
        raise SystemExit("topics differ from Firebase")
    print(f"topics: {len(saved)} topics; every row matches Firebase")


BORN = ("User ID", "Month", "Day", "Timezone", "Display UTC Date", "Fav Character")
BORN_ROWS = """SELECT user_id, month, day, timezone, display_utc_date, fav_character
    FROM birthdays ORDER BY id"""
WISHING = ("Server ID", "Channel ID", "Webhook ID", "Role ID")
WISHING_ROWS = """SELECT server_id, channel_id, webhook_id, role_id, create_thread
    FROM birthday_servers ORDER BY id"""


def kinds(rows, kinds, what):
    """Stops if a row holds a value of another kind, or its first id comes twice."""
    bad = [row for row in rows if [type(value) for value in row] != kinds]
    if bad:
        raise SystemExit(f"{what} of the wrong kind: {bad}")
    if len({row[0] for row in rows}) != len(rows):
        raise SystemExit(f"{what} with the same id more than once")


async def birthday(pool, db, folder=None):
    """Birthdays and the servers that wish them, in the old order.

    A server saved before threads existed has no thread flag, which the bot read
    as off. Dates must be written `MM-DD HH:MM`, the form the bot now looks up."""
    from commands.Birthday import birthdayStore as store

    await store.create(pool)
    for table in ("birthdays", "birthday_servers"):
        if await pool.fetchval(f"SELECT count(*) FROM {table}"):
            raise SystemExit(f"{table} already has rows; Postgres is the live copy")
    folder = folder or os.environ["EXPORT_FOLDER"]
    data = export(folder, "birthday", db, ("Birthday", "Birthday System"))
    born = [
        tuple(record[field] for field in BORN) for record in data["Birthday"].values()
    ]
    wishing = [
        (
            *(record[field] for field in WISHING),
            record.get("Create Birthday Thread", False),
        )
        for record in data["Birthday System"].values()
    ]
    kinds(born, [int, int, int, str, str, str], "birthdays")
    kinds(wishing, [int, int, int, int, bool], "birthday servers")
    odd = [row for row in born if not re.fullmatch(r"\d\d-\d\d \d\d:\d\d", row[4])]
    if odd:
        raise SystemExit(f"birthdays with a date in another form: {odd}")

    await pool.executemany(
        """INSERT INTO birthdays
        (user_id, month, day, timezone, display_utc_date, fav_character)
        VALUES ($1, $2, $3, $4, $5, $6)""",
        born,
    )
    await pool.executemany(
        """INSERT INTO birthday_servers
        (server_id, channel_id, webhook_id, role_id, create_thread)
        VALUES ($1, $2, $3, $4, $5)""",
        wishing,
    )
    if [tuple(row) for row in await pool.fetch(BORN_ROWS)] != born:
        raise SystemExit("birthdays differ from Firebase")
    if [tuple(row) for row in await pool.fetch(WISHING_ROWS)] != wishing:
        raise SystemExit("birthday servers differ from Firebase")
    print(
        f"birthday: {len(born)} birthdays, {len(wishing)} servers "
        f"({sum(row[4] for row in wishing)} with threads); every row matches Firebase"
    )


COOP = (
    "Server ID",
    "Co-op Channel ID",
    "NA Helper Role ID",
    "EU Helper Role ID",
    "Asia Helper Role ID",
    "SAR Helper Role ID",
)
COOP_ROWS = """SELECT server_id, channel_id, na_role_id, eu_role_id, asia_role_id,
    sar_role_id FROM coop_servers ORDER BY id"""


async def coop(pool, db, folder=None):
    """Co-op servers in the old order, their sticky panels, and members' game UIDs.

    A UID is copied as it was typed. Reputation stays in Firebase."""
    from commands.CoOp import coOpStore as store

    await store.create(pool)
    for table in ("coop_servers", "coop_panels", "coop_uids"):
        if await pool.fetchval(f"SELECT count(*) FROM {table}"):
            raise SystemExit(f"{table} already has rows; Postgres is the live copy")
    folder = folder or os.environ["EXPORT_FOLDER"]
    data = export(folder, "coop", db, ("Co-Op", "Co-Op Sticky Panel", "Co-Op-UID"))
    servers = [
        tuple(record[field] for field in COOP) for record in data["Co-Op"].values()
    ]
    panels = [
        (record["Channel ID"], record["Message ID"])
        for record in data["Co-Op Sticky Panel"].values()
    ]
    odd = [key for key in data["Co-Op-UID"] if not re.fullmatch(r"[1-9]\d*", key)]
    if odd:
        raise SystemExit(f"co-op uids of members with an id in another form: {odd}")
    uids = [(int(key), record["UID"]) for key, record in data["Co-Op-UID"].items()]
    kinds(servers, [int] * 6, "co-op servers")
    kinds(panels, [int, int], "co-op panels")
    kinds(uids, [int, str], "co-op uids")

    await pool.executemany(
        """INSERT INTO coop_servers
        (server_id, channel_id, na_role_id, eu_role_id, asia_role_id, sar_role_id)
        VALUES ($1, $2, $3, $4, $5, $6)""",
        servers,
    )
    await pool.executemany("INSERT INTO coop_panels VALUES ($1, $2)", panels)
    await pool.executemany("INSERT INTO coop_uids VALUES ($1, $2)", uids)
    if [tuple(row) for row in await pool.fetch(COOP_ROWS)] != servers:
        raise SystemExit("co-op servers differ from Firebase")
    await same(
        pool, "SELECT channel_id, message_id FROM coop_panels", panels, "co-op panels"
    )
    await same(pool, "SELECT user_id, uid FROM coop_uids", uids, "co-op uids")
    print(
        f"coop: {len(servers)} servers, {len(panels)} panels, {len(uids)} uids; "
        "every row matches Firebase"
    )


async def winners(pool, db, folder=None):
    """Each server's current weekly leaderboard winner."""
    from commands.Custom import winnerStore as store

    await store.create(pool)
    if await pool.fetchval("SELECT count(*) FROM weekly_winners"):
        raise SystemExit("weekly_winners already has rows; Postgres is the live copy")
    folder = folder or os.environ["EXPORT_FOLDER"]
    saved = export(folder, "winners", db, ("Weekly Leaderboard",))["Weekly Leaderboard"]
    ids = [str(key) for key in saved] + list(saved.values())
    odd = [id for id in ids if type(id) is not str or not re.fullmatch(r"[1-9]\d*", id)]
    if odd:
        raise SystemExit(f"winners with an id in another form: {odd}")
    rows = [(int(server), int(member)) for server, member in saved.items()]
    for row in rows:
        await store.crown(pool, *row)
    await same(pool, "SELECT server_id, user_id FROM weekly_winners", rows, "winners")
    if await pool.fetchval("SELECT count(*) FROM weekly_winners") != len(rows):
        raise SystemExit("winners differ from Firebase")
    print(f"winners: {len(rows)} servers; every row matches Firebase")


def whole(value):
    """Says whether a value is a whole number, or the text of one, above zero."""
    if type(value) is int:
        return value > 0
    return type(value) is str and re.fullmatch(r"[1-9]\d*", value) is not None


def rewards(server_id, roles):
    """Splits a server's saved rewards into rows to copy and the ones left out.

    A reward keyed by anything but a role id could never be given, so it is left out."""
    if roles in (None, "None"):
        return [], []
    if type(roles) is not dict:
        raise SystemExit(f"rewards of server {server_id} in another form: {roles!r}")
    rows, left = [], []
    for role, cost in roles.items():
        if type(cost) is not int:
            raise SystemExit(f"reward cost of server {server_id} not whole: {cost!r}")
        if whole(role):
            rows.append((server_id, int(role), cost))
        else:
            left.append((server_id, role, cost))
    return rows, left


async def reputation(pool, db, folder=None):
    """Reputation settings, role rewards and members' points."""
    from commands.CoOp import reputationStore as store

    await store.create(pool)
    for table in ("reputation_servers", "reputation_roles", "reputation_points"):
        if await pool.fetchval(f"SELECT count(*) FROM {table}"):
            raise SystemExit(f"{table} already has rows; Postgres is the live copy")
    folder = folder or os.environ["EXPORT_FOLDER"]
    saved = export(folder, "reputation", db, ("Global Reps System", "Global Reps"))
    servers, roles, left = {}, [], []
    for record in (saved["Global Reps System"] or {}).values():
        server_id, most = record["Server ID"], record["Max Rep"]
        if type(server_id) is not int or type(most) is not int:
            raise SystemExit(f"reputation server in another form: {record}")
        if server_id in servers:
            continue
        servers[server_id] = most
        rows, odd = rewards(server_id, record.get("Roles"))
        roles += rows
        left += odd
    points = []
    for server_id, record in (saved["Global Reps"] or {}).items():
        for user_id, amount in (record.get("Users") or {}).items():
            if not whole(server_id) or not whole(user_id) or type(amount) is not int:
                raise SystemExit(
                    f"reps in another form: {server_id} {user_id} {amount!r}"
                )
            points.append((int(server_id), int(user_id), amount))
    await pool.executemany(
        "INSERT INTO reputation_servers VALUES ($1, $2)", list(servers.items())
    )
    await pool.executemany("INSERT INTO reputation_roles VALUES ($1, $2, $3)", roles)
    await pool.executemany("INSERT INTO reputation_points VALUES ($1, $2, $3)", points)
    for table, rows in (
        ("reputation_servers", list(servers.items())),
        ("reputation_roles", roles),
        ("reputation_points", points),
    ):
        found = [tuple(row) for row in await pool.fetch(f"SELECT * FROM {table}")]
        if sorted(found) != sorted(rows):
            raise SystemExit(f"{table} differs from Firebase")
    print(
        f"reputation: {len(servers)} servers, {len(roles)} role rewards, "
        f"{len(points)} members with reps; every row matches Firebase. "
        f"Left out, not role ids: {left}"
    )


SYSTEMS = {
    "tag": tag,
    "vanity": vanity,
    "sticky": sticky,
    "topics": topics,
    "birthday": birthday,
    "coop": coop,
    "winners": winners,
    "reputation": reputation,
}


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
