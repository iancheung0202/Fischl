import discord, firebase_admin, datetime, asyncio, time, emoji, pytz, genshin
from firebase_admin import db
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

timezones = ['America/Araguaina', 'America/Argentina/Buenos_Aires', 'America/Argentina/Catamarca', 'America/Argentina/Cordoba', 'America/Argentina/Jujuy', 'America/Argentina/La_Rioja', 'America/Argentina/Mendoza', 'America/Argentina/Rio_Gallegos', 'America/Argentina/Salta', 'America/Argentina/San_Juan', 'America/Argentina/San_Luis', 'America/Argentina/Tucuman', 'America/Argentina/Ushuaia', 'America/Asuncion', 'America/Bahia', 'America/Belem', 'America/Boa_Vista', 'America/Bogota', 'America/Campo_Grande', 'America/Caracas', 'America/Cayenne', 'America/Cuiaba', 'America/Eirunepe', 'America/Fortaleza', 'America/Guayaquil', 'America/Guyana', 'America/La_Paz', 'America/Lima', 'America/Maceio', 'America/Manaus', 'America/Montevideo', 'America/Noronha', 'America/Paramaribo', 'America/Porto_Velho', 'America/Punta_Arenas', 'America/Recife', 'America/Rio_Branco', 'America/Santarem', 'America/Santiago', 'America/Sao_Paulo', 'Antarctica/Palmer', 'Atlantic/South_Georgia', 'Atlantic/Stanley', 'Pacific/Easter', 'Pacific/Galapagos', 'America/Adak', 'America/Anchorage', 'America/Bahia_Banderas', 'America/Barbados', 'America/Belize', 'America/Boise', 'America/Cambridge_Bay', 'America/Cancun', 'America/Chicago', 'America/Chihuahua', 'America/Ciudad_Juarez', 'America/Costa_Rica', 'America/Dawson', 'America/Dawson_Creek', 'America/Denver', 'America/Detroit', 'America/Edmonton', 'America/El_Salvador', 'America/Fort_Nelson', 'America/Glace_Bay', 'America/Goose_Bay', 'America/Grand_Turk', 'America/Guatemala', 'America/Halifax', 'America/Havana', 'America/Hermosillo', 'America/Indiana/Indianapolis', 'America/Indiana/Knox', 'America/Indiana/Marengo', 'America/Indiana/Petersburg', 'America/Indiana/Tell_City', 'America/Indiana/Vevay', 'America/Indiana/Vincennes', 'America/Indiana/Winamac', 'America/Inuvik', 'America/Iqaluit', 'America/Jamaica', 'America/Juneau', 'America/Kentucky/Louisville', 'America/Kentucky/Monticello', 'America/Los_Angeles', 'America/Managua', 'America/Martinique', 'America/Matamoros', 'America/Mazatlan', 'America/Menominee', 'America/Merida', 'America/Metlakatla', 'America/Mexico_City', 'America/Miquelon', 'America/Moncton', 'America/Monterrey', 'America/New_York', 'America/Nome', 'America/North_Dakota/Beulah', 'America/North_Dakota/Center', 'America/North_Dakota/New_Salem', 'America/Ojinaga', 'America/Panama', 'America/Phoenix', 'America/Port-au-Prince', 'America/Puerto_Rico', 'America/Rankin_Inlet', 'America/Regina', 'America/Resolute', 'America/Santo_Domingo', 'America/Sitka', 'America/St_Johns', 'America/Swift_Current', 'America/Tegucigalpa', 'America/Tijuana', 'America/Toronto', 'America/Vancouver', 'America/Whitehorse', 'America/Winnipeg', 'America/Yakutat', 'Atlantic/Bermuda', 'Pacific/Honolulu', 'Africa/Ceuta', 'America/Danmarkshavn', 'America/Nuuk', 'America/Scoresbysund', 'Scoresbysund/Ittoqqortoormiit', 'America/Thule', 'Thule/Pituffik', 'Asia/Anadyr', 'Asia/Barnaul', 'Asia/Chita', 'Asia/Irkutsk', 'Asia/Kamchatka', 'Asia/Khandyga', 'Asia/Krasnoyarsk', 'Asia/Magadan', 'Asia/Novokuznetsk', 'Asia/Novosibirsk', 'Asia/Omsk', 'Asia/Sakhalin', 'Asia/Srednekolymsk', 'Asia/Tomsk', 'Asia/Ust-Nera', 'Asia/Vladivostok', 'Asia/Yakutsk', 'Asia/Yekaterinburg', 'Atlantic/Azores', 'Atlantic/Canary', 'Atlantic/Faroe', 'Atlantic/Madeira', 'Europe/Andorra', 'Europe/Astrakhan', 'Europe/Athens', 'Europe/Belgrade', 'Europe/Berlin', 'Europe/Brussels', 'Europe/Bucharest', 'Europe/Budapest', 'Europe/Chisinau', 'Europe/Dublin', 'Europe/Gibraltar', 'Europe/Helsinki', 'Europe/Istanbul', 'Europe/Kaliningrad', 'Europe/Kirov', 'Europe/Kyiv', 'Europe/Lisbon', 'Europe/London', 'Europe/Madrid', 'Europe/Malta', 'Europe/Minsk', 'Europe/Moscow', 'Europe/Paris', 'Europe/Prague', 'Europe/Riga', 'Europe/Rome', 'Europe/Samara', 'Europe/Saratov', 'Europe/Simferopol', 'Europe/Sofia', 'Europe/Tallinn', 'Europe/Tirane', 'Europe/Ulyanovsk', 'Europe/Vienna', 'Europe/Vilnius', 'Europe/Volgograd', 'Europe/Warsaw', 'Europe/Zurich', 'Antarctica/Macquarie', 'Australia/Adelaide', 'Australia/Brisbane', 'Australia/Broken_Hill', 'Australia/Darwin', 'Australia/Eucla', 'Australia/Hobart', 'Australia/Lindeman', 'Australia/Lord_Howe', 'Australia/Melbourne', 'Australia/Perth', 'Australia/Sydney', 'Pacific/Apia', 'Pacific/Auckland', 'Pacific/Bougainville', 'Pacific/Chatham', 'Pacific/Efate', 'Pacific/Fakaofo', 'Pacific/Fiji', 'Pacific/Gambier', 'Pacific/Guadalcanal', 'Pacific/Guam', 'Pacific/Kanton', 'Pacific/Kiritimati', 'Pacific/Kosrae', 'Pacific/Kwajalein', 'Pacific/Marquesas', 'Pacific/Nauru', 'Pacific/Niue', 'Pacific/Norfolk', 'Pacific/Noumea', 'Pacific/Pago_Pago', 'Pacific/Palau', 'Pacific/Pitcairn', 'Pacific/Port_Moresby', 'Pacific/Rarotonga', 'Pacific/Tahiti', 'Pacific/Tarawa', 'Pacific/Tongatapu', 'Asia/Almaty', 'Asia/Amman', 'Asia/Aqtau', 'Mangghystaū/Mankistau', 'Asia/Aqtobe', 'Aqtöbe/Aktobe', 'Asia/Ashgabat', 'Asia/Atyrau', "Atyraū/Atirau/Gur'yev", 'Asia/Baghdad', 'Asia/Baku', 'Asia/Bangkok', 'Asia/Beirut', 'Asia/Bishkek', 'Asia/Choibalsan', 'Asia/Colombo', 'Asia/Damascus', 'Asia/Dhaka', 'Asia/Dili', 'Asia/Dubai', 'Asia/Dushanbe', 'Asia/Famagusta', 'Asia/Gaza', 'Asia/Hebron', 'Asia/Ho_Chi_Minh', 'Asia/Hong_Kong', 'Asia/Hovd', 'Asia/Jakarta', 'Asia/Jayapura', 'New Guinea (West Papua / Irian Jaya), Malukus/Moluccas', 'Asia/Jerusalem', 'Asia/Kabul', 'Asia/Karachi', 'Asia/Kathmandu', 'Asia/Kolkata', 'Asia/Kuching', 'Asia/Macau', 'Asia/Makassar', 'Asia/Manila', 'Asia/Nicosia', 'Asia/Oral', 'Asia/Pontianak', 'Asia/Pyongyang', 'Asia/Qatar', 'Asia/Qostanay', 'Qostanay/Kostanay/Kustanay', 'Asia/Qyzylorda', 'Qyzylorda/Kyzylorda/Kzyl-Orda', 'Asia/Riyadh', 'Asia/Samarkand', 'Asia/Seoul', 'Asia/Shanghai', 'Asia/Singapore', 'Asia/Taipei', 'Asia/Tashkent', 'Asia/Tbilisi', 'Asia/Tehran', 'Asia/Thimphu', 'Asia/Tokyo', 'Asia/Ulaanbaatar', 'Asia/Urumqi', 'Asia/Yangon', 'Asia/Yerevan', 'Indian/Chagos', 'Indian/Maldives', 'Antarctica/Casey', 'Antarctica/Davis', 'Antarctica/Mawson', 'Antarctica/Rothera', 'Antarctica/Troll', 'Antarctica/Vostok', 'Africa/Abidjan', 'Africa/Algiers', 'Africa/Bissau', 'Africa/Cairo', 'Africa/Casablanca', 'Africa/El_Aaiun', 'Africa/Johannesburg', 'Africa/Juba', 'Africa/Khartoum', 'Africa/Lagos', 'Africa/Maputo', 'Africa/Monrovia', 'Africa/Nairobi', 'Africa/Ndjamena', 'Africa/Sao_Tome', 'Africa/Tripoli', 'Africa/Tunis', 'Africa/Windhoek', 'Atlantic/Cape_Verde', 'Indian/Mauritius']

