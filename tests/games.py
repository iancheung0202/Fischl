"""Stand-ins for Discord that the minigame tests share."""

import asyncio
import itertools
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events import helperFunctions, quests
from commands.Events.games import common

GUILD, CHANNEL = 10, 30
ids = itertools.count(1000)


def member(uid: int, name: str = None, bot: bool = False):
    """Gives a member with the few fields the minigames read."""
    name = name or f"member{uid}"
    avatar = SimpleNamespace(url=f"https://cdn/{uid}.png")
    return SimpleNamespace(
        id=uid,
        name=name,
        display_name=name,
        mention=f"<@{uid}>",
        bot=bot,
        roles=[],
        avatar=avatar,
        default_avatar=avatar,
        display_avatar=avatar,
    )


class Message:
    """A sent message that remembers its latest content, embed and view."""

    def __init__(self, channel, author=None, content=None, embed=None, view=None):
        self.id = next(ids)
        self.channel = channel
        self.guild = channel.guild
        self.author = author or member(1, "Fischl", bot=True)
        self.content = content
        self.embeds = [embed] if embed else []
        self.view = view
        self.deleted = False
        self.replies = []
        self.jump_url = f"https://discord/{self.id}"
        self.mentions = []
        self.add_reaction = AsyncMock()

    @property
    def embed(self):
        return self.embeds[0] if self.embeds else None

    async def edit(self, **changes):
        if "content" in changes:
            self.content = changes["content"]
        if "embed" in changes:
            self.embeds = [changes["embed"]] if changes["embed"] else []
        if "view" in changes:
            self.view = changes["view"]
        return self

    async def delete(self, **_):
        self.deleted = True

    async def reply(self, content=None, **parts):
        sent = await self.channel.send(content, **parts)
        self.replies.append(sent)
        return sent


class Channel:
    """A text channel that keeps what was sent and gives back a set history."""

    def __init__(self, authors=()):
        self.id = CHANNEL
        self.name = "chat"
        self.guild = SimpleNamespace(id=GUILD, name="Server")
        self.guild.get_member = lambda uid: None
        self.guild.fetch_member = AsyncMock(side_effect=lambda uid: member(uid))
        self.sent = []
        self.past = [Message(self, author, "hello there friend") for author in authors]

    async def send(self, content=None, **parts):
        sent = Message(self, None, content, parts.get("embed"), parts.get("view"))
        sent.file = parts.get("file")
        self.sent.append(sent)
        return sent

    def history(self, limit=None, **_):
        async def walk():
            for message in self.past[:limit]:
                yield message

        return walk()

    @property
    def last(self):
        return self.sent[-1]

    def texts(self) -> list:
        """Gives everything sent as text: the content, else the embed's description."""
        return [
            m.content or (m.embed.description if m.embed else "") for m in self.sent
        ]


class Press:
    """One member's press of a button or send of a form, remembering how it was answered."""

    def __init__(self, client, message, user):
        self.client = client
        self.message = message
        self.channel = message.channel
        self.guild = message.guild
        self.guild_id = message.guild.id
        self.user = user if hasattr(user, "id") else member(user)
        self.said = []
        self.modal = None
        self.reply = None
        self.deferred = False
        self.response = MagicMock()
        self.response.send_message = self.say
        self.response.edit_message = self.edit
        self.response.defer = self.defer
        self.response.send_modal = self.open
        self.response.is_done = lambda: bool(self.said or self.deferred)
        self.followup = MagicMock()
        self.followup.send = self.say
        self.edit_original_response = message.edit

    async def say(self, content=None, **parts):
        self.said.append(content or parts.get("embed"))
        if not parts.get("ephemeral"):
            return await self.channel.send(content, **parts)
        self.reply = Message(self.channel, None, content, parts.get("embed"), parts.get("view"))  # fmt: skip

    async def original_response(self):
        return self.reply

    async def edit(self, **changes):
        self.deferred = True
        await self.message.edit(**changes)

    async def defer(self, **_):
        self.deferred = True

    async def open(self, modal):
        self.modal = modal


def button(view, label: str = None, index: int = None):
    """Finds a view's button by its label or its place."""
    if index is not None:
        return view.children[index]
    return next(
        child for child in view.children if getattr(child, "label", None) == label
    )


async def press(client, message, user, label: str = None, index: int = None) -> Press:
    """Presses a button on a message's view as a member; gives how it was answered."""
    interaction = Press(client, message, user)
    view = message.view
    if await view.interaction_check(interaction):
        await button(view, label, index).callback(interaction)
    return interaction


def typed(client, channel, *lines) -> list:
    """Makes the bot hear these (member, text) lines one by one, then nothing more; gives the messages."""
    heard = [Message(channel, member(uid), text) for uid, text in lines]
    for message in heard:
        message.author.guild = channel.guild
    waiting = list(heard)

    async def wait_for(event, check=None, timeout=None):
        while waiting:
            message = waiting.pop(0)
            if check is None or check(message):
                return message
        raise asyncio.TimeoutError

    client.wait_for = wait_for
    return heard


@pytest.fixture
async def client(pool, monkeypatch):
    """A bot on an empty database with the minigame tables; quests are recorded, not run."""
    bot = MagicMock(pool=pool)
    bot.user = member(1, "Fischl", bot=True)
    bot.add_cog = AsyncMock()
    await helperFunctions.setup(bot)
    await quests.setup(bot)
    bot.quests = []

    async def update_quest(uid, gid, cid, quest, client, **_):
        bot.quests.append((uid, quest))

    monkeypatch.setattr(common, "update_quest", update_quest)
    monkeypatch.setattr(quests, "update_quest", AsyncMock())
    monkeypatch.setattr(helperFunctions, "delayed_check_milestones", AsyncMock())
    return bot


async def mora(pool) -> dict:
    """Gives each member's total Mora in the test server."""
    rows = await pool.fetch(
        "SELECT uid, SUM(count) AS total FROM minigame_mora WHERE gid = $1 GROUP BY uid",
        GUILD,
    )
    return {row["uid"]: row["total"] for row in rows}


def won(client, uid: int) -> list:
    """Gives the quests counted for a member, merged in order."""
    return [quest for who, quest in client.quests if who == uid]


async def started(channel, game):
    """Runs a minigame that waits for its own end; gives its task once its message is up."""
    task = asyncio.create_task(game)
    for _ in range(200):
        if channel.sent and channel.last.view:
            return task
        await asyncio.sleep(0.01)
    raise AssertionError("the minigame never started")


def button_styles(view) -> dict:
    """Gives the buttons that are not grey, by label."""
    return {
        child.label: child.style
        for child in view.children
        if child.style != discord.ButtonStyle.secondary
    }
