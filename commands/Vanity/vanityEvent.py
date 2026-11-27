import asyncio
import datetime
import time

import aiohttp
import discord
from discord.ext import commands
from firebase_admin import db

from commands.Vanity import vanityStore as store
from utils.config import MASTER_LOG_CHANNEL, THANKS_COOLDOWN

IAN = 692254240290242601


def word(n):
    """Gives 1st, 2nd, 3rd, 4th and so on."""
    return str(n) + (
        "th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    )


def get_custom_status(member):
    """Gives the member's custom status as text, or an empty string."""
    for act in member.activities:
        if isinstance(act, discord.CustomActivity):
            return str(act)
    return ""


async def safe_send(target, *args, context="", **kwargs):
    """Sends a message, and prints why if it could not be sent."""
    if target is None:
        print(f"[Vanity] Tried to send but target was None ({context})")
        return
    try:
        await target.send(*args, **kwargs)
    except discord.Forbidden:
        print(f"[Vanity] Missing permission to send ({context})")
    except discord.HTTPException as e:
        print(f"[Vanity] HTTP error sending message ({context}): {e}")
    except Exception as e:
        print(f"[Vanity] Unexpected error sending message ({context}): {e}")


async def send_master_log(bot, guild, *args, embed=None, context=""):
    """Copies a message to the master log, naming the server it is about."""
    master_embed = embed.copy() if embed is not None else discord.Embed()
    master_embed.add_field(name="Guild", value=f"{guild.name} ({guild.id})")
    await safe_send(
        bot.get_channel(MASTER_LOG_CHANNEL),
        *args,
        embed=master_embed,
        allowed_mentions=discord.AllowedMentions.none(),
        context=f"master log mirror: {context}",
    )


async def send_vanity_log(bot, chn, guild, *args, embed=None, context=""):
    """Sends to the server's log channel, then to the master log."""
    await safe_send(chn, *args, embed=embed, context=context)
    await send_master_log(bot, guild, *args, embed=embed, context=context)


def script(string, user, role, link):
    """Fills the placeholders of a thank-you text."""
    if not string:
        return string
    count = len(role.members) if "{count" in string else 0
    values = {
        "{mention}": user.mention,
        "{server}": user.guild.name,
        "{user}": user.name,
        "{count}": count,
        "{count-th}": word(count),
        "{role}": role.mention,
        "{rolename}": role.name,
        "{link}": link or "",
    }
    for placeholder, value in values.items():
        string = string.replace(placeholder, f"{value}")
    return string


def save_ian_activity(member):
    """Keeps Ian's current activities in Firebase for the status API."""

    def convert_ints_to_str(obj):
        if isinstance(obj, dict):
            return {k: convert_ints_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_ints_to_str(i) for i in obj]
        elif isinstance(obj, int):
            return str(obj)
        else:
            return obj

    try:
        activities = [
            convert_ints_to_str(activity.to_dict()) for activity in member.activities
        ]
        db.reference("/Ian Activity").set(activities)
    except Exception as e:
        print(f"[Vanity] Debug activity logging failed: {e}")


async def embed_color(hex_code, guild_id):
    """Gives the colour for a hex code, or blurple if it cannot be looked up."""
    if not hex_code:
        return discord.Color.blurple()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.thecolorapi.com/id",
                params={"hex": hex_code},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as server:
                if server.status == 200:
                    js = await server.json()
                    return discord.Color(int(f"0x{js['hex']['clean']}", 16))
    except Exception as e:
        print(
            f"[Vanity] Color API lookup failed for guild {guild_id}, hex={hex_code!r}: {e}"
        )
    return discord.Color.blurple()


class OnStatusUpdate(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self.chunked_guilds = set()
        self.watched = {}
        self.loading = asyncio.Lock()

    async def cog_load(self):
        """Makes the tables and reads the settings before the first presence."""
        await store.create(self.client.pool)
        await self.load()

    async def load(self):
        """Reads the role settings of the enabled servers into memory."""
        async with self.loading:
            rows = await store.watched(self.client.pool)
            self.watched = {row["guild_id"]: row for row in rows}

    @commands.Cog.listener()
    async def on_ready(self):
        """Loads the members of the enabled servers; presences need them."""
        for guild_id in await store.enabled(self.client.pool):
            guild = self.client.get_guild(guild_id)
            if guild and guild_id not in self.chunked_guilds:
                await guild.chunk()
                self.chunked_guilds.add(guild_id)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """Gives or takes the vanity role as the link enters or leaves a status."""
        if after.id == IAN:
            save_ian_activity(after)

        settings = self.watched.get(after.guild.id) if after.guild else None
        if settings is None:
            return
        guild = after.guild
        chn = await self.log_channel(guild, settings["log_channel_id"])
        role = guild.get_role(settings["role_id"]) if settings["role_id"] else None
        if role is None:
            await self.role_deleted(guild, chn, settings["role_id"])
            return

        link = settings["link"]
        if not link:
            print(f"[Vanity] Guild {guild.id} has no Link configured; skipping")
            return
        try:
            link = link.split(".")[1]
        except IndexError:
            print(
                f"[Vanity] Guild {guild.id} has a malformed Link value ({link!r}); skipping"
            )
            return

        has_link = link in get_custom_status(after)
        had_link = link in get_custom_status(before)
        was_offline = str(before.status) == "offline"
        if not has_link and role in after.roles and (had_link or was_offline):
            went_offline = had_link and str(after.status) == "offline"
            await self.link_removed(after, role, chn, went_offline, had_link)
        elif has_link and role not in after.roles:
            await self.link_added(after, role, chn, had_link, was_offline, settings)

    async def log_channel(self, guild, channel_id):
        """Finds the server's log channel, asking Discord if it is not cached."""
        if not channel_id:
            return None
        chn = guild.get_channel_or_thread(channel_id) or self.client.get_channel(
            channel_id
        )
        if chn is None:
            print(
                f"[Vanity] Log channel {channel_id} not in cache for guild {guild.id}; trying fetch"
            )
            try:
                chn = await self.client.fetch_channel(channel_id)
            except discord.HTTPException as e:
                print(
                    f"[Vanity] Log channel {channel_id} unavailable for guild {guild.id}: {e}"
                )
        return chn

    async def role_deleted(self, guild, chn, role_id):
        """Turns vanity roles off for a server whose role no longer exists."""
        self.watched.pop(guild.id, None)
        try:
            await store.drop_roles(self.client.pool, guild.id)
            await self.load()
        except Exception as e:
            print(
                f"[Vanity] Failed to remove guild {guild.id} after role deletion: {e}"
            )
        embed = discord.Embed(
            title="Vanity roles disabled!",
            description="You can always re-enable the feature by using `/vanity enable`.",
            colour=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await send_vanity_log(
            self.client,
            chn,
            guild,
            "# Custom vanity role has been deleted by someone else.",
            embed=embed,
            context=f"role-deleted notice, guild {guild.id}",
        )
        print(
            f"[Vanity] Role {role_id} missing in guild {guild.id}; vanity roles disabled for this guild"
        )

    async def link_removed(self, member, role, chn, went_offline, had_link):
        """Takes the role back and logs it; going offline keeps the role."""
        if went_offline:
            embed = discord.Embed(
                description=f":yellow_circle: {member.mention} went offline."
            )
        else:
            try:
                await member.remove_roles(role)
            except discord.HTTPException as e:
                print(
                    f"[Vanity] Failed to remove role from {member} in guild {member.guild.id}: {e}"
                )
            embed = discord.Embed(
                description=f":red_circle: {member.mention} has **removed** vanity link from their status."
            )
            embed.set_footer(text="Role removed")
        path = "" if had_link else " (offline path)"
        await send_vanity_log(
            self.client,
            chn,
            member.guild,
            embed=embed,
            context=f"status-removed{path} notice, guild {member.guild.id}",
        )

    async def link_added(self, member, role, chn, had_link, was_offline, settings):
        """Gives the role, logs it and thanks the member if the link is new."""
        guild = member.guild
        try:
            await member.add_roles(role)
        except discord.HTTPException as e:
            print(f"[Vanity] Failed to add role to {member} in guild {guild.id}: {e}")
            return
        if had_link:
            return

        if was_offline:
            embed = discord.Embed(
                description=f":white_circle: {member.mention} went back online."
            )
        else:
            embed = discord.Embed(
                description=f":green_circle: {member.mention} has **added** vanity link to their status."
            )
            embed.set_footer(text="Role added")
        await send_vanity_log(
            self.client,
            chn,
            guild,
            embed=embed,
            context=f"status-added notice, guild {guild.id}",
        )
        await self.send_thank_you(member, role, settings["link"])

    async def send_thank_you(self, member, role, link):
        """Sends the server's thank-you message, at most once a day per member."""
        guild = member.guild
        try:
            thanks = await store.thanks(self.client.pool, guild.id)
        except Exception as e:
            print(f"[Vanity] Error fetching Vanity Thanks for guild {guild.id}: {e}")
            return
        if thanks is None:
            return
        target = member if thanks["dm"] else guild.get_channel(thanks["channel_id"])
        if target is None:
            print(
                f"[Vanity] Configured thank-you channel {thanks['channel_id']} not found in guild {guild.id}"
            )
            return

        if not await self._claim(guild.id, member.id):
            return

        embed = None
        if thanks["title"] or thanks["description"] or thanks["image"]:
            embed = discord.Embed(
                title=script(thanks["title"] or "", member, role, link),
                description=script(thanks["description"] or "", member, role, link),
                color=await embed_color((thanks["color"] or "").lstrip("#"), guild.id),
            )
            if thanks["image"]:
                embed.set_image(url=thanks["image"])
        content = script(thanks["content"] or "", member, role, link)
        place = "DM" if thanks["dm"] else "channel"
        await safe_send(
            target, content, embed=embed, context=f"thank-you {place}, guild {guild.id}"
        )
        await send_master_log(
            self.client,
            guild,
            content,
            embed=embed,
            context=f"thank-you log, guild {guild.id}",
        )

    async def _claim(self, guild_id, member_id):
        """Starts the member's cooldown; False if they are still in one."""
        try:
            return await store.claim_thanks(
                self.client.pool, guild_id, member_id, int(time.time()), THANKS_COOLDOWN
            )
        except Exception as e:
            print(f"[Vanity] Error fetching Vanity User for guild {guild_id}: {e}")
            return True


async def setup(bot):
    await bot.add_cog(OnStatusUpdate(bot))
