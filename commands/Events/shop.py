import discord

from discord import app_commands
from discord.ext import commands

from commands.Events.helperFunctions import get_shop_items, get_shop_item_by_name, process_pending_stock_edits, update_shop_item_cost, update_shop_item_stock_by_name, add_shop_item, remove_shop_item_by_name, update_shop_item_field, add_pending_edit
from utils.pagination import BasePaginationView, BaseSortSelect
from utils.commands import SlashCommand

from commands.Events.config import BALANCE_COMMAND, NO_EMOTE, REPLY_EMOTE, NO_STOCK_EMOTE, SHOP_SORT_OPTIONS, SHOP_CURRENCY_FILTERS, CURRENCY_INFO, YES_EMOTE, GUILD_MORA_EMOTE, GLOBAL_MORA_EMOTE, GUILD_SIGIL_EMOTE, GLOBAL_SIGIL_EMOTE

def get_currency_display(currency_type: str) -> str:
    info = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])
    return f"{info['emoji']}"

def parse_cost(cost_str: str) -> int:
    multiplier_map = {"k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12}
    cost_lower = cost_str.lower().strip()
    if cost_lower[-1] in multiplier_map:
        return int(float(cost_lower[:-1]) * multiplier_map[cost_lower[-1]])
    return int(float(cost_lower))

async def get_shop_embeds(
    interaction, item_list, empty_condition, sort_by="cost", reverse=True, currency_filter="all"
):
    if empty_condition:
        return [discord.Embed(title="This server has no purchasable items.")], []

    if currency_filter != "all":
        filtered = [item for item in item_list if len(item) > 5 and item[5] == currency_filter]
        if not filtered:
            currency_display = get_currency_display(currency_filter)
            return [discord.Embed(title=f"No items found costing {currency_display}.")], []
        item_list = filtered

    sort_index = {"cost": 2, "name": 0}

    def key_func(x):
        if sort_by == "cost":
            return int(x[sort_index[sort_by]])
        else:
            if isinstance(x[0], int) or x[0].isdigit():
                role = interaction.guild.get_role(int(x[0]))
                return role.name.lower() if role else ""
            return str(x[sort_index[sort_by]]).lower()

    order_text = "Descending" if reverse else "Ascending"
    sort_text = "Cost" if sort_by == "cost" else "Name"

    sorted_items = sorted(item_list, key=key_func, reverse=reverse)
    pages = []
    embed = discord.Embed(
        title=f"{interaction.guild.name}'s Server Shop",
        description=(
            f"{REPLY_EMOTE} *To check your balances and inventory, use {SlashCommand(BALANCE_COMMAND)}.*\n"
            f"{REPLY_EMOTE} *To purchase an item, use {SlashCommand('buy')}.*\n"
            f"{REPLY_EMOTE} *A 🔄 emoji indicates that the title can be purchased multiple times.*\n"
        ),
        color=discord.Color.gold(),
    )

    for i, item in enumerate(sorted_items):
        count = i + 1
        currency_type = item[5] if len(item) > 5 else "guild_mora"
        currency_display = get_currency_display(currency_type)
        emote = f"{NO_STOCK_EMOTE} " if item[4] == 0 else ''
        stock_count = f"\n> **Remaining:** {emote}`{item[4]}`" if item[4] != -1 else None

        if isinstance(item[0], int) or item[0].isdigit():
            role = interaction.guild.get_role(int(item[0]))
            embed.add_field(
                name=f"{count}ㅤ {currency_display} {int(item[2]):,} • {role.name if role else 'Unknown Role'} {'🔄' if (len(item) > 3 and item[3]) else ''}",
                value=f"> **Role:** {role.mention if role else 'N/A'}\n> **Description:** {item[1]}{stock_count if stock_count is not None else ''}",
                inline=False,
            )
        else:
            embed.add_field(
                name=f"{count}ㅤ {currency_display} {int(item[2]):,} • {item[0]} {'🔄' if (len(item) > 3 and item[3]) else ''}",
                value=f"> **Description:** {item[1]}{stock_count if stock_count is not None else ''}",
                inline=False,
            )

        if (i + 1) % 5 == 0 or (i + 1) == len(sorted_items):
            embed.set_footer(text=f"Sorted by {sort_text} in {order_text} order")
            pages.append(embed)
            embed = discord.Embed(
                title=f"{interaction.guild.name}'s Server Shop",
                description=(
                    f"{REPLY_EMOTE} *To check your balances and inventory, use {SlashCommand(BALANCE_COMMAND)}.*\n"
                    f"{REPLY_EMOTE} *To purchase an item, use {SlashCommand('buy')}.*\n"
                    f"{REPLY_EMOTE} *A 🔄 emoji indicates that the title can be purchased multiple times.*\n"
                ),
                color=discord.Color.gold(),
            )

    return pages, sorted_items

def build_reward_detail_embed(item, guild=None):
    currency_type = item[5] if len(item) > 5 else "guild_mora"
    currency_display = get_currency_display(currency_type)
    description_text = f"> **Description:** {item[1] if item[1] else 'No description provided.'}"
    stock_display = "`Unlimited`" if item[4] == -1 else f"`{item[4]}`"
    multiple_display = "Yes 🔄" if item[3] else "No"

    pending_change = item[6] if len(item) > 6 else None
    pending_time = item[7] if len(item) > 7 else None
    if pending_change is not None and pending_time is not None:
        stock_display += f"\n⏰ Scheduled: `{pending_change}` <t:{int(pending_time)}:R>"

    title_name = item[0]
    if isinstance(item[0], int) or str(item[0]).isdigit():
        if guild:
            role_obj = guild.get_role(int(item[0]))
            if role_obj:
                title_name = role_obj.name
                description_text = f"> **Role:** {role_obj.mention}\n> **Description:** {description_text}"

    embed = discord.Embed(
        title=f"Reward: {title_name}",
        description=description_text,
        color=discord.Color.gold(),
    )
    embed.add_field(name="Cost", value=f"{currency_display} `{int(item[2]):,}`", inline=True)
    embed.add_field(name="Stock", value=f"{stock_display}", inline=True)
    embed.add_field(name="Multiple Purchases", value=multiple_display, inline=True)
    return embed


class SortSelection(BaseSortSelect):
    def __init__(self, default="sort by cost (high to low)", initial_author=None):
        super().__init__(SHOP_SORT_OPTIONS, default, initial_author, custom_id="sortselection")

    async def callback(self, interaction: discord.Interaction):
        originalList = await get_shop_items(interaction.client.pool, interaction.guild.id)
        currency_filter = getattr(self.view, "currency_filter", "all")
        sort_val = interaction.data["values"][0]
        if sort_val == "sort by cost (low to high)":
            pages, items = await get_shop_embeds(interaction, originalList, len(originalList) == 0, sort_by="cost", reverse=False, currency_filter=currency_filter)
        elif sort_val == "sort by cost (high to low)":
            pages, items = await get_shop_embeds(interaction, originalList, len(originalList) == 0, sort_by="cost", reverse=True, currency_filter=currency_filter)
        elif sort_val == "sort by name (a-z)":
            pages, items = await get_shop_embeds(interaction, originalList, len(originalList) == 0, sort_by="name", reverse=False, currency_filter=currency_filter)
        elif sort_val == "sort by name (z-a)":
            pages, items = await get_shop_embeds(interaction, originalList, len(originalList) == 0, sort_by="name", reverse=True, currency_filter=currency_filter)
        else:
            pages, items = await get_shop_embeds(interaction, originalList, len(originalList) == 0, currency_filter=currency_filter)

        view = ShopView(pages=pages, items=items, default=sort_val, initial_author=self.initial_author, is_admin=interaction.user.guild_permissions.administrator, currency_filter=currency_filter, guild_id=interaction.guild.id, pool=interaction.client.pool, guild=interaction.guild)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)


