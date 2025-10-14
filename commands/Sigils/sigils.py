import discord
import random 
import asyncio
import time
import re

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import View, Modal, TextInput
from difflib import SequenceMatcher

SIGIL_EMOTE = "<a:sigils:1402736987902967850>"
NO_EMOTE = "<:no:1036810470860013639>"
DEFAULT_MAX_DAILY_SIGILS = 60

class PersistentSigilsInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="What is this?",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_sigils_info_view",
        emoji="<:PinkConfused:1204614149628498010>",
    )
    async def persistentSigilsInfoView(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title=f"What Are Sigils? <:AlbedoQuestion:1191574408544923799>",
            description=f"-# Earn {SIGIL_EMOTE} **Sigils** by chatting actively and use them to enter giveaways!",
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SigilSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_cooldowns = {}
        self.message_counts = {}
        self.last_messages = {}
        self.earnings_cache = {}
        self.enabled_guilds_cache = {}
        self.server_config_cache = {}
        self.guild_config_check_cache = set()

    def _get_server_ref(self, guild_id: int):
        return db.reference(f'Sigils System/{guild_id}')

    def _get_user_ref(self, guild_id: int, user_id: int):
        return db.reference(f'Sigils System/{guild_id}/User Sigils/{user_id}')

    async def is_enabled(self, guild_id: int):
        if guild_id in self.enabled_guilds_cache:
            return self.enabled_guilds_cache[guild_id]
        
        ref = self._get_server_ref(guild_id)
        data = ref.get() or {}
        enabled = data.get('enabled', False)
        
        self.enabled_guilds_cache[guild_id] = enabled
        return enabled
    
    async def get_server_config(self, guild_id: int):
        if guild_id in self.server_config_cache:
            return self.server_config_cache[guild_id]
            
        ref = self._get_server_ref(guild_id)
        data = ref.get() or {}
        config = {
            'enabled': data.get('enabled', False),
            'max_daily_sigils': data.get('max_daily_sigils', DEFAULT_MAX_DAILY_SIGILS),
            'role_bonuses': data.get('role_bonuses', {}),
            'blacklisted_channels': data.get('blacklisted_channels', []) 
        }
        
        self.server_config_cache[guild_id] = config
        self.enabled_guilds_cache[guild_id] = config['enabled']
        return config

    async def update_guild_cache(self, guild_id: int):
        if guild_id in self.server_config_cache:
            del self.server_config_cache[guild_id]
        if guild_id in self.enabled_guilds_cache:
            del self.enabled_guilds_cache[guild_id]
        
        self.guild_config_check_cache.add(guild_id)

    async def add_sigils(self, guild_id: int, user_id: int, amount: int):
        ref = self._get_user_ref(guild_id, user_id)
        data = ref.get() or {'balance': 0}
        new_balance = data['balance'] + amount
        ref.update({'balance': new_balance})
        return new_balance

    async def deduct_sigils(self, guild_id: int, user_id: int, amount: int):
        ref = self._get_user_ref(guild_id, user_id)
        data = ref.get() or {'balance': 0}
        if data['balance'] < amount:
            return False
        new_balance = data['balance'] - amount
        ref.update({'balance': new_balance})
        return True

    async def get_balance(self, guild_id: int, user_id: int):
        ref = self._get_user_ref(guild_id, user_id)
        data = ref.get() or {'balance': 0}
        return data['balance']

    def is_effortful_message(self, message: str, user_id: int) -> tuple[bool, str]:
        content = message.strip()
        if len(content) < 5:
            return False, "Too short"
        if re.fullmatch(r"(\s*<a?:\w+:\d+>\s*){1,4}", content):
            return False, "Only emojis"
        if re.search(r"(https?:\/\/|www\.|discord\.gg\/)", content.lower()):
            return False, "Contains links"
        last_msg = self.last_messages.get(user_id, "")
        if last_msg:
            similarity = SequenceMatcher(None, last_msg.lower(), content.lower()).ratio()
            if similarity > 0.9:
                return False, "Too similar to previous"
        return True, "Effortful"

    async def calculate_max_daily_sigils(self, guild: discord.Guild, member: discord.Member):
        config = await self.get_server_config(guild.id)
        if not config['enabled']:
            return 0
            
        max_sigils = config['max_daily_sigils']
        
        role_bonuses = config.get('role_bonuses', {})
        for role_id, bonus in role_bonuses.items():
            if role_id in [str(r.id) for r in member.roles]:
                if bonus.startswith('+'):
                    max_sigils += int(bonus[1:])
                else:
                    max_sigils = max(max_sigils, int(bonus))
        
        return max_sigils

    async def process_message(self, message):
        if message.author.bot or not message.guild:
            return
            
        if not await self.is_enabled(message.guild.id):
            return

        config = await self.get_server_config(message.guild.id)
        blacklisted_channels = config.get('blacklisted_channels', [])
        
        if (str(message.channel.id) in blacklisted_channels or 
            (message.channel.category and str(message.channel.category.id) in blacklisted_channels)):
            return

        max_daily_sigils = await self.calculate_max_daily_sigils(message.guild, message.author)
        if max_daily_sigils <= 0:
            return

        user_id = message.author.id
        current_time = time.time()

        if user_id not in self.user_cooldowns:
            self.user_cooldowns[user_id] = 0
            self.message_counts[user_id] = 0

        if current_time - self.user_cooldowns[user_id] < 5:
            return

        valid, reason = self.is_effortful_message(message.content, user_id)
        if not valid:
            return

        self.user_cooldowns[user_id] = current_time
        self.message_counts[user_id] += 1
        self.last_messages[user_id] = message.content.strip()

        if user_id in self.earnings_cache:
            earnings_data = self.earnings_cache[user_id]
        else:
            ref = db.reference(f"Sigils System/{message.guild.id}/Daily Sigil Earnings/{user_id}")
            data = ref.get() or {"earnings": 0, "reset_time": 0}
            earnings_data = data
            self.earnings_cache[user_id] = earnings_data

        reset_time = earnings_data["reset_time"]
        if current_time > reset_time:
            earnings_data["earnings"] = 0
            earnings_data["reset_time"] = current_time + 86400

        if earnings_data["earnings"] >= max_daily_sigils:
            return

        if self.message_counts[user_id] < random.randint(15, 20):
            return

        self.message_counts[user_id] = 0

        sigils_earned = random.randint(19, 25)
        if earnings_data["earnings"] + sigils_earned > max_daily_sigils:
            sigils_earned = max_daily_sigils - earnings_data["earnings"]
        
        earnings_data["earnings"] += int(sigils_earned)
        await self.add_sigils(message.guild.id, user_id, sigils_earned)
        
        ref = db.reference(f"Sigils System/{message.guild.id}/Daily Sigil Earnings/{user_id}")
        ref.set(earnings_data)

        try:
            reset_time = earnings_data["reset_time"]
            await message.channel.send(
                f"<:SigewinneHappy:1287803663842152458> {message.author.mention} earned {SIGIL_EMOTE} **{sigils_earned} Sigils** "
                f"for chatting actively! *(Daily Cap: `{earnings_data['earnings']}/{int(max_daily_sigils)}`)*\n"
                f"> -# <a:clock:1382887924273774754> Resets <t:{int(reset_time)}:R>. Use </sigils:1402740034603319569> to check your progress!"
            )
        except:
            pass

    @app_commands.command(name="sigils", description="Check your Sigil balance and daily progress")
    async def sigils(self, interaction: discord.Interaction):
        if not await self.is_enabled(interaction.guild.id):
            return await interaction.response.send_message(
                f"{NO_EMOTE} The Sigil system is not enabled in this server. Admins can enable it with `/giveaway enable`.",
                ephemeral=True
            )
            
        user_id = interaction.user.id
        balance = await self.get_balance(interaction.guild.id, user_id)
        
        ref = db.reference(f"Sigils System/{interaction.guild.id}/Daily Sigil Earnings/{user_id}")
        earnings_data = ref.get() or {"earnings": 0, "reset_time": 0}
        reset_time = earnings_data["reset_time"]
        
        max_daily_sigils = await self.calculate_max_daily_sigils(interaction.guild, interaction.user)
        
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Sigils",
            color=discord.Color.purple()
        )
        embed.add_field(name=f"{SIGIL_EMOTE} Balance", value=f"`{balance}`", inline=True)
        embed.add_field(
            name="Daily Chat Progress", 
            value=f"`{earnings_data['earnings']}/{int(max_daily_sigils)}` Sigils earned",
            inline=True
        )
        embed.add_field(
            name="Reset Time", 
            value=f"<t:{int(reset_time)}:R>" if reset_time > time.time() else "Available now!",
            inline=True
        )
        
        config = await self.get_server_config(interaction.guild.id)
        if config.get('role_bonuses'):
            bonus_text = []
            for role_id, bonus in config['role_bonuses'].items():
                role = interaction.guild.get_role(int(role_id))
                if role:
                    if role in interaction.user.roles:
                        bonus_text.append(f"{role.mention}: `{bonus}` <:yes:1036811164891480194>")
                    else:
                        bonus_text.append(f"-# {role.mention}: `{bonus}`")

            if bonus_text:
                embed.add_field(
                    name="Role Bonuses to Max Sigils",
                    value="\n".join(bonus_text),
                    inline=False
                )
        
        embed.set_footer(text="🔻 Click this button to learn more!")
        
        await interaction.response.send_message(embed=embed, view=PersistentSigilsInfoView())

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
            
        guild_id = message.guild.id
        if guild_id in self.enabled_guilds_cache:
            if not self.enabled_guilds_cache[guild_id]:
                return
        else:
            if guild_id not in self.guild_config_check_cache:
                enabled = await self.is_enabled(guild_id)
                if not enabled:
                    self.guild_config_check_cache.add(guild_id)
                    return

        await self.process_message(message)

