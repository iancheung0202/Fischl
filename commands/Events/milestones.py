import discord
import time

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View, Select

from commands.Events.helperFunctions import get_guild_mora

MORA_EMOTE = "<:MORA:1364030973611610205>"

def get_milestone_embeds(interaction: discord.Interaction, milestones: dict) -> list:
    if not milestones:
        return [discord.Embed(description="This server has no milestones set up yet.", color=discord.Color.default())]
    
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
    sorted_milestones = sorted(
        milestones.items(),
        key=lambda x: x[1].get("threshold", 0)
    )
    
    for milestone_id, milestone in sorted_milestones:
        threshold = milestone.get("threshold", 0)
        reward = milestone.get("reward", "?")
        description = milestone.get("description", "No description")
        
        if str(reward).isdigit():
            role = interaction.guild.get_role(int(reward))
            display_name = f"{role.name}" if role else "Unknown Role"
            page.add_field(
                name=f"{MORA_EMOTE} {threshold} • {display_name}",
                value=f"> **Role:** {role.mention if role else 'Unknown'}\n> **Description:** {description}",
                inline=False
            )
        else:
            display_name = f"{reward}"
            page.add_field(
                name=f"{MORA_EMOTE} {threshold} • {display_name}",
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
        
        ref = db.reference(f"/Milestones/{interaction.guild.id}")
        milestone_data = {
            "threshold": threshold,
            "reward": reward,
            "description": description
        }
        new_milestone_ref = ref.push()
        new_milestone_ref.set(milestone_data)
        
        count = 0
        mora_ref = db.reference("/Mora")
        all_users = mora_ref.get() or {}

        for user_id, user_data in all_users.items():
            guild_mora = get_guild_mora(user_data, str(interaction.guild.id))
            if guild_mora >= threshold:
                inventory_ref = db.reference("/User Events Inventory")
                inventories = inventory_ref.get() or {}
                has_reward = False
                for inv_key, inv_data in inventories.items():
                    if inv_data["User ID"] == user_id:
                        for item in inv_data.get("Items", []):
                            if item[0] == reward and item[3] == interaction.guild.id:
                                has_reward = True
                                break
                        if has_reward:
                            break
                
                if not has_reward:
                    count += 1
                    item_data = [
                        reward, 
                        description,
                        0,  # cost is 0 because it's a milestone
                        interaction.guild.id,
                        int(time.time())
                    ]
                    
                    found = False
                    for inv_key, inv_data in inventories.items():
                        if inv_data["User ID"] == user_id:
                            items = inv_data.get("Items", [])
                            items.append(item_data)
                            inventory_ref.child(inv_key).update({"Items": items})
                            found = True
                            break
                    if not found:
                        data = {"User ID": user_id, "Items": [item_data]}
                        inventory_ref.push().set(data)
                    
                    if reward.isdigit():
                        member = await interaction.guild.fetch_member(user_id)
                        role = interaction.guild.get_role(int(reward))
                        if member and role:
                            try:
                                await member.add_roles(role)
                            except:
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
        ref = db.reference(f"/Milestones/{interaction.guild.id}")
        milestones = ref.get() or {}
        removed = False
        
        for milestone_id, milestone in milestones.items():
            if milestone.get("reward") == name:
                ref.child(milestone_id).delete()
                removed = True
                
        if removed:
            milestones = ref.get() or {}
            self.pages = get_milestone_embeds(interaction, milestones)
            await interaction.response.send_message("✅ Milestone removed successfully.", ephemeral=True)
        else:
            await interaction.response.send_message("Milestone not found!", ephemeral=True)


class MilestonePageView(discord.ui.View):
    def __init__(self, pages, initial_author=None):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self.initial_author = initial_author

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

    @discord.ui.button(label="<<", style=discord.ButtonStyle.blurple, custom_id="super_prev_ms")
    async def super_prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page+1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="<", style=discord.ButtonStyle.blurple, custom_id="prev_ms")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page+1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label=">", style=discord.ButtonStyle.blurple, custom_id="next_ms")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.pages) - 1:
            self.page += 1
        else:
            self.page = 0
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page+1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.blurple, custom_id="super_next_ms")
    async def super_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = len(self.pages) - 1
        embed = self.pages[self.page]
        embed.set_footer(text=f"Page {self.page+1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed)
        
        
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
        ref = db.reference(f"/Milestones/{interaction.guild.id}")
        milestones = ref.get() or {}
        
        pages = get_milestone_embeds(interaction, milestones)
        
        view = MilestonePageView(pages, interaction.user)
        view.message = await interaction.followup.send(embed=pages[0], view=view)
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Milestones(bot))