class CurrencyFilterSelect(discord.ui.Select):
    def __init__(self, current_filter="all", initial_author=None):
        self.initial_author = initial_author
        options = []
        all_emoji = next((emoji for label, emoji in SHOP_CURRENCY_FILTERS if label == "All currencies"), None)
        options.append(discord.SelectOption(label="All currencies", emoji=all_emoji, default=(current_filter == "all")))
        
        for key, info in CURRENCY_INFO.items():
            options.append(
                discord.SelectOption(
                    label=info["filter_label"], 
                    emoji=info["emoji"], 
                    default=(current_filter == key)
                )
            )
            
        super().__init__(placeholder="Filter by currency...", max_values=1, min_values=1, options=options, custom_id="currencyfilter")

    async def callback(self, interaction: discord.Interaction):
        label = self.values[0]
        
        new_filter = "all"
        for key, info in CURRENCY_INFO.items():
            if info["filter_label"] == label:
                new_filter = key
                break
                
        originalList = await get_shop_items(interaction.client.pool, interaction.guild.id)
        pages, items = await get_shop_embeds(interaction, originalList, len(originalList) == 0, currency_filter=new_filter)
        view = ShopView(pages=pages, items=items, default="sort by cost (high to low)", initial_author=self.initial_author, is_admin=interaction.user.guild_permissions.administrator, currency_filter=new_filter, guild_id=interaction.guild.id, pool=interaction.client.pool, guild=interaction.guild)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)


