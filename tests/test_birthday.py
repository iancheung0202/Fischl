import datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Birthday import birthday, birthdayEvent
from commands.Birthday import birthdayStore as store
from commands.Birthday.birthdayTexts import characters, characters_dict

GUILD, CHANNEL, WEBHOOK, ROLE, MEMBER = 10, 20, 30, 40, 50
UTC = datetime.timezone.utc


def missing():
    return discord.NotFound(MagicMock(status=404), "gone")


@pytest.fixture
async def cog(pool):
    bot = MagicMock()
    bot.pool = pool
    found = birthday.Birthday(bot)
    await found.cog_load()
    return found


def interaction(user=MEMBER):
    found = MagicMock()
    found.user.id = user
    found.guild.id = GUILD
    found.guild.name = "Teyvat"
    found.response.send_message = AsyncMock()
    found.response.defer = AsyncMock()
    found.followup.send = AsyncMock()
    return found


def answer(found):
    """Gives the embed and whether only the member saw it."""
    call = found.response.send_message.await_args
    return call.kwargs["embed"], call.kwargs.get("ephemeral", False)


async def saved(pool):
    rows = await pool.fetch(
        """SELECT user_id, month, day, timezone, display_utc_date, fav_character
        FROM birthdays ORDER BY id"""
    )
    return [tuple(row) for row in rows]


async def set_birthday(cog, found, month="March", day="5", **changes):
    choice = discord.app_commands.Choice(
        name=month, value=str(birthday.months.index(month) + 1)
    )
    options = {"timezone": "Asia/Tokyo", "character": "Fischl", **changes}
    await birthday.Birthday.birthday_set.callback(
        cog, found, choice, day, options["timezone"], options["character"]
    )


def test_commands_look_the_same():
    assert birthday.Birthday.__cog_group_name__ == "birthday"
    commands = {
        "sync": "Sync data from Birthday Bot (Admin only)",
        "set": "Set your birth date and timezone",
        "get": "Get the birthday of a member",
        "remove": "Remove your birthday from the database",
        "export": "Exports all birthdays of your server members (Admin only)",
        "enable": "Enable birthday wishes in a channel",
        "disable": "Disable birthday wishes in the server",
    }
    for name, description in commands.items():
        command = getattr(birthday.Birthday, f"birthday_{name}")
        assert (command.name, command.description) == (name, description)
        assert command.on_error is not None
    options = birthday.Birthday.birthday_set.parameters
    assert [option.name for option in options] == [
        "month",
        "day",
        "timezone",
        "character",
    ]
    assert [choice.name for choice in options[0].choices] == birthday.months


async def test_menus_offer_the_first_25_then_what_matches():
    days = await birthday.menu(birthday.days)(None, "")
    assert [(choice.name, choice.value) for choice in days] == [
        (str(day), str(day)) for day in range(1, 26)
    ]
    days = await birthday.menu(birthday.days)(None, "3")
    assert [choice.name for choice in days] == ["3", "13", "23", "30", "31"]
    zones = await birthday.menu(birthday.timezones)(None, "TOKYO")
    assert [choice.value for choice in zones] == ["Asia/Tokyo"]
    assert len(await birthday.menu(characters)(None, "a")) == 25


async def test_set_saves_the_utc_start_and_answers(cog, pool):
    found = interaction()
    await set_birthday(cog, found)
    assert await saved(pool) == [(MEMBER, 3, 5, "Asia/Tokyo", "03-04 15:00", "Fischl")]
    embed, private = answer(found)
    assert not private
    assert (embed.title, embed.color.value) == ("✅ Birthday Saved", 0x04C607)
    assert embed.description == (
        ":birthday: You have set your birthday to **March 5** *(Asia/Tokyo)*. \n"
        "*<:YanfeiNote:1335644122253623458> Your birthday in UTC time is "
        "**03-04 15:00** :clock3:*"
    )
    assert embed.thumbnail.url == characters_dict["Fischl"]["icon"]
    assert embed.footer.text == (
        "Missing your favorite character? Join discord.gg/BXkc8CC4uJ and let us know!"
    )


