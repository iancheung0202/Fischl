import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import requests
from app import expeditions
from config.settings import (
    API_BASE,
    BOT_TOKEN,
    CLIENT_ID,
    CLIENT_SECRET,
    ELITE_TRACK_PRICE,
    PAYPAL_CLIENT_ID,
    PROFILE_REDIRECT_URI,
)
from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)

from utils.firebase import save_user_to_firebase
from utils.minigames import (
    activate_elite_subscription,
    check_events_enabled,
    get_current_season,
    get_current_track,
    get_db_connection,
    is_elite_active,
)
from utils.request import requests_session

profile = Blueprint("profile", __name__)

# ---------- helpers ----------
_cache = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = fn()
    _cache[key] = (time.time(), value)
    return value


def bearer():
    return {"Authorization": f"Bearer {session['discord_token']}"}


def bot():
    return {"Authorization": f"Bot {BOT_TOKEN}"}


def user_guilds():
    def fetch():
        r = requests_session.get(f"{API_BASE}/users/@me/guilds", headers=bearer())
        return r.json() if r.status_code == 200 else []

    return cached(f"ug:{session['discord_token']}", 60, fetch)


def bot_guild_ids():
    def fetch():
        ids, after = set(), None
        while True:
            r = requests_session.get(
                f"{API_BASE}/users/@me/guilds",
                headers=bot(),
                params={"limit": 200, **({"after": after} if after else {})},
            )
            data = r.json() if r.status_code == 200 else []
            ids |= {g["id"] for g in data}
            if len(data) < 200:
                return ids
            after = data[-1]["id"]

    return cached("botguilds", 120, fetch)


def avatar_url(u):
    return (
        f"https://cdn.discordapp.com/avatars/{u['id']}/{u['avatar']}.png?size=128"
        if u.get("avatar")
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )


def session_user():
    if "user" not in session:  # sessions created before this update
        u = requests_session.get(f"{API_BASE}/users/@me", headers=bearer()).json()
        session["user"] = {
            "id": str(u["id"]),
            "username": u["username"],
            "avatar": avatar_url(u),
        }
    return session["user"]


def user_name(uid):
    def fetch():
        try:
            u = requests_session.get(f"{API_BASE}/users/{uid}", headers=bot()).json()
            return u.get("global_name") or u.get("username") or f"User {str(uid)[-4:]}"
        except Exception:
            return f"User {str(uid)[-4:]}"

    return cached(f"name:{uid}", 3600, fetch)


def guard(guild_id):
    """Returns (guild, error_response). Verifies login, membership and events enabled."""
    if "discord_token" not in session:
        return None, (jsonify(error="Not authenticated"), 401)
    guild = next((g for g in user_guilds() if g["id"] == guild_id), None)
    if not guild:
        return None, (jsonify(error="Realm not found."), 404)
    if not check_events_enabled(guild_id):
        return None, (jsonify(error="Events are not enabled in this realm."), 400)
    return guild, None


# ---------- pages (shells only: zero network calls, so they paint instantly) ----------
@profile.route("/profile")
def view_profile():
    code = request.args.get("code")
    if code:
        r = requests.post(
            f"{API_BASE}/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": PROFILE_REDIRECT_URI,
                "scope": "identify guilds",
            },
        )
        if r.status_code != 200:
            return f"Token exchange failed: {r.text}", 400
        token = r.json()["access_token"]
        user = requests.get(
            f"{API_BASE}/users/@me", headers={"Authorization": f"Bearer {token}"}
        ).json()
        save_user_to_firebase(user, token)
        session["discord_token"] = token
        session["user_id"] = str(user["id"])
        session["user"] = {
            "id": str(user["id"]),
            "username": user["username"],
            "avatar": avatar_url(user),
        }
        return redirect("/profile")
    return shell(None)


@profile.route("/profile/<guild_id>")
def profile_guild(guild_id):
    return shell(guild_id)