months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

days = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']

characters = ['Albedo', 'Alhaitham', 'Aloy', 'Amber', 'Arlecchino', 'Ayaka', 'Ayato', 'Baizhu', 'Barbara', 'Beidou', 'Bennett', 'Candace', 'Charlotte', 'Chevreuse', 'Chiori', 'Chongyun', 'Collei', 'Cyno', 'Dehya', 'Diluc', 'Diona', 'Dori', 'Eula', 'Faruzan', 'Fischl', 'Freminet', 'Furina', 'Gaming', 'Ganyu', 'Gorou', 'Heizou', 'Hu Tao', 'Itto', 'Jean', 'Kaeya', 'Kaveh', 'Kazuha', 'Keqing', 'Kirara', 'Klee', 'Kokomi', 'Layla', 'Lisa', 'Lynette', 'Lyney', 'Mika', 'Mona', 'Nahida', 'Navia', 'Neuvillette', 'Nilou', 'Ningguang', 'Noelle', 'Qiqi', 'Raiden Shogun', 'Razor', 'Rosaria', 'Kujou Sara', 'Sayu', 'Shenhe', 'Shinobu', 'Sucrose', 'Tartaglia', 'Thoma', 'Tighnari', 'Venti', 'Wanderer', 'Wriothesley', 'Xiangling', 'Xianyun', 'Xiao', 'Xingqiu', 'Xinyan', 'Yae Miko', 'Yanfei', 'Yaoyao', 'Yelan', 'Yoimiya', 'Yun Jin', 'Zhongli']

