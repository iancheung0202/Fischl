"""`/hug`: hugs a member with a random GIF and counts the hugs between the two."""

import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

from commands.Events.quests import update_quest

GIFS = "assets/hugs"
COUNT = "INSERT INTO hugs (target_id, hugger_id, count) VALUES ($1, $2, 1) ON CONFLICT (target_id, hugger_id) DO UPDATE SET count = hugs.count + 1 RETURNING count"


async def ensure_minigame_hugs_table(pool):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hugs (
                target_id   BIGINT NOT NULL,
                hugger_id   BIGINT NOT NULL,
                count       INTEGER DEFAULT 1,

                PRIMARY KEY (target_id, hugger_id)
            )
        """
        )


def random_gif():
    """Gives the file name of a random hug picture, or None when there are none."""
    gifs = [
        name
        for name in os.listdir(GIFS)
        if name.endswith((".gif", ".png", ".jpg", ".jpeg"))
    ]
    return random.choice(gifs) if gifs else None


async def count_hug(pool, hugger, target):
    """Adds one hug from the hugger to the target and gives the new count."""
    async with pool.acquire() as conn:
        return await conn.fetchval(COUNT, target.id, hugger.id)


def announcement(hugger, target, count, gif):
    """Gives the embed and picture that say who hugged whom, and how often."""
    extension = os.path.splitext(gif)[1]
    times = "That's the first time!" if count == 1 else f"That's `{count}` times now!"
    embed = discord.Embed(
        description=f":people_hugging: {hugger.mention} hugged {target.mention}! {times}",
        color=0xD596C4,
    )
    embed.set_image(url=f"attachment://hug{extension}")
    return {
        "content": target.mention,
        "embed": embed,
        "file": discord.File(f"{GIFS}/{gif}", filename=f"hug{extension}"),
    }


async def count_quest(member, interaction):
    """Counts the hug toward the member's quests."""
    await update_quest(
        member.id,
        interaction.guild.id,
        interaction.channel.id,
        {"hug_user": 1},
        interaction.client,
    )


class HugBackView(View):
    """The Hug Back button under a hug, for the member who was hugged."""

    def __init__(self, original_hugger: discord.Member, target: discord.Member):
        super().__init__(timeout=120)
        self.original_hugger = original_hugger
        self.target = target

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Hug Back", style=discord.ButtonStyle.primary, emoji="❤️")
    async def hug_back(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                "Only the hugged user can hug back!", ephemeral=True
            )
            return

        count = await count_hug(
            interaction.client.pool, self.target, self.original_hugger
        )
        gif = random_gif()
        if not gif:
            await interaction.response.send_message(
                "Hug GIFs not found!", ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True
        await interaction.channel.send(
            **announcement(self.target, self.original_hugger, count, gif)
        )
        await interaction.response.send_message(
            content="Hug sent back!", ephemeral=True
        )
        await self.message.edit(view=self)
        await count_quest(self.target, interaction)


class Hug(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="hug", description="Give someone a warm hug!")
    @app_commands.describe(user="The user you want to hug")
    async def hug(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "I appreciate your self love, but you can't hug yourself!",
                ephemeral=True,
            )
            return

        count = await count_hug(interaction.client.pool, interaction.user, user)
        gif = random_gif()
        if not gif:
            await interaction.response.send_message(
                f"Hug GIF `{gif}` not found!", ephemeral=True
            )
            return

        view = HugBackView(interaction.user, user)
        await interaction.channel.send(
            **announcement(interaction.user, user, count, gif), view=view
        )
        await interaction.response.send_message(content="Hug sent!", ephemeral=True)
        view.message = await interaction.original_response()
        await count_quest(interaction.user, interaction)


async def setup(bot: commands.Bot) -> None:
    await ensure_minigame_hugs_table(bot.pool)
    await bot.add_cog(Hug(bot))
