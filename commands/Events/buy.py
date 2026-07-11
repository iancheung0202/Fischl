import discord
import time
import datetime
import asyncio
import copy

from discord import app_commands
from discord.ext import commands
from commands.Events.helperFunctions import TierRewardsView, get_guild_mora, get_total_mora, subtractGuildMora, subtract_global_mora, add_inventory_item, get_user_inventory, apply_discount, get_shop_discount, get_shop_items, get_shop_item_by_name, process_pending_stock_edits as process_pending_stock_edits_helper, get_sigils_balance, get_global_sigils_balance, subtract_guild_sigils, subtract_global_sigils, update_shop_item_stock_by_name
from utils.commands import SlashCommand

from commands.Events.config import BALANCE_COMMAND, HMM_EMOTE, THINK_EMOTE, NO_STOCK_EMOTE, LOADING_EMOTE, SHRUG_EMOTE, HAPPY_EMOTE, CONFUSED_EMOTE, CURRENCY_INFO, MORA_TO_XP_RATIO, SIGILS_TO_XP_RATIO

global_purchase_queue = asyncio.Queue()

def get_currency_display(currency_type: str) -> str:
    info = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])
    return f"{info['emoji']}"

def format_discounted_price(original_cost: int, discounted_cost: int, discount_percent: int, currency_type: str = "guild_mora") -> str:
    currency_display = get_currency_display(currency_type)
    if discount_percent <= 0 or discounted_cost >= original_cost:
        return f"{currency_display} **{original_cost:,}**"
    return f"{currency_display} ~~**{original_cost:,}**~~ ➜ **{discounted_cost:,}** (-{discount_percent}%)"

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

async def process_pending_stock_edits(guild_id: int, pool=None):
    if pool is None:
        return 0
    return await process_pending_stock_edits_helper(pool, guild_id)

async def purchase_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    ref = await get_shop_items(interaction.client.pool, interaction.guild.id)
    rewards_data = ref
    choices = []

    if isinstance(rewards_data, dict):
        rewards = list(rewards_data.values())
    else:
        rewards = rewards_data

    for reward in rewards:
        if not isinstance(reward, (list, tuple)) or len(reward) < 3:
            continue

        reward_name = reward[0]
        reward_cost = reward[2]
        currency_type = reward[5] if len(reward) > 5 else "guild_mora"
        currency_label = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])["label"]

        if isinstance(reward_name, int) or str(reward_name).isdigit():
            role = interaction.guild.get_role(int(reward_name))
            display_name = f"Role: {role.name}" if role else "Unknown Role"
        else:
            display_name = reward_name

        choice_name = f"{display_name} ({reward_cost} {currency_label})"

        if current.lower() in str(reward_name).lower() or (
            (isinstance(reward_name, int) or str(reward_name).isdigit())
            and role
            and current.lower() in role.name.lower()
        ):
            choices.append(app_commands.Choice(name=choice_name[:100], value=str(reward_name)))

    return choices[:25]

class PurchaseRequest:
    __slots__ = ('interaction', 'itemName', 'timestamp')
    def __init__(self, interaction, itemName):
        self.interaction = interaction
        self.itemName = itemName
        self.timestamp = time.time()

async def check_balance(pool, uid, gid, amount, currency_type):
    if currency_type == "guild_mora":
        return await get_guild_mora(pool, uid, gid) >= amount
    elif currency_type == "global_mora":
        return await get_total_mora(pool, uid) >= amount
    elif currency_type == "guild_sigils":
        return await get_sigils_balance(pool, uid, gid) >= amount
    elif currency_type == "global_sigils":
        return await get_global_sigils_balance(pool, uid) >= amount
    return False

async def deduct_balance(pool, uid, gid, channel_id, amount, currency_type):
    if currency_type == "guild_mora":
        result = await subtractGuildMora(pool, uid, amount, channel_id, gid)
        return result is not False
    elif currency_type == "global_mora":
        return await subtract_global_mora(pool, uid, amount, channel_id, gid)
    elif currency_type == "guild_sigils":
        return await subtract_guild_sigils(pool, uid, gid, amount)
    elif currency_type == "global_sigils":
        return await subtract_global_sigils(pool, uid, gid, amount)
    return False

