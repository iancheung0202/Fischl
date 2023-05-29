import discord, firebase_admin, asyncio, datetime, os, openai, random
from discord import app_commands
from discord.ext import commands
from firebase_admin import credentials, db
from commands.Utility.welcome import createWelcomeMsg


class WelcomeBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Welcome our new traveler",
                         emoji="👋",
                         style=discord.ButtonStyle.green,
                         custom_id="welcomeBtn")

    async def callback(self, interaction: discord.Interaction):
        joiner = interaction.guild.get_member(
            int(interaction.message.mentions[0].id))
        left = False
        try:
          print(joiner.name)
        except Exception:
          left = True
        if left:
          await interaction.message.delete(delay=3)
          await interaction.response.send_message(
                content=
                "Unfortunately our dear traveler left the server.",
                ephemeral=True)
          raise Exception("Unfortunately our dear traveler left the server.")
        welcomer = interaction.user
        mc = interaction.message.content
        msg = [
            'said, "warm welcome to the server! :heart:"',
            'said, "make yourself at home! :couch:"',
            'said, "hope you enjoy your stay here! :blush:"',
            'gave a heartful hug :hugging:', 'said hi :wave:',
            'are delighted that you are here :grin:',
            'are glad that you joined! :homes:',
            'said you should be proud being here! :star_struck:',
            'said formally, "Greetings" :bow:',
            'wishes you a fantastic time in the server! :sparkles:',
            'thinks you\'re awesome for joining! :thumbsup:',
            'gave a virtual high-five! :hand_splayed:',
            'believes you\'ll be a great addition to our community! :muscle:',
            'are thrilled to have you! :partying_face:'
        ]
        if joiner == welcomer:
            await interaction.response.send_message(
                content=
                "Hey! Thank you for joining our server! Enjoy your stay!",
                ephemeral=True)
        elif welcomer.name in mc:
            await interaction.response.send_message()
        else:
            if mc[-1] == "!":
                await interaction.message.edit(
                    content=f"{mc}\n\n> **{welcomer.name}** {random.choice(msg)}"
                )
            else:
                await interaction.message.edit(
                    content=f"{mc}\n> **{welcomer.name}** {random.choice(msg)}"
                )
            await interaction.response.send_message()


class WelcomeBtnView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(WelcomeBtn())


