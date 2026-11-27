"""The bot's rotating status, and the heartbeat the website reads from Firebase."""

import asyncio
import datetime
import time

import discord
from discord.ext import commands, tasks
from firebase_admin import db

TURN = 30
DAY = 24 * 60 * 60 * 1000
PLAYING, LISTENING = discord.ActivityType.playing, discord.ActivityType.listening


class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_task.start()
        self.status_heartbeat.start()

    def cog_unload(self):
        self.status_task.cancel()
        self.status_heartbeat.cancel()

    async def show(self, kind, name):
        """Sets what the bot is shown doing."""
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=kind, name=name),
        )

    @tasks.loop()
    async def status_task(self):
        await self.show(PLAYING, "Genshin Impact")
        await asyncio.sleep(TURN)
        await self.show(LISTENING, "Website: fischl.app")
        await asyncio.sleep(TURN)

    @tasks.loop(minutes=1)
    async def status_heartbeat(self):
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            latency = int(self.bot.latency * 1000)
            db.reference("Bot Status").update(
                {
                    "last_ping": now.isoformat(timespec="milliseconds") + "Z",
                    "last_latency_ms": latency,
                }
            )
            stamp = int(time.time() * 1000)
            pings = db.reference("Bot Status/ping_history")
            pings.push({"timestamp": stamp, "latency_ms": latency})
            if self.status_heartbeat.current_loop % 60 == 0:
                forget(stamp - DAY)
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")

    @status_task.before_loop
    @status_heartbeat.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()


def forget(cutoff):
    """Deletes the pings sent at or before the cutoff."""
    pings = db.reference("Bot Status/ping_history")
    old = pings.order_by_child("timestamp").end_at(cutoff).get()
    if old:
        pings.update({key: None for key in old.keys()})


async def setup(bot):
    await bot.add_cog(StatusCog(bot))
