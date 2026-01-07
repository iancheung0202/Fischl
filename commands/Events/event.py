import discord
import datetime
import asyncio
import time
import random
import os
import requests
import re
import json
import importlib
import pandas as pd

from firebase_admin import db
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
from essential_generators import DocumentGenerator
from difflib import SequenceMatcher
from bs4 import BeautifulSoup

from commands.Events.trackData import get_current_track, check_tier_rewards
from commands.Events.helperFunctions import addMora, get_guild_mora, get_minigame_list
from commands.Events.quests import update_quest

MORA_EMOTE = "<:MORA:1364030973611610205>"
MORA_CHEST_DESCRIPTION = f"""## How the Daily Mora Chest Works 🎁
<:dot:1357188726047899760> Earn a chest per day after sending **4 to 6 effortful messages** in minigame channels.
<:dot:1357188726047899760> Messages must be spaced out and not repetitive/spammy.
<:dot:1357188726047899760> A chest starts as **Common**, containing {MORA_EMOTE} `2500`.
<:dot:1357188726047899760> You get a minimum of **4 chances** to upgrade your chest.
<:dot:1357188726047899760> You must claim your chest within **5 minutes** or it will be wasted.
<:dot:1357188726047899760> After claiming, wait until the next **UTC +0 midnight** to earn a new chest.
### Rewards (Base Mora) 🏆
<:dot:1357188726047899760> `Common:       2,500 Mora`
<:dot:1357188726047899760> `Exquisite:    7,500 Mora`
<:dot:1357188726047899760> `Precious:    15,000 Mora`
<:dot:1357188726047899760> `Luxurious:   30,000 Mora`
### Upgrade Chances :arrow_up:  
<:dot:1357188726047899760> `Common → Exquisite:     30% chance`
<:dot:1357188726047899760> `Exquisite → Precious:   15% chance`
<:dot:1357188726047899760> `Precious → Luxurious:   20% chance`
### Streak Bonus <a:streak:1371651844652273694>
<:dot:1357188726047899760> You gain a **daily streak** if you claim a chest every day.
<:dot:1357188726047899760> Each day in your streak adds `+100` {MORA_EMOTE} (max 10000) to the reward.
<:dot:1357188726047899760> Miss a day? Your streak resets to 1."""

def get_next_reset_unix():
    now = datetime.datetime.now(datetime.timezone.utc)
    next_reset = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(next_reset.timestamp())

active_channels = {}
active_auctions = {}
active_pfp_games = {}
active_rps_games = {}
active_who_said_it_games = {}
active_know_members_games = {}
active_memory_games = {}
active_ttol_games = {}
active_split_or_steal_games = {}

commands_module = importlib.import_module("commands")
from commands.Events.enabledChannels import enabledChannels
last_modified = os.path.getmtime("./commands/Events/enabledChannels.py")

def check_and_reload():
    global last_modified, enabledChannels
    new_modified = os.path.getmtime("./commands/Events/enabledChannels.py")
    if new_modified > last_modified:
        with open("./commands/Events/enabledChannels.py", "r") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("enabledChannels ="):
                new_enabled_channels = eval(
                    line.split("=")[1].strip()
                )  # Extract the new list
        if new_enabled_channels != enabledChannels:  # Only update if there's a change
            enabledChannels = new_enabled_channels
            last_modified = new_modified
            print("Random Events ./commands/Events/enabledChannels.py reloaded!")

async def handle_message_deletion(message):
    await asyncio.sleep(3)
    try:
        await message.delete()
    except discord.NotFound:
        pass  # already deleted/was removed
    
async def add_xp(user_id, guild_id, xp_amount, client):
    ref = db.reference(f"/Progression/{guild_id}/{user_id}")
    data = ref.get() or {"xp": 0, "prestige": 0, "bonus_tier": 0}
    
    old_xp = data.get("xp", 0)
    data["xp"] = old_xp + xp_amount
    current_xp = data["xp"]
    
    current_tier = 0
    TRACK_DATA = get_current_track()
    for tier in TRACK_DATA:
        if current_xp >= tier["cumulative_xp"]:
            current_tier = tier["tier"]
        else:
            break
    
    if current_tier == 31:
        bonus_xp = current_xp - TRACK_DATA[-1]["cumulative_xp"]
        bonus_tiers = bonus_xp // 1500
        
        if bonus_tiers > data.get("bonus_tier", 0):
            data["bonus_tier"] = bonus_tiers
    
    ref.set(data)
    return (current_tier, old_xp, current_xp)

            
def userAndTitle(userID, guildID):
    ref = db.reference("/User Events Inventory")
    inventories = ref.get()
    if inventories:
        for key, val in inventories.items():
            if val["User ID"] == userID:
                print(userID)
                try:
                    inv = val["Items"].copy()
                except Exception as e:
                    print(e)
                    break
                for i, item in enumerate(inv):
                    if item[3] == guildID and len(item) > 5 and item[5] == "Pinned":
                        role_mention = (
                            f"<@&{item[0]}>"
                            if isinstance(item[0], int) or item[0].isdigit()
                            else item[0]
                        )
                        return f"<@{userID}> **({role_mention})**"
    return f"<@{userID}>"


### --- DEFEAT THE BOSS --- ###

class BossAttackButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            style=discord.ButtonStyle.red,
            label="Attack!",
            emoji="⚔️",
            disabled=disabled,
            custom_id="boss_attack_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not view.active or view.current_hp <= 0:
            await interaction.response.send_message("The boss is already defeated!", ephemeral=True)
            return

        damage = random.randint(50, 150)
        is_crit = False
        if random.random() < 0.15: # 15% Crit Chance
            damage *= 2
            is_crit = True

        async with view.lock:
            if view.current_hp > 0:
                actual_damage = min(damage, view.current_hp)
                view.current_hp -= actual_damage
                view.participants[interaction.user.id] = view.participants.get(interaction.user.id, 0) + actual_damage
                view.total_damage += actual_damage
                view.last_hitter = interaction.user.id
                
                if view.current_hp <= 0:
                    view.active = False
                    view.stop()
        
        await view.update_ui(interaction)

class BossBattleView(discord.ui.View):
    def __init__(self, hp, boss_name, client, channel, start_time):
        super().__init__(timeout=None)
        self.max_hp = hp
        self.current_hp = hp
        self.boss_name = boss_name
        self.client = client
        self.channel = channel
        self.start_time = start_time
        self.participants = {}
        self.total_damage = 0
        self.last_hitter = None
        self.active = True
        self.dirty = False
        self.message = None
        self.lock = asyncio.Lock()
        self.add_item(BossAttackButton())

    async def update_loop(self):
        while self.active and self.current_hp > 0:
            if (time.time() - self.start_time) >= 60:
                self.active = False
                break
            await asyncio.sleep(1.0)
        
        if self.current_hp <= 0:
            await self.end_game()
        else:
            await self.timeout_game()

    async def update_ui(self, interaction=None):
        if not self.message: return
        
        try:
            embed = self.message.embeds[0]
            percent = max(0, self.current_hp / self.max_hp)
            
            # HP Bar
            bar_len = 15
            filled = int(percent * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            status = "🔥 **BOSS IS ENRAGED!** 🔥" if percent < 0.3 else "⚔️ **BATTLE IN PROGRESS** ⚔️"
            if self.current_hp <= 0: status = "💀 **BOSS DEFEATED** 💀"
            
            embed.description = (
                f"{status} (Ending <t:{self.start_time + 60}:R>)\n\n"
                f"**HP:** `{self.current_hp}/{self.max_hp}`\n"
                f"`[{bar}]` **{int(percent*100)}%**\n\n"
                f"**Battle Stats:**\n"
                f"-# Total Damage: `{self.total_damage}`\n"
                f"-# Attackers: `{len(self.participants)}`"
            )

            # Leaderboard
            sorted_dmg = sorted(self.participants.items(), key=lambda x: x[1], reverse=True)[:5]
            lb_text = ""
            for i, (uid, dmg) in enumerate(sorted_dmg, 1):
                lb_text += f"`#{i}` <@{uid}>: **{dmg}** damage\n"
            
            if not lb_text: lb_text = "Waiting for attackers..."
            
            if len(embed.fields) > 0:
                embed.set_field_at(0, name="🏆 Top Damage Dealers", value=lb_text, inline=False)
            else:
                embed.add_field(name="🏆 Top Damage Dealers", value=lb_text, inline=False)
            
            if self.current_hp <= 0:
                embed.color = discord.Color.green()
                for item in self.children:
                    item.disabled = True
                    item.style = discord.ButtonStyle.success
            elif (time.time() - self.start_time) >= 60 or not self.active:
                 for item in self.children:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
            
            if interaction:
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating boss UI: {e}")

    async def end_game(self):
        # Distribute rewards
        summary = []
        
        # Sort by damage
        sorted_users = sorted(self.participants.items(), key=lambda x: x[1], reverse=True)
        
        for rank, (uid, dmg) in enumerate(sorted_users, 1):
            amount = 3000 # Base participation
            
            # Damage Bonus (1 mora per 1 dmg)
            amount += dmg 
            
            # First Place Bonus
            if rank == 1: amount += 2000
            
            # Last Hit Bonus
            if uid == self.last_hitter: amount += 1500
            
            text, addedMora = await addMora(uid, amount, self.channel.id, self.channel.guild.id, self.client)
            
            # Quest Update
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            await update_quest(uid, self.channel.guild.id, self.channel.id, quest_data, self.client)
            
            entry = f"**#{rank}** <@{uid}>: {MORA_EMOTE} `{text}` ({dmg} damage)"
            if uid == self.last_hitter: entry += " 🗡️ **Last Hit!**"
            if rank == 1: entry += " 🥇 **Best Damage Dealer!**"
            summary.append(entry)
            
        result_embed = discord.Embed(
            title=f"Boss Defeated! - {self.boss_name}",
            description="Rewards have been distributed:\n\n" + "\n".join(summary),
            color=discord.Color.gold()
        )
        await self.message.reply(embed=result_embed)

    async def timeout_game(self):
        embed = discord.Embed(
            title="Boss Escaped!",
            description=f"**{self.boss_name}** got away! The raid failed.",
            color=discord.Color.red()
        )
        await self.message.reply(embed=embed)
        self.stop()

async def defeatTheBoss(channel, client):
    bosses = [
        "Stormterror Dvalin",
        "Andrius",
        "Childe",
        "Azhdaha",
        "La Signora",
        "Magatsu Mitake Narukami no Mikoto",
        "Everlasting Lord of Arcane Wisdom",
        "Guardian of Apep's Oasis",
        "All-Devouring Narwhal",
        "The Knave",
        "Lord of Eroded Primal Fire",
        "Geo Hypostasis",
        "Cryo Hypostasis",
        "Pyro Hypostasis",
        "Electro Hypostasis",
        "Anemo Hypostasis",
        "Hydro Hypostasis",
        "Cryo Regisvine",
        "Pyro Regisvine",
        "Oceanid",
        "Primo Geovishap",
        "Perpetual Mechanical Array",
        "Maguu Kenki",
        "Ruin Serpent",
        "Thunder Manifestation",
        "Golden Wolflord",
        "Bathysmal Vishap Herd",
        "Algorithm of Semi-Intransient Matrix of Overseer Network",
        "Aeonblight Drake",
        "Jadeplume Terrorshroom",
        "Electro Regisvine",
        "Pyro Scorpion",
        "Iniquitous Baptist",
        "Emperor of Fire and Iron",
        "Emperor of Wind and Frost",
        "Emperor of Pure Water",
        "Emperor of Lightning and Thunder",
        "Emperor of Earth and Stone",
        "Emperor of Ice and Snow",
        "Emperor of Flames and Ashes",
        "Emperor of Storms and Tempests",
        "Emperor of Shadows and Darkness",
        "Emperor of Light and Radiance",
        "Doomsday Beast",
        "Cocolia, Mother of Deception",
        "Phantylia the Undying",
        "Starcrusher Swarm King - Skaracabaz (Synthetic)",
        "Harmonious Choir - The Great Septimus",
        "Shadow of Feixiao and Ecliptic Inner Beast",
        "Abundant Ebon Deer",
        "Annihilator of Desolation Mistral",
        "Argenti (Boss)",
        "Blaznana Monkey Trick",
        "Borisin Warhead: Hoolay",
        "Savage God, Mad King, Incarnation of Strife",
        "The Giver, Master of Legions, Lance of Fury",
        "The Past, Present, and Eternal Show",
    ]
    boss = random.choice(bosses)
    hp = random.randint(3000, 8000)
    start_time = int(time.time())
    
    view = BossBattleView(hp, boss, client, channel, start_time)
    
    embed = discord.Embed(
        title=f"Boss Battle Blitz - {boss}",
        description=(
            f"A wild **{boss}** has appeared!\n"
            f"**HP:** `{hp}/{hp}`\n\n"
            f"Everyone click **Attack** to deal damage <t:{int(start_time + 60)}:R>"
        ),
        color=discord.Color.dark_red(),
    )
    embed.add_field(name="🏆 Top Damage Dealers", value="No attacks yet...", inline=False)
    
    msg = await channel.send(embed=embed, view=view)
    view.message = msg
    asyncio.create_task(view.update_loop())

### --- PICK UP THE WATERMELON --- ###

class PickUpButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            style=discord.ButtonStyle.grey,
            emoji="🍉", 
            disabled=disabled
        )
        
    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        
        reward = int(interaction.message.embeds[0].description.split("`")[3])
        text, addedMora = await addMora(
            interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client
        )
        await interaction.response.edit_message(
            content="",
            embed=discord.Embed(
                title=f"Snatch the watermelon - :watermelon:",
                description=f"{userAndTitle(interaction.user.id, interaction.guild.id)} picked up the `🍉` watermelon and earned {MORA_EMOTE} `{text}`.",
                color=discord.Color.gold(),
            ),
            view=PickUpView(disabled=True, timeout=None)
        )
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)

class PickUpView(discord.ui.View):
    def __init__(self, disabled=False, timeout=300):
        super().__init__(timeout=timeout)
        self.add_item(PickUpButton(disabled=disabled))

    async def on_timeout(self):
        if not any(item.disabled for item in self.children):
            for item in self.children:
                item.disabled = True
            expired_embed = discord.Embed(
                title="Snatch the watermelon - :watermelon:",
                description="⏳ This watermelon expired as no one picked it up in time!",
                color=discord.Color.light_grey()
            )
            try:
                await self.message.edit(embed=expired_embed, view=self)
            except discord.NotFound:
                pass

async def pickUpTheWatermelon(channel, client):
    reward = random.randint(3000, 5000)
    view = PickUpView()
    msg = await channel.send(
        embed=discord.Embed(
            title=f"Snatch the watermelon - :watermelon:",
            description=f"First to react to the `🍉` emoji earns {MORA_EMOTE} `{reward}`.",
            color=discord.Color.fuchsia(),
        ),
        view=view
    )
    view.message = msg


### --- PICK UP THE ICECREAM --- ###

class PickUpIceCreamButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            style=discord.ButtonStyle.grey,
            emoji="🍦",
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        
        num = int(interaction.message.embeds[0].description.split("`")[1])
        reward = random.randint(3000, num)
        
        if random.choice(["pos", "neg"]) == "neg":
            reason = random.choice([
                "having tooth decay",
                "having a brain freeze",
                "catching a cold",
                "melt"
            ])
            
            text, addedMora = await addMora(interaction.user.id, -reward, interaction.channel.id, interaction.guild.id, interaction.client)
            if reason == "melt":
                embed = discord.Embed(
                    title=f"A wild 🍦 has appeared.",
                    description=f"Unfortunately, {interaction.user.mention} did not eat the `🍦` in time. The ice cream melted and {userAndTitle(interaction.user.id, interaction.guild.id)} lost {MORA_EMOTE} `{text}`.",
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title=f"A wild 🍦 has appeared.",
                    description=f"Unfortunately, {userAndTitle(interaction.user.id, interaction.guild.id)} ate the `🍦` and lost {MORA_EMOTE} `{text}` for {reason}.",
                    color=discord.Color.red(),
                )
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "earn_mora": addedMora}, interaction.client)
        else:
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            embed = discord.Embed(
                title=f"A wild 🍦 has appeared.",
                description=f"{userAndTitle(interaction.user.id, interaction.guild.id)} enjoyed the `🍦` while earning {MORA_EMOTE} `{text}`.",
                color=discord.Color.green(),
            )
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)

        await interaction.response.edit_message(
            content="",
            embed=embed,
            view=PickUpIceCreamView(disabled=True, timeout=None)
        )


class PickUpIceCreamView(discord.ui.View):
    def __init__(self, disabled=False, timeout=300):
        super().__init__(timeout=timeout)
        self.add_item(PickUpIceCreamButton(disabled=disabled))

    async def on_timeout(self):
        if not any(item.disabled for item in self.children):
            for item in self.children:
                item.disabled = True
            expired_embed = discord.Embed(
                title="A wild 🍦 has appeared.",
                description="⏳ The ice cream melted before anyone could eat it!",
                color=discord.Color.light_grey()
            )
            try:
                await self.message.edit(embed=expired_embed, view=self)
            except discord.NotFound:
                pass


async def pickUpIceCream(channel, client):
    num = random.randint(5000, 8000)
    view = PickUpIceCreamView()
    msg = await channel.send(
        embed=discord.Embed(
            title=f"A wild 🍦 has appeared.",
            description=f"First to eat can earn **up to** {MORA_EMOTE} `{num}`, **BUT** you can also lose up to that amount. \nIt's simply a 50/50 chance.",
            color=discord.Color.fuchsia(),
        ),
        view=view
    )
    view.message = msg 


### --- TYPE RACER --- ###

async def createImage(
    text, bg="./assets/F7E8BE.png", filename="./assets/typeracer.png"
):
    im1 = Image.open(bg)
    color = (0, 0, 0)
    font = ImageFont.truetype("./assets/ja-jp.ttf", 55)
    d1 = ImageDraw.Draw(im1)
    d1.text((120, 60), text, font=font, fill=color)
    im1.save(filename)
    return filename


