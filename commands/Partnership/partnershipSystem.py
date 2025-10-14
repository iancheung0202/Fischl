import discord
import re
import asyncio
import datetime
import aiohttp
import time

from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from firebase_admin import db
from typing import Optional, List

def _config_ref(guild_id: int):
    return db.reference(f'Partner/config/{guild_id}')

def _partners_ref(guild_id: int):
    return db.reference(f'Partner/partners/{guild_id}')

def _categories_ref(guild_id: int):
    return db.reference(f'Partner/categories/{guild_id}')

def _panel_ref(guild_id: int):
    return db.reference(f'Partner/panels/{guild_id}')

def _cooldown_ref(guild_id: int, user_id: int = None):
    base = db.reference(f'Partner/Cooldown/{guild_id}')
    return base.child(str(user_id)) if user_id else base

def _blacklist_ref(guild_id: int):
    return db.reference(f'Partner/Blacklist/{guild_id}')

async def _build_panel_embeds(guild_id: int) -> List[discord.Embed]:
    config = _config_ref(guild_id).get()
    partners = _partners_ref(guild_id).get() or {}
    categories = _categories_ref(guild_id).get() or {}
    embed_config = config.get('embed', {})
    header = embed_config.get('header', {})
    footer = embed_config.get('footer', {})

    header_embed = discord.Embed(
        title=header.get('title', None),
        description=header.get('description', None),
        color=int(header.get('color', '#5865F2').lstrip('#'), 16)
    )
    if header_embed.title is None and header_embed.description is None:
        header_embed = discord.Embed(
            title='Server Partner List',
            description='Use </partner edit-panel:1364761118324822128> and select `Header` to edit this embed!',
            color=int(header.get('color', '#5865F2').lstrip('#'), 16)
        )
    if 'thumbnail' in header:
        header_embed.set_thumbnail(url=header['thumbnail'])
    if 'image' in header:
        header_embed.set_image(url=header['image'])

    category_embeds = []
    for cat_name, cat_data in categories.items():
        category_partners = [p for p in partners.values() if p.get('category') == cat_name]
        if not category_partners:
            continue

        sorted_partners = sorted(category_partners, key=lambda x: x['name'].lower())
        lines = []
        for p in sorted_partners:
            if p['invite'].isdigit(): # Bot application ID
                print(p['invite'].isdigit())
                line = f"{cat_data.get('prefix', '')} [{p['name']}](https://discord.com/oauth2/authorize?client_id={p['invite']}) {cat_data.get('suffix', '')}"
                lines.append(line)
            else:
                line = f"{cat_data.get('prefix', '')} [{p['name']}](https://discord.gg/{p['invite']}) {cat_data.get('suffix', '')}"
                lines.append(line)

        fields = []
        current_start_char = 'A'
        start_idx = 0

        def next_char(c):
            return chr(ord(c) + 1) if c != 'Z' else 'Z'

        while current_start_char <= 'Z' and start_idx < len(sorted_partners):
            while start_idx < len(sorted_partners):
                server_first_char = sorted_partners[start_idx]['name'][0].upper()
                if server_first_char >= current_start_char:
                    break
                start_idx += 1
            else:
                break 

            current_chunk = []
            current_length = 0
            end_idx = start_idx

            for i in range(start_idx, len(sorted_partners)):
                if sorted_partners[i]['invite'].isdigit(): # Bot application ID
                    line = f"{cat_data.get('prefix', '')} [{sorted_partners[i]['name']}](https://discord.com/oauth2/authorize?client_id={sorted_partners[i]['invite']}) {cat_data.get('suffix', '')}"
                else:
                    line = f"{cat_data.get('prefix', '')} [{sorted_partners[i]['name']}](https://discord.gg/{sorted_partners[i]['invite']}) {cat_data.get('suffix', '')}"
                line_length = len(line) + 1 

                if current_length + line_length > 1024:
                    break
                current_chunk.append(line)
                current_length += line_length
                end_idx = i + 1

            if not current_chunk:
                current_start_char = next_char(current_start_char)
                continue

            end_char = sorted_partners[end_idx - 1]['name'][0].upper()
            fields.append({
                'name': f"{current_start_char} - {end_char}",
                'value': '\n'.join(current_chunk)
            })

            current_start_char = next_char(end_char)
            start_idx = end_idx

        if fields:
            last_field = fields[-1]
            last_start = last_field['name'].split(' - ')[0]
            fields[-1]['name'] = f"{last_start} - Z"

        for i in range(0, len(fields), 25):
            group = fields[i:i+25]
            group_embed = discord.Embed(
                title=cat_data.get('title', cat_name),
                color=int(cat_data.get('color', '#5865F2').lstrip('#'), 16)
            )
            if cat_data.get('thumbnail'):
                group_embed.set_thumbnail(url=cat_data['thumbnail'])
            for field in group:
                group_embed.add_field(name=field['name'], value=field['value'], inline=False)
            category_embeds.append(group_embed)

    footer_embed = discord.Embed(
        title=footer.get('title', None),
        description=footer.get('description', None),
        color=int(footer.get('color', '#5865F2').lstrip('#'), 16)
    )
    if footer_embed.title is None and footer_embed.description is None:
        footer_embed = discord.Embed(
            title='Instructions',
            description='Use </partner edit-panel:1364761118324822128> and select `Footer` to edit this embed!',
            color=int(header.get('color', '#5865F2').lstrip('#'), 16)
        )
    if 'thumbnail' in footer:
        footer_embed.set_thumbnail(url=footer['thumbnail'])
    if 'image' in footer:
        footer_embed.set_image(url=footer['image'])
    footer_embed.set_footer(text="⚡ Panel automatically updated • Powered by Fischl") 

    return [header_embed] + category_embeds + [footer_embed]

async def _update_panel(guild_id: int, bot):
    config = _config_ref(guild_id).get()
    panel = _panel_ref(guild_id).get()
    if not config or not panel:
        return

    try:
        channel = bot.get_channel(panel['channel_id'])
        if not channel:
            return
            
        message = await channel.fetch_message(panel['message_id'])
        await message.edit(embeds=await _build_panel_embeds(guild_id))
        return "<:yes:1036811164891480194> Panel updated!"
    except Exception as e:
        return f"<:no:1036810470860013639> Failed to update panel: {e}"
        
