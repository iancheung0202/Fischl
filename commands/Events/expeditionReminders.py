import time
import discord

from discord.ext import commands, tasks

from commands.Events.config import MORA_EMOTE


class ExpeditionReminders(commands.Cog):
    """DMs users when their web expeditions (fischl.app/profile) have returned."""

    def __init__(self, bot):
        self.bot = bot
        self.notify.start()

    def cog_unload(self):
        self.notify.cancel()

    @tasks.loop(minutes=1)
    async def notify(self):
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("""CREATE TABLE IF NOT EXISTS web_expeditions (
                    id SERIAL PRIMARY KEY, uid BIGINT, gid BIGINT, slot INT, character TEXT, hours INT,
                    started_at DOUBLE PRECISION, ends_at DOUBLE PRECISION, mora INT, summons INT, claimed BOOLEAN DEFAULT FALSE)""")
                await conn.execute("ALTER TABLE web_expeditions ADD COLUMN IF NOT EXISTS notified BOOLEAN DEFAULT FALSE")
                # Atomically flag due runs so a restart can never double-DM
                rows = await conn.fetch(
                    "UPDATE web_expeditions SET notified = TRUE WHERE NOT claimed AND NOT notified AND ends_at <= $1 "
                    "RETURNING uid, gid, character, mora, summons", time.time())
        except Exception as e:
            print(f"Expedition reminder error: {e}")
            return

        groups = {}
        for r in rows:
            groups.setdefault((r["uid"], r["gid"]), []).append(r)

        for (uid, gid), runs in groups.items():
            try:
                user = await self.bot.fetch_user(uid)
                guild = self.bot.get_guild(gid)
                names = ", ".join(r["character"] for r in runs)
                mora, summons = sum(r["mora"] for r in runs), sum(r["summons"] for r in runs)
                embed = discord.Embed(
                    title="🧭 Your expedition has returned!",
                    description=(f"**{names}** came back from **{guild.name if guild else 'your realm'}** with "
                                 f"{MORA_EMOTE} **{mora:,}** mora and **{summons}** summon{'s' if summons != 1 else ''} waiting.\n"
                                 f"[Collect rewards & send them out again](https://fischl.app/profile/{gid})"),
                    color=0xFA0ADD)
                await user.send(embed=embed)
            except Exception:
                pass  # DMs closed or user gone; rewards stay claimable on the site

    @notify.before_loop
    async def before_notify(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ExpeditionReminders(bot))
