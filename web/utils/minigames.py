import datetime
import time
import os
import psycopg2

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

from config.settings import BOT_TOKEN, API_BASE, MORA_EMOTE, POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
from utils.request import requests_session

def get_db_connection():
    """Get a synchronous PostgreSQL connection for web layer"""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB
    )

def get_total_mora(user_id):
    """Get total mora across all guilds for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(count), 0) FROM minigame_mora WHERE uid = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        total = result[0] if result else 0
        cursor.close()
        conn.close()
        return total
    except Exception as e:
        print(f"Error getting total mora: {e}")
        return 0

def get_guild_mora(user_id, guild_id):
    """Get total mora for a user in a specific guild"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(count), 0) FROM minigame_mora WHERE uid = %s AND gid = %s",
            (user_id, guild_id)
        )
        result = cursor.fetchone()
        total = result[0] if result else 0
        cursor.close()
        conn.close()
        return total
    except Exception as e:
        print(f"Error getting guild mora: {e}")
        return 0

def get_channel_settings_sync(guild_id, channel_id):
    """Synchronously read channel settings from PostgreSQL for the web layer"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT minigame_list, mora_multiplier, minigames_frequency, chests_enabled "
            "FROM minigame_settings WHERE channel_id = %s",
            (channel_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return {
                "minigame_list": row[0],
                "mora_multiplier": row[1],
                "minigames_frequency": row[2],
                "chests_enabled": row[3],
            }
        return None
    except Exception as e:
        print(f"Error getting channel settings: {e}")
        return None

_ENABLED_CHANNELS_TTL = 30      # seconds
_GUILD_CHANNELS_TTL = 300       # seconds
_enabled_channels_cache = {"ts": 0.0, "ids": set()}
_guild_channels_cache = {}      # guild_id -> (timestamp, set of channel/thread ids)

def get_enabled_channel_ids():
    """Channel IDs where the bot's event system is active, using the bot's own definition:
    chat minigames (minigames_enabled) and/or chests (chests_enabled) and/or sigils (chat_enabled)."""
    now = time.time()
    if now - _enabled_channels_cache["ts"] < _ENABLED_CHANNELS_TTL:
        return _enabled_channels_cache["ids"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT channel_id FROM minigame_settings "
            "WHERE minigames_enabled = TRUE OR chests_enabled = TRUE OR chat_enabled = TRUE"
        )
        ids = {int(r[0]) for r in cursor.fetchall()}
        cursor.close()
    finally:
        conn.close()
    _enabled_channels_cache.update(ts=now, ids=ids)
    return ids

def get_guild_channel_ids(guild_id):
    """All channel (and active thread) IDs of a guild, fetched with the bot token and cached.
    minigame_settings is keyed by channel_id only, so this is how channels are tied to a guild."""
    guild_id = str(guild_id)
    now = time.time()
    cached = _guild_channels_cache.get(guild_id)
    if cached and now - cached[0] < _GUILD_CHANNELS_TTL:
        return cached[1]
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    resp = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Could not fetch channels for guild {guild_id}: HTTP {resp.status_code}")
    ids = {int(c["id"]) for c in resp.json()}
    # Settings can also be set on threads; include active ones (best effort)
    try:
        t = requests_session.get(f"{API_BASE}/guilds/{guild_id}/threads/active", headers=headers)
        if t.status_code == 200:
            ids |= {int(c["id"]) for c in t.json().get("threads", [])}
    except Exception:
        pass
    _guild_channels_cache[guild_id] = (now, ids)
    return ids

def check_events_enabled(guild_id, stickies=None):
    """True if at least one channel of this guild has the event system enabled
    (chat minigames and/or chests and/or sigils), matching the bot's definition.
    `stickies` is unused and kept only for backwards compatibility."""
    try:
        enabled = get_enabled_channel_ids()
        if not enabled:
            return False
        return not enabled.isdisjoint(get_guild_channel_ids(guild_id))
    except Exception as e:
        print(f"Error checking events enabled: {e}")
        return False


def _load_events_config():
    """Load commands/Events/config.py (the bot's source of truth for seasons and tracks) by file path,
    so the web layer doesn't need the repo root on sys.path (its own `utils` package would clash)."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "commands", "Events", "config.py")
    spec = importlib.util.spec_from_file_location("fischl_events_config", os.path.normpath(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

SEASONS = _load_events_config().SEASONS  # Season objects: id, name, start_ts, end_ts, track_data

def _active_season():
    """Currently active Season object; falls back to the latest defined season (same as before)."""
    now = time.time()
    for season in SEASONS:
        if season.start_ts <= now < season.end_ts:
            return season
    return SEASONS[-1]

def get_current_season():
    """Get current season info from the bot's season config"""
    season = _active_season()
    return {"id": season.id, "name": season.name, "end_ts": season.end_ts}

def get_current_track():
    """Get current track data from the bot's season config"""
    return list(_active_season().track_data)

def load_elite_subscriptions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, guild_id, server_name, expires_at FROM minigame_elite")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        subs = {}
        for row in rows:
            key = f"{row[0]}-{row[1]}"
            subs[key] = {
                "user_id": row[0],
                "server_id": row[1],
                "server_name": row[2] or "",
                "expires_at": row[3]
            }
        return subs
    except Exception:
        return {}

def save_elite_subscriptions(subscriptions):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for key, sub in subscriptions.items():
            cursor.execute(
                """INSERT INTO minigame_elite (user_id, guild_id, server_name, expires_at)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id, guild_id)
                   DO UPDATE SET server_name = EXCLUDED.server_name, expires_at = EXCLUDED.expires_at""",
                (sub["user_id"], sub["server_id"], sub.get("server_name", ""), sub["expires_at"])
            )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

def activate_elite_subscription(user_id, guild_id, order_id=None):
    """Activate elite subscription for a user in a guild"""
    try:
        print(f"Starting elite subscription activation for user {user_id} in guild {guild_id}")
        if order_id:
            print(f"Order ID: {order_id}")

        current_season = get_current_season()
        print(f"Current season: {current_season}")
        if not current_season:
            return False, "No active season found"

        expires_at = current_season.get("end_ts", time.time() + (3 * 30 * 24 * 60 * 60))
        print(f"Subscription will expire at: {expires_at}")

        guild_response = requests_session.get(
            f"{API_BASE}/guilds/{guild_id}",
            headers={"Authorization": f"Bot {BOT_TOKEN}"}
        )
        guild_name = guild_response.json().get("name", f"Server {guild_id}") if guild_response.status_code == 200 else f"Server {guild_id}"
        print(f"Guild name: {guild_name}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO minigame_elite (user_id, guild_id, server_name, expires_at, order_id, pending_processed)
               VALUES (%s, %s, %s, %s, %s, FALSE)
               ON CONFLICT (user_id, guild_id)
               DO UPDATE SET server_name = EXCLUDED.server_name, expires_at = EXCLUDED.expires_at,
                             order_id = EXCLUDED.order_id, pending_processed = FALSE""",
            (int(user_id), int(guild_id), guild_name, expires_at, order_id or "")
        )
        conn.commit()
        cursor.close()
        conn.close()
        print("Subscription saved to PostgreSQL successfully")

        try:
            print("Sending Discord notification...")
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

        except Exception as e:
            print(f"Error sending Discord notification: {e}")

        print("Elite subscription activation completed successfully")
        return True, "Elite subscription activated successfully"

    except Exception as e:
        print(f"Error activating elite subscription: {e}")
        return False, f"Error activating subscription: {str(e)}"

def is_elite_active(user_id, guild_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT expires_at FROM minigame_elite WHERE user_id = %s AND guild_id = %s",
            (int(user_id), int(guild_id))
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return time.time() < row[0]
        return False
    except Exception:
        return False