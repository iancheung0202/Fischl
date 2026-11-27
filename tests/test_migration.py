import json
import time

import pytest

from commands.Tag import tagStore as store
from scripts import firebase_to_postgres as move

NOW = time.time()


@pytest.fixture
def old_tag_data(firebase, tmp_path):
    """Firebase and the enabled file as the bot left them; gives the file's path."""
    firebase("/Tag Roles").set(
        {
            "a": {
                "Server ID": 1,
                "Tag Server ID": 9,
                "Role ID": 2,
                "Log Channel ID": 3,
            },
            "b": {
                "Server ID": 1,
                "Tag Server ID": 8,
                "Role ID": 7,
                "Log Channel ID": 6,
            },
            "c": {"Server ID": 4, "Role ID": 5, "Log Channel ID": 6},
        }
    )
    firebase("/Tag Thanks").set(
        {
            "a": {"Server ID": 1, "Channel ID": 3, "DM": False},
            "b": {"Server ID": 4, "Channel ID": None, "DM": True},
        }
    )
    firebase("/Tag Thanks Message").set(
        {
            "a": {
                "Server ID": 1,
                "Message Content": "hi",
                "Title": "",
                "Description": "d",
                "Color": "#fff",
                "Image Link": "",
            }
        }
    )
    firebase("/Tag Thanks Cooldown").set(
        {
            "a": {"Guild": 1, "User": 5, "Timestamp": NOW - 90000},
            "b": {"Guild": 1, "User": 5, "Timestamp": NOW - 50},
            "c": {"Guild": 1, "User": 5, "Timestamp": NOW - 100},
            "d": {"Guild": 1, "User": 6, "Timestamp": NOW - 86401},
        }
    )
    path = tmp_path / "tagEnabledGuilds.py"
    path.write_text("enabledGuilds = [1, 77]\n")
    return str(path)


async def test_tag_data_moves_once(pool, firebase, old_tag_data):
    import firebase_admin.db

    await move.tag(pool, firebase_admin.db, old_tag_data)
    assert [tuple(row) for row in await store.watched(pool)] == [(1, 9, 2, 3)]
    assert (
        await pool.fetchval("SELECT tag_guild_id FROM tag_roles WHERE guild_id = 4")
        is None
    )
    assert tuple(await store.thanks(pool, 1)) == (
        1,
        3,
        False,
        "hi",
        "",
        "d",
        "#fff",
        "",
    )
    assert tuple(await store.thanks(pool, 4)) == (4, None, True) + (None,) * 5
    rows = await pool.fetch("SELECT * FROM tag_thanks_cooldown")
    assert [tuple(row) for row in rows] == [(1, 5, NOW - 50)]


async def test_what_was_read_is_saved_beside_the_old_file(
    pool, firebase, old_tag_data, tmp_path
):
    import firebase_admin.db

    await move.tag(pool, firebase_admin.db, old_tag_data)
    saved = json.loads((tmp_path / "tag-export.json").read_text())
    assert saved["enabled"] == [1, 77]
    assert len(saved["Tag Thanks Cooldown"]) == 4

    with pytest.raises(SystemExit):
        await move.tag(pool, firebase_admin.db, old_tag_data)


async def test_tag_move_needs_the_enabled_file(pool, firebase, tmp_path):
    import firebase_admin.db

    with pytest.raises(FileNotFoundError):
        await move.tag(pool, firebase_admin.db, str(tmp_path / "missing.py"))


async def test_tag_move_refuses_when_any_table_has_rows(pool, firebase, old_tag_data):
    import firebase_admin.db

    await store.create(pool)
    await store.set_thanks(pool, 1, None, True)
    with pytest.raises(SystemExit):
        await move.tag(pool, firebase_admin.db, old_tag_data)
    assert (await store.thanks(pool, 1))["dm"] is True


async def test_tag_move_skips_a_message_without_settings(pool, firebase, old_tag_data):
    import firebase_admin.db

    firebase("/Tag Thanks Message/z").set({"Server ID": 50, "Title": "t"})
    await move.tag(pool, firebase_admin.db, old_tag_data)
    assert await store.thanks(pool, 50) is None


