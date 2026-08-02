import datetime
import hashlib
import hmac
import threading
import time

from collections import OrderedDict, defaultdict
from discord.ext import commands
from flask import Flask, jsonify, request

from assets.secret import MSG_HISTORY_API_KEY

CHANNEL_ID = 1106664283250626671
RATE_LIMIT_PER_MINUTE = 60
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 100


class MessageHistoryAPICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.messages = OrderedDict()
        self.lock = threading.Lock()
        self.last_update = time.time()
        self.revision = 0
        self.backfill_complete = False
        self.rate_limits = {}
        self.rate_limit_lock = threading.Lock()
        self.app = Flask("msg_history_api")
        self.app.add_url_rule("/summary", "summary", self.handle_summary)
        self.app.add_url_rule("/messages", "messages", self.handle_messages)
        threading.Thread(target=self.run_server, daemon=True).start()
        self.bot.loop.create_task(self.backfill())

    def run_server(self):
        self.app.run(host="0.0.0.0", port=2030, use_reloader=False)

    async def backfill(self):
        await self.bot.wait_until_ready()
        try:
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(CHANNEL_ID)
            count = 0
            async for message in channel.history(limit=None):
                with self.lock:
                    self.insert(message)
                count += 1
            with self.lock:
                self.backfill_complete = True
        except Exception as e:
            print(f"#introduce-yourself channel messages backfill failed: {e}")

    def insert(self, message):
        self.messages[message.id] = self.serialize(message)
        self.messages.move_to_end(message.id, last=False)
        self.bump()

    def bump(self):
        self.revision += 1
        self.last_update = time.time()

    def etag(self):
        return hashlib.sha1(f"{self.revision}:{len(self.messages)}".encode()).hexdigest()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id != CHANNEL_ID:
            return
        with self.lock:
            self.insert(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.channel.id != CHANNEL_ID:
            return
        with self.lock:
            if after.id in self.messages:
                self.messages[after.id] = self.serialize(after)
                self.bump()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.channel.id != CHANNEL_ID:
            return
        with self.lock:
            if message.id in self.messages:
                del self.messages[message.id]
                self.bump()

    def serialize(self, message):
        author = message.author
        author_data = None
        if author is not None:
            author_data = {
                "id": str(author.id),
                "name": author.name,
                "global_name": getattr(author, "global_name", None),
                "display_name": getattr(author, "display_name", author.name),
                "bot": author.bot,
                "avatar_url": author.display_avatar.url if author.display_avatar else None
            }
        return {
            "id": str(message.id),
            "author": author_data,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None
        }

    def summary_payload(self):
        with self.lock:
            total = len(self.messages)
            if total:
                newest = next(iter(self.messages.values()))
                oldest = next(reversed(self.messages.values()))
                first_timestamp = oldest["timestamp"]
                last_timestamp = newest["timestamp"]
            else:
                first_timestamp = None
                last_timestamp = None
            daily = defaultdict(int)
            for msg in self.messages.values():
                daily[msg["timestamp"][:10]] += 1
            return {
                "channel_id": str(CHANNEL_ID),
                "total_messages": total,
                "first_message": first_timestamp,
                "last_message": last_timestamp,
                "messages_per_day": dict(sorted(daily.items())),
                "cache": {
                    "backfill_complete": self.backfill_complete,
                    "last_update": datetime.datetime.fromtimestamp(
                        self.last_update, tz=datetime.timezone.utc
                    ).isoformat(),
                    "revision": self.revision,
                },
            }

    def messages_payload(self, page, limit):
        with self.lock:
            items = list(self.messages.values())
        total = len(items)
        total_pages = max(1, (total + limit - 1) // limit) if total else 1
        page = max(1, min(page, total_pages))
        start = (page - 1) * limit
        return {
            "page": page,
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "next_page": page + 1 if page < total_pages else None,
            "prev_page": page - 1 if page > 1 else None,
            "messages": items[start : start + limit],
        }

    def client_ip(self):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"

    def check_auth(self):
        key = request.headers.get("X-API-Key", "")
        return bool(key) and hmac.compare_digest(key, MSG_HISTORY_API_KEY)

    def rate_limit_check(self, ip):
        now = time.monotonic()
        with self.rate_limit_lock:
            bucket = self.rate_limits.get(ip)
            if bucket is None:
                self.rate_limits[ip] = (RATE_LIMIT_PER_MINUTE - 1, now)
                return None
            tokens, last = bucket
            tokens = min(RATE_LIMIT_PER_MINUTE, tokens + (now - last))
            if tokens < 1:
                self.rate_limits[ip] = (tokens, now)
                return 1.0 - tokens
            self.rate_limits[ip] = (tokens - 1, now)
            return None

    def unauthorized(self):
        resp = jsonify({"error": "Unauthorized"})
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = "ApiKey"
        return resp

    def rate_limited(self, retry_after):
        resp = jsonify({"error": "Rate limit exceeded"})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(round(retry_after, 3))
        return resp

    def warming(self):
        resp = jsonify({"error": "Cache warming, full message history is still being fetched"})
        resp.status_code = 503
        resp.headers["Retry-After"] = "30"
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    def cached(self, data):
        etag = self.etag()
        if_match = request.headers.get("If-None-Match")
        if if_match and etag in [token.strip().strip('"') for token in if_match.split(",")]:
            resp = self.app.response_class(status=304)
        else:
            resp = jsonify(data)
            resp.setetag(etag)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    def handle_summary(self):
        if not self.check_auth():
            return self.unauthorized()
        retry_after = self.rate_limit_check(self.client_ip())
        if retry_after is not None:
            return self.rate_limited(retry_after)
        if not self.backfill_complete:
            return self.warming()
        return self.cached(self.summary_payload())

    def handle_messages(self):
        if not self.check_auth():
            return self.unauthorized()
        retry_after = self.rate_limit_check(self.client_ip())
        if retry_after is not None:
            return self.rate_limited(retry_after)
        if not self.backfill_complete:
            return self.warming()
        try:
            page = max(1, int(request.args.get("page", 1)))
        except ValueError:
            page = 1
        try:
            limit = int(request.args.get("limit", DEFAULT_PAGE_SIZE))
        except ValueError:
            limit = DEFAULT_PAGE_SIZE
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        return self.cached(self.messages_payload(page, limit))


async def setup(bot):
    await bot.add_cog(MessageHistoryAPICog(bot))
