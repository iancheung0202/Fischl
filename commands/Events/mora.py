import discord
import time
import datetime
import os
import pandas as pd
import matplotlib.pyplot as plt

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View, Select
from matplotlib.dates import DateFormatter

from commands.Events.createProfileCard import createProfileCard
from commands.Events.trackData import get_current_track
from commands.Events.helperFunctions import get_total_mora, get_guild_mora, addMora
from commands.Events.trackData import is_elite_active, get_current_track
from commands.Events.seasons import get_current_season
from commands.Events.quests import update_quest, QUEST_DESCRIPTIONS, QUEST_BONUS_XP, QUEST_XP_REWARDS
from commands.Events.domain import get_kingdom_embed, upgrade_building, BUILDINGS, calculate_cost, get_rank_title

MORA_EMOTE = "<:MORA:1364030973611610205>"

async def generate_mora_graph(user_id: int, guild_id: int, display_name: str) -> str:
    ref = db.reference(f"/Mora/{user_id}/{guild_id}")
    guild_data = ref.get() or {}

    timestamps = []
    mora_values = []
    entry_count = 0

    for channel_data in guild_data.values():
        for ts, mora in channel_data.items():
            if isinstance(mora, int) and mora >= 0:
                entry_count += 1
            timestamps.append(int(ts))
            mora_values.append(mora)

    if not timestamps:
        return None

    first_played = min(timestamps)

    daily_earnings = {}
    for ts, mora in zip(timestamps, mora_values):
        date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date()
        daily_earnings[date] = daily_earnings.get(date, 0) + mora

    largest_daily = max(daily_earnings.values(), default=0)
    largest_daily_date = None
    for date, amount in daily_earnings.items():
        if amount == largest_daily:
            largest_daily_date = date
            break

    total_days = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.datetime.fromtimestamp(first_played, datetime.timezone.utc).date()).days + 1
    total_mora = sum(mora_values)
    average_daily = total_mora / total_days if total_days > 0 else 0

    days_active = len(daily_earnings)
    
    ref_counts = db.reference(f"/Mora Chest Counts/{guild_id}/{user_id}")
    chest_counts = ref_counts.get() or {"Common": 0, "Exquisite": 0, "Precious": 0, "Luxurious": 0}
    total_chests = sum(chest_counts.values())

    ref_streak = db.reference(f"/Mora Chest Streaks/{guild_id}/{user_id}")
    streak_data = ref_streak.get() or {}
    last_claimed = datetime.datetime.fromisoformat(streak_data["last_claimed"]).date() if "last_claimed" in streak_data else None
    current_streak = streak_data.get("streak", 0) if last_claimed and (datetime.datetime.now(datetime.timezone.utc).date() - last_claimed).days <= 1 else 0
    max_streak = streak_data.get("max_streak", current_streak)

    chest_info = (
        f"<a:common:1371641883121680465> `{chest_counts.get('Common', 0)}` <:blank:1036792889121980426>"
        f"<a:exquisite:1371641856344985620> `{chest_counts.get('Exquisite', 0)}` <:blank:1036792889121980426>"
        f"<a:precious:1371641871452995689> `{chest_counts.get('Precious', 0)}` <:blank:1036792889121980426>"
        f"<a:luxurious:1371641841338023976> `{chest_counts.get('Luxurious', 0)}`\n"
        f"**Total:** `{total_chests}` <:blank:1036792889121980426>"
        f"<a:streak:1371651844652273694> `{current_streak}` day{'s' if current_streak > 1 else ''} <:blank:1036792889121980426>"
        f"<a:max_streak:1371655286049214672> `{max_streak}` day{'s' if max_streak > 1 else ''}"
    )

    stats = {
        "`📦` Daily Mora Chests": chest_info,
        "`📅` First Played": f"<t:{first_played}:D>",
        "`💰` Largest Day Earning": f"<t:{int(time.mktime(largest_daily_date.timetuple()))}:D>\n({MORA_EMOTE} `{largest_daily:,}`)",
        "`📈` Average Daily Mora": f"{MORA_EMOTE} `{average_daily:,.0f}`",
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
    
    ax.set_title(f"{display_name}'s Mora Earnings History", fontsize=20, pad=20, fontweight='bold', color='#f5d8ff')
    ax.set_ylabel("Total Mora", fontsize=14, labelpad=16, color='white')
    ax.xaxis.set_major_formatter(DateFormatter('%b %d'))
    ax.tick_params(axis='both', which='major', labelsize=15, colors='white')
    ax.grid(True, alpha=1, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    os.makedirs("./assets/graph", exist_ok=True)
    path = f"./assets/graph/{user_id}.png"
    plt.savefig(path, bbox_inches='tight', dpi=120, transparent=True)
    plt.close()
    
    return (path, stats)

class ThanksEliteTrack(discord.ui.Button):
    def __init__(self, is_active=False):
        super().__init__(
            label="Elite Track Subscriber",
            style=discord.ButtonStyle.green,
            disabled=True,
            emoji="❤️", 
            row=1
        )
    async def callback(self, interaction: discord.Interaction):
        pass
    
class PurchaseEliteTrack(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Elite Track",
            style=discord.ButtonStyle.green,
            emoji="<a:moneydance:1227425759077859359>",
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        elite_button = Button(
            label="Purchase on Website",
            style=discord.ButtonStyle.link,
            url="https://fischl.app/profile",
        )
        embed = discord.Embed(
            title="<a:tada:1227425729654820885> Less than USD $1/month. More than worth it. <a:moneydance:1227425759077859359>",
            description=(
                "> -# *\"Cheaper than a single Genshin wish, plus you always get value.\"*\n\n"
                "**Elite Track** unlocks a premium reward tier alongside every free tier while supporting development work:\n\n"
                "-# <:dot:1357188726047899760>**Animated Cosmetics**: exclusive animated backgrounds, frames, and badge titles <:KokoWow:1191868161851666583>\n"
                "-# <:dot:1357188726047899760>**Enhanced Boosts**: extra Mora gains, reduced gifting tax, more chest upgrades, and more <:PinkCelebrate:1204614140044386314>\n"
                "-# <:dot:1357188726047899760>**Flexing Perks**: earn **+1 additional Prestige** at the final tier <:LynetteSip:1335609206988079169>\n\n"
                "**Elite rewards are server-specific, and a season lasts for 3 months.**\n"
                f"<:reply:1036792837821435976> <:YanfeiNote:1335644122253623458> ***[View Full Track Comparison](https://fischl.app/profile)***"
            ),
            color=0xfa0af6
        )
        embed.set_footer(text="Login with Discord on the website and select a server to purchase.")
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1106727534479032341/1381827880488669327/elite_track.png?ex=6848eeff&is=68479d7f&hm=079b87a3cac4fdcc8c3fd3fbe615bbf1380651da2e5119c748c5e78ffaa2e752&=&format=webp&quality=lossless&width=840&height=840")
        view = View()
        view.add_item(elite_button)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
class ToggleView(discord.ui.View):
    def __init__(self, original_embed, user_id, command_user_id, message=None, guild_id=None, custom_color=None):
        super().__init__(timeout=180)
        self.original_embed = original_embed
        self.user_id = user_id
        self.command_user_id = command_user_id
        self.message = message
        self.state = "home"  # home, graph, track, quests, domain
        self.guild_id = guild_id
        self.purchase_button = None
        self.custom_color = custom_color
        
        self.upgrade_select = None

        self.profile_button = Button(label="Earn Daily Mora & Summons", style=discord.ButtonStyle.link, url=f"https://fischl.app/profile", emoji="<a:legacy:1345876714240213073>", row=1)
        self.add_item(self.profile_button)

        is_elite = is_elite_active(self.user_id, self.guild_id)
        self.purchase_button = ThanksEliteTrack() if is_elite else PurchaseEliteTrack()
        self.add_item(self.purchase_button)

        self.update_buttons() # Ensure initial state is correct 
        
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
        self.update_buttons()
        await interaction.response.edit_message(embed=self.original_embed, view=self)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.grey, custom_id="graph")
    async def graph_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        result = await generate_mora_graph(self.user_id, interaction.guild.id, (await interaction.guild.fetch_member(self.user_id)).display_name)
        if not result:
            await interaction.response.send_message("No mora data available!", ephemeral=True)
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
        self.update_buttons()
        await interaction.response.edit_message(embed=graph_embed, view=self)

    @discord.ui.button(label="Track", style=discord.ButtonStyle.grey, custom_id="track")
    async def track_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        track_embed = await self.create_track_embed(interaction)
        
        self.state = "track"
        self.update_buttons()
        await interaction.response.edit_message(embed=track_embed, view=self)

    async def create_track_embed(self, interaction: discord.Interaction) -> discord.Embed:
        ref = db.reference(f"/Progression/{interaction.guild.id}/{self.user_id}")
        data = ref.get() or {"xp": 0, "prestige": 0}
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

        track_table = "```ansi\n[2;34mTier    Free Track[0m              [2;33mElite Track (Paid)[0m\n"
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
                if any(k in lower for k in ["title", "frame", "background"]):
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
            title=f"{(await interaction.guild.fetch_member(self.user_id)).display_name}'s Progression Track",
            description=(
                f"### [Season {season.id}: **{season.name}**](https://fischl.app/profile) <:PaiHype:1194817285748183140>\n-# <a:clock:1382887924273774754> *Season ends <t:{int(season.end_ts)}:R>* | **[View Full Track](https://fischl.app/profile)**\n-# <:reply:1036792837821435976> **Earn XP** by purchasing in the shop and completing quests.\n"
                f"```diff\n"
                f"+ Current Tier: {current_tier_display} ({user_xp} total XP)\n"
                + f"- Status: {'Elite Track Activated' if is_elite_active(self.user_id, self.guild_id) else 'Free Track Only'}\n"
                + f"{next_tier_info}\n"
                + (f" {double_struck_number(current_tier)} {emoji_bar(xp_in_current_tier / next_tier_xp)} {double_struck_number(current_tier + 1)}\n" if current_tier < 31 else "")
                + f"```\n"
                + f"{track_table}\n"
                + "`✅` = Tier reached     `🔄` = In progress     `🔐` = Locked\n"
            ),
            color=self.custom_color or discord.Color.purple()
        )
        stats_ref = db.reference(f"/User Events Stats/{interaction.guild.id}/{self.user_id}")
        stats = stats_ref.get() or {}
        embed.add_field(name=f"{MORA_EMOTE} Mora Boost", value=f"`+{stats.get('mora_boost', 0)}%`", inline=True)
        embed.add_field(name=":arrow_up_small: Daily Chest Upgrades", value=f"`{stats.get('chest_upgrades', 4)}`", inline=True)
        gift_tax = stats.get('gift_tax', 'Not unlocked')
        embed.add_field(name=":gift: Gift Tax", value=f"`{gift_tax}{'%' if gift_tax != 'Not unlocked' else ''}`", inline=True)
        embed.add_field(name="🧲 Minigame Summons", value=f"`{stats.get('minigame_summons', 0)}`", inline=True)

        ref_selected = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{self.user_id}/selected")
        selected = ref_selected.get() or {}
        ref_color = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{self.user_id}/embed_color")
        color_unlocked = ref_color.get() or False
        color_status = "`Not unlocked`"
        if color_unlocked:
            custom_color = selected.get("embed_color_hex")
            color_status = f"`{custom_color}`" if custom_color else "`Unlocked but not set`"
        embed.add_field(name="🎨 Custom Embed Color", value=color_status, inline=True)
        embed.add_field(name="<:PRIMOGEM:1364031230357540894> Prestige", value=f"`{prestige}`")
        
        embed.set_footer(text="Tip: XP Progression is tracked separately per server.")
        return embed

    @discord.ui.button(label="Quests", style=discord.ButtonStyle.grey, custom_id="quests")
    async def quests_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        
        await update_quest(self.user_id, interaction.guild.id, interaction.channel.id, 0, interaction.client, refresh_only=True)
        
        ref = db.reference(f"/Global User Quests/{self.user_id}/{self.guild_id}")
        quest_data = ref.get() or {}
        
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
                status = f"`{data['current']}/{data['goal']}` <:yes:1036811164891480194>" if q_type in completed else f"`{data['current']}/{data['goal']}`"
                quest_text.append(f"- {QUEST_DESCRIPTIONS.get(q_type, q_type)}: {status}")
                
            if dur_data.get("bonus_awarded"):
                quest_text.append(f"-# <:reply:1036792837821435976> *`{QUEST_BONUS_XP[duration]}` XP bonus already claimed! <:resolved:1364813186028797984>*")
            else:
                quest_text.append(f"-# <:reply:1036792837821435976> *Complete all for `+{QUEST_BONUS_XP[duration]}` XP bonus! <:yae_hi:1364813223307645000>*")
        
        if not quest_text:
            quest_text = ["No active quests. The next season starts <t:1751328000:R>."]
        
        quests_embed = discord.Embed(
            title=f"{(await interaction.guild.fetch_member(self.user_id)).display_name}'s Quests",
            description="\n".join(quest_text),
            color=self.custom_color or discord.Color.green()
        )
        quests_embed.set_footer(text="Tip: Quests reset at the same time chests do")

        
        self.state = "quests"
        self.update_buttons()
        await interaction.response.edit_message(embed=quests_embed, view=self)

    @discord.ui.button(label="Kingdom", style=discord.ButtonStyle.grey, custom_id="domain", emoji="🏰")
    async def domain_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return

        self.state = "domain"
        self.update_buttons()
        
        target_user = await interaction.guild.fetch_member(self.user_id)
        embed = get_kingdom_embed(target_user, interaction.guild.id, self.custom_color)
        await interaction.response.edit_message(embed=embed, view=self)

    async def upgrade_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.command_user_id:
            return await interaction.response.send_message("You can't use this button!", ephemeral=True)
            
        building_key = self.upgrade_select.values[0].replace("upgrade_", "")
        
        success, msg = await upgrade_building(interaction.user.id, interaction.guild.id, building_key, interaction)
        
        if success:
            embed = get_kingdom_embed(interaction.user, interaction.guild.id, self.custom_color)
            self.update_buttons()
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send(f"<:yes:1036811164891480194> {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"<:no:1036810470860013639> {msg}", ephemeral=True)

    def update_buttons(self):
        for child in self.children:
            if child.custom_id in ["home", "graph", "track", "quests", "domain"]:
                child.disabled = False
                child.style = discord.ButtonStyle.grey
            if self.state == child.custom_id:
                child.disabled = True
                child.style = discord.ButtonStyle.blurple
        
        show_profile_promo = (self.state != "domain")
        
        items_to_remove = []
        
        if self.profile_button in self.children and not show_profile_promo:
            items_to_remove.append(self.profile_button)
            
        if self.purchase_button in self.children and not show_profile_promo:
            items_to_remove.append(self.purchase_button)
            
        for child in self.children:
            cid = getattr(child, "custom_id", "")
            if cid:
                if cid.startswith("upgrade_") or cid in ["kingdom_upgrade_select", "kingdom_upgrade_select_disabled"]:
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
                    placeholder=f"Viewing Kingdom (Read Only)",
                    options=[discord.SelectOption(label="Only the owner can upgrade", value="dummy")], 
                    disabled=True, 
                    custom_id="kingdom_upgrade_select_disabled",
                    row=2
                 )
                 self.add_item(self.upgrade_select)
            else:
                ref = db.reference(f"/Kingdom/{self.guild_id}/{self.user_id}/buildings")
                data = ref.get() or {}
                
                options = []
                for key, info in BUILDINGS.items():
                    lvl = data.get(key, 0)
                    cost = calculate_cost(lvl)
                    
                    label = f"{info['name']}"
                    desc = f"Lv. {lvl} ➜ Lv. {lvl+1} | Cost: {cost:,}"
                    emoji = info['emoji']
                    
                    options.append(discord.SelectOption(
                        label=label,
                        description=desc,
                        value=f"upgrade_{key}",
                        emoji=emoji
                    ))
                
                self.upgrade_select = Select(
                    placeholder="Choose a building to upgrade...",
                    options=options,
                    custom_id="kingdom_upgrade_select",
                    row=2
                )
                self.upgrade_select.callback = self.upgrade_select_callback
                self.add_item(self.upgrade_select)

class Mora(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="mora", description="Check a user's mora inventory")
    @app_commands.describe(user="Specify any user other than yourself if needed")
    async def mora(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer(thinking=True)
        user = user or interaction.user

        user_ref = db.reference(f"/Mora/{user.id}")
        user_data = user_ref.get() or {}

        all_users = db.reference("/Mora").get() or {}
        global_ranking = []
        for uid_str, guilds in all_users.items():
            total = get_total_mora(guilds)
            global_ranking.append((int(uid_str), total))
        global_ranking.sort(key=lambda x: x[1], reverse=True)
        global_total = dict(global_ranking).get(user.id, 0)
        global_rank = next((i+1 for i,(uid,_) in enumerate(global_ranking) if uid == user.id), "N/A")

        guild_id = str(interaction.guild.id)
        guild_data = []
        for uid_str, guilds in all_users.items():
            amt = get_guild_mora(guilds, guild_id)
            if amt > 0:
                guild_data.append({"user_id": int(uid_str), "mora": amt})
        
        if guild_data:
            guild_df = pd.DataFrame(guild_data)
            guild_df = guild_df.sort_values("mora", ascending=False).reset_index(drop=True)
            user_row = guild_df[guild_df["user_id"] == user.id]
            guild_total = user_row["mora"].iloc[0] if len(user_row) > 0 else 0
            guild_rank = user_row.index[0] + 1 if len(user_row) > 0 else "N/A"
        else:
            guild_total = 0
            guild_rank = "N/A"

        def word(n):
            if n == "N/A":
                return "N/A"
            return str(n) + (
                "th"
                if 4 <= n % 100 <= 20
                else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
            )

        ref = db.reference("/User Events Inventory")
        inventories = ref.get()
        inv = "No </shop:1345883946105311383> items purchased yet"

        MAX_INV_LENGTH = 1024
        EXTRA_LENGTH = 15 

        if inventories:
            for key, val in inventories.items():
                if val["User ID"] == user.id:
                    try:
                        item_dict = {}
                        pinned_items = {}

                        for item in val["Items"]:
                            if len(item) > 3 and item[3] == interaction.guild.id:
                                if item[2] == 0:
                                    continue
                                role_id = item[0]
                                timestamp = item[4] if len(item) > 4 else 1741083000
                                is_pinned = len(item) > 5 and item[5] == "Pinned"

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
                            prefix = "📌 **Pinned:** " if pinned else "- "
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

                        break
                    except Exception as e:
                        print(e)

        # beta_amount = next(
        #     (
        #         val["Mora"]
        #         for val in db.reference("/Global Events Mora").get().values()
        #         if val["User ID"] == user.id
        #     ),
        #     0,
        # )
        # legacy = None
        # if beta_amount != 0:
        #     legacy = (
        #         f"\n-# <a:legacy:1345876714240213073> *Legacy Player: `{beta_amount}`*"
        #     )
            
        ref_selected = db.reference(f"/Global Progression Rewards/{interaction.guild.id}/{user.id}/selected")
        selected = ref_selected.get() or {}
        custom_color_hex = selected.get("embed_color_hex")
        custom_color = discord.Color(int(custom_color_hex, 16)) if custom_color_hex else None
        
        embed = discord.Embed(
            title=f"{user.display_name}'s Inventory",
            # description=f"{legacy if legacy is not None else ''}",
            description="",
            color=custom_color or discord.Color.gold()
        )

        if guild_rank != "N/A":
            embed.add_field(
                name=interaction.guild.name,
                value=f"Mora: {MORA_EMOTE} `{int(guild_total):,}`\n<:rank:1364439165189488854> Rank: **{word(guild_rank)}**",
                inline=True,
            )

        if global_rank != "N/A":
            embed.add_field(
                name="Global",
                value=f"Mora: {MORA_EMOTE} `{int(global_total):,}`\n<:rank:1364439165189488854> Rank: **{word(global_rank)}**",
                inline=True,
            )

        embed.add_field(name="Guild Inventory", value=inv, inline=False)
        
        milestones_ref = db.reference(f"/Milestones/{interaction.guild.id}")
        milestones = milestones_ref.get() or {}

        user_milestones = []
        if inventories:
            for key, val in inventories.items():
                if val["User ID"] == user.id:
                    for item in val.get("Items", []):
                        if len(item) > 3 and item[2] == 0 and item[3] == interaction.guild.id:
                            for milestone_id, milestone in milestones.items():
                                if milestone.get("reward") == item[0]:
                                    user_milestones.append({
                                        "threshold": milestone.get("threshold", 0),
                                        "reward": item[0],
                                        "description": item[1]
                                    })
                                    break

        user_milestones.sort(key=lambda x: x["threshold"], reverse=True)

        milestones_text = ""
        if user_milestones:
            user_milestones.sort(key=lambda x: x["threshold"])
            for ms in user_milestones:
                is_role = isinstance(ms["reward"], int) or str(ms["reward"]).isdigit()
                reward_display = f"<@&{ms['reward']}>" if is_role else ms["reward"]
                milestones_text += f"- {MORA_EMOTE} **`{ms['threshold']:,}`** - {reward_display}\n"
        else:
            milestones_text = "No </milestones:1380247962390888578> earned yet"
    
        embed.add_field(name="Server Milestones", value=milestones_text, inline=False)

        animated_background = selected.get("animated_background")
        profile_frame = selected.get("profile_frame")
        
        customized = os.path.isfile(f"./assets/Mora Inventory Background/{user.id}.png") or bool(profile_frame) or bool(animated_background)
            
        global_title_key = selected.get("global_title")
        global_title = None
        if global_title_key:
            global_ref = db.reference(f"/Global User Titles/{user.id}/global_titles")
            global_titles = global_ref.get() or {}
            if global_title_key in global_titles:
                title_data = global_titles[global_title_key]
                guild = self.bot.get_guild(int(title_data["guild_id"]))
                server_name = guild.name if guild else f"Server {title_data['guild_id']}"
                pin = ":round_pushpin:" if "<a:" not in title_data['name'] else ""
                global_title = (
                    f"### {pin}{title_data['name']} \n"
                    f"-# *<:reply:1036792837821435976> Earned from **{server_name}***"
                )

        if global_title:
            embed.description = f"{global_title}\n{embed.description}"

        if customized:
            if animated_background:
                bg_path = f"./assets/Animated Mora Inventory Background/{animated_background}.gif"
            else:
                bg_path = f"./assets/Mora Inventory Background/{user.id}.png"

            filename = await createProfileCard(
                user,
                f"{int(guild_total):,}",
                guild_rank,
                bg=bg_path,
                profile_frame=profile_frame if profile_frame else None
            )
            followup = False
        else:
            filename = await createProfileCard(user, f"{guild_total:,}", guild_rank)
            followup = True

        chn = interaction.client.get_channel(1026968305208131645)
        
        kingdom_ref = db.reference(f"/Kingdom/{interaction.guild.id}/{user.id}/buildings")
        k_data = kingdom_ref.get() or {}
        k_level = sum(k_data.values())
        if k_level > 0:
            rank_title = get_rank_title(k_level)
            
            current_footer = f"| {embed.footer.text}" if embed.footer else ""
            embed.set_footer(text=f"Kingdom Rank: {rank_title} (Lv. {k_level}) {current_footer}")

        msg_obj = await chn.send(file=discord.File(filename))
        url = msg_obj.attachments[0].proxy_url
        embed.set_image(url=url)

        view = ToggleView(embed, user.id, interaction.user.id, message=None, guild_id=interaction.guild.id, custom_color=custom_color)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message
        if followup:
            await interaction.followup.send("💡 Tip: Customize your inventory however you like (custom background, profile frame, titles) with </customize:1339721187953082544>!", ephemeral=True)

    @app_commands.command(name="gift", description="Gift mora to another user")
    @app_commands.describe(
        user="User to gift mora to",
        amount="Amount of mora to gift"
    )
    async def gift(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await interaction.response.defer()

        stats_ref = db.reference(f"/User Events Stats/{interaction.guild.id}/{interaction.user.id}")
        stats = stats_ref.get() or {}

        if "gift_tax" not in stats:
            return await interaction.followup.send("⏳ You haven't unlocked Mora gifting for this season yet. Unlock it at Tier `5` in the free track!")

        if amount <= 0:
            return await interaction.followup.send("<:no:1036810470860013639> Amount must be positive and non-zero!")

        if amount < 100:
            return await interaction.followup.send(f"<:no:1036810470860013639> The minimum amount to gift is {MORA_EMOTE} `100`!")

        if interaction.user == user:
            return await interaction.followup.send(f"<:no:1036810470860013639> You can't gift {MORA_EMOTE} to yourself!")
        
        if user.bot:
            return await interaction.followup.send(f"<:no:1036810470860013639> Why would you waste your {MORA_EMOTE} on a non-human being?")

        tax_rate = stats["gift_tax"]
        tax_amount = int(amount * tax_rate / 100)
        total_cost = amount + tax_amount

        ref = db.reference(f"/Mora/{interaction.user.id}")
        user_data = ref.get() or {}
        donor_mora = get_guild_mora(user_data, str(interaction.guild.id))
                    
        if donor_mora < total_cost:
            return await interaction.followup.send(
                f"You need {MORA_EMOTE} `{total_cost}` ({amount} + {tax_rate}% tax) to make this gift! \n-# You currently only have {MORA_EMOTE} `{donor_mora}`."
            )

        await addMora(interaction.user.id, -total_cost, interaction.channel.id, interaction.guild.id, interaction.client) # Donor
        await addMora(user.id, amount, interaction.channel.id, interaction.guild.id, interaction.client) # Recipient
        await addMora(interaction.client.user.id, tax_amount, interaction.channel.id, interaction.guild.id, interaction.client) # Tax

        await interaction.followup.send(
            embed=discord.Embed(
                title="<a:2_star:1366158196213022800> Gift Sent!",
                description=(
                    f"{interaction.user.mention} gifted {MORA_EMOTE} `{amount}` to {user.mention}\n"
                    f"-# Fischl also collected {MORA_EMOTE} `{tax_amount}` ({tax_rate}%) in taxes"
                ),
                color=discord.Color.green()
            )
        )
        await update_quest(interaction.user.id, interaction.guild.id, interaction.channel.id, {"gift_mora": amount, "gift_mora_unique": user.id}, interaction.client)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Mora(bot))