@pytest.mark.parametrize(
    "path, value, moved",
    [
        ("/Tag Roles/a/Tag Server ID", "9", True),
        ("/Tag Roles/a/Role ID", 2.0, False),
        ("/Tag Roles/a/Log Channel ID", "3", False),
        ("/Tag Thanks/a/Channel ID", 3.0, False),
        ("/Tag Thanks Cooldown/b/User", 5.0, False),
    ],
)
async def test_tag_move_stops_on_ids_that_are_not_whole_numbers(
    pool, firebase, old_tag_data, path, value, moved
):
    import firebase_admin.db

    firebase(path).set(value)
    if moved:
        await move.tag(pool, firebase_admin.db, old_tag_data)
        assert [tuple(row) for row in await store.watched(pool)] == [(1, 9, 2, 3)]
    else:
        with pytest.raises(SystemExit):
            await move.tag(pool, firebase_admin.db, old_tag_data)


@pytest.fixture
def old_vanity_data(firebase, tmp_path):
    """Firebase and the enabled file as the bot left them; gives the file's path."""
    role = {"Role ID": 2, "Log Channel ID": 3}
    firebase("/Vanity Roles").set(
        {
            "a": {"Server ID": 1, "Link": "discord.gg/a", **role},
            "b": {"Server ID": 1, "Link": "discord.gg/later", **role},
            "c": {"Server ID": 4, "Link": "bro", **role},
        }
    )
    firebase("/Vanity Thanks").set(
        {
            "a": {"Server ID": 1, "Channel ID": 3, "DM": False},
            "b": {"Server ID": 4, "DM": True},
        }
    )
    message = {"Title": "", "Description": "d", "Color": "#fff", "Image Link": ""}
    firebase("/Vanity Thanks Message").set(
        {
            "a": {"Server ID": 1, "Message Content": "hi", **message},
            "b": {"Server ID": 50, "Message Content": "kept", **message},
        }
    )
    now = int(NOW)
    firebase("/Vanity User").set(
        {
            "a": {"Server ID": 1, "User ID": 5, "Last Thanked Timestamp": now - 100},
            "b": {"Server ID": 1, "User ID": 5, "Last Thanked Timestamp": now - 50},
            "c": {"Server ID": 1, "User ID": 6, "Last Thanked Timestamp": now - 86500},
            "d": {"Server ID": 4, "User ID": 5, "Last Thanked Timestamp": now - 86000},
        }
    )
    path = tmp_path / "enabledGuilds.py"
    path.write_text("enabledGuilds = [1, 77]\n")
    return str(path)


async def test_vanity_data_moves_once(pool, firebase, old_vanity_data, tmp_path):
    import firebase_admin.db

    from commands.Vanity import vanityStore

    await move.vanity(pool, firebase_admin.db, old_vanity_data)
    watched = [tuple(row) for row in await vanityStore.watched(pool)]
    assert watched == [(1, "discord.gg/a", 2, 3)]
    assert (
        await pool.fetchval("SELECT link FROM vanity_roles WHERE guild_id = 4") == "bro"
    )
    assert sorted(await vanityStore.enabled(pool)) == [1, 77]
    assert tuple(await vanityStore.thanks(pool, 1))[1:] == (
        3,
        False,
        "hi",
        "",
        "d",
        "#fff",
        "",
    )
    assert tuple(await vanityStore.thanks(pool, 4)) == (4, None, True) + (None,) * 5
    assert await vanityStore.thanks(pool, 50) is None
    kept = await pool.fetchrow(
        "SELECT dm, content FROM vanity_thanks WHERE guild_id = 50"
    )
    assert tuple(kept) == (None, "kept")
    rows = await pool.fetch(
        "SELECT * FROM vanity_thanks_cooldown ORDER BY guild_id, user_id"
    )
    now = int(NOW)
    assert [tuple(row) for row in rows] == [(1, 5, now - 100), (4, 5, now - 86000)]

    saved = json.loads((tmp_path / "vanity-export.json").read_text())
    assert saved["enabled"] == [1, 77]
    assert len(saved["Vanity User"]) == 4
    with pytest.raises(SystemExit):
        await move.vanity(pool, firebase_admin.db, old_vanity_data)


async def test_vanity_move_needs_the_enabled_file(pool, firebase, tmp_path):
    import firebase_admin.db

    with pytest.raises(FileNotFoundError):
        await move.vanity(pool, firebase_admin.db, str(tmp_path / "missing.py"))


async def test_vanity_move_refuses_when_any_table_has_rows(
    pool, firebase, old_vanity_data
):
    import firebase_admin.db

    from commands.Vanity import vanityStore

    await vanityStore.create(pool)
    await vanityStore.claim_thanks(pool, 1, 5, 100, 86400)
    with pytest.raises(SystemExit):
        await move.vanity(pool, firebase_admin.db, old_vanity_data)
    assert await pool.fetchval("SELECT count(*) FROM vanity_roles") == 0


