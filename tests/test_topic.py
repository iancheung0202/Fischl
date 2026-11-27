from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Utility import topic
from commands.Utility import topicStore as store

OWNER, REVIEW_CHANNEL, SUGGESTER = 692254240290242601, 1026867655468126249, 42


@pytest.fixture
async def cog(pool):
    bot = MagicMock()
    bot.pool = pool
    found = topic.Topic(bot)
    await found.cog_load()
    return found


def interaction(pool, user=OWNER):
    found = MagicMock()
    found.client.pool = pool
    found.user.id = user
    found.user.mention = f"<@{user}>"
    found.response.send_message = AsyncMock()
    found.response.send_modal = AsyncMock()
    found.response.defer = AsyncMock()
    found.followup.send = AsyncMock()
    found.message.edit = AsyncMock()
    return found


def suggestion(found, text="Best element: fire?"):
    found.message.embeds = [
        discord.Embed(
            description=f"Suggested by: <@{SUGGESTER}>\nTopic: {text}\n\nSimilar topics:\nNone"
        )
    ]
    return found


async def saved(pool):
    rows = await pool.fetch("SELECT query, suggester_id FROM topics ORDER BY id")
    return [tuple(row) for row in rows]


async def test_ids_and_commands_look_the_same():
    assert (topic.OWNER, topic.REVIEW_CHANNEL) == (OWNER, REVIEW_CHANNEL)
    get, add = topic.Topic.topic_get, topic.Topic.topic_add
    assert (get.name, get.description, get.guild_only) == (
        "topic",
        "Get a random Genshin topic to chat on",
        True,
    )
    assert (add.name, add.description, add.guild_only) == (
        "add-topic",
        "Adds a topic to our bot's database",
        False,
    )
    assert [(p.name, p.description) for p in add.parameters] == [
        ("topic", "ONE topic at a time")
    ]
    view = topic.TopicAcceptRejectView()
    assert view.timeout is None
    assert [(b.custom_id, b.label, b.style) for b in view.children] == [
        ("accept_topic", "Accept", discord.ButtonStyle.green),
        ("reject_topic", "Reject", discord.ButtonStyle.red),
    ]


async def test_topic_posts_one_saved_topic(cog):
    for text in ("one", "two", "three"):
        await store.add(cog.bot.pool, text, SUGGESTER)
    seen = set()
    for _ in range(40):
        found = interaction(cog.bot.pool)
        await cog.topic_get.callback(cog, found)
        found.response.defer.assert_awaited_once_with()
        embed = found.followup.send.call_args.kwargs["embed"]
        assert embed.colour.value == 0x00B0FF
        assert embed.footer.text == (
            '🆕 Use "/add-topic" to suggest freshly-baked topics to our developer!'
        )
        seen.add(embed.title)
    assert seen == {"one", "two", "three"}


async def test_add_topic_sends_the_suggestion_to_the_owner(cog, monkeypatch):
    await store.add(cog.bot.pool, "old one", SUGGESTER)
    await store.add(cog.bot.pool, "old two", SUGGESTER)
    generate = AsyncMock(return_value="1. old one")
    monkeypatch.setattr(topic, "generate", generate)
    channel = MagicMock()
    channel.send = AsyncMock()
    cog.bot.get_channel = lambda channel_id: (
        channel if channel_id == REVIEW_CHANNEL else None
    )
    found = interaction(cog.bot.pool, user=SUGGESTER)

    await cog.topic_add.callback(cog, found, "new idea")

    prompt = generate.call_args.args[0]
    assert "New topic:\n    new idea\n" in prompt
    assert "Existing topics:\n    old one\nold two\n" in prompt
    args, kwargs = channel.send.call_args
    assert args == (f"<@{OWNER}>",)
    embed = kwargs["embed"]
    assert (embed.title, embed.colour.value) == ("New Topic Suggestion", 0xFFFF00)
    assert embed.description == (
        f"Suggested by: <@{SUGGESTER}>\nTopic: new idea\n\nSimilar topics:\n1. old one"
    )
    assert isinstance(kwargs["view"], topic.TopicAcceptRejectView)
    found.response.send_message.assert_awaited_once_with(
        ":white_check_mark: Your topic suggestion has been sent for review!\n\n> new idea"
    )
    assert await saved(cog.bot.pool) == [("old one", SUGGESTER), ("old two", SUGGESTER)]


async def test_only_the_owner_may_accept_or_reject(cog):
    view = topic.TopicAcceptRejectView()
    for button in (view.accept, view.reject):
        found = suggestion(interaction(cog.bot.pool, user=SUGGESTER))
        await button.callback(found)
        found.response.send_message.assert_awaited_once_with(
            "Only the owner can do this.", ephemeral=True
        )
        found.response.send_modal.assert_not_awaited()
        found.message.edit.assert_not_awaited()


async def test_accept_opens_the_topic_for_editing(cog):
    found = suggestion(interaction(cog.bot.pool))
    await topic.TopicAcceptRejectView().accept.callback(found)
    modal = found.response.send_modal.call_args.args[0]
    assert (modal.title, modal.topic_input.label) == ("Edit Topic", "Topic")
    assert modal.topic_input.default == "Best element: fire?".split(": ")[0]
    assert (modal.suggester_id, modal.message) == (SUGGESTER, found.message)


async def test_reject_marks_the_suggestion(cog):
    found = suggestion(interaction(cog.bot.pool), "plain topic")
    await topic.TopicAcceptRejectView().reject.callback(found)
    embed = found.message.edit.call_args.kwargs["embed"]
    assert (embed.title, embed.description, embed.colour.value) == (
        "Topic Suggestion Rejected",
        "Topic: plain topic",
        0xFF0000,
    )
    assert found.message.edit.call_args.kwargs["view"] is None
    found.response.defer.assert_awaited_once_with()


async def submit(pool, text):
    message = MagicMock()
    message.edit = AsyncMock()
    modal = topic.TopicModal("draft", SUGGESTER, message)
    modal.topic_input._value = text
    found = interaction(pool)
    await modal.on_submit(found)
    return found, message


async def test_submitting_saves_the_edited_topic(cog):
    found, message = await submit(cog.bot.pool, "edited")
    assert await saved(cog.bot.pool) == [("edited", SUGGESTER)]
    embed = message.edit.call_args.kwargs["embed"]
    assert (embed.title, embed.description, embed.colour.value) == (
        "Topic Suggestion Accepted",
        "Added: edited",
        0x00FF00,
    )
    assert message.edit.call_args.kwargs["view"] is None
    found.response.send_message.assert_awaited_once_with("Topic added!", ephemeral=True)


async def test_submitting_a_saved_topic_again_is_refused(cog):
    await store.add(cog.bot.pool, "edited", 7)
    found, message = await submit(cog.bot.pool, "edited")
    found.response.send_message.assert_awaited_once_with(
        "This topic already exists!", ephemeral=True
    )
    message.edit.assert_not_awaited()
    assert await saved(cog.bot.pool) == [("edited", 7)]
    await submit(cog.bot.pool, "Edited")
    assert len(await saved(cog.bot.pool)) == 2