def shell(guild_id):
    if "discord_token" not in session:
        return redirect("/auth")
    boot = {
        "user": session_user(),
        "gid": guild_id,
        "paypal": PAYPAL_CLIENT_ID,
        "price": ELITE_TRACK_PRICE,
    }
    return render_template("profile.html", boot=boot)


@profile.route("/world/ja-jp.ttf")
def world_font():
    """The game font lives in the bot's assets/ folder; serve it from there instead of copying it."""
    root = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets"
    )
    return send_from_directory(os.path.normpath(root), "ja-jp.ttf", max_age=31536000)


# ---------- JSON API ----------
@profile.route("/api/profile/data")
def api_profile_data():
    if "discord_token" not in session:
        return jsonify(error="Not authenticated"), 401
    ug, bg = user_guilds(), bot_guild_ids()
    candidates = [g for g in ug if g["id"] in bg]
    with ThreadPoolExecutor(max_workers=8) as ex:
        flags = list(ex.map(lambda g: check_events_enabled(g["id"]), candidates))
    guilds = sorted(
        (g for g, ok in zip(candidates, flags) if ok), key=lambda g: g["name"].lower()
    )
    return jsonify(
        guilds=[
            {"id": g["id"], "name": g["name"], "icon": g.get("icon")} for g in guilds
        ]
    )


@profile.route("/api/profile/<guild_id>/state")
def api_state(guild_id):
    guild, err = guard(guild_id)
    if err:
        return err
    uid = session["user_id"]
    track, season, elite = (
        get_current_track(),
        get_current_season(),
        is_elite_active(uid, guild_id),
    )
    runs, board = expeditions.guild_runs(guild_id, uid), expeditions.leaderboard(
        guild_id
    )
    ids = {r["uid"] for r in runs} | {b["uid"] for b in board}
    with ThreadPoolExecutor(max_workers=8) as ex:
        names = dict(zip(ids, ex.map(user_name, ids)))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT xp FROM minigame_progression WHERE gid=%s AND uid=%s",
            (guild_id, uid),
        )
        row = cur.fetchone()
        xp = row[0] if row else 0
    finally:
        conn.close()
    tier = max([t["tier"] for t in track if xp >= t["cumulative_xp"]], default=0)
    prev = track[tier - 1]["cumulative_xp"] if tier else 0
    need = track[tier]["xp_req"] if tier < len(track) else 0
    return jsonify(
        guild={"id": guild["id"], "name": guild["name"], "icon": guild.get("icon")},
        season={"id": season["id"], "name": season["name"], "end_ts": season["end_ts"]},
        elite=elite,
        xp=xp,
        tier=tier,
        tier_xp=xp - prev,
        tier_need=need,
        tiers=[
            {
                "tier": t["tier"],
                "free": t["free"].split("|")[0].strip(),
                "elite": t["elite"].split("|")[0].strip(),
            }
            for t in track
        ],
        me=str(uid),
        roster=expeditions.roster(),
        rewards=expeditions.rewards(elite),
        runs=[{**r, "uid": str(r["uid"]), "name": names[r["uid"]]} for r in runs],
        board=[
            {"name": names[b["uid"]], "hours": b["hours"], "trips": b["trips"]}
            for b in board
        ],
    )


@profile.route("/api/profile/<guild_id>/dispatch", methods=["POST"])
def api_dispatch(guild_id):
    guild, err = guard(guild_id)
    if err:
        return err
    d = request.get_json(silent=True) or {}
    ok, msg = expeditions.dispatch(
        session["user_id"],
        guild_id,
        d.get("character"),
        int(d.get("hours") or 0),
        is_elite_active(session["user_id"], guild_id),
    )
    return jsonify(ok=True) if ok else (jsonify(error=msg), 400)


@profile.route("/api/profile/<guild_id>/claim", methods=["POST"])
def api_claim(guild_id):
    guild, err = guard(guild_id)
    if err:
        return err
    res = expeditions.claim(
        session["user_id"], guild_id, (request.get_json(silent=True) or {}).get("id", 0)
    )
    return jsonify(res) if res else (jsonify(error="Not ready yet."), 400)


# PayPal Payment Routes


