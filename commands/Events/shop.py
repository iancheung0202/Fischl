"""The server shop: the /shop list, and the screens admins edit its rewards with."""

import time

import discord
from discord import app_commands
from discord.ext import commands

from commands.Events.config import (
    BALANCE_COMMAND,
    CURRENCY_INFO,
    NO_EMOTE,
    NO_STOCK_EMOTE,
    REPLY_EMOTE,
    SHOP_CURRENCY_FILTERS,
    SHOP_SORT_OPTIONS,
    YES_EMOTE,
)
from commands.Events.helperFunctions import (
    add_pending_edit,
    add_shop_item,
    get_shop_item_by_name,
    get_shop_items,
    process_pending_stock_edits,
    remove_shop_item_by_name,
    update_shop_item_cost,
    update_shop_item_field,
    update_shop_item_stock_by_name,
)
from utils.commands import SlashCommand
from utils.pagination import BasePaginationView, BaseSortSelect

# A reward is [name, description, cost, multiple, stock, currency, pending stock, pending time];
# the name is a title or a role ID, and a stock of -1 means unlimited.
DEFAULT_SORT = "sort by cost (high to low)"
SORTS = {
    "sort by cost (low to high)": ("cost", False),
    DEFAULT_SORT: ("cost", True),
    "sort by name (a-z)": ("name", False),
    "sort by name (z-a)": ("name", True),
}
MULTIPLIERS = {"k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12}
# What each edit button opens: the button and box title, the box label, the longest text, if it must be filled.
FIELDS = {
    "name": ("Edit Name", "Role ID / Reward Title", 50, True),
    "description": ("Edit Description", "Description / Perk", 150, True),
    "cost": ("Edit Cost", "Cost of Reward", 10, True),
    "stock": ("Edit Stock", "Stock Value", 20, False),
}


def get_currency_display(currency_type: str) -> str:
    """Gives the emoji of a currency, Mora's when the currency is unknown."""
    return CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])["emoji"]


def parse_cost(cost_str: str) -> int:
    """Reads a cost such as `1500`, `1.5k` or `2m` as a whole number."""
    cost_lower = cost_str.lower().strip()
    if cost_lower[-1] in MULTIPLIERS:
        return int(float(cost_lower[:-1]) * MULTIPLIERS[cost_lower[-1]])
    return int(float(cost_lower))


def currency_of(item) -> str:
    """Gives the currency a reward is paid in."""
    return item[5] if len(item) > 5 else "guild_mora"


def is_role(name) -> bool:
    """Says whether a reward's name is a role ID."""
    return isinstance(name, int) or str(name).isdigit()


def shop_page(guild):
    """Starts one page of the shop."""
    return discord.Embed(
        title=f"{guild.name}'s Server Shop",
        description=(
            f"{REPLY_EMOTE} *To check your balances and inventory, use {SlashCommand(BALANCE_COMMAND)}.*\n"
            f"{REPLY_EMOTE} *To purchase an item, use {SlashCommand('buy')}.*\n"
            f"{REPLY_EMOTE} *A 🔄 emoji indicates that the title can be purchased multiple times.*\n"
        ),
        color=discord.Color.gold(),
    )


def add_reward_field(embed, guild, count, item):
    """Adds one reward to a page of the shop."""
    stock = ""
    if item[4] != -1:
        emote = f"{NO_STOCK_EMOTE} " if item[4] == 0 else ""
        stock = f"\n> **Remaining:** {emote}`{item[4]}`"
    price = f"{count}ㅤ {get_currency_display(currency_of(item))} {int(item[2]):,}"
    repeat = "🔄" if (len(item) > 3 and item[3]) else ""
    if isinstance(item[0], int) or item[0].isdigit():
        role = guild.get_role(int(item[0]))
        name = role.name if role else "Unknown Role"
        value = f"> **Role:** {role.mention if role else 'N/A'}\n> **Description:** {item[1]}{stock}"
    else:
        name = item[0]
        value = f"> **Description:** {item[1]}{stock}"
    embed.add_field(name=f"{price} • {name} {repeat}", value=value, inline=False)


