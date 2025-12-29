import asyncio
import time

from discord.ext import commands
from firebase_admin import db

class Season:
    def __init__(self, id, name, start_ts, end_ts, track_data):
        self.id = id
        self.name = name
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.track_data = track_data

SEASONS = [
    Season(
        id=1,
        name="Liyue's Lanterns",
        start_ts=1751328000,  # July 1, 2025
        end_ts=1759276800,    # October 1, 2025
        track_data = [
            {'tier': 1,  'xp_req': 250, 'cumulative_xp': 250,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 250, 'cumulative_xp': 500,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 250, 'cumulative_xp': 750,    'free': '+3 Minigames Summon',                                            'elite': '+3 Minigames Summon'},
            {'tier': 4,  'xp_req': 250, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 250, 'cumulative_xp': 1250,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 500, 'cumulative_xp': 1750,    'free': 'Global Title | Liyue Harbor',                                    'elite': 'Animated Background | assets/Animated Mora Inventory Background/Aether\'s Watch.gif'},
            {'tier': 7,  'xp_req': 500, 'cumulative_xp': 2250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 500, 'cumulative_xp': 2750,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 500, 'cumulative_xp': 3250,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 500, 'cumulative_xp': 3750,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | assets/Profile Frame/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 4750,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 5750,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+3 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 6750,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 7750,   'free': 'Static Frame | assets/Profile Frame/Golden Ring.png',             'elite': 'Animated Badge Title | <a:tada:1227425729654820885> Cool Traveler'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 8750,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 11250,   'free': 'Mora Gift Tax -5%',                                              'elite': '+3 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 13750,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 16250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 18750,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 21250,   'free': 'Global Title | Genshin Adventurer',                               'elite': 'Animated Frame | assets/Profile Frame/Sakura Blossoms.gif'},
            {'tier': 21, 'xp_req': 5000, 'cumulative_xp': 26250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 5000, 'cumulative_xp': 31250,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 5000, 'cumulative_xp': 36250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 24, 'xp_req': 5000, 'cumulative_xp': 41250,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 5000, 'cumulative_xp': 46250,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 26, 'xp_req': 7250, 'cumulative_xp': 53500,   'free': 'Static Frame | assets/Profile Frame/Meander Lanterns.png',        'elite': 'Animated Background | assets/Animated Mora Inventory Background/Festive Night.gif'},
            {'tier': 27, 'xp_req': 7250, 'cumulative_xp': 60750,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 7250, 'cumulative_xp': 68000,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 7250, 'cumulative_xp': 75250,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 7250, 'cumulative_xp': 82500,   'free': 'Animated Background | assets/Animated Mora Inventory Background/Stone Gate.gif', 'elite': 'Animated Badge Title | <a:tada:1227425729654820885> Loyal Paimon'},
            {'tier': 31, 'xp_req': 7500, 'cumulative_xp': 90000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
    Season(
        id=2,
        name="Season of the Dragon",
        start_ts=1759276801,   # October 1, 2025
        end_ts=1767229200,     # January 1, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1000, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 1000, 'cumulative_xp': 2000,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 1000, 'cumulative_xp': 3000,    'free': '+3 Minigames Summon',                                            'elite': '+3 Minigames Summon'},
            {'tier': 4,  'xp_req': 1000, 'cumulative_xp': 4000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 1000, 'cumulative_xp': 5000,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 1000, 'cumulative_xp': 6000,    'free': 'Global Title | Stromterror Winds',                                'elite': '+3 Minigames Summon'},
            {'tier': 7,  'xp_req': 1000, 'cumulative_xp': 7000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 1000, 'cumulative_xp': 8000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 1000, 'cumulative_xp': 9000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 1000, 'cumulative_xp': 10000,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | assets/Profile Frame/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 11000,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 12000,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+3 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 13000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 14000,   'free': 'Static Frame | assets/Profile Frame/Dragon Balls.png',             'elite': 'Animated Badge Title | <a:dragon_gif:1422382705307291770> Don\'t mess with me!'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 15000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 17500,   'free': 'Mora Gift Tax -5%',                                              'elite': '+3 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 20000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 22500,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 25000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 27500,   'free': 'Global Title | The Master of Loong',                            'elite': 'Animated Frame | assets/Profile Frame/Dragon Mouth.gif'},
            {'tier': 21, 'xp_req': 2500, 'cumulative_xp': 30000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 2500, 'cumulative_xp': 32500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 2500, 'cumulative_xp': 35000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 24, 'xp_req': 2500, 'cumulative_xp': 37500,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 2500, 'cumulative_xp': 40000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+3 Minigames Summon'},
            {'tier': 26, 'xp_req': 2500, 'cumulative_xp': 42500,   'free': 'Static Frame | assets/Profile Frame/Green Dragon.png',        'elite': 'Animated Frame | assets/Profile Frame/Holodragon.gif'},
            {'tier': 27, 'xp_req': 2500, 'cumulative_xp': 45000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 2500, 'cumulative_xp': 47500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 2500, 'cumulative_xp': 50000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 2500, 'cumulative_xp': 52500,   'free': 'Animated Badge Title | <a:dragon1:1422382712043339836> Dragon Hunter',        'elite': 'Animated Badge Title | <a:DragonHa:1422382728518701159> You can\'t catch me!'},
            {'tier': 31, 'xp_req': 2500, 'cumulative_xp': 55000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    ),
    Season(
        id=3,
        name="Lantern Rite Festival",
        start_ts=1767229201,   # January 1, 2026
        end_ts=1775001600,     # April 1, 2026
        track_data = [
            {'tier': 1,  'xp_req': 1000, 'cumulative_xp': 1000,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 1000, 'cumulative_xp': 2000,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 3,  'xp_req': 1000, 'cumulative_xp': 3000,    'free': '+3 Minigames Summon',                                            'elite': '+10 Minigames Summon'},
            {'tier': 4,  'xp_req': 1000, 'cumulative_xp': 4000,    'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 5,  'xp_req': 1000, 'cumulative_xp': 5000,    'free': 'Unlocks Mora Gifting',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 6,  'xp_req': 1000, 'cumulative_xp': 6000,    'free': 'Global Title | Vigilant Yaksha',                                'elite': '+10 Minigames Summon'},
            {'tier': 7,  'xp_req': 1000, 'cumulative_xp': 7000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 8,  'xp_req': 1000, 'cumulative_xp': 8000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gift Tax -5%'},
            {'tier': 9,  'xp_req': 1000, 'cumulative_xp': 9000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 10, 'xp_req': 1000, 'cumulative_xp': 10000,   'free': 'Drop Pack',                                                      'elite': 'Animated Frame | assets/Profile Frame/Jade Stone.gif'},
            {'tier': 11, 'xp_req': 1000, 'cumulative_xp': 11000,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 12, 'xp_req': 1000, 'cumulative_xp': 12000,   'free': '+1 Chest Upgrade Limit',                                         'elite': '+10 Minigames Summon'},
            {'tier': 13, 'xp_req': 1000, 'cumulative_xp': 13000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 14, 'xp_req': 1000, 'cumulative_xp': 14000,   'free': 'Static Frame | assets/Profile Frame/Firecracker.png',             'elite': 'Animated Badge Title | <a:dragon_gif:1422382705307291770> Dragonic Defender'},
            {'tier': 15, 'xp_req': 1000, 'cumulative_xp': 15000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 16, 'xp_req': 2500, 'cumulative_xp': 17500,   'free': 'Mora Gift Tax -5%',                                              'elite': '+10 Minigames Summon'},
            {'tier': 17, 'xp_req': 2500, 'cumulative_xp': 20000,   'free': 'Drop Pack',                                                      'elite': 'Mora Gain Boost +5%'},
            {'tier': 18, 'xp_req': 2500, 'cumulative_xp': 22500,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 19, 'xp_req': 2500, 'cumulative_xp': 25000,   'free': '+1 Chest Upgrade Limit',                                         'elite': 'Mora Gain Boost +5%'},
            {'tier': 20, 'xp_req': 2500, 'cumulative_xp': 27500,   'free': 'Global Title | Golden Prosperity',                            'elite': 'Animated Frame | assets/Profile Frame/Dragon Mouth.gif'},
            {'tier': 21, 'xp_req': 2500, 'cumulative_xp': 30000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+1 Chest Upgrade Limit'},
            {'tier': 22, 'xp_req': 2500, 'cumulative_xp': 32500,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 23, 'xp_req': 2500, 'cumulative_xp': 35000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 24, 'xp_req': 2500, 'cumulative_xp': 37500,   'free': 'Mora Gift Tax -5%',                                              'elite': 'Mora Gain Boost +5%'},
            {'tier': 25, 'xp_req': 2500, 'cumulative_xp': 40000,   'free': 'Mora Gain Boost +5%',                                            'elite': '+10 Minigames Summon'},
            {'tier': 26, 'xp_req': 5000, 'cumulative_xp': 45000,   'free': 'Static Frame | assets/Profile Frame/Lunar Roof.png',        'elite': 'Animated Frame | assets/Profile Frame/Holodragon.gif'},
            {'tier': 27, 'xp_req': 5000, 'cumulative_xp': 50000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 28, 'xp_req': 5000, 'cumulative_xp': 55000,   'free': '+3 Minigames Summon',                                            'elite': 'Mora Gift Tax -5%'},
            {'tier': 29, 'xp_req': 5000, 'cumulative_xp': 60000,   'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
            {'tier': 30, 'xp_req': 5000, 'cumulative_xp': 65000,   'free': 'Animated Badge Title | <:guizhong:1455084957335683366> Glow of the Guizhong',        'elite': 'Animated Badge Title | <a:dragon1:1422382712043339836> Dragonic Master'},
            {'tier': 31, 'xp_req': 5000, 'cumulative_xp': 70000,  'free': 'Prestige +1',                                                     'elite': 'Prestige +1'},
        ]
    )
]

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
        progression_ref = db.reference("/Progression")
        stats_ref = db.reference("/User Events Stats")
        rewards_ref = db.reference("/Global Progression Rewards")
        
        for guild_id, guild_data in (progression_ref.get() or {}).items():
            for user_id, user_data in guild_data.items():
                progression_ref.child(guild_id).child(user_id).update({
                    "xp": 0,
                    "prestige": user_data.get("prestige", 0),  # Keep existing prestige
                    "bonus_tier": 0
                })
        
        for guild_id, guild_data in (stats_ref.get() or {}).items():
            for user_id, user_stats in guild_data.items():
                updates = {}
                if "mora_boost" in user_stats:
                    updates["mora_boost"] = 0
                if "chest_upgrades" in user_stats:
                    updates["chest_upgrades"] = 4
                if "gift_tax" in user_stats:
                    stats_ref.child(guild_id).child(user_id).child("gift_tax").delete()
                if updates:
                    stats_ref.child(guild_id).child(user_id).update(updates)
        
        for guild_id, guild_data in (rewards_ref.get() or {}).items():
            for user_id, user_data in guild_data.items():
                rewards_ref.child(guild_id).child(user_id).child("embed_color").delete()
                rewards_ref.child(guild_id).child(user_id).child("selected").update({
                    "embed_color_hex": None,
                    "elite_claimed": []
                })
                
        print("Season user data resets successfully!")

async def setup(bot):
    await bot.add_cog(SeasonCog(bot))