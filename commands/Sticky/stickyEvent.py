import asyncio
import importlib
import os

from discord.ext import commands
from firebase_admin import db

commands_module = importlib.import_module('commands')
from commands.Sticky.enabledChannels import enabledChannels
last_modified = os.path.getmtime("./commands/Sticky/enabledChannels.py")

def check_and_reload():
    global last_modified, enabledChannels
    new_modified = os.path.getmtime("./commands/Sticky/enabledChannels.py")
    if new_modified > last_modified:
        with open("./commands/Sticky/enabledChannels.py", "r") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("enabledChannels ="):
                new_enabled_channels = eval(line.split("=")[1].strip())
        if new_enabled_channels != enabledChannels:
            enabledChannels = new_enabled_channels
            last_modified = new_modified
            print("Sticky Messages ./commands/Sticky/enabledChannels.py reloaded!")

class OnMessage(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self._debounce_tasks = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user:
            return

        check_and_reload()
        cid = message.channel.id
        if cid not in enabledChannels:
            return

        task = self._debounce_tasks.get(cid)
        if task and not task.done():
            task.cancel()

        self._debounce_tasks[cid] = asyncio.create_task(
            self._delayed_update(message.channel, delay=10)
        )

    async def _delayed_update(self, channel, delay):
        try:
            await asyncio.sleep(delay)
            await self._do_sticky_update(channel)
        except asyncio.CancelledError:
            return

    async def _do_sticky_update(self, channel):
        ref = db.reference("/Sticky Messages")
        stickies = ref.get() or {}
        for key, val in stickies.items():
            if val['Channel ID'] == channel.id:
                try:
                    old = await channel.fetch_message(val["Message ID"])
                    await old.delete()
                except Exception:
                    pass
                msg = await channel.send(val["Message Content"])
                db.reference('/Sticky Messages').child(key).delete()
                db.reference('/Sticky Messages').push().set({
                    "Channel ID": channel.id,
                    "Message ID": msg.id,
                    "Message Content": val["Message Content"]
                })
                break

async def setup(bot): 
    await bot.add_cog(OnMessage(bot))