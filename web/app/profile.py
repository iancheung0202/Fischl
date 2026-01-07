
import requests
import os
import time
import importlib.util
import concurrent.futures
import sys
import datetime
import base64
import traceback
import html
import io
import random
import asyncio

from PIL import Image, ImageDraw, ImageFont, ImageSequence
from firebase_admin import db
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, session, redirect, abort, jsonify

from config.settings import CLIENT_ID, CLIENT_SECRET, API_BASE, BOT_TOKEN, PROFILE_REDIRECT_URI, MORA_EMOTE, PAYPAL_CLIENT_ID, ELITE_TRACK_PRICE
from utils.firebase import save_user_to_firebase
from utils.request import requests_session
from utils.minigames import get_total_mora, get_guild_mora, check_events_enabled, get_current_season, get_current_track, activate_elite_subscription, is_elite_active, generate_mora_graph
from utils.theme import wrap_page
from utils.loading import create_loading_skeleton
from utils.daily_games import DAILY_GAMES, HANGMAN_WORDS, UNSCRAMBLE_WORDS, TYPING_PHRASES

profile = Blueprint('profile', __name__)

async def addMora(userID: int, addedMora: int, channelID: int, guildID: int, client=None):
    """Add Mora to user's account with timestamp"""
    ts = str(int(time.time()))
    path = f"/Mora/{userID}/{guildID}/{channelID}/{ts}"
    db.reference(path).set(addedMora)

async def grant_summon(guild_id, user_id):
    """Grant a minigame summon to the user"""
    stats_ref = db.reference(f"/User Events Stats/{guild_id}/{user_id}")
    stats = stats_ref.get() or {}
    current_summons = stats.get("minigame_summons", 0)
    new_summons = current_summons + 1
    stats_ref.update({"minigame_summons": new_summons})
    return new_summons

def get_daily_games_status(user_id, guild_id):
    """Get user's daily games status for a specific guild"""
    ref = db.reference(f"/Daily Games/{user_id}/{guild_id}")
    data = ref.get() or {}
    
    # Check if it's a new day (UTC)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    last_reset = data.get("last_reset", "")
    
    if last_reset != today:
        # Generate a random game for today
        game_id = random.choice(list(DAILY_GAMES.keys()))
        
        # Reset for new day
        data = {
            "last_reset": today,
            "daily_game_id": game_id,
            "game_completed": False,
            "game_success": False,
            "mora_earned": 0,
            "completed_at": 0,
            "total_games_played": data.get("total_games_played", 0),
            "total_mora_earned": data.get("total_mora_earned", 0),
            "total_summons_earned": data.get("total_summons_earned", 0)
        }
        ref.set(data)
    
    return data

def can_play_game(user_id, guild_id):
    """Check if user can play today's game"""
    status = get_daily_games_status(user_id, guild_id)
    return not status.get("game_completed", False)

def record_game_completion(user_id, guild_id, success, mora_earned):
    """Record game completion for a specific guild"""
    ref = db.reference(f"/Daily Games/{user_id}/{guild_id}")
    data = ref.get() or {}
    
    data["game_completed"] = True
    data["game_success"] = success
    data["completed_at"] = int(time.time())
    
    if success:
        data["mora_earned"] = mora_earned
        data["total_mora_earned"] = data.get("total_mora_earned", 0) + mora_earned
        data["total_summons_earned"] = data.get("total_summons_earned", 0) + 1
        
        # Use proper Mora and summon functions
        # Note: These are sync functions called from Flask, so we need to handle async properly
        try:
            # Try to get the existing event loop first
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            # No existing loop or loop is closed, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            should_close_loop = True
        else:
            # Use existing loop
            should_close_loop = False
        
        try:
            # Add Mora using the proper function with website channel ID
            if loop.is_running():
                # If loop is already running, we need to use run_in_executor
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    executor.submit(asyncio.run, addMora(int(user_id), mora_earned, 200, int(guild_id))).result()
                    executor.submit(asyncio.run, grant_summon(int(guild_id), int(user_id))).result()
            else:
                # Loop is not running, safe to use run_until_complete
                loop.run_until_complete(addMora(int(user_id), mora_earned, 200, int(guild_id)))
                
                # Grant minigame summon
                loop.run_until_complete(grant_summon(int(guild_id), int(user_id)))
        finally:
            # Only close the loop if we created it
            if should_close_loop and not loop.is_closed():
                loop.close()
    else:
        data["mora_earned"] = 0
    
    data["total_games_played"] = data.get("total_games_played", 0) + 1
    
    ref.set(data)

def generate_memory_game():
    """Generate memory game data"""
    emojis = ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐸", "🐵", "🐔", "🐧"]
    selected_emojis = random.sample(emojis, 5)
    answer_position = random.randint(0, 4)  # 0-indexed position
    question_emoji = selected_emojis[answer_position]  # The emoji at that position
    return {
        "emojis": selected_emojis,
        "answer_position": answer_position + 1,  # Convert to 1-indexed for user
        "question_emoji": question_emoji
    }

def generate_math_game():
    """Generate math game data"""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    return {
        "num1": num1,
        "num2": num2,
        "answer": num1 + num2
    }

def generate_hangman_game():
    """Generate hangman game data"""
    word = random.choice(HANGMAN_WORDS)
    return {
        "word": word,
        "length": len(word),
        "display": "_" * len(word)
    }

def generate_shapes_game():
    """Generate shapes counting game"""
    shapes = ["🔴", "🔵", "🟢", "🟡", "🟣", "🔺", "⬜", "⬛"]
    target_shape = random.choice(shapes)
    
    # Generate random shapes for counting
    total_shapes = random.randint(15, 25)
    target_count = random.randint(3, 8)
    other_shapes = [random.choice([s for s in shapes if s != target_shape]) for _ in range(total_shapes - target_count)]
    all_shapes = [target_shape] * target_count + other_shapes
    random.shuffle(all_shapes)
    
    return {
        "shapes": all_shapes,
        "target_shape": target_shape,
        "correct_count": target_count
    }

def generate_typing_game():
    """Generate typing game data"""
    phrase = random.choice(TYPING_PHRASES)
    return {
        "phrase": phrase
    }

class MockUser:
    def __init__(self, user_data, member_data=None):
        self.id = user_data['id']
        self.display_name = member_data.get('nick') if member_data and member_data.get('nick') else user_data.get('global_name', user_data['username'])
        self.name = user_data['username']
        self.avatar_url = f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data.get('avatar', '')}.png?size=128"
    
    @property
    def avatar(self):
        return MockAvatar(self.avatar_url)

class MockAvatar:
    def __init__(self, url):
        self.url = url
    
    def with_static_format(self, format):
        return self
    
    def with_size(self, size):
        return self
    
    async def read(self):
        response = requests.get(self.url)
        return response.content

async def createProfileCard(
    user,
    num: str,
    rank: str,
    bg: str = "../assets/mora_bg.png",
    filename: str = "../assets/mora.png",
    profile_frame: str = None
):
    # Preload avatar once (RGBA circle)
    avatar_bytes = await user.avatar.read()
    im_avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    # Create circular mask for avatar
    mask = Image.new("L", im_avatar.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0) + im_avatar.size, fill=255)
    im_avatar.putalpha(mask)  # avatar is now circular RGBA

    # Preload fonts only once
    font_display = ImageFont.truetype("../assets/ja-jp.ttf", 45)
    font_username = ImageFont.truetype("../assets/ja-jp.ttf", 25)
    font_mora = ImageFont.truetype("../assets/ja-jp.ttf", 40)
    font_rank = ImageFont.truetype("../assets/ja-jp.ttf", 35)

    # Helper to load image frames
    def load_image_frames(path):
        if not os.path.exists(path):
            return None, None, None
        try:
            im = Image.open(path)
            frames = []
            durations = []
            disposals = []
            if path.lower().endswith('.gif'):
                for frame in ImageSequence.Iterator(im):
                    frames.append(frame.convert('RGBA'))
                    durations.append(frame.info.get('duration', 100))
                    disposals.append(frame.info.get('disposal', 2))
                return frames, durations, disposals
            else:
                return [im.convert('RGBA')], [100], [2]
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None, None, None

    # Determine if we need animated output
    bg_animated = bg and bg.lower().endswith('.gif') and os.path.exists(bg)
    frame_animated = profile_frame and profile_frame.lower().endswith('.gif') and os.path.exists(f"../assets/Profile Frame/{profile_frame}")
    print("bg_animated:", bg_animated)
    print("frame_animated:", frame_animated)
    print("bg exists:", os.path.exists(bg) if bg else "no bg")
    print("frame exists:", os.path.exists(f"../assets/Profile Frame/{profile_frame}") if profile_frame else "no frame")

    
    if bg_animated or frame_animated:
        print("Generating animated profile card...")
        # Load background frames
        bg_frames, bg_durations, bg_disposals = load_image_frames(bg) or ([Image.new('RGBA', (720, 256), (0,0,0,255))], [100], [2])

        # Load profile frame frames
        frame_path = f"../assets/Profile Frame/{profile_frame}" if profile_frame else None
        frame_frames, frame_durations, frame_disposals = load_image_frames(frame_path) or ([None], [100], [2])
        print("Number of bg frames:", len(bg_frames))
        print("Number of frame frames:", len(frame_frames))
        
        # Determine frame count and timing
        if len(bg_frames) > 1:  # Background animation drives timing
            total_frames = len(bg_frames)
            durations = bg_durations
            disposals = bg_disposals
            if len(frame_frames) == 1:  # Static frame
                frame_frames = frame_frames * total_frames
            else:  # Animated frame - cycle to match background
                frame_frames = [frame_frames[i % len(frame_frames)] for i in range(total_frames)]
        else:  # Frame animation drives timing
            total_frames = len(frame_frames)
            durations = frame_durations
            disposals = frame_disposals
            bg_frames = bg_frames * total_frames  # Repeat static BG
        
        # Create output frames
        output_frames = []
        for i in range(total_frames):

            frame = bg_frames[i].copy()
            frame.paste(im_avatar, (40, 30), im_avatar)
            
            try:
                im_mora_icon = Image.open("../assets/mora_icon.png").convert("RGBA")
                # Create circular mask for Mora icon
                icon_mask = Image.new("L", im_mora_icon.size, 0)
                d_icon = ImageDraw.Draw(icon_mask)
                d_icon.ellipse((0, 0) + im_mora_icon.size, fill=255)
                im_mora_icon.putalpha(icon_mask)
                frame.paste(im_mora_icon, (38, 190), im_mora_icon)
            except FileNotFoundError:
                # If mora_icon.png is missing, skip it
                pass
            
            if frame_frames[i]:
                frame_img = frame_frames[i]
                x = 40 + (128 - frame_img.width) // 2
                y = 30 + (128 - frame_img.height) // 2
                frame.paste(frame_img, (x, y), frame_img)
            
            draw = ImageDraw.Draw(frame)
            draw.text((200, 45), user.display_name, font=font_display, fill=(255, 255, 255))
            draw.text((200, 100), user.name, font=font_username, fill=(225, 225, 225))
            draw.text((89, 185), num.split(".")[0], font=font_mora, fill=(233, 253, 255))
            
            if rank != "N/A":
                draw.text((400, 190), f"Guild Rank: {rank}", font=font_rank, fill=(203, 254, 196))
            
            output_frames.append(frame)
        
        # Save animated GIF
        if not filename.lower().endswith('.gif'):
            filename = filename.rsplit(".", 1)[0] + ".gif"
            print("Forcing output to .gif:", filename)


        output_frames[0].save(
            filename,
            save_all=True,
            append_images=output_frames[1:],
            duration=durations,
            loop=0,
            disposal=disposals,
            optimize=False,
        )
        return filename

    # Otherwise: create a static (PNG) card 
    # Load a static background image (PNG)
    try:
        im_bg = Image.open(bg).convert("RGBA")
    except Exception:
        im_bg = Image.open("../assets/mora_bg.png").convert("RGBA")

    # Paste the avatar onto background
    im_bg.paste(im_avatar, (40, 30), im_avatar)
    im_profile_frame = Image.open(f"../assets/Profile Frame/{profile_frame}").convert("RGBA") if profile_frame else None
    # Paste the Mora icon
    try:
        im_mora_icon = Image.open("../assets/mora_icon.png").convert("RGBA")
        # Create circular mask for Mora icon
        icon_mask = Image.new("L", im_mora_icon.size, 0)
        d_icon = ImageDraw.Draw(icon_mask)
        d_icon.ellipse((0, 0) + im_mora_icon.size, fill=255)
        im_mora_icon.putalpha(icon_mask)
        im_bg.paste(im_mora_icon, (38, 190), im_mora_icon)
    except FileNotFoundError:
        # If mora_icon.png is missing, skip it
        pass

    if im_profile_frame:
        frame_w, frame_h = im_profile_frame.size
        avatar_w, avatar_h = im_avatar.size  # should be 128 x 128

        # Center the frame over the avatar's center (which is at 20 + 128 // 2 = 84, 84)
        center_x = 40 + avatar_w // 2
        center_y = 30 + avatar_h // 2

        paste_x = center_x - frame_w // 2
        paste_y = center_y - frame_h // 2

        im_bg.paste(im_profile_frame, (paste_x, paste_y), im_profile_frame)
        
    # Draw all text onto the static background
    draw = ImageDraw.Draw(im_bg)
    draw.text((200, 45), user.display_name, font=font_display, fill=(255, 255, 255))
    draw.text((200, 100), user.name, font=font_username, fill=(225, 225, 225))
    draw.text((89, 185), num.split(".")[0], font=font_mora, fill=(233, 253, 255))

    if rank != "N/A":
        draw.text((400, 190), f"Guild Rank: {rank}", font=font_rank, fill=(203, 254, 196))

    # Finally save once (PNG)
    im_bg.save(filename)
    return filename