class ShopItemSelect(discord.ui.Select):
    def __init__(self, items_page, all_items, guild_id, pool, initial_author, current_page=0, guild=None):
        self.initial_author = initial_author
        self.all_items = all_items
        self.guild_id = guild_id
        self.pool = pool
        self.current_page = current_page
        options = []
        for item in items_page:
            display = item[0]
            if isinstance(display, int) or str(display).isdigit():
                role = guild.get_role(int(display)) if guild else None
                display = role.name if role else "Unknown Role"
            if len(str(display)) > 90:
                display = str(display)[:87] + "..."
            currency_type = item[5] if len(item) > 5 else "guild_mora"
            currency_emoji = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])["emoji"]
            cost = int(item[2])
            options.append(
                discord.SelectOption(
                    label=f"{cost:,} • {display}",
                    description=f"Stock: {'∞' if item[4] == -1 else item[4]}",
                    emoji=currency_emoji,
                    value=str(item[0]),
                )
            )
        placeholder = f"Select an item to edit (page {current_page+1})..."
        super().__init__(placeholder=placeholder, max_values=1, min_values=1, options=options, row=3)

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]
        item = await get_shop_item_by_name(self.pool, self.guild_id, item_name)
        if not item:
            return await interaction.response.send_message(f"{NO_EMOTE} Item not found.", ephemeral=True)
        embed = build_reward_detail_embed(item, guild=interaction.guild)
        view = RewardDetailView(item, self.all_items, self.guild_id, self.pool, 0, initial_author=self.initial_author, parent_message=interaction.message)
        await interaction.response.edit_message(embed=embed, view=view)


class ShopView(BasePaginationView):
    def __init__(self, pages=None, items=None, initial_author=None, default="sort by cost (high to low)", is_admin=False, currency_filter="all", guild_id=None, pool=None, guild=None, *, timeout=300):
        self.is_admin = is_admin
        self.currency_filter = currency_filter
        self.guild_id = guild_id
        self.pool = pool
        self.guild = guild
        self.items = items or []
        super().__init__(pages=pages, initial_author=initial_author, timeout=timeout)
        self.add_item(SortSelection(default, initial_author))
        self.add_item(CurrencyFilterSelect(currency_filter, initial_author))

    def _update_button_states(self) -> None:
        super()._update_button_states()
        to_remove = []
        for child in self.children:
            if isinstance(child, ShopItemSelect) or (isinstance(child, discord.ui.Button) and child.label == "Add Reward"):
                to_remove.append(child)
        for child in to_remove:
            self.remove_item(child)
        if self.is_admin:
            start = self.page * 5
            end = start + 5
            page_items = self.items[start:end]
            if page_items:
                self.add_item(ShopItemSelect(page_items, self.items, self.guild_id, self.pool, self.initial_author, current_page=self.page, guild=self.guild))
            self.add_item(ShopAddRewardButton(self.guild_id, self.pool, self.initial_author, self.items))


class ShopAddRewardButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author=None, items=None):
        super().__init__(label="Add Reward", style=discord.ButtonStyle.green, row=0)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.items = items or []

    async def callback(self, interaction: discord.Interaction):
        import time
        temp_name = f"_new_{int(time.time())}"
        await add_shop_item(self.pool, self.guild_id, temp_name, "", "0", False, -1, "guild_mora")
        item = await get_shop_item_by_name(self.pool, self.guild_id, temp_name)
        if not item:
            return await interaction.response.send_message(f"{NO_EMOTE} Failed to create reward.", ephemeral=True)
        items = await get_shop_items(self.pool, self.guild_id)
        embed = build_reward_detail_embed(item, guild=interaction.guild)
        view = RewardDetailView(item, items, self.guild_id, self.pool, 0, initial_author=self.initial_author, parent_message=interaction.message)
        await interaction.response.edit_message(embed=embed, view=view)


