import discord, firebase_admin, random, datetime, asyncio
from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from assets.appliedVCMod import users as appliedVCMod
from ai import simple_get
from discord.ui import Button, View

class AcceptRejectButtonForVCMod(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Accept', style=discord.ButtonStyle.green, custom_id='acceptvc')
  async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.guild.get_role(753869940162953357) not in interaction.user.roles:
      await interaction.response.send_message("Only the server owners can accept/reject applications! You can of course give suggestions or opinions on the application!", ephemeral=True)
      raise Exception()
    user = interaction.guild.get_member(int(interaction.message.content.split("`")[1]))
    embed = discord.Embed(title="You are accepted! :tada:", description="Congratulations! Your VC moderator application is accepted by the server owners! You have been given the VC Moderator role! Your job is to look out for any annoying or inappropriate behaviours in voice channels. Happy moderatin'!", color=0x00FF00)
    await user.add_roles(interaction.guild.get_role(1115161674194878575))
    await user.send(embed=embed)
    await interaction.message.edit(content=f"✅ Applicant ID: `{user.id}`", view=None)
    await interaction.response.send_message(ephemeral=True)

  @discord.ui.button(label='Reject', style=discord.ButtonStyle.red, custom_id='rejectvc')
  async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.guild.get_role(753869940162953357) not in interaction.user.roles:
      await interaction.response.send_message("Only the server owners can accept/reject applications! You can of course give suggestions or opinions on the application!", ephemeral=True)
      raise Exception()
    user = interaction.guild.get_member(int(interaction.message.content.split("`")[1]))
    embed = discord.Embed(title="You are rejected! :pensive:", description="Thank you so much for applying for VC moderator. Unfortunately, we aren't able to accept you at this time. n\nDon't fret – you're always welcome to reapply in the future. In order to reapply, you'll have to wait 60 days from today. Applications sent from you during the waiting period will be ignored.\n\nWe're currently unable to provide any more detailed or specifics about the nature of your application. We really hope you're not too discouraged by the news, and remember; this decision in no way speaks to the value, joy, and belonging you bring to your community every day.\n\n*PS: You can always report inappropriate behaviours to us by creating a ticket!*", color=0xFF0000)
    await user.send(embed=embed)
    await interaction.message.edit(content=f":x: Applicant ID: `{user.id}`", view=None)
    await interaction.response.send_message(ephemeral=True)

class ApplyForVCMod(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(label='Start Application', style=discord.ButtonStyle.grey, custom_id='vcmodapp', emoji="🎙️")
  async def startapp(self, interaction: discord.Interaction, button: discord.ui.Button):
    lvl20 = interaction.guild.get_role(752874966919151666)
    lvl35 = interaction.guild.get_role(879629862627835954)
    lvl40 = interaction.guild.get_role(949336415563579522)
    lvl50 = interaction.guild.get_role(759223538779160608)
    lvl69 = interaction.guild.get_role(879629784718663750)
    lvl75 = interaction.guild.get_role(879629786455097344)
    lvl90 = interaction.guild.get_role(949339134273679420)
    lvl100 = interaction.guild.get_role(765485751680892958)
    requiredLevel = [lvl20, lvl35, lvl40, lvl50, lvl69, lvl75, lvl90, lvl100]
    if not (any(role in requiredLevel for role in interaction.user.roles) or interaction.guild.get_role(1058526486967095296) in interaction.user.roles):
      await interaction.response.send_message(":x: You are not qualified for the application! You have to be at least **level 20** or have the exclusive <@&1058526486967095296> role obtainable in <#1107010468440186970>.", ephemeral=True)
      raise Exception()
    else:
    # if True:
      duplicate = appliedVCMod
      if int(interaction.user.id) in duplicate:
        await interaction.response.send_message(":x: You have already applied for VC moderator previously. Please wait until the next moderator application is open!", ephemeral=True)
        raise Exception()
      await interaction.response.send_message(":envelope_with_arrow: Please proceed to your DMs to finish the application.", ephemeral=True)
      cancelNotice = "All answers will be kept confidential. Type \"cancel\" to stop the application."
      q1 = "Where do you live in? Specify continent and timezone wherever possible."
      q2 = "What is your age? "
      q3 = "How much time can you devote to using/moderating voice channels per week?"
      q4 = "Do you have any past moderation experiences in Discord servers (whether VC related or not)? If yes, please tell us about it."
      q5 = "If a user is spamming soundboard in a voice channel and would not stop even after verbal warnings, you will..."
      q6 = "Do you have any connection issues with using voice channels?"
      q7 = "Why should we choose you over other applicants? What qualities do you have that stand out?"
      q8 = "Are you familiar with the rules and regulations of Genshin Impact Cafe. Do you affirm that all information provided is accurate and genuine? Is there anything else you would like to add before submitting this application?"
      
      def check(message):
        if message.content.lower() == "cancel" and message.author == interaction.user and isinstance(message.channel, discord.DMChannel):
          raise Exception()
        return message.author == interaction.user and isinstance(message.channel, discord.DMChannel)
        
      embed = discord.Embed(title="Question #1", description=q1, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      username = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #2", description=q2, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      age = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #3", description=q3, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      where = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #4", description=q4, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      mod = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #5", description=q5, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      firstspam = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #6", description=q6, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      argue = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #7", description=q7, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      whymod = await interaction.client.wait_for('message', check=check)
  
      embed = discord.Embed(title="Question #8", description=q8, color=0xADD8E6)
      embed.set_footer(text=cancelNotice)
      await interaction.user.send(embed=embed)
      genshin = await interaction.client.wait_for('message', check=check)
      
      chn = interaction.client.get_channel(1083848942334246933)
      try:
        embed = discord.Embed(title="New Submitted VC Moderator Application", description=f"""
        From {interaction.user.mention}
        
        **{q1}**
        {username.content}
        
        **{q2}**
        {age.content}
        
        **{q3}**
        {where.content}
        
        **{q4}**
        {mod.content}
        
        **{q5}**
        {firstspam.content}
        
        **{q6}**
        {argue.content}
        
        **{q7}**
        {whymod.content}
        
        **{q8}**
        {genshin.content}
        
        """, color=0xFFFF00)
        await chn.send(f"Applicant ID: `{interaction.user.id}`",embed=embed,view=AcceptRejectButtonForVCMod())
    
        embed = discord.Embed(title="Application Submitted", description="All done! You will be notified shortly after our management team has finished reviewing your application! Thank you for applying, and stay tuned!", color=0x00FF00)
        await interaction.user.send(embed=embed)
        duplicate.append(int(interaction.user.id))
        f = open(f"./assets/appliedVCMod.py", "w")
        f.write(f"users = {duplicate}")
        f.close()
      except Exception:
        embed = discord.Embed(title="Sorry something went wrong :warning: ", description="This is likely due to the fact that your application is too long. Please make sure all of your responses **do not exceed a total of 3000 characters**. Trim your response and try again at <#1083848742312104026>.\n\nIf this issue persists, please contact our owner and bot developer <@692254240290242601>.", color=discord.Color.red())
        await interaction.user.send(embed=embed)
  

class VCMod(commands.Cog): 
  def __init__(self, bot):
    self.client = bot
  
  @commands.Cog.listener() 
  async def on_message(self, message):
    if message.author == self.client.user or message.author.bot == True: 
        return
    
    if message.guild.id == 717029019270381578 and message.content == "-vcmodapp":
      embed = discord.Embed(title="VC Moderator Application Details & Guidelines", description="<:Ganyu_smile:1026818142586028122> The **Voice Channel Moderator** is a dedicated position for trusted community members designed to assist staff members in **managing voice channels**. \n\n🔸 __**Here are the requirements for being a VC moderator:**__\n\n> **» Monitor voice channels and their chats for up to 5 hours per week <:Keqing_note:945209842975531008>**\n> **» Familiar with VC moderation tools like kick, deafen and mute <:Yanfei_Ban:999894648640245821>**\n> **» Be friendly and non-toxic <:DionaPat:999893451506196490>**\n\n:sparkles: *You have to be at least **level 20** or have the exclusive <@&1058526486967095296> role obtainable in <#1107010468440186970>.*\n\n🔹 If we believe you will meet the requirements and accepted you, you will be given the <@&1115161674194878575> role to start off. You may be promoted to a staff accordingly.", color=0xADD8E6)
      await message.channel.send(embed=embed, view=ApplyForVCMod())
      
      

async def setup(bot): 
  await bot.add_cog(VCMod(bot))