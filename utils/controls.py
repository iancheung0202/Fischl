import os
import sys
import asyncio
import base64
from aiohttp import web

AUTH_USER = "ian"
AUTH_PASS = "fischlisthebest"
API_KEY = "8AE7589FG7F75746548DCB869B"

class BotControlServer:
    def __init__(self, bot, host="0.0.0.0", port=8086):
        self.bot = bot
        self.host = host
        self.port = port

    async def start(self):
        app = web.Application()
        app.router.add_route("*", "/restart", self.handle_restart)
        app.router.add_route("*", "/stop", self.handle_stop)
        app.router.add_route("*", "/start", self.handle_start)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        print(f"[Bot Control] Running on http://{self.host}:{self.port}")

    async def _restart(self):
        await asyncio.sleep(1)
        os.execv(sys.executable, ["python3"] + sys.argv)

    async def _stop(self):
        await asyncio.sleep(1)
        await self.bot.close()
        sys.exit(0)

    async def _check_basic_auth(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return False

        try:
            scheme, encoded = auth_header.split(" ")
            if scheme.lower() != "basic":
                return False
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
            return username == AUTH_USER and password == AUTH_PASS
        except Exception:
            return False

    async def _check_key(self, request):
        return request.query.get("key") == API_KEY

    async def _check_auth(self, request):
        return await self._check_basic_auth(request) and await self._check_key(request)

    async def _require_auth(self, request):
        return web.Response(
            status=401,
            text="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="Bot Control"'}
        )

    async def handle_restart(self, request):
        if not await self._check_auth(request):
            return await self._require_auth(request)
        asyncio.create_task(self._restart())
        return web.Response(text="Bot is restarting...")

    async def handle_stop(self, request):
        if not await self._check_auth(request):
            return await self._require_auth(request)
        asyncio.create_task(self._stop())
        return web.Response(text="Bot is stopping...")

    async def handle_start(self, request):
        if not await self._check_auth(request):
            return await self._require_auth(request)
        return web.Response(text="Bot is already running")
