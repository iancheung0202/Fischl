import discord
import time

from discord import app_commands
from discord.ext import commands

from commands.Events.helperFunctions import (
    get_milestones_list, get_milestone_by_name, add_milestone, remove_milestone_by_name,
    update_milestone_field, update_milestone_threshold,
    migrate_milestone_reward, revoke_all_milestone_holders, sync_milestone_holders,
)
from utils.pagination import BasePaginationView, BaseSortSelect
from utils.commands import SlashCommand

from commands.Events.config import (
    YES_EMOTE, NO_EMOTE, REPLY_EMOTE, MILESTONE_SORT_OPTIONS,
    SHOP_CURRENCY_FILTERS, CURRENCY_INFO,
    GUILD_MORA_EMOTE, GLOBAL_MORA_EMOTE, GUILD_SIGIL_EMOTE, GLOBAL_SIGIL_EMOTE,
)


def get_currency_display(currency_type: str) -> str:
    info = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])
    return f"{info['emoji']}"


def parse_threshold(value_str: str) -> int:
    multiplier_map = {"k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12}
    value_lower = value_str.lower().strip()
    if value_lower and value_lower[-1] in multiplier_map:
        return int(float(value_lower[:-1]) * multiplier_map[value_lower[-1]])
    return int(float(value_lower))


async def get_milestone_embeds(
    interaction, milestone_list, empty_condition, sort_by="threshold", reverse=True, currency_filter="all"
):
    if empty_condition:
        return [discord.Embed(title="This server has no milestones set up yet.")], []

    if currency_filter != "all":
        filtered = [m for m in milestone_list if len(m) > 3 and m[3] == currency_filter]
        if not filtered:
            currency_display = get_currency_display(currency_filter)
            return [discord.Embed(title=f"No milestones found for {currency_display}.")], []
        milestone_list = filtered

    def key_func(x):
        if sort_by == "threshold":
            return int(x[2])
        else:  # sort by name
            reward = x[1]
            if str(reward).isdigit():
                role = interaction.guild.get_role(int(reward))
                return role.name.lower() if role else ""
            return str(reward).lower()

    order_text = "Descending" if reverse else "Ascending"
    sort_text = "Threshold" if sort_by == "threshold" else "Name"

    sorted_milestones = sorted(milestone_list, key=key_func, reverse=reverse)
    pages = []
    embed = discord.Embed(
        title=f"{interaction.guild.name}'s Server Milestones",
        description=(
            f"{REPLY_EMOTE} *Unlike {SlashCommand('shop')} items, all milestones cost `0`.*\n"
            f"{REPLY_EMOTE} *You automatically earn roles and titles when reaching certain thresholds. They are designed to be cumulative.*"
        ),
        color=discord.Color.pink(),
    )

    for i, milestone in enumerate(sorted_milestones):
        count = i + 1
        description = milestone[0]
        reward = milestone[1]
        threshold = milestone[2]
        currency_type = milestone[3] if len(milestone) > 3 else "guild_mora"
        currency_display = get_currency_display(currency_type)

        if str(reward).isdigit():
            role = interaction.guild.get_role(int(reward))
            display_name = role.name if role else "Unknown Role"
            embed.add_field(
                name=f"{count}ㅤ {currency_display} {int(threshold):,} • {display_name}",
                value=f"> **Role:** {role.mention if role else 'Unknown'}\n> **Description:** {description}",
                inline=False,
            )
        else:
            embed.add_field(
                name=f"{count}ㅤ {currency_display} {int(threshold):,} • {reward}",
                value=f"> **Description:** {description}",
                inline=False,
            )

        if (i + 1) % 5 == 0 or (i + 1) == len(sorted_milestones):
            embed.set_footer(text=f"Sorted by {sort_text} in {order_text} order")
            pages.append(embed)
            embed = discord.Embed(
                title=f"{interaction.guild.name}'s Server Milestones",
                description=(
                    f"{REPLY_EMOTE} *Unlike {SlashCommand('shop')} items, all milestones cost `0`.*\n"
                    f"{REPLY_EMOTE} *You automatically earn roles and titles when reaching certain thresholds. They are designed to be cumulative.*"
                ),
                color=discord.Color.pink(),
            )

    return pages, sorted_milestones


def build_milestone_detail_embed(milestone, guild=None):
    currency_type = milestone[3] if len(milestone) > 3 else "guild_mora"
    currency_display = get_currency_display(currency_type)
    description_text = f"> **Description:** {milestone[0] if milestone[0] else 'No description provided.'}"

    reward = milestone[1]
    title_name = reward
    if str(reward).isdigit() and guild:
        role_obj = guild.get_role(int(reward))
        if role_obj:
            title_name = role_obj.name
            description_text = f"> **Role:** {role_obj.mention}\n> **Description:** {description_text}"

    embed = discord.Embed(
        title=f"Milestone: {title_name}",
        description=description_text,
        color=discord.Color.pink(),
    )
    embed.add_field(name="Threshold", value=f"{currency_display} `{int(milestone[2]):,}`", inline=True)
    return embed


class MilestoneSort(BaseSortSelect):
    def __init__(self, default="sort by threshold (high to low)", initial_author=None):
        super().__init__(MILESTONE_SORT_OPTIONS, default, initial_author, custom_id="milestonesorting")

    async def callback(self, interaction: discord.Interaction):
        originalList = await get_milestones_list(interaction.client.pool, interaction.guild.id)
        currency_filter = getattr(self.view, "currency_filter", "all")

        sort_mapping = {
            "sort by threshold (low to high)": ("threshold", False),
            "sort by threshold (high to low)": ("threshold", True),
            "sort by name (a-z)": ("name", False),
            "sort by name (z-a)": ("name", True),
        }
        selected_sort = interaction.data["values"][0]
        sort_by, reverse = sort_mapping.get(selected_sort, ("threshold", True))

        pages, items = await get_milestone_embeds(interaction, originalList, len(originalList) == 0, sort_by=sort_by, reverse=reverse, currency_filter=currency_filter)

        view = MilestoneView(pages=pages, items=items, default=selected_sort, initial_author=self.initial_author, is_admin=interaction.user.guild_permissions.administrator, currency_filter=currency_filter, guild_id=interaction.guild.id, pool=interaction.client.pool, guild=interaction.guild)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)


