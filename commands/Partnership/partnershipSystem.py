import asyncio
import datetime
import re
from typing import List, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View
from firebase_admin import db

from utils.commands import SlashCommand

YES = "<:yes:1036811164891480194>"
NO = "<:no:1036810470860013639>"
BLURPLE = "#5865F2"
NO_ICON = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTEkPA5_-j6SudIbSZh-ExIs1eSeuCYIIRthjHfg0P2dbwUH2E&s"
THREADS_PICTURE = "https://media.discordapp.net/attachments/1106727534479032341/1366102857366896781/thread_instructions.png?ex=680fb9ee&is=680e686e&hm=4a80c4dda380d4b3e5ef7781576a9be6981e909a0179780e50dc605b1a4570c1&="
STATUSES = {
    "pending": ("🟡", 0xFEE75C),
    "accepted": ("🟢", 0x57F287),
    "rejected": ("🔴", 0xED4245),
    "blacklisted": ("⚫", 0x000000),
}
STAFF = app_commands.checks.has_permissions(manage_webhooks=True, manage_channels=True)
EDITORS = app_commands.checks.has_permissions(
    manage_webhooks=True, manage_channels=True, manage_messages=True
)


def ref(name, guild_id):
    """Gives one server's part of the partnership data; BrawlKit keeps its own here too."""
    return db.reference(f"Partner/{name}/{guild_id}")


def color(text):
    """Turns a hex code like #5865F2 into a number."""
    return int(text.lstrip("#"), 16)


def plural(count, word):
    """Gives "1 message" or "2 messages"."""
    return f"{count} {word}{'s' if count != 1 else ''}"


def edge(section, colour, title, name):
    """Builds the header or footer embed, or a hint on how to edit it when it is empty."""
    embed = discord.Embed(
        title=section.get("title", None),
        description=section.get("description", None),
        color=color(section.get("color", BLURPLE)),
    )
    if embed.title is None and embed.description is None:
        embed = discord.Embed(
            title=title,
            description=f'Use {SlashCommand("partner edit-panel")} and select `{name}` to edit this embed!',
            color=colour,
        )
    if "thumbnail" in section:
        embed.set_thumbnail(url=section["thumbnail"])
    if "image" in section:
        embed.set_image(url=section["image"])
    return embed


def link(partner, group):
    """Gives a partner's line on the panel; an all-digit invite is a bot's ID."""
    url = (
        f"https://discord.com/oauth2/authorize?client_id={partner['invite']}"
        if partner["invite"].isdigit()
        else f"https://discord.gg/{partner['invite']}"
    )
    return f"{group.get('prefix', '')} [{partner['name']}]({url}) {group.get('suffix', '')}"


def letter_fields(partners, group):
    """Splits a group's sorted partners into fields named by their first letters."""
    fields = []
    first, start = "A", 0
    while first <= "Z" and start < len(partners):
        while start < len(partners) and partners[start]["name"][0].upper() < first:
            start += 1
        if start == len(partners):
            break

        lines, length, end = [], 0, start
        for index in range(start, len(partners)):
            line = link(partners[index], group)
            if length + len(line) + 1 > 1024:
                break
            lines.append(line)
            length += len(line) + 1
            end = index + 1
        if not lines:
            first = chr(ord(first) + 1) if first != "Z" else "Z"
            continue

        last = partners[end - 1]["name"][0].upper()
        fields.append([first, last, "\n".join(lines)])
        first = chr(ord(last) + 1) if last != "Z" else "Z"
        start = end

    if fields:
        fields[-1][1] = "Z"
    return [(f"{first} - {last}", value) for first, last, value in fields]


async def _build_panel_embeds(guild_id: int) -> List[discord.Embed]:
    """Builds the panel: the header, each group's partners by letter, and the footer."""
    config = ref("config", guild_id).get()
    partners = ref("partners", guild_id).get() or {}
    groups = ref("categories", guild_id).get() or {}
    sections = config.get("embed", {})
    header = sections.get("header", {})
    footer = sections.get("footer", {})
    fallback = color(header.get("color", BLURPLE))

    embeds = [edge(header, fallback, "Server Partner List", "Header")]
    for name, group in groups.items():
        members = sorted(
            (p for p in partners.values() if p.get("category") == name),
            key=lambda partner: partner["name"].lower(),
        )
        fields = letter_fields(members, group)
        for index in range(0, len(fields), 25):
            embed = discord.Embed(
                title=group.get("title", name),
                color=color(group.get("color", BLURPLE)),
            )
            if group.get("thumbnail"):
                embed.set_thumbnail(url=group["thumbnail"])
            for field, value in fields[index : index + 25]:
                embed.add_field(name=field, value=value, inline=False)
            embeds.append(embed)

    last = edge(footer, fallback, "Instructions", "Footer")
    last.set_footer(text="⚡ Panel automatically updated • Powered by Fischl")
    return embeds + [last]


def _calculate_embed_size(embed: discord.Embed) -> int:
    """Counts an embed's characters, with 100 to spare."""
    size = len(embed.title or "") + len(embed.description or "") + 100
    if embed.author:
        size += len(embed.author.name or "")
    if embed.footer:
        size += len(embed.footer.text or "")
    return size + sum(len(field.name) + len(field.value) for field in embed.fields)


