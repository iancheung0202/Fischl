import asyncio
import time

from discord.ext import commands

from commands.Events.config import SEASONS

def get_current_season():
    now = time.time()
    for season in SEASONS:
        if season.start_ts <= now < season.end_ts:
            return season
    return None
    
    
class SeasonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_season_check = time.time()
        self.bot.loop.create_task(self.season_monitor())
    
    async def season_monitor(self):
        await self.bot.wait_until_ready()

        last_active_season_id = None 

        while not self.bot.is_closed():
            current_time = time.time()

            current_season = None
            for season in SEASONS:
                if season.start_ts <= current_time < season.end_ts:
                    current_season = season
                    break

            if current_season:
                if last_active_season_id is not None and last_active_season_id != current_season.id:
                    print(f"Season changed from season {last_active_season_id} to season {current_season.id}")
                    await self.reset_season_data()

                last_active_season_id = current_season.id

            else:
                if last_active_season_id is not None:
                    print(f"Season {last_active_season_id} ended, no new season started yet.")
                    await self.reset_season_data()
                    last_active_season_id = None
                else:
                    print("No season active yet.")

            await asyncio.sleep(60)

    
    async def reset_season_data(self):
        pool = self.bot.pool
        if not pool:
            print("ERROR: Database pool not available for season reset!")
            return
        
        async with pool.acquire() as conn:
            await conn.execute("UPDATE minigame_elite SET claimed_tiers = '{}'")
            await conn.execute("""
                UPDATE minigame_cosmetics
                SET embed_color = FALSE,
                    selected_embed_color_hex = NULL
            """)
        
        async with pool.acquire() as conn:
            try:
                await conn.execute("ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS shop_discount INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS domain_discount INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE minigame_progression ADD COLUMN IF NOT EXISTS express_daily_chests BOOLEAN DEFAULT FALSE")
                # Reset XP and bonus_tier. Keep prestige
                await conn.execute(
                    "UPDATE minigame_progression SET xp = 0, bonus_tier = 0, updated_at = CURRENT_TIMESTAMP"
                )
                
                # Reset mora_boost, chest_upgrades, gift_tax, and discounts to default values. Keep summon
                await conn.execute(
                    "UPDATE minigame_progression SET mora_boost = 0, chest_upgrades = 4, gift_tax = NULL, shop_discount = 0, domain_discount = 0, express_daily_chests = FALSE, updated_at = CURRENT_TIMESTAMP"
                )
                
                print("Season user data reset successfully!")
            except Exception as e:
                print(f"ERROR resetting season data: {e}")

async def setup(bot):
    await bot.add_cog(SeasonCog(bot))