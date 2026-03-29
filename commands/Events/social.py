import discord
import random
import os

from discord.ext import commands
from discord import app_commands
from firebase_admin import db
from discord.ui import Button, View
from commands.Events.quests import update_quest

class Hug(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hug_gifs_path = "assets/hugs"
        
    def _get_random_hug_gif(self):
        gifs = [f for f in os.listdir(self.hug_gifs_path) 
               if f.endswith(('.gif', '.png', '.jpg', '.jpeg'))]
        return random.choice(gifs) if gifs else None

    async def _update_hug_count(self, hugger_id: int, target_id: int) -> int:
        async with self.bot.pool.acquire() as conn:
            return await conn.fetchval("INSERT INTO hugs (target_id, hugger_id, count) VALUES ($1, $2, 1) ON CONFLICT (target_id, hugger_id) DO UPDATE SET count = hugs.count + 1 RETURNING count", target_id, hugger_id)

    class HugBackView(View):
        def __init__(self, cog, original_hugger: discord.Member, target: discord.Member):
            super().__init__(timeout=120)
            self.cog = cog
            self.original_hugger = original_hugger
            self.target = target
            
        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
            
        @discord.ui.button(label="Hug Back", style=discord.ButtonStyle.primary, emoji="❤️")
        async def hug_back(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.target.id:
                await interaction.response.send_message("Only the hugged user can hug back!", ephemeral=True)
                return
                
            new_count = await self.cog._update_hug_count(
                hugger_id=self.target.id,
                target_id=self.original_hugger.id
            )
            
            gif_name = self.cog._get_random_hug_gif()
            if not gif_name:
                await interaction.response.send_message("Hug GIFs not found!", ephemeral=True)
                return
                
            extension = os.path.splitext(gif_name)[1]
            file = discord.File(f"{self.cog.hug_gifs_path}/{gif_name}", filename=f"hug{extension}")
            
            if new_count == 1:
                count_text = "That's the first time!"
            else:
                count_text = f"That's `{new_count}` times now!"

            embed = discord.Embed(
                description=f":people_hugging: {self.target.mention} hugged {self.original_hugger.mention}! {count_text}",
                color=0xd596c4
            )
            embed.set_image(url=f"attachment://hug{extension}")
            
            for item in self.children:
                item.disabled = True
            
            await interaction.channel.send(content=self.original_hugger.mention, embed=embed, file=file)
            await interaction.response.send_message(content="Hug sent back!", ephemeral=True)
            await self.message.edit(view=self)
            await update_quest(self.target.id, interaction.guild.id, interaction.channel.id, {"hug_user": 1}, self.cog.bot)

    @app_commands.command(
        name="hug",
        description="Give someone a warm hug!"
    )
    @app_commands.describe(
        user="The user you want to hug"
    )
    async def hug(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member
    ) -> None:
        is_self_hug = user.id == interaction.user.id
        
        if is_self_hug:
            await interaction.response.send_message("I appreciate your self love, but you can't hug yourself!", ephemeral=True)
            return
        
        new_count = await self._update_hug_count(
            hugger_id=interaction.user.id,
            target_id=user.id
        )
        
        gif_name = self._get_random_hug_gif()
        if not gif_name:
            await interaction.response.send_message(f"Hug GIF `{gif_name}` not found!", ephemeral=True)
            return
            
        extension = os.path.splitext(gif_name)[1]
        file = discord.File(f"{self.hug_gifs_path}/{gif_name}", filename=f"hug{extension}")
        
        if new_count == 1:
            count_text = "That's the first time!"
        else:
            count_text = f"That's `{new_count}` times now!"
            
        embed = discord.Embed(
            description=f":people_hugging: {interaction.user.mention} hugged {user.mention}! {count_text}",
            color=0xd596c4
        )
        embed.set_image(url=f"attachment://hug{extension}")
        
        view = self.HugBackView(self, interaction.user, user)
        await interaction.channel.send(content=user.mention, embed=embed, file=file, view=view)
        await interaction.response.send_message(content="Hug sent!", ephemeral=True)
        view.message = await interaction.original_response()
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"hug_user": 1}, self.bot)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Hug(bot))