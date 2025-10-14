import discord
import time

from firebase_admin import db

from commands.Events.dropPack import create_drop_pack
from commands.Events.seasons import get_current_season

MORA_EMOTE = "<:MORA:1364030973611610205>"

def get_current_track():
    season = get_current_season()
    return season.track_data if season else []

REWARD_TYPES = {
    "Drop Pack": "drop_pack",
    "Animated Background": "animated_background",
    "Static Frame": "static_frame",
    "Animated Frame": "animated_frame",
    "Prestige +1": "prestige",
    "Mora Gain Boost +5%": "mora_boost",
    "+1 Chest Upgrade Limit": "chest_upgrade",
    "Unlocks Mora Gifting": "unlock_gifting",
    "Mora Gift Tax -5%": "gift_tax",
    "+3 Minigames Summon": "minigame_summon",
    "Custom Embed Color": "embed_color",
    "Global Title": "global_title",
    "Animated Badge Title": "global_title"
}

async def grant_reward(guild_id, user_id, reward_str, tier, channel, is_elite=False):
    if is_elite:
        elite_claimed_ref = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/elite_claimed")
        elite_claimed = elite_claimed_ref.get() or []
        if tier in elite_claimed:
            return
        if tier != "Bonus":
            elite_claimed.append(tier)
            elite_claimed_ref.set(elite_claimed)
        
    reward_type = REWARD_TYPES.get(reward_str.split("|")[0].strip(), "other")
    title = None
    description = None
    stats_ref = db.reference(f"/User Events Stats/{guild_id}/{user_id}")
    stats = stats_ref.get() or {}
    
    if reward_type == "drop_pack":
        is_bonus = tier == "Bonus"
        message = await create_drop_pack(guild_id, user_id, channel, is_elite, is_bonus, tier)
        if is_bonus:
            title = f"{'Elite ' if is_elite else ''}New Bonus Drop Pack"
            description = "**Bonus:** "
        else:
            title = f"{'Elite Reward: ' if is_elite else ''}New Drop Pack"
            description = f"**Tier `{tier}`:** "
        description += f"You can claim your drop pack [here]({message.jump_url})!"
        
    elif reward_type == "animated_background":
        ref = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/animated_backgrounds")
        backgrounds = ref.get() or []
        reward_file_name = reward_str.split('|')[1].strip()
        background_name = f"{reward_file_name.split('/')[2].split('.')[0].strip()}"
        if background_name not in backgrounds:
            backgrounds.append(background_name)
            ref.set(backgrounds)
            title = f"{'Elite Reward: ' if is_elite else ''} Animated Inventory Background Unlocked 🖼️"
            description = f"**Tier `{tier}`:** You have unlocked **{background_name}**! Use </customize:1339721187953082544> to equip it in this server!"
        
    elif reward_type == "global_title":
        title_parts = reward_str.split('|')
        title_name = title_parts[1].strip() if len(title_parts) > 1 else reward_str
        global_ref = db.reference(f"/Global User Titles/{user_id}/global_titles")
        titles = global_ref.get() or {}
        unique_key = f"{guild_id}_{int(time.time() * 1000)}"
        titles[unique_key] = {
            "name": title_name,
            "guild_id": guild_id,
            "timestamp": int(time.time())
        }
        global_ref.set(titles)
        title = f"{'Elite Reward: ' if is_elite else ''} Global Title Unlocked 📍"
        description = f"**Tier `{tier}`:** You have unlocked **{title_name}**! Use </customize:1339721187953082544> to equip it globally!"
            
    elif reward_type == "static_frame" or reward_type == "animated_frame":
        ref = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/profile_frames")
        profile_frames = ref.get() or []
        reward_file_name = reward_str.split('|')[1].strip()
        frame_name = f"{reward_file_name.split('/')[2].strip()}"
        if frame_name not in profile_frames:
            profile_frames.append(frame_name)
            ref.set(profile_frames)
            title = f"{'Elite Reward: ' if is_elite else ''} {'Static' if 'static' in reward_type else '**Animated**'} Profile Frame Unlocked 👤"
            description = f"**Tier `{tier}`:** You have unlocked **{frame_name.split('.')[0]}**! Use </customize:1339721187953082544> to equip it in this server!"
            
    elif reward_type == "embed_color":
        ref = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/embed_color")
        ref.set(True)
        title = f"{'Elite Reward: ' if is_elite else ''} Custom Embed Color Unlocked 🎨"
        description = f"**Tier `{tier}`:** You can have a custom color on your inventory! Use </customize:1339721187953082544> to edit your favorite color!"
            
    elif reward_type == "prestige":
        ref = db.reference(f"/Progression/{guild_id}/{user_id}")
        data = ref.get() or {"xp": 0, "prestige": 0}
        prestige = data.get("prestige", 0)
        prestige += 1
        ref.update({"prestige": prestige})
        title = f"{'Elite Reward: ' if is_elite else ''} Prestige +1 <:PRIMOGEM:1364031230357540894>"
        description = f"You have earned `+1` prestige for **reaching the end of the {'elite' if is_elite else 'free'} track**! Use </mora:1339721187953082543> view your prestige count!"
        
    elif reward_type == "mora_boost":
        boost_amount = 5
        new_boost = stats.get("mora_boost", 0) + boost_amount
        stats_ref.update({"mora_boost": new_boost})
        title = f"{'Elite Reward: ' if is_elite else ''}Mora Gain Boost +{boost_amount}% {MORA_EMOTE}"
        description = f"**Tier `{tier}`:** Your mora gain from all sources will now be **increased by `{new_boost}%`**!"
    
    elif reward_type == "chest_upgrade":
        upgrade_amount = 1
        current_upgrades = stats.get("chest_upgrades", 4)
        new_upgrades = current_upgrades + upgrade_amount
        stats_ref.update({"chest_upgrades": new_upgrades})
        title = f"{'Elite Reward: ' if is_elite else ''}+{upgrade_amount} Chest Upgrades :arrow_up_small:"
        description = f"**Tier `{tier}`:** Your daily Mora chest now has a total of **`{new_upgrades}` upgrade chances**!"
    
    elif reward_type == "unlock_gifting":
        if "gift_tax" not in stats:
            stats_ref.update({"gift_tax": 30})
            title = "Mora Gifting Unlocked! :gift:"
            description = f"**Tier `{tier}`:** You can now </gift:1382148690155802657> mora to others with an initial tax rate of `30%`!"
    
    elif reward_type == "gift_tax":
        tax_reduction = 5
        current_tax = stats.get("gift_tax", 30)
        new_tax = max(0, current_tax - tax_reduction)  # Minimum 0% tax
        stats_ref.update({"gift_tax": new_tax})
        title = f"{'Elite Reward: ' if is_elite else ''}Gift Tax Reduced -{tax_reduction}% :chart_with_downwards_trend:"
        description = f"**Tier `{tier}`:** Your gifting tax rate is now **`{new_tax}%`**! Use </gift:1382148690155802657> to send some love!"
    
    elif reward_type == "minigame_summon":
        summon_amount = int(reward_str.split()[0].replace('+', '')) # Extract summon amount (e.g., "+3" from "+3 Minigames Summon")
        current_summons = stats.get("minigame_summons", 0)
        new_summons = current_summons + summon_amount
        stats_ref.update({"minigame_summons": new_summons})
        title = f"{'Elite Reward: ' if is_elite else ''}+{summon_amount} Minigame Summons 🧲"
        description = f"**Tier `{tier}`:** You have a total of **{new_summons} minigame summons** available! Use </summon:1382148690155802656> to immediately start a minigame in a channel!"

    return (title, description)

