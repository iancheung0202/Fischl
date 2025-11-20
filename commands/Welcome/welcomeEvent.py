import discord
import aiohttp

from discord.ext import commands
from firebase_admin import db
from commands.Welcome.createWelcomeMsg import createWelcomeMsg, script

class OnWelcomeMemberJoin(commands.Cog): 
    def __init__(self, bot):
        self.client = bot
  
    @commands.Cog.listener() 
    async def on_member_join(self, member):
        ref = db.reference(f"/WelcomeV2/{member.guild.id}")
        welcome_data = ref.get()
        
        if welcome_data:
            # New system
            await self.handle_new_welcome(member, welcome_data)
        else:
            # Legacy system
            await self.handle_legacy_welcome(member)
    
    async def handle_new_welcome(self, member, welcome_data):
        editor_data = welcome_data
        channel_id = editor_data.get('channel_id')
        welcome_image_enabled = editor_data.get('welcome_image_enabled', False)
        
        if not channel_id:
            return
        
        channel = self.client.get_channel(channel_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title=script(editor_data['embed']['title'], member, member.guild) if editor_data['embed']['title'] else None,
            description=script(editor_data['embed']['description'], member, member.guild) if editor_data['embed']['description'] else None,
            color=editor_data['embed']['color']
        )
        
        if editor_data['embed']['footer']['text']:
            embed.set_footer(
                text=script(editor_data['embed']['footer']['text'], member, member.guild),
                icon_url=editor_data['embed']['footer']['icon_url'] or None
            )
        
        if editor_data['embed']['author']['name']:
            embed.set_author(
                name=script(editor_data['embed']['author']['name'], member, member.guild),
                icon_url=editor_data['embed']['author']['icon_url'] or None
            )
        
        if editor_data['embed']['thumbnail']:
            embed.set_thumbnail(url=editor_data['embed']['thumbnail'])
        
        if welcome_image_enabled:
            filename = await createWelcomeMsg(member, bg=f"./assets/Welcome Image Background/{member.guild.id}.png")
            chn = self.client.get_channel(1026904121237831700)
            msg = await chn.send(f"**Guild Name:** {member.guild}", file=discord.File(filename))
            url = msg.attachments[0].proxy_url 
            embed.set_image(url=url)
        elif editor_data['embed']['image']:
            embed.set_image(url=editor_data['embed']['image'])
        
        for field in editor_data['embed'].get('fields', []):
            embed.add_field(
                name=script(field['name'], member, member.guild),
                value=script(field['value'], member, member.guild),
                inline=field['inline']
            )
        
        if editor_data['embed']['timestamp']:
            embed.timestamp = discord.utils.utcnow()
        
        view = discord.ui.View()
        for link in editor_data.get('button_links', []):
            try:
                emoji = discord.PartialEmoji.from_str(link["emoji"]) if link["emoji"] else None
            except:
                emoji = None
            button = discord.ui.Button(
                label=script(link["label"], member, member.guild),
                url=script(link["url"], member, member.guild),
                emoji=emoji,
                style=discord.ButtonStyle.link
            )
            view.add_item(button)
        
        message_content = script(editor_data.get('message_content', ''), member, member.guild)
        await channel.send(
            content=message_content or None,
            embed=embed,
            view=view if editor_data.get('button_links') else None
        )
    
    async def handle_legacy_welcome(self, member):
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