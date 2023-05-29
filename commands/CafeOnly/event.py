import discord, firebase_admin, datetime, asyncio, time, emoji, random
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
from essential_generators import DocumentGenerator

### --- ADD MORA TO USER --- ###

async def addMora(userID, addedMora):
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  
  ogmora = 0
  try:
    for key, val in randomevents.items():
      if val['User ID'] == userID:
        ogmora = val['Mora']
        db.reference('/Random Events').child(key).delete()
        break
  except Exception:
    pass

  newmora = ogmora + addedMora
  data = {
    "Random Event Participant": {
      "User ID": userID,
      "Mora": newmora,
    }
  }

  for key, value in data.items():
    ref.push().set(value)

### --- DEFEAT THE BOSS --- ###

async def defeatTheBoss(channel, client):
  bosses = ["Perpetual Mechanical Array", "Ruin Serpent", "Aeonblight Drake", "Coral Defenders", "Iniquitous Baptist", "Maguu Kenki", "Primo Geovishap", "Anemo Hypostasis", "Setekh Wenut", "Cryo Hypostasis", "Cryo Regisvine", "Algorithm of Semi-Intransient Matrix of Overseer Network", "Dendro Hypostasis", "Jadeplume Terrorshroom", "Electro Hypostasis", "Electro Regisvine", "Thunder Manifestation", "Geo Hypostasis", "Golden Wolflord", "Hydro Hypostasis", "Rhodeia of Loch", "Pyro Hypostasis", "Pyro Regisvine", " Azhdaha", "Stormterror Dvalin", "Magatsu Mitake Narukami no Mikoto", "Childe", "Everlasting Lord of Arcane Wisdom", "La Signora", "Warden of the Last Oasis", "Warden of Oasis Prime", "Andrius"]
  boss = random.choice(bosses)
  punches = random.randint(4, 6)
  reward = random.randint(50, 150)
  seconds = random.randint(15, 20)
  msg = await channel.send(embed=discord.Embed(title=f"Defeat The Boss - {boss}", description=f"`{punches}` people must react with `👊` to defeat **{boss}** within `{seconds} Seconds`.\nEach user will be rewarded <:MORA:953918490421641246> `{reward}` if successful!", color=discord.Color.purple()))
  await msg.add_reaction("👊")
  await asyncio.sleep(seconds)
  msg = await msg.channel.fetch_message(msg.id)
  if msg.reactions[0].count >= punches and str(msg.reactions[0].emoji) == "👊":
    async for user in msg.reactions[0].users():
      await addMora(user.id, reward)
    await msg.reply(embed=discord.Embed(title=f"{boss} has died!", description=f"Congratulations, you all have defeated the boss! \nEach user who reacted with `👊` has been awarded <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green()))
  elif msg.reactions[0].count < punches and str(msg.reactions[0].emoji) == "👊":
    await msg.reply(embed=discord.Embed(title=f"{boss} NOT defeated...", description=f"Uh oh, only **{msg.reactions[0].count}** users reacted with `👊`. \nGood effort and best of luck next time!", color=discord.Color.red()))

### --- PICK UP THE WATERMELON --- ###

class PickUpButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(emoji="🍉", 
 style=discord.ButtonStyle.grey, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.embeds[0].description.split("`")[3])
      await interaction.response.edit_message(content="", embed=discord.Embed(title=f"Pick up the watermelon - :watermelon:", description=f"{interaction.user.mention} picked up the `🍉` watermelon and earned <:MORA:953918490421641246> `{reward}`.", color=discord.Color.gold()), view=PickUpView(disabled=True))
      await addMora(interaction.user.id, reward)
      
class PickUpView(discord.ui.View):
    def __init__(self, disabled=False):
        super().__init__(timeout=None)
        self.add_item(PickUpButton(disabled))
    
async def pickUpTheWatermelon(channel, client):
  reward = random.randint(60, 300)
  await channel.send(embed=discord.Embed(title=f"Pick up the watermelon - :watermelon:", description=f"First to react to the `🍉` emoji earns <:MORA:953918490421641246> `{reward}`.", color=discord.Color.fuchsia()), view=PickUpView())

### --- TYPE RACER --- ###

async def createImage(text, bg="./assets/F7E8BE.png", filename="./assets/typeracer.png"):
  im1 = Image.open(bg)
  color = (0, 0, 0)
  font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
  d1 = ImageDraw.Draw(im1)
  d1.text((15,15), text, font=font, fill=color)
  im1.save(filename)
  return filename

async def typerRacer(channel, client):
  reward = random.randint(200, 500)
  
  gen = DocumentGenerator()
  words = str(gen.sentence())[:45]
  filename = await createImage(words)
  chn = client.get_channel(1026968305208131645)
  msg = await chn.send(file=discord.File(filename))
  url = msg.attachments[0].proxy_url 
  embed=discord.Embed(title=f"Type Racer", description=f"First to type the following phrase in chat wins <:MORA:953918490421641246> `{reward}`.", color=discord.Color.blurple())
  embed.set_image(url=url)
  msg = await channel.send(embed=embed)
  def check(message):
    return message.channel == channel
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.strip() == words.strip():
      embed=discord.Embed(title=f"Type Racer", description=f"{answer.author.mention} won <:MORA:953918490421641246> `{reward}`.", color=discord.Color.brand_green())
      embed.set_image(url=url)
      await addMora(answer.author.id, reward)
      await msg.edit(embed=embed)
      break

### --- EGGWALK --- ###

async def eggWalk(channel, client):
  reward = random.randint(20, 65)
  embed=discord.Embed(title=f"Eggwalk", description=f"**Users must alternate!** Start at 1 and count to 10. \nEach number you type will earn you <:MORA:953918490421641246> `{reward}` if successful.", color=discord.Color.dark_purple())
  msg = await channel.send(embed=embed)
  def check(message):
    return message.channel == channel
  number = 1
  previousUserID = None
  userIDs = []
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.isnumeric():
      if answer.content.strip() == str(number):
        if answer.author.id != previousUserID:
          number += 1
          previousUserID = answer.author.id
          userIDs.append(answer.author.id)
          await answer.add_reaction("✅")
        else:
          await answer.add_reaction("❌")
          await msg.reply(embed=discord.Embed(title=f"Eggwalk", description=f"One user did not alternate! Good luck next time!", color=discord.Color.red()))
          break
      else:
        await answer.add_reaction("❌")
        await msg.reply(embed=discord.Embed(title=f"Eggwalk", description=f"Wrong number. Next number should be `{number}`! Better luck next time!", color=discord.Color.red()))
        break
      if number > 10:
        for userID in userIDs:
          await addMora(userID, reward)
        await msg.reply(embed=discord.Embed(title=f"Eggwalk", description=f"Good job everyone! That's not an easy task!\nAll of you earned <:MORA:953918490421641246> `{reward}` for every number you counted.", color=discord.Color.green()))
        break

### --- MATCH THE PROFILE PICTURE --- ###

class matchPFPBtn(discord.ui.Button):
    def __init__(self, name, disabled=False):
        super().__init__(label=name, emoji="👤", 
 style=discord.ButtonStyle.grey, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.embeds[0].description.split("`")[1])
      url = interaction.message.embeds[0].image.url
      ref = db.reference("/Random Events")
      randomevents = ref.get()
      for key, val in randomevents.items():
        if val['User ID'] == "Match the Profile Picture":
          user = val["Mora"]
          break

      duplicate = []
      for key, val in randomevents.items():
        if val['User ID'] == "Those who answered":
          duplicate = val["Mora"]
          break
      
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have guessed once already. No second try!", ephemeral=True)
      else:
        if str(self.label) == user:
          embed=discord.Embed(title=f"Match the Profile Picture", description=f"{interaction.user.mention} guessed correctly and earned <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green())
          embed.set_image(url=url)
          await interaction.response.edit_message(content="", embed=embed, view=None)
          await addMora(interaction.user.id, reward)
          
          for key, val in randomevents.items():
            if val['User ID'] == "Those who answered":
              db.reference('/Random Events').child(key).delete()
              break
        else:
          await interaction.response.send_message("Wrong! :x:", ephemeral=True)
          duplicate.append(int(interaction.user.id))
          data = {
            "Those who answered": {
              "User ID": "Those who answered",
              "Mora": duplicate
            }
          }
        
          for key, value in data.items():
            ref.push().set(value)

async def matchThePFP(channel, client):
  reward = random.randint(30, 85)
  messages = [message async for message in channel.history(limit=200)]
  selected_items = []
  unique_ids = set()
  for message in messages:
      if message.author.id not in unique_ids and message.author.id != 732422232273584198:
          selected_items.append(message)
          unique_ids.add(message.author.id)
      if len(selected_items) == 100:
          break
  random_numbers = random.sample(range(len(selected_items)), 3)
  random_items = [selected_items[i] for i in random_numbers]
  embed=discord.Embed(title=f"Match the Profile Picture", description=f"The first to guess wins <:MORA:953918490421641246> `{reward}`. **You can only guess once!**", color=discord.Color.light_grey())
  user = random.choice(random_items).author
  embed.set_image(url=user.avatar.url)
  view = View()
  for item in random_items:
    # await channel.send(item.author.mention)
    view.add_item(matchPFPBtn(str(item.author)))
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  try:
    for key, val in randomevents.items():
      if val['User ID'] == "Match the Profile Picture":
        db.reference('/Random Events').child(key).delete()
        break
  except Exception:
    pass
  data = {
    "Match the Profile Picture": {
      "User ID": "Match the Profile Picture",
      "Mora": str(user)
    }
  }
  for key, value in data.items():
    ref.push().set(value)
  await channel.send(embed=embed, view=view)

### --- SPLIT or STEAL --- ###

class split(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Split", emoji="🤝", 
 style=discord.ButtonStyle.green, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.content.split("`")[1])
      a = interaction.message.mentions[0]
      b = interaction.message.mentions[1]

      ref = db.reference("/Random Events")
      randomevents = ref.get()
      
      if interaction.user == a: # A chose "Split"
        aChoice = "Split"
        bChoice = None
        try:
          for key, val in randomevents.items():
            if val['User ID'] == "Split Or Steal":
              aChoice = val['Mora'][0]
              bChoice = val['Mora'][1]
              break
        except Exception:
          pass
        if aChoice != "Split" and aChoice != None:
          await interaction.response.send_message(f"You can't change your selection!", ephemeral=True)
        elif bChoice == None:
          data = {
            "Split Or Steal": {
              "User ID": "Split Or Steal",
              "Mora": ["Split", None]
            }
          }
          for key, value in data.items():
            ref.push().set(value)
          await interaction.response.send_message(f"Still waiting for {b.mention} to make their choice.", ephemeral=True)
        elif bChoice == "Split":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"Congrats, both {a.mention} and {b.mention} chose Split. You each won <:MORA:953918490421641246> `{int(reward/2)}`!")
          await addMora(a.id, int(reward/2))
          await addMora(b.id, int(reward/2))
        elif bChoice == "Steal":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"{b.mention} stole all the money and won <:MORA:953918490421641246> `{reward}`!")
          await addMora(b.id, reward)
          
      elif interaction.user == b: # B chose "Split"
        bChoice = "Split"
        aChoice = None
        try:
          for key, val in randomevents.items():
            if val['User ID'] == "Split Or Steal":
              aChoice = val['Mora'][0]
              bChoice = val['Mora'][1]
              break
        except Exception:
          pass
        if bChoice != "Split" and bChoice != None:
          await interaction.response.send_message(f"You can't change your selection!", ephemeral=True)
        elif aChoice == None:
          data = {
            "Split Or Steal": {
              "User ID": "Split Or Steal",
              "Mora": [None, "Split"]
            }
          }
          for key, value in data.items():
            ref.push().set(value)
          await interaction.response.send_message(f"Still waiting for {a.mention} to make their choice.", ephemeral=True)
        elif aChoice == "Split":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"Congrats, both {a.mention} and {b.mention} chose Split. You each won <:MORA:953918490421641246> `{int(reward/2)}`!")
          await addMora(a.id, int(reward/2))
          await addMora(b.id, int(reward/2))
        elif aChoice == "Steal":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"{a.mention} stole all the money and won <:MORA:953918490421641246> `{reward}`!")
          await addMora(a.id, reward)

      else:
        await interaction.response.send_message("You are not part of this game!", ephemeral=True)
        