async def test_setting_again_replaces_and_moves_to_the_end(cog, pool):
    await set_birthday(cog, interaction(1))
    await set_birthday(cog, interaction(2))
    found = interaction(1)
    await set_birthday(cog, found, "July", "9", character="None")
    assert await saved(pool) == [
        (2, 3, 5, "Asia/Tokyo", "03-04 15:00", "Fischl"),
        (1, 7, 9, "Asia/Tokyo", "07-08 15:00", "None"),
    ]
    assert not answer(found)[0].thumbnail


@pytest.mark.parametrize(
    "month, day, changes, problem",
    [
        (
            "March",
            "5",
            {"timezone": "Mars"},
            "**Invalid timezone.** Please search and select from the menu or refer to https://arilyn.cc/.",
        ),
        (
            "March",
            "32",
            {},
            "**Invalid day.** Please search and select from the menu.",
        ),
        (
            "March",
            "5",
            {"character": "Nobody"},
            "**Invalid character.** Please search and select from the menu.",
        ),
        (
            "February",
            "30",
            {},
            "The date you specified is not a valid calendar date.",
        ),
        ("April", "31", {}, "The date you specified is not a valid calendar date."),
    ],
)
async def test_set_refuses_what_is_not_on_the_menus(
    cog, pool, month, day, changes, problem
):
    found = interaction()
    await set_birthday(cog, found, month, day, **changes)
    embed, private = answer(found)
    assert private
    assert embed.description == f"<:no:1036810470860013639> {problem}"
    assert embed.color.value == 0xFF0000
    assert await saved(pool) == []


async def test_set_takes_feb_29_and_the_last_days(cog, pool):
    await set_birthday(cog, interaction(1), "February", "29")
    await set_birthday(cog, interaction(2), "January", "31")
    assert [row[4] for row in await saved(pool)] == ["02-28 15:00", "01-30 15:00"]


async def test_get_shows_your_own_and_another_members(cog, pool):
    await set_birthday(cog, interaction())
    found = interaction()
    await birthday.Birthday.birthday_get.callback(cog, found)
    embed, private = answer(found)
    assert not private and embed.color.value == 0xF1EE0C
    assert embed.description == (
        ":birthday: Your birthday is **March 5** *(Asia/Tokyo)*.\n"
        " Your birthday in UTC time is **03-04 15:00** :clock3:"
    )
    assert embed.thumbnail.url == characters_dict["Fischl"]["icon"]

    found, other = interaction(7), MagicMock(id=MEMBER, mention="<@50>")
    await birthday.Birthday.birthday_get.callback(cog, found, other)
    assert answer(found)[0].description == (
        ":birthday: <@50>'s birthday is **March 5** *(Asia/Tokyo)*.\n"
        " In UTC time, it is **03-04 15:00** :clock3:"
    )


async def test_get_says_when_nothing_is_saved(cog):
    found = interaction()
    await birthday.Birthday.birthday_get.callback(cog, found)
    embed, private = answer(found)
    assert private and embed.color.value == 0xFF0000
    assert embed.description.startswith(
        "<:no:1036810470860013639> We don't have your birthday in our database. Use "
    )
    assert embed.description.endswith(" to set your birthday!")

    found, other = interaction(), MagicMock(id=7, mention="<@7>")
    await birthday.Birthday.birthday_get.callback(cog, found, other)
    embed, private = answer(found)
    assert private and embed.description == (
        "<:no:1036810470860013639> We don't have <@7>'s birthday in our database."
    )


async def test_remove_forgets_once(cog, pool):
    await set_birthday(cog, interaction())
    found = interaction()
    await birthday.Birthday.birthday_remove.callback(cog, found)
    embed, private = answer(found)
    assert (embed.title, embed.color.value, private) == (
        "Birthday Removed :pensive:",
        0xE35417,
        False,
    )
    assert await saved(pool) == []
    found = interaction()
    await birthday.Birthday.birthday_remove.callback(cog, found)
    embed, private = answer(found)
    assert (embed.title, embed.color.value, private) == (
        "We could not find your birthday",
        0xCDCB20,
        False,
    )