@pytest.mark.parametrize(
    "path, value",
    [
        ("/Vanity Roles/a/Role ID", 2.0),
        ("/Vanity Roles/a/Log Channel ID", "3"),
        ("/Vanity Roles/a/Link", 5),
        ("/Vanity Thanks/a/Channel ID", 3.0),
        ("/Vanity Thanks/a/DM", "False"),
        ("/Vanity Thanks Message/a/Server ID", "1"),
        ("/Vanity User/a/User ID", 5.0),
        ("/Vanity User/a/Last Thanked Timestamp", float(int(NOW))),
    ],
)
async def test_vanity_move_stops_on_values_of_the_wrong_kind(
    pool, firebase, old_vanity_data, path, value
):
    import firebase_admin.db

    firebase(path).set(value)
    with pytest.raises(SystemExit):
        await move.vanity(pool, firebase_admin.db, old_vanity_data)
    assert await pool.fetchval("SELECT count(*) FROM vanity_roles") == 0


async def test_vanity_move_reads_the_file_named_in_the_environment(
    pool, firebase, old_vanity_data, monkeypatch
):
    import firebase_admin.db

    monkeypatch.setenv("VANITY_ENABLED_FILE", old_vanity_data)
    await move.vanity(pool, firebase_admin.db)
    assert await pool.fetchval("SELECT count(*) FROM vanity_enabled") == 2


async def test_vanity_move_reads_a_missing_dm_flag_as_channel(
    pool, firebase, old_vanity_data
):
    import firebase_admin.db

    firebase("/Vanity Thanks/a").set({"Server ID": 1, "Channel ID": 3})
    await move.vanity(pool, firebase_admin.db, old_vanity_data)
    assert (
        await pool.fetchval("SELECT dm FROM vanity_thanks WHERE guild_id = 1") is False
    )


async def test_vanity_move_leaves_nothing_behind_when_the_check_fails(
    pool, firebase, old_vanity_data, monkeypatch
):
    import firebase_admin.db

    async def differ(*args):
        raise SystemExit("differ")

    monkeypatch.setattr(move, "check_vanity", differ)
    with pytest.raises(SystemExit):
        async with pool.acquire() as connection, connection.transaction():
            await move.vanity(connection, firebase_admin.db, old_vanity_data)
    assert await pool.fetchval("SELECT to_regclass('vanity_roles')") is None


@pytest.fixture
def old_sticky_data(firebase, tmp_path):
    """Firebase and the enabled file as the bot left them; gives the file's path."""
    firebase("/Sticky Messages").set(
        {
            "a": {"Channel ID": 1, "Message ID": 10, "Message Content": "one"},
            "b": {"Channel ID": 2, "Message ID": 20, "Message Content": "two"},
            "c": {"Channel ID": 1, "Message ID": 30, "Message Content": "three 🎉"},
            "d": {"Channel ID": 4, "Message ID": 40, "Message Content": "not listed"},
        }
    )
    path = tmp_path / "enabledChannels.py"
    path.write_text("enabledChannels = [1, 2, 1, 3]\n\nasync def setup(bot):\n  pass")
    return str(path)


async def test_sticky_data_moves_once(pool, firebase, old_sticky_data, tmp_path):
    import firebase_admin.db

    await move.sticky(pool, firebase_admin.db, old_sticky_data)
    rows = await pool.fetch("SELECT * FROM sticky_enabled ORDER BY channel_id")
    assert [tuple(row) for row in rows] == [(1, 2), (2, 1), (3, 1)]
    rows = await pool.fetch(move.STUCK_ROWS)
    assert [tuple(row) for row in rows] == [
        (1, 10, "one"),
        (2, 20, "two"),
        (1, 30, "three 🎉"),
        (4, 40, "not listed"),
    ]
    saved = json.loads((tmp_path / "sticky-export.json").read_text())
    assert saved["enabled"] == [1, 2, 1, 3]
    assert saved["Sticky Messages"] == firebase("/Sticky Messages").get()
    with pytest.raises(SystemExit):
        await move.sticky(pool, firebase_admin.db, old_sticky_data)


async def test_sticky_move_reads_the_file_named_in_the_environment(
    pool, firebase, old_sticky_data, monkeypatch
):
    import firebase_admin.db

    monkeypatch.setenv("STICKY_ENABLED_FILE", old_sticky_data)
    await move.sticky(pool, firebase_admin.db)
    assert await pool.fetchval("SELECT count(*) FROM sticky_messages") == 4


