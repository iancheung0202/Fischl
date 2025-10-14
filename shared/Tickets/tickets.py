import discord
import datetime
import asyncio
import time
import emoji
import re
import hashlib
import os
import aiohttp

from groq import Groq
from collections import defaultdict
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from assets.secret import GROQ_API_KEY

async def generate(prompt: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
    )

    return chat_completion.choices[0].message.content

class Select(discord.ui.Select):
    def __init__(self, placeholder, options):
        super().__init__(
            placeholder=placeholder,
            max_values=1,
            min_values=1,
            options=options,
            custom_id="ticketcreation",
        )

    async def callback(self, interaction: discord.Interaction):

        selectedValue = self.values[0]
        embed = discord.Embed(
            title="Confirm Ticket",
            description=f"Are you sure you want to make a ticket about **{selectedValue}**?",
            colour=0x4F545B,
        )
        try:
            embed.set_author(
                name=interaction.user.name, icon_url=interaction.user.avatar.url
            )
        except Exception:
            embed.set_author(name=interaction.user.name)
        embed.set_footer(
            icon_url=interaction.guild.icon.url,
            text=f"{interaction.guild.name} • #{interaction.channel.name}",
        )
        await interaction.response.send_message(
            embed=embed, view=CreateTicketButtonView(), ephemeral=True
        )


