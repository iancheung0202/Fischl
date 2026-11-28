"""The profile pages of fischl.app: expeditions, the season pass and Elite Track payments."""

import hmac
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import config.settings as settings
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

from utils import paypal
from utils.minigames import (
    activate_elite_subscription,
    active_season,
    check_events_enabled,
    get_current_season,
    get_current_track,
    get_db_connection,
    is_elite_active,
    order_spent,
)
from utils.request import requests_session

profile = Blueprint("profile", __name__)

ORDER_ID = re.compile(r"[A-Za-z0-9]{1,64}")
SUPPORT_TOKEN = getattr(settings, "SUPPORT_TOKEN", "")

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets")
)
CACHE_LIMIT = 5000
cache = {}


def cached(key, ttl, fetch):
    """Gives the kept value under a key, fetching it again once it is older than ttl seconds."""
    now = time.time()
    hit = cache.get(key)
    if hit and now < hit[0]:
        return hit[1]
    if len(cache) >= CACHE_LIMIT:
        for old, (until, _) in list(cache.items()):
            if until <= now:
                cache.pop(old, None)
        while len(cache) >= CACHE_LIMIT:
            cache.pop(next(iter(cache)), None)
    value = fetch()
    cache[key] = (now + ttl, value)
    return value


def whole(value):
    """Gives a request value as a whole number, or 0 when it is not one."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def bearer():
    return {"Authorization": f"Bearer {session['discord_token']}"}


def bot():
    return {"Authorization": f"Bot {BOT_TOKEN}"}


def user_guilds():
    def fetch():
        r = requests_session.get(f"{API_BASE}/users/@me/guilds", headers=bearer())
        if r.status_code >= 500:
            raise RuntimeError(f"Discord answered {r.status_code}")
        return r.json() if r.status_code == 200 else []

    return cached(f"ug:{session['user_id']}", 60, fetch)


def bot_guild_ids():
    def fetch():
        ids, after = set(), None
        while True:
            r = requests_session.get(
                f"{API_BASE}/users/@me/guilds",
                headers=bot(),
                params={"limit": 200, **({"after": after} if after else {})},
            )
            if r.status_code >= 500:
                raise RuntimeError(f"Discord answered {r.status_code}")
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
        member = {
            "id": str(user["id"]),
            "username": user["username"],
            "avatar": avatar_url(user),
        }
        session.update(discord_token=token, user_id=member["id"], user=member)
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
    return send_from_directory(ASSETS, "ja-jp.ttf", max_age=31536000)


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
        whole(d.get("hours")),
        is_elite_active(session["user_id"], guild_id),
    )
    return jsonify(ok=True) if ok else (jsonify(error=msg), 400)


@profile.route("/api/profile/<guild_id>/claim", methods=["POST"])
def api_claim(guild_id):
    guild, err = guard(guild_id)
    if err:
        return err
    res = expeditions.claim(
        session["user_id"],
        guild_id,
        whole((request.get_json(silent=True) or {}).get("id")),
    )
    return jsonify(res) if res else (jsonify(error="Not ready yet."), 400)


@profile.route("/payment/success")
def payment_success():
    """Payment success page"""
    if "discord_token" not in session or "user_id" not in session:
        return redirect("/login")

    guild_id = request.args.get("guild_id")
    if not guild_id:
        return "Invalid request - missing guild_id", 400
    if not (guild_id.isascii() and guild_id.isdigit()):
        return "Invalid request - bad guild_id", 400
    return render_template("payment_success.html", guild_id=guild_id)


def activation(user_id, guild_id, order_id, done=None):
    """Turns the Elite Track on and gives the JSON answer of an activation request."""
    worked, message = activate_elite_subscription(int(user_id), int(guild_id), order_id)
    if not worked:
        print(f"Failed to activate elite subscription: {message}")
        return jsonify({"error": message}), 500
    return jsonify({"success": True, "message": done or message})


def payment_refused(user_id, guild_id, order_id):
    """Gives why an order may not turn the Elite Track on, or None when it may."""
    if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id):
        return "Missing order"
    if order_spent(order_id, user_id, guild_id):
        return "This order has already been used."
    if paypal.can_check_orders() and not paypal.order_paid_for(
        order_id, user_id, guild_id, active_season().start_ts
    ):
        return "Payment could not be verified."
    return None


@profile.route("/payment/activate", methods=["POST"])
def activate_payment():
    """Activate elite subscription after successful PayPal payment"""
    if "discord_token" not in session or "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        data = request.get_json()
        user_id, guild_id = str(data.get("user_id")), str(data.get("guild_id"))
        order_id = data.get("order_id")
        mine = str(session["user_id"])
        if user_id != mine:
            details = f"Request: {user_id}, Session: {mine}"
            return jsonify({"error": "User ID mismatch", "details": details}), 403
        refused = payment_refused(int(user_id), int(guild_id), order_id)
        if refused:
            print(f"Payment refused for user {user_id}, order {order_id}: {refused}")
            return jsonify({"error": refused}), 400
        return activation(user_id, guild_id, order_id)
    except Exception as error:
        print(f"Error in payment activation: {error}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@profile.route("/payment/manual-activate", methods=["POST"])
def manual_activate_payment():
    """Manual activation for support purposes - requires the support token from the settings"""
    try:
        data = request.get_json()
        given = str(data.get("support_token") or "")
        if not SUPPORT_TOKEN or not hmac.compare_digest(
            given.encode(), SUPPORT_TOKEN.encode()
        ):
            return jsonify({"error": "Invalid support token"}), 403
        order_id = data.get("order_id")
        return activation(
            data.get("user_id"),
            data.get("guild_id"),
            order_id,
            f"Manually activated subscription for order {order_id}",
        )
    except Exception as error:
        print(f"Error in manual payment activation: {error}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


def buyer(custom):
    """Gives the (user id, server id) a PayPal notification names, or None."""
    try:
        user_id, guild_id = custom.split("-", 1)
        return int(user_id), int(guild_id)
    except ValueError:
        return None


@profile.route("/payment/webhook", methods=["POST"])
def paypal_webhook():
    """Handle PayPal IPN (Instant Payment Notification) webhook"""
    try:
        body, form = request.get_data(), request.form.to_dict()
        if form.get("payment_status", "").lower() != "completed":
            return "OK", 200
        found = buyer(form.get("custom", ""))
        txn_id = form.get("txn_id", "")
        if not found or not txn_id:
            print("PayPal webhook without a buyer or transaction")
            return "OK", 200
        if order_spent(txn_id, *found) or not paypal.notification_is_real(body, form):
            print(f"PayPal webhook not verified: transaction {txn_id}")
            return "OK", 200
        worked, message = activate_elite_subscription(*found, txn_id)
        if not worked:
            print(f"Failed to activate elite subscription: {message}")
        return "OK", 200
    except Exception as error:
        print(f"Error processing PayPal webhook: {error}")
        return "Error", 500