@pytest.mark.parametrize(
    "record",
    [
        {"Channel ID": "1", "Message ID": 10, "Message Content": "x"},
        {"Channel ID": 1, "Message ID": 10.0, "Message Content": "x"},
        {"Channel ID": 1, "Message ID": True, "Message Content": "x"},
        {"Channel ID": 1, "Message ID": 10, "Message Content": 5},
    ],
)
async def test_sticky_move_stops_on_values_of_the_wrong_kind(
    pool, firebase, old_sticky_data, record
):
    import firebase_admin.db

    firebase("/Sticky Messages/z").set(record)
    with pytest.raises(SystemExit):
        async with pool.acquire() as connection, connection.transaction():
            await move.sticky(connection, firebase_admin.db, old_sticky_data)
    assert await pool.fetchval("SELECT to_regclass('sticky_messages')") is None


async def test_sticky_move_refuses_when_only_a_message_is_there(
    pool, firebase, old_sticky_data, tmp_path
):
    import firebase_admin.db

    from commands.Sticky import stickyStore

    await stickyStore.create(pool)
    await stickyStore.add(pool, 1, 2, "live")
    with pytest.raises(SystemExit):
        await move.sticky(pool, firebase_admin.db, old_sticky_data)
    assert not (tmp_path / "sticky-export.json").exists()
    assert await pool.fetchval("SELECT count(*) FROM sticky_enabled") == 0


async def test_sticky_move_stops_when_the_saved_order_differs(
    pool, firebase, old_sticky_data, monkeypatch
):
    import firebase_admin.db

    monkeypatch.setattr(move, "STUCK_ROWS", move.STUCK_ROWS + " DESC")
    with pytest.raises(SystemExit, match="differ"):
        await move.sticky(pool, firebase_admin.db, old_sticky_data)


async def test_sticky_move_leaves_nothing_behind_when_the_check_fails(
    pool, firebase, old_sticky_data, monkeypatch
):
    import firebase_admin.db

    async def differ(*args):
        raise SystemExit("differ")

    monkeypatch.setattr(move, "same", differ)
    with pytest.raises(SystemExit):
        async with pool.acquire() as connection, connection.transaction():
            await move.sticky(connection, firebase_admin.db, old_sticky_data)
    assert await pool.fetchval("SELECT to_regclass('sticky_messages')") is None


@pytest.fixture
def old_topics(firebase):
    firebase("/Topics").set(
        {
            "b": {"Topic Query": "second key, first saved?", "Topic Suggester ID": 5},
            "a": {"Topic Query": "it's 🎉", "Topic Suggester ID": 692254240290242601},
        }
    )


async def test_topics_move_once(pool, firebase, old_topics, tmp_path, monkeypatch):
    import firebase_admin.db

    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path))
    await move.topics(pool, firebase_admin.db)
    assert [tuple(row) for row in await pool.fetch(move.TOPIC_ROWS)] == [
        ("second key, first saved?", 5),
        ("it's 🎉", 692254240290242601),
    ]
    saved = json.loads((tmp_path / "topics-export.json").read_text())
    assert saved == {"Topics": firebase("/Topics").get()}
    (tmp_path / "topics-export.json").unlink()
    with pytest.raises(SystemExit):
        await move.topics(pool, firebase_admin.db, str(tmp_path))
    assert not (tmp_path / "topics-export.json").exists()