class MilestoneCurrencyFilterSelect(discord.ui.Select):
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
            
        super().__init__(placeholder="Filter by currency...", max_values=1, min_values=1, options=options, custom_id="milestonecurrencyfilter")

    async def callback(self, interaction: discord.Interaction):
        label = self.values[0]
        new_filter = "all"
        for key, info in CURRENCY_INFO.items():
            if info["filter_label"] == label:
                new_filter = key
                break
                
        originalList = await get_milestones_list(interaction.client.pool, interaction.guild.id)
        pages, items = await get_milestone_embeds(interaction, originalList, len(originalList) == 0, currency_filter=new_filter)
        view = MilestoneView(pages=pages, items=items, default="sort by threshold (high to low)", initial_author=self.initial_author, is_admin=interaction.user.guild_permissions.administrator, currency_filter=new_filter, guild_id=interaction.guild.id, pool=interaction.client.pool, guild=interaction.guild)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)


class MilestoneItemSelect(discord.ui.Select):
    def __init__(self, items_page, all_items, guild_id, pool, initial_author, current_page=0, guild=None):
        self.initial_author = initial_author
        self.all_items = all_items
        self.guild_id = guild_id
        self.pool = pool
        self.current_page = current_page
        options = []
        for milestone in items_page:
            reward = milestone[1]
            display = reward
            if str(reward).isdigit():
                role = guild.get_role(int(reward)) if guild else None
                display = role.name if role else "Unknown Role"
            if len(str(display)) > 90:
                display = str(display)[:87] + "..."
            currency_type = milestone[3] if len(milestone) > 3 else "guild_mora"
            currency_emoji = CURRENCY_INFO.get(currency_type, CURRENCY_INFO["guild_mora"])["emoji"]
            threshold = int(milestone[2])
            options.append(
                discord.SelectOption(
                    label=f"{threshold:,} • {display}",
                    emoji=currency_emoji,
                    value=str(reward),
                )
            )
        placeholder = f"Select a milestone to edit (page {current_page+1})..."
        super().__init__(placeholder=placeholder, max_values=1, min_values=1, options=options, row=3)

    async def callback(self, interaction: discord.Interaction):
        reward = self.values[0]
        milestone = await get_milestone_by_name(self.pool, self.guild_id, reward)
        if not milestone:
            return await interaction.response.send_message(f"{NO_EMOTE} Milestone not found.", ephemeral=True)
        embed = build_milestone_detail_embed(milestone, guild=interaction.guild)
        view = MilestoneDetailView(milestone, self.all_items, self.guild_id, self.pool, 0, initial_author=self.initial_author, parent_message=interaction.message)
        await interaction.response.edit_message(embed=embed, view=view)


