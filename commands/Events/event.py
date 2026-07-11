import discord
import datetime
import asyncio
import time
import random
import re
import pandas as pd
import io
import aiohttp

from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
from essential_generators import DocumentGenerator
from difflib import SequenceMatcher

from commands.Events.trackData import get_current_track, check_tier_rewards, is_elite_active
from commands.Events.helperFunctions import addMora, get_guild_mora, get_channel_settings, get_channel_mora_multiplier, get_channel_chest_config, get_user_minigame_settings, get_guild_settings, get_chest_progress, upsert_chest_progress, get_chest_streaks, upsert_chest_streaks, get_chest_counts, upsert_chest_counts, get_sigils_balance, get_daily_sigils, add_sigils, parse_boosted_roles
from commands.Events.quests import update_quest

from commands.Events.config import CROSS_EMOJI, CIRCLE_EMOJI, MEMORY_GAME_EMOJIS, BALANCE_COMMAND, SIGILS_MESSAGE_EMOTE, MORA_EMOTE, TTOL_EMOJIS, YES_EMOTE, NO_EMOTE, MONEYDANCE_EMOTE, TYPERACER_FONT_PATH, TYPERACER_BG_PATH, TYPERACER_PATH, MORA_CHEST_NAME, MORA_CHEST_TIERS, MORA_CHEST_REWARDS, MORA_CHEST_UPGRADE_CHANCES, MORA_CHEST_STREAK_BONUS, MORA_CHEST_MAX_STREAK_BONUS, MORA_CHEST_TIMEOUT, EMOTE_STREAK, EMOTE_MAX_STREAK, EMOTE_BLANK, LETTER_LIST, TIPS, PROFILE_LINK_BUTTON, BOSSES, HSR_EMOJI_RIDDLE_CSV_URL, GENSHIN_EMOJI_RIDDLE_CSV_URL, CURRENCY_EMOTES, WORDS, SIGIL_EMOTE, SIGIL_CURRENCY_NAME, DEFAULT_CHAT_RANGE, DEFAULT_CHAT_MAX_CAP, DEFAULT_CHAT_MSG_RANGE
from commands.Events.config import build_chest_description

from utils.commands import SlashCommand


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


async def handle_message_deletion(message):
    await asyncio.sleep(3)
    try:
        await message.delete()
    except discord.NotFound:
        pass  # already deleted/was removed
    
async def add_xp(user_id, guild_id, xp_amount, client):
    from commands.Events.helperFunctions import get_user_xp, get_progression_data, ensure_progression_user
    
    pool = client.pool
    await ensure_progression_user(pool, guild_id, user_id)
    
    data = await get_progression_data(pool, guild_id, user_id)
    
    old_xp = data.get("xp", 0)
    new_xp = old_xp + xp_amount
    
    current_tier = 0
    TRACK_DATA = get_current_track()
    for tier in TRACK_DATA:
        if new_xp >= tier["cumulative_xp"]:
            current_tier = tier["tier"]
        else:
            break
    
    # Update bonus_tier if needed
    if current_tier == 31:
        bonus_xp = new_xp - TRACK_DATA[-1]["cumulative_xp"]
        bonus_tiers = bonus_xp // 1500
        
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE minigame_progression SET xp = $3, bonus_tier = $4, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                guild_id, user_id, new_xp, bonus_tiers
            )
    else:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE minigame_progression SET xp = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                guild_id, user_id, new_xp
            )
    
    return (current_tier, old_xp, new_xp)

            
async def userAndTitle(userID, guildID, pool):
    from commands.Events.helperFunctions import get_pinned_item
    pinned_title = await get_pinned_item(pool, userID, guildID)
    if pinned_title:
        role_mention = (
            f"<@&{pinned_title}>"
            if isinstance(pinned_title, int) or str(pinned_title).isdigit()
            else pinned_title
        )
        return f"<@{userID}> **({role_mention})** {MONEYDANCE_EMOTE if await is_elite_active(pool, userID, guildID) else ''}"
    return f"<@{userID}> {MONEYDANCE_EMOTE if await is_elite_active(pool, userID, guildID) else ''}"


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
        summary = []
        elapsed = time.time() - self.start_time
        
        mora_mult = await get_channel_mora_multiplier(self.client.pool, self.channel.id)
        sorted_users = sorted(self.participants.items(), key=lambda x: x[1], reverse=True)
        
        for rank, (uid, dmg) in enumerate(sorted_users, 1):
            amount = int((3000 + dmg) * mora_mult)
            
            if rank == 1: 
                amount += int(2000 * mora_mult)
            if uid == self.last_hitter: 
                amount += int(1500 * mora_mult)
            
            text, addedMora = await addMora(self.client.pool, uid, amount, self.channel.id, self.channel.guild.id, self.client)
            
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
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
    boss = random.choice(BOSSES)
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
        elapsed = time.time() - self.view.start_time
        text, addedMora = await addMora(
            interaction.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client
        )
        user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
        await interaction.response.edit_message(
            content="",
            embed=discord.Embed(
                title=f"Snatch the watermelon - :watermelon:",
                description=f"{user_display} picked up the `🍉` watermelon and earned {MORA_EMOTE} `{text}`.",
                color=discord.Color.gold(),
            ),
            view=PickUpView(disabled=True, timeout=None)
        )
        
        quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
        if elapsed < 5:
            quest_data["win_minigames_under_5s"] = 1
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)

class PickUpView(discord.ui.View):
    def __init__(self, disabled=False, timeout=300, start_time=None):
        super().__init__(timeout=timeout)
        self.start_time = start_time
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
    start_time = time.time()
    view = PickUpView(start_time=start_time)
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
        elapsed = time.time() - self.view.start_time
        
        num = int(interaction.message.embeds[0].description.split("`")[1])
        reward = random.randint(3000, num)
        
        if random.choice(["pos", "neg"]) == "neg":
            reason = random.choice([
                "having tooth decay",
                "having a brain freeze",
                "catching a cold",
                "melt"
            ])
            
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, -reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            if reason == "melt":
                embed = discord.Embed(
                    title=f"A wild 🍦 has appeared.",
                    description=f"Unfortunately, {interaction.user.mention} did not eat the `🍦` in time. The ice cream melted and {user_display} lost {MORA_EMOTE} `{text}`.",
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title=f"A wild 🍦 has appeared.",
                    description=f"Unfortunately, {user_display} ate the `🍦` and lost {MORA_EMOTE} `{text}` for {reason}.",
                    color=discord.Color.red(),
                )
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1, "earn_mora": addedMora}, interaction.client)
        else:
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            embed = discord.Embed(
                title=f"A wild 🍦 has appeared.",
                description=f"{user_display} enjoyed the `🍦` while earning {MORA_EMOTE} `{text}`.",
                color=discord.Color.green(),
            )
            
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)

        await interaction.response.edit_message(
            content="",
            embed=embed,
            view=PickUpIceCreamView(disabled=True, timeout=None)
        )


class PickUpIceCreamView(discord.ui.View):
    def __init__(self, disabled=False, timeout=300, start_time=None):
        super().__init__(timeout=timeout)
        self.start_time = start_time
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    num = int(random.randint(5000, 8000) * mora_mult)
    start_time = time.time()
    view = PickUpIceCreamView(start_time=start_time)
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
    text, bg=TYPERACER_BG_PATH, filename=TYPERACER_PATH
):
    im1 = Image.open(bg)
    color = (0, 0, 0)
    font = ImageFont.truetype(TYPERACER_FONT_PATH, 55)
    d1 = ImageDraw.Draw(im1)
    d1.text((120, 60), text, font=font, fill=color)
    im1.save(filename)
    return filename