@pytest.mark.parametrize(
    "record",
    [
        {"Topic Query": 5, "Topic Suggester ID": 5},
        {"Topic Query": "x", "Topic Suggester ID": "5"},
        {"Topic Query": "x", "Topic Suggester ID": 5.0},
        {"Topic Query": "x", "Topic Suggester ID": True},
        {"Topic Query": "x"},
    ],
)
async def test_topics_move_stops_on_values_of_the_wrong_kind(
    pool, firebase, old_topics, tmp_path, record
):
    import firebase_admin.db

    firebase("/Topics/z").set(record)
    with pytest.raises((SystemExit, KeyError)):
        async with pool.acquire() as connection, connection.transaction():
            await move.topics(connection, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT to_regclass('topics')") is None


async def test_topics_move_stops_when_the_saved_order_differs(
    pool, firebase, old_topics, tmp_path, monkeypatch
):
    import firebase_admin.db

    monkeypatch.setattr(move, "TOPIC_ROWS", move.TOPIC_ROWS + " DESC")
    with pytest.raises(SystemExit, match="differ"):
        await move.topics(pool, firebase_admin.db, str(tmp_path))


def born(user, date="03-04 15:00", **changes):
    return {
        "User ID": user,
        "Month": 3,
        "Day": 5,
        "Timezone": "Asia/Tokyo",
        "Display UTC Date": date,
        "Fav Character": "None",
        **changes,
    }


def wishing(server, **changes):
    return {
        "Server ID": server,
        "Channel ID": 2,
        "Webhook ID": 3,
        "Role ID": 4,
        "Server Name": "Teyvat",
        **changes,
    }


@pytest.fixture
def old_birthdays(firebase):
    firebase("/Birthday").set(
        {"b": born(692254240290242601, "02-29 01:00"), "a": born(5)}
    )
    firebase("/Birthday System").set(
        {
            "b": wishing(9, **{"Create Birthday Thread": True}),
            "a": wishing(8),
            "c": wishing(7, **{"Create Birthday Thread": False}),
        }
    )


async def test_birthdays_move_once(
    pool, firebase, old_birthdays, tmp_path, monkeypatch
):
    import firebase_admin.db

    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path))
    await move.birthday(pool, firebase_admin.db)
    assert [tuple(row) for row in await pool.fetch(move.BORN_ROWS)] == [
        (692254240290242601, 3, 5, "Asia/Tokyo", "02-29 01:00", "None"),
        (5, 3, 5, "Asia/Tokyo", "03-04 15:00", "None"),
    ]
    assert [tuple(row) for row in await pool.fetch(move.WISHING_ROWS)] == [
        (9, 2, 3, 4, True),
        (8, 2, 3, 4, False),
        (7, 2, 3, 4, False),
    ]
    saved = json.loads((tmp_path / "birthday-export.json").read_text())
    assert saved == {
        "Birthday": firebase("/Birthday").get(),
        "Birthday System": firebase("/Birthday System").get(),
    }
    (tmp_path / "birthday-export.json").unlink()
    with pytest.raises(SystemExit):
        await move.birthday(pool, firebase_admin.db, str(tmp_path))
    assert not (tmp_path / "birthday-export.json").exists()