class GiveawayEntryView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.primary, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button): 
        giveaway_id = self.extract_giveaway_id(interaction)
        if not giveaway_id:
            await interaction.response.send_message("This giveaway message is invalid.", ephemeral=True)
            return

        await handle_join(interaction, giveaway_id)
        
    @discord.ui.button(label="Get Extra Entries", style=discord.ButtonStyle.green, custom_id="giveaway_extra")
    async def extra(self, interaction: discord.Interaction, button: discord.ui.Button): 
        giveaway_id = self.extract_giveaway_id(interaction)
        if not giveaway_id:
            await interaction.response.send_message("This giveaway message is invalid.", ephemeral=True)
            return

        await handle_extra(interaction, giveaway_id)

    @discord.ui.button(label="View My Entries", style=discord.ButtonStyle.secondary, custom_id="giveaway_view")
    async def view_entries(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_id = self.extract_giveaway_id(interaction)
        if not giveaway_id:
            await interaction.response.send_message("This giveaway message is invalid.", ephemeral=True)
            return
            
        await handle_view_entries(interaction, giveaway_id)

    @staticmethod
    def extract_giveaway_id(interaction: discord.Interaction) -> str:
        if not interaction.message.embeds:
            return None
            
        embed = interaction.message.embeds[0]
        if not embed.footer or not embed.footer.text:
            return None
            
        parts = embed.footer.text.split()
        if len(parts) < 3 or parts[-2] != "ID:":
            return None
            
        return parts[-1].strip()

class LeaveGiveawayView(View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=300)
        self.giveaway_id = giveaway_id
        
    @discord.ui.button(label="Leave Giveaway", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_leave(interaction, self.giveaway_id)

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int):
        super().__init__(
            placeholder="Select channels/categories to toggle blacklist",
            min_values=0,
            max_values=25,
        )
        self.guild_id = guild_id
        
    async def callback(self, interaction: discord.Interaction):
        ref = db.reference(f'Sigils System/{self.guild_id}')
        data = ref.get() or {}
        current_blacklist = data.get('blacklisted_channels', [])
        
        new_blacklist = current_blacklist.copy()
        for channel in self.values:
            channel_id = str(channel.id)
            if channel_id in new_blacklist:
                new_blacklist.remove(channel_id) 
            else:
                new_blacklist.append(channel_id) 
        
        ref.update({'blacklisted_channels': new_blacklist})
        
        sigil_cog = interaction.client.get_cog("SigilSystem")
        if sigil_cog:
            await sigil_cog.update_guild_cache(self.guild_id)
        
        if new_blacklist:
            channel_mentions = [f"- <#{cid}>" for cid in new_blacklist]
            blacklist_text = "\n".join(channel_mentions)
        else:
            blacklist_text = "No channels blacklisted"
            
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            index=2,
            name="Updated Blacklisted Channels/Categories",
            value=blacklist_text,
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed)

