"""Expedition game logic (the web-only loop). No HTML in here."""

import ast
import os
import time

from utils.minigames import get_db_connection

MORA_PER_HOUR = 250
ELITE_MULT = 1.5
# Longer trips go to farther places, and pay better per hour than short ones.
RULES = {
    4: {"mora_mult": 1.0, "summons": 1},
    8: {"mora_mult": 1.25, "summons": 1},
    12: {"mora_mult": 1.6, "summons": 2},
}

_roster = None


def roster():
    """Every character from the bot's birthdayTexts.py, read with ast so the web layer needn't import discord."""
    global _roster
    if _roster is None:
        path = os.path.normpath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "..",
                "commands",
                "Birthday",
                "birthdayTexts.py",
            )
        )
        _roster = []
        try:
            for node in ast.parse(open(path, encoding="utf-8").read()).body:
                if (
                    isinstance(node, ast.Assign)
                    and getattr(node.targets[0], "id", "") == "characters_dict"
                ):
                    _roster = [
                        {"name": k, "icon": v["icon"]}
                        for k, v in ast.literal_eval(node.value).items()
                    ]
        except Exception as e:
            print(f"Could not load roster: {e}")
    return _roster


def mora_for(hours, elite):
    return int(
        hours * MORA_PER_HOUR * RULES[hours]["mora_mult"] * (ELITE_MULT if elite else 1)
    )


def rewards(elite):
    return {
        h: {"mora": mora_for(h, elite), "summons": r["summons"]}
        for h, r in RULES.items()
    }


_ready = False


def _run(fn):
    global _ready
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if not _ready:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS web_expeditions (
                id SERIAL PRIMARY KEY, uid BIGINT, gid BIGINT, slot INT, character TEXT, hours INT,
                started_at DOUBLE PRECISION, ends_at DOUBLE PRECISION, mora INT, summons INT, claimed BOOLEAN DEFAULT FALSE)"""
            )
            cur.execute(
                "ALTER TABLE web_expeditions ADD COLUMN IF NOT EXISTS notified BOOLEAN DEFAULT FALSE"
            )
            _ready = True
        out = fn(cur)
        conn.commit()
        return out
    finally:
        conn.close()


def guild_runs(gid, viewer):
    """Everyone currently out in this server, plus the viewer's own run even if it already returned."""

    def q(cur):
        cur.execute(
            "SELECT id, uid, character, hours, started_at, ends_at, mora, summons FROM web_expeditions "
            "WHERE gid=%s AND NOT claimed AND (ends_at > %s OR uid=%s) ORDER BY id",
            (int(gid), time.time(), int(viewer)),
        )
        return [
            dict(
                zip(
                    (
                        "id",
                        "uid",
                        "character",
                        "hours",
                        "started_at",
                        "ends_at",
                        "mora",
                        "summons",
                    ),
                    r,
                )
            )
            for r in cur.fetchall()
        ]

    return _run(q)


def leaderboard(gid):
    """Most hours spent on the road in this server (collected expeditions only)."""

    def q(cur):
        cur.execute(
            "SELECT uid, SUM(hours), COUNT(*) FROM web_expeditions WHERE gid=%s AND claimed GROUP BY uid ORDER BY 2 DESC LIMIT 10",
            (int(gid),),
        )
        return [
            {"uid": r[0], "hours": int(r[1]), "trips": r[2]} for r in cur.fetchall()
        ]

    return _run(q)


def dispatch(uid, gid, character, hours, elite):
    if hours not in RULES or character not in {c["name"] for c in roster()}:
        return None, "That isn't a valid expedition."

    def q(cur):
        cur.execute(
            "SELECT pg_advisory_xact_lock(%s)", (int(gid),)
        )  # two people can't grab the same character at once
        now = time.time()
        cur.execute(
            "SELECT ends_at FROM web_expeditions WHERE uid=%s AND gid=%s AND NOT claimed",
            (int(uid), int(gid)),
        )
        mine = cur.fetchone()
        if mine:
            return None, (
                "Collect your last expedition first."
                if mine[0] <= now
                else "You already have someone out."
            )
        cur.execute(
            "SELECT 1 FROM web_expeditions WHERE gid=%s AND character=%s AND NOT claimed AND ends_at > %s",
            (int(gid), character, now),
        )
        if cur.fetchone():
            return None, f"Someone else just sent {character} out."
        cur.execute(
            "INSERT INTO web_expeditions (uid,gid,slot,character,hours,started_at,ends_at,mora,summons) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                int(uid),
                int(gid),
                list(RULES).index(hours),
                character,
                hours,
                now,
                now + hours * 3600,
                mora_for(hours, elite),
                RULES[hours]["summons"],
            ),
        )
        return True, None

    return _run(q)


def claim(uid, gid, exp_id):
    def q(cur):
        cur.execute(
            "UPDATE web_expeditions SET claimed=TRUE WHERE id=%s AND uid=%s AND gid=%s AND NOT claimed AND ends_at<=%s RETURNING mora, summons",
            (int(exp_id), int(uid), int(gid), time.time()),
        )
        row = cur.fetchone()
        if not row:
            return None
        grant_rewards(cur, uid, gid, row[0], row[1])
        return {"mora": row[0], "summons": row[1]}

    return _run(q)


def grant_rewards(cur, uid, gid, mora, summons):
    """Mirrors the bot: mora is an event log in minigame_mora (cid 0 = web), summons live in minigame_progression."""
    uid, gid = int(uid), int(gid)
    cur.execute(
        """INSERT INTO minigame_mora (uid, gid, cid, timestamp, count) VALUES (%s,%s,0,%s,%s)
                   ON CONFLICT (gid, uid, cid, timestamp) DO UPDATE SET count = minigame_mora.count + EXCLUDED.count""",
        (uid, gid, int(time.time()), mora),
    )
    cur.execute(
        """INSERT INTO minigame_progression (gid, uid, kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten,
                   xp, prestige, bonus_tier, mora_boost, chest_upgrades, gift_tax, minigame_summons, shop_discount, domain_discount, express_daily_chests)
                   VALUES (%s,%s,0,0,0,0,0,0,0,0,4,NULL,0,0,0,FALSE) ON CONFLICT (gid, uid) DO NOTHING""",
        (gid, uid),
    )
    cur.execute(
        "UPDATE minigame_progression SET minigame_summons = minigame_summons + %s, updated_at = CURRENT_TIMESTAMP WHERE gid=%s AND uid=%s",
        (summons, gid, uid),
    )