async def category_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    categories = _categories_ref(interaction.guild.id).get() or {}
    return [
        app_commands.Choice(name=name, value=name)
        for name in categories.keys() if current.lower() in name.lower()
    ][:25]

class PartnershipFirebaseListener:
    def __init__(self, bot):
        self.bot = bot
        self.listeners = {}
        self.update_queue = asyncio.Queue()
        self.update_task = None
        
    def start_listeners(self):
        partners_ref = db.reference('Partner/partners')
        categories_ref = db.reference('Partner/categories') 
        config_ref = db.reference('Partner/config')
        panel_ref = db.reference('Partner/panels')
        
        partners_ref.listen(self._on_partners_change)
        categories_ref.listen(self._on_categories_change)
        config_ref.listen(self._on_config_change)
        
        self.update_task = asyncio.create_task(self._process_updates())
        print("[Partnership] Firebase listeners started successfully")
    
    def stop_listeners(self):
        if self.update_task:
            self.update_task.cancel()
    
    def _on_partners_change(self, event):
        if event.path == '/':
            if event.data:
                for guild_id in event.data.keys():
                    self._queue_update(guild_id, 'partners', event.event_type)
        else:
            guild_id = event.path.split('/')[1] if len(event.path.split('/')) > 1 else None
            if guild_id:
                self._queue_update(guild_id, 'partners', event.event_type)
    
    def _on_categories_change(self, event):
        if event.path == '/':
            if event.data:
                for guild_id in event.data.keys():
                    self._queue_update(guild_id, 'categories', event.event_type)
        else:
            guild_id = event.path.split('/')[1] if len(event.path.split('/')) > 1 else None
            if guild_id:
                self._queue_update(guild_id, 'categories', event.event_type)
    
    def _on_config_change(self, event):
        if event.path == '/':
            if event.data:
                for guild_id in event.data.keys():
                    self._queue_update(guild_id, 'config', event.event_type)
        else:
            guild_id = event.path.split('/')[1] if len(event.path.split('/')) > 1 else None
            if guild_id:
                self._queue_update(guild_id, 'config', event.event_type)
    
    def _queue_update(self, guild_id, data_type, event_type):
        try:
            guild_id = int(guild_id)
            
            update_data = {
                'guild_id': guild_id,
                'data_type': data_type,
                'event_type': event_type,
                'timestamp': time.time()
            }
            
            asyncio.run_coroutine_threadsafe(
                self.update_queue.put(update_data), 
                self.bot.loop
            )
        except Exception as e:
            print(f"[Partnership] Error queuing update: {e}")
    
    async def _process_updates(self):
        pending_updates = {}
        
        while True:
            try:
                try:
                    update = await asyncio.wait_for(self.update_queue.get(), timeout=2.0)
                    guild_id = update['guild_id']
                    pending_updates[guild_id] = update
                except asyncio.TimeoutError:
                    if pending_updates:
                        updates_to_process = list(pending_updates.values())
                        pending_updates.clear()
                        
                        for update in updates_to_process:
                            await self._execute_panel_update(update['guild_id'])
                            
                        await asyncio.sleep(0.5)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Partnership] Error processing updates: {e}")
                await asyncio.sleep(1)
    
    async def _execute_panel_update(self, guild_id):
        try:
            panel = _panel_ref(guild_id).get()
            if not panel:
                return
                
            result = await _update_panel(guild_id, self.bot)
            
            if result and "Failed" not in result:
                print(f"[Partnership] Panel update successful for guild {guild_id}")
            elif result is not None:
                print(f"[Partnership] Panel update failed for guild {guild_id}: {result}")
                
        except Exception as e:
            print(f"[Partnership] Error executing panel update for guild {guild_id}: {e}")

async def _log_action(client, guild_id: int, user: discord.User, action: str, details: dict, button = None):
    config = _config_ref(guild_id).get() or {}
    channel_id = config.get('log_channel')
    if not channel_id:
        return

    channel = client.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title=f"{action}",
        color=0x5865F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)

    for key, value in details.items():
        embed.add_field(name=key, value=str(value), inline=False)

    if button:
        view = View()
        view.add_item(button)
    else:
        view = None
    await channel.send(embed=embed, view=view)