async def quicktype(channel, client):
    reward = random.randint(4000, 6000)
    start_time = time.time() 
    timeout = 300

    gen = DocumentGenerator()
    words = str(gen.sentence())[:25]
    filename = await createImage(words)
    chn = client.get_channel(1026968305208131645)
    img_msg = await chn.send(file=discord.File(filename))
    url = img_msg.attachments[0].proxy_url
    
    embed = discord.Embed(
        title=f"Quicktype Racer",
        description=f"First to type the following phrase in chat wins {MORA_EMOTE} `{reward}`.",
        color=discord.Color.blurple(),
    )
    embed.set_image(url=url)
    game_msg = await channel.send(embed=embed)

    def check(message):
        return (
            message.channel == channel and
            not message.author.bot
        )

    qualified_users = set()
    winner_id = None

    while True:
        try:
            elapsed = time.time() - start_time
            answer = await client.wait_for('message', check=check)

            typed = answer.content.strip()
            correct = words.strip()

            if typed == correct:
                try:
                    await answer.add_reaction("<:yes:1036811164891480194>")
                except Exception:
                    continue
                    
                winner_id = answer.author.id
                text, addedMora = await addMora(answer.author.id, reward, answer.channel.id, answer.guild.id, client)
                success_embed = discord.Embed(
                    title=f"Quicktype Racer",
                    description=f"{userAndTitle(answer.author.id, answer.guild.id)} won {MORA_EMOTE} `{text}`.",
                    color=discord.Color.brand_green(),
                )
                success_embed.set_image(url=url)
                await game_msg.edit(embed=success_embed)

                await update_quest(
                    answer.author.id,
                    channel.guild.id,
                    channel.id,
                    {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora},
                    client
                )
                break

            elif sum(1 for a, b in zip(typed, correct) if a == b) >= 10:
                qualified_users.add(answer.author.id)
                try:
                    await answer.add_reaction("<:no:1036810470860013639>")
                except Exception:
                    continue

            if elapsed >= timeout:
                timeout_embed = discord.Embed(
                    title="Quicktype Racer - Time Out! ⌛",
                    description=f"No one typed the phrase in time!\n**Correct answer:** `{words}`",
                    color=discord.Color.light_grey()
                )
                timeout_embed.set_image(url=url)
                await game_msg.edit(embed=timeout_embed)
                break

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"Type Racer error: {e}")
            return

    for uid in qualified_users:
        if uid != winner_id:
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                {"participate_minigames": 1},
                client
            )


### --- REVERSE QUICKTYPE --- ###

async def reverseQuicktype(channel, client):
    reward = random.randint(3000, 5000)
    start_time = time.time()
    timeout = 300

    words = "".join(str(random.randint(0, 9)) for _ in range(8))
    reversed_words = words[::-1]

    filename = await createImage(words, bg="./assets/94e3fe.png")
    chn = client.get_channel(1026968305208131645)
    img_msg = await chn.send(file=discord.File(filename))
    url = img_msg.attachments[0].proxy_url

    embed = discord.Embed(
        title="Reverse Number Quicktype",
        description=f"First to type the following numbers **IN REVERSE** in chat wins {MORA_EMOTE} `{reward}`.",
        color=discord.Color.blurple(),
    )
    embed.set_image(url=url)
    game_msg = await channel.send(embed=embed)

    def check(message):
        return (
            message.channel == channel and
            not message.author.bot
        )

    qualified_users = set()
    winner_id = None

    while True:
        try:
            elapsed = time.time() - start_time
            answer = await client.wait_for('message', check=check)

            typed = answer.content.strip()

            if typed == reversed_words:
                try:
                    await answer.add_reaction("<:yes:1036811164891480194>")
                except Exception:
                    continue
                    
                winner_id = answer.author.id
                text, addedMora = await addMora(answer.author.id, reward, answer.channel.id, answer.guild.id, client)
                success_embed = discord.Embed(
                    title="Reverse Number Quicktype",
                    description=f"{userAndTitle(answer.author.id, answer.guild.id)} won {MORA_EMOTE} `{text}`.",
                    color=discord.Color.brand_green(),
                )
                success_embed.set_image(url=url)
                await game_msg.edit(embed=success_embed)

                await update_quest(
                    answer.author.id,
                    channel.guild.id,
                    channel.id,
                    {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora},
                    client
                )
                break

            elif sum(1 for a, b in zip(typed, reversed_words) if a == b) >= 5:
                try:
                    await answer.add_reaction("<:no:1036810470860013639>")
                except Exception:
                    continue
                qualified_users.add(answer.author.id)

            if elapsed >= timeout:
                timeout_embed = discord.Embed(
                    title="Reverse Quicktype - Time Out! ⌛",
                    description=f"**Original Numbers:** `{words}`\n**Reversed Answer:** `{reversed_words}`\nNo one answered in time!",
                    color=discord.Color.light_grey()
                )
                timeout_embed.set_image(url=url)
                await game_msg.edit(embed=timeout_embed)
                break

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"Reverse Quicktype error: {e}")
            return

    for uid in qualified_users:
        if uid != winner_id:
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                {"participate_minigames": 1},
                client
            )


### --- UNSCRAMBLE THE SCRAMBLED --- ###

def scramble_string(input_string):
    char_list = list(input_string)
    random.shuffle(char_list)
    while True:
        if char_list == list(input_string):
            random.shuffle(char_list)
        else:
            break
    scrambled_string = "".join(char_list)
    return scrambled_string


async def unscrambleWords(channel, client):
    reward = random.randint(3000, 5000)
    start_time = time.time()
    timeout = 300

    from assets.words import words
    word = random.choice(words).strip().lower()
    scrambled = scramble_string(word)

    embed = discord.Embed(
        title="Unscramble the Scrambled",
        description=(
            f"First to unscramble the following word wins {MORA_EMOTE} `{reward}`.\n"
            "**Hint:** Might be related to Genshin/HSR!"
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Scrambled Word", value=f"`{scrambled}`", inline=True)
    game_msg = await channel.send(embed=embed)

    def check(message):
        return (
            message.channel == channel and
            not message.author.bot
        )

    qualified_users = set()
    winner_id = None

    def contains_all_letters(answer_str, scrambled_str):
        from collections import Counter
        answer_counter = Counter(answer_str)
        scrambled_counter = Counter(scrambled_str)
        for letter, count in scrambled_counter.items():
            if answer_counter[letter] < count:
                return False
        return True

    while True:
        try:
            elapsed = time.time() - start_time
            answer = await client.wait_for('message', check=check)
            typed = answer.content.lower().strip()

            if typed == word:
                try:
                    await answer.add_reaction("<:yes:1036811164891480194>")
                except Exception:
                    continue
                    
                winner_id = answer.author.id
                text, addedMora = await addMora(answer.author.id, reward, answer.channel.id, answer.guild.id, client)
                success_embed = discord.Embed(
                    title="Unscramble the Scrambled",
                    description=(
                        f"{userAndTitle(answer.author.id, answer.guild.id)} won {MORA_EMOTE} `{text}`.\n\n"
                        f"**Scrambled:** `{scrambled}`\n"
                        f"**Correct:** `{word}`"
                    ),
                    color=discord.Color.brand_green(),
                )
                await game_msg.edit(embed=success_embed)

                await update_quest(
                    answer.author.id,
                    channel.guild.id,
                    channel.id,
                    {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora},
                    client
                )
                break

            elif contains_all_letters(typed, scrambled):
                try:
                    await answer.add_reaction("<:no:1036810470860013639>")
                except Exception:
                    continue
                qualified_users.add(answer.author.id)

            if elapsed >= timeout:
                timeout_embed = discord.Embed(
                    title="Unscramble - Time Out! ⌛",
                    description=(
                        f"**Scrambled:** `{scrambled}`\n"
                        f"**Correct Answer:** `{word}`\n"
                        "No one guessed in time!"
                    ),
                    color=discord.Color.light_grey(),
                )
                await game_msg.edit(embed=timeout_embed)
                break

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"Unscramble error: {e}")
            return

    for uid in qualified_users:
        if uid != winner_id:
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                {"participate_minigames": 1},
                client
            )


### --- ROLL A DICE --- ###

class RollDiceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label="Roll Dice",
            emoji="🎲"
        )

    async def callback(self, interaction: discord.Interaction):
        view: RollDiceView = self.view
        user_id = interaction.user.id

        if user_id not in view.user_rolls:
            view.user_rolls[user_id] = []

        if len(view.user_rolls[user_id]) >= 2:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You've already rolled twice!", 
                ephemeral=True
            )
            return

        roll = random.randint(1, 6)
        view.user_rolls[user_id].append(roll)

        current_total = sum(view.user_rolls[user_id])

        if len(view.user_rolls[user_id]) == 1:
            msg = (
                f"You rolled: **{roll}**\n"
                f"Your current total: **{current_total}**\n"
                "Click again to roll your second dice!"
            )
        else:
            view.participant_ids.add(user_id)
            msg = (
                f"You rolled: **{roll}**\n"
                f"Your total: **{current_total}**\n"
                "<:yes:1036810470860013639> You've completed your two rolls! Wait patiently for the results!"
            )

        await interaction.response.send_message(embed=discord.Embed(description=msg, color=discord.Color.green()), ephemeral=True)


class RollDiceView(discord.ui.View):
    def __init__(self, target, reward, timeout=45):
        super().__init__(timeout=timeout)
        self.target = target
        self.reward = reward
        self.user_rolls = {} 
        self.participant_ids = set()
        self.message = None
        self.add_item(RollDiceButton())

    async def on_timeout(self):
        if not self.user_rolls:
            embed = discord.Embed(
                title="Roll a Dice - Time's Up!",
                description="No one rolled the dice in time!",
                color=discord.Color.red()
            )
            await self.message.edit(embed=embed, view=None)
            return

        totals = {user_id: sum(rolls) for user_id, rolls in self.user_rolls.items()}

        min_diff = float('inf')
        winners = []

        for user_id, total in totals.items():
            diff = abs(total - self.target)
            if diff < min_diff:
                min_diff = diff
                winners = [(user_id, total)]
            elif diff == min_diff:
                winners.append((user_id, total))

        reward_lines = []
        for winner_id, total in winners:
            reward_multiplier = 2 if total == self.target else 1
            final_reward = self.reward * reward_multiplier
            text, addedMora = await addMora(
                winner_id,
                final_reward,
                self.message.channel.id,
                self.message.guild.id,
                self.message._state._get_client()
            )
            reward_lines.append(
                f"-# <@{winner_id}>: {MORA_EMOTE} `{text}` "
                f"({'Exact match! ' if total == self.target else ''}Rolled: {total})"
            )

            await update_quest(
                winner_id,
                self.message.guild.id,
                self.message.channel.id,
                {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora},
                self.message._state._get_client()
            )

        for participant_id in self.participant_ids:
            if participant_id not in [w[0] for w in winners]:
                await update_quest(
                    participant_id,
                    self.message.guild.id,
                    self.message.channel.id,
                    {"participate_minigames": 1},
                    self.message._state._get_client()
                )

        result_embed = discord.Embed(
            title="Roll a Dice 🎲 - Results",
            description=(
                f"Target number: **{self.target}**\n"
                f"Base reward: {MORA_EMOTE} `{self.reward}`\n\n"
                f"**Winners:**\n" + "\n".join(reward_lines)
            ),
            color=discord.Color.green()
        )
        await self.message.reply(embed=result_embed, view=None)


async def rollADice(channel, client):
    target = random.randint(2, 12)
    reward = random.randint(4000, 6000)

    embed = discord.Embed(
        title="Roll a Dice 🎲",
        description=(
            f"Roll **a dice twice** and get as close as possible to **{target}**!\n"
            f"> Base reward: {MORA_EMOTE} `{reward}` | Exact match doubles your reward!\n"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Game ends after no one rolls for 45 seconds")

    view = RollDiceView(target, reward)
    message = await channel.send(embed=embed, view=view)
    view.message = message


class QuizButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(style=discord.ButtonStyle.primary, label=label)

    async def callback(self, interaction: discord.Interaction):
        view: QuizView = self.view
        
        if interaction.user.id in view.participants:
             await interaction.response.send_message("You have already answered!", ephemeral=True)
             return

        view.participants.add(interaction.user.id)
        
        if self.label == view.answer:
            view.winner_id = interaction.user.id
            await interaction.response.defer()
            
            for child in view.children:
                child.disabled = True
                if child.label == view.answer:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary
            
            view.stop()
            
            text, addedMora = await addMora(interaction.user.id, view.reward, view.channel.id, view.channel.guild.id, view.client)
            success_embed = view.win_embed_factory(interaction.user, text)
            await view.game_msg.edit(embed=success_embed, view=view)

            await update_quest(
                interaction.user.id,
                view.channel.guild.id,
                view.channel.id,
                {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora},
                view.client
            )
        else:
            await interaction.response.send_message("That is incorrect!", ephemeral=True)

class QuizView(discord.ui.View):
    def __init__(self, answer, options, reward, client, channel, win_embed_factory, timeout_embed_factory=None):
        super().__init__(timeout=300)
        self.answer = answer
        self.options = options
        
        # Ensure answer is in options, just in case
        if self.answer not in self.options:
            self.options.append(self.answer)
            
        random.shuffle(self.options)
        self.reward = reward
        self.client = client
        self.channel = channel
        self.game_msg = None
        self.win_embed_factory = win_embed_factory
        self.timeout_embed_factory = timeout_embed_factory
        self.winner_id = None
        self.participants = set()

        for option in self.options:
            self.add_item(QuizButton(option))
            
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        
        if self.game_msg:
            if self.timeout_embed_factory:
                embed = self.timeout_embed_factory()
                await self.game_msg.edit(embed=embed, view=self)
            else:
                 await self.game_msg.edit(view=self)


### --- GUESS THE VOICELINE --- ###

async def guessTheVoiceline(channel, client):
    reward = random.randint(4000, 6000)
    start_time = time.time()
    timeout = 300

    df = pd.read_csv(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVeIY2FLhHODz6nyJ5D8IWBtDRRttfIZNkUKnRmqoTksaHXxZnckUD7ou4s5DKT_CDRZbMBs9tlnd8/pub?output=csv"
    )
    characterEmojis = dict(zip(df["Character Name"], df["Emojis"]))
    valid_names = {name.lower() for name in characterEmojis.keys()}

    def replace_character_name(text, character_name):
        if " " not in character_name:
            return re.sub(
                r"\b" + character_name + r"\b",
                "_" * len(character_name),
                text,
                flags=re.IGNORECASE,
            )
        for word in character_name.split():
            text = re.sub(
                r"\b" + word + r"\b",
                "_" * len(word),
                text,
                flags=re.IGNORECASE,
            )
        return text

    processed_voice_lines = []

    while not processed_voice_lines:
        char = None
        while not char:
            char = random.choice(list(characterEmojis.keys()))
            formatted_char = char.replace(" ", "_")
            url = f"https://genshin-impact.fandom.com/wiki/{formatted_char}/Voice-Overs"
            try:
                response = requests.get(url)
                response.raise_for_status()
            except:
                char = None

        soup = BeautifulSoup(response.content, "html.parser")
        voice_lines = []
        tables = soup.find_all("table", class_="wikitable")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if cells:
                    line = cells[0].get_text(separator=" ", strip=True)
                    if line:
                        voice_lines.append(line)

        for ul in soup.find_all("ul"):
            for li in ul.find_all("li"):
                text = li.get_text(separator=" ", strip=True)
                if text.startswith('"') and text.endswith('"'):
                    voice_lines.append(text)

        voice_lines = list(dict.fromkeys(voice_lines))

        for line in voice_lines:
            if "class=hidden" not in line:
                split_line = line.split(".ogg")
                if len(split_line) > 2:
                    try:
                        new_line = split_line[2]
                        processed_line = replace_character_name(new_line, char)
                        processed_voice_lines.append(processed_line)
                    except Exception as e:
                        print(e)
    
    voiceline = random.choice(processed_voice_lines).strip()

    embed = discord.Embed(
        title="Teyvat Voiceline Quiz | Genshin Character",
        description=f"First to guess the character wins {MORA_EMOTE} `{reward}`.\n\n```{voiceline}```",
        color=discord.Color.blue(),
    )
    embed.set_footer(text="Voicelines from Genshin Impact Wiki Fandom • 5-minute time limit")
    print(voiceline)
    print(char)

    # Generate Distractors
    all_chars = list(characterEmojis.keys())
    distractors = random.sample([n for n in all_chars if n != char], 4)
    options = [char] + distractors

    def win_embed_factory(user, text):
        return discord.Embed(
            title="Teyvat Voiceline Quiz | Genshin Character",
            description=(
                f"```{voiceline}```\n"
                f"{userAndTitle(user.id, user.guild.id)} "
                f"answered `{char}` and won {MORA_EMOTE} `{text}`."
            ),
            color=discord.Color.brand_green(),
        )

    def timeout_embed_factory():
        return discord.Embed(
            title="Genshin Voiceline Quiz - Time Out! ⌛",
            description=(
                f"**Voiceline:** ```{voiceline}```\n"
                f"**Character:** `{char}`\n"
                "No one guessed in time!"
            ),
            color=discord.Color.light_grey(),
        )

    view = QuizView(char, options, reward, client, channel, win_embed_factory, timeout_embed_factory)
    game_msg = await channel.send(embed=embed, view=view)
    view.game_msg = game_msg

    await view.wait()

    for uid in view.participants:
        if uid != view.winner_id:
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                {"participate_minigames": 1},
                client
            )


### --- HSR EMOJI RIDDLE  --- ###

async def hsrEmojiRiddle(channel, client):
    reward = random.randint(3000, 5000)
    start_time = time.time()
    timeout = 300 

    df = pd.read_csv(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0pPz9A-wegeqpyIxYSjR-trCnP5ffIkOE-ThkVXhCC46pjgL9h5eEwOp42-oDce340eHYhO6TSbLl/pub?output=csv"
    )
    characterEmojis = dict(zip(df["Character Name"], df["Emojis"]))
    valid_names = {name.lower() for name in characterEmojis.keys()}

    character = random.choice(list(characterEmojis.keys()))
    response = characterEmojis[character]

    embed = discord.Embed(
        title="Galaxy *Emojified* Riddles | HSR Character",
        description=(
            f"The following emojis describe a **Honkai: Star Rail** character. "
            f"First to guess wins {MORA_EMOTE} `{reward}`.\n\n```{response}```"
        ),
        color=0xFFEB20,
    )
    embed.set_footer(text="Credits: schaeffly, treble4tea_03755, rubi134 • 5-minute time limit")
    
    # Generate Distractors
    all_chars = list(characterEmojis.keys())
    distractors = random.sample([n for n in all_chars if n != character], 4)
    options = [character] + distractors

    def win_embed_factory(user, text):
        success_embed = discord.Embed(
            title="Galaxy *Emojified* Riddles | HSR Character",
            description=(
                f"```{response}```\n"
                f"{userAndTitle(user.id, user.guild.id)} "
                f"answered `{character}` and won {MORA_EMOTE} `{text}`."
            ),
            color=discord.Color.brand_green(),
        )
        success_embed.set_footer(
            text="Credits: schaeffly, treble4tea_03755, rubi134, maraudersacrusader, fishyfishery"
        )
        return success_embed

    def timeout_embed_factory():
        return discord.Embed(
            title="HSR Emoji Riddle - Time Out! ⌛",
            description=(
                f"**Emojis:** ```{response}```\n"
                f"**Correct Answer:** `{character}`\n"
                "No one guessed in time!"
            ),
            color=discord.Color.light_grey()
        )

    view = QuizView(character, options, reward, client, channel, win_embed_factory, timeout_embed_factory)
    game_msg = await channel.send(embed=embed, view=view)
    view.game_msg = game_msg

    await view.wait()
    
    for uid in view.participants:
        if uid != view.winner_id:
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                {"participate_minigames": 1},
                client
            )

    
