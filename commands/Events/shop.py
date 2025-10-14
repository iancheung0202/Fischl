import discord
import time
import datetime

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View, Select

from commands.Events.helperFunctions import addMora

MORA_EMOTE = "<:MORA:1364030973611610205>"
    

class SortSelection(discord.ui.Select):
    def __init__(self, default="sort by cost (high to low)", initial_author=None):
        self.initial_author = initial_author
        options = []
        sortOptions = [
            "sort by cost (low to high)",
            "sort by cost (high to low)",
            "sort by name (a-z)",
            "sort by name (z-a)",
        ]
        sortOptionsEmoji = [
            "<:price_ascending:1346329079145562112>",
            "<:price_descending:1346329080462577725>",
            "<:name_ascending:1346329053455585324>",
            "<:name_descending:1346329054634053703>",
        ]
        for i in sortOptions:
            if i == default:
                options.append(
                    discord.SelectOption(
                        label=i,
                        emoji=sortOptionsEmoji[sortOptions.index(i)],
                        default=True,
                    )
                )
            else:
                options.append(
                    discord.SelectOption(
                        label=i, emoji=sortOptionsEmoji[sortOptions.index(i)]
                    )
                )
        super().__init__(
            placeholder="Choose the Sorting",
            max_values=1,
            min_values=1,
            options=options,
            custom_id="sortselection",
        )

    async def callback(self, interaction: discord.Interaction):
        ref = db.reference("/Global Events Rewards")
        rewards = ref.get()
        originalList = []
        try:
            for key, val in rewards.items():
                if val["Server ID"] == interaction.guild.id:
                    originalList = val["Rewards"]
                    break
        except Exception:
            pass

        if interaction.data["values"][0] == "sort by cost (low to high)":
            pages = await get_shop_embeds(
                interaction,
                originalList,
                len(originalList) == 0,
                sort_by="cost",
                reverse=False,
            )
        elif interaction.data["values"][0] == "sort by cost (high to low)":
            pages = await get_shop_embeds(
                interaction,
                originalList,
                len(originalList) == 0,
                sort_by="cost",
                reverse=True,
            )
        elif interaction.data["values"][0] == "sort by name (a-z)":
            pages = await get_shop_embeds(
                interaction,
                originalList,
                len(originalList) == 0,
                sort_by="name",
                reverse=False,
            )
        elif interaction.data["values"][0] == "sort by name (z-a)":
            pages = await get_shop_embeds(
                interaction,
                originalList,
                len(originalList) == 0,
                sort_by="name",
                reverse=True,
            )
        else:
            pages = await get_shop_embeds(
                interaction, originalList, len(originalList) == 0
            )

        if interaction.user.guild_permissions.administrator:
            view = Panel(default=interaction.data["values"][0], pages=pages, initial_author=self.initial_author)
        else:
            view = SortSelectionView(default=interaction.data["values"][0], pages=pages, initial_author=self.initial_author)

        view.message = await interaction.response.edit_message(embed=pages[0], view=view)

class SortSelectionView(discord.ui.View):
    def __init__(self, default="sort by price (high to low)", pages=None, initial_author=None, *, timeout=300):
        super().__init__(timeout=timeout)
        self.initial_author = initial_author
        self.add_item(SortSelection(default, self.initial_author))
        self.page = 0
        self.pages = pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.initial_author != interaction.user:
            await interaction.response.send_message("<:no:1036810470860013639> You are not the author of this command", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, Button) and child.style == discord.ButtonStyle.link:
                continue
            child.disabled = True
            if isinstance(child, Select):
                child.add_option(label="Disabled due to timeout", value="X", emoji="<:no:1036810470860013639>", default=True)
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass
        self.stop()

    @discord.ui.button(
        emoji="<:fastbackward:1351972112696479824>", style=discord.ButtonStyle.grey, custom_id="super_prev_shop"
    )
    async def super_prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = 0
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        emoji="<:backarrow:1351972111010369618>", style=discord.ButtonStyle.grey, custom_id="prev_shop"
    )
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        emoji="<:rightarrow:1351972116819480616>", style=discord.ButtonStyle.grey, custom_id="next_shop"
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page < len(self.pages) - 1:
            self.page += 1
        else:
            self.page = 0
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        emoji="<:fastforward:1351972114433048719>", style=discord.ButtonStyle.grey, custom_id="super_next_shop"
    )
    async def super_next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)


