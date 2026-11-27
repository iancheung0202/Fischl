"""Finds the season running now and resets season progress when it changes."""

import asyncio
import time

from discord.ext import commands

from commands.Events.config import SEASONS

COLUMNS = (
    "ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS shop_discount INTEGER DEFAULT 0",
    "ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS domain_discount INTEGER DEFAULT 0",
    "ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS express_daily_chests BOOLEAN DEFAULT FALSE",
)
# Prestige is kept.
RESET_XP = "UPDATE minigame_progression SET xp = 0, bonus_tier = 0, updated_at = CURRENT_TIMESTAMP"
# Summons are kept.
RESET_PERKS = "UPDATE minigame_progression SET mora_boost = 0, chest_upgrades = 4, gift_tax = NULL, shop_discount = 0, domain_discount = 0, express_daily_chests = FALSE, updated_at = CURRENT_TIMESTAMP"


def get_current_season():
    """Gives the season running now, or None between seasons."""
    now = time.time()
    for season in SEASONS:
        if season.start_ts <= now < season.end_ts:
            return season
    return None


class SeasonCog(commands.Cog):
    """Watches for the season changing."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.season_monitor())

    async def season_monitor(self):
        """Checks the season every minute and resets progress when it ends or changes."""
        await self.bot.wait_until_ready()
        last = None
        while not self.bot.is_closed():
            season = get_current_season()
            if season:
                if last is not None and last != season.id:
                    print(f"Season changed from season {last} to season {season.id}")
                    await self.reset_season_data()
                last = season.id
            elif last is not None:
                print(f"Season {last} ended, no new season started yet.")
                await self.reset_season_data()
                last = None
            else:
                print("No season active yet.")
            await asyncio.sleep(60)

    async def reset_season_data(self):
        """Clears every member's claimed tiers, embed colour, XP and season perks."""
        pool = self.bot.pool
        if not pool:
            print("ERROR: Database pool not available for season reset!")
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE minigame_elite SET claimed_tiers = '{}'")
            await conn.execute(
                """
                UPDATE minigame_cosmetics
                SET embed_color = FALSE,
                    selected_embed_color_hex = NULL
            """
            )
        async with pool.acquire() as conn:
            try:
                for statement in (*COLUMNS, RESET_XP, RESET_PERKS):
                    await conn.execute(statement)
                print("Season user data reset successfully!")
            except Exception as e:
                print(f"ERROR resetting season data: {e}")


async def setup(bot):
    await bot.add_cog(SeasonCog(bot))