async def get_shop_embeds(
    interaction,
    item_list,
    empty_condition,
    sort_by="cost",
    reverse=True,
    currency_filter="all",
):
    """Gives the shop's pages, five rewards each, and the rewards in the order shown."""
    if empty_condition:
        return [discord.Embed(title="This server has no purchasable items.")], []

    if currency_filter != "all":
        filtered = [
            item for item in item_list if len(item) > 5 and item[5] == currency_filter
        ]
        if not filtered:
            currency_display = get_currency_display(currency_filter)
            return [
                discord.Embed(title=f"No items found costing {currency_display}.")
            ], []
        item_list = filtered

    def key_func(x):
        if sort_by == "cost":
            return int(x[2])
        if isinstance(x[0], int) or x[0].isdigit():
            role = interaction.guild.get_role(int(x[0]))
            return role.name.lower() if role else ""
        return str(x[0]).lower()

    order_text = "Descending" if reverse else "Ascending"
    sort_text = "Cost" if sort_by == "cost" else "Name"
    sorted_items = sorted(item_list, key=key_func, reverse=reverse)
    pages = []
    for start in range(0, len(sorted_items), 5):
        embed = shop_page(interaction.guild)
        for offset, item in enumerate(sorted_items[start : start + 5]):
            add_reward_field(embed, interaction.guild, start + offset + 1, item)
        embed.set_footer(text=f"Sorted by {sort_text} in {order_text} order")
        pages.append(embed)
    return pages, sorted_items


def build_reward_detail_embed(item, guild=None):
    """Draws the screen of one reward."""
    description_text = (
        f"> **Description:** {item[1] if item[1] else 'No description provided.'}"
    )
    stock_display = "`Unlimited`" if item[4] == -1 else f"`{item[4]}`"
    pending_change = item[6] if len(item) > 6 else None
    pending_time = item[7] if len(item) > 7 else None
    if pending_change is not None and pending_time is not None:
        stock_display += f"\n⏰ Scheduled: `{pending_change}` <t:{int(pending_time)}:R>"

    title_name = item[0]
    if is_role(item[0]) and guild:
        role_obj = guild.get_role(int(item[0]))
        if role_obj:
            title_name = role_obj.name
            description_text = (
                f"> **Role:** {role_obj.mention}\n> **Description:** {description_text}"
            )

    embed = discord.Embed(
        title=f"Reward: {title_name}",
        description=description_text,
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Cost",
        value=f"{get_currency_display(currency_of(item))} `{int(item[2]):,}`",
        inline=True,
    )
    embed.add_field(name="Stock", value=f"{stock_display}", inline=True)
    embed.add_field(
        name="Multiple Purchases", value="Yes 🔄" if item[3] else "No", inline=True
    )
    return embed


async def listing(interaction, author, sort=DEFAULT_SORT, currency_filter="all"):
    """Reads the server's shop; gives the first page of the list and its view."""
    items = await get_shop_items(interaction.client.pool, interaction.guild.id)
    pages, ordered = await get_shop_embeds(
        interaction,
        items,
        len(items) == 0,
        *SORTS.get(sort, SORTS[DEFAULT_SORT]),
        currency_filter,
    )
    view = ShopView(
        pages,
        ordered,
        author,
        sort,
        interaction.user.guild_permissions.administrator,
        currency_filter,
        interaction.guild,
    )
    return pages[0], view


async def apply_due_stock_edits(interaction):
    """Applies the scheduled stock changes that are due."""
    processed = await process_pending_stock_edits(
        interaction.client.pool, interaction.guild.id
    )
    if processed > 0:
        print(
            f"Processed {processed} scheduled stock edits for guild {interaction.guild.id}"
        )


async def show_detail(interaction, item, author, parent_message=None):
    """Swaps the message for the screen of one reward."""
    await interaction.response.edit_message(
        embed=build_reward_detail_embed(item, guild=interaction.guild),
        view=RewardDetailView(item, author, parent_message),
    )


async def show_saved(interaction, name, author):
    """Reads a reward again and shows its screen, if it is still there."""
    item = await get_shop_item_by_name(
        interaction.client.pool, interaction.guild.id, name
    )
    if item:
        await show_detail(interaction, item, author)


def refuse(text, title=None):
    """Gives the red embed that turns down an edit."""
    return discord.Embed(title=title, description=text, color=discord.Color.red())


class SortSelection(BaseSortSelect):
    """Reorders the shop."""

    def __init__(self, default=DEFAULT_SORT, initial_author=None):
        super().__init__(
            SHOP_SORT_OPTIONS, default, initial_author, custom_id="sortselection"
        )

    async def callback(self, interaction: discord.Interaction):
        embed, view = await listing(
            interaction,
            self.initial_author,
            interaction.data["values"][0],
            getattr(self.view, "currency_filter", "all"),
        )
        view.message = await interaction.response.edit_message(embed=embed, view=view)


