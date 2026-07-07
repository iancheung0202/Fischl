import discord, firebase_admin, asyncio, datetime, time, aiohttp, ast
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db
from discord.ui import Button, View
import importlib
import os

from commands.Vanity.enabledGuilds import enabledGuilds

ENABLED_GUILDS_PATH = "./commands/Vanity/enabledGuilds.py"

# Guards all read-modify-write access to enabledGuilds.py so two concurrent
# events (e.g. presence updates for two different guilds) can't race and
# silently clobber each other's changes.
enabled_guilds_lock = asyncio.Lock()

last_modified = os.path.getmtime(ENABLED_GUILDS_PATH)
ref = db.reference("/Vanity Roles")
vanity = ref.get() or {}


def get_vanity_entry(guild_id):
    """Safely look up a guild's vanity config. Returns None (and logs) instead
    of leaving locals unbound / crashing when the entry can't be found."""
    if not vanity:
        print(f"[Vanity] No vanity data loaded at all (DB empty?) while looking up guild {guild_id}")
        return None
    for key, val in vanity.items():
        if val.get("Server ID") == guild_id:
            return val
    print(f"[Vanity] No vanity entry found in cache for guild {guild_id} (enabledGuilds/DB may be out of sync)")
    return None


async def read_enabled_guilds():
    """Read the current list from disk. Returns None on parse failure instead
    of raising/leaving a variable unbound."""
    async with enabled_guilds_lock:
        try:
            with open(ENABLED_GUILDS_PATH, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"[Vanity] {ENABLED_GUILDS_PATH} not found while reading enabled guilds")
            return None, None

        for i, line in enumerate(lines):
            if line.startswith("enabledGuilds ="):
                try:
                    parsed = ast.literal_eval(line.split("=", 1)[1].strip())
                except (ValueError, SyntaxError) as e:
                    print(f"[Vanity] Failed to parse enabledGuilds.py line {i}: {e}")
                    return None, None
                return parsed, lines
        print("[Vanity] Could not find an 'enabledGuilds =' line in enabledGuilds.py")
        return None, None


async def write_enabled_guilds(guild_id, remove=False):
    """Add or remove a guild id from enabledGuilds.py safely, under the lock,
    so concurrent events don't overwrite each other's edits."""
    async with enabled_guilds_lock:
        try:
            with open(ENABLED_GUILDS_PATH, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"[Vanity] {ENABLED_GUILDS_PATH} not found while writing enabled guilds")
            return False

        found_line = False
        for i, line in enumerate(lines):
            if line.startswith("enabledGuilds ="):
                found_line = True
                try:
                    existing_ids = ast.literal_eval(line.split("=", 1)[1].strip())
                except (ValueError, SyntaxError) as e:
                    print(f"[Vanity] Failed to parse enabledGuilds.py while writing: {e}")
                    return False
                if remove:
                    if guild_id in existing_ids:
                        existing_ids.remove(guild_id)
                    else:
                        print(f"[Vanity] Guild {guild_id} was not in enabledGuilds; nothing to remove")
                else:
                    if guild_id not in existing_ids:
                        existing_ids.append(guild_id)
                lines[i] = f"enabledGuilds = {existing_ids}\n"
                break

        if not found_line:
            print("[Vanity] Could not find an 'enabledGuilds =' line; write aborted")
            return False

        try:
            with open(ENABLED_GUILDS_PATH, "w") as f:
                f.writelines(lines)
        except OSError as e:
            print(f"[Vanity] Failed to write enabledGuilds.py: {e}")
            return False
        return True


async def check_and_reload():
    global last_modified, vanity, enabledGuilds
    try:
        new_modified = os.path.getmtime(ENABLED_GUILDS_PATH)
    except FileNotFoundError:
        print(f"[Vanity] {ENABLED_GUILDS_PATH} missing during mtime check")
        return

    if new_modified <= last_modified:
        return

    new_enabled_guilds, _ = await read_enabled_guilds()
    if new_enabled_guilds is None:
        # Parsing failed; don't touch state, just try again next time.
        return

    if new_enabled_guilds != enabledGuilds:
        enabledGuilds = new_enabled_guilds
        last_modified = new_modified
        fresh = db.reference("/Vanity Roles").get()
        vanity = fresh or {}
        if fresh is None:
            print("[Vanity] /Vanity Roles came back empty from Firebase on reload")


