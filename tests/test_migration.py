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
