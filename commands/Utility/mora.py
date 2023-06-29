import discord, time, datetime, firebase_admin
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os.path

# Also exists in buy.py
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

### --- ADD MORA TO USER --- ###

  

### --- CONFIRM CUSTOMIZE BACKGROUND --- ###

class ConfirmView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='confirmbg')
  async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
    if str(interaction.user.id) not in interaction.message.embeds[0].description:
      await interaction.response.send_message("You can't perform this action!", ephemeral=True)
      raise Exception()

    embed = interaction.message.embeds[0]
    embed.title = "Confirmed"
    embed.description = f"The following will be how {interaction.user.mention}'s inventory would appear.\n\nYou have **paid** <:MORA:953918490421641246> `5000`. You can always use </customize:1123732330679390219> change your current inventory background."
    embed.color = discord.Color.green()

    try:
      os.remove(f"./assets/Mora Inventory Background/{interaction.user.id}.png")
    except Exception:
      pass

    os.rename(f"./assets/Mora Inventory Background/{interaction.user.id}-temp.png", f"./assets/Mora Inventory Background/{interaction.user.id}.png")

    await interaction.response.edit_message(embed=embed, view=None)

  @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey, custom_id='cancelbg')
  async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
    if str(interaction.user.id) not in interaction.message.embeds[0].description:
      await interaction.response.send_message("You can't perform this action!", ephemeral=True)
      raise Exception()

    os.remove(f"./assets/Mora Inventory Background/{interaction.user.id}-temp.png")
    embed = discord.Embed(title="Action Cancelled", description="You can always use </customize:1123732330679390219> again in the future.", color=discord.Color.red())
    ref = db.reference("/Random Events")
    randomevents = ref.get()
    
    ogmora = 0
    try:
      for key, val in randomevents.items():
        if val['User ID'] == interaction.user.id:
          ogmora = val['Mora']
          db.reference('/Random Events').child(key).delete()
          break
    except Exception:
      pass
  
    newmora = ogmora + 5000
    data = {
      "Random Event Participant": {
        "User ID": interaction.user.id,
        "Mora": newmora,
      }
    }
  
    for key, value in data.items():
      ref.push().set(value)
    await interaction.response.edit_message(embed=embed, view=None)

### --- CREATE PROFILE CARD --- ###

async def createProfileCard(user, num, rank, bg="./assets/mora_bg.png", filename="./assets/mora.png"):
  await user.avatar.with_static_format("png").with_size(128).save(filename)
  im1 = Image.open(bg) # background (720, 256)
  im2 = Image.open(filename) # user logo
  im3 = Image.open("./assets/mora_icon.png") # mora icon

  bigsize = (im2.size[0] * 1, im2.size[1] * 1)
  mask = Image.new('L', bigsize, 0)
  draw = ImageDraw.Draw(mask) 
  draw.ellipse((0, 0) + bigsize, fill=255)
  mask = mask.resize(im2.size, Image.ANTIALIAS)
  im2.putalpha(mask) # USER AVATAR
  im1.paste(im2, (20, 20), im2.convert("RGBA"))
  
  font = ImageFont.truetype("./assets/ja-jp.ttf", 45)
  d1 = ImageDraw.Draw(im1)
  d1.text((162,35), user.display_name, font=font, fill=(255, 255, 255)) # DISPLAY NAME
  im1.save(filename)
  
  font = ImageFont.truetype("./assets/ja-jp.ttf", 25)
  d1 = ImageDraw.Draw(im1)
  d1.text((162,90), user.name, font=font, fill=(225, 225, 225)) # USERNAME
  im1.save(filename)

  bigsize = (im3.size[0] * 1, im3.size[1] * 1)
  mask = Image.new('L', bigsize, 0)
  draw = ImageDraw.Draw(mask) 
  draw.ellipse((0, 0) + bigsize, fill=255)
  mask = mask.resize(im3.size, Image.ANTIALIAS)
  im3.putalpha(mask) # MORA ICON
  im1.paste(im3, (38, 180), im3.convert("RGBA"))
  
  font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
  d1 = ImageDraw.Draw(im1)
  d1.text((89,175), num, font=font, fill=(233, 253, 255)) # MORA AMOUNT
  im1.save(filename)
  
  font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
  d1 = ImageDraw.Draw(im1)
  d1.text((516,180), f"Rank: {rank}", font=font, fill=(203, 254, 196)) # RANK 
  im1.save(filename)
  
  # font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
  # text = f"{user.name}"
  # textLen = len(text)
  # d2 = ImageDraw.Draw(im1)
  # d2.text((((1024/2)-(20*(textLen/2))),410), text, font=font, fill=(255, 255, 255))
  # im1.save(filename)
  
  return filename


  
