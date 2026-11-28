"""A drop pack whose message is gone times out quietly."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from commands.Events import dropPack


async def test_drop_pack_timeout_with_deleted_message():
    view = dropPack.DropPackView(1, 2, [], False)
    gone = discord.NotFound(MagicMock(status=404, reason="Not Found"), "gone")
    view.message = SimpleNamespace(edit=AsyncMock(side_effect=gone))
    await view.on_timeout()
    assert all(child.disabled for child in view.children)
