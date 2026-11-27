import asyncio
import os
import time

import discord
from discord.ext import commands, tasks
from firebase_admin import db

try:
    from .tagEnabledGuilds import enabledGuilds
except:
    enabledGuilds = []
last_modified = (
    os.path.getmtime("./commands/Tag/tagEnabledGuilds.py")
    if os.path.exists("./commands/Tag/tagEnabledGuilds.py")
    else 0
)


SWEEP_INTERVAL = 3600  # seconds between full member scans of one server
RECENT_WINDOW = 60  # seconds in which the same role change is not repeated
MEMBER_EVENTS = ("GUILD_MEMBER_ADD", "GUILD_MEMBER_UPDATE")


def check_reload():
    global enabledGuilds, last_modified
    current_modified = os.path.getmtime("./commands/Tag/tagEnabledGuilds.py")
    if current_modified > last_modified:
        with open("./commands/Tag/tagEnabledGuilds.py", "r") as f:
            for line in f:
                if line.startswith("enabledGuilds ="):
                    enabledGuilds = eval(line.split("=")[1].strip())
                    last_modified = current_modified
                    print("Reloaded tagEnabledGuilds.py")
                    break


def word(n):
    return str(n) + (
        "th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    )


def script(string, user, guild):
    replacements = {
        "{mention}": user.mention,
        "{server}": guild.name,
        "{user}": user.name,
        "{tag}": user.primary_guild.tag if user.primary_guild else "No Tag",
    }
    for k, v in replacements.items():
        string = string.replace(k, v)
    return string


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
        guild_id = int(data["guild_id"])
        if guild_id not in self._active:
            return
        task = asyncio.create_task(self._sync_from_event(guild_id, data))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _sync_from_event(self, guild_id, data):
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
            log_chn = self.bot.get_channel(1555014249762398359)
            await self._sync_member(
                member, guild, role, log_channel, settings[2], log_chn
            )
        except Exception as e:
            print(f"Error syncing tag role from event in guild {guild_id}: {e}")

    async def _sync_member(
        self, member, guild, role, log_channel, tag_server_id, log_chn
    ):
        key = (guild.id, member.id)
        if key in self._busy:
            return
        self._busy.add(key)
        try:
            # Ensure IDs are compared as integers
            m_tag_id = member.primary_guild.id if member.primary_guild else None
            t_server_id = int(tag_server_id) if tag_server_id else None

            has_tag = m_tag_id == t_server_id and member.primary_guild.tag is not None
            has_role = role in member.roles

            if has_tag != has_role:
                # A scan can hold a member fetched just before an event already
                # fixed their role; don't act and announce it a second time.
                now = time.time()
                if now - self._recent.get((*key, has_tag), 0) < RECENT_WINDOW:
                    return
                self._recent[(*key, has_tag)] = now

            # Should have role but doesn't
            if has_tag and not has_role:
                await member.add_roles(role)
                embed = discord.Embed(
                    description=f"✅ {member.mention} was given the tag role",
                    colour=0x00FF00,
                )
                await log_chn.send(
                    embed=embed.add_field(
                        name="Guild",
                        value=f"{guild.name} ({guild.id})",
                    )
                )
                try:
                    await log_channel.send(embed=embed)
                except:
                    pass
                await self.send_thank_you(member, guild)

            # Shouldn't have role but does
            elif not has_tag and has_role:
                await member.remove_roles(role)
                embed = discord.Embed(
                    description=f"❌ {member.mention} had tag role removed",
                    colour=0xFF0000,
                )
                await log_chn.send(
                    embed=embed.add_field(
                        name="Guild",
                        value=f"{guild.name} ({guild.id})",
                    )
                )
                try:
                    await log_channel.send(embed=embed)
                except:
                    pass
        except discord.Forbidden:
            print(f"Forbidden: Could not modify role for {member} in {guild.name}")
        except Exception as e:
            print(f"Error processing {member}: {e}")
        finally:
            self._busy.discard(key)

    @tasks.loop(minutes=1)
    async def tag_check(self):
        try:
            check_reload()
        except Exception as e:
            print(f"Error reloading guilds: {e}")

        try:
            ref = db.reference("/Tag Roles")
            all_configs = ref.get()
        except Exception as e:
            print(f"Error fetching tag roles: {e}")
            return

        if not all_configs:
            return

        log_chn = self.bot.get_channel(1555014249762398359)
        active = {}

        for guild_id in enabledGuilds:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                config = None
                for _, val in all_configs.items():
                    if val.get("Server ID") == guild_id:
                        config = val
                        break
                if not config:
                    continue

                # Validate config
                if (
                    "Role ID" not in config
                    or "Log Channel ID" not in config
                    or "Tag Server ID" not in config
                ):
                    # print(f"Incomplete config for guild {guild.name}")
                    continue

                role = guild.get_role(config["Role ID"])
                log_channel = guild.get_channel(config["Log Channel ID"])
                tag_server_id = config["Tag Server ID"]

                if not role or not log_channel:
                    # print(f"Missing role/channel in {guild.name}")
                    continue

                # Check bot permissions
                if not guild.me.guild_permissions.manage_roles:
                    # print(f"Missing manage_roles permission in {guild.name}")
                    continue

                if role >= guild.me.top_role:
                    if log_channel:
                        embed = discord.Embed(
                            description=f"⚠️ Cannot manage tag role {role.mention} because it is higher than or equal to the bot's top role. Make sure the bot's role is higher in your server settings.",
                            colour=0xFFFF00,
                        )
                        try:
                            await log_channel.send(embed=embed)
                        except:
                            pass
                    # print(f"Role {role.name} is higher than bot's top role in {guild.name}")
                    continue

                # Members are synced as their updates arrive (see _on_member_event).
                # A full scan runs only when a server is first seen, its setup
                # changes, or as an hourly safety net.
                settings = (role.id, log_channel.id, tag_server_id)
                active[guild_id] = settings
                last = self._last_sweep.get(guild_id)
                if (
                    last is not None
                    and last[0] == settings
                    and time.time() - last[1] < SWEEP_INTERVAL
                ):
                    continue
                self._active[guild_id] = settings
                self._last_sweep[guild_id] = (settings, time.time())

                async for member in guild.fetch_members(limit=None):
                    await self._sync_member(
                        member, guild, role, log_channel, tag_server_id, log_chn
                    )
            except Exception as e:
                print(f"Error processing guild {guild_id}: {e}")

        self._active = active
        cutoff = time.time() - RECENT_WINDOW
        self._recent = {k: t for k, t in self._recent.items() if t > cutoff}
        for guild_id in list(self._last_sweep):
            if guild_id not in active:
                del self._last_sweep[guild_id]

    @tag_check.error
    async def tag_check_error(self, error):
        print(f"Tag check loop crashed: {error}")

    async def send_thank_you(self, member, guild):
        """Send thank you message if configured and cooldown passed"""
        # Check thank you config
        ref = db.reference("/Tag Thanks")
        thanks_config = None

        # Optimize: Query by Server ID instead of fetching all
        try:
            snapshot = ref.order_by_child("Server ID").equal_to(guild.id).get()
            if snapshot:
                # snapshot is a dict {key: val}, take the first one
                thanks_config = list(snapshot.values())[0]
        except Exception as e:
            print(f"Error fetching Tag Thanks config: {e}")

        if not thanks_config:
            return

        # Check cooldown
        ref = db.reference("/Tag Thanks Cooldown")
        last_thanked = 0

        # Query by User instead of fetching all
        try:
            snapshot = ref.order_by_child("User").equal_to(member.id).get()
            if snapshot:
                for key, val in snapshot.items():
                    if val["Guild"] == guild.id:
                        last_thanked = val["Timestamp"]
                        if time.time() - last_thanked < 86400:  # 24 hours
                            return
                        else:
                            ref.child(key).delete()
        except Exception as e:
            print(f"Error checking cooldown: {e}")

        # Record new thank
        ref.push().set({"User": member.id, "Guild": guild.id, "Timestamp": time.time()})

        # Get message content
        msg_ref = db.reference("/Tag Thanks Message")
        msg_config = None

        # Query by Server ID
        try:
            snapshot = msg_ref.order_by_child("Server ID").equal_to(guild.id).get()
            if snapshot:
                msg_config = list(snapshot.values())[0]
        except Exception as e:
            print(f"Error fetching Tag Thanks Message: {e}")

        # Prepare message
        content = (
            script(msg_config.get("Message Content", ""), member, guild)
            if msg_config
            else ""
        )
        embed = None

        if msg_config and any(
            msg_config.get(k) for k in ["Title", "Description", "Image Link"]
        ):
            color_str = msg_config.get("Color", "")
            color = (
                discord.Color(int(color_str[1:], 16))
                if color_str.startswith("#")
                else discord.Color.blurple()
            )

            embed = discord.Embed(
                title=script(msg_config.get("Title", ""), member, guild),
                description=script(msg_config.get("Description", ""), member, guild),
                color=color,
            )
            if msg_config.get("Image Link"):
                embed.set_image(url=msg_config["Image Link"])

        # Send message
        try:
            if thanks_config["DM"]:
                await member.send(content, embed=embed)
            else:
                channel = guild.get_channel(thanks_config["Channel ID"])
                if channel:
                    await channel.send(content, embed=embed)
        except Exception as e:
            print(f"Failed to send thank you: {e}")

    @tag_check.before_loop
    async def before_tag_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TagRoleHandler(bot))
