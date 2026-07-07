import discord, firebase_admin, datetime, asyncio, time, emoji, ast, re
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import importlib
import os

ENABLED_GUILDS_PATH = "./commands/Vanity/enabledGuilds.py"

# NOTE: vanityEvent.py has its own asyncio.Lock() guarding this same file.
# Locks are per-process-module, so this one does NOT protect against a race
# with that one if they're different Python objects at runtime. Ideally both
# files should import a single shared lock/helper module for enabledGuilds.py
# access. Flagging this rather than silently leaving the race in place.
enabled_guilds_lock = asyncio.Lock()

# A permissive-but-sane check for "discord.gg/xyz"-shaped invite links. This
# doesn't verify the invite is real/live -- just that a later `.split(".")[1]`
# won't blow up with an IndexError.
LINK_PATTERN = re.compile(r"^[\w.-]+\.[a-zA-Z]{2,}/.+$")


def word(n):
  return str(n)+("th" if 4<=n%100<=20 else {1:"st",2:"nd",3:"rd"}.get(n%10, "th"))


async def add_guild_to_enabled(guild_id):
  """Safely add a guild id to enabledGuilds.py. Returns True/False."""
  async with enabled_guilds_lock:
    try:
      with open(ENABLED_GUILDS_PATH, "r") as file:
        lines = file.readlines()
    except FileNotFoundError:
      print(f"[Vanity] {ENABLED_GUILDS_PATH} not found while adding guild {guild_id}")
      return False

    found_line = False
    for i, line in enumerate(lines):
      if line.startswith("enabledGuilds ="):
        found_line = True
        try:
          existing_ids = ast.literal_eval(line.split("=", 1)[1].strip())
        except (ValueError, SyntaxError) as e:
          print(f"[Vanity] Failed to parse enabledGuilds.py: {e}")
          return False
        if guild_id not in existing_ids:
          existing_ids.append(guild_id)
        lines[i] = f"enabledGuilds = {existing_ids}\n"
        break

    if not found_line:
      print("[Vanity] Could not find 'enabledGuilds =' line; add aborted")
      return False

    try:
      with open(ENABLED_GUILDS_PATH, "w") as file:
        file.writelines(lines)
    except OSError as e:
      print(f"[Vanity] Failed to write enabledGuilds.py: {e}")
      return False
    print(f"[Vanity] Added server ID {guild_id} to enabledGuilds.py")
    return True


async def remove_guild_from_enabled(guild_id):
  """Safely remove a guild id from enabledGuilds.py. Returns True/False."""
  async with enabled_guilds_lock:
    try:
      with open(ENABLED_GUILDS_PATH, "r") as file:
        lines = file.readlines()
    except FileNotFoundError:
      print(f"[Vanity] {ENABLED_GUILDS_PATH} not found while removing guild {guild_id}")
      return False

    found_line = False
    for i, line in enumerate(lines):
      if line.startswith("enabledGuilds ="):
        found_line = True
        try:
          existing_ids = ast.literal_eval(line.split("=", 1)[1].strip())
        except (ValueError, SyntaxError) as e:
          print(f"[Vanity] Failed to parse enabledGuilds.py: {e}")
          return False
        if guild_id in existing_ids:
          existing_ids.remove(guild_id)
        else:
          print(f"[Vanity] Guild {guild_id} wasn't in enabledGuilds; nothing to remove")
        lines[i] = f"enabledGuilds = {existing_ids}\n"
        break

    if not found_line:
      print("[Vanity] Could not find 'enabledGuilds =' line; remove aborted")
      return False

    try:
      with open(ENABLED_GUILDS_PATH, "w") as file:
        file.writelines(lines)
    except OSError as e:
      print(f"[Vanity] Failed to write enabledGuilds.py: {e}")
      return False
    print(f"[Vanity] Removed server ID {guild_id} from enabledGuilds.py")
    return True

def script(string, user, guild):
  if "{mention}" in string:
    string = string.replace("{mention}", f"{user.mention}")
  if "{server}" in string:
    string = string.replace("{server}", f"{guild.name}")
  if "{user}" in string:
    string = string.replace("{user}", f"{user.name}")
  if "{count}" in string:
    string = string.replace("{count}", f"{guild.member_count}")
  if "{count-th}" in string:
    string = string.replace("{count-th}", f"{word(guild.member_count)}")
  return string
  
