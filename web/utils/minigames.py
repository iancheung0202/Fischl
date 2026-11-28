"""What the website reads and writes of the bot's minigame data."""

import importlib.util
import os
import time
from contextlib import closing

import psycopg2
from config.settings import (
    API_BASE,
    BOT_TOKEN,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_USER,
)

from utils.request import requests_session

REPO = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
BOT = {"Authorization": f"Bot {BOT_TOKEN}"}
ENABLED_SECONDS = 30
CHANNELS_SECONDS = 300
ENABLED = "SELECT channel_id FROM minigame_settings WHERE minigames_enabled = TRUE OR chests_enabled = TRUE OR chat_enabled = TRUE"
ELITE_UNTIL = (
    "SELECT expires_at FROM minigame_elite WHERE user_id = %s AND guild_id = %s"
)
# A payment stays usable by its buyer until the season it paid for ends, so a repeated request is harmless.
ORDER_SPENT = """SELECT 1 FROM minigame_elite_orders
                  WHERE order_id = %s AND NOT (user_id = %s AND guild_id = %s AND expires_at > %s)"""
# Records a payment; gives a row unless the payment is already spent, so two requests at once cannot share one.
KEEP_ORDER = """INSERT INTO minigame_elite_orders AS kept (order_id, user_id, guild_id, expires_at)
                 VALUES (%s, %s, %s, %s)
                 ON CONFLICT (order_id) DO UPDATE SET order_id = kept.order_id
                 WHERE kept.user_id = EXCLUDED.user_id AND kept.guild_id = EXCLUDED.guild_id
                   AND kept.expires_at > %s
                 RETURNING 1"""
ACTIVATE = """INSERT INTO minigame_elite (user_id, guild_id, server_name, expires_at, order_id, pending_processed)
               VALUES (%s, %s, %s, %s, %s, FALSE)
               ON CONFLICT (user_id, guild_id)
               DO UPDATE SET server_name = EXCLUDED.server_name, expires_at = EXCLUDED.expires_at,
                             order_id = EXCLUDED.order_id, pending_processed = FALSE"""

enabled_channels = {"at": 0.0, "ids": set()}
guild_channels = {}


def get_db_connection():
    """Opens a connection to the bot's Postgres database."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
    )


def get_enabled_channel_ids():
    """Gives the channels with minigames, chests or sigils on, read at most every 30 s."""
    now = time.time()
    if now - enabled_channels["at"] >= ENABLED_SECONDS:
        with closing(get_db_connection()) as conn, conn.cursor() as cursor:
            cursor.execute(ENABLED)
            ids = {int(row[0]) for row in cursor.fetchall()}
        enabled_channels.update(at=now, ids=ids)
    return enabled_channels["ids"]


def get_guild_channel_ids(guild_id):
    """Gives a server's channel and active thread ids, asked from Discord at most every 5 min."""
    guild_id = str(guild_id)
    now = time.time()
    kept = guild_channels.get(guild_id)
    if kept and now - kept[0] < CHANNELS_SECONDS:
        return kept[1]
    answer = requests_session.get(f"{API_BASE}/guilds/{guild_id}/channels", headers=BOT)
    if answer.status_code != 200:
        raise RuntimeError(
            f"Could not fetch channels for guild {guild_id}: HTTP {answer.status_code}"
        )
    ids = {int(channel["id"]) for channel in answer.json()}
    try:
        threads = requests_session.get(
            f"{API_BASE}/guilds/{guild_id}/threads/active", headers=BOT
        )
        if threads.status_code == 200:
            ids |= {int(thread["id"]) for thread in threads.json().get("threads", [])}
    except Exception:
        pass
    guild_channels[guild_id] = (now, ids)
    return ids


def check_events_enabled(guild_id):
    """Says whether any channel of a server has minigames, chests or sigils on."""
    try:
        enabled = get_enabled_channel_ids()
        return bool(enabled) and not enabled.isdisjoint(get_guild_channel_ids(guild_id))
    except Exception as error:
        print(f"Error checking events enabled: {error}")
        return False


