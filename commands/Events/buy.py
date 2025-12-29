import discord
import time
import datetime
import asyncio

from discord import app_commands
from discord.ext import commands
from firebase_admin import db

MORA_EMOTE = "<:MORA:1364030973611610205>"

global_purchase_queue = asyncio.Queue()

async def purchase_worker():
    while True:
        request, future, process_func = await global_purchase_queue.get()
        try:
            await process_func(request)
            if not future.done():
                future.set_result(None)
        except Exception as e:
            print(f"Error in purchase worker: {e}")
            if not future.done():
                future.set_exception(e)
        finally:
            global_purchase_queue.task_done()

async def process_pending_stock_edits(guild_id: int):
    current_time = time.time()
    ref = db.reference(f"/Pending Shop Edits/{guild_id}")
    pending_edits = ref.get() or {}
    
    processed_count = 0
    for key, edit in list(pending_edits.items()):
        scheduled_time = edit.get('scheduled_time', 0)
        
        if scheduled_time > current_time:
            continue
        
        guild_ref = db.reference("/Global Events Rewards")
        guild_rewards = guild_ref.get() or {}
        rewards_list = None
        guild_key = None
        
        for gkey, gval in guild_rewards.items():
            if gval["Server ID"] == guild_id:
                rewards_list = gval["Rewards"]
                guild_key = gkey
                break
        
        if not rewards_list:
            ref.child(key).delete()
            continue
            
        for i, reward in enumerate(rewards_list):
            if len(reward) < 5:
                rewards_list[i] = reward + [-1]
        
        item_found = False
        for i, item in enumerate(rewards_list):
            if item[0] == edit['item_identifier']:
                current_stock = item[4]
                stock_change = edit['stock_change']
                
                if stock_change.startswith(('+', '-')):
                    if current_stock == -1:
                        current_stock = 0
                    
                    try:
                        change = int(stock_change)
                        new_stock = current_stock + change
                    except ValueError:
                        sign = stock_change[0]
                        num_str = stock_change[1:].strip()
                        if not num_str:
                            num = 0
                        else:
                            num = int(num_str)
                        new_stock = current_stock + num if sign == '+' else current_stock - num
                else:
                    try:
                        new_stock = int(stock_change)
                    except ValueError:
                        continue
                
                if new_stock < 0:
                    new_stock = 0
                
                rewards_list[i][4] = new_stock
                item_found = True
                print(f"Updated stock for {item[0]} from {current_stock} to {new_stock}")
                break
        
        if item_found:
            guild_ref.child(guild_key).update({"Rewards": rewards_list})
            processed_count += 1
        else:
            continue
        
        ref.child(key).delete()
    
    return processed_count

async def purchase_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    ref = db.reference("/Global Events Rewards")
    daily = ref.get()
    rewards = []
    choices = []
    for key, val in daily.items():
        if val["Server ID"] == interaction.guild.id:
            rewards = val["Rewards"]
            break

    for reward in rewards:
        reward_name = reward[0]
        reward_cost = reward[2]

        if isinstance(reward_name, int) or reward_name.isdigit():
            role = interaction.guild.get_role(int(reward_name))
            display_name = f"Role: {role.name}" if role else "Unknown Role"
        else:
            display_name = reward_name

        choice_name = f"{display_name} (Cost: {reward_cost})"

        if current.lower() in reward_name.lower() or (
            isinstance(reward_name, int)
            or reward_name.isdigit()
            and role
            and current.lower() in role.name.lower()
        ):
            choices.append(app_commands.Choice(name=choice_name, value=reward_name))

    return choices[:25]

class PurchaseRequest:
    __slots__ = ('interaction', 'itemName', 'timestamp')
    def __init__(self, interaction, itemName):
        self.interaction = interaction
        self.itemName = itemName
        self.timestamp = time.time()