class RewardDetailView(discord.ui.View):
    def __init__(self, item, all_items, guild_id, pool, item_index, initial_author=None, parent_message=None, *, timeout=300):
        super().__init__(timeout=timeout)
        self.item = item
        self.all_items = all_items
        self.guild_id = guild_id
        self.pool = pool
        self.item_index = item_index
        self.initial_author = initial_author
        self.parent_message = parent_message
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.initial_author and self.initial_author != interaction.user:
            await interaction.response.send_message(f"{NO_EMOTE} You are not the author of this command", ephemeral=True)
            return False
        return True

    def _build(self):
        self.clear_items()
        item = self.item
        self.add_item(EditFieldButton("Edit Name", "name", str(item[0]), "Role ID / Reward Title", self.guild_id, self.pool, self.initial_author, max_length=50, row=0, item_name=str(item[0])))
        self.add_item(EditFieldButton("Edit Description", "description", str(item[1]), "Description / Perk", self.guild_id, self.pool, self.initial_author, max_length=150, row=0, item_name=str(item[0])))
        self.add_item(EditFieldButton("Edit Cost", "cost", str(item[2]), "Cost of Reward", self.guild_id, self.pool, self.initial_author, max_length=10, row=0, item_name=str(item[0])))
        self.add_item(ShopItemCurrencySelect(self.guild_id, self.pool, self.initial_author, self.item, row=1))
        self.add_item(ToggleMultipleButton(self.guild_id, self.pool, self.initial_author, row=2, item_name=str(item[0])))
        self.add_item(EditFieldButton("Edit Stock", "stock", str(item[4]) if item[4] != -1 else "", "Stock Value", self.guild_id, self.pool, self.initial_author, max_length=20, required=False, row=2, item_name=str(item[0])))
        self.add_item(DeleteRewardButton(self.guild_id, self.pool, self.initial_author, row=2, item_name=str(item[0])))
        self.add_item(BackToShopButton(self.guild_id, self.pool, self.initial_author, row=2, item_name=str(item[0])))

    async def refresh(self, interaction):
        updated = await get_shop_item_by_name(self.pool, self.guild_id, self.item[0])
        if updated:
            self.item = updated
        self.all_items = await get_shop_items(self.pool, self.guild_id)
        self.item_index = next((i for i, it in enumerate(self.all_items) if it[0] == self.item[0]), 0)
        embed = build_reward_detail_embed(self.item, guild=interaction.guild)
        self._build()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        self.clear_items()
        self.add_item(discord.ui.Button(label="Expired", style=discord.ButtonStyle.grey, emoji="<a:clock:1382887924273774754>", disabled=True))
        try:
            if self.parent_message:
                await self.parent_message.edit(view=self)
        except discord.NotFound:
            pass


class ShopItemCurrencySelect(discord.ui.Select):
    def __init__(self, guild_id, pool, initial_author, item, row=1):
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = str(item[0])
        current_currency = item[5] if len(item) > 5 else "guild_mora"
        
        currency_options = [
            discord.SelectOption(
                label=info["label"], 
                value=key, 
                emoji=info["emoji"], 
                default=(current_currency == key)
            )
            for key, info in CURRENCY_INFO.items()
        ]
        
        super().__init__(placeholder="Select a currency...", max_values=1, min_values=1, options=currency_options, row=row)

    async def callback(self, interaction: discord.Interaction):
        new_currency = self.values[0]
        await update_shop_item_field(self.pool, self.guild_id, self.item_name, "currency_type", new_currency)
        updated_item = await get_shop_item_by_name(self.pool, self.guild_id, self.item_name)
        if updated_item:
            items = await get_shop_items(self.pool, self.guild_id)
            embed = build_reward_detail_embed(updated_item, guild=interaction.guild)
            view = RewardDetailView(updated_item, items, self.guild_id, self.pool, 0, initial_author=self.initial_author)
            await interaction.response.edit_message(embed=embed, view=view)


class EditFieldButton(discord.ui.Button):
    def __init__(self, label, field_name, current_value, field_label, guild_id, pool, initial_author, max_length=50, required=True, row=0, item_name=None):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.field_name = field_name
        self.current_value = current_value
        self.field_label = field_label
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.edit_max_length = max_length
        self.edit_required = required
        self.item_name = item_name or current_value

    async def callback(self, interaction: discord.Interaction):
        modal = EditFieldModal(self.field_name, self.current_value, self.field_label, self.guild_id, self.pool, self.initial_author, self.edit_max_length, self.edit_required, self.item_name)
        await interaction.response.send_modal(modal)


