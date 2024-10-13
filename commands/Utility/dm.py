import discord, datetime, time
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

class Reply(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)
    ticketbtn = Button(label="Create a Ticket", style=discord.ButtonStyle.link, url="https://discord.com/channels/717029019270381578/1083745974402420846")
    self.add_item(ticketbtn)

  @discord.ui.button(label='Reply', style=discord.ButtonStyle.blurple, custom_id='reply', emoji="↩️")
  async def reply(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_message(embed=discord.Embed(description="Your next message sent in this DM will be sent to our staff team. Note that server rules still apply. Type `cancel` if you wish to terminate the action."))
    await interaction.message.edit(embeds=interaction.message.embeds, view=UnReply())
    def check(message):
      return (message.channel == interaction.user.dm_channel) and (message.author == interaction.user)
    msg = await interaction.client.wait_for('message', check=check)
    if msg.content.lower().strip() == "cancel":
      raise Exception("Terminate Reply to DM")
    chn = interaction.client.get_channel(1270550367335350385)
    embed = discord.Embed(title=f"New Reply", description=f"> {interaction.message.embeds[0].description}", color=0xFFFF00)
    embed.add_field(name=f"Reply from {interaction.user.name}", value=msg.content)
    await chn.send(embed=embed)
    await msg.add_reaction("✅")

class UnReply(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)
    ticketbtn = Button(label="Create a Ticket", style=discord.ButtonStyle.link, url="https://discord.com/channels/717029019270381578/1083745974402420846")
    self.add_item(ticketbtn)

  @discord.ui.button(label='Reply', style=discord.ButtonStyle.grey, custom_id='unreply', emoji="↩️", disabled=True)
  async def unreply(self, interaction: discord.Interaction, button: discord.ui.Button):
    pass
    

class Dm(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "dm",
    description = "DM a user"
  )
  @app_commands.choices(type_of_dm=[
      app_commands.Choice(name="Warning", value="⚠️ Warning"),
      app_commands.Choice(name="Reminder", value="⏰ Reminder"),
      app_commands.Choice(name="Notification", value="🔔 Notification"),
      app_commands.Choice(name="Follow-up", value="📝 Follow-up"),
      app_commands.Choice(name="Request", value="🙏 Request"),
      app_commands.Choice(name="Congratulations", value="🎉 Congratulations"),
      app_commands.Choice(name="Invitation", value="✉️ Invitation"),
  ])
  @app_commands.describe(
    user = "The user to DM",
    type_of_dm = "The type of DM",
    message = "Message to DM",
  )
  @app_commands.checks.has_permissions(view_audit_log=True)
  @app_commands.guild_only()
  async def dm(
    self,
    interaction: discord.Interaction,
    user: discord.Member,
    type_of_dm: app_commands.Choice[str],
    message: str
  ) -> None:
    if interaction.guild.id != 717029019270381578:
      raise Exception()
    typeName = type_of_dm.name
    typeValue = type_of_dm.value
    colors = {
      "Warning": 0xFF0000,         # Red for warning
      "Reminder": 0xFFA500,        # Orange for reminder
      "Notification": 0x0000FF,    # Blue for notification
      "Follow-up": 0x008000,       # Green for follow-up
      "Request": 0x964B00,         # Yellow for request
      "Congratulations": 0x00FF00, # Bright green for congratulations
      "Invitation": 0x800080       # Purple for invitation
    }

    try:
      embed = discord.Embed(title=f"{typeValue} from {interaction.guild.name}", description=message, color=colors[typeName])
      embed.set_footer(text="Do not reply unless it is necessary or more convenient. Create a ticket for longer conversations.")
      await user.send(embed=embed, view=Reply())
      chn = interaction.client.get_channel(1270550367335350385)
      embed = discord.Embed(title="DM Sent", color=0x41ff00)
      embed.add_field(name="__Member__", value=f"**User Mention:** {user.mention}\n**User Name:** {user.name}\n**User ID:** `{user.id}`", inline=True)
      embed.add_field(name="__Responsible Moderator__", value=f"**User Mention:** {interaction.user.mention}\n**User Name:** {interaction.user.name}\n**Rank:** {interaction.user.roles[len(interaction.user.roles) - 1].mention}", inline=True)
      embed.add_field(name="__Type of DM__", value=typeName, inline=False)
      embed.add_field(name="__Message__", value=message, inline=True)
      
      await chn.send(embed=embed)
      await interaction.response.send_message(embed=embed)
    except Exception as e:
      print(e)
      await interaction.response.send_message(f"Unable to DM {user.mention}.\n```{e}```", ephemeral=True)
    
    
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Dm(bot))