class MilestoneView(BasePaginationView):
    def __init__(self, pages=None, items=None, initial_author=None, default="sort by threshold (high to low)", is_admin=False, currency_filter="all", guild_id=None, pool=None, guild=None, *, timeout=300):
        self.is_admin = is_admin
        self.currency_filter = currency_filter
        self.guild_id = guild_id
        self.pool = pool
        self.guild = guild
        self.items = items or []
        super().__init__(pages=pages, initial_author=initial_author, timeout=timeout)
        self.add_item(MilestoneSort(default, initial_author))
        self.add_item(MilestoneCurrencyFilterSelect(currency_filter, initial_author))

    def _update_button_states(self) -> None:
        super()._update_button_states()
        to_remove = []
        for child in self.children:
            if isinstance(child, MilestoneItemSelect) or (isinstance(child, discord.ui.Button) and child.label == "Add Milestone"):
                to_remove.append(child)
        for child in to_remove:
            self.remove_item(child)
        if self.is_admin:
            start = self.page * 5
            end = start + 5
            page_items = self.items[start:end]
            if page_items:
                self.add_item(MilestoneItemSelect(page_items, self.items, self.guild_id, self.pool, self.initial_author, current_page=self.page, guild=self.guild))
            self.add_item(MilestoneAddButton(self.guild_id, self.pool, self.initial_author, self.items))


class MilestoneAddButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author=None, items=None):
        super().__init__(label="Add Milestone", style=discord.ButtonStyle.green, row=0)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.items = items or []

    async def callback(self, interaction: discord.Interaction):
        temp_name = f"_new_{int(time.time())}"
        await add_milestone(self.pool, self.guild_id, temp_name, "", 0, "guild_mora")
        milestone = await get_milestone_by_name(self.pool, self.guild_id, temp_name)
        if not milestone:
            return await interaction.response.send_message(f"{NO_EMOTE} Failed to create milestone.", ephemeral=True)
        items = await get_milestones_list(self.pool, self.guild_id)
        embed = build_milestone_detail_embed(milestone, guild=interaction.guild)
        view = MilestoneDetailView(milestone, items, self.guild_id, self.pool, 0, initial_author=self.initial_author, parent_message=interaction.message)
        await interaction.response.edit_message(embed=embed, view=view)


class MilestoneDetailView(discord.ui.View):
    def __init__(self, milestone, all_items, guild_id, pool, item_index, initial_author=None, parent_message=None, *, timeout=300):
        super().__init__(timeout=timeout)
        self.milestone = milestone
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
        milestone = self.milestone
        reward = str(milestone[1])
        self.add_item(MilestoneEditFieldButton("Edit Name", "name", reward, "Role ID / Title", self.guild_id, self.pool, self.initial_author, max_length=100, row=0, item_name=reward))
        self.add_item(MilestoneEditFieldButton("Edit Description", "description", str(milestone[0]), "Description", self.guild_id, self.pool, self.initial_author, max_length=200, required=False, row=0, item_name=reward))
        self.add_item(MilestoneEditFieldButton("Edit Threshold", "threshold", str(milestone[2]), "Mora/Sigils Threshold", self.guild_id, self.pool, self.initial_author, max_length=10, row=0, item_name=reward))
        self.add_item(MilestoneCurrencySelect(self.guild_id, self.pool, self.initial_author, milestone, row=1))
        self.add_item(DeleteMilestoneButton(self.guild_id, self.pool, self.initial_author, row=2, item_name=reward))
        self.add_item(BackToMilestonesButton(self.guild_id, self.pool, self.initial_author, row=2, item_name=reward))

    async def on_timeout(self):
        self.clear_items()
        self.add_item(discord.ui.Button(label="Expired", style=discord.ButtonStyle.grey, disabled=True))
        try:
            if self.parent_message:
                await self.parent_message.edit(view=self)
        except discord.NotFound:
            pass


class MilestoneCurrencySelect(discord.ui.Select):
    def __init__(self, guild_id, pool, initial_author, milestone, row=1):
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = str(milestone[1])
        current_currency = milestone[3] if len(milestone) > 3 else "guild_mora"
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
        await update_milestone_field(self.pool, self.guild_id, self.item_name, "currency_type", new_currency)
        updated_milestone = await get_milestone_by_name(self.pool, self.guild_id, self.item_name)
        if updated_milestone:
            # Switching currencies changes who qualifies, so recheck everyone's balance.
            sync_result = await sync_milestone_holders(self.pool, interaction.guild, updated_milestone)

            items = await get_milestones_list(self.pool, self.guild_id)
            embed = build_milestone_detail_embed(updated_milestone, guild=interaction.guild)
            view = MilestoneDetailView(updated_milestone, items, self.guild_id, self.pool, 0, initial_author=self.initial_author)
            await interaction.response.edit_message(embed=embed, view=view)


