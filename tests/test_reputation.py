import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.CoOp import coOpStore, coOpSystem
from commands.CoOp import reputationStore as store
from commands.CoOp import reputationSystem

GUILD, OTHER, AUTHOR, MEMBER, ROLE = 10, 11, 50, 60, 70


@pytest.fixture
async def cog(pool):
    bot = MagicMock()
    bot.pool = pool
    found = reputationSystem.ReputationSystem(bot)
    await found.cog_load()
    return found


def member(user_id):
    found = MagicMock()
    found.id = user_id
    found.name = f"user{user_id}"
    found.add_roles = AsyncMock()
    found.guild.get_role = role
    return found


def role(role_id):
    found = MagicMock()
    found.id = role_id
    found.mention = f"<@&{role_id}>"
    return found


def message(content, guild=GUILD, gone=()):
    found = MagicMock()
    found.content = content
    found.author = member(AUTHOR)
    found.author.bot = False
    found.guild.id = guild
    members = {}

    async def fetch(user_id):
        if user_id in gone:
            raise discord.NotFound(MagicMock(status=404), "gone")
        return members.setdefault(user_id, member(user_id))

    found.guild.fetch_member = fetch
    found.members = members
    found.channel.send = AsyncMock()
    found.reply = AsyncMock()
    return found


def sent(found):
    return found.channel.send.await_args.args[0]


async def test_store_keeps_settings_rewards_and_points(pool):
    await store.create(pool)
    assert await store.max_rep(pool, GUILD) is None
    assert await store.enable(pool, GUILD, 5) is True
    assert await store.enable(pool, GUILD, 9) is False
    assert await store.max_rep(pool, GUILD) == 9
    assert await store.add_reward(pool, GUILD, 2, 30) is True
    assert await store.add_reward(pool, GUILD, 1, 10) is True
    assert await store.add_reward(pool, GUILD, 1, 99) is False
    assert await store.rewards(pool, GUILD) == {1: 10, 2: 30}
    assert list(await store.rewards(pool, GUILD)) == [1, 2]
    assert await store.remove_reward(pool, GUILD, 2) is True
    assert await store.remove_reward(pool, GUILD, 2) is False
    assert await store.points(pool, GUILD, MEMBER) == 0
    assert await store.give(pool, GUILD, MEMBER, 3) == 3
    assert await store.give(pool, GUILD, MEMBER, 4) == 7
    assert await store.points(pool, OTHER, MEMBER) == 0
    assert await store.disable(pool, GUILD) is True
    assert await store.disable(pool, GUILD) is False
    assert await store.rewards(pool, GUILD) == {}
    assert await store.points(pool, GUILD, MEMBER) == 7


async def test_reps_given_together_all_count(pool):
    await store.create(pool)
    await asyncio.gather(*(store.give(pool, GUILD, MEMBER, 1) for _ in range(40)))
    assert await store.points(pool, GUILD, MEMBER) == 40


@pytest.mark.parametrize("content", ["-rep", "-toprep", f"-giverep <@{MEMBER}> 1"])
async def test_nothing_is_said_with_the_system_off(cog, content):
    found = message(content)
    await cog.on_message(found)
    found.channel.send.assert_not_awaited()
    found.reply.assert_not_awaited()


@pytest.mark.parametrize("content", ["hello", "-", "-help", "rep"])
async def test_other_messages_do_not_reach_the_database(content):
    bot = MagicMock()
    bot.pool = None
    await reputationSystem.ReputationSystem(bot).on_message(message(content))


async def test_rep_shows_the_named_member_or_the_author(cog, pool):
    await store.enable(pool, GUILD, 999)
    await store.give(pool, GUILD, MEMBER, 4)
    found = message(f"-rep <@{MEMBER}>")
    await cog.on_message(found)
    assert sent(found) == f"**user{MEMBER}**: **4** rep"
    for content in ("-rep", "-rep nobody", f"-REP <@{MEMBER}>"[:4]):
        found = message(content)
        await cog.on_message(found)
        assert sent(found) == f"**user{AUTHOR}**: **0** rep"


async def test_giverep_adds_up_and_gives_the_role_once(cog, pool):
    await store.enable(pool, GUILD, 5)
    await store.add_reward(pool, GUILD, ROLE, 6)
    found = message(f"-giverep <@{MEMBER}> 5")
    await cog.on_message(found)
    assert sent(found) == (
        f"<:yes:1036811164891480194> Gave `5` Rep to **user{MEMBER}** (current - `5`)"
    )
    assert found.channel.send.await_args.kwargs["embeds"] == []
    found.members[MEMBER].add_roles.assert_not_awaited()
    found = message(f"-giverep {MEMBER} 2")
    await cog.on_message(found)
    assert "(current - `7`)" in sent(found)
    (embed,) = found.channel.send.await_args.kwargs["embeds"]
    assert embed.description == (
        f"**user{MEMBER}** just earned a new role: **<@&{ROLE}>**"
    )
    found.members[MEMBER].add_roles.assert_awaited_once()
    found = message(f"-giverep {MEMBER} 2")
    await cog.on_message(found)
    assert found.channel.send.await_args.kwargs["embeds"] == []
    assert await store.points(pool, GUILD, MEMBER) == 9
    assert await store.points(pool, OTHER, MEMBER) == 0