class Panel(discord.ui.View):
    def __init__(self, default="sort by price (high to low)", pages=None, initial_author=None):
        super().__init__(timeout=300)
        self.initial_author = initial_author
        self.add_item(SortSelection(default, self.initial_author))
        self.page = 0
        self.pages = pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.initial_author != interaction.user:
            await interaction.response.send_message("<:no:1036810470860013639> You are not the author of this command", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, Button) and child.style == discord.ButtonStyle.link:
                continue
            child.disabled = True
            if isinstance(child, Select):
                 child.add_option(label="Disabled due to timeout", value="X", emoji="<:no:1036810470860013639>", default=True)
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass
        self.stop()

    @discord.ui.button(
        label="Add Reward",
        style=discord.ButtonStyle.green,
        custom_id="addreward",
        row=0,
    )
    async def add_reward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        addRewardModel = AddRewardModel(title=f"Add a Custom Reward")
        if interaction.user.guild_permissions.administrator:
            await interaction.response.send_modal(addRewardModel)
            response = await addRewardModel.wait()
            pages = addRewardModel.pages
            if pages is not None:
                if interaction.user.guild_permissions.administrator:
                    view = Panel(pages=pages, initial_author=interaction.user)
                else:
                    view = SortSelectionView(pages=pages, initial_author=interaction.user)
                view.message = await interaction.edit_original_response(embed=pages[0], view=view)
            await addRewardModel.on_submit_interaction.response.send_message(
                embed=addRewardModel.update, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You are missing `Administrator` permissions.", ephemeral=True
            )

    @discord.ui.button(
        label="Remove Reward",
        style=discord.ButtonStyle.red,
        custom_id="removereward",
        row=0,
    )
    async def remove_reward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        removeRewardModel = RemoveRewardModel(title=f"Remove a Custom Reward")
        if interaction.user.guild_permissions.administrator:
            await interaction.response.send_modal(removeRewardModel)
            response = await removeRewardModel.wait()
            pages = removeRewardModel.pages
            if pages is not None:
                if interaction.user.guild_permissions.administrator:
                    view = Panel(pages=pages, initial_author=interaction.user)
                else:
                    view = SortSelectionView(pages=pages, initial_author=interaction.user)
                view.message = await interaction.edit_original_response(embed=pages[0], view=view)
            await removeRewardModel.on_submit_interaction.response.send_message(
                embed=removeRewardModel.update, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You are missing `Administrator` permissions.", ephemeral=True
            )

    @discord.ui.button(
        label="<<",
        style=discord.ButtonStyle.blurple,
        custom_id="super_prev_shop_admin",
        row=1,
    )
    async def super_prev_button_admin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = 0
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)
        
    @discord.ui.button(
        label="Edit Cost",
        style=discord.ButtonStyle.grey,
        custom_id="editcost",
        row=0,
    )
    async def edit_cost(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.guild_permissions.administrator:
            edit_cost_model = EditCostModel()
            await interaction.response.send_modal(edit_cost_model)
            response = await edit_cost_model.wait()
            pages = edit_cost_model.pages
            if pages is not None:
                if interaction.user.guild_permissions.administrator:
                    view = Panel(pages=pages, initial_author=interaction.user)
                else:
                    view = SortSelectionView(pages=pages, initial_author=interaction.user)
                view.message = await interaction.edit_original_response(embed=pages[0], view=view)
            await edit_cost_model.on_submit_interaction.response.send_message(
                embed=edit_cost_model.update, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You are missing `Administrator` permissions.", ephemeral=True
            )
        
    @discord.ui.button(
        label="Edit Stock",
        style=discord.ButtonStyle.grey,
        custom_id="editstock",
        row=0,
    )
    async def edit_stock(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.guild_permissions.administrator:
            edit_stock_model = EditStockModel()
            await interaction.response.send_modal(edit_stock_model)
            response = await edit_stock_model.wait()
            pages = edit_stock_model.pages
            if pages is not None:
                if interaction.user.guild_permissions.administrator:
                    view = Panel(pages=pages, initial_author=interaction.user)
                else:
                    view = SortSelectionView(pages=pages, initial_author=interaction.user)
                view.message = await interaction.edit_original_response(embed=pages[0], view=view)
            await edit_stock_model.on_submit_interaction.response.send_message(
                embed=edit_stock_model.update, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You are missing `Administrator` permissions.", ephemeral=True
            )

    @discord.ui.button(
        label="<", style=discord.ButtonStyle.blurple, custom_id="prev_shop_admin", row=1
    )
    async def prev_button_admin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        label=">", style=discord.ButtonStyle.blurple, custom_id="next_shop_admin", row=1
    )
    async def next_button_admin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page < len(self.pages) - 1:
            self.page += 1
        else:
            self.page = 0
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        label=">>",
        style=discord.ButtonStyle.blurple,
        custom_id="super_next_shop_admin",
        row=1,
    )
    async def super_next_button_admin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed)


