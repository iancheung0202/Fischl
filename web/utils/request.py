import requests
from concurrent.futures import ThreadPoolExecutor
from config.settings import BOT_TOKEN, API_BASE

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

requests_session = requests.Session()
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PATCH"],
    backoff_factor=1
)
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry_strategy)
requests_session.mount("http://", adapter)
requests_session.mount("https://", adapter)


def verify_guild_access(guild_id, discord_token, api_base=API_BASE, bot_token=BOT_TOKEN, require_admin=True, require_bot_in_guild=True, user_guilds_only=False):
    """
    Verify that the user has access to a guild and optionally check permissions and bot membership.
    
    Args:
        guild_id (str): The Discord guild ID to verify
        discord_token (str): The user's Discord access token
        api_base (str): The Discord API base URL
        bot_token (str): The bot's token
        require_admin (bool): Whether to require administrator permissions (default: True)
        require_bot_in_guild (bool): Whether to require bot to be in the guild (default: True)
        user_guilds_only (bool): Whether to restrict access to user-guilds-only features (default: False)

    Returns:
        tuple: (success: bool, guild_or_error: dict, status_code: int)
               - If success=True: guild_or_error contains guild data, status_code is None
               - If success=False: guild_or_error contains error info, status_code is HTTP code
    """
    def fetch_user_guilds():
        try:
            guilds = requests_session.get(f"{api_base}/users/@me/guilds", 
                                        headers={"Authorization": f"Bearer {discord_token}"}).json()
            guild = next((g for g in guilds if g['id'] == guild_id), None)
            
            if not guild:
                return False, {"error": "Guild not found or you don't have access to this guild anymore."}, 404

            if require_admin and not (guild.get("owner") or (int(guild.get("permissions", 0)) & 0x8)):
                return False, {"error": "You need administrator permissions to configure this guild."}, 403
            
            return True, guild, None
        except Exception as e:
            return False, {"error": f"Failed to fetch user guilds: {str(e)}"}, 500

    def fetch_bot_guilds():
        if not require_bot_in_guild:
            return True, None, None
            
        try:
            bot_guilds = requests_session.get(f"{api_base}/users/@me/guilds", 
                                            headers={"Authorization": f"Bot {bot_token}"}).json()
            bot_guild_ids = {g["id"] for g in bot_guilds}

            if guild_id not in bot_guild_ids:
                return False, {"error": "Bot is not in this guild. Please invite it first."}, 400
            
            return True, bot_guild_ids, None
        except Exception as e:
            return False, {"error": f"Failed to fetch bot guilds: {str(e)}"}, 500

    # Execute verifications concurrently
    if require_bot_in_guild:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_guild = executor.submit(fetch_user_guilds)
            if user_guilds_only:
                future_bot_verification = executor.submit(lambda: (True, None, None))
            else:
                future_bot_verification = executor.submit(fetch_bot_guilds)

            guild_success, guild_data, guild_status = future_guild.result()
            if not guild_success:
                return guild_success, guild_data, guild_status
                
            bot_success, bot_data, bot_status = future_bot_verification.result()
            if not bot_success:
                return bot_success, bot_data, bot_status
            
            return True, guild_data, None
    else:
        return fetch_user_guilds()