def _group_embeds_by_message_limit(
    embeds: List[discord.Embed], limit: int = 6000
) -> List[List[discord.Embed]]:
    """Splits embeds into messages that each stay under Discord's size limit."""
    groups, size = [[]], 0
    for embed in embeds:
        if size + _calculate_embed_size(embed) > limit and groups[-1]:
            groups.append([])
            size = 0
        groups[-1].append(embed)
        size += _calculate_embed_size(embed)
    return groups if groups[-1] else []


def panel_messages(panel):
    """Gives a panel's message IDs; old panels stored only one."""
    if "message_ids" in panel:
        return panel.get("message_ids", [])
    return [panel["message_id"]] if "message_id" in panel else []


def request_view(last):
    """Gives the Request Partnership button for a panel's last message only."""
    if not last:
        return None
    view = View()
    view.add_item(PartnerRequestButton())
    return view


async def _update_panel(guild_id: int, bot):
    """Rewrites a server's panel in place and gives the line to tell staff, or None."""
    config = ref("config", guild_id).get()
    panel = ref("panels", guild_id).get()
    if not config or not panel:
        return None

    try:
        channel = bot.get_channel(panel["channel_id"])
        if not channel:
            return None

        groups = _group_embeds_by_message_limit(await _build_panel_embeds(guild_id))
        old = panel_messages(panel)
        new = []
        for index, embeds in enumerate(groups):
            view = request_view(index == len(groups) - 1)
            message = None
            if index < len(old):
                try:
                    message = await channel.fetch_message(old[index])
                    await message.edit(embeds=embeds, view=view)
                except (discord.NotFound, discord.Forbidden):
                    message = None
            if message is None:
                message = await channel.send(embeds=embeds, view=view)
            new.append(message.id)

        for message_id in old[len(groups) :]:
            try:
                await (await channel.fetch_message(message_id)).delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        ref("panels", guild_id).set(
            {"message_ids": new, "channel_id": panel["channel_id"]}
        )
        return f"{YES} Panel updated! ({plural(len(groups), 'message')})"
    except Exception as e:
        return f"{NO} Failed to update panel: {e}"


async def category_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    """Suggests the server's groups that contain what was typed."""
    groups = ref("categories", interaction.guild.id).get() or {}
    return [
        app_commands.Choice(name=name, value=name)
        for name in groups
        if current.lower() in name.lower()
    ][:25]


class PartnershipFirebaseListener:
    """Updates a server's panel when its partners, groups or settings change in Firebase."""

    def __init__(self, bot):
        self.bot = bot
        self.update_queue = asyncio.Queue()
        self.update_task = None

    def start_listeners(self):
        for name in ("partners", "categories", "config"):
            db.reference(f"Partner/{name}").listen(self.changed)
        self.update_task = asyncio.create_task(self._process_updates())
        print("[Partnership] Firebase listeners started successfully")

    def stop_listeners(self):
        if self.update_task:
            self.update_task.cancel()

    def changed(self, event):
        """Queues every server a Firebase event touches; runs on Firebase's thread."""
        if event.path == "/":
            guilds = list(event.data.keys()) if event.data else []
        else:
            guilds = event.path.split("/")[1:2]
        for guild_id in guilds:
            if not guild_id:
                continue
            try:
                asyncio.run_coroutine_threadsafe(
                    self.update_queue.put(int(guild_id)), self.bot.loop
                )
            except Exception as e:
                print(f"[Partnership] Error queuing update: {e}")

    async def _process_updates(self):
        """Updates each queued server once after 2 quiet seconds."""
        pending = {}
        while True:
            try:
                try:
                    guild_id = await asyncio.wait_for(
                        self.update_queue.get(), timeout=2.0
                    )
                    pending[guild_id] = None
                except asyncio.TimeoutError:
                    if pending:
                        guilds = list(pending)
                        pending.clear()
                        for guild_id in guilds:
                            await self._execute_panel_update(guild_id)
                        await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Partnership] Error processing updates: {e}")
                await asyncio.sleep(1)

    async def _execute_panel_update(self, guild_id):
        try:
            if not ref("panels", guild_id).get():
                return
            result = await _update_panel(guild_id, self.bot)
            if result and "Failed" not in result:
                print(f"[Partnership] Panel update successful for guild {guild_id}")
            elif result is not None:
                print(
                    f"[Partnership] Panel update failed for guild {guild_id}: {result}"
                )
        except Exception as e:
            print(
                f"[Partnership] Error executing panel update for guild {guild_id}: {e}"
            )


