import discord
import os
import time

from firebase_admin import db

from commands.Events.dropPack import create_drop_pack
from commands.Events.seasons import get_current_season
from utils.commands import SlashCommand

from commands.Events.config import MORA_EMOTE, COSMETICS_DB, REWARD_TYPES, CURRENCY_NAME

def get_current_track():
    season = get_current_season()
    return season.track_data if season else []

async def grant_reward(guild_id, user_id, reward_str, tier, channel, is_elite=False, client=None, pool=None):
    if is_elite:
        elite_claimed_ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/elite_claimed")
        elite_claimed = elite_claimed_ref.get() or []
        if tier in elite_claimed:
            return (None, None)
        if tier != "Bonus":
            elite_claimed.append(tier)
            elite_claimed_ref.set(elite_claimed)
        
    reward_type = REWARD_TYPES.get(reward_str.split("|")[0].strip(), "other")
    title = None
    description = None
    
    if pool is None:
        # Fallback if pool not provided
        from commands.Events.helperFunctions import get_user_stats
        stats = {"mora_boost": 0, "chest_upgrades": 4, "gift_tax": None, "minigame_summons": 0}
    else:
        from commands.Events.helperFunctions import get_user_stats
        stats = await get_user_stats(pool, guild_id, user_id)
    
    if reward_type == "drop_pack":
        is_bonus = tier == "Bonus"
        message = await create_drop_pack(guild_id, user_id, channel, is_elite, is_bonus, tier)
        if client:
            from commands.Events.quests import update_quest
            await update_quest(user_id, guild_id, channel.id, {"unlock_drop_packs": 1}, client)
        if is_bonus:
            title = f"{'Elite ' if is_elite else ''}New Bonus Drop Pack"
            description = "**Bonus:** "
        else:
            title = f"{'Elite Reward: ' if is_elite else ''}New Drop Pack"
            description = f"**Tier `{tier}`:** "
        description += f"You can claim your drop pack [here]({message.jump_url})!"
        
    elif reward_type == "animated_background":
        ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/animated_backgrounds")
        backgrounds = ref.get() or []
        reward_file_name = reward_str.split('|')[1].strip()
        background_name = f"{reward_file_name.split('/')[2].split('.')[0].strip()}"
        if background_name not in backgrounds:
            backgrounds.append(background_name)
            ref.set(backgrounds)
            title = f"{'Elite Reward: ' if is_elite else ''} Animated Inventory Background Unlocked 🖼️"
            description = f"**Tier `{tier}`:** You have unlocked **{background_name}**! Use {SlashCommand('customize')} to equip it in this server!"

    elif reward_type == "custom_gif_background":
        ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/selected")
        selected = ref.get() or {}
        selected["animated_background_unlocked"] = True
        ref.set(selected)
        title = f"{'Elite Reward: ' if is_elite else ''} Custom GIF Background Unlocked 🖼️"
        description = f"**Tier `{tier}`:** You can now upload and use a custom animated GIF background with {SlashCommand('customize')}!"

    elif reward_type == "font_unlock":
        ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/selected")
        selected = ref.get() or {}
        selected["font_unlocked"] = True
        ref.set(selected)
        title = f"{'Elite Reward: ' if is_elite else ''} Custom Card Font Unlocked 🔤"
        description = f"**Tier `{tier}`:** You can now select an Elite Track font preset with {SlashCommand('customize')}!"
        
    elif reward_type == "title":
        title_parts = reward_str.split('|')
        title_name = title_parts[1].strip() if len(title_parts) > 1 else reward_str
        cosmetics_ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/titles")
        titles = cosmetics_ref.get() or {}
        timestamp = str(int(time.time() * 1000))
        titles[timestamp] = {"name": title_name}
        cosmetics_ref.set(titles)
        title = f"{'Elite Reward: ' if is_elite else ''} Server Title Unlocked 📍"
        description = f"**Tier `{tier}`:** You have unlocked **{title_name}**! Use {SlashCommand('customize')} to equip it in this server!"
            
    elif reward_type == "static_frame" or reward_type == "animated_frame":
        ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/profile_frames")
        profile_frames = ref.get() or []
        reward_file_name = reward_str.split('|')[1].strip()
        frame_name = os.path.basename(reward_file_name)
        if frame_name not in profile_frames:
            profile_frames.append(frame_name)
            ref.set(profile_frames)
            title = f"{'Elite Reward: ' if is_elite else ''} {'Static' if 'static' in reward_type else '**Animated**'} Profile Frame Unlocked 👤"
            description = f"**Tier `{tier}`:** You have unlocked **{frame_name.split('.')[0]}**! Use {SlashCommand('customize')} to equip it in this server!"
            
    elif reward_type == "accent_color" or reward_type == "embed_color":
        ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/embed_color")
        ref.set(True)
        title = f"{'Elite Reward: ' if is_elite else ''} Custom Accent Color Unlocked 🎨"
        description = f"**Tier `{tier}`:** You can have a custom accent color on your inventory and profile card! Use {SlashCommand('customize')} to edit your favorite color!"

    elif reward_type == "custom_title":
        ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/selected")
        selected = ref.get() or {}
        selected["custom_title_unlocked"] = True
        ref.set(selected)
        title = f"{'Elite Reward: ' if is_elite else ''} Custom Title Unlocked 📍"
        description = f"**Tier `{tier}`:** You can now set a custom text title with {SlashCommand('customize')}!"

    elif reward_type == "express_daily_chests":
        from commands.Events.helperFunctions import update_express_daily_chests
        await update_express_daily_chests(pool, guild_id, user_id, True)
        title = f"{'Elite Reward: ' if is_elite else ''} Express Daily Chests ⚡"
        description = f"**Tier `{tier}`:** Your daily chest will now spawn after **1 effortful message** in minigame channels."
            
    elif reward_type == "prestige":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE minigame_progression SET prestige = prestige + 1, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                guild_id, user_id
            )
        title = f"{'Elite Reward: ' if is_elite else ''} Prestige +1 <:PRIMOGEM:1364031230357540894>"
        description = f"You have earned `+1` prestige for **reaching the end of the {'elite' if is_elite else 'free'} track**! Use {SlashCommand('mora')} to view your prestige count!"
        
    elif reward_type == "mora_boost" or reward_type == "mora_boost_67":
        boost_amount = 5 if reward_type == "mora_boost" else 67
        from commands.Events.helperFunctions import get_mora_boost, update_mora_boost
        current_boost = await get_mora_boost(pool, guild_id, user_id)
        new_boost = current_boost + boost_amount
        await update_mora_boost(pool, guild_id, user_id, new_boost)
        title = f"{'Elite Reward: ' if is_elite else ''}{CURRENCY_NAME} Gain Boost +{boost_amount}% {MORA_EMOTE}"
        description = f"**Tier `{tier}`:** Your {CURRENCY_NAME} gain from all sources will now be **increased by `{new_boost}%`**!"
    
    elif reward_type == "chest_upgrade" or reward_type == "chest_upgrade_69":
        upgrade_amount = 1 if reward_type == "chest_upgrade" else 69
        from commands.Events.helperFunctions import get_chest_upgrades
        current_upgrades = await get_chest_upgrades(pool, guild_id, user_id)
        new_upgrades = current_upgrades + upgrade_amount
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE minigame_progression SET chest_upgrades = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                guild_id, user_id, new_upgrades
            )
        title = f"{'Elite Reward: ' if is_elite else ''}+{upgrade_amount} Chest Upgrades :arrow_up_small:"
        description = f"**Tier `{tier}`:** Your daily chest now has a total of **`{new_upgrades}` upgrade chances**!"
    
    elif reward_type == "unlock_gifting":
        if stats.get("gift_tax") is None:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE minigame_progression SET gift_tax = 30, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                    guild_id, user_id
                )
            title = f"{CURRENCY_NAME} Gifting Unlocked! :gift:"
            description = f"**Tier `{tier}`:** You can now {SlashCommand('gift')} {CURRENCY_NAME} to others with an initial tax rate of `30%`!"
    
    elif reward_type == "gift_tax":
        tax_reduction = 5
        current_tax = stats.get("gift_tax", 30) if stats.get("gift_tax") is not None else 30
        new_tax = max(0, current_tax - tax_reduction)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE minigame_progression SET gift_tax = $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2",
                guild_id, user_id, new_tax
            )
        title = f"{'Elite Reward: ' if is_elite else ''}Gift Tax Reduced -{tax_reduction}% :chart_with_downwards_trend:"
        description = f"**Tier `{tier}`:** Your gifting tax rate is now **`{new_tax}%`**! Use {SlashCommand('gift')} to send some love!"
    
    elif reward_type == "minigame_summon" or reward_type == "minigame_summon_30":
        summon_amount = 30 if reward_type == "minigame_summon_30" else int(reward_str.split()[0].replace('+', '')) # Extract summon amount (e.g., "+3" from "+3 Minigames Summon")
        async with pool.acquire() as conn:
            new_summons = await conn.fetchval(
                "UPDATE minigame_progression SET minigame_summons = minigame_summons + $3, updated_at = CURRENT_TIMESTAMP WHERE gid = $1 AND uid = $2 RETURNING minigame_summons",
                guild_id, user_id, summon_amount
            )
        title = f"{'Elite Reward: ' if is_elite else ''}+{summon_amount} Minigame Summons 🧲"
        description = f"**Tier `{tier}`:** You have a total of **{new_summons} minigame summons** available! Use {SlashCommand('summon')} to immediately start a minigame in a channel!"

    elif reward_type == "shop_discount":
        from commands.Events.helperFunctions import get_shop_discount, update_shop_discount
        current_discount = await get_shop_discount(pool, guild_id, user_id)
        new_discount = min(50, current_discount + 10)
        await update_shop_discount(pool, guild_id, user_id, new_discount)
        title = f"{'Elite Reward: ' if is_elite else ''} Shop Discount +10% 🏷️"
        description = f"**Tier `{tier}`:** Your shop purchases now get a **{new_discount}% discount**."

    elif reward_type == "domain_discount":
        from commands.Events.helperFunctions import get_domain_discount, update_domain_discount
        current_discount = await get_domain_discount(pool, guild_id, user_id)
        new_discount = min(50, current_discount + 10)
        await update_domain_discount(pool, guild_id, user_id, new_discount)
        title = f"{'Elite Reward: ' if is_elite else ''} Domain Discount +10% 🏰"
        description = f"**Tier `{tier}`:** Your domain upgrades now get a **{new_discount}% discount**."

    return (title, description)

