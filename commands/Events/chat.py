import datetime
import random
import re
import time
from difflib import SequenceMatcher

from commands.Events.chests import get_next_reset_unix
from commands.Events.config import (
    BALANCE_COMMAND,
    DEFAULT_CHAT_MSG_RANGE,
    DEFAULT_CHAT_RANGE,
    SIGIL_CURRENCY_NAME,
    SIGIL_EMOTE,
    SIGILS_MESSAGE_EMOTE,
)
from commands.Events.helperFunctions import (
    add_sigils,
    get_daily_sigils,
    get_guild_settings,
    parse_boosted_roles,
)
from utils.commands import SlashCommand

COOLDOWN = 5


def is_effortful(content: str, last_content: str) -> bool:
    """Says whether a message counts towards Sigils: not short, only emojis, a link or a near copy of the last."""
    if len(content) < 5:
        return False
    if re.fullmatch(r"(\s*<a?:\w+:\d+>\s*){1,4}", content):
        return False
    if re.search(r"(https?:\/\/|www\.|discord\.gg\/)", content.lower()):
        return False
    if not last_content:
        return True
    return SequenceMatcher(None, last_content.lower(), content.lower()).ratio() <= 0.9


def between(saved, default) -> int:
    """Gives a random whole number in a saved [low, high] range; a range of one number is that number."""
    low = saved[0] if saved else default[0]
    return random.randint(low, saved[1] if len(saved) > 1 else low)


class DailySigilSystem:
    """Pays Sigils to members who chat actively, up to each member's cap for the day."""

    def __init__(self, pool):
        self.pool = pool
        self.cooldowns = {}
        self.msg_counts = {}
        self.last_messages = {}

    async def calculate_max_sigils(self, member, cap: int, settings: dict) -> int:
        """Gives a member's cap for the day: the server's, raised by what their roles add or set."""
        roles = {role.id for role in member.roles}
        for role, bonus in await parse_boosted_roles(
            settings.get("chat_boosted_roles")
        ):
            if role not in roles:
                continue
            try:
                if str(bonus).startswith("+"):
                    cap += int(bonus[1:])
                else:
                    cap = max(cap, int(bonus))
            except ValueError:
                continue
        return cap

    def counted(self, message, settings: dict) -> bool:
        """Counts an effortful message and says whether its author has now sent enough for a payout."""
        key = (message.guild.id, message.author.id)
        now = time.time()
        if now - self.cooldowns.get(key, 0) < COOLDOWN:
            return False
        content = message.content.strip()
        if not is_effortful(content, self.last_messages.get(key, "")):
            return False
        self.cooldowns[key] = now
        self.last_messages[key] = content
        self.msg_counts[key] = self.msg_counts.get(key, 0) + 1
        needed = between(settings.get("chat_msg_range") or [], DEFAULT_CHAT_MSG_RANGE)
        if self.msg_counts[key] < needed:
            return False
        self.msg_counts[key] = 0
        return True

    async def process_chat_sigils(self, message, settings: dict, client=None) -> None:
        """Counts a message in a chat channel and pays its author Sigils when one is due and their cap allows."""
        if not self.counted(message, settings):
            return
        gid, uid = message.guild.id, message.author.id
        server = await get_guild_settings(self.pool, gid)
        cap = await self.calculate_max_sigils(
            message.author, server["chat_max_cap"], settings
        )
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        had = (await get_daily_sigils(self.pool, uid, gid, date)).get("earnings", 0)
        earned = min(
            between(settings.get("chat_range") or [], DEFAULT_CHAT_RANGE), cap - had
        )
        if earned <= 0:
            return
        await add_sigils(self.pool, uid, gid, earned, message.channel.id, client)
        try:
            await message.channel.send(
                f"{SIGILS_MESSAGE_EMOTE} {message.author.mention} earned {SIGIL_EMOTE} **{earned} {SIGIL_CURRENCY_NAME}** "
                f"for chatting actively! *(Daily Cap: `{had + earned}/{int(cap)}`)*\n"
                f"> -# <a:clock:1382887924273774754> Resets <t:{get_next_reset_unix()}:R>. Use {SlashCommand(BALANCE_COMMAND)} to check your progress!"
            )
        except Exception:
            pass

    def forget(self) -> None:
        """Drops the remembered last messages and cooldowns, which otherwise grow without end."""
        self.cooldowns.clear()
        self.last_messages.clear()
        self.msg_counts = {key: n for key, n in self.msg_counts.items() if n}


async def setup(bot) -> None:
    pass