def time_to_emoji(time_str):
    # Create a dictionary mapping time strings to emoji names
    time_to_emoji_map = {
        "00:00": ":clock12:", "00:30": ":clock1230:",
        "01:00": ":clock1:", "01:30": ":clock130:",
        "02:00": ":clock2:", "02:30": ":clock230:",
        "03:00": ":clock3:", "03:30": ":clock330:",
        "04:00": ":clock4:", "04:30": ":clock430:",
        "05:00": ":clock5:", "05:30": ":clock530:",
        "06:00": ":clock6:", "06:30": ":clock630:",
        "07:00": ":clock7:", "07:30": ":clock730:",
        "08:00": ":clock8:", "08:30": ":clock830:",
        "09:00": ":clock9:", "09:30": ":clock930:",
        "10:00": ":clock10:", "10:30": ":clock1030:",
        "11:00": ":clock11:", "11:30": ":clock1130:",
        "12:00": ":clock12:", "12:30": ":clock1230:",
        "13:00": ":clock1:", "13:30": ":clock130:",
        "14:00": ":clock2:", "14:30": ":clock230:",
        "15:00": ":clock3:", "15:30": ":clock330:",
        "16:00": ":clock4:", "16:30": ":clock430:",
        "17:00": ":clock5:", "17:30": ":clock530:",
        "18:00": ":clock6:", "18:30": ":clock630:",
        "19:00": ":clock7:", "19:30": ":clock730:",
        "20:00": ":clock8:", "20:30": ":clock830:",
        "21:00": ":clock9:", "21:30": ":clock930:",
        "22:00": ":clock10:", "22:30": ":clock1030:",
        "23:00": ":clock11:", "23:30": ":clock1130:"
    }
    
    # Return the corresponding emoji or None if not found
    return time_to_emoji_map.get(time_str)

