"""Server milestones: the /milestones list, and the screens admins edit them with."""

import time

import discord
from discord import app_commands
from discord.ext import commands

from commands.Events.config import (
    CURRENCY_INFO,
    MILESTONE_SORT_OPTIONS,
    NO_EMOTE,
    REPLY_EMOTE,
    SHOP_CURRENCY_FILTERS,
    YES_EMOTE,
)
from commands.Events.helperFunctions import (
    add_milestone,
    get_milestone_by_name,
    get_milestones_list,
    migrate_milestone_reward,
    remove_milestone_by_name,
    revoke_all_milestone_holders,
    sync_milestone_holders,
    update_milestone_field,
    update_milestone_threshold,
)
from utils.commands import SlashCommand
from utils.pagination import BasePaginationView, BaseSortSelect

# A milestone is [description, reward, threshold, currency]; the reward is a title or a role ID.
DEFAULT_SORT = "sort by threshold (high to low)"
SORTS = {
    "sort by threshold (low to high)": ("threshold", False),
    DEFAULT_SORT: ("threshold", True),
    "sort by name (a-z)": ("name", False),
    "sort by name (z-a)": ("name", True),
}
MULTIPLIERS = {"k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12}
# What each edit button changes: its place in the milestone, the box label, the longest text, if it must be filled.
FIELDS = {
    "name": (1, "Role ID / Title", 100, True),
    "description": (0, "Description", 200, False),
    "threshold": (2, "Mora/Sigils Threshold", 10, True),
}


def get_currency_display(currency_type: str) -> str:
    """Gives the emoji of a currency, the server's Mora for one it does not know."""
    return f"{CURRENCY_INFO.get(currency_type, CURRENCY_INFO['guild_mora'])['emoji']}"


def parse_threshold(value_str: str) -> int:
    """Reads a number such as `1500`, `2.5k` or `3m`."""
    text = value_str.lower().strip()
    if text and text[-1] in MULTIPLIERS:
        return int(float(text[:-1]) * MULTIPLIERS[text[-1]])
    return int(float(text))


def list_page(guild):
    """Gives an empty page of the milestone list."""
    return discord.Embed(
        title=f"{guild.name}'s Server Milestones",
        description=(
            f"{REPLY_EMOTE} *Unlike {SlashCommand('shop')} items, all milestones cost `0`.*\n"
            f"{REPLY_EMOTE} *You automatically earn roles and titles when reaching certain thresholds. They are designed to be cumulative.*"
        ),
        color=discord.Color.pink(),
    )


def get_milestone_embeds(
    guild, milestones, sort_by="threshold", reverse=True, currency_filter="all"
):
    """Gives the list as pages of five, and the milestones in the order shown."""
    if not milestones:
        return [discord.Embed(title="This server has no milestones set up yet.")], []
    if currency_filter != "all":
        milestones = [m for m in milestones if m[3] == currency_filter]
        if not milestones:
            return [
                discord.Embed(
                    title=f"No milestones found for {get_currency_display(currency_filter)}."
                )
            ], []

    def name(milestone):
        reward = str(milestone[1])
        if reward.isdigit():
            role = guild.get_role(int(reward))
            return role.name.lower() if role else ""
        return reward.lower()

    ordered = sorted(
        milestones,
        key=(lambda m: int(m[2])) if sort_by == "threshold" else name,
        reverse=reverse,
    )
    footer = f"Sorted by {'Threshold' if sort_by == 'threshold' else 'Name'} in {'Descending' if reverse else 'Ascending'} order"
    pages = []
    for i, (description, reward, threshold, currency) in enumerate(ordered):
        if i % 5 == 0:
            pages.append(list_page(guild).set_footer(text=footer))
        start = f"{i + 1}ㅤ {get_currency_display(currency)} {int(threshold):,} • "
        if str(reward).isdigit():
            role = guild.get_role(int(reward))
            pages[-1].add_field(
                name=start + (role.name if role else "Unknown Role"),
                value=f"> **Role:** {role.mention if role else 'Unknown'}\n> **Description:** {description}",
                inline=False,
            )
        else:
            pages[-1].add_field(
                name=f"{start}{reward}",
                value=f"> **Description:** {description}",
                inline=False,
            )
    return pages, ordered


def build_milestone_detail_embed(milestone, guild=None):
    """Gives the screen showing one milestone."""
    description, reward, threshold, currency = milestone
    title = reward
    text = f"> **Description:** {description if description else 'No description provided.'}"
    role = guild.get_role(int(reward)) if str(reward).isdigit() and guild else None
    if role:
        title = role.name
        text = f"> **Role:** {role.mention}\n> **Description:** {text}"
    return discord.Embed(
        title=f"Milestone: {title}", description=text, color=discord.Color.pink()
    ).add_field(
        name="Threshold",
        value=f"{get_currency_display(currency)} `{int(threshold):,}`",
        inline=True,
    )


async def listing(interaction, author, sort=DEFAULT_SORT, currency_filter="all"):
    """Reads the server's milestones; gives the first page of the list and its view."""
    milestones = await get_milestones_list(
        interaction.client.pool, interaction.guild.id
    )
    pages, ordered = get_milestone_embeds(
        interaction.guild,
        milestones,
        *SORTS.get(sort, SORTS[DEFAULT_SORT]),
        currency_filter,
    )
    view = MilestoneView(
        pages,
        ordered,
        author,
        sort,
        interaction.user.guild_permissions.administrator,
        currency_filter,
        interaction.guild,
    )
    return pages[0], view


async def show_detail(interaction, milestone, author, parent_message=None):
    """Swaps the message for the screen of one milestone."""
    await interaction.response.edit_message(
        embed=build_milestone_detail_embed(milestone, guild=interaction.guild),
        view=MilestoneDetailView(milestone, author, parent_message),
    )


async def say_recheck(interaction, result, start, awarded):
    """Tells the admin how many members gained or lost the reward, if any did."""
    parts = []
    if result["awarded"]:
        parts.append(f"awarded to {result['awarded']} {awarded}")
    if result["revoked"]:
        parts.append(
            f"removed from {result['revoked']} member(s) who no longer qualify"
        )
    if not parts:
        return
    try:
        await interaction.followup.send(
            f"{YES_EMOTE} {start}" + " and ".join(parts) + ".", ephemeral=True
        )
    except discord.HTTPException:
        pass


def refuse(text, title=None):
    """Gives the red embed that turns an edit down."""
    return discord.Embed(title=title, description=text, color=discord.Color.red())


class MilestoneSort(BaseSortSelect):
    """The menu that orders the list."""

    def __init__(self, default=DEFAULT_SORT, initial_author=None):
        super().__init__(
            MILESTONE_SORT_OPTIONS,
            default,
            initial_author,
            custom_id="milestonesorting",
        )

    async def callback(self, interaction: discord.Interaction):
        embed, view = await listing(
            interaction,
            self.initial_author,
            interaction.data["values"][0],
            getattr(self.view, "currency_filter", "all"),
        )
        view.message = await interaction.response.edit_message(embed=embed, view=view)


class MilestoneCurrencyFilterSelect(discord.ui.Select):
    """The menu that keeps only the milestones of one currency."""

    def __init__(self, current_filter="all", initial_author=None):
        self.initial_author = initial_author
        options = [
            discord.SelectOption(
                label="All currencies",
                emoji=dict(SHOP_CURRENCY_FILTERS).get("All currencies"),
                default=current_filter == "all",
            )
        ] + [
            discord.SelectOption(
                label=info["filter_label"],
                emoji=info["emoji"],
                default=current_filter == key,
            )
            for key, info in CURRENCY_INFO.items()
        ]
        super().__init__(
            placeholder="Filter by currency...",
            max_values=1,
            min_values=1,
            options=options,
            custom_id="milestonecurrencyfilter",
        )

    async def callback(self, interaction: discord.Interaction):
        chosen = next(
            (
                key
                for key, info in CURRENCY_INFO.items()
                if info["filter_label"] == self.values[0]
            ),
            "all",
        )
        embed, view = await listing(
            interaction, self.initial_author, currency_filter=chosen
        )
        view.message = await interaction.response.edit_message(embed=embed, view=view)


class MilestoneItemSelect(discord.ui.Select):
    """The admin menu that opens one of the milestones on the page."""

    def __init__(self, items_page, initial_author, current_page=0, guild=None):
        self.initial_author = initial_author
        options = []
        for _, reward, threshold, currency in items_page:
            display = reward
            if str(reward).isdigit():
                role = guild.get_role(int(reward)) if guild else None
                display = role.name if role else "Unknown Role"
            if len(str(display)) > 90:
                display = str(display)[:87] + "..."
            options.append(
                discord.SelectOption(
                    label=f"{int(threshold):,} • {display}",
                    emoji=get_currency_display(currency),
                    value=str(reward),
                )
            )
        super().__init__(
            placeholder=f"Select a milestone to edit (page {current_page+1})...",
            max_values=1,
            min_values=1,
            options=options,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        milestone = await get_milestone_by_name(
            interaction.client.pool, interaction.guild.id, self.values[0]
        )
        if not milestone:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Milestone not found.", ephemeral=True
            )
        await show_detail(
            interaction, milestone, self.initial_author, interaction.message
        )


class MilestoneView(BasePaginationView):
    """The list, with its sort and filter menus and, for admins, the edit controls."""

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
        self.add_item(MilestoneSort(default, initial_author))
        self.add_item(MilestoneCurrencyFilterSelect(currency_filter, initial_author))

    def _update_button_states(self) -> None:
        super()._update_button_states()
        for child in [
            child
            for child in self.children
            if isinstance(child, (MilestoneItemSelect, MilestoneAddButton))
        ]:
            self.remove_item(child)
        if not self.is_admin:
            return
        page_items = self.items[self.page * 5 : self.page * 5 + 5]
        if page_items:
            self.add_item(
                MilestoneItemSelect(
                    page_items, self.initial_author, self.page, self.guild
                )
            )
        self.add_item(MilestoneAddButton(self.initial_author))


class MilestoneAddButton(discord.ui.Button):
    """Makes an empty milestone and opens it for editing."""

    def __init__(self, initial_author=None):
        super().__init__(label="Add Milestone", style=discord.ButtonStyle.green, row=0)
        self.initial_author = initial_author

    async def callback(self, interaction: discord.Interaction):
        pool, guild_id = interaction.client.pool, interaction.guild.id
        name = f"_new_{int(time.time())}"
        await add_milestone(pool, guild_id, name, "", 0, "guild_mora")
        milestone = await get_milestone_by_name(pool, guild_id, name)
        if not milestone:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Failed to create milestone.", ephemeral=True
            )
        await show_detail(
            interaction, milestone, self.initial_author, interaction.message
        )


