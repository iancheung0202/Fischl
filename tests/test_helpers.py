"""The minigame helpers on a real database: what each read gives and each write leaves."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from commands.Events import helperFunctions as helpers

GUILD, OTHER_GUILD, USER = 10, 11, 1


@pytest.fixture
async def db(pool):
    await helpers.create_tables(pool)
    return pool


async def earn(pool, uid, amount, gid=GUILD, when=1_700_000_000):
    await pool.execute(
        "INSERT INTO minigame_mora (uid, gid, cid, timestamp, count) VALUES ($1, $2, 5, $3, $4)",
        uid,
        gid,
        when,
        amount,
    )


def server(roles=()):
    """A server whose members can be fetched and given or taken roles."""
    found = {role: SimpleNamespace(id=role) for role in roles}
    member = SimpleNamespace(
        add_roles=AsyncMock(), remove_roles=AsyncMock(), roles=list(found.values())
    )
    return SimpleNamespace(
        id=GUILD,
        member=member,
        get_role=found.get,
        get_member=lambda uid: member,
        fetch_member=AsyncMock(return_value=member),
    )


async def titles(pool, uid=USER, gid=GUILD):
    return [item[0] for item in await helpers.get_user_inventory(pool, uid, gid)]


async def test_a_server_board_only_counts_that_server(db):
    await earn(db, 1, 100)
    await earn(db, 2, 900, OTHER_GUILD)
    await earn(db, 1, 50, OTHER_GUILD)
    assert await helpers.get_guild_leaderboard(db, GUILD) == [(1, 100)]
    assert await helpers.get_global_leaderboard(db) == [(2, 900), (1, 150)]


async def test_the_threshold_counts_a_member_exactly_on_it(db):
    await earn(db, 1, 500)
    await earn(db, 2, 499)
    over = helpers.get_users_by_currency_threshold
    assert await over(db, GUILD, 500, "guild_mora") == [(1, 500)]
    assert await over(db, GUILD, 500, "no such currency") == [(1, 500)]


async def test_sigils_everywhere_add_up_over_servers(db):
    await helpers.add_sigils(db, USER, GUILD, 4)
    await helpers.add_sigils(db, USER, OTHER_GUILD, 6)
    assert await helpers.get_sigils_balance(db, USER, GUILD) == 4
    assert await helpers.get_global_sigils_balance(db, USER) == 10
    assert await helpers.balance(db, "global_sigils", USER, GUILD) == 10
    assert await helpers.balance(db, "guild_sigils", USER, GUILD) == 4
    assert await helpers.balance(db, "global_mora", USER, GUILD) == 0


async def test_a_milestone_is_given_exactly_on_its_threshold_and_once(db, monkeypatch):
    from commands.Events import event

    monkeypatch.setattr(event, "userAndTitle", AsyncMock(return_value="<@1>"))
    await helpers.add_milestone(db, GUILD, "Rich", "Has 100", 100)
    client = SimpleNamespace(get_guild=lambda id: None, get_channel=lambda id: None)
    await earn(db, USER, 99)
    await helpers.check_milestones(db, USER, GUILD, None, client)
    assert await titles(db) == []
    await earn(db, USER, 1, when=1_700_000_001)
    await helpers.check_milestones(db, USER, GUILD, "not a channel", client)
    await helpers.check_milestones(db, USER, GUILD, None, client)
    assert await titles(db) == ["Rich"]


async def test_syncing_a_milestone_gives_and_takes_back(db):
    guild = server(roles=[501])
    await earn(db, 1, 300)
    await earn(db, 2, 50)
    await helpers.add_inventory_item(db, 2, GUILD, "501", "old", 0, 1)
    await helpers.add_inventory_item(db, 3, GUILD, "501", "bought", 40, 1)
    counts = await helpers.sync_milestone_holders(
        db, guild, ["new", "501", 100, "guild_mora"]
    )
    assert counts == {"awarded": 1, "revoked": 1}
    assert await helpers.get_milestone_holders(db, GUILD, "501") == [1]
    assert await titles(db, 3) == ["501"]
    guild.member.add_roles.assert_awaited_once()
    guild.member.remove_roles.assert_awaited_once()
    for unset in (["d", "_new_1", 100], ["d", "501", 0], ["d", "501", "many"]):
        assert await helpers.sync_milestone_holders(db, guild, unset) == {
            "awarded": 0,
            "revoked": 0,
        }


async def test_holders_are_members_who_earned_it_once_each(db):
    await helpers.add_inventory_item(db, 2, GUILD, "Rich", "", 0, 1)
    await helpers.add_inventory_item(db, 2, GUILD, "Rich", "", 0, 2)
    await helpers.add_inventory_item(db, 1, GUILD, "Rich", "", 0, 1)
    await helpers.add_inventory_item(db, 3, GUILD, "Rich", "", 25, 1)
    await helpers.add_inventory_item(db, 4, OTHER_GUILD, "Rich", "", 0, 1)
    assert await helpers.get_milestone_holders(db, GUILD, "Rich") == [1, 2]
    assert await helpers.revoke_all_milestone_holders(db, server(), "Rich") == 2
    assert await titles(db, 3) == ["Rich"]
    assert await titles(db, 4, OTHER_GUILD) == ["Rich"]


async def test_only_some_milestone_columns_can_be_edited(db):
    await helpers.add_milestone(db, GUILD, "Rich", "Has 100", 100)
    with pytest.raises(ValueError, match="not editable"):
        await helpers.update_milestone_field(db, GUILD, "Rich", "gid", 5)
    await helpers.update_milestone_field(db, GUILD, "Rich", "threshold", 250)
    await helpers.update_milestone_threshold(db, GUILD, "Rich", 300)
    assert await helpers.get_milestones_list(db, GUILD) == [
        ["Has 100", "Rich", 300, "guild_mora"]
    ]


async def test_pinning_an_item_unpins_the_rest(db):
    await helpers.add_inventory_item(db, USER, GUILD, "A", "", 0, 1, pinned=True)
    await helpers.add_inventory_item(db, USER, GUILD, "B", "", 0, 2)
    assert await helpers.get_pinned_item(db, USER, GUILD) == "A"
    assert await helpers.pin_item(db, USER, GUILD, "B") is True
    assert await helpers.get_pinned_item(db, USER, GUILD) == "B"
    assert await helpers.pin_item(db, USER, GUILD, "missing") is False
    assert await helpers.get_pinned_item(db, USER, GUILD) is None


async def test_a_setting_is_saved_for_a_member_without_a_row(db):
    await helpers.upsert_user_minigame_setting(db, GUILD, USER, "chest_disabled", 1)
    assert await helpers.get_user_minigame_settings(db, GUILD, USER) == {
        "chest_disabled": True,
        "minigame_disabled": False,
        "sigils_disabled": False,
    }
    assert await helpers.get_user_minigame_settings(db, GUILD, 2) == {
        "chest_disabled": False,
        "minigame_disabled": False,
        "sigils_disabled": False,
    }


async def test_discounts_stop_at_half(db):
    await helpers.set_progression(db, GUILD, USER, "shop_discount", 80)
    await helpers.set_progression(db, GUILD, USER, "domain_discount", 70)
    assert await helpers.get_shop_discount(db, GUILD, USER) == 50
    assert await helpers.get_domain_discount(db, GUILD, USER) == 50
    assert await helpers.get_shop_discount(db, GUILD, 2) == 0
    apply = helpers.apply_discount
    assert [apply(101, 80), apply(101, 10), apply(101, None)] == [51, 91, 101]


async def test_mora_numbers_survive_an_entry_without_an_amount(db):
    await earn(db, USER, None)
    numbers = await helpers.get_mora_stats(db, USER, GUILD)
    assert (numbers["largest_daily"], numbers["largest_single"]) == (0, 0)
    assert (numbers["days_active"], numbers["entry_count"]) == (1, 0)


async def test_the_inventory_is_oldest_first_and_can_leave_a_cost_out(db):
    await helpers.add_inventory_item(db, USER, GUILD, "New", "", 30, 2)
    await helpers.add_inventory_item(db, USER, GUILD, "Old", "", 0, 1)
    assert await titles(db) == ["Old", "New"]
    bought = await helpers.get_user_inventory(db, USER, GUILD, exclude_cost=0)
    assert [item[0] for item in bought] == ["New"]


async def test_the_tables_keep_their_defaults(db):
    await db.execute("INSERT INTO minigame_settings (channel_id) VALUES (7)")
    row = await db.fetchrow("SELECT * FROM minigame_settings WHERE channel_id = 7")
    assert (float(row["mora_multiplier"]), row["minigames_enabled"]) == (1.0, True)
    await db.execute(
        "INSERT INTO minigame_rewards (gid, item_type, name) VALUES ($1, 'shop_item', 'x')",
        GUILD,
    )
    item = await helpers.get_shop_item_by_name(db, GUILD, "x")
    assert (item[4], item[5]) == (-1, "guild_mora")
    indexes = await db.fetch(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'minigame_rewards'"
    )
    assert "idx_rewards_gid_type" in {row["indexname"] for row in indexes}