async def get_shop_embeds(
    interaction, item_list, empty_condition, sort_by="cost", reverse=True
):
    if empty_condition:
        return [discord.Embed(title="This server has no purchasable items.")]

    sort_index = {"cost": 2, "name": 0}

    def key_func(x):
        if sort_by == "cost":
            return int(x[sort_index[sort_by]])
        else:
            if isinstance(x[0], int) or x[0].isdigit():  # Check if it's a role ID
                role = interaction.guild.get_role(int(x[0]))
                return role.name.lower() if role else ""  # Use role name for sorting
            return str(x[sort_index[sort_by]]).lower()

    order_text = "Descending" if reverse else "Ascending"
    sort_text = "Cost" if sort_by == "cost" else "Name"

    sorted_items = sorted(item_list, key=key_func, reverse=reverse)
    pages = []
    embed = discord.Embed(
        title=f"{interaction.guild.name}'s Server Shop",
        description=(
            f"You can use {MORA_EMOTE} earned in {interaction.guild.name} to purchase these items.\n"
            f"<:reply:1036792837821435976> *To check your mora balance and inventory, use </mora:1339721187953082543>.*\n"
            f"<:reply:1036792837821435976> *To purchase an item, use </buy:1345883946105311382>.*\n"
            f"<:reply:1036792837821435976> *A 🔄 emoji indicates that the title can be purchased multiple times.*\n"
        ),
        color=discord.Color.gold(),
    )

    for i, item in enumerate(sorted_items):
        count = i + 1
        stock_count = f"\n> **Remaining:** {'<a:out_of_stock:1384990609584033812> ' if item[4] == 0 else ''}`{item[4]}`" if item[4] != -1 else None
        if isinstance(item[0], int) or item[0].isdigit():
            role = interaction.guild.get_role(int(item[0]))
            embed.add_field(
                name=f"{count}ㅤ {MORA_EMOTE} {int(item[2]):,} • {role.name if role else 'Unknown Role'} {'🔄' if (len(item) > 3 and item[3]) else ''}",
                value=f"> **Role:** {role.mention if role else 'N/A'}\n> **Description:** {item[1]}{stock_count if stock_count is not None else ''}",
                inline=False,
            )
        else:
            embed.add_field(
                name=f"{count}ㅤ {MORA_EMOTE} {int(item[2]):,} • {item[0]} {'🔄' if (len(item) > 3 and item[3]) else ''}",
                value=f"> **Description:** {item[1]}{stock_count if stock_count is not None else ''}",
                inline=False,
            )
            
        if (i + 1) % 5 == 0 or (i + 1) == len(sorted_items):
            embed.set_footer(
                text=f"Sorted by {sort_text} in {order_text} order • Page {len(pages) + 1} of {len(sorted_items) // 5 + 1 if len(sorted_items) % 5 != 0 else len(sorted_items) // 5}"
            )
            pages.append(embed)
            embed = discord.Embed(
                title=f"{interaction.guild.name}'s Server Shop",
                description=(
                    f"You can use {MORA_EMOTE} earned in {interaction.guild.name} to purchase these items.\n"
                    f"<:reply:1036792837821435976> *To check your mora balance and inventory, use </mora:1339721187953082543>.*\n"
                    f"<:reply:1036792837821435976> *To purchase an item, use </buy:1345883946105311382>.*\n"
                ),
                color=discord.Color.gold(),
            )

    return pages