async def check_tier_rewards(guild_id, user_id, old_xp, new_xp, channel, client=None, pool=None):
    unlocked_tiers = []
    TRACK_DATA = get_current_track()
    for tier in TRACK_DATA:
        if old_xp < tier["cumulative_xp"] <= new_xp:
            unlocked_tiers.append(tier)
    
    embed = discord.Embed(color=0xffd700)
    elite_embed = discord.Embed(color=0xfa0add)
    for tier in unlocked_tiers:
        title, description = await grant_reward(guild_id, user_id, tier["free"], tier["tier"], channel, client=client, pool=pool)
        if title is not None and description is not None:
            embed.add_field(name=title, value=f"-# {description}", inline=False)
        
        if is_elite_active(user_id, guild_id):
            title, description = await grant_reward(guild_id, user_id, tier["elite"], tier["tier"], channel, is_elite=True, client=client, pool=pool)
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
            await grant_reward(guild_id, user_id, "Drop Pack", "Bonus", channel, client=client, pool=pool)
            
            if is_elite_active(user_id, guild_id):
                await grant_reward(guild_id, user_id, "Drop Pack", "Bonus", channel, is_elite=True, client=client, pool=pool)

    return (embed, elite_embed)

async def grant_elite_rewards_up_to_tier(guild_id, user_id, channel, max_xp, client=None, pool=None):
    elite_claimed_ref = db.reference(f"{COSMETICS_DB}/{guild_id}/{user_id}/elite_claimed")
    elite_claimed = elite_claimed_ref.get() or []
    
    rewards_granted = []
    TRACK_DATA = get_current_track()
    for tier in TRACK_DATA:
        if tier["cumulative_xp"] <= max_xp and tier["tier"] not in elite_claimed:
            await grant_reward(guild_id, user_id, tier["elite"], tier["tier"], channel, is_elite=True, client=client, pool=pool)
            rewards_granted.append(f"Tier {tier['tier']}: {tier['elite'].split('|')[0].strip()}")
    
    max_tier_xp = TRACK_DATA[-1]["cumulative_xp"]
    if max_xp > max_tier_xp:
        total_bonus_tiers = (max_xp - max_tier_xp) // 2500
        
        for _ in range(total_bonus_tiers):
            await grant_reward(guild_id, user_id, "Drop Pack", "Bonus", channel, is_elite=True, client=client, pool=pool)
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