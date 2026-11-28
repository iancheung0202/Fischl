import asyncio
import datetime
import time

import discord
from discord import app_commands
from discord.ext import commands

from commands.Events.config import (
    BALANCE_COMMAND,
    CONFUSED_EMOTE,
    CURRENCY_INFO,
    HAPPY_EMOTE,
    HMM_EMOTE,
    LOADING_EMOTE,
    MORA_TO_XP_RATIO,
    NO_STOCK_EMOTE,
    SHRUG_EMOTE,
    SIGILS_TO_XP_RATIO,
    THINK_EMOTE,
)
from commands.Events.helperFunctions import (
    TierRewardsView,
    add_inventory_item,
    apply_discount,
    get_global_sigils_balance,
    get_guild_mora,
    get_shop_discount,
    get_shop_item_by_name,
    get_shop_items,
    get_sigils_balance,
    get_total_mora,
    get_user_inventory,
    process_pending_stock_edits,
    subtract_global_mora,
    subtract_global_sigils,
    subtract_guild_sigils,
    subtractGuildMora,
    update_shop_item_stock_by_name,
)
from utils.commands import SlashCommand

XIANYUN = 1344543366372655164
REBUY_WAIT = 60 * 60 * 24 * 45
LIMITED_WORDS = ("welkin", "pass", "voucher", "nitro")
EXPIRES_AFTER = 15 * 60 - 30

global_purchase_queue = asyncio.Queue()


def get_currency_display(currency_type: str) -> str:
    """Gives the emoji of a currency, Mora's when the currency is unknown."""
    return CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])["emoji"]


def format_discounted_price(
    original_cost: int,
    discounted_cost: int,
    discount_percent: int,
    currency_type: str = "guild_mora",
) -> str:
    """Writes a price, with the old one struck through when a discount lowers it."""
    currency_display = get_currency_display(currency_type)
    if discount_percent <= 0 or discounted_cost >= original_cost:
        return f"{currency_display} **{original_cost:,}**"
    return f"{currency_display} ~~**{original_cost:,}**~~ ➜ **{discounted_cost:,}** (-{discount_percent}%)"


def mention(name: str) -> str:
    """Writes an item as a role mention when its name is a role ID."""
    return f"<@&{name}>" if name.isdigit() else name


async def purchase_worker():
    """Handles queued purchases one at a time."""
    while True:
        interaction, future, process_func = await global_purchase_queue.get()
        try:
            await process_func(interaction)
            if not future.done():
                future.set_result(None)
        except Exception as e:
            print(f"Error in purchase worker: {e}")
            if not future.done():
                future.set_exception(e)
        finally:
            global_purchase_queue.task_done()


async def purchase_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    """Suggests shop items whose name, or role name, contains what was typed."""
    choices = []
    for reward in await get_shop_items(interaction.client.pool, interaction.guild.id):
        name = str(reward[0])
        role = interaction.guild.get_role(int(name)) if name.isdigit() else None
        if name.isdigit():
            display_name = f"Role: {role.name}" if role else "Unknown Role"
        else:
            display_name = name
        label = CURRENCY_INFO.get(reward[5], CURRENCY_INFO["guild_mora"])["label"]
        if current.lower() in name.lower() or (
            role and current.lower() in role.name.lower()
        ):
            choices.append(
                app_commands.Choice(
                    name=f"{display_name} ({reward[2]} {label})"[:100], value=name
                )
            )
    return choices[:25]


async def check_balance(pool, uid, gid, amount, currency_type):
    """Says whether the member can pay `amount` in the given currency."""
    if currency_type == "guild_mora":
        return await get_guild_mora(pool, uid, gid) >= amount
    if currency_type == "global_mora":
        return await get_total_mora(pool, uid) >= amount
    if currency_type == "guild_sigils":
        return await get_sigils_balance(pool, uid, gid) >= amount
    if currency_type == "global_sigils":
        return await get_global_sigils_balance(pool, uid) >= amount
    return False


async def deduct_balance(pool, uid, gid, channel_id, amount, currency_type):
    """Takes `amount` of the given currency from the member."""
    if currency_type == "guild_mora":
        return await subtractGuildMora(pool, uid, amount, channel_id, gid) is not False
    if currency_type == "global_mora":
        return await subtract_global_mora(pool, uid, amount, channel_id, gid)
    if currency_type == "guild_sigils":
        return await subtract_guild_sigils(pool, uid, gid, amount)
    if currency_type == "global_sigils":
        return await subtract_global_sigils(pool, uid, gid, amount)
    return False


async def refuse(interaction, title, description):
    """Replaces the purchase message with a red notice."""
    embed = discord.Embed(
        title=title, description=description, color=discord.Color.red()
    )
    await interaction.edit_original_response(embed=embed, view=None)