class OnMemberJoin(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        ### ------ GENSHIN IMPACT CAFE ------ ###
        btn = [
            "Greet our new traveler", "Say hi to user",
            "Welcome our new traveler", "Show some support to our new traveler"
        ]
        emote = ["👋", "💖", "❤️", "💛", "💜", "💙"]
        if member.guild.id == 717029019270381578:
            if member.id == 692254240290242601:
                role = member.guild.get_role(753869940162953357)
                await member.add_roles(role)
                raise Exception()
            channel = self.client.get_channel(1104212482312122388)
            member_count = 0
            for member in member.guild.members:
                member_count += 1

            def word(n):
                return str(n) + ("th" if 4 <= n % 100 <= 20 else {
                    1: "st",
                    2: "nd",
                    3: "rd"
                }.get(n % 10, "th"))

            openai.api_key = os.environ['OPENAI_KEY']

            # response = openai.Completion.create(
            #   model="text-davinci-003",
            #   prompt=f"Write a welcome message for a new member called {member.name} in a Discord server called {member.guild.name}.",
            #   temperature=0.99,
            #   max_tokens=256,
            #   top_p=1,
            #   frequency_penalty=0,
            #   presence_penalty=0
            # )
            # msg = response['choices'][0]['text']
            # msg = msg[msg.find('! '):]
            msg = "!"
            msg = f"Warm welcome to **{member.guild.name}**, {member.mention}! You are the **{word(member_count)} member** here{msg}"

            filename = await createWelcomeMsg(member)
            await channel.send(msg,
                               file=discord.File(filename),
                               view=WelcomeBtnView())

            embed = discord.Embed(title=f"Welcome to {member.guild.name}!",
                                  description=f"""
  Hi young Traveler! Wow, it's our honour to finally have you here! We've been waiting for you!
  
  _Who am I? I am your guide, Paimon! Ehe~_

  To make sure you won't accidentally get too close to the Sun, please read <#1083632416561844274> before doing anything!
  
  Ay, what are you waiting for? Let's go and start saying hi <#1104212482312122388>!
  
  Oh yeah, and btw, PAIMON IS NOT EMERGENCY FOOD! <:Paimon_Think:944862982213632101>
  """,
                                  color=0xFECEF8)
            embed.set_thumbnail(
                url=
                "https://progameguides.com/wp-content/uploads/2022/01/Featured-Paimon-Genshin-Impact.jpg"
            )

            chn = self.client.get_channel(1026904121237831700)
            msg = await chn.send(file=discord.File(filename))
            url = msg.attachments[0].proxy_url
            embed.set_image(url=url)

            try:
                await member.send(embed=embed)
                await member.send(
                    """***Are you interested in the following event? <:Paimon_Think:944862982213632101>***
If yes, **click the `Interested` button** so you will be notified! :bell: 

https://discord.gg/NhtyFAC9w3?event=1102054015568728156""")
            except Exception:
                pass

            # selfRolesChannel = self.client.get_channel(952914912018067567)
            # selfRoleReminderMessage = await selfRolesChannel.send(f"Welcome to **{member.guild.name}**, {member.mention}! Make sure to grab your **self roles**!")
            # await asyncio.sleep(20)
            # await selfRoleReminderMessage.delete()

            # bipso = self.client.get_channel(1057093435535929394)
            # bipsomsg = await bipso.send(member.mention)
            # await asyncio.sleep(1)
            # await bipsomsg.delete()

            selectyourteam = self.client.get_channel(1083866201773588571)
            selectmsg = await selectyourteam.send(member.mention)
            await asyncio.sleep(1)
            await selectmsg.delete()

            # giveaway = self.client.get_channel(1083634013287219240)
            # gwmsg = await giveaway.send(member.mention)
            # await asyncio.sleep(1)
            # await gwmsg.delete()

        ### ------ GENSHIN HANGOUT ------ ###
        elif member.guild.id == 862842816571768852:
            filename = await createWelcomeMsg(member)
            channel = self.client.get_channel(862842816571768854)
            member_count = 0
            for member in member.guild.members:
                member_count += 1

            def word(n):
                return str(n) + ("th" if 4 <= n % 100 <= 20 else {
                    1: "st",
                    2: "nd",
                    3: "rd"
                }.get(n % 10, "th"))

            welcomeMsg = f"Hey, {member.mention}! You are the **{word(member_count)} traveler** in **{member.guild.name}**!"
            embed = discord.Embed(title="Traveler! Traveler! where are you?",
                                  description="""
  Oh look I found you! Phew! Finally! I thought I lost you!
  
  Anyways, thanks for joining and welcome to the server! Remember the following before you come in:
  
  ~ Go wipe your dirty shoes in <#862843570453348412>
  
  ~ Cook some delicious food in <#862843998825480212>
  
  ~ Remember to talk with Paimon's friends in <#862842816571768855>
  """,
                                  color=0x5ADCAE)
            embed.set_author(name=member.name, icon_url=member.avatar.url)
            filename = await createWelcomeMsg(member)
            chn = self.client.get_channel(1026904121237831700)
            msg = await chn.send(file=discord.File(filename))
            url = msg.attachments[0].proxy_url
            embed.set_image(url=url)
            embed.set_thumbnail(
                url=
                "https://media.discordapp.net/attachments/717216024910364732/955679237547909210/genshin-impact-all-characters.jpg"
            )
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.datetime.utcnow()
            await channel.send(welcomeMsg, embed=embed)
            embed = discord.Embed(title=f"Welcome to {member.guild.name}!",
                                  description=f"""
  Hi young Traveler! Wow, it's our honour to finally have you here! We've been waiting for you!
  
  _Who am I? I am your guide, Paimon! Ehe~_
  
  Ay, what are you waiting for? Let's go and start saying hi <#862842816571768855>!
  
  Oh yeah, and btw, PAIMON IS NOT EMERGENCY FOOD! <:Paimon_Think:944862982213632101>
  """,
                                  color=0xFECEF8)
            embed.set_thumbnail(
                url=
                "https://progameguides.com/wp-content/uploads/2022/01/Featured-Paimon-Genshin-Impact.jpg"
            )
            embed.set_image(url=url)
            await member.send(embed=embed)


async def setup(bot):
    await bot.add_cog(OnMemberJoin(bot))