class AddRewardModel(discord.ui.Modal, title="Add a Custom Reward"):
    name = discord.ui.TextInput(
        label="Role ID / Reward Title",
        style=discord.TextStyle.short,
        placeholder="Pick one or the other to add",
        required=True,
        max_length=50,
    )
    desc = discord.ui.TextInput(
        label="Description / Perk",
        style=discord.TextStyle.short,
        placeholder="Enter a short description of the reward",
        required=True,
        max_length=150,
    )
    cost = discord.ui.TextInput(
        label="Cost of Reward",
        style=discord.TextStyle.short,
        placeholder="Must be a reasonable integer",
        required=True,
        max_length=10,
    )
    multiple = discord.ui.TextInput(
        label="Enable multiple purchases? (Titles only)",
        style=discord.TextStyle.short,
        placeholder="Enter 'yes' or 'no'",
        required=False,
        max_length=3,
    )
    stock = discord.ui.TextInput(
        label="Stock Count (optional)",
        style=discord.TextStyle.short,
        placeholder="Leave blank for unlimited.",
        required=False,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Global Events Rewards")
        rewards = ref.get()
        originalList = []
        try:
            for key, val in rewards.items():
                if val["Server ID"] == interaction.guild.id:
                    originalList = val["Rewards"]
                    break
        except Exception:
            pass

        duplicate = False
        for item in originalList:
            if item[0] == str(self.name):
                duplicate = True

        multiplier_map = {"k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12}
        cost_lower = str(self.cost).lower()
        self.cost = int(
            float(str(self.cost)[:-1]) * multiplier_map.get(cost_lower[-1], 1)
            if cost_lower[-1] in multiplier_map
            else float(str(self.cost))
        )

        costNotInteger = False
        if not (str(self.cost).isdigit()):
            duplicate = True
            costNotInteger = True

        if str(self.multiple).lower() == "yes":
            multiple = True
        else:
            multiple = False
            
        stock_val = -1
        if self.stock.value.strip() != "":
            try:
                stock_val = int(str(self.stock))
                if stock_val < 0:
                    raise ValueError
            except ValueError:
                self.update = discord.Embed(
                    description=f"Stock must be a non-negative integer <:no:1036810470860013639>",
                    color=discord.Color.red(),
                )

        if duplicate is not True:
            originalList.append(
                [str(self.name), str(self.desc), str(self.cost), multiple, stock_val]
            )

            try:
                for key, val in rewards.items():
                    if val["Server ID"] == interaction.guild.id:
                        db.reference("/Global Events Rewards").child(key).delete()
                        break
            except Exception:
                pass

            data = {
                interaction.guild.id: {
                    "Server ID": interaction.guild.id,
                    "Rewards": originalList,
                }
            }
            for key, value in data.items():
                ref.push().set(value)
            self.update = discord.Embed(
                description=f"Added reward :slight_smile:", color=discord.Color.green()
            )
        else:
            if costNotInteger:
                self.update = discord.Embed(
                    description=f"Cost must be a reasonable integer <:no:1036810470860013639>",
                    color=discord.Color.red(),
                )
            else:
                self.update = discord.Embed(
                    description=f"Found duplicate entry <:no:1036810470860013639>", color=discord.Color.red()
                )
        
        if self.cost <= 0:
            self.update = discord.Embed(
                description=f"Cost must be greater than zero <:no:1036810470860013639>",
                color=discord.Color.red(),
            )

        self.pages = await get_shop_embeds(interaction, originalList, originalList == 0)

        self.on_submit_interaction = interaction
        self.stop()


class RemoveRewardModel(discord.ui.Modal, title="Remove a Custom Reward"):
    name = discord.ui.TextInput(
        label="Role ID / Reward Title",
        style=discord.TextStyle.short,
        placeholder="Pick one or the other to remove",
        required=True,
        max_length=50,
    )

    remove = discord.ui.TextInput(
        label="Remove this item from all and compensate?",
        style=discord.TextStyle.short,
        placeholder="Type 'yes' or 'no'",
        required=True,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Global Events Rewards")
        rewards = ref.get()
        originalList = []
        try:
            for key, val in rewards.items():
                if val["Server ID"] == interaction.guild.id:
                    originalList = val["Rewards"]
                    break
        except Exception:
            pass

        if len(originalList) == 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"Put on your glasses. You haven't added any rewards yet... <:no:1036810470860013639>",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        itemToDelete = None
        for item in originalList:
            if item[0] == str(self.name):
                itemToDelete = item

        if itemToDelete is not None:
            originalList.remove(itemToDelete)
            self.update = discord.Embed(
                description=f"Removed reward :slight_smile:",
                color=discord.Color.green(),
            )
        else:
            self.update = discord.Embed(
                description=f"Reward not found <:no:1036810470860013639>", color=discord.Color.red()
            )

        try:
            for key, val in rewards.items():
                if val["Server ID"] == interaction.guild.id:
                    db.reference("/Global Events Rewards").child(key).delete()
                    break
        except Exception:
            pass

        data = {
            interaction.guild.id: {
                "Server ID": interaction.guild.id,
                "Rewards": originalList,
            }
        }
        for key, value in data.items():
            ref.push().set(value)

        if str(self.remove).lower() == "yes":
            ref = db.reference("/User Events Inventory")
            inventories = ref.get()

            if inventories:
                for key, val in inventories.items():
                    try:
                        inv = [
                            item
                            for item in val["Items"]
                            if not (
                                item[3] == interaction.guild.id
                                and item[0] == str(self.name)
                            )
                        ]

                        if len(inv) < len(val["Items"]): 
                            db.reference("/User Events Inventory").child(key).delete()
                            if len(inv) != 0:
                                data = {
                                    interaction.user.id: {
                                        "User ID": interaction.user.id,
                                        "Items": inv,
                                    }
                                }
                                for key, value in data.items():
                                    ref.push().set(value)

                            try:
                                member = await interaction.guild.fetch_member(
                                    int(val["User ID"])
                                )

                                total_refund = sum(
                                    int(i[2]) for i in val["Items"] if i not in inv
                                )
                                text, addedMora = await addMora(val["User ID"], total_refund, 1, interaction.guild.id, interaction.client)
                                
                                await member.send(
                                    f"**Notice:** One or more items from your guild inventory in **{interaction.guild.name}** have been deleted from the shop. The total original cost of {MORA_EMOTE} `{text}` has been refunded to your inventory."
                                )

                                try:
                                    gangRole = interaction.guild.get_role(
                                        int(item[0])
                                    )  # Keep same logic
                                except Exception:
                                    gangRole = None

                                if (
                                    gangRole is not None
                                    and gangRole in interaction.user.roles
                                ):
                                    await member.remove_roles(gangRole)
                            except Exception:
                                pass
                    except Exception:
                        pass

        self.pages = await get_shop_embeds(interaction, originalList, originalList == 0)

        self.on_submit_interaction = interaction
        self.stop()

class EditCostModel(discord.ui.Modal, title="Edit Item Cost"):
    item = discord.ui.TextInput(
        label="Role ID / Reward Title",
        style=discord.TextStyle.short,
        placeholder="Pick one or the other to edit",
        required=True,
        max_length=50,
    )
    
    cost = discord.ui.TextInput(
        label="New Cost",
        style=discord.TextStyle.short,
        placeholder="Enter new cost value",
        required=True,
        max_length=20,
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Global Events Rewards")
        rewards = ref.get()
        originalList = []
        found_key = None
        
        try:
            for key, val in rewards.items():
                if val["Server ID"] == interaction.guild.id:
                    originalList = val["Rewards"]
                    found_key = key
                    break
        except Exception:
            pass
            
        item_found = False
        multiplier_map = {"k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12}
        
        for item in originalList:
            if item[0] == str(self.item):
                item_found = True
                try:
                    cost_str = str(self.cost).lower().strip()
                    
                    if cost_str[-1] in multiplier_map:
                        new_cost = float(cost_str[:-1]) * multiplier_map[cost_str[-1]]
                    else:
                        new_cost = float(cost_str)
                    
                    if new_cost <= 0:
                        raise ValueError("Cost must be positive")
                    
                    item[2] = str(int(new_cost))
                    self.update = discord.Embed(
                        description=f"Updated cost for **{item[0]}** to {MORA_EMOTE} `{int(new_cost):,}`",
                        color=discord.Color.green(),
                    )
                except Exception:
                    self.update = discord.Embed(
                        description=f"Invalid cost value <:no:1036810470860013639>\nMust be a positive number (e.g. 5000 or 5k)",
                        color=discord.Color.red(),
                    )
                break
                
        if not item_found:
            self.update = discord.Embed(
                description=f"Item **{self.item}** not found <:no:1036810470860013639>",
                color=discord.Color.red(),
            )
            
        if found_key and item_found and "Updated" in self.update.description:
            db.reference("/Global Events Rewards").child(found_key).delete()
            data = {
                interaction.guild.id: {
                    "Server ID": interaction.guild.id,
                    "Rewards": originalList,
                }
            }
            for key, value in data.items():
                ref.push().set(value)
            
        self.pages = await get_shop_embeds(interaction, originalList, len(originalList) == 0)
        self.on_submit_interaction = interaction
        self.stop()

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
    
    print(f"Processed {processed_count} pending edits for guild {guild_id}")
    return processed_count

class EditStockModel(discord.ui.Modal, title="Edit Item Stock"):
    item = discord.ui.TextInput(
        label="Role ID / Reward Title",
        style=discord.TextStyle.short,
        placeholder="Pick one or the other to edit",
        required=True,
        max_length=50,
    )
    
    stock = discord.ui.TextInput(
        label="New Stock Count",
        style=discord.TextStyle.short,
        placeholder="'10', '+5', '-3', or leave blank for unlimited",
        required=False,
        max_length=10,
    )
    
    schedule = discord.ui.TextInput(
        label="Timestamp for Optional Scheduled Update",
        style=discord.TextStyle.short,
        placeholder="Visit unixtimestamp.com (e.g. 1754021240)",
        required=False,
        max_length=10,
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Global Events Rewards")
        rewards = ref.get()
        originalList = []
        found_key = None
        
        try:
            for key, val in rewards.items():
                if val["Server ID"] == interaction.guild.id:
                    originalList = val["Rewards"]
                    found_key = key
                    break
        except Exception:
            pass
        
        await process_pending_stock_edits(interaction.guild.id)
            
        for i, item in enumerate(originalList):
            if len(item) < 5:
                originalList[i] = item + [-1]
                
        item_found = False
        stock_value = str(self.stock).strip()
        schedule_value = str(self.schedule).strip()
        
        if schedule_value:
            try:
                scheduled_time = float(schedule_value)
                current_time = time.time()
                
                if scheduled_time <= current_time:
                    immediate = True
                else:
                    immediate = False
                    
                    pending_ref = db.reference(f"/Pending Shop Edits/{interaction.guild.id}")
                    new_edit = {
                        'item_identifier': str(self.item),
                        'stock_change': stock_value,
                        'scheduled_time': scheduled_time
                    }
                    pending_ref.push().set(new_edit)
                    
                    self.update = discord.Embed(
                        description=f"Scheduled stock update for **{self.item}** at <t:{int(scheduled_time)}>.",
                        color=discord.Color.green(),
                    )
            except ValueError:
                immediate = True
                self.update = discord.Embed(
                    description=f"Invalid timestamp format <:no:1036810470860013639>",
                    color=discord.Color.red(),
                )
        else:
            immediate = True
        
        if immediate:
            for item in originalList:
                if item[0] == str(self.item):
                    item_found = True
                    current_stock = item[4]
                    
                    if not stock_value:
                        new_stock = -1
                    elif stock_value.startswith(('+', '-')):
                        if current_stock == -1:
                            current_stock = 0
                        
                        try:
                            change = int(stock_value)
                            new_stock = current_stock + change
                        except ValueError:
                            sign = stock_value[0]
                            num_str = stock_value[1:].strip()
                            if not num_str:
                                num = 0
                            else:
                                num = int(num_str)
                            new_stock = current_stock + num if sign == '+' else current_stock - num
                    else:
                        try:
                            new_stock = int(stock_value)
                        except ValueError:
                            self.update = discord.Embed(
                                description=f"Invalid stock value <:no:1036810470860013639>",
                                color=discord.Color.red(),
                            )
                            break
                    
                    if new_stock < 0 and new_stock != -1:
                        new_stock = 0
                    
                    item[4] = new_stock
                    self.update = discord.Embed(
                        description=f"Updated stock for **{item[0]}** to `{'Unlimited' if new_stock == -1 else new_stock}`",
                        color=discord.Color.green(),
                    )
                    break
                    
            if not item_found:
                self.update = discord.Embed(
                    description=f"Item **{self.item}** not found <:no:1036810470860013639>",
                    color=discord.Color.red(),
                )
            
            if found_key and item_found:
                db.reference("/Global Events Rewards").child(found_key).delete()
                
            data = {
                interaction.guild.id: {
                    "Server ID": interaction.guild.id,
                    "Rewards": originalList,
                }
            }
            for key, value in data.items():
                ref.push().set(value)
            
        self.pages = await get_shop_embeds(interaction, originalList, len(originalList) == 0)
        self.on_submit_interaction = interaction
        self.stop()
        
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
        
        processed = await process_pending_stock_edits(interaction.guild.id)
        if processed > 0:
            print(f"Processed {processed} scheduled stock updates for guild {interaction.guild.id}")
        
        ref = db.reference("/Global Events System")
        stickies = ref.get()
        found = None
        try:
            for channel in interaction.guild.channels:
                for key, val in stickies.items():
                    if val["Channel ID"] == channel.id:
                        found = val["Events"]
                        break
        except Exception:
            pass

        if found is not None:
            ref = db.reference("/Global Events Rewards")
            rewards = ref.get()
            foundGuild = "Empty"
            try:
                for key, val in rewards.items():
                    if val["Server ID"] == interaction.guild.id:
                        foundGuild = val["Rewards"]
                        break
            except Exception:
                pass

            pages = await get_shop_embeds(
                interaction, foundGuild, foundGuild == "Empty"
            )

            if interaction.user.guild_permissions.administrator:
                view = Panel(pages=pages, initial_author=interaction.user)
            else:
                view = SortSelectionView(pages=pages, initial_author=interaction.user)

            view.message = await interaction.followup.send(embed=pages[0], view=view)
        else:
            embed = discord.Embed(
                title="Random events are not enabled within this server!",
                description=f"What are you thinking? Random event is currently not even enabled in **{interaction.guild.name}**. To enable the function in a channel, use </events enable:1339782470677299260>.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
            
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))