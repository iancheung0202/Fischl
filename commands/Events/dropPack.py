import discord
import time
import random

from discord.ui import Button, View
from firebase_admin import db

from commands.Events.helperFunctions import addMora

MORA_EMOTE = "<:MORA:1364030973611610205>"

def generate_drops():
    num_drops = random.randint(2, 6)
    drops = []
    for _ in range(num_drops):
        size = random.choices(
            ["Tiny", "Small", "Medium", "Large", "Huge", "Mega"],
            weights=[0.3, 0.25, 0.2, 0.15, 0.08, 0.02],
            k=1
        )[0]
        
        if size == "Tiny":
            amount = random.randint(500, 999)
        elif size == "Small":
            amount = random.randint(1500, 2000)
        elif size == "Medium":
            amount = random.randint(3000, 3500)
        elif size == "Large":
            amount = random.randint(6000, 6700)
        elif size == "Huge":
            amount = random.randint(9800, 10200)
        else:  # Mega
            amount = random.randint(13000, 15000)
        
        drops.append({"type": size, "amount": amount, "revealed": False})
    return drops

class DropPackView(View):
    def __init__(self, pack_id, guild_id, user_id, drops, xp_bonus):
        super().__init__(timeout=180)
        self.pack_id = pack_id
        self.guild_id = guild_id
        self.user_id = user_id
        self.drops = drops
        self.xp_bonus = xp_bonus
        self.current_index = 0
        self.total_mora = 0

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Open Drop", style=discord.ButtonStyle.green, emoji="🎁")
    async def open_drop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This pack isn't yours!", ephemeral=True)
            return
            
        if self.current_index >= len(self.drops):
            button.disabled = True
            await interaction.response.edit_message(view=self)
            return

        drop = self.drops[self.current_index]
        drop["revealed"] = True
        self.total_mora += drop["amount"]
        self.current_index += 1
        
        embed = interaction.message.embeds[0]
        if self.current_index == 1:
            embed.description += f"\n"
        embed.description += f"\n-# **Drop #{self.current_index}:** {drop['type']} - {MORA_EMOTE} `{drop['amount']:,}`"
        
        if self.current_index < len(self.drops):
            embed.set_footer(text=f"{len(self.drops) - self.current_index} drops remaining...")
            await interaction.response.edit_message(embed=embed)
        else:
            text, addedMora = await addMora(self.user_id, self.total_mora, interaction.channel.id, self.guild_id, interaction.client)
            embed.title = "🎉 Mora Drop Pack Summary"
            embed.description += f"\n\n**Total Mora:** {MORA_EMOTE} `{text}`"
            
            if self.xp_bonus:
                embed.description += f"\n✨ **Bonus Reward:** +1000 XP!"
                
            embed.set_footer(text=None)
            button.label = "Complete"
            button.style = discord.ButtonStyle.grey
            button.disabled = True
            self.add_item(DropPackDelete())
            await interaction.response.edit_message(embed=embed, view=self)

            from commands.Events.quests import update_quest
            from commands.Events.trackData import check_tier_rewards
            from commands.Events.event import add_xp
            from commands.Events.helperFunctions import TierRewardsView

            await update_quest(self.user_id, self.guild_id, interaction.channel.id, {"earn_mora": addedMora}, interaction.client)
            
            if self.xp_bonus:
                tier, old_xp, new_xp = await add_xp(self.user_id, self.guild_id, 1000, interaction.client)
                free_embed, elite_embed = await check_tier_rewards(
                    guild_id=self.guild_id,
                    user_id=self.user_id,
                    old_xp=old_xp,
                    new_xp=new_xp,
                    channel=interaction.channel,
                    client=interaction.client
                )
                await interaction.followup.send(view=TierRewardsView(free_embed, elite_embed))
                
            db.reference(f"/Mora Drop Packs/{self.guild_id}/{self.user_id}/{self.pack_id}").delete()
            
class DropPackDelete(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.grey,
            custom_id="persistent_drop_pack_delete",
            emoji="<a:delete:1372423674640207882>",
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) not in interaction.message.content:
            await interaction.response.send_message("❌ This isn't your drop pack!", ephemeral=True)
        else:
            await interaction.message.delete()

async def create_drop_pack(guild_id, user_id, channel, is_elite, is_bonus, tier):
    pack_id = str(int(time.time() * 1000))
    drops = generate_drops()
    xp_bonus = random.random() < 0.2  # 20% chance
    
    ref = db.reference(f"/Mora Drop Packs/{guild_id}/{user_id}/{pack_id}")
    ref.set({
        "drops": drops,
        "xp_bonus": xp_bonus
    })
    
    if is_bonus:
        title = f"{'Elite ' if is_elite else ''}New Bonus Drop Pack"
        description = (
            f"<@{user_id}>, you've earned a bonus drop pack for "
            "accumulating +2500 XP beyond tier 31! \nClick below to reveal your drops now!"
        )
    else:
        title = f"{'Elite Reward: ' if is_elite else ''}New Drop Pack"
        description = f"<@{user_id}>, you've reached tier `{tier}` and unlocked a drop pack! \nClick below to reveal your drops now!"

    embed = discord.Embed(
        title=title,
        description=description,
        color=0xfa0add if is_elite else 0xffd700
    )
    embed.set_footer(text=f"{len(drops)} drops incoming!")
    
    view = DropPackView(pack_id, guild_id, user_id, drops, xp_bonus)
    message = await channel.send(content=f"<@{user_id}>, claim this pack <t:{int(time.time()) + 180}:R>!", embed=embed, view=view)
    view.message = message
    return message
    
async def setup(bot) -> None:
    pass