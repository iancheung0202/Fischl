import discord
import asyncio

from discord.ext import commands

from commands.Events.trackData import grant_elite_rewards_up_to_tier

from commands.Events.config import YES_EMOTE, NO_EMOTE, MONEYDANCE_EMOTE

class EliteTrack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.init_elite())
        self.bot.loop.create_task(self.process_pending_activations())

    async def init_elite(self):
        await self.bot.wait_until_ready()
        from commands.Events.helperFunctions import ensure_minigame_elite_table
        await ensure_minigame_elite_table(self.bot.pool)

    async def process_pending_activations(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

        while not self.bot.is_closed():
            try:
                async with self.bot.pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT user_id, guild_id, server_name FROM minigame_elite WHERE pending_processed = FALSE AND expires_at > EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)"
                    )

                for row in rows:
                    guild_id = row['guild_id']
                    user_id = row['user_id']

                    guild = await self.bot.fetch_guild(guild_id)
                    if not guild:
                        continue

                    try:
                        from commands.Events.helperFunctions import get_user_xp
                        current_xp = await get_user_xp(self.bot.pool, guild_id, user_id)

                        async with self.bot.pool.acquire() as conn:
                            enabled_rows = await conn.fetch(
                                "SELECT channel_id FROM minigame_settings WHERE minigames_enabled = TRUE"
                            )
                        enabled_ids = {r['channel_id'] for r in enabled_rows}
                        channel = None
                        for ch in guild.text_channels:
                            if ch.id in enabled_ids and ch.permissions_for(guild.me).send_messages:
                                channel = ch
                                break

                        if channel and current_xp > 0:
                            rewards_granted = await grant_elite_rewards_up_to_tier(
                                guild_id,
                                user_id,
                                channel,
                                current_xp,
                                client=self.bot,
                                pool=self.bot.pool
                            )

                            if rewards_granted:
                                user = await self.bot.fetch_user(user_id)
                                if user:
                                    try:
                                        rewards_message = "***You've received these elite rewards from previous tiers:***\n\n" + "\n".join(rewards_granted)
                                        await user.send(
                                            embed=discord.Embed(
                                                title="🎁 Elite Rewards Granted!",
                                                description=(
                                                    f"Your elite rewards have been processed for **{guild.name}**!\n\n"
                                                    f"{rewards_message}"
                                                ),
                                                color=0xfa0add
                                            )
                                        )
                                    except discord.Forbidden:
                                        pass

                        async with self.bot.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE minigame_elite SET pending_processed = TRUE WHERE user_id = $1 AND guild_id = $2",
                                user_id, guild_id
                            )

                        print(f"Processed pending elite activation for user {user_id} in guild {guild_id}")

                    except Exception as e:
                        print(f"Error processing pending activation: {e}")

            except Exception as e:
                print(f"Error in process_pending_activations: {e}")

            await asyncio.sleep(60)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.content.startswith("-addSub"):
            if message.author.id != 692254240290242601:
                await message.channel.send(f"{NO_EMOTE} You don't have permission to use this command.")
                return

            args = message.content.split()
            if len(args) != 4:
                await message.channel.send(f"{NO_EMOTE} Usage: `-addSub userID serverID timestamp`")
                return

            try:
                user_id = int(args[1])
                server_id = int(args[2])
                timestamp = float(args[3])
            except ValueError:
                await message.channel.send(f"{NO_EMOTE} Invalid arguments. Make sure IDs are numbers and timestamp is a float.")
                return

            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO minigame_elite (user_id, guild_id, expires_at, pending_processed)
                       VALUES ($1, $2, $3, TRUE)
                       ON CONFLICT (user_id, guild_id)
                       DO UPDATE SET expires_at = EXCLUDED.expires_at, pending_processed = TRUE""",
                    user_id, server_id, timestamp
                )

            user = await self.bot.fetch_user(user_id)
            server = await self.bot.fetch_guild(server_id)

            from commands.Events.helperFunctions import get_user_xp
            current_xp = await get_user_xp(self.bot.pool, server_id, user_id)

            rewards_granted = await grant_elite_rewards_up_to_tier(
                server_id,
                user_id,
                message.channel,
                current_xp,
                client=self.bot,
                pool=self.bot.pool
            )

            rewards_message = "***You've also automatically received these elite rewards from previous tiers:***\n\n" + "\n".join(rewards_granted) if rewards_granted else "⭐ *No elite rewards from previous tiers are automatically claimed.*"

            if user:
                try:
                    server_name = server.name if server else f"Server {server_id}"
                    await user.send(
                        embed=discord.Embed(
                            title=f"{MONEYDANCE_EMOTE} Elite Track Activated!",
                            description=(
                                f"🎉 You now have sweet perks in **{server_name}**! Enjoy friend!\n"
                                f"⏰ Expires on <t:{int(timestamp)}> (<t:{int(timestamp)}:R>)\n\n"
                                f"{rewards_message}"
                            ),
                            color=0xfa0add
                        )
                    )
                except discord.Forbidden:
                    pass

            await message.channel.send(f"{YES_EMOTE} Subscription added for <@{user_id}> in server `{server_id}`")

async def setup(bot):
    await bot.add_cog(EliteTrack(bot))