### --- GENSHIN EMOJI RIDDLE --- ###

async def genshinEmojiRiddle(channel, client):
    reward = random.randint(3000, 5000)
    start_time = time.time()
    timeout = 300

    df = pd.read_csv(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVeIY2FLhHODz6nyJ5D8IWBtDRRttfIZNkUKnRmqoTksaHXxZnckUD7ou4s5DKT_CDRZbMBs9tlnd8/pub?output=csv"
    )
    characterEmojis = dict(zip(df["Character Name"], df["Emojis"]))
    valid_names = {name.lower() for name in characterEmojis.keys()}

    character = random.choice(list(characterEmojis.keys()))
    response = characterEmojis[character]

    embed = discord.Embed(
        title="Teyvat *Emojified* Riddles | Genshin Character",
        description=(
            f"The following emojis describe a **Genshin Impact** character. "
            f"First to guess wins {MORA_EMOTE} `{reward}`.\n\n```{response}```"
        ),
        color=0xFFEB20,
    )
    embed.set_footer(text="Credits: schaeffly, treble4tea_03755 • 5-minute time limit")

    # Generate Distractors
    all_chars = list(characterEmojis.keys())
    distractors = random.sample([n for n in all_chars if n != character], 4)
    options = [character] + distractors

    def win_embed_factory(user, text):
        success_embed = discord.Embed(
            title="Teyvat *Emojified* Riddles | Genshin Character",
            description=(
                f"```{response}```\n"
                f"{userAndTitle(user.id, user.guild.id)} "
                f"answered `{character}` and won {MORA_EMOTE} `{text}`."
            ),
            color=discord.Color.brand_green(),
        )
        success_embed.set_footer(text="Credits: schaeffly, treble4tea_03755")
        return success_embed
    
    def timeout_embed_factory():
        return discord.Embed(
            title="Genshin Emoji Riddle - Time Out! ⌛",
            description=(
                f"**Emojis:** ```{response}```\n"
                f"**Correct Answer:** `{character}`\n"
                "No one guessed in time!"
            ),
            color=discord.Color.light_grey(),
        )

    view = QuizView(character, options, reward, client, channel, win_embed_factory, timeout_embed_factory)
    game_msg = await channel.send(embed=embed, view=view)
    view.game_msg = game_msg

    await view.wait()

    for uid in view.participants:
        if uid != view.winner_id:
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                {"participate_minigames": 1},
                client
            )


### --- EGGWALK --- ###

async def eggWalk(channel, client): 
    reward = random.randint(2000, 3000)
    start_time = time.time()
    timeout = 300

    embed = discord.Embed(
        title="Eggwalk",
        description=f"**Users must alternate!** Start at 1 and count to 10. \nEach number you type will earn you {MORA_EMOTE} `{reward}` if successful.",
        color=discord.Color.dark_purple(),
    )
    game_msg = await channel.send(embed=embed)

    def check(message):
        return message.channel == channel

    number = 1
    previousUser = None
    userCounts = {}
    userMoras = {}
    success = False

    while True:
        try:
            elapsed = time.time() - start_time
            answer = await client.wait_for("message", check=check)

            if answer.content.isnumeric():
                if answer.content.strip() == str(number):
                    if answer.author != previousUser:
                        try:
                            await answer.add_reaction("<:yes:1036811164891480194>")
                        except Exception:
                            continue
                        number += 1
                        previousUser = answer.author
                        userCounts[answer.author] = userCounts.get(answer.author, 0) + 1
                    else:
                        try:
                            await answer.add_reaction("<:no:1036810470860013639>")
                        except Exception:
                            continue
                        await answer.reply(
                            embed=discord.Embed(
                                title="Eggwalk",
                                description=f"{answer.author.mention} did not alternate! Good luck next time!",
                                color=discord.Color.red(),
                            )
                        )
                        break
                else:
                    try:
                        await answer.add_reaction("<:no:1036810470860013639>")
                    except Exception:
                        continue
                    await answer.reply(
                        embed=discord.Embed(
                            title="Eggwalk",
                            description=f"Wrong number. Next number should be `{number}`! Better luck next time!",
                            color=discord.Color.red(),
                        )
                    )
                    break

                if number > 10:
                    success = True
                    summary_lines = []
                    for user, count in userCounts.items():
                        total_reward = count * reward
                        text, addedMora = await addMora(user.id, total_reward, answer.channel.id, answer.guild.id, client)
                        userMoras[user.id] = addedMora
                        summary_lines.append(
                            f"-# - {userAndTitle(user.id, answer.guild.id)}: {count} numbers → {MORA_EMOTE} `{text}`"
                        )

                    final_embed = discord.Embed(
                        title="Eggwalk - Success!",
                        description="Good job everyone! That is not an easy task!\n\n" + "\n".join(summary_lines),
                        color=discord.Color.green(),
                    )
                    await game_msg.reply(embed=final_embed)
                    break

            else:
                if elapsed >= timeout:
                    timeout_embed = discord.Embed(
                        title="Eggwalk - Time Out!",
                        description="⏳ The game is not finished in time!",
                        color=discord.Color.light_grey()
                    )
                    await game_msg.edit(embed=timeout_embed)
                    return

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"Eggwalk: {e}")
            return

    for user, count in userCounts.items():
        quest_data = {"participate_minigames": 1}
        if success:
            quest_data["win_minigames"] = 1
            quest_data["earn_mora"] = userMoras[user.id]
        await update_quest(user.id, channel.guild.id, channel.id, quest_data, client)


### --- GUESS THE NUMBER --- ###

async def guessTheNumber(channel, client):
    reward = random.randint(3000, 5000)
    start_time = time.time()
    timeout = 300

    embed = discord.Embed(
        title="Guess The Mystery Number",
        description=(
            "First to guess what number in **between 1 and 10 (inclusive)** I am thinking of "
            f"will earn {MORA_EMOTE} `{reward}`."
        ),
        color=discord.Color.dark_purple(),
    )

    number = random.randint(1, 10)
    view = GuessNumberView(number)
    game_msg = await channel.send(embed=embed, view=view)
    
    await view.wait()
    
    if view.winner_id:
        embed.color = discord.Color.green()
        embed.description += f"\n\n🏆 {userAndTitle(view.winner_id, channel.guild.id)} got it and earned {MORA_EMOTE} `{view.winner_text}`."
        await game_msg.edit(embed=embed, view=view)
    else:
        timeout_embed = discord.Embed(
            title="Guess The Mystery Number",
            description="⏳ Was it really that hard to guess a number between 1 to 10?",
            color=discord.Color.light_grey(),
        )
        for child in view.children:
            child.disabled = True
        await game_msg.edit(embed=timeout_embed, view=view)

    for uid in view.participants:
        quest_data = {"participate_minigames": 1}
        if uid == view.winner_id:
            quest_data.update({"win_minigames": 1})
            quest_data.update({"earn_mora": view.addedMora})
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)

class GuessNumberButton(discord.ui.Button):
    def __init__(self, number, row):
        super().__init__(label=str(number), style=discord.ButtonStyle.secondary, row=row)
        self.number = number

    async def callback(self, interaction: discord.Interaction):
        view: GuessNumberView = self.view
        
        if interaction.user.id not in view.participants:
            view.participants.add(interaction.user.id)
            
        if self.number == view.target_number:
            self.style = discord.ButtonStyle.success
            view.winner_id = interaction.user.id
            reward = int(interaction.message.embeds[0].description.split("`")[1])
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            view.addedMora = addedMora
            view.winner_text = text
            
            for child in view.children:
                child.disabled = True
                if child.label == str(view.target_number):
                    child.style = discord.ButtonStyle.success
            
            view.stop()
            await interaction.response.defer()
        else:
            self.style = discord.ButtonStyle.danger
            self.disabled = True
            await interaction.response.edit_message(view=view)

class GuessNumberView(discord.ui.View):
    def __init__(self, target_number):
        super().__init__(timeout=300)
        self.target_number = target_number
        self.participants = set()
        self.winner_id = None
        self.addedMora = 0
        self.winner_text = ""
        
        # Row 0: 1-5
        for i in range(1, 6):
            self.add_item(GuessNumberButton(i, row=0))
            
        # Row 1: 6-10
        for i in range(6, 11):
            self.add_item(GuessNumberButton(i, row=1))


### --- COUNTING CURRENCY --- ###

async def countingCurrency(channel, client):
    reward = random.randint(3000, 5000)
    start_time = time.time()
    timeout = 300

    A = f"{MORA_EMOTE}"
    B = "<:PRIMOGEM:1364031230357540894>"
    C = "<:Polychrome:1316607903939035236>"

    grid = [[None for _ in range(15)] for _ in range(15)]
    fill_probability = 0.2

    for i in range(15):
        for j in range(15):
            if random.random() < fill_probability:
                grid[i][j] = random.choice([A, B, C])

    gridString = ""
    for row in grid:
        for col in row:
            gridString += col if col else "ㅤ"
        gridString += "\n"

    itemToCount = random.choice([A, B, C])
    embed = discord.Embed(
        title="Currency Counting",
        description=f"{gridString}\nFirst to count how many {itemToCount} there are wins {MORA_EMOTE} `{reward}`. Type the number in chat.",
        color=discord.Color.blue(),
    )
    game_msg = await channel.send(embed=embed)

    def check(message):
        return message.channel == channel and not message.author.bot

    number = sum(row.count(itemToCount) for row in grid)
    participants = set()
    winner_id = None
    addedMora = 0

    while True:
        try:
            elapsed = time.time() - start_time
            answer = await client.wait_for("message", check=check)

            if answer.content.isnumeric():
                participants.add(answer.author.id)
                if int(answer.content.strip()) == number:
                    try:
                        await answer.add_reaction("<:yes:1036811164891480194>")
                    except Exception:
                        continue
                    winner_id = answer.author.id
                    text, addedMora = await addMora(winner_id, reward, answer.channel.id, answer.guild.id, client)
                    await answer.reply(
                        embed=discord.Embed(
                            title="Currency Counting",
                            description=f"{userAndTitle(winner_id, answer.guild.id)} got it and earned {MORA_EMOTE} `{text}`.",
                            color=discord.Color.green(),
                        )
                    )
                    break
                else:
                    try:
                        await answer.add_reaction("<:no:1036810470860013639>")
                    except Exception:
                        continue
                    asyncio.create_task(handle_message_deletion(answer))

            elif elapsed >= timeout:
                timeout_embed = discord.Embed(
                    title="Currency Counting - Time Out! ⌛",
                    description=(
                        f"{gridString}\n**Correct Count:** `{number}` {itemToCount}\n"
                        f"No one answered in time!"
                    ),
                    color=discord.Color.red()
                )
                await game_msg.edit(embed=timeout_embed)
                break

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"Currency Counting: {e}")
            return

    for uid in participants:
        quest_data = {"participate_minigames": 1}
        if uid == winner_id:
            quest_data.update({"win_minigames": 1})
            quest_data.update({"earn_mora": addedMora})
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)


### --- HANGMAN --- ###

def choose_word():
    from assets.words import words
    # Filter out words containing 'z'
    available_words = [w for w in words if 'z' not in w.lower()]
    if not available_words:
        return "error"
    return random.choice(available_words).lower()

def update_word(word, guessed_letters):
    return ''.join([letter if letter in guessed_letters else '_' for letter in word])

def format_guess_dict(d):
    return "\n".join([f"- <@{uid}>: {', '.join(sorted(letters))}" for uid, letters in d.items()]) or "`None`"