class SelectView(discord.ui.View):
    def __init__(self, placeholder=None, options=None, *, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(Select(placeholder, options))


class CreateTicketButton(discord.ui.Button):
    def __init__(self, title, emoji, color):
        super().__init__(label=title, emoji=emoji, style=color, custom_id="create")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                CATEGORY_ID = value["Category ID"]
                LOGCHANNEL_ID = value["Log Channel ID"]
                try:
                    COOLDOWN_IN_SECONDS = value["Cooldown"]
                except Exception:
                    COOLDOWN_IN_SECONDS = 0
                try:
                    PING_ROLE_ID = value["Ping Role ID"]
                except Exception:
                    PING_ROLE_ID = None
                found = True
                break

        if not found:
            embed = discord.Embed(
                title="Ticket not enabled!",
                description=f"This server doesn't have a ticket category or a log channel. Please ask the server moderator to use `/ticket setup` to setup tickets!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        category = interaction.guild.get_channel(CATEGORY_ID)

        for channel in category.channels:
            if str(channel.topic) == str(interaction.user.id):
                await interaction.followup.send(
                    content=f"<:no:1036810470860013639> You already had your ticket created at <#{channel.id}>.",
                    ephemeral=True,
                )
                return
            
        blacklist_ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}/{interaction.user.id}").get()
        if blacklist_ref:
            await interaction.followup.send(f"<:no:1036810470860013639> You are blacklisted from creating tickets in **{interaction.guild.name}**.", ephemeral=True)
            return
        
        last_created_ref = db.reference(f"/Tickets Cooldown/{interaction.guild.id}/users/{interaction.user.id}/last_created")
        last_created = last_created_ref.get()
        if last_created and (time.time() - last_created) < COOLDOWN_IN_SECONDS:
            remaining = COOLDOWN_IN_SECONDS - (time.time() - last_created)
            await interaction.followup.send(f"<:no:1036810470860013639> You are on a cooldown! Try again in **{int(remaining // 3600)}h {int((remaining % 3600) // 60)}m**.", ephemeral=True)
            return

        log = interaction.guild.get_channel(LOGCHANNEL_ID)
        embed = discord.Embed(
            title="Ticket created",
            description=f"**{interaction.user.mention}** created a new ticket <t:{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}:R>!",
            color=discord.Colour.green(),
        )

        special_embed = None
        try:
            createembed = interaction.message.embeds[0]
            if "Are you sure you want to make a ticket" in createembed.description:
                topic = f"{createembed.description.split('**')[1]}"
                embed.add_field(name="Ticket Topic", value=topic)
            else:
                topic = f"{createembed.title}"
                embed.add_field(name="Ticket Topic", value=topic)
            ref = db.reference(f"/Ticket Instructions/{interaction.guild.id}")
            instructions = ref.get()
            if instructions:
                for i, (cat, embed_info) in enumerate(instructions.items()):
                    if cat.strip().lower() == topic.strip().lower():
                        special_embed = discord.Embed(
                            title=embed_info.get("title", ""),
                            description=embed_info.get("description", ""),
                            color=int(embed_info.get("color", "#5865F2").lstrip('#'), 16)
                        )
                        break
        except Exception:
            topic = ""

        ### SPECIAL TOPICS ###
        channel_extension = None
        if interaction.guild.id == 1094228164324114493:  # Lumine Mains
            if "general" in topic.lower():
                channel_extension = "support"
            elif "role" in topic.lower():
                channel_extension = "role"
            elif "partner" in topic.lower():
                channel_extension = "partner"
            else:
                channel_extension = None
        elif interaction.guild.id == 1197491630807199834:
            if "partner" in topic.lower():
                category = interaction.guild.get_channel(1253988610194018384)
                log = interaction.guild.get_channel(1235251162056495226)
            elif "help" in topic.lower():
                channel_extension = "support"
            elif "rule" in topic.lower():
                channel_extension = "report"

        try:
            if channel_extension is not None:
                chn = await interaction.guild.create_text_channel(
                    f"{interaction.user.name}-{channel_extension}", category=category
                )
            else:
                chn = await interaction.guild.create_text_channel(
                    f"{interaction.user.name}", category=category
                )

            await chn.edit(topic=interaction.user.id)
            await chn.set_permissions(
                interaction.user, send_messages=True, read_messages=True, attach_files=True
            )
        except Exception:
            await interaction.followup.send(
                content=f"<:no:1036810470860013639> **I'm missing permissions to create or edit text channels!** \nPlease make sure my role has `MANAGE_CHANNELS` permissions.", ephemeral=True
            )
            return

        try:
            embed.set_author(
                name=f"{interaction.user.name}", icon_url=interaction.user.avatar.url
            )
        except Exception:
            embed.set_author(name=f"{interaction.user.name}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"Ticket ID: {chn.id}")

        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{chn.id}",
        )
        view = View()
        view.add_item(button)
        await log.send(embed=embed, view=view)
        embed.title = f"Ticket created in {interaction.guild.name}"
        await interaction.client.get_channel(1417408712980697099).send(embed=embed)

        roles = interaction.user.roles
        roles.reverse()

        embed = discord.Embed(
            title=topic if topic != "" else "New Ticket",
            description=f"Type your message here in this channel!\nYou can use `/ticket close` or click the red button below to close this ticket.",
            color=discord.Colour.gold(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.add_field(
            name="User Mention", value=f"{interaction.user.mention}", inline=True
        )
        embed.add_field(name="User ID", value=f"{interaction.user.id}", inline=True)
        embed.add_field(name="Highest Role", value=f"{roles[0].mention}", inline=True)
        embed.add_field(
            name="Ticket Created",
            value=f"<t:{int(chn.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Server Joined",
            value=f"<t:{int(interaction.user.joined_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(interaction.user.created_at.timestamp())}:R>",
            inline=True,
        )
        await chn.send(
            f"**{interaction.user.mention}, welcome!** {f'||<@&{PING_ROLE_ID}>||' if PING_ROLE_ID is not None else ''}",
            embed=embed,
            view=CloseTicketButton(),
        )
        if special_embed is not None:
            await chn.send(embed=special_embed)

        await interaction.followup.send(
            content=f"<:yes:1036811164891480194> Ticket created at <#{chn.id}>", ephemeral=True
        )
        
        last_created_ref.set(time.time())


class CreateTicketButtonView(discord.ui.View):
    def __init__(
        self,
        title="Create Ticket",
        emoji="🎫",
        color=discord.ButtonStyle.green,
        *,
        timeout=None,
    ):
        super().__init__(timeout=timeout)
        self.add_item(CreateTicketButton(title, emoji, color))


class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close",
        emoji="🔒",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ":no_entry_sign:" in interaction.channel.topic:
            embed = discord.Embed(
                title="Ticket already closed :no_entry_sign:",
                description="This ticket is already closed.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            title="Are you sure about that?",
            description="Only moderators and administrators can reopen the ticket.",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(
            embed=embed, view=ConfirmCloseTicketButtons(), ephemeral=True
        )


class TicketAdminButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Reopen Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="reopen",
        emoji="🔓",
    )
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user = await interaction.guild.fetch_member(
                int(interaction.channel.topic.split(":")[2].strip())
            )
        except Exception:
            await interaction.response.send_message("Unable to fetch the user. They probably left the server.", ephemeral=True)
            return
        await interaction.channel.edit(topic=user.id)
        await interaction.channel.set_permissions(
            user, send_messages=True, read_messages=True, attach_files=True
        )

        ref = db.reference("/Tickets")
        tickets = ref.get()
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                LOGCHANNEL_ID = value["Log Channel ID"]
                break
        log = interaction.guild.get_channel(LOGCHANNEL_ID)

        embed = discord.Embed(
            title="Ticket Reopened",
            color=0xFFFF00,
        )
        embed.add_field(name="Ticket Owner", value=f"{user.mention}", inline=True)
        embed.add_field(name="Reopened By", value=f"{interaction.user.mention}", inline=True)
        try:
            embed.set_author(name=f"{user.name}", icon_url=user.avatar.url)
        except Exception:
            embed.set_author(name=f"{user.name}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
        )
        view = View()
        view.add_item(button)
        await log.send(embed=embed, view=view)
        embed = discord.Embed(
            title="Ticket reopened",
            description=f"Your ticket is reopened by {interaction.user.mention}.",
            color=0xE44D41,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        button = Button(
            style=discord.ButtonStyle.link,
            label="Head over to your ticket",
            emoji="🎫",
            url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
        )
        view = View()
        view.add_item(button)
        try:
            await user.send(embed=embed, view=view)
        except Exception:
            pass
        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description="Ticket is again visible to the member.",
            color=0xFFFF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.message.delete()
        await interaction.channel.send(embed=embed, view=CloseTicketButton())
        await interaction.response.send_message("Ticket is reopened.", ephemeral=True)

    @discord.ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.grey,
        custom_id="delete",
        emoji="✉️",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Deleting Ticket...",
            description="Ticket will be deleted in 5 seconds",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.message.delete()
        await interaction.channel.send(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def parse_mentions(interaction, text):
    member_cache = {}

    async def replace_users_async(text):
        result = ""
        last_end = 0

        for match in re.finditer(r"<@!?([0-9]+)>", text):
            uid = int(match.group(1))
            try:
                member = await interaction.guild.fetch_member(uid)
                if not member:
                    if uid in member_cache:
                        member = member_cache[uid]
                    else:
                        member = await interaction.client.fetch_user(uid)
                        member_cache[uid] = member
            except Exception:
                try:
                    member = await interaction.client.fetch_user(uid)
                    member_cache[uid] = member
                except Exception:
                    member = None
            name = member.name if member else f"user:{uid}"
            result += text[last_end:match.start()] + f"<span class='mention'>@{name}</span>"
            last_end = match.end()

        return result + text[last_end:]

    text = await replace_users_async(text)

    def replace_role(match):
        rid = int(match.group(1))
        role = interaction.guild.get_role(rid)
        color = f"rgb{role.color.to_rgb()}" if role and role.color else "#ccc"
        name = role.name if role else f"role:{rid}"
        return f"<span style='color: {color};'>@{name}</span>"

    def replace_channel(match):
        cid = int(match.group(1))
        channel = interaction.guild.get_channel(cid)
        name = channel.name if channel else f"channel:{cid}"
        return f"<span class='mention'>#{name}</span>"

    def replace_command(match):
        command_name = match.group(1)
        return f"<span class='mention'>/{command_name}</span>"

    text = re.sub(r"<@&([0-9]+)>", replace_role, text)
    text = re.sub(r"<#([0-9]+)>", replace_channel, text)
    text = re.sub(r"</([A-Za-z\- ]+):[0-9]+>", replace_command, text)

    return text

def parse_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
    text = re.sub(r'[\*_](.*?)[\*_]', r'<em>\1</em>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    text = re.sub(r'^#\s+(.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'-#\s+(.*?)$', r'<small>\1</small>', text, flags=re.MULTILINE)
    text = re.sub(r'\|\|(.*?)\|\|', r'<span class="spoiler">\1</span>', text, flags=re.DOTALL)
    
    def replace_timestamp(match):
        timestamp = int(match.group(1))
        style = match.group(2) if match.group(2) else None
        return f"<span class='discord-timestamp' data-timestamp='{timestamp}' data-style='{style}'></span>"
    text = re.sub(r'<t:(\d+)(?::([a-zA-Z]))?>', replace_timestamp, text)
    
    lines = text.split('\n')
    in_blockquote = False
    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('>'):
            content = re.sub(r'^>\s*', '', stripped)
            if not in_blockquote:
                new_lines.append('<blockquote>')
                in_blockquote = True
            new_lines.append(content)
        else:
            if in_blockquote:
                new_lines.append('</blockquote>')
                in_blockquote = False
            new_lines.append(line)
    if in_blockquote:
        new_lines.append('</blockquote>')
    text = '\n'.join(new_lines)
    
    return text

async def get_transcript(interaction, user):
    messages = [
        message async for message in interaction.channel.history(limit=None)
    ]
    f = open(f"../Fischl/shared/Tickets/{interaction.channel.id}.html", "w", encoding="utf-8")

    iconURL = interaction.guild.icon.url if interaction.guild.icon else "https://discord.com/assets/5d6a5e9d7d77ac29116e.png"
    f.write(f"""<Server-Info>
    Server: {interaction.guild.name} ({interaction.guild.id})
    Channel: #{interaction.channel.name} ({interaction.channel.id})
    Ticket Owner: {user} ({user.id})
    Messages: {len(messages)}
    Attachments: {sum(1 for message in messages if message.attachments)}
    
    """)
    f.write(f"</Server-Info><!DOCTYPE html> <html> <head> <meta name='viewport' content='width=device-width, initial-scale=1.0'> <title>{user}</title> <script data-cfasync='false'> function formatDiscordTimestamps() {{ document.querySelectorAll('.discord-timestamp').forEach(element => {{ const timestamp = parseInt(element.dataset.timestamp); const style = element.dataset.style; const date = new Date(timestamp * 1000); let formatted; switch (style) {{ case 't': formatted = date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'T': formatted = date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true }}); break; case 'd': formatted = date.toLocaleDateString('en-US', {{ month: 'numeric', day: 'numeric', year: 'numeric' }}); break; case 'D': formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}); break; case 'f': formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'F': formatted = date.toLocaleDateString('en-US', {{ weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); break; case 'R': const now = new Date(); const diff = now - date; const seconds = Math.floor(diff / 1000); const intervals = {{ year: 31536000, month: 2592000, week: 604800, day: 86400, hour: 3600, minute: 60, second: 1 }}; for (const [unit, secondsInUnit] of Object.entries(intervals)) {{ const count = Math.floor(seconds / secondsInUnit); if (count >= 1) {{ formatted = `${{count}} ${{unit}}${{count !== 1 ? 's' : ''}} ago`; break; }} }} break; default: formatted = date.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }}) + ' ' + date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit', hour12: true }}); }} element.textContent = formatted; }}); }} function initializeSpoilers() {{ document.querySelectorAll('.spoiler').forEach(spoiler => {{ spoiler.addEventListener('click', () => {{ spoiler.classList.toggle('revealed'); }}); }}); }} window.addEventListener('DOMContentLoaded', () => {{ formatDiscordTimestamps(); initializeSpoilers(); }}); </script> <style> Server-Info {{visibility: hidden}} body {{ background-color: #2c2f33; color: white; font-family: 'Segoe UI', sans-serif; padding: 20px; }} .chat-container {{ max-width: 800px; margin: auto; }} .message {{ display: flex; gap: 12px; }} .message.grouped {{ margin-bottom: 6px; }} .message.not-grouped {{ margin: 20px 0 6px 0; }} .avatar {{ border-radius: 50%; width: 40px; height: 40px; }} .content {{ flex: 1; }} .username {{ font-weight: 600; }} .userid {{ font-size: 0.8em; color: #999; margin-left: 5px; }} .text {{ padding: 2px 0px; white-space: pre-wrap; margin-top: 2px; }} .attachment-img {{ max-width: 300px; border-radius: 6px; margin-top: 6px; }} .media-file {{ background-color: #4f545c; padding: 10px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; color: white; margin-top: 6px; text-decoration: none; }} .embed {{ background-color: #2f3136; padding: 10px 15px; border-left: 6px solid #7289da; border-radius: 8px; margin-top: 6px; }} .embed-title {{ font-weight: bold; color: white; }} .embed-description {{ color: #ccc; font-size: 0.95em; }} .header-container {{ display: flex; gap: 20px; margin-bottom: 30px; align-items: center; }} .header-container img {{ width: 80px; border-radius: 20px; }} .header-info div {{ margin-bottom: 5px; }} .app-badge {{ display: inline-flex; align-items: center; background-color: #5a5df0; color: white; font-weight: 600; font-family: sans-serif; border-radius: 5px; padding: 2px 8px; font-size: 12px; margin-left: 4px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }} .mention {{ background-color: rgb(65,68,112); color: rgb(183,195,234); padding: 2px 4px; border-radius: 3px; font-weight: 500; }} .embed-fields {{ margin-top: 10px; display: flex; flex-direction: column; gap: 10px;}} .embed-field {{ background-color: rgba(255, 255, 255, 0.05); padding: 8px 12px; border-radius: 6px; }} .embed-field-name {{ font-weight: bold; color: #fff; margin-bottom: 4px; font-size: 0.95em; }} .embed-field-value {{ color: #ccc; font-size: 0.95em; white-space: pre-wrap; }} blockquote {{ border-left: 3px solid rgb(101, 101, 108); padding-left: 10px; margin-left: 5px; color: #dcddde; }} .spoiler {{ position: relative; cursor: pointer; display: inline-block; }} .spoiler::after {{ content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(101, 101, 108); border-radius: 3px; transition: opacity 0.2s; }} .spoiler.revealed::after {{ opacity: 0; }} </style> </head> <body> <div class='chat-container'> <div class='header-container'> <img src='{iconURL}' /> <div class='header-info'> <div><strong>Server:</strong> {interaction.guild.name} ({interaction.guild.id})</div> <div><strong>Channel:</strong> #{interaction.channel.name} ({interaction.channel.id})</div> <div><strong>Ticket Owner:</strong> {user} ({user.id})</div> </div> </div>")

    user_message_counts = defaultdict(int)
    usersInvolved = []
    lastUser = None

    async with aiohttp.ClientSession() as session:
        for msg in reversed(messages):
            if msg.author != interaction.client.user:
                user_message_counts[msg.author] += 1
                if msg.author not in usersInvolved:
                    usersInvolved.append(msg.author)

            avatarURL = msg.author.avatar.url if hasattr(msg.author, 'avatar') and msg.author.avatar else "https://discord.com/assets/5d6a5e9d7d77ac29116e.png"
            userColor = msg.author.color if hasattr(msg.author, 'color') and msg.author.color != '#000000' else '#dfe0e2'
            username = msg.author.name
            userId = msg.author.id
            isBot = msg.author.bot if hasattr(msg.author, 'bot') else False

            show_user_info = lastUser != msg.author.id
            message_class = "message not-grouped" if show_user_info else "message grouped"

            f.write(f"<div class='{message_class}'>")
            f.write(f"<img class='avatar' src='{avatarURL}' />" if show_user_info else "<div style='width: 40px;'></div>")
            f.write("<div class='content'>")

            if show_user_info:
                f.write(f"<div><span class='username' style='color: {userColor};'>{username}</span>")
                if isBot:
                    f.write("<div class='app-badge' data-toggle='tooltip' title='Verified Bot'>BOT</div>")
                f.write(f"<code class='userid'>({userId})</code></div>")

            if msg.content:
                content = await parse_mentions(interaction, parse_markdown(msg.content))
                f.write(f"<div class='text'>{content}</div>")

            for attachment in msg.attachments:
                if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    f.write(f'<img class="attachment-img" src="{attachment.url}" />')
                elif attachment.filename.lower().endswith(('.mp4', '.mov', '.webm', '.mkv')):
                    f.write(f'<video class="attachment-media" controls> <source src="{attachment.url}" type="video/mp4"> Your browser doesn\'t support embedded videos. </video>')
                elif attachment.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                    f.write(f'<audio class="attachment-media" controls> <source src="{attachment.url}" type="audio/mpeg"> Your browser doesn\'t support embedded audio. </audio>')
                else:
                    f.write(f"<a href='{attachment.url}' download class='media-file'> <img src='https://cdn.discordapp.com/attachments/1026904121237831700/1129787805381423265/file.png' height='20'> <span>{attachment.filename}</span> </a>")

            for embed in msg.embeds:
                if embed.title or embed.description or embed.fields:
                    embedColor = embed.color if embed.color else '#7289da'
                    f.write(f"<div class='embed' style='border-left-color: {embedColor};'>")
                    if embed.title:
                        f.write(f"<div class='embed-title'>{embed.title}</div>")
                    if embed.description:
                        description = await parse_mentions(interaction, parse_markdown(embed.description))
                        f.write(f"<div class='embed-description'>{description}</div>")
                    if embed.fields:
                        f.write("<div class='embed-fields'>")
                        for field in embed.fields:
                            f.write("<div class='embed-field'>")
                            f.write(f"<div class='embed-field-name'>{parse_markdown(field.name)}</div>")
                            f.write(f"<div class='embed-field-value'>{await parse_mentions(interaction, parse_markdown(field.value))}</div>")
                            f.write("</div>")
                        f.write("</div>")
                    f.write("</div>")

            f.write("</div></div>")
            lastUser = msg.author.id

        f.write("</div></body></html>")
        f.close()

        return (f, usersInvolved, user_message_counts)

class ConfirmCloseTicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="yes")
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Closing Ticket...",
            description="Ticket will be closed in 3 seconds",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.edit_message(
            embed=discord.Embed(description="<:yes:1036811164891480194> **Ticket Closure Confirmed**", color=discord.Color.green()), 
            view=None
        )
        msg = await interaction.channel.send(embed=embed)
        left = False
        user = None
        try:
            user = await interaction.guild.fetch_member(int(interaction.channel.topic))
        except Exception:
            left = True

        ref = db.reference("/Tickets")
        tickets = ref.get()
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                LOGCHANNEL_ID = value["Log Channel ID"]
                break
        log = interaction.guild.get_channel(LOGCHANNEL_ID)

        if not user:
            left = True

        f, usersInvolved, user_message_counts = await get_transcript(interaction, user)

        if left == False and user != None:
            embed = discord.Embed(
                title="Ticket closed",
                description=f"Ticket created by {user.mention} is closed by {interaction.user.mention}",
                color=0xE44D41,
            )
            try:
                embed.set_author(
                    name=f"{user.name}", icon_url=user.avatar.url
                )
            except Exception:
                embed.set_author(name=f"{user.name}")
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
        else:
            embed = discord.Embed(
                title="Ticket closed",
                description=f"Ticket created by a member who has left the server is closed by {interaction.user.mention}",
                color=0xE44D41,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        user_list = "\n".join(f"- {user.mention} `({user_message_counts[user]})`" for user in usersInvolved) if usersInvolved else "`None`"
        embed.add_field(name="Users Involved", value=user_list, inline=True)

        with open(f"../Fischl/shared/Tickets/{interaction.channel.id}.html", "r", encoding="utf-8") as f:
            try:
                summary = await generate(
                    f"The following is the entire history of the ticket in a Discord server for a user. "
                    "Please summarise the entire interaction into 1 or 2 sentences. "
                    "Only give 1 response option. Do not output additional text such as 'Here is the summary:'. "
                    f"Do NOT include the channel names, user IDs, server names, Fischl (bot name), or the fact that a ticket is created or closed, since they are trivial.\n\n"
                    "Full transcript:\n"
                    f"{f.read().split('<!DOCTYPE html>')[1]}")
            except Exception as e:
                print(e)
                summary = "`AI Summary Temporarily Unavailable`"

        first_message = [msg async for msg in interaction.channel.history(oldest_first=True)][0]
        embed.add_field(name="Ticket Topic", value=first_message.embeds[0].title)

        log_message = await log.send(
            embed=embed,
            file=discord.File(f"../Fischl/shared/Tickets/{interaction.channel.id}.html")
        )

        with open(f"../Fischl/shared/Tickets/{interaction.channel.id}.html", "rb") as f:
            file_content = f.read()

        checksum = hashlib.sha256(file_content + str(log.id).encode()).hexdigest()[:20]
        token = f"{log.id}-{log_message.id}-{checksum}"
        url = f"https://fischl.app/logs/{token}"

        embed.add_field(name="Transcript Link", value=url, inline=False)
        embed.add_field(name="Ticket Summary", value=summary)
        await log_message.edit(embed=embed)
        embed.title = f"Ticket closed in {interaction.guild.name}"
        await interaction.client.get_channel(1417408712980697099).send(
            embed=embed,
            file=discord.File(f"../Fischl/shared/Tickets/{interaction.channel.id}.html")
        )

        try:
            os.remove(f"../Fischl/shared/Tickets/{interaction.channel.id}.html")
        except Exception:
            pass

        transcript_button = Button(
            style=discord.ButtonStyle.link,
            label="Transcript Link",
            emoji="📜",
            url=url
        )
        user_view = View()
        user_view.add_item(transcript_button)

        embed = discord.Embed(
            title="Ticket closed",
            description=f"Your ticket in **{interaction.guild.name}** is now closed.",
            color=0xE44D41,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(
            text=f"You can always create a new ticket for additional assistance!"
        )
        try:
            await user.send(embed=embed, view=user_view)
            await interaction.channel.set_permissions(
                user, send_messages=False, read_messages=False, attach_files=False
            )
        except Exception:
            pass
        await msg.delete()
        if left == False:
            embed = discord.Embed(
                title="",
                description="Ticket is closed and no longer visible to the member.",
                color=0xE44D41,
            )
        else:
            embed = discord.Embed(
                title="",
                description="Member left the server. Ticket is closed still.",
                color=0xE44D41,
            )
        await interaction.channel.send(embed=embed)
        embed = discord.Embed(
            title="", description="""```STAFF CONTROLS PANEL```""", color=0xE44D41
        )
        view = TicketAdminButtons()
        view.add_item(transcript_button)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.channel.edit(
            topic=f":no_entry_sign: {interaction.channel.topic}"
        )

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, custom_id="no")
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Action Cancelled",
            description=f"Alright {interaction.user.mention}! I will not close the ticket!",
            color=0xFF0000,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.edit_message(embed=embed, view=None)


@app_commands.guild_only()
class Ticket(commands.GroupCog, name="ticket"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="reset", description="Reset the settings of ticket in the server"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_reset(self, interaction: discord.Interaction) -> None:
        tickets = db.reference("/Tickets").get()
        found = False
        for key, val in tickets.items():
            if val["Server ID"] == interaction.guild.id:
                db.reference("/Tickets").child(key).delete()
                found = True
                break
        if found:
            embed = discord.Embed(
                title="Ticket successfully reset",
                description=f"You can use `/ticket setup` at anytime to setup the ticket function again.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="We could not find your server",
                description=f"Maybe you have already reset the ticket function in your server, or you have never enabled ticket function. Anyways, no records found in our system.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_reset.error
    async def ticket_reset_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="setup", description="Setup ticket function in the server"
    )
    @app_commands.describe(
        category="The category to hold all the tickets (If you do not specify, we will create one for you)",
        log_channel="The channel to log all future tickets (If you do not specify, we will create one for you)",
        ping_role="The role to ping for all new tickets (default: None)",
        cooldown="Cooldown between ticket creations per user (format: 3d12h45m; default: 0)"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_guild=True)
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel = None,
        log_channel: discord.TextChannel = None,
        ping_role: discord.Role = None,
        cooldown: str = None
    ) -> None:
        ref = db.reference("/Tickets")
        tickets = ref.get()
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                embed = discord.Embed(
                    title="Ticket already enabled!",
                    description=f'The category is already set as <#{value["Category ID"]}> `({value["Category ID"]})` and the ticket log channel is already set as <#{value["Log Channel ID"]}> `({value["Log Channel ID"]})`\n\nPlease use `/ticket button` or `/ticket dropdown` to create your own customized ticket panel.\n\nIf you wish to reset the settings of tickets, please use `/ticket reset`.',
                    colour=0xFF0000,
                )
                embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        if not category:
            category = await interaction.guild.create_category("Tickets")
        if not log_channel:
            log_channel = await interaction.guild.create_text_channel(
                f"ticket-log", category=category
            )

        embed = discord.Embed(
            title="What is this?",
            description=f"This channel logs all ticket deletion and creation events! It clearly provides server moderators a list of past tickets. ",
            colour=discord.Color.blurple(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await log_channel.send(embed=embed)

        await category.set_permissions(
            interaction.guild.default_role, read_messages=False
        )
        await log_channel.set_permissions(
            interaction.guild.default_role, read_messages=False
        )
        
        cooldown_in_seconds = 0
        cooldown_str = []
        
        if cooldown is not None:
            days = re.search(r"(\d+)d", cooldown)
            hours = re.search(r"(\d+)h", cooldown)
            minutes = re.search(r"(\d+)m", cooldown)
            
            if days:
                cooldown_in_seconds += int(days.group(1)) * 86400
                cooldown_str.append(f"{days.group(1)}d")
            if hours:
                cooldown_in_seconds += int(hours.group(1)) * 3600
                cooldown_str.append(f"{hours.group(1)}h")
            if minutes:
                cooldown_in_seconds += int(minutes.group(1)) * 60
                cooldown_str.append(f"{minutes.group(1)}m")
        
        cooldown_readable = ", ".join(cooldown_str) if cooldown_str else "0s"

        data = {
            interaction.guild.name: {
                "Server Name": interaction.guild.name,
                "Server ID": interaction.guild.id,
                "Category ID": category.id,
                "Ping Role ID": ping_role.id if ping_role is not None else None,
                "Log Channel ID": log_channel.id,
                "Cooldown": cooldown_in_seconds
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        embed = discord.Embed(
            title="Ticket System Successfully Enabled!",
            description=(
                f"- Tickets will be created under the category <#{category.id}> `({category.id})`, "
                f"and logs will be sent to <#{log_channel.id}> `({log_channel.id})`.\n"
                f"- A **cooldown of {cooldown_readable}** is applied per user between ticket creations.\n"
                f"- {ping_role.mention if ping_role is not None else '**No roles**'} will be pinged for every new ticket.\n"
                "- **By default, all administrators can view tickets.** "
                "To allow additional staff roles to view tickets, use `/ticket addrole`."
                "To remove them, use `/ticket removerole`.\n"
                "- To set up your custom ticket panel, use either `/ticket button` "
                "or `/ticket dropdown`.\n"
                "**Bonus:** Use `/ticket instructions` to customize welcome messages for each ticket topic."
            ),
            colour=0x00FF00,
        )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed)
    @ticket_setup.error
    async def ticket_setup_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="addrole", description="Add a role that can see and manage tickets"
    )
    @app_commands.describe(
        role="The role at your own choice that can see and manage tickets"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    async def ticket_addrole(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                CATEGORY_ID = value["Category ID"]
                LOGCHANNEL_ID = value["Log Channel ID"]
                found = True
                break

        if found:
            category = interaction.guild.get_channel(CATEGORY_ID)
            log_channel = interaction.guild.get_channel(LOGCHANNEL_ID)
            await category.set_permissions(
                role,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            )
            await log_channel.set_permissions(
                role,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
            )
            for channel in category.channels:
                await channel.set_permissions(
                    role,
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    manage_channels=True,
                    manage_messages=True,
                    read_message_history=True,
                )
            embed = discord.Embed(
                title="Role Added!",
                description=f"{role.mention} now has the following permissions in all ticket-related channels:\n\n`- Read Messages`\n`- Send Messages`\n`- Attach Files`\n`- Manage Channels`\n`- Manage Messages`\n`- Read Message History`",
                colour=0x00FF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Ticket not enabled!",
                description=f"This server doesn't have a ticket category or a log channel. Please ask the server moderators to use `/ticket setup` to setup tickets!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_addrole.error
    async def ticket_addrole_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="removerole", description="Remove a role that can see and manage tickets"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.describe(
        role="The role at your own choice that can no longer see and manage tickets"
    )
    async def ticket_removerole(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                CATEGORY_ID = value["Category ID"]
                LOGCHANNEL_ID = value["Log Channel ID"]
                found = True
                break

        if found:
            category = interaction.guild.get_channel(CATEGORY_ID)
            log_channel = interaction.guild.get_channel(LOGCHANNEL_ID)
            await category.set_permissions(
                role,
                read_messages=None,
                send_messages=None,
                attach_files=None,
                manage_channels=None,
                manage_messages=None,
                read_message_history=None,
            )
            await log_channel.set_permissions(
                role,
                read_messages=None,
                send_messages=None,
                attach_files=None,
                manage_channels=None,
                manage_messages=None,
                read_message_history=None,
            )
            for channel in category.channels:
                await channel.set_permissions(
                    role,
                    read_messages=None,
                    send_messages=None,
                    attach_files=None,
                    manage_channels=None,
                    manage_messages=None,
                    read_message_history=None,
                )
            embed = discord.Embed(
                title="Role Added!",
                description=f"{role.mention} now has the following permissions in all ticket-related channels:\n\n`- Read Messages`\n`- Send Messages`\n`- Attach Files`\n`- Manage Channels`\n`- Manage Messages`\n`- Read Message History`",
                colour=0x00FF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Ticket not enabled!",
                description=f"This server doesn't have a ticket category or a log channel. Please ask the server moderators to use `/ticket setup` to setup tickets!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_removerole.error
    async def ticket_removerole_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="notify",
        description="Send a DM to ticket author requiring their attention",
    )
    @app_commands.describe(message="Optional message to be included in the DMs")
    async def ticket_notify(
        self, interaction: discord.Interaction, message: str = None
    ) -> None:
        if message is None:
            message = " "
        else:
            message = f"\n\n> {message}"
        try:
            user = await interaction.guild.fetch_member(int(interaction.channel.topic))
        except Exception:
            return
        embed = discord.Embed(
            title="⚠️ Notification ⚠️",
            description=f"The ticket you created in **{interaction.guild.name}** needs your attention! Please kindly respond.{message}\n\nIf you no longer need assistance or your issue has been resolved, **please still let us know in the ticket** so we can help close the ticket.",
            color=0xE44D41,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        try:
            button = Button(
                style=discord.ButtonStyle.link,
                label="Head over to your ticket",
                emoji="🎫",
                url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
            )
            view = View()
            view.add_item(button)
            await user.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"{user.mention} received a DM notification."
            )
        except Exception:
            await interaction.response.send_message(
                "<:no:1036810470860013639> Unable to DM user!", ephemeral=True
            )

    @app_commands.command(
        name="delete", description="Deletes an existing ticket channel"
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_delete(self, interaction: discord.Interaction) -> None:
        try:
            user = await interaction.guild.fetch_member(
                int(interaction.channel.topic.split(":")[2])
            )
            embed = discord.Embed(
                title="Deleting Ticket...",
                description="Ticket will be deleted in 5 seconds",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed)
            await asyncio.sleep(5)
            await interaction.channel.delete()
        except Exception:
            embed = discord.Embed(
                title="Invalid Action",
                description="This command can only be used in ticket channels, or this ticket has not been closed.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_delete.error
    async def ticket_delete_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="close",
        description="Closes the current ticket and prevents ticket author from viewing the ticket",
    )
    async def ticket_close(self, interaction: discord.Interaction) -> None:
        if ":no_entry_sign:" in interaction.channel.topic:
            embed = discord.Embed(
                title="Ticket already closed :no_entry_sign:",
                description="This ticket is already closed.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            embed = discord.Embed(
                title="Are you sure about that?",
                description="Only moderators and administrators can reopen the ticket.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(
                embed=embed, view=ConfirmCloseTicketButtons(), ephemeral=True
            )
        except Exception:
            embed = discord.Embed(
                title="Invalid Action",
                description="This command can only be used in ticket channels.",
                color=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="button", description="Creates a ticket panel with buttons"
    )
    @app_commands.describe(
        title="Makes the title of the embed",
        description="Makes the description of the embed",
        color="Sets the color of the embed",
        thumbnail="Please provide a URL for the thumbnail of the embed (upper-right hand corner image)",
        image="Please provide a URL for the image of the embed (appears at the bottom of the embed)",
        footer="Sets the footer of the embed that appears at the bottom of the embed as small texts",
        footer_time="Shows the time of the embed being sent?",
        button_emoji="Sets the emoji of the button (Supports custom emoji)",
        button_text="Sets the text of the button",
        button_color="Chooses a color for the button",
    )
    @app_commands.choices(
        button_color=[
            discord.app_commands.Choice(name="Grey", value="Grey"),
            discord.app_commands.Choice(name="Green", value="Green"),
            discord.app_commands.Choice(name="Blurple", value="Blurple"),
            discord.app_commands.Choice(name="Red", value="Red"),
        ]
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_button(
        self,
        interaction: discord.Interaction,
        title: str = None,
        description: str = None,
        color: str = None,
        thumbnail: str = None,
        image: str = None,
        footer: str = None,
        footer_time: bool = None,
        button_emoji: str = "🎫",
        button_text: str = "Create Ticket",
        button_color: str = None,
    ) -> None:
        # Converting color
        if color is not None:
            try:
                color = await commands.ColorConverter().convert(interaction, color)
            except:
                color = None
        if color is None:
            color = discord.Color.default()
        embed = discord.Embed(color=color)
        if title is not None:
            embed.title = title
        if description is not None:
            embed.description = description
        if thumbnail is not None:
            embed.set_thumbnail(url=thumbnail)
        if image is not None:
            embed.set_image(url=image)
        if footer is not None:
            embed.set_footer(text=footer)
        if footer_time is not None or footer_time == True:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        if button_emoji != "🎫":
            button_emoji = emoji.emojize(button_emoji.strip())
        if button_color == "Grey":
            color = discord.ButtonStyle.grey
        elif button_color == "Blurple":
            color = discord.ButtonStyle.blurple
        elif button_color == "Red":
            color = discord.ButtonStyle.red
        else:
            color = discord.ButtonStyle.green

        await interaction.channel.send(
            embed=embed, view=CreateTicketButtonView(button_text, button_emoji, color)
        )
        embed = discord.Embed(
            title="<:yes:1036811164891480194> Custom Ticket Panel Sent",
            description="All members who have access to this channel can create a ticket by clicking the button below the panel!",
            color=0x00FF00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_button.error
    async def ticket_button_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="dropdown", description="Creates a ticket panel with dropdown menu"
    )
    @app_commands.describe(
        title="Makes the title of the embed",
        description="Makes the description of the embed",
        color="Sets the color of the embed",
        thumbnail="Please provide a URL for the thumbnail of the embed (upper-right hand corner image)",
        image="Please provide a URL for the image of the embed (appears at the bottom of the embed)",
        footer="Sets the footer of the embed that appears at the bottom of the embed as small texts",
        footer_time="Shows the time of the embed being sent?",
        dropdown_placeholder="Sets the placeholder of the dropdown menu",
        dropdown1_emoji="Sets the emoji of the first option",
        dropdown1_title="Sets the title of the first option",
        dropdown1_description="Sets the description of the first option",
        dropdown2_emoji="Sets the emoji of the second option",
        dropdown2_title="Sets the title of the second option",
        dropdown2_description="Sets the description of the second option",
        dropdown3_emoji="Sets the emoji of the third option",
        dropdown3_title="Sets the title of the third option",
        dropdown3_description="Sets the description of the third option",
        dropdown4_emoji="Sets the emoji of the fourth option",
        dropdown4_title="Sets the title of the fourth option",
        dropdown4_description="Sets the description of the fourth option",
        dropdown5_emoji="Sets the emoji of the fifth option",
        dropdown5_title="Sets the title of the fifth option",
        dropdown5_description="Sets the description of the fifth option",
    )
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_dropdown(
        self,
        interaction: discord.Interaction,
        title: str = None,
        description: str = None,
        color: str = None,
        thumbnail: str = None,
        image: str = None,
        footer: str = None,
        footer_time: bool = None,
        dropdown_placeholder: str = "Select a Category",
        dropdown1_emoji: str = None,
        dropdown1_title: str = None,
        dropdown1_description: str = None,
        dropdown2_emoji: str = None,
        dropdown2_title: str = None,
        dropdown2_description: str = None,
        dropdown3_emoji: str = None,
        dropdown3_title: str = None,
        dropdown3_description: str = None,
        dropdown4_emoji: str = None,
        dropdown4_title: str = None,
        dropdown4_description: str = None,
        dropdown5_emoji: str = None,
        dropdown5_title: str = None,
        dropdown5_description: str = None,
    ) -> None:
        # Converting color
        if color is not None:
            try:
                color = await commands.ColorConverter().convert(interaction, color)
            except:
                color = None
        if color is None:
            color = discord.Color.default()
        embed = discord.Embed(color=color)
        if title is not None:
            embed.title = title
        if description is not None:
            embed.description = description
        if thumbnail is not None:
            embed.set_thumbnail(url=thumbnail)
        if image is not None:
            embed.set_image(url=image)
        if footer is not None:
            embed.set_footer(text=footer)
        if footer_time is not None or footer_time == True:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        options = []

        list = [
            [dropdown1_emoji, dropdown1_title, dropdown1_description],
            [dropdown2_emoji, dropdown2_title, dropdown2_description],
            [dropdown3_emoji, dropdown3_title, dropdown3_description],
            [dropdown4_emoji, dropdown4_title, dropdown4_description],
            [dropdown5_emoji, dropdown5_title, dropdown5_description],
        ]

        for item in list:
            if item[1] is None and (
                item[0] is not None or item[2] is not None
            ):  # Title missing
                embed = discord.Embed(
                    title="Dropdown Menu Option's Title Missing",
                    description="You must include a title for every option!",
                    color=0xFF0000,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if (
                item[0] is not None and item[1] is not None and item[2] is not None
            ):  # Emoji + Title + Description
                emote = emoji.emojize(item[0].strip())
                title = item[1].strip()
                description = item[2].strip()
                options.append(
                    discord.SelectOption(
                        label=title, value=title, description=description, emoji=emote
                    ),
                )
            elif (
                item[0] is None and item[1] is not None and item[2] is not None
            ):  # Title + Description
                title = item[1].strip()
                description = item[2].strip()
                options.append(
                    discord.SelectOption(
                        label=title, value=title, description=description
                    ),
                )
            elif (
                item[0] is not None and item[1] is not None and item[2] is None
            ):  # Emoji + Title
                emote = emoji.emojize(item[0].strip())
                title = item[1].strip()
                options.append(
                    discord.SelectOption(label=title, value=title, emoji=emote),
                )
            elif (
                item[0] is None and item[1] is not None and item[2] is None
            ):  # Title Only
                title = item[1].strip()
                options.append(
                    discord.SelectOption(label=title, value=title),
                )

        await interaction.channel.send(
            embed=embed, view=SelectView(dropdown_placeholder, options)
        )
        embed = discord.Embed(
            title="<:yes:1036811164891480194> Custom Ticket Panel Sent",
            description="All members who have access to this channel can create a ticket by selecting the dropdown menu below the panel!",
            color=0x00FF00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @ticket_dropdown.error
    async def ticket_dropdown_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="add", description="Add a user to the current ticket (Mods only)")
    @app_commands.describe(user="User to add to channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if ":no_entry_sign:" in interaction.channel.topic or not interaction.channel.topic:
            await interaction.response.send_message("<:no:1036810470860013639> This is not a valid ticket channel.", ephemeral=True)
            return
        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        embed = discord.Embed(description=f"{user.mention} has been added to this ticket.", color=0x00FF00)
        await interaction.response.send_message(embed=embed)
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                LOGCHANNEL_ID = value["Log Channel ID"]
                break
        log_channel = interaction.guild.get_channel(LOGCHANNEL_ID)
        left = False
        try:
            user = await interaction.guild.fetch_member(int(interaction.channel.topic))
        except Exception:
            left = True
        log_embed = discord.Embed(
            title="User Added",
            description=(
                f"{user.mention} was added by {interaction.user.mention} to "
                f"{user.mention}'s ticket." if not left else
                "a ticket created by someone who left the server."
            ),
            color=0x6b9f6b
        )
        log_embed.set_footer(text=f"Ticket ID: {interaction.channel.id}")
        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
        )
        view = View()
        view.add_item(button)
        await log_channel.send(embed=log_embed, view=view)
    @ticket_add.error
    async def ticket_add_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="create", description="Create a ticket for a user (Mods only, bypasses cooldown & blacklist)")
    @app_commands.describe(user="Specify a user")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_create(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                CATEGORY_ID = value["Category ID"]
                LOGCHANNEL_ID = value["Log Channel ID"]
                found = True
                break

        if not found:
            embed = discord.Embed(
                title="Ticket not enabled!",
                description=f"This server doesn't have a ticket category or a log channel. Please use `/ticket setup` to setup tickets first!",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        category = interaction.guild.get_channel(CATEGORY_ID)

        for channel in category.channels:
            if str(channel.topic) == str(user.id):
                await interaction.followup.send(
                    content=f"<:no:1036810470860013639> {user.mention} already has their ticket created at <#{channel.id}>.",
                    ephemeral=True,
                )
                return

        log = interaction.guild.get_channel(LOGCHANNEL_ID)
        embed = discord.Embed(title="Ticket created", description=f"Staff {interaction.user.mention} created a new ticket for {user.mention} <t:{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}:R>!", color=discord.Colour.green())
        embed.add_field(name="Ticket Topic", value="Created by server staff")

        try:
            chn = await interaction.guild.create_text_channel(
                f"{user.name}", category=category
            )

            await chn.edit(topic=user.id)
            await chn.set_permissions(
                user, send_messages=True, read_messages=True, attach_files=True
            )
        except Exception:
            await interaction.followup.send(
                content=f"<:no:1036810470860013639> **I'm missing permissions to create or edit text channels!** \nPlease make sure my role has `MANAGE_CHANNELS` permissions.", ephemeral=True
            )
            return

        try:
            embed.set_author(
                name=f"{user.name}", icon_url=interaction.user.avatar.url
            )
        except Exception:
            embed.set_author(name=f"{user.name}")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"Ticket ID: {chn.id}")

        button = Button(
            style=discord.ButtonStyle.link,
            label="View Ticket",
            url=f"https://discord.com/channels/{interaction.guild.id}/{chn.id}",
        )
        view = View()
        view.add_item(button)
        await log.send(embed=embed, view=view)
        embed.title = f"Ticket created in {interaction.guild.name}"
        await interaction.client.get_channel(1417408712980697099).send(embed=embed)

        roles = user.roles
        roles.reverse()

        embed = discord.Embed(
            title=f"New Ticket",
            description=f"This ticket is created *by {interaction.user.mention}* for {user.mention}! \nYou can use `/ticket close` or click the red button below to close this ticket.",
            color=discord.Colour.gold(),
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.add_field(
            name="User Mention", value=f"{user.mention}", inline=True
        )
        embed.add_field(name="User ID", value=f"{user.id}", inline=True)
        embed.add_field(name="Highest Role", value=f"{roles[0].mention}", inline=True)
        embed.add_field(
            name="Ticket Created",
            value=f"<t:{int(chn.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Server Joined",
            value=f"<t:{int(user.joined_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(user.created_at.timestamp())}:R>",
            inline=True,
        )
        await chn.send(
            f"**{user.mention}, welcome!** {'[ <@&1309928108312498227> ]' if interaction.guild.id == 1281655927791030293 else ''}",
            embed=embed,
            view=CloseTicketButton(),
        )
        
        try:
            await user.send(f":warning: A staff in **{interaction.guild.name}** has created a ticket for you and requires your attention.\n<:reply:1036792837821435976> <#{chn.id}>")
            dm = True
        except:
            dm = False
            pass
            
        message_status = "and the user is notified via DM" if dm else "but I'm unable to DM the user"
        content = f"<:yes:1036811164891480194> Ticket for {user.mention} created at <#{chn.id}> {message_status}"

        await interaction.followup.send(
            content=content, ephemeral=True
        )
    @ticket_create.error
    async def ticket_create_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="blacklist", description="View all blacklisted users or blacklist a user")
    @app_commands.describe(user="User to blacklist (leave empty to view all blacklisted users)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_blacklist(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer(thinking=True)
        if user is None:
            # Fetch blacklisted users from Firebase
            ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}")
            blacklisted_users = ref.get()

            if not blacklisted_users:
                embed = discord.Embed(
                    description="No users are currently blacklisted from creating tickets.",
                    color=0x00FF00
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Convert user IDs to mentions or raw IDs
            user_list = []
            for user_id in blacklisted_users.keys():
                user = await interaction.guild.fetch_member(int(user_id))
                if user:
                    user_list.append(f"- {user.mention} (`{user_id}`)")
                else:
                    user_list.append(f"- `{user_id}` (User not in server)")

            # Format into an embed
            embed = discord.Embed(
                title=f"Blacklisted Users ({len(user_list)})",
                description="\n".join(user_list),
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {interaction.user.name}")
            await interaction.followup.send(embed=embed)
        else:
            ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}/{user.id}")
            ref.set(True)
            embed = discord.Embed(description=f"{user.mention} has been blacklisted from creating tickets.", color=0x00FF00)
            await interaction.followup.send(embed=embed)
    @ticket_blacklist.error
    async def ticket_blacklist_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="unblacklist", description="Unblacklist a user from creating tickets")
    @app_commands.describe(user="User to unblacklist")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_unblacklist(self, interaction: discord.Interaction, user: discord.Member):
        ref = db.reference(f"/Ticket Blacklist/{interaction.guild.id}/{user.id}")
        ref.delete()
        embed = discord.Embed(description=f"{user.mention} has been unblacklisted.", color=0x00FF00)
        await interaction.response.send_message(embed=embed)
    @ticket_unblacklist.error
    async def ticket_unblacklist_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
    @app_commands.command(name="instructions", description="Manage custom ticket instructions")
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_guild=True)
    async def ticket_instructions(self, interaction: discord.Interaction):
        ref = db.reference(f"/Ticket Instructions/{interaction.guild.id}")
        data = ref.get()
        pages = await get_instruction_embeds(interaction, data or {})
        await interaction.response.send_message(embed=pages[0], view=InstructionView(pages=pages), ephemeral=True)
    @ticket_instructions.error
    async def ticket_instructions_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

class InstructionModal(discord.ui.Modal, title="Add Ticket Instructions"):
    category = discord.ui.TextInput(label="Ticket Topic", placeholder="e.g. General Support", required=True)
    embed_title = discord.ui.TextInput(label="Embed Title", placeholder="Title of the embed", required=True, max_length=256)
    embed_description = discord.ui.TextInput(label="Embed Description", placeholder="Content of the embed", style=discord.TextStyle.paragraph, required=True, max_length=4000)
    embed_color = discord.ui.TextInput(label="Embed Color (Hex code)", placeholder="e.g. #FF0000", required=True, max_length=7)

    async def on_submit(self, interaction: discord.Interaction):
        category = str(self.category)
        embed_title = str(self.embed_title)
        embed_description = str(self.embed_description)
        embed_color = str(self.embed_color)
        if embed_color[0] != "#":
            embed_color = f"#{embed_color}"
        
        ref = db.reference(f"/Ticket Instructions/{interaction.guild.id}/{category}")
        ref.set({
            "title": embed_title,
            "description": embed_description,
            "color": embed_color
        })
        self.update = await interaction.response.send_message(f"<:yes:1036811164891480194> Instructions for Ticket Topic `{category}` saved! \nAbove is the preview of the embed message that will be sent in the ticket channel (besides the footer!).\n-# :person_raising_hand: If you are not satisfied with it, click **Remove this Instruction** and re-add one!", ephemeral=True)
        self.on_submit_interaction = interaction
        self.stop()

async def get_instruction_embeds(interaction, instructions: dict):
    if not instructions:
        embed = discord.Embed(
            title="No Ticket Instructions Found",
            description=(
                "There are currently no custom instructions set for any ticket topics.\n\n"
                "Click **Add an Instruction** below to create one.\n\n"
                "*Ticket topics refer to the option labels shown in a `/ticket dropdown`, or the embed titles in a `/ticket button`.*"
            ),
            color=discord.Color.orange()
        )

        return [embed]
    pages = []
    for i, (cat, embed_info) in enumerate(instructions.items()):
        embed = discord.Embed(
            title=embed_info.get("title", "No Title"),
            description=embed_info.get("description", "No Description"),
            color=int(embed_info.get("color", "#5865F2").lstrip('#'), 16)
        )
        embed.set_footer(text=f"Ticket Topic: {cat} | Page {i + 1} of {len(instructions)}")
        pages.append(embed)
    return pages

class InstructionView(discord.ui.View):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.page = 0
        self.is_empty = pages[0].title == "No Ticket Instructions Found"

        if self.is_empty:
            for child in self.children:
                if child.label in {"<<", "<", ">", ">>", "Remove this Instruction"}:
                    child.disabled = True

    @discord.ui.button(emoji="<:fastbackward:1351972112696479824>", style=discord.ButtonStyle.secondary)
    async def first(self, interaction, button): 
        self.page = 0
        await interaction.response.edit_message(embed=self.pages[self.page])

    @discord.ui.button(emoji="<:backarrow:1351972111010369618>", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button): 
        self.page = (self.page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.page])

    @discord.ui.button(emoji="<:rightarrow:1351972116819480616>", style=discord.ButtonStyle.secondary)
    async def forward(self, interaction, button): 
        self.page = (self.page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.page])

    @discord.ui.button(emoji="<:fastforward:1351972114433048719>", style=discord.ButtonStyle.secondary)
    async def last(self, interaction, button):
        self.page = len(self.pages) - 1
        await interaction.response.edit_message(embed=self.pages[self.page])

    @discord.ui.button(label="Add an Instruction", style=discord.ButtonStyle.success, row=1)
    async def add_instruction(self, interaction, button):
        modal = InstructionModal()
        await interaction.response.send_modal(modal)
        response = await modal.wait()
        ref = db.reference(f"/Ticket Instructions/{interaction.guild.id}")
        data = ref.get()
        pages = await get_instruction_embeds(interaction, data or {})
        await interaction.edit_original_response(embed=pages[0], view=InstructionView(pages=pages))
        
    @discord.ui.button(label="Remove this Instruction", style=discord.ButtonStyle.danger, row=1)
    async def remove_instruction(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        try:
            category = self.pages[self.page].footer.text.split("Ticket Topic: ")[1].split(" |")[0]
            db.reference(f"/Ticket Instructions/{interaction.guild.id}/{category}").delete()
            
            ref = db.reference(f"/Ticket Instructions/{interaction.guild.id}")
            data = ref.get()
            pages = await get_instruction_embeds(interaction, data or {})
            await interaction.edit_original_response(embed=pages[0], view=InstructionView(pages=pages))
            await interaction.followup.send(f"<:yes:1036811164891480194> Instructions for Ticket Topic `{category}` removed. 🗑️", ephemeral=True)
        except Exception:
            await interaction.followup.send("⚠️ No instruction to remove on this page.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ticket(bot))