import discord
import asyncio
import time
import datetime

from discord.ext import commands, tasks
from firebase_admin import db

class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_task.start()
        self.status_heartbeat.start()

    def cog_unload(self):
        self.status_task.cancel()
        self.status_heartbeat.cancel()

    @tasks.loop()
    async def status_task(self):
        timeout = 30
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="Genshin Impact"
            ),
        )
        await asyncio.sleep(timeout)
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"Website: fischl.app",
            ),
        )
        await asyncio.sleep(timeout)
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.playing, name=f"Support: discord.gg/kaycd3fxHh"
            ),
        )

    @tasks.loop(minutes=1)
    async def status_heartbeat(self):
        try:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds") + "Z"
            latency_ms = int(self.bot.latency * 1000) 

            db.reference('Bot Status').update({
                'last_ping': now,
                'last_latency_ms': latency_ms
            })

            timestamp_ms = int(time.time() * 1000)

            db.reference('Bot Status/ping_history').push({
                'timestamp': timestamp_ms,
                'latency_ms': latency_ms
            })

            # Cleanup every hour
            if self.status_heartbeat.current_loop % 60 == 0:
                cutoff = timestamp_ms - 24 * 60 * 60 * 1000
                ref = db.reference('Bot Status/ping_history')
                old_entries = ref.order_by_child('timestamp').end_at(cutoff).get()
                if old_entries:
                    updates = {key: None for key in old_entries.keys()}
                    ref.update(updates) 

        except Exception as e:
            print(f"Failed to send heartbeat: {e}")

    @status_task.before_loop
    @status_heartbeat.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(StatusCog(bot))