class HangmanButton(discord.ui.Button):
    def __init__(self, letter, row):
        super().__init__(label=letter, style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view: HangmanView = self.view
        letter = self.label.lower()
        
        if interaction.user.id not in view.participants:
            view.participants.add(interaction.user.id)

        if letter in view.word:
            self.style = discord.ButtonStyle.success
            view.guessed_letters.add(letter)
            if interaction.user.id not in view.correct_letters:
                view.correct_letters[interaction.user.id] = set()
            view.correct_letters[interaction.user.id].add(letter)
        else:
            self.style = discord.ButtonStyle.danger
            view.tries -= 1
            if interaction.user.id not in view.incorrect_letters:
                view.incorrect_letters[interaction.user.id] = set()
            view.incorrect_letters[interaction.user.id].add(letter)

        self.disabled = True
        
        display_word = update_word(view.word, view.guessed_letters)
        
        view.embed.set_field_at(0, name="Word:", value=f"`{display_word}`", inline=False)
        view.embed.set_field_at(1, name="<:yes:1036811164891480194> Correct letters:", value=format_guess_dict(view.correct_letters), inline=True)
        view.embed.set_field_at(2, name="<:no:1036810470860013639> Incorrect letters:", value=format_guess_dict(view.incorrect_letters), inline=True)
        view.embed.set_field_at(3, name="Tries remaining:", value=f"`{view.tries}`", inline=True)

        if "_" not in display_word:
             view.winner_id = interaction.user.id
             text, addedMora = await addMora(interaction.user.id, 3000, interaction.channel.id, interaction.guild.id, interaction.client)
             view.addedMora = addedMora
             view.winner_text = text
             
             # Disable all buttons
             for child in view.children:
                 child.disabled = True
                 
             view.stop()
             await interaction.response.defer()
        elif view.tries <= 0:
             # Disable all buttons
             for child in view.children:
                 child.disabled = True

             view.stop()
             await interaction.response.defer()
        else:
             await interaction.response.edit_message(embed=view.embed, view=view)

class HangmanView(discord.ui.View):
    def __init__(self, word, embed, tries):
        super().__init__(timeout=300)
        self.word = word
        self.embed = embed
        self.tries = tries
        self.guessed_letters = set()
        self.correct_letters = {}
        self.incorrect_letters = {}
        self.participants = set()
        self.winner_id = None
        self.addedMora = 0
        self.winner_text = ""

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXY"
        for i, letter in enumerate(letters):
            self.add_item(HangmanButton(letter, row=i // 5))

async def hangmanGame(channel, client):
    word = choose_word().lower()
    print(word)
    tries = round(5 + 0.4 * len(word))
    
    guessed_letters = set()
    incorrect_letters = {}
    correct_letters = {}
    
    display_word = update_word(word, guessed_letters)
    embed = discord.Embed(
        title="Hangman Game",
        description=f"**Guess a letter!** Earn {MORA_EMOTE} **1500** per correct letter and an extra {MORA_EMOTE} **3000** for completing the word.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Word:", value=f"`{display_word}`", inline=False)
    embed.add_field(name="<:yes:1036811164891480194> Correct letters:", value=format_guess_dict(correct_letters), inline=True)
    embed.add_field(name="<:no:1036810470860013639> Incorrect letters:", value=format_guess_dict(incorrect_letters), inline=True)
    embed.add_field(name="Tries remaining:", value=f"`{tries}`", inline=True)
    embed.set_footer(text="Click a letter to guess • 5-minute time limit")
    
    view = HangmanView(word, embed, tries)
    game_msg = await channel.send(embed=embed, view=view)
    
    # Wait for the view to finish (timeout or win/loss)
    await view.wait()
    
    # After game ends (loop logic replacement)
    
    if view.winner_id or "_" not in update_word(word, view.guessed_letters):
        final_embed = discord.Embed(
            title="Hangman Game",
            description=f"Success! Everyone got {MORA_EMOTE} **`1500`** per correct letter. {userAndTitle(view.winner_id, channel.guild.id)} earned an extra {MORA_EMOTE} **`{view.winner_text}`**.",
            color=discord.Color.green()
        )
    elif view.tries <= 0:
        final_embed = discord.Embed(
            title="Hangman Game",
            description=f"Game over! The word was `{word}`. Better luck next time!",
            color=discord.Color.red()
        )
    else: # Timeout
        final_embed = discord.Embed(
            title="Hangman - Time Out! ⌛",
            description=f"Game over! The word was `{word}`. Better luck next time!",
            color=discord.Color.light_grey()
        )
        
        # Disable buttons on timeout if not already
        for child in view.children:
            child.disabled = True
        await game_msg.edit(view=view)

    display_word = update_word(word, view.guessed_letters)
    final_embed.add_field(name="Word:", value=f"`{display_word}`", inline=False)
    final_embed.add_field(name="<:yes:1036811164891480194> Correct letters:", value=format_guess_dict(view.correct_letters), inline=True)
    final_embed.add_field(name="<:no:1036810470860013639> Incorrect letters:", value=format_guess_dict(view.incorrect_letters), inline=True)
    final_embed.add_field(name="Tries remaining:", value=f"`{view.tries}`", inline=True)

    for user_id, letters in view.correct_letters.items():
        count = sum(word.count(letter) for letter in letters)
        reward = count * 1500
        if reward > 0:
            await addMora(user_id, reward, channel.id, game_msg.guild.id, client)

    await game_msg.edit(embed=final_embed, view=view)

    for uid in view.participants:
        quest_data = {"participate_minigames": 1}
        if uid == view.winner_id:
            quest_data["win_minigames"] = 1
            quest_data["earn_mora"] = view.addedMora
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)


### --- MATCH THE PROFILE PICTURE --- ###

class MatchPFPState:
    def __init__(self, correct_name, avatar_url):
        self.correct_name = correct_name
        self.avatar_url = avatar_url
        self.participants = []

class MatchPFPButton(discord.ui.Button):
    def __init__(self, name, target_name):
        super().__init__(label=name, style=discord.ButtonStyle.grey)
        self.target_name = target_name

    async def callback(self, interaction: discord.Interaction):
        game_state = active_pfp_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.participants:
            await interaction.response.send_message("<:no:1036810470860013639> You already guessed!", ephemeral=True)
            return

        game_state.participants.append(interaction.user.id)
        
        if self.target_name == game_state.correct_name:
            reward = int(interaction.message.embeds[0].description.split("`")[1])
            
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            embed = discord.Embed(
                title=f"Who's this?",
                description=f"{userAndTitle(interaction.user.id, interaction.guild.id)} guessed **{self.label}** correctly and earned {MORA_EMOTE} `{text}`.",
                color=discord.Color.green()
            )
            embed.set_image(url=game_state.avatar_url)
            
            for child in self.view.children:
                child.disabled = True
                if child.label == self.label:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary
            
            await interaction.response.edit_message(embed=embed, view=self.view)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)
            del active_pfp_games[interaction.message.id]
        else:
            await interaction.response.send_message("Wrong! <:no:1036810470860013639>", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

async def matchThePFP(channel, client):
    messages = [message async for message in channel.history(limit=200)]
    selected_items = []
    unique_ids = set()
    
    for message in messages:
        author = message.author
        if not author.bot and author.id != client.user.id and author.id not in unique_ids:
            selected_items.append(author)
            unique_ids.add(author.id)
        if len(selected_items) == 3:
            break

    if len(selected_items) < 3:
        return await channel.send(embed=discord.Embed(description="<:no:1036810470860013639> Not enough unique users for the game."))

    target_user = random.choice(selected_items)
    
    view = View()
    for user in selected_items:
        view.add_item(MatchPFPButton(
            name=user.display_name,
            target_name=user.display_name
        ))

    reward = random.randint(3000, 5000)
    embed = discord.Embed(
        title=f"Who's this?",
        description=f"First to guess wins {MORA_EMOTE} `{reward}`. **You can only guess once!**",
        color=discord.Color.light_grey()
    )
    embed.set_image(url=target_user.avatar.url)

    game_message = await channel.send(embed=embed, view=view)

    active_pfp_games[game_message.id] = MatchPFPState(
        correct_name=target_user.display_name,
        avatar_url=target_user.avatar.url
    )

    async def cleanup():
        await asyncio.sleep(300)
        if game_message.id in active_pfp_games:
            del active_pfp_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="⏳ This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(cleanup())


### --- WHO SAID IT --- ###

class WhoSaidItState:
    def __init__(self, correct_author, jump_url):
        self.correct_author = correct_author
        self.jump_url = jump_url
        self.participants = []

class WhoSaidItButton(discord.ui.Button):
    def __init__(self, display_name, target_author):
        super().__init__(label=display_name, style=discord.ButtonStyle.grey)
        self.target_author = target_author

    async def callback(self, interaction: discord.Interaction):
        game_state = active_who_said_it_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.participants:
            await interaction.response.send_message("<:no:1036810470860013639> You already guessed!", ephemeral=True)
            return

        game_state.participants.append(interaction.user.id)
        
        if self.target_author == game_state.correct_author:
            reward = int(interaction.message.embeds[0].description.split("`")[1])
            
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            embed = discord.Embed(
                title="Who Said That?",
                description=f"{userAndTitle(interaction.user.id, interaction.guild.id)} guessed **{self.label}** correctly and earned {MORA_EMOTE} `{text}`.\n\n[Message Jump URL]({game_state.jump_url})",
                color=discord.Color.green()
            )
            
            for child in self.view.children:
                child.disabled = True
                if child.label == self.label:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

            await interaction.response.edit_message(embed=embed, view=self.view)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)
            del active_who_said_it_games[interaction.message.id]
        else:
            await interaction.response.send_message("Wrong! <:no:1036810470860013639>", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

async def whoSaidIt(channel, client):
    selected_messages = []
    unique_authors = set()
    
    async for message in channel.history(limit=100):
        if (message.author != client.user and
            not message.author.bot and
            message.content.strip() and
            message.author.id not in unique_authors):
            
            selected_messages.append(message)
            unique_authors.add(message.author.id)
            if len(selected_messages) == 3:
                break

    if len(selected_messages) < 3:
        return await channel.send(embed=discord.Embed(description="<:no:1036810470860013639> Not enough unique messages for the game."))

    target_message = random.choice(selected_messages)
    options = selected_messages

    view = View()
    for msg in options:
        view.add_item(WhoSaidItButton(
            display_name=msg.author.display_name,
            target_author=msg.author.id
        ))

    reward = random.randint(3000, 5000)
    embed = discord.Embed(
        title="Who Said That?",
        description=f"The first to guess wins {MORA_EMOTE} `{reward}`. **You can only guess once!**",
        color=discord.Color.light_grey()
    )
    embed.add_field(name="Message Content", value=target_message.content, inline=False)

    game_message = await channel.send(embed=embed, view=view)

    active_who_said_it_games[game_message.id] = WhoSaidItState(
        correct_author=target_message.author.id,
        jump_url=target_message.jump_url
    )

    async def cleanup():
        await asyncio.sleep(300)
        if game_message.id in active_who_said_it_games:
            del active_who_said_it_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="⌛ This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(cleanup())


### --- KNOW YOUR MEMBERS --- ###

class KnowMembersState:
    def __init__(self, correct_member, question, participants):
        self.correct_member = correct_member
        self.question = question
        self.participants = participants
        self.answerers = []

class KnowMembersButton(discord.ui.Button):
    def __init__(self, label, target_member, correct_member):
        super().__init__(label=label, style=discord.ButtonStyle.grey)
        self.target_member = target_member
        self.correct_member = correct_member

    async def callback(self, interaction: discord.Interaction):
        game_state = active_know_members_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.answerers:
            await interaction.response.send_message("<:no:1036810470860013639> You already guessed!", ephemeral=True)
            return

        game_state.answerers.append(interaction.user.id)
        
        if self.target_member.id == game_state.correct_member.id:
            reward = int(interaction.message.embeds[0].description.split("`")[1])
            
            participants_info = "\n".join(
                f"- **{child.label}**: <t:{int(member.joined_at.timestamp())}:D>"
                for member, child in zip(game_state.participants, self.view.children)
            )
            
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description = f"**{game_state.question}**\n\n{userAndTitle(interaction.user.id, interaction.guild.id)} answered correctly and earned {MORA_EMOTE} `{text}`!\n\n**Server Join Dates:**\n{participants_info}"
            
            for child in self.view.children:
                child.disabled = True
                if child.label == self.label:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

            await interaction.response.edit_message(embed=embed, view=self.view)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)
            del active_know_members_games[interaction.message.id]
        else:
            await interaction.response.send_message("Incorrect! <:no:1036810470860013639>", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

async def knowYourMembers(channel, client):
    messages = [msg async for msg in channel.history(limit=10) if msg.author != client.user and not msg.author.bot and msg.content]
    
    author_ids = list({msg.author.id for msg in messages if not msg.author.bot})
    if len(author_ids) < 2:
        return await channel.send(embed=discord.Embed(description="<:no:1036810470860013639> Not enough unique recent messaging users for the game."))
    
    authors = []
    for author_id in author_ids:
        try:
            member = await channel.guild.fetch_member(author_id)
            authors.append(member)
        except discord.NotFound:
            continue
    
    if len(authors) < 2:
        return await channel.send(embed=discord.Embed(description="<:no:1036810470860013639> Not enough valid members for the game."))
    
    selected = random.sample(authors, 2)
    mode = random.choice(["earlier", "later", "specific"])

    if mode == "earlier":
        sorted_members = sorted(selected, key=lambda m: m.joined_at)
        question = f"Which user has been in **{channel.guild.name}** longer?"
        correct_member = sorted_members[0]
    elif mode == "later":
        sorted_members = sorted(selected, key=lambda m: m.joined_at, reverse=True)
        question = f"Which user is newer in **{channel.guild.name}**?"
        correct_member = sorted_members[0]
    else:
        correct_member = random.choice(selected)
        question = f"Which user joined on <t:{int(correct_member.joined_at.timestamp())}:D>?"

    view = View()
    for member in selected:
        view.add_item(KnowMembersButton(
            label=member.display_name,
            target_member=member,
            correct_member=correct_member
        ))

    reward = random.randint(3000, 5000)
    embed = discord.Embed(
        title="Know Your Members",
        description=f"{question}\nFirst correct guess earns {MORA_EMOTE} `{reward}`",
        color=0x9dbfc4
    )
    game_message = await channel.send(embed=embed, view=view)

    active_know_members_games[game_message.id] = KnowMembersState(
        correct_member=correct_member,
        question=question,
        participants=selected
    )

    async def cleanup():
        await asyncio.sleep(300)
        if game_message.id in active_know_members_games:
            del active_know_members_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="⏳ This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(cleanup())


### --- MEMORY GAME --- ###

class MemoryGameState:
    def __init__(self, correct_emote, chosen_col):
        self.correct_emote = correct_emote
        self.chosen_col = chosen_col
        self.participants = []

class memoryBtn(discord.ui.Button):
    def __init__(self, emote, disabled=False):
        super().__init__(emoji=emote, style=discord.ButtonStyle.grey, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        game_state = active_memory_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        reward = int(interaction.message.embeds[0].description.split("`")[1])
        
        if interaction.user.id in game_state.participants:
            await interaction.response.send_message(
                "<:no:1036810470860013639> You have guessed once already. No second try!", ephemeral=True
            )
            return
            
        if str(self.emoji) == game_state.correct_emote:
            game_state.participants.append(interaction.user.id)
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description = f"**Which emote was in Column {game_state.chosen_col}?**\n\n{userAndTitle(interaction.user.id, interaction.guild.id)} guessed correctly and earned {MORA_EMOTE} `{text}`."
            
            for child in self.view.children:
                child.disabled = True
                if str(child.emoji) == str(self.emoji):
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

            await interaction.response.edit_message(
                content="", embed=embed, view=self.view
            )
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)
            del active_memory_games[interaction.message.id]
        else:
            await interaction.response.send_message("Wrong! <:no:1036810470860013639>", ephemeral=True)
            game_state.participants.append(interaction.user.id)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)


async def memoryGame(channel, client):
    reward = random.randint(5000, 7000)

    allEmojis = [ "😄", "😊", "😃", "😉", "😍", "😘", "😚", "😗", "😙", "😜", "😝", "😛", "🤑", "🤓", "😎", "🤗", "🙂", "🤔", "😐", "😑", "😶", "🙄", "😏", "😒", "🤥", "😌", "😔", "😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤧", "😢", "😭", "😰", "😥", "😓", "😈", "👿", "👹", "👺", "💩", "👻", "💀", "👽", "🤖", "🎃", "🎉", "🌟", "🔥", "❤️", "💙", "💜", "💛", "💚", "🖤", "💖", "💗", "💓", "💕", "💞", "💘", "💝", "💌", "💍", "💎", "🎀", "🌈", "👍", "👎", "👌", "✌", "🤞", "🤟", "🤘", "👏", "🙌", "🤲", "💪", "🙏", "👊", "🤛", "🤜", "💅", "👀", "👁", "👅", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐷", "🐸", "🐵", "🦄", "🐉", "🐲", "🐍", "🦎", "🐢", "🍕", "🌺", "📚", "⚽", "🎵", "🍔", "🍦", "🎂", "🎁", "🎈", "🎨", "🚀", "⌛", "💡", "🎮", "📷", "📱", "💻", "⭐", "🌙", "🍎", "🍉", "🍇", "🍓", "🥑", "🍩", "🥨", "🥗", "🍿", "🍰", "🚗", "🚕", "🚙", "🚌", "🚎", "🚜", "🚲", "✈", "🚁", "🛳", ]

    emojis = random.sample(allEmojis, 3)
    chosen_col = random.randint(0, 2)
    chosen_emote = emojis[chosen_col]
    chosen_col += 1

    embed = discord.Embed(
        title=f"Memory Game",
        description=f"Remember the following order of emotes. You will be asked to recall which column an emoji is from. **You can only guess once!**\n\nFirst to guess correctly wins {MORA_EMOTE} `{reward}`.",
        color=discord.Color.light_grey(),
    )
    for x in range(3):
        embed.add_field(name=f"Column {x+1}", value=f"`{emojis[x]}`", inline=True)

    msg = await channel.send(embed=embed)
    await asyncio.sleep(5)
    await msg.delete()

    view = View()
    random.shuffle(emojis)
    for emote in emojis:
        view.add_item(memoryBtn(str(emote)))

    game_message = await channel.send(
        embed=discord.Embed(
            title=f"Memory Game",
            description=f"Now, which of the following emote was in **Column {chosen_col}**? **You can only guess once!**\n\nFirst to guess correctly wins {MORA_EMOTE} `{reward}`.",
            color=discord.Color.light_grey(),
        ),
        view=view,
    )
    
    active_memory_games[game_message.id] = MemoryGameState(
        correct_emote=str(chosen_emote),
        chosen_col=chosen_col
    )


### --- TWO TRUTHS AND A LIE --- ###

class TwoTruthsState:
    def __init__(self, correct_emote, question_author_id, reward):
        self.correct_emote = correct_emote
        self.participants = []
        self.question_author_id = question_author_id
        self.reward = reward

class answerLieBtn(discord.ui.Button):
    def __init__(self, emote, disabled=False):
        super().__init__(emoji=emote, style=discord.ButtonStyle.grey, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        game_state = active_ttol_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        if str(interaction.user.id) == str(game_state.question_author_id):
            await interaction.response.send_message("You can't answer your own question smh", ephemeral=True)
            return

        if interaction.user.id in game_state.participants:
            await interaction.response.send_message("<:no:1036810470860013639> You have guessed once already. No second try!", ephemeral=True)
            return

        game_state.participants.append(interaction.user.id)
        
        if str(self.emoji) == str(game_state.correct_emote):
            embed = interaction.message.embeds[0]
            
            for child in self.view.children:
                child.disabled = True
                if str(child.emoji) == str(self.emoji):
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

            text, addedMora = await addMora(interaction.user.id, game_state.reward, interaction.channel.id, interaction.guild.id, interaction.client)
            
            embed.color = discord.Color.green()
            embed.description += f"\n\n🏆 {userAndTitle(interaction.user.id, interaction.guild.id)} chose {self.emoji} correctly and earned {MORA_EMOTE} `{text}`!"
            embed.set_footer(text="Now y'all know a little bit more about each other.")

            await interaction.response.edit_message(content="", embed=embed, view=self.view)
            
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)
            del active_ttol_games[interaction.message.id]
        else:
            await interaction.response.send_message("Wrong! <:no:1036810470860013639>", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)


class TwoTruthAndALieModal(discord.ui.Modal, title="Enter your two truths and one lie"):
    truth1 = discord.ui.TextInput(
        label="Truth #1",
        style=discord.TextStyle.short,
        placeholder="Enter a TRUE statement about yourself.",
        max_length=256
    )
    
    truth2 = discord.ui.TextInput(
        label="Truth #2",
        style=discord.TextStyle.short,
        placeholder="Enter another TRUE statement about yourself.",
        max_length=256
    )
    
    lie = discord.ui.TextInput(
        label="Lie",
        style=discord.TextStyle.short,
        placeholder="Enter a FALSE statement about yourself.",
        max_length=256
    )

    def __init__(self, reward):
        super().__init__()
        self.reward = reward 

    async def on_submit(self, interaction: discord.Interaction):
        statements = [
            str(self.truth1),
            str(self.truth2),
            str(self.lie)
        ]
        random.shuffle(statements)

        self.correct_emote = (
            "<:Anemo:1364310439781072946>" if statements[0] == str(self.lie) else
            "<:Pyro:1364310441949663274>" if statements[1] == str(self.lie) else
            "<:Electro:1364310441014071345>"
        )

        self.game_embed = discord.Embed(
            title="Two Truths, One Lie",
            description=(
                f'First to determine which of the following statement by '
                f'{userAndTitle(interaction.user.id, interaction.guild.id)} '
                f'is a lie wins {MORA_EMOTE} `{self.reward}`!\n\n'
                f'<:Anemo:1364310439781072946> "{statements[0]}"\n'
                f'<:Pyro:1364310441949663274> "{statements[1]}"\n'
                f'<:Electro:1364310441014071345> "{statements[2]}"'
            )
        )
        
        self.submission_interaction = interaction
        self.stop()


class TwoTruthAndALieButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Enter your two truths and one lie",
            emoji="🤫",
            style=discord.ButtonStyle.grey
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) not in interaction.message.embeds[0].description:
            await interaction.response.send_message("You can't click this button!", ephemeral=True)
            return

        original_embed = interaction.message.embeds[0]
        reward = int(original_embed.description.split("`")[1])
        msg = original_embed.description.split("\n\n")[0]

        if "entering their truths and lies..." not in original_embed.description:
            new_embed = discord.Embed(
                title=original_embed.title,
                description=f"{msg}\n\n> *{userAndTitle(interaction.user.id, interaction.guild.id)} is entering their truths and lies...*"
            )
            await interaction.message.edit(embed=new_embed)

        modal = TwoTruthAndALieModal(reward)
        await interaction.response.send_modal(modal)
        await modal.wait()

        await interaction.message.edit(
            embed=discord.Embed(
                title="Two Truths, One Lie",
                description=msg
            ),
            view=None
        )

        view = View()
        view.add_item(answerLieBtn("<:Anemo:1364310439781072946>"))
        view.add_item(answerLieBtn("<:Pyro:1364310441949663274>"))
        view.add_item(answerLieBtn("<:Electro:1364310441014071345>"))
        
        await modal.submission_interaction.response.send_message("<:yes:1036811164891480194> Success", ephemeral=True)
        
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)
        
        game_message = await interaction.channel.send(
            embed=modal.game_embed,
            view=view
        )

        active_ttol_games[game_message.id] = TwoTruthsState(
            correct_emote=modal.correct_emote,
            question_author_id=interaction.user.id,
            reward=reward
        )

        async def expire_game():
            await asyncio.sleep(300)
            if game_message.id in active_ttol_games:
                del active_ttol_games[game_message.id]
                await game_message.edit(view=None)
                
        asyncio.create_task(expire_game())