def events_config():
    """Loads the bot's commands/Events/config.py by path, since the website has its own `utils`."""
    path = os.path.join(REPO, "commands", "Events", "config.py")
    spec = importlib.util.spec_from_file_location("fischl_events_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEASONS = events_config().SEASONS


def active_season():
    """Gives the season running now, or the last one defined."""
    now = time.time()
    return next((s for s in SEASONS if s.start_ts <= now < s.end_ts), SEASONS[-1])


def get_current_season():
    """Gives the id, name and end of the season running now."""
    season = active_season()
    return {"id": season.id, "name": season.name, "end_ts": season.end_ts}


def get_current_track():
    """Gives the tiers of the season running now."""
    return list(active_season().track_data)


def guild_name(guild_id):
    """Gives a server's name, or a stand-in when Discord does not tell."""
    answer = requests_session.get(f"{API_BASE}/guilds/{guild_id}", headers=BOT)
    fallback = f"Server {guild_id}"
    return (
        answer.json().get("name", fallback) if answer.status_code == 200 else fallback
    )


def announce_elite(user_id, server_name, expires_at, order_id):
    """DMs the buyer that their Elite Track is on."""
    channel = requests_session.post(
        f"{API_BASE}/users/@me/channels",
        headers=BOT,
        json={"recipient_id": str(user_id)},
    )
    if channel.status_code != 200:
        print(f"Failed to create DM channel: {channel.status_code}")
        return
    embed = {
        "description": (
            f"## <a:moneydance:1227425759077859359> Elite Track Activated!\n"
            f"🎉 You now have sweet perks in **{server_name}**! Elite rewards should have been automatically granted! Enjoy friend!\n"
            f"-# ⏰ Expires <t:{int(expires_at)}:R> by the end of the current season."
        ),
        "color": 0xFA0ADD,
    }
    if order_id:
        embed["footer"] = {"text": f"Order ID: {order_id}"}
    requests_session.post(
        f"{API_BASE}/channels/{channel.json()['id']}/messages",
        headers=BOT,
        json={"embed": embed},
    )


def activate_elite_subscription(user_id, guild_id, order_id=None):
    """Turns the Elite Track on until the season ends; gives (worked, message)."""
    try:
        print(
            f"Activating elite for user {user_id} in guild {guild_id}, order {order_id}"
        )
        expires_at = get_current_season()["end_ts"]
        server_name = guild_name(guild_id)
        with closing(get_db_connection()) as conn, conn.cursor() as cursor:
            if order_id:
                cursor.execute(
                    KEEP_ORDER,
                    (order_id, int(user_id), int(guild_id), expires_at, time.time()),
                )
                if cursor.fetchone() is None:
                    return False, "This order has already been used."
            cursor.execute(
                ACTIVATE,
                (int(user_id), int(guild_id), server_name, expires_at, order_id or ""),
            )
            conn.commit()
        try:
            announce_elite(user_id, server_name, expires_at, order_id)
        except Exception as error:
            print(f"Error sending Discord notification: {error}")
        return True, "Elite subscription activated successfully"
    except Exception as error:
        print(f"Error activating elite subscription: {error}")
        return False, f"Error activating subscription: {str(error)}"


def order_spent(order_id, user_id, guild_id):
    """Says whether a payment already turned the Elite Track on for someone else or in a season that is over."""
    with closing(get_db_connection()) as conn, conn.cursor() as cursor:
        cursor.execute(
            ORDER_SPENT, (order_id, int(user_id), int(guild_id), time.time())
        )
        return cursor.fetchone() is not None


def is_elite_active(user_id, guild_id):
    """Says whether a member's Elite Track in a server has not run out."""
    try:
        with closing(get_db_connection()) as conn, conn.cursor() as cursor:
            cursor.execute(ELITE_UNTIL, (int(user_id), int(guild_id)))
            row = cursor.fetchone()
        return bool(row) and time.time() < row[0]
    except Exception:
        return False