class steal(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Steal", emoji="🤑", 
 style=discord.ButtonStyle.red, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.content.split("`")[1])
      a = interaction.message.mentions[0]
      b = interaction.message.mentions[1]

      ref = db.reference("/Random Events")
      randomevents = ref.get()
      
      if interaction.user == a: # A chose "Steal"
        aChoice = "Steal"
        bChoice = None
        try:
          for key, val in randomevents.items():
            if val['User ID'] == "Split Or Steal":
              aChoice = val['Mora'][0]
              bChoice = val['Mora'][1]
              break
        except Exception:
          pass
        if aChoice != "Steal" and aChoice != None:
          await interaction.response.send_message(f"You can't change your selection!", ephemeral=True)
        elif bChoice == None:
          data = {
            "Split Or Steal": {
              "User ID": "Split Or Steal",
              "Mora": ["Steal", None]
            }
          }
          for key, value in data.items():
            ref.push().set(value)
          await interaction.response.send_message(f"Still waiting for {b.mention} to make their choice.", ephemeral=True)
        elif bChoice == "Split":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"{a.mention} stole all the money and won <:MORA:953918490421641246> `{reward}`!")
          await addMora(a.id, reward)
        elif bChoice == "Steal":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"Both {a.mention} and {b.mention} chose Steal. No money for y'all.")
      
      elif interaction.user == b: # B chose "Steal"
        bChoice = "Steal"
        aChoice = None
        try:
          for key, val in randomevents.items():
            if val['User ID'] == "Split Or Steal":
              aChoice = val['Mora'][0]
              bChoice = val['Mora'][1]
              break
        except Exception:
          pass
        if bChoice != "Steal" and bChoice != None:
          await interaction.response.send_message(f"You can't change your selection!", ephemeral=True)
        elif aChoice == None:
          data = {
            "Split Or Steal": {
              "User ID": "Split Or Steal",
              "Mora": [None, "Steal"]
            }
          }
          for key, value in data.items():
            ref.push().set(value)
          await interaction.response.send_message(f"Still waiting for {a.mention} to make their choice.", ephemeral=True)
        elif aChoice == "Split":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"{b.mention} stole all the money and won <:MORA:953918490421641246> `{reward}`!")
          await addMora(b.id, reward)
        elif aChoice == "Steal":
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.response.edit_message(content=interaction.message.content, view=None)
          await interaction.channel.send(f"Both {a.mention} and {b.mention} chose Steal. No money for y'all.")

      else:
        await interaction.response.send_message("You are not part of this game!", ephemeral=True)
        