async def twoTruthsAndALie(channel, client):
    messages = [message async for message in channel.history(limit=10)]
    for msg in messages:
        user = msg.author
        if not user.bot: break

    view = View()
    view.add_item(TwoTruthAndALieButton())
    reward = random.randint(5000, 7000)
    
    await channel.send(
        embed=discord.Embed(
            title="Two Truths, One Lie",
            description=f"{userAndTitle(user.id, channel.guild.id)} will be entering their **three statements**. First to determine which statement is a lie wins {MORA_EMOTE} `{reward}`!",
            color=discord.Color.blurple()
        ),
        view=view
    )


### --- SPLIT OR STEAL --- ###

class SplitOrStealState:
    def __init__(self, player_a, player_b, reward):
        self.player_a = player_a
        self.player_b = player_b
        self.reward = reward
        self.choices = {player_a.id: None, player_b.id: None}
        self.message_id = None

class SplitButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Split", emoji="🤝", style=discord.ButtonStyle.green, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        game_state = active_split_or_steal_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        user = interaction.user
        if user.id not in game_state.choices:
            await interaction.response.send_message("You're not part of this game!", ephemeral=True)
            return

        if game_state.choices[user.id] is not None:
            await interaction.response.send_message("You can't change your selection!", ephemeral=True)
            return

        game_state.choices[user.id] = "Split"
        await self.process_choice(interaction, game_state)

    async def process_choice(self, interaction, game_state):
        if None in game_state.choices.values():
            await interaction.response.send_message(
                f"Waiting for {userAndTitle(game_state.player_b.id, interaction.guild.id) if interaction.user == game_state.player_a else userAndTitle(game_state.player_a.id, interaction.guild.id)} to choose...",
                ephemeral=True
            )
        else:
            await self.resolve_game(interaction, game_state)

    async def resolve_game(self, interaction, game_state):
        a_choice = game_state.choices[game_state.player_a.id]
        b_choice = game_state.choices[game_state.player_b.id]
        reward = game_state.reward
        await interaction.message.edit(view=None)

        if a_choice == "Split" and b_choice == "Split":
            split_reward = int(reward / 2)
            textA, addedMoraA = await addMora(game_state.player_a.id, split_reward, interaction.channel.id, interaction.guild.id, interaction.client)
            textB, addedMoraB = await addMora(game_state.player_b.id, split_reward, interaction.channel.id, interaction.guild.id, interaction.client)
            if addedMoraA == addedMoraB:
                result_embed = discord.Embed(
                    title="Split Success! 🎉",
                    description=f"Congrats, both {userAndTitle(game_state.player_a.id, interaction.guild.id)} and {userAndTitle(game_state.player_b.id, interaction.guild.id)} chose Split. You each won {MORA_EMOTE} `{textA}`!",
                    color=discord.Color.green()
                )
            else:
                a = userAndTitle(game_state.player_a.id, interaction.guild.id)
                b = userAndTitle(game_state.player_b.id, interaction.guild.id)
                result_embed = discord.Embed(
                    title="Split Success! 🎉",
                    description=f"Congrats, both {a} and {b} chose Split. {a} won {MORA_EMOTE} `{textA}` and {b} won {MORA_EMOTE} `{textB}`!",
                    color=discord.Color.green()
                )
            await interaction.message.reply(embed=result_embed)
            await update_quest(game_state.player_a.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMoraA}, interaction.client)
            await update_quest(game_state.player_b.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMoraB}, interaction.client)
        elif "Steal" in [a_choice, b_choice]:
            stealer = game_state.player_a if a_choice == "Steal" else game_state.player_b
            text, addedMora = await addMora(stealer.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            result_embed = discord.Embed(
                title="It's a Steal! 💰",
                description=f"{userAndTitle(stealer.id, interaction.guild.id)} stole all the money and won {MORA_EMOTE} `{text}`!",
                color=discord.Color.yellow()
            )
            await interaction.message.reply(embed=result_embed)
            await update_quest(stealer.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMora}, interaction.client)
            await update_quest(game_state.player_a.id if game_state.player_b.id == stealer.id else game_state.player_b.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

        del active_split_or_steal_games[interaction.message.id]

class StealButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Steal", emoji="🤑", style=discord.ButtonStyle.red, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        game_state = active_split_or_steal_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message("This game session has expired!", ephemeral=True)
            return

        user = interaction.user
        if user.id not in game_state.choices:
            await interaction.response.send_message("You're not part of this game!", ephemeral=True)
            return

        if game_state.choices[user.id] is not None:
            await interaction.response.send_message("You can't change your selection!", ephemeral=True)
            return

        game_state.choices[user.id] = "Steal"
        await self.process_choice(interaction, game_state)

    async def process_choice(self, interaction, game_state):
        if None in game_state.choices.values():
            await interaction.response.send_message(
                f"Waiting for {userAndTitle(game_state.player_b.id, interaction.guild.id) if interaction.user == game_state.player_a else userAndTitle(game_state.player_a.id, interaction.guild.id)} to choose...",
                ephemeral=True
            )
        else:
            await self.resolve_game(interaction, game_state)

    async def resolve_game(self, interaction, game_state):
        a_choice = game_state.choices[game_state.player_a.id]
        b_choice = game_state.choices[game_state.player_b.id]
        reward = game_state.reward
        await interaction.message.edit(view=None)
        
        if a_choice == "Steal" and b_choice == "Steal":
            result_embed = discord.Embed(
                title=random.choice(["Both Got Nothing :person_shrugging:", "Greed Leaves You With Nothing 💸"]),
                description=f"Both {userAndTitle(game_state.player_a.id, interaction.guild.id)} and {userAndTitle(game_state.player_b.id, interaction.guild.id)} chose Steal. No money for y'all.",
                color=discord.Color.red()
            )
            await interaction.message.reply(embed=result_embed)
            await update_quest(game_state.player_a.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)
            await update_quest(game_state.player_b.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

        elif "Steal" in [a_choice, b_choice]:
            stealer = game_state.player_a if a_choice == "Steal" else game_state.player_b
            text, addedMora = await addMora(stealer.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            result_embed = discord.Embed(
                title="It's a Steal! 💰",
                description=f"{userAndTitle(stealer.id, interaction.guild.id)} stole all the money and won {MORA_EMOTE} `{text}`!",
                color=discord.Color.yellow()
            )
            await interaction.message.reply(embed=result_embed)
            await update_quest(stealer.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMora}, interaction.client)
            await update_quest(game_state.player_a.id if game_state.player_b.id == stealer.id else game_state.player_b.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

        del active_split_or_steal_games[interaction.message.id]

async def splitOrSteal(channel, client):
    messages = [message async for message in channel.history(limit=10)]
    selected_players = []
    unique_ids = set()

    for message in messages:
        author = message.author
        if not author.bot and author.id not in unique_ids:
            selected_players.append(author)
            unique_ids.add(author.id)
            if len(selected_players) == 2:
                break

    if len(selected_players) < 2:
        return await channel.send(embed=discord.Embed(description="<:no:1036810470860013639> Not enough unique recent messaging users for the game."))

    a, b = selected_players[0], selected_players[1]
    reward = random.randint(10000, 14000)
    
    view = View()
    view.add_item(SplitButton())
    view.add_item(StealButton())

    game_message = await channel.send(
        content=f"{a.mention} vs {b.mention}",
        embed=discord.Embed(
            title=f"Choose to **Split or Steal** {MORA_EMOTE} `{reward}`!",
            color=0x7F00FF
        ),
        view=view
    )

    game_state = SplitOrStealState(a, b, reward)
    game_state.message_id = game_message.id
    active_split_or_steal_games[game_message.id] = game_state

    async def cleanup():
        await asyncio.sleep(300)
        if game_message.id in active_split_or_steal_games:
            del active_split_or_steal_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="🕒 This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(cleanup())


### --- ROCK PAPER SCISSORS --- ###

class RPSGameState:
    def __init__(self, player_a, player_b, reward):
        self.players = [player_a, player_b]
        self.choices = {player_a.id: None, player_b.id: None}
        self.reward = reward
        self.message_id = None

class RockButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Rock", emoji="🪨", style=discord.ButtonStyle.red, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        await process_rps_choice(interaction, "Rock")

class PaperButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Paper", emoji="📄", style=discord.ButtonStyle.green, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        await process_rps_choice(interaction, "Paper")

class ScissorsButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Scissors", emoji="✂️", style=discord.ButtonStyle.grey, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        await process_rps_choice(interaction, "Scissors")

async def process_rps_choice(interaction: discord.Interaction, choice: str):
    game_state = active_rps_games.get(interaction.message.id)
    if not game_state:
        await interaction.response.send_message("This game session has expired!", ephemeral=True)
        return

    player = interaction.user
    if player.id not in game_state.choices:
        await interaction.response.send_message("You're not part of this game!", ephemeral=True)
        return

    if game_state.choices[player.id] is not None:
        await interaction.response.send_message("You already made your choice!", ephemeral=True)
        return

    game_state.choices[player.id] = choice
    await interaction.response.defer()

    # Check if both players have chosen
    if None not in game_state.choices.values():
        await resolve_rps_game(interaction, game_state)

async def resolve_rps_game(interaction: discord.Interaction, game_state: RPSGameState):
    a_choice = game_state.choices[game_state.players[0].id]
    b_choice = game_state.choices[game_state.players[1].id]
    reward = game_state.reward

    results = {
        ("Rock", "Scissors"): game_state.players[0],
        ("Scissors", "Paper"): game_state.players[0],
        ("Paper", "Rock"): game_state.players[0],
        ("Scissors", "Rock"): game_state.players[1],
        ("Paper", "Scissors"): game_state.players[1],
        ("Rock", "Paper"): game_state.players[1],
    }

    rps_dict = {"Rock": "🪨", "Paper": "📄", "Scissors": "✂️"}
    a_emoji = rps_dict.get(a_choice, a_choice)
    b_emoji = rps_dict.get(b_choice, b_choice)
    await interaction.message.edit(view=None)

    if a_choice == b_choice:
        split_reward = int(reward / 7)
        message = "It's a tie! "
        count = 0
        for player in game_state.players:
            text, addedMora = await addMora(player.id, split_reward, interaction.channel.id, interaction.guild.id, interaction.client)
            await update_quest(player.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "earn_mora": addedMora}, interaction.client)
            message += f"{player.mention} earned {MORA_EMOTE} `{text}`{'!' if count == 1 else 'and '}"
            count += 1
        result_embed = discord.Embed(
            title=f"Both of you chose {a_emoji}!",
            description=message,
            color=discord.Color.yellow()
        )
        await interaction.message.reply(embed=result_embed)
    else:
        winner = results.get((a_choice, b_choice))
        text, addedMora = await addMora(winner.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
        result_embed = discord.Embed(
            title=f"",
            description=f"### {userAndTitle(winner.id, interaction.guild.id)} wins {MORA_EMOTE} `{text}`!\n-# {game_state.players[0].mention} chose {a_emoji}\n-# {game_state.players[1].mention} chose {b_emoji}",
            color=discord.Color.green()
        )
        await interaction.message.reply(embed=result_embed)
        for player in game_state.players:
            if player.id == winner.id:
                await update_quest(player.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMora}, interaction.client)
            else:
                await update_quest(player.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

    del active_rps_games[interaction.message.id]

async def rockPaperScissors(channel, client):
    messages = [message async for message in channel.history(limit=50)]
    selected_players = []
    unique_ids = set()

    for message in messages:
        author = message.author
        if not author.bot and author.id not in unique_ids:
            selected_players.append(author)
            unique_ids.add(author.id)
            if len(selected_players) == 2:
                break

    if len(selected_players) < 2:
        return await channel.send("<:no:1036810470860013639> Not enough players for the game.")

    a, b = selected_players[0], selected_players[1]
    reward = random.randint(5000, 7000)
    
    view = View()
    view.add_item(RockButton())
    view.add_item(PaperButton())
    view.add_item(ScissorsButton())

    game_message = await channel.send(
        content=f"{a.mention} vs {b.mention}",
        embed=discord.Embed(
            title=f"Choose **Rock, Paper, or Scissors!**",
            description=f"Winner gets {MORA_EMOTE} `{reward}`.",
            color=0xFF5349
        ),
        view=view
    )

    game_state = RPSGameState(a, b, reward)
    game_state.message_id = game_message.id
    active_rps_games[game_message.id] = game_state

    async def cleanup():
        await asyncio.sleep(300)
        if game_message.id in active_rps_games:
            del active_rps_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="⌛ This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(cleanup())


### DOUBLE IT AND GIVE IT TO THE NEXT PERSON ###

class ClaimButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Claim Reward",
            style=discord.ButtonStyle.red,
            custom_id="claim_reward_",
        )

    async def callback(self, interaction: discord.Interaction):
        view: UserSelectView = self.view

        if interaction.user.id != view.current_user.id:
            await interaction.response.send_message(
                "You can't claim the reward for someone else!", ephemeral=True
            )
            return

        view.participant_ids.add(interaction.user.id)
        view.winner_id = view.current_user.id
        text, addedMora = await addMora(view.current_user.id, view.reward, interaction.channel.id, interaction.guild.id, interaction.client)
        await interaction.message.delete()
        embed = discord.Embed(
            title="Double or Keep",
            description=f"{userAndTitle(view.current_user.id, interaction.guild.id)} has claimed the current reward of {MORA_EMOTE} `{text}`!",
            color=discord.Color.green(),
        )
        if view.previous_user:
            embed.set_footer(text=f"Last doubled by {view.previous_user.display_name}")
        await interaction.channel.send(embed=embed)
        
        for uid in view.participant_ids:
            quest_data = {"participate_minigames": 1}
            if uid == view.winner_id:
                quest_data["win_minigames"] = 1
                quest_data["earn_mora"] = addedMora
            await update_quest(uid, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)

class UserSelect(discord.ui.Select):
    def __init__(self, users: list[discord.Member], current_user: discord.Member):
        options = []
        if users is not None:
            options = [
                discord.SelectOption(label=user.display_name, value=str(user.id))
                for user in users
                if user.id != current_user.id  # 👈 only exclude for *this* round
            ]
        super().__init__(
            placeholder="Select a user",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="userSelectEvent",
        )

    async def callback(self, interaction: discord.Interaction):
        view: UserSelectView = self.view

        if interaction.user.id != view.current_user.id:
            await interaction.response.send_message(
                "You're not allowed to make this choice.", ephemeral=True
            )
            return

        selected_user_id = int(self.values[0])
        selected_user = await interaction.guild.fetch_member(selected_user_id)
        view.participant_ids.add(interaction.user.id)

        view.reward *= 2
        view.times_remaining -= 1

        embed = discord.Embed(
            title="Double or Keep",
            description=f"You can either keep {MORA_EMOTE} `{view.reward}`, or double it and give it to the next person **({view.times_remaining} times remaining)**.",
            color=0xADD8E6,
        )

        if view.previous_user:
            embed.set_footer(text=f"Last doubled by {view.current_user.display_name}")

        if view.times_remaining > 0:
            await interaction.message.delete()
            await interaction.channel.send(
                content=f"{selected_user.mention}",
                embed=embed,
                view=UserSelectView(
                    valid_users=view.valid_users,
                    reward=view.reward,
                    times_remaining=view.times_remaining,
                    current_user=selected_user,
                    previous_user=view.current_user,
                ),
            )
        else:
            view.winner_id = selected_user.id
            text, addedMora = await addMora(selected_user.id, view.reward, interaction.channel.id, interaction.guild.id, interaction.client)
            await interaction.message.delete()
            embed = discord.Embed(
                title="Double or Keep",
                description=f"{userAndTitle(selected_user.id, interaction.guild.id)} receives the final reward of {MORA_EMOTE} `{text}`!",
                color=discord.Color.green(),
            )
            if view.previous_user:
                embed.set_footer(
                    text=f"Last doubled by {view.current_user.display_name}"
                )
            await interaction.channel.send(embed=embed)
        
            for uid in view.participant_ids:
                quest_data = {"participate_minigames": 1}
                if uid == view.winner_id:
                    quest_data["win_minigames"] = 1
                    quest_data["earn_mora"] = addedMora
                await update_quest(uid, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)


class UserSelectView(discord.ui.View):
    def __init__(
        self,
        valid_users: list[discord.Member] = None,
        reward: int = None,
        times_remaining: int = None,
        current_user: discord.Member = None,
        previous_user: discord.Member = None,
        *,
        timeout=None,
    ):
        super().__init__(timeout=timeout)
        self.valid_users = valid_users
        self.reward = reward
        self.times_remaining = times_remaining
        self.current_user = current_user
        self.previous_user = previous_user
        self.participant_ids = set() 
        self.winner_id = None
        self.add_item(UserSelect(valid_users, current_user))
        self.add_item(ClaimButton())
        

async def doubleOrKeep(channel: discord.TextChannel, client: discord.Client):
    messages = [message async for message in channel.history(limit=20)]
    unique_ids = []
    user_list = []

    for message in messages:
        if message.author.id not in unique_ids and not message.author.bot:
            unique_ids.append(message.author.id)
            member = await channel.guild.fetch_member(message.author.id)
            if member:
                user_list.append(member)

    reward = random.randint(300, 500)
    first_user = user_list[0]
    
    if len(user_list) < 2:
        return await channel.send(embed=discord.Embed(description="<:no:1036810470860013639> Not enough unique recent messaging users for the game."))

    await channel.send(
        content=f"{first_user.mention}",
        embed=discord.Embed(
            title="Double or Keep",
            description=f"You can either keep {MORA_EMOTE} `{reward}`, or double it and give it to the next person **(5 times remaining)**.",
            color=0xADD8E6,
        ),
        view=UserSelectView(
            valid_users=user_list,
            reward=reward,
            times_remaining=5,
            current_user=first_user,
            previous_user=first_user,
        ),
    )

    
### MORA AUCTION HOUSE ###

class BidModal(discord.ui.Modal):
    def __init__(self, auction_view):
        super().__init__(title="Place Your Bid")
        self.auction_view = auction_view
        self.bid_amount = discord.ui.TextInput(
            label="Bid Amount (between 1000 and 15000)",
            placeholder="Enter your mora bid...",
            min_length=4,
            max_length=5
        )
        self.add_item(self.bid_amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id in self.auction_view.bids:
                embed = discord.Embed(
                    title="Already Bid! <:no:1036810470860013639>",
                    description="You can only bid **once** per auction!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            bid = int(self.bid_amount.value)
            if not 1000 <= bid <= 15000:
                raise ValueError
                
            user_data = db.reference(f"/Mora/{interaction.user.id}").get() or {}
            user_mora = get_guild_mora(user_data, str(interaction.guild.id))

            if bid > user_mora:
                embed = discord.Embed(
                    title="Bid Failed <:no:1036810470860013639>",
                    description=(
                        f"{MORA_EMOTE} **Insufficient Funds!**\n"
                        f"You only have: {MORA_EMOTE} {user_mora}"
                    ),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            self.auction_view.bids[interaction.user.id] = bid
            self.auction_view.participant_ids.add(interaction.user.id)
            embed = discord.Embed(
                title="Bid Placed <:yes:1036811164891480194>",
                description=f"You've bid {MORA_EMOTE} **{bid}**!\n*This will only be deducted if you win the box!*",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            embed = discord.Embed(
                description=f"📈 Total bids received: **{len(self.auction_view.bids)}**",
                color=0x2b2d31
            )
            await interaction.channel.send(embed=embed, delete_after=5)
            
        except ValueError:
            embed = discord.Embed(
                title="Invalid Bid <:no:1036810470860013639>",
                description="Please enter a number between **1000** and **15000**!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class AuctionView(discord.ui.View):
    def __init__(self, end_time):
        super().__init__(timeout=None)
        self.end_time = end_time
        self.message = None
        self.countdown_task = None
        self.bids = {}
        self.client_ref = None
        self.participant_ids = set()

    @discord.ui.button(label="Place Bid", style=discord.ButtonStyle.blurple, emoji="💰")
    async def bid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.bids:
            embed = discord.Embed(
                description="<:no:1036810470860013639> You've already bid!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_modal(BidModal(self))

    async def disable_button(self):
        """Disable button after exact 90 seconds"""
        now = await get_accurate_time(self.client_ref)
        remaining = self.end_time - now
        if remaining > 0:
            await asyncio.sleep(remaining)
        
        if self.message.id in active_auctions:
            del active_auctions[self.message.id]

        self.clear_items()
        embed = self.message.embeds[0]
        embed.description = embed.description.replace("ends", "ended")
        embed.description += "\n\n**Auction Closed!** 🔒"
        await self.message.edit(embed=embed, view=None)
        
async def get_accurate_time(client) -> float:
    """Get precise server time by sending a message to your time channel"""
    time_channel = client.get_channel(1026968305208131645)
    try:
        time_msg = await time_channel.send("⏱️ Auction time sync")
        accurate_time = time_msg.created_at.timestamp()
        await time_msg.delete()
        return accurate_time
    except Exception as e:
        print(f"Time sync failed: {e}")
        return time.time()
    
async def moraAuctionHouse(channel, client):
    start_time = await get_accurate_time(client)
    end_time = int(start_time) + 90
    
    embed = discord.Embed(
        title="Mora Auction House 🏛️",
        description=(
            f"A mysterious box worth anywhere **between {MORA_EMOTE} `5000` and `15000`** spawned! "
            f"**Closest bid UNDER the value of the box wins!** Auction ends <t:{end_time}:R>"
        ),
        color=0x3498db
    )
    
    view = AuctionView(end_time)
    view.client_ref = client
    view.message = await channel.send(embed=embed, view=view)
    active_auctions[view.message.id] = view
    view.countdown_task = asyncio.create_task(view.disable_button())
    
    remaining = end_time - int(await get_accurate_time(client))
    if remaining > 0:
        await asyncio.sleep(remaining)
    
    box_value = random.randint(5000, 15000)
    
    if not view.bids:
        await view.message.reply(embed=discord.Embed(description="<:no:1036810470860013639> Auction ended with no bids.", color=discord.Color.red()))
        return

    # Determine winner: Closest bid under (or equal to) box_value
    valid_bids = {uid: bid for uid, bid in view.bids.items() if bid <= box_value}
    
    if not valid_bids:
        result_embed = discord.Embed(
            title="Auction Failed! 🏚️",
            description=(
                f"**Box Value:** {MORA_EMOTE} `{box_value}`\n\n"
                "Everyone overbid! No one takes the box home."
            ),
            color=discord.Color.red()
        )
        await view.message.reply(embed=result_embed)
        # Update participation but no win
        for uid in view.participant_ids:
             await update_quest(uid, channel.guild.id, channel.id, {"participate_minigames": 1}, client)
        return

    # Winner is the highest bid among valid bids
    winner_id = max(valid_bids, key=valid_bids.get)
    winner_bid = valid_bids[winner_id]
    
    # User wins the box value, but paid the bid. Net profit = box_value - winner_bid.
    profit = box_value - winner_bid
    
    text, addedMora = await addMora(winner_id, profit, channel.id, channel.guild.id, client)
    
    result_embed = discord.Embed(
        title="Auction Results! 🎉",
        description=(
            f"### 🏆 Winner: <@{winner_id}>\n"
            f"**Box Value:** {MORA_EMOTE} `{box_value}`\n"
            f"**Winning Bid:** {MORA_EMOTE} `{winner_bid}`\n"
            f"**Net Profit:** {MORA_EMOTE} `{text}`"
        ),
        color=discord.Color.green()
    )
    
    await view.message.reply(embed=result_embed)
    
    for uid in view.participant_ids:
        quest_data = {"participate_minigames": 1}
        if uid == winner_id:
            quest_data["win_minigames"] = 1
            if addedMora > 0:
                quest_data["earn_mora"] = addedMora
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)


### --- MORA HEIST --- ###

async def moraHeist(channel, client):
    """Mora Heist minigame where users click a button to earn random Mora"""
    embed = discord.Embed(
        title=":new: Mora Heist! 💰 ",
        description=(
            "Click the button below as many times as you can in 20 seconds!\n"
            f"Each click earns you {MORA_EMOTE} `500-600` Mora!\n\n"
            "**Top participants will be shown here**"
        ),
        color=discord.Color.gold()
    )
    embed.add_field(
        name="Leaderboard (0 participants)",
        value="No participants yet",
        inline=False
    )
    embed.set_footer(text="Game ends in 20 seconds")
    
    view = discord.ui.View()
    view.user_data = {} 
    view.game_over = False 
    view.add_item(MoraHeistButton())
    message = await channel.send(embed=embed, view=view)
    
    async def end_game():
        await asyncio.sleep(20)
        view.game_over = True 
        
        embed = message.embeds[0]
        embed.title = "⏳ Mora Heist - Finished!"
        embed.description = "Time's up! Rewards distributed below."
        embed.color = discord.Color.green()
        embed.set_footer(text="")
        
        sorted_users = sorted(
            view.user_data.items(),
            key=lambda x: x[1]["mora_earned"],
            reverse=True
        )
        
        leaderboard = []
        for rank, (uid, data) in enumerate(sorted_users, 1):
            leaderboard.append(
                f"{rank}. <@{uid}>: {MORA_EMOTE} `{data['mora_earned']}` ({data['clicks']} clicks)"
            )
        
        embed.add_field(
            name="Final Results",
            value="\n".join(leaderboard) if leaderboard else "No participants",
            inline=False
        )
        
        await message.edit(embed=embed, view=None)
        
        summary = []
        if sorted_users:
            top_uid = sorted_users[0][0]

        for uid, data in view.user_data.items():
            text, addedMora = await addMora(uid, data["mora_earned"], channel.id, channel.guild.id, client)
            summary.append(f"-# <@{uid}>: {MORA_EMOTE} `{text}`")
            
            quest_data = {"participate_minigames": 1, "earn_mora": addedMora}
            if uid == top_uid:
                quest_data["win_minigames"] = 1
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                quest_data,
                client
            )
        
        reward_embed = discord.Embed(
            title="Mora Rewards Distributed",
            description="\n".join(summary),
            color=discord.Color.green()
        )
        await message.reply(embed=reward_embed)

    asyncio.create_task(end_game())

class MoraHeistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.grey, emoji="💰", label="Click to Steal")
        
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if getattr(view, 'game_over', False):
            return 

        # Initialize user_data if not exists
        if not hasattr(view, 'user_data'):
            view.user_data = {}
            
        user_id = interaction.user.id
        
        if user_id not in view.user_data:
            view.user_data[user_id] = {"clicks": 0, "mora_earned": 0}
        
        mora_gain = random.randint(500, 600)
        view.user_data[user_id]["clicks"] += 1
        view.user_data[user_id]["mora_earned"] += mora_gain
        
        embed = interaction.message.embeds[0]
        leaderboard = []
        
        sorted_users = sorted(
            view.user_data.items(),
            key=lambda x: x[1]["mora_earned"],
            reverse=True
        )[:10]  # Top 10
        
        for uid, data in sorted_users:
            leaderboard.append(
                f"-# <@{uid}>: {data['clicks']} clicks → {MORA_EMOTE} `{data['mora_earned']}`"
            )
        
        embed.set_field_at(
            0,
            name=f"Leaderboard ({len(view.user_data)} participants)",
            value="\n".join(leaderboard) if leaderboard else "No participants yet",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed)
    

### --- SIMPLE MATH GAME --- ###

class SimpleMathButton(discord.ui.Button):
    def __init__(self, label, is_correct):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(label))
        self.is_correct = is_correct

    async def callback(self, interaction: discord.Interaction):
        view: SimpleMathView = self.view
        if interaction.user.id in view.participants:
            await interaction.response.send_message("You have already guessed!", ephemeral=True)
            return

        view.participants.add(interaction.user.id)

        if self.is_correct:
            view.winner_id = interaction.user.id
            view.stop()
            for child in view.children:
                child.disabled = True
                if child == self:
                    child.style = discord.ButtonStyle.success
            
            reward = view.reward
            text, addedMora = await addMora(interaction.user.id, reward, interaction.channel.id, interaction.guild.id, view.client)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, view.client)

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            if "\nFirst to" in embed.description:
                embed.description = embed.description.split("\nFirst to")[0]
            
            embed.description += f"\n:nerd: <@{interaction.user.id}> solved it correctly and earned {MORA_EMOTE} `{text}`!"
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("That is incorrect!", ephemeral=True)


class SimpleMathView(discord.ui.View):
    def __init__(self, correct_val, options, reward, client):
        super().__init__(timeout=300)
        self.correct_val = correct_val
        self.reward = reward
        self.client = client
        self.winner_id = None
        self.participants = set()
        self.message = None

        random.shuffle(options)
        
        for val in options:
            is_correct = (val == correct_val)
            self.add_item(SimpleMathButton(val, is_correct))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

async def simpleMathGame(channel, client):
    import operator
    ops = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv
    }
    
    while True:
        nums = [random.randint(1, 20) for _ in range(3)]
        op_symbols = [random.choice(list(ops.keys())) for _ in range(2)]
        
        expr_str = f"{nums[0]} {op_symbols[0]} {nums[1]} {op_symbols[1]} {nums[2]}"
        try:
            res = eval(expr_str)
        except ZeroDivisionError:
            continue
            
        # If not integer
        if int(res) != res:
            continue
        if not (0 <= res <= 1000):
            continue
        
        ground_truth = int(res)
        break

    distractors = set()
    attempts = 0
    while len(distractors) < 4 and attempts < 50:
        op_symbols_d = [random.choice(list(ops.keys())) for _ in range(2)]
        expr_str_d = f"{nums[0]} {op_symbols_d[0]} {nums[1]} {op_symbols_d[1]} {nums[2]}"
        try:
            res_d = eval(expr_str_d)
            # if integer
            if int(res_d) == res_d:
                val_d = int(res_d)
                if val_d != ground_truth:
                    distractors.add(val_d)
        except ZeroDivisionError:
            pass
        attempts += 1
        
    while len(distractors) < 4:
        val_d = random.randint(0, 1000)
        if val_d != ground_truth:
            distractors.add(val_d)
            
    options = list(distractors) + [ground_truth]
    reward = random.randint(4000, 6000)
    
    view = SimpleMathView(ground_truth, options, reward, client)
    
    display_eq = f"{nums[0]} {op_symbols[0].replace('*', '×').replace('/', '÷')} {nums[1]} {op_symbols[1].replace('*', '×').replace('/', '÷')} {nums[2]}"
    
    embed = discord.Embed(
        title="Simple Math Game 🧮",
        description=f"Calculate the result:\n# {display_eq}\nFirst to answer correctly wins {MORA_EMOTE} `{reward}`. One try per person!",
        color=discord.Color.gold()
    )
    
    msg = await channel.send(embed=embed, view=view)
    view.message = msg


### --- TIC TAC TOK --- ###

class TicTacTokButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=x)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacTokView = self.view
        
        if interaction.user.id != view.current_player:
            if interaction.user.id in view.players.values():
                await interaction.response.send_message("It's not your turn!", ephemeral=True)
            else:
                await interaction.response.send_message("You are not part of this game!", ephemeral=True)
            return
            
        player_symbol = view.current_symbol
        self.disabled = True
        self.label = ""
        self.emoji = "<:cross:1458355882940170280>" if player_symbol == "X" else "<:circle:1458355853731168307>"
        self.style = discord.ButtonStyle.secondary
        
        view.board[self.x][self.y] = player_symbol
        
        winner_symbol = view.check_win()
        if winner_symbol:
            view.stop()
            view.winner_id = interaction.user.id
            
            winning_line = view.get_winning_line()
            for child in view.children:
                child.disabled = True
                if isinstance(child, TicTacTokButton):
                    if (child.x, child.y) in winning_line:
                        child.style = discord.ButtonStyle.success
            
            reward = view.reward
            text, addedMora = await addMora(view.winner_id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            await update_quest(view.winner_id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, interaction.client)

            winner_text = f"🎉 <@{view.winner_id}> won the Tik Tac Tok match and earned {MORA_EMOTE} `{text}`!"
            await interaction.response.edit_message(content=winner_text, view=view)
            return

        if all(cell is not None for row in view.board for cell in row):
            view.stop()
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content="It's a draw!", view=view)
            return

        if view.current_player == view.player1_id:
            view.current_player = view.player2_id
            view.current_symbol = "O"
        else:
            view.current_player = view.player1_id
            view.current_symbol = "X"
            
        content, embed = view.get_game_state()
        await interaction.response.edit_message(content=content, embed=embed, view=view)


class TicTacTokView(discord.ui.View):
    def __init__(self, player1, player2, reward):
        super().__init__(timeout=300)
        self.player1_id = player1.id
        self.player2_id = player2.id
        self.players = {player1.id: player1, player2.id: player2}
        self.reward = reward
        
        self.current_player = player1.id
        self.current_symbol = "X"
        
        self.board = [[None for _ in range(3)] for _ in range(3)]
        self.winner_id = None
        
        for r in range(3):
            for c in range(3):
                self.add_item(TicTacTokButton(r, c))

    def get_game_state(self):
        p1 = self.players[self.player1_id]
        p2 = self.players[self.player2_id]
        
        turn_msg = f"It's {'<:cross:1458355882940170280>' if self.current_symbol == 'X' else '<:circle:1458355853731168307>'} <@{self.current_player}>'s turn!"
        
        embed = discord.Embed(
            title="Tik Tac Tok", 
            description=f"First to match 3 symbols in a line wins {MORA_EMOTE} `{self.reward}`.\n\n<:cross:1458355882940170280> {p1.mention}\n<:circle:1458355853731168307> {p2.mention}",
            color=discord.Color.blurple()
        )
        
        return turn_msg, embed

    def check_win(self):
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] and self.board[i][0] is not None:
                return self.board[i][0]
        for i in range(3):
            if self.board[0][i] == self.board[1][i] == self.board[2][i] and self.board[0][i] is not None:
                return self.board[0][i]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return self.board[0][2]
        return None

    def get_winning_line(self):
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] and self.board[i][0] is not None:
                return [(i, 0), (i, 1), (i, 2)]
        for i in range(3):
            if self.board[0][i] == self.board[1][i] == self.board[2][i] and self.board[0][i] is not None:
                return [(0, i), (1, i), (2, i)]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return [(0, 0), (1, 1), (2, 2)]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return [(0, 2), (1, 1), (2, 0)]
        return []

