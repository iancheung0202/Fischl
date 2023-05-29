import discord, os, firebase_admin, datetime, time, asyncio
from discord.ext import commands
from firebase_admin import credentials, db
from keepOnline import keepOnline
from commands.Tickets.tickets import CloseTicketButton, TicketAdminButtons, ConfirmCloseTicketButtons, CreateTicketButtonView
from commands.Tickets.tickets import SelectView as ticketselection
from commands.Help.help import HelpPanel
from partnership.partnership import PartnerView, PartnershipView, ConfirmView, SelectView
from partnership.nopingpartnership import PartnerView as pv
from partnership.nopingpartnership import PartnershipView as prv
from partnership.nopingpartnership import ConfirmView as cv
from partnership.nopingpartnership import SelectView as sv
from replit import db as replit_db
from commands.CafeOnly.staff import ApplyForStaff, AcceptRejectButton
from commands.CafeOnly.team import TeamSelectionButtons, JanTeamChallenge
from commands.onMemberJoin import WelcomeBtnView

cred = credentials.Certificate("./assets/fischl-beta-firebase-adminsdk-pir1k-798a85c249.json")
# fischl-beta-firebase-adminsdk-pir1k-798a85c249
# fischl-backup-firebase-adminsdk-wq5ya-e31d81e586
default_app = firebase_admin.initialize_app(cred, {
	'databaseURL':"https://fischl-beta-default-rtdb.firebaseio.com"
})
      
class Fischl(commands.Bot):

  def __init__(self):
    super().__init__(
      command_prefix = "-",
      intents = discord.Intents.all(),
      application_id = 732422232273584198,
      help_command=None
    )

  async def setup_hook(self):
    for path, subdirs, files in os.walk('commands'):
      for name in files:
        if name.endswith('.py'):
          extension = os.path.join(path, name).replace("/", ".")[:-3]
          await self.load_extension(extension)
          print(f"Loaded {extension}")
    await bot.tree.sync()
    
    self.add_view(CloseTicketButton())
    self.add_view(TicketAdminButtons())
    self.add_view(ConfirmCloseTicketButtons())
    self.add_view(CreateTicketButtonView())
    self.add_view(ticketselection())
    list = await bot.tree.fetch_commands()
    self.add_view(HelpPanel(list))
    self.add_view(PartnerView())
    self.add_view(PartnershipView())
    self.add_view(ConfirmView())
    self.add_view(SelectView())
    self.add_view(pv())
    self.add_view(prv())
    self.add_view(cv())
    self.add_view(sv())
    self.add_view(ApplyForStaff())
    self.add_view(AcceptRejectButton())
    self.add_view(TeamSelectionButtons())
    self.add_view(JanTeamChallenge())
    self.add_view(WelcomeBtnView())

  async def status_task(self):
    timeout = 5
    while True:
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.playing, name="Genshin Impact"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name=f"over {len(self.users)} users"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="discord.gg/traveler"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name=f"{len(self.guilds)} guilds"))
      await asyncio.sleep(timeout)

  async def on_ready(self):
    print(f'{self.user} has connected to Discord!')
    self.loop.create_task(self.status_task())
    replit_db["ready_time"] = int(float(time.mktime(datetime.datetime.now().timetuple())))
    chn = self.get_channel(1036314355169513482)
    embed = discord.Embed(title="✅ Bot Online", description=f"**Date:** <t:{replit_db['ready_time']}:D>\n**Time:** <t:{replit_db['ready_time']}:t>\n\n**Servers in:** {len(self.guilds)}\n**Discord Version:** {discord.__version__}", colour=0x7BE81B)
    embed.timestamp = datetime.datetime.utcnow()
    await chn.send(embed=embed)

keepOnline()
bot = Fischl()

# try:
#   bot.run(os.environ['TOKEN']) 
# except Exception:
#    os.system("kill 1")
bot.run(os.environ['TOKEN']) 