class ConfirmPurchaseView(discord.ui.View):
    def __init__(self, bot, itemName = "", allowed_user_id: int = None, currency_type: str = "guild_mora", discounted_cost: int = 0):
        self.bot = bot
        self.itemName = itemName
        self.allowed_user_id = allowed_user_id
        self.currency_type = currency_type
        self.discounted_cost = discounted_cost
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
            embed.set_footer(text=f"Purchase cancelled due to timeout")
            await current_message.edit(embed=embed, view=self)
        except (discord.NotFound, IndexError, AttributeError):
            pass

    async def process_purchase(self, request):
        interaction, itemName = request.interaction, request.itemName

        if (datetime.datetime.now(datetime.timezone.utc) - interaction.created_at).total_seconds() > 15 * 60 - 30:
            embed = discord.Embed(
                title="Purchase Expired",
                description="Your purchase request timed out. Please try again.",
                color=discord.Color.red()
            )
            return await interaction.edit_original_response(embed=embed)

        processed = await process_pending_stock_edits(interaction.guild.id, interaction.client.pool)
        if processed > 0:
            print(f"Processed {processed} scheduled stock updates for guild {interaction.guild.id}")
            await asyncio.sleep(1)

        roleName = self.itemName

        if interaction.guild.id == 1344543366372655164:
            async with interaction.client.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT title, description, timestamp FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND title = $3 ORDER BY timestamp DESC LIMIT 10",
                    interaction.user.id, interaction.guild.id, roleName
                )
                current_time = time.time()
                for row in rows:
                    desc = (row['description'] or '').lower()
                    if any(keyword in desc for keyword in ["welkin", "pass", "voucher", "nitro"]):
                        purchase_time = int(row['timestamp'].timestamp()) if hasattr(row['timestamp'], 'timestamp') else int(row['timestamp'])
                        if current_time - purchase_time < 60 * 60 * 24 * 45:
                            embed = discord.Embed(
                                title="<:keksweat:1381225834110652497> Miss Xianyun wants to give someone else a chance!",
                                description=f"You have already purchased **{roleName}** recently. You can only buy this item again <t:{int(60 * 60 * 24 * 45 + purchase_time)}:R>.",
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
                title=f"{HMM_EMOTE} Oops!",
                description=f"You already have the {gangRole.mention} role. Unlike some titles, you can only purchase roles **once**.",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return

        item_entry = await get_shop_item_by_name(interaction.client.pool, interaction.guild.id, roleName)
        if item_entry is None:
            embed = discord.Embed(
                title="Error",
                description="This item could not be found in the shop anymore.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return

        currency_type = item_entry[5] if len(item_entry) > 5 else "guild_mora"
        itemCost = int(item_entry[2])
        cannotBuyAgain = not (len(item_entry) > 3 and item_entry[3])

        is_mora_currency = currency_type in ("guild_mora", "global_mora")
        shop_discount = await get_shop_discount(interaction.client.pool, interaction.guild.id, interaction.user.id)
        discountedCost = apply_discount(itemCost, shop_discount)
        final_cost = discountedCost

        role_mention = (
            f"<@&{roleName}>"
            if isinstance(roleName, int) or roleName.isdigit()
            else roleName
        )

        if len(item_entry) > 4 and item_entry[4] == 0:
            embed = discord.Embed(
                title=f"{NO_STOCK_EMOTE} Out of Stock",
                description=f"**{role_mention}** has run out of stock! Ask an admin to restock.",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return

        has_balance = await check_balance(interaction.client.pool, interaction.user.id, interaction.guild.id, final_cost, currency_type)

        if not has_balance:
            currency_display = get_currency_display(currency_type)
            embed = discord.Embed(
                title=f"{SHRUG_EMOTE} Insufficient {currency_display}",
                description=f"You don't have enough {currency_display} for **{role_mention}**. Please check your balance using {SlashCommand(BALANCE_COMMAND)}.",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            if gangRole is not None:
                await interaction.user.add_roles(gangRole)

            inventory = await get_user_inventory(interaction.client.pool, interaction.user.id, interaction.guild.id)
            already_owns = any(item[0] == str(roleName) for item in inventory)

            if already_owns and cannotBuyAgain:
                embed = discord.Embed(
                    title=f"{HMM_EMOTE} Oops",
                    description=f"You already own **{role_mention}**! This title does not allow multiple purchases. If you believe this is a mistake, contact a server admin.",
                    color=discord.Color.red(),
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            title = item_entry[0]
            desc = item_entry[1]
            timestamp = int(time.mktime(datetime.datetime.now().timetuple()))

            await add_inventory_item(interaction.client.pool, interaction.user.id, interaction.guild.id, title, desc, final_cost, timestamp, pinned=False)
            await deduct_balance(interaction.client.pool, interaction.user.id, interaction.guild.id, interaction.channel.id, final_cost, currency_type)

            currency_display = get_currency_display(currency_type)
            xp_earned = ""
            if is_mora_currency:
                xp_ratio = MORA_TO_XP_RATIO
            else:
                xp_ratio = SIGILS_TO_XP_RATIO
            xp_earned = f"\n> {CONFUSED_EMOTE} You have also earned **`{int(final_cost * xp_ratio):,}` XP** from this purchase!"

            embed = discord.Embed(
                title=f"{HAPPY_EMOTE} Successful Purchase",
                description=(
                    f"Congratulations! You have paid {currency_display} **{final_cost:,}** and now own **{role_mention}**. {xp_earned}"
                ),
                color=discord.Color.green(),
            )

            from commands.Events.event import add_xp
            from commands.Events.trackData import check_tier_rewards
            from commands.Events.quests import update_quest

            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"purchase_items": 1}, interaction.client)

            tier, old_xp, new_xp = await add_xp(interaction.user.id, interaction.guild.id, int(final_cost * xp_ratio), interaction.client)
            print(f"Added {int(final_cost * xp_ratio)} XP from purchase.")
            free_embed, elite_embed = await check_tier_rewards(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                old_xp=old_xp,
                new_xp=new_xp,
                channel=interaction.channel,
                client=interaction.client,
                pool=interaction.client.pool
            )
            await interaction.edit_original_response(embed=embed, view=TierRewardsView(free_embed, elite_embed) if xp_earned != "" else None)

            items = await get_shop_items(interaction.client.pool, interaction.guild.id)
            og_item = None
            for it in items:
                if it[0] == roleName:
                    og_item = it
                    break
            if og_item and len(og_item) > 4 and og_item[4] > 0:
                new_stock = og_item[4] - 1
                await update_shop_item_stock_by_name(interaction.client.pool, interaction.guild.id, roleName, new_stock)

            link = (await interaction.original_response()).jump_url
            print(f"{interaction.user.name} ({interaction.user.id}) have paid {final_cost:,} {currency_type} and now own {role_mention} in {interaction.guild.name} ({interaction.guild.id}) → {link}")

            try:
                async with interaction.client.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE minigame_inventory SET link = $3 WHERE uid = $1 AND gid = $2 AND title = $4 AND timestamp = $5",
                        interaction.user.id, interaction.guild.id, link, str(roleName), timestamp
                    )
                print(f"Logged purchase link to minigame_inventory for user {interaction.user.id} in guild {interaction.guild.id}")
            except Exception as e:
                print(f"Error logging purchase link: {e}")

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
                description=f"Your purchase is in queue. Please wait while we validate your purchase {LOADING_EMOTE}",
                color=discord.Color.orange()
            )
            await interaction.edit_original_response(embed=embed)
        else:
            processing_embed = discord.Embed(
                title="Processing Purchase",
                description=f"Validating your purchase {LOADING_EMOTE}",
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

        rewards = await get_shop_items(interaction.client.pool, interaction.guild.id)

        found_item = None
        for i in rewards:
            if i[0] == item:
                found_item = i
                break

        if found_item is None:
            embed = discord.Embed(
                title="Error",
                description=f"{interaction.user.mention}, **{item}** is not a valid item!",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        itemCost = int(found_item[2])
        currency_type = found_item[5] if len(found_item) > 5 else "guild_mora"
        currency_display = get_currency_display(currency_type)

        role_mention = (
            f"<@&{item}>" if isinstance(item, int) or item.isdigit() else item
        )

        shop_discount = await get_shop_discount(interaction.client.pool, interaction.guild.id, interaction.user.id)

        if shop_discount > 0:
            discounted_cost = apply_discount(itemCost, shop_discount) 
            purchase_price_text = format_discounted_price(itemCost, discounted_cost, shop_discount, currency_type)
            purchase_description = (
                f"Are you sure you want to purchase **{role_mention}** for {purchase_price_text}?"
            )
        else:
            discounted_cost = itemCost
            purchase_description = f"Are you sure you want to purchase **{role_mention}** for {currency_display} **{itemCost:,}**?"

        embed = discord.Embed(
            title=f"{THINK_EMOTE} Confirm Purchase",
            description=purchase_description,
            color=discord.Color.gold()
        )
        embed.set_footer(text="Purchase buttons will timeout in 30 seconds")
        view = ConfirmPurchaseView(self.bot, item, interaction.user.id, currency_type, discounted_cost)
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