class SettingsView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.add_item(ChannelSelect(self.guild_id))
        
    @discord.ui.button(label="Edit Max Daily Sigils", style=discord.ButtonStyle.primary)
    async def edit_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MaxSigilsModal(self.guild_id)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Edit Role Bonuses", style=discord.ButtonStyle.secondary)
    async def edit_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleBonusesModal(self.guild_id)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()

class MaxSigilsModal(Modal, title="Edit Max Daily Sigils"):
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

        data = db.reference(f'Sigils System/{guild_id}').get()
        current_max = data.get('max_daily_sigils', DEFAULT_MAX_DAILY_SIGILS)

        self.max_sigils = TextInput(
            label="Maximum Daily Sigils",
            default=str(current_max),
            placeholder=f"Default: {DEFAULT_MAX_DAILY_SIGILS}",
            required=True
        )
        self.add_item(self.max_sigils)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_sigils = int(self.max_sigils.value)
            if max_sigils < 1:
                raise ValueError
                
            ref = db.reference(f'Sigils System/{self.guild_id}')
            ref.update({'max_daily_sigils': max_sigils})
            
            sigil_cog = interaction.client.get_cog("SigilSystem")
            if sigil_cog:
                await sigil_cog.update_guild_cache(self.guild_id)
            
            await interaction.response.send_message(
                f"<:yes:1036811164891480194> Maximum daily Sigils set to `{max_sigils}`",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                f"{NO_EMOTE} Please enter a valid positive number",
                ephemeral=True
            )