class ConfirmPurchaseView(discord.ui.View):
    def __init__(self, bot, itemName = "", allowed_user_id: int = None):
        self.bot = bot
        self.itemName = itemName
        self.allowed_user_id = allowed_user_id 
        super().__init__(timeout=30)

    async def on_timeout(self):
        try:
            current_message = await self.message.channel.fetch_message(self.message.id)
            current_embed = current_message.embeds[0]
            
            if "Confirm Purchase" not in current_embed.title:
                return
                
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            
            embed = current_embed.copy()
            embed.set_footer(text="❌ Purchase cancelled due to timeout")
            await current_message.edit(embed=embed, view=self)
        except (discord.NotFound, IndexError, AttributeError):
            pass

    async def process_purchase(self, request):
        interaction, itemName = request.interaction, request.itemName
        
        if (datetime.datetime.now(datetime.timezone.utc) - interaction.created_at).total_seconds() > 15 * 60 - 30: # Still processing purchase after 15 minutes
            embed = discord.Embed(
                title="Purchase Expired",
                description="Your purchase request timed out. Please try again.",
                color=discord.Color.red()
            )
            return await interaction.edit_original_response(embed=embed)
        
        processed = await process_pending_stock_edits(interaction.guild.id)
        if processed > 0:
            print(f"Processed {processed} scheduled stock updates for guild {interaction.guild.id}")
            await asyncio.sleep(1)  # Give a moment for DB to stabilize
        
        roleName = self.itemName

        if interaction.guild.id == 1344543366372655164:  # Xianyun's Hangout
            history_ref = db.reference(f"/Mora Purchase History/{interaction.guild.id}/{interaction.user.id}")
            history_snapshot = history_ref.order_by_key().limit_to_last(10).get()
            
            if history_snapshot:
                current_time = time.time()
                for key, val in history_snapshot.items():
                    if val.get('item_name') == roleName:
                        purchase_time = val.get('timestamp', 0)
                        if current_time - purchase_time < 60 * 60 * 24 * 45: # 45 days
                            embed = discord.Embed(
                                title="<:keksweat:1381225834110652497> Miss Xianyun wants to give someone else a chance!",
                                description=f"You have already purchased **{roleName}** recently. You can only buy this item again in <t:{int(60 +  purchase_time)}:R>.",
                                color=discord.Color.red()
                            )
                            await interaction.edit_original_response(embed=embed, view=None)
                            return

        try:
            gangRole = interaction.guild.get_role(int(roleName))
        except Exception:
            gangRole = None
        if gangRole is not None and gangRole in interaction.user.roles:
            embed = discord.Embed(
                title="<:DW_elhmm:971735422147379200> Oops!",
                description=f"You already have the {gangRole.mention} role. Unlike some titles, you can only purchase roles **once**.",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return

        ref = db.reference("/Global Events Rewards")
        daily = ref.get()
        rewards = []
        for key, val in daily.items():
            if val["Server ID"] == interaction.guild.id:
                rewards = val["Rewards"]
                break

        x = 0
        for i in rewards:
            if i[0] == roleName:
                break
            x += 1
        itemCost = int(rewards[x][2])
        import copy
        ogRewards = copy.deepcopy(rewards)

        cannotBuyAgain = False
        if not (len(rewards[x]) > 3 and rewards[x][3]):
            cannotBuyAgain = True
        
        user_key = str(interaction.user.id)
        guild_key = str(interaction.guild.id)
        channel_key = str(interaction.channel.id)

        base_ref = db.reference(f"/Mora/{user_key}/{guild_key}")
        channels = base_ref.get() or {}  # {channel_id: {timestamp: amount}}

        entries = [
            amt for chan in channels.values()
            for amt in chan.values()
        ]
        total_available = sum(entries)
        
        role_mention = (
            f"<@&{roleName}>"
            if isinstance(roleName, int) or roleName.isdigit()
            else roleName
        )
                
        if len(rewards[x]) > 4 and rewards[x][4] == 0:
            embed = discord.Embed(
                title="<a:out_of_stock:1384990609584033812> Out of Stock",
                description=f"**{role_mention}** has run out of stock! Ask an admin to restock.",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        if itemCost > total_available:
            embed = discord.Embed(
                title="<:WrioShrug:1304094173795713114> Insufficient Mora",
                description=f"We couldn't assign you **{role_mention}**. Please check your mora balance using </mora:1339721187953082543> to confirm if you have enough guild-specific mora for this purchase.",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            if gangRole is not None:
                await interaction.user.add_roles(gangRole)

            ref = db.reference("/User Events Inventory")
            inventories = ref.get()
            inv = []
            found = False
            foundKey = None
            if inventories:
                for key, val in inventories.items():
                    if val["User ID"] == interaction.user.id:
                        try:
                            inv = val["Items"]
                            for item in inv:
                                if item[0] == roleName:
                                    found = True
                            foundKey = key
                        except Exception as e:
                            print(e)

                    if found and cannotBuyAgain:
                        role_mention = (
                            f"<@&{roleName}>"
                            if isinstance(roleName, int) or roleName.isdigit()
                            else roleName
                        )
                        embed = discord.Embed(
                            title="Oops",
                            description=f"You already own **{role_mention}**! This title does not allow multiple purchases. If you believe this is a mistake, contact a server admin.",
                            color=discord.Color.red(),
                        )
                        await interaction.edit_original_response(embed=embed, view=None)
                        return


            if foundKey is not None:
                db.reference("/User Events Inventory").child(foundKey).delete()

            rewards[x].pop()
            if isinstance(rewards[x][-1], bool):
                rewards[x].pop()
            rewards[x].append(interaction.guild.id) 
            rewards[x].append(
                int(time.mktime(datetime.datetime.now().timetuple()))
            )
            inv.append(rewards[x])

            data = {
                interaction.user.id: {
                    "User ID": interaction.user.id,
                    "Items": inv,
                }
            }

            for key, value in data.items():
                ref.push().set(value)
                
            timestamp = str(int(time.time()))
            subtract_ref = db.reference(f"/Mora/{user_key}/{guild_key}/{channel_key}/{timestamp}")
            subtract_ref.set(-itemCost)
            
            xp_earned = f"\n> <:PinkConfused:1204614149628498010> You have also earned **`{int(itemCost/100):,}` XP** from this purchase!"
                
            embed = discord.Embed(
                title="<a:NekoHappy:1335019855920758855> Successful Purchase",
                description=f"Congratulations! You have paid {MORA_EMOTE} **{itemCost:,}** and now own **{role_mention}**. {xp_earned}",
                color=discord.Color.green(),
            )

            from commands.Events.helperFunctions import TierRewardsView
            from commands.Events.event import add_xp
            from commands.Events.trackData import check_tier_rewards
            from commands.Events.quests import update_quest

            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"purchase_items": 1}, interaction.client)
            tier, old_xp, new_xp = await add_xp(interaction.user.id, interaction.guild.id, int(itemCost / 100), interaction.client)
            print(f"Added {int(itemCost/100)} XP from purchase.")
            free_embed, elite_embed = await check_tier_rewards(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                old_xp=old_xp,
                new_xp=new_xp,
                channel=interaction.channel,
                client=interaction.client
            )
            await interaction.edit_original_response(embed=embed, view=TierRewardsView(free_embed, elite_embed) if xp_earned != "" else None)
            
            if len(ogRewards[x]) > 4 and ogRewards[x][4] > 0:
                ref = db.reference("/Global Events Rewards")
                ogRewards[x][4] -= 1
                try:
                    for key, val in daily.items():
                        if val["Server ID"] == interaction.guild.id:
                            db.reference("/Global Events Rewards").child(key).delete()
                            break
                except Exception:
                    pass
                data = {
                    interaction.guild.id: {
                        "Server ID": interaction.guild.id,
                        "Rewards": ogRewards,
                    }
                }
                for key, value in data.items():
                    ref.push().set(value)
                
            link = (await interaction.original_response()).jump_url
            print(f"{interaction.user.name} ({interaction.user.id}) have paid {itemCost:,} Mora and now own {role_mention} in {interaction.guild.name} ({interaction.guild.id}) → {link}")

            try:
                purchase_timestamp = int(time.time())
                purchase_history_ref = db.reference(f"/Mora Purchase History/{interaction.guild.id}/{interaction.user.id}")
                purchase_id = f"purchase_{purchase_timestamp}_{interaction.user.id}"
                
                item_name = roleName
                item_description = rewards[x][1] if len(rewards[x]) > 1 else ""
                
                purchase_data = {
                    "item_name": item_name,
                    "item_description": item_description,
                    "cost": itemCost,
                    "timestamp": purchase_timestamp,
                    "link": link
                }
                
                purchase_history_ref.child(purchase_id).set(purchase_data)
                print(f"Logged purchase to history: {purchase_id} for user {interaction.user.id} in guild {interaction.guild.id}")
            except Exception as e:
                print(f"Error logging purchase to history: {e}")

    @discord.ui.button(label="Purchase Item", style=discord.ButtonStyle.green)
    async def purchaseItem(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message("You can't perform this action.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
        except discord.NotFound:
            return
        await interaction.edit_original_response(view=None)

        request = PurchaseRequest(interaction, self.itemName)
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        if global_purchase_queue.qsize() > 0:
            embed = discord.Embed(
                title="Purchase Queued",
                description=f"Your purchase is in queue. Please wait while we validate your purchase <a:loading:1026905298088243240>",
                color=discord.Color.orange()
            )
            await interaction.edit_original_response(embed=embed)
        else:
            processing_embed = discord.Embed(
                title="Processing Purchase",
                description="Validating your purchase <a:loading:1026905298088243240>",
                color=discord.Color.gold()
            )
            await interaction.edit_original_response(embed=processing_embed)

        await global_purchase_queue.put((request, future, self.process_purchase))
        await future

    @discord.ui.button(
        label="Cancel", style=discord.ButtonStyle.grey, custom_id="cancelbuy"
    )
    async def cancelItem(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message("You can't perform this action.", ephemeral=True)
            return
        await interaction.message.delete()


class Buy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.worker_task = None

    async def cog_load(self):
        self.worker_task = self.bot.loop.create_task(purchase_worker())

    async def cog_unload(self):
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    @app_commands.command(
        name="buy", description="Purchase an item from the guild shop"
    )
    @app_commands.describe(item="The item you wish to purchase")
    @app_commands.autocomplete(item=purchase_autocomplete)
    @app_commands.checks.cooldown(1, 10.0, key=lambda interaction: interaction.user.id)
    async def buy(self, interaction: discord.Interaction, item: str) -> None:
        await interaction.response.defer(thinking=True)
            
        ref = db.reference("/Global Events Rewards")
        daily = ref.get()
        rewards = []
        for key, val in daily.items():
            if val["Server ID"] == interaction.guild.id:
                rewards = val["Rewards"]
                break

        x = 0
        for i in rewards:
            if i[0] == item:
                break
            x += 1

        try:
            itemCost = int(rewards[x][2])
        except Exception:
            embed = discord.Embed(
                title="Error",
                description=f"{interaction.user.mention}, **{item}** is not a valid item!",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        role_mention = (
            f"<@&{item}>" if isinstance(item, int) or item.isdigit() else item
        )
        embed = discord.Embed(
            title="<:Paimon_Think:1414561896299888700> Confirm Purchase",
            description=f"Are you sure you want to purchase **{role_mention}** for {MORA_EMOTE} **{itemCost:,}**?",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Purchase buttons will timeout in 30 seconds")
        view = ConfirmPurchaseView(self.bot, item, interaction.user.id)
        view.message = await interaction.followup.send(
            embed=embed, view=view
        )
    @buy.error
    async def buy_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="Cooldown",
                description=f"You're on cooldown. Please try this command again in {error.retry_after:.2f} seconds.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Error",
                description=f"An unexpected error occurred. Please try again later.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            raise error
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Buy(bot))