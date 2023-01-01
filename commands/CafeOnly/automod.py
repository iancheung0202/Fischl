import discord, firebase_admin, asyncio, openai, os, datetime
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db
from discord.ui import Button, View

class OnAutoMod(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user: 
        return
    if message.channel.id == 968751043884224532:
      openai.api_key = os.environ['OPENAI_KEY']
      query = f"""- Keep this community positive and productive
- Be respectful towards each other. 
- Be tolerant of different views and opinions. 
- Treat others the way you would like to be treated. 
- Refrain from harassing, attacking, and using offensive language. 
- Avoid gossiping or speaking negatively about other members. While criticism is encouraged, it should be kept reasonable and constructive.
- Refrain from discussing or posting content regarding the topics such as sexuality, politics, religion, racism or any other topics that could potentially hurt, stir up anger disrespect or discriminate against a group of people or an individual. 
- No spamming, trolling, or illegal activities. 
- Refrain from sharing any personal or sensitive information on the server. 
- Doxxing other individuals and impersonating others are also prohibited. 
- We do not tolerate spoilers or discussion of unreleased content. 
- Account buying, selling, trading or sharing should be refrained. 
- Do not post any harmful, phishing or suspicious links as well.
- No self-advertising or soliciting. Posting in any channels or direct messaging any members of this server to promote services, products, social media, or projects that focus on monetary gain is strictly forbidden.
- Help maintain a safe atmosphere for everyone to share in this server.

Determine if the following message sent in a Discord server violates the above rules.
\"{message.content}\""""
      response = openai.Completion.create(
        model="text-davinci-003",
        prompt=query,
        temperature=0.7,
        max_tokens=1000,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
      )
      firstreply = response['choices'][0]['text']
      msg = firstreply.replace(query, "")
      yesorno = msg.split(".")[0]
      if "No" in yesorno:
        pass
      elif "Yes" in yesorno:
        secondquery = f"""{firstreply}
        
        If yes, send a message to the person who sent this message explaining why and which rule it broke."""
        secondresponse = openai.Completion.create(
          model="text-davinci-003",
          prompt=secondquery,
          temperature=0.7,
          max_tokens=1000,
          top_p=1,
          frequency_penalty=0,
          presence_penalty=0
        )
        await message.delete()
        try:
          await message.author.timeout(datetime.timedelta(days=0, seconds=0, microseconds=0, milliseconds=0, minutes=5, hours=0, weeks=0))
        except Exception as e:
          print(e)
          print("user cannot be timed out")
        announcement = secondresponse['choices'][0]['text'].replace(secondquery, '').replace('[Name]', message.author.mention).replace('[Your Name]', 'The Discord Automod')
        embed=discord.Embed(description=f"{announcement}", color=discord.Color.blurple())
        notice = await message.channel.send(embed=embed)
        await message.author.send(embed=embed)
        logchn = self.client.get_channel(955410549477351445)
        await logchn.send(embed=discord.Embed(title="Automod Actions Taken", description=f"User: {message.author.mention} `({message.author.id})`\nMessage: {message.content}\nActions taken: Timed out\n\nMessage sent to offender: ```{announcement}```", color=discord.Color.blurple()))
        await asyncio.sleep(20)
        await notice.delete()
        
  

async def setup(bot): 
  await bot.add_cog(OnAutoMod(bot))