class embed_modal(discord.ui.Modal, title = "Setup Vanity Roles Thank You Message"):
  msg = discord.ui.TextInput(label="Message Content", style=discord.TextStyle.paragraph, placeholder="Visit fischl.app/variables for all dynamic variables", max_length=2000, required=False)
  embedtitle = discord.ui.TextInput(label="Embed Title", style=discord.TextStyle.paragraph, placeholder="Visit fischl.app/variables for all dynamic variables", max_length=256, required=False)
  description = discord.ui.TextInput(label="Embed Description", style=discord.TextStyle.paragraph, placeholder="Visit fischl.app/variables for all dynamic variables", max_length=4000, required=False)
  color = discord.ui.TextInput(label="Embed Color", style=discord.TextStyle.short, placeholder="Use hex code (e.g. #ff0000)", max_length=7, required=False)
  image = discord.ui.TextInput(label="Embed Image", style=discord.TextStyle.paragraph, placeholder="Put a permanent image link", required=False)

  async def on_submit(self, interaction:discord.Interaction):
    ref = db.reference("/Vanity Thanks Message")
    welcome = ref.get() or {}

    for key, val in welcome.items():
      if val.get('Server ID') == interaction.guild.id:
        try:
          db.reference('/Vanity Thanks Message').child(key).delete()
        except Exception as e:
          print(f"[Vanity] Failed to delete old Vanity Thanks Message entry for guild {interaction.guild.id}: {e}")
        break

    data = {
      interaction.guild.id: {
        "Server ID": interaction.guild.id,
        "Message Content": self.msg.value,
        "Title": self.embedtitle.value,
        "Description": self.description.value,
        "Color": self.color.value,
        "Image Link": self.image.value
      }
    }

    try:
      for key, value in data.items():
        ref.push().set(value)
    except Exception as e:
      print(f"[Vanity] Failed to save Vanity Thanks Message for guild {interaction.guild.id}: {e}")
      await interaction.response.send_message(
        ":x: Something went wrong saving your thank-you message. Please try again.", ephemeral=True
      )
      return

    ref = db.reference("/Vanity Thanks")
    welcome = ref.get() or {}

    # Default in case no matching config is found (shouldn't normally happen,
    # since /vanity thanks writes this before showing the modal, but the
    # original code would crash here with an UnboundLocalError if it did).
    thankyouChannel = "the configured channel"
    found = False
    for key, val in welcome.items():
      if val.get('Server ID') == interaction.guild.id:
        found = True
        if not val.get("DM"):
          thankyouChannel = f'<#{val.get("Channel ID")}>'
        else:
          thankyouChannel = "DM"
        break

    if not found:
      print(f"[Vanity] No /Vanity Thanks entry found for guild {interaction.guild.id} when confirming thank-you message setup")

    embed = discord.Embed(
      title="✅ Vanity Role Thank You Message Enabled!",
      description=f"Congratulations! The bot will now send a thank-you message in **{thankyouChannel}** whenever a user adds your server invite link to their status!\n\n*Note: The thank-you message will only be sent if the user has not added the invite link to their status in the past 24 hours.*",
      colour=0x00FF00
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    

@app_commands.guild_only()
class VanityCommands(commands.GroupCog, name="vanity"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "migrate",
    description = "Migrate vanity role configuration from Fischl Vanity to Fischl"
  )
  @app_commands.checks.has_permissions(manage_roles=True)
  async def vanity_migrate(
    self,
    interaction: discord.Interaction,
  ) -> None:
    ok = await add_guild_to_enabled(interaction.guild.id)
    if not ok:
      print(f"[MIGRATION ERROR] Failed to add guild {interaction.guild.id} to enabledGuilds.py")
      await interaction.response.send_message(
        ":x: Something went wrong migrating your server. Please try again or contact support.",
        ephemeral=True,
      )
      return

    embed = discord.Embed(
      title="Vanity roles migrated successfully!", 
      description=f'Your vanity role configuration has been successfully migrated from Fischl Vanity to Fischl. You can now manage your vanity roles using the commands in Fischl.\n\n*Note: If you had thank-you messages enabled, your settings have also been migrated.*\n\nYou should now kick Fischl Vanity from your server to avoid duplicate functionality.', 
      colour=0x00FFBB # Slight color variation to distinguish migration from fresh enable
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await interaction.response.send_message(embed=embed, ephemeral=True)


  @app_commands.command(
    name = "enable",
    description = "Enable vanity roles in the server"
  )
  @app_commands.describe(
    link = "Your Discord server invite link (Format: discord.gg/traveler)",
    role = "The role to give when a user put the link in their status",
    log_channel = "The log channel for all actions related to vanity roles"
  )
  @app_commands.checks.has_permissions(manage_roles=True)
  async def vanity_enable(
    self,
    interaction: discord.Interaction,
    link: str,
    role: discord.Role,
    log_channel: discord.TextChannel
  ) -> None:
    # Validate the link format up front. The original code only discovered a
    # malformed link when `link.split(".")[1]` crashed further down -- by
    # which point a DB entry may already have been written with no rollback,
    # and the user just sees a generic "interaction failed" with no reason.
    if not LINK_PATTERN.match(link):
      await interaction.response.send_message(
        ":x: That doesn't look like a valid invite link. Expected format: `discord.gg/yourinvite`.",
        ephemeral=True,
      )
      return

    ref = db.reference("/Vanity Roles")
    avanity = ref.get() or {}

    for key, val in avanity.items():
      if val.get('Server ID') == interaction.guild.id:
        try:
          db.reference('/Vanity Roles').child(key).delete()
        except Exception as e:
          print(f"[Vanity] Failed to delete old Vanity Roles entry for guild {interaction.guild.id}: {e}")
        break

    data = {
      interaction.user.id: {
        "Server ID": interaction.guild.id,
        "Link": link,
        "Role ID": role.id,
        "Log Channel ID": log_channel.id
      }
    }

    try:
      for key, value in data.items():
        ref.push().set(value)
    except Exception as e:
      print(f"[Vanity] Failed to save Vanity Roles entry for guild {interaction.guild.id}: {e}")
      await interaction.response.send_message(
        ":x: Something went wrong enabling vanity roles. Please try again.", ephemeral=True
      )
      return

    link_slug = link.split(".")[1]
    embed = discord.Embed(title="Vanity roles enabled!", description=f'Whenever a member includes `{link_slug}` in their **status**, they receive {role.mention} as long as it remains there.\n\n> **All vanity role actions are logged in {log_channel.mention} for transparency.**\n\n*Note: The bot does not remove roles from users who go offline but had the link in their status. It verifies eligibility when they come back online.*\n## Make sure to put my bot role above the vanity role!\nIf you wish to send an **automatic thank-you message** to members when they put your link on their status, use `/vanity thanks`.', colour=0x00FF00)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    ok = await add_guild_to_enabled(interaction.guild.id)
    if not ok:
      print(f"[Vanity] Failed to add guild {interaction.guild.id} to enabledGuilds.py after enabling")

    embed = discord.Embed(title="What is this?", description='This channel logs all role addition and removal as a result of activity changes of a member.', colour=discord.Color.blurple())
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    try:
      await log_channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as e:
      print(f"[Vanity] Could not send intro message to log channel {log_channel.id} in guild {interaction.guild.id}: {e}")

    for member in interaction.guild.members:
      if (link_slug in str(member.activity)) and role not in member.roles:
        try:
          await member.add_roles(role)
        except (discord.Forbidden, discord.HTTPException) as e:
          print(f"[Vanity] Failed to add role to {member} in guild {interaction.guild.id}: {e}")
          continue
        embed = discord.Embed(description=f":green_circle: {member.mention} has **added** vanity link to their status.")
        embed.set_footer(text="Role added")
        try:
          await log_channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
          print(f"[Vanity] Failed to send role-added log for {member} in guild {interaction.guild.id}: {e}")
    

  @app_commands.command(
    name = "disable",
    description = "Disable vanity roles in the server"
  )
  @app_commands.checks.has_permissions(manage_roles=True)
  async def vanity_disable(
    self,
    interaction: discord.Interaction,
  ) -> None:
    await interaction.response.defer(ephemeral=True)

    found = None
    try:
      avanity = db.reference("/Vanity Roles").get() or {}
      for key, val in avanity.items():
        if val.get('Server ID') == interaction.guild.id:
          found = val.get('Role ID')
          db.reference('/Vanity Roles').child(key).delete()
          break

      vanityThanks = db.reference("/Vanity Thanks").get() or {}
      for key, val in vanityThanks.items():
        if val.get('Server ID') == interaction.guild.id:
          db.reference('/Vanity Thanks').child(key).delete()
          break

      vanityThanksMsg = db.reference("/Vanity Thanks Message").get() or {}
      for key, val in vanityThanksMsg.items():
        if val.get('Server ID') == interaction.guild.id:
          db.reference('/Vanity Thanks Message').child(key).delete()
          break
    except Exception as e:
      print(f"[Vanity] Error while cleaning up DB entries for guild {interaction.guild.id} on disable: {e}")

    if found is not None:
      embed = discord.Embed(title="Vanity roles disabled!", description='Sad to see you go. If you change your mind at anytime, you could use `/vanity enable` to enable vanity roles again. \n\n*If you had thank-you messages enabled, your settings have been deleted from our database.*', colour=0xFF0000)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.followup.send(embed=embed, ephemeral=True)

      ok = await remove_guild_from_enabled(interaction.guild.id)
      if not ok:
        print(f"[Vanity] Failed to remove guild {interaction.guild.id} from enabledGuilds.py on disable")
    else:
      embed = discord.Embed(title="Vanity roles is not enabled!", description='What are you thinking? Vanity roles aren\'t currently enabled in this server! To enable the function, use `/vanity enable`.', colour=0xFFFF00)
      embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
      await interaction.followup.send(embed=embed, ephemeral=True)
    

  @app_commands.command(
    name = "thanks",
    description = "Toggle thank you channel/message for vanity roles"
  )
  @app_commands.describe(
    dm = "Whether thank you message is sent DM (default: False)",
    channel = "The thank you channel (leave blank if enabling DM message or disabling thank you message)",
  )
  @app_commands.checks.has_permissions(manage_roles=True)
  async def vanity_thanks(
    self,
    interaction: discord.Interaction,
    dm: bool = False,
    channel: discord.TextChannel = None,
  ) -> None:
        
    avanity = db.reference("/Vanity Roles").get() or {}

    found = False
    for key, val in avanity.items():
      if val.get('Server ID') == interaction.guild.id:
        found = True
        break

    if not found:
      await interaction.response.send_message(":x: Vanity roles is not currently enabled in this server!", ephemeral=True)
      return

    ref = db.reference("/Vanity Thanks")
    vanityThanks = ref.get() or {}

    done = False
    try:
      for key, val in vanityThanks.items():
        if val.get('Server ID') == interaction.guild.id:
          db.reference('/Vanity Thanks').child(key).delete()
          if channel is None and not dm:
            await interaction.response.send_message(":white_check_mark: Thank you message **disabled**! *Vanity roles function is still enabled though!*", ephemeral=True)
            done = True
          break
    except Exception as e:
      print(f"[Vanity] Error checking existing Vanity Thanks for guild {interaction.guild.id}: {e}")

    if done:
      return

    if channel is None and not dm:
      await interaction.response.send_message(":x: Please either specify the channel *or* specify `dm` as `True` to enable thank you message.", ephemeral=True)
      return

    if channel is not None and dm:
      await interaction.response.send_message(f":x: You specified both {channel.mention} and DM. \nWhere do you actually want to send the thank you message? Specify one only!", ephemeral=True)
      return

    channelID = channel.id if channel is not None else None

    data = {
      interaction.user.id: {
        "Server ID": interaction.guild.id,
        "Channel ID": channelID,
        "DM": dm,
      }
    }

    try:
      for key, value in data.items():
        ref.push().set(value)
    except Exception as e:
      print(f"[Vanity] Failed to save Vanity Thanks config for guild {interaction.guild.id}: {e}")
      await interaction.response.send_message(
        ":x: Something went wrong saving that setting. Please try again.", ephemeral=True
      )
      return

    await interaction.response.send_modal(embed_modal())
    
      

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(VanityCommands(bot))