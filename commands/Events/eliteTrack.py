import discord
import asyncio

from discord.ext import commands
from firebase_admin import db

from commands.Events.trackData import grant_elite_rewards_up_to_tier, load_elite_subscriptions, save_elite_subscriptions

class EliteTrack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.subscriptions = load_elite_subscriptions()
        self.bot.loop.create_task(self.process_pending_activations())

    async def process_pending_activations(self): 
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                pending_ref = db.reference("/Elite Track Pending")
                all_pending = pending_ref.get() or {}
                
                for guild_id, pending_list in all_pending.items():
                    if not isinstance(pending_list, list):
                        continue

                    guild = await self.bot.fetch_guild(int(guild_id))
                    if not guild:
                        continue
                    
                    for i, pending in enumerate(pending_list):
                        if not isinstance(pending, dict):
                            continue
                            
                        user_id = pending.get('user_id')
                        if not user_id:
                            continue
                        
                        try:
                            progression_ref = db.reference(f"/Progression/{guild_id}/{user_id}")
                            progression_data = progression_ref.get() or {"xp": 0}
                            current_xp = progression_data.get("xp", 0)
                            
                            channel = guild.system_channel
                            if not channel:
                                for ch in guild.text_channels:
                                    if ch.permissions_for(guild.me).send_messages:
                                        channel = ch
                                        break
                            
                            if channel and current_xp > 0:
                                rewards_granted = await grant_elite_rewards_up_to_tier(
                                    int(guild_id), 
                                    user_id, 
                                    channel, 
                                    current_xp,
                                    client=self.bot
                                )
                                
                                if rewards_granted:
                                    user = await self.bot.fetch_user(user_id)
                                    if user:
                                        try:
                                            rewards_message = "***You've received these elite rewards from previous tiers:***\n" + "\n".join(rewards_granted)
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
                            
                            print(f"Processed pending elite activation for user {user_id} in guild {guild_id}")
                        
                        except Exception as e:
                            print(f"Error processing pending activation: {e}")
                    
                    db.reference(f"/Elite Track Pending/{guild_id}").delete()
                        
            except Exception as e:
                print(f"Error in process_pending_activations: {e}")
            
            await asyncio.sleep(60)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.content.startswith("-addSub"):
            if message.author.id != 692254240290242601:
                await message.channel.send("❌ You don't have permission to use this command.")
                return

            args = message.content.split()
            if len(args) != 4:
                await message.channel.send("Usage: `-addSub userID serverID timestamp`")
                return

            try:
                user_id = int(args[1])
                server_id = int(args[2])
                timestamp = float(args[3])
            except ValueError:
                await message.channel.send("❌ Invalid arguments. Make sure IDs are numbers and timestamp is a float.")
                return

            key = f"{user_id}-{server_id}"
            self.subscriptions[key] = {
                "user_id": user_id,
                "server_id": server_id,
                "expires_at": timestamp
            }
            save_elite_subscriptions(self.subscriptions)

            user = await self.bot.fetch_user(user_id)
            server = await self.bot.fetch_guild(server_id)
            
            progression_ref = db.reference(f"/Progression/{server_id}/{user_id}")
            progression_data = progression_ref.get() or {"xp": 0}
            current_xp = progression_data.get("xp", 0)

            rewards_granted = await grant_elite_rewards_up_to_tier(
                server_id, 
                user_id, 
                message.channel, 
                current_xp,
                client=self.bot
            )

            rewards_message = "***You've also automatically received these elite rewards from previous tiers:***\n" + "\n".join(rewards_granted) if rewards_granted else "⭐ *No elite rewards from previous tiers are automatically claimed.*"

            if user:
                try:
                    server_name = server.name if server else f"Server {server_id}"
                    await user.send(
                        embed=discord.Embed(
                            title="<a:moneydance:1227425759077859359> Elite Track Activated!",
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

            await message.channel.send(f"✅ Subscription added for <@{user_id}> in server `{server_id}`")
            
async def setup(bot):
    await bot.add_cog(EliteTrack(bot))