class CheckMora(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  ### --- /CUSTOMIZE --- ###

  @app_commands.command(
    name = "customize",
    description = "Customize your mora inventory background."
  )
  @app_commands.describe(
    background = "The required background (auto cropped and scaled to 720x256px)"
  )
  async def customize(
    self,
    interaction: discord.Interaction,
    background: discord.Attachment
  ) -> None:
    await interaction.response.defer(thinking=True)
    
    ref = db.reference("/Random Events")
    randomevents = ref.get()
    
    ogmora = 0
    try:
      for key, val in randomevents.items():
        if val['User ID'] == interaction.user.id:
          ogmora = val['Mora']
          break
    except Exception:
      pass

    if ogmora <= 5000:
      embed = discord.Embed(title="Not Enough Mora", description=f"Customizing your inventory background each time requires <:MORA:953918490421641246> `5000`.\nYou only have <:MORA:953918490421641246> `{ogmora}`. Earn more mora by being active in <#1104212482312122388>!", color=discord.Color.red())
      await interaction.followup.send(embed=embed)
      raise Exception()
      
    path = f"./assets/Mora Inventory Background/{interaction.user.id}-temp.png"
    await background.save(path)
    image  = Image.open(path)
    width  = image.size[0]
    height = image.size[1]
    aspect = width / float(height)
    ideal_width = 720
    ideal_height = 256
    ideal_aspect = ideal_width / float(ideal_height)
    if aspect > ideal_aspect:
        new_width = int(ideal_aspect * height)
        offset = (width - new_width) / 2
        resize = (offset, 0, width - offset, height)
    else:
        new_height = int(width / ideal_aspect)
        offset = (height - new_height) / 2
        resize = (0, offset, width, height - offset)
    thumb = image.crop(resize).resize((ideal_width, ideal_height), Image.ANTIALIAS)
    thumb.save(path)
    image  = Image.open(path)
    enhancer = ImageEnhance.Brightness(image)
    im_output = enhancer.enhance(0.4)
    im_output.save(path)

    filename = await createProfileCard(
      interaction.user, 
      f"69,420",
      "69",
      bg=path
    )

    chn = interaction.client.get_channel(1026968305208131645)
    msg = await chn.send(file=discord.File(filename))
    url = msg.attachments[0].proxy_url 

    
    try:
      for key, val in randomevents.items():
        if val['User ID'] == interaction.user.id:
          db.reference('/Random Events').child(key).delete()
          break
    except Exception:
      pass
  
    newmora = ogmora - 5000
    data = {
      "Random Event Participant": {
        "User ID": interaction.user.id,
        "Mora": newmora,
      }
    }
  
    for key, value in data.items():
      ref.push().set(value)
    
    embed = discord.Embed(title="Preview", description=f"The following image showcases how {interaction.user.mention}'s inventory would appear.\n\nYou have **paid** <:MORA:953918490421641246> `5000`. If you are unsatisfied, click `Cancel` to have your mora refunded.", color=discord.Color.gold())
    embed.set_image(url=url)
    await interaction.followup.send(embed=embed, view=ConfirmView())
    
  ### --- /MORA --- ###
  
  @app_commands.command(
    name = "mora",
    description = "Check your mora inventory in the 2023 Cafe Summer Festival."
  )
  @app_commands.describe(
    user = "Specify any user other than you if needed",
  )
  async def mora(
    self,
    interaction: discord.Interaction,
    user: discord.Member = None
  ) -> None:
    await interaction.response.defer(thinking=True)
    if user == None:
      user = interaction.user
      string = f"{user.mention}, you currently have <:MORA:953918490421641246>"
    else:
      string = f"{user.mention} currently has <:MORA:953918490421641246>"
    ref = db.reference("/Random Events")
    randomevents = ref.get()
    moraAmount = 0
    for key, val in randomevents.items():
      if val['User ID'] == user.id:
        moraAmount = val['Mora']
        break

    inv = ""

    for item in items:
      gangRole = discord.utils.get(interaction.guild.roles,name=item[0])
      if gangRole in user.roles:
        inv += f"{item[0]} "

    if inv == "":
      inv = "_Empty (Use </buy:1121918740632715385> to purchase an item)_"

    userIDs = []
    moras = []
    if moraAmount == 0:
      hasMora = False
    else:
      hasMora = True
      
      
    while hasMora:
      highestMora = 0
      for key, val in randomevents.items():
        user_id = val['User ID']
        mora = val['Mora']
        if not(isinstance(user_id, int)) or not(isinstance(mora, int)):
          continue
        if mora > highestMora and mora not in moras:
          highestMora = mora
          highestUser = user_id
      userIDs.append(highestUser)
      moras.append(highestMora)
      if (int(highestUser) == int(user.id)):
        break

    def word(n):
      return str(n) + ("th" if 4 <= n % 100 <= 20 else {
          1: "st",
          2: "nd",
          3: "rd"
      }.get(n % 10, "th"))

    if moraAmount == 0:
      place = "N/A"
      msg = ""
    else:
      place = len(userIDs)
      msg = f"You are in the **{word(place)}** place."
    
    embed = discord.Embed(title="Inventory - 2023 Cafe Summer Festival", description=f"{string} `{moraAmount}`.\n\n**Inventory:**\n{inv}\n\n{msg}", color=discord.Color.gold())

    customized = os.path.isfile(f"./assets/Mora Inventory Background/{user.id}.png")

    if customized:
      filename = await createProfileCard(
        user, 
        f"{moraAmount:,}",
        place,
        bg=f"./assets/Mora Inventory Background/{user.id}.png"
      )
    else:
      filename = await createProfileCard(
        user, 
        f"{moraAmount:,}",
        place
      )
      embed.set_footer(text="Tip: use /customize to customize your own inventory background!")
    chn = interaction.client.get_channel(1026968305208131645)
    msg = await chn.send(file=discord.File(filename))
    url = msg.attachments[0].proxy_url 
    embed.set_image(url=url)
    
    if interaction.guild.id != 717029019270381578:
      content = "This is for the event happening in **Genshin Impact Cafe♡**: discord.gg/traveler"
    else:
      content = None
    await interaction.followup.send(content=content, embed=embed)
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(CheckMora(bot))