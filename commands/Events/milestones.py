import discord
import time

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View, Select

from commands.Events.helperFunctions import get_guild_mora, get_users_by_mora_threshold
from utils.pagination import BasePaginationView, BaseSortSelect

MORA_EMOTE = "<:MORA:1364030973611610205>"

MILESTONE_SORT_OPTIONS = [
    ("sort by threshold (low to high)", "<:price_ascending:1346329079145562112>"),
    ("sort by threshold (high to low)", "<:price_descending:1346329080462577725>"),
    ("sort by name (a-z)", "<:name_ascending:1346329053455585324>"),
    ("sort by name (z-a)", "<:name_descending:1346329054634053703>"),
]

def get_milestone_embeds(interaction: discord.Interaction, milestones: list, sort_by="threshold", reverse=True) -> list:
    if not milestones:
        return [discord.Embed(description="This server has no milestones set up yet.", color=discord.Color.default())]
    
    def sort_key(x):
        milestone = x[1]
        if sort_by == "threshold":
            return int(milestone[2])
        else:  # sort by name
            reward = milestone[1]
            if str(reward).isdigit():
                role = interaction.guild.get_role(int(reward))
                return role.name.lower() if role else ""
            return str(reward).lower()
    
    sorted_milestones = sorted(
        enumerate(milestones),
        key=sort_key,
        reverse=reverse
    )
    
    pages = []
    page = discord.Embed(
        title=f"{interaction.guild.name}'s Server Milestones",
        description=(
            f"<:reply:1036792837821435976> *Unlike </shop:1345883946105311383> items, all milestones cost {MORA_EMOTE} `0`.*\n"
            "<:reply:1036792837821435976> *You automatically earn roles and titles when reaching certain thresholds.*\n"
            "<:reply:1036792837821435976> *Server milestones are designed to be cumulative.*"
        ),
        color=discord.Color.pink()
    )
    count = 0
    
    for idx, milestone in sorted_milestones:
        description = milestone[0] 
        reward = milestone[1]  
        threshold = milestone[2]  
        
        if str(reward).isdigit():
            role = interaction.guild.get_role(int(reward))
            display_name = f"{role.name}" if role else "Unknown Role"
            page.add_field(
                name=f"{MORA_EMOTE} {threshold:,} • {display_name}",
                value=f"> **Role:** {role.mention if role else 'Unknown'}\n> **Description:** {description}",
                inline=False
            )
        else:
            display_name = f"{reward}"
            page.add_field(
                name=f"{MORA_EMOTE} {threshold:,} • {display_name}",
                value=f"> **Description:** {description}",
                inline=False
            )
        
        count += 1
        if count % 5 == 0:
            pages.append(page)
            page = discord.Embed(
                title=f"{interaction.guild.name}'s Server Milestones",
                description=(
                    f"<:reply:1036792837821435976> *Unlike </shop:1345883946105311383> items, all milestones cost {MORA_EMOTE} `0`.*\n"
                    "<:reply:1036792837821435976> *You automatically earn roles and titles when reaching certain thresholds.*\n"
                    "<:reply:1036792837821435976> *Server milestones are designed to be cumulative.*"
                ),
                color=discord.Color.pink()
            )
    
    if count % 5 != 0 or count == 0:
        pages.append(page)
    
    for i, embed in enumerate(pages):
        embed.set_footer(text=f"Page {i+1}/{len(pages)}")
    
    return pages