@profile.route("/payment/success")
def payment_success():
    """Payment success page"""
    if "discord_token" not in session or "user_id" not in session:
        return redirect("/login")

    # Get guild_id from query params
    guild_id = request.args.get("guild_id")
    if not guild_id:
        return "Invalid request - missing guild_id", 400

    return f"""
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
                    Back to Track
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
    """


@profile.route("/payment/activate", methods=["POST"])
def activate_payment():
    """Activate elite subscription after successful PayPal payment"""
    if "discord_token" not in session or "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json()
        user_id = str(
            data.get("user_id")
        )  # Ensure string type to avoid precision issues
        guild_id = str(data.get("guild_id"))
        order_id = data.get("order_id")
        session_user_id = str(session["user_id"])  # Ensure string type

        print(
            f"Payment activation request: user_id={user_id}, guild_id={guild_id}, order_id={order_id}"
        )
        print(f"Session user_id: {session_user_id}")
        print(f"User ID comparison: request='{user_id}' vs session='{session_user_id}'")

        # Verify the user_id matches the session
        if user_id != session_user_id:
            print(
                f"User ID mismatch: request_id={user_id} != session_id={session_user_id}"
            )
            print(
                f"Request ID length: {len(user_id)}, Session ID length: {len(session_user_id)}"
            )
            return (
                jsonify(
                    {
                        "error": "User ID mismatch",
                        "details": f"Request: {user_id}, Session: {session_user_id}",
                    }
                ),
                403,
            )

        # Convert to integers for the activation function
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)

        # Activate elite subscription
        print(
            f"Activating elite subscription for user {user_id_int} in guild {guild_id_int}"
        )
        success, message = activate_elite_subscription(
            user_id_int, guild_id_int, order_id
        )

        if success:
            print(
                f"Elite subscription activated successfully for user {user_id_int} in guild {guild_id_int}, order: {order_id}"
            )
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
        support_token = data.get("support_token")
        user_id = str(data.get("user_id"))
        guild_id = str(data.get("guild_id"))
        order_id = data.get("order_id")

        # Simple security check - in production, use a proper secret
        if support_token != "support_manual_activation_2024":
            return jsonify({"error": "Invalid support token"}), 403

        print(
            f"Manual activation request: user_id={user_id}, guild_id={guild_id}, order_id={order_id}"
        )

        # Convert to integers for the activation function
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)

        # Activate elite subscription
        success, message = activate_elite_subscription(
            user_id_int, guild_id_int, order_id
        )

        if success:
            print(
                f"Manual elite subscription activated for user {user_id_int} in guild {guild_id_int}, order: {order_id}"
            )
            return jsonify(
                {
                    "success": True,
                    "message": f"Manually activated subscription for order {order_id}",
                }
            )
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
        # Parse form data
        form_data = request.form.to_dict()

        # Verify payment status
        payment_status = form_data.get("payment_status", "").lower()

        # Only process completed payments
        if payment_status != "completed":
            print(f"Payment not completed: {payment_status}")
            return "OK", 200

        custom_data = form_data.get(
            "custom", ""
        )  # This should contain user_id-guild_id
        txn_id = form_data.get("txn_id", "")  # PayPal transaction ID

        print(f"PayPal webhook received: {form_data}")

        # Parse custom data (should be in format: user_id-guild_id)
        if not custom_data:
            print("No custom data found in PayPal webhook")
            return "OK", 200

        try:
            user_id, guild_id = custom_data.split("-", 1)
            user_id = int(user_id)
            guild_id = int(guild_id)
        except (ValueError, IndexError):
            print(f"Invalid custom data format: {custom_data}")
            return "OK", 200

        # Activate elite subscription with transaction ID
        success, message = activate_elite_subscription(user_id, guild_id, txn_id)

        if success:
            print(
                f"Elite subscription activated for user {user_id} in guild {guild_id}"
            )
        else:
            print(f"Failed to activate elite subscription: {message}")

        return "OK", 200

    except Exception as e:
        print(f"Error processing PayPal webhook: {e}")
        return "Error", 500