# Import quests
quests_path = os.path.join(os.path.dirname(__file__), "..", "..", "commands", "Events", "quests.py")
spec_quests = importlib.util.spec_from_file_location("quests", quests_path)
quests_module = importlib.util.module_from_spec(spec_quests)
sys.modules["quests"] = quests_module
spec_quests.loader.exec_module(quests_module)
QUEST_DESCRIPTIONS = quests_module.QUEST_DESCRIPTIONS
QUEST_BONUS_XP = quests_module.QUEST_BONUS_XP
QUEST_XP_REWARDS = quests_module.QUEST_XP_REWARDS

@profile.route("/profile")
def view_profile():
    """Profile page - shows user's servers where they can view their stats"""
    # Handle OAuth callback
    code = request.args.get("code")
    if code:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": PROFILE_REDIRECT_URI,
            "scope": "identify guilds",
        }

        r = requests.post(f"{API_BASE}/oauth2/token", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status_code != 200:
            return f"Token exchange failed: {r.text}", 400

        tokens = r.json()
        session["discord_token"] = tokens["access_token"]

        user = requests.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()
        save_user_to_firebase(user, tokens["access_token"])
        session["user_id"] = str(user["id"])  # Ensure string type to avoid precision issues

        return redirect("/profile")

    # Check authentication for normal visits
    if "discord_token" not in session:
        return redirect("/auth")
    
    # Get basic user info immediately for display
    discord_token = session['discord_token']
    user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
    
    # Page content with immediate user info and skeleton loading for guilds
    content = f"""
      <main class="p-6 max-w-5xl mx-auto">
        <div class="flex items-center gap-4 mb-8">
          <img src="https://cdn.discordapp.com/avatars/{user['id']}/{user.get('avatar','')}.png?size=128" 
               alt="Avatar" class="rounded-full w-20 h-20 shadow-md">
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{user['username']}</h2>
            <p class="text-gray-500 dark:text-gray-400">ID: {user['id']}</p>
            <div id="total-mora-container">
              <div class="animate-pulse">
                <div class="bg-gray-200 dark:bg-gray-600 h-6 w-40 rounded"></div>
              </div>
            </div>
          </div>
        </div>

        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Your Servers with Minigames</h3>
        <div id="guilds-container" class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {create_loading_skeleton(3, "bg-white dark:bg-gray-800 rounded-2xl shadow p-6 transition-colors", "guild")}
        </div>
      </main>
      
      <script>
        // Load guild data and total mora asynchronously
        fetch('/api/profile/data')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.getElementById('guilds-container').innerHTML = 
                '<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">' + data.error + '</p></div>';
              return;
            }}
            document.getElementById('guilds-container').innerHTML = data.html;
            // Update total mora if provided
            if (data.total_mora) {{
              document.getElementById('total-mora-container').innerHTML = 
                '<p class="text-green-600 dark:text-green-400 font-medium">' + data.total_mora + '</p>';
            }}
          }})
          .catch(error => {{
            console.error('Error loading profile data:', error);
            document.getElementById('guilds-container').innerHTML = 
              '<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">Failed to load content. Please refresh the page.</p></div>';
          }});
      </script>
    """
    
    return wrap_page("Profile - Fischl", content, [("/dashboard", "Dashboard", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@profile.route("/api/profile/data")
def api_profile_data():
    """API endpoint for profile guild data"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Extract session data
    discord_token = session['discord_token']
    user_id = session['user_id']

    # Make concurrent API calls
    def fetch_user_guilds(token):
        return requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}).json()
    
    def fetch_bot_guilds():
        all_guilds = []
        last_id = None
        while True:
            params = {"limit": 200}
            if last_id:
                params["after"] = last_id
            
            try:
                resp = requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bot {BOT_TOKEN}"}, params=params)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                all_guilds.extend(data)
                if len(data) < 200:
                    break
                last_id = data[-1]["id"]
            except Exception as e:
                print(f"Error fetching bot guilds: {e}")
                break
        return all_guilds

    # Execute all API calls concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        guilds_future = executor.submit(fetch_user_guilds, discord_token)
        bot_guilds_future = executor.submit(fetch_bot_guilds)
        
        guilds = guilds_future.result()
        bot_guilds = bot_guilds_future.result()

    bot_guild_ids = {g["id"] for g in bot_guilds}

    guild_cards = ""
    guilds_with_events = []
    
    # Pre-fetch stickies for optimization
    stickies_data = db.reference("/Global Events System").get() or {}

    # Filter guilds where bot is present and events are enabled
    for g in guilds:
        if g["id"] in bot_guild_ids and check_events_enabled(g["id"], stickies_data):
            guilds_with_events.append(g)

    guilds_sorted = sorted(guilds_with_events, key=lambda g: g["name"].lower())

    for g in guilds_sorted:
        icon = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png?size=128" if g.get("icon") else ""
        
        # Get user's mora in this guild
        user_mora = get_guild_mora(user_id, g['id'])
        
        guild_cards += f"""
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow p-6 transition-colors">
          <div class="flex items-center gap-4 mb-4">
            {"<img src='"+icon+"' class='rounded-full w-16 h-16 shadow-md'>" if icon else "<div class='w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300 text-xl font-bold'>"+(html.escape(g.get('name', 'Unknown')[0]) if g.get('name') else 'U')+"</div>"}
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white">{html.escape(g.get('name', 'Unknown Server'))}</h3>
              <p class="text-gray-500 dark:text-gray-400 text-sm">Events Enabled</p>
              <p class="text-blue-600 dark:text-blue-400 text-sm font-medium">{MORA_EMOTE} {user_mora:,} Mora</p>
            </div>
          </div>
          <a href="/profile/{g['id']}" class="block w-full py-2 bg-blue-500 dark:bg-blue-600 text-white rounded-md text-center font-medium hover:bg-blue-600 dark:hover:bg-blue-700 transition">
            View Stats
          </a>
        </div>"""

    # Also update the total mora in the header
    total_mora = get_total_mora(user_id)
    
    # Build response with guild cards and total mora update
    guild_content = guild_cards if guild_cards else "<p class='col-span-full text-center text-gray-500 dark:text-gray-400 py-8'>No servers found with minigames enabled.</p>"
    
    # Return both guild data and total mora update
    return jsonify({
        "html": guild_content,
        "total_mora": f"Total Mora: {MORA_EMOTE} {total_mora:,}"
    })

@profile.route("/api/profile/total-mora")
def api_profile_total_mora():
    """API endpoint for updating total mora"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = session['user_id']
    total_mora = get_total_mora(user_id)
    
    return jsonify({
        "html": f'<p class="text-green-600 dark:text-green-400 font-medium">Total Mora: {MORA_EMOTE} {total_mora:,}</p>'
    })

@profile.route("/profile/<guild_id>")
def profile_guild(guild_id):
    """Profile page for a specific guild - shows user stats in 4 tabs like mora command"""
    if "discord_token" not in session:
        return redirect("/auth")
    
    # Extract session data
    discord_token = session['discord_token']
    user_id = session['user_id']
    
    # Get basic user info immediately
    user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
    
    # Verify user has access to this guild (quick check)
    guilds = requests_session.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization": f"Bearer {discord_token}"}).json()
    guild = next((g for g in guilds if g['id'] == guild_id), None)
    if not guild:
        abort(404)
    
    # Verify events are enabled in this guild
    if not check_events_enabled(guild_id):
        content = """
        <main class="p-6 max-w-3xl mx-auto">
          <div class="bg-yellow-100 dark:bg-yellow-900 border border-yellow-400 dark:border-yellow-600 text-yellow-700 dark:text-yellow-200 px-4 py-3 rounded">
            <h3 class="font-bold">Minigames Not Enabled</h3>
            <p>This server doesn't have minigames enabled, so there are no stats to display.</p>
          </div>
        </main>
        """
        
        return wrap_page(f"Profile - {html.escape(guild['name'])}", content, [("/profile", "Back to Profile", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])
    
    icon = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=128" if guild.get("icon") else ""
    
    content = f"""
      <style>
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .tab-button.active {{ background-color: #3b82f6; color: white; }}
        
        /* PayPal form styling fixes */
        #paypal-button-container iframe {{
          min-height: 300px !important;
        }}
      </style>

      <main class="p-6 max-w-5xl mx-auto">
        <div class="flex items-center gap-4 mb-8">
          {"<img src='"+icon+"' class='rounded-full w-16 h-16 shadow-md'>" if icon else "<div class='w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500 dark:text-gray-300'>"+html.escape(guild['name'][0])+"</div>"}
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">
              <div id="display-name-container">
                <div class="animate-pulse">
                  <div class="bg-gray-200 dark:bg-gray-600 h-8 w-64 rounded"></div>
                </div>
              </div>
            </h2>
            <p class="text-gray-500 dark:text-gray-400">Guild ID: {guild['id']}</p>
          </div>
        </div>

        <div id="elite-track-container">
          <div class="animate-pulse border-2 border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 rounded-2xl p-6 mb-8">
            <div class="bg-gray-200 dark:bg-gray-600 h-8 w-96 rounded mb-4 mx-auto"></div>
            <div class="bg-gray-200 dark:bg-gray-600 h-4 w-full rounded mb-2"></div>
            <div class="bg-gray-200 dark:bg-gray-600 h-4 w-3/4 rounded mb-4 mx-auto"></div>
            <div class="bg-gray-200 dark:bg-gray-600 h-12 w-64 rounded mx-auto"></div>
          </div>
        </div>

        <!-- Tab Navigation -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow mb-6 transition-colors">
          <div class="flex border-b border-gray-200 dark:border-gray-700">
            <button class="tab-button px-6 py-3 font-medium rounded-tl-lg active text-gray-900 dark:text-white" onclick="showTab('inventory')">
              Inventory
            </button>
            <button class="tab-button px-6 py-3 font-medium text-gray-900 dark:text-white" onclick="showTab('stats')">
              Stats
            </button>
            <button class="tab-button px-6 py-3 font-medium text-gray-900 dark:text-white" onclick="showTab('track')">
              Track
            </button>
            <button class="tab-button px-6 py-3 font-medium text-gray-900 dark:text-white" onclick="showTab('quests')">
              Quests
            </button>
            <button class="tab-button px-6 py-3 font-medium rounded-tr-lg text-gray-900 dark:text-white" onclick="showTab('dailygame')">
              🎮 Daily Game
            </button>
          </div>

          <!-- Tab Contents -->
          <div class="p-6">
            <!-- Inventory Tab -->
            <div id="inventory" class="tab-content active">
              <div id="inventory-loading" class="text-center py-8">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p class="mt-2 text-gray-600 dark:text-gray-400">Loading inventory...</p>
              </div>
              <div id="inventory-content" style="display: none;"></div>
            </div>

            <!-- Stats Tab -->
            <div id="stats" class="tab-content">
              <div id="stats-loading" class="text-center py-8">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p class="mt-2 text-gray-600 dark:text-gray-400">Loading stats...</p>
              </div>
              <div id="stats-content" style="display: none;"></div>
            </div>

            <!-- Track Tab -->
            <div id="track" class="tab-content">
              <div id="track-loading" class="text-center py-8">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p class="mt-2 text-gray-600 dark:text-gray-400">Loading track...</p>
              </div>
              <div id="track-content" style="display: none;"></div>
            </div>

            <!-- Quests Tab -->
            <div id="quests" class="tab-content">
              <div id="quests-loading" class="text-center py-8">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p class="mt-2 text-gray-600 dark:text-gray-400">Loading quests...</p>
              </div>
              <div id="quests-content" style="display: none;"></div>
            </div>

            <!-- Daily Game Tab -->
            <div id="dailygame" class="tab-content">
              <div id="dailygame-loading" class="text-center py-8">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p class="mt-2 text-gray-600 dark:text-gray-400">Loading daily game...</p>
              </div>
              <div id="dailygame-content" style="display: none;"></div>
            </div>
          </div>
        </div>
      </main>

      <!-- Game Modal -->
      <div id="game-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <div class="p-6">
            <div class="flex justify-between items-center mb-4">
              <h3 id="game-title" class="text-2xl font-bold text-gray-900 dark:text-white">Game</h3>
              <button id="close-modal" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-2xl">×</button>
            </div>
            <div id="game-content" class="text-gray-900 dark:text-white">
              <!-- Game content will be loaded here -->
            </div>
          </div>
        </div>
      </div>

      <script>
        let currentTab = 'inventory';
        let loadedTabs = new Set();

        function showTab(tabName) {{
          // Hide all tabs and remove active class
          document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
          document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
          
          // Show selected tab and add active class
          document.getElementById(tabName).classList.add('active');
          event.target.classList.add('active');
          
          currentTab = tabName;
          
          // Load content if not already loaded
          if (!loadedTabs.has(tabName)) {{
            loadTabContent(tabName);
          }}
        }}

        function loadTabContent(tabName) {{
          fetch(`/profile/{guild_id}/` + tabName)
            .then(response => response.json())
            .then(data => {{
              document.getElementById(tabName + '-loading').style.display = 'none';
              document.getElementById(tabName + '-content').style.display = 'block';
              document.getElementById(tabName + '-content').innerHTML = data.content;
              loadedTabs.add(tabName);
            }})
            .catch(error => {{
              console.error('Error loading tab:', error);
              document.getElementById(tabName + '-loading').innerHTML = '<p class="text-red-500 dark:text-red-400">Error loading content</p>';
            }});
        }}

        // Load initial tab
        loadTabContent('inventory');

        // Game modal functionality
        const gameModal = document.getElementById('game-modal');
        const closeModal = document.getElementById('close-modal');
        
        closeModal.addEventListener('click', () => {{
          gameModal.classList.add('hidden');
          document.body.style.overflow = '';
        }});
        
        gameModal.addEventListener('click', (e) => {{
          if (e.target === gameModal) {{
            gameModal.classList.add('hidden');
            document.body.style.overflow = '';
          }}
        }});
        
        function openGame(gameId) {{
          document.getElementById('game-title').textContent = 'Loading...';
          document.getElementById('game-content').innerHTML = '<div class="text-center py-8"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div></div>';
          gameModal.classList.remove('hidden');
          document.body.style.overflow = 'hidden';
          
          fetch('/api/daily-games/{guild_id}/' + gameId + '/play')
            .then(response => response.json())
            .then(data => {{
              if (data.error) {{
                document.getElementById('game-content').innerHTML = '<div class="text-center py-8"><p class="text-red-500">' + data.error + '</p></div>';
                return;
              }}
              document.getElementById('game-title').textContent = data.title;
              // Set innerHTML first
              document.getElementById('game-content').innerHTML = data.html;
              
              // Execute any scripts in the loaded content
              const scripts = document.getElementById('game-content').querySelectorAll('script');
              scripts.forEach(script => {{
                const newScript = document.createElement('script');
                if (script.src) {{
                  newScript.src = script.src;
                }} else {{
                  newScript.textContent = script.textContent;
                }}
                document.head.appendChild(newScript);
              }});
            }})
            .catch(error => {{
              console.error('Error loading game:', error);
              document.getElementById('game-content').innerHTML = '<div class="text-center py-8"><p class="text-red-500">Failed to load game</p></div>';
            }});
        }}

        // Load guild info asynchronously
        fetch('/api/profile/{guild_id}/info')
          .then(response => response.json())
          .then(data => {{
            if (data.error) {{
              document.getElementById('display-name-container').innerHTML = 
                '<span class="text-red-500 dark:text-red-400">' + data.error + '</span>';
              return;
            }}
            document.getElementById('display-name-container').innerHTML = data.display_name + ' in ' + {repr(guild["name"])};
            document.getElementById('elite-track-container').innerHTML = data.elite_track_html;
          }})
          .catch(error => {{
            console.error('Error loading guild info:', error);
            document.getElementById('display-name-container').innerHTML = 
              '<span class="text-red-500 dark:text-red-400">Error loading info</span>';
          }});
      </script>

      <!-- PayPal Modal -->
      <style>
        .gradient-text {{
          background: linear-gradient(270deg, #FC774E, #E3346E, #FC774E);
          background-size: 200% 100%;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          animation: gradientMove 1.5s linear infinite;
        }}
        .gradient-bg {{
          background: linear-gradient(270deg, #fd9271, #f06292, #fd9271);
          background-size: 200% 100%;
          animation: gradientMove 1.5s linear infinite;
        }}
        @keyframes gradientMove {{
          0% {{
            background-position: 0% center;
          }}
          100% {{
            background-position: 200% center;
          }}
        }}
      </style>
      <div id="paypal-modal" class="hidden fixed inset-0 bg-black bg-opacity-85 z-50 flex justify-center items-center p-4">
        <div class="relative w-full max-w-md max-h-full bg-white rounded-xl shadow-2xl text-center overflow-hidden text-gray-900 flex flex-col">
          <div class="p-6 pb-4">
            <button id="modalCloseBtn" class="absolute top-3 right-4 bg-transparent border-none text-2xl font-bold cursor-pointer text-gray-600 hover:text-gray-900" aria-label="Close modal">&times;</button>
            <h3 class="text-2xl font-bold mb-4 text-gray-900">Complete Your Purchase</h3>
            <p class="text-xl mb-4 gradient-text font-bold">Activate Elite Track in <b>{html.escape(guild['name'])}</b> for just <b>${ELITE_TRACK_PRICE}</b>!</p> <!-- Moving gradient color -->
          </div>
          <div class="flex-1 overflow-y-auto px-6">
            <div id="paypal-button-container" class="min-h-0"></div>
          </div>
          <div class="p-6 pt-4">
            <div class="text-xs text-gray-600">
              <p class="mt-2 text-yellow-600">One season lasts for 3 months. Thanks for supporting the bot!</p>
            </div>
          </div>
        </div>
      </div>

      <script src="https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}&intent=capture&enable-funding=venmo&currency=USD"></script>

      <script>
        // Modal and PayPal button logic
        const modal = document.getElementById('paypal-modal');
        const paypalContainer = document.getElementById('paypal-button-container');
        const closeBtn = document.getElementById('modalCloseBtn');

        function disableBodyScroll() {{
          document.body.style.overflow = 'hidden';
        }}

        function enableBodyScroll() {{
          document.body.style.overflow = '';
        }}

        function clearPaypalButtons() {{
          paypalContainer.innerHTML = '';
        }}

        function renderPaypalButton() {{
          // Clear before render
          clearPaypalButtons();
          
          // Check if PayPal SDK is loaded
          if (typeof paypal === 'undefined') {{
            paypalContainer.innerHTML = '<div class="text-red-400 text-center p-4">PayPal SDK failed to load. Please refresh the page.</div>';
            return;
          }}
          
          console.log('PayPal SDK loaded, rendering button...');
          
          // Render PayPal button with better error handling
          paypal.Buttons({{
            createOrder: function(data, actions) {{
              console.log('Creating PayPal order...');
              console.log('User ID: "{user_id}", Guild ID: "{guild_id}"');
              return actions.order.create({{
                purchase_units: [{{
                  amount: {{
                    value: '{ELITE_TRACK_PRICE}',
                    currency_code: 'USD'
                  }},
                  description: 'Fischl Discord Bot Elite Track (1 season)',
                  custom_id: '{user_id}-{guild_id}'
                }}],
                application_context: {{
                  shipping_preference: 'NO_SHIPPING'  // Disable shipping address collection
                }}
              }}).then(function(orderID) {{
                console.log('Order created successfully:', orderID);
                return orderID;
              }}).catch(function(error) {{
                console.error('Error creating order:', error);
                alert('Failed to create payment order. Please try again. Error: ' + (error.message || error));
                throw error;
              }});
            }},
            onApprove: function(data, actions) {{
              console.log('Payment approved:', data);
              return actions.order.capture().then(function(details) {{
                console.log('Payment captured:', details);
                
                // Show loading state
                paypalContainer.innerHTML = '<div class="text-white text-center p-4">Processing payment...</div>';
                
                // Activate subscription immediately
                return fetch('/payment/activate', {{
                  method: 'POST',
                  headers: {{
                    'Content-Type': 'application/json',
                  }},
                  body: JSON.stringify({{
                    user_id: "{user_id}",  // Ensure string to avoid precision loss
                    guild_id: "{guild_id}",
                    order_id: data.orderID,
                    payment_details: details
                  }})
                }}).then(response => {{
                  console.log('Activation response status:', response.status);
                  if (response.ok) {{
                    window.location.href = '/payment/success?guild_id={guild_id}';
                  }} else {{
                    return response.json().then(errorData => {{
                      console.error('Activation error:', errorData);
                      alert('Payment processed but there was an error activating your subscription. Please contact support with order ID: ' + data.orderID);
                    }});
                  }}
                }}).catch(error => {{
                  console.error('Network error:', error);
                  alert('Payment processed but there was a network error. Please contact support with order ID: ' + data.orderID);
                }});
              }}).catch(function(error) {{
                console.error('Error capturing payment:', error);
                alert('Payment capture failed. Please try again.');
              }});
            }},
            onCancel: function(data) {{
              console.log('Payment cancelled:', data);
              closePaypalModal();
            }},
            onError: function(err) {{
              console.error('PayPal button error:', err);
              alert('Payment system error. Please refresh the page and try again.');
            }},
            style: {{
              layout: 'vertical',
              color: 'blue',
              shape: 'rect',
              label: 'paypal',
              height: 40
            }}
          }}).render('#paypal-button-container').catch(function(error) {{
            console.error('Failed to render PayPal button:', error);
            paypalContainer.innerHTML = '<div class="text-red-400 text-center p-4">Failed to load payment options. Please refresh the page.</div>';
          }});
        }}

        function openModal() {{
          console.log('Opening PayPal modal...');
          modal.classList.remove('hidden');
          disableBodyScroll();
          
          // Add loading message
          paypalContainer.innerHTML = '<div class="text-white text-center p-4">Loading payment options...</div>';
          
          // Small delay to ensure modal is visible before rendering button
          setTimeout(function() {{
            renderPaypalButton();
          }}, 100);
        }}

        function closePaypalModal() {{
          console.log('Closing PayPal modal...');
          modal.classList.add('hidden');
          enableBodyScroll();
          clearPaypalButtons();
        }}

        closeBtn.addEventListener('click', closePaypalModal);

        // Open modal on clicking unlock buttons (will be set up after elite track loads)
        document.addEventListener('click', function(e) {{
          if (e.target.classList.contains('btn-unlock')) {{
            console.log('Unlock button clicked');
            openModal();
          }}
        }});

        // Optional: close modal if clicking outside modal-content
        modal.addEventListener('click', (e) => {{
          if (e.target === modal) {{
            closePaypalModal();
          }}
        }});
      </script>
    """

    return wrap_page(f"Profile - {html.escape(guild['name'])}", content, [("/profile", "Back to Profile", "text-blue-500 dark:text-blue-400 font-medium hover:underline")])

@profile.route("/api/profile/<guild_id>/info")
def api_profile_guild_info(guild_id):
    """API endpoint for guild profile info"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    discord_token = session['discord_token']
    user_id = session['user_id']
    
    # Get user info and guild member info to get display name
    try:
        user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
        
        # Try to get guild member info for display name
        try:
            member = requests_session.get(f"{API_BASE}/guilds/{guild_id}/members/{user_id}", 
                                        headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
            display_name = member.get('nick') or user['username']
        except:
            display_name = user['username']
        
        # Check elite status and generate elite track HTML
        is_elite = is_elite_active(user_id, guild_id)
        
        if not is_elite:
            elite_track_html = f'''<div class="border-2 border-indigo-500 bg-indigo-200 dark:bg-indigo-900 rounded-2xl p-6 mb-8 text-black dark:text-white shadow-lg">
              <h2 class="text-2xl font-bold mb-2 text-center">Less than USD $1/month. More than worth it</h2>
              <p class="text-center text-indigo-900 dark:text-indigo-100 italic mb-4">"Cheaper than a single Genshin wish, plus you always get value."</p>
              <p class="text-lg font-semibold mb-3">Get <strong>Elite Track</strong> to unlock premium rewards to each track tier while supporting development work!</p>
              <ul class="space-y-2 mb-4 list-disc list-inside text-indigo-900 dark:text-indigo-100">
                <li>Animated backgrounds, frames, and badge titles</li>
                <li>Boosted Mora gains, gifting perks, and chest upgrades</li>
                <li>+1 extra Prestige at the final tier</li>
              </ul>
              <p class="text-indigo-900 dark:text-indigo-100 italic mb-4">One purchase only unlocks elite track rewards in one specific server.</p>
              <div class="flex justify-center mb-4">
                <button class="btn-unlock text-white font-bold py-3 px-8 rounded-lg hover:bg-indigo-50 transition gradient-bg">
                  Unlock Elite Track – USD ${ELITE_TRACK_PRICE} (3 months)
                </button>
              </div>
              <p class="text-sm text-indigo-900 dark:text-indigo-100 text-center italic">Note: One season lasts for 3 months. Thanks for supporting the bot!</p>
            </div>'''
        else:
            elite_track_html = ""
        
        return jsonify({
            "display_name": display_name,
            "elite_track_html": elite_track_html
        })
        
    except Exception as e:
        print(f"Error loading guild info: {e}")
        return jsonify({"error": "Failed to load guild information"}), 500

@profile.route("/profile/<guild_id>/inventory")
def profile_inventory(guild_id):
    """Get inventory tab content"""
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401
    
    user_id = session['user_id']
    discord_token = session['discord_token']
    
    # Get user and member data for profile card
    try:
        user_data = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
        member_data = requests_session.get(f"{API_BASE}/guilds/{guild_id}/members/{user_id}", 
                                         headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
    except:
        return {"error": "Failed to fetch user data"}, 500
    
    # Create mock user object for profile card
    mock_user = MockUser(user_data, member_data)
    
    # Get guild mora balance for profile card
    guild_mora = get_guild_mora(user_id, guild_id)
    
    # Calculate guild rank like in mora.py
    all_users = db.reference("/Mora").get() or {}
    guild_data = []
    for uid_str, guilds in all_users.items():
        uid = int(uid_str)
        guild_str = str(guild_id)
        if guild_str in guilds:
            user_mora = sum(
                mora for channel_data in guilds[guild_str].values()
                for mora in channel_data.values()
                if isinstance(mora, int) and mora >= 0
            )
            guild_data.append((uid, user_mora))
    
    if guild_data:
        guild_data.sort(key=lambda x: x[1], reverse=True)
        guild_rank = next((i+1 for i,(uid,_) in enumerate(guild_data) if uid == int(user_id)), "N/A")
    else:
        guild_rank = "N/A"
    
    # Get selected cosmetics for profile card
    ref_selected = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/selected")
    selected = ref_selected.get() or {}
    
    # Generate profile card
    try:
        import asyncio
        
        # Determine background and frame
        bg_path = "../assets/mora_bg.png"  # default

        animated_background = selected.get("animated_background")
        profile_frame = selected.get("profile_frame")

        customized = os.path.isfile(f"../assets/Mora Inventory Background/{user_id}.png") or bool(profile_frame) or bool(animated_background)

        if customized:
            if animated_background:
                bg_path = f"../assets/Animated Mora Inventory Background/{animated_background}.gif"
            else:
                bg_path = f"../assets/Mora Inventory Background/{user_id}.png"

        # Create unique filename for this user/guild
        card_filename = f"./assets/profile_cards/{user_id}_{guild_id}.png"
        os.makedirs("./assets/profile_cards", exist_ok=True)
        
        # Generate profile card (need to handle async in sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            card_path = loop.run_until_complete(createProfileCard(
                mock_user,
                f"{guild_mora:,}",
                str(guild_rank),
                bg_path,
                card_filename,
                profile_frame
            ))
        finally:
            loop.close()
        
        # Convert to base64 for web display
        with open(card_path, 'rb') as f:
            card_data = base64.b64encode(f.read()).decode()
        
        # Determine file extension for proper MIME type
        is_gif = card_path.lower().endswith('.gif')
        mime_type = "image/gif" if is_gif else "image/png"
        
        profile_card_html = f"""
        <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 transition-colors mb-6">
          <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">🎴 Profile Card</h3>
          <div class="flex justify-center">
            <img src="data:{mime_type};base64,{card_data}" alt="Profile Card" class="rounded-lg shadow-lg max-w-full">
          </div>
        </div>
        """
    except Exception as e:
        print(f"Error generating profile card: {e}")
        profile_card_html = ""
    
    # Get inventory data using the same structure as mora.py

    ref = db.reference("/User Events Inventory")
    inventories = ref.get() or {}
    
    inv_content = "No shop items purchased yet"
    MAX_INV_LENGTH = 1024
    EXTRA_LENGTH = 15
    
    if inventories:
        for key, val in inventories.items():
            if val.get("User ID") == int(user_id):
                # Process items like in Discord bot
                guild_inventories = []
                items = val.get("Items", [])
                
                for item in items:
                    # Skip milestones (cost=0) and items not for this guild
                    if len(item) > 3 and item[2] != 0 and item[3] == int(guild_id):
                        item_name = item[0]  # First element is the name
                        # Count duplicates
                        count = sum(1 for i in items if len(i) > 3 and i[0] == item_name and i[3] == int(guild_id))
                        
                        # Only add once per unique item
                        if not any(item_name in existing for existing in guild_inventories):
                            if count == 1:
                                guild_inventories.append(f"<b>{item_name}</b>")
                            else:
                                guild_inventories.append(f"<b>{item_name}</b> <code>(x{count})</code>")

                if guild_inventories:
                    # Make a list
                    full_text = "<ul style='list-style-type: disc; padding-left: 1.2em;'>"
                    for inv in guild_inventories:
                        full_text += f"<li>{inv}</li>"
                    full_text += "</ul>"
                    if len(full_text) <= MAX_INV_LENGTH - EXTRA_LENGTH:
                        inv_content = full_text
                    else:
                        # Calculate how many items we can fit
                        truncated_text = ""
                        included_items = 0
                        for item in guild_inventories:
                            test_text = f"{truncated_text} • {item}" if truncated_text else item
                            if len(test_text) + EXTRA_LENGTH <= MAX_INV_LENGTH:
                                truncated_text = test_text
                                included_items += 1
                            else:
                                break
                        
                        remaining_count = len(guild_inventories) - included_items
                        inv_content = f"{truncated_text} (+{remaining_count} more)"
                break
    
    # Get milestones like in Discord bot
    milestones_ref = db.reference(f"/Milestones/{guild_id}")
    milestones = milestones_ref.get() or {}
    
    # Fetch user's earned milestones
    user_milestones = []
    if inventories:
        for key, val in inventories.items():
            if val.get("User ID") == int(user_id):
                for item in val.get("Items", []):
                    # Milestones are identified by cost=0 and matching guild ID
                    if len(item) > 3 and item[2] == 0 and item[3] == int(guild_id):
                        # Find corresponding milestone info
                        milestone_name = item[0]
                        for milestone_id, milestone_data in milestones.items():
                            if isinstance(milestone_data, dict) and milestone_data.get("reward") == milestone_name:
                                user_milestones.append({
                                    "threshold": milestone_data.get("threshold", 0),
                                    "reward": milestone_data.get("reward", "Unknown")
                                })
                                break
                break
    
    # Format milestones
    milestones_content = "No milestones earned yet"
    if user_milestones:
        user_milestones.sort(key=lambda x: x["threshold"])
        milestone_items = []
        for ms in user_milestones:
            is_role = isinstance(ms["reward"], int) or str(ms["reward"]).isdigit()
            reward_display = f"<@&{ms['reward']}>" if is_role else ms["reward"]
            milestone_items.append(f"<li>{MORA_EMOTE} <code>{ms['threshold']:,}</code> - <b>{reward_display}</b></li>")
        milestones_content = "<ul style='list-style-type: disc; padding-left: 1.2em;'>" + "".join(milestone_items) + "</ul>"

    content = f"""
    <div class="space-y-6">
      {profile_card_html}
      
      <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 transition-colors">
        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">🛍️ Guild Inventory</h3>
        <div class="text-gray-700 dark:text-gray-300">
          {inv_content}
        </div>
      </div>
      
      <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 transition-colors">
        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">🏆 Server Milestones</h3>
        <div class="text-gray-700 dark:text-gray-300">
          {milestones_content}
        </div>
      </div>
    </div>
    """
    
    return {"content": content}

@profile.route("/profile/<guild_id>/stats")
def profile_stats(guild_id):
    """Get stats tab content"""
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401
    
    user_id = session['user_id']
    discord_token = session['discord_token']
    
    # Get user display name
    try:
        member = requests_session.get(f"{API_BASE}/guilds/{guild_id}/members/{user_id}", 
                                    headers={"Authorization": f"Bot {BOT_TOKEN}"}).json()
        display_name = member.get('nick')
        if not display_name:
            user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
            display_name = user['username']
    except:
        user = requests_session.get(f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {discord_token}"}).json()
        display_name = user['username']
    
    # Generate graph and get stats
    graph_result = generate_mora_graph(user_id, guild_id, display_name)
    
    if not graph_result:
        content = """
        <div class="text-center py-8">
          <p class="text-gray-500 dark:text-gray-400">No statistics available yet. Start playing minigames to see your stats!</p>
        </div>
        """
    else:
        graph_path, stats = graph_result
        
        # Convert graph to base64 for embedding
        with open(graph_path, 'rb') as f:
            graph_data = base64.b64encode(f.read()).decode()
        
        stats_html = ""
        for key, value in stats.items():
            stats_html += f"""
            <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
              <h4 class="font-semibold text-gray-800 dark:text-white mb-2">{key}</h4>
              <div class="text-gray-600 dark:text-gray-300">{value}</div>
            </div>
            """
        
        content = f"""
        <div class="space-y-6">
          <div class="bg-white dark:bg-gray-300 rounded-lg p-6 border border-gray-200 dark:border-gray-700 transition-colors">
            <img src="data:image/png;base64,{graph_data}" alt="Mora Graph" class="w-full rounded-lg">
          </div>
          
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            {stats_html}
          </div>
        </div>
        """
    
    return {"content": content}

@profile.route("/profile/<guild_id>/track")
def profile_track(guild_id):
    """Get track tab content"""
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401
    
    user_id = session['user_id']
    
    # Get user progression
    ref = db.reference(f"/Progression/{guild_id}/{user_id}")
    data = ref.get() or {"xp": 0, "prestige": 0}
    user_xp = data["xp"]
    prestige = data.get("prestige", 0)

    TRACK_DATA = get_current_track()
    
    # Calculate current tier
    current_tier = 0
    for tier in TRACK_DATA:
        if user_xp >= tier["cumulative_xp"]:
            current_tier = tier["tier"]
        else:
            break

    # Calculate XP in current tier
    prev_xp = TRACK_DATA[current_tier - 1]["cumulative_xp"] if current_tier > 0 else 0
    xp_in_current_tier = user_xp - prev_xp

    # Determine XP required for the next tier
    if current_tier < len(TRACK_DATA):
        next_tier_xp = TRACK_DATA[current_tier]["xp_req"]
        progress_percentage = (xp_in_current_tier / next_tier_xp) * 100 if next_tier_xp > 0 else 100
    else:
        next_tier_xp = 0
        progress_percentage = 100

    # Build track table - show claimed + current + 2 upcoming (like Discord)
    track_html = ""
    max_tier_to_show = max(len(TRACK_DATA), current_tier + 2) # Change to min if you want to show less tiers
    visible_tiers = TRACK_DATA[:max_tier_to_show + 1]  # inclusive

    for tier in visible_tiers:
        if tier["tier"] <= current_tier:
            status = "✅"
            row_class = "bg-green-100 dark:bg-green-900/20"
        elif tier["tier"] == current_tier + 1:
            status = "🔄"
            row_class = "bg-blue-100 dark:bg-blue-900/20"
        else:
            status = "🔐"
            row_class = "bg-gray-50 dark:bg-gray-700/20"

        # Display reward text with proper truncation like Discord (22 chars)
        free_reward = tier["free"].split("|")[0].strip()[:22]
        elite_reward = tier["elite"].split("|")[0].strip()[:22]

        track_html += f"""
        <tr class="{row_class}">
          <td class="px-4 py-2 font-semibold text-gray-900 dark:text-white">{tier['tier']}</td>
          <td class="px-4 py-2 text-center">{status}</td>
          <td class="px-4 py-2 text-gray-800 dark:text-gray-200">{free_reward}</td>
          <td class="px-4 py-2 text-gray-800 dark:text-gray-200">{elite_reward}</td>
        </tr>
        """
    
    # Show how many more tiers exist after the shown ones (like Discord)
    if max_tier_to_show < len(TRACK_DATA) - 1:
        hidden_remaining = len(TRACK_DATA) - (max_tier_to_show + 1)
        track_html += f"""
        <tr>
          <td colspan="4" class="px-4 py-2 text-center text-gray-500 dark:text-gray-400 italic">
            ... ({hidden_remaining} more tiers)
          </td>
        </tr>
        """

    # Get bonus stats
    stats_ref = db.reference(f"/User Events Stats/{guild_id}/{user_id}")
    stats = stats_ref.get() or {}
    
    season = get_current_season()
    is_elite = is_elite_active(user_id, guild_id)

    ref_selected = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/selected")
    selected = ref_selected.get() or {}
    ref_color = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/embed_color")
    color_unlocked = ref_color.get() or False
    color_status = "Not unlocked"
    if color_unlocked:
        custom_color = selected.get("embed_color_hex")
        color_status = f"{custom_color}" if custom_color else "Unlocked but not set"

    content = f"""
    <div class="space-y-6">
      <div class="bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg p-6 text-white">
        <h3 class="text-2xl font-bold mb-2">Season {season['id']}: {season['name']}</h3>
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div>
            <p class="text-sm opacity-90">Current Tier</p>
            <p class="text-2xl font-bold">{current_tier}</p>
          </div>
          <div>
            <p class="text-sm opacity-90">Total XP</p>
            <p class="text-2xl font-bold">{user_xp}</p>
          </div>
        </div>
        {"<div class='mt-4'><div class='bg-white bg-opacity-20 rounded-full h-3'><div class='bg-white h-3 rounded-full' style='width: " + str(progress_percentage) + "%'></div></div><p class='text-sm mt-1'>" + str(xp_in_current_tier) + " / " + str(next_tier_xp) + " XP to next tier</p></div>" if current_tier < len(TRACK_DATA) else ""}
      </div>
      
      <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 transition-colors">
        <h3 class="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Track Progress</h3>
        <div class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-100 dark:bg-gray-700">
                <th class="px-4 py-2 text-left text-gray-900 dark:text-white">Tier</th>
                <th class="px-4 py-2 text-center text-gray-900 dark:text-white">Status</th>
                <th class="px-4 py-2 text-left text-gray-900 dark:text-white">Free Track</th>
                <th class="px-4 py-2 text-left text-gray-900 dark:text-white">Elite Track {'✅' if is_elite else '❌'}</th>
              </tr>
            </thead>
            <tbody>
              {track_html}
            </tbody>
          </table>
        </div>
      </div>
      
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
          <h4 class="font-semibold text-gray-800 dark:text-white">💰 Mora Boost</h4>
          <p class="text-2xl font-bold text-green-600 dark:text-green-400">+{stats.get('mora_boost', 0)}%</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
          <h4 class="font-semibold text-gray-800 dark:text-white">📦 Chest Upgrades</h4>
          <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.get('chest_upgrades', 4)}</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
          <h4 class="font-semibold text-gray-800 dark:text-white">🎁 Gift Tax</h4>
          <p class="text-2xl font-bold text-red-600 dark:text-red-400">{stats.get('gift_tax', 'Not unlocked')}{'%' if stats.get('gift_tax', -1) != -1 else ''}</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
          <h4 class="font-semibold text-gray-800 dark:text-white">🧲 Minigame Summons</h4>
          <p class="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{stats.get('minigame_summons', 0)}</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
          <h4 class="font-semibold text-gray-800 dark:text-white">🎨 Custom Embed Color</h4>
          <p class="text-2xl font-bold text-pink-600 dark:text-pink-400">{color_status}</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 transition-colors">
          <h4 class="font-semibold text-gray-800 dark:text-white">🎖️ Prestige</h4>
          <p class="text-2xl font-bold text-purple-600 dark:text-purple-400">{prestige}</p>
        </div>
      </div>
    </div>
    """
    
    return {"content": content}

@profile.route("/profile/<guild_id>/quests")
def profile_quests(guild_id):
    """Get quests tab content"""
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401
    
    user_id = session['user_id']
    
    # Get quest data using the same structure as mora.py
    ref = db.reference(f"/Global User Quests/{user_id}/{guild_id}")
    quest_data = ref.get() or {}
    
    quest_html = ""

    for duration in ["daily", "weekly", "monthly"]:
        dur_data = quest_data.get(duration, {})
        quests = dur_data.get("quests", {})
        completed = dur_data.get("completed", {})
        end_time = dur_data.get("end_time", 0)
        
        if not quests:
            continue
            
        # Get XP rewards from imported constants
        xp_reward = QUEST_XP_REWARDS.get(duration, 50) if QUEST_XP_REWARDS else 50
        bonus_xp = QUEST_BONUS_XP.get(duration, 100) if QUEST_BONUS_XP else 100

        def format_time(seconds):
            """Format time in seconds to a human-readable string."""
            if seconds < 0:
                return "Expired"
            final_string = "Resets in "
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            if days > 0:
                final_string += f"{int(days)} days "
            if hours > 0:
                final_string += f"{int(hours)} hrs "
            final_string += f"{int(minutes)} mins"
            return final_string

        reset_time = format_time(end_time - time.time())

        quest_html += f"""
        <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 mb-4 transition-colors">
          <h3 class="text-lg font-semibold mb-4 capitalize text-gray-900 dark:text-white">{duration} Quests - {xp_reward} XP each</h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">{reset_time}</p>
          <div class="space-y-3">
        """
        
        for q_type, data in quests.items():
            if isinstance(data, dict):
                current = data.get('current', 0)
                goal = data.get('goal', 1)
                
                # Get description from imported constants
                description = QUEST_DESCRIPTIONS.get(q_type, q_type) if QUEST_DESCRIPTIONS else f"Quest: {q_type}"
                
                is_completed = q_type in completed
                progress_percentage = min((current / goal) * 100, 100) if goal > 0 else 100
                status_color = "text-green-600 dark:text-green-400" if is_completed else "text-blue-600 dark:text-blue-400"
                status_text = "✅ Completed" if is_completed else f"{current}/{goal}"
                
                quest_html += f"""
                <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50 transition-colors">
                  <div class="flex justify-between items-start mb-2">
                    <p class="font-medium text-gray-900 dark:text-white">{description}</p>
                    <span class="{status_color} text-sm font-semibold">{status_text}</span>
                  </div>
                  <div class="bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                    <div class="bg-blue-500 dark:bg-blue-400 h-2 rounded-full" style="width: {progress_percentage}%"></div>
                  </div>
                </div>
                """
        
        # Show bonus status
        if dur_data.get("bonus_awarded"):
            quest_html += f"""
            <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-lg p-3 mt-4 transition-colors">
              <p class="text-green-700 dark:text-green-300 text-sm font-medium">✅ {bonus_xp} XP bonus already claimed!</p>
            </div>
            """
        else:
            quest_html += f"""
            <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-3 mt-4 transition-colors">
              <p class="text-blue-700 dark:text-blue-300 text-sm font-medium">🎯 Complete all for +{bonus_xp} XP bonus!</p>
            </div>
            """
        
        quest_html += "</div></div>"
    
    if not quest_html:
        quest_html = """
        <div class="text-center py-8">
          <p class="text-gray-500 dark:text-gray-400">No quests available. Check back later!</p>
        </div>
        """
    
    content = f"""
    <div class="space-y-6">
      {quest_html}
    </div>
    """
    
    return {"content": content}

@profile.route("/profile/<guild_id>/dailygame")
def profile_dailygame(guild_id):
    """Get daily game tab content"""
    if "discord_token" not in session:
        return {"error": "Not authenticated"}, 401
    
    user_id = session['user_id']
    
    try:
        # Get user's daily game status for this guild
        status = get_daily_games_status(user_id, guild_id)
        
        game_id = status.get("daily_game_id")
        if not game_id:
            return {"content": '<div class="text-center py-8"><p class="text-gray-500 dark:text-gray-400">No game assigned for today. Please refresh the page.</p></div>'}
        
        game_config = DAILY_GAMES[game_id]
        game_completed = status.get("game_completed", False)
        
        if game_completed:
            # Show completed game results
            game_success = status.get("game_success", False)
            mora_earned = status.get("mora_earned", 0)
            
            if game_success:
                result_class = "bg-green-100 dark:bg-green-900/20 border-green-300 dark:border-green-700"
                result_text = f"✅ Completed! You earned {mora_earned} Mora and 1 minigame summon!"
            else:
                result_class = "bg-red-100 dark:bg-red-900/20 border-red-300 dark:border-red-700"
                result_text = "❌ Game failed. Better luck tomorrow!"
            
            content = f"""
            <div class="space-y-6">
              <div class="bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg p-6 text-white text-center">
                <h3 class="text-2xl font-bold mb-2">🎮 Daily Web Game</h3>
                <p class="text-purple-100">One random game per day. Resets at midnight UTC (just like daily chests!)</p>
              </div>
              
              <div class="border-2 rounded-lg p-6 transition-colors {result_class}">
                <div class="text-center">
                  <div class="text-6xl mb-4">{game_config['icon']}</div>
                  <h4 class="text-2xl font-bold mb-2 text-gray-900 dark:text-white">{game_config['name']}</h4>
                  <p class="text-gray-600 dark:text-gray-400 mb-4">{game_config['description']}</p>
                  <p class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-4">{result_text}</p>
                  <p class="text-sm text-gray-500 dark:text-gray-400">Come back tomorrow for a new game!</p>
                </div>
              </div>
              
              <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <h4 class="font-bold mb-4 text-gray-900 dark:text-white">📊 Your Daily Game Stats (This Server)</h4>
                <div class="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">{status.get('total_games_played', 0)}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">Games Played</p>
                  </div>
                  <div>
                    <p class="text-2xl font-bold text-green-600 dark:text-green-400">{status.get('total_mora_earned', 0):,}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">Mora Earned</p>
                  </div>
                  <div>
                    <p class="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{status.get('total_summons_earned', 0)}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">Summons Earned</p>
                  </div>
                </div>
              </div>
            </div>
            """
        else:
            # Show playable game
            content = f"""
            <div class="space-y-6">
              <div class="bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg p-6 text-white text-center">
                <h3 class="text-2xl font-bold mb-2">🎮 Daily Web Game</h3>
                <p class="text-purple-100">One random game per day. Resets at midnight UTC (just like daily chests!)</p>
              </div>
              
              <div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4 mb-4">
                <h4 class="font-bold text-yellow-800 dark:text-yellow-200 mb-2">📋 Important Notes:</h4>
                <ul class="text-sm text-yellow-700 dark:text-yellow-300 space-y-1">
                  <li>• Mora earned from web games is <strong>not affected</strong> by your guild Mora boost</li>
                  <li>• Web game activity <strong>does not contribute</strong> to guild quest progressions</li>
                  <li>• In typing-based web games, answers will <strong>auto-submit</strong> when time runs out, so don't worry about clicking Submit.</li>
                </ul>
              </div>
              
              <div class="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 text-center">
                <div class="text-6xl mb-4">{game_config['icon']}</div>
                <h4 class="text-2xl font-bold mb-2 text-gray-900 dark:text-white">{game_config['name']}</h4>
                <p class="text-gray-600 dark:text-gray-400 mb-4">{game_config['description']}</p>
                <div class="bg-gradient-to-r from-yellow-400 to-orange-500 rounded-lg p-4 mb-6 text-white">
                  <p class="font-bold">🎁 Reward: {game_config['reward']} Mora + 1 Minigame Summon</p>
                  <p class="text-sm opacity-90">Time Limit: {game_config['time_limit']} seconds</p>
                </div>
                <button onclick="openGame('{game_id}')" class="px-8 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-bold text-xl">
                  🎮 Play Now!
                </button>
              </div>
              
              <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <h4 class="font-bold mb-4 text-gray-900 dark:text-white">📊 Your Daily Game Stats (This Server)</h4>
                <div class="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">{status.get('total_games_played', 0)}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">Games Played</p>
                  </div>
                  <div>
                    <p class="text-2xl font-bold text-green-600 dark:text-green-400">{status.get('total_mora_earned', 0):,}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">Mora Earned</p>
                  </div>
                  <div>
                    <p class="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{status.get('total_summons_earned', 0)}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">Summons Earned</p>
                  </div>
                </div>
              </div>
            </div>
            """
        
        return {"content": content}
        
    except Exception as e:
        print(f"Error loading daily game: {e}")
        return {"content": '<div class="text-center py-8"><p class="text-red-500 dark:text-red-400">Failed to load daily game</p></div>'}


# Daily Games API Routes

# Daily Games API Routes (removed - now handled per-guild)

@profile.route("/api/daily-games/<guild_id>/<game_id>/play")
def api_daily_game_play_guild(guild_id, game_id):
    """API endpoint to start playing a daily game for a specific guild"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = session['user_id']
    
    # Get today's assigned game for this guild
    status = get_daily_games_status(user_id, guild_id)
    assigned_game_id = status.get("daily_game_id")
    
    # Verify this is the correct game for today
    if game_id != assigned_game_id:
        return jsonify({"error": "This is not today's assigned game for this server!"}), 400
    
    if game_id not in DAILY_GAMES:
        return jsonify({"error": "Invalid game"}), 400
    
    game_config = DAILY_GAMES[game_id]
    
    # Check if user can play this game
    if not can_play_game(user_id, guild_id):
        return jsonify({"error": "You've already played today's game!"}), 400
    
    # Generate game data based on game type
    game_data = {}
    if game_id == "memory":
        game_data = generate_memory_game()
    elif game_id == "math":
        game_data = generate_math_game()
    elif game_id == "hangman":
        game_data = generate_hangman_game()
    elif game_id == "shapes":
        game_data = generate_shapes_game()
    elif game_id == "typing":
        game_data = generate_typing_game()
    elif game_id == "coinflip":
        game_data = {"result": random.choice(["heads", "tails"])}
    elif game_id == "unscramble":
        word = random.choice(UNSCRAMBLE_WORDS)
        scrambled = list(word)
        random.shuffle(scrambled)
        game_data = {"word": word, "scrambled": "".join(scrambled)}
    
    # Store game data in session for verification
    session[f"game_data_{guild_id}_{game_id}"] = game_data
    
    # Generate game HTML based on game type
    html_content = generate_game_html_guild(game_id, game_config, game_data, guild_id)
    
    return jsonify({
        "title": game_config["name"],
        "html": html_content
    })

@profile.route("/api/daily-games/<guild_id>/<game_id>/submit", methods=["POST"])
def api_daily_game_submit_guild(guild_id, game_id):
    """API endpoint to submit game answer for a specific guild"""
    if "discord_token" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = session['user_id']
    
    # Get today's assigned game for this guild
    status = get_daily_games_status(user_id, guild_id)
    assigned_game_id = status.get("daily_game_id")
    
    # Verify this is the correct game for today
    if game_id != assigned_game_id:
        return jsonify({"error": "This is not today's assigned game for this server!"}), 400
    
    if game_id not in DAILY_GAMES:
        return jsonify({"error": "Invalid game"}), 400
    
    # Check if user can play this game
    if not can_play_game(user_id, guild_id):
        return jsonify({"error": "You've already played today's game!"}), 400
    
    # Get stored game data
    game_data = session.get(f"game_data_{guild_id}_{game_id}")
    if not game_data:
        return jsonify({"error": "Game session expired"}), 400
    
    # Get user's answer
    data = request.get_json()
    user_answer = data.get("answer")
    
    # Check answer based on game type
    correct = False
    if game_id == "memory":
        correct = user_answer == game_data["answer_position"]
    elif game_id == "math":
        correct = user_answer == str(game_data["answer"])
    elif game_id == "hangman":
        correct = user_answer.upper() == game_data["word"]
    elif game_id == "coinflip":
        user_choice = data.get("choice")
        correct = user_choice == game_data["result"]
    elif game_id == "unscramble":
        correct = user_answer.upper() == game_data["word"]
    elif game_id == "shapes":
        correct = user_answer == str(game_data["correct_count"])
    elif game_id == "typing":
        correct = user_answer == game_data["phrase"]
    
    # Calculate rewards
    game_config = DAILY_GAMES[game_id]
    mora_earned = game_config["reward"] if correct else 0
    
    # Record completion
    record_game_completion(user_id, guild_id, correct, mora_earned)
    
    # Clean up session
    session.pop(f"game_data_{guild_id}_{game_id}", None)
    
    # Return result
    if correct:
        return jsonify({
            "success": True,
            "message": f"🎉 Congratulations! You earned {mora_earned} Mora and 1 minigame summon for this server!\n\n📝 Note: This Mora is not affected by guild boosts and doesn't count toward quest progress.",
            "mora_earned": mora_earned
        })
    else:
        return jsonify({
            "success": False,
            "message": "Failed! Better luck next time! Try again tomorrow for a new random game.",
            "mora_earned": 0
        })

def generate_game_html_guild(game_id, game_config, game_data, guild_id):
    """Generate HTML for specific game types with guild-specific endpoints"""
    
    if game_id == "memory":
        emojis_html = ""
        for i, emoji in enumerate(game_data["emojis"]):
            emojis_html += f'<div id="emoji-{i}" class="text-4xl p-4 border rounded bg-gray-100 dark:bg-gray-700">{emoji}</div>'
        
        return f"""
        <div class="text-center">
          <div id="instructions" class="mb-4 text-gray-700 dark:text-gray-300">
            <p class="text-lg font-bold mb-2">📝 Instructions:</p>
            <p>Study the positions of these 5 emojis for 10 seconds. You'll need to remember their locations!</p>
          </div>
          
          <div id="study-timer" class="text-lg font-bold text-blue-600 mb-4">Study time remaining: 10s</div>
          
          <div id="emoji-grid" class="grid grid-cols-5 gap-2 mb-6 max-w-md mx-auto">
            {emojis_html}
          </div>
          
          <div id="question-section" class="hidden">
            <p class="mb-4 font-bold text-lg">Which position was the {game_data['question_emoji']} in?</p>
            <div class="flex justify-center gap-2 mb-4">
              <button onclick="submitMemoryAnswer(1)" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">1</button>
              <button onclick="submitMemoryAnswer(2)" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">2</button>
              <button onclick="submitMemoryAnswer(3)" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">3</button>
              <button onclick="submitMemoryAnswer(4)" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">4</button>
              <button onclick="submitMemoryAnswer(5)" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">5</button>
            </div>
            <div id="memory-timer" class="text-lg font-bold text-red-600">Time to answer: 10s</div>
          </div>
          
        </div>
        <script>
          let gameActive = false;
          let answerTimer;
          let studyTimer;
          
          // Start study countdown timer immediately
          let studyTimeLeft = 10;
          studyTimer = setInterval(() => {{
            studyTimeLeft--;
            document.getElementById('study-timer').textContent = 'Study time remaining: ' + studyTimeLeft + 's';
            if (studyTimeLeft <= 0) {{
              clearInterval(studyTimer);
            }}
          }}, 1000);
          
          // Show emojis for 10 seconds
          setTimeout(() => {{
            // Clear the study timer and hide study timer and emojis, show question
            clearInterval(studyTimer);
            document.getElementById('study-timer').style.display = 'none';
            document.getElementById('emoji-grid').style.visibility = 'hidden';
            document.getElementById('emoji-grid').style.display = 'none';
            document.getElementById('instructions').innerHTML = '<p class="text-lg font-bold text-red-600">Now answer the question!</p>';
            document.getElementById('question-section').classList.remove('hidden');
            gameActive = true;
            
            // Start 10-second answer timer
            let timeLeft = 10;
            answerTimer = setInterval(() => {{
              timeLeft--;
              document.getElementById('memory-timer').textContent = 'Time to answer: ' + timeLeft + 's';
              if (timeLeft <= 0) {{
                clearInterval(answerTimer);
                if (gameActive) {{
                  submitMemoryAnswer(-1);
                }}
              }}
            }}, 1000);
          }}, 10000);
          
          window.submitMemoryAnswer = function(answer) {{
            if (!gameActive) return;
            gameActive = false;
            clearInterval(answerTimer);
            clearInterval(studyTimer);
            
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{answer: answer}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }}
        </script>
        """
    
    elif game_id == "math":
        return f"""
        <div class="text-center">
          <p class="mb-6 text-gray-700 dark:text-gray-300">Solve this math problem:</p>
          <div class="text-6xl font-bold mb-6 text-blue-600">{game_data['num1']} + {game_data['num2']} = ?</div>
          <input type="number" id="math-answer" class="px-4 py-2 border rounded text-center text-2xl w-32 text-black" placeholder="?">
          <button onclick="submitMathAnswer()" class="ml-4 px-6 py-2 bg-green-500 text-white rounded hover:bg-green-600">Submit</button>
          <div id="timer" class="mt-4 text-lg font-bold text-red-600">Time: {game_config['time_limit']}s</div>
        </div>
        <script>
          let timeLeft = {game_config['time_limit']};
          const timer = setInterval(() => {{
            timeLeft--;
            document.getElementById('timer').textContent = 'Time: ' + timeLeft + 's';
            if (timeLeft <= 0) {{
              clearInterval(timer);
              alert('Time up! We will submit your answer now. Click OK to continue.');
              submitMathAnswer();
            }}
          }}, 1000);
          
          document.getElementById('math-answer').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') submitMathAnswer();
          }});
          
          window.submitMathAnswer = function() {{
            clearInterval(timer);
            const answer = document.getElementById('math-answer').value;
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{answer: answer}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }}
        </script>
        """
    
    elif game_id == "hangman":
        return f"""
        <div class="text-center">
          <p class="mb-4 text-gray-700 dark:text-gray-300">Guess the {game_data['length']}-letter word:</p>
          <div class="text-4xl font-mono mb-6 tracking-widest" id="word-display">{game_data['display']}</div>
          <div class="mb-4">
            <input type="text" id="hangman-guess" maxlength="1" class="px-4 py-2 border rounded text-center text-2xl w-16 text-black" placeholder="?">
            <button onclick="makeGuess()" class="ml-4 px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">Guess Letter</button>
          </div>
          <div class="mb-4">
            <input type="text" id="hangman-word" class="px-4 py-2 border rounded text-center text-black" placeholder="Full word guess">
            <button onclick="guessWord()" class="ml-4 px-6 py-2 bg-green-500 text-white rounded hover:bg-green-600">Guess Word</button>
          </div>
          <div id="guesses-left" class="text-lg font-bold">Guesses left: 7</div>
          <div id="timer" class="text-lg font-bold text-red-600">Time per guess: {game_config['time_limit']}s</div>
          <div id="wrong-letters" class="mt-4 text-red-600"></div>
        </div>
        <script>
          let word = '{game_data["word"]}';
          let display = '{game_data["display"]}';
          let guessesLeft = 7;
          let wrongLetters = [];
          let timeLeft = {game_config['time_limit']};
          let timer;
          
          function startTimer() {{
            timer = setInterval(() => {{
              timeLeft--;
              document.getElementById('timer').textContent = 'Time per guess: ' + timeLeft + 's';
              if (timeLeft <= 0) {{
                clearInterval(timer);
                alert('Time up for this guess! You just lost a guess.');
                guessesLeft--;
                updateDisplay();
                if (guessesLeft > 0) {{
                  timeLeft = {game_config['time_limit']};
                  startTimer();
                }} else {{
                  endGame(false);
                }}
              }}
            }}, 1000);
          }}
          
          startTimer();
          
          function updateDisplay() {{
            document.getElementById('word-display').textContent = display;
            document.getElementById('guesses-left').textContent = 'Guesses left: ' + guessesLeft;
            document.getElementById('wrong-letters').textContent = 'Wrong letters: ' + wrongLetters.join(', ');
          }}
          
          window.makeGuess = function() {{
            const letter = document.getElementById('hangman-guess').value.toUpperCase();
            if (!letter) return;
            
            // Check if letter already guessed
            if (wrongLetters.includes(letter) || display.includes(letter)) {{
              alert('You already guessed that letter!');
              document.getElementById('hangman-guess').value = '';
              return;
            }}
            
            clearInterval(timer);
            timeLeft = {game_config['time_limit']};
            
            if (word.includes(letter)) {{
              let newDisplay = '';
              for (let i = 0; i < word.length; i++) {{
                if (word[i] === letter) {{
                  newDisplay += letter;
                }} else {{
                  newDisplay += display[i];
                }}
              }}
              display = newDisplay;
              if (display === word) {{
                endGame(true);
                return;
              }}
            }} else {{
              wrongLetters.push(letter);
              guessesLeft--;
            }}
            
            document.getElementById('hangman-guess').value = '';
            updateDisplay();
            
            if (guessesLeft <= 0) {{
              endGame(false);
            }} else {{
              startTimer();
            }}
          }}
          
          window.guessWord = function() {{
            clearInterval(timer);
            const word_guess = document.getElementById('hangman-word').value.toUpperCase();
            endGame(word_guess === word);
          }}
          
          function endGame(won) {{
            clearInterval(timer);
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{answer: won ? word : 'WRONG'}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message + (won ? '' : ' The word was: ' + word));
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }}
          
          document.getElementById('hangman-guess').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') makeGuess();
          }});
          
          document.getElementById('hangman-word').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') guessWord();
          }});
        </script>
        """
    
    elif game_id == "coinflip":
        return f"""
        <div class="text-center">
          <p class="mb-6 text-gray-700 dark:text-gray-300">Choose heads or tails - 50/50 chance! One will grant you rewards while the other grants you nothing.</p>
          <div class="text-8xl mb-6">🪙</div>
          <div class="mb-6">
            <button onclick="flipCoin('heads')" class="px-8 py-4 bg-yellow-500 text-white rounded-lg text-xl font-bold hover:bg-yellow-600 mr-4">HEADS</button>
            <button onclick="flipCoin('tails')" class="px-8 py-4 bg-yellow-600 text-white rounded-lg text-xl font-bold hover:bg-yellow-700">TAILS</button>
          </div>
          <div id="timer" class="text-lg font-bold text-red-600">Time: {game_config['time_limit']}s</div>
        </div>
        <script>
          let timeLeft = {game_config['time_limit']};
          const timer = setInterval(() => {{
            timeLeft--;
            document.getElementById('timer').textContent = 'Time: ' + timeLeft + 's';
            if (timeLeft <= 0) {{
              clearInterval(timer);
              alert('Time up! We will flip the coin for you... it landed on heads. Let\\'s see if you are lucky!');
              flipCoin('heads'); // Default choice
            }}
          }}, 1000);
          
          window.flipCoin = function(choice) {{
            clearInterval(timer);
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{choice: choice}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }};
        </script>
        """
    
    elif game_id == "unscramble":
        return f"""
        <div class="text-center">
          <p class="mb-4 text-gray-700 dark:text-gray-300">Unscramble this word:</p>
          <div class="text-4xl font-bold mb-6 tracking-widest text-blue-600">{game_data['scrambled']}</div>
          <input type="text" id="unscramble-answer" class="px-4 py-2 border rounded text-center text-xl text-black" placeholder="Your answer">
          <button onclick="submitUnscramble()" class="ml-4 px-6 py-2 bg-green-500 text-white rounded hover:bg-green-600">Submit</button>
          <div id="timer" class="mt-4 text-lg font-bold text-red-600">Time: {game_config['time_limit']}s</div>
        </div>
        <script>
          let timeLeft = {game_config['time_limit']};
          const timer = setInterval(() => {{
            timeLeft--;
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            document.getElementById('timer').textContent = 'Time: ' + minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
            if (timeLeft <= 0) {{
              clearInterval(timer);
              alert('Time up! We will submit your answer now. Click OK to continue.');
              submitUnscramble();
            }}
          }}, 1000);
          
          document.getElementById('unscramble-answer').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') submitUnscramble();
          }});
          
          window.submitUnscramble = function() {{
            clearInterval(timer);
            const answer = document.getElementById('unscramble-answer').value;
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{answer: answer}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }}
        </script>
        """
    
    elif game_id == "shapes":
        shapes_html = ""
        for shape in game_data["shapes"]:
            shapes_html += f'<span class="text-2xl">{shape}</span>'
        
        return f"""
        <div class="text-center">
          <p class="mb-4 text-gray-700 dark:text-gray-300">Count how many <span class="text-3xl">{game_data['target_shape']}</span> you see:</p>
          <div class="border-2 border-gray-300 rounded-lg p-4 mb-6 max-w-md mx-auto bg-gray-50 dark:bg-gray-700" style="line-height: 1.2;">
            {shapes_html}
          </div>
          <input type="number" id="shapes-answer" class="px-4 py-2 border rounded text-center text-2xl w-24 text-black" placeholder="?">
          <button onclick="submitShapes()" class="ml-4 px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">Submit</button>
          <div id="timer" class="mt-4 text-lg font-bold text-red-600">Time: {game_config['time_limit']}s</div>
        </div>
        <script>
          let timeLeft = {game_config['time_limit']};
          let timer = setInterval(() => {{
            timeLeft--;
            document.getElementById('timer').textContent = 'Time: ' + timeLeft + 's';
            if (timeLeft <= 0) {{
              clearInterval(timer);
              alert('Time up! We will submit your answer now. Click OK to continue.');
              submitShapes();
            }}
          }}, 1000);
          
          document.getElementById('shapes-answer').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') submitShapes();
          }});
          
          window.submitShapes = function() {{
            clearInterval(timer);
            const answer = document.getElementById('shapes-answer').value;
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{answer: answer}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }}
        </script>
        """
    
    elif game_id == "typing":
        return f"""
        <div class="text-center">
          <p class="mb-4 text-gray-700 dark:text-gray-300">Type this phrase exactly:</p>
          <div class="bg-gray-100 dark:bg-gray-700 p-4 rounded-lg mb-6 font-mono text-lg">
            {game_data['phrase']}
          </div>
          <textarea id="typing-answer" class="w-full px-4 py-2 border rounded font-mono text-black" rows="3" placeholder="Type the phrase exactly here..."></textarea>
          <button onclick="submitTyping()" class="mt-4 px-6 py-2 bg-green-500 text-white rounded hover:bg-green-600">Submit</button>
          <div id="timer" class="mt-4 text-lg font-bold text-red-600">Time: {game_config['time_limit']}s</div>
        </div>
        <script>
          let timeLeft = {game_config['time_limit']};
          let timer = setInterval(() => {{
            timeLeft--;
            document.getElementById('timer').textContent = 'Time: ' + timeLeft + 's';
            if (timeLeft <= 0) {{
              clearInterval(timer);
              alert('Time up! We will submit your answer now. Click OK to continue.');
              submitTyping();
            }}
          }}, 1000);
          
          window.submitTyping = function() {{
            clearInterval(timer);
            const answer = document.getElementById('typing-answer').value;
            fetch('/api/daily-games/{guild_id}/{game_id}/submit', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{answer: answer}})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
              document.getElementById('game-modal').classList.add('hidden');
              document.body.style.overflow = '';
              location.reload();
            }});
          }}
        </script>
        """
    
    return "<p>Game not implemented yet</p>"


# PayPal Payment Routes

@profile.route("/payment/success")
def payment_success():
    """Payment success page"""
    if "discord_token" not in session or "user_id" not in session:
        return redirect("/login")
    
    # Get guild_id from query params
    guild_id = request.args.get('guild_id')
    if not guild_id:
        return "Invalid request - missing guild_id", 400
    
    user_id = session["user_id"]
    
    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Successful - Fischl Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                theme: {{
                    extend: {{
                        colors: {{
                            primary: '#6366f1',
                            secondary: '#ec4899'
                        }}
                    }}
                }}
            }}
        </script>
    </head>
    <body class="bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900 min-h-screen flex items-center justify-center">
        <div class="bg-white/10 backdrop-blur-lg rounded-xl shadow-2xl p-8 max-w-md w-full mx-4 text-center">
            <div class="text-6xl mb-4">🎉</div>
            <h1 class="text-3xl font-bold text-white mb-4">Elite Track Activated!</h1>
            <p class="text-indigo-100 mb-6">Thank you for your purchase! Your Elite Track has been activated and you should receive a Discord notification shortly.</p>
            <p class="text-sm text-indigo-200 mb-6">Elite rewards from previous tiers will be automatically granted in the next 30 seconds.</p>
            <div class="space-y-3">
                <a href="/profile/{guild_id}" class="block w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg transition">
                    Back to Guild Inventory
                </a>
                <p style="color: #a1a1aa;">You will be redirected automatically in <span id="redirect-timer">30</span> seconds...</p>
            </div>
        </div>
        <script>
            // Auto redirect after 30 seconds
            setTimeout(function() {{
                window.location.href = '/profile/{guild_id}';
            }}, 30000);
            // Countdown timer
            let countdown = 30;
            const timerElement = document.getElementById('redirect-timer');
            setInterval(function() {{
                if (countdown > 0) {{
                    countdown--;
                    timerElement.textContent = countdown;
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    '''

@profile.route("/payment/activate", methods=["POST"])
def activate_payment():
    """Activate elite subscription after successful PayPal payment"""
    if "discord_token" not in session or "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))  # Ensure string type to avoid precision issues
        guild_id = str(data.get('guild_id'))
        order_id = data.get('order_id')
        session_user_id = str(session["user_id"])  # Ensure string type
        
        print(f"Payment activation request: user_id={user_id}, guild_id={guild_id}, order_id={order_id}")
        print(f"Session user_id: {session_user_id}")
        print(f"User ID comparison: request='{user_id}' vs session='{session_user_id}'")
        
        # Verify the user_id matches the session
        if user_id != session_user_id:
            print(f"User ID mismatch: request_id={user_id} != session_id={session_user_id}")
            print(f"Request ID length: {len(user_id)}, Session ID length: {len(session_user_id)}")
            return jsonify({"error": "User ID mismatch", "details": f"Request: {user_id}, Session: {session_user_id}"}), 403
        
        # Convert to integers for the activation function
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)
        
        # Activate elite subscription
        print(f"Activating elite subscription for user {user_id_int} in guild {guild_id_int}")
        success, message = activate_elite_subscription(user_id_int, guild_id_int, order_id)
        
        if success:
            # Log the successful payment
            print(f"Elite subscription activated successfully for user {user_id_int} in guild {guild_id_int}, order: {order_id}")
            return jsonify({"success": True, "message": message})
        else:
            print(f"Failed to activate elite subscription: {message}")
            return jsonify({"error": message}), 500
            
    except Exception as e:
        print(f"Error in payment activation: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

@profile.route("/payment/manual-activate", methods=["POST"])
def manual_activate_payment():
    """Manual activation for support purposes - requires special token"""
    try:
        data = request.get_json()
        support_token = data.get('support_token')
        user_id = str(data.get('user_id'))
        guild_id = str(data.get('guild_id'))
        order_id = data.get('order_id')
        
        # Simple security check - in production, use a proper secret
        if support_token != "support_manual_activation_2024":
            return jsonify({"error": "Invalid support token"}), 403
        
        print(f"Manual activation request: user_id={user_id}, guild_id={guild_id}, order_id={order_id}")
        
        # Convert to integers for the activation function
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)
        
        # Activate elite subscription
        success, message = activate_elite_subscription(user_id_int, guild_id_int, order_id)
        
        if success:
            print(f"Manual elite subscription activated for user {user_id_int} in guild {guild_id_int}, order: {order_id}")
            return jsonify({"success": True, "message": f"Manually activated subscription for order {order_id}"})
        else:
            print(f"Manual activation failed: {message}")
            return jsonify({"error": message}), 500
            
    except Exception as e:
        print(f"Error in manual payment activation: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

@profile.route("/payment/webhook", methods=["POST"])
def paypal_webhook():
    """Handle PayPal IPN (Instant Payment Notification) webhook"""
    try:
        # Get the raw POST data
        raw_data = request.get_data(as_text=True)
        
        # Parse form data
        form_data = request.form.to_dict()
        
        # Verify payment status
        payment_status = form_data.get('payment_status', '').lower()
        txn_type = form_data.get('txn_type', '').lower()
        
        # Only process completed payments
        if payment_status != 'completed':
            print(f"Payment not completed: {payment_status}")
            return "OK", 200
        
        # Extract payment information
        payer_email = form_data.get('payer_email', '')
        amount = form_data.get('mc_gross', '0')
        currency = form_data.get('mc_currency', 'USD')
        item_name = form_data.get('item_name', '')
        custom_data = form_data.get('custom', '')  # This should contain user_id-guild_id
        txn_id = form_data.get('txn_id', '')  # PayPal transaction ID
        
        print(f"PayPal webhook received: {form_data}")
        
        # Parse custom data (should be in format: user_id-guild_id)
        if not custom_data:
            print("No custom data found in PayPal webhook")
            return "OK", 200
        
        try:
            user_id, guild_id = custom_data.split('-', 1)
            user_id = int(user_id)
            guild_id = int(guild_id)
        except (ValueError, IndexError):
            print(f"Invalid custom data format: {custom_data}")
            return "OK", 200
        
        # Activate elite subscription with transaction ID
        success, message = activate_elite_subscription(user_id, guild_id, txn_id)
        
        if success:
            print(f"Elite subscription activated for user {user_id} in guild {guild_id}")
        else:
            print(f"Failed to activate elite subscription: {message}")
        
        return "OK", 200
        
    except Exception as e:
        print(f"Error processing PayPal webhook: {e}")
        return "Error", 500