async def test_export_lists_members_here_by_utc_date(cog, pool):
    for user, month, day in ((1, "July", "9"), (2, "March", "5"), (3, "March", "5")):
        await set_birthday(cog, interaction(user), month, day)
    await set_birthday(cog, interaction(4), "February", "29")
    await set_birthday(cog, interaction(5), "January", "1", character="None")
    found = interaction()

    names = {1: "amber", 2: "bennett", 5: "chongyun"}
    found.guild.fetch_member = AsyncMock()
    found.guild.fetch_member.side_effect = lambda user_id: member(names, user_id)
    await birthday.Birthday.birthday_export.callback(cog, found)
    found.response.defer.assert_awaited_once_with(thinking=True)
    file = found.followup.send.await_args.kwargs["file"]
    assert file.filename == "birthday_export.txt"
    assert file.fp.read().decode() == (
        "Birthdays in Teyvat\n\n"
        "● Mar-5 (Asia/Tokyo): 2 bennett | 03-04 15:00 | Fischl\n"
        "● Jul-9 (Asia/Tokyo): 1 amber | 07-08 15:00 | Fischl\n"
        "● Jan-1 (Asia/Tokyo): 5 chongyun | 12-31 15:00 | None\n"
    )


def member(names, user_id):
    if user_id not in names:
        raise missing()
    found = MagicMock()
    found.name = names[user_id]
    return found


async def enable(cog, found, thread=False):
    channel = MagicMock(id=CHANNEL, mention="<#20>")
    channel.create_webhook = AsyncMock(return_value=MagicMock(id=WEBHOOK))
    role = MagicMock(id=ROLE, mention="<@&40>")
    await birthday.Birthday.birthday_enable.callback(cog, found, channel, role, thread)
    return channel


async def places(pool):
    return [tuple(row)[1:] for row in await store.servers(pool)]


async def test_enable_makes_a_webhook_and_replaces_the_old_settings(cog, pool):
    found = interaction()
    channel = await enable(cog, found)
    channel.create_webhook.assert_awaited_once_with(
        name="Birthday Wishes", reason=f"Created by user ID: {MEMBER}"
    )
    assert await places(pool) == [(GUILD, CHANNEL, WEBHOOK, ROLE, False)]
    embed, private = answer(found)
    assert (embed.title, embed.colour.value, private) == (
        "Birthday wishes enabled!",
        0x00FF00,
        False,
    )
    assert "in <#20> and grant them the <@&40> temporarily." in embed.description
    assert embed.timestamp is not None

    await enable(cog, interaction(), thread=True)
    assert await places(pool) == [(GUILD, CHANNEL, WEBHOOK, ROLE, True)]


async def test_enable_refuses_the_everyone_role(cog, pool):
    found = interaction()
    await birthday.Birthday.birthday_enable.callback(
        cog, found, MagicMock(), found.guild.default_role
    )
    found.response.send_message.assert_awaited_once_with(
        "<:no:1036810470860013639> You have specified an unknown role!",
        ephemeral=True,
    )
    assert await places(pool) == []


async def test_a_failed_webhook_leaves_the_server_off_as_before(cog, pool):
    await enable(cog, interaction())
    channel = MagicMock()
    channel.create_webhook = AsyncMock(side_effect=RuntimeError("no"))
    with pytest.raises(RuntimeError):
        await birthday.Birthday.birthday_enable.callback(
            cog, interaction(), channel, MagicMock(id=ROLE)
        )
    assert await places(pool) == []


async def test_disable_answers_whether_it_was_on(cog, pool):
    await enable(cog, interaction())
    found = interaction()
    await birthday.Birthday.birthday_disable.callback(cog, found)
    embed, private = answer(found)
    assert (embed.title, embed.colour.value, private) == (
        "Birthday Wishes disabled!",
        0xFF0000,
        False,
    )
    assert await places(pool) == []
    found = interaction()
    await birthday.Birthday.birthday_disable.callback(cog, found)
    embed, private = answer(found)
    assert (embed.title, embed.colour.value, private) == (
        "Birthday Wishes is not enabled!",
        0xFFFF00,
        True,
    )


