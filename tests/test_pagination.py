from unittest.mock import AsyncMock, MagicMock

import discord

from utils.pagination import BasePaginationView


def pages(count=2):
    return [discord.Embed(title=str(number)) for number in range(count)]


async def timed_out(message):
    view = BasePaginationView(pages())
    view.message = message
    await view.on_timeout()
    (button,) = view.children
    assert (button.label, button.disabled) == ("Timed out", True)
    return view


async def test_timeout_edits_a_plain_message():
    message = MagicMock(edit=AsyncMock())
    view = await timed_out(message)
    message.edit.assert_awaited_once_with(view=view)


async def test_timeout_edits_the_message_behind_an_interaction_edit():
    message = MagicMock(edit=AsyncMock())
    response = MagicMock(spec=discord.InteractionCallbackResponse, resource=message)
    view = await timed_out(response)
    message.edit.assert_awaited_once_with(view=view)


async def test_timeout_with_no_message_or_a_deleted_one():
    await timed_out(None)
    await timed_out(MagicMock(spec=discord.InteractionCallbackResponse, resource=None))
    gone = discord.NotFound(MagicMock(status=404), "gone")
    await timed_out(MagicMock(edit=AsyncMock(side_effect=gone)))