class MilestoneDetailView(discord.ui.View):
    """The screen of one milestone: three edit buttons, the currency, delete and back."""

    def __init__(self, milestone, initial_author=None, parent_message=None):
        super().__init__(timeout=300)
        self.initial_author = initial_author
        self.parent_message = parent_message
        for field in FIELDS:
            self.add_item(MilestoneEditFieldButton(field, milestone, initial_author))
        self.add_item(MilestoneCurrencySelect(initial_author, milestone))
        self.add_item(DeleteMilestoneButton(initial_author, str(milestone[1])))
        self.add_item(BackToMilestonesButton(initial_author, str(milestone[1])))

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
                label="Expired", style=discord.ButtonStyle.grey, disabled=True
            )
        )
        try:
            if self.parent_message:
                await self.parent_message.edit(view=self)
        except discord.NotFound:
            pass


class MilestoneCurrencySelect(discord.ui.Select):
    """Picks the currency the threshold is counted in."""

    def __init__(self, initial_author, milestone):
        self.initial_author = initial_author
        self.item_name = str(milestone[1])
        super().__init__(
            placeholder="Select a currency...",
            max_values=1,
            min_values=1,
            options=[
                discord.SelectOption(
                    label=info["label"],
                    value=key,
                    emoji=info["emoji"],
                    default=milestone[3] == key,
                )
                for key, info in CURRENCY_INFO.items()
            ],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        pool, guild_id = interaction.client.pool, interaction.guild.id
        await update_milestone_field(
            pool, guild_id, self.item_name, "currency_type", self.values[0]
        )
        milestone = await get_milestone_by_name(pool, guild_id, self.item_name)
        if milestone:
            # Another currency changes who qualifies.
            await sync_milestone_holders(pool, interaction.guild, milestone)
            await show_detail(interaction, milestone, self.initial_author)


class MilestoneEditFieldButton(discord.ui.Button):
    """Opens the box that edits the name, the description or the threshold."""

    def __init__(self, field_name, milestone, initial_author):
        super().__init__(
            label=f"Edit {field_name.capitalize()}",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.field_name = field_name
        self.milestone = milestone
        self.initial_author = initial_author

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            MilestoneEditFieldModal(
                self.field_name, self.milestone, self.initial_author
            )
        )


class MilestoneEditFieldModal(discord.ui.Modal):
    """The box that edits one field, then rechecks who holds the reward."""

    def __init__(self, field_name, milestone, initial_author):
        super().__init__(title=f"Edit {field_name.capitalize()}")
        place, label, longest, required = FIELDS[field_name]
        value = str(milestone[place])
        self.field_name = field_name
        self.initial_author = initial_author
        # A milestone with no name is found by the value being edited.
        self.item_name = str(milestone[1]) or value
        self.input = discord.ui.TextInput(
            label=label,
            style=(
                discord.TextStyle.paragraph
                if field_name == "description"
                else discord.TextStyle.short
            ),
            placeholder=value or "Enter new value",
            required=required,
            max_length=longest,
            default=value,
        )
        self.add_item(self.input)

    async def save(self, interaction, value):
        """Stores the new value; gives the milestone's name after, or None when turned down."""
        pool, guild_id, name = (
            interaction.client.pool,
            interaction.guild.id,
            self.item_name,
        )
        if self.field_name == "threshold":
            try:
                threshold = parse_threshold(value)
                if threshold <= 0:
                    raise ValueError
            except (ValueError, IndexError):
                return await self.turn_down(
                    interaction, "Threshold must be a valid positive integer."
                )
            await update_milestone_threshold(pool, guild_id, name, threshold)
        elif self.field_name == "name":
            if not value:
                return await self.turn_down(interaction, "Name cannot be empty.")
            if value.isdigit() and not interaction.guild.get_role(int(value)):
                return await self.turn_down(
                    interaction, "That role ID doesn't exist in this server!"
                )
            await update_milestone_field(pool, guild_id, name, "name", value)
            # Members who hold the old name (and its role) keep it under the new one.
            await migrate_milestone_reward(pool, interaction.guild, name, value)
            return value
        else:
            await update_milestone_field(
                pool, guild_id, name, "description", value or "Reached milestone"
            )
        return name

    async def turn_down(self, interaction, reason):
        """Tells the admin why the value was not saved."""
        await interaction.response.send_message(
            embed=refuse(f"{NO_EMOTE} {reason}"), ephemeral=True
        )

    async def on_submit(self, interaction: discord.Interaction):
        name = await self.save(interaction, str(self.input.value).strip())
        if name is None:
            return
        pool = interaction.client.pool
        milestone = await get_milestone_by_name(pool, interaction.guild.id, name)
        if not milestone:
            return
        result = {"awarded": 0, "revoked": 0}
        if self.field_name in ("threshold", "name"):
            # A new threshold or name can change who qualifies.
            result = await sync_milestone_holders(pool, interaction.guild, milestone)
        await show_detail(interaction, milestone, self.initial_author)
        await say_recheck(interaction, result, "Milestone rechecked: ", "member(s)")


class DeleteMilestoneButton(discord.ui.Button):
    """Asks before deleting the milestone."""

    def __init__(self, initial_author, item_name):
        super().__init__(
            label="Delete Milestone", style=discord.ButtonStyle.danger, row=2
        )
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=refuse(
                "Are you sure you want to delete this milestone? This cannot be undone."
            ),
            view=ConfirmDeleteMilestoneView(
                self.item_name
                or str(interaction.message.embeds[0].title).replace("Milestone: ", ""),
                self.initial_author,
                interaction.message,
            ),
            ephemeral=True,
        )