@pytest.mark.parametrize(
    "content, said",
    [
        ("-giverep", "Command Usage: `-giverep @user amount`"),
        (f"-giverep <@{MEMBER}>", "Command Usage: `-giverep @user amount`"),
        (
            f"-giverep <@{MEMBER}> lots",
            "<:no:1036810470860013639> Invalid format. Use `-giverep @user amount`",
        ),
        (
            f"-giverep <@{MEMBER}> 6",
            "<:no:1036810470860013639> You can't give more than 5 reps at once.",
        ),
        (
            f"-giverep <@{AUTHOR}> 1",
            "<:no:1036810470860013639> You can't give yourself reps!",
        ),
        (
            f"-giverep <@{MEMBER}> 0",
            "<:no:1036810470860013639> You must give at least 1 rep.",
        ),
    ],
)
async def test_giverep_refuses(cog, pool, content, said):
    await store.enable(pool, GUILD, 5)
    found = message(content)
    await cog.on_message(found)
    found.reply.assert_awaited_once_with(said)
    assert await pool.fetchval("SELECT count(*) FROM reputation_points") == 0


async def test_toprep_lists_this_server_and_skips_members_who_left(cog, pool):
    await store.enable(pool, GUILD, 999)
    for user_id, amount in ((1, 5), (2, 9), (3, 7)):
        await store.give(pool, GUILD, user_id, amount)
    await store.give(pool, OTHER, 4, 100)
    found = message("-toprep 2", gone={3})
    await cog.on_message(found)
    embed = found.channel.send.await_args.kwargs["embed"]
    assert embed.title == "Global Reputation Leaderboard - Top 2"
    assert embed.description == "1. **user2** `(2)` - **9**\n"
    found = message("-toprep")
    await cog.on_message(found)
    embed = found.channel.send.await_args.kwargs["embed"]
    assert embed.title == "Global Reputation Leaderboard - Top 10"
    assert embed.description == (
        "1. **user2** `(2)` - **9**\n"
        "2. **user3** `(3)` - **7**\n"
        "3. **user1** `(1)` - **5**\n"
    )
    found = message("-toprep", guild=OTHER + 1)
    await store.enable(pool, OTHER + 1, 999)
    await cog.on_message(found)
    assert sent(found) == "No reputation data found."


def interaction(pool):
    found = MagicMock()
    found.client.pool = pool
    found.guild.id = GUILD
    found.response.send_message = AsyncMock()
    found.response.edit_message = AsyncMock()
    return found


def field(modal, name, value):
    setattr(modal, name, MagicMock(value=value, __str__=lambda self: value))


async def add(pool, role_id, cost):
    modal = coOpSystem.AddRewardModel()
    field(modal, "role_id", role_id)
    field(modal, "cost", cost)
    await modal.on_submit(interaction(pool))
    return modal


async def remove(pool, role_id):
    modal = coOpSystem.RemoveRewardModel()
    field(modal, "role_id", role_id)
    await modal.on_submit(interaction(pool))
    return modal


async def edit(pool, most):
    modal = coOpSystem.CoOpRepEnableModal()
    field(modal, "maxrep", most)
    await modal.on_submit(interaction(pool))
    return modal


async def test_settings_forms(pool):
    await store.create(pool)
    modal = await add(pool, "70", "5")
    assert modal.update.description == (
        "Reputation system is not enabled for this server yet. Please enable it first."
    )
    modal = await edit(pool, "")
    assert modal.embed.title == "Reputation System Enabled"
    assert "maximum of `999`" in modal.embed.description
    assert modal.embed.fields[0].value == "None"
    modal = await remove(pool, "70")
    assert modal.update.description == "No rewards found for this server."
    modal = await add(pool, "70", "many")
    assert modal.update.description == "Cost must be a valid integer."
    modal = await add(pool, "Eu helper", "5")
    assert modal.update.description == "Role ID must be a valid role ID."
    assert modal.roles == "None"
    modal = await add(pool, " 70 ", "5")
    assert modal.update.description == (
        "Added reward for role ID: `70` with a cost of 5 reputation points."
    )
    assert modal.roles == {70: 5}
    modal = await add(pool, "70", "8")
    assert modal.update.description == (
        "This role ID already exists as a reward in this server."
    )
    modal = await edit(pool, "20")
    assert modal.embed.title == "Reputation System Updated"
    assert modal.embed.description == (
        "The reputation system is updated with a maximum of `20` reputation points."
    )
    assert modal.embed.fields[0].value == "1. <@&70> • 5 reps \n"
    modal = await remove(pool, "71")
    assert modal.update.description == "Role ID not found as a reward."
    modal = await remove(pool, "70")
    assert modal.update.description == "Removed reward for role ID: `70`."
    assert modal.roles == "None"