async def _log_action(
    client, guild_id: int, user: discord.User, action: str, details: dict, button=None
):
    """Posts what a member did in the server's partnership log channel."""
    channel_id = (ref("config", guild_id).get() or {}).get("log_channel")
    channel = client.get_channel(channel_id) if channel_id else None
    if not channel:
        return

    embed = discord.Embed(
        title=f"{action}",
        color=0x5865F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    for key, value in details.items():
        embed.add_field(name=key, value=str(value), inline=False)

    view = None
    if button:
        view = View()
        view.add_item(button)
    await channel.send(embed=embed, view=view)


async def fetch_invite(code, **params):
    """Gives the status and answer for an invite; a failed detailed ask has no answer."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://discord.com/api/v9/invites/{code}", params=params or None
        ) as resp:
            if resp.status != 200 and params:
                return resp.status, None
            return resp.status, await resp.json()


def permanent(data):
    """Says whether an invite never expires, as text for an embed."""
    return f"{YES} Yes" if data.get("expires_at", None) is None else f"{NO} No"


async def thread_for(channel, bot_id, server_id):
    """Finds the request channel's thread, open or archived, for a server."""
    threads = channel.threads + [thread async for thread in channel.archived_threads()]
    for thread in threads:
        try:
            async for message in thread.history(limit=2, oldest_first=True):
                if message.author.id != bot_id or len(message.embeds) == 0:
                    continue
                for field in message.embeds[0].fields:
                    if field.name == "Server ID" and field.value == str(server_id):
                        return thread
        except Exception as e:
            print(e)
    return None


def thread_embed(title, data, who, user):
    """Builds the first message of a partnership thread."""
    guild = data.get("guild", {})
    embed = discord.Embed(
        title=title,
        description=f"-# - Staff can use {SlashCommand('partner status')} to update the thread and {SlashCommand('partner add-partner')} to add partner to the panel.\n-# - Everyone here can use {SlashCommand('partner invite')} to invite other server reps/staff to this thread.",
        color=0xFEE75C,
    )
    embed.add_field(name="Server ID", value=guild["id"], inline=True)
    embed.add_field(name="Server Name", value=guild.get("name"), inline=True)
    embed.add_field(
        name="Members",
        value=data.get("approximate_member_count", "Unknown"),
        inline=True,
    )
    embed.add_field(name="Permanent Server Invite", value=permanent(data), inline=True)
    embed.add_field(name=f"{who} ID", value=user.id, inline=True)
    embed.add_field(name=f"{who} Mention", value=user.mention, inline=True)
    embed.set_footer(text="Status: 🟡 Pending")
    return embed


def invite_code(url):
    """Pulls the invite code out of a link pasted in a partner list."""
    for start in ("discord.gg/", "discord.com/invite/"):
        if start in url:
            return url.split(start)[-1].split("/")[0]
    return url.rstrip("/").split("/")[-1]


class PartnershipRequestModal(Modal, title="Partnership Request"):
    invite_link = TextInput(
        label="Your Server's Permanent Invite Link",
        required=True,
        placeholder="Other details will be fetched automatically.",
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cooldown = ref("Cooldown", interaction.guild.id).child(str(interaction.user.id))
        waited = datetime.datetime.now().timestamp() - (cooldown.get() or 0)
        config = ref("config", interaction.guild.id).get()
        wait = config.get("user_cooldown", 0)
        manager = config.get("partner_manager_role_id", None)

        if waited < wait:
            remaining = int(wait - waited)
            await interaction.followup.send(
                f"{NO} You're on cooldown! Try again in {remaining//3600}h {remaining%3600//60}m",
                ephemeral=True,
            )
            return

        try:
            code = self.invite_link.value.split("/")[-1]
            status, data = await fetch_invite(
                code, with_counts="true", with_expiration="true"
            )
            if status != 200:
                await interaction.followup.send(
                    f"{NO} Invalid invite link!", ephemeral=True
                )
                return
            guild = data.get("guild", {})
            icon = guild.get("icon")
            icon = (
                f"https://cdn.discordapp.com/icons/{guild['id']}/{icon}.png"
                if icon
                else NO_ICON
            )
        except Exception as e:
            await interaction.followup.send(
                f"{NO} Failed to validate invite!```{e}```", ephemeral=True
            )
            return

        if ref("Blacklist", interaction.guild.id).child(guild["id"]).get():
            await interaction.followup.send(
                f"{NO} This server is blacklisted! If you believe this is a mistake, contact a server staff and ask them to unblacklist your server!",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(config["request_channel"])
        thread = await thread_for(channel, interaction.client.user.id, guild["id"])
        if thread:
            await interaction.followup.send(
                f"{NO} A partnership thread for this server already exists: {thread.mention}",
                ephemeral=True,
            )
            return

        thread = await channel.create_thread(
            name=f"🟡 {guild.get('name')}", type=discord.ChannelType.private_thread
        )
        await thread.add_user(interaction.user)

        embed = thread_embed(
            "New Partnership Request", data, "Requester", interaction.user
        )
        embed.set_thumbnail(url=icon)
        ping = f"<@&{manager}>" if manager not in [None, ""] else ""
        await thread.send(content=f"{ping} {self.invite_link}", embed=embed)

        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            f"New Partnership Request ({guild.get('name')})",
            {
                "Server ID": guild.get("id"),
                "Server Name": guild.get("name"),
                "Invite Link": f"https://discord.gg/{code}",
                "Permanent Invite": permanent(data),
                "Members": data.get("approximate_member_count", "Unknown"),
            },
            Button(
                label="Go to thread",
                style=discord.ButtonStyle.link,
                url=thread.jump_url,
            ),
        )
        await interaction.followup.send(
            f"{YES} Request created in {thread.mention}", ephemeral=True
        )
        cooldown.set(datetime.datetime.now().timestamp())


class EditPanelModal(Modal):
    """Edits the panel's header or footer embed."""

    def __init__(self, section, current):
        super().__init__(title=f"Edit {section.capitalize()} Embed")
        self.section = section
        self.title_input = TextInput(
            label="Title",
            required=False,
            placeholder="Enter an embed title",
            default=current.get("title", ""),
        )
        self.description = TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            required=False,
            placeholder="Enter an embed description",
            default=current.get("description", ""),
        )
        self.color = TextInput(
            label="Color (hex code)",
            required=False,
            placeholder="e.g. #0f0f0f",
            default=current.get("color", BLURPLE),
        )
        self.thumbnail = TextInput(
            label="Thumbnail URL",
            required=False,
            placeholder="Enter an link for thumbnail image",
            default=current.get("thumbnail", ""),
        )
        self.image = TextInput(
            label="Image URL",
            required=False,
            placeholder="Enter an link for large image",
            default=current.get("image", ""),
        )
        for field in (
            self.title_input,
            self.description,
            self.color,
            self.thumbnail,
            self.image,
        ):
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        updates = {
            "title": self.title_input.value.strip() or None,
            "description": self.description.value.strip() or None,
            "color": self.color.value.strip() or BLURPLE,
            "thumbnail": self.thumbnail.value.strip() or None,
            "image": self.image.value.strip() or None,
        }
        section = ref("config", interaction.guild.id).child(f"embed/{self.section}")
        existing = section.get() or {}
        changes = {
            key: value for key, value in updates.items() if value != existing.get(key)
        }
        if not changes:
            await interaction.response.send_message(
                f"{NO} No changes detected!", ephemeral=True
            )
            return

        section.update(changes)
        msg = await _update_panel(interaction.guild.id, interaction.client)
        for key, value in changes.items():
            if value is None:
                section.child(key).delete()

        await interaction.response.send_message(f"{msg}", ephemeral=True)
        if "Failed to update panel" not in msg:
            await _log_action(
                interaction.client,
                interaction.guild.id,
                interaction.user,
                f"Panel Edited ({self.section.capitalize()})",
                changes,
            )


class EditGroupModal(Modal, title="Edit Partner Group"):
    def __init__(self, original_name: str, current: dict):
        super().__init__()
        self.original_name = original_name
        prefix = current.get("prefix", "-")
        suffix = current.get("suffix", "")
        self.name_input = TextInput(
            label="Unique Group Name",
            placeholder="Letters, numbers, underscores, hyphens",
            default=original_name,
            required=True,
        )
        self.title_input = TextInput(
            label="Display Title",
            default=current.get("title", ""),
            required=False,
        )
        self.color = TextInput(
            label="Color (hex)",
            default=current.get("color", BLURPLE),
            required=False,
        )
        self.prefix_suffix = TextInput(
            label="Prefix, Suffix (separated by a comma)",
            placeholder="Example: -, >",
            default=f"{prefix}, {suffix}".strip(", "),
            required=False,
        )
        self.thumbnail = TextInput(
            label="Thumbnail URL",
            default=current.get("thumbnail", ""),
            required=False,
        )
        for field in (
            self.name_input,
            self.title_input,
            self.color,
            self.prefix_suffix,
            self.thumbnail,
        ):
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        prefix, _, suffix = self.prefix_suffix.value.partition(",")
        updates = {
            "title": self.title_input.value.strip() or new_name,
            "color": self.color.value.strip(),
            "prefix": prefix.strip(),
            "suffix": suffix.strip(),
            "thumbnail": self.thumbnail.value.strip() or None,
        }

        if not re.match(r"^[\w-]+$", new_name):
            await interaction.response.send_message(
                f"{NO} Invalid group name! Only letters, numbers, underscores, and hyphens allowed.",
                ephemeral=True,
            )
            return

        groups = ref("categories", interaction.guild.id)
        if new_name.lower() != self.original_name.lower() and any(
            name.lower() == new_name.lower() for name in groups.get() or {}
        ):
            await interaction.response.send_message(
                f"{NO} Group name already exists!", ephemeral=True
            )
            return

        if new_name != self.original_name:
            groups.child(self.original_name).delete()
            partners = ref("partners", interaction.guild.id)
            for key, partner in (partners.get() or {}).items():
                if partner.get("category") == self.original_name:
                    partners.child(key).update({"category": new_name})

        groups.child(new_name).update(updates)

        msg = await _update_panel(interaction.guild.id, interaction.client)
        await interaction.response.send_message(
            f"{YES} Group updated! \n{msg}", ephemeral=True
        )
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Group Edited",
            {"Original Name": self.original_name, "New Name": new_name, **updates},
        )