class CurrencyFilterSelect(discord.ui.Select):
    """Narrows the shop to the rewards paid in one currency."""

    def __init__(self, current_filter="all", initial_author=None):
        self.initial_author = initial_author
        all_emoji = next(
            (
                emoji
                for label, emoji in SHOP_CURRENCY_FILTERS
                if label == "All currencies"
            ),
            None,
        )
        options = [
            discord.SelectOption(
                label="All currencies",
                emoji=all_emoji,
                default=(current_filter == "all"),
            )
        ]
        for key, info in CURRENCY_INFO.items():
            options.append(
                discord.SelectOption(
                    label=info["filter_label"],
                    emoji=info["emoji"],
                    default=(current_filter == key),
                )
            )
        super().__init__(
            placeholder="Filter by currency...",
            max_values=1,
            min_values=1,
            options=options,
            custom_id="currencyfilter",
        )

    async def callback(self, interaction: discord.Interaction):
        new_filter = next(
            (
                key
                for key, info in CURRENCY_INFO.items()
                if info["filter_label"] == self.values[0]
            ),
            "all",
        )
        embed, view = await listing(
            interaction, self.initial_author, currency_filter=new_filter
        )
        view.message = await interaction.response.edit_message(embed=embed, view=view)


class ShopItemSelect(discord.ui.Select):
    """Lets an admin open one of the rewards on the page."""

    def __init__(self, items_page, initial_author, current_page=0, guild=None):
        self.initial_author = initial_author
        options = []
        for item in items_page:
            display = item[0]
            if is_role(display):
                role = guild.get_role(int(display)) if guild else None
                display = role.name if role else "Unknown Role"
            if len(str(display)) > 90:
                display = str(display)[:87] + "..."
            options.append(
                discord.SelectOption(
                    label=f"{int(item[2]):,} • {display}",
                    description=f"Stock: {'∞' if item[4] == -1 else item[4]}",
                    emoji=get_currency_display(currency_of(item)),
                    value=str(item[0]),
                )
            )
        super().__init__(
            placeholder=f"Select an item to edit (page {current_page+1})...",
            max_values=1,
            min_values=1,
            options=options,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        item = await get_shop_item_by_name(
            interaction.client.pool, interaction.guild.id, self.values[0]
        )
        if not item:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Item not found.", ephemeral=True
            )
        await show_detail(interaction, item, self.initial_author, interaction.message)


class ShopView(BasePaginationView):
    """The shop, with its sort and filter menus and, for admins, the edit controls."""

    def __init__(
        self,
        pages=None,
        items=None,
        initial_author=None,
        default=DEFAULT_SORT,
        is_admin=False,
        currency_filter="all",
        guild=None,
        *,
        timeout=300,
    ):
        self.is_admin = is_admin
        self.currency_filter = currency_filter
        self.guild = guild
        self.items = items or []
        super().__init__(pages=pages, initial_author=initial_author, timeout=timeout)
        self.add_item(SortSelection(default, initial_author))
        self.add_item(CurrencyFilterSelect(currency_filter, initial_author))

    def _update_button_states(self) -> None:
        super()._update_button_states()
        for child in [
            child
            for child in self.children
            if isinstance(child, ShopItemSelect)
            or (isinstance(child, discord.ui.Button) and child.label == "Add Reward")
        ]:
            self.remove_item(child)
        if not self.is_admin:
            return
        page_items = self.items[self.page * 5 : self.page * 5 + 5]
        if page_items:
            self.add_item(
                ShopItemSelect(page_items, self.initial_author, self.page, self.guild)
            )
        self.add_item(ShopAddRewardButton(self.initial_author))


class ShopAddRewardButton(discord.ui.Button):
    """Makes an empty reward and opens it for editing."""

    def __init__(self, initial_author=None):
        super().__init__(label="Add Reward", style=discord.ButtonStyle.green, row=0)
        self.initial_author = initial_author

    async def callback(self, interaction: discord.Interaction):
        pool, gid = interaction.client.pool, interaction.guild.id
        temp_name = f"_new_{int(time.time())}"
        await add_shop_item(pool, gid, temp_name, "", "0", False, -1, "guild_mora")
        item = await get_shop_item_by_name(pool, gid, temp_name)
        if not item:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Failed to create reward.", ephemeral=True
            )
        await show_detail(interaction, item, self.initial_author, interaction.message)