async def test_errors_are_shown_to_the_member(cog):
    found = interaction()
    await cog.birthday_error(found, RuntimeError("boom"))
    found.response.send_message.assert_awaited_once_with("```boom```", ephemeral=True)


# The wishes


class Server:
    """A server with one member, a role and a webhook, recording what happens."""

    def __init__(self, bot, guild_id=GUILD, has_role=False):
        self.role = MagicMock(id=ROLE)
        self.member = MagicMock(id=MEMBER, mention="<@50>", display_name="Mona")
        self.member.name = "mona"
        self.member.roles = [self.role] if has_role else []
        self.member.add_roles = AsyncMock()
        self.member.remove_roles = AsyncMock()
        self.member.send = AsyncMock()
        self.message = MagicMock(jump_url="https://discord.com/x")
        self.message.add_reaction = AsyncMock()
        self.message.create_thread = AsyncMock()
        self.webhook = MagicMock()
        self.webhook.send = AsyncMock(return_value=self.message)
        self.guild = MagicMock(id=guild_id)
        self.guild.name = "Teyvat"
        self.guild.get_role = lambda role_id: self.role if role_id == ROLE else None
        self.guild.fetch_member = AsyncMock(side_effect=self.fetch)
        bot.get_guild = lambda found: self.guild if found == guild_id else None
        bot.fetch_webhook = AsyncMock(side_effect=self.fetch_webhook)

    async def fetch(self, user_id):
        if user_id != MEMBER:
            raise missing()
        return self.member

    async def fetch_webhook(self, webhook_id):
        assert webhook_id == WEBHOOK
        return self.webhook


@pytest.fixture
async def wishes(pool, no_loops):
    bot = MagicMock()
    bot.pool = pool
    found = birthdayEvent.BirthdayCog(bot)
    await found.cog_load()
    await store.enable(pool, GUILD, CHANNEL, WEBHOOK, ROLE, False)
    return found


def at(month, day, hour=15, minute=0):
    return datetime.datetime(2026, month, day, hour, minute, 7, tzinfo=UTC)


async def born(pool, date="03-04 15:00", character="Fischl", user=MEMBER):
    await store.save(pool, user, 3, 5, "Asia/Tokyo", date, character)


async def test_wish_posts_gives_the_role_and_dms(wishes, pool):
    await born(pool)
    server = Server(wishes.bot)
    await wishes.check(at(3, 4))

    sent = server.webhook.send.await_args.kwargs
    assert sent["content"] == (
        ":birthday: Happy birthday to <@50>! Enjoy your special day!"
    )
    assert (sent["username"], sent["avatar_url"], sent["wait"]) == (
        "Fischl",
        characters_dict["Fischl"]["icon"],
        True,
    )
    line = characters_dict["Fischl"]["line"].replace("USER", "**Mona**")
    assert sent["embed"].description == line
    assert sent["embed"].footer.text == (
        'Use "/birthday set" to have your favorite character celebrate your birthday with you!'
    )
    server.message.add_reaction.assert_awaited_once_with("🎂")
    server.message.create_thread.assert_not_awaited()
    server.member.add_roles.assert_awaited_once_with(server.role)

    dm = server.member.send.await_args.kwargs
    assert dm["embed"].title == "Happy Birthday! 🎉🎂🥳"
    assert dm["embed"].description == (
        "Happy birthday, <@50>! **Teyvat** and its staff team wishes you a fantastic "
        "day. May your special day be as amazing as you are!\n\n*PS: **Fischl** has "
        "something to say to you... :eyes:*"
    )
    assert dm["embed"].thumbnail.url == characters_dict["Fischl"]["icon"]
    assert dm["embed"].footer.text == (
        "You received this DM because you've set your birthday and Teyvat has "
        "birthday notifications enabled!"
    )
    button = dm["view"].children[0]
    assert (button.label, button.url, button.style) == (
        "Read Fischl's Message",
        "https://discord.com/x",
        discord.ButtonStyle.link,
    )