class Partner(commands.GroupCog, name="partner"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.firebase_listener = PartnershipFirebaseListener(bot)

    async def cog_load(self):
        self.firebase_listener.start_listeners()

    async def cog_unload(self):
        self.firebase_listener.stop_listeners()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(name="status", description="Update partnership status")
    @app_commands.describe(status="New status", reason="Reason for status change")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="🟡 Pending", value="pending"),
            app_commands.Choice(name="🟢 Accepted", value="accepted"),
            app_commands.Choice(name="🔴 Rejected", value="rejected"),
            app_commands.Choice(name="⚫ Blacklisted", value="blacklisted"),
        ]
    )
    @STAFF
    async def partner_status(
        self,
        interaction: discord.Interaction,
        status: str,
        reason: str = "No reason provided",
    ):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                f"{NO} This command must be used in a partnership thread!",
                ephemeral=True,
            )
            return

        emoji, colour = STATUSES[status]
        old_name = interaction.channel.name
        for mark, _ in STATUSES.values():
            old_name = old_name.removeprefix(mark)
        old_name = old_name.strip()
        await interaction.channel.edit(name=f"{emoji} {old_name}")

        async for message in interaction.channel.history(limit=2, oldest_first=True):
            if (
                message.author.id != interaction.client.user.id
                or len(message.embeds) == 0
            ):
                continue
            embed = message.embeds[0]
            embed.color = colour
            embed.set_footer(
                text=f"Status: {emoji} {status.capitalize()} | Reason: {reason}"
            )
            await message.edit(embed=embed)

        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            f"Partner Status Updated {emoji}",
            {"Server Name": old_name},
        )
        await interaction.response.send_message(
            f"{YES} Status updated to {emoji} {status}!", ephemeral=True
        )

    @app_commands.command(
        name="invite",
        description="Invite server representatives to the partnership thread",
    )
    @app_commands.describe(user="User to invite")
    async def partner_invite(
        self, interaction: discord.Interaction, user: discord.User
    ):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                f"{NO} This command can only be used in partnership threads!",
                ephemeral=True,
            )
            return

        try:
            await interaction.channel.add_user(user)
            await interaction.response.send_message(
                f"{YES} {user.mention} has been added to the thread!", ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                f"{NO} Sorry, something went wrong!", ephemeral=True
            )

    @app_commands.command(
        name="create",
        description="Manually create a partnership thread (bypasses blacklist)",
    )
    @app_commands.describe(invite_link="Permanent invite link for the server")
    @STAFF
    async def partner_create(self, interaction: discord.Interaction, invite_link: str):
        await interaction.response.defer(ephemeral=True)
        config = ref("config", interaction.guild.id).get()

        try:
            code = invite_link.split("/")[-1]
            status, data = await fetch_invite(code, with_counts="true")
            if status != 200:
                await interaction.followup.send(
                    f"{NO} Invalid invite link!", ephemeral=True
                )
                return
            guild = data.get("guild", {})
        except Exception as e:
            await interaction.followup.send(
                f"{NO} Error validating invite: {e}", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(config["request_channel"])
        thread = await thread_for(channel, interaction.client.user.id, guild["id"])
        if thread:
            await interaction.followup.send(
                f"{NO} A partnership thread for this server already exists: {thread.mention}",
                ephemeral=True,
            )
            return

        thread = await channel.create_thread(
            name=f"🟡 {guild.get('name')}", type=discord.ChannelType.private_thread
        )
        embed = thread_embed(
            "Partnership Thread (initiated by Staff)", data, "Staff", interaction.user
        )
        await thread.send(content=invite_link, embed=embed)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            f"Staff Partnership Thread Creation ({guild.get('name')})",
            {
                "Server ID": guild.get("id"),
                "Server Name": guild.get("name"),
                "Invite Link": f"https://discord.gg/{code}",
                "Members": data.get("approximate_member_count", "Unknown"),
            },
        )
        await interaction.followup.send(
            f"{YES} Thread created: {thread.mention}. Use {SlashCommand('partner invite')} to invite server representatives to the thread!",
            ephemeral=True,
        )

    @app_commands.command(
        name="blacklist", description="Blacklist a server from partnerships"
    )
    @app_commands.describe(
        invite_link="The invite link of server to blacklist (Leave blank to view blacklist)"
    )
    @STAFF
    async def partner_blacklist(
        self, interaction: discord.Interaction, invite_link: Optional[str] = None
    ):
        if not invite_link:
            blacklist = ref("Blacklist", interaction.guild.id).get() or {}
            if not blacklist:
                return await interaction.response.send_message(
                    "No servers are blacklisted!", ephemeral=True
                )

            embed = discord.Embed(title="Blacklisted Server ID", color=0xFF0000)
            embed.description = "\n".join(f"- `{gid}`" for gid in blacklist.keys())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            _, data = await fetch_invite(invite_link.split("/")[-1])
            guild_id = data["guild"]["id"]
        except Exception as e:
            await interaction.response.send_message(
                f"{NO} Invalid invite: {e}", ephemeral=True
            )
            return

        ref("Blacklist", interaction.guild.id).child(guild_id).set(True)
        await interaction.response.send_message(
            f"{YES} Server {guild_id} blacklisted!", ephemeral=True
        )

    @app_commands.command(
        name="unblacklist", description="Remove a server from blacklist"
    )
    @app_commands.describe(guild_id="Server ID to unblacklist")
    @STAFF
    async def partner_unblacklist(
        self, interaction: discord.Interaction, guild_id: str
    ):
        server = ref("Blacklist", interaction.guild.id).child(guild_id)
        if not server.get():
            await interaction.response.send_message(
                f"{NO} Server not in blacklist!", ephemeral=True
            )
            return

        server.delete()
        await interaction.response.send_message(
            f"{YES} Server {guild_id} unblacklisted!", ephemeral=True
        )

    @app_commands.command(name="edit-panel", description="Edit panel embeds")
    @app_commands.describe(section="Section to edit")
    @app_commands.choices(
        section=[
            app_commands.Choice(name="Header", value="header"),
            app_commands.Choice(name="Footer", value="footer"),
        ]
    )
    @EDITORS
    async def partner_edit_panel(self, interaction: discord.Interaction, section: str):
        current = (
            ref("config", interaction.guild.id).child(f"embed/{section}").get() or {}
        )
        await interaction.response.send_modal(EditPanelModal(section, current))

    @app_commands.command(name="disable", description="Disable partnership system")
    @STAFF
    async def partner_disable(self, interaction: discord.Interaction):
        config = ref("config", interaction.guild.id)
        if not config.get():
            await interaction.response.send_message(
                f"{NO} Partnership system not enabled!", ephemeral=True
            )
            return

        panel = ref("panels", interaction.guild.id).get()
        if panel:
            try:
                channel = self.bot.get_channel(panel.get("channel_id"))
                for message_id in panel_messages(panel) if channel else ():
                    try:
                        await (await channel.fetch_message(message_id)).delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
            except Exception as e:
                print(f"[Partnership] Error deleting panel messages: {e}")

        config.delete()
        for name in ("panels", "categories", "partners"):
            ref(name, interaction.guild.id).delete()

        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Partnership System Disabled",
            {"Status": "All configurations removed"},
        )
        await interaction.response.send_message(
            f"{YES} Partnership system disabled! All configurations removed.",
            ephemeral=True,
        )

    @app_commands.command(name="send-panel", description="Send the partnership panel")
    @STAFF
    async def partner_send_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        config = ref("config", interaction.guild.id).get()
        if not config:
            await interaction.followup.send(
                f"{NO} Partnership system not enabled!", ephemeral=True
            )
            return

        try:
            channel = self.bot.get_channel(config["panel_channel"])
            if not channel:
                await interaction.followup.send(
                    f"{NO} Panel channel not found!", ephemeral=True
                )
                return

            embeds = await _build_panel_embeds(interaction.guild.id)
            groups = _group_embeds_by_message_limit(embeds)
            messages = []
            for index, group in enumerate(groups):
                message = await channel.send(
                    embeds=group, view=request_view(index == len(groups) - 1)
                )
                messages.append(message.id)

            ref("panels", interaction.guild.id).set(
                {"message_ids": messages, "channel_id": channel.id}
            )
            await _log_action(
                interaction.client,
                interaction.guild.id,
                interaction.user,
                "Panel Sent",
                {
                    "Channel": channel.mention,
                    "Message Count": len(messages),
                    "Embed Count": len(embeds),
                },
            )
            await interaction.followup.send(
                f"{YES} Partnership panel sent! ({plural(len(messages), 'message')}, {plural(len(embeds), 'embed')})\n*All other panels sent previously will no longer automatically update.*",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"{NO} Failed to send panel: {e}", ephemeral=True
            )

    @app_commands.command(
        name="update-panel", description="Manually update the partnership panel"
    )
    @STAFF
    async def partner_update_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not ref("config", interaction.guild.id).get():
            await interaction.followup.send(
                f"{NO} Partnership system not enabled!", ephemeral=True
            )
            return

        if not ref("panels", interaction.guild.id).get():
            await interaction.followup.send(
                f"{NO} No panel found! Use `/partner send-panel` first.",
                ephemeral=True,
            )
            return

        result = await _update_panel(interaction.guild.id, self.bot)
        if result and "Failed" not in result:
            await interaction.followup.send(
                f"{result}\n*Panel updated successfully.*", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"{result or f'{NO} Update failed for unknown reason.'}",
                ephemeral=True,
            )

    @app_commands.command(
        name="add-group",
        description="Create new partner group with separate panel embed",
    )
    @app_commands.describe(
        name="Unique group name (no spaces)",
        title="Display title (default: the group name)",
        color="Embed color in hex code (default: #5865F2)",
        prefix="Line prefix (default: bullet point)",
        suffix="Line suffix (default: None)",
        thumbnail="Thumbnail URL (optional)",
    )
    @STAFF
    async def partner_add_group(
        self,
        interaction: discord.Interaction,
        name: str,
        title: Optional[str] = None,
        color: Optional[str] = "#5865F2",
        prefix: Optional[str] = "-",
        suffix: Optional[str] = "",
        thumbnail: Optional[str] = None,
    ):
        if not re.match(r"^[\w-]+$", name):
            await interaction.response.send_message(
                f"{NO} Group name can only contain letters, numbers, underscores and hyphens!",
                ephemeral=True,
            )
            return

        groups = ref("categories", interaction.guild.id)
        if name.lower() in [group.lower() for group in (groups.get() or {})]:
            await interaction.response.send_message(
                f"{NO} Group already exists!", ephemeral=True
            )
            return

        groups.child(name).set(
            {
                "title": title or name,
                "color": color,
                "prefix": prefix,
                "suffix": suffix,
                "thumbnail": thumbnail,
                "created_at": datetime.datetime.now().timestamp(),
            }
        )
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
                "Thumbnail": thumbnail or "None",
            },
        )
        await interaction.response.send_message(
            f"{YES} Group '{name}' created! To delete a group, use {SlashCommand('partner remove-group')}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="edit-group", description="Edit an existing partner group"
    )
    @app_commands.describe(group="Group to edit")
    @app_commands.autocomplete(group=category_autocomplete)
    @STAFF
    async def partner_edit_group(self, interaction: discord.Interaction, group: str):
        groups = ref("categories", interaction.guild.id).get() or {}
        if group not in groups:
            await interaction.response.send_message(
                f"{NO} Group not found!", ephemeral=True
            )
            return

        await interaction.response.send_modal(EditGroupModal(group, groups[group]))

    @app_commands.command(
        name="remove-group", description="⚠️ Remove a group and ALL its partners"
    )
    @app_commands.describe(name="Group name to remove")
    @app_commands.autocomplete(name=category_autocomplete)
    @STAFF
    async def partner_remove_group(self, interaction: discord.Interaction, name: str):
        groups = ref("categories", interaction.guild.id)
        if name not in (groups.get() or {}):
            await interaction.response.send_message(
                f"{NO} Group not found!", ephemeral=True
            )
            return

        partners = ref("partners", interaction.guild.id)
        deleted = 0
        for key, partner in (partners.get() or {}).items():
            if partner.get("category") == name:
                partners.child(key).delete()
                deleted += 1
        groups.child(name).delete()

        await _update_panel(interaction.guild.id, interaction.client)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Group Removed",
            {"Group Name": name, "Partners Deleted": deleted},
        )
        await interaction.response.send_message(
            f"{YES} Group '{name}' and its {deleted} partner(s) were permanently deleted!",
            ephemeral=True,
        )

    @app_commands.command(name="setup", description="Set up partnership system")
    @app_commands.describe(
        log_channel="Channel for partnership logs",
        partner_role="Role to grant server partners",
        request_channel="Channel to create partnership threads under",
        panel_channel="Channel to send the partnership panel",
        partner_manager_role="Staff role to ping for new partnership requests (default: None)",
        user_cooldown="Cooldown between user requests (format: 3d12h45m; default: 0)",
    )
    @STAFF
    async def partner_setup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
        partner_role: discord.Role,
        request_channel: discord.TextChannel,
        panel_channel: discord.TextChannel,
        partner_manager_role: discord.Role = None,
        user_cooldown: str = "0m",
    ):
        match = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?", user_cooldown)
        if not match:
            await interaction.response.send_message(
                "⚠️ Invalid cooldown format. Use something like `3d12h45m`, `5h`, or `30m`.",
                ephemeral=True,
            )
            return
        days, hours, minutes = (int(part or 0) for part in match.groups())
        pretty = ", ".join(
            plural(count, word)
            for count, word in ((days, "day"), (hours, "hour"), (minutes, "minute"))
            if count
        )

        ref("config", interaction.guild.id).update(
            {
                "log_channel": log_channel.id,
                "partner_role": partner_role.id,
                "request_channel": request_channel.id,
                "panel_channel": panel_channel.id,
                "user_cooldown": days * 86400 + hours * 3600 + minutes * 60,
                "partner_manager_role_id": (
                    str(partner_manager_role.id)
                    if partner_manager_role is not None
                    else ""
                ),
                "enabled": True,
            }
        )

        embed = discord.Embed(
            title=f"{YES} Partnership System Setup Complete!",
            description=(
                "Here are something you can do next to make everything work:\n"
                f"- Check out {panel_channel.mention} and {request_channel.mention} and follow the instructions there.\n"
                f"- Use {SlashCommand('partner add-group')} to group partners (e.g., \"Hangouts\", \"Genshin\", \"HSR\", etc).  \n"
                "  - **Name**: A short ID is required (no spaces, like `Genshin_Impact`).  \n"
                '  - **Title**: The display name of the group (e.g., "🎮 Genshin Impact Servers").  \n'
                "  - **Prefix/Suffix**: Customize how server links appear on the panel with your favorite symbols.  \n"
                "  - Partners will only show up on the panel if they're in a group!\n"
                f"- Try {SlashCommand('partner add-partner')} and {SlashCommand('partner remove-partner')} to test add/remove partners.\n"
                f"- Use {SlashCommand('partner create')} to manually create a partnership thread as a staff\n\n"
                "**⚙️ Your Configured Settings**"
            ),
            color=0x00FF00,
        )
        fields = {
            "Log Channel": log_channel.mention,
            "Request Channel": request_channel.mention,
            "Panel Channel": panel_channel.mention,
            "Partner Role": partner_role.mention,
            "Partner Manager Role *(pinged for new requests)*": (
                partner_manager_role.mention
                if partner_manager_role is not None
                else "None"
            ),
            "User Cooldown": pretty or "None",
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)
        await interaction.response.send_message(embed=embed)

        try:
            panel = await panel_channel.send(
                embeds=await _build_panel_embeds(interaction.guild.id),
                view=request_view(True),
            )
            ref("panels", interaction.guild.id).set(
                {"message_id": panel.id, "channel_id": panel_channel.id}
            )

            await log_channel.send(
                embed=discord.Embed(
                    description="📝 This channel will be used for logging all partnership-related actions.",
                    color=0x5865F2,
                )
            )

            instructions = discord.Embed(
                title="Partnership Request Instructions", color=0x5865F2
            )
            instructions.add_field(
                name="For Server Representatives",
                value=f"1. Click `Request Partnership` **[here]({panel.jump_url})** in {panel_channel.mention}\n2. Check existing threads using:\n  - **Threads <:thread_icon:1366092363822268598> button** at channel top\n  - **Channel Sidebar** on desktop (hover → 'See All')",
                inline=False,
            )
            instructions.add_field(
                name="For Staff Only",
                value=f"- Manage partnership requests in threads. Use the methods above to access all the threads.\n- Use {SlashCommand('partner create')} to manually create a partnership thread.",
                inline=False,
            )
            instructions.set_image(url=THREADS_PICTURE)
            instructions.set_footer(
                text="You may delete/replace this message if you wish to."
            )
            await request_channel.send(embed=instructions)
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Partially completed setup: {type(e).__name__} - {str(e)}",
                ephemeral=True,
            )

    @app_commands.command(
        name="mass-add-partner",
        description="Mass add partner servers from formatted text",
    )
    @app_commands.describe(
        group="Group that servers belong to",
        content="Formatted partner list (each line: [Server Name](invite_link))",
    )
    @app_commands.autocomplete(group=category_autocomplete)
    @EDITORS
    async def partner_mass_add(
        self, interaction: discord.Interaction, group: str, content: str
    ):
        await interaction.response.defer(ephemeral=True)

        if group not in (ref("categories", interaction.guild.id).get() or {}):
            await interaction.followup.send(
                f"{NO} Invalid group! Create groups first using {SlashCommand('partner add-group')}.",
                ephemeral=True,
            )
            return

        added = 0
        errors = []
        for number, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", line.strip())
            if not match:
                errors.append(f"Line {number}: Invalid format")
                continue
            code = invite_code(match.group(2))
            if not code:
                errors.append(f"Line {number}: Couldn't extract invite code")
                continue

            try:
                ref("partners", interaction.guild.id).push().set(
                    {
                        "name": match.group(1),
                        "invite": code,
                        "member_count": 0,
                        "staff_id": interaction.user.id,
                        "created_at": int(datetime.datetime.now().timestamp()),
                        "category": group,
                    }
                )
                added += 1
            except Exception as e:
                errors.append(f"Line {number}: {str(e)}")

        update_msg = await _update_panel(interaction.guild.id, interaction.client)

        response = f"{YES} Added {added} partners to group `{group}`!\n{update_msg}"
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
            {"Group": group, "Added Count": added, "Error Count": len(errors)},
        )

    @app_commands.command(name="add-partner", description="Add a partner server")
    @app_commands.describe(
        name="Server name",
        invite_link="Server's permanent invite link (please include 'https://')",
        group="Group that server belongs (use /partner add-group to create a group)",
        server_rep="The server's representative to get the partner role",
    )
    @app_commands.autocomplete(group=category_autocomplete)
    @EDITORS
    async def add_partner(
        self,
        interaction: discord.Interaction,
        name: str,
        invite_link: str,
        group: str,
        server_rep: discord.User = None,
    ):
        await interaction.response.defer(ephemeral=True)
        if group not in (ref("categories", interaction.guild.id).get() or {}):
            await interaction.followup.send(
                f"{NO} Invalid group! Create groups first using {SlashCommand('partner add-group')}.",
                ephemeral=True,
            )
            return

        if server_rep is not None:
            config = ref("config", interaction.guild.id).get()
            try:
                await server_rep.add_roles(
                    interaction.guild.get_role(int(config.get("partner_role", {})))
                )
            except Exception:
                await interaction.followup.send(
                    f"{NO} Invalid partner role. Double check to see if the role has been deleted.",
                    ephemeral=True,
                )
                return

        bot = invite_link.isdigit()
        code, members = invite_link, "N/A"
        if not bot:
            try:
                code = invite_link.split("/")[-1]
                status, data = await fetch_invite(
                    code, with_counts="true", with_expiration="true"
                )
                if status != 200:
                    await interaction.followup.send(
                        f"{NO} Invalid invite link!", ephemeral=True
                    )
                    return
                if data.get("expires_at", None) is not None:
                    await interaction.followup.send(
                        f"{NO} Invite link is not permanent.", ephemeral=True
                    )
                    return
                members = data.get("approximate_member_count", 0)
            except Exception as e:
                await interaction.followup.send(
                    f"{NO} Failed to validate invite!```{e}```", ephemeral=True
                )
                return

        ref("partners", interaction.guild.id).push().set(
            {
                "name": name,
                "invite": code,
                "member_count": members,
                "staff_id": interaction.user.id,
                "created_at": int(datetime.datetime.now().timestamp()),
                "category": group,
            }
        )
        await _update_panel(interaction.guild.id, interaction.client)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Bot Partner Added" if bot else "Partner Added",
            {
                "Server Name": name,
                "Invite Code": code,
                "Category": group,
                "Member Count": members,
            },
        )
        await interaction.followup.send(
            f"{YES} Bot partner added!" if bot else f"{YES} Partner server added!",
            ephemeral=True,
        )

    @app_commands.command(name="remove-partner", description="Remove a partner server")
    @app_commands.describe(
        server_name="Server name to remove", invite="Invite link to remove"
    )
    @EDITORS
    async def remove_partner(
        self,
        interaction: discord.Interaction,
        server_name: Optional[str] = None,
        invite: Optional[str] = None,
    ):
        if not server_name and not invite:
            await interaction.response.send_message(
                f"{NO} You must provide either server name or invite link!",
                ephemeral=True,
            )
            return

        partners = ref("partners", interaction.guild.id).get() or {}
        found = None
        for key, partner in partners.items():
            named = server_name and partner["name"].lower() == server_name.lower()
            invited = invite and partner["invite"] in invite
            if not named and not invited:
                continue
            if server_name and invite and not (named and invited):
                await interaction.response.send_message(
                    f"{NO} Server name and invite don't match!", ephemeral=True
                )
                return
            found = key
            break

        if not found:
            await interaction.response.send_message(
                f"{NO} Partner server not found!", ephemeral=True
            )
            return

        ref("partners", interaction.guild.id).child(found).delete()
        await _update_panel(interaction.guild.id, interaction.client)
        await _log_action(
            interaction.client,
            interaction.guild.id,
            interaction.user,
            "Partner Removed",
            {
                "Partner ID": found,
                "Server Name": partners[found]["name"],
                "Invite Code": partners[found]["invite"],
            },
        )
        await interaction.response.send_message(
            f"{YES} Partner server removed!", ephemeral=True
        )


class PartnerRequestButtonView(discord.ui.View):
    def __init__(self, *, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(PartnerRequestButton())


class PartnerRequestButton(Button):
    def __init__(self):
        super().__init__(
            label="Request Partnership",
            style=discord.ButtonStyle.blurple,
            custom_id="partner_request",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PartnershipRequestModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(Partner(bot))
