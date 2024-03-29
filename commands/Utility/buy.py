import discord, time, datetime, firebase_admin
from discord import app_commands
from discord.ext import commands
from firebase_admin import db

# Also exists in mora.py
items = [
  ["🍞", 25000, "Bread"],
  ["🧀", 50000, "Cheese"],
  ["🍬", 50000, "Candy"],
  ["☕️", 75000, "Coffee"],
  ["🍣", 85000, "Sushi"],
  ["🍕", 95000, "Pizza"],
  ["🍔", 100000, "Burger"],
  ["🍰", 125000, "Cake"],
  ["🍜", 150000, "Ramen"],
  ["ඞ", 250000, "Sus"]
]

### --- REMOVE MORA FROM USER --- ###

async def removeMora(userID, removeMora):
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  
  ogmora = 0
  try:
    for key, val in randomevents.items():
      if val['User ID'] == userID:
        ogmora = val['Mora']
        if removeMora > ogmora:
          return False
        db.reference('/Random Events').child(key).delete()
        break
  except Exception:
    pass

  

  newmora = ogmora - removeMora
  data = {
    "Random Event Participant": {
      "User ID": userID,
      "Mora": newmora,
    }
  }

  for key, value in data.items():
    ref.push().set(value)

  return True

class ConfirmPurchaseView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Purchase Item ', style=discord.ButtonStyle.green, custom_id='buy')
  async def mondstadt(self, interaction: discord.Interaction, button: discord.ui.Button):
    if str(interaction.user.id) not in interaction.message.embeds[0].description:
      await interaction.response.send_message("You can't perform this action.", ephemeral=True)
      raise Exception
    
    roleName = interaction.message.embeds[0].description.split("**")[1]
    gangRole = discord.utils.get(interaction.guild.roles,name=roleName)
    if gangRole in interaction.user.roles:
      embed = discord.Embed(title="Bruh", description=f"You already owned the {gangRole.mention} role. What are you trying to do?", color=discord.Color.red())
      await interaction.response.edit_message(embed=embed, view=None)
      raise Exception
    x = 0
    for i in items:
      if i[0] == roleName:
        break
      x += 1

    itemCost = items[x][1]

    remove = await removeMora(interaction.user.id, itemCost)
    if remove == False:
      embed = discord.Embed(title="Unsuccessful Purchase", description=f"Apologies, but we are unable to give you `{roleName}`. We kindly request you to verify your mora balance by using </mora:1113523731122372618> in order to confirm if you possess enough mora to complete the purchase.", color=discord.Color.red())
      await interaction.response.edit_message(embed=embed, view=None)
    else:
      await interaction.user.add_roles(gangRole)
      embed = discord.Embed(title="Sucessful Purchase", description=f"Congratulations! You have paid <:MORA:953918490421641246> **{itemCost:,}** now own the {gangRole.mention} role.", color=discord.Color.green())
      await interaction.response.edit_message(embed=embed, view=None)
    

  @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey, custom_id='cancelbuy')
  async def liyue(self, interaction: discord.Interaction, button: discord.ui.Button):
    if str(interaction.user.id) not in interaction.message.embeds[0].description:
      await interaction.response.send_message("You can't perform this action.", ephemeral=True)
      raise Exception
    await interaction.message.delete()



class BuyInventory(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "buy",
    description = "Purchase an item from the shop"
  )
  @app_commands.describe(
    item = "The item you wish to purchase"
  )
  @app_commands.choices(item=[
      app_commands.Choice(name="🍞 - Bread", value="🍞"),
      app_commands.Choice(name="🧀 - Cheese", value="🧀"),
      app_commands.Choice(name="🍬 - Candy", value="🍬"),
      app_commands.Choice(name="☕️ - Coffee", value="☕️"),
      app_commands.Choice(name="🍣 - Sushi", value="🍣"),
      app_commands.Choice(name="🍕 - Pizza", value="🍕"),
      app_commands.Choice(name="🍔 - Burger", value="🍔"),
      app_commands.Choice(name="🍰 - Cake", value="🍰"),
      app_commands.Choice(name="🍜 - Ramen", value="🍜"),
      app_commands.Choice(name="ඞ - Sus", value="ඞ"),
  ])
  async def buy(
    self,
    interaction: discord.Interaction,
    item: app_commands.Choice[str]
  ) -> None:
    x = 0
    for i in items:
      if i[0] == item.value:
        break
      x += 1

    itemCost = items[x][1]

    gangRole = discord.utils.get(interaction.guild.roles,name=item.value)
  
    embed = discord.Embed(title="Confirm Purchase", description=f"{interaction.user.mention}, are you sure you want to purchase **{item.value}**?\n\n_You will pay <:MORA:953918490421641246> **{itemCost:,}** (no refund) and earn the {gangRole.mention} role._", color=discord.Color.gold())
    
    if interaction.guild.id != 717029019270381578:
      content = "This command is for the event happening in **Genshin Impact Cafe♡**: discord.gg/traveler"
      await interaction.response.send_message(content =content)
    else:
      await interaction.response.send_message(embed=embed, view=ConfirmPurchaseView())

  @app_commands.command(
    name = "shop",
    description = "View the shop"
  )
  async def shop(
    self,
    interaction: discord.Interaction,
  ) -> None:
    desc = ""
    for item in items:
      desc += f"- {item[0]} ({item[2]}) - <:MORA:953918490421641246> **{item[1]:,}**\n"

    embed1 = discord.Embed(title="Shop", description=f"Here are all the purchasable items/roles using <:MORA:953918490421641246> in **Genshin Impact Cafe♡**", color=discord.Color.blurple())
    embed2 = discord.Embed(description=desc, color=discord.Color.blurple())
    embed3 = discord.Embed(description="► To check your mora balance and inventory, use </mora:1113523731122372618>.\n► To purchase an item, use </buy:1121918740632715385>.", color=discord.Color.blurple())

    if interaction.guild.id != 717029019270381578:
      content = "This command is for the event happening in **Genshin Impact Cafe♡**: discord.gg/traveler"
      await interaction.response.send_message(content =content)
    else:
      await interaction.response.send_message(embeds=[embed1, embed2, embed3])
    
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(BuyInventory(bot))