class EditFieldModal(discord.ui.Modal):
    def __init__(self, field_name, current_value, field_label, guild_id, pool, initial_author, max_length=50, required=True, item_name=None):
        title_map = {
            "name": "Edit Name",
            "description": "Edit Description",
            "cost": "Edit Cost",
            "stock": "Edit Stock",
        }
        modal_title = title_map.get(field_name, f"Edit {field_name.capitalize()}")
        super().__init__(title=modal_title)
        self.field_name = field_name
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = item_name
        self.input = discord.ui.TextInput(
            label=field_label,
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

    async def on_submit(self, interaction: discord.Interaction):
        new_value = str(self.input.value).strip()
        old_name = self.item_name

        if self.field_name == "cost":
            try:
                parsed = parse_cost(new_value)
                if parsed <= 0:
                    raise ValueError
                new_value = str(parsed)
            except (ValueError, IndexError):
                return await interaction.response.send_message(
                    embed=discord.Embed(description=f"{NO_EMOTE} Cost must be a valid positive integer.", color=discord.Color.red()),
                    ephemeral=True
                )
        elif self.field_name == "stock":
            stock_part = new_value
            timestamp_str = str(self.time_input.value).strip() if self.time_input else ""

            if stock_part == "" or stock_part == "-1":
                stock_val = -1
            else:
                try:
                    sv = int(stock_part)
                    if sv < -1:
                        raise ValueError
                    stock_val = sv
                except ValueError:
                    return await interaction.response.send_message(
                        embed=discord.Embed(description=f"{NO_EMOTE} Stock must be -1 (unlimited) or a non-negative integer.", color=discord.Color.red()),
                        ephemeral=True
                    )

            if timestamp_str:
                try:
                    scheduled_ts = int(timestamp_str)
                    await add_pending_edit(self.pool, self.guild_id, old_name, stock_part, scheduled_ts)
                except (ValueError, IndexError):
                    return await interaction.response.send_message(
                        embed=discord.Embed(description=f"{NO_EMOTE} Invalid timestamp. Provide a valid Unix timestamp.", color=discord.Color.red()),
                        ephemeral=True
                    )
            else:
                await update_shop_item_stock_by_name(self.pool, self.guild_id, old_name, stock_val)

            lookup_name = old_name
            updated_item = await get_shop_item_by_name(self.pool, self.guild_id, lookup_name)
            if updated_item:
                items = await get_shop_items(self.pool, self.guild_id)
                embed = build_reward_detail_embed(updated_item, guild=interaction.guild)
                view = RewardDetailView(updated_item, items, self.guild_id, self.pool, 0, initial_author=self.initial_author)
                await interaction.response.edit_message(embed=embed, view=view)
            return
        elif self.field_name == "name":
            if not new_value:
                return await interaction.response.send_message(
                    embed=discord.Embed(description=f"{NO_EMOTE} Name cannot be empty.", color=discord.Color.red()),
                    ephemeral=True
                )

        if self.field_name == "cost":
            await update_shop_item_cost(self.pool, self.guild_id, old_name, new_value)
        elif self.field_name != "stock":
            await update_shop_item_field(self.pool, self.guild_id, old_name, self.field_name, new_value)

        lookup_name = new_value if self.field_name == "name" else old_name
        updated_item = await get_shop_item_by_name(self.pool, self.guild_id, lookup_name)
        if updated_item:
            items = await get_shop_items(self.pool, self.guild_id)
            embed = build_reward_detail_embed(updated_item, guild=interaction.guild)
            view = RewardDetailView(updated_item, items, self.guild_id, self.pool, 0, initial_author=self.initial_author)
            await interaction.response.edit_message(embed=embed, view=view)


class ToggleMultipleButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author, row=1, item_name=None):
        super().__init__(label="Toggle Allow Multiple", style=discord.ButtonStyle.secondary, row=row)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        name_to_update = self.item_name or interaction.message.embeds[0].title.replace("Reward: ", "")
        current_raw = await get_shop_item_by_name(self.pool, self.guild_id, name_to_update)
        if not current_raw:
            return await interaction.response.send_message(f"{NO_EMOTE} Reward not found.", ephemeral=True)
        new_val = not current_raw[3]
        await update_shop_item_field(self.pool, self.guild_id, name_to_update, "multiple", new_val)
        updated_item = await get_shop_item_by_name(self.pool, self.guild_id, name_to_update)
        if updated_item:
            items = await get_shop_items(self.pool, self.guild_id)
            embed = build_reward_detail_embed(updated_item, guild=interaction.guild)
            view = RewardDetailView(updated_item, items, self.guild_id, self.pool, 0, initial_author=self.initial_author)
            await interaction.response.edit_message(embed=embed, view=view)


class DeleteRewardButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author, row=2, item_name=None):
        super().__init__(label="Delete Reward", style=discord.ButtonStyle.danger, row=row)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        name_to_update = self.item_name or interaction.message.embeds[0].title.replace("Reward: ", "")
        view = ConfirmDeleteView(name_to_update, self.guild_id, self.pool, self.initial_author, parent_message=interaction.message)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"Are you sure you want to delete **{name_to_update}**? This cannot be undone.", color=discord.Color.red()),
            view=view,
            ephemeral=True
        )


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, item_name, guild_id, pool, initial_author, parent_message=None):
        super().__init__(timeout=30)
        self.item_name = item_name
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.parent_message = parent_message

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await remove_shop_item_by_name(self.pool, self.guild_id, self.item_name)
        items = await get_shop_items(self.pool, self.guild_id)
        pages, sorted_items = await get_shop_embeds(interaction, items, len(items) == 0)
        is_admin = interaction.user.guild_permissions.administrator
        view = ShopView(pages=pages, items=sorted_items, initial_author=self.initial_author, is_admin=is_admin, guild_id=self.guild_id, pool=self.pool, guild=interaction.guild)
        await interaction.response.edit_message(
            content=f"{YES_EMOTE} Reward **{self.item_name}** has been deleted.",
            embed=None, view=None
        )
        if self.parent_message:
            try:
                await self.parent_message.edit(embed=pages[0], view=view)
            except (discord.HTTPException, discord.NotFound):
                pass


class BackToShopButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author, row=2, item_name=None):
        super().__init__(label="Back to Shop", style=discord.ButtonStyle.blurple, row=row)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        item = await get_shop_item_by_name(self.pool, self.guild_id, self.item_name) if self.item_name else None
        if item:
            name = str(item[0]).strip()
            desc = str(item[1]).strip()
            try:
                cost = int(item[2])
            except (ValueError, TypeError):
                cost = 0
            currency_type = item[5] if len(item) > 5 else "guild_mora"
            valid_currencies = {"guild_mora", "global_mora", "guild_sigils", "global_sigils"}

            errors = []
            if not name or name.startswith("_new_"):
                errors.append("Reward title/role ID is required")
            if not desc:
                errors.append("Description is required")
            if cost <= 0:
                errors.append("Cost must be a positive number")
            if currency_type not in valid_currencies:
                errors.append("Currency type is invalid")

            if errors:
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Cannot return to shop yet",
                        description="\n".join(f"{NO_EMOTE} {e}" for e in errors),
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

        processed = await process_pending_stock_edits(self.pool, self.guild_id)
        if processed > 0:
            print(f"Processed {processed} scheduled stock edits for guild {self.guild_id}")

        foundGuild = await get_shop_items(self.pool, self.guild_id)
        pages, sorted_items = await get_shop_embeds(interaction, foundGuild, len(foundGuild) == 0)

        is_admin = interaction.user.guild_permissions.administrator
        view = ShopView(pages=pages, items=sorted_items, initial_author=self.initial_author, is_admin=is_admin, guild_id=self.guild_id, pool=self.pool, guild=interaction.guild)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="shop", description="View the guild shop (Admins can edit here too)"
    )
    async def shop(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(thinking=True)

        processed = await process_pending_stock_edits(interaction.client.pool, interaction.guild.id)
        if processed > 0:
            print(f"Processed {processed} scheduled stock edits for guild {interaction.guild.id}")

        foundGuild = await get_shop_items(interaction.client.pool, interaction.guild.id)

        pages, sorted_items = await get_shop_embeds(
            interaction, foundGuild, len(foundGuild) == 0
        )

        is_admin = interaction.user.guild_permissions.administrator
        view = ShopView(pages=pages, items=sorted_items, initial_author=interaction.user, is_admin=is_admin, guild_id=interaction.guild.id, pool=interaction.client.pool, guild=interaction.guild)

        view.message = await interaction.followup.send(embed=pages[0], view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))