class RoleBonusesModal(Modal, title="Edit Role Bonuses"):
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

        data = db.reference(f'Sigils System/{guild_id}').get()
        current_bonuses: dict = data.get('role_bonuses', {})
        formatted_bonuses = ", ".join(f"<@&{rid}> {bonus}" for rid, bonus in current_bonuses.items())

        self.role_bonuses = TextInput(
            label="Role Bonuses",
            default=formatted_bonuses or None,
            placeholder="Example: <@&783528750524268580> 80, <@&783528750498971660> +20",
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.role_bonuses)

    async def on_submit(self, interaction: discord.Interaction):
        role_bonuses = {}
        input_text = self.role_bonuses.value.strip()
        
        if input_text:
            try:
                for part in input_text.split(','):
                    part = part.strip()
                    if not part:
                        continue
                        
                    role_part, bonus_part = part.rsplit(maxsplit=1)
                    role_id = int(role_part.strip()[3:-1]) 
                    
                    if not (bonus_part.startswith('+') or bonus_part.isdigit()):
                        raise ValueError
                        
                    role_bonuses[str(role_id)] = bonus_part
                    
            except Exception as e:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Invalid format. Use: `@role amount` or `@role +amount` separated by commas",
                    ephemeral=True
                )
        
        ref = db.reference(f'Sigils System/{self.guild_id}')
        ref.update({'role_bonuses': role_bonuses})
        
        sigil_cog = interaction.client.get_cog("SigilSystem")
        if sigil_cog:
            await sigil_cog.update_guild_cache(self.guild_id)
        
        if role_bonuses:
            bonus_text = "\n".join(f"<@&{rid}>: `{bonus}`" for rid, bonus in role_bonuses.items())
            embed = discord.Embed(
                title="Role Bonuses Updated",
                description=bonus_text,
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "<:yes:1036811164891480194> Cleared all role bonuses",
                ephemeral=True
            )

async def handle_join(interaction: discord.Interaction, giveaway_id: str):
    await interaction.response.defer(ephemeral=True)
    
    sigil_cog = interaction.client.get_cog("SigilSystem")
    if not await sigil_cog.is_enabled(interaction.guild.id):
        return await interaction.followup.send(
            f"{NO_EMOTE} The Sigil system is not enabled in this server. Admins can enable it with `/giveaway enable`.",
            ephemeral=True
        )

    ref = db.reference(f"Giveaways/{giveaway_id}")
    data = ref.get()

    if not data:
        return await interaction.followup.send(
            f"{NO_EMOTE} Giveaway not found",
            ephemeral=True
        )

    if data["end_time"] < time.time():
        return await interaction.followup.send(
            f"{NO_EMOTE} This giveaway has ended",
            ephemeral=True
        )

    user_entries = data.get("entries", {}).get(str(interaction.user.id), 0)
    if user_entries > 0:
        view = LeaveGiveawayView(giveaway_id)
        return await interaction.followup.send(
            "You've already joined this giveaway! Leaving the giveaway **will not** refund your Sigils.",
            view=view,
            ephemeral=True
        )

    if not await sigil_cog.deduct_sigils(interaction.guild.id, interaction.user.id, data["base_cost"]):
        return await interaction.followup.send(
            f"{NO_EMOTE} You need {SIGIL_EMOTE} `{data['base_cost']}` Sigils to enter!",
            ephemeral=True
        )

    ref.child(f"entries/{interaction.user.id}").set(1)

    await interaction.followup.send(
        f"<:yes:1036811164891480194> Joined giveaway for {SIGIL_EMOTE} `{data['base_cost']}` Sigils!",
        ephemeral=True
    )

