"""DMs members when their web expeditions (fischl.app/profile) have returned."""

import time

import discord
from discord.ext import commands, tasks

from commands.Events.config import MORA_EMOTE

TABLE = """CREATE TABLE IF NOT EXISTS web_expeditions (
    id SERIAL PRIMARY KEY, uid BIGINT, gid BIGINT, slot INT, character TEXT, hours INT,
    started_at DOUBLE PRECISION, ends_at DOUBLE PRECISION, mora INT, summons INT, claimed BOOLEAN DEFAULT FALSE)"""
NOTIFIED = "ALTER TABLE web_expeditions ADD COLUMN IF NOT EXISTS notified BOOLEAN DEFAULT FALSE"
# Flags the due runs as it reads them, so a restart can never DM twice.
DUE = (
    "UPDATE web_expeditions SET notified = TRUE WHERE NOT claimed AND NOT notified AND ends_at <= $1 "
    "RETURNING uid, gid, character, mora, summons"
)


def by_member(rows):
    """Groups the runs by the member and server they belong to."""
    groups = {}
    for row in rows:
        groups.setdefault((row["uid"], row["gid"]), []).append(row)
    return groups


def returned(runs, guild, gid):
    """Gives the DM that says which characters came back and with what."""
    names = ", ".join(run["character"] for run in runs)
    mora = sum(run["mora"] for run in runs)
    summons = sum(run["summons"] for run in runs)
    return discord.Embed(
        title="🧭 Your expedition has returned!",
        description=(
            f"**{names}** came back from **{guild.name if guild else 'your realm'}** with "
            f"{MORA_EMOTE} **{mora:,}** mora and **{summons}** summon{'s' if summons != 1 else ''} waiting.\n"
            f"[Collect rewards & send them out again](https://fischl.app/profile/{gid})"
        ),
        color=0xFA0ADD,
    )


class ExpeditionReminders(commands.Cog):
    """Checks every minute for expeditions that have just ended."""

    def __init__(self, bot):
        self.bot = bot
        self.notify.start()

    def cog_unload(self):
        self.notify.cancel()

    @tasks.loop(minutes=1)
    async def notify(self):
        """DMs each member whose runs ended; rewards stay on the site if the DM fails."""
        try:
            rows = await self.bot.pool.fetch(DUE, time.time())
        except Exception as e:
            print(f"Expedition reminder error: {e}")
            return
        for (uid, gid), runs in by_member(rows).items():
            try:
                user = await self.bot.fetch_user(uid)
                await user.send(embed=returned(runs, self.bot.get_guild(gid), gid))
            except Exception:
                pass

    @notify.before_loop
    async def before_notify(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    try:
        async with bot.pool.acquire() as conn:
            await conn.execute(TABLE)
            await conn.execute(NOTIFIED)
    except Exception as e:
        print(f"Expedition reminder error: {e}")
    await bot.add_cog(ExpeditionReminders(bot))
