import psutil
import socket

from aiohttp import web
from aioprometheus import Counter, Gauge
from aioprometheus.service import Service
from discord.ext import commands, tasks

class MetricsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.prom_service = Service()
        self.setup_metrics()
        self.start_prometheus.start()
        self.update_system_stats.start()
        self.update_bot_stats.start()

    def setup_metrics(self):
        self.events_counter = Counter(
            "events_total",
            "Number of events.",
            const_labels={"host": socket.gethostname()},
        )
        self.commands_counter = Counter(
            "commands_total",
            "Number of commands invoked.",
            const_labels={"host": socket.gethostname()},
        )

        self.bot_guilds = Gauge("bot_guilds", "Number of guilds the bot is in.")
        self.bot_users = Gauge("bot_users", "Number of unique users visible to the bot.")
        self.bot_latency = Gauge("bot_latency_seconds", "Heartbeat latency in seconds.")

        self.cpu_usage_percent = Gauge("cpu_usage_percent", "CPU usage percentage.")
        self.memory_used_gb = Gauge("memory_used_gb", "Memory used in GB.")
        self.memory_total_gb = Gauge("memory_total_gb", "Total memory available in GB.")
        self.memory_percent = Gauge("memory_percent", "Memory usage percentage.")
        self.ram_usage_gb = Gauge("ram_usage_gb", "RAM usage in GB (RSS).")

    def cog_unload(self):
        self.start_prometheus.cancel()
        self.update_system_stats.cancel()
        self.update_bot_stats.cancel()

    @tasks.loop(seconds=10, count=1)
    async def start_prometheus(self):
        await self.prom_service.start(addr="0.0.0.0", port=9091)
        try:
            self.prom_service._runner._server._kwargs["access_log"] = None
        except Exception as e:
            print(f"Error occurred while disabling access log: {e}")

        print(f"Prometheus metrics available at: {self.prom_service.metrics_url}")

    @tasks.loop(seconds=10)
    async def update_system_stats(self):
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_usage_percent.set({}, cpu_percent)
            mem_usage = psutil.virtual_memory()
            memory_used_gb = mem_usage.used / (1024**3)
            memory_total_gb = mem_usage.total / (1024**3)
            memory_percent = mem_usage.percent
            self.memory_used_gb.set({}, memory_used_gb)
            self.memory_total_gb.set({}, memory_total_gb)
            self.memory_percent.set({}, memory_percent)
            ram_usage_gb = mem_usage.rss / (1024**3) if hasattr(mem_usage, 'rss') else memory_used_gb
            self.ram_usage_gb.set({}, ram_usage_gb)
        except Exception as e:
            print(f"System stats update failed: {e}")

    @tasks.loop(seconds=30)
    async def update_bot_stats(self):
        try:
            self.bot_guilds.set({}, len(self.bot.guilds))
            self.bot_users.set({}, len(self.bot.users))
            lat = float(self.bot.latency) if self.bot.latency is not None else 0.0
            self.bot_latency.set({}, lat)
        except Exception as e:
            print(f"Bot stats update failed: {e}")

    @start_prometheus.before_loop
    @update_system_stats.before_loop
    @update_bot_stats.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        self.commands_counter.inc({"command": command.name})

    @commands.Cog.listener()
    async def on_socket_event_type(self, event_type):
        self.events_counter.inc({"event": event_type})

async def setup(bot):
    await bot.add_cog(MetricsCog(bot))