import discord
import aiohttp

from discord.ext import commands
from firebase_admin import db
from commands.Welcome.createWelcomeMsg import createWelcomeMsg

def word(n):
    return str(n)+("th" if 4<=n%100<=20 else {1:"st",2:"nd",3:"rd"}.get(n%10, "th"))
  
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

class OnWelcomeMemberJoin(commands.Cog): 
    def __init__(self, bot):
        self.client = bot
  
    @commands.Cog.listener() 
    async def on_member_join(self, member):
        ref = db.reference("/Welcome")
        welcome = ref.get()

        welcomeChannel = found = False
        file = embed = None

        for key, val in welcome.items():
            if val['Server ID'] == member.guild.id:
                welcomeChannel = val["Welcome Channel ID"]
                welcomeImageEnabled = val["Welcome Image Enabled"]
                break

        if welcomeChannel is not False:
            ref2 = db.reference("/Welcome Content")
            welcomecontent = ref2.get()
        
            for key, val in welcomecontent.items():
                if val['Server ID'] == member.guild.id:
                    if (val['Title'] != "" or val['Description'] != ""):
                        hex = val['Color']
                        if hex.startswith('#'):
                            hex = hex[1:]
                        async with aiohttp.ClientSession() as session:
                            async with session.get('https://www.thecolorapi.com/id', params={"hex": hex}) as server:
                              if server.status == 200:
                                  js = await server.json()
                                  try:
                                      color = discord.Color(int(f"0x{js['hex']['clean']}", 16))
                                  except:
                                      color = discord.Color.blurple()
                            
                        embed = discord.Embed(title=script(val['Title'], member, member.guild), description=script(val['Description'], member, member.guild), color=color)
                        if welcomeImageEnabled:
                            filename = await createWelcomeMsg(member, bg=f"./assets/Welcome Image Background/{member.guild.id}.png")
                            chn = self.client.get_channel(1026904121237831700)
                            msg = await chn.send(f"**Guild Name:** {member.guild}", file=discord.File(filename))
                            url = msg.attachments[0].proxy_url 
                            embed.set_image(url=url)
                    elif (val['Title'] == "" and val['Description'] == ""):
                        if welcomeImageEnabled:
                            filename = await createWelcomeMsg(member, bg=f"./assets/Welcome Image Background/{member.guild.id}.png")
                            file = discord.File(filename)

                    channel = self.client.get_channel(welcomeChannel)
                    await channel.send(script(val['Message Content'], member, member.guild), embed=embed, file=file)
      

async def setup(bot): 
    await bot.add_cog(OnWelcomeMemberJoin(bot))