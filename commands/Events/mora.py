import discord
import time
import datetime
import os
import asyncpg
import pandas as pd
import matplotlib.pyplot as plt

from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
from matplotlib.dates import DateFormatter

from commands.Events.createProfileCard import createProfileCard
from commands.Events.trackData import get_current_track, is_elite_active
from commands.Events.helperFunctions import addMora, get_global_leaderboard, get_guild_leaderboard, get_user_mora_history, get_mora_stats, get_guild_mora, get_user_inventory, apply_discount, get_user_minigame_settings, upsert_user_minigame_setting, get_guild_settings, get_channel_settings, get_chest_counts, get_chest_streaks, get_cosmetics, get_milestones_list, get_sigils_balance, get_daily_sigils, parse_boosted_roles, get_global_sigils_balance, get_guild_sigils_leaderboard, get_global_sigils_leaderboard
from commands.Events.seasons import get_current_season
from commands.Events.quests import update_quest, get_quest_data, QUEST_DESCRIPTIONS, QUEST_BONUS_XP, QUEST_XP_REWARDS
from commands.Events.domain import get_kingdom_embed, upgrade_building, BUILDINGS, calculate_cost, get_rank_title
from utils.commands import SlashCommand

from commands.Events.config import DOT_EMOTE, MORA_EMOTE, TRACK_EMOTE, PRESTIGE_EMOTE, ANIMATED_INVENTORY_BG_PATH, INVENTORY_BG_PATH, NO_EMOTE_2, REPLY_EMOTE, YES_EMOTE, NO_EMOTE, RESOLVED_EMOTE, UNRESOLVED_EMOTE, MORA_CHEST_TIERS, MORA_CHEST_NAME, EMOTE_BLANK, EMOTE_STREAK, EMOTE_MAX_STREAK, BALANCE_COMMAND, CURRENCY_NAME, PROFILE_LINK_BUTTON, KINGDOM_NAME, VIEW_FULL_TRACK, GRAPHS_DIRECTORY, SIGIL_EMOTE, SIGIL_CURRENCY_NAME, DEFAULT_CHAT_MSG_RANGE, DEFAULT_CHAT_MAX_CAP, YES_EMOTE_2, GUILD_MORA_EMOTE, GLOBAL_MORA_EMOTE, GUILD_SIGIL_EMOTE, GLOBAL_SIGIL_EMOTE
from commands.Events.config import ThanksEliteTrack, PurchaseEliteTrack

