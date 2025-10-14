import discord
import asyncio
import time

from firebase_admin import db

def get_minigame_list(channel_id):
    ref = db.reference("/Global Events System")
    events = ref.get() or {}
    for key, val in events.items():
        if val["Channel ID"] == channel_id:
            return val["Events"]
    return None

def get_total_mora(data: dict) -> int:
    total = 0
    for guild in data.values():
        for channel in guild.values():
            for amt in channel.values():
                total += amt
    return total

def get_guild_mora(data: dict, guild_id: str) -> int:
    total = 0
    guild = data.get(guild_id, {})
    for channel in guild.values():
        for amt in channel.values():
            total += amt
    return total

async def subtractGuildMora(userID: int, subtractMora: int, guildID: int, channelID: int) -> int | bool:
    user_key = str(userID)
    guild_key = str(guildID)
    channel_key = str(channelID)

    base_ref = db.reference(f"/Mora/{user_key}/{guild_key}")
    channels = base_ref.get() or {}

    entries = [
        amt for chan in channels.values()
        for amt in chan.values()
    ]
    total_available = sum(entries)

    if subtractMora > total_available:
        return False

    timestamp = str(int(time.time()))
    subtract_ref = db.reference(f"/Mora/{user_key}/{guild_key}/{channel_key}/{timestamp}")
    subtract_ref.set(-subtractMora)

    updated = base_ref.get() or {}
    new_total = sum(
        amt for chan in updated.values()
        for amt in chan.values()
    )
    return new_total

async def addMora(userID: int, addedMora: int, channelID: int, guildID: int, client=None):
    baseMora = addedMora 
    if addedMora > 0:
        stats_ref = db.reference(f"/User Events Stats/{guildID}/{userID}")
        stats = stats_ref.get() or {}
        boost = stats.get("mora_boost", 0)
        addedMora = int(addedMora * (1 + boost / 100))
    else:
        boost = 0

    ts = str(int(time.time()))
    path = f"/Mora/{userID}/{guildID}/{channelID}/{ts}"
    db.reference(path).set(addedMora)

    asyncio.create_task(delayed_check_milestones(userID, guildID, channelID, client))

    if baseMora > 0 and boost > 0:
        return f"{baseMora} + {addedMora - baseMora} ({boost}% boost)", addedMora
    return abs(addedMora), addedMora

async def delayed_check_milestones(userID, guildID, channelID, client):
    await asyncio.sleep(1)  # Allow time for Firebase write
    await check_milestones(userID, guildID, channelID, client)
    
async def check_milestones(user_id, guild_id, channel_id, client):
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        channel_id = None
    ref = db.reference(f"/Mora/{user_id}")
    user_data = ref.get() or {}
    total_mora = get_guild_mora(user_data, str(guild_id))

    milestones_ref = db.reference(f"/Milestones/{guild_id}")
    milestones = milestones_ref.get() or {}
    
    inventory_ref = db.reference("/User Events Inventory")
    inventories = inventory_ref.get()
    user_items = []
    if inventories:
        for key, val in inventories.items():
            if val["User ID"] == user_id:
                user_items = [item[0] for item in val.get("Items", []) 
                              if len(item) > 3 and item[3] == guild_id]
                break
    
    for milestone_id, milestone in milestones.items():
        threshold = milestone.get("threshold", 0)
        reward = milestone.get("reward")
        description = milestone.get("description", "Reached milestone")
        
        if reward in user_items or total_mora < threshold:
            continue
        
        item_data = [
            reward, 
            description,
            0,  # cost is 0 because it's a milestone
            guild_id,
            int(time.time())
        ]
        
        found = False
        if inventories:
            for key, val in inventories.items():
                if val["User ID"] == user_id:
                    items = val.get("Items", [])
                    items.append(item_data)
                    inventory_ref.child(key).update({"Items": items})
                    found = True
                    break
        
        if not found:
            data = {"User ID": user_id, "Items": [item_data]}
            inventory_ref.push().set(data)
        
        if isinstance(reward, int) or str(reward).isdigit():
            guild = client.get_guild(guild_id)
            if guild:
                member = await guild.fetch_member(user_id)
                role = guild.get_role(int(reward))
                if member and role:
                    try:
                        await member.add_roles(role)
                    except:
                        pass
        
        channel = client.get_channel(channel_id)
        if channel:
            if isinstance(reward, int) or str(reward).isdigit():
                reward_display = f"<@&{reward}>"
            else:
                reward_display = reward
            
            from commands.Events.event import userAndTitle

            await channel.send(
                embed=discord.Embed(
                    title="🏆 Milestone Achieved!",
                    description=(
                        f"Congratulations, {userAndTitle(user_id, guild_id)}! \n"
                        f"You've reached {MORA_EMOTE} `{threshold}` and earned **{reward_display}**\n"
                    ),
                    color=discord.Color.gold()
                )
            )

class PersistentXPQuestInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="What is this?",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_xp_quest_info_view",
        emoji="<:PinkConfused:1204614149628498010>",
    )
    async def persistentXPQuestInfoView(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="What Are XP & Quests? <:AlbedoQuestion:1191574408544923799>",
            description="-# Read the full patch notes [here](https://fischlbot.web.app/track/update/).",
            color=discord.Color.random()
        )
        embed.add_field(
            name="<:NingguangStonks:1265470501707321344> Quests ➜ XP",
            value="-# Complete daily, weekly, and monthly quests to **earn XP** just by playing, winning, or gifting!",
            inline=True
        )
        embed.add_field(
            name="<:CharlotteHeart:1191594476263702528> XP ➜ Rewards",
            value="-# Earning XP moves you up the Progression Track to **unlock Mora boosts, chest upgrades, animated backgrounds**, and more!",
            inline=True
        )
        embed.add_field(
            name="<:MelonBread_KeqingNote:1342924552392671254> Track in One Place",
            value="-# Use </mora:1339721187953082543> to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
            inline=True
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_info_delete",
        emoji="<a:delete:1372423674640207882>",
    )
    async def persistent_info_delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content and str(interaction.user.id) not in interaction.message.embeds[0].description:
            await interaction.response.send_message("❌ This isn't your notification!", ephemeral=True)
        else:
            await interaction.message.delete()
        
class TierRewardsView(discord.ui.View):
    def __init__(self, free_embed=discord.Embed(title="This button has timed out.", color=discord.Color.red()), elite_embed=discord.Embed(color=0xFF0000)):
        super().__init__(timeout=None)
        self.free_embed = free_embed
        self.elite_embed = elite_embed

    @discord.ui.button(
        label="View Earned Tiers",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_tier_rewards_view",
    )
    async def show_tier_rewards(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.elite_embed.title is not None:
            await interaction.response.send_message(embeds=[self.free_embed, self.elite_embed], ephemeral=True)
        elif self.free_embed.title is not None:
            await interaction.response.send_message(embeds=[self.free_embed], ephemeral=True)
        else:
            await interaction.response.send_message("You did not earn any tiers from this XP gain.", ephemeral=True)
            
    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_xp_quest_info_view_new",
        emoji="<:PinkConfused:1204614149628498010>",
    )
    async def persistentXPQuestInfoViewNew(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="What Are XP & Quests? <:AlbedoQuestion:1191574408544923799>",
            description="-# Read the full patch notes [here](https://fischlbot.web.app/track/update/).",
            color=discord.Color.random()
        )
        embed.add_field(
            name="<:NingguangStonks:1265470501707321344> Quests ➜ XP",
            value="-# Complete daily, weekly, and monthly quests to **earn XP** just by playing, winning, or gifting!",
            inline=True
        )
        embed.add_field(
            name="<:CharlotteHeart:1191594476263702528> XP ➜ Rewards",
            value="-# Earning XP moves you up the Progression Track to **unlock Mora boosts, chest upgrades, animated backgrounds**, and more!",
            inline=True
        )
        embed.add_field(
            name="<:MelonBread_KeqingNote:1342924552392671254> Track in One Place",
            value="-# Use </mora:1339721187953082543> to view **quests, XP, and rewards**. Each season's track lasts **3 months**!",
            inline=True
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_info_delete_new",
        emoji="<a:delete:1372423674640207882>",
    )
    async def persistent_info_delete_new(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content and str(interaction.user.id) not in interaction.message.embeds[0].description:
            await interaction.response.send_message("❌ This isn't your notification!", ephemeral=True)
        else:
            await interaction.message.delete()
            
async def setup(bot) -> None:
    pass