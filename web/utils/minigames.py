import datetime
import time
import os

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

from firebase_admin import db
from config.settings import BOT_TOKEN, API_BASE, MORA_EMOTE
from utils.request import requests_session

def get_total_mora(user_id):
    """Get total mora across all guilds for a user"""
    user_ref = db.reference(f"/Mora/{user_id}")
    user_data = user_ref.get() or {}
    
    total = 0
    for guild_data in user_data.values():
        if isinstance(guild_data, dict):
            for channel_data in guild_data.values():
                if isinstance(channel_data, dict):
                    for mora in channel_data.values():
                        if isinstance(mora, int):
                            total += mora
    return total

def get_guild_mora(user_id, guild_id):
    """Get total mora for a user in a specific guild"""
    ref = db.reference(f"/Mora/{user_id}/{guild_id}")
    guild_data = ref.get() or {}
    
    total = 0
    for channel_data in guild_data.values():
        if isinstance(channel_data, dict):
            for mora in channel_data.values():
                if isinstance(mora, int):
                    total += mora
    return total

def check_events_enabled(guild_id):
    """Check if events are enabled in any channel of a guild"""
    ref = db.reference("/Global Events System")
    stickies = ref.get() or {}
    
    # Get all channels in the guild first
    try:
        channels = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", 
                                      headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
        
        # Handle API errors
        if isinstance(channels, dict) and 'message' in channels:
            return False
            
        guild_channel_ids = {int(channel['id']) for channel in channels if channel.get('type') == 0}  # Text channels only
    except Exception as e:
        print(f"Error fetching channels for guild {guild_id}: {e}")
        return False
    
    # Check if any channel in this guild has events enabled
    for val in stickies.values():
        if isinstance(val, dict):
            channel_id = val.get("Channel ID")
            if channel_id and int(channel_id) in guild_channel_ids:
                return True
    return False

def get_current_season():
    """Get current season info from hardcoded season data"""
    try:
        current_time = time.time()
        
        # Hardcoded season data matching Discord bot
        SEASONS = [
            {
                "id": 1,
                "name": "Liyue's Lanterns",
                "start_ts": 1751328000,  # July 1, 2025
                "end_ts": 1759276800,    # October 1, 2025
            },
            {
                "id": 2,
                "name": "Season of the Dragon",
                "start_ts": 1759276801,   # October 1, 2025
                "end_ts": 1767229200,     # January 1, 2026
            }
        ]
        
        # Find current active season
        for season in SEASONS:
            if season["start_ts"] <= current_time < season["end_ts"]:
                return {
                    "id": season["id"],
                    "name": season["name"],
                    "end_ts": season["end_ts"]
                }
        
        # Default to season 2 if no active season (since current date is Oct 2025)
        return {
            "id": 2,
            "name": "Season of the Dragon",
            "end_ts": 1767229200
        }
            
    except Exception as e:
        print(f"Error fetching season data: {e}")
        return {
            "id": 2,
            "name": "Season of the Dragon",
            "end_ts": 1767229200
        }

