import discord
import os
import firebase_admin
import threading
import psutil

from firebase_admin import credentials
from discord.ext import commands
from utils.persistent import views
from utils.controls import BotControlServer
from utils.uptime import app
from assets.secret import DISCORD_TOKEN, DATABASE_PATH, DATABASE_URL

cred = credentials.Certificate(DATABASE_PATH)
default_app = firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

class Fischl(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.presences = False
        super().__init__(
            command_prefix="-",
            intents=intents,
            application_id=732422232273584198,
            help_command=None,
            member_cache_flags=discord.MemberCacheFlags.none(),
            chunk_guilds_at_startup=False,
        )

    async def setup_hook(self):
        for directory in ["cogs", "commands", "shared"]:
            for path, _, files in os.walk(directory):
                for name in files:
                    if name.endswith(".py"):
                        extension = os.path.join(path, name).replace("/", ".")[:-3]
                        await self.load_extension(extension)
                        print(f"Loaded {extension} in {self.user}")
            
        await self.tree.sync()

        for view in views:
            self.add_view(view())

        control = BotControlServer(self, port=8086)
        self.loop.create_task(control.start())

    async def on_ready(self):
        threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8083, use_reloader=False), daemon=True).start()
        print(f"{self.user} has connected to Discord!")

        print(f"CPU Usage: {psutil.cpu_percent()}%")
        print(f"Memory Usage: {psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024} MB ({psutil.Process(os.getpid()).memory_percent()}%)")
 
bot = Fischl()
bot.run(DISCORD_TOKEN)
