import discord, firebase_admin, random, datetime, asyncio, time, re
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from discord.ui import Button, View


class AllRoles(commands.Cog): 
  def __init__(self, bot):
    self.client = bot

  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return
    
    if message.guild.id == 717029019270381578 and message.content == "-artcredits":
      chn = message.guild.get_channel(1115935004267134976)
      thread = message.guild.get_thread(1259547951903281153)
      messages = [msg async for msg in chn.history(limit=None, oldest_first=True)]
      for m in messages:
        try:
          webhook = await self.client.fetch_webhook(1259560515425009694)
          await webhook.send(content=m.content, username=m.author.display_name, avatar_url=m.author.avatar.url, wait=True, thread=thread)
          if len(m.attachments) > 0:
            for attachment in m.attachments:
              await webhook.send(content=attachment.url, username=m.author.display_name, avatar_url=m.author.avatar.url, wait=True, thread=thread)
          if len(m.stickers) > 0:
            for sticker in m.stickers:
              await webhook.send(content=sticker.url, username=m.author.display_name, avatar_url=m.author.avatar.url, wait=True, thread=thread)
        except Exception as e:
          print(e)
          continue

    if message.guild.id == 717029019270381578 and message.content == "-partnerreq":
      msg = await message.channel.fetch_message(1259547917275107468)
      embed = discord.Embed(color=0x1fceb9, title="Partnership List & Requirements 🤝", description="""> Please create a ticket at <#1083745974402420846> for any partnership offers, questions or concerns. **The strict minimum server member requirement is `500`**, but your server's eligibility is evaluated case-by-case. *Even if your server meets all the requirements, this does not guarantee acceptance as a server partner.*

_**Server owners and administrators** who are partnered with us will be granted the esteemed <@&1049100647884132443> role. If you are a partnered owner or administrator, **kindly inform us** whom we should assign this role to._""")
      embed.add_field(name="1) Genshin/HSR related", value="Your server **must** have some kind of Genshin/HSR related content, we will not accept you otherwise.", inline=True)
      embed.add_field(name="2) Good Atmosphere", value="Your server should be friendly, and non-toxic overall. *If possible, the server should also have AutoMod enabled and be suitable for all ages.*", inline=True)
      embed.set_footer(text="* Servers that no longer fulfill these requirements will have their partnership revoked")
      embed.set_image(url="https://i.imgur.com/pxFUCeF.png")
      await msg.edit(embed=embed)

    if message.guild.id == 717029019270381578 and message.content == "-allroles":
      # embed = discord.Embed(color=0x7F00FF)
      # embed.set_image(url="https://media.discordapp.net/attachments/1083650021351751700/1135715748560511066/bg-dark.png")
      # await message.channel.send(embed=embed)

      embed = discord.Embed(color=0x7F00FF, title="Staff Team & Helpers", description="""- <@&753869940162953357>
  - The people who own the server and oversee all operations within the server.
- <@&1185401288763121735>
  - The highest staff position for the most experienced moderators who lead the server.
- <@&748840161240023040>
  - Staff with administrator permissions who manage all aspects of the server.
- <@&1185402319731429547>
  - For senior and trusted staff members who have been around for quite some time.
- <@&828624806839844965>
  - For staff members who prove themselves worthy as one.
- <@&814390209034321920>
  - A trial staff role for the newest staff members, applicable in <#1083848742312104026>.
- <@&1185149001775992935>
  - Official staff members who manage the <@&1185149195695439932>, create and monitor server-wide events
- <@&1185149195695439932>
  - Unofficial staff members in charge of creating, moderating, and managing server-wide events
- <@&1185148937275986031>
  - Official staff members who manage the <@&1185148937275986031>, create and monitor art-related affairs
- <@&1185149073947361462>
  - Unofficial staff members in charge of creating artworks for the server and managing art-related affairs
- <@&1227716082178068530>
  - Official staff members in charge of overseeing and reviewing applications for <@&1196992769584025640> and <@&1233135427981021206>
- <@&1167237629637570571>
  - Official staff members in charge of overseeing and reviewing applications for <@&987249271403343893> and <@&1167496178645078178>
- <@&1230382717758083102>
  - Unofficial staff members managing all leaks-related affairs in the server
""")
      await message.channel.send(embed=embed)
      embed = discord.Embed(color=0x7F00FF, title="Self Roles", description="""- Color roles
  - <@&829710752562413629>
  - <@&829709938192023602>  
  - <@&829715732274610247>  
  - <@&829710119612579920>  
  - <@&829710561318666251>  
  - <@&829710668638191646>  
  - <@&829710981122097212>
- Game roles
  - <@&1202771128322629673>
  - <@&1202771167434375189>
- Genshin Co-op region roles
  - <@&950655921003036682>
  - <@&950655922760470569>
  - <@&950655925033775114>
  - <@&950655926518562828>
- HSR Supports system roles
  - <@&1258906839484207166>
  - <@&1258907126814871693>
  - <@&1258907112072020180>
  - <@&1258907094875242578>
- In-game region roles
  - <@&938466616092536903>
  - <@&938466600909172787>
  - <@&938466606747631676>
  - <@&938466611550101524>
- Leak access roles 
  - <@&1209662193918804128>
  - <@&1254822637029425254>
  - <@&1209662255227084881>
  - <@&1254822679718924408>
- <@&952852416221564958>
  - Role for members who want to be notified for <#1083698310059143199>.
- <@&1196984810900566138>
  - Role for members who want to be notified for <#1196984161022525501>.
- <@&811891248830087189>
  - Role for members who want to be notified for <#1083639743746691132>.
- <@&759377982467866664>
  - Role for members who want to receive <#1107450503069192302> notifications and advertisements.
- <@&911603880419295284>
  - Role for members who want to be notified for <#1083634013287219240>.
- <@&1159317294212714599>
  - Role for members who want to be notified for <#1181236958844948551>.
- <@&1181467953091334155>
  - Role for members who want to be pinged for drops in <#1104206549527838770>.
- <@&847482419170770954>
  - Role for members who want to avoid unnecessary pings.
""")
      await message.channel.send(embed=embed)
      embed = discord.Embed(color=0x7F00FF, title="Exclusive Roles", description="""- <@&1048210028387127306>
  - Former staff members who have left a lasting impact on the server.
- <@&1013158809709060249>
  - Exclusive role for members who have won very special and challenging server events.
- <@&1039306817429311508>
  - Exclusive role for members with future mysterious special privileges.
- <@&1191109570450432060>
  - Exclusive role for celebrating the New Year in 2024.
- <@&1058145940868960256>
  - Exclusive role for celebrating the New Year in 2023.
- <@&985557483219214416>
  - Exclusive role for winners of photography contests.
- <@&1034851436682551438>
  - Exclusive role for winners of Halloween events.
- <@&1051611672042811432>
  - Exclusive role for participants in the 2022 Winter Festival event.
- Exclusive roles obtainable in 2023 Cafe Summer Festival.
  - <@&1121926639316643861>
  - <@&1121926508773126225>
  - <@&1121926535641841744>
  - <@&1121926689669259375>
  - <@&1121926614935150652>
  - <@&1121926665610743960>
  - <@&1121926579673641111>
  - <@&1121926589949681665>
  - <@&1121926474765697044>
  - <@&1121926417777696798>
- <@&1186274223342223501>
  - Exclusive role for participants in the joint-server photography event in December 2023
- <@&1153350519927091301>
  - Exclusive role for participants in the September 2023 Team Challenge:tm:
- <@&748840679370915850>
  - Role for bots in the server.
""")
      await message.channel.send(embed=embed) 
      embed = discord.Embed(color=0x7F00FF, title="Team Roles", description="""- <@&1051602356011282502>
  - Role for members affiliated with Team Mondstadt.
- <@&1051600715761586206>
  - Role for the leader of Team Mondstadt.
- <@&1052043798542295131>
  - Role for members affiliated with Team Liyue.
- <@&1199042975158784090>
  - Exclusive role for members of Team Liyue in 2023.
- <@&1051600954031624264>
  - Role for the leader of Team Liyue.
- <@&1051610326166147122>
  - Role for members affiliated with Team Inazuma.
- <@&1051601178649174156>
  - Role for the leader of Team Inazuma.
- <@&1051601337189666826>
  - Role for members affiliated with Team Sumeru.
- <@&1051600483657187418>
  - Role for the leader of Team Sumeru.
- <@&1106654739791364197>
  - Role for members affiliated with Team Fontaine.
- <@&1146524181090021436>
  - Role for the leader of Team Fontaine.
- <@&1200241691798536345>
  - Role for team members who wish to be notified for every attack initiated on their team
""")
      await message.channel.send(embed=embed) 
      embed = discord.Embed(color=0x7F00FF, title="Obtainable Roles", description="""
- <@&1140813525414068288> who have joined our [Server Subscriptions](https://discord.com/channels/717029019270381578/shop)
  - <@&1141132746421452871>
  - <@&1141131886341668875>
  - <@&1140813528803057754>
- <@&793102989362855946>
  - Role for members who have boosted the server and are enjoying <#1083739428876464198>.
- <@&1111002520442110052>
  - Honorary role given to the two most active members of the week on the <#1110998569466474716>.
- <@&996707492853710888>
  - Role for dedicated members of the server who put our [server invite link](https://discord.gg/traveler) on their Discord statuses.
- <@&885555357374636052>
  - Role for members celebrating their birthday by setting it in <#1084690060923916288>.
- <@&987249271403343893>
  - Role for members with expertise in Genshin character builds in <#1083738044173139999>.
- <@&1196992769584025640>
  - Role for members with expertise in HSR character builds in <#1196988766972281003>.
- <@&1167496178645078178>
  - Trial role for members with expertise in Genshin character builds.
- <@&1233135427981021206>
  - Trial role for members with expertise in HSR character builds.
- <@&993360929808990248>
  - Role for members with at least one C6 5☆ character or R5 5☆ weapon in the game.
- <@&815132429189644318>
  - Role for skilled artists in the community who frequently post their works in <#1140818871847235604>.
- <@&993402036529930290>
  - Role for players who have a 36-star abyss on their current rotation in the game.
- <@&1191055539447267438>
  - Role for experienced travelers with 90%+ exploration in Fontaine.
- <@&1066923137335296142>
  - Role for experienced travelers with 90%+ exploration in Sumeru.
- <@&1066923029961130004>
  - Role for experienced travelers with 90%+ exploration in Inazuma.
- <@&1066921995796742216>
  - Role for experienced travelers with 90%+ exploration in Liyue.
- <@&1066921990482563183>
  - Role for experienced travelers with 90%+ exploration in Mondstadt.
- <@&1066923619030143006>
  - Role for exceptional players who have reached player level 10 in Genius Invokation: TCG!
- <@&1203812547686572052>
  - Have at least 1+ E6 5☆ character, or a S5 light cone
- <@&1203812976843292792>
  - Completed Simulated Universe's Gold and gears at conundrum level 12
- <@&1203813469397188618>
  - Completed the floor 12 in Memory of Chaos
- <@&1203813672691040276>
  - Completed the Pure Fiction with all 12 stars
- <@&1203813802752090125>
  - Acquired all 45 stars in Jarilo VI's Memory of Chaos
- <@&1203813949552853084>
  - Acquired all 18 stars in Xiangzhou Luofu's Memory of Chaos
- <@&1058526486967095296>
  - Role for members who have at least one suggestion approved in <#1107010468440186970>.
- <@&1049100647884132443>
  - Role for official partners of the Genshin Impact Cafe.
- <@&943486837559791618>
  - Role for members who create Genshin Impact content.
- <@&1163266817268129882>
  - Purchasable role that allows members permanent access to <#1141416403090546728>
- <@&1083687810340507668>
  - Default role for new verified members joining the server.
""")
      embed.set_footer(text="If you wish to obtain any of the above roles, or have questions regarding them, kindly create a ticket.")
      await message.channel.send(embed=embed)
      embed = discord.Embed(color=0x7F00FF, title="Level Roles & Perks", description="""
- <@&765485751680892958>
  - Access to the private channel <#1116766385008283739>
- <@&949339134273679420>
  - Access to <#1094814137143541800>
- <@&879629786455097344>
  - Be able to receive customized Genshin-themed graphic design (profile picture/banner) by our <@&1185149073947361462>
- <@&879629784718663750>
  - Priority in events such as talks hosted by voice actors
- <@&759223538779160608>
  - Qualification to become a leader for existing/new team
- <@&949336415563579522>
  - Access to <#1141416403090546728>
- <@&879629862627835954>
  - Ability to create polls in the server
- <@&752874966919151666>
  - Qualification to apply for staff in <#1083848742312104026>
- <@&752763116894421072>
  - Access to embed links in chats
  - Access to view and send messages in <#1104206549527838770> to prevent lurkers
- <@&949336411255996416>
  - Access to upload attachments in <#1104212482312122388>
- <@&949337290969350304>
  - Qualification to join a team in <#1083866201773588571>
- <@&767558681113526272>
  - Access to <#1241130007955509248>
- <@&1209678396444119051>""")
      await message.channel.send(embed=embed)


async def setup(bot): 
  await bot.add_cog(AllRoles(bot))