async def next_rebuy_time(interaction, name):
    """Gives when a limited Xianyun item can be bought again, None when it can be now."""
    async with interaction.client.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT title, description, timestamp FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND title = $3 ORDER BY timestamp DESC LIMIT 10",
            interaction.user.id,
            interaction.guild.id,
            name,
        )
    current_time = time.time()
    for row in rows:
        desc = (row["description"] or "").lower()
        if not any(keyword in desc for keyword in LIMITED_WORDS):
            continue
        bought = row["timestamp"]
        bought = int(bought.timestamp() if hasattr(bought, "timestamp") else bought)
        if current_time - bought < REBUY_WAIT:
            return REBUY_WAIT + bought
    return None


async def lower_stock(interaction, name):
    """Takes one off the item's stock when it has a limited stock left."""
    items = await get_shop_items(interaction.client.pool, interaction.guild.id)
    item = next((it for it in items if it[0] == name), None)
    if item and len(item) > 4 and item[4] > 0:
        await update_shop_item_stock_by_name(
            interaction.client.pool, interaction.guild.id, name, item[4] - 1
        )


async def save_link(interaction, link, name, timestamp):
    """Stores the purchase message's link with the bought item."""
    try:
        async with interaction.client.pool.acquire() as conn:
            await conn.execute(
                "UPDATE minigame_inventory SET link = $3 WHERE uid = $1 AND gid = $2 AND title = $4 AND timestamp = $5",
                interaction.user.id,
                interaction.guild.id,
                link,
                name,
                timestamp,
            )
        print(
            f"Logged purchase link to minigame_inventory for user {interaction.user.id} in guild {interaction.guild.id}"
        )
    except Exception as e:
        print(f"Error logging purchase link: {e}")


async def reward_purchase(interaction, embed, xp):
    """Counts the purchase for quests, pays its XP and shows the result."""
    from commands.Events.games.common import add_xp
    from commands.Events.quests import update_quest
    from commands.Events.trackData import check_tier_rewards

    await update_quest(
        interaction.user.id,
        interaction.guild.id,
        interaction.channel.id,
        {"purchase_items": 1},
        interaction.client,
    )
    _, old_xp, new_xp = await add_xp(
        interaction.user.id, interaction.guild.id, xp, interaction.client
    )
    print(f"Added {xp} XP from purchase.")
    free_embed, elite_embed = await check_tier_rewards(
        guild_id=interaction.guild.id,
        user_id=interaction.user.id,
        old_xp=old_xp,
        new_xp=new_xp,
        channel=interaction.channel,
        client=interaction.client,
        pool=interaction.client.pool,
    )
    await interaction.edit_original_response(
        embed=embed, view=TierRewardsView(free_embed, elite_embed)
    )