async def generate_mora_graph(pool: asyncpg.Pool, user_id: int, guild_id: int, display_name: str) -> str:
    history = await get_user_mora_history(pool, user_id, guild_id)
    if not history:
        return None
    
    timestamps, mora_values = zip(*history) if history else ([], [])
    timestamps = list(timestamps)
    mora_values = list(mora_values)
    
    stats_data = await get_mora_stats(pool, user_id, guild_id)

    largest_daily = stats_data['largest_daily']
    largest_daily_date = stats_data['largest_daily_date']
    entry_count = stats_data['entry_count']
    first_played = stats_data['first_played']
    average_daily = stats_data['average_daily']
    days_active = stats_data['days_active']
    
    gc = await get_guild_settings(pool, guild_id)
    tier_names = gc.get("chests_tier_names", MORA_CHEST_TIERS)
    tier_emotes_list = gc.get("chests_emotes", [])
    tier_emotes = dict(zip(tier_names, tier_emotes_list)) if tier_emotes_list else {}

    counts = await get_chest_counts(pool, guild_id, user_id)
    total_chests = sum(counts)

    streak_data = await get_chest_streaks(pool, guild_id, user_id)
    
    last_claimed = streak_data.get("last_claimed") if streak_data else None
    if last_claimed:
        if isinstance(last_claimed, str):
            last_claimed = datetime.datetime.fromisoformat(last_claimed).date()
        elif isinstance(last_claimed, (datetime.datetime, datetime.date)):
            if isinstance(last_claimed, datetime.datetime):
                last_claimed = last_claimed.date()
        else:
            last_claimed = None
    current_streak = streak_data.get("streak", 0) if last_claimed and (datetime.datetime.now(datetime.timezone.utc).date() - last_claimed).days <= 1 else 0
    max_streak = streak_data.get("max_streak", current_streak)

    chest_info = ""
    for i, name in enumerate(tier_names):
        emote = tier_emotes.get(name, EMOTE_BLANK)
        count = counts[i] if i < len(counts) else 0
        chest_info += f"{emote} `{count}` {EMOTE_BLANK}"
    chest_info += (
        f"\n**Total:** `{total_chests}` {EMOTE_BLANK}"
        f"{EMOTE_STREAK} `{current_streak}` day{'s' if current_streak > 1 else ''} {EMOTE_BLANK}"
        f"{EMOTE_MAX_STREAK} `{max_streak}` day{'s' if max_streak > 1 else ''}"
    )

    stats = {
        f"`📦` {MORA_CHEST_NAME}s": chest_info,
        "`📅` First Played": f"<t:{first_played}:D>",
        "`💰` Largest Day Earning": f"<t:{largest_daily_date}:D>\n({MORA_EMOTE} `{largest_daily:,}`)",
        f"`📈` Average Daily {CURRENCY_NAME}": f"{MORA_EMOTE} `{average_daily:,}`",
        "`✌️` Minigame Wins": f"`{entry_count - total_chests}` total wins",
        "`😎` Active Days": f"`{days_active}` different day(s)",
    }
    
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps, unit='s'),
        'mora': mora_values
    }).sort_values('timestamp')
    
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, ax = plt.subplots(figsize=(10, 6))
    df['cumulative'] = df['mora'].cumsum()
    df['smooth'] = df['cumulative'].rolling(7, min_periods=1).mean()
    
    ax.plot(df['timestamp'], df['smooth'], 
           color='#FFD700', linewidth=3, 
           solid_capstyle='round')
    
    def format_mora(value, _):
        if value >= 1_000_000:
            return f'{value/1_000_000:.1f}M'
        if value >= 1_000:
            return f'{value/1_000:.0f}K'
        return f'{value:.0f}'
    
    ax.yaxis.set_major_formatter(plt.FuncFormatter(format_mora))
    
    ax.set_title(f"{display_name}'s {CURRENCY_NAME} Earnings History", fontsize=20, pad=20, fontweight='bold', color='#f5d8ff')
    ax.set_ylabel(f"Total {CURRENCY_NAME}", fontsize=14, labelpad=16, color='white')
    ax.xaxis.set_major_formatter(DateFormatter('%b %d'))
    ax.tick_params(axis='both', which='major', labelsize=15, colors='white')
    ax.grid(True, alpha=1, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    os.makedirs(GRAPHS_DIRECTORY, exist_ok=True)
    path = f"{GRAPHS_DIRECTORY}/{user_id}.png"
    plt.savefig(path, bbox_inches='tight', dpi=120, transparent=True)
    plt.close()
    
    return (path, stats)

        
class ToggleView(discord.ui.View):
    def __init__(self, original_embed, user_id, command_user_id, message=None, guild_id=None, custom_color=None, is_elite=False):
        super().__init__(timeout=180)
        self.original_embed = original_embed
        self.user_id = user_id
        self.command_user_id = command_user_id
        self.message = message
        self.state = "home"
        self.guild_id = guild_id
        self.purchase_button = None
        self.custom_color = custom_color
        
        self.upgrade_select = None
        self.settings_select = None

        self.profile_button = PROFILE_LINK_BUTTON
        self.add_item(self.profile_button)

        self.purchase_button = ThanksEliteTrack() if is_elite else PurchaseEliteTrack()
        self.add_item(self.purchase_button) 
        
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
        self.stop()

    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.blurple, disabled=True, custom_id="home")
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        self.state = "home"
        await self.update_buttons(interaction.client.pool)
        await interaction.response.edit_message(embed=self.original_embed, view=self)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.grey, custom_id="graph")
    async def graph_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        result = await generate_mora_graph(interaction.client.pool, self.user_id, interaction.guild.id, (await interaction.guild.fetch_member(self.user_id)).display_name)
        if not result:
            await interaction.response.send_message("No data available! Start playing to see your stats.", ephemeral=True)
            return
        
        graph_path, stats = result
        chn = interaction.client.get_channel(1026968305208131645)
        msg = await chn.send(file=discord.File(graph_path))
        graph_url = msg.attachments[0].proxy_url

        graph_embed = discord.Embed(
            title=f"{(await interaction.guild.fetch_member(self.user_id)).display_name}'s Player Statistics in {interaction.guild.name}",
            color=self.custom_color or 0x02e6c3
        )
        
        first = True
        for key, value in stats.items():
            if first:
                graph_embed.add_field(name=key, value=value, inline=False)
                first = False
            else:
                graph_embed.add_field(name=key, value=value, inline=True)
        graph_embed.set_image(url=graph_url)
        graph_embed.set_footer(
            text="Tip: Claim your chest at the same time each day to keep your streak!"
        )

        self.state = "graph"
        await self.update_buttons(interaction.client.pool)
        await interaction.response.edit_message(embed=graph_embed, view=self)

    @discord.ui.button(label="Track", style=discord.ButtonStyle.grey, custom_id="track")
    async def track_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        track_embed = await self.create_track_embed(interaction)
        
        self.state = "track"
        await self.update_buttons(interaction.client.pool)
        await interaction.response.edit_message(embed=track_embed, view=self)

    async def create_track_embed(self, interaction: discord.Interaction) -> discord.Embed:
        from commands.Events.helperFunctions import get_progression_data
        data = await get_progression_data(interaction.client.pool, interaction.guild.id, self.user_id)
        user_xp = data["xp"]
        prestige = data.get("prestige", 0)

        TRACK_DATA = get_current_track()
        current_tier = 0
        for tier in TRACK_DATA:
            if user_xp >= tier["cumulative_xp"]:
                current_tier = tier["tier"]
            else:
                break

        prev_xp = TRACK_DATA[current_tier - 1]["cumulative_xp"] if current_tier > 0 else 0
        xp_in_current_tier = user_xp - prev_xp

        if current_tier < len(TRACK_DATA):
            next_tier_xp = TRACK_DATA[current_tier]["xp_req"]
        else:
            next_tier_xp = 0

        track_table = "```ansi\n[2;34mTier    Free Track[0m              [2;33mElite Track (Patrons)[0m\n"
        track_table += "------------------------------------------------------\n"

        max_tier_to_show = min(len(TRACK_DATA), current_tier + 2)
        visible_tiers = TRACK_DATA[:max_tier_to_show + 1]  # inclusive

        if max_tier_to_show < len(TRACK_DATA) - 1:
            hidden_remaining = len(TRACK_DATA) - (max_tier_to_show + 1)
            show_footer_dots = True
        else:
            show_footer_dots = False

        for tier in visible_tiers:
            if tier["tier"] <= current_tier:
                status = "✅"
            elif tier["tier"] == current_tier + 1:
                status = "🔄"
            else:
                status = "🔐"

            def format_reward(text: str) -> str:
                lower = text.lower()
                if any(k in lower for k in ["title", "frame", "background", "custom", "express"]):
                    return f"\u001b[1;2m\u001b[1;36m{text}\u001b[0m\u001b[0m"
                if "prestige" in lower:
                    return f"\u001b[1;2m\u001b[1;31m{text}\u001b[0m\u001b[0m"
                return text

            free_reward = format_reward(tier["free"].split("|")[0].strip()[:22].ljust(24))
            elite_reward = format_reward(tier["elite"].split("|")[0].strip()[:22])

            track_table += (
                f"[1;37m{tier['tier']:2d}[0m  "
                f"{status.ljust(2)} "
                f"{free_reward}"
                f"{elite_reward}\n"
            )

        if show_footer_dots:
            track_table += f"... ({hidden_remaining} more)\n"
            
        last_tier_visible = any(tier['tier'] == 31 for tier in visible_tiers)
        bonus_message = "Earn Bonus Drop Packs for every 2500 XP gained!" if last_tier_visible else ""
        track_table += f"{bonus_message}```"

        bonus_tiers = 0
        if current_tier == 31:
            bonus_tiers = data.get("bonus_tier", 0)
            current_tier_display = f"31 + {bonus_tiers} Bonus"
            xp_past_max = user_xp - TRACK_DATA[-1]["cumulative_xp"]
            current_progress = xp_past_max % 2500
            next_tier_info = f"Next Bonus Tier: {current_progress} / 2500 XP"
        else:
            current_tier_display = str(current_tier)
            next_tier_info = f"\n Next Tier: {xp_in_current_tier} / {next_tier_xp} XP"

        def emoji_bar(fraction):
            bar_len = 20
            fraction = max(0, min(fraction, 1))
            filled = int(fraction * bar_len)
            return "━" * filled + "-" * (bar_len - filled)
        
        def double_struck_number(num):
            ds_digits = {
                "0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒",
                "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗"
            }
            return "".join(ds_digits[d] for d in str(num))
        
        season = get_current_season()
        embed = discord.Embed(
            title=f"{(await interaction.guild.fetch_member(self.user_id)).display_name}'s Progression Track in {interaction.guild.name}",
            description=(
                f"### [Season {season.id}: **{season.name}**](https://fischl.app/profile) {TRACK_EMOTE}\n-# <a:clock:1382887924273774754> *Season ends <t:{int(season.end_ts)}:R>* {VIEW_FULL_TRACK}\n-# {REPLY_EMOTE} **Earn XP** by purchasing in the shop and completing quests.\n"
                f"```diff\n"
                f"+ Current Tier: {current_tier_display} ({user_xp} total XP)\n"
                + f"- Status: {'Elite Track Activated' if await is_elite_active(interaction.client.pool, self.user_id, self.guild_id) else 'Free Track Only'}\n"
                + f"{next_tier_info}\n"
                + (f" {double_struck_number(current_tier)} {emoji_bar(xp_in_current_tier / next_tier_xp if next_tier_xp else 0)} {double_struck_number(current_tier + 1)}\n" if current_tier < 31 else "")
                + f"```\n"
                + f"{track_table}\n"
                + "`✅` = Tier reached     `🔄` = In progress     `🔐` = Locked\n"
            ),
            color=self.custom_color or discord.Color.purple()
        )
        from commands.Events.helperFunctions import get_user_stats
        stats = await get_user_stats(interaction.client.pool, interaction.guild.id, self.user_id)
        embed.add_field(name=f"{MORA_EMOTE} {CURRENCY_NAME} Boost", value=f"`+{stats.get('mora_boost', 0)}%`", inline=True)
        embed.add_field(name=":arrow_up_small: Daily Chest Upgrades", value=f"`{stats.get('chest_upgrades', 4)}`", inline=True)
        gift_tax = stats.get('gift_tax', 'Not unlocked')
        embed.add_field(name=":gift: Gift Tax", value=f"`{gift_tax}{'%' if gift_tax != 'Not unlocked' and gift_tax is not None else ''}`", inline=True)
        embed.add_field(name="🧲 Minigame Summons", value=f"`{stats.get('minigame_summons', 0)}`", inline=True)
        embed.add_field(name="🏷️ Shop Discount", value=f"`{stats.get('shop_discount', 0)}%`", inline=True)
        embed.add_field(name=f"🏰 {KINGDOM_NAME} Discount", value=f"`{stats.get('domain_discount', 0)}%`", inline=True)

        cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, self.user_id)
        selected = dict(cosmetics) if cosmetics else {}
        color_unlocked = cosmetics["embed_color"] if cosmetics else False
        color_status = "`Not unlocked`"
        if color_unlocked:
            custom_color = selected.get("selected_embed_color_hex")
            color_status = f"`{custom_color}`" if custom_color else "`Unlocked but not set`"
        embed.add_field(name="🎨 Custom Accent Color", value=color_status, inline=True)
        embed.add_field(name=f"{PRESTIGE_EMOTE} Prestige", value=f"`{prestige}`")
        
        embed.set_footer(text="Tip: XP Progression is tracked separately per server.")
        return embed

    @discord.ui.button(label="Quests", style=discord.ButtonStyle.grey, custom_id="quests")
    async def quests_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        await update_quest(self.user_id, interaction.guild.id, interaction.channel.id, 0, interaction.client, refresh_only=True)
        
        quest_data = await get_quest_data(interaction.client.pool, self.guild_id, self.user_id)
        
        quest_text = []
        for duration in ["daily", "weekly", "monthly"]:
            dur_data = quest_data.get(duration, {})
            quests = dur_data.get("quests", {})
            completed = dur_data.get("completed", {})
            end_time = dur_data.get("end_time", 0)
            
            if not quests:
                continue
                
            reset_time = f"<t:{end_time}:R>" if end_time else "Unknown"
            quest_text.append(f"### {duration.capitalize()} Quests - `{QUEST_XP_REWARDS[duration]}` XP each *(resets {reset_time})*")
            
            for q_type, data in quests.items():
                status = f"`{data['current']}/{data['goal']}` {YES_EMOTE}" if q_type in completed else f"`{data['current']}/{data['goal']}`"
                quest_text.append(f"- {QUEST_DESCRIPTIONS.get(q_type, q_type)}: {status}")
                
            if dur_data.get("bonus_awarded"):
                quest_text.append(f"-# {REPLY_EMOTE} *`{QUEST_BONUS_XP[duration]}` XP bonus already claimed! {RESOLVED_EMOTE}*")
            else:
                quest_text.append(f"-# {REPLY_EMOTE} *Complete all for `+{QUEST_BONUS_XP[duration]}` XP bonus! {UNRESOLVED_EMOTE}*")
        
        if not quest_text:
            quest_text = ["No active quests. The next season starts <t:1751328000:R>."]
        
        quests_embed = discord.Embed(
            title=f"{(await interaction.guild.fetch_member(self.user_id)).display_name}'s Quests in {interaction.guild.name}",
            description="\n".join(quest_text),
            color=self.custom_color or discord.Color.green()
        )
        quests_embed.set_footer(text="Tip: Quests reset at the same time chests do")

        
        self.state = "quests"
        await self.update_buttons(interaction.client.pool)
        await interaction.response.edit_message(embed=quests_embed, view=self)

    @discord.ui.button(label=KINGDOM_NAME, style=discord.ButtonStyle.grey, custom_id="domain")
    async def domain_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return

        self.state = "domain"
        await self.update_buttons(interaction.client.pool)
        
        target_user = await interaction.guild.fetch_member(self.user_id)
        embed = await get_kingdom_embed(target_user, interaction.guild.id, self.custom_color, interaction.client.pool)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label=SIGIL_CURRENCY_NAME, style=discord.ButtonStyle.grey, custom_id="sigils")
    async def sigils_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return

        self.state = "sigils"
        await self.update_buttons(interaction.client.pool)

        balance = await get_sigils_balance(interaction.client.pool, self.user_id, interaction.guild.id)
        import datetime as dt
        today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        daily_data = await get_daily_sigils(interaction.client.pool, self.user_id, interaction.guild.id, today)
        daily_earned = daily_data.get("earnings", 0)
        reset_ts = (dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)).timestamp()

        guild_settings = await get_guild_settings(interaction.client.pool, interaction.guild.id)
        base_cap = guild_settings.get("chat_max_cap", DEFAULT_CHAT_MAX_CAP)
        effective_cap = int(base_cap)
        bonus_text = []
        all_settings = await get_channel_settings(interaction.client.pool, interaction.channel.id) if interaction.channel else {}
        boosted_raw = await parse_boosted_roles(all_settings.get("chat_boosted_roles", [])) if all_settings else []
        if boosted_raw:
            member = await interaction.guild.fetch_member(self.user_id)
            for rid, bonus in boosted_raw:
                role = interaction.guild.get_role(rid)
                if role:
                    has_role = role in member.roles
                    if has_role and str(bonus).startswith("+"):
                        effective_cap += int(str(bonus).lstrip("+"))
                    elif has_role:
                        effective_cap = max(effective_cap, int(bonus))
                    bonus_text.append(
                        f"{DOT_EMOTE} {role.mention}: `{bonus}` {YES_EMOTE}" if has_role
                        else f"-# {DOT_EMOTE} {role.mention}: `{bonus}`"
                    )

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s {SIGIL_CURRENCY_NAME} in {interaction.guild.name}",
            color=self.custom_color or discord.Color.purple()
        )
        embed.add_field(name=f"{SIGIL_EMOTE} Balance", value=f"`{balance}`", inline=True)
        embed.add_field(
            name="Daily Chat Progress",
            value=f"`{daily_earned}/{effective_cap}` {SIGIL_CURRENCY_NAME} earned",
            inline=True
        )
        embed.add_field(
            name="Reset Time",
            value=f"<t:{int(reset_ts)}:R>" if reset_ts > time.time() else "Available now!",
            inline=True
        )

        if bonus_text:
            embed.add_field(
                name="Role Bonuses to Max Sigils",
                value="\n".join(bonus_text),
                inline=False
            )
        
        chat_msg_range = all_settings.get("chat_msg_range", list(DEFAULT_CHAT_MSG_RANGE)) if all_settings else list(DEFAULT_CHAT_MSG_RANGE)
        msg_footer = f"{chat_msg_range[0]}" if len(chat_msg_range) == 1 else f"{chat_msg_range[0]}-{chat_msg_range[1]}"
        embed.set_footer(text=f"Tip: Earn a batch of {SIGIL_CURRENCY_NAME} by sending {msg_footer} messages in enabled channels.")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.grey, custom_id="settings")
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return

        self.state = "settings"
        await self.update_buttons(interaction.client.pool)
        embed = await self.build_settings_embed(interaction.client.pool, interaction.guild, self.user_id, interaction.channel.id if interaction.channel else None)
        await interaction.response.edit_message(embed=embed, view=self)

    async def upgrade_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.command_user_id:
            return await interaction.response.send_message("You can't use this button!", ephemeral=True)
            
        building_key = self.upgrade_select.values[0].replace("upgrade_", "")
        
        success, msg = await upgrade_building(interaction.user.id, interaction.guild.id, building_key, interaction)
        
        if success:
            embed = await get_kingdom_embed(interaction.user, interaction.guild.id, self.custom_color, interaction.client.pool)
            await self.update_buttons(interaction.client.pool)
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(f"{YES_EMOTE} {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NO_EMOTE} {msg}", ephemeral=True)

    async def build_settings_embed(self, pool, guild, user_id, channel_id):
        user_settings = await get_user_minigame_settings(pool, guild.id, user_id)
        chest_disabled = user_settings["chest_disabled"]
        minigame_disabled = user_settings["minigame_disabled"]
        sigils_disabled = user_settings["sigils_disabled"]

        csettings = await get_channel_settings(pool, channel_id) if channel_id else {}
        chests_enabled = csettings.get("chests_enabled", False)
        minigames_enabled = csettings.get("minigames_enabled", False)
        chat_enabled = csettings.get("chat_enabled", False)

        channel = guild.get_channel(channel_id) if channel_id else None

        def pref(user_off):
            return NO_EMOTE_2 if user_off else YES_EMOTE_2

        def ch_state(enabled):
            return YES_EMOTE if enabled else NO_EMOTE

        try:
            member = await guild.fetch_member(user_id)
            title = f"{member.display_name}'s Settings in {guild.name}"
        except:
            title = "Settings"

        desc = (
            f"A feature works only when both **you** and a **channel** both have it enabled."
        )

        embed = discord.Embed(
            title=title,
            description=desc,
            color=self.custom_color or discord.Color.blurple()
        )

        prefs = (
            f"-# {DOT_EMOTE} Daily Chest Spawning: {pref(chest_disabled)} \n"
            f"-# {DOT_EMOTE} Minigame Spawning: {pref(minigame_disabled)} \n"
            f"-# {DOT_EMOTE} {SIGIL_CURRENCY_NAME} Chat Earning: {pref(sigils_disabled)}"
        )
        embed.add_field(name="Your Server Preferences", value=prefs, inline=True)

        states = (
            f"-# {DOT_EMOTE} Daily Chest Spawning: {ch_state(chests_enabled)} \n"
            f"-# {DOT_EMOTE} Minigame Spawning: {ch_state(minigames_enabled)} \n"
            f"-# {DOT_EMOTE} {SIGIL_CURRENCY_NAME} Chat Earning: {ch_state(chat_enabled)}"
        )
        ch_name = f"#{channel.name} (Current Channel)" if channel else "Current Channel"
        embed.add_field(name=ch_name, value=states, inline=True)

        embed.set_footer(text="Tip: You can toggle your server preferences at any time.")
        return embed

    async def settings_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.command_user_id:
            return await interaction.response.send_message("You can't use this button!", ephemeral=True)

        setting_key = self.settings_select.values[0]
        column = {"toggle_chest_spawn": "chest_disabled", "toggle_minigame_spawn": "minigame_disabled", "toggle_sigils_spawn": "sigils_disabled"}[setting_key]
        label = {"toggle_chest_spawn": "Daily chest spawning", "toggle_minigame_spawn": "Minigame spawning", "toggle_sigils_spawn": f"{SIGIL_CURRENCY_NAME} chat earning"}[setting_key]

        user_settings = await get_user_minigame_settings(interaction.client.pool, interaction.guild.id, self.user_id)
        new_status = not user_settings[column]
        await upsert_user_minigame_setting(interaction.client.pool, interaction.guild.id, self.user_id, column, new_status)

        chest_cog = interaction.client.get_cog('TheEventItself')
        if chest_cog and hasattr(chest_cog, 'chest_system'):
            chest_cog.chest_system.invalidate_flag_cache(interaction.guild.id, self.user_id)

        embed = await self.build_settings_embed(interaction.client.pool, interaction.guild, self.user_id, interaction.channel.id if interaction.channel else None)
        await self.update_buttons(interaction.client.pool)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"{YES_EMOTE} {label} is now **{'disabled' if new_status else 'enabled'}**!", ephemeral=True)

    async def update_buttons(self, pool=None):
        for child in self.children:
            if child.custom_id in ["home", "graph", "track", "quests", "domain", "sigils", "settings"]:
                child.disabled = False
                child.style = discord.ButtonStyle.grey
            if self.state == child.custom_id:
                child.disabled = True
                child.style = discord.ButtonStyle.blurple
        
        show_profile_promo = True # (self.state != "domain" and self.state != "sigils" and self.state != "settings")
        
        items_to_remove = []
        
        if self.profile_button in self.children and not show_profile_promo:
            items_to_remove.append(self.profile_button)
            
        if self.purchase_button in self.children and not show_profile_promo:
            items_to_remove.append(self.purchase_button)
            
        for child in self.children:
            cid = getattr(child, "custom_id", "")
            if cid:
                if cid.startswith("upgrade_") or cid in ["kingdom_upgrade_select", "kingdom_upgrade_select_disabled", "settings_select", "settings_select_disabled"]:
                    items_to_remove.append(child)
                    
        for item in items_to_remove:
            self.remove_item(item)
            
        if show_profile_promo:
             if self.profile_button not in self.children:
                 self.add_item(self.profile_button)
             if self.purchase_button not in self.children:
                 self.add_item(self.purchase_button)
            
        if self.state == "domain":
            is_viewer = (self.user_id != self.command_user_id)

            if is_viewer:
                 self.upgrade_select = Select(
                    placeholder=f"Viewing {KINGDOM_NAME} (Read Only)",
                    options=[discord.SelectOption(label="Only the owner can upgrade", value="dummy")], 
                    disabled=True, 
                    custom_id="kingdom_upgrade_select_disabled",
                    row=2
                 )
                 self.add_item(self.upgrade_select)
            else:
                from commands.Events.helperFunctions import get_kingdom_buildings
                from commands.Events.helperFunctions import get_domain_discount
                
                kb_data = {}
                if pool:
                    kb_data = await get_kingdom_buildings(pool, self.guild_id, self.command_user_id)
                    domain_discount = await get_domain_discount(pool, self.guild_id, self.command_user_id)
                else:
                    domain_discount = 0
                
                options = []
                for key, info in BUILDINGS.items():
                    lvl = kb_data.get(key, 0)
                    cost = calculate_cost(lvl)
                    discounted_cost = apply_discount(cost, domain_discount)
                    
                    label = f"{info['emoji']} {info['name']}"
                    if domain_discount > 0 and discounted_cost < cost:
                        desc = f"Lv. {lvl} ➜ Lv. {lvl+1} | Cost: {discounted_cost:,} (discounted)"
                    else:
                        desc = f"Lv. {lvl} ➜ Lv. {lvl+1} | Cost: {cost:,}"
                    
                    options.append(discord.SelectOption(
                        label=label,
                        description=desc,
                        value=f"upgrade_{key}",
                        emoji=info['emoji']
                    ))
                
                self.upgrade_select = Select(
                    placeholder="Choose a building to upgrade...",
                    options=options,
                    custom_id="kingdom_upgrade_select",
                    row=2
                )
                self.upgrade_select.callback = self.upgrade_select_callback
                self.add_item(self.upgrade_select)
        
        if self.state == "settings":
            # Get current chest and minigame spawn status for display
            user_settings = await get_user_minigame_settings(pool, self.guild_id, self.user_id)
            chest_disabled = user_settings["chest_disabled"]
            chest_status = "Disabled" if chest_disabled else "Enabled"
            minigame_disabled = user_settings["minigame_disabled"]
            minigame_status = "Disabled" if minigame_disabled else "Enabled"

            is_viewer = (self.user_id != self.command_user_id)

            if is_viewer:
                 self.settings_select = Select(
                    placeholder=f"Viewing Settings (Read Only)",
                    options=[discord.SelectOption(label="Only the owner can edit", value="dummy")], 
                    disabled=True, 
                    custom_id="settings_select_disabled",
                    row=2
                 )
                 self.add_item(self.settings_select)
            else:
                self.settings_select = Select(
                    placeholder="Select a setting to modify...",
                    options=[
                        discord.SelectOption(
                            label="Daily Chest Spawning",
                            value="toggle_chest_spawn",
                        ),
                        discord.SelectOption(
                            label="Minigame Spawning",
                            value="toggle_minigame_spawn",
                        ),
                        discord.SelectOption(
                            label=f"{SIGIL_CURRENCY_NAME} Chat Earning",
                            value="toggle_sigils_spawn",
                        ),
                    ],
                    custom_id="settings_select",
                    row=2
                )
                self.settings_select.callback = self.settings_select_callback
                self.add_item(self.settings_select)