def get_current_track():
    """Get current track data from current season"""
    try:
        current_season = get_current_season()
        if not current_season:
            return []
            
        # Try to get track data from Firebase based on season
        season_id = current_season.get("id", 1)
        
        # Hardcoded track data based on actual seasons from Discord bot
        SEASON_TRACKS = {
            1: [
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
            ],
            2: [
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
        }
        
        return SEASON_TRACKS.get(season_id, SEASON_TRACKS[1])
        
    except Exception as e:
        print(f"Error fetching track data: {e}")
        # Fallback to season 1 data
        return [
            {'tier': 1,  'xp_req': 250, 'cumulative_xp': 250,    'free': 'Drop Pack',                                                      'elite': 'Custom Embed Color'},
            {'tier': 2,  'xp_req': 250, 'cumulative_xp': 500,    'free': 'Mora Gain Boost +5%',                                            'elite': 'Mora Gain Boost +5%'},
        ]

def save_elite_subscriptions(subscriptions):
    try:
        elite_track_ref = db.reference("/Elite Track")
        elite_track_ref.set(subscriptions)
    except Exception:
        pass

def activate_elite_subscription(user_id, guild_id, order_id=None):
    """Activate elite subscription for a user in a guild"""
    try:
        print(f"Starting elite subscription activation for user {user_id} in guild {guild_id}")
        if order_id:
            print(f"Order ID: {order_id}")
        
        # Calculate expiration date (current season end)
        current_season = get_current_season()
        print(f"Current season: {current_season}")
        if not current_season:
            return False, "No active season found"
        
        expires_at = current_season.get("end_ts", time.time() + (3 * 30 * 24 * 60 * 60))  # Default 3 months if no season
        print(f"Subscription will expire at: {expires_at}")
        
        # Load existing subscriptions
        print("Loading existing subscriptions...")
        subscriptions = load_elite_subscriptions()
        print(f"Loaded {len(subscriptions)} existing subscriptions")

        # Get guild name for notification
        guild_response = requests_session.get(
            f"{API_BASE}/guilds/{guild_id}",
            headers={"Authorization": f"Bot {BOT_TOKEN}"}
        )
        guild_name = guild_response.json().get("name", f"Server {guild_id}") if guild_response.status_code == 200 else f"Server {guild_id}"
        print(f"Guild name: {guild_name}")
        
        # Add new subscription
        key = f"{user_id}-{guild_id}"
        subscriptions[key] = {
            "user_id": int(user_id),
            "server_id": int(guild_id),
            "server_name": guild_name,
            "expires_at": expires_at
        }
        print(f"Added subscription with key: {key}")
        
        # Save subscriptions
        print("Saving subscriptions to Firebase...")
        save_elite_subscriptions(subscriptions)
        print("Subscriptions saved successfully")
        
        # Send Discord notification
        try:
            print("Sending Discord notification...")
            
            # Send DM to user
            user_response = requests_session.post(
                f"{API_BASE}/users/@me/channels",
                headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
                json={"recipient_id": str(user_id)}
            )
            
            if user_response.status_code == 200:
                dm_channel_id = user_response.json()["id"]
                print(f"Created DM channel: {dm_channel_id}")
                
                embed = {
                    "description": (
                        f"## <a:moneydance:1227425759077859359> Elite Track Activated!\n"
                        f"🎉 You now have sweet perks in **{guild_name}**! Elite rewards should have been automatically granted! Enjoy friend!\n"
                        f"-# ⏰ Expires <t:{int(expires_at)}:R> by the end of the current season."
                    ),
                    "color": 0xfa0add
                }
                
                # Add footer with order ID if provided
                if order_id:
                    embed["footer"] = {"text": f"Order ID: {order_id}"}
                
                dm_response = requests_session.post(
                    f"{API_BASE}/channels/{dm_channel_id}/messages",
                    headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
                    json={"embed": embed}
                )
                print(f"DM sent successfully")
            else:
                print(f"Failed to create DM channel: {user_response.status_code}")
            
            # Create a notification for the bot to process retroactive rewards
            # The bot can monitor this path and process pending activations
            try:
                print("Creating pending activation notification...")
                pending_ref = db.reference(f"/Elite Track Pending/{guild_id}")
                current_pending = pending_ref.get() or []
                current_pending.append({
                    "user_id": user_id,
                    "timestamp": time.time(),
                    "activated_via": "website"
                })
                pending_ref.set(current_pending)
                print("Pending activation notification created successfully")
            except Exception as e:
                print(f"Could not create pending activation: {e}")
                        
        except Exception as e:
            print(f"Error sending Discord notification: {e}")
        
        print("Elite subscription activation completed successfully")
        return True, "Elite subscription activated successfully"
        
    except Exception as e:
        print(f"Error activating elite subscription: {e}")
        traceback.print_exc()
        return False, f"Error activating subscription: {str(e)}"

def load_elite_subscriptions():
    try:
        elite_track_ref = db.reference("/Elite Track")
        return elite_track_ref.get() or {}
    except Exception:
        return {}
    
def is_elite_active(user_id, guild_id):
    subscriptions = load_elite_subscriptions()
    key = f"{user_id}-{guild_id}"
    if key in subscriptions:
        return time.time() < subscriptions[key]["expires_at"]
    return False

def generate_mora_graph(user_id, guild_id, display_name):
    """Generate mora earnings graph for a user in a guild"""
    try:
        ref = db.reference(f"/Mora/{user_id}/{guild_id}")
        guild_data = ref.get() or {}

        # Extract data and count entries
        timestamps = []
        mora_values = []
        entry_count = 0

        for channel_data in guild_data.values():
            if isinstance(channel_data, dict):
                for ts, mora in channel_data.items():
                    try:
                        timestamp = int(ts)
                        if isinstance(mora, int) and mora >= 0:
                            entry_count += 1
                        timestamps.append(timestamp)
                        mora_values.append(mora)
                    except (ValueError, TypeError):
                        # Skip invalid timestamps
                        continue

        if not timestamps:
            return None

        # Calculate stats
        first_played = min(timestamps)
        
        # Calculate daily earnings
        daily_earnings = {}
        for ts, mora in zip(timestamps, mora_values):
            date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date()
            daily_earnings[date] = daily_earnings.get(date, 0) + mora

        # Find largest daily earning
        largest_daily = max(daily_earnings.values(), default=0)
        largest_daily_date = None
        for date, amount in daily_earnings.items():
            if amount == largest_daily:
                largest_daily_date = date
                break

        # Calculate average daily mora
        total_days = (datetime.datetime.now(datetime.timezone.utc).date() - 
                     datetime.datetime.fromtimestamp(first_played, datetime.timezone.utc).date()).days + 1
        total_mora = sum(mora_values)
        average_daily = total_mora / total_days if total_days > 0 else 0

        # Days the user actively earned Mora
        days_active = len(daily_earnings)
        
        # Get chest counts
        ref_counts = db.reference(f"/Mora Chest Counts/{guild_id}/{user_id}")
        chest_counts = ref_counts.get() or {"Common": 0, "Exquisite": 0, "Precious": 0, "Luxurious": 0}
        total_chests = sum(chest_counts.values())

        # Get streak data
        ref_streak = db.reference(f"/Mora Chest Streaks/{guild_id}/{user_id}")
        streak_data = ref_streak.get() or {}
        last_claimed = datetime.datetime.fromisoformat(streak_data["last_claimed"]).date() if "last_claimed" in streak_data else None
        current_streak = streak_data.get("streak", 0) if last_claimed and (datetime.datetime.now(datetime.timezone.utc).date() - last_claimed).days <= 1 else 0
        max_streak = streak_data.get("max_streak", current_streak)

        chest_info = (
            f"<img src='https://cdn.discordapp.com/emojis/1371641883121680465.png?size=20' style='line-height: 1em; display: inline; vertical-align: baseline;'> <code>{chest_counts.get('Common', 0)}</code> &nbsp; &nbsp; "
            f"<img src='https://cdn.discordapp.com/emojis/1371641856344985620.png?size=20' style='line-height: 1em; display: inline; vertical-align: baseline;'> <code>{chest_counts.get('Exquisite', 0)}</code> &nbsp; &nbsp; "
            f"<img src='https://cdn.discordapp.com/emojis/1371641871452995689.png?size=20' style='line-height: 1em; display: inline; vertical-align: baseline;'> <code>{chest_counts.get('Precious', 0)}</code> &nbsp; &nbsp; "
            f"<img src='https://cdn.discordapp.com/emojis/1371641841338023976.png?size=20' style='line-height: 1em; display: inline; vertical-align: baseline;'> <code>{chest_counts.get('Luxurious', 0)}</code> <br>"
            f"<b>Total:</b> <code>{total_chests}</code> &nbsp; &nbsp; "
            f"<img src='https://cdn.discordapp.com/emojis/1371651844652273694.png?size=20' style='line-height: 1em; display: inline; vertical-align: baseline;'> <code>{current_streak}</code> day{'s' if current_streak > 1 else ''} &nbsp; &nbsp; "
            f"<img src='https://cdn.discordapp.com/emojis/1371655286049214672.png?size=20' style='line-height: 1em; display: inline; vertical-align: baseline;'> <code>{max_streak}</code> day{'s' if max_streak > 1 else ''}"
        )

        # Format stats
        stats = {
            "📦 Daily Mora Chests": chest_info,
            "📅 First Played": f"{datetime.datetime.fromtimestamp(first_played, datetime.timezone.utc).date()}",
            "💰 Largest Day Earning": f"{largest_daily_date} (<code>{largest_daily:,} Mora</code>)",
            "📈 Average Daily Mora": f"{MORA_EMOTE} <code>{average_daily:,.0f}</code>",
            "✌️ Minigame Wins": f"<code>{entry_count - total_chests}</code> total wins",
            "😎 Active Days": f"<code>{days_active}</code> different day(s)",
        }

        # Create DataFrame and graph
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps, unit='s'),
            'mora': mora_values
        }).sort_values('timestamp')
        
        # Set plot style
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor('none')
        fig.patch.set_alpha(0)
        ax.patch.set_facecolor('none')
        ax.patch.set_alpha(0)
        
        # Calculate cumulative mora
        df['cumulative'] = df['mora'].cumsum()
        df['smooth'] = df['cumulative'].rolling(7, min_periods=1).mean()
        
        # Plot
        ax.plot(df['timestamp'], df['smooth'], 
               color="#0087DB", linewidth=3, solid_capstyle='round')
        
        # Format y-axis
        def format_mora(value, _):
            if value >= 1_000_000:
                return f'{value/1_000_000:.1f}M'
            if value >= 1_000:
                return f'{value/1_000:.0f}K'
            return f'{value:.0f}'
        
        ax.yaxis.set_major_formatter(plt.FuncFormatter(format_mora))
        
        # Styling
        ax.set_title(f"Mora Earnings History", fontsize=20, pad=20, fontweight='bold', color="#000000")
        ax.set_ylabel("Total Mora", fontsize=14, labelpad=16, color='black')
        ax.xaxis.set_major_formatter(DateFormatter('%b %d'))
        ax.tick_params(axis='both', which='major', labelsize=15, colors='black')
        
        # Grid
        ax.grid(True, alpha=0.3, linestyle='--', color='grey')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('grey')
        ax.spines['left'].set_color('grey')

        plt.tight_layout()
        
        # Save graph
        os.makedirs("./assets/graph", exist_ok=True)
        path = f"./assets/graph/{user_id}_{guild_id}.png"
        plt.savefig(path, bbox_inches='tight', dpi=120, transparent=True)
        plt.close()
        
        return (path, stats)
    
    except Exception as e:
        print(f"Error generating mora graph: {e}")
        return None