class Partner(commands.GroupCog, name="partner"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.firebase_listener = PartnershipFirebaseListener(bot)
        
    async def cog_load(self):
        self.firebase_listener.start_listeners()
        
    async def cog_unload(self):
        self.firebase_listener.stop_listeners()
        await self.session.close()

    class PartnershipRequestModal(Modal, title='Partnership Request'):
        invite_link = TextInput(label='Your Server\'s Permanent Invite Link', required=True, placeholder="Other details will be fetched automatically.")

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            cooldown_ref = _cooldown_ref(interaction.guild.id, interaction.user.id)
            last_request = cooldown_ref.get() or 0
            config = _config_ref(interaction.guild.id).get()
            cooldown_seconds = config.get('user_cooldown', 0)
            partner_manager_role_id = config.get('partner_manager_role_id', None)

            if datetime.datetime.now().timestamp() - last_request < cooldown_seconds:
                remaining = int(cooldown_seconds - (datetime.datetime.now().timestamp() - last_request))
                await interaction.followup.send(
                    f"<:no:1036810470860013639> You're on cooldown! Try again in {remaining//3600}h {remaining%3600//60}m",
                    ephemeral=True
                )
                return

            try:
                code = self.invite_link.value.split('/')[-1]
                print(code)

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f'https://discord.com/api/v9/invites/{code}',
                        params={"with_counts": "true", "with_expiration": "true"}
                    ) as resp:
                        if resp.status != 200:
                            await interaction.followup.send("<:no:1036810470860013639> Invalid invite link!", ephemeral=True)
                            return

                        data = await resp.json()
                        guild_data = data.get('guild', {})
                        expires_at = data.get('expires_at', None)
                        is_permanent = expires_at is None

                        icon_hash = guild_data.get('icon')
                        server_icon_url = (
                            f"https://cdn.discordapp.com/icons/{guild_data['id']}/{icon_hash}.png"
                            if icon_hash
                            else "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTEkPA5_-j6SudIbSZh-ExIs1eSeuCYIIRthjHfg0P2dbwUH2E&s"
                        )

            except Exception as e:
                await interaction.followup.send(f"<:no:1036810470860013639> Failed to validate invite!```{e}```", ephemeral=True)
                return
            
            blacklisted = _blacklist_ref(interaction.guild.id).child(guild_data['id']).get()
            if blacklisted:
                await interaction.followup.send("<:no:1036810470860013639> This server is blacklisted! If you believe this is a mistake, contact a server staff and ask them to unblacklist your server!", ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(config['request_channel'])
            guild_id = guild_data['id']
            existing_threads = channel.threads
            archived_threads = []
            async for thread in channel.archived_threads():
                archived_threads.append(thread)
            all_threads = existing_threads + archived_threads
            for thread in all_threads:
                try:
                    messages = [
                        message async for message in thread.history(limit=2, oldest_first=True)
                    ]
                    for message in messages:
                        if message.author.id != interaction.client.user.id or len(message.embeds) == 0:
                            continue
                        embed = message.embeds[0]
                        for field in embed.fields:
                            if field.name == "Server ID" and field.value == str(guild_id):
                                await interaction.followup.send(
                                    f"<:no:1036810470860013639> A partnership thread for this server already exists: {thread.mention}",
                                    ephemeral=True
                                )
                                return
                except Exception as e:
                    print(e)
                    continue

            channel = interaction.guild.get_channel(config['request_channel'])
            thread = await channel.create_thread(
                name=f"🟡 {guild_data.get('name')}",
                type=discord.ChannelType.private_thread
            )
            await thread.add_user(interaction.user)

            embed = discord.Embed(
                title="New Partnership Request",
                description="-# - Staff can use </partner status:1364761118324822128> to update the thread and </partner add-partner:1364761118324822128> to add partner to the panel.\n-# - Everyone here can use </partner invite:1364761118324822128> to invite other server reps/staff to this thread.",
                color=0xfee75c
            )

            embed.add_field(name="Server ID", value=guild_id, inline=True)
            embed.add_field(name="Server Name", value=guild_data.get('name'), inline=True)
            embed.add_field(
                name="Members",
                value=data.get('approximate_member_count', 'Unknown'),
                inline=True
            )
            embed.add_field(
                name="Permanent Server Invite",
                value='<:yes:1036811164891480194> Yes' if is_permanent else '<:no:1036810470860013639> No',
                inline=True
            )
            embed.add_field(name="Requester ID", value=interaction.user.id, inline=True)
            embed.add_field(name="Requester Mention", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Status: 🟡 Pending")
            embed.set_thumbnail(url=server_icon_url)

            await thread.send(
                content=f"{('<@&' + partner_manager_role_id + '>') if partner_manager_role_id not in [None, ''] else ''} {self.invite_link}",
                embed=embed
            )

            await _log_action(
                interaction.client,
                interaction.guild.id,
                interaction.user,
                f"New Partnership Request ({guild_data.get('name')})",
                {
                    "Server ID": guild_data.get('id'),
                    "Server Name": guild_data.get('name'),
                    "Invite Link": f"https://discord.gg/{code}",
                    "Permanent Invite": "<:yes:1036811164891480194> Yes" if is_permanent else "<:no:1036810470860013639> No",
                    "Members": data.get('approximate_member_count', 'Unknown')
                },
                Button(
                    label="Go to thread",
                    style=discord.ButtonStyle.link,
                    url=thread.jump_url
                )
            )
            await interaction.followup.send(f"<:yes:1036811164891480194> Request created in {thread.mention}", ephemeral=True)
            cooldown_ref.set(datetime.datetime.now().timestamp())
            
            
    @app_commands.command(name="status", description="Update partnership status")
    @app_commands.describe(
        status="New status",
        reason="Reason for status change"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="🟡 Pending", value="pending"),
        app_commands.Choice(name="🟢 Accepted", value="accepted"),
        app_commands.Choice(name="🔴 Rejected", value="rejected"),
        app_commands.Choice(name="⚫ Blacklisted", value="blacklisted")
    ])
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_status(self, interaction: discord.Interaction, status: str, reason: str = "No reason provided"):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("<:no:1036810470860013639> This command must be used in a partnership thread!", ephemeral=True)
            return

        status_emoji = {
            "pending": "🟡",
            "accepted": "🟢",
            "rejected": "🔴",
            "blacklisted": "⚫"
        }[status]

        old_name = interaction.channel.name.removeprefix('🟡').removeprefix('🟢').removeprefix('🔴').removeprefix('⚫').strip()
        new_name = f"{status_emoji} {old_name}"
        await interaction.channel.edit(name=new_name)

        messages = [
            message async for message in interaction.channel.history(limit=2, oldest_first=True)
        ]
        for message in messages:
            if message.author.id != interaction.client.user.id or len(message.embeds) == 0:
                continue
            embed = message.embeds[0]
            embed.color = {
                "pending": 0xfee75c,
                "accepted": 0x57f287,
                "rejected": 0xed4245,
                "blacklisted": 0x000000
            }[status]
            embed.set_footer(text=f"Status: {status_emoji} {status.capitalize()} | Reason: {reason}")
            await message.edit(embed=embed)
            
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            f"Partner Status Updated {status_emoji}",
            {"Server Name": old_name}
        )

        await interaction.response.send_message(f"<:yes:1036811164891480194> Status updated to {status_emoji} {status}!", ephemeral=True)
    @partner_status.error
    async def partner_status_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="invite", description="Invite server representatives to the partnership thread")
    @app_commands.describe(user="User to invite")
    async def partner_invite(self, interaction: discord.Interaction, user: discord.User):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("<:no:1036810470860013639> This command can only be used in partnership threads!", ephemeral=True)
            return

        thread = interaction.channel
        try:
            await thread.add_user(user)
            await interaction.response.send_message(f"<:yes:1036811164891480194> {user.mention} has been added to the thread!", ephemeral=True)
        except Exception:
            await interaction.response.send_message("<:no:1036810470860013639> Sorry, something went wrong!", ephemeral=True)
    @partner_invite.error
    async def partner_invite_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
            
            
    @app_commands.command(name="create", description="Manually create a partnership thread (bypasses blacklist)")
    @app_commands.describe(
        invite_link="Permanent invite link for the server"
    )
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_create(self, interaction: discord.Interaction, invite_link: str):
        await interaction.response.defer(ephemeral=True)
        config = _config_ref(interaction.guild.id).get()

        try:
            code = invite_link.split('/')[-1]
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'https://discord.com/api/v9/invites/{code}',
                    params={"with_counts": "true"}
                ) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("<:no:1036810470860013639> Invalid invite link!", ephemeral=True)
                        return
                    data = await resp.json()
                    guild_data = data.get('guild', {})
                    expires_at = data.get('expires_at', None)
                    is_permanent = expires_at is None
        except Exception as e:
            await interaction.followup.send(f"<:no:1036810470860013639> Error validating invite: {e}", ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(config['request_channel'])
        guild_id = guild_data['id']
        existing_threads = channel.threads
        archived_threads = []
        async for thread in channel.archived_threads():
            archived_threads.append(thread)
        all_threads = existing_threads + archived_threads
        for thread in all_threads:
            try:
                messages = [
                    message async for message in thread.history(limit=2, oldest_first=True)
                ]
                for message in messages:
                    if message.author.id != interaction.client.user.id or len(message.embeds) == 0:
                        continue
                    embed = message.embeds[0]
                    for field in embed.fields:
                        if field.name == "Server ID" and field.value == str(guild_id):
                            await interaction.followup.send(
                                f"<:no:1036810470860013639> A partnership thread for this server already exists: {thread.mention}",
                                ephemeral=True
                            )
                            return
            except Exception as e:
                print(e)
                continue

        channel = interaction.guild.get_channel(config['request_channel'])
        thread = await channel.create_thread(
            name=f"🟡 {guild_data.get('name')}",
            type=discord.ChannelType.private_thread
        )

        embed = discord.Embed(
            title="Partnership Thread (initiated by Staff)",
            description="-# - Staff can use </partner status:1364761118324822128> to update the thread and </partner add-partner:1364761118324822128> to add partner to the panel.\n-# - Everyone here can use </partner invite:1364761118324822128> to invite other server reps/staff to this thread.",
            color=0xfee75c
        )

        embed.add_field(name="Server ID", value=guild_id, inline=True)
        embed.add_field(name="Server Name", value=guild_data.get('name'), inline=True)
        embed.add_field(
            name="Members",
            value=data.get('approximate_member_count', 'Unknown'),
            inline=True
        )
        embed.add_field(
            name="Permanent Server Invite",
            value='<:yes:1036811164891480194> Yes' if is_permanent else '<:no:1036810470860013639> No',
            inline=True
        )
        embed.add_field(name="Staff ID", value=interaction.user.id, inline=True)
        embed.add_field(name="Staff Mention", value=interaction.user.mention, inline=True)

        embed.set_footer(text="Status: 🟡 Pending")

        await thread.send(content=invite_link, embed=embed)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            f"Staff Partnership Thread Creation ({guild_data.get('name')})",
            {
                "Server ID": guild_data.get('id'),
                "Server Name": guild_data.get('name'),
                "Invite Link": f"https://discord.gg/{code}",
                "Members": data.get('approximate_member_count', 'Unknown')
            }
        )
        await interaction.followup.send(f"<:yes:1036811164891480194> Thread created: {thread.mention}. Use </partner invite:1364761118324822128> to invite server representatives to the thread!", ephemeral=True)
    @partner_create.error
    async def partner_create_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    
    @app_commands.command(name="blacklist", description="Blacklist a server from partnerships")
    @app_commands.describe(invite_link="The invite link of server to blacklist (Leave blank to view blacklist)")
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_blacklist(self, interaction: discord.Interaction, invite_link: Optional[str] = None):
        if not invite_link:
            blacklist = _blacklist_ref(interaction.guild.id).get() or {}
            if not blacklist:
                return await interaction.response.send_message("No servers are blacklisted!", ephemeral=True)

            embed = discord.Embed(title="Blacklisted Server ID", color=0xff0000)
            embed.description = "\n".join([f"- `{gid}`" for gid in blacklist.keys()])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            code = invite_link.split('/')[-1]
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://discord.com/api/v9/invites/{code}') as resp:
                    data = await resp.json()
                    guild_id = data['guild']['id']
        except Exception as e:
            await interaction.response.send_message(f"<:no:1036810470860013639> Invalid invite: {e}", ephemeral=True)
            return

        _blacklist_ref(interaction.guild.id).child(guild_id).set(True)
        await interaction.response.send_message(f"<:yes:1036811164891480194> Server {guild_id} blacklisted!", ephemeral=True)
    @partner_blacklist.error
    async def partner_blacklist_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

        
    @app_commands.command(name="unblacklist", description="Remove a server from blacklist")
    @app_commands.describe(guild_id="Server ID to unblacklist")
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_unblacklist(self, interaction: discord.Interaction, guild_id: str):
        ref = _blacklist_ref(interaction.guild.id).child(guild_id)
        if not ref.get():
            await interaction.response.send_message("<:no:1036810470860013639> Server not in blacklist!", ephemeral=True)
            return

        ref.delete()
        await interaction.response.send_message(f"<:yes:1036811164891480194> Server {guild_id} unblacklisted!", ephemeral=True)
    @partner_unblacklist.error
    async def partner_unblacklist_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="edit-panel", description="Edit panel embeds")
    @app_commands.describe(section="Section to edit")
    @app_commands.choices(section=[
        app_commands.Choice(name="Header", value="header"),
        app_commands.Choice(name="Footer", value="footer")
    ])
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True, manage_messages=True)
    async def partner_edit_panel(self, interaction: discord.Interaction, section: str):
        current_data = _config_ref(interaction.guild.id).child(f'embed/{section}').get() or {}
        
        class EditPanelModal(Modal, title=f'Edit {section.capitalize()} Embed'):
            title_input = TextInput(
                label="Title", 
                required=False,
                placeholder="Enter an embed title",
                default=current_data.get('title', '')
            )
            description = TextInput(
                label="Description", 
                style=discord.TextStyle.paragraph,
                required=False,
                placeholder="Enter an embed description",
                default=current_data.get('description', '')
            )
            color = TextInput(
                label="Color (hex code)", 
                required=False,
                placeholder="e.g. #0f0f0f",
                default=current_data.get('color', '#5865F2')
            )
            thumbnail = TextInput(
                label="Thumbnail URL", 
                required=False,
                placeholder="Enter an link for thumbnail image",
                default=current_data.get('thumbnail', '')
            )
            image = TextInput(
                label="Image URL", 
                required=False,
                placeholder="Enter an link for large image",
                default=current_data.get('image', '')
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                raw_updates = {
                    'title': self.title_input.value.strip(),
                    'description': self.description.value.strip(),
                    'color': self.color.value.strip(),
                    'thumbnail': self.thumbnail.value.strip(),
                    'image': self.image.value.strip()
                }

                updates = {
                    k: (v if v != "" else None) 
                    for k, v in raw_updates.items()
                }

                if updates.get('color') is None:
                    updates['color'] = '#5865F2' 

                existing_data = _config_ref(modal_interaction.guild.id).child(f'embed/{section}').get() or {}

                final_updates = {}
                for key, value in updates.items():
                    if value != existing_data.get(key):
                        final_updates[key] = value

                if final_updates:
                    _config_ref(modal_interaction.guild.id).child(f'embed/{section}').update(final_updates)
                else:
                    await modal_interaction.response.send_message(
                        "<:no:1036810470860013639> No changes detected!",
                        ephemeral=True
                    )
                    return

                msg = await _update_panel(modal_interaction.guild.id, interaction.client)

                for key, value in final_updates.items():
                    if value is None:
                        _config_ref(modal_interaction.guild.id).child(f'embed/{section}/{key}').delete()

                await modal_interaction.response.send_message(f"{msg}", ephemeral=True)

                if "Failed to update panel" not in msg:
                    await _log_action(
                        interaction.client,
                        modal_interaction.guild.id,
                        modal_interaction.user,
                        f"Panel Edited ({section.capitalize()})",
                        final_updates or {"No changes": "N/A"}
                    )

        await interaction.response.send_modal(EditPanelModal())
    @partner_edit_panel.error
    async def partner_edit_panel_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        

    @app_commands.command(name="disable", description="Disable partnership system")
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_disable(self, interaction: discord.Interaction):
        config_ref = _config_ref(interaction.guild.id)
        if not config_ref.get():
            await interaction.response.send_message("<:no:1036810470860013639> Partnership system not enabled!", ephemeral=True)
            return
            
        config_ref.delete()
        _panel_ref(interaction.guild.id).delete()
        _categories_ref(interaction.guild.id).delete()
        _partners_ref(interaction.guild.id).delete()
        
        await interaction.response.send_message(
            "<:yes:1036811164891480194> Partnership system disabled! All configurations removed.",
            ephemeral=True
        )
    @partner_disable.error
    async def partner_disable_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="send-panel", description="Send the partnership panel")
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_send_panel(self, interaction: discord.Interaction):
        config = _config_ref(interaction.guild.id).get()
        if not config:
            await interaction.response.send_message("<:no:1036810470860013639> Partnership system not enabled!", ephemeral=True)
            return

        view = View()
        view.add_item(PartnerRequestButton())
        
        channel = self.bot.get_channel(config['panel_channel'])
        message = await channel.send(
            embeds=await _build_panel_embeds(interaction.guild.id),
            view=view
        )
        
        _panel_ref(interaction.guild.id).set({
            'message_id': message.id,
            'channel_id': channel.id
        })
        
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Panel Sent",
            {
                "Channel": channel.mention,
                "Message ID": message.id,
                "Embed Count": len(await _build_panel_embeds(interaction.guild.id))
            }
        )
        
        await interaction.response.send_message(f"<:yes:1036811164891480194> [Partnership panel sent]({message.jump_url})! *All other panels sent previously will no longer automatically update.*", ephemeral=True)
    @partner_send_panel.error
    async def partner_send_panel_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    
    @app_commands.command(name="update-panel", description="Manually update the partnership panel")
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_update_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        config = _config_ref(interaction.guild.id).get()
        if not config:
            await interaction.followup.send("<:no:1036810470860013639> Partnership system not enabled!", ephemeral=True)
            return
            
        panel = _panel_ref(interaction.guild.id).get()
        if not panel:
            await interaction.followup.send("<:no:1036810470860013639> No panel found! Use `/partner send-panel` first.", ephemeral=True)
            return
        
        result = await _update_panel(interaction.guild.id, self.bot)
        
        if result and "Failed" not in result:
            await interaction.followup.send(f"{result}\n*Panel updated successfully.*", ephemeral=True)
        else:
            await interaction.followup.send(f"{result or '<:no:1036810470860013639> Update failed for unknown reason.'}", ephemeral=True)
            
    @partner_update_panel.error
    async def partner_update_panel_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
        
    @app_commands.command(name="add-group", description="Create new partner group with separate panel embed")
    @app_commands.describe(
        name="Unique group name (no spaces)",
        title="Display title (default: the group name)",
        color="Embed color in hex code (default: #5865F2)",
        prefix="Line prefix (default: bullet point)",
        suffix="Line suffix (default: None)",
        thumbnail="Thumbnail URL (optional)"
    )
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_add_group(
        self,
        interaction: discord.Interaction,
        name: str,
        title: Optional[str] = None,
        color: Optional[str] = "#5865F2",
        prefix: Optional[str] = "-",
        suffix: Optional[str] = "",
        thumbnail: Optional[str] = None
    ):
        if not re.match(r"^[\w-]+$", name):
            await interaction.response.send_message(
                "<:no:1036810470860013639> Group name can only contain letters, numbers, underscores and hyphens!",
                ephemeral=True
            )
            return

        categories = _categories_ref(interaction.guild.id).get()
        if name.lower() in [k.lower() for k in (categories or {})]:
            await interaction.response.send_message("<:no:1036810470860013639> Group already exists!", ephemeral=True)
            return

        _categories_ref(interaction.guild.id).child(name).set({
            'title': title or name,
            'color': color,
            'prefix': prefix,
            'suffix': suffix,
            'thumbnail': thumbnail,
            'created_at': datetime.datetime.now().timestamp()
        })
        
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Group Created",
            {
                "Group Name": name,
                "Title": title or name,
                "Color": color,
                "Prefix": prefix,
                "Suffix": suffix if suffix != "" else "None",
                "Thumbnail": thumbnail or "None"
            }
        )

        await interaction.response.send_message(
            f"<:yes:1036811164891480194> Group '{name}' created! To delete a group, use </partner remove-group:1364761118324822128>.",
            ephemeral=True
        )
    @partner_add_group.error
    async def partner_add_group_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="edit-group", description="Edit an existing partner group")
    @app_commands.describe(group="Group to edit")
    @app_commands.autocomplete(group=category_autocomplete)
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_edit_group(self, interaction: discord.Interaction, group: str):
        categories = _categories_ref(interaction.guild.id).get() or {}
        if group not in categories:
            await interaction.response.send_message("<:no:1036810470860013639> Group not found!", ephemeral=True)
            return

        current_data = categories[group]

        class EditGroupModal(Modal, title="Edit Partner Group"):
            def __init__(self, original_name: str):
                super().__init__()
                self.original_name = original_name

                prefix = current_data.get('prefix', '-')
                suffix = current_data.get('suffix', '')
                prefix_suffix_default = f"{prefix}, {suffix}".strip(', ')

                self.name_input = TextInput(
                    label="Unique Group Name",
                    placeholder="Letters, numbers, underscores, hyphens",
                    default=original_name,
                    required=True
                )
                self.title_input = TextInput(
                    label="Display Title",
                    default=current_data.get('title', ''),
                    required=False
                )
                self.color = TextInput(
                    label="Color (hex)",
                    default=current_data.get('color', '#5865F2'),
                    required=False
                )
                self.prefix_suffix = TextInput(
                    label="Prefix, Suffix (separated by a comma)",
                    placeholder="Example: -, >",
                    default=prefix_suffix_default,
                    required=False
                )
                self.thumbnail = TextInput(
                    label="Thumbnail URL",
                    default=current_data.get('thumbnail', ''),
                    required=False
                )

                self.add_item(self.name_input)
                self.add_item(self.title_input)
                self.add_item(self.color)
                self.add_item(self.prefix_suffix)
                self.add_item(self.thumbnail)

            async def on_submit(self, modal_interaction: discord.Interaction):
                new_name = self.name_input.value.strip()
                prefix_suffix = self.prefix_suffix.value.split(',', 1) 
                prefix = prefix_suffix[0].strip() if len(prefix_suffix) > 0 else '-'
                suffix = prefix_suffix[1].strip() if len(prefix_suffix) > 1 else ''

                updates = {
                    'title': self.title_input.value.strip() or new_name,
                    'color': self.color.value.strip(),
                    'prefix': prefix,
                    'suffix': suffix,
                    'thumbnail': self.thumbnail.value.strip() or None
                }

                if not re.match(r"^[\w-]+$", new_name):
                    await modal_interaction.response.send_message(
                        "<:no:1036810470860013639> Invalid group name! Only letters, numbers, underscores, and hyphens allowed.",
                        ephemeral=True
                    )
                    return

                categories_ref = _categories_ref(modal_interaction.guild.id)
                existing_groups = categories_ref.get() or {}

                if new_name.lower() != self.original_name.lower() and any(name.lower() == new_name.lower() for name in existing_groups):
                    await modal_interaction.response.send_message(
                        "<:no:1036810470860013639> Group name already exists!",
                        ephemeral=True
                    )
                    return

                if new_name != self.original_name:
                    categories_ref.child(self.original_name).delete()
                    partners_ref = _partners_ref(modal_interaction.guild.id)
                    partners = partners_ref.get() or {}
                    for p_id, p_data in partners.items():
                        if p_data.get('category') == self.original_name:
                            partners_ref.child(p_id).update({'category': new_name})

                categories_ref.child(new_name).update(updates)

                msg = await _update_panel(modal_interaction.guild.id, modal_interaction.client)
                await modal_interaction.response.send_message(
                    f"<:yes:1036811164891480194> Group updated! \n{msg}",
                    ephemeral=True
                )

                await _log_action(
                    modal_interaction.client,
                    modal_interaction.guild.id,
                    modal_interaction.user,
                    "Group Edited",
                    {
                        "Original Name": self.original_name,
                        "New Name": new_name,
                        **updates
                    }
                )

        modal = EditGroupModal(group)
        await interaction.response.send_modal(modal)
    @partner_edit_group.error
    async def partner_edit_group_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="remove-group", description="⚠️ Remove a group and ALL its partners")
    @app_commands.describe(name="Group name to remove")
    @app_commands.autocomplete(name=category_autocomplete)
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_remove_group(self, interaction: discord.Interaction, name: str):
        categories = _categories_ref(interaction.guild.id).get()
        if not categories or name not in categories:
            await interaction.response.send_message("<:no:1036810470860013639> Group not found!", ephemeral=True)
            return

        partners = _partners_ref(interaction.guild.id).get() or {}
        deleted_count = 0

        for partner_id, partner_data in partners.items():
            if partner_data.get('category') == name:
                _partners_ref(interaction.guild.id).child(partner_id).delete()
                deleted_count += 1

        _categories_ref(interaction.guild.id).child(name).delete()

        await _update_panel(interaction.guild.id, interaction.client)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Group Removed",
            {
                "Group Name": name,
                "Partners Deleted": deleted_count
            }
        )
        await interaction.response.send_message(
            f"<:yes:1036811164891480194> Group '{name}' and its {deleted_count} partner(s) were permanently deleted!",
            ephemeral=True
        )
    @partner_remove_group.error
    async def partner_remove_group_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        

    @app_commands.command(name="setup", description="Set up partnership system")
    @app_commands.describe(
        log_channel="Channel for partnership logs",
        partner_role="Role to grant server partners",
        request_channel="Channel to create partnership threads under",
        panel_channel="Channel to send the partnership panel",
        partner_manager_role="Staff role to ping for new partnership requests (default: None)",
        user_cooldown="Cooldown between user requests (format: 3d12h45m; default: 0)"
    )
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
    async def partner_setup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
        partner_role: discord.Role,
        request_channel: discord.TextChannel,
        panel_channel: discord.TextChannel,
        partner_manager_role: discord.Role = None,
        user_cooldown: str = "0m"  # Default cooldown set to 0
    ):
        def format_pretty(days: int, hours: int, minutes: int) -> str:
            parts = []
            if days:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            return ", ".join(parts) if parts else "None"

        seconds = 0
        match = re.fullmatch(r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?', user_cooldown)
        if match:
            days = int(match.group(1)) if match.group(1) else 0
            hours = int(match.group(2)) if match.group(2) else 0
            minutes = int(match.group(3)) if match.group(3) else 0
            seconds = days * 86400 + hours * 3600 + minutes * 60
            pretty_cooldown = format_pretty(days, hours, minutes)
        else:
            await interaction.response.send_message(
                "⚠️ Invalid cooldown format. Use something like `3d12h45m`, `5h`, or `30m`.", ephemeral=True
            )
            return

        _config_ref(interaction.guild.id).update({
            'log_channel': log_channel.id,
            'partner_role': partner_role.id,
            'request_channel': request_channel.id,
            'panel_channel': panel_channel.id,
            'user_cooldown': seconds,
            'partner_manager_role_id': str(partner_manager_role.id) if partner_manager_role is not None else '',
            'enabled': True
        })

        embed = discord.Embed(
            title="<:yes:1036811164891480194> Partnership System Setup Complete!",
            description=(
                "Here are something you can do next to make everything work:\n"
                f"- Check out {panel_channel.mention} and {request_channel.mention} and follow the instructions there.\n"
                f"- Use </partner add-group:1364761118324822128> to group partners (e.g., \"Hangouts\", \"Genshin\", \"HSR\", etc).  \n"
                "  - **Name**: A short ID is required (no spaces, like `Genshin_Impact`).  \n"
                "  - **Title**: The display name of the group (e.g., \"🎮 Genshin Impact Servers\").  \n"
                "  - **Prefix/Suffix**: Customize how server links appear on the panel with your favorite symbols.  \n"
                "  - Partners will only show up on the panel if they're in a group!\n"
                "- Try </partner add-partner:1364761118324822128> and </partner remove-partner:1364761118324822128> to test add/remove partners.\n"
                "- Use </partner create:1364761118324822128> to manually create a partnership thread as a staff\n\n"
                "**⚙️ Your Configured Settings**"
            ),
            color=0x00FF00
        )
        fields = {
            "Log Channel": log_channel.mention,
            "Request Channel": request_channel.mention,
            "Panel Channel": panel_channel.mention,
            "Partner Role": partner_role.mention,
            "Partner Manager Role *(pinged for new requests)*": partner_manager_role.mention if partner_manager_role is not None else 'None',
            "User Cooldown": pretty_cooldown
        }

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)

        await interaction.response.send_message(embed=embed)
        
        try:
            view = View()
            view.add_item(PartnerRequestButton())
            panel_message = await panel_channel.send(
                embeds=await _build_panel_embeds(interaction.guild.id),
                view=view
            )
            _panel_ref(interaction.guild.id).set({
                'message_id': panel_message.id,
                'channel_id': panel_channel.id
            })

            log_embed = discord.Embed(
                description="📝 This channel will be used for logging all partnership-related actions.",
                color=0x5865F2
            )
            await log_channel.send(embed=log_embed)

            instructions_embed = discord.Embed(
                title="Partnership Request Instructions",
                color=0x5865F2
            )
            instructions_embed.add_field(name="For Server Representatives", value=f"1. Click `Request Partnership` **[here]({panel_message.jump_url})** in {panel_channel.mention}\n2. Check existing threads using:\n  - **Threads <:thread_icon:1366092363822268598> button** at channel top\n  - **Channel Sidebar** on desktop (hover → 'See All')", inline=False)
            instructions_embed.add_field(name="For Staff Only", value=f"- Manage partnership requests in threads. Use the methods above to access all the threads.\n- Use </partner create:1364761118324822128> to manually create a partnership thread.", inline=False)
            instructions_embed.set_image(url="https://media.discordapp.net/attachments/1106727534479032341/1366102857366896781/thread_instructions.png?ex=680fb9ee&is=680e686e&hm=4a80c4dda380d4b3e5ef7781576a9be6981e909a0179780e50dc605b1a4570c1&=")
            instructions_embed.set_footer(text="You may delete/replace this message if you wish to.")
            await request_channel.send(embed=instructions_embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Partially completed setup: {type(e).__name__} - {str(e)}",
                ephemeral=True
            )
    @partner_setup.error
    async def partner_setup_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        

    @app_commands.command(name="mass-add-partner", description="Mass add partner servers from formatted text")
    @app_commands.describe(
        group="Group that servers belong to",
        content="Formatted partner list (each line: [Server Name](invite_link))"
    )
    @app_commands.autocomplete(group=category_autocomplete)
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True, manage_messages=True)
    async def partner_mass_add(
        self,
        interaction: discord.Interaction,
        group: str,
        content: str
    ):
        await interaction.response.defer(ephemeral=True)

        categories = _categories_ref(interaction.guild.id).get()
        if not categories or group not in categories:
            await interaction.followup.send("<:no:1036810470860013639> Invalid group! Create groups first using </partner add-group:1364761118324822128>.", ephemeral=True)
            return

        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        lines = content.splitlines()
        added_count = 0
        errors = []

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            match = re.search(pattern, line)
            if not match:
                errors.append(f"Line {i}: Invalid format")
                continue

            name = match.group(1)
            url = match.group(2)

            if 'discord.gg/' in url:
                code = url.split('discord.gg/')[-1].split('/')[0]
            elif 'discord.com/invite/' in url:
                code = url.split('discord.com/invite/')[-1].split('/')[0]
            else:
                code = url.rstrip('/').split('/')[-1]

            if not code:
                errors.append(f"Line {i}: Couldn't extract invite code")
                continue

            try:
                _partners_ref(interaction.guild.id).push().set({
                    'name': name,
                    'invite': code,
                    'member_count': 0,
                    'staff_id': interaction.user.id,
                    'created_at': int(datetime.datetime.now().timestamp()),
                    'category': group
                })
                added_count += 1
            except Exception as e:
                errors.append(f"Line {i}: {str(e)}")

        update_msg = await _update_panel(interaction.guild.id, interaction.client)

        response = f"<:yes:1036811164891480194> Added {added_count} partners to group `{group}`!\n{update_msg}"
        if errors:
            error_list = "\n".join(errors[:5])
            if len(errors) > 5:
                error_list += f"\n...and {len(errors)-5} more errors"
            response += f"\n\n**Errors:**\n{error_list}"

        await interaction.followup.send(response, ephemeral=True)

        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Mass Partner Add",
            {
                "Group": group,
                "Added Count": added_count,
                "Error Count": len(errors)
            }
        )
    @partner_mass_add.error
    async def partner_mass_add_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
    

    @app_commands.command(name="add-partner", description="Add a partner server")
    @app_commands.describe(
        name="Server name",
        invite_link="Server's permanent invite link (please include 'https://')",
        group="Group that server belongs (use /partner add-group to create a group)",
        server_rep="The server's representative to get the partner role"
    )
    @app_commands.autocomplete(group=category_autocomplete)
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True, manage_messages=True)
    async def add_partner(
        self,
        interaction: discord.Interaction,
        name: str,
        invite_link: str,
        group: str,
        server_rep: discord.User = None
    ):
        await interaction.response.defer(ephemeral=True)
        categories = _categories_ref(interaction.guild.id).get()
        if not categories or group not in categories:
            await interaction.followup.send("<:no:1036810470860013639> Invalid group! Create groups first using </partner add-group:1364761118324822128>.", ephemeral=True)
            return
        
        if server_rep is not None:
            config = _config_ref(interaction.guild.id).get()
            partner_role_id = config.get('partner_role', {})
            try:
                await server_rep.add_roles(interaction.guild.get_role(int(partner_role_id)))
            except Exception:
                await interaction.followup.send("<:no:1036810470860013639> Invalid partner role. Double check to see if the role has been deleted.", ephemeral=True)
                return
        
        if invite_link.isdigit(): # Bot application ID
            _partners_ref(interaction.guild.id).push().set({
                'name': name,
                'invite': invite_link, 
                'member_count': "N/A",
                'staff_id': interaction.user.id,
                'created_at': int(datetime.datetime.now().timestamp()),
                'category': group
            })

            await _update_panel(interaction.guild.id, interaction.client)
            await _log_action(
                interaction.client,
                interaction.guild.id,
                interaction.user,
                "Bot Partner Added",
                {
                    "Server Name": name,
                    "Invite Code": invite_link,
                    "Category": group,
                    "Member Count": "N/A"
                }
            )
            await interaction.followup.send("<:yes:1036811164891480194> Bot partner added!", ephemeral=True)
        else:
            try:
                code = invite_link.split('/')[-1]
                print(code)
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f'https://discord.com/api/v9/invites/{code}',
                        params={"with_counts": "true", "with_expiration": "true"}
                    ) as resp:
                        if resp.status != 200:
                            await interaction.followup.send("<:no:1036810470860013639> Invalid invite link!", ephemeral=True)
                            return

                        data = await resp.json()
                        guild_data = data.get('guild', {})
                        expires_at = data.get('expires_at', None)
                        is_permanent = expires_at is None

                        if not is_permanent:
                            await interaction.followup.send("<:no:1036810470860013639> Invite link is not permanent.", ephemeral=True)
                            return

            except Exception as e:
                await interaction.followup.send(f"<:no:1036810470860013639> Failed to validate invite!```{e}```", ephemeral=True)
                return

            _partners_ref(interaction.guild.id).push().set({
                'name': name,
                'invite': code,
                'member_count': guild_data.get('approximate_member_count', 0),
                'staff_id': interaction.user.id,
                'created_at': int(datetime.datetime.now().timestamp()),
                'category': group
            })

            await _update_panel(interaction.guild.id, interaction.client)
            await _log_action(
                interaction.client,
                interaction.guild.id,
                interaction.user,
                "Partner Added",
                {
                    "Server Name": name,
                    "Invite Code": code,
                    "Category": group,
                    "Member Count": data.get('approximate_member_count', 0)
                }
            )
            await interaction.followup.send("<:yes:1036811164891480194> Partner server added!", ephemeral=True)
    @add_partner.error
    async def add_partner_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)


    @app_commands.command(name="remove-partner", description="Remove a partner server")
    @app_commands.describe(
        server_name="Server name to remove",
        invite="Invite link to remove"
    )
    @app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True, manage_messages=True)
    async def remove_partner(
        self,
        interaction: discord.Interaction,
        server_name: Optional[str] = None,
        invite: Optional[str] = None
    ):
        if not server_name and not invite:
            await interaction.response.send_message("<:no:1036810470860013639> You must provide either server name or invite link!", ephemeral=True)
            return

        partners = _partners_ref(interaction.guild.id).get() or {}
        found_partner = None

        for key, data in partners.items():
            if (server_name and data['name'].lower() == server_name.lower()) or \
               (invite and data['invite'] in invite):
                
                if server_name and invite:
                    if data['name'].lower() != server_name.lower() or data['invite'] not in invite:
                        await interaction.response.send_message("<:no:1036810470860013639> Server name and invite don't match!", ephemeral=True)
                        return
                
                found_partner = key
                break

        if not found_partner:
            await interaction.response.send_message("<:no:1036810470860013639> Partner server not found!", ephemeral=True)
            return

        _partners_ref(interaction.guild.id).child(found_partner).delete()
        await _update_panel(interaction.guild.id, interaction.client)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Partner Removed",
            {
                "Partner ID": found_partner,
                "Server Name": partners[found_partner]['name'],
                "Invite Code": partners[found_partner]['invite']
            }
        )
        await interaction.response.send_message("<:yes:1036811164891480194> Partner server removed!", ephemeral=True)
    @remove_partner.error
    async def remove_partner_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
            
class PartnerRequestButtonView(discord.ui.View):
    def __init__(
        self,
        *,
        timeout=None,
    ):
        super().__init__(timeout=timeout)
        self.add_item(PartnerRequestButton())

class PartnerRequestButton(Button):
    def __init__(self):
        super().__init__(
            label="Request Partnership",
            style=discord.ButtonStyle.blurple,
            custom_id="partner_request"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(Partner.PartnershipRequestModal())

async def setup(bot: commands.Bot):
    await bot.add_cog(Partner(bot))
