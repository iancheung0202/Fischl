import asyncio
import time

import discord
from discord.ext import commands, tasks

from commands.Tag import tagStore as store
from utils.config import MASTER_LOG_CHANNEL, THANKS_COOLDOWN

SWEEP_INTERVAL = 3600  # seconds between full member scans of one server
RECENT_WINDOW = 60  # seconds in which the same role change is not repeated
MEMBER_EVENTS = ("GUILD_MEMBER_ADD", "GUILD_MEMBER_UPDATE")
GIVEN = ("✅ {} was given the tag role", 0x00FF00)
REMOVED = ("❌ {} had tag role removed", 0xFF0000)
ROLE_TOO_HIGH = (
    "⚠️ Cannot manage tag role {} because it is higher than or equal to the bot's "
    "top role. Make sure the bot's role is higher in your server settings."
)


def script(string, user, guild):
    """Fills the variables a thank-you message may use."""
    replacements = {
        "{mention}": user.mention,
        "{server}": guild.name,
        "{user}": user.name,
        "{tag}": user.primary_guild.tag if user.primary_guild else "No Tag",
    }
    for k, v in replacements.items():
        string = string.replace(k, v)
    return string


def thanks_embed(thanks, member, guild):
    """Builds the embed of a thank-you message, or None if it has none."""
    if not any(thanks[part] for part in ("title", "description", "image")):
        return None
    color = thanks["color"] or ""
    embed = discord.Embed(
        title=script(thanks["title"] or "", member, guild),
        description=script(thanks["description"] or "", member, guild),
        color=(
            discord.Color(int(color[1:], 16))
            if color.startswith("#")
            else discord.Color.blurple()
        ),
    )
    if thanks["image"]:
        embed.set_image(url=thanks["image"])
    return embed


class TagRoleHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._active = {}  # guild id -> (role id, log channel id, tag server id)
        self._last_sweep = {}  # guild id -> (settings, time of last full scan)
        self._busy = set()  # (guild id, member id) being synced right now
        self._recent = {}  # (guild id, member id, gave role) -> time, last minute only
        self._tasks = set()
        self._original_parsers = {}
        self._hook_member_events()
        self.tag_check.start()

    def cog_unload(self):
        """Stops the minute check and hands member events back to discord.py."""
        self.tag_check.cancel()
        self.bot._connection.parsers.update(self._original_parsers)

    def _hook_member_events(self):
        """Reads member joins and updates straight from Discord.

        discord.py drops these for members it does not keep in memory, and we
        keep none. Nothing is stored here either: the member is checked and let go."""
        parsers = self.bot._connection.parsers
        for event in MEMBER_EVENTS:
            original = parsers[event]
            self._original_parsers[event] = original

            def parser(data, original=original):
                original(data)
                try:
                    self._on_member_event(data)
                except Exception as e:
                    print(f"Error reading member event for tag roles: {e}")

            parsers[event] = parser

    def _on_member_event(self, data):
        """Starts a sync for a member of a watched server."""
        guild_id = int(data["guild_id"])
        if guild_id not in self._active:
            return
        task = asyncio.create_task(self._sync_from_event(guild_id, data))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _sync_from_event(self, guild_id, data):
        """Syncs the member a join or update event is about."""
        try:
            settings = self._active.get(guild_id)
            guild = self.bot.get_guild(guild_id)
            if not settings or not guild:
                return
            role = guild.get_role(settings[0])
            log_channel = guild.get_channel(settings[1])
            if not role or not log_channel:
                return
            member = discord.Member(data=data, guild=guild, state=self.bot._connection)
            await self._sync_member(member, role, log_channel, settings[2])
        except Exception as e:
            print(f"Error syncing tag role from event in guild {guild_id}: {e}")

    async def _sync_member(self, member, role, log_channel, tag_server_id):
        """Gives or removes the tag role so it matches the member's tag."""
        key = (member.guild.id, member.id)
        if key in self._busy:
            return
        self._busy.add(key)
        try:
            tag = member.primary_guild
            has_tag = (tag.id if tag else None) == tag_server_id and tag.tag is not None
            if has_tag == (role in member.roles) or self._just_done(key, has_tag):
                return
            if has_tag:
                await member.add_roles(role)
                await self._log(member, log_channel, GIVEN)
                await self.send_thank_you(member)
            else:
                await member.remove_roles(role)
                await self._log(member, log_channel, REMOVED)
        except discord.Forbidden:
            print(
                f"Forbidden: Could not modify role for {member} in {member.guild.name}"
            )
        except Exception as e:
            print(f"Error processing {member}: {e}")
        finally:
            self._busy.discard(key)

    def _just_done(self, key, has_tag):
        """True if this same change was made within the last minute.

        A scan can hold a member fetched just before an event already fixed
        their role; this keeps it from acting and announcing a second time."""
        now = time.time()
        if now - self._recent.get((*key, has_tag), 0) < RECENT_WINDOW:
            return True
        self._recent[(*key, has_tag)] = now
        return False

    async def _log(self, member, log_channel, change):
        """Reports a role change to our own log and the server's."""
        text, colour = change
        embed = discord.Embed(description=text.format(member.mention), colour=colour)
        guild = member.guild
        await self.bot.get_channel(MASTER_LOG_CHANNEL).send(
            embed=embed.add_field(name="Guild", value=f"{guild.name} ({guild.id})")
        )
        try:
            await log_channel.send(embed=embed)
        except:
            pass

    async def _target(self, guild, row):
        """Gives the role, log channel and tag server to check, or None."""
        if None in (row["role_id"], row["log_channel_id"], row["tag_guild_id"]):
            return None
        role = guild.get_role(row["role_id"])
        log_channel = guild.get_channel(row["log_channel_id"])
        if not role or not log_channel or not guild.me.guild_permissions.manage_roles:
            return None
        if role >= guild.me.top_role:
            embed = discord.Embed(
                description=ROLE_TOO_HIGH.format(role.mention), colour=0xFFFF00
            )
            try:
                await log_channel.send(embed=embed)
            except:
                pass
            return None
        return role, log_channel, row["tag_guild_id"]

    def _due(self, guild_id, settings):
        """True when a server needs a full scan: new, changed, or an hour on."""
        last = self._last_sweep.get(guild_id)
        return (
            last is None
            or last[0] != settings
            or time.time() - last[1] >= SWEEP_INTERVAL
        )

    @tasks.loop(minutes=1)
    async def tag_check(self):
        """Refreshes which servers are watched and scans the ones that are due.

        Members are synced as their updates arrive (see _on_member_event), so
        a full scan is only a safety net."""
        try:
            rows = await store.watched(self.bot.pool)
        except Exception as e:
            print(f"Error fetching tag roles: {e}")
            return

        active = {}
        for row in rows:
            guild_id = row["guild_id"]
            try:
                guild = self.bot.get_guild(guild_id)
                target = guild and await self._target(guild, row)
                if not target:
                    continue
                role, log_channel, tag_server_id = target
                active[guild_id] = settings = (role.id, log_channel.id, tag_server_id)
                if not self._due(guild_id, settings):
                    continue
                self._active[guild_id] = settings
                self._last_sweep[guild_id] = (settings, time.time())
                async for member in guild.fetch_members(limit=None):
                    await self._sync_member(member, role, log_channel, tag_server_id)
            except Exception as e:
                print(f"Error processing guild {guild_id}: {e}")

        self._active = active
        cutoff = time.time() - RECENT_WINDOW
        self._recent = {k: t for k, t in self._recent.items() if t > cutoff}
        self._last_sweep = {g: s for g, s in self._last_sweep.items() if g in active}

    @tag_check.error
    async def tag_check_error(self, error):
        """Reports a crash of the minute check."""
        print(f"Tag check loop crashed: {error}")

    async def send_thank_you(self, member):
        """Sends the server's thank-you message, at most once a day per member."""
        guild = member.guild
        pool = self.bot.pool
        thanks = await store.thanks(pool, guild.id)
        if not thanks or not await self._claim(guild.id, member.id):
            return
        content = script(thanks["content"] or "", member, guild)
        embed = thanks_embed(thanks, member, guild)
        try:
            if thanks["dm"]:
                await member.send(content, embed=embed)
            else:
                channel = guild.get_channel(thanks["channel_id"])
                if channel:
                    await channel.send(content, embed=embed)
        except Exception as e:
            print(f"Failed to send thank you: {e}")

    async def _claim(self, guild_id, member_id):
        """Starts the member's cooldown; False if they are still in one."""
        try:
            return await store.claim_thanks(
                self.bot.pool, guild_id, member_id, time.time(), THANKS_COOLDOWN
            )
        except Exception as e:
            print(f"Error checking cooldown: {e}")
            return True

    @tag_check.before_loop
    async def before_tag_check(self):
        """Holds the first check until the bot knows its servers."""
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TagRoleHandler(bot))