async def quicktype(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(4000, 6000) * mora_mult)
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
                    await answer.add_reaction(YES_EMOTE)
                except Exception:
                    continue
                    
                winner_id = answer.author.id
                text, addedMora = await addMora(client.pool, answer.author.id, reward, answer.channel.id, answer.guild.id, client)
                user_display = await userAndTitle(answer.author.id, answer.guild.id, client.pool)
                success_embed = discord.Embed(
                    title=f"Quicktype Racer",
                    description=f"{user_display} won {MORA_EMOTE} `{text}`.",
                    color=discord.Color.brand_green(),
                )
                success_embed.set_image(url=url)
                await game_msg.edit(embed=success_embed)

                quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
                if elapsed < 5:
                    quest_data["win_minigames_under_5s"] = 1
                
                await update_quest(
                    answer.author.id,
                    channel.guild.id,
                    channel.id,
                    quest_data,
                    client
                )
                break

            elif sum(1 for a, b in zip(typed, correct) if a == b) >= 10:
                qualified_users.add(answer.author.id)
                try:
                    await answer.add_reaction(NO_EMOTE)
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
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
                    await answer.add_reaction(YES_EMOTE)
                except Exception:
                    continue
                    
                winner_id = answer.author.id
                text, addedMora = await addMora(client.pool, answer.author.id, reward, answer.channel.id, answer.guild.id, client)
                user_display = await userAndTitle(answer.author.id, answer.guild.id, client.pool)
                success_embed = discord.Embed(
                    title="Reverse Number Quicktype",
                    description=f"{user_display} won {MORA_EMOTE} `{text}`.",
                    color=discord.Color.brand_green(),
                )
                success_embed.set_image(url=url)
                await game_msg.edit(embed=success_embed)

                quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
                if elapsed < 5:
                    quest_data["win_minigames_under_5s"] = 1
                
                await update_quest(
                    answer.author.id,
                    channel.guild.id,
                    channel.id,
                    quest_data,
                    client
                )
                break

            elif sum(1 for a, b in zip(typed, reversed_words) if a == b) >= 5:
                try:
                    await answer.add_reaction(NO_EMOTE)
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
    start_time = time.time()
    timeout = 300

    word = random.choice(WORDS).strip().lower()
    scrambled = scramble_string(word)

    embed = discord.Embed(
        title="Unscramble the Scrambled",
        description=(
            f"First to unscramble the following word wins {MORA_EMOTE} `{reward}`."
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
                    await answer.add_reaction(YES_EMOTE)
                except Exception:
                    continue
                    
                winner_id = answer.author.id
                text, addedMora = await addMora(client.pool, answer.author.id, reward, answer.channel.id, answer.guild.id, client)
                user_display = await userAndTitle(answer.author.id, answer.guild.id, client.pool)
                success_embed = discord.Embed(
                    title="Unscramble the Scrambled",
                    description=(
                        f"{user_display} won {MORA_EMOTE} `{text}`.\n\n"
                        f"**Scrambled:** `{scrambled}`\n"
                        f"**Correct:** `{word}`"
                    ),
                    color=discord.Color.brand_green(),
                )
                await game_msg.edit(embed=success_embed)

                quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
                if elapsed < 5:
                    quest_data["win_minigames_under_5s"] = 1
                
                await update_quest(
                    answer.author.id,
                    channel.guild.id,
                    channel.id,
                    quest_data,
                    client
                )
                break

            elif contains_all_letters(typed, scrambled):
                try:
                    await answer.add_reaction(NO_EMOTE)
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
                f"{NO_EMOTE} You've already rolled twice!", 
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
                f"{YES_EMOTE} You've completed your two rolls! Wait patiently for the results!"
            )

        await interaction.response.send_message(embed=discord.Embed(description=msg, color=discord.Color.green()), ephemeral=True)


class RollDiceView(discord.ui.View):
    def __init__(self, target, reward, client, timeout=45, start_time=None):
        super().__init__(timeout=timeout)
        self.target = target
        self.reward = reward
        self.client = client
        self.start_time = start_time
        self.user_rolls = {} 
        self.participant_ids = set()
        self.message = None
        self.add_item(RollDiceButton())

    async def on_timeout(self):
        elapsed = time.time() - self.start_time if self.start_time else 45
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
                self.client.pool,
                winner_id,
                final_reward,
                self.message.channel.id,
                self.message.guild.id,
                self.client
            )
            reward_lines.append(
                f"-# <@{winner_id}>: {MORA_EMOTE} `{text}` "
                f"({'Exact match! ' if total == self.target else ''}Rolled: {total})"
            )

            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            
            await update_quest(
                winner_id,
                self.message.guild.id,
                self.message.channel.id,
                quest_data,
                self.client
            )

        for participant_id in self.participant_ids:
            if participant_id not in [w[0] for w in winners]:
                await update_quest(
                    participant_id,
                    self.message.guild.id,
                    self.message.channel.id,
                    {"participate_minigames": 1},
                    self.client
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    target = random.randint(2, 12)
    reward = int(random.randint(4000, 6000) * mora_mult)
    start_time = time.time()

    embed = discord.Embed(
        title="Roll a Dice 🎲",
        description=(
            f"Roll **a dice twice** and get as close as possible to **{target}**!\n"
            f"> Base reward: {MORA_EMOTE} `{reward}` | Exact match doubles your reward!\n"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Game ends after no one rolls for 45 seconds")

    view = RollDiceView(target, reward, client, start_time=start_time)
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
            
            text, addedMora = await addMora(view.client.pool, interaction.user.id, view.reward, view.channel.id, view.channel.guild.id, view.client)
            success_embed = await view.win_embed_factory(interaction.user, text, view.client.pool)
            await view.game_msg.edit(embed=success_embed, view=view)

            elapsed = time.time() - view.start_time if view.start_time else 300
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1

            await update_quest(
                interaction.user.id,
                view.channel.guild.id,
                view.channel.id,
                quest_data,
                view.client
            )
        else:
            await interaction.response.send_message("That is incorrect!", ephemeral=True)

class QuizView(discord.ui.View):
    def __init__(self, answer, options, reward, client, channel, win_embed_factory, timeout_embed_factory=None, start_time=None):
        super().__init__(timeout=300)
        self.answer = answer
        self.options = options
        
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
        self.start_time = start_time

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


### --- GROUP BLACKJACK --- ###

class EventBlackjackGameView(View):
    _DECK = [
        (rank, suit)
        for rank in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        for suit in ['♠', '♥', '♦', '♣']
    ]
    _SUIT_EMOJIS = {'♠': '♠️', '♥': '♥️', '♦': '♦️', '♣': '♣️'}

    def __init__(self, client, channel, user_id, reward, dealer_cards, player_cards, active_players, start_time=None):
        super().__init__(timeout=60)
        self.client = client
        self.channel = channel
        self.user_id = user_id
        self.reward = reward
        self.dealer_cards = dealer_cards
        self.player_cards = player_cards
        self.active_players = active_players
        self.game_over = False
        self.message = None
        self.start_time = start_time

    def _hand_value(self, cards):
        value, aces = 0, 0
        for rank, _ in cards:
            if rank in ('J', 'Q', 'K'):
                value += 10
            elif rank == 'A':
                aces += 1
                value += 11
            else:
                value += int(rank)
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def _draw_card(self):
        used = set(map(tuple, self.dealer_cards + self.player_cards))
        available = [c for c in self._DECK if c not in used]
        return random.choice(available)

    def _fmt_cards(self, cards, hide_first=False):
        parts = []
        for i, (rank, suit) in enumerate(cards):
            parts.append("`??`" if hide_first and i == 0 else f"`{rank}{self._SUIT_EMOJIS[suit]}`")
        return " ".join(parts)

    def _build_embed(self, title, description, color):
        embed = discord.Embed(title=title, description=description, color=color)
        dv = self._hand_value(self.dealer_cards)
        pv = self._hand_value(self.player_cards)
        if self.game_over:
            embed.add_field(name="🎩 Dealer", value=f"{self._fmt_cards(self.dealer_cards)} (Value: {dv})", inline=False)
        else:
            embed.add_field(name="🎩 Dealer", value=f"{self._fmt_cards(self.dealer_cards, hide_first=True)} (Value: ?)", inline=False)
        embed.add_field(name="🎲 Your Hand", value=f"{self._fmt_cards(self.player_cards)} (Value: {pv})", inline=False)
        embed.add_field(name="🏆 Reward", value=f"{MORA_EMOTE} `{self.reward:,}` if you win!", inline=False)
        return embed

    async def _finish(self, interaction, title, description, color, mora_reward=0):
        self.game_over = True
        self.active_players.discard(self.user_id)
        self.clear_items()
        embed = self._build_embed(title, description, color)
        await interaction.response.edit_message(embed=embed, view=self)
        if mora_reward > 0:
            _, added = await addMora(self.client.pool, self.user_id, mora_reward, self.channel.id, self.channel.guild.id, self.client)
            elapsed = time.time() - self.start_time if self.start_time else 300
            quest_data = {"win_minigames": 1, "earn_mora": added}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(self.user_id, self.channel.guild.id, self.channel.id, quest_data, self.client)

    async def _dealer_play_and_resolve(self, interaction):
        used = self.dealer_cards + self.player_cards
        deck = list(self._DECK)
        while self._hand_value(self.dealer_cards) < 17:
            available = [c for c in deck if c not in used]
            card = random.choice(available)
            self.dealer_cards.append(card)
            used.append(card)

        dv = self._hand_value(self.dealer_cards)
        pv = self._hand_value(self.player_cards)

        if dv > 21 or pv > dv:
            reason = "Dealer busted!" if dv > 21 else "You beat the dealer!"
            await self._finish(interaction, "🎉 You Win!", f"{reason} You win {MORA_EMOTE} `{self.reward:,}`!", discord.Color.green(), mora_reward=self.reward)
        elif dv > pv:
            await self._finish(interaction, "💔 You Lose!", "Dealer wins! Better luck next time.", discord.Color.red())
        else:
            consolation = self.reward // 4
            await self._finish(interaction, "🤝 Push!", f"It's a tie! You receive a consolation of {MORA_EMOTE} `{consolation:,}`.", discord.Color.yellow(), mora_reward=consolation)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🎯", row=0)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        self.player_cards.append(self._draw_card())
        pv = self._hand_value(self.player_cards)
        if pv > 21:
            await self._finish(interaction, "💥 Bust!", "You went over 21! No reward this time.", discord.Color.red())
        elif pv == 21:
            await self._dealer_play_and_resolve(interaction)
        else:
            embed = self._build_embed("🎲 Blackjack — Your Turn", "Hit or Stand?", discord.Color.blue())
            embed.set_footer(text="You have 60 seconds to make each move!")
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.green, emoji="✋", row=0)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        await self._dealer_play_and_resolve(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.red, emoji="💵", row=0)
    async def double_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        self.reward *= 2
        self.player_cards.append(self._draw_card())
        if self._hand_value(self.player_cards) > 21:
            await self._finish(interaction, "💥 Bust!", f"You went over 21 after doubling down! No reward.", discord.Color.red())
        else:
            await self._dealer_play_and_resolve(interaction)

    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.grey, emoji="🏳️", row=1)
    async def surrender_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        consolation = self.reward // 4
        await self._finish(interaction, "🏳️ Surrendered", f"You surrendered and receive a consolation of {MORA_EMOTE} `{consolation:,}`.", discord.Color.orange(), mora_reward=consolation)

    async def on_timeout(self):
        if not self.game_over and self.message:
            self.game_over = True
            self.active_players.discard(self.user_id)
            self.clear_items()
            embed = discord.Embed(title="⏰ Game Timeout!", description="You took too long! Your game has ended without a reward.", color=discord.Color.red())
            embed.add_field(name="🎩 Dealer", value=f"{self._fmt_cards(self.dealer_cards)} (Value: {self._hand_value(self.dealer_cards)})", inline=False)
            embed.add_field(name="🎲 Your Hand", value=f"{self._fmt_cards(self.player_cards)} (Value: {self._hand_value(self.player_cards)})", inline=False)
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass


class EventBlackjackLobbyView(View):
    def __init__(self, client, channel, reward, active_players, all_participants, deadline):
        super().__init__(timeout=None)
        self.client = client
        self.channel = channel
        self.reward = reward
        self.active_players = active_players 
        self.all_participants = all_participants 
        self.deadline = deadline
        self.game_msg = None

    @discord.ui.button(label="Play Blackjack", style=discord.ButtonStyle.green, emoji="🃏")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        if time.time() > self.deadline:
            return await interaction.response.send_message(f"{NO_EMOTE} The blackjack table is closed! No new games can be started.", ephemeral=True)
        if user_id in self.active_players:
            return await interaction.response.send_message(f"{NO_EMOTE} You already have an active game!", ephemeral=True)
        if user_id in self.all_participants:
            return await interaction.response.send_message(f"{NO_EMOTE} You've already played your game for this event!", ephemeral=True)

        self.active_players.add(user_id)
        self.all_participants.add(user_id)

        # Deal initial cards
        deck = list(EventBlackjackGameView._DECK)
        random.shuffle(deck)
        player_cards = [deck[0], deck[2]]
        dealer_cards = [deck[1], deck[3]]

        def _hv(cards):
            v, a = 0, 0
            for r, _ in cards:
                if r in ('J','Q','K'): v += 10
                elif r == 'A': a += 1; v += 11
                else: v += int(r)
            while v > 21 and a: v -= 10; a -= 1
            return v

        pv = _hv(player_cards)
        dv = _hv(dealer_cards)

        game_view = EventBlackjackGameView(
            client=self.client,
            channel=self.channel,
            user_id=user_id,
            reward=self.reward,
            dealer_cards=dealer_cards,
            player_cards=player_cards,
            active_players=self.active_players,
            start_time=time.time(),
        )

        # Natural blackjack checks
        if pv == 21 and dv == 21:
            game_view.game_over = True
            self.active_players.discard(user_id)
            embed = game_view._build_embed("🤝 Push!", "Both you and the dealer got blackjack! No reward.", discord.Color.yellow())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif pv == 21:
            game_view.game_over = True
            self.active_players.discard(user_id)
            bj_reward = int(self.reward * 1.5)
            text, added = await addMora(self.client.pool, user_id, bj_reward, self.channel.id, self.channel.guild.id, self.client)
            elapsed = time.time() - game_view.start_time if game_view.start_time else 300
            embed = game_view._build_embed("🎰 Natural Blackjack!", f"You got blackjack! You win {MORA_EMOTE} `{text}`! (1.5× bonus)", discord.Color.gold())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            quest_data = {"win_minigames": 1, "earn_mora": added}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(user_id, self.channel.guild.id, self.channel.id, quest_data, self.client)
        elif dv == 21:
            game_view.game_over = True
            self.active_players.discard(user_id)
            embed = game_view._build_embed("💔 Dealer Blackjack!", "The dealer got natural blackjack! Better luck next time.", discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = game_view._build_embed("🃏 Blackjack — Your Turn!", "Hit or Stand?", discord.Color.blue())
            embed.set_footer(text="You have 60 seconds per move • Double Down & Surrender available!")
            await interaction.response.send_message(embed=embed, view=game_view, ephemeral=True)
            game_view.message = await interaction.original_response()

        try:
            count = len(self.all_participants)
            new_embed = discord.Embed(
                title="🃏 Group Blackjack Event!",
                description=(
                    f"A blackjack table just opened! Click the button below to start **your own game**.\n\n"
                    f"**Win:** {MORA_EMOTE} `{self.reward:,}` • **Natural BJ:** {MORA_EMOTE} `{int(self.reward * 1.5):,}` (1.5×)\n\n"
                    f"-# New games close in 2 minutes from start • One game per player"
                ),
                color=0x1a6635,
            )
            new_embed.set_footer(text=f"{count} player{'s' if count != 1 else ''} playing so far!")
            await self.game_msg.edit(embed=new_embed, view=self)
        except Exception:
            pass


async def groupBlackjack(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
    active_players: set = set()  
    all_participants: set = set()
    deadline = time.time() + 120

    embed = discord.Embed(
        title="🃏 Group Blackjack Event!",
        description=(
            f"A blackjack table just opened! Click the button below to start **your own game**.\n\n"
            f"**Win:** {MORA_EMOTE} `{reward:,}` • **Natural BJ:** {MORA_EMOTE} `{int(reward * 1.5):,}` (1.5×)\n\n"
            f"-# New games close in 2 minutes • One game per player • Beat the dealer to win!"
        ),
        color=0x1a6635,
    )
    embed.set_footer(text="Hit, Stand, Double Down or Surrender!")

    lobby_view = EventBlackjackLobbyView(client, channel, reward, active_players, all_participants, deadline)
    game_msg = await channel.send(embed=embed, view=lobby_view)
    lobby_view.game_msg = game_msg

    await asyncio.sleep(120)

    lobby_view.join_button.disabled = True
    count = len(all_participants)
    closed_embed = discord.Embed(
        title="🃏 Group Blackjack — Table Closed",
        description=(
            f"The blackjack table has closed. No new games can be started.\n\n"
            f"**{count}** player{'s' if count != 1 else ''} participated!"
        ),
        color=discord.Color.greyple(),
    )
    try:
        await game_msg.edit(embed=closed_embed, view=lobby_view)
    except Exception:
        pass

    await asyncio.sleep(30)

    for uid in all_participants:
        await update_quest(uid, channel.guild.id, channel.id, {"participate_minigames": 1}, client)


### --- HSR EMOJI RIDDLE  --- ###

async def hsrEmojiRiddle(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
    start_time = time.time()
    timeout = 300 

    url = HSR_EMOJI_RIDDLE_CSV_URL
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                embed = discord.Embed(description=f"Event crashed: `Failed to fetch minigame data (HTTP {response.status})`")
                embed.set_footer(text="Error has been logged and developer has been notified.")
                msg = await channel.send(embed=embed)
                ian = await client.fetch_user(692254240290242601)
                await ian.send(f"Event crashed: {msg.jump_url}")
                return
            csv_text = await response.text()
    
    df = pd.read_csv(io.StringIO(csv_text))

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
    
    all_chars = list(characterEmojis.keys())
    distractors = random.sample([n for n in all_chars if n != character], 4)
    options = [character] + distractors

    async def win_embed_factory(user, text, pool):
        user_display = await userAndTitle(user.id, user.guild.id, pool)
        success_embed = discord.Embed(
            title="Galaxy *Emojified* Riddles | HSR Character",
            description=(
                f"```{response}```\n"
                f"{user_display} "
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

    view = QuizView(character, options, reward, client, channel, win_embed_factory, timeout_embed_factory, start_time=start_time)
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
    start_time = time.time()
    timeout = 300

    url = GENSHIN_EMOJI_RIDDLE_CSV_URL
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                embed = discord.Embed(description=f"Event crashed: `Failed to fetch minigame data (HTTP {response.status})`")
                embed.set_footer(text="Error has been logged and developer has been notified.")
                msg = await channel.send(embed=embed)
                ian = await client.fetch_user(692254240290242601)
                await ian.send(f"Event crashed: {msg.jump_url}")
                return
            csv_text = await response.text()
    
    df = pd.read_csv(io.StringIO(csv_text))

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

    all_chars = list(characterEmojis.keys())
    distractors = random.sample([n for n in all_chars if n != character], 4)
    options = [character] + distractors

    async def win_embed_factory(user, text, pool):
        user_display = await userAndTitle(user.id, user.guild.id, pool)
        success_embed = discord.Embed(
            title="Teyvat *Emojified* Riddles | Genshin Character",
            description=(
                f"```{response}```\n"
                f"{user_display} "
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

    view = QuizView(character, options, reward, client, channel, win_embed_factory, timeout_embed_factory, start_time=start_time)
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(2000, 3000) * mora_mult)
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
                            await answer.add_reaction(YES_EMOTE)
                        except Exception:
                            continue
                        number += 1
                        previousUser = answer.author
                        userCounts[answer.author] = userCounts.get(answer.author, 0) + 1
                    else:
                        try:
                            await answer.add_reaction(NO_EMOTE)
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
                        await answer.add_reaction(NO_EMOTE)
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
                        text, addedMora = await addMora(client.pool, user.id, total_reward, answer.channel.id, answer.guild.id, client)
                        userMoras[user.id] = addedMora
                        user_display = await userAndTitle(user.id, answer.guild.id, client.pool)
                        summary_lines.append(
                            f"-# - {user_display}: {count} numbers → {MORA_EMOTE} `{text}`"
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
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
        await update_quest(user.id, channel.guild.id, channel.id, quest_data, client)


### --- GUESS THE NUMBER --- ###

async def guessTheNumber(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
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
    view = GuessNumberView(number, start_time=start_time)
    game_msg = await channel.send(embed=embed, view=view)
    view.client = client
    
    await view.wait()
    
    if view.winner_id:
        embed.color = discord.Color.green()
        user_display = await userAndTitle(view.winner_id, channel.guild.id, client.pool)
        embed.description += f"\n\n🏆 {user_display} got it and earned {MORA_EMOTE} `{view.winner_text}`."
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

    elapsed = time.time() - start_time
    for uid in view.participants:
        quest_data = {"participate_minigames": 1}
        if uid == view.winner_id:
            quest_data.update({"win_minigames": 1})
            quest_data.update({"earn_mora": view.addedMora})
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
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
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
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
    def __init__(self, target_number, start_time=None):
        super().__init__(timeout=300)
        self.target_number = target_number
        self.participants = set()
        self.winner_id = None
        self.addedMora = 0
        self.winner_text = ""
        self.start_time = start_time
        
        # Row 0: 1-5
        for i in range(1, 6):
            self.add_item(GuessNumberButton(i, row=0))
            
        # Row 1: 6-10
        for i in range(6, 11):
            self.add_item(GuessNumberButton(i, row=1))


### --- COUNTING CURRENCY --- ###

async def countingCurrency(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)
    start_time = time.time()
    timeout = 300

    A = CURRENCY_EMOTES[0]
    B = CURRENCY_EMOTES[1]
    C = CURRENCY_EMOTES[2]

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
    winner_elapsed = 0

    while True:
        try:
            elapsed = time.time() - start_time
            answer = await client.wait_for("message", check=check)

            if answer.content.isnumeric():
                participants.add(answer.author.id)
                if int(answer.content.strip()) == number:
                    try:
                        await answer.add_reaction(YES_EMOTE)
                    except Exception:
                        continue
                    winner_id = answer.author.id
                    winner_elapsed = elapsed
                    text, addedMora = await addMora(client.pool, winner_id, reward, answer.channel.id, answer.guild.id, client)
                    user_display = await userAndTitle(winner_id, answer.guild.id, client.pool)
                    await answer.reply(
                        embed=discord.Embed(
                            title="Currency Counting",
                            description=f"{user_display} got it and earned {MORA_EMOTE} `{text}`.",
                            color=discord.Color.green(),
                        )
                    )
                    break
                else:
                    try:
                        await answer.add_reaction(NO_EMOTE)
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
            if winner_elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)


### --- HANGMAN --- ###

def choose_word():
    available_words = [w for w in WORDS if 'z' not in w.lower()]
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
        view.embed.set_field_at(1, name=YES_EMOTE + " Correct letters:", value=format_guess_dict(view.correct_letters), inline=True)
        view.embed.set_field_at(2, name=NO_EMOTE + " Incorrect letters:", value=format_guess_dict(view.incorrect_letters), inline=True)
        view.embed.set_field_at(3, name="Tries remaining:", value=f"`{view.tries}`", inline=True)

        if "_" not in display_word:
             view.winner_id = interaction.user.id
             text, addedMora = await addMora(interaction.client.pool, interaction.user.id, view.bonus_reward, interaction.channel.id, interaction.guild.id, interaction.client)
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
    def __init__(self, word, embed, tries, start_time=None, word_reward=1500, bonus_reward=3000):
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
        self.start_time = start_time
        self.word_reward = word_reward
        self.bonus_reward = bonus_reward

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXY"
        for i, letter in enumerate(letters):
            self.add_item(HangmanButton(letter, row=i // 5))

async def hangmanGame(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    WORD_REWARD = int(1500 * mora_mult)
    BONUS_REWARD = int(3000 * mora_mult)
    word = choose_word().lower()
    print(word)
    tries = round(5 + 0.4 * len(word))
    start_time = time.time()
    
    guessed_letters = set()
    incorrect_letters = {}
    correct_letters = {}
    
    display_word = update_word(word, guessed_letters)
    embed = discord.Embed(
        title="Hangman Game",
        description=f"**Guess a letter!** Earn {MORA_EMOTE} **{WORD_REWARD}** per correct letter and an extra {MORA_EMOTE} **{BONUS_REWARD}** for completing the word.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Word:", value=f"`{display_word}`", inline=False)
    embed.add_field(name=YES_EMOTE + " Correct letters:", value=format_guess_dict(correct_letters), inline=True)
    embed.add_field(name=NO_EMOTE + " Incorrect letters:", value=format_guess_dict(incorrect_letters), inline=True)
    embed.add_field(name="Tries remaining:", value=f"`{tries}`", inline=True)
    embed.set_footer(text="Click a letter to guess • 5-minute time limit")
    
    view = HangmanView(word, embed, tries, start_time=start_time, word_reward=WORD_REWARD, bonus_reward=BONUS_REWARD)
    game_msg = await channel.send(embed=embed, view=view)
    
    # Wait for the view to finish (timeout or win/loss)
    await view.wait()
    
    # After game ends (loop logic replacement)
    
    if view.winner_id or "_" not in update_word(word, view.guessed_letters):
        user_display = await userAndTitle(view.winner_id, channel.guild.id, client.pool)
        final_embed = discord.Embed(
            title="Hangman Game",
            description=f"Success! Everyone got {MORA_EMOTE} **`1500`** per correct letter. {user_display} earned an extra {MORA_EMOTE} **`{view.winner_text}`**.",
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
    final_embed.add_field(name=YES_EMOTE + " Correct letters:", value=format_guess_dict(view.correct_letters), inline=True)
    final_embed.add_field(name=NO_EMOTE + " Incorrect letters:", value=format_guess_dict(view.incorrect_letters), inline=True)
    final_embed.add_field(name="Tries remaining:", value=f"`{view.tries}`", inline=True)

    for user_id, letters in view.correct_letters.items():
        count = sum(word.count(letter) for letter in letters)
        reward = count * view.word_reward
        if reward > 0:
            await addMora(client.pool, user_id, reward, channel.id, game_msg.guild.id, client)

    await game_msg.edit(embed=final_embed, view=view)

    elapsed = time.time() - start_time if start_time else 300
    for uid in view.participants:
        quest_data = {"participate_minigames": 1}
        if uid == view.winner_id:
            quest_data["win_minigames"] = 1
            quest_data["earn_mora"] = view.addedMora
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)


### --- MATCH THE PROFILE PICTURE --- ###

class MatchPFPState:
    def __init__(self, correct_name, avatar_url, start_time=None):
        self.correct_name = correct_name
        self.avatar_url = avatar_url
        self.participants = []
        self.start_time = start_time

class MatchPFPButton(discord.ui.Button):
    def __init__(self, name, target_name):
        super().__init__(label=name, style=discord.ButtonStyle.grey)
        self.target_name = target_name

    async def callback(self, interaction: discord.Interaction):
        game_state = active_pfp_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message(f"{NO_EMOTE} This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.participants:
            await interaction.response.send_message(f"{NO_EMOTE} You already guessed!", ephemeral=True)
            return

        game_state.participants.append(interaction.user.id)
        
        if self.target_name == game_state.correct_name:
            reward = int(interaction.message.embeds[0].description.split("`")[1])
            elapsed = time.time() - game_state.start_time if game_state.start_time else 300
            
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            embed = discord.Embed(
                title=f"Who's this?",
                description=f"{user_display} guessed **{self.label}** correctly and earned {MORA_EMOTE} `{text}`.",
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
            
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
            del active_pfp_games[interaction.message.id]
        else:
            await interaction.response.send_message(f"Wrong! {NO_EMOTE}", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

async def matchThePFP(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
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
        return await channel.send(embed=discord.Embed(description=f"{NO_EMOTE} Not enough unique users for the game."))

    target_user = random.choice(selected_items)
    
    view = View()
    for user in selected_items:
        view.add_item(MatchPFPButton(
            name=user.display_name,
            target_name=user.display_name
        ))

    reward = int(random.randint(3000, 5000) * mora_mult)
    embed = discord.Embed(
        title=f"Who's this?",
        description=f"First to guess wins {MORA_EMOTE} `{reward}`. **You can only guess once!**",
        color=discord.Color.light_grey()
    )
    embed.set_image(url=target_user.avatar.url)

    game_message = await channel.send(embed=embed, view=view)

    active_pfp_games[game_message.id] = MatchPFPState(
        correct_name=target_user.display_name,
        avatar_url=target_user.avatar.url,
        start_time=time.time()
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


### --- WHO SAID THAT --- ###

WHO_SAID_THAT_MAX_SUBMISSIONS = 5
WHO_SAID_THAT_SUBMISSION_WINDOW = 60

class WhoSaidItState:
    def __init__(self, reward, start_time=None):
        self.reward = reward
        self.submissions = {}  # user_id -> phrase
        self.guessers = []
        self.phase = "submission"  # "submission" -> "guessing"
        self.finalized = False
        self.correct_user_id = None
        self.start_time = start_time

def whoSaidThatSubmissionEmbed(reward, count):
    return discord.Embed(
        title="Who Said That?",
        description=(
            f"Click below to submit a phrase! Once **{WHO_SAID_THAT_MAX_SUBMISSIONS} submissions** "
            f"come in or after **1 minute** passes with 2+ entries, a random phrase gets revealed and the "
            f"first to guess who said it wins {MORA_EMOTE} `{reward}`!\n\n**Submissions:** `{count}`"
        ),
        color=0x27F5B4
    )

class WhoSaidThatModal(discord.ui.Modal, title="Who Said That?"):
    phrase_input = discord.ui.TextInput(
        label="Enter a phrase about yourself",
        style=discord.TextStyle.short,
        placeholder="e.g. I've never broken a bone in my life",
        max_length=200
    )

    def __init__(self, game_message, game_state):
        super().__init__()
        self.game_message = game_message
        self.game_state = game_state

    async def on_submit(self, interaction: discord.Interaction):
        if self.game_state.finalized or self.game_state.phase != "submission":
            await interaction.response.send_message(f"{NO_EMOTE} This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in self.game_state.submissions:
            await interaction.response.send_message(f"{NO_EMOTE} You've already submitted a phrase!", ephemeral=True)
            return

        self.game_state.submissions[interaction.user.id] = str(self.phrase_input)

        await interaction.response.send_message(f"{YES_EMOTE} Your phrase has been recorded!", ephemeral=True)
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

        count = len(self.game_state.submissions)
        try:
            await self.game_message.edit(embed=whoSaidThatSubmissionEmbed(self.game_state.reward, count))
        except discord.NotFound:
            return

        if count >= WHO_SAID_THAT_MAX_SUBMISSIONS and not self.game_state.finalized:
            self.game_state.finalized = True
            await startWhoSaidThatGuessing(self.game_message, interaction.client, self.game_state)

class WhoSaidThatSubmitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Submit a Phrase", emoji="✍️", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        game_state = active_who_said_it_games.get(interaction.message.id)
        if not game_state or game_state.finalized or game_state.phase != "submission":
            await interaction.response.send_message(f"{NO_EMOTE} This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.submissions:
            await interaction.response.send_message(f"{NO_EMOTE} You've already submitted a phrase!", ephemeral=True)
            return

        await interaction.response.send_modal(WhoSaidThatModal(interaction.message, game_state))

class WhoSaidThatGuessButton(discord.ui.Button):
    def __init__(self, display_name, target_user_id):
        super().__init__(label=display_name, style=discord.ButtonStyle.grey)
        self.target_user_id = target_user_id

    async def callback(self, interaction: discord.Interaction):
        game_state = active_who_said_it_games.get(interaction.message.id)
        if not game_state or game_state.phase != "guessing":
            await interaction.response.send_message(f"{NO_EMOTE} This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.guessers:
            await interaction.response.send_message(f"{NO_EMOTE} You already guessed!", ephemeral=True)
            return
        
        if interaction.user.id == game_state.correct_user_id:
            await interaction.response.send_message(f"{NO_EMOTE} Unfortunately, your phrase is chosen, so you are not allowed to guess! Don't spoil the fun!", ephemeral=True)
            return

        game_state.guessers.append(interaction.user.id)

        if self.target_user_id == game_state.correct_user_id:
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, game_state.reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description += f"\n\n🏆 {user_display} guessed **{self.label}** correctly and earned {MORA_EMOTE} `{text}`!"

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
            await interaction.response.send_message(f"Wrong! {NO_EMOTE}", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

async def startWhoSaidThatGuessing(game_message, client, game_state):
    game_state.phase = "guessing"
    chosen_user_id, chosen_phrase = random.choice(list(game_state.submissions.items()))
    game_state.correct_user_id = chosen_user_id

    user_ids = list(game_state.submissions.keys())
    random.shuffle(user_ids)

    view = View()
    for uid in user_ids:
        member = game_message.guild.get_member(uid)
        if member is None:
            try:
                member = await game_message.guild.fetch_member(uid)
            except discord.NotFound:
                member = None
        display_name = member.display_name if member else "Unknown User"
        view.add_item(WhoSaidThatGuessButton(display_name=display_name, target_user_id=uid))

    embed = discord.Embed(
        title="Who Said That?",
        description=f"Someone submitted this phrase:\n\n> {chosen_phrase}\n\nFirst to guess who said it wins {MORA_EMOTE} `{game_state.reward}`!",
        color=discord.Color.light_grey()
    )

    await game_message.edit(embed=embed, view=view)

    async def cleanup():
        await asyncio.sleep(300)
        if game_message.id in active_who_said_it_games:
            del active_who_said_it_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="⌛ This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(cleanup())

async def whoSaidIt(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(3000, 5000) * mora_mult)

    view = View()
    view.add_item(WhoSaidThatSubmitButton())

    game_message = await channel.send(embed=whoSaidThatSubmissionEmbed(reward, 0), view=view)

    game_state = WhoSaidItState(reward=reward, start_time=time.time())
    active_who_said_it_games[game_message.id] = game_state

    async def resolve_submission_window():
        await asyncio.sleep(WHO_SAID_THAT_SUBMISSION_WINDOW)

        if game_message.id not in active_who_said_it_games:
            return

        state = active_who_said_it_games[game_message.id]
        if state.finalized or state.phase != "submission":
            return

        count = len(state.submissions)

        if count >= 2:
            state.finalized = True
            await startWhoSaidThatGuessing(game_message, client, state)
        elif count == 1:
            state.finalized = True
            uid, _ = next(iter(state.submissions.items()))

            text, addedMora = await addMora(client.pool, uid, state.reward, channel.id, channel.guild.id, client)
            user_display = await userAndTitle(uid, channel.guild.id, client.pool)

            embed = discord.Embed(
                title="Who Said That?",
                description=(
                    f"Not enough players joined in time! Since {user_display} was the only one who submitted "
                    f"a phrase, they win {MORA_EMOTE} `{text}` by default."
                ),
                color=discord.Color.green()
            )
            await game_message.edit(embed=embed, view=None)
            await update_quest(uid, channel.guild.id, channel.id, {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}, client)
            del active_who_said_it_games[game_message.id]
        else:
            del active_who_said_it_games[game_message.id]
            await game_message.edit(embed=discord.Embed(
                description="⌛ This game session has timed out",
                color=discord.Color.dark_grey()
            ), view=None)

    asyncio.create_task(resolve_submission_window())


### --- KNOW YOUR MEMBERS --- ###

class KnowMembersState:
    def __init__(self, correct_member, question, participants, start_time=None):
        self.correct_member = correct_member
        self.question = question
        self.participants = participants
        self.answerers = []
        self.start_time = start_time

class KnowMembersButton(discord.ui.Button):
    def __init__(self, label, target_member, correct_member):
        super().__init__(label=label, style=discord.ButtonStyle.grey)
        self.target_member = target_member
        self.correct_member = correct_member

    async def callback(self, interaction: discord.Interaction):
        game_state = active_know_members_games.get(interaction.message.id)
        if not game_state:
            await interaction.response.send_message(f"{NO_EMOTE} This game session has expired!", ephemeral=True)
            return

        if interaction.user.id in game_state.answerers:
            await interaction.response.send_message(f"{NO_EMOTE} You already guessed!", ephemeral=True)
            return

        game_state.answerers.append(interaction.user.id)
        
        if self.target_member.id == game_state.correct_member.id:
            reward = int(interaction.message.embeds[0].description.split("`")[1])
            elapsed = time.time() - game_state.start_time if game_state.start_time else 300
            
            participants_info = "\n".join(
                f"- **{child.label}**: <t:{int(member.joined_at.timestamp())}:D>"
                for member, child in zip(game_state.participants, self.view.children)
            )
            
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description = f"**{game_state.question}**\n\n{user_display} answered correctly and earned {MORA_EMOTE} `{text}`!\n\n**Server Join Dates:**\n{participants_info}"
            
            for child in self.view.children:
                child.disabled = True
                if child.label == self.label:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

            await interaction.response.edit_message(embed=embed, view=self.view)
            
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
            del active_know_members_games[interaction.message.id]
        else:
            await interaction.response.send_message(f"Incorrect! {NO_EMOTE}", ephemeral=True)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

async def knowYourMembers(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    messages = [msg async for msg in channel.history(limit=10) if msg.author != client.user and not msg.author.bot and msg.content]
    
    author_ids = list({msg.author.id for msg in messages if not msg.author.bot})
    if len(author_ids) < 2:
        return await channel.send(embed=discord.Embed(description=f"{NO_EMOTE} Not enough unique recent messaging users for the game."))
    
    authors = []
    for author_id in author_ids:
        try:
            member = await channel.guild.fetch_member(author_id)
            authors.append(member)
        except discord.NotFound:
            continue
    
    if len(authors) < 2:
        return await channel.send(embed=discord.Embed(description=f"{NO_EMOTE} Not enough valid members for the game."))
    
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

    reward = int(random.randint(3000, 5000) * mora_mult)
    embed = discord.Embed(
        title="Know Your Members",
        description=f"{question}\nFirst correct guess earns {MORA_EMOTE} `{reward}`",
        color=0x9dbfc4
    )
    game_message = await channel.send(embed=embed, view=view)

    active_know_members_games[game_message.id] = KnowMembersState(
        correct_member=correct_member,
        question=question,
        participants=selected,
        start_time=time.time()
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
    def __init__(self, correct_emote, chosen_col, start_time=None):
        self.correct_emote = correct_emote
        self.chosen_col = chosen_col
        self.participants = []
        self.start_time = start_time

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
                f"{NO_EMOTE} You have guessed once already. No second try!", ephemeral=True
            )
            return
            
        if str(self.emoji) == game_state.correct_emote:
            game_state.participants.append(interaction.user.id)
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            
            elapsed = time.time() - game_state.start_time if game_state.start_time else 300
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description = f"**Which emote was in Column {game_state.chosen_col}?**\n\n{user_display} guessed correctly and earned {MORA_EMOTE} `{text}`."
            
            for child in self.view.children:
                child.disabled = True
                if str(child.emoji) == str(self.emoji):
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

            await interaction.response.edit_message(
                content="", embed=embed, view=self.view
            )
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
            del active_memory_games[interaction.message.id]
        else:
            await interaction.response.send_message(f"Wrong! {NO_EMOTE}", ephemeral=True)
            game_state.participants.append(interaction.user.id)
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)


async def memoryGame(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(5000, 7000) * mora_mult)

    emojis = random.sample(MEMORY_GAME_EMOJIS, 3)
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
        chosen_col=chosen_col,
        start_time=time.time()
    )


### --- TWO TRUTHS AND A LIE --- ###

class TwoTruthsState:
    def __init__(self, correct_emote, question_author_id, reward, start_time=None):
        self.correct_emote = correct_emote
        self.participants = []
        self.question_author_id = question_author_id
        self.reward = reward
        self.start_time = start_time

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
            await interaction.response.send_message(f"{NO_EMOTE} You have guessed once already. No second try!", ephemeral=True)
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

            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            
            elapsed = time.time() - game_state.start_time if game_state.start_time else 300
            
            text, addedMora = await addMora(interaction.client.pool, interaction.user.id, game_state.reward, interaction.channel.id, interaction.guild.id, interaction.client)
            
            embed.color = discord.Color.green()
            embed.description += f"\n\n🏆 {user_display} chose {self.emoji} correctly and earned {MORA_EMOTE} `{text}`!"
            embed.set_footer(text="Now y'all know a little bit more about each other.")

            await interaction.response.edit_message(content="", embed=embed, view=self.view)
            
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
            del active_ttol_games[interaction.message.id]
        else:
            await interaction.response.send_message(f"Wrong! {NO_EMOTE}", ephemeral=True)
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
            TTOL_EMOJIS[0] if statements[0] == str(self.lie) else
            TTOL_EMOJIS[1] if statements[1] == str(self.lie) else
            TTOL_EMOJIS[2]
        )

        user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
        self.game_embed = discord.Embed(
            title="Two Truths, One Lie",
            description=(
                f'First to determine which of the following statement by '
                f'{user_display} '
                f'is a lie wins {MORA_EMOTE} `{self.reward}`!\n\n'
                f'{TTOL_EMOJIS[0]} "{statements[0]}"\n'
                f'{TTOL_EMOJIS[1]} "{statements[1]}"\n'
                f'{TTOL_EMOJIS[2]} "{statements[2]}"'
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
            user_display = await userAndTitle(interaction.user.id, interaction.guild.id, interaction.client.pool)
            new_embed = discord.Embed(
                title=original_embed.title,
                description=f"{msg}\n\n> *{user_display} is entering their truths and lies...*"
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
        for ttol_emoji in TTOL_EMOJIS:
            view.add_item(answerLieBtn(ttol_emoji))
        
        await modal.submission_interaction.response.send_message(f"{YES_EMOTE} Success", ephemeral=True)
        
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)
        
        game_message = await interaction.channel.send(
            embed=modal.game_embed,
            view=view
        )

        active_ttol_games[game_message.id] = TwoTruthsState(
            correct_emote=modal.correct_emote,
            question_author_id=interaction.user.id,
            reward=reward,
            start_time=time.time()
        )

        async def expire_game():
            await asyncio.sleep(300)
            if game_message.id in active_ttol_games:
                del active_ttol_games[game_message.id]
                await game_message.edit(view=None)
                
        asyncio.create_task(expire_game())


async def twoTruthsAndALie(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    reward = int(random.randint(4000, 6000) * mora_mult)
    messages = [message async for message in channel.history(limit=10)]
    for msg in messages:
        user = msg.author
        if not user.bot: break

    view = View()
    view.add_item(TwoTruthAndALieButton())
    user_display = await userAndTitle(user.id, channel.guild.id, client.pool)
    
    await channel.send(
        content=f"{user.mention}, you have been put in the hot seat!",
        embed=discord.Embed(
            title="Two Truths, One Lie",
            description=f"{user_display} will be entering their **three statements**. First to determine which statement is a lie wins {MORA_EMOTE} `{reward}`!",
            color=discord.Color.blurple()
        ),
        view=view
    )


### --- SPLIT OR STEAL --- ###

class SplitOrStealState:
    def __init__(self, player_a, player_b, reward, start_time=None):
        self.player_a = player_a
        self.player_b = player_b
        self.reward = reward
        self.choices = {player_a.id: None, player_b.id: None}
        self.message_id = None
        self.start_time = start_time

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
            awaiting_user = game_state.player_b if interaction.user == game_state.player_a else game_state.player_a
            user_display = await userAndTitle(awaiting_user.id, interaction.guild.id, interaction.client.pool)
            await interaction.response.send_message(
                f"Waiting for {user_display} to choose...",
                ephemeral=True
            )
        else:
            await self.resolve_game(interaction, game_state)

    async def resolve_game(self, interaction, game_state):
        a_choice = game_state.choices[game_state.player_a.id]
        b_choice = game_state.choices[game_state.player_b.id]
        reward = game_state.reward
        elapsed = time.time() - game_state.start_time if game_state.start_time else 300
        await interaction.message.edit(view=None)

        if a_choice == "Split" and b_choice == "Split":
            split_reward = int(reward / 2)
            textA, addedMoraA = await addMora(interaction.client.pool, game_state.player_a.id, split_reward, interaction.channel.id, interaction.guild.id, interaction.client)
            textB, addedMoraB = await addMora(interaction.client.pool, game_state.player_b.id, split_reward, interaction.channel.id, interaction.guild.id, interaction.client)
            
            player_a_display = await userAndTitle(game_state.player_a.id, interaction.guild.id, interaction.client.pool)
            player_b_display = await userAndTitle(game_state.player_b.id, interaction.guild.id, interaction.client.pool)
            
            if addedMoraA == addedMoraB:
                result_embed = discord.Embed(
                    title="Split Success! 🎉",
                    description=f"Congrats, both {player_a_display} and {player_b_display} chose Split. You each won {MORA_EMOTE} `{textA}`!",
                    color=discord.Color.green()
                )
            else:
                a = player_a_display
                b = player_b_display
                result_embed = discord.Embed(
                    title="Split Success! 🎉",
                    description=f"Congrats, both {a} and {b} chose Split. {a} won {MORA_EMOTE} `{textA}` and {b} won {MORA_EMOTE} `{textB}`!",
                    color=discord.Color.green()
                )
            await interaction.message.reply(embed=result_embed)
            quest_dataA = {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMoraA}
            quest_dataB = {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMoraB}
            if elapsed < 5:
                quest_dataA["win_minigames_under_5s"] = 1
                quest_dataB["win_minigames_under_5s"] = 1
            await update_quest(game_state.player_a.id, interaction.guild.id, interaction.channel.id, quest_dataA, interaction.client)
            await update_quest(game_state.player_b.id, interaction.guild.id, interaction.channel.id, quest_dataB, interaction.client)
        elif "Steal" in [a_choice, b_choice]:
            stealer = game_state.player_a if a_choice == "Steal" else game_state.player_b
            text, addedMora = await addMora(interaction.client.pool, stealer.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            stealer_display = await userAndTitle(stealer.id, interaction.guild.id, interaction.client.pool)
            result_embed = discord.Embed(
                title="It's a Steal! 💰",
                description=f"{stealer_display} stole all the money and won {MORA_EMOTE} `{text}`!",
                color=discord.Color.yellow()
            )
            await interaction.message.reply(embed=result_embed)
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(stealer.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
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
            awaiting_user = game_state.player_b if interaction.user == game_state.player_a else game_state.player_a
            user_display = await userAndTitle(awaiting_user.id, interaction.guild.id, interaction.client.pool)
            await interaction.response.send_message(
                f"Waiting for {user_display} to choose...",
                ephemeral=True
            )
        else:
            await self.resolve_game(interaction, game_state)

    async def resolve_game(self, interaction, game_state):
        a_choice = game_state.choices[game_state.player_a.id]
        b_choice = game_state.choices[game_state.player_b.id]
        reward = game_state.reward
        elapsed = time.time() - game_state.start_time if game_state.start_time else 300
        await interaction.message.edit(view=None)
        
        if a_choice == "Steal" and b_choice == "Steal":
            player_a_display = await userAndTitle(game_state.player_a.id, interaction.guild.id, interaction.client.pool)
            player_b_display = await userAndTitle(game_state.player_b.id, interaction.guild.id, interaction.client.pool)
            result_embed = discord.Embed(
                title=random.choice(["Both Got Nothing :person_shrugging:", "Greed Leaves You With Nothing 💸"]),
                description=f"Both {player_a_display} and {player_b_display} chose Steal. No money for y'all.",
                color=discord.Color.red()
            )
            await interaction.message.reply(embed=result_embed)
            await update_quest(game_state.player_a.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)
            await update_quest(game_state.player_b.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

        elif "Steal" in [a_choice, b_choice]:
            stealer = game_state.player_a if a_choice == "Steal" else game_state.player_b
            text, addedMora = await addMora(interaction.client.pool, stealer.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            stealer_display = await userAndTitle(stealer.id, interaction.guild.id, interaction.client.pool)
            result_embed = discord.Embed(
                title="It's a Steal! 💰",
                description=f"{stealer_display} stole all the money and won {MORA_EMOTE} `{text}`!",
                color=discord.Color.yellow()
            )
            await interaction.message.reply(embed=result_embed)
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(stealer.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
            await update_quest(game_state.player_a.id if game_state.player_b.id == stealer.id else game_state.player_b.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

        del active_split_or_steal_games[interaction.message.id]

async def splitOrSteal(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
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
        return await channel.send(embed=discord.Embed(description=f"{NO_EMOTE} Not enough unique recent messaging users for the game."))

    a, b = selected_players[0], selected_players[1]
    reward = int(random.randint(10000, 14000) * mora_mult)

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

    game_state = SplitOrStealState(a, b, reward, start_time=time.time())
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
    def __init__(self, player_a, player_b, reward, start_time=None):
        self.players = [player_a, player_b]
        self.choices = {player_a.id: None, player_b.id: None}
        self.reward = reward
        self.message_id = None
        self.start_time = start_time

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
    elapsed = time.time() - game_state.start_time if game_state.start_time else 300

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
            text, addedMora = await addMora(interaction.client.pool, player.id, split_reward, interaction.channel.id, interaction.guild.id, interaction.client)
            quest_data = {"participate_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(player.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
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
        text, addedMora = await addMora(interaction.client.pool, winner.id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
        winner_display = await userAndTitle(winner.id, interaction.guild.id, interaction.client.pool)
        result_embed = discord.Embed(
            title=f"",
            description=f"### {winner_display} wins {MORA_EMOTE} `{text}`!\n-# {game_state.players[0].mention} chose {a_emoji}\n-# {game_state.players[1].mention} chose {b_emoji}",
            color=discord.Color.green()
        )
        await interaction.message.reply(embed=result_embed)
        for player in game_state.players:
            if player.id == winner.id:
                quest_data = {"participate_minigames": 1, "win_minigames": 1, "win_1v1_minigames": 1, "earn_mora": addedMora}
                if elapsed < 5:
                    quest_data["win_minigames_under_5s"] = 1
                await update_quest(player.id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)
            else:
                await update_quest(player.id, interaction.guild.id, interaction.channel.id, {"participate_minigames": 1}, interaction.client)

    del active_rps_games[interaction.message.id]

async def rockPaperScissors(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
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
        return await channel.send(f"{NO_EMOTE} Not enough players for the game.")

    a, b = selected_players[0], selected_players[1]
    reward = int(random.randint(5000, 7000) * mora_mult)
    
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

    game_state = RPSGameState(a, b, reward, start_time=time.time())
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
        elapsed = time.time() - view.start_time if view.start_time else 300
        text, addedMora = await addMora(interaction.client.pool, view.current_user.id, view.reward, interaction.channel.id, interaction.guild.id, interaction.client)
        user_display = await userAndTitle(view.current_user.id, interaction.guild.id, interaction.client.pool)
        await interaction.message.delete()
        embed = discord.Embed(
            title="Double or Keep",
            description=f"{user_display} has claimed the current reward of {MORA_EMOTE} `{text}`!",
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
                if elapsed < 5:
                    quest_data["win_minigames_under_5s"] = 1
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
                    start_time=view.start_time,
                ),
            )
        else:
            view.winner_id = selected_user.id
            elapsed = time.time() - view.start_time if view.start_time else 300
            text, addedMora = await addMora(interaction.client.pool, selected_user.id, view.reward, interaction.channel.id, interaction.guild.id, interaction.client)
            user_display = await userAndTitle(selected_user.id, interaction.guild.id, interaction.client.pool)
            await interaction.message.delete()
            embed = discord.Embed(
                title="Double or Keep",
                description=f"{user_display} receives the final reward of {MORA_EMOTE} `{text}`!",
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
                    if elapsed < 5:
                        quest_data["win_minigames_under_5s"] = 1
                await update_quest(uid, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)


class UserSelectView(discord.ui.View):
    def __init__(
        self,
        valid_users: list[discord.Member] = None,
        reward: int = None,
        times_remaining: int = None,
        current_user: discord.Member = None,
        previous_user: discord.Member = None,
        start_time=None,
        *,
        timeout=None,
    ):
        super().__init__(timeout=timeout)
        self.valid_users = valid_users
        self.reward = reward
        self.times_remaining = times_remaining
        self.current_user = current_user
        self.previous_user = previous_user
        self.start_time = start_time
        self.participant_ids = set() 
        self.winner_id = None
        self.add_item(UserSelect(valid_users, current_user))
        self.add_item(ClaimButton())
        

async def doubleOrKeep(channel: discord.TextChannel, client: discord.Client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    messages = [message async for message in channel.history(limit=20)]
    unique_ids = []
    user_list = []

    for message in messages:
        if message.author.id not in unique_ids and not message.author.bot:
            unique_ids.append(message.author.id)
            member = await channel.guild.fetch_member(message.author.id)
            if member:
                user_list.append(member)

    reward = int(random.randint(300, 500) * mora_mult)
    first_user = user_list[0]
    
    if len(user_list) < 2:
        return await channel.send(embed=discord.Embed(description=f"{NO_EMOTE} Not enough unique recent messaging users for the game."))

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
            start_time=time.time(),
        ),
    )

    
### GRAND AUCTION HOUSE ###

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
                    title=f"Already Bid! {NO_EMOTE}",
                    description="You can only bid **once** per auction!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            bid = int(self.bid_amount.value)
            if not 1000 <= bid <= 15000:
                raise ValueError
                
            user_mora = await get_guild_mora(interaction.client.pool, interaction.user.id, interaction.guild.id)

            if bid > user_mora:
                embed = discord.Embed(
                    title=f"Bid Failed {NO_EMOTE}",
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
                title=f"Bid Placed {YES_EMOTE}",
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
                title=f"Invalid Bid {NO_EMOTE}",
                description="Please enter a number between **1000** and **15000**!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class AuctionView(discord.ui.View):
    def __init__(self, end_time, start_time=None):
        super().__init__(timeout=None)
        self.end_time = end_time
        self.message = None
        self.countdown_task = None
        self.bids = {}
        self.client_ref = None
        self.participant_ids = set()
        self.start_time = start_time

    @discord.ui.button(label="Place Bid", style=discord.ButtonStyle.blurple, emoji="💰")
    async def bid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.bids:
            embed = discord.Embed(
                description=f"{NO_EMOTE} You've already bid!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_modal(BidModal(self))

    async def disable_button(self):
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
    time_channel = client.get_channel(1026968305208131645)
    try:
        time_msg = await time_channel.send("⏱️ Auction time sync")
        accurate_time = time_msg.created_at.timestamp()
        await time_msg.delete()
        return accurate_time
    except Exception as e:
        print(f"Time sync failed: {e}")
        return time.time()
    
async def grandAuctionHouse(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    start_time_init = time.time()
    start_time = await get_accurate_time(client)
    end_time = int(start_time) + 90
    
    embed = discord.Embed(
        title="Grand Auction House 🏛️",
        description=(
            f"A mysterious box worth anywhere **between {MORA_EMOTE} `{int(5000 * mora_mult)}` and `{int(15000 * mora_mult)}`** spawned! "
            f"**Closest bid UNDER the value of the box wins!** Auction ends <t:{end_time}:R>"
        ),
        color=0x3498db
    )
    
    view = AuctionView(end_time, start_time=start_time_init)
    view.client_ref = client
    view.message = await channel.send(embed=embed, view=view)
    active_auctions[view.message.id] = view
    view.countdown_task = asyncio.create_task(view.disable_button())
    
    remaining = end_time - int(await get_accurate_time(client))
    if remaining > 0:
        await asyncio.sleep(remaining)
    
    box_value = int(random.randint(5000, 15000) * mora_mult)
    
    if not view.bids:
        await view.message.reply(embed=discord.Embed(description=f"{NO_EMOTE} Auction ended with no bids.", color=discord.Color.red()))
        return

    # Winner: Closest bid under (or equal to) box value
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
    
    text, addedMora = await addMora(client.pool, winner_id, profit, channel.id, channel.guild.id, client)
    elapsed = time.time() - view.start_time if view.start_time else 300
    
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
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
        await update_quest(uid, channel.guild.id, channel.id, quest_data, client)


### --- BANK HEIST --- ###

async def bankHeist(channel, client):
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
    start_time = time.time()
    MIN_CLICK = int(500 * mora_mult)
    MAX_CLICK = int(600 * mora_mult)
    embed = discord.Embed(
        title="Bank Heist! 💰 ",
        description=(
            "Click the button below as many times as you can in 20 seconds!\n"
            f"Each click earns you {MORA_EMOTE} `{MIN_CLICK}-{MAX_CLICK}` Mora!\n\n"
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
    view.start_time = start_time
    view.mora_mult = mora_mult
    view.add_item(BankHeistButton())
    message = await channel.send(embed=embed, view=view)
    
    async def end_game():
        await asyncio.sleep(20)
        view.game_over = True 
        
        embed = message.embeds[0]
        embed.title = "⏳ Bank Heist - Finished!"
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
        elapsed = time.time() - view.start_time
        if sorted_users:
            top_uid = sorted_users[0][0]

        for uid, data in view.user_data.items():
            text, addedMora = await addMora(client.pool, uid, data["mora_earned"], channel.id, channel.guild.id, client)
            summary.append(f"-# <@{uid}>: {MORA_EMOTE} `{text}`")
            
            quest_data = {"participate_minigames": 1, "earn_mora": addedMora}
            if uid == top_uid:
                quest_data["win_minigames"] = 1
                if elapsed < 5:
                    quest_data["win_minigames_under_5s"] = 1
            await update_quest(
                uid,
                channel.guild.id,
                channel.id,
                quest_data,
                client
            )
        
        reward_embed = discord.Embed(
            title="Rewards Distributed",
            description="\n".join(summary),
            color=discord.Color.green()
        )
        await message.reply(embed=reward_embed)

    asyncio.create_task(end_game())

class BankHeistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.grey, emoji="💰", label="Click to Steal")
        
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if getattr(view, 'game_over', False):
            return 

        if not hasattr(view, 'user_data'):
            view.user_data = {}
            
        user_id = interaction.user.id
        
        if user_id not in view.user_data:
            view.user_data[user_id] = {"clicks": 0, "mora_earned": 0}
        
        mora_gain = int(random.randint(500, 600) * view.mora_mult)
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
            text, addedMora = await addMora(view.client.pool, interaction.user.id, reward, interaction.channel.id, interaction.guild.id, view.client)
            
            elapsed = time.time() - view.start_time if view.start_time else 300
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_data, view.client)

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            if "\nFirst to" in embed.description:
                embed.description = embed.description.split("\nFirst to")[0]
            
            embed.description += f"\n:nerd: <@{interaction.user.id}> solved it correctly and earned {MORA_EMOTE} `{text}`!"
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("That is incorrect!", ephemeral=True)


class SimpleMathView(discord.ui.View):
    def __init__(self, correct_val, options, reward, client, start_time=None):
        super().__init__(timeout=300)
        self.correct_val = correct_val
        self.reward = reward
        self.client = client
        self.winner_id = None
        self.participants = set()
        self.message = None
        self.start_time = start_time

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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
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
    reward = int(random.randint(4000, 6000) * mora_mult)
    start_time = time.time()
    
    view = SimpleMathView(ground_truth, options, reward, client, start_time=start_time)
    
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
        self.emoji = CROSS_EMOJI if player_symbol == "X" else CIRCLE_EMOJI
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
            elapsed = time.time() - view.start_time if view.start_time else 300
            text, addedMora = await addMora(interaction.client.pool, view.winner_id, reward, interaction.channel.id, interaction.guild.id, interaction.client)
            quest_data = {"participate_minigames": 1, "win_minigames": 1, "earn_mora": addedMora}
            if elapsed < 5:
                quest_data["win_minigames_under_5s"] = 1
            await update_quest(view.winner_id, interaction.guild.id, interaction.channel.id, quest_data, interaction.client)

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
    def __init__(self, player1, player2, reward, start_time=None):
        super().__init__(timeout=300)
        self.player1_id = player1.id
        self.player2_id = player2.id
        self.players = {player1.id: player1, player2.id: player2}
        self.reward = reward
        self.start_time = start_time
        
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
        
        turn_msg = f"It's {CROSS_EMOJI if self.current_symbol == 'X' else CIRCLE_EMOJI} <@{self.current_player}>'s turn!"
        
        embed = discord.Embed(
            title="Tik Tac Tok", 
            description=f"First to match 3 symbols in a line wins {MORA_EMOTE} `{self.reward}`.\n\n{CROSS_EMOJI} {p1.mention}\n{CIRCLE_EMOJI} {p2.mention}",
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
    mora_mult = await get_channel_mora_multiplier(client.pool, channel.id)
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
    
    reward = int(random.randint(5000, 7000) * mora_mult)
    view = TicTacTokView(p1, p2, reward, start_time=time.time())
    content, embed = view.get_game_state()
    await channel.send(content=content, embed=embed, view=view)


# --- DAILY MORA CHESTS --- #
    
class MoraChestView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, initial_tier, streak, clicks_remaining, channel_settings: dict = None):
        super().__init__(timeout=MORA_CHEST_TIMEOUT)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.tier = initial_tier
        self.streak = streak
        self.clicks_remaining = clicks_remaining
        self.completed = False
        self.message = None
        self.channel_settings = channel_settings or {}
        tiers = self.channel_settings.get("chests_tier_names", MORA_CHEST_TIERS)
        rewards = self.channel_settings.get("chests_tier_rewards", MORA_CHEST_REWARDS)
        emotes = self.channel_settings.get("chests_emotes", [])
        icons = self.channel_settings.get("chests_icons", [])
        self._tier_map = dict(zip(tiers, rewards))
        self._tier_emotes = dict(zip(tiers, emotes)) if emotes else {}
        self._tier_icons = dict(zip(tiers, icons)) if icons else {}
        self._upgrade_chances = self.channel_settings.get("chests_upgrade_chances", MORA_CHEST_UPGRADE_CHANCES)
        self._streak_bonus = self.channel_settings.get("chests_streak_bonus", MORA_CHEST_STREAK_BONUS)
        self._max_streak_bonus = self.channel_settings.get("chests_max_streak_bonus", MORA_CHEST_MAX_STREAK_BONUS)
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
            await interaction.response.send_message(f"{NO_EMOTE} This isn't your chest!", ephemeral=True)
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
            tiers = list(view._tier_map.keys())
            chances = view._upgrade_chances

            for i in range(len(tiers) - 1):
                if view.tier == tiers[i] and random.random() < float(chances[i] if i < len(chances) else 0):
                    new_tier = tiers[i + 1]
                    break

            success = new_tier != view.tier
            view.tier = new_tier

            streak_total = min((view.streak * view._streak_bonus), view._max_streak_bonus)
            total = view._tier_map.get(view.tier, 0) + streak_total

            embed = interaction.message.embeds[0]
            embed.title = f"{MORA_CHEST_NAME} 🎁 ({view.tier})"
            embed.description = (
                f"Upgrades left: `{view.clicks_remaining}`\n\n"
                f"**Tier:** {view.tier} Chest ({MORA_EMOTE} `{view._tier_map.get(view.tier, 0)}`)\n"
                f"**Streak:** {EMOTE_STREAK if view.streak > 1 else ''} `{view.streak}` day{'s' if view.streak > 1 else ''} (`+{streak_total}` {MORA_EMOTE})\n"
                f"**Total:** {MORA_EMOTE} `{total}`"
            )
            embed.color = discord.Color.gold() if success else discord.Color.random()
            embed.set_thumbnail(url=view._tier_icons.get(view.tier, ""))

            view.update_buttons()
            await interaction.response.edit_message(embed=embed, view=view)

    class ClaimButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Claim", style=discord.ButtonStyle.green, emoji="💰")

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            streak_total = min((view.streak * view._streak_bonus), view._max_streak_bonus)
            total = view._tier_map.get(view.tier, 0) + streak_total

            from commands.Events.helperFunctions import get_chest_bonus_chance
            bonus_chance = await get_chest_bonus_chance(interaction.client.pool, view.guild_id, view.user_id)
            is_bonus = False

            if bonus_chance > 0 and random.random() * 100 < bonus_chance:
                is_bonus = True
                async with interaction.client.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE minigame_progression SET minigame_summons = minigame_summons + 1, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                        view.guild_id, view.user_id
                    )

            streak_data = await get_chest_streaks(interaction.client.pool, view.guild_id, view.user_id)
            max_streak = streak_data.get("max_streak", 0)

            new_max_streak = max(max_streak, view.streak)
            text, addedMora = await addMora(interaction.client.pool, view.user_id, total, interaction.channel.id, view.guild_id, interaction.client)

            embed = discord.Embed(
                title=f"{MONEYDANCE_EMOTE} {view.tier} {MORA_CHEST_NAME.split(' ')[-1]} Claimed! {MONEYDANCE_EMOTE}",
                description=f"{MORA_EMOTE} `{text}` is **added** to your inventory!",
                color=discord.Color.green()
            )

            breakdown_val = f"-# Base: {MORA_EMOTE} `{view._tier_map.get(view.tier, 0)}` \n-# Streak Bonus: {MORA_EMOTE} `{streak_total}` {EMOTE_STREAK if view.streak > 1 else ''}"
            if is_bonus:
                breakdown_val += f"\n-# 🌹 **Realm Bonus:** +1 Summon!"

            embed.add_field(name="Reward Breakdown", value=breakdown_val, inline=True)

            reset_unix = get_next_reset_unix()
            embed.add_field(
                name="Next Claim Available", 
                value=f"-# <t:{reset_unix}:f> (<t:{reset_unix}:R>)", 
                inline=True
            )

            tiers_for_counts = list(view._tier_map.keys())
            counts = await get_chest_counts(interaction.client.pool, view.guild_id, view.user_id)
            while len(counts) < len(tiers_for_counts):
                counts.append(0)
            tier_index = tiers_for_counts.index(view.tier)
            counts[tier_index] += 1
            total_chests = sum(counts)

            def _tier_icon(t):
                return view._tier_emotes.get(t, EMOTE_BLANK)

            chest_info = "".join(
                f"{_tier_icon(t)} `{counts[i] if i < len(counts) else 0}` {EMOTE_BLANK}"
                for i, t in enumerate(tiers_for_counts)
            )
            chest_info += (
                f"\n📦 **Total:** `{total_chests}` {EMOTE_BLANK}"
                f"{EMOTE_STREAK} `{view.streak}` day{'s' if view.streak > 1 else ''} {EMOTE_BLANK}"
                f"{EMOTE_MAX_STREAK} `{new_max_streak}` day{'s' if new_max_streak > 1 else ''}"
            )
            embed.add_field(name="Your Inventory", value=chest_info, inline=False)
            embed.set_thumbnail(url=view._tier_icons.get(view.tier, ""))

            await interaction.response.edit_message(content=interaction.user.mention, embed=embed, view=PersistentChestInfoView())

            await upsert_chest_streaks(
                interaction.client.pool, view.guild_id, view.user_id,
                view.streak, new_max_streak,
                datetime.datetime.now(datetime.timezone.utc).date().isoformat()
            )
            await upsert_chest_counts(interaction.client.pool, view.guild_id, view.user_id, counts)
            view.cog.pending_chests.discard((view.user_id, view.guild_id))
            view.completed = True
            view.update_buttons()
            print(f"📦📦📦📦📦 {interaction.user.name} ({interaction.user.id}) has claimed a {view.tier} Chest in {interaction.guild.name} ({interaction.guild.id})")
            await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"collect_chests": 1, "earn_mora": addedMora}, interaction.client)

            from commands.Events.announcements import announcement_embed
            await interaction.followup.send(embed=announcement_embed, ephemeral=True)

    class WhatIsItButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="What is this?", style=discord.ButtonStyle.secondary, emoji="❓")

        async def callback(self, interaction: discord.Interaction):
            reset_unix = get_next_reset_unix()
            embed = discord.Embed(
                description=f"{build_chest_description(self.view.channel_settings)}\n\n***Next reset at** <t:{reset_unix}:f> (<t:{reset_unix}:R>)*",
                color=discord.Color.random()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            
class PersistentChestInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        import copy
        btn = copy.copy(PROFILE_LINK_BUTTON)
        btn.row = 0
        self.add_item(btn)

    @discord.ui.button(
        label="What is this?",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_chest_info_view",
        emoji="❓",
        row=0
    )
    async def persistentChestInfoView(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        reset_unix = get_next_reset_unix()
        gc = await get_guild_settings(interaction.client.pool, interaction.guild_id)
        embed = discord.Embed(
            description=f"{build_chest_description(gc)}\n\n***Next reset at** <t:{reset_unix}:f> (<t:{reset_unix}:R>)*",
            color=discord.Color.random()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="persistent_chest_delete",
        emoji="<a:delete:1372423674640207882>",
        row=0
    )
    async def persistent_chest_delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if str(interaction.user.id) not in interaction.message.content:
            await interaction.response.send_message(f"{NO_EMOTE} This isn't your chest!", ephemeral=True)
        else:
            await interaction.message.delete()
    

DATA_FILE = "commands/Events/mora_chest_data.json"

class ChannelCache:
    TTL = 60

    def __init__(self, pool):
        self.pool = pool
        self.settings = {}     # {channel_id: (ts, dict)}
        self.minigame = {}     # {channel_id: frequency}
        self.minigame_ts = 0
        self.chest = set()     # set of channel ids with chests enabled
        self.chest_ts = 0
        self.guild_chest = {}  # {guild_id: (ts, dict)}
        self.guild_chest_ts = {}  # per-guild TTL tracker

    async def get_channel(self, channel_id):
        now = time.time()
        cached = self.settings.get(channel_id)
        if cached and now - cached[0] < self.TTL:
            return cached[1]
        s = await get_channel_settings(self.pool, channel_id)
        self.settings[channel_id] = (now, s)
        return s

    async def get_mg_channels(self):
        now = time.time()
        if now - self.minigame_ts < self.TTL:
            return self.minigame
        rows = await self.pool.fetch(
            "SELECT channel_id, minigames_frequency FROM minigame_settings WHERE minigames_enabled = TRUE"
        )
        self.minigame = {r["channel_id"]: r["minigames_frequency"] for r in rows}
        self.minigame_ts = now
        return self.minigame

    async def get_chest_channels(self):
        now = time.time()
        if now - self.chest_ts < self.TTL:
            return self.chest
        rows = await self.pool.fetch(
            "SELECT channel_id FROM minigame_settings WHERE chests_enabled = TRUE"
        )
        self.chest = {r["channel_id"] for r in rows}
        self.chest_ts = now
        return self.chest

    async def get_guild_chest(self, guild_id):
        now = time.time()
        cached = self.guild_chest.get(guild_id)
        if cached and now - cached[0] < self.TTL:
            return cached[1]
        cfg = await get_guild_settings(self.pool, guild_id)
        self.guild_chest[guild_id] = (now, cfg)
        return cfg

    def invalidate_channel(self, channel_id):
        self.settings.pop(channel_id, None)

    def invalidate_all(self):
        self.settings.clear()
        self.minigame.clear()
        self.minigame_ts = 0
        self.chest.clear()
        self.chest_ts = 0
        self.guild_chest.clear()


class UserFlags:
    TTL = 6000

    def __init__(self, pool):
        self.pool = pool
        self.flags = {}  # {(gid, uid): (ts, {chest_disabled, minigame_disabled})}

    async def get(self, guild_id, user_id):
        key = (guild_id, user_id)
        now = time.time()
        cached = self.flags.get(key)
        if cached and now - cached[0] < self.TTL:
            return cached[1]
        settings = await get_user_minigame_settings(self.pool, guild_id, user_id)
        self.flags[key] = (now, settings)
        return settings

    def invalidate(self, guild_id, user_id):
        self.flags.pop((guild_id, user_id), None)


class DailyChestSystem:
    def __init__(self, flags: UserFlags):
        self.user_states = {}
        self.cooldown = 5
        self.claimed_today = set()
        self.flags = flags

    def is_effortful_message(self, content: str, last_content: str) -> bool:
        content = content.strip()
        
        if len(content) < 7:
            return False
            
        if content.lower().split():
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

    async def process_message(self, message, cog, cache: ChannelCache, flags: UserFlags):
        if message.author.bot:
            return

        chest_channels = await cache.get_chest_channels()
        if message.channel.id not in chest_channels:
            return

        csettings = await cache.get_channel(message.channel.id)
        csettings_chest_enabled = csettings.get("chests_enabled", True)
        if not csettings_chest_enabled:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        cache_key = (guild_id, user_id)
        current_time = time.time()

        flags_data = await flags.get(guild_id, user_id)
        if flags_data.get("chest_disabled", False):
            return

        key = (guild_id, user_id)
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()

        if key in self.claimed_today:
            return

        from commands.Events.helperFunctions import get_express_daily_chests

        channel_chest_config = await get_channel_chest_config(cog.client.pool, message.guild.id, message.channel.id)
        spawn_req = channel_chest_config.get("chests_spawn_req", [4, 6])

        if key not in self.user_states or self.user_states[key]['current_date'] != today:
            db_state = await self.load_from_db(cog.client.pool, guild_id, user_id)
            if db_state and db_state['current_date'] == today:
                self.user_states[key] = db_state
                if db_state['chest_triggered']:
                    self.claimed_today.add(key)
                    return
            else:
                express_daily_chests = await get_express_daily_chests(cog.client.pool, guild_id, user_id)
                if express_daily_chests:
                    threshold = 1
                elif len(spawn_req) == 1:
                    threshold = spawn_req[0]
                else:
                    threshold = random.randint(spawn_req[0], spawn_req[1])
                self.user_states[key] = {
                    'message_count': 0,
                    'last_time': 0,
                    'last_content': '',
                    'current_date': today,
                    'threshold': threshold,
                    'chest_triggered': False
                }

        state = self.user_states[key]
        if await get_express_daily_chests(cog.client.pool, guild_id, user_id):
            state['threshold'] = 1
        elif state.get('threshold') is None:
            if len(spawn_req) == 1:
                state['threshold'] = spawn_req[0]
            else:
                state['threshold'] = random.randint(spawn_req[0], spawn_req[1])
        current_time = time.time()

        if current_time - state['last_time'] < self.cooldown:
            return

        if not self.is_effortful_message(message.content, state['last_content']):
            return

        state['message_count'] += 1
        state['last_time'] = current_time
        state['last_content'] = message.content

        if not state['chest_triggered']:
            await self.save_to_db(cog.client.pool, guild_id, user_id, state)

        if (not state['chest_triggered'] and
            state['message_count'] >= state['threshold'] and
            (user_id, guild_id) not in cog.pending_chests):

            state['chest_triggered'] = True
            self.claimed_today.add(key)
            await self.save_to_db(cog.client.pool, guild_id, user_id, state)
            await self.trigger_chest(message, cog, channel_chest_config)

    async def load_from_db(self, pool, guild_id, user_id):
        return await get_chest_progress(pool, guild_id, user_id)
        
    async def save_to_db(self, pool, guild_id, user_id, state):
        await upsert_chest_progress(pool, guild_id, user_id, state)
    
    def invalidate_flag_cache(self, guild_id, user_id):
        self.flags.invalidate(guild_id, user_id)
    
    async def check_minigame_disabled(self, pool, guild_id, user_id):
        data = await self.flags.get(guild_id, user_id)
        return data.get("minigame_disabled", False)
    
    def invalidate_minigame_flag_cache(self, guild_id, user_id):
        self.flags.invalidate(guild_id, user_id)
        
    async def reset_daily_states(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        if now.hour == 0 and now.minute == 0:
            self.claimed_today.clear()
            for key in list(self.user_states.keys()):
                del self.user_states[key]
        
    async def trigger_chest(self, message, cog, channel_chest_config=None):
        user_id = message.author.id
        guild_id = message.guild.id
        key = (user_id, guild_id)
        
        if channel_chest_config is None:
            channel_chest_config = await get_channel_chest_config(cog.client.pool, message.guild.id, message.channel.id)
        ccfg = channel_chest_config
        tier_names = ccfg.get("chests_tier_names", MORA_CHEST_TIERS)
        tier_rewards = ccfg.get("chests_tier_rewards", MORA_CHEST_REWARDS)
        streak_bonus = ccfg.get("chests_streak_bonus", MORA_CHEST_STREAK_BONUS)
        spawn_req = ccfg.get("chests_spawn_req", [4, 6])
        
        streak_data = await get_chest_streaks(cog.client.pool, guild_id, user_id)
        last_claimed_raw = streak_data.get("last_claimed")
        if isinstance(last_claimed_raw, str):
            last_claimed = datetime.datetime.fromisoformat(last_claimed_raw).date()
        elif hasattr(last_claimed_raw, "date"):
            last_claimed = last_claimed_raw.date()
        elif isinstance(last_claimed_raw, datetime.date): 
            last_claimed = last_claimed_raw
        else:
            last_claimed = None
        current_streak = streak_data.get("streak", 0)

        today = datetime.datetime.now(datetime.timezone.utc).date()
        new_streak = current_streak + 1 if last_claimed and (today - last_claimed).days == 1 else 1
        
        from commands.Events.helperFunctions import get_chest_upgrades
        clicks_remaining = await get_chest_upgrades(cog.client.pool, guild_id, user_id)

        view = MoraChestView(cog, user_id, guild_id, tier_names[0], new_streak, clicks_remaining, channel_settings=ccfg)
        embed = discord.Embed(
            title=f"{MORA_CHEST_NAME} Unlocked! <a:tada:1227425729654820885>",
            description=(
                f"**{tier_names[0]} Chest** - *{MORA_EMOTE} `{tier_rewards[0]:,}`*\n"
                f"**Click to upgrade** (`{clicks_remaining}` chances left)\n"
                f"**Messages counted:** `{self.user_states[(guild_id, user_id)]['message_count']}`\n"
                f"**Streak:** {EMOTE_STREAK if new_streak > 1 else ''} `{new_streak}` day{'s' if new_streak > 1 else ''} ({MORA_EMOTE} `+{new_streak * streak_bonus}`)"
            ),
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=ccfg.get("chests_icons", [None])[0] if ccfg.get("chests_icons") else "")
        embed.set_footer(text=f"This chest spawned after you sent {self.user_states[(guild_id, user_id)]['threshold']} effortful messages in minigame channels today")
        chest_msg = await message.channel.send(
            content=f"{message.author.mention}, claim this chest <t:{int(time.time()) + MORA_CHEST_TIMEOUT}:R>!",
            embed=embed,
            view=view
        )
        print(f"⛔️⛔️⛔️⛔️⛔️ {message.author.name} ({message.author.id}) is currently claiming a chest in {message.guild.name} ({message.guild.id})")
        view.message = chest_msg
        cog.pending_chests.add(key)
        

class DailySigilSystem:
    def __init__(self, pool):
        self.pool = pool
        self.cooldowns = {}
        self.msg_counts = {}
        self.last_messages = {}

    def is_effortful_message(self, content: str, user_id: int) -> bool:
        content = content.strip()
        if len(content) < 5:
            return False
        if re.fullmatch(r"(\s*<a?:\w+:\d+>\s*){1,4}", content):
            return False
        if re.search(r"(https?:\/\/|www\.|discord\.gg\/)", content.lower()):
            return False
        last_msg = self.last_messages.get(user_id, "")
        if last_msg:
            similarity = SequenceMatcher(None, last_msg.lower(), content.lower()).ratio()
            if similarity > 0.9:
                return False
        return True

    async def calculate_max_sigils(self, guild: discord.Guild, member: discord.Member, guild_settings: dict, csettings: dict) -> int:
        max_sigils = guild_settings.get("chat_max_cap", DEFAULT_CHAT_MAX_CAP)
        boosted = csettings.get("chat_boosted_roles", [])
        if isinstance(boosted, list):
            for entry in boosted:
                if isinstance(entry, str) and ":" in entry:
                    parts = entry.split(":", 1)
                    try:
                        rid = int(parts[0])
                        bonus = parts[1]
                        if rid in [r.id for r in member.roles]:
                            if bonus.startswith("+"):
                                max_sigils += int(bonus[1:])
                            else:
                                max_sigils = max(max_sigils, int(bonus))
                    except (ValueError, IndexError):
                        continue
        return max_sigils

    async def process_chat_sigils(self, message, csettings: dict, client=None):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        current_time = time.time()

        cooldown = 5
        last_time = self.cooldowns.get(user_id, 0)
        if current_time - last_time < cooldown:
            return

        if not self.is_effortful_message(message.content, user_id):
            return

        self.cooldowns[user_id] = current_time
        self.msg_counts[user_id] = self.msg_counts.get(user_id, 0) + 1
        self.last_messages[user_id] = message.content.strip()

        chat_range = csettings.get("chat_range", list(DEFAULT_CHAT_RANGE))
        low = chat_range[0] if len(chat_range) > 0 else DEFAULT_CHAT_RANGE[0]
        high = chat_range[1] if len(chat_range) > 1 else low
        chat_msg_range = csettings.get("chat_msg_range", list(DEFAULT_CHAT_MSG_RANGE))
        msg_low = chat_msg_range[0] if len(chat_msg_range) > 0 else DEFAULT_CHAT_MSG_RANGE[0]
        msg_high = chat_msg_range[1] if len(chat_msg_range) > 1 else msg_low

        if self.msg_counts[user_id] < random.randint(msg_low, msg_high):
            return

        self.msg_counts[user_id] = 0

        guild_settings = await get_guild_settings(self.pool, message.guild.id)
        max_sigils = await self.calculate_max_sigils(message.guild, message.author, guild_settings, csettings)
        if max_sigils <= 0:
            return

        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        daily_data = await get_daily_sigils(self.pool, user_id, message.guild.id, today)
        daily_earned = daily_data.get("earnings", 0)

        sigils_earned = random.randint(low, high)
        if daily_earned + sigils_earned > max_sigils:
            sigils_earned = max(0, max_sigils - daily_earned)
        if sigils_earned <= 0:
            return

        balance = await add_sigils(self.pool, user_id, message.guild.id, sigils_earned, message.channel.id, client)
        new_daily = daily_earned + sigils_earned
        reset_ts = get_next_reset_unix()

        try:
            await message.channel.send(
                f"{SIGILS_MESSAGE_EMOTE} {message.author.mention} earned {SIGIL_EMOTE} **{sigils_earned} {SIGIL_CURRENCY_NAME}** "
                f"for chatting actively! *(Daily Cap: `{new_daily}/{int(max_sigils)}`)*\n"
                f"> -# <a:clock:1382887924273774754> Resets <t:{reset_ts}:R>. Use {SlashCommand(BALANCE_COMMAND)} to check your progress!"
            )
        except Exception:
            pass


class TheEventItself(commands.Cog):
    def __init__(self, bot):
        self.client = bot
        self.cache = ChannelCache(bot.pool)
        self.user_flags = UserFlags(bot.pool)
        self.pending_chests = set()
        self.chest_system = DailyChestSystem(self.user_flags)
        self.daily_reset.start()
        self.sigil_system = DailySigilSystem(bot.pool)

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
                return await message.add_reaction(f"{NO_EMOTE}")
            else:
                uid = int(
                    message.content.split(" ")[1].replace("<@", "").replace(">", "")
                )
                mora = int(message.content.split(" ")[2])

                timestamp = int(time.time())
                async with self.client.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO minigame_mora (uid, gid, cid, timestamp, count)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (gid, uid, cid, timestamp)
                        DO UPDATE SET count = $5
                    """, uid, message.guild.id, 10, timestamp, mora)

                await message.reply(
                    f"Added exactly {MORA_EMOTE} `{mora:,}` to <@{uid}>'s inventory. \n-# This is not boosted and doesn't count towards quest progression."
                )
                
        if message.content.startswith('-addXP'):
            if message.author.id != 692254240290242601: 
                return await message.add_reaction(f"{NO_EMOTE}")
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
                    client=self.client,
                    pool=self.client.pool
                )
                await message.channel.send(f"Added `{xp_amount}` XP to {user.mention}. Reached tier `{tier}`!")
            except Exception as e:
                await message.channel.send(f"Error: {e}")

        if message.author.id == 1006694571167719527:
            return

        chest_channels = await self.cache.get_chest_channels()
        if message.channel.id in chest_channels:
            await self.chest_system.process_message(message, self, self.cache, self.user_flags)

        csettings = await self.cache.get_channel(message.channel.id)
        if csettings.get("chat_enabled", False):
            flags_data = await self.user_flags.get(message.guild.id, message.author.id)
            if not flags_data.get("sigils_disabled", False):
                await self.sigil_system.process_chat_sigils(message, csettings, self.client)

        mg_channels = await self.cache.get_mg_channels()
        if message.channel.id not in mg_channels:
            return

        if not csettings.get("minigames_enabled", False):
            return

        frequency = mg_channels[message.channel.id]
        if message.id % frequency != 0:
            return

        minigame_list = csettings.get("minigames_list", [])
        if not minigame_list or not isinstance(minigame_list, list) or len(minigame_list) == 0:
            return

        flags_data = await self.user_flags.get(message.guild.id, message.author.id)
        if flags_data.get("minigame_disabled", False):
            return

        messages = [
            msg
            async for msg in message.channel.history(limit=frequency)
        ]
        for msg in messages:
            try:
                if len(msg.embeds) > 0 and msg.author.id == self.client.user.id:
                    return
            except Exception:
                pass

        if message.channel.id in active_channels:
            return
        active_channels[message.channel.id] = True

        embed = discord.Embed(
            description=f"Since chat is relatively active, I'm dropping a random event in `3 seconds`.\n-# ***Tip:** {random.choice(TIPS)}*",
            color=discord.Color.orange(),
        )

        view = View()
        btn = PROFILE_LINK_BUTTON
        btn.disabled = False
        view.add_item(btn)

        await message.channel.send(embed=embed, view=view)

        events = [
            defeatTheBoss, quicktype, eggWalk, matchThePFP, splitOrSteal,
            reverseQuicktype, pickUpIceCream, pickUpTheWatermelon, guessTheNumber,
            memoryGame, whoSaidIt, unscrambleWords, twoTruthsAndALie,
            countingCurrency, rockPaperScissors, rollADice, groupBlackjack,
            genshinEmojiRiddle, hsrEmojiRiddle, doubleOrKeep, knowYourMembers,
            hangmanGame, grandAuctionHouse, bankHeist, simpleMathGame, ticTacTok
        ]
        letter_to_event = dict(zip(LETTER_LIST, events))
        eligible_events = [
            letter_to_event[letter]
            for letter in minigame_list
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
            active_channels.pop(message.channel.id, None)
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
            "groupBlackjack": groupBlackjack,
            "genshinEmojiRiddle": genshinEmojiRiddle,
            "hsrEmojiRiddle": hsrEmojiRiddle,
            "doubleOrKeep": doubleOrKeep,
            "knowYourMembers": knowYourMembers,
            "hangmanGame": hangmanGame,
            "grandAuctionHouse": grandAuctionHouse,
            "bankHeist": bankHeist,
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
        
        from commands.Events.helperFunctions import get_user_stats, get_encore_chance
        stats = await get_user_stats(interaction.client.pool, interaction.guild.id, interaction.user.id)
        summons = stats.get("minigame_summons", 0)

        if summons < 1:
            return await interaction.followup.send(f"{NO_EMOTE} You don't have any minigame summons left!")

        minigame_func = self.minigame_mapping.get(minigame)
        if not minigame_func:
            return await interaction.followup.send(f"{NO_EMOTE} Invalid minigame selection!")

        encore_chance = await get_encore_chance(interaction.client.pool, interaction.guild.id, interaction.user.id)
        import random
        saved = False
        eff_chance = min(50, encore_chance)
        
        if random.random() * 100 < eff_chance:
            saved = True
        else:
            async with interaction.client.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE minigame_progression SET minigame_summons = minigame_summons - 1, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                    interaction.guild.id, interaction.user.id
                )

        footer_text = f"You have {summons if saved else summons - 1} summon{'s' if (summons if saved else summons - 1) != 1 else ''} remaining"
        if saved:
            footer_text += " | 🎭 Encore! This summon is not consumed."

        embed = discord.Embed(
            title=":magnet: Minigame Summoned!",
            description=f"{interaction.user.mention} successfully started the **{minigame.replace('The', 'the').replace('Pfp', 'PFP').title()}** minigame.",
            color=discord.Color.green()
        )
        embed.set_footer(text=footer_text)
        await interaction.followup.send(embed=embed)
        from commands.Events.quests import update_quest
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"summon_minigame": 1}, interaction.client)
        await minigame_func(interaction.channel, interaction.client)
        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TheEventItself(bot))
    await bot.add_cog(Summon(bot))