async def ticTacTok(channel, client):
    players = []
    async for msg in channel.history(limit=50):
        if not msg.author.bot and msg.author not in players:
            players.append(msg.author)
            if len(players) == 2:
                break
                
    if len(players) < 2:
        return
        
    p1 = players[0]
    p2 = players[1]
    
    reward = random.randint(5000, 7000)
    view = TicTacTokView(p1, p2, reward)
    content, embed = view.get_game_state()
    await channel.send(content=content, embed=embed, view=view)


# --- DAILY MORA CHESTS --- #
    
class MoraChestView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, initial_tier, streak, clicks_remaining):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.tier = initial_tier
        self.streak = streak
        self.clicks_remaining = clicks_remaining
        self.completed = False
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.clicks_remaining > 0 and not self.completed:
            self.add_item(self.UpgradeButton())
        if not self.completed:
            self.add_item(self.ClaimButton())
            self.add_item(self.WhatIsItButton())

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your chest!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if not self.completed and self.message:
            self.cog.pending_chests.discard((self.user_id, self.guild_id))
            try:
                await self.message.edit(content=f"<@{self.user_id}>", view=PersistentChestInfoView(), embed=discord.Embed(
                    description=f"⏳ <@{self.user_id}> did not claim their chest in time. You can earn a new chest tomorrow!",
                    color=discord.Color.light_grey()
                ))
            except:
                pass

    class UpgradeButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Upgrade", style=discord.ButtonStyle.blurple, emoji="🔼")

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            if view.clicks_remaining <= 0:
                await interaction.response.send_message("No upgrades left!", ephemeral=True)
                return

            view.clicks_remaining -= 1
            new_tier = view.tier

            if view.tier == "Common" and random.random() < 0.30:
                new_tier = "Exquisite"
            elif view.tier == "Exquisite" and random.random() < 0.15:
                new_tier = "Precious"
            elif view.tier == "Precious" and random.random() < 0.20:
                new_tier = "Luxurious"

            success = new_tier != view.tier
            view.tier = new_tier

            tier_map = {
                "Common": 2500,
                "Exquisite": 7500,
                "Precious": 15000,
                "Luxurious": 30000
            }
            streak_total = min((view.streak * 100), 10000)
            total = tier_map[view.tier] + streak_total
            embed = interaction.message.embeds[0]
            embed.title = f"Daily Mora Chest 🎁 ({view.tier})"
            embed.description = (
                f"Upgrades left: `{view.clicks_remaining}`\n\n"
                f"**Tier:** {view.tier} Chest ({MORA_EMOTE} `{tier_map[view.tier]}`)\n"
                f"**Streak:** {'<a:streak:1371651844652273694>' if view.streak > 1 else ''} `{view.streak}` day{'s' if view.streak > 1 else ''} (`+{streak_total}` {MORA_EMOTE})\n"
                f"**Total:** {MORA_EMOTE} `{total}`"
            )
            embed.color = discord.Color.gold() if success else discord.Color.random()
            chest_icon = {
                "Common": "https://i.imgur.com/2kOfLSC.png",
                "Exquisite": "https://i.imgur.com/DBPQSAu.png",
                "Precious": "https://i.imgur.com/zxOlrCo.png",
                "Luxurious": "https://i.imgur.com/5nWwRdc.png"
            }
            embed.set_thumbnail(url=chest_icon[view.tier])

            view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=view)

    class ClaimButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Claim", style=discord.ButtonStyle.green, emoji="💰")

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            tier_map = {
                "Common": 2500,
                "Exquisite": 7500,
                "Precious": 15000,
                "Luxurious": 30000
            }
            streak_total = min((view.streak * 100), 10000)
            total = tier_map[view.tier] + streak_total

            ref = db.reference(f"/Mora Chest Streaks/{view.guild_id}/{view.user_id}")
            data = ref.get() or {}
            max_streak = data.get("max_streak", 0)

            new_max_streak = max(max_streak, view.streak)
            text, addedMora = await addMora(view.user_id, total, interaction.channel.id, view.guild_id, interaction.client)

            embed = discord.Embed(
                title=f"<a:moneydance:1227425759077859359> {view.tier} Chest Claimed! <a:moneydance:1227425759077859359>",
                description=f"{MORA_EMOTE} `{text}` is **added** to your inventory!",
                color=discord.Color.green()
            )

            embed.add_field(name="Chest Breakdown", value=f"-# Base: {MORA_EMOTE} `{tier_map[view.tier]}` \n-# Streak Bonus: {MORA_EMOTE} `{streak_total}` {'<a:streak:1371651844652273694>' if view.streak > 1 else ''}", inline=True)

            reset_unix = get_next_reset_unix()
            embed.add_field(
                name="Next Claim Available", 
                value=f"-# <t:{reset_unix}:f> (<t:{reset_unix}:R>)", 
                inline=True
            )
            
            ref_counts = db.reference(f"/Mora Chest Counts/{view.guild_id}/{view.user_id}")
            chest_counts = ref_counts.get() or {"Common": 0, "Exquisite": 0, "Precious": 0, "Luxurious": 0}
            chest_counts[view.tier] = chest_counts.get(view.tier, 0) + 1
            total_chests = sum(chest_counts.values())

            chest_info = (
                f"<a:common:1371641883121680465> `{chest_counts.get('Common', 0)}` <:blank:1036792889121980426>"
                f"<a:exquisite:1371641856344985620> `{chest_counts.get('Exquisite', 0)}` <:blank:1036792889121980426>"
                f"<a:precious:1371641871452995689> `{chest_counts.get('Precious', 0)}` <:blank:1036792889121980426>"
                f"<a:luxurious:1371641841338023976> `{chest_counts.get('Luxurious', 0)}`\n"
                f"📦 **Total:** `{total_chests}` <:blank:1036792889121980426>"
                f"<a:streak:1371651844652273694> `{view.streak}` day{'s' if view.streak > 1 else ''} <:blank:1036792889121980426>"
                f"<a:max_streak:1371655286049214672> `{new_max_streak}` day{'s' if new_max_streak > 1 else ''}"
            )
            embed.add_field(name="Your Inventory", value=chest_info, inline=False)
            chest_icon = {
                "Common": "https://i.imgur.com/2kOfLSC.png",
                "Exquisite": "https://i.imgur.com/DBPQSAu.png",
                "Precious": "https://i.imgur.com/zxOlrCo.png",
                "Luxurious": "https://i.imgur.com/5nWwRdc.png"
            }
            embed.set_thumbnail(url=chest_icon[view.tier])
            await interaction.response.edit_message(content=interaction.user.mention, embed=embed, view=PersistentChestInfoView())
            ref.set({
                "streak": view.streak,
                "max_streak": new_max_streak,
                "last_claimed": datetime.datetime.now(datetime.timezone.utc).date().isoformat()
            })
            ref_counts.set(chest_counts)
            view.cog.pending_chests.discard((view.user_id, view.guild_id))
            view.completed = True
            view.update_buttons()
            print(f"📦📦📦📦📦 {interaction.user.name} ({interaction.user.id}) has claimed a {view.tier} Chest in {interaction.guild.name} ({interaction.guild.id})")
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"collect_chests": 1, "earn_mora": addedMora}, interaction.client)

            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:PinkCelebrate:1204614140044386314> **Minigames Just Got a Fresh New Look!**\n"
                        "We’ve given **many minigames a visual revamp** with cleaner layouts, smoother flow, and an overall fresher feel. "
                        "Everything should now feel clearer and more fun to play! <:PaimonWow:1188553806456291489>\n"
                        "### <:YanfeiNote:1335644122253623458> **2 New Minigames Added**\n"
                        "<:dot:1357188726047899760> **Simple Math Game** — Quick mental math challenges to test your speed and accuracy 🧠\n"
                        "<:dot:1357188726047899760> **Tik Tac Tok** — The classic **tic-tac-toe**, but with a *punny twist* 😏\n\n"
                        "-# Jump in and try them out — your usual rewards, streaks, and progression all work just like before!"
                    ),
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
            return 

            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:CharlotteHeart:1191594476263702528> **Bot Development Isn't Cheap**\n"
                        f"<:reply:1036792837821435976> Consider purchasing the **Elite Track** for **{interaction.guild.name}** to unlock exclusive cosmetics and boosts, all while supporting ~~your favorite bot~~ Fischl! ***[:yum: Click the link and select {interaction.guild.name} to view and purchase the Elite Track!](https://fischl.app/profile)***"
                    ),
                    color=discord.Color.gold()
                ),
                ephemeral=True,
                view=View().add_item(Button(label="Your Support Would Mean A Lot!", url="https://fischl.app/profile", style=discord.ButtonStyle.link))
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:YanfeiNote:1335644122253623458> **How do you even check your staff past experiences?**\n"
                        "Introducing **ServerCV** — a **verified staff experience resume** applicants can share when applying for roles. "
                        "It helps servers instantly spot real experience and reduce fake claims. <:PaimonWow:1188553806456291489>\n\n"
                        "<:dot:1357188726047899760> Clean, trusted resume link (example: https://servercv.com/u/ian)\n"
                        "<:dot:1357188726047899760> No setup required for your server. Just endorse your staff members!\n"
                        "### <:CharlotteHeart:1191594476263702528> **Check us out for more info:** https://servercv.com/"
                    ),
                    color=discord.Color.blurple()
                ).set_footer(text="Share this to your server owner or staff members!"),
                ephemeral=True,
                view=View().add_item(Button(label="Try ServerCV", url="https://servercv.com/", style=discord.ButtonStyle.link))
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:HuTaoEvil:1350630212617896120> **Free Mora & Summons Every day?!**\n"
                        "You can do just that for each server that has minigame enabled at **https://fischl.app/profile**! <:PaimonWow:1188553806456291489>\n\n"
                        "<:dot:1357188726047899760>Play a **random daily minigame** on the website to earn **bonus Mora** + **1 extra summon** each day\n"
                        "<:dot:1357188726047899760>Each challenge refreshes **daily at 00:00 UTC** (like daily chests)!\n\n"
                        "-# Once you finish, your rewards will **automatically be credited** to your </mora:1339721187953082543> inventory. <:AyakaShine:1191592023946432522>"
                    ),
                    color=discord.Color.gold()
                ).set_footer(text="Why are we doing this? We just launched our brand new profile website and dashboard! Check them out!"),
                ephemeral=True,
                view=View().add_item(Button(label="Complete your daily challenge", url="https://fischl.app/profile", style=discord.ButtonStyle.link))
            ) 
        
            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:CharlotteHeart:1191594476263702528> **Introducing the Fischl Profile Website!**\n"
                        "You can now access **your Fischl profile** directly from your browser at **https://fischl.app/profile**! <:PaimonWow:1188553806456291489>\n\n"
                        f"<:dot:1357188726047899760>View your **Mora inventory**, **Elite status**, and **track progress** — everything you see in </mora:1339721187953082543>.\n"
                        f"<:dot:1357188726047899760>**Purchase Elite Track instantly!** No more waiting for manual activation — it’ll **unlock automatically** right after purchase.\n"
                        "### <:PinkCelebrate:1204614140044386314> Still only **$0.99/month** *(or $2.97 per 3-month season!)*\n"
                        f"<:reply:1036792837821435976> ***[View Your Profile & Become Elite Now](https://fischl.app/profile)***"
                    ),
                    color=discord.Color.random()
                ).set_thumbnail(url="https://media.discordapp.net/attachments/1106727534479032341/1381827880488669327/elite_track.png"),
                ephemeral=True,
                view=View().add_item(Button(label="View Your Profile", url="https://fischl.app/profile", style=discord.ButtonStyle.link))
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:YanfeiNote:1335644122253623458> **Prestige Reset Notice**\n"
                        "Due to a **season reset malfunction**, all players’ **Prestige levels were accidentally reset to 0**, even though Prestige is meant to be **permanent**.\n\n"
                        "<:dot:1357188726047899760>Players who **completed all 31 tiers in Season 1’s track** should have **`+1 Prestige`**.\n"
                        "<:dot:1357188726047899760>Those who **purchased the Elite Track** *and* reached its end should receive an **additional `+1 Prestige`** *(total of 2)*.\n"
                        "### <:CharlotteHeart:1191594476263702528> **How to Restore Your Prestige**\n"
                        f"If you believe you’re affected by this issue:\n"
                        f"<:reply:1036792837821435976> Join our [support server](https://discord.gg/BXkc8CC4uJ) and create a **support ticket**\n"
                        f"<:reply:1036792837821435976> **Forward a message by Fischl** showing your </mora:1339721187953082543> command as proof of your Season 1 track progress\n"
                        f"<:reply:1036792837821435976> If you cannot find proof, **please provide any relevant information about your progress**\n\n"
                        "-# Your Prestige will then be **restored manually** after verification. Thank you for your understanding and patience!"
                    ),
                    color=discord.Color.red()
                ).set_thumbnail(url="https://i.imgur.com/Lhyd7HI.png"),
                ephemeral=True
            )
        
            if datetime.datetime.now(datetime.timezone.utc).month == 10:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="",
                        description=(
                            "## <:MelonBread_KeqingNote:1342924552392671254> **Season 2 Starts Now!**\n"
                            f"> The new season **started <t:1759276801:R>**! All seasonal boosts and cosmetics have been **reset**.\n\n"
                            f"- <:YanfeiNote:1335644122253623458> We've capped chest streak earnings at {MORA_EMOTE} `10,000` (if you reach >100 days on your streak)\n"
                            f"- <:AyakaShine:1191592023946432522> We also added a </preview:1422386451705888850> command, allowing you to check out the **new profile frames**!\n\n"
                            "-# *The XP needed to get to the end of the season track is **decreased by half** (from 90K to 55K XP)! <:CharlotteHeart:1191594476263702528> "
                            "Visit https://fischl.app/track/season_2/index.html and consider **purchasing the Elite Track** to support Fischl!*\n"
                        ),
                        color=discord.Color.random()
                    ),
                    ephemeral=True
                )

            if sigils_earned:
                embed = discord.Embed(
                    title=f"What Are Lunar Sigils? <:AlbedoQuestion:1191574408544923799>",
                    description="-# Earn <a:sigils:1402736987902967850> **Sigils** by chatting actively and use them to enter giveaways!",
                    color=discord.Color.purple()
                )
                embed.add_field(
                    name="<:NingguangStonks:1265470501707321344> Chat ➜ Sigils",
                    value="-# Start **meaningful conversations** to passively earn </sigils:1402740034603319569> in batches!",
                    inline=True
                )
                embed.add_field(
                    name=f"<:CharlotteHeart:1191594476263702528> Sigils ➜ Giveaways",
                    value="-# Spend your Sigils to **enter giveaways** and increase your chances with extra entries!",
                    inline=True
                )
                embed.add_field(
                    name="<:MelonBread_KeqingNote:1342924552392671254> Boost Your Earnings",
                    value="-# **Special roles** can get increased daily Sigil caps for more rewards!",
                    inline=True
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title=f"A new feature has just arrived <:AlbedoQuestion:1191574408544923799>",
                    description="-# Ask your server admins to enable this system via </giveaway enable:1402740034603319570>.",
                    color=discord.Color.purple()
                )
                embed.add_field(
                    name="<:NingguangStonks:1265470501707321344> Chat ➜ Sigils",
                    value="-# Start **meaningful conversations** to passively earn <a:sigils:1402736987902967850> </sigils:1402740034603319569> in batches!",
                    inline=True
                )
                embed.add_field(
                    name=f"<:CharlotteHeart:1191594476263702528> Sigils ➜ Giveaways",
                    value="-# Spend your Sigils to **enter giveaways** and increase your chances with extra entries!",
                    inline=True
                )
                embed.add_field(
                    name="<:MelonBread_KeqingNote:1342924552392671254> Boost Your Earnings",
                    value="-# **Special roles** can get increased daily Sigil caps for more rewards!",
                    inline=True
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            embed = discord.Embed(
                title="",
                description=(
                    "## <:YanfeiNote:1335644122253623458> **Chest System Just Got Smarter!**\n"
                    "We’ve improved how **message-based chest unlocking** works to make things fairer and less abusable for everyone. Here’s what’s changed:\n\n"
                    "<:dot:1357188726047899760>Messages must now meet **minimum quality** (no spam, repeats, or filler)\n"
                    "<:dot:1357188726047899760>Added a **cooldown** between countable messages\n"
                    "<:dot:1357188726047899760>Anywhere between **4 to 6** effortful messages are needed for chest to spawn\n"
                    "### <:PinkCelebrate:1204614140044386314> All your **upgrades, streaks, and chest rewards** stay the same!\n"
                    f"<:reply:1036792837821435976> ***[Unlock the Elite Track](https://fischlbot.web.app/track/season_1)***"
                ),
                color=discord.Color.teal()
            )
            embed.set_footer(text="Thank you for helping keep things fair for everyone! 🫶")
            await interaction.followup.send(embed=embed, ephemeral=True)

            embed=discord.Embed(
                    title="",
                    description=(
                        "## <a:moneydance:1227425759077859359> Did you know...?\n"
                        "Upgrade to **Elite Track** and get more than **DOUBLE** the rewards of the free version! Here's what you're missing: <:KokoWow:1191868161851666583>\n\n"
                        "<:dot:1357188726047899760>**Extra `60%` Mora Boosts** (Free: `+50%` only)\n"
                        "<:dot:1357188726047899760>**Extra `18` Minigame Summons** (Free: `+9` only)\n"
                        "<:dot:1357188726047899760>**Extra `2` Chest Upgrades** (Free: `+3` only)\n"
                        "<:dot:1357188726047899760>**4+ Exclusive Animated Cosmetics**\n"
                        "<:dot:1357188726047899760>Personalize your </mora:1339721187953082543> inventory with **custom colors**\n"
                        "### <:PinkCelebrate:1204614140044386314> **All this and more for less than USD $1/month!**\n"
                        f"<:reply:1036792837821435976> ***[Compare Tracks / Purchase Now](https://fischlbot.web.app/track/season_1)***"
                    ),
                    color=0xfa0af6
                ).set_thumbnail(url="https://media.discordapp.net/attachments/1106727534479032341/1381827880488669327/elite_track.png")
            embed.set_footer(text="Your purchase will help support bot development tremendously! 🙏")
            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )
            await interaction.followup.send(embed=discord.Embed(title="", description="## <:PaimonWow:1188553806456291489> NEW FEATURE ALERT! <:YanfeiNote:1335644122253623458>\nYou can now earn **XP** by **completing quests** or buying items! Unlock **Mora boosts**, **additional chest upgrades**, **Mora gifting**, exclusive cosmetics and titles in the new Progression Track! <:HuTaoEvil:1350630212617896120> \n### <:PinkCelebrate:1204614140044386314> **Use </mora:1339721187953082543> to check your daily quests & free rewards now!** \n-# **You can find the [full update release notes here!](https://fischlbot.web.app/track/update/)** <:MelonBread_KeqingNote:1342924552392671254> ", color=discord.Color.gold()), ephemeral=True)
            frequency = enabledChannels[interaction.channel.id]
            await interaction.followup.send(
                embed=discord.Embed(
                    title="",
                    description=(
                        "## <:MelonBread_KeqingNote:1342924552392671254> **1 Day Until the Massive Update!**\n"
                        f"> The first season **starts <t:1751328000:R>**! When you claim your chest tomorrow, you’ll see everything you need to know to **maximize your rewards**.\n\n"
                        f"<:AyakaShine:1191592023946432522> Hang out and chat - minigames are still the best way to earn **tons of {MORA_EMOTE}**!\n"
                        "-# **Feeling curious?** Sneak a peek at ||the [update preview](https://fischlbot.web.app/track/update/) and the new [season track](https://fischlbot.web.app/track/season_1/) :eyes:||"
                    ),
                    color=discord.Color.random()
                ),
                ephemeral=True
            )
            
    class WhatIsItButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="What is this?", style=discord.ButtonStyle.secondary, emoji="❓")

        async def callback(self, interaction: discord.Interaction):
            reset_unix = get_next_reset_unix()
            embed = discord.Embed(
                description=f"{MORA_CHEST_DESCRIPTION}\n\n***Next reset at** <t:{reset_unix}:f> (<t:{reset_unix}:R>)*",
                color=discord.Color.random()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
class FeedbackModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Game Feedback Survey", timeout=600)
        
        self.question1 = discord.ui.TextInput(
            label="1. Do you find track & quests confusing?",
            placeholder="The text, layout, delivery...",
            required=True
        )
        
        self.question2 = discord.ui.TextInput(
            label="2. Are you aware of seasonal boosts?",
            placeholder="Tax reduction, chest upgrades, summons...",
            required=True
        )

        self.question3 = discord.ui.TextInput(
            label="3. How do you customize your inventory?",
            placeholder="Do you upload custom backgrounds, equip profile frames...",
            required=True
        )

        self.question4 = discord.ui.TextInput(
            label="4. Is the Elite Track worth it?",
            placeholder="Would you pay for it? What's missing?",
            required=True
        )
        
        self.question5 = discord.ui.TextInput(
            label="5. Any new quests/minigame ideas?",
            style=discord.TextStyle.paragraph,
            placeholder="Gambling, more inventory upgrades...",
            required=True
        )
        
        self.additional_comments = discord.ui.TextInput(
            label="6. Any other suggestions?",
            style=discord.TextStyle.paragraph,
            placeholder="Any other improvements or feedback...",
            required=False
        )

        self.add_item(self.question1)
        self.add_item(self.question2)
        self.add_item(self.question3)
        self.add_item(self.question4)
        self.add_item(self.question5)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎮 New Game Feedback Received", color=0x00ff00)
        
        feedback_data = {
            "🏮 Do you find track & quests confusing?": self.question1.value,
            "⏱ Are you aware of seasonal boosts?": self.question2.value,
            "💡 How do you customize your inventory?": self.question3.value,
            "💎 Is the Elite Track worth it?": self.question4.value,
            "⚠️ Any new quests/minigame ideas?": self.question5.value,
        }
        
        for name, value in feedback_data.items():
            embed.add_field(name=name, value=value, inline=False)
            
        embed.set_footer(text=f"Submitted by {interaction.user} in {interaction.user.guild} | ID: {interaction.user.id}")

        try:
            feedback_target = await interaction.client.fetch_user(692254240290242601)
            await feedback_target.send(embed=embed)
            await interaction.response.send_message(
                "📬 Thank you for your feedback! Your responses have been recorded. \n<:yes:1036811164891480194> You can always resubmit this form as long as it's available.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                "❌ Failed to submit feedback. Please try again later.",
                ephemeral=True
            )
            
class PersistentChestInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.profile_button = Button(label="Earn Daily Mora & Summons", style=discord.ButtonStyle.link, url=f"https://fischl.app/profile", emoji="<a:legacy:1345876714240213073>")
        self.add_item(self.profile_button)

    @discord.ui.button(
        label="What is this?",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_chest_info_view",
        emoji="❓",
    )
    async def persistentChestInfoView(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        reset_unix = get_next_reset_unix()
        embed = discord.Embed(
            description=f"{MORA_CHEST_DESCRIPTION}\n\n***Next reset at** <t:{reset_unix}:f> (<t:{reset_unix}:R>)*",
            color=discord.Color.random()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_chest_delete",
        emoji="<a:delete:1372423674640207882>",
    )
    async def persistent_chest_delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content:
            await interaction.response.send_message("❌ This isn't your chest!", ephemeral=True)
        else:
            await interaction.message.delete()
    
    """@discord.ui.button(
        label="Submit Feedback",
        style=discord.ButtonStyle.green,
        custom_id="persistent_feedback_button",
        emoji="📝"
    )
    async def feedback_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FeedbackModal())"""
        
class FeedbackView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Submit Feedback",
        style=discord.ButtonStyle.green,
        custom_id="feedback_button",
        emoji="📝"
    )
    async def feedback_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FeedbackModal())

