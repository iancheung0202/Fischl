# tagCommands.py
import discord, firebase_admin, datetime, asyncio, time
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import importlib
import os

def word(n):
    return str(n) + ("th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))

def script(string, user, guild):
    if "{mention}" in string:
        string = string.replace("{mention}", f"{user.mention}")
    if "{server}" in string:
        string = string.replace("{server}", f"{guild.name}")
    if "{user}" in string:
        string = string.replace("{user}", f"{user.name}")
    return string

class tag_embed_modal(discord.ui.Modal, title="Setup Tag Roles Thank You Message"):
    msg = discord.ui.TextInput(label="Message Content", style=discord.TextStyle.paragraph, placeholder="Visit fischl.app/variables for all dynamic variables", max_length=2000, required=False)
    embedtitle = discord.ui.TextInput(label="Embed Title", style=discord.TextStyle.paragraph, placeholder="Visit fischl.app/variables for all dynamic variables", max_length=256, required=False)
    description = discord.ui.TextInput(label="Embed Description", style=discord.TextStyle.paragraph, placeholder="Visit fischl.app/variables for all dynamic variables", max_length=4000, required=False)
    color = discord.ui.TextInput(label="Embed Color", style=discord.TextStyle.short, placeholder="Use hex code (e.g. #ff0000)", max_length=7, required=False)
    image = discord.ui.TextInput(label="Embed Image", style=discord.TextStyle.paragraph, placeholder="Put a permanent image link", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        ref = db.reference("/Tag Thanks Message")
        try:
            for key, val in ref.get().items():
                if val['Server ID'] == interaction.guild.id:
                    db.reference('/Tag Thanks Message').child(key).delete()
                    break
        except: pass
        
        data = {
            "Server ID": interaction.guild.id,
            "Message Content": self.msg.value,
            "Title": self.embedtitle.value,
            "Description": self.description.value,
            "Color": self.color.value,
            "Image Link": self.image.value
        }
        ref.push().set(data)

        ref = db.reference("/Tag Thanks")
        welcome = ref.get()
        for key, val in welcome.items():
            if val['Server ID'] == interaction.guild.id:
                thankyouChannel = "DM" if val["DM"] else f'<#{val["Channel ID"]}>'
                break

        embed = discord.Embed(
            title="✅ Tag Role Thank You Message Enabled!",
            description=f"Congratulations! The bot will now send a thank-you message in **{thankyouChannel}** when users set the required server tag!\n\n*Note: The thank-you message will only be sent if the user hasn't been thanked in the past 24 hours.*",
            colour=0x00FF00
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@app_commands.guild_only()
class TagCommands(commands.GroupCog, name="tag"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="migrate",
        description="Migrate tag role configuration from Fischl Vanity to Fischl"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def tag_migrate(
        self,
        interaction: discord.Interaction,
    ) -> None:
        try:
            with open("./commands/Tag/tagEnabledGuilds.py", "r+") as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    if line.startswith("enabledGuilds ="):
                        guilds = eval(line.split("=")[1].strip())
                        if interaction.guild.id not in guilds:
                            guilds.append(interaction.guild.id)
                        lines[i] = f"enabledGuilds = {guilds}\n"
                        break
                file.seek(0)
                file.writelines(lines)
                file.truncate()
            print(f"[MIGRATION] Added server ID {interaction.guild.id} to tagEnabledGuilds.py")
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to write to file: {e}")

        embed = discord.Embed(
            title="Tag roles migrated successfully!", 
            description=f'Your tag role configuration has been successfully migrated from Fischl Vanity to Fischl. You can now manage your tag roles using the commands in Fischl.\n\n*Note: If you had thank-you messages enabled, your settings have also been migrated.*\n\nYou should now kick Fischl Vanity from your server to avoid duplicate functionality.', 
            colour=0x00FFBB
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="enable",
        description="Enable tag roles in the server"
    )
    @app_commands.describe(
        sample_user="The user who has your desired tag",
        role="The role to give when a user has the tag",
        log_channel="The log channel for tag role actions"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def tag_enable(
        self,
        interaction: discord.Interaction,
        sample_user: discord.Member,
        role: discord.Role,
        log_channel: discord.TextChannel
    ) -> None:
        try:
            tag_server_id = sample_user.primary_guild.id
        except:
            await interaction.response.send_message("❌ Erroreous sample user", ephemeral=True)
            return

        ref = db.reference("/Tag Roles")
        try:
            for key, val in ref.get().items():
                if val['Server ID'] == interaction.guild.id:
                    db.reference('/Tag Roles').child(key).delete()
                    break
        except: pass

        data = {
            "Server ID": interaction.guild.id,
            "Tag Server ID": tag_server_id,
            "Role ID": role.id,
            "Log Channel ID": log_channel.id
        }
        ref.push().set(data)

        embed = discord.Embed(
            title="✅ Tag Roles Enabled!",
            description=f"Users with the tag **{sample_user.primary_guild.tag}** `{tag_server_id}` will receive {role.mention}.\nAll actions will be logged in {log_channel.mention}.",
            colour=0x00FF00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Add to enabled guilds
        with open("./commands/Tag/tagEnabledGuilds.py", "r+") as file:
            lines = file.readlines()
            for i, line in enumerate(lines):
                if line.startswith("enabledGuilds ="):
                    guilds = eval(line.split("=")[1].strip())
                    if interaction.guild.id not in guilds:
                        guilds.append(interaction.guild.id)
                    lines[i] = f"enabledGuilds = {guilds}\n"
                    break
            file.seek(0)
            file.writelines(lines)
            file.truncate()
        
        # Initial role assignment
        for member in interaction.guild.members:
            if member.primary_guild and member.primary_guild.id == tag_server_id and member.primary_guild.tag is not None:
                if role not in member.roles:
                    await member.add_roles(role)
                    embed = discord.Embed(
                        description=f"✅ {member.mention} was given the tag role (initial setup)",
                        colour=0x00FF00
                    )
                    await log_channel.send(embed=embed)

    @app_commands.command(
        name="disable",
        description="Disable tag roles in the server"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def tag_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        ref = db.reference("/Tag Roles")
        found = False
        
        try:
            # Remove from all databases
            for path in ["/Tag Roles", "/Tag Thanks", "/Tag Thanks Message"]:
                ref = db.reference(path)
                for key, val in ref.get().items():
                    if val['Server ID'] == interaction.guild.id:
                        ref.child(key).delete()
                        found = True
        except Exception as e:
            print(f"Error disabling tag roles: {e}")

        if found:
            # Remove from enabled guilds
            with open("./commands/Tag/tagEnabledGuilds.py", "r+") as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    if line.startswith("enabledGuilds ="):
                        guilds = eval(line.split("=")[1].strip())
                        if interaction.guild.id in guilds:
                            guilds.remove(interaction.guild.id)
                        lines[i] = f"enabledGuilds = {guilds}\n"
                        break
                file.seek(0)
                file.writelines(lines)
                file.truncate()
            
            embed = discord.Embed(
                title="✅ Tag Roles Disabled",
                description="Tag role functionality has been disabled for this server.",
                colour=0xFF0000
            )
        else:
            embed = discord.Embed(
                title="⚠️ Tag Roles Not Enabled",
                description="Tag roles were not enabled in this server.",
                colour=0xFFFF00
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="thanks",
        description="Configure thank you message for tag roles"
    )
    @app_commands.describe(
        dm="Send thank you in DMs instead of a channel",
        channel="Channel to send thank you messages (ignored if DM is True)"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def tag_thanks(
        self,
        interaction: discord.Interaction,
        dm: bool = False,
        channel: discord.TextChannel = None,
    ) -> None:
        if not dm and not channel:
            await interaction.response.send_message("❌ Please specify a channel or enable DM", ephemeral=True)
            return
        if dm and channel:
            await interaction.response.send_message("❌ Choose either DM or a channel, not both", ephemeral=True)
            return

        ref = db.reference("/Tag Thanks")
        try:
            for key, val in ref.get().items():
                if val['Server ID'] == interaction.guild.id:
                    ref.child(key).delete()
                    break
        except: pass

        data = {
            "Server ID": interaction.guild.id,
            "Channel ID": channel.id if channel else None,
            "DM": dm
        }
        ref.push().set(data)
        await interaction.response.send_modal(tag_embed_modal())

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TagCommands(bot))