async def test_no_favorite_gets_a_random_character_and_another_footer(
    wishes, pool, monkeypatch
):
    await born(pool, character="None")
    server = Server(wishes.bot)
    monkeypatch.setattr(birthdayEvent.random, "choice", lambda found: found[3])
    await wishes.check(at(3, 4))
    sent = server.webhook.send.await_args.kwargs
    assert sent["username"] == characters[3]
    assert sent["embed"].footer.text == (
        'Use "/birthday set" to update your birthday with timezones & favorite character!'
    )


async def test_thread_is_opened_where_the_server_asked(wishes, pool):
    await store.enable(pool, GUILD, CHANNEL, WEBHOOK, ROLE, True)
    await born(pool)
    server = Server(wishes.bot)
    await wishes.check(at(3, 4))
    server.message.create_thread.assert_awaited_once_with(
        name="Wish mona a Happy Birthday 🎉"
    )


@pytest.mark.parametrize(
    "now", [at(3, 4, 15, 15), at(3, 4, 14), at(3, 3), at(4, 4), at(3, 6)]
)
async def test_nothing_happens_at_other_times(wishes, pool, now):
    await born(pool)
    server = Server(wishes.bot)
    await wishes.check(now)
    server.guild.fetch_member.assert_not_awaited()


async def test_feb_29_is_wished_in_a_leap_year(wishes, pool):
    await born(pool, "02-29 01:00")
    server = Server(wishes.bot)
    await wishes.check(datetime.datetime(2028, 2, 28, 1, 0, tzinfo=UTC))
    server.webhook.send.assert_not_awaited()
    await wishes.check(datetime.datetime(2028, 2, 29, 1, 0, tzinfo=UTC))
    server.webhook.send.assert_awaited_once()
    server = Server(wishes.bot, has_role=True)
    await wishes.check(datetime.datetime(2028, 3, 1, 1, 30, tzinfo=UTC))
    server.member.remove_roles.assert_awaited_once_with(server.role)


async def test_feb_29_is_wished_on_feb_28_in_other_years(wishes, pool):
    await born(pool, "02-29 01:00")
    server = Server(wishes.bot)
    await wishes.check(at(2, 27, 1))
    await wishes.check(at(2, 28, 2))
    await wishes.check(at(3, 1, 1))
    server.webhook.send.assert_not_awaited()
    await wishes.check(at(2, 28, 1))
    server.webhook.send.assert_awaited_once()
    server.member.add_roles.assert_awaited_once_with(server.role)


async def test_feb_29_role_is_taken_back_on_march_1_in_other_years(wishes, pool):
    await born(pool, "02-29 01:00")
    server = Server(wishes.bot, has_role=True)
    await wishes.check(at(3, 1, 1, 45))
    server.member.remove_roles.assert_awaited_once_with(server.role)
    server.webhook.send.assert_not_awaited()


async def test_feb_28_is_wished_once_beside_a_feb_29(wishes, pool):
    await born(pool, "02-28 01:00")
    await born(pool, "02-29 01:00", user=77)
    server = Server(wishes.bot)
    await wishes.check(at(2, 28, 1))
    assert [call.args[0] for call in server.guild.fetch_member.await_args_list] == [
        MEMBER,
        77,
    ]


async def test_an_unreadable_date_is_skipped(wishes, pool):
    await born(pool, "02-30 01:00")
    server = Server(wishes.bot)
    await wishes.check(at(3, 1, 1))
    server.guild.fetch_member.assert_not_awaited()


async def test_members_elsewhere_and_servers_the_bot_left_are_skipped(wishes, pool):
    await born(pool, user=77)
    await born(pool)
    await store.enable(pool, 999, CHANNEL, WEBHOOK, ROLE, False)
    server = Server(wishes.bot)
    await wishes.check(at(3, 4))
    assert [call.args for call in server.guild.fetch_member.await_args_list] == [
        (77,),
        (MEMBER,),
    ]
    server.webhook.send.assert_awaited_once()