DATA_FILE = "commands/Events/mora_chest_data.json"

def load_counts():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
            return {
                tuple(map(int, k.split("|"))): (v[0], datetime.datetime.fromisoformat(v[1]))
                for k, v in raw.items()
            }
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_counts(counts):
    with open(DATA_FILE, "w") as f:
        json.dump({
            f"{k[0]}|{k[1]}": [v[0], v[1].isoformat()]
            for k, v in counts.items()
        }, f)

class DailyChestSystem:
    def __init__(self):
        self.user_states = {} 
        self.cooldown = 5 
        self.claimed_today = set()
        
    def is_effortful_message(self, content: str, last_content: str) -> bool:
        content = content.strip()
        
        if len(content) < 7:
            return False
            
        words = content.lower().split()
        if len(set(words)) <= 2 and len(words) > 5:
            return False
            
        if re.search(r"(.)\1{4,}", content):
            return False
            
        if last_content:
            similarity = SequenceMatcher(None, last_content, content).ratio()
            if similarity > 0.9:
                return False
                
        return True

    async def process_message(self, message, cog):
        if message.author.bot:
            return
            
        if message.channel.id not in enabledChannels:
            return
            
        user_id = message.author.id
        guild_id = message.guild.id
        key = (guild_id, user_id)
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        
        if key in self.claimed_today:
            return
            
        if key not in self.user_states or self.user_states[key]['current_date'] != today:
            db_state = self.load_from_db(guild_id, user_id)
            if db_state and db_state['current_date'] == today:
                self.user_states[key] = db_state
                if db_state['chest_triggered']:
                    self.claimed_today.add(key)
                    return
            else:
                self.user_states[key] = {
                    'message_count': 0,
                    'last_time': 0,
                    'last_content': '',
                    'current_date': today,
                    'threshold': random.randint(4, 6),
                    'chest_triggered': False
                }
        
        state = self.user_states[key]
        current_time = time.time()
        
        if current_time - state['last_time'] < self.cooldown:
            return
            
        if not self.is_effortful_message(message.content, state['last_content']):
            return
            
        state['message_count'] += 1
        state['last_time'] = current_time
        state['last_content'] = message.content
        
        if not state['chest_triggered']:
            self.save_to_db(guild_id, user_id, state)
        
        if (not state['chest_triggered'] and 
            state['message_count'] >= state['threshold'] and
            (user_id, guild_id) not in cog.pending_chests):
            
            state['chest_triggered'] = True
            self.claimed_today.add(key)
            self.save_to_db(guild_id, user_id, state)
            await self.trigger_chest(message, cog)

    def load_from_db(self, guild_id, user_id):
        ref = db.reference(f"/Daily Chest Progress/{guild_id}/{user_id}")
        return ref.get()
        
    def save_to_db(self, guild_id, user_id, state):
        ref = db.reference(f"/Daily Chest Progress/{guild_id}/{user_id}")
        ref.set(state)
        
    async def reset_daily_states(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        if now.hour == 0 and now.minute == 0:
            self.claimed_today.clear()
            for key in list(self.user_states.keys()):
                del self.user_states[key]
        
    async def trigger_chest(self, message, cog):
        user_id = message.author.id
        guild_id = message.guild.id
        key = (user_id, guild_id)
        
        ref = db.reference(f"/Mora Chest Streaks/{guild_id}/{user_id}")
        data = ref.get() or {}
        last_claimed = datetime.datetime.fromisoformat(data["last_claimed"]).date() if "last_claimed" in data else None
        current_streak = data.get("streak", 0)

        today = datetime.datetime.now(datetime.timezone.utc).date()
        new_streak = current_streak + 1 if last_claimed and (today - last_claimed).days == 1 else 1
        
        stats_ref = db.reference(f"/User Events Stats/{guild_id}/{user_id}")
        stats = stats_ref.get() or {}
        clicks_remaining = stats.get("chest_upgrades", 4)

        view = MoraChestView(cog, user_id, guild_id, "Common", new_streak, clicks_remaining)
        embed = discord.Embed(
            title="Daily Mora Chest Unlocked! <a:tada:1227425729654820885>",
            description=(
                f"**Common Chest** - *{MORA_EMOTE} `2500`*\n"
                f"**Click to upgrade** (`{clicks_remaining}` chances left)\n"
                f"**Messages counted:** `{self.user_states[(guild_id, user_id)]['message_count']}`\n"
                f"**Streak:** {'<a:streak:1371651844652273694>' if new_streak > 1 else ''} `{new_streak}` day{'s' if new_streak > 1 else ''} ({MORA_EMOTE} `+{new_streak * 100}`)"
            ),
            color=discord.Color.random()
        )
        embed.set_thumbnail(url="https://i.imgur.com/2kOfLSC.png")
        embed.set_footer(text="A chest spawns after sending 4-7 effortful messages in minigame channels each day")
        chest_msg = await message.channel.send(
            content=f"{message.author.mention}, claim this chest <t:{int(time.time()) + 300}:R>!",
            embed=embed,
            view=view
        )
        print(f"⛔️⛔️⛔️⛔️⛔️ {message.author.name} ({message.author.id}) is currently claiming a chest in {message.guild.name} ({message.guild.id})")
        view.message = chest_msg
        cog.pending_chests.add(key)
        
class TheEventItself(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self.pending_chests = set()
        self.chest_system = DailyChestSystem()
        self.daily_reset.start()
    
    @tasks.loop(minutes=1)
    async def daily_reset(self):
        await self.chest_system.reset_daily_states()
        
    @daily_reset.before_loop
    async def before_daily_reset(self):
        await self.client.wait_until_ready()
        now = datetime.datetime.now(datetime.timezone.utc)
        next_minute = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
        await asyncio.sleep((next_minute - now).total_seconds())

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user or message.author.bot == True:
            return

        if "-addMora" in message.content:
            if message.author.id not in [692254240290242601, 1251949796210638989, 885217186468229140]:
                return await message.add_reaction("<:no:1036810470860013639>")
            else:
                uid = int(
                    message.content.split(" ")[1].replace("<@", "").replace(">", "")
                )
                mora = int(message.content.split(" ")[2])

                ts = str(int(time.time()))
                path = f"/Mora/{uid}/{message.guild.id}/{10}/{ts}"
                db.reference(path).set(mora)

                await message.reply(
                    f"Added exactly {MORA_EMOTE} `{mora:,}` to <@{uid}>'s inventory. \n-# This is not boosted and doesn't count towards quest progression."
                )
                
        if message.content.startswith('-addXP'):
            if message.author.id != 692254240290242601: 
                return await message.add_reaction("<:no:1036810470860013639>")
            try:
                parts = message.content.split()
                user = message.mentions[0] if message.mentions else None
                if not user:
                    await message.channel.send("Mention a user!")
                    return
                xp_amount = int(parts[2])
                tier, old_xp, new_xp = await add_xp(user.id, message.guild.id, xp_amount, self.client)
                
                await check_tier_rewards(
                    guild_id=message.guild.id,
                    user_id=user.id,
                    old_xp=old_xp,
                    new_xp=new_xp,
                    channel=message.channel,
                    client=self.client
                )
                await message.channel.send(f"Added `{xp_amount}` XP to {user.mention}. Reached tier `{tier}`!")
            except Exception as e:
                await message.channel.send(f"Error: {e}")

        check_and_reload()
        
        if message.channel.id in enabledChannels:
            if message.author.id == 1006694571167719527:
                return
            
            await self.chest_system.process_message(message, self)
            
            frequency = enabledChannels[message.channel.id]

            if message.id % frequency == 0:
                originalList = get_minigame_list(message.channel.id)
                okForEvent = True
                messages = [
                    message
                    async for message in message.channel.history(limit=frequency)
                ]

                for msg in messages:
                    try:
                        if len(msg.embeds) > 0 and msg.author.id == self.client.user.id:
                            okForEvent = False
                    except Exception:
                        pass

                if okForEvent and originalList is not None:
                    channel_id = message.channel.id

                    if channel_id in active_channels:
                        return
                    active_channels[channel_id] = True
                    
                    text = random.choice([
                        "Send 4-6 effortful messages a day to earn daily mora chests 📦",
                        "Reach </milestones:1380247962390888578> to earn titles/roles! Check it out! 💎",
                        "Use </customize:1339721187953082544> to add a custom inventory background image & pin titles 🌆",
                        "Hug your favorite person(s) using </hug:1379632715707715594> 🫂",
                        "Get FREE mora & minigame summons at [by **playing daily games on the website**](https://fischl.app/profile) 📈",
                        "Admins can edit event settings & view purchase logs at **[Fischl Dashboard](https://fischl.app/dashboard) ⚙️**",
                    ])
                    
                    embed = discord.Embed(
                        description=f"Since chat is relatively active, I'm dropping a random event in `3 seconds`.\n-# ***Tip:** {text}*",
                        color=discord.Color.orange(),
                    )

                    view = View()
                    view.add_item(Button(
                        label="Earn Free Mora & Summons",
                        style=discord.ButtonStyle.link,
                        url="https://fischl.app/profile",
                        row=1,
                        emoji="<a:legacy:1345876714240213073>"
                    ))
                    # view.add_item(Button(
                    #     label="Invite",
                    #     style=discord.ButtonStyle.link,
                    #     url="https://discord.com/api/oauth2/authorize?client_id=732422232273584198",
                    #     row=1,
                    #     emoji="<a:robot:1366940845697400935>"
                    # ))
                    # view.add_item(Button(
                    #     label="Support",
                    #     style=discord.ButtonStyle.link,
                    #     url="https://discord.gg/kaycd3fxHh",
                    #     row=1,
                    #     emoji="<a:join:1366940843088543775>"
                    # ))

                    await message.channel.send(embed=embed, view=view)
                    
                    events = [
                        defeatTheBoss,
                        quicktype,
                        eggWalk,
                        matchThePFP,
                        splitOrSteal,
                        reverseQuicktype,
                        pickUpIceCream,
                        pickUpTheWatermelon,
                        guessTheNumber,
                        memoryGame,
                        whoSaidIt,
                        unscrambleWords,
                        twoTruthsAndALie,
                        countingCurrency,
                        rockPaperScissors,
                        rollADice,
                        guessTheVoiceline,
                        genshinEmojiRiddle,
                        hsrEmojiRiddle,
                        doubleOrKeep,
                        knowYourMembers,
                        hangmanGame,
                        moraAuctionHouse,
                        moraHeist,
                        simpleMathGame,
                        ticTacTok
                    ]
                    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                    letter_to_event = dict(zip(letters, events))
                    eligible_events = [
                        letter_to_event[letter]
                        for letter in originalList
                        if letter in letter_to_event
                    ]

                    await asyncio.sleep(2.4)

                    try:
                        event = random.choice(eligible_events)
                        print(f"<{event.__name__}>: #{message.channel.name} ({message.channel.id}) in {message.guild.name} ({message.guild.id})")
                        await event(message.channel, self.client)
                    except Exception as e:
                        import traceback
                        tb_str = traceback.format_exc()
                        print("Event crashed:\n", tb_str)
                        embed = discord.Embed(description=f"Event crashed: `{e}`")
                        embed.set_footer(text="Error has been logged and developer has been notified.")
                        msg = await message.channel.send(embed=embed)
                        ian = await self.client.fetch_user(692254240290242601)
                        await ian.send(f"Event crashed: {msg.jump_url}")
                    finally:
                        active_channels.pop(channel_id, None)
                        print("✅")


class Summon(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.minigame_mapping = {
            "defeatTheBoss": defeatTheBoss,
            "quicktype": quicktype,
            "eggWalk": eggWalk,
            "matchThePFP": matchThePFP,
            "splitOrSteal": splitOrSteal,
            "reverseQuicktype": reverseQuicktype,
            "pickUpIceCream": pickUpIceCream,
            "pickUpTheWatermelon": pickUpTheWatermelon,
            "guessTheNumber": guessTheNumber,
            "memoryGame": memoryGame,
            "whoSaidIt": whoSaidIt,
            "unscrambleWords": unscrambleWords,
            "twoTruthsAndALie": twoTruthsAndALie,
            "countingCurrency": countingCurrency,
            "rockPaperScissors": rockPaperScissors,
            "rollADice": rollADice,
            "guessTheVoiceline": guessTheVoiceline,
            "genshinEmojiRiddle": genshinEmojiRiddle,
            "hsrEmojiRiddle": hsrEmojiRiddle,
            "doubleOrKeep": doubleOrKeep,
            "knowYourMembers": knowYourMembers,
            "hangmanGame": hangmanGame,
            "moraAuctionHouse": moraAuctionHouse,
            "moraHeist": moraHeist,
            "simpleMathGame": simpleMathGame,
            "ticTacTok": ticTacTok
        }

    async def minigame_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> list[app_commands.Choice[str]]:
        choices = []
        
        for func_name in self.minigame_mapping.keys():
            display_name = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', func_name)
            display_name = display_name.replace("The", "the").title().replace("The", "the")
            display_name = display_name.replace("Pfp", "PFP").replace("Hsremojiriddle", "HSR Emoji Riddle")
            
            if current.lower() in display_name.lower():
                choices.append(
                    app_commands.Choice(name=display_name, value=func_name)
                )
                
        return choices[:25]

    @app_commands.command(name="summon", description="Start a minigame using your summons")
    @app_commands.autocomplete(minigame=minigame_autocomplete)
    @app_commands.describe(
        minigame="Choose a minigame to start"
    )
    async def summon(self, interaction: discord.Interaction, minigame: str):
        await interaction.response.defer()
        
        stats_ref = db.reference(f"/User Events Stats/{interaction.guild.id}/{interaction.user.id}")
        stats = stats_ref.get() or {}
        summons = stats.get("minigame_summons", 0)

        if summons < 1:
            return await interaction.followup.send("<:no:1036810470860013639> You don't have any minigame summons left!")

        minigame_func = self.minigame_mapping.get(minigame)
        if not minigame_func:
            return await interaction.followup.send("<:no:1036810470860013639> Invalid minigame selection!")

        stats_ref.update({"minigame_summons": summons - 1})

        embed = discord.Embed(
            title=":magnet: Minigame Summoned!",
            description=f"{interaction.user.mention} successfully started the **{minigame.replace('The', 'the').replace('Pfp', 'PFP').title()}** minigame.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"You have {summons - 1} summon{'s' if summons - 1 != 1 else ''} remaining")
        await interaction.followup.send(embed=embed)
        from commands.Events.quests import update_quest
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"summon_minigame": 1}, interaction.client)
        await minigame_func(interaction.channel, interaction.client)
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TheEventItself(bot))
    await bot.add_cog(Summon(bot))