async def test_birthdays_move_refuses_when_only_a_server_is_there(
    pool, firebase, old_birthdays, tmp_path
):
    import firebase_admin.db

    from commands.Birthday import birthdayStore

    await birthdayStore.create(pool)
    await birthdayStore.enable(pool, 1, 2, 3, 4, False)
    with pytest.raises(SystemExit):
        await move.birthday(pool, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT count(*) FROM birthdays") == 0
    assert not (tmp_path / "birthday-export.json").exists()


@pytest.mark.parametrize(
    "path, record",
    [
        ("Birthday", born("5")),
        ("Birthday", born(5.0)),
        ("Birthday", born(True)),
        ("Birthday", born(6, Month="3")),
        ("Birthday", born(6, Timezone=None)),
        ("Birthday", born(6, "3-4 15:00")),
        ("Birthday", born(6, "03-04 15:00 ")),
        ("Birthday", born(5)),
        ("Birthday", {"User ID": 6}),
        ("Birthday System", wishing("7")),
        ("Birthday System", wishing(6, **{"Role ID": 4.0})),
        ("Birthday System", wishing(6, **{"Create Birthday Thread": "yes"})),
        ("Birthday System", wishing(6, **{"Create Birthday Thread": 1})),
        ("Birthday System", wishing(8)),
        ("Birthday System", {"Server ID": 6}),
    ],
)
async def test_birthdays_move_stops_on_values_of_the_wrong_kind(
    pool, firebase, old_birthdays, tmp_path, path, record
):
    import firebase_admin.db

    firebase(f"/{path}/z").set(record)
    with pytest.raises((SystemExit, KeyError)):
        async with pool.acquire() as connection, connection.transaction():
            await move.birthday(connection, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT to_regclass('birthdays')") is None


@pytest.mark.parametrize("rows", ["BORN_ROWS", "WISHING_ROWS"])
async def test_birthdays_move_stops_when_the_saved_order_differs(
    pool, firebase, old_birthdays, tmp_path, monkeypatch, rows
):
    import firebase_admin.db

    monkeypatch.setattr(
        move, rows, getattr(move, rows).replace("ORDER BY id", "ORDER BY id DESC")
    )
    with pytest.raises(SystemExit):
        async with pool.acquire() as connection, connection.transaction():
            await move.birthday(connection, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT to_regclass('birthdays')") is None


def coop_server(server, **changes):
    return {
        "Server Name": "Teyvat",
        "Server ID": server,
        "Co-op Channel ID": 2,
        "NA Helper Role ID": 3,
        "EU Helper Role ID": 4,
        "Asia Helper Role ID": 5,
        "SAR Helper Role ID": 6,
        **changes,
    }


@pytest.fixture
def old_coop(firebase):
    firebase("/Co-Op").set({"b": coop_server(692254240290242601), "a": coop_server(8)})
    firebase("/Co-Op Sticky Panel").set(
        {"x": {"Channel ID": 692254240290242603, "Message ID": 12}}
    )
    firebase("/Co-Op-UID").set(
        {"692254240290242605": {"UID": "800000001"}, "7": {"UID": "my uid"}}
    )


COOP_PATHS = ("Co-Op", "Co-Op Sticky Panel", "Co-Op-UID")


async def test_coop_moves_once(pool, firebase, old_coop, tmp_path, monkeypatch):
    import firebase_admin.db

    before = {path: firebase(f"/{path}").get() for path in COOP_PATHS}
    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path))
    await move.coop(pool, firebase_admin.db)
    assert [tuple(row) for row in await pool.fetch(move.COOP_ROWS)] == [
        (692254240290242601, 2, 3, 4, 5, 6),
        (8, 2, 3, 4, 5, 6),
    ]
    assert [tuple(row) for row in await pool.fetch("SELECT * FROM coop_panels")] == [
        (692254240290242603, 12)
    ]
    uids = await pool.fetch("SELECT * FROM coop_uids ORDER BY user_id")
    assert [tuple(row) for row in uids] == [
        (7, "my uid"),
        (692254240290242605, "800000001"),
    ]
    assert json.loads((tmp_path / "coop-export.json").read_text()) == before
    assert {path: firebase(f"/{path}").get() for path in COOP_PATHS} == before
    (tmp_path / "coop-export.json").unlink()
    with pytest.raises(SystemExit):
        await move.coop(pool, firebase_admin.db, str(tmp_path))
    assert not (tmp_path / "coop-export.json").exists()


@pytest.mark.parametrize(
    "table, values",
    [
        ("coop_servers", "DEFAULT, 1, 2, 3, 4, 5, 6"),
        ("coop_panels", "1, 2"),
        ("coop_uids", "1, '2'"),
    ],
)
async def test_coop_move_refuses_when_any_table_has_rows(
    pool, firebase, old_coop, tmp_path, table, values
):
    import firebase_admin.db

    from commands.CoOp import coOpStore

    await coOpStore.create(pool)
    await pool.execute(f"INSERT INTO {table} VALUES ({values})")
    with pytest.raises(SystemExit):
        await move.coop(pool, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT count(*) FROM coop_uids") == (
        table == "coop_uids"
    )
    assert not (tmp_path / "coop-export.json").exists()


@pytest.mark.parametrize(
    "path, key, record",
    [
        ("Co-Op", "z", coop_server(9.0)),
        ("Co-Op", "z", coop_server("9")),
        ("Co-Op", "z", coop_server(True)),
        ("Co-Op", "z", coop_server(8)),
        ("Co-Op", "z", coop_server(9, **{"EU Helper Role ID": 6.922542402902426e17})),
        ("Co-Op Sticky Panel", "z", {"Channel ID": 1, "Message ID": "2"}),
        (
            "Co-Op Sticky Panel",
            "z",
            {"Channel ID": 692254240290242603, "Message ID": 1},
        ),
        ("Co-Op-UID", "8", {"UID": 800000001}),
        ("Co-Op-UID", "07", {"UID": "1"}),
        ("Co-Op-UID", "abc", {"UID": "1"}),
    ],
)
async def test_coop_move_stops_on_bad_records(
    pool, firebase, old_coop, tmp_path, path, key, record
):
    import firebase_admin.db

    firebase(f"/{path}").child(key).set(record)
    with pytest.raises(SystemExit):
        async with pool.acquire() as connection, connection.transaction():
            await move.coop(connection, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT to_regclass('coop_servers')") is None


async def test_coop_move_stops_on_a_missing_field(pool, firebase, old_coop, tmp_path):
    import firebase_admin.db

    record = coop_server(9)
    del record["SAR Helper Role ID"]
    firebase("/Co-Op").child("z").set(record)
    with pytest.raises(KeyError):
        async with pool.acquire() as connection, connection.transaction():
            await move.coop(connection, firebase_admin.db, str(tmp_path))
    assert await pool.fetchval("SELECT to_regclass('coop_servers')") is None