async def char_name_to_icon(char_name):
    CHAR_NAME = char_name.replace(' ', '').capitalize() if ' ' not in char_name else char_name.split()[0] + char_name.split()[1].lower()
    return f"https://enka.network/ui/UI_AvatarIcon_{CHAR_NAME}.png"

async def timezone_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    if current == "":
      return [
        app_commands.Choice(name=timezones[x], value=timezones[x])
        for x in range(25)
      ]
    else:
      list = []
      for tz in timezones:
        if current.lower() in tz.lower():
          list.append(tz)
      list = list[:25]
      return [
        app_commands.Choice(name=x, value=x)
        for x in list
      ]

async def day_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    if current == "":
      return [
        app_commands.Choice(name=days[x], value=days[x])
        for x in range(25)
      ]
    else:
      list = []
      for day in days:
        if current.lower() in day.lower():
          list.append(day)
      list = list[:25]
      return [
        app_commands.Choice(name=x, value=x)
        for x in list
      ]

async def character_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    if current == "":
      return [
        app_commands.Choice(name=characters[x], value=characters[x])
        for x in range(25)
      ]
    else:
      list = []
      for char in characters:
        if current.lower() in char.lower():
          list.append(char)
      list = list[:25]
      return [
        app_commands.Choice(name=x, value=x)
        for x in list
      ]