class MilestoneModal(discord.ui.Modal, title="Add a Milestone"):
    threshold = discord.ui.TextInput(
        label="Mora Threshold",
        style=discord.TextStyle.short,
        placeholder="e.g., 10000",
        required=True,
        max_length=10,
    )
    
    reward = discord.ui.TextInput(
        label="Role ID / Title",
        style=discord.TextStyle.short,
        placeholder="Role ID (must be a number) or Title text",
        required=True,
        max_length=100,
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="What does this milestone represent?",
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            threshold = int(self.threshold.value)
            if threshold <= 0:
                await interaction.followup.send("Threshold must be a positive integer!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Threshold must be a number!", ephemeral=True)
            return
        
        reward = self.reward.value
        description = self.description.value or "Reached milestone"
        
        if reward.isdigit():
            role = interaction.guild.get_role(int(reward))
            if not role:
                await interaction.followup.send("That role ID doesn't exist in this server!", ephemeral=True)
                return
        
        ref = db.reference(f"/Chat Minigames Rewards/{interaction.guild.id}/milestones")
        milestones = ref.get() or []
        # New format: [description, reward, threshold]
        milestone_data = [description, reward, threshold]
        milestones.append(milestone_data)
        ref.set(milestones)
        
        count = 0
        qualified_users = await get_users_by_mora_threshold(interaction.client.pool, interaction.guild.id, threshold)

        from commands.Events.helperFunctions import get_user_inventory, add_inventory_item

        for user_id, mora_amount in qualified_users:
            inventory = await get_user_inventory(interaction.client.pool, user_id, interaction.guild.id)
            has_reward = any(item[0] == reward for item in inventory)
            
            if not has_reward:
                count += 1
                await add_inventory_item(
                    interaction.client.pool, 
                    user_id, 
                    interaction.guild.id, 
                    reward, 
                    description,
                    0,  # cost is 0 because it's a milestone
                    int(time.time()), 
                    pinned=False
                )
                
                if reward.isdigit():
                    try:
                        member = await interaction.guild.fetch_member(user_id)
                        role = interaction.guild.get_role(int(reward))
                        if member and role:
                            await member.add_roles(role)
                    except Exception:
                        pass
        
        milestones_ref = db.reference(f"/Milestones/{interaction.guild.id}")
        updated_milestones = milestones_ref.get() or {}
        self.pages = get_milestone_embeds(interaction, updated_milestones) 
        
        await interaction.followup.send(
            f"✅ Milestone added successfully! It has also been awarded to existing players who qualified.",
            ephemeral=True
        )

class RemoveMilestoneModal(discord.ui.Modal, title="Remove a Milestone"):
    milestone_name = discord.ui.TextInput(
        label="Milestone Name",
        style=discord.TextStyle.short,
        placeholder="Enter exact milestone name",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        name = self.milestone_name.value.strip()
        ref = db.reference(f"/Chat Minigames Rewards/{interaction.guild.id}/milestones")
        milestones = ref.get() or []
        removed = False
        
        new_milestones = []
        for milestone in milestones:
            if isinstance(milestone, list) and len(milestone) >= 2 and milestone[1] != name:
                new_milestones.append(milestone)
            elif milestone[1] == name:
                removed = True
        
        if removed:
            ref.set(new_milestones)
            self.pages = get_milestone_embeds(interaction, new_milestones)
            await interaction.response.send_message("✅ Milestone removed successfully.", ephemeral=True)
        else:
            await interaction.response.send_message("Milestone not found!", ephemeral=True)


class MilestoneSort(BaseSortSelect):
    def __init__(self, default="sort by threshold (high to low)", initial_author=None):
        super().__init__(MILESTONE_SORT_OPTIONS, default, initial_author, custom_id="milestonesorting")

    async def callback(self, interaction: discord.Interaction):
        ref = db.reference(f"/Chat Minigames Rewards/{interaction.guild.id}/milestones")
        milestones = ref.get() or []

        sort_mapping = {
            "sort by threshold (low to high)": ("threshold", False),
            "sort by threshold (high to low)": ("threshold", True),
            "sort by name (a-z)": ("name", False),
            "sort by name (z-a)": ("name", True),
        }

        selected_sort = interaction.data["values"][0]
        sort_by, reverse = sort_mapping.get(selected_sort, ("threshold", True))

        pages = get_milestone_embeds(interaction, milestones, sort_by=sort_by, reverse=reverse)

        view = MilestonePageView(pages=pages, default=selected_sort, initial_author=self.initial_author, is_admin=interaction.user.guild_permissions.administrator)
        view.message = await interaction.response.edit_message(embed=pages[0], view=view)


class MilestonePageView(BasePaginationView):
    def __init__(self, pages, initial_author=None, default="sort by threshold (high to low)", is_admin=False):
        self.is_admin = is_admin
        super().__init__(pages=pages, initial_author=initial_author, timeout=300)
        self.add_item(MilestoneSort(default, initial_author))

    @discord.ui.button(label="Add Milestone", style=discord.ButtonStyle.green, custom_id="add_milestone", row=1)
    async def add_milestone(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("<:no:1036810470860013639> You need administrator permissions to do that.", ephemeral=True)
            return
        modal = MilestoneModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if hasattr(modal, 'pages'):
            self.pages = modal.pages
            self.page = 0
            await self.message.edit(embed=self.pages[0], view=self)

    @discord.ui.button(label="Remove Milestone", style=discord.ButtonStyle.red, custom_id="remove_milestone", row=1)
    async def remove_milestone(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("<:no:1036810470860013639> You need administrator permissions to do that.", ephemeral=True)
            return
        modal = RemoveMilestoneModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if hasattr(modal, 'pages'):
            self.pages = modal.pages
            self.page = 0
            await self.message.edit(embed=self.pages[0], view=self)

    def _update_button_states(self) -> None:
        super()._update_button_states()
        
        if not self.is_admin:
            for child in list(self.children):
                if isinstance(child, discord.ui.Button) and child.custom_id in ("add_milestone", "remove_milestone"):
                    self.remove_item(child)
        
        
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
        ref = db.reference(f"/Chat Minigames Rewards/{interaction.guild.id}/milestones")
        milestones = ref.get() or []
        
        pages = get_milestone_embeds(interaction, milestones)
        
        view = MilestonePageView(pages, initial_author=interaction.user, is_admin=interaction.user.guild_permissions.administrator)
        view.message = await interaction.followup.send(embed=pages[0], view=view)
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Milestones(bot))