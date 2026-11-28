import asyncio
import random
import time

import discord

from commands.Events.config import BOSSES, MORA_EMOTE
from commands.Events.games.common import count, earn
from commands.Events.helperFunctions import get_channel_mora_multiplier

SECONDS = 60
BAR = 15
BOARD = "🏆 Top Damage Dealers"


class BossBattleView(discord.ui.View):
    def __init__(self, hp, boss_name, client, channel, start_time):
        super().__init__(timeout=None)
        self.max_hp = self.current_hp = hp
        self.boss_name = boss_name
        self.client = client
        self.channel = channel
        self.start_time = start_time
        self.participants = {}
        self.total_damage = 0
        self.last_hitter = None
        self.active = True
        self.message = None

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        label="Attack!",
        emoji="⚔️",
        custom_id="boss_attack_btn",
    )
    async def attack(self, interaction: discord.Interaction, button):
        if not self.active or self.current_hp <= 0:
            return await interaction.response.send_message(
                "The boss is already defeated!", ephemeral=True
            )
        damage = random.randint(50, 150)
        if random.random() < 0.15:
            damage *= 2
        damage = min(damage, self.current_hp)
        uid = interaction.user.id
        self.current_hp -= damage
        self.participants[uid] = self.participants.get(uid, 0) + damage
        self.total_damage += damage
        self.last_hitter = uid
        if self.current_hp <= 0:
            self.active = False
            self.stop()
        await self.update_ui(interaction)

    def ranked(self) -> list:
        """Gives (member, damage) pairs, most damage first."""
        return sorted(self.participants.items(), key=lambda pair: pair[1], reverse=True)

    async def update_loop(self):
        while self.active and self.current_hp > 0:
            if time.time() - self.start_time >= SECONDS:
                self.active = False
                break
            await asyncio.sleep(1.0)
        if self.current_hp <= 0:
            await self.end_game()
        else:
            await self.timeout_game()

    async def update_ui(self, interaction):
        """Redraws the health bar, the numbers and the top five on the battle message."""
        try:
            embed = self.message.embeds[0]
            left = max(0, self.current_hp / self.max_hp)
            filled = int(left * BAR)
            status = "⚔️ **BATTLE IN PROGRESS** ⚔️"
            if self.current_hp <= 0:
                status = "💀 **BOSS DEFEATED** 💀"
            elif left < 0.3:
                status = "🔥 **BOSS IS ENRAGED!** 🔥"
            embed.description = (
                f"{status} (Ending <t:{self.start_time + SECONDS}:R>)\n\n"
                f"**HP:** `{self.current_hp}/{self.max_hp}`\n"
                f"`[{'█' * filled}{'░' * (BAR - filled)}]` **{int(left*100)}%**\n\n"
                f"**Battle Stats:**\n"
                f"-# Total Damage: `{self.total_damage}`\n"
                f"-# Attackers: `{len(self.participants)}`"
            )
            board = "".join(
                f"`#{place}` <@{uid}>: **{damage}** damage\n"
                for place, (uid, damage) in enumerate(self.ranked()[:5], 1)
            )
            embed.set_field_at(0, name=BOARD, value=board, inline=False)
            if self.current_hp <= 0:
                embed.color = discord.Color.green()
                self.attack.disabled = True
                self.attack.style = discord.ButtonStyle.success
            elif time.time() - self.start_time >= SECONDS or not self.active:
                self.attack.disabled = True
                self.attack.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as error:
            print(f"Error updating boss UI: {error}")

    async def end_game(self):
        """Pays every attacker, with extra for the most damage and the last hit, and posts the list."""
        lines = []
        multiplier = await get_channel_mora_multiplier(
            self.client.pool, self.channel.id
        )
        for place, (uid, damage) in enumerate(self.ranked(), 1):
            amount = int((3000 + damage) * multiplier)
            if place == 1:
                amount += int(2000 * multiplier)
            if uid == self.last_hitter:
                amount += int(1500 * multiplier)
            text, earned = await earn(self.client, self.channel, uid, amount)
            await count(self.client, self.channel, uid, earned, self.start_time)
            line = f"**#{place}** <@{uid}>: {MORA_EMOTE} `{text}` ({damage} damage)"
            if uid == self.last_hitter:
                line += " 🗡️ **Last Hit!**"
            if place == 1:
                line += " 🥇 **Best Damage Dealer!**"
            lines.append(line)
        await self.message.reply(
            embed=discord.Embed(
                title=f"Boss Defeated! - {self.boss_name}",
                description="Rewards have been distributed:\n\n" + "\n".join(lines),
                color=discord.Color.gold(),
            )
        )

    async def timeout_game(self):
        await self.message.reply(
            embed=discord.Embed(
                title="Boss Escaped!",
                description=f"**{self.boss_name}** got away! The raid failed.",
                color=discord.Color.red(),
            )
        )
        self.stop()


async def defeatTheBoss(channel, client):
    boss = random.choice(BOSSES)
    hp = random.randint(3000, 8000)
    start_time = int(time.time())
    view = BossBattleView(hp, boss, client, channel, start_time)
    embed = discord.Embed(
        title=f"Boss Battle Blitz - {boss}",
        description=(
            f"A wild **{boss}** has appeared!\n"
            f"**HP:** `{hp}/{hp}`\n\n"
            f"Everyone click **Attack** to deal damage <t:{start_time + SECONDS}:R>"
        ),
        color=discord.Color.dark_red(),
    )
    embed.add_field(name=BOARD, value="No attacks yet...", inline=False)
    view.message = await channel.send(embed=embed, view=view)
    asyncio.create_task(view.update_loop())


async def setup(bot) -> None:
    pass