class ConfirmPurchaseView(discord.ui.View):
    def __init__(self, itemName="", allowed_user_id: int = None):
        self.itemName = itemName
        self.allowed_user_id = allowed_user_id
        super().__init__(timeout=30)

    async def on_timeout(self):
        """Greys out the buttons if the purchase was never confirmed."""
        try:
            current_message = await self.message.channel.fetch_message(self.message.id)
            current_embed = current_message.embeds[0]
            if "Confirm Purchase" not in current_embed.title:
                return
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            embed = current_embed.copy()
            embed.set_footer(text="Purchase cancelled due to timeout")
            await current_message.edit(embed=embed, view=self)
        except (discord.NotFound, IndexError, AttributeError):
            pass

    async def process_purchase(self, interaction):
        """Checks the purchase, then gives the item and takes the payment."""
        pool, user, guild = interaction.client.pool, interaction.user, interaction.guild
        age = datetime.datetime.now(datetime.timezone.utc) - interaction.created_at
        if age.total_seconds() > EXPIRES_AFTER:
            embed = discord.Embed(
                title="Purchase Expired",
                description="Your purchase request timed out. Please try again.",
                color=discord.Color.red(),
            )
            return await interaction.edit_original_response(embed=embed)

        processed = await process_pending_stock_edits(pool, guild.id)
        if processed > 0:
            print(f"Processed {processed} scheduled stock updates for guild {guild.id}")
            await asyncio.sleep(1)

        name = self.itemName
        if guild.id == XIANYUN:
            again = await next_rebuy_time(interaction, name)
            if again is not None:
                return await refuse(
                    interaction,
                    "<:keksweat:1381225834110652497> Miss Xianyun wants to give someone else a chance!",
                    f"You have already purchased **{name}** recently. You can only buy this item again <t:{again}:R>.",
                )

        try:
            role = guild.get_role(int(name))
        except Exception:
            role = None
        if role is not None and role in user.roles:
            return await refuse(
                interaction,
                f"{HMM_EMOTE} Oops!",
                f"You already have the {role.mention} role. Unlike some titles, you can only purchase roles **once**.",
            )

        item = await get_shop_item_by_name(pool, guild.id, name)
        if item is None:
            return await refuse(
                interaction,
                "Error",
                "This item could not be found in the shop anymore.",
            )

        currency_type = item[5] if len(item) > 5 else "guild_mora"
        cost = apply_discount(
            int(item[2]), await get_shop_discount(pool, guild.id, user.id)
        )
        currency_display = get_currency_display(currency_type)

        if len(item) > 4 and item[4] == 0:
            return await refuse(
                interaction,
                f"{NO_STOCK_EMOTE} Out of Stock",
                f"**{mention(name)}** has run out of stock! Ask an admin to restock.",
            )

        if not await check_balance(pool, user.id, guild.id, cost, currency_type):
            return await refuse(
                interaction,
                f"{SHRUG_EMOTE} Insufficient {currency_display}",
                f"You don't have enough {currency_display} for **{mention(name)}**. Please check your balance using {SlashCommand(BALANCE_COMMAND)}.",
            )

        if role is not None:
            await user.add_roles(role)

        inventory = await get_user_inventory(pool, user.id, guild.id)
        if any(owned[0] == name for owned in inventory) and not (
            len(item) > 3 and item[3]
        ):
            return await refuse(
                interaction,
                f"{HMM_EMOTE} Oops",
                f"You already own **{mention(name)}**! This title does not allow multiple purchases. If you believe this is a mistake, contact a server admin.",
            )

        timestamp = int(time.mktime(datetime.datetime.now().timetuple()))
        timestamp = await add_inventory_item(
            pool, user.id, guild.id, item[0], item[1], cost, timestamp, pinned=False
        )
        await deduct_balance(
            pool, user.id, guild.id, interaction.channel.id, cost, currency_type
        )

        if currency_type in ("guild_mora", "global_mora"):
            xp = int(cost * MORA_TO_XP_RATIO)
        else:
            xp = int(cost * SIGILS_TO_XP_RATIO)
        embed = discord.Embed(
            title=f"{HAPPY_EMOTE} Successful Purchase",
            description=(
                f"Congratulations! You have paid {currency_display} **{cost:,}** and now own **{mention(name)}**. "
                f"\n> {CONFUSED_EMOTE} You have also earned **`{xp:,}` XP** from this purchase!"
            ),
            color=discord.Color.green(),
        )
        await reward_purchase(interaction, embed, xp)
        await lower_stock(interaction, name)
        link = (await interaction.original_response()).jump_url
        print(
            f"{user.name} ({user.id}) have paid {cost:,} {currency_type} and now own {mention(name)} in {guild.name} ({guild.id}) → {link}"
        )
        await save_link(interaction, link, name, timestamp)

    @discord.ui.button(label="Purchase Item", style=discord.ButtonStyle.green)
    async def purchaseItem(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message(
                "You can't perform this action.", ephemeral=True
            )
            return

        try:
            await interaction.response.defer()
        except discord.NotFound:
            return
        await interaction.edit_original_response(view=None)

        if global_purchase_queue.qsize() > 0:
            embed = discord.Embed(
                title="Purchase Queued",
                description=f"Your purchase is in queue. Please wait while we validate your purchase {LOADING_EMOTE}",
                color=discord.Color.orange(),
            )
        else:
            embed = discord.Embed(
                title="Processing Purchase",
                description=f"Validating your purchase {LOADING_EMOTE}",
                color=discord.Color.gold(),
            )
        await interaction.edit_original_response(embed=embed)

        future = asyncio.get_running_loop().create_future()
        await global_purchase_queue.put((interaction, future, self.process_purchase))
        await future

    @discord.ui.button(
        label="Cancel", style=discord.ButtonStyle.grey, custom_id="cancelbuy"
    )
    async def cancelItem(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message(
                "You can't perform this action.", ephemeral=True
            )
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
        found_item = next((reward for reward in rewards if reward[0] == item), None)
        if found_item is None:
            embed = discord.Embed(
                title="Error",
                description=f"{interaction.user.mention}, **{item}** is not a valid item!",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        cost = int(found_item[2])
        discount = await get_shop_discount(
            interaction.client.pool, interaction.guild.id, interaction.user.id
        )
        price = format_discounted_price(
            cost, apply_discount(cost, discount), discount, found_item[5]
        )
        embed = discord.Embed(
            title=f"{THINK_EMOTE} Confirm Purchase",
            description=f"Are you sure you want to purchase **{mention(item)}** for {price}?",
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Purchase buttons will timeout in 30 seconds")
        view = ConfirmPurchaseView(item, interaction.user.id)
        view.message = await interaction.followup.send(embed=embed, view=view)

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
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Buy(bot))