class MilestoneEditFieldButton(discord.ui.Button):
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
        modal = MilestoneEditFieldModal(self.field_name, self.current_value, self.field_label, self.guild_id, self.pool, self.initial_author, self.edit_max_length, self.edit_required, self.item_name)
        await interaction.response.send_modal(modal)


class MilestoneEditFieldModal(discord.ui.Modal):
    def __init__(self, field_name, current_value, field_label, guild_id, pool, initial_author, max_length=50, required=True, item_name=None):
        title_map = {
            "name": "Edit Name",
            "description": "Edit Description",
            "threshold": "Edit Threshold",
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
            style=discord.TextStyle.paragraph if field_name == "description" else discord.TextStyle.short,
            placeholder=current_value or "Enter new value",
            required=required,
            max_length=max_length,
            default=str(current_value) if current_value else "",
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        new_value = str(self.input.value).strip()
        old_name = self.item_name

        if self.field_name == "threshold":
            try:
                parsed = parse_threshold(new_value)
                if parsed <= 0:
                    raise ValueError
                new_value = parsed
            except (ValueError, IndexError):
                return await interaction.response.send_message(
                    embed=discord.Embed(description=f"{NO_EMOTE} Threshold must be a valid positive integer.", color=discord.Color.red()),
                    ephemeral=True
                )
            await update_milestone_threshold(self.pool, self.guild_id, old_name, new_value)
        elif self.field_name == "name":
            if not new_value:
                return await interaction.response.send_message(
                    embed=discord.Embed(description=f"{NO_EMOTE} Name cannot be empty.", color=discord.Color.red()),
                    ephemeral=True
                )
            if new_value.isdigit():
                role = interaction.guild.get_role(int(new_value))
                if not role:
                    return await interaction.response.send_message(
                        embed=discord.Embed(description=f"{NO_EMOTE} That role ID doesn't exist in this server!", color=discord.Color.red()),
                        ephemeral=True
                    )
            await update_milestone_field(self.pool, self.guild_id, old_name, "name", new_value)
            # Carry existing holders (and their role, if applicable) over to the new name.
            await migrate_milestone_reward(self.pool, interaction.guild, old_name, new_value)
        else:  # description
            await update_milestone_field(self.pool, self.guild_id, old_name, "description", new_value or "Reached milestone")

        lookup_name = new_value if self.field_name == "name" else old_name
        updated_milestone = await get_milestone_by_name(self.pool, self.guild_id, lookup_name)

        sync_result = {"awarded": 0, "revoked": 0}
        if updated_milestone and self.field_name in ("threshold", "name"):
            # Threshold/name changes can change who qualifies, so recheck everyone's balance.
            sync_result = await sync_milestone_holders(self.pool, interaction.guild, updated_milestone)

        if updated_milestone:
            items = await get_milestones_list(self.pool, self.guild_id)
            embed = build_milestone_detail_embed(updated_milestone, guild=interaction.guild)
            view = MilestoneDetailView(updated_milestone, items, self.guild_id, self.pool, 0, initial_author=self.initial_author)
            await interaction.response.edit_message(embed=embed, view=view)

            if sync_result["awarded"] or sync_result["revoked"]:
                parts = []
                if sync_result["awarded"]:
                    parts.append(f"awarded to {sync_result['awarded']} member(s)")
                if sync_result["revoked"]:
                    parts.append(f"removed from {sync_result['revoked']} member(s) who no longer qualify")
                try:
                    await interaction.followup.send(f"{YES_EMOTE} Milestone rechecked: " + " and ".join(parts) + ".", ephemeral=True)
                except discord.HTTPException:
                    pass


class DeleteMilestoneButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author, row=2, item_name=None):
        super().__init__(label="Delete Milestone", style=discord.ButtonStyle.danger, row=row)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        name_to_delete = self.item_name or str(interaction.message.embeds[0].title).replace("Milestone: ", "")
        view = ConfirmDeleteMilestoneView(name_to_delete, self.guild_id, self.pool, self.initial_author, parent_message=interaction.message)
        await interaction.response.send_message(
            embed=discord.Embed(description="Are you sure you want to delete this milestone? This cannot be undone.", color=discord.Color.red()),
            view=view,
            ephemeral=True
        )