@app_commands.guild_only()
class Birthday(commands.GroupCog, name="birthday"):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    super().__init__()

  @app_commands.command(
    name = "sync",
    description = "Sync data from Birthday Bot (Admin only)"
  )
  @app_commands.describe(
    file = "The TXT file exported from Birthday Bot"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def birthday_sync(
    self,
    interaction: discord.Interaction,
    file: discord.Attachment
  ) -> None:
    await interaction.response.defer()
    
    oldFile = open("./assets/BirthdayBotData.txt", "r")
    oldfileContent = oldFile.read()
    oldbirthdays = oldfileContent.split("●")
    oldbirthdays.pop(0)
    ids = []
    for obday in oldbirthdays:
      id = int(obday.split("-")[1].split(" ")[1])
      ids.append(id)
    
    await file.save("./assets/BirthdayBotData.txt")
    f = open("./assets/BirthdayBotData.txt", "r")
    fileContent = f.read()

    birthdays = fileContent.split("●")
    birthdays.pop(0)
    count = 0
    for bday in birthdays:
      x = bday.split("-")
      month = x[0].strip()
      month_map = {
        'Jan': 1,
        'Feb': 2,
        'Mar': 3,
        'Apr': 4,
        'May': 5,
        'Jun': 6,
        'Jul': 7,
        'Aug': 8,
        'Sep': 9,
        'Oct': 10,
        'Nov': 11,
        'Dec': 12
      }
      month = month_map.get(month, "Invalid abbr")
      if month == "Invalid abbr":
        continue
      day = int(x[1].split(":")[0].strip())
      id = int(x[1].split(" ")[1])
      if id in ids:
        #print("Existed in old file")
        continue
      if "Time zone:" in bday:
        timezone = bday.split("Time zone: ")[1].strip()
        if timezone == "GMT":
          timezone = "Atlantic/Azores"
      else:
        timezone = "Atlantic/Azores"
      
      birth_date = datetime.datetime(2024, month, day, 0, 0, 0)
      birth_timezone = pytz.timezone(timezone)
      localized_birth_date = birth_timezone.localize(birth_date)
      utc_birth_date = localized_birth_date.astimezone(pytz.utc)
      display_utc_date = utc_birth_date.strftime('%m-%d %H:%M')
        
      existed = False
      ref = db.reference("/Birthday")
      bday = ref.get()
      for key, value in bday.items():
        if (value["User ID"] == id):
          existed = True
          break
      
      if existed:
        #print("Existed in Database")
        continue

      data = {
        interaction.guild.name: {
            "User ID": id,
            "Month": month,
            "Day": day,
            "Timezone": timezone,
            "Display UTC Date": display_utc_date,
            "Fav Character": "None"
          }
      }

      for key, value in data.items():
        ref.push().set(value)
      count += 1
      print(id)
      print(month)
      print(day)
      print(timezone)
      print(display_utc_date)
      print("=================")
    await interaction.followup.send(f"Added **{count}** birthday records.")

  @app_commands.command(
    name = "set",
    description = "Set your birth date and timezone"
  )
  @app_commands.choices(month=[
      app_commands.Choice(name="January", value="1"),
      app_commands.Choice(name="February", value="2"),
      app_commands.Choice(name="March", value="3"),
      app_commands.Choice(name="April", value="4"),
      app_commands.Choice(name="May", value="5"),
      app_commands.Choice(name="June", value="6"),
      app_commands.Choice(name="July", value="7"),
      app_commands.Choice(name="August", value="8"),
      app_commands.Choice(name="September", value="9"),
      app_commands.Choice(name="October", value="10"),
      app_commands.Choice(name="November", value="11"),
      app_commands.Choice(name="December", value="12")
  ])
  @app_commands.autocomplete(day=day_autocomplete, timezone=timezone_autocomplete, character=character_autocomplete)
  @app_commands.describe(
    month = "The month of your birth date",
    day = "The day of your birth date",
    timezone = "The timezone of your birth location (go to https://arilyn.cc to find your timezone)",
    character = "Your favorite Genshin character who will wish you a happy birthday",
  )
  async def birthday_set(
    self,
    interaction: discord.Interaction,
    month: app_commands.Choice[str],
    day: str,
    timezone: str,
    character: str,
  ) -> None:
    monthName = month.name
    month = int(month.value)
    
    if timezone not in timezones:
      await interaction.response.send_message(embed=discord.Embed(description=":x: **Invalid timezone.** Please search and select from the menu or refer to https://arilyn.cc/.", color=0xFF0000), ephemeral=True)
      raise Exception("Invalid timezone")
    if monthName not in months:
      await interaction.response.send_message(embed=discord.Embed(description=":x: **Invalid month.** Please search and select from the menu.", color=0xFF0000), ephemeral=True)
      raise Exception("Invalid month")
    if day not in days:
      await interaction.response.send_message(embed=discord.Embed(description=":x: **Invalid day.** Please search and select from the menu.", color=0xFF0000), ephemeral=True)
      raise Exception("Invalid day")
    if character not in characters and character != "None":
      await interaction.response.send_message(embed=discord.Embed(description=":x: **Invalid character.** Please search and select from the menu.", color=0xFF0000), ephemeral=True)
      raise Exception("Invalid character")
        
    day = int(day)
    if (month == 2 and day > 29) or (month in [4, 6, 9, 11] and day > 30) or (month in [1, 3, 5, 7, 8, 10, 12] and day > 31):
      await interaction.response.send_message(embed=discord.Embed(description=":x: The date you specified is not a valid calendar date.", color=0xFF0000), ephemeral=True)
      raise Exception("Invalid calendar date")
    birth_date = datetime.datetime(2024, month, day, 0, 0, 0)
    birth_timezone = pytz.timezone(timezone)
    localized_birth_date = birth_timezone.localize(birth_date)
    utc_birth_date = localized_birth_date.astimezone(pytz.utc)
    display_utc_date = utc_birth_date.strftime('%m-%d %H:%M')
    
    ref = db.reference("/Birthday")
    bday = ref.get()
    for key, value in bday.items():
      if (value["User ID"] == interaction.user.id):
        db.reference('/Birthday').child(key).delete()
        break

    data = {
      interaction.guild.name: {
          "User ID": interaction.user.id,
          "Month": month,
          "Day": day,
          "Timezone": timezone,
          "Display UTC Date": display_utc_date,
          "Fav Character": character
        }
    }

    for key, value in data.items():
    	ref.push().set(value)
    
    embed=discord.Embed(title="✅ Birthday Saved", description=f":birthday: You have set your birthday to **{monthName} {day}** *({timezone})*. \n*<a:klee_note:949609277805436999> Your birthday in UTC time is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}*", color=0x04C607)
    icon_link = await char_name_to_icon(character)
    embed.set_thumbnail(url=icon_link)
    
    await interaction.response.send_message(embed=embed)
    
    
  @app_commands.command(
    name = "get",
    description = "Get the birthday of a member"
  )
  @app_commands.describe(
    user = "The member you wish to get the birthday of",
  )
  async def birthday_get(
    self,
    interaction: discord.Interaction,
    user: discord.Member = None
  ) -> None:
    if user is None:
      user = interaction.user
    
    ref = db.reference("/Birthday")
    bday = ref.get()
    month = day = timezone = display_utc_date = None
    for key, value in bday.items():
      if (value["User ID"] == user.id):
        month = value["Month"]
        day = value["Day"]
        timezone = value["Timezone"]
        display_utc_date = value["Display UTC Date"]
        character = value["Fav Character"]
        break

    if (month is None or day is None or timezone is None or display_utc_date is None):
      if user == interaction.user:
        embed=discord.Embed(description=f":x: We don't have your birthday in our database. Use </birthday set:1246958872502075463> to set your birthday!", color=0xFF0000)
      else:
        embed=discord.Embed(description=f":x: We don't have {user.mention}'s birthday in our database.", color=0xFF0000)
      await interaction.response.send_message(embed=embed, ephemeral=True)
      raise Exception("Member birthday not found")
    
    if user == interaction.user:
      embed=discord.Embed(description=f":birthday: Your birthday is **{months[month-1]} {day}** *({timezone})*.\n Your birthday in UTC time is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}", color=0xF1EE0C)
    else:
      embed=discord.Embed(description=f":birthday: {user.mention}'s birthday is **{months[month-1]} {day}** *({timezone})*.\n In UTC time, it is **{display_utc_date}** {time_to_emoji(display_utc_date.split(' ')[1])}", color=0xF1EE0C)
    icon_link = await char_name_to_icon(character)
    embed.set_thumbnail(url=icon_link)
    await interaction.response.send_message(embed=embed)
    
  @app_commands.command(
    name = "remove",
    description = "Remove your birthday from the database"
  )
  async def birthday_remove(
    self,
    interaction: discord.Interaction,
  ) -> None:
    found = False
    ref = db.reference("/Birthday")
    bday = ref.get()
    for key, value in bday.items():
      if (value["User ID"] == interaction.user.id):
        db.reference('/Birthday').child(key).delete()
        found = True
        break
    
    if not found:
      embed=discord.Embed(title="We could not find your birthday", description=f"Maybe you have already removed your birthday, or you have never set one in the first place. Anyways, no records found in our database.\n\n*What are you doing anyways, go **set your birthday** by using </birthday set:1246958872502075463>!*", color=0xCDCB20)
    else:
      embed=discord.Embed(title="Birthday Removed :pensive:", description=f"It's sad to see you go ~ your birthday is a very important milestone, and we want to celebrate it with you! Please consider changing your mind and **set your birthday** by using </birthday set:1246958872502075463>.", color=0xE35417)
    
    await interaction.response.send_message(embed=embed)
    
    
  @app_commands.command(
    name = "export",
    description = "Exports all birthdays (Admin only)"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def birthday_export(
    self,
    interaction: discord.Interaction,
  ) -> None:
    await interaction.response.defer()
    list = []
    ref = db.reference("/Birthday")
    bday = ref.get()
    for x in bday.items():
      list.append(x)
    data_items = list
    data_items_with_dates = []
    for key, value in data_items:
      try:
        date = datetime.datetime.strptime(value['Display UTC Date'], "%m-%d %H:%M")
        data_items_with_dates.append((key, value, date))
      except ValueError:
        print(f"Invalid date found: {value['Display UTC Date']} for key {key}")
    #data_items_with_dates = [(key, value, datetime.datetime.strptime(value['Display UTC Date'], "%m-%d %H:%M")) for key, value in data_items]
    sorted_data_items = sorted(data_items_with_dates, key=lambda x: x[2])
    sorted_data_items_final = [(key, value) for key, value, date in sorted_data_items]
    
    content = f"Birthdays in {interaction.guild.name}\n\n"
    for key, value in sorted_data_items_final:
      try:
        months_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        content = f"{content}● {months_short[value['Month']-1]}-{value['Day']} ({value['Timezone']}): {value['User ID']} {interaction.guild.get_member(value['User ID']).name} | {value['Display UTC Date']} | {value['Fav Character']}\n"
      except Exception:
        pass

    filename = "./assets/birthday_export.txt"
    with open(filename, "w") as file:
      file.write(content)

    await interaction.followup.send(file=discord.File(filename))
    
  
  @app_commands.command(
    name = "enable",
    description = "Enable birthday wishes in a channel"
  )
  @app_commands.describe(
    channel = "The channel to send birthday wishes in",
    role = "The role to given those who are celebrating their birthdays"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def birthday_enable(
    self,
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    role: discord.Role
  ) -> None:

    ref = db.reference("/Birthday System")
    bs = ref.get()
    
    try:
      for key, val in bs.items():
        if val['Server ID'] == interaction.guil.id:
          db.reference('/Birthday System').child(key).delete()
          break
    except Exception:
      pass
    
    webhook = await channel.create_webhook(name="Birthday Wishes", reason=f"Created by user ID: {interaction.user.id}")

    data = {
      channel.id: {
        "Channel ID": channel.id,
        "Webhook ID": webhook.id,
        "Server ID": interaction.guild.id,
        "Server Name": interaction.guild.name,
        "Role ID": role.id
      }
    }

    for key, value in data.items():
      ref.push().set(value)

    embed = discord.Embed(title="Birthday wishes enabled!", description=f'If a member in your server has set their birthday in this bot using </birthday set:1254927191129456640>, then I will wish them a happy birthday when the day comes in {channel.mention} and grant them the {role.mention} temporarily.', colour=0x00FF00)
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.response.send_message(embed=embed)
    

  @app_commands.command(
    name = "disable",
    description = "Disable birthday wishes in the server"
  )
  @app_commands.checks.has_permissions(administrator=True)
  async def birthday_disable(
    self,
    interaction: discord.Interaction,
  ) -> None:
    
    ref = db.reference("/Birthday System")
    bs = ref.get()

    found = False
    for key, val in bs.items():
      if val['Server ID'] == interaction.guild.id:
        db.reference('/Birthday System').child(key).delete()
        found = True
        break

    if found:
      embed = discord.Embed(title="Birthday Wishes disabled!", description=f'Sad to see you go. If you change your mind at anytime, you could use </birthday enable:1036382520033415196> to enable birthday wishes again.', colour=0xFF0000)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed)
    else:
      embed = discord.Embed(title="Birthday Wishes is not enabled!", description=f'What are you thinking? Birthday wishes are even enabled in this server in the first place. To enable the function, use </birthday enable:1036382520033415196>.', colour=0xFFFF00)
      embed.timestamp = datetime.datetime.utcnow()
      await interaction.response.send_message(embed=embed, ephemeral=True)
      
      

async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(Birthday(bot))