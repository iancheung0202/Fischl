import discord, firebase_admin, datetime, asyncio, time, emoji, random, os, string
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
from essential_generators import DocumentGenerator
from Bard import Chatbot

try:
  token = os.environ['BARD_KEY']
  chatbot = Chatbot(token)
except Exception:
  print("UHHHHHHHHHHHHHHH")

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
  reward = random.randint(400, 950)
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
  reward = random.randint(3490, 6300)
  await channel.send(embed=discord.Embed(title=f"Pick up the watermelon - :watermelon:", description=f"First to react to the `🍉` emoji earns <:MORA:953918490421641246> `{reward}`.", color=discord.Color.fuchsia()), view=PickUpView())

### --- PICK UP THE ICECREAM --- ###

class PickUpIceCreamButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(emoji="🍦", 
 style=discord.ButtonStyle.grey, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      num = int(interaction.message.embeds[0].description.split("`")[1])
      
      reward = random.randint(1250, num)
      if random.choice(["pos", "neg"]) == "neg":
        reason = random.choice(["having tooth decay", "having a brain freeze", "catching a cold", "melt"])
        if reason == "melt":
          await interaction.response.edit_message(content="", embed=discord.Embed(title=f"A wild 🍦 has appeared.", description=f"Unfortunately, {interaction.user.mention} did not ate the `🍦` in time. The ice cream melted and {interaction.user.mention} lost <:MORA:953918490421641246> `{reward}`.", color=discord.Color.red()), view=PickUpIceCreamView(disabled=True))
        else:
          await interaction.response.edit_message(content="", embed=discord.Embed(title=f"A wild 🍦 has appeared.", description=f"Unfortunately, {interaction.user.mention} ate the `🍦` and lost <:MORA:953918490421641246> `{reward}` for {reason}.", color=discord.Color.red()), view=PickUpIceCreamView(disabled=True))
        await addMora(interaction.user.id, -reward)
      else:
        await interaction.response.edit_message(content="", embed=discord.Embed(title=f"A wild 🍦 has appeared.", description=f"{interaction.user.mention} enjoyed the `🍦` while earning <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green()), view=PickUpIceCreamView(disabled=True))
        await addMora(interaction.user.id, reward)
      
class PickUpIceCreamView(discord.ui.View):
    def __init__(self, disabled=False):
        super().__init__(timeout=None)
        self.add_item(PickUpIceCreamButton(disabled))
    
async def pickUpIceCream(channel, client):
  num = random.randint(2700, 4400)
  await channel.send(embed=discord.Embed(title=f"A wild 🍦 has appeared.", description=f"First to eat can earn **up to** <:MORA:953918490421641246> `{num}`, **BUT** you can also lose up to that amount. \nIt's simply a 50/50 chance.", color=discord.Color.fuchsia()), view=PickUpIceCreamView())

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
  reward = random.randint(1000, 2000)
  
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

async def reverseTyper(channel, client):
  reward = random.randint(2500, 7000)
  
  gen = DocumentGenerator()
  words = str(gen.sentence())[:45]
  filename = await createImage(words)
  chn = client.get_channel(1026968305208131645)
  msg = await chn.send(file=discord.File(filename))
  url = msg.attachments[0].proxy_url 
  embed=discord.Embed(title=f"Reverse Typer", description=f"First to type the following phrase **IN REVERSE** in chat wins <:MORA:953918490421641246> `{reward}`.", color=discord.Color.blurple())
  embed.set_image(url=url)
  msg = await channel.send(embed=embed)
  def check(message):
    return message.channel == channel
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.strip() == words.strip()[::-1]:
      embed=discord.Embed(title=f"Reverse Typer", description=f"{answer.author.mention} won <:MORA:953918490421641246> `{reward}`.", color=discord.Color.brand_green())
      embed.set_image(url=url)
      await addMora(answer.author.id, reward)
      await msg.edit(embed=embed)
      await answer.add_reaction("✅")
      break

### --- UNSCRAMBLE THE SCRAMBLED --- ###

def scramble_string(input_string):
    # Convert the string into a list of characters
    char_list = list(input_string)
    
    # Use the random.shuffle() function to shuffle the list
    random.shuffle(char_list)
    
    # Join the shuffled characters back into a string
    scrambled_string = ''.join(char_list)
    
    return scrambled_string

async def unscrambleWords(channel, client):
  reward = random.randint(5000, 7500)
  from assets.words import words
  word = random.choice(words)
  print(word)
  scrambled = scramble_string(word)
  embed=discord.Embed(title=f"Unscramble the Scrambled", description=f"First to unscramble the following word in chat wins <:MORA:953918490421641246> `{reward}`.", color=discord.Color.blurple())
  embed.add_field(name=f"Word:", value=f"`{scrambled}`", inline=True)
  msg = await channel.send(embed=embed)
  def check(message):
    return message.channel == channel
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.lower().strip() == word.strip():
      await answer.add_reaction("✅")
      embed=discord.Embed(title=f"Unscramble the Scrambled", description=f"{answer.author.mention} won <:MORA:953918490421641246> `{reward}`.", color=discord.Color.brand_green())
      await addMora(answer.author.id, reward)
      await msg.edit(embed=embed)
      break

### --- TRUE OR FALSE --- ###

class TOFBtn(discord.ui.Button):
    def __init__(self, name, color=discord.ButtonStyle.grey, disabled=False):
        super().__init__(label=name, style=color, disabled=disabled, custom_id=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.embeds[0].description.split("`")[1])
      url = interaction.message.embeds[0].image.url
      ref = db.reference("/Random Events")
      randomevents = ref.get()
      for key, val in randomevents.items():
        if val['User ID'] == "TOF":
          answer = val["Mora"]
          break

      duplicate = []
      for key, val in randomevents.items():
        if val['User ID'] == "Those who answered in TOF":
          duplicate = val["Mora"]
          break
      
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have guessed once already. No second try!", ephemeral=True)
      else:
        if str(self.label) in answer:
          embed=discord.Embed(title=f"True Or False | Genshin Trivia", description=f"{interaction.user.mention} answered correctly and earned <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green())
          embed.set_image(url=url)
          await interaction.response.edit_message(content="", embed=embed, view=None)
          await addMora(interaction.user.id, reward)
          
          for key, val in randomevents.items():
            if val['User ID'] == "Those who answered in TOF":
              db.reference('/Random Events').child(key).delete()
        else:
          await interaction.response.send_message("Wrong! :x:", ephemeral=True)
          duplicate.append(int(interaction.user.id))
          data = {
            "Those who answered in TOF": {
              "User ID": "Those who answered in TOF",
              "Mora": duplicate
            }
          }
        
          for key, value in data.items():
            ref.push().set(value)

async def trueOrFalse(channel, client):
  reward = random.randint(3000, 6000)

  ref = db.reference("/Random Events")
  randomevents = ref.get()
  
  for key, val in randomevents.items():
    if val['User ID'] == "Those who answered in TOF":
      db.reference('/Random Events').child(key).delete()
  
  response = chatbot.ask(f'Write ONE very specific true or false question regarding any random Genshin Impact\'s characters, maps, or events. Send the question and answer (True / False) separated by a vertical line symbol. DO NOT include ANYTHING else other than the question and answer themselves. No explanation nor codeblock is needed. Answer in the following sample format: **Question:** [INSERT THE QUESTION YOU GENERATED] | **Answer:** [True/False]')['content']
  print(response)
  question = response.split("|")[0].split("**")[2].strip()
  try:
    answer = response.split("|")[1].split("**")[3].replace("Answer:", "").strip()
  except Exception:
    try:
      answer = response.split("|")[1].split("**")[2].replace("Answer:", "").strip()
    except Exception:
      answer = None
  print(answer)
  if answer == None:
    raise Exception("Can't extract answer")
  view = View()
  view.add_item(TOFBtn("True", discord.ButtonStyle.green))
  view.add_item(TOFBtn("False", discord.ButtonStyle.red))
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  try:
    for key, val in randomevents.items():
      if val['User ID'] == "TOF":
        db.reference('/Random Events').child(key).delete()
        break
  except Exception:
    pass
  data = {
    "TOF": {
      "User ID": "TOF",
      "Mora": str(answer)
    }
  }
  for key, value in data.items():
    ref.push().set(value)
  await channel.send(embed=discord.Embed(title="True Or False | Genshin Trivia", description=f"First one to answer the following question correctly wins <:MORA:953918490421641246> `{reward}`.\n```{question}```", color=0x9B59B6), view=view)
  
  

### --- RIDDLE --- ###

async def riddle(channel, client):
  reward = random.randint(2700, 7500)
  
  characters = ['Albedo', 'Aloy', 'Amber', 'Arataki Itto', 'Ayaka', 'Ayato', 'Barbara', 'Beidou', 'Bennett', 'Chongyun', 'Collei', 'Diluc', 'Diona', 'Eula', 'Fischl', 'Ganyu', 'Gorou', 'Hu Tao', 'Jean', 'Kaeya', 'Kazuha', 'Keqing', 'Klee', 'Kokomi', 'Kuki Shinobu', 'Lisa', 'Mona', 'Ningguang', 'Noelle', 'Qiqi', 'Raiden Shogun', 'Razor', 'Rosaria', 'Sara', 'Sayu', 'Shenhe', 'Shikanoin Heizou', 'Sucrose', 'Tartaglia', 'Thoma', 'Tighnari', 'Traveler', 'Venti', 'Xiangling', 'Xiao', 'Xingqiu', 'Xinyan', 'Yae Miko', 'Yanfei', 'Yelan', 'Yoimiya', 'Yun Jin', 'Zhongli']

  character = random.choice(characters)
  
  response = chatbot.ask(f"Write a unique riddle of the character named {character} in Genshin Impact. Google this character if you don't know anything about them.")['content']
  
  spaceLoc = character.find(" ")
  
  if spaceLoc == -1:
    response = response.replace(character, "_"*len(character))
  else:
    string = "_"*len(character)
    res = string[: spaceLoc] + " " + string[spaceLoc + 1:]
    response = response.replace(character, res)
  
  try:
    riddle = response.split("```")[1]
    embed=discord.Embed(title=f"Solve The Riddle | Genshin Character", description=f"First to solve the riddle in chat wins <:MORA:953918490421641246> `{reward}`.\n```{riddle}```", color=discord.Color.blurple())
  except Exception:
    if "model" in response:
      embed=discord.Embed(title=f"Guess The Genshin Character", description=f"Unfortunately, I was not able to generate a riddle due to API overloading. However, first to guess the character wins <:MORA:953918490421641246> `{reward}`.\n```Hint: the character name has {len(character)} letters (including possible blank spaces)```", color=discord.Color.blurple())
    else:
      embed=discord.Embed(title=f"Guess The Genshin Character", description=f"```{response}```", color=discord.Color.blurple())
  msg = await channel.send(embed=embed)
  print(response)
  print(character)
  def check(message):
    return message.channel == channel
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.strip().lower() == character.strip().lower():
      await answer.add_reaction("✅")
      embed=discord.Embed(title=f"Solve The Riddle | Genshin Character", description=f"{answer.author.mention} won <:MORA:953918490421641246> `{reward}`.", color=discord.Color.brand_green())
      await addMora(answer.author.id, reward)
      await msg.edit(embed=embed)
      break

### --- EMOJI RIDDLE --- ###

async def emojiRiddle(channel, client):
  reward = random.randint(3500, 6990)
  
  characters = ['Albedo', 'Aloy', 'Amber', 'Arataki Itto', 'Ayaka', 'Ayato', 'Barbara', 'Beidou', 'Bennett', 'Chongyun', 'Collei', 'Diluc', 'Diona', 'Eula', 'Fischl', 'Ganyu', 'Gorou', 'Hu Tao', 'Jean', 'Kaeya', 'Kazuha', 'Keqing', 'Klee', 'Kokomi', 'Kuki Shinobu', 'Lisa', 'Mona', 'Ningguang', 'Noelle', 'Qiqi', 'Raiden Shogun', 'Razor', 'Rosaria', 'Sara', 'Sayu', 'Shenhe', 'Shikanoin Heizou', 'Sucrose', 'Tartaglia', 'Thoma', 'Tighnari', 'Traveler', 'Venti', 'Xiangling', 'Xiao', 'Xingqiu', 'Xinyan', 'Yae Miko', 'Yanfei', 'Yelan', 'Yoimiya', 'Yun Jin', 'Zhongli']

  character = random.choice(characters)
  
  response = chatbot.ask(f"Use less than 4 emojis to describe the character named {character} in Genshin Impact and wrap all the emojis with large codeblock. Google this character if you don't know anything about them.")['content']
  
  riddle = response.split("```")[1]
  
  embed=discord.Embed(title=f"Solve The *Emojified* Riddle | Genshin Character", description=f"The following emojis describe a Genshin character. First to guess wins <:MORA:953918490421641246> `{reward}`.\n```{riddle}```", color=discord.Color.blurple())
  msg = await channel.send(embed=embed)
  print(response)
  print(character)
  def check(message):
    return message.channel == channel
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.strip().lower() == character.strip().lower():
      await answer.add_reaction("✅")
      embed=discord.Embed(title=f"Solve The *Emojified* Riddle | Genshin Character", description=f"{answer.author.mention} won <:MORA:953918490421641246> `{reward}`.", color=discord.Color.brand_green())
      await addMora(answer.author.id, reward)
      await msg.edit(embed=embed)
      break
      
### --- EGGWALK --- ###

async def eggWalk(channel, client):
  reward = random.randint(190, 850)
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

### --- GUESS THE NUMBER --- ###

async def guessTheNumber(channel, client):
  reward = random.randint(1270, 2450)
  embed=discord.Embed(title=f"Guess The Number", description=f"First to guess what number in **between 1 and 10 (inclusive)** I am thinking of. \nFirst one to guess correctly will earn <:MORA:953918490421641246> `{reward}`.\n\nReacted `⬆️` means the actual number is **higher**\nReacted `⬇️` means the actual number is **lower**\n\n_Do not spam numbers in chat as I might not be able to process them._", color=discord.Color.dark_purple())
  msg = await channel.send(embed=embed)
  def check(message):
    return message.channel == channel
  number = random.randint(1, 10)
  
  while True:
    answer = await client.wait_for('message', check=check)
    if answer.content.isnumeric():
      if int(answer.content.strip()) == number:
        await answer.add_reaction("✅")
        await answer.reply(embed=discord.Embed(title=f"Guess The Number", description=f"{answer.author.mention} got it and earned <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green()))
        await addMora(answer.author.id, reward)
        break
      elif int(answer.content.strip()) > number:
        await answer.add_reaction("⬇️")
      else:
        await answer.add_reaction("⬆️")
      

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
          embed=discord.Embed(title=f"Who's this?", description=f"{interaction.user.mention} guessed correctly and earned <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green())
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
  reward = random.randint(300, 850)
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
  embed=discord.Embed(title=f"Who's this?", description=f"The first to guess wins <:MORA:953918490421641246> `{reward}`. **You can only guess once!**", color=discord.Color.light_grey())
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

### --- WHO SAID IT --- ###

class whoSaidItBtn(discord.ui.Button):
    def __init__(self, name, disabled=False):
        super().__init__(label=name, emoji="👤", 
 style=discord.ButtonStyle.grey, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.embeds[0].description.split("`")[1])
      ref = db.reference("/Random Events")
      randomevents = ref.get()
      duplicate = []
      for key, val in randomevents.items():
        if val['User ID'] == "Who said it":
          user = val["Mora"]
        if val['User ID'] == "Who said it Jump URL":
          jumpUrl = val["Mora"]
        if val['User ID'] == "Those who answered in who said it":
          duplicate = val["Mora"]
          
      
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have guessed once already. No second try!", ephemeral=True)
      else:
        if str(self.label) == user:
          embed=discord.Embed(title=f"Who said it?", description=f"{interaction.user.mention} guessed correctly and earned <:MORA:953918490421641246> `{reward}`.\n\n[Message Jump URL]({jumpUrl})", color=discord.Color.green())
          await interaction.response.edit_message(content="", embed=embed, view=None)
          await addMora(interaction.user.id, reward)
          
          for key, val in randomevents.items():
            if val['User ID'] == "Those who answered in who said it":
              db.reference('/Random Events').child(key).delete()
              break
        else:
          await interaction.response.send_message("Wrong! :x:", ephemeral=True)
          duplicate.append(int(interaction.user.id))
          data = {
            "Those who answered in who said it": {
              "User ID": "Those who answered in who said it",
              "Mora": duplicate
            }
          }
        
          for key, value in data.items():
            ref.push().set(value)

async def whoSaidIt(channel, client):
  reward = random.randint(1600, 4850)
  messages = [message async for message in channel.history(limit=200)]
  random_messages = random.sample(messages, 3)
  message = random.choice(random_messages)
  embed=discord.Embed(title=f"Who said it?", description=f"The first to guess wins <:MORA:953918490421641246> `{reward}`. **You can only guess once!**", color=discord.Color.light_grey())
  embed.add_field(name=f"Message Content", value=message.content, inline=True)
  view = View()
  for item in random_messages:
    # await channel.send(item.author.mention)
    view.add_item(whoSaidItBtn(str(item.author)))
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  try:
    for key, val in randomevents.items():
      if val['User ID'] == "Who said it" or val['User ID'] == "Who said it Jump URL" or val['User ID'] == "Those who answered in who said it":
        db.reference('/Random Events').child(key).delete()
  except Exception:
    print(Exception)
  data = {
    "Who said it": {
      "User ID": "Who said it",
      "Mora": str(message.author)
    }
  }
  for key, value in data.items():
    ref.push().set(value)
  data = {
    "Who said it Jump URL": {
      "User ID": "Who said it Jump URL",
      "Mora": str(message.jump_url)
    }
  }
  for key, value in data.items():
    ref.push().set(value)
  await channel.send(embed=embed, view=view)

### --- MEMORY GAME --- ###

class memoryBtn(discord.ui.Button):
    def __init__(self, emote, disabled=False):
        super().__init__(emoji=emote, 
 style=discord.ButtonStyle.grey, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      reward = int(interaction.message.embeds[0].description.split("`")[1])
      
      ref = db.reference("/Random Events")
      randomevents = ref.get()
      for key, val in randomevents.items():
        if val['User ID'] == "Memory Game":
          emote = val["Mora"]
          break

      duplicate = []
      for key, val in randomevents.items():
        if val['User ID'] == "Those who answered in Memory Game":
          duplicate = val["Mora"]
          break
      
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have guessed once already. No second try!", ephemeral=True)
      else:
        if str(self.emoji) == emote:
          embed=discord.Embed(title=f"Memory Game", description=f"{interaction.user.mention} guessed correctly and earned <:MORA:953918490421641246> `{reward}`.", color=discord.Color.green())
          await interaction.response.edit_message(content="", embed=embed, view=None)
          await addMora(interaction.user.id, reward)
          
          for key, val in randomevents.items():
            if val['User ID'] == "Those who answered in Memory Game":
              db.reference('/Random Events').child(key).delete()
        else:
          await interaction.response.send_message("Wrong! :x:", ephemeral=True)
          duplicate.append(int(interaction.user.id))
          data = {
            "Those who answered in Memory Game": {
              "User ID": "Those who answered in Memory Game",
              "Mora": duplicate
            }
          }
        
          for key, value in data.items():
            ref.push().set(value)

async def memoryGame(channel, client):
  reward = random.randint(1300, 5850)
  
  allEmojis = ["😄", "😊", "😃", "😉", "😍", "😘", "😚", "😗", "😙", "😜",
"😝", "😛", "🤑", "🤓", "😎", "🤗", "🙂", "🤔",
"😐", "😑", "😶", "🙄", "😏", "😒", "🤥", "😌", "😔",
"😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤧",
"😢", "😭", "😰", "😥", "😓", "😈", "👿", "👹", "👺",
"💩", "👻", "💀", "👽", "🌟", "🔥", "❤️", "😊", "🎉",
"🌈", "👍", "✨", "👏", "💕", "🐶", "🍕", "🌺", "📚",
"⚽", "🎵", "🍔", "🍦", "🎂", "🎁", "🎈", "🎨", "🚀",
"⌛", "💡", "🎮", "📷", "📱", "💻", "⭐", "🌙", "🍎"]

  emojis = random.sample(allEmojis, 3)
  chosenCol = random.randint(0, 2)
  chosenEmote = emojis[chosenCol]
  chosenCol += 1
  
  embed=discord.Embed(title=f"Memory Game", description=f"Remember the following order of emotes. You will be asked to recall which column an emoji is from. **You can only guess once!**\n\nFirst to guess correctly wins <:MORA:953918490421641246> `{reward}`.", color=discord.Color.light_grey())

  for x in range(3):
    embed.add_field(name=f"Column {x+1}", value=f"`{emojis[x]}`", inline=True)

  msg = await channel.send(embed=embed)
  await asyncio.sleep(5)
  await msg.delete()
  
  
  view = View()
  random.shuffle(emojis)
  for emote in emojis:
    # await channel.send(item.author.mention)
    view.add_item(memoryBtn(str(emote)))
    
  ref = db.reference("/Random Events")
  randomevents = ref.get()
  try:
    for key, val in randomevents.items():
      if val['User ID'] == "Memory Game" or val['User ID'] == "Those who answered in Memory Game":
        db.reference('/Random Events').child(key).delete()
  except Exception:
    pass
  data = {
    "Memory Game": {
      "User ID": "Memory Game",
      "Mora": str(chosenEmote)
    }
  }
  for key, value in data.items():
    ref.push().set(value)

  await channel.send(embed=discord.Embed(title=f"Memory Game", description=f"Now, which of the following emote was in **Column {chosenCol}**? **You can only guess once!**\n\nFirst to guess correctly wins <:MORA:953918490421641246> `{reward}`.", color=discord.Color.light_grey()), view=view)

### --- TWO TRUTH AND A LIE --- ###

class answerLieBtn(discord.ui.Button):
    def __init__(self, emote, disabled=False):
        super().__init__(emoji=emote, 
 style=discord.ButtonStyle.grey, disabled=disabled)
    async def callback(self, interaction: discord.Interaction):
      mon = interaction.guild.get_role(1051602356011282502)
      liy = interaction.guild.get_role(1052043798542295131)
      inaz = interaction.guild.get_role(1051610326166147122)
      sum = interaction.guild.get_role(1051601337189666826)
      teamRoles = [mon, liy, inaz, sum]
      if not any(role in teamRoles for role in interaction.user.roles):
        await interaction.response.send_message("You must be in a team to participate in this game. Head over to <#1083866201773588571> to select your favorite team.", ephemeral=True)
        raise Exception()
      if str(interaction.user.id) in interaction.message.embeds[0].description:
        await interaction.response.send_message("You can't answer your own question smh", ephemeral=True)
        raise Exception()
      reward = int(interaction.message.embeds[0].description.split("`")[1])
      ref = db.reference("/Random Events")
      randomevents = ref.get()
      for key, val in randomevents.items():
        if val['User ID'] == "Two Truths And A Lie":
          emote = val["Mora"]
          break

      duplicate = []
      for key, val in randomevents.items():
        if val['User ID'] == "Those who answered in ttal":
          duplicate = val["Mora"]
          break
      
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have guessed once already. No second try!", ephemeral=True)
      else:
        if str(self.emoji) == str(emote):
          embed = interaction.message.embeds[0]
          await interaction.message.edit(content="", embed=embed, view=None)
          if mon in interaction.user.roles:
            chanel = interaction.client.get_channel(1119078405971914884)
            num = int(chanel.topic) + 1
            await chanel.edit(topi=str(num))
          elif liy in interaction.user.roles:
            chanel = interaction.client.get_channel(1119078420853293077)
            num = int(chanel.topic) + 1
            await chanel.edit(topi=str(num))
          elif inaz in interaction.user.roles:
            chanel = interaction.client.get_channel(1119078436686807180)
            num = int(chanel.topic) + 1
            await chanel.edit(topi=str(num))
          elif sum in interaction.user.roles:
            chanel = interaction.client.get_channel(1119078456148365312)
            num = int(chanel.topic) + 1
            await chanel.edit(topi=str(num))
            
            
          ref = db.reference("/Team Credits")
          teamcredits = ref.get()
          
          ogcredits = 0
          for key, val in teamcredits.items():
            if val['User ID'] == interaction.user.id:
              ogcredits = val['Team Credits']
              db.reference('/Team Credits').child(key).delete()
              break

          print(ogcredits)
      
          newcredits = ogcredits + 1
          data = {
            interaction.guild.id: {
              "User ID": interaction.user.id,
              "Team Credits": newcredits,
            }
          }
      
          for key, value in data.items():
            ref.push().set(value)
          
          embed=discord.Embed(title=f"Two Truths And A Lie", description=f"{interaction.user.mention} chose {self.emoji} correctly and earned `+1` **Team Credit**! \n*(Use </team mine:1063975298984587316> to check your Team Credits)*", color=discord.Color.green())
          embed.set_footer(text="Now you all know a little bit more about each other.")
          await interaction.response.send_message(embed=embed)
          
          for key, val in randomevents.items():
            if val['User ID'] == "Those who answered in ttal":
              db.reference('/Random Events').child(key).delete()
              break
        else:
          await interaction.response.send_message("Wrong! :x:", ephemeral=True)
          duplicate.append(int(interaction.user.id))
          data = {
            "Those who answered in ttal": {
              "User ID": "Those who answered in ttal",
              "Mora": duplicate
            }
          }
        
          for key, value in data.items():
            ref.push().set(value)

class TwoTruthAndALieModal(discord.ui.Modal, title = "Enter two truths and one lie about you"):
  
  truth1 = discord.ui.TextInput(label="Truth #1", style=discord.TextStyle.short, placeholder="Enter a true statement about yourself.", max_length=256, required=True)
  
  truth2 = discord.ui.TextInput(label="Truth #2", style=discord.TextStyle.short, placeholder="Enter another true statement about yourself.", max_length=256, required=True)
  
  lie = discord.ui.TextInput(label="Lie", style=discord.TextStyle.short, placeholder="Enter a false statement about yourself.", max_length=256, required=True)

  async def on_submit(self, interaction:discord.Interaction):
    truth1 = str(self.truth1)
    truth2 = str(self.truth2)
    lie = str(self.lie)
    reward = int(interaction.message.embeds[0].description.split("`")[1])
    statements = [truth1, truth2, lie]
    
    random.shuffle(statements)

    if statements[0] == lie:
      emote = "<:Anemo:1083874231307214908>"
    elif statements[1] == lie:
      emote = "<:Pyro:1083874234343882792>"
    elif statements[2] == lie:
      emote = "<:Electro:1083874241717489694>"

    ref = db.reference("/Random Events")
    randomevents = ref.get()
    try:
      for key, val in randomevents.items():
        if val['User ID'] == "Two Truths And A Lie" or val['User ID'] == "Those who answered in ttal":
          db.reference('/Random Events').child(key).delete()
    except Exception:
      pass
    data = {
      "Two Truths And A Lie": {
        "User ID": "Two Truths And A Lie",
        "Mora": emote
      }
    }
    for key, value in data.items():
      ref.push().set(value)

    view = View()
    view.add_item(answerLieBtn("<:Anemo:1083874231307214908>"))
    view.add_item(answerLieBtn("<:Pyro:1083874234343882792>"))
    view.add_item(answerLieBtn("<:Electro:1083874241717489694>"))
    
    embed = discord.Embed(title="Two Truths and A Lie", description=f"First to determine which of the following statement by {interaction.user.mention} is a lie wins `+1` Team Credit!\n\n> **You must be in a team to answer this question.**\n\n <:Anemo:1083874231307214908> \"{statements[0]}\"\n <:Pyro:1083874234343882792> \"{statements[1]}\"\n <:Electro:1083874241717489694> \"{statements[2]}\"")
    await interaction.response.send_message(embed=embed, view=view)
      

class TwoTruthAndALieButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Enter your two truths and one lie", emoji="🤫", style=discord.ButtonStyle.grey)
    async def callback(self, interaction: discord.Interaction):
      msg = interaction.message.embeds[0].description
      if str(interaction.user.id) not in msg:
        await interaction.response.send_message("You can't click this button!", ephemeral=True)
        raise Exception()
      await interaction.message.edit(embed=discord.Embed(title="Two Truths and A Lie", description=f"{msg}\n\n> *{interaction.user.mention} is entering their truths and lies...*"), view=None)
      await interaction.response.send_modal(TwoTruthAndALieModal())

async def twoTruthsAndALie(channel, client):
  reward = random.randint(2400, 5700)
  messages = [message async for message in channel.history(limit=1)]
  user = messages[0].author
  view = View()
  view.add_item(TwoTruthAndALieButton())
  await channel.send(embed=discord.Embed(title="Two Truths and A Lie", description=f"{user.mention} will be entering their **three statements**. First to determine which statement is a lie wins `+1` Team Credit!"), view=view)

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
  reward = random.randint(3400, 8500)
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
      
    if (message.channel.id == 1104212482312122388 and message.id % 20 == 0) or (message.author.id == 692254240290242601 and message.content == "summonevent"):
    # if message.channel.id == 1026867655468126249 and message.id % 2 == 0:
      if (message.author.id == 692254240290242601 and message.content == "summonevent"):
        chn = self.client.get_channel(1104212482312122388)
      else:
        chn = message.channel
      okForEvent = True
      messages = [message async for message in chn.history(limit=15)]
      for msg in messages:
        if len(msg.embeds) > 0 and msg.author.id == 732422232273584198:
          okForEvent = False
      if okForEvent:
        # await message.channel.send(embed=discord.Embed(title="<:gi_cafe:1103720959950725190>  2023 Cafe Summer Festival", description="Happy summer! Since chat is relatively active, I'm dropping a random event in `3 seconds`.", color=discord.Color.orange()))
        # \n\n_> Keep in mind that your uploaded images will be automatically cropped, maintaining a ratio of 720x256 pixels instead of being scaled. We recommended you select an image with a similar shape to the new </mora:1113523731122372618> inventory image._
        
        events = [
          # defeatTheBoss,
          # typerRacer,
          # eggWalk,
          # matchThePFP
          # splitOrSteal,
          # reverseTyper,
          # pickUpIceCream,
          pickUpTheWatermelon,
          # riddle,
          guessTheNumber,
          # emojiRiddle,
          # memoryGame,
          whoSaidIt,
          unscrambleWords,
          twoTruthsAndALie,
          # trueOrFalse
        ]
        

        # - Element Mastery
        # - Roll a dice (gotcha system)
        event = random.choice(events)
        if event != twoTruthsAndALie:
          await chn.send(embed=discord.Embed(title="NEW Feature Dropped :tada: ", description="**Update on Jun 28:** You can now use the </customize:1123732330679390219> command to personalize your mora inventory background. Each customization will have a cost of <:MORA:953918490421641246> `5000`. ", color=discord.Color.gold()))
        await event(chn, self.client)
        

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(TheEventItself(bot))