def word(n):
    return str(n) + (
        "th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    )


def get_custom_status(member):
    for act in member.activities:
        if isinstance(act, discord.CustomActivity):
            return act
    return None


async def safe_send(channel_or_member, *args, context="", **kwargs):
    """Send a message and log (instead of silently swallowing) any failure,
    consistently, wherever we message a channel/DM/member."""
    if channel_or_member is None:
        print(f"[Vanity] Tried to send but target was None ({context})")
        return None
    try:
        return await channel_or_member.send(*args, **kwargs)
    except discord.Forbidden:
        print(f"[Vanity] Missing permission to send ({context})")
    except discord.HTTPException as e:
        print(f"[Vanity] HTTP error sending message ({context}): {e}")
    except Exception as e:
        print(f"[Vanity] Unexpected error sending message ({context}): {e}")
    return None


def script(string, user, guild):
    if not string:
        return string

    if "{mention}" in string:
        string = string.replace("{mention}", f"{user.mention}")
    if "{server}" in string:
        string = string.replace("{server}", f"{guild.name}")
    if "{user}" in string:
        string = string.replace("{user}", f"{user.name}")

    # These four all need the configured role, so resolve it once instead of
    # re-scanning `vanity` per placeholder. If the guild has no entry (stale
    # cache, race with check_and_reload, etc.) or the role no longer exists,
    # we log and leave the placeholder untouched rather than crashing.
    if any(tag in string for tag in ("{count}", "{count-th}", "{role}", "{rolename}")):
        entry = get_vanity_entry(guild.id)
        role = guild.get_role(entry["Role ID"]) if entry else None
        if role is None:
            print(f"[Vanity] script(): could not resolve role for guild {guild.id}; leaving role-based placeholders as-is")
        else:
            if "{count}" in string:
                string = string.replace("{count}", f"{len(role.members)}")
            if "{count-th}" in string:
                string = string.replace("{count-th}", f"{word(len(role.members))}")
            if "{role}" in string:
                string = string.replace("{role}", f"{role.mention}")
            if "{rolename}" in string:
                string = string.replace("{rolename}", f"{role.name}")

    if "{link}" in string:
        entry = get_vanity_entry(guild.id)
        if entry:
            string = string.replace("{link}", f"{entry.get('Link', '')}")
        else:
            print(f"[Vanity] script(): could not resolve link for guild {guild.id}; leaving {{link}} as-is")

    return string


class OnStatusUpdate(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self.chunked_guilds = set()

    @commands.Cog.listener()
    async def on_ready(self):
        overlapping = [gid for gid in enabledGuilds if self.client.get_guild(gid)]

        for guild_id in overlapping:
            if guild_id not in self.chunked_guilds:
                guild = self.client.get_guild(guild_id)
                if guild:
                    await guild.chunk()
                    self.chunked_guilds.add(guild_id)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        await check_and_reload()

        if after.id == 692254240290242601:
            # NOTE: this looks like leftover personal debug/logging code
            # unrelated to vanity roles (tracking one hardcoded user's
            # activity to Firebase). Left in place but hardened so a bad
            # activity payload can't crash the rest of this listener (and
            # therefore vanity-role processing) for every other guild.
            try:
                debug_ref = db.reference("/Ian Activity")

                def convert_ints_to_str(obj):
                    if isinstance(obj, dict):
                        return {k: convert_ints_to_str(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_ints_to_str(i) for i in obj]
                    elif isinstance(obj, int):
                        return str(obj)
                    else:
                        return obj

                activities = [
                    convert_ints_to_str(activity.to_dict()) for activity in after.activities
                ]
                debug_ref.set(activities)
            except Exception as e:
                print(f"[Vanity] Debug activity logging failed: {e}")

        if after.guild is None or after.guild.id not in enabledGuilds:
            return

        entry = get_vanity_entry(after.guild.id)
        if entry is None:
            # Already logged inside get_vanity_entry. There's nothing sane
            # to do without the config, so bail instead of crashing on
            # unbound locals further down (the original bug).
            return

        log_channel_id = entry.get("Log Channel ID")
        role_id = entry.get("Role ID")
        link = entry.get("Link")

        chn = self.client.get_channel(log_channel_id) if log_channel_id else None
        if chn is None and log_channel_id:
            print(f"[Vanity] Log channel {log_channel_id} not in cache for guild {after.guild.id}; trying fetch")
            try:
                chn = await self.client.fetch_channel(log_channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                print(f"[Vanity] Log channel {log_channel_id} unavailable for guild {after.guild.id}: {e}")
                chn = None

        role = after.guild.get_role(role_id) if role_id else None
        if role is None:
            # The configured role no longer exists (deleted by someone) —
            # disable the feature for this guild instead of repeatedly
            # crashing on every future presence update.
            for key, val in vanity.items():
                if val.get("Server ID") == after.guild.id:
                    try:
                        db.reference("/Vanity Roles").child(key).delete()
                    except Exception as e:
                        print(f"[Vanity] Failed to delete stale /Vanity Roles entry for guild {after.guild.id}: {e}")
                    break

            ok = await write_enabled_guilds(after.guild.id, remove=True)
            if not ok:
                print(f"[Vanity] Failed to remove guild {after.guild.id} from enabledGuilds.py after role deletion")

            embed = discord.Embed(
                title="Vanity roles disabled!",
                description="You can always re-enable the feature by using `/vanity enable`.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await safe_send(
                chn,
                "# Custom vanity role has been deleted by someone else.",
                embed=embed,
                context=f"role-deleted notice, guild {after.guild.id}",
            )
            print(f"[Vanity] Role {role_id} missing in guild {after.guild.id}; vanity roles disabled for this guild")
            return

        if not link:
            print(f"[Vanity] Guild {after.guild.id} has no Link configured; skipping")
            return
        try:
            link = link.split(".")[1]
        except (IndexError, AttributeError):
            print(f"[Vanity] Guild {after.guild.id} has a malformed Link value ({link!r}); skipping")
            return

        after_status = get_custom_status(after)
        before_status = get_custom_status(before)
        after_str = str(after_status) if after_status else ""
        before_str = str(before_status) if before_status else ""

        if (link not in after_str) and (link in before_str) and (role in after.roles):
            if str(after.status) == "offline":
                embed = discord.Embed(description=f":yellow_circle: {after.mention} went offline.")
            else:
                try:
                    await after.remove_roles(role)
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(f"[Vanity] Failed to remove role from {after} in guild {after.guild.id}: {e}")
                embed = discord.Embed(
                    description=f":red_circle: {after.mention} has **removed** vanity link from their status."
                )
                embed.set_footer(text="Role removed")
            await safe_send(chn, embed=embed, context=f"status-removed notice, guild {after.guild.id}")

        # Added vanity, go offline, removed vanity, go back online
        elif (link not in after_str) and (str(before.status) == "offline") and (role in after.roles):
            try:
                await after.remove_roles(role)
            except (discord.Forbidden, discord.HTTPException) as e:
                print(f"[Vanity] Failed to remove role from {after} in guild {after.guild.id}: {e}")
            embed = discord.Embed(
                description=f":red_circle: {after.mention} has **removed** vanity link from their status."
            )
            embed.set_footer(text="Role removed")
            await safe_send(chn, embed=embed, context=f"status-removed (offline path) notice, guild {after.guild.id}")

        elif (link in after_str) and (role not in after.roles):
            try:
                await after.add_roles(role)
            except (discord.Forbidden, discord.HTTPException) as e:
                print(f"[Vanity] Failed to add role to {after} in guild {after.guild.id}: {e}")
                return

            if link in before_str:
                return  # already had it, nothing new to announce/thank

            if str(before.status) == "offline":
                embed = discord.Embed(description=f":white_circle: {after.mention} went back online.")
            else:
                embed = discord.Embed(
                    description=f":green_circle: {after.mention} has **added** vanity link to their status."
                )
                embed.set_footer(text="Role added")
            await safe_send(chn, embed=embed, context=f"status-added notice, guild {after.guild.id}")

            # --- Thank-you message ---
            thanks_ref = db.reference("/Vanity Thanks")
            thankyouChannel = None
            try:
                snapshot = thanks_ref.order_by_child("Server ID").equal_to(after.guild.id).get()
                if snapshot:
                    val = list(snapshot.values())[0]
                    if not val.get("DM"):
                        thankyouChannel = after.guild.get_channel(val.get("Channel ID"))
                        if thankyouChannel is None:
                            print(f"[Vanity] Configured thank-you channel {val.get('Channel ID')} not found in guild {after.guild.id}")
                    else:
                        thankyouChannel = "DM"
            except Exception as e:
                print(f"[Vanity] Error fetching Vanity Thanks for guild {after.guild.id}: {e}")

            if thankyouChannel is None:
                return

            msg_ref = db.reference("/Vanity Thanks Message")
            embed = None
            msgContent = ""
            try:
                snapshot = msg_ref.order_by_child("Server ID").equal_to(after.guild.id).get()
                if snapshot:
                    val = list(snapshot.values())[0]
                    msgContent = val.get("Message Content", "") or ""
                    if val.get("Title") or val.get("Description") or val.get("Image Link"):
                        hex_code = (val.get("Color") or "").lstrip("#")
                        color = discord.Color.blurple()
                        if hex_code:
                            try:
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(
                                        "https://www.thecolorapi.com/id",
                                        params={"hex": hex_code},
                                        timeout=aiohttp.ClientTimeout(total=5),
                                    ) as server:
                                        if server.status == 200:
                                            js = await server.json()
                                            color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
                            except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError) as e:
                                print(f"[Vanity] Color API lookup failed for guild {after.guild.id}, hex={hex_code!r}: {e}")
                                color = discord.Color.blurple()

                        embed = discord.Embed(
                            title=script(val.get("Title", ""), after, after.guild),
                            description=script(val.get("Description", ""), after, after.guild),
                            color=color,
                        )
                        if val.get("Image Link"):
                            embed.set_image(url=val["Image Link"])
            except Exception as e:
                print(f"[Vanity] Error fetching Vanity Thanks Message for guild {after.guild.id}: {e}")

            user_ref = db.reference("/Vanity User")
            lastThanked = 0
            try:
                snapshot = user_ref.order_by_child("User ID").equal_to(after.id).get()
                if snapshot:
                    for key, val in snapshot.items():
                        if val.get("Server ID") == after.guild.id:
                            lastThanked = val.get("Last Thanked Timestamp", 0)
                            now_ts = int(time.mktime(datetime.datetime.now().timetuple()))
                            if (now_ts - lastThanked) > 86400:
                                try:
                                    db.reference("/Vanity User").child(key).delete()
                                except Exception as e:
                                    print(f"[Vanity] Failed to delete stale Vanity User entry: {e}")
                            break
            except Exception as e:
                print(f"[Vanity] Error fetching Vanity User for guild {after.guild.id}: {e}")

            now_ts = int(time.mktime(datetime.datetime.now().timetuple()))
            if (now_ts - lastThanked) > 86400:
                data = {
                    "Data": {
                        "User ID": after.id,
                        "Server ID": after.guild.id,
                        "Last Thanked Timestamp": now_ts,
                    }
                }
                try:
                    for key, value in data.items():
                        user_ref.push().set(value)
                except Exception as e:
                    print(f"[Vanity] Failed to record Last Thanked Timestamp for guild {after.guild.id}: {e}")

                rendered_msg = script(msgContent, after, after.guild)
                if thankyouChannel == "DM":
                    await safe_send(after, rendered_msg, embed=embed, context=f"thank-you DM, guild {after.guild.id}")
                else:
                    await safe_send(thankyouChannel, rendered_msg, embed=embed, context=f"thank-you channel, guild {after.guild.id}")


async def setup(bot):
    await bot.add_cog(OnStatusUpdate(bot))