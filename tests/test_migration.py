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