async def handle_leave(interaction: discord.Interaction, giveaway_id: str):
    await interaction.response.defer(ephemeral=True)
    ref = db.reference(f"Giveaways/{giveaway_id}")
    data = ref.get()

    if not data:
        return await interaction.followup.send(
            f"{NO_EMOTE} Giveaway not found",
            ephemeral=True
        )

    if data["end_time"] < time.time():
        return await interaction.followup.send(
            f"{NO_EMOTE} This giveaway has ended",
            ephemeral=True
        )

    user_entries = data.get("entries", {}).get(str(interaction.user.id), 0)
    if user_entries == 0:
        return await interaction.followup.send(
            f"{NO_EMOTE} You haven't entered this giveaway",
            ephemeral=True
        )

    ref.child(f"entries/{interaction.user.id}").delete()

    await interaction.followup.send(
        "<:yes:1036811164891480194> You've left the giveaway",
        ephemeral=True
    )

async def handle_extra(interaction: discord.Interaction, giveaway_id: str):
    sigil_cog = interaction.client.get_cog("SigilSystem")
    if not await sigil_cog.is_enabled(interaction.guild.id):
        return await interaction.response.send_message(
            f"{NO_EMOTE} The Sigil system is not enabled in this server. Admins can enable it with `/giveaway enable`.",
            ephemeral=True
        )

    ref = db.reference(f"Giveaways/{giveaway_id}")
    data = ref.get()

    if not data:
        return await interaction.response.send_message(
            f"{NO_EMOTE} Giveaway not found",
            ephemeral=True
        )

    if data["end_time"] < time.time():
        return await interaction.response.send_message(
            f"{NO_EMOTE} This giveaway has ended",
            ephemeral=True
        )

    user_entries = data.get("entries", {}).get(str(interaction.user.id), 0)
    if user_entries == 0:
        return await interaction.response.send_message(
            f"{NO_EMOTE} You must join the giveaway first!",
            ephemeral=True
        )

    balance = await sigil_cog.get_balance(interaction.guild.id, interaction.user.id)
    max_entries = balance // data["extra_cost"]

    if max_entries == 0:
        return await interaction.response.send_message(
            f"{NO_EMOTE} You don't have enough Sigils for any extra entries "
            f"(need `{data['extra_cost']}` per entry)",
            ephemeral=True
        )

    modal = EntryModal(giveaway_id, max_entries, data["extra_cost"])
    await interaction.response.send_modal(modal)

async def handle_view_entries(interaction: discord.Interaction, giveaway_id: str):
    await interaction.response.defer(ephemeral=True)
    
    sigil_cog = interaction.client.get_cog("SigilSystem")
    if not await sigil_cog.is_enabled(interaction.guild.id):
        return await interaction.followup.send(
            f"{NO_EMOTE} The Sigil system is not enabled in this server. Admins can enable it with `/giveaway enable`.",
            ephemeral=True
        )
    
    ref = db.reference(f"Giveaways/{giveaway_id}")
    data = ref.get()
    
    if not data:
        return await interaction.followup.send(
            f"{NO_EMOTE} Giveaway not found",
            ephemeral=True
        )
    
    if data["end_time"] < time.time():
        return await interaction.followup.send(
            f"{NO_EMOTE} This giveaway has ended",
            ephemeral=True
        )
    
    user_entries = data.get("entries", {}).get(str(interaction.user.id), 0)
    balance = await sigil_cog.get_balance(interaction.guild.id, interaction.user.id)
    extra_cost = data["extra_cost"]
    max_extra_entries = balance // extra_cost
    
    embed = discord.Embed(
        title=f"Your Entries for {data['prize']}",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Current Entries", 
        value=f"`{user_entries}`",
        inline=True
    )
    embed.add_field(
        name="Your Sigil Balance", 
        value=f"{SIGIL_EMOTE} `{balance}`",
        inline=True
    )
    embed.add_field(
        name="Possible Extra Entries", 
        value=f"`{max_extra_entries}` (Cost: {SIGIL_EMOTE} `{extra_cost}` each)",
        inline=True
    )
    
    await interaction.followup.send(embed=embed, ephemeral=True)
        
