import discord, os, openai
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

### ------ WELCOME IMAGE CARD ------ ###
async def createWelcomeMsg(user, bg="./assets/bg.png", filename="./assets/welcome.png"):
  await user.avatar.with_static_format("png").with_size(256).save(filename)
  im1 = Image.open(bg)
  im2 = Image.open(filename)

  bigsize = (im2.size[0] * 3, im2.size[1] * 3)
  mask = Image.new('L', bigsize, 0)
  draw = ImageDraw.Draw(mask) 
  draw.ellipse((0, 0) + bigsize, fill=255)
  mask = mask.resize(im2.size, Image.ANTIALIAS)
  im2.putalpha(mask)

  im1.paste(im2, (384, 50), im2.convert("RGBA"))
  color = (255, 255, 255)
  font = ImageFont.truetype("./assets/ja-jp.ttf", 75)
  d1 = ImageDraw.Draw(im1)
  d1.text((350,330), "Welcome", font=font, fill=color)
  im1.save(filename)
  font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
  text = f"{user.name}"
  textLen = len(text)
  d2 = ImageDraw.Draw(im1)
  d2.text((((1024/2)-(20*(textLen/2))),410), text, font=font, fill=color)
  im1.save(filename)
  return filename

class Welcome(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot

  @app_commands.command(
    name = "welcome",
    description = "Generates a custom welcome image card"
  )
  @app_commands.describe(
    user = "Specify any user",
  )
  async def welcome(
    self,
    interaction: discord.Interaction,
    user: discord.Member = None
  ) -> None:
    if user == None:
      user = interaction.user
    await interaction.response.defer()
    filename = await createWelcomeMsg(user)
    openai.api_key = os.environ['OPENAI_KEY']
    
    response = openai.Completion.create(
      model="text-davinci-003",
      prompt=f"Write a welcome message for a new member called {user.name} in a Discord server called {interaction.guild.name}.",
      temperature=0.99,
      max_tokens=256,
      top_p=1,
      frequency_penalty=0,
      presence_penalty=0
    )
    await interaction.followup.send(content=response['choices'][0]['text'], file=discord.File(filename))
    

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Welcome(bot), guilds=[discord.Object(id=783528750474199041)])