import datetime
import json
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, call

import discord
import pytest
from discord.ext import tasks

from cogs import history, logs, status, sync

SUB = discord.AppCommandOptionType.subcommand
GROUP = discord.AppCommandOptionType.subcommand_group
TEXT = discord.AppCommandOptionType.string
CHANNEL = 1106664283250626671
KEY = {"X-API-Key": "test"}


def command(name, command_id, *options):
    found = MagicMock(
        id=command_id, options=[MagicMock(type=kind) for _, kind in options]
    )
    found.name = name
    for option, (option_name, _) in zip(found.options, options):
        option.name = option_name
    return found


async def test_ready_saves_every_command_id(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets").mkdir()
    bot = MagicMock()
    bot.tree.fetch_commands = AsyncMock(
        return_value=[
            command("help", 1),
            command("tag", 2, ("enable", SUB), ("set", GROUP), ("loose", TEXT)),
        ]
    )
    await sync.CommandSync(bot).on_ready()
    saved = (tmp_path / "assets" / "commands.json").read_text()
    assert saved == json.dumps(
        {"help": "1", "tag": "2", "tag enable": "2", "tag set": "2"}, indent=4
    )
    assert (
        capsys.readouterr().out
        == "Successfully updated & synced assets/commands.json\n"
    )


async def test_ready_says_when_commands_cannot_be_fetched(capsys):
    bot = MagicMock()
    bot.tree.fetch_commands = AsyncMock(side_effect=RuntimeError("down"))
    await sync.CommandSync(bot).on_ready()
    assert capsys.readouterr().out == "Failed to fetch application commands: down\n"


async def test_status_takes_turns(no_loops, monkeypatch):
    waits = []
    monkeypatch.setattr(status.asyncio, "sleep", AsyncMock(side_effect=waits.append))
    bot = MagicMock()
    shown = []

    async def change_presence(status, activity):
        shown.append((status, activity.type, activity.name, len(waits)))

    bot.change_presence = change_presence
    cog = status.StatusCog(bot)
    assert (cog.status_task.seconds, cog.status_task.minutes) == (0, 0)
    await cog.status_task.coro(cog)
    online = discord.Status.online
    assert shown == [
        (online, discord.ActivityType.playing, "Genshin Impact", 0),
        (online, discord.ActivityType.listening, "Website: fischl.app", 1),
        (online, discord.ActivityType.playing, "Support: discord.gg/kaycd3fxHh", 2),
    ]
    assert waits == [30, 30]


class Clock(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 2, 3, 4, 5, 678901, tzinfo=tz)


async def heartbeat(monkeypatch, loop_number, old=None):
    """Runs one heartbeat and gives the Firebase calls it made."""
    monkeypatch.setattr(status.datetime, "datetime", Clock)
    monkeypatch.setattr(status.time, "time", lambda: 1_700_000_000.5)
    base = MagicMock()
    base.reference.return_value.order_by_child.return_value.end_at.return_value.get.return_value = (
        old
    )
    monkeypatch.setattr(status, "db", base)
    bot = MagicMock(latency=0.0456)
    cog = status.StatusCog(bot)
    assert cog.status_heartbeat.minutes == 1
    cog.status_heartbeat._current_loop = loop_number
    await cog.status_heartbeat.coro(cog)
    return base


BEAT = [
    call.reference("Bot Status"),
    call.reference().update(
        {"last_ping": "2026-01-02T03:04:05.678+00:00Z", "last_latency_ms": 45}
    ),
    call.reference("Bot Status/ping_history"),
    call.reference().push({"timestamp": 1_700_000_000_500, "latency_ms": 45}),
]
SWEEP = [
    call.reference("Bot Status/ping_history"),
    call.reference().order_by_child("timestamp"),
    call.reference().order_by_child().end_at(1_700_000_000_500 - 86_400_000),
    call.reference().order_by_child().end_at().get(),
]


async def test_heartbeat_between_sweeps(no_loops, monkeypatch):
    assert (await heartbeat(monkeypatch, 59)).mock_calls == BEAT
    assert (await heartbeat(monkeypatch, 30)).mock_calls == BEAT
    assert (await heartbeat(monkeypatch, 90)).mock_calls == BEAT


async def test_heartbeat_fails_on_old_pings_that_are_not_a_record(
    no_loops, monkeypatch, capsys
):
    swept = await heartbeat(monkeypatch, 60, old=["a"])
    assert swept.mock_calls == BEAT + SWEEP
    assert capsys.readouterr().out.startswith("Failed to send heartbeat: ")


async def test_heartbeat_sweeps_every_hour(no_loops, monkeypatch):
    assert (await heartbeat(monkeypatch, 60)).mock_calls == BEAT + SWEEP
    assert (await heartbeat(monkeypatch, 0, old={})).mock_calls == BEAT + SWEEP
    swept = await heartbeat(monkeypatch, 120, old={"a": {}, "b": {}})
    assert swept.mock_calls == BEAT + SWEEP + [
        call.reference().update({"a": None, "b": None})
    ]


async def test_heartbeat_failure_is_printed(no_loops, monkeypatch, capsys):
    base = MagicMock()
    base.reference.side_effect = RuntimeError("down")
    monkeypatch.setattr(status, "db", base)
    cog = status.StatusCog(MagicMock(latency=0.1))
    await cog.status_heartbeat.coro(cog)
    assert capsys.readouterr().out == "Failed to send heartbeat: down\n"


async def test_status_loops_start_wait_for_ready_and_stop_on_unload(monkeypatch):
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    started = []
    monkeypatch.setattr(tasks.Loop, "start", lambda self, *args: started.append(self))
    cog = status.StatusCog(bot)
    assert started == [cog.status_task, cog.status_heartbeat]
    for loop in (cog.status_task, cog.status_heartbeat):
        await loop._before_loop(cog)
    assert bot.wait_until_ready.await_count == 2
    cog.status_task.cancel = MagicMock()
    cog.status_heartbeat.cancel = MagicMock()
    cog.cog_unload()
    cog.status_task.cancel.assert_called_once_with()
    cog.status_heartbeat.cancel.assert_called_once_with()


@pytest.fixture
def logging_kept(monkeypatch):
    """Puts print, the crash hook and the log clock back after a test."""
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(logging.Formatter, "converter", logging.Formatter.converter)


async def test_logging_setup(no_loops, logging_kept, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    basic = MagicMock()
    monkeypatch.setattr(logs.logging, "basicConfig", basic)
    info, error = MagicMock(), MagicMock()
    monkeypatch.setattr(logs.logging, "info", info)
    monkeypatch.setattr(logs.logging, "error", error)
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    cog = logs.LoggingSetupCog(bot)
    assert cog.setup_logging.count == 1
    await cog.setup_logging._before_loop(cog)
    bot.wait_until_ready.assert_awaited_once_with()
    real = sys.stdout
    await cog.setup_logging.coro(cog)

    (), config = basic.call_args
    assert set(config) == {"level", "handlers"} and config["level"] == logging.INFO
    file, console = config["handlers"]
    assert isinstance(file, logging.handlers.RotatingFileHandler)
    assert (file.baseFilename, file.maxBytes, file.backupCount, file.level) == (
        str(tmp_path / "console_output.log"),
        20 * 1024 * 1024,
        3,
        logging.INFO,
    )
    assert type(console) is logging.StreamHandler
    assert (console.stream, console.level) == (real, logging.INFO)
    for handler in (file, console):
        assert handler.formatter._fmt == "%(asctime)s - %(levelname)s - %(message)s"
        assert handler.formatter.datefmt == "%Y-%m-%d %H:%M:%S"
    file.close()

    assert sys.stdout is not real and sys.stdout.stdout is real
    sys.stdout.write("  hello \n")
    sys.stdout.write(" \n")
    sys.stdout.write("")
    assert sys.stdout.flush() is None
    info.assert_called_once_with("hello")

    pacific = datetime.datetime.now(datetime.timezone.utc).astimezone(
        __import__("pytz").timezone("America/Los_Angeles")
    )
    assert logging.Formatter.converter(0)[:4] == pacific.timetuple()[:4]

    crash = (ValueError, ValueError("x"), None)
    sys.excepthook(*crash)
    error.assert_called_once_with("Uncaught exception", exc_info=crash)
    plain = MagicMock()
    monkeypatch.setattr(sys, "__excepthook__", plain)
    stop = (KeyboardInterrupt, KeyboardInterrupt(), None)
    sys.excepthook(*stop)
    plain.assert_called_once_with(*stop)
    error.assert_called_once()


def message(message_id, content="hi", channel=CHANNEL, day=1, edited=None, author=True):
    found = MagicMock()
    found.id, found.content, found.channel.id = message_id, content, channel
    found.created_at = datetime.datetime(2026, 1, day, 12, tzinfo=datetime.timezone.utc)
    found.edited_at = edited
    if author:
        found.author.id, found.author.name, found.author.bot = 5, "amy", False
        found.author.global_name, found.author.display_name = "Amy", "Amy A"
        found.author.display_avatar.url = "https://cdn/amy.png"
    else:
        found.author = None
    return found


def written(message_id, content="hi", day=1, edited=None):
    return {
        "id": str(message_id),
        "author": {
            "id": "5",
            "name": "amy",
            "global_name": "Amy",
            "display_name": "Amy A",
            "bot": False,
            "avatar_url": "https://cdn/amy.png",
        },
        "content": content,
        "timestamp": f"2026-01-0{day}T12:00:00+00:00",
        "edited_timestamp": edited,
    }


@pytest.fixture
def api(monkeypatch):
    """The message history cog with no web server or backfill started."""
    thread = MagicMock()
    monkeypatch.setattr(history.threading, "Thread", thread)
    monkeypatch.setattr(history.time, "time", lambda: 1_700_000_000)
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    cog = history.MessageHistoryAPICog(bot)
    thread.assert_called_once_with(target=cog.run_server, daemon=True)
    thread.return_value.start.assert_called_once_with()
    cog.started = bot.loop.create_task.call_args[0][0]
    cog.web = cog.app.test_client()
    yield cog
    cog.started.close()


def test_history_server_address(api, monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(api.app, "run", run)
    api.run_server()
    run.assert_called_once_with(host="0.0.0.0", port=2030, use_reloader=False)
    assert sorted(rule.rule for rule in api.app.url_map.iter_rules()) == [
        "/messages",
        "/static/<path:filename>",
        "/summary",
    ]


def test_history_needs_the_key(api):
    for path in ("/summary", "/messages"):
        for headers in (
            {},
            {"X-API-Key": ""},
            {"X-API-Key": "wrong"},
            {"X-API-Key": "tess"},
        ):
            answer = api.web.get(path, headers=headers)
            assert (answer.status_code, answer.json) == (401, {"error": "Unauthorized"})
            assert answer.headers["WWW-Authenticate"] == "ApiKey"
    assert api.rate_limits == {}


def test_history_warming(api):
    for path in ("/summary", "/messages"):
        answer = api.web.get(path, headers=KEY)
        assert (answer.status_code, answer.json) == (
            503,
            {"error": "Cache warming, full message history is still being fetched"},
        )
        assert answer.headers["Retry-After"] == "30"
        assert answer.headers["Cache-Control"] == "no-cache"


def test_history_rate_limit(api, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(history.time, "monotonic", lambda: now[0])
    forwarded = {**KEY, "X-Forwarded-For": "1.1.1.1 , 2.2.2.2"}
    for _ in range(60):
        assert api.web.get("/summary", headers=forwarded).status_code == 503
    assert set(api.rate_limits) == {"1.1.1.1"}
    answer = api.web.get("/messages", headers=forwarded)
    assert (answer.status_code, answer.json) == (429, {"error": "Rate limit exceeded"})
    assert answer.headers["Retry-After"] == "1.0"
    now[0] += 0.25
    assert api.web.get("/summary", headers=forwarded).headers["Retry-After"] == "0.75"
    now[0] += 1
    assert api.web.get("/summary", headers=forwarded).status_code == 503
    assert api.web.get("/summary", headers=forwarded).status_code == 429
    assert api.web.get("/summary", headers=KEY).status_code == 503
    assert set(api.rate_limits) == {"1.1.1.1", "127.0.0.1"}
    now[0] += 1000
    api.web.get("/summary", headers=forwarded)
    assert api.rate_limits["1.1.1.1"] == (59, now[0])


async def test_history_backfill(api):
    channel = MagicMock()

    def past(limit, oldest_first):
        assert (limit, oldest_first) == (None, True)

        async def each():
            for number in (1, 2, 3):
                assert not api.backfill_complete
                yield message(number, day=number)

        return each()

    channel.history = past
    api.bot.get_channel.return_value = channel
    await api.started
    api.bot.wait_until_ready.assert_awaited_once_with()
    api.bot.get_channel.assert_called_once_with(CHANNEL)
    assert api.backfill_complete and api.revision == 3
    assert list(api.messages) == [3, 2, 1]


async def test_history_backfill_fetches_an_unknown_channel_and_prints_failure(
    api, capsys
):
    api.bot.get_channel.return_value = None
    api.bot.fetch_channel = AsyncMock(side_effect=RuntimeError("gone"))
    await api.started
    api.bot.fetch_channel.assert_awaited_once_with(CHANNEL)
    assert not api.backfill_complete
    assert capsys.readouterr().out == (
        "#introduce-yourself channel messages backfill failed: gone\n"
    )


async def test_history_follows_the_channel(api):
    edited = datetime.datetime(2026, 1, 3, tzinfo=datetime.timezone.utc)
    await api.on_message(message(1))
    await api.on_message(message(2, day=2))
    await api.on_message(message(9, channel=7))
    await api.on_message_edit(None, message(1, "new", edited=edited))
    await api.on_message_edit(None, message(8, "unknown"))
    await api.on_message_edit(None, message(2, "elsewhere", channel=7))
    assert list(api.messages.values()) == [
        written(2, day=2),
        written(1, "new", edited="2026-01-03T00:00:00+00:00"),
    ]
    assert api.revision == 3
    await api.on_message_delete(message(2, channel=7))
    await api.on_message_delete(message(8))
    await api.on_message_delete(message(2))
    assert list(api.messages) == [1] and api.revision == 4
    await api.on_message(message(3, author=False))
    assert api.messages[3]["author"] is None
    odd = message(4)
    odd.author.display_avatar = None
    await api.on_message(odd)
    assert api.messages[4]["author"]["avatar_url"] is None


async def test_history_summary(api):
    api.backfill_complete = True
    empty = api.web.get("/summary", headers=KEY)
    assert empty.json == {
        "channel_id": str(CHANNEL),
        "total_messages": 0,
        "first_message": None,
        "last_message": None,
        "messages_per_day": {},
        "cache": {
            "backfill_complete": True,
            "last_update": "2023-11-14T22:13:20+00:00",
            "revision": 0,
        },
    }
    for number, day in ((1, 1), (2, 1), (3, 2)):
        await api.on_message(message(number, day=day))
    answer = api.web.get("/summary", headers=KEY)
    assert answer.status_code == 200
    assert answer.get_data(as_text=True).index("channel_id") < answer.get_data(
        as_text=True
    ).index("cache")
    assert list(answer.json) == list(empty.json)
    assert {k: v for k, v in answer.json.items() if k != "cache"} == {
        "channel_id": str(CHANNEL),
        "total_messages": 3,
        "first_message": "2026-01-02T12:00:00+00:00",
        "last_message": "2026-01-01T12:00:00+00:00",
        "messages_per_day": {"2026-01-02": 1, "2026-01-01": 2},
    }
    assert list(answer.json["messages_per_day"]) == ["2026-01-02", "2026-01-01"]
    assert answer.json["cache"]["revision"] == 3


async def test_history_etag(api):
    import hashlib

    api.backfill_complete = True
    await api.on_message(message(1))
    answer = api.web.get("/messages", headers=KEY)
    tag = hashlib.sha1(b"1:1").hexdigest()
    assert answer.headers["ETag"] == f'"{tag}"'
    assert answer.headers["Cache-Control"] == "no-cache"
    for sent in (f'"{tag}"', tag, f'"other", "{tag}"'):
        again = api.web.get("/summary", headers={**KEY, "If-None-Match": sent})
        assert (again.status_code, again.data) == (304, b"")
        assert again.headers["Cache-Control"] == "no-cache"
        assert "ETag" not in again.headers
    assert (
        api.web.get("/messages", headers={**KEY, "If-None-Match": '"old"'}).status_code
        == 200
    )


async def test_history_pages(api):
    api.backfill_complete = True
    assert api.web.get("/messages", headers=KEY).json == {
        "page": 1,
        "page_size": 100,
        "total": 0,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False,
        "next_page": None,
        "prev_page": None,
        "messages": [],
    }
    for number in range(1, 6):
        await api.on_message(message(number, day=number))

    def page(query):
        found = api.web.get(f"/messages{query}", headers=KEY).json
        found["messages"] = [int(item["id"]) for item in found["messages"]]
        return tuple(found.values())

    assert list(api.web.get("/messages", headers=KEY).json["messages"][0]) == [
        "id",
        "author",
        "content",
        "timestamp",
        "edited_timestamp",
    ]
    assert page("") == (1, 100, 5, 1, False, False, None, None, [5, 4, 3, 2, 1])
    assert page("?limit=2") == (1, 2, 5, 3, True, False, 2, None, [5, 4])
    assert page("?limit=2&page=2") == (2, 2, 5, 3, True, True, 3, 1, [3, 2])
    assert page("?limit=2&page=3") == (3, 2, 5, 3, False, True, None, 2, [1])
    assert page("?limit=2&page=99") == (3, 2, 5, 3, False, True, None, 2, [1])
    assert page("?limit=2&page=-4") == (1, 2, 5, 3, True, False, 2, None, [5, 4])
    assert page("?limit=x&page=y") == (
        1,
        100,
        5,
        1,
        False,
        False,
        None,
        None,
        [5, 4, 3, 2, 1],
    )
    assert page("?limit=0") == (1, 1, 5, 5, True, False, 2, None, [5])
    assert page("?limit=9999")[1] == 500


def test_ready_is_listened_for():
    listeners = sync.CommandSync(MagicMock()).get_listeners()
    assert [name for name, _ in listeners] == ["on_ready"]
