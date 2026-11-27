import asyncio

import discord
from discord.ext import commands

from commands.Sticky import stickyStore as store

DELAY = 10  # seconds a channel stays quiet before its message is sent again


class StickyHandler(commands.Cog):
    def __init__(self, bot):
        """Starts with no watched channels and no waits; cog_load fills them in."""
        self.client = bot
        self.enabled = set()
        self.loading = asyncio.Lock()
        self.waiting = {}

    async def cog_load(self):
        """Makes the tables and reads the watched channels before the first message."""
        await store.create(self.client.pool)
        await self.load()

    async def load(self):
        """Reads the watched channels into memory."""
        async with self.loading:
            self.enabled = await store.enabled(self.client.pool)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Starts the channel's wait again on every message that is not the bot's."""
        if message.author == self.client.user:
            return
        channel = message.channel
        if channel.id not in self.enabled:
            return

        task = self.waiting.get(channel.id)
        if task and not task.done():
            task.cancel()
        self.waiting[channel.id] = asyncio.create_task(self.restick_later(channel))

    async def restick_later(self, channel):
        """Sends the message again once the channel has been quiet long enough."""
        try:
            await asyncio.sleep(DELAY)
            await self.restick(channel)
        except asyncio.CancelledError:
            return

    async def restick(self, channel):
        """Deletes the channel's oldest stuck message and sends it again."""
        row = await store.oldest(self.client.pool, channel.id)
        if not row:
            return
        try:
            old = await channel.fetch_message(row["message_id"])
            await old.delete()
        except Exception:
            pass
        msg = await channel.send(row["content"])
        await asyncio.shield(self.keep(row, msg))

    async def keep(self, row, msg):
        """Saves the new message; deletes it if its sticky was taken away meanwhile."""
        kept = await store.move(
            self.client.pool, row["id"], msg.channel.id, msg.id, row["content"]
        )
        if not kept:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass


async def setup(bot):
    await bot.add_cog(StickyHandler(bot))