class ConfirmDeleteMilestoneView(discord.ui.View):
    """The Yes button that deletes a milestone and takes it from everyone."""

    def __init__(self, item_name, initial_author, parent_message=None):
        super().__init__(timeout=30)
        self.item_name = item_name
        self.initial_author = initial_author
        self.parent_message = parent_message

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm_delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pool = interaction.client.pool
        await remove_milestone_by_name(pool, interaction.guild.id, self.item_name)
        revoked = await revoke_all_milestone_holders(
            pool, interaction.guild, self.item_name
        )
        embed, view = await listing(interaction, self.initial_author)
        content = f"{YES_EMOTE} Milestone has been deleted."
        if revoked:
            content += f" Removed it from {revoked} member(s) who had it."
        await interaction.response.edit_message(content=content, embed=None, view=None)
        if self.parent_message:
            try:
                await self.parent_message.edit(embed=embed, view=view)
            except discord.HTTPException:
                pass


class BackToMilestonesButton(discord.ui.Button):
    """Checks the milestone is complete, rechecks its holders and returns to the list."""

    def __init__(self, initial_author, item_name):
        super().__init__(
            label="Back to Milestones", style=discord.ButtonStyle.blurple, row=2
        )
        self.initial_author = initial_author
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        pool, guild_id = interaction.client.pool, interaction.guild.id
        milestone = None
        if self.item_name:
            milestone = await get_milestone_by_name(pool, guild_id, self.item_name)
        result = {"awarded": 0, "revoked": 0}
        if milestone:
            description = str(milestone[0]).strip()
            reward = str(milestone[1]).strip()
            try:
                threshold = int(milestone[2])
            except (ValueError, TypeError):
                threshold = 0
            errors = []
            if not reward or reward.startswith("_new_"):
                errors.append("Reward title/role ID is required")
            if threshold <= 0:
                errors.append("Threshold must be a positive number")
            if milestone[3] not in CURRENCY_INFO:
                errors.append("Currency type is invalid")
            if errors:
                return await interaction.response.send_message(
                    embed=refuse(
                        "\n".join(f"{NO_EMOTE} {error}" for error in errors),
                        "Cannot return to milestones yet",
                    ),
                    ephemeral=True,
                )
            if not description:
                description = "Reached milestone"
                await update_milestone_field(
                    pool, guild_id, reward, "description", description
                )
            result = await sync_milestone_holders(
                pool, interaction.guild, [description, reward, threshold, milestone[3]]
            )

        embed, view = await listing(interaction, self.initial_author)
        view.message = await interaction.response.edit_message(embed=embed, view=view)
        await say_recheck(
            interaction,
            result,
            "Milestone saved and ",
            "existing qualifying member(s)",
        )


class Milestones(commands.Cog):
    """The /milestones command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="milestones",
        description="View the guild milestones (Admins can edit here too)",
    )
    async def milestones(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        embed, view = await listing(interaction, interaction.user)
        view.message = await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Milestones(bot))
