import discord
import firebase_admin
import platform
import psutil

from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from firebase_admin import db

BLANK = "<:blank:1036792889121980426>"
REPLY = "<:reply:1036792837821435976>"

class Select(discord.ui.Select):
    def __init__(self, list, initial_author):
        self.initial_author = initial_author
        self.list = list

        simple_formatter = lambda cmd: "".join(
            f"\n\n</{cmd.name} {sub.name}:{cmd.id}>\n{REPLY} {sub.description}"
            if sub.type == discord.AppCommandOptionType.subcommand
            else f"\n\n{BLANK}{REPLY} `{sub.name}` - {sub.description}"
            for sub in cmd.options
        )
        
        formatter = lambda cmd: "".join(
            f"\n\n</{cmd.name} {sub.name}:{cmd.id}>\n{REPLY} {sub.description}"
            + "".join(f"\n{BLANK}{REPLY} `{sub_cmd.name}` - {sub_cmd.description}" for sub_cmd in sub.options)
            if sub.type == discord.AppCommandOptionType.subcommand
            else f"\n\n{BLANK}{REPLY} `{sub.name}` - {sub.description}"
            for sub in cmd.options
        )
        
        utility_formatter = lambda cmd: (
            f" \n\n{cmd.mention}\n{REPLY} {cmd.description}"
            + "".join(
                f"\n</{cmd.name} {sub.name}:{cmd.id}>\n{REPLY} {sub.description}"
                + "".join(f"\n{BLANK}{REPLY} `{sub_cmd.name}` - {sub_cmd.description}" for sub_cmd in sub.options)
                if sub.type == discord.AppCommandOptionType.subcommand
                else f"\n{BLANK}{REPLY} `{sub.name}` - {sub.description}"
                for sub in cmd.options
            )
        )
        
        categories = {
            "ticket": {
                "title": "Tickets",
                "emoji": "🎫",
                "description": "The following slash commands are used to setup and deal with tickets. To start using tickets instantly, use </ticket settings:1254927191129456641> and the bot will guide you through the procedures of setting up your ticket system!",
                "condition": lambda cmd: "ticket" in cmd.name,
                "formatter": simple_formatter
            },
            "coop": {
                "title": "Co-op System",
                "emoji": "🎮",
                "description": "The following commands are used to setup co-op system in your server. Use </co-op setup:1254927191037317149> to starting setting up the co-op system, and the bot will guide you through the procedures!",
                "condition": lambda cmd: "co-op" in cmd.name,
                "formatter": formatter
            },
            "partner": {
                "title": "Partnership Panels",
                "emoji": "🤝",
                "description": "The following slash commands are for managing your server’s partnerships. When a user requests for partnership, a private thread is created, just like a ticket. Server representatives can be invited into the thread, and admins can easily add/remove partnered servers to the customizable and auto-updating partnership panels. Use </partner setup:1364761118324822128> to get started!",
                "condition": lambda cmd: "partner" in cmd.name,
                "formatter": simple_formatter
            },
            "sticky": {
                "title": "Sticky Messages",
                "emoji": "🫧",
                "description": "The following slash commands are for setting up sticky messages in different channels. Sticky messages will be stayed at the bottom of the channel no matter what messages are sent afterwards. This function is especially useful when you need give your members a heads up on how to use this chat channel or what they need to know before going ahead and sending any messages. Use </sticky enable:1254927190915551254> to setup sticky messages in a channel.",
                "condition": lambda cmd: "sticky" in cmd.name,
                "formatter": formatter
            },
            "welcome": {
                "title": "Welcomer",
                "emoji": "👋",
                "description": "The following slash commands are for setting up welcome messages in a server. If enabled, the bot will automatically greet new server members in a designated text channel. You can customize your own greetings to tailor to your server's needs. Use </welcome setup:1254927190915551255> to setup welcome messages.",
                "condition": lambda cmd: "welcome" in cmd.name,
                "formatter": formatter
            },
            "birthday": {
                "title": "Birthday Wishes",
                "emoji": "🎂",
                "description": "The following slash commands are for wishing users in your server a happy birthday. Member will receive personalized birthday wishes from their favorite characters in servers that have this system enabled. Use </birthday enable:1254927191129456640> to setup birthday wishes in the server.",
                "condition": lambda cmd: "birthday" in cmd.name,
                "formatter": formatter
            },
            "events": {
                "title": "Chat Minigames",
                "emoji": "🎉",
                "description": "The following slash commands are dedicated to random events that appear in a chat channel. Servers that have random events enabled will have exciting mini-games randomly spawned to the chat based on the chat activity and frequency you provided. Use </events settings:1339782470677299260> to setup and configure random chat events in the server.",
                "condition": lambda cmd: (
                    "customize" in cmd.name
                    or "mora" in cmd.name
                    or "lb" in cmd.name
                    or "buy" in cmd.name
                    or "shop" in cmd.name
                    or "milestones" in cmd.name
                    or "gift" in cmd.name
                    or "summon" in cmd.name
                    or "chest" in cmd.name
                    or "events" in cmd.name
                    or "preview" in cmd.name
                ),
                "formatter": lambda cmd: (
                    f" \n\n{cmd.mention}\n{REPLY} {cmd.description}"
                    if cmd.name in ["customize", "mora", "lb", "buy", "shop", "milestones", "gift", "summon", "chest", "preview"]
                    else formatter(cmd)
                )
            },
            "boosterrole": {
                "title": "Booster Roles",
                "emoji": "💎",
                "description": "The following slash commands are for rewarding your server boosters with customizable roles and thank-you messages. When a member boosts the server, the bot will automatically send a personalized thank-you message in a designated channel, and the booster can create a custom role. Use </boosterrole setup:1377127436247892080> to setup booster roles in your server.",
                "condition": lambda cmd: "boosterrole" in cmd.name,
                "formatter": formatter
            },
            "utility": {
                "title": "Utility Commands",
                "emoji": "🛠️",
                "description": "The following slash commands are used for basic functions that many bots offer. These commands are accessible to everyone in the server.",
                "condition": lambda cmd: (
                    "reload" not in cmd.name
                    and "update_rewards" not in cmd.name
                    and "send-leaderboard" not in cmd.name
                    and "Edit Embed" not in cmd.name
                    and "emotes" not in cmd.name
                    and "layout" not in cmd.name
                ),
                "formatter": utility_formatter
            },
            "vanity": {
                "title": "Vanity/Tag Roles",
                "emoji": "👤",
                "description": "We also offer features for vanity roles and tag roles. If enabled, the bot will reward your members with an exclusive role for advertising your server in their status *or* for equipping your server tag.",
                "condition": lambda cmd: False,  # Static entry
                "formatter": lambda cmd: ""
            },
        }

        content = {cat: "" for cat in categories}
        for command in self.list:
            for cat_name, cat_info in categories.items():
                if cat_info["condition"](command):
                    content[cat_name] += cat_info["formatter"](command)
                    break

        content["vanity"] = "-# <:LuckySad:1344057325341642862> We’d like to inform you that the vanity feature will **no longer be available through the main Fischl bot** due to the requirement for special Discord intents. Fortunately, this functionality has been moved to a separate bot.\n\n> **To use these awesome features, kindly invite our extension bot using [this link](https://discord.com/oauth2/authorize?client_id=1033190899229929542&permissions=8&integration_type=0&scope=bot+applications.commands)**. <:PinkCelebrate:1204614140044386314>\n\n*After inviting the bot, you can use `/vanity enable` or `/tag enable` to setup the system(s)!*"

        self.lyst = [
            [content[cat], categories[cat]["title"], categories[cat]["emoji"], categories[cat]["description"]]
            for cat in categories
        ]

        options = [discord.SelectOption(label=item[1], emoji=item[2]) for item in self.lyst]

        super().__init__(
            placeholder="Browse All Commands",
            max_values=1,
            min_values=1,
            options=options,
            custom_id="browsecommands",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.initial_author != interaction.user:
            await interaction.response.send_message("<:no:1036810470860013639> You are not the author of this command", ephemeral=True)
            return
        for item in self.lyst:
            if self.values[0] == item[1]:
                intro = discord.Embed(title=f"{item[2]} {item[1]}", description=item[3], color=0xFFFF00)
                embed = discord.Embed(description=item[0], color=discord.Color.blurple())
                await interaction.response.edit_message(embeds=[intro, embed], view=HelpPanel(self.list, self.initial_author))
                break


class HelpPanel(discord.ui.View):
    def __init__(self, list=None, initial_author=None):
        self.list = list
        self.initial_author = initial_author
        super().__init__(timeout=300)
        inviteButton = Button(
            label="Invite Bot",
            style=discord.ButtonStyle.link,
            url="https://discord.com/api/oauth2/authorize?client_id=732422232273584198",
            row=1,
            emoji="<a:robot:1366940845697400935>"
        )
        self.add_item(inviteButton)
        serverButton = Button(
            label="Support Server",
            style=discord.ButtonStyle.link,
            url="https://discord.gg/kaycd3fxHh",
            row=1,
            emoji="<a:join:1366940843088543775>"
        )
        self.add_item(serverButton)
        websiteButton = Button(
            label="Website",
            style=discord.ButtonStyle.link,
            url="https://fischl.app/",
            row=1,
            emoji="<a:globe:1366940841829994557>"
        )
        self.add_item(websiteButton)
        self.add_item(Select(self.list, self.initial_author))
        
    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, Button) and child.style == discord.ButtonStyle.link:
                continue
            child.disabled = True
            if isinstance(child, Select):
                child.add_option(label="Disabled due to timeout", value="X", emoji="<:no:1036810470860013639>", default=True)
                
        if hasattr(self, 'message'):
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
        self.stop()


    @discord.ui.button(
        label="Overview", style=discord.ButtonStyle.blurple, custom_id="overview", row=0, emoji="<a:memo:1366940844300701714>"
    )
    async def overview(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.initial_author != interaction.user:
            await interaction.response.send_message("<:no:1036810470860013639> You are not the author of this command", ephemeral=True)
            return
        embed = discord.Embed(
            title="Fischl Help",
            description=f"> <a:hoyoverse:1366950037728530472> Fischl is a powerful utility Discord bot **designed with all Hoyoverse communities in mind**. Trusted by numerous large servers, Fischl makes server management effortless with **easy-to-use systems** for *tickets, co-op matchmaking, partnerships, welcomes, birthdays, and fun minigames*. <:HuTaoWow:1253167030748840067>",
            color=0x1DBCEB,
        )
        embed.add_field(
            name="<:genshin_impact:1103720959950725190> Support Server",
            value=f"Head over to our **[support server](https://discord.gg/kaycd3fxHh)** if you have any suggestions, questions or bug reports! :writing_hand:",
            inline=True,
        )
        embed.add_field(
            name="<:slash:1037445915348324505> Command Usage",
            value=f"This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` or **select a category** below to see the list of available bot commands.",
            inline=True,
        )

        await interaction.response.edit_message(
            embed=embed, view=HelpPanel(self.list, self.initial_author)
        )

    @discord.ui.button(
        label="Statistics",
        style=discord.ButtonStyle.blurple,
        custom_id="statistics",
        row=0,
        emoji="<a:server:1366940847093841961>"
    )
    async def statistics(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.initial_author != interaction.user:
            await interaction.response.send_message("<:no:1036810470860013639> You are not the author of this command", ephemeral=True)
            return
        embed = discord.Embed(title="Fischl Discord Bot Statistics <a:server:1366940847093841961>", color=0x1DBCEB)
        mem_usage = psutil.virtual_memory()
        embed.add_field(
            name="<:info:1037445870469267638> Package Info",
            value=(
                f"```OS - {platform.system()}\n"
                f"Python - {platform.python_version()}\n"
                f"discord.py - {discord.__version__}\n"
                f"Google Firebase - {firebase_admin.__version__}```"
            ),
            inline=False,
        )
        ref = db.reference("/Uptime")
        status = ref.get()
        for key, value in status.items():
            uptime = value["Uptime"]
            break
        embed.add_field(
            name="<:dev:1037445830749204624>  Bot Metadata",
            value=(
                f"> App ID: `{interaction.client.application_id}`"
                f"\n> Last Reboot: <t:{uptime}:R>"
                f"\n> Servers Count: `{len(interaction.client.guilds)}`"
                f"\n> API/Bot Latency: `{int(round(interaction.client.latency * 1000, 1))}ms`"
            ),
            inline=True,
        )
        embed.add_field(
            name="📊  Bot Process Data",
            value=(
                f"> CPU Usage: `{psutil.cpu_percent(0.1)}%`"
                f"\n> RAM Usage: `{psutil.virtual_memory()[3]/1000000000:.2f} GB`"
                f"\n> Memory:  `{mem_usage.used/(1024**3):.2f}/{mem_usage.total/(1024**3):.2f} GB ({(mem_usage.percent):.2f}%)`"
            ),
            inline=True,
        )

        await interaction.response.edit_message(embed=embed, view=HelpPanel(self.list, self.initial_author))

    @discord.ui.button(
        label="View Server Configuration",
        style=discord.ButtonStyle.blurple,
        custom_id="serverconfig",
        row=0,
        emoji="<a:config:1366940834628505650>"
    )
    async def tutorial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.initial_author != interaction.user:
            await interaction.response.send_message("<:no:1036810470860013639> You are not the author of this command", ephemeral=True)
            return
        embed = discord.Embed(
            title="Server Configuration <a:config:1366940834628505650>",
            description=f"You could view the server settings of the bot in this page instantly. The configuration for **{interaction.guild.name}** is as follows:",
            color=0x1DBCEB,
        )

        ################
        
        await interaction.response.send_message("<a:loading:1026905298088243240>  Loading Server Configuration", ephemeral=True)

        ref = db.reference("/Tickets")
        tickets = ref.get()
        found = False
        for key, value in tickets.items():
            if value["Server ID"] == interaction.guild.id:
                CATEGORY_ID = value["Category ID"]
                LOGCHANNEL_ID = value["Log Channel ID"]
                found = True
                break

        if not found:
            embed.add_field(
                name="Ticket System",
                value="<:no:1036810470860013639> Disabled",
                inline=True,
            )
        else:
            embed.add_field(
                name="Ticket System",
                value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Category:** <#{CATEGORY_ID}>\n<:reply:1036792837821435976> **Log Channel:** <#{LOGCHANNEL_ID}>",
                inline=True,
            )

        ################

        ref = db.reference("/Co-Op")
        coop = ref.get()
        found = False
        for key, value in coop.items():
            if value["Server ID"] == interaction.guild.id:
                CO_OP_CHANNEL_ID = value["Co-op Channel ID"]
                NA_HELPER_ROLE_ID = value["NA Helper Role ID"]
                EU_HELPER_ROLE_ID = value["EU Helper Role ID"]
                ASIA_HELPER_ROLE_ID = value["Asia Helper Role ID"]
                SAR_HELPER_ROLE_ID = value["SAR Helper Role ID"]
                found = True
                break

        if not found:
            embed.add_field(
                name="Co-op System",
                value="<:no:1036810470860013639> Disabled",
                inline=True,
            )
        else:
            embed.add_field(
                name="Co-op System",
                value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Co-op Channel:** <#{CO_OP_CHANNEL_ID}>\n<:reply:1036792837821435976> **NA Helper Role:** <@&{NA_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **EU Helper Role:** <@&{EU_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **Asia Helper Role:** <@&{ASIA_HELPER_ROLE_ID}>\n<:reply:1036792837821435976> **SAR Helper Role:** <@&{SAR_HELPER_ROLE_ID}>",
                inline=True,
            )

        ################

        ref = db.reference("/Birthday System")
        bs = ref.get()
        found = False
        for key, value in bs.items():
            if value["Server ID"] == interaction.guild.id:
                CHANNEL_ID = value["Channel ID"]
                ROLE_ID = value["Role ID"]
                found = True
                break

        if not found:
            embed.add_field(
                name="Birthday Wishes",
                value="<:no:1036810470860013639> Disabled",
                inline=True,
            )
        else:
            embed.add_field(
                name="Birthday Wishes",
                value=f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Channel:** <#{CHANNEL_ID}>\n<:reply:1036792837821435976> **Birthday Role:** <@&{ROLE_ID}>",
                inline=True,
            )

        ################

        ref = db.reference("/Sticky Messages")
        stickies = ref.get()

        found = False
        stickiedchannels = []
        for channel in interaction.guild.text_channels:
            for key, val in stickies.items():
                if val["Channel ID"] == channel.id:
                    stickiedchannels.append(channel.id)
                    found = True
        for channel in interaction.guild.threads:
            for key, val in stickies.items():
                if val["Channel ID"] == channel.id:
                    stickiedchannels.append(channel.id)
                    found = True

        if not found:
            embed.add_field(
                name="Sticky Messages",
                value="<:no:1036810470860013639> Disabled",
                inline=True,
            )
        else:
            x = "<:yes:1036811164891480194> Enabled\n"
            for chn in stickiedchannels:
                x = f"{x}<:reply:1036792837821435976> <#{chn}>\n"
            embed.add_field(name="Sticky Messages", value=x, inline=True)

        ################

        ref = db.reference("/Global Events System")
        event = ref.get()

        found = False
        eventchannels = []
        for channel in interaction.guild.text_channels:
            for key, val in event.items():
                if val["Channel ID"] == channel.id:
                    eventchannels.append(channel.id)
                    found = True
        for channel in interaction.guild.threads:
            for key, val in event.items():
                if val["Channel ID"] == channel.id:
                    eventchannels.append(channel.id)
                    found = True

        if not found:
            embed.add_field(
                name="Chat Minigames",
                value="<:no:1036810470860013639> Disabled",
                inline=True,
            )
        else:
            max_length = 1024 - 16
            x = "<:yes:1036811164891480194> Enabled\n"
            extra = 0
            for chn in eventchannels:
                channel_str = f"<:reply:1036792837821435976> <#{chn}>\n"
                if len(x) + len(channel_str) > max_length:
                    extra += 1
                else:
                    x += channel_str
            if extra > 0:
                x += f"... *({extra} more)*"
            embed.add_field(name="Chat Minigames", value=x, inline=True)

        ################

        ref = db.reference("/Welcome")
        welcome = ref.get()

        found = False

        for key, val in welcome.items():
            if val["Server ID"] == interaction.guild.id:
                welcomeChannel = val["Welcome Channel ID"]
                welcomeImageEnabled = val["Welcome Image Enabled"]
                found = True
                break

        if not found:
            embed.add_field(
                name="Welcome Messages",
                value="<:no:1036810470860013639> Disabled",
                inline=True,
            )
        else:
            x = f"<:yes:1036811164891480194> Enabled\n<:reply:1036792837821435976> **Welcome Channel:** <#{welcomeChannel}>\n"
            if welcomeImageEnabled:
                x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** `Uploaded`\n"
            else:
                x = f"{x}<:reply:1036792837821435976> **Custom Image Background:** `Not uploaded`\n"
            embed.add_field(name="Welcome Messages", value=x, inline=True)
        
        ################
        
        ref = db.reference(f"/Partner/config/{interaction.guild.id}")
        config = ref.get()
        if config:
            request_channel = config.get('request_channel')
            panel_channel = config.get('panel_channel')
            log_channel = config.get('log_channel')
            partner_role = config.get('partner_role')
            
            value = f"<:yes:1036811164891480194> Enabled\n"
            value += f"<:reply:1036792837821435976> **Request Channel:** <#{request_channel}>\n"
            value += f"<:reply:1036792837821435976> **Panel Channel:** <#{panel_channel}>\n"
            value += f"<:reply:1036792837821435976> **Log Channel:** <#{log_channel}>\n"
            value += f"<:reply:1036792837821435976> **Partner Role:** <@&{partner_role}>"
        else:
            value = "<:no:1036810470860013639> Disabled"
        embed.add_field(name="Partnership System", value=value, inline=True)

        ################
        
        ref = db.reference(f"Booster Role/{interaction.guild.id}")
        config = ref.get()
        if config and "base_role" in config:
            base_role = config.get('base_role')
            system_channel = config.get('system_channel')
            public_channel = config.get('channel')
            log_channel = config.get('log')
            
            value = f"<:yes:1036811164891480194> Enabled\n"
            value += f"<:reply:1036792837821435976> **Base Role:** <@&{base_role}>\n"
            value += f"<:reply:1036792837821435976> **System Channel:** <#{system_channel}>\n"
            value += f"<:reply:1036792837821435976> **Public Channel:** <#{public_channel}>\n"
            value += f"<:reply:1036792837821435976> **Log Channel:** <#{log_channel}>"
        else:
            value = "<:no:1036810470860013639> Disabled"
        embed.add_field(name="Booster Roles", value=value, inline=True)

        await interaction.message.edit(
            content=None, embed=embed, view=HelpPanel(self.list, self.initial_author)
        )
        await interaction.edit_original_response(content="<:yes:1036811164891480194> Loaded Server Configuration")


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="View all the bot's commands")
    @app_commands.guild_only()
    async def help(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        list = await self.bot.tree.fetch_commands()

        embed = discord.Embed(
            title="Fischl Help",
            description=f"> <a:hoyoverse:1366950037728530472> Fischl is a powerful utility Discord bot **designed with all Hoyoverse communities in mind**. Trusted by numerous large servers, Fischl makes server management effortless with **easy-to-use systems** for *tickets, co-op matchmaking, partnerships, welcomes, birthdays, and fun minigames*. <:HuTaoWow:1253167030748840067>",
            color=0x1DBCEB,
        )
        embed.add_field(
            name="<:genshin_impact:1103720959950725190> Support Server",
            value=f"Head over to our **[support server](https://discord.gg/kaycd3fxHh)** if you have any suggestions, questions or bug reports! :writing_hand:",
            inline=True,
        )
        embed.add_field(
            name="<:slash:1037445915348324505> Command Usage",
            value=f"This bot uses [slash commands](https://discord.com/blog/welcome-to-the-new-era-of-discord-apps). Type `/` or **select a category** below to see the list of available bot commands.",
            inline=True,
        )

        view = HelpPanel(list, interaction.user)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