@app_commands.guild_only()
class GiveawaySystem(commands.GroupCog, name="giveaway"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.loop.create_task(self._check_giveaways())
        super().__init__()

    async def _check_giveaways(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                ref = db.reference('Giveaways')
                all_giveaways = ref.get() or {}
                
                current_time = int(time.time())
                for giveaway_id, data in list(all_giveaways.items()):
                    if data["end_time"] <= current_time:
                        await self.end_giveaway(giveaway_id)
                
                await asyncio.sleep(30)
            except Exception as e:
                print(f"Error in giveaway check: {e}")
                await asyncio.sleep(300)

    async def end_giveaway(self, giveaway_id: str):
        ref = self._get_giveaway_ref(giveaway_id)
        data = ref.get()
        if not data:
            return

        entries_dict = data.get("entries", {})
        total_entries = sum(entries_dict.values())

        winners = []
        distinct_users = list(entries_dict.keys())
        weights = list(entries_dict.values())
        num_winners = min(data["winners"], len(distinct_users))

        for _ in range(num_winners):
            winner_id = random.choices(distinct_users, weights=weights)[0]
            winners.append(int(winner_id))
            idx = distinct_users.index(winner_id)
            distinct_users.pop(idx)
            weights.pop(idx)

        channel = self.bot.get_channel(data["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(data["message_id"])
                if winners:
                    winner_mentions = ", ".join(f"<@{w}>" for w in winners)
                    embed = discord.Embed(
                        title=f"🎉 {data['prize']} Giveaway Ended!",
                        description=f"Congratulations to the winners: {winner_mentions}",
                        color=discord.Color.gold()
                    )
                    embed.add_field(name="Total Entries", value=f"`{total_entries}`", inline=True)
                    embed.add_field(name="Winners", value=f"`{len(winners)}`", inline=True)
                    await msg.reply(content=winner_mentions, embed=embed)
                else:
                    embed = discord.Embed(
                        title=f"🎉 {data['prize']} Giveaway Ended!",
                        description="Not enough participants to select winners.",
                        color=discord.Color.gold()
                    )
                    await msg.reply(embed=embed)

                await msg.edit(view=None)
            except Exception as e:
                print(f"Error ending giveaway: {e}")

        ref.delete()
    
    def _get_giveaway_ref(self, giveaway_id: str):
        return db.reference(f'Giveaways/{giveaway_id}')
    
    async def create_giveaway(
        self, 
        prize: str, 
        duration: int, 
        winners: int, 
        channel: discord.TextChannel, 
        base_cost: int,
        extra_cost: int
    ):
        end_time = int(time.time() + duration)
        giveaway_id = str(int(time.time()))
        
        data = {
            "prize": prize,
            "end_time": end_time,
            "winners": winners,
            "channel_id": channel.id,
            "base_cost": base_cost,
            "extra_cost": extra_cost,
            "entries": {}
        }
        
        ref = self._get_giveaway_ref(giveaway_id)
        ref.set(data)
        
        embed = discord.Embed(
            title=f"🎉 {prize} Giveaway",
            description=f"Click the buttons below to enter!\nEnds: <t:{end_time}:R>\nYou can chat actively to earn {SIGIL_EMOTE} Sigils!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Base Entry Cost", value=f"{SIGIL_EMOTE} `{base_cost}`", inline=True)
        embed.add_field(name="Extra Entry Cost", value=f"{SIGIL_EMOTE} `{extra_cost}` each", inline=True)
        embed.add_field(name="Winners", value=f"`{str(winners)}`", inline=True)
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        
        view = GiveawayEntryView()
        message = await channel.send(embed=embed, view=view)
        
        # Store message ID
        ref.update({"message_id": message.id})
        
        return giveaway_id


    @app_commands.command(name="enable", description="Enable the Sigil and Giveaway system for this server")
    @app_commands.describe(
        max_daily="Maximum daily Sigils (default: 60)",
        role_bonuses="Role bonuses (format: @role amount, @role +amount)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_enable(
        self, 
        interaction: discord.Interaction,
        max_daily: int = DEFAULT_MAX_DAILY_SIGILS,
        role_bonuses: str = None
    ):
        if max_daily < 1:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Maximum daily Sigils must be at least 1",
                ephemeral=True
            )
            
        role_bonus_dict = {}
        if role_bonuses:
            try:
                for part in role_bonuses.split(','):
                    part = part.strip()
                    if not part:
                        continue
                        
                    role_part, bonus_part = part.rsplit(maxsplit=1)
                    role_id = int(role_part.strip()[3:-1]) 
                    
                    if not (bonus_part.startswith('+') or bonus_part.isdigit()):
                        raise ValueError
                        
                    role_bonus_dict[str(role_id)] = bonus_part
            except:
                return await interaction.response.send_message(
                    f"{NO_EMOTE} Invalid role bonuses format. Use: `@role amount` or `@role +amount` separated by commas",
                    ephemeral=True
                )
            
        ref = db.reference(f'Sigils System/{interaction.guild.id}')
        ref.set({
            'enabled': True,
            'max_daily_sigils': max_daily,
            'role_bonuses': role_bonus_dict
        })
        
        sigil_cog = self.bot.get_cog("SigilSystem")
        if sigil_cog:
            await sigil_cog.update_guild_cache(interaction.guild.id)
            if interaction.guild.id in sigil_cog.guild_config_check_cache:
                sigil_cog.guild_config_check_cache.remove(interaction.guild.id)
        
        embed = discord.Embed(
            title="Sigil System Enabled",
            description=f"<:yes:1036811164891480194> **Sigils and giveaways are now enabled in this server!** Use </giveaway create:1402740034603319570> to start a giveaway or </giveaway settings:1402740034603319570> to edit the settings.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Max Daily Sigils",
            value=f"`{max_daily}`",
            inline=True
        )
        
        if role_bonus_dict:
            bonus_text = "\n".join(f"<@&{rid}>: `{bonus}`" for rid, bonus in role_bonus_dict.items())
            embed.add_field(
                name="Role Bonuses",
                value=bonus_text,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    @giveaway_enable.error
    async def giveaway_enable_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="disable", description="Disable the Sigil and Giveaway system for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_disable(self, interaction: discord.Interaction):
        sigil_cog = self.bot.get_cog("SigilSystem")
        if not await sigil_cog.is_enabled(interaction.guild.id):
            return await interaction.response.send_message(
                f"{NO_EMOTE} The Sigil system is not even enabled in this server. What are you thinking?",
                ephemeral=True
            )
        
        ref = db.reference(f'Sigils System/{interaction.guild.id}')
        ref.update({'enabled': False})
        
        sigil_cog = self.bot.get_cog("SigilSystem")
        if sigil_cog:
            await sigil_cog.update_guild_cache(interaction.guild.id)
            sigil_cog.guild_config_check_cache.add(interaction.guild.id)
        
        await interaction.response.send_message(
            "<:yes:1036811164891480194> Sigils and giveaways are now disabled in this server",
            ephemeral=True
        )
    @giveaway_disable.error
    async def giveaway_disable_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="settings", description="View and edit Sigil system settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_settings(self, interaction: discord.Interaction):
        sigil_cog = self.bot.get_cog("SigilSystem")
        config = await sigil_cog.get_server_config(interaction.guild.id)
        
        if not(config['enabled']):
            return await interaction.response.send_message(
                f"{NO_EMOTE} The Sigil system is not enabled in this server. Enable it with `/giveaway enable` first.",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="Sigil System Settings",
            description="<:info:1037445870469267638> Members earn **19–25 Sigils** every **15–20 messages**. *Daily chests give 5–10 extra if chat events are enabled in the server.*",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Status",
            value="Enabled" if config['enabled'] else "Disabled",
            inline=True
        )
        embed.add_field(
            name="Max Daily Sigils",
            value=f"`{config['max_daily_sigils']}`",
            inline=True
        )
        
        blacklisted = config.get('blacklisted_channels', [])
        if blacklisted:
            mentions = [f'- <#{cid}>' for cid in blacklisted[:10]]
            if len(blacklisted) > 10:
                mentions.append(f"... and {len(blacklisted)-10} more")
            blacklist_text = '\n'.join(mentions)
        else:
            blacklist_text = "No channels blacklisted"
            
        embed.add_field(
            name="Blacklisted Channels/Categories",
            value=blacklist_text,
            inline=True
        )
        
        if config.get('role_bonuses'):
            bonus_text = "\n".join(f"<@&{rid}>: `{bonus}`" for rid, bonus in config['role_bonuses'].items())
            embed.add_field(
                name="Role Bonuses",
                value=bonus_text,
                inline=False
            )
        
        embed.set_footer(text="You can use \"/giveaway create\" to start a giveaway")
        view = SettingsView(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @giveaway_settings.error
    async def giveaway_settings_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="create", description="Create a new giveaway")
    @app_commands.describe(
        prize="Prize name",
        duration_minutes="Duration in minutes",
        winners="Number of winners",
        channel="Channel to post in",
        base_cost="Sigil cost to enter",
        extra_cost="Sigil cost per extra entry"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_create(
        self, 
        interaction: discord.Interaction,
        prize: str,
        duration_minutes: int,
        winners: int,
        channel: discord.TextChannel,
        base_cost: int,
        extra_cost: int
    ):
        sigil_cog = self.bot.get_cog("SigilSystem")
        if not await sigil_cog.is_enabled(interaction.guild.id):
            return await interaction.response.send_message(
                f"{NO_EMOTE} The Sigil system is not enabled in this server. Enable it with `/giveaway enable` first.",
                ephemeral=True
            )
        
        if duration_minutes < 1:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Duration must be at least 1 minute",
                ephemeral=True
            )
            
        await interaction.response.defer()
        giveaway_id = await self.create_giveaway(
            prize,
            duration_minutes * 60,
            winners,
            channel,
            base_cost,
            extra_cost
        )
        
        await interaction.followup.send(
            f"<:yes:1036811164891480194> Giveaway created! ID: `{giveaway_id}`",
            ephemeral=True
        )
    @giveaway_create.error
    async def giveaway_create_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="end", description="End a giveaway early")
    @app_commands.describe(giveaway_id="The giveaway ID to end")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, giveaway_id: str):
        ref = self._get_giveaway_ref(giveaway_id)
        data = ref.get()
        
        if not data:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Giveaway not found",
                ephemeral=True
            )
        
        ref.update({"end_time": int(time.time())})
        
        channel = self.bot.get_channel(data["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(data["message_id"])
                await msg.edit(view=None)
                await msg.reply("🎉 Giveaway ended early! Drawing winners soon...")
            except:
                pass
        
        await interaction.response.send_message(
            "<:yes:1036811164891480194> Giveaway ended successfully",
            ephemeral=True
        )
    @giveaway_end.error
    async def giveaway_end_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="list", description="List active giveaways")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_list(self, interaction: discord.Interaction):
        ref = db.reference('Giveaways')
        all_giveaways = ref.get() or {}
        
        if not all_giveaways:
            return await interaction.response.send_message(
                "No active giveaways",
                ephemeral=True
            )
            
        embed = discord.Embed(
            title="Active Giveaways",
            color=discord.Color.blurple()
        )
        
        for gid, data in all_giveaways.items():
            if data["end_time"] > time.time():
                channel = self.bot.get_channel(data["channel_id"])
                channel_name = f"#{channel.name}" if channel else "Unknown"
                embed.add_field(
                    name=f"🎁 {data['prize']}",
                    value=(
                        f"ID: `{gid}`\n"
                        f"Ends: <t:{data['end_time']}:R>\n"
                        f"Channel: {channel_name}\n"
                        f"Entries: {len(data.get('entries', {}))}"
                    ),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @giveaway_list.error
    async def giveaway_list_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        

class EntryModal(Modal, title="Get Extra Entries"):
    def __init__(self, giveaway_id: str, max_entries: int, extra_cost: int):
        super().__init__()
        self.giveaway_id = giveaway_id
        self.max_entries = max_entries
        self.extra_cost = extra_cost
        self.count = TextInput(
            label="How many extra entries?",
            placeholder=f"Max: {max_entries}",
            default=str(max_entries),
            required=True
        )
        self.add_item(self.count)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.count.value)
            if count < 1 or count > self.max_entries:
                raise ValueError
        except:
            return await interaction.response.send_message(
                f"{NO_EMOTE} Invalid number (1-{self.max_entries})",
                ephemeral=True
            )
            
        sigil_cog = interaction.client.get_cog("SigilSystem")
        cost = count * self.extra_cost
        if not await sigil_cog.deduct_sigils(interaction.guild.id, interaction.user.id, cost):
            return await interaction.response.send_message(
                f"{NO_EMOTE} You don't have enough Sigils!",
                ephemeral=True
            )
            
        ref = db.reference(f"Giveaways/{self.giveaway_id}/entries/{interaction.user.id}")
        current = ref.get() or 0
        ref.set(current + count)
        
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> Added `{count}` extra entries for {SIGIL_EMOTE} `{cost}` Sigils!",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SigilSystem(bot))
    await bot.add_cog(GiveawaySystem(bot))