async def splitOrSteal(channel, client):
  reward = random.randint(1400, 6700)
  messages = [message async for message in channel.history(limit=20)]
  selected_items = []
  unique_ids = set()
  for message in messages:
      if message.author.id not in unique_ids and message.author.id != 732422232273584198:
          selected_items.append(message)
          unique_ids.add(message.author.id)
      if len(selected_items) == 2:
          break
  a = selected_items[0].author
  b = selected_items[1].author
  view = View()
  view.add_item(split())
  view.add_item(steal())
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  try:
    for key, val in randomevents.items():
      if val['User ID'] == "Split Or Steal":
        db.reference('/Random Events').child(key).delete()
        break
  except Exception:
    pass
  await channel.send(f"{a.mention} and {b.mention}, choose to **Split or Steal** <:MORA:953918490421641246> `{reward}`!", view=view)
  
# class OnReaction(commands.Cog): 
#   def __init__(self, bot):
#     self.client = bot
  
#   @commands.Cog.listener() 
#   async def on_reaction_add(self, reaction, user):
#     if user == self.client.user: 
#       return
#     if str(reaction) == "👊" and reaction.message.author == self.client.user:
#       channel = self.client.get_channel(reaction.message.channel.id)
#       message = await channel.fetch_message(reaction.message.id)
#       required = int(message.embeds[0].description.split("`")[1])
#       current = reaction.count
#       await message.reply("Nice! Reacted!")
#       await message.reply(f"Required: {required}")
#       await message.reply(f"Count: {reaction.count}")

class TheEventItself(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return
    if message.channel.id == 1104212482312122388 and message.id % 20 == 0:
    # if message.channel.id == 1026867655468126249 and message.id % 2 == 0:
      messages = [message async for message in message.channel.history(limit=20)]
      for msg in messages:
        if len(msg.embeds) > 0 and "Event Starting Soon" in msg.embeds[0].title:
          raise Exception("Event occuring too soon!")
      await message.channel.send(embed=discord.Embed(title="<:gi_cafe:1103720959950725190>  Event Starting Soon", description="A random event will occur in `5 seconds`.", color=discord.Color.orange()))
      events = [
        defeatTheBoss,
        defeatTheBoss,
        pickUpTheWatermelon,
        pickUpTheWatermelon,
        pickUpTheWatermelon,
        typerRacer,
        eggWalk,
        eggWalk,
        matchThePFP,
        matchThePFP,
        matchThePFP,
        splitOrSteal,
        splitOrSteal
      ]
      event = random.choice(events)
      await asyncio.sleep(5)
      await event(message.channel, self.client)

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(TheEventItself(bot))
  # await bot.add_cog(OnReaction(bot))