import discord, os, openai
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

perks = {
    100: "Access to #exclusive-chat",
    90: "Access to Archived Channels",
    75: "One custom profile picture or banner",
    69: "Priority in events like talks hosted by voice actors",
    50: "Qualification to become a leader for existing or new team",
    40: "Access to #manage-your-vc",
    35: "Ability to create polls in the server",
    20: "Qualification to apply for staff in #applications",
    10: "Access to embed links and GIFs in chats",
    5: "Access to upload attachments in #chill-chat",
    3: "Qualification to join a team in ⁠#select-your-team",
    1: "Access to ⁠#Join here to create VC"
}

def rgb_to_hex(r, g, b):
  hex_code = "#{:02X}{:02X}{:02X}".format(r, g, b)
  return hex_code

### ------ WELCOME IMAGE CARD ------ ###
# home/container/commands/CafeOnly/admin.py
async def createLevelImage(user, level, levelRole, bg="./assets/levelbg.png", filename="./assets/levelup.png"):
  try:
    await user.avatar.with_static_format("png").with_size(256).save(filename)
    im1 = Image.open(bg)
    im2 = Image.open(filename)
    await levelRole.icon.with_static_format("png").save("./assets/leveluproleicon.png")
    im3 = Image.open("./assets/leveluproleicon.png")
  except Exception as e:
    print(e)
    im1 = Image.open(bg)
    im2 = Image.open("./assets/DefaultIcon.png")
    im3 = None

  bigsize = (int(im2.size[0] * 2), int(im2.size[1] * 2))
  mask = Image.new('L', bigsize, 0)
  draw = ImageDraw.Draw(mask) 
  draw.ellipse((0, 0) + bigsize, fill=255)
  mask = mask.resize(im2.size, Image.LANCZOS)
  im2.putalpha(mask)
  im1.paste(im2, (247, 87), im2.convert("RGBA"))
  
  ### ROLE ICON
  im1.paste(im3, (755, 280), im3.convert("RGBA"))
  
  ### TEXT "LEVEL"
  font = ImageFont.truetype("./assets/ja-jp.ttf", 90)
  d1 = ImageDraw.Draw(im1)
  d1.text((700,150), "Level", font=font, fill=(255, 255, 255))
  im1.save(filename)
  
  ### LEVEL ROLE NAME
  color = rgb_to_hex(user.color.r, user.color.g, user.color.b)
  name = levelRole.name.split("-")[1].strip()
  font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
  d5 = ImageDraw.Draw(im1)
  d5.text((700,90), f"{name.upper()}", font=font, fill=color)
  im1.save(filename)
  
  ### ACTUAL LEVEL
  font = ImageFont.truetype("./assets/ja-jp.ttf", 275)
  d2 = ImageDraw.Draw(im1)
  d2.text((1000, 120), f"{level}", font=font, fill=color)
  im1.save(filename)
  
  ### USER NAME
  font = ImageFont.truetype("./assets/ja-jp.ttf", 40)
  text = f"{user.name}"
  textLen = len(text)
  d3 = ImageDraw.Draw(im1)
  d3.text((((724/2)-(22*(textLen/2))),387), text, font=font, fill=(255, 255, 255))
  im1.save(filename)
  
  ### PERK
  try:
    font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
    text = f"Earned: {perks[int(level)]}"
    textLen = len(text)
    d4 = ImageDraw.Draw(im1)
    d4.text((((740)-(17*(textLen/2))), 494), text, font=font, fill=color)
    im1.save(filename)
  except KeyError:
    font = ImageFont.truetype("./assets/ja-jp.ttf", 29)
    if level > 69:
      text = f"Keep yapping to level up!"
    else:
      text = f"Keep chatting to level up!"
    d4 = ImageDraw.Draw(im1)
    d4.text((570, 494), text, font=font, fill=(255, 255, 255))
    im1.save(filename)

  return filename


async def setup(bot):
    pass