async def test_bad_limit_changes_nothing(pool):
    await store.create(pool)
    found = interaction(pool)
    modal = coOpSystem.CoOpRepEnableModal()
    field(modal, "maxrep", "lots")
    await modal.on_submit(found)
    found.response.send_message.assert_awaited_once_with(
        "Invalid input for maximum reputation. Please enter a valid integer.",
        ephemeral=True,
    )
    assert await store.max_rep(pool, GUILD) is None


async def test_command_and_disable_button(pool):
    await store.create(pool)
    await coOpStore.create(pool)
    cog = coOpSystem.CoOp(MagicMock())
    found = interaction(pool)
    await coOpSystem.CoOp.coop_reputation.callback(cog, found)
    embed = found.response.send_message.await_args.kwargs["embed"]
    assert embed.title == "Reputation System Not Enabled"
    await store.enable(pool, GUILD, 7)
    await store.add_reward(pool, GUILD, 2, 30)
    await store.add_reward(pool, GUILD, 1, 10)
    found = interaction(pool)
    await coOpSystem.CoOp.coop_reputation.callback(cog, found)
    embed = found.response.send_message.await_args.kwargs["embed"]
    assert embed.title == "Reputation System"
    assert "maximum of `7`" in embed.description
    assert embed.fields[0].value == "1. <@&1> • 10 reps \n2. <@&2> • 30 reps \n"
    view = coOpSystem.CoOpRepEnableView()
    for title in ("Reputation System Disabled", "Reputation System Not Enabled"):
        found = interaction(pool)
        await view.disable_rep_system.callback(found)
        assert found.response.edit_message.await_args.kwargs["embed"].title == title
    assert await store.rewards(pool, GUILD) == {}


def test_nothing_reads_firebase():
    import inspect

    for module in (coOpSystem, reputationSystem):
        source = inspect.getsource(module)
        assert "Global Reps" not in source
        assert "firebase" not in source


async def test_role_is_given_only_by_the_gift_that_reaches_its_cost():
    found = member(MEMBER)
    for before, after, given in ((0, 9, 0), (5, 10, 1), (10, 11, 0), (0, 30, 1)):
        found.add_roles.reset_mock()
        embeds = await reputationSystem.earned(found, before, after, {ROLE: 10})
        assert (len(embeds), found.add_roles.await_count) == (given, given)
        assert all(embed.color == discord.Color.green() for embed in embeds)


async def test_reward_of_a_deleted_role_is_skipped():
    found = member(MEMBER)
    found.guild.get_role = lambda role_id: None
    assert await reputationSystem.earned(found, 0, 10, {ROLE: 10}) == []
    found.add_roles.assert_not_awaited()


@pytest.mark.parametrize(
    "text, number",
    [("5", 5), ("+5", 5), ("-5", -5), ("1_000", 1000), ("+-5", None), ("x", None)],
)
def test_cost_typed_in_the_form(text, number):
    assert coOpSystem.whole(text) == number


async def test_toprep_shows_between_one_and_fifty(cog, pool):
    await store.enable(pool, GUILD, 999)
    for user_id in range(1, 53):
        await store.give(pool, GUILD, user_id, user_id)
    for asked, shown in (("99", 50), ("0", 1), ("-3", 1)):
        found = message(f"-toprep {asked}")
        await cog.on_message(found)
        embed = found.channel.send.await_args.kwargs["embed"]
        assert embed.title == f"Global Reputation Leaderboard - Top {shown}"
        assert embed.description.count("\n") == shown
        assert embed.color.value == 0xEB7660


async def test_bots_and_direct_messages_get_no_answer(cog, pool):
    await store.enable(pool, GUILD, 999)
    found = message("-rep")
    found.author.bot = True
    await cog.on_message(found)
    found.channel.send.assert_not_awaited()
    found = message("-rep")
    found.guild = None
    await cog.on_message(found)
    found.channel.send.assert_not_awaited()


async def test_reps_for_someone_not_in_the_server_are_not_saved(cog, pool):
    await store.enable(pool, GUILD, 999)
    found = message(f"-giverep {MEMBER} 2", gone={MEMBER})
    with pytest.raises(discord.NotFound):
        await cog.on_message(found)
    assert await store.points(pool, GUILD, MEMBER) == 0