async def test_a_wish_that_cannot_be_sent_still_gives_the_role_but_no_dm(wishes, pool):
    await born(pool)
    server = Server(wishes.bot)
    server.webhook.send.side_effect = RuntimeError("deleted")
    await wishes.check(at(3, 4))
    server.member.add_roles.assert_awaited_once_with(server.role)
    server.member.send.assert_not_awaited()


async def test_no_dm_without_the_role(wishes, pool):
    await born(pool)
    server = Server(wishes.bot)
    server.guild.get_role = lambda role_id: None
    await wishes.check(at(3, 4))
    server.webhook.send.assert_awaited_once()
    server.member.send.assert_not_awaited()

    server = Server(wishes.bot)
    server.member.add_roles.side_effect = RuntimeError("too high")
    await wishes.check(at(3, 4))
    server.member.send.assert_not_awaited()


async def test_one_failure_does_not_stop_the_next_member(wishes, pool):
    await born(pool, user=77)
    await born(pool)
    server = Server(wishes.bot)
    server.guild.fetch_member.side_effect = lambda user_id: (
        (_ for _ in ()).throw(RuntimeError("discord is down"))
        if user_id == 77
        else server.member
    )
    await wishes.check(at(3, 4))
    server.member.add_roles.assert_awaited_once()


@pytest.mark.parametrize("minute", [0, 15, 30, 45])
async def test_role_is_taken_back_in_the_same_hour_a_day_later(wishes, pool, minute):
    await born(pool)
    server = Server(wishes.bot, has_role=True)
    await wishes.check(at(3, 5, 15, minute))
    server.member.remove_roles.assert_awaited_once_with(server.role)
    server.webhook.send.assert_not_awaited()


async def test_role_stays_when_the_member_lost_it_or_the_hour_differs(wishes, pool):
    await born(pool)
    server = Server(wishes.bot)
    await wishes.check(at(3, 5))
    server.member.remove_roles.assert_not_awaited()
    server = Server(wishes.bot, has_role=True)
    await wishes.check(at(3, 5, 16))
    server.guild.fetch_member.assert_not_awaited()


@pytest.mark.parametrize(
    "date,now",
    [
        ("03-31 15:00", at(4, 1)),
        ("12-31 15:00", at(1, 1)),
        ("02-28 15:00", at(3, 1)),
        ("02-28 15:00", datetime.datetime(2028, 2, 29, 15, 0, tzinfo=UTC)),
    ],
)
async def test_role_is_taken_back_across_a_month_end(wishes, pool, date, now):
    await born(pool, date)
    server = Server(wishes.bot, has_role=True)
    await wishes.check(now)
    server.member.remove_roles.assert_awaited_once_with(server.role)
    server.webhook.send.assert_not_awaited()


async def test_each_quarter_is_checked_once(wishes, monkeypatch):
    seen = []
    wishes.check = AsyncMock(side_effect=lambda now: seen.append(now.minute))

    class Clock(datetime.datetime):
        minute_now = 0

        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 4, 15, cls.minute_now, 30, tzinfo=tz)

    monkeypatch.setattr(birthdayEvent.datetime, "datetime", Clock)
    for minute in (0, 0, 1, 14, 15, 15, 30, 45, 46):
        Clock.minute_now = minute
        await wishes.birthday_task.coro(wishes)
    assert seen == [0, 15, 30, 45]


async def test_a_failed_check_does_not_end_the_loop(wishes, monkeypatch):
    wishes.check = AsyncMock(side_effect=RuntimeError("database is down"))
    monkeypatch.setattr(birthdayEvent, "MINUTES", range(60))
    await wishes.birthday_task.coro(wishes)
    wishes.check.assert_awaited_once()


async def test_help_reads_the_servers_settings(pool):
    await store.create(pool)
    assert await store.server(pool, GUILD) is None
    await store.enable(pool, GUILD, CHANNEL, WEBHOOK, ROLE, True)
    found = await store.server(pool, GUILD)
    assert (found["channel_id"], found["role_id"]) == (CHANNEL, ROLE)