class ConfirmDeleteMilestoneView(discord.ui.View):
    def __init__(self, item_name, guild_id, pool, initial_author, parent_message=None):
        super().__init__(timeout=30)
        self.item_name = item_name
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.parent_message = parent_message

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await remove_milestone_by_name(self.pool, self.guild_id, self.item_name)
        # Deleting a milestone means nobody should hold its reward anymore.
        revoked_count = await revoke_all_milestone_holders(self.pool, interaction.guild, self.item_name)

        items = await get_milestones_list(self.pool, self.guild_id)
        pages, sorted_items = await get_milestone_embeds(interaction, items, len(items) == 0)
        is_admin = interaction.user.guild_permissions.administrator
        view = MilestoneView(pages=pages, items=sorted_items, initial_author=self.initial_author, is_admin=is_admin, guild_id=self.guild_id, pool=self.pool, guild=interaction.guild)

        content = f"{YES_EMOTE} Milestone has been deleted."
        if revoked_count:
            content += f" Removed it from {revoked_count} member(s) who had it."

        await interaction.response.edit_message(
            content=content,
            embed=None, view=None
        )
        if self.parent_message:
            try:
                await self.parent_message.edit(embed=pages[0], view=view)
            except (discord.HTTPException, discord.NotFound):
                pass


class BackToMilestonesButton(discord.ui.Button):
    def __init__(self, guild_id, pool, initial_author, row=2, item_name=None):
        super().__init__(label="Back to Milestones", style=discord.ButtonStyle.blurple, row=row)
        self.guild_id = guild_id
        self.pool = pool
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        milestone = await get_milestone_by_name(self.pool, self.guild_id, self.item_name) if self.item_name else None
        sync_result = {"awarded": 0, "revoked": 0}

        if milestone:
            description = str(milestone[0]).strip()
            reward = str(milestone[1]).strip()
            try:
                threshold = int(milestone[2])
            except (ValueError, TypeError):
                threshold = 0
            currency_type = milestone[3] if len(milestone) > 3 else "guild_mora"
            valid_currencies = {"guild_mora", "global_mora", "guild_sigils", "global_sigils"}

            errors = []
            if not reward or reward.startswith("_new_"):
                errors.append("Reward title/role ID is required")
            if threshold <= 0:
                errors.append("Threshold must be a positive number")
            if currency_type not in valid_currencies:
                errors.append("Currency type is invalid")

            if errors:
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Cannot return to milestones yet",
                        description="\n".join(f"{NO_EMOTE} {e}" for e in errors),
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

            if not description:
                await update_milestone_field(self.pool, self.guild_id, reward, "description", "Reached milestone")
                description = "Reached milestone"

            # Final consistency check: award anyone now qualifying, revoke anyone who
            # no longer does, based on the milestone's finalized criteria.
            finalized_milestone = [description, reward, threshold, currency_type]
            sync_result = await sync_milestone_holders(self.pool, interaction.guild, finalized_milestone)

        foundGuild = await get_milestones_list(self.pool, self.guild_id)
        pages, sorted_items = await get_milestone_embeds(interaction, foundGuild, len(foundGuild) == 0)

        is_admin = interaction.user.guild_permissions.administrator
        view = MilestoneView(pages=pages, items=sorted_items, initial_author=self.initial_author, is_admin=is_admin, guild_id=self.guild_id, pool=self.pool, guild=interaction.guild)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)

        if sync_result["awarded"] or sync_result["revoked"]:
            parts = []
            if sync_result["awarded"]:
                parts.append(f"awarded to {sync_result['awarded']} existing qualifying member(s)")
            if sync_result["revoked"]:
                parts.append(f"removed from {sync_result['revoked']} member(s) who no longer qualify")
            try:
                await interaction.followup.send(
                    f"{YES_EMOTE} Milestone saved and " + " and ".join(parts) + ".",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass


class Milestones(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="milestones", description="View the guild milestones (Admins can edit here too)"
    )
    async def milestones(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(thinking=True)

        foundGuild = await get_milestones_list(interaction.client.pool, interaction.guild.id)

        pages, sorted_items = await get_milestone_embeds(
            interaction, foundGuild, len(foundGuild) == 0
        )

        is_admin = interaction.user.guild_permissions.administrator
        view = MilestoneView(pages=pages, items=sorted_items, initial_author=interaction.user, is_admin=is_admin, guild_id=interaction.guild.id, pool=interaction.client.pool, guild=interaction.guild)

        view.message = await interaction.followup.send(embed=pages[0], view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Milestones(bot))