class Mora(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name=BALANCE_COMMAND, description=f"Check a user's {CURRENCY_NAME} inventory")
    @app_commands.describe(user="Specify any user other than yourself if needed")
    async def mora(self, interaction: discord.Interaction, user: discord.Member = None):
        start_time = time.perf_counter()
        await interaction.response.defer(thinking=True)
        user = user or interaction.user
        
        # Get global ranking
        global_ranking = await get_global_leaderboard(interaction.client.pool, limit=10000)
        global_total = next((mora for uid, mora in global_ranking if uid == user.id), 0)
        global_rank = next((i+1 for i, (uid, _) in enumerate(global_ranking) if uid == user.id), "N/A")
        global_sigils = await get_global_sigils_balance(interaction.client.pool, user.id)
        global_sigils_leaderboard = await get_global_sigils_leaderboard(interaction.client.pool, limit=10000)
        global_sigils_rank = next((i+1 for i, (uid, _) in enumerate(global_sigils_leaderboard) if uid == user.id), "N/A")

        # Get guild ranking 
        guild_leaderboard = await get_guild_leaderboard(interaction.client.pool, interaction.guild.id, limit=10000)
        guild_total = next((mora for uid, mora in guild_leaderboard if uid == user.id), 0)
        guild_rank = next((i+1 for i, (uid, _) in enumerate(guild_leaderboard) if uid == user.id), "N/A")
        guild_sigils = await get_sigils_balance(interaction.client.pool, user.id, interaction.guild.id)
        guild_sigils_leaderboard = await get_guild_sigils_leaderboard(interaction.client.pool, interaction.guild.id, limit=10000)
        guild_sigils_rank = next((i+1 for i, (uid, _) in enumerate(guild_sigils_leaderboard) if uid == user.id), "N/A")

        inventory_items = await get_user_inventory(interaction.client.pool, user.id, interaction.guild.id)
        inv = f"No {SlashCommand('shop')} items purchased yet"

        MAX_INV_LENGTH = 1024
        EXTRA_LENGTH = 15 

        if inventory_items:
            try:
                item_dict = {}
                pinned_items = {}

                for item in inventory_items:
                    # item = (title, description, cost, gid, timestamp, pinned)
                    if item[2] == 0:  # Skip free items (cost = 0)
                        continue
                    role_id = item[0]
                    timestamp = item[4]
                    is_pinned = item[5]  # Boolean from PostgreSQL

                    target_dict = pinned_items if is_pinned else item_dict

                    if role_id in target_dict:
                        target_dict[role_id]["count"] += 1
                        target_dict[role_id]["timestamp"] = min(
                            target_dict[role_id]["timestamp"], timestamp
                        )
                    else:
                        target_dict[role_id] = {
                            "count": 1,
                            "timestamp": timestamp,
                        }

                def format_item(role, data, pinned=False):
                    prefix = "📌 **Pinned:** " if pinned else "- -# "
                    if isinstance(role, int) or str(role).isdigit():  # Role
                        return (
                            f"{prefix}<@&{role}> **(x{data['count']})** - *First acquired <t:{data['timestamp']}:R>*"
                            if data["count"] > 1
                            else f"{prefix}<@&{role}> - *Acquired <t:{data['timestamp']}:R>*"
                        )
                    else: # Item
                        return (
                            f"{prefix}{role} **(x{data['count']})** - *First acquired <t:{data['timestamp']}:R>*"
                            if data["count"] > 1
                            else f"{prefix}{role} - *Acquired <t:{data['timestamp']}:R>*"
                        )

                pinned_list = [format_item(role, data, True) for role, data in pinned_items.items()]
                items_list = [format_item(role, data) for role, data in item_dict.items()]
                combined_list = pinned_list + items_list

                if combined_list:
                    inv = ""
                    remaining_count = 0

                    for item in combined_list:
                        if len(inv) + len(item) + EXTRA_LENGTH > MAX_INV_LENGTH:
                            break
                        inv += item + "\n"

                    remaining_count = len(combined_list) - inv.count("\n")
                    if remaining_count > 0:
                        inv += f"*({remaining_count} more...)*"

                    inv = inv.strip()

            except Exception as e:
                print(e)
            
        cosmetics = await get_cosmetics(interaction.client.pool, interaction.guild.id, user.id)
        selected = dict(cosmetics) if cosmetics else {}
        elite_active = await is_elite_active(interaction.client.pool, user.id, interaction.guild.id)
        custom_color_hex = selected.get("selected_embed_color_hex") if elite_active else None
        custom_color = discord.Color(int(custom_color_hex, 16)) if custom_color_hex else None
        
        embed = discord.Embed(
            title=f"{user.display_name}'s Inventory in {interaction.guild.name}",
            description="",
            color=custom_color or discord.Color.gold()
        )

        if guild_rank != "N/A":
            embed.add_field(
                name=interaction.guild.name,
                value=(
                    f"{GUILD_MORA_EMOTE} {CURRENCY_NAME}: **`{int(guild_total):,}`**\n"
                    f"{GUILD_SIGIL_EMOTE} {SIGIL_CURRENCY_NAME}: **`{int(guild_sigils):,}`**"
                ),
                inline=True,
            )

        if global_rank != "N/A":
            embed.add_field(
                name="Global",
                value=(
                    f"{GLOBAL_MORA_EMOTE} {CURRENCY_NAME}: **`{int(global_total):,}`**\n"
                    f"{GLOBAL_SIGIL_EMOTE} {SIGIL_CURRENCY_NAME}: **`{int(global_sigils):,}`**"
                ),
                inline=True,
            )

        embed.add_field(name="Guild Inventory", value=inv, inline=False)
        
        milestones = await get_milestones_list(interaction.client.pool, interaction.guild.id)

        user_milestones = []
        try:
            async with interaction.client.pool.acquire() as conn:
                milestone_titles = await conn.fetch(
                    "SELECT title, timestamp FROM minigame_inventory WHERE uid = $1 AND gid = $2 AND cost = 0",
                    user.id, interaction.guild.id
                )
            
            user_milestone_titles = {row['title']: row['timestamp'] for row in milestone_titles}
            
            for milestone in milestones:
                if isinstance(milestone, list) and len(milestone) >= 3:
                    milestone_reward = milestone[1]  # milestone[1] is reward
                    if milestone_reward in user_milestone_titles:
                        user_milestones.append({
                            "threshold": milestone[2], 
                            "reward": milestone_reward,
                            "description": milestone[0],
                            "timestamp": user_milestone_titles[milestone_reward]
                        })
        except Exception as e:
            print(f"Error fetching milestones from PostgreSQL: {e}")

        milestones_text = ""
        if user_milestones:
            user_milestones.sort(key=lambda x: x["threshold"])
            for ms in user_milestones:
                is_role = isinstance(ms["reward"], int) or str(ms["reward"]).isdigit()
                reward_display = f"<@&{ms['reward']}>" if is_role else ms["reward"]
                milestones_text += f"- -# {reward_display} - *Earned at {MORA_EMOTE} `{ms['threshold']:,}` <t:{ms['timestamp']}:R>*\n"
        else:
            milestones_text = f"No {SlashCommand('milestones')} earned yet"

        embed.add_field(name="Guild Milestones", value=milestones_text, inline=False)

        animated_background = selected.get("selected_animated_background") if elite_active else None
        profile_frame = selected.get("selected_profile_frame")
        
        customized = os.path.isfile(f"{INVENTORY_BG_PATH}/{user.id}.png") or bool(profile_frame) or bool(animated_background)
            
        custom_title = selected.get("selected_custom_title")
        title_key = selected.get("selected_title")
        title_display = None
        if custom_title:
            title_display = f"### {custom_title}"
        elif title_key:
            titles = cosmetics["titles"] if cosmetics else []
            
            title_entry = next((e for e in titles if len(e) >= 2 and e[0] == title_key), None)
            if title_entry:
                title_name = title_entry[1]
                
                pin = "<:rank:1364439165189488854>" if "<a:" not in title_name else ""
                title_display = (
                    f"### {pin}{title_name}"
                )

        if title_display:
            embed.description = f"{title_display}\n{embed.description}"

        if customized:
            if animated_background:
                bg_path = f"{ANIMATED_INVENTORY_BG_PATH}/{animated_background}"
                if not os.path.exists(bg_path) and not animated_background.lower().endswith(".gif"):
                    bg_path = f"{bg_path}.gif"
            else:
                bg_path = f"{INVENTORY_BG_PATH}/{user.id}.png"

            filename = await createProfileCard(
                user,
                f"{int(guild_total):,}",
                guild_rank,
                f"{int(guild_sigils):,}",
                guild_sigils_rank,
                f"{int(global_total):,}",
                global_rank,
                f"{int(global_sigils):,}",
                global_sigils_rank,
                bg=bg_path,
                profile_frame=profile_frame if profile_frame else None,
                accent_color_hex=custom_color_hex,
                font_name=selected.get("font") if elite_active else None
            )
            followup = False
        else:
            filename = await createProfileCard(
                user,
                f"{int(guild_total):,}",
                guild_rank,
                f"{int(guild_sigils):,}",
                guild_sigils_rank,
                f"{int(global_total):,}",
                global_rank,
                f"{int(global_sigils):,}",
                global_sigils_rank,
                accent_color_hex=custom_color_hex,
                font_name=selected.get("font") if elite_active else None
            )
            followup = True

        chn = interaction.client.get_channel(1026968305208131645)
        
        from commands.Events.helperFunctions import get_kingdom_buildings
        kb_data = await get_kingdom_buildings(interaction.client.pool, interaction.guild.id, user.id)
        k_data = kb_data
        k_level = sum(k_data.values())
        if k_level > 0:
            rank_title = get_rank_title(k_level)
            
            current_footer = f"| {embed.footer.text}" if embed.footer else ""
            embed.set_footer(text=f"{KINGDOM_NAME} Rank: {rank_title} (Lv. {k_level}) {current_footer}")

        msg_obj = await chn.send(file=discord.File(filename))
        url = msg_obj.attachments[0].proxy_url
        embed.set_image(url=url)

        elite = await is_elite_active(interaction.client.pool, user.id, interaction.guild.id)
        view = ToggleView(embed, user.id, interaction.user.id, message=None, guild_id=interaction.guild.id, custom_color=custom_color, is_elite=elite)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message
        if followup:
            await interaction.followup.send(f"💡 Tip: Customize your inventory however you like (custom background, profile frame, titles) with {SlashCommand('customize')}!", ephemeral=True)
        end_time = time.perf_counter()
        print(f"Total /{BALANCE_COMMAND} execution time: {end_time - start_time} seconds")

    @app_commands.command(name="gift", description=f"Gift {CURRENCY_NAME} to another user")
    @app_commands.describe(
        user=f"User to gift {CURRENCY_NAME} to",
        amount=f"Amount of {CURRENCY_NAME} to gift"
    )
    async def gift(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await interaction.response.defer()

        from commands.Events.helperFunctions import get_user_stats
        stats = await get_user_stats(interaction.client.pool, interaction.guild.id, interaction.user.id)

        if "gift_tax" not in stats or stats["gift_tax"] is None:
            return await interaction.followup.send(f"⏳ You haven't unlocked gifting for this season yet. Unlock it at Tier `5` in the free track!")

        if amount <= 0:
            return await interaction.followup.send(f"{NO_EMOTE} Amount must be positive and non-zero!")

        if amount < 100:
            return await interaction.followup.send(f"{NO_EMOTE} The minimum amount to gift is {MORA_EMOTE} `100`!")

        if interaction.user == user:
            return await interaction.followup.send(f"{NO_EMOTE} You can't gift {MORA_EMOTE} to yourself!")
        
        if user.bot:
            return await interaction.followup.send(f"{NO_EMOTE} Why would you waste your {MORA_EMOTE} on a non-human being?")

        tax_rate = stats["gift_tax"]
        tax_amount = int(amount * tax_rate / 100)
        total_cost = amount + tax_amount

        donor_mora = await get_guild_mora(interaction.client.pool, interaction.user.id, interaction.guild.id)
        recipient_mora = await get_guild_mora(interaction.client.pool, user.id, interaction.guild.id)
                    
        if donor_mora < total_cost:
            return await interaction.followup.send(
                f"You need {MORA_EMOTE} `{total_cost}` ({amount} + {tax_rate}% tax) to make this gift! \n-# You currently only have {MORA_EMOTE} `{donor_mora}`."
            )

        await addMora(interaction.client.pool, interaction.user.id, -total_cost, interaction.channel.id, interaction.guild.id, interaction.client) # Donor
        await addMora(interaction.client.pool, user.id, amount, interaction.channel.id, interaction.guild.id, interaction.client, bypass_boost=True) # Recipient
        await addMora(interaction.client.pool, interaction.client.user.id, tax_amount, interaction.channel.id, interaction.guild.id, interaction.client, bypass_boost=True) # Tax

        embed = discord.Embed(
            title="<a:2_star:1366158196213022800> Gift Sent",
            description=(
                f"**Sender:** {interaction.user.mention}\n"
                f"**Total Deducted:** {MORA_EMOTE} `{total_cost:,}`\n"
                f"-# Fischl also collected {MORA_EMOTE} `{tax_amount:,}` ({tax_rate}%) in taxes\n\n"
                f"**Recipient:** {user.mention}\n"
                f"**Total Received:** {MORA_EMOTE} `{amount:,}`"
            ),
            color=0x2ecc71 
        )
        embed.set_footer(text="Sharing is caring! You just made your friend's day a little brighter!")
        await interaction.followup.send(content=f"{user.mention} has been blessed by {interaction.user.mention}! <a:2_star:1366158196213022800>", embed=embed)
        
        quest_dict = {"gift_mora": amount, "gift_mora_unique": user.id}
        if recipient_mora < donor_mora:
            quest_dict["gift_mora_poorer"] = 1
        
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, quest_dict, interaction.client)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Mora(bot))