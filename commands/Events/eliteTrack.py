"""Elite Track: the owner's `-addSub` command, and paying out the elite rewards a new subscriber is owed."""

import asyncio

import discord
from discord.ext import commands

from commands.Events.config import MONEYDANCE_EMOTE, NO_EMOTE, YES_EMOTE
from commands.Events.helperFunctions import get_user_xp
from commands.Events.trackData import grant_elite_rewards_up_to_tier

IAN = 692254240290242601
PENDING = "SELECT user_id, guild_id, server_name FROM minigame_elite WHERE pending_processed = FALSE AND expires_at > EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)"
ENABLED = "SELECT channel_id FROM minigame_settings WHERE minigames_enabled = TRUE"
PROCESSED = "UPDATE minigame_elite SET pending_processed = TRUE WHERE user_id = $1 AND guild_id = $2"
SUBSCRIBE = """INSERT INTO minigame_elite (user_id, guild_id, expires_at, pending_processed)
                       VALUES ($1, $2, $3, TRUE)
                       ON CONFLICT (user_id, guild_id)
                       DO UPDATE SET expires_at = EXCLUDED.expires_at, pending_processed = TRUE"""


async def dm(user, embed):
    """DMs the embed, unless the member has DMs closed."""
    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        pass


def granted(guild, rewards):
    """Gives the DM listing the rewards paid out for earlier tiers."""
    return discord.Embed(
        title="🎁 Elite Rewards Granted!",
        description=(
            f"Your elite rewards have been processed for **{guild.name}**!\n\n"
            "***You've received these elite rewards from previous tiers:***\n\n"
            + "\n".join(rewards)
        ),
        color=0xFA0ADD,
    )


def activated(server, server_id, timestamp, rewards):
    """Gives the DM that says the Elite Track is on and until when."""
    server_name = server.name if server else f"Server {server_id}"
    rewards_message = (
        "***You've also automatically received these elite rewards from previous tiers:***\n\n"
        + "\n".join(rewards)
        if rewards
        else "⭐ *No elite rewards from previous tiers are automatically claimed.*"
    )
    return discord.Embed(
        title=f"{MONEYDANCE_EMOTE} Elite Track Activated!",
        description=(
            f"🎉 You now have sweet perks in **{server_name}**! Enjoy friend!\n"
            f"⏰ Expires on <t:{int(timestamp)}> (<t:{int(timestamp)}:R>)\n\n"
            f"{rewards_message}"
        ),
        color=0xFA0ADD,
    )


class EliteTrack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.process_pending_activations())

    async def process_pending_activations(self):
        """Every minute, pays out subscriptions bought on the website."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)
        while not self.bot.is_closed():
            try:
                async with self.bot.pool.acquire() as conn:
                    rows = await conn.fetch(PENDING)
                for row in rows:
                    guild = await self.bot.fetch_guild(row["guild_id"])
                    if not guild:
                        continue
                    try:
                        await self.activate(row["user_id"], guild, row["guild_id"])
                    except Exception as e:
                        print(f"Error processing pending activation: {e}")
            except Exception as e:
                print(f"Error in process_pending_activations: {e}")
            await asyncio.sleep(60)

    async def minigame_channel(self, guild):
        """Gives the server's first minigame channel the bot can write in, or None."""
        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetch(ENABLED)
        enabled = {row["channel_id"] for row in rows}
        for channel in guild.text_channels:
            if (
                channel.id in enabled
                and channel.permissions_for(guild.me).send_messages
            ):
                return channel
        return None

    async def activate(self, user_id, guild, guild_id):
        """Grants a new subscriber the elite rewards of tiers already reached."""
        pool = self.bot.pool
        current_xp = await get_user_xp(pool, guild_id, user_id)
        channel = await self.minigame_channel(guild)
        if channel and current_xp > 0:
            rewards = await grant_elite_rewards_up_to_tier(
                guild_id, user_id, channel, current_xp, client=self.bot, pool=pool
            )
            if rewards:
                user = await self.bot.fetch_user(user_id)
                if user:
                    await dm(user, granted(guild, rewards))
        async with pool.acquire() as conn:
            await conn.execute(PROCESSED, user_id, guild_id)
        print(
            f"Processed pending elite activation for user {user_id} in guild {guild_id}"
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.content.startswith("-addSub"):
            return
        if message.author.id != IAN:
            await message.channel.send(
                f"{NO_EMOTE} You don't have permission to use this command."
            )
            return

        args = message.content.split()
        if len(args) != 4:
            await message.channel.send(
                f"{NO_EMOTE} Usage: `-addSub userID serverID timestamp`"
            )
            return
        try:
            user_id = int(args[1])
            server_id = int(args[2])
            timestamp = float(args[3])
        except ValueError:
            await message.channel.send(
                f"{NO_EMOTE} Invalid arguments. Make sure IDs are numbers and timestamp is a float."
            )
            return

        pool = self.bot.pool
        async with pool.acquire() as conn:
            await conn.execute(SUBSCRIBE, user_id, server_id, timestamp)
        user = await self.bot.fetch_user(user_id)
        server = await self.bot.fetch_guild(server_id)
        current_xp = await get_user_xp(pool, server_id, user_id)
        rewards = await grant_elite_rewards_up_to_tier(
            server_id, user_id, message.channel, current_xp, client=self.bot, pool=pool
        )
        if user:
            await dm(user, activated(server, server_id, timestamp, rewards))
        await message.channel.send(
            f"{YES_EMOTE} Subscription added for <@{user_id}> in server `{server_id}`"
        )


async def setup(bot):
    await bot.add_cog(EliteTrack(bot))