class RewardDetailView(discord.ui.View):
    """The screen of one reward, with the buttons that edit it."""

    def __init__(self, item, initial_author=None, parent_message=None, *, timeout=300):
        super().__init__(timeout=timeout)
        self.item = item
        self.initial_author = initial_author
        self.parent_message = parent_message
        name = str(item[0])
        values = {
            "name": name,
            "description": str(item[1]),
            "cost": str(item[2]),
            "stock": str(item[4]) if item[4] != -1 else "",
        }
        for field in ("name", "description", "cost"):
            self.add_item(
                EditFieldButton(field, values[field], initial_author, 0, name)
            )
        self.add_item(ShopItemCurrencySelect(initial_author, item))
        self.add_item(ToggleMultipleButton(initial_author, name))
        self.add_item(
            EditFieldButton("stock", values["stock"], initial_author, 2, name)
        )
        self.add_item(DeleteRewardButton(initial_author, name))
        self.add_item(BackToShopButton(initial_author, name))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.initial_author and self.initial_author != interaction.user:
            await interaction.response.send_message(
                f"{NO_EMOTE} You are not the author of this command", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.clear_items()
        self.add_item(
            discord.ui.Button(
                label="Expired",
                style=discord.ButtonStyle.grey,
                emoji="<a:clock:1382887924273774754>",
                disabled=True,
            )
        )
        try:
            if self.parent_message:
                await self.parent_message.edit(view=self)
        except discord.NotFound:
            pass


class ShopItemCurrencySelect(discord.ui.Select):
    """Changes the currency a reward is paid in."""

    def __init__(self, initial_author, item):
        self.initial_author = initial_author
        self.item_name = str(item[0])
        super().__init__(
            placeholder="Select a currency...",
            max_values=1,
            min_values=1,
            options=[
                discord.SelectOption(
                    label=info["label"],
                    value=key,
                    emoji=info["emoji"],
                    default=(currency_of(item) == key),
                )
                for key, info in CURRENCY_INFO.items()
            ],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await update_shop_item_field(
            interaction.client.pool,
            interaction.guild.id,
            self.item_name,
            "currency_type",
            self.values[0],
        )
        await show_saved(interaction, self.item_name, self.initial_author)


class EditFieldButton(discord.ui.Button):
    """Opens the box that edits one field of a reward."""

    def __init__(self, field_name, current_value, initial_author, row, item_name):
        super().__init__(
            label=FIELDS[field_name][0], style=discord.ButtonStyle.secondary, row=row
        )
        self.field_name = field_name
        self.current_value = current_value
        self.initial_author = initial_author
        self.item_name = item_name or current_value

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            EditFieldModal(
                self.field_name, self.current_value, self.initial_author, self.item_name
            )
        )


class EditFieldModal(discord.ui.Modal):
    """The box an admin types a reward's new name, description, cost or stock into."""

    def __init__(self, field_name, current_value, initial_author, item_name):
        title, label, max_length, required = FIELDS[field_name]
        super().__init__(title=title)
        self.field_name = field_name
        self.initial_author = initial_author
        self.item_name = item_name
        self.input = discord.ui.TextInput(
            label=label,
            style=discord.TextStyle.short,
            placeholder=current_value or "Enter new value",
            required=required,
            max_length=max_length,
            default=str(current_value) if current_value else "",
        )
        self.add_item(self.input)
        self.time_input = None
        if field_name == "stock":
            self.time_input = discord.ui.TextInput(
                label="Schedule Unix Timestamp (optional)",
                style=discord.TextStyle.short,
                placeholder="Leave blank to apply immediately",
                required=False,
                max_length=15,
            )
            self.add_item(self.time_input)

    async def turn_down(self, interaction, reason):
        """Tells the admin why the value was not saved."""
        await interaction.response.send_message(
            embed=refuse(f"{NO_EMOTE} {reason}"), ephemeral=True
        )

    async def save_stock(self, interaction, stock_part):
        """Sets the stock now, or schedules the change when a time is given."""
        pool, gid = interaction.client.pool, interaction.guild.id
        timestamp_str = str(self.time_input.value).strip() if self.time_input else ""
        if stock_part == "" or stock_part == "-1":
            stock_val = -1
        else:
            try:
                stock_val = int(stock_part)
                if stock_val < -1:
                    raise ValueError
            except ValueError:
                return await self.turn_down(
                    interaction,
                    "Stock must be -1 (unlimited) or a non-negative integer.",
                )
        if timestamp_str:
            try:
                await add_pending_edit(
                    pool, gid, self.item_name, stock_part, int(timestamp_str)
                )
            except (ValueError, IndexError):
                return await self.turn_down(
                    interaction, "Invalid timestamp. Provide a valid Unix timestamp."
                )
        else:
            await update_shop_item_stock_by_name(pool, gid, self.item_name, stock_val)
        await show_saved(interaction, self.item_name, self.initial_author)

    async def on_submit(self, interaction: discord.Interaction):
        pool, gid = interaction.client.pool, interaction.guild.id
        new_value = str(self.input.value).strip()
        if self.field_name == "stock":
            return await self.save_stock(interaction, new_value)
        if self.field_name == "cost":
            try:
                parsed = parse_cost(new_value)
                if parsed <= 0:
                    raise ValueError
            except (ValueError, IndexError):
                return await self.turn_down(
                    interaction, "Cost must be a valid positive integer."
                )
            await update_shop_item_cost(pool, gid, self.item_name, str(parsed))
        else:
            if self.field_name == "name" and not new_value:
                return await self.turn_down(interaction, "Name cannot be empty.")
            await update_shop_item_field(
                pool, gid, self.item_name, self.field_name, new_value
            )
        await show_saved(
            interaction,
            new_value if self.field_name == "name" else self.item_name,
            self.initial_author,
        )


def shown_reward(interaction, item_name):
    """Gives the reward a button belongs to, read off the screen when it has no name."""
    return item_name or interaction.message.embeds[0].title.replace("Reward: ", "")


class ToggleMultipleButton(discord.ui.Button):
    """Switches whether a reward can be bought more than once."""

    def __init__(self, initial_author, item_name=None):
        super().__init__(
            label="Toggle Allow Multiple", style=discord.ButtonStyle.secondary, row=2
        )
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        pool, gid = interaction.client.pool, interaction.guild.id
        name = shown_reward(interaction, self.item_name)
        current = await get_shop_item_by_name(pool, gid, name)
        if not current:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Reward not found.", ephemeral=True
            )
        await update_shop_item_field(pool, gid, name, "multiple", not current[3])
        await show_saved(interaction, name, self.initial_author)