async def check_tier_rewards(guild_id, user_id, old_xp, new_xp, channel):
    unlocked_tiers = []
    TRACK_DATA = get_current_track()
    for tier in TRACK_DATA:
        if old_xp < tier["cumulative_xp"] <= new_xp:
            unlocked_tiers.append(tier)
    
    embed = discord.Embed(color=0xffd700)
    elite_embed = discord.Embed(color=0xfa0add)
    for tier in unlocked_tiers:
        title, description = await grant_reward(guild_id, user_id, tier["free"], tier["tier"], channel)
        if title is not None and description is not None:
            embed.add_field(name=title, value=f"-# {description}", inline=False)
        
        if is_elite_active(user_id, guild_id):
            title, description = await grant_reward(guild_id, user_id, tier["elite"], tier["tier"], channel, is_elite=True)
            if title is not None and description is not None:
                elite_embed.add_field(name=title, value=f"-# {description}", inline=False)
    
    if len(embed.fields) > 0:
        embed.title = "🏆 Tiers Achieved"
        embed.description = f"<@{user_id}>, you have reached **`{len(embed.fields)}`** new tier{'s' if len(embed.fields) > 1 else ''} and unlocked the following reward{'s' if len(embed.fields) > 1 else ''}!"
    
    if len(elite_embed.fields) > 0:
        elite_embed.title = "🏆 Elite Tiers Achieved"
        
    max_tier_xp = TRACK_DATA[-1]["cumulative_xp"]
    if new_xp > max_tier_xp:
        old_bonus_tiers = max((old_xp - max_tier_xp) // 2500, 0)
        new_bonus_tiers = (new_xp - max_tier_xp) // 2500
        bonus_tiers_earned = new_bonus_tiers - old_bonus_tiers
        
        for _ in range(bonus_tiers_earned):
            await grant_reward(guild_id, user_id, "Drop Pack", "Bonus", channel)
            
            if is_elite_active(user_id, guild_id):
                await grant_reward(guild_id, user_id, "Drop Pack", "Bonus", channel, is_elite=True)

    return (embed, elite_embed)

async def grant_elite_rewards_up_to_tier(guild_id, user_id, channel, max_xp):
    elite_claimed_ref = db.reference(f"/Global Progression Rewards/{guild_id}/{user_id}/elite_claimed")
    elite_claimed = elite_claimed_ref.get() or []
    
    rewards_granted = []
    TRACK_DATA = get_current_track()
    for tier in TRACK_DATA:
        if tier["cumulative_xp"] <= max_xp and tier["tier"] not in elite_claimed:
            await grant_reward(guild_id, user_id, tier["elite"], tier["tier"], channel, is_elite=True)
            rewards_granted.append(f"Tier {tier['tier']}: {tier['elite'].split('|')[0].strip()}")
    
    max_tier_xp = TRACK_DATA[-1]["cumulative_xp"]
    if max_xp > max_tier_xp:
        total_bonus_tiers = (max_xp - max_tier_xp) // 2500
        
        for _ in range(total_bonus_tiers):
            await grant_reward(guild_id, user_id, "Drop Pack", "Bonus", channel, is_elite=True)
            rewards_granted.append(f"Bonus Drop Pack")
    
    return rewards_granted

def load_elite_subscriptions():
    try:
        elite_track_ref = db.reference("/Elite Track")
        return elite_track_ref.get() or {}
    except Exception:
        return {}

def save_elite_subscriptions(subscriptions):
    try:
        elite_track_ref = db.reference("/Elite Track")
        elite_track_ref.set(subscriptions)
    except Exception:
        pass

def is_elite_active(user_id, guild_id):
    subscriptions = load_elite_subscriptions()
    key = f"{user_id}-{guild_id}"
    if key in subscriptions:
        return time.time() < subscriptions[key]["expires_at"]
    return False

async def setup(bot):
    pass