class DeleteRewardButton(discord.ui.Button):
    """Asks before deleting a reward."""

    def __init__(self, initial_author, item_name=None):
        super().__init__(label="Delete Reward", style=discord.ButtonStyle.danger, row=2)
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        name = shown_reward(interaction, self.item_name)
        await interaction.response.send_message(
            embed=refuse(
                f"Are you sure you want to delete **{name}**? This cannot be undone."
            ),
            view=ConfirmDeleteView(name, self.initial_author, interaction.message),
            ephemeral=True,
        )


class ConfirmDeleteView(discord.ui.View):
    """The Yes button that deletes a reward."""

    def __init__(self, item_name, initial_author, parent_message=None):
        super().__init__(timeout=30)
        self.item_name = item_name
        self.initial_author = initial_author
        self.parent_message = parent_message

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm_delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await remove_shop_item_by_name(
            interaction.client.pool, interaction.guild.id, self.item_name
        )
        embed, view = await listing(interaction, self.initial_author)
        await interaction.response.edit_message(
            content=f"{YES_EMOTE} Reward **{self.item_name}** has been deleted.",
            embed=None,
            view=None,
        )
        if self.parent_message:
            try:
                await self.parent_message.edit(embed=embed, view=view)
            except (discord.HTTPException, discord.NotFound):
                pass


def missing_parts(item):
    """Lists what a reward still needs before it can be left."""
    try:
        cost = int(item[2])
    except (ValueError, TypeError):
        cost = 0
    name = str(item[0]).strip()
    errors = []
    if not name or name.startswith("_new_"):
        errors.append("Reward title/role ID is required")
    if not str(item[1]).strip():
        errors.append("Description is required")
    if cost <= 0:
        errors.append("Cost must be a positive number")
    if currency_of(item) not in CURRENCY_INFO:
        errors.append("Currency type is invalid")
    return errors


class BackToShopButton(discord.ui.Button):
    """Goes back to the shop once the reward is complete."""

    def __init__(self, initial_author, item_name=None):
        super().__init__(label="Back to Shop", style=discord.ButtonStyle.blurple, row=2)
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        item = (
            await get_shop_item_by_name(
                interaction.client.pool, interaction.guild.id, self.item_name
            )
            if self.item_name
            else None
        )
        errors = missing_parts(item) if item else []
        if errors:
            return await interaction.response.send_message(
                embed=refuse(
                    "\n".join(f"{NO_EMOTE} {e}" for e in errors),
                    "Cannot return to shop yet",
                ),
                ephemeral=True,
            )
        await apply_due_stock_edits(interaction)
        embed, view = await listing(interaction, self.initial_author)
        view.message = await interaction.response.edit_message(embed=embed, view=view)


class Shop(commands.Cog):
    """The /shop command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="shop", description="View the guild shop (Admins can edit here too)"
    )
    async def shop(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        await apply_due_stock_edits(interaction)
        embed, view = await listing(interaction, interaction.user)
        view.message = await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))
