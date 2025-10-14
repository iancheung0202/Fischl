import discord
import datetime
import os

from discord import app_commands
from discord.ext import commands
from firebase_admin import db
from PIL import Image, ImageEnhance, ImageSequence
from discord.ui import View

MORA_EMOTE = "<:MORA:1364030973611610205>"

letter_emojis = [
    "🇦",
    "🇧",
    "🇨",
    "🇩",
    "🇪",
    "🇫",
    "🇬",
    "🇭",
    "🇮",
    "🇯",
    "🇰",
    "🇱",
    "🇲",
    "🇳",
    "🇴",
    "🇵",
    "🇶",
    "🇷",
    "🇸",
    "🇹",
    "🇺",
    "🇻",
    "🇼",
    "🇽",
]
letterList = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
]
letterString = "".join(letterList)

minigame_titles = [
    "Boss Battle Blitz",
    "Quicktype Racer",
    "Egg Walk",
    "Match The Profile Picture",
    "Split or Steal",
    "Reverse Number Quicktype",
    "Pick Up Ice Cream",
    "Snatch The Watermelon",
    "Guess The Mystery Number",
    "Memory Game",
    "Who Said That",
    "Unscramble Words",
    "Two Truths, One Lie",
    "Currency Counting",
    "Rock Paper Scissors Duel",
    "Roll A Dice",
    "Teyvat Voiceline Quiz",
    "Teyvat Emoji Riddles",
    "Galaxy Emoji Riddles",
    "Double or Keep",
    "Know Your Members",
    "Hangman",
    "Mora Auction House",
    ":new: Mora Heist"
]


class ToggleEventModal(discord.ui.Modal, title="Toggling Event"):

    letter = discord.ui.TextInput(
        label="The corresponding letter(s)",
        style=discord.TextStyle.short,
        placeholder="Type letters consecutively to toggle multiple games (no spaces please)",
        max_length=26,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # await interaction.response.defer()
        channelID = int(str(self.title).split(":")[1].replace(")", "").strip())
        ref = db.reference("/Global Events System")
        stickies = ref.get()
        originalList = None
        try:
            for key, val in stickies.items():
                if val["Channel ID"] == channelID:
                    originalList = val.get("Events", [])
                    frequency = val["Frequency"]
                    break
        except Exception as e:
            print(e)

        for letter in list(str(self.letter)):
            self.toggleLetter = str(letter).upper()

            if self.toggleLetter in letterList and originalList is not None:
                if self.toggleLetter in originalList:
                    originalList.remove(self.toggleLetter)
                else:
                    originalList.append(self.toggleLetter)
                error = False
            else:
                error = True
                break

        if not (error):
            for key, val in stickies.items():
                if val["Channel ID"] == channelID:
                    db.reference("/Global Events System").child(key).delete()
                    break

            data = {
                channelID: {
                    "Channel ID": channelID,
                    "Frequency": frequency,
                    "Events": originalList,
                }
            }
            for key, value in data.items():
                ref.push().set(value)

            string = "\n> ".join(
                [
                    f"{emoji} - {title} <:yes:1036811164891480194>"
                    if self.toggleLetter in originalList
                    else f"{emoji} - {title} <:no:1036810470860013639>"
                    for self.toggleLetter, emoji, title in zip(
                        letterString, letter_emojis, minigame_titles
                    )
                ]
            )

            self.embed = discord.Embed(
                title="Customize which mini-games you'd like to enable",
                description=f"**Channel:** <#{channelID}>\n\n > {string}\n\nClick the button below and type in the **corresponding letter(s)** (i.e. `h` or `abdfm`) to **toggle** the mini-game(s). *To edit the frequency, use </events enable:1339782470677299260> again.*",
                color=discord.Color.blurple(),
            )
            self.update = discord.Embed(
                description=f"Toggle successful :slight_smile:",
                color=discord.Color.green(),
            )
        else:
            self.embed = None
            self.update = discord.Embed(
                description=f"Invalid input. Please try again.",
                color=discord.Color.red(),
            )

        self.on_submit_interaction = interaction
        self.stop()


class ToggleEventButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Event", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        channelID = (
            interaction.message.embeds[0]
            .description.split("<#")[1]
            .split(">")[0]
            .strip()
        )

        toggleEventModal = ToggleEventModal(title=f"Toggle Event (ID: {channelID})")
        await interaction.response.send_modal(toggleEventModal)
        response = await toggleEventModal.wait()

        if toggleEventModal.embed is not None:
            await interaction.edit_original_response(embed=toggleEventModal.embed)
        await toggleEventModal.on_submit_interaction.response.send_message(
            embed=toggleEventModal.update, ephemeral=True
        )


@app_commands.guild_only()
class EventSystem(commands.GroupCog, name="events"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="enable", description="Enable random events in a channel"
    )
    @app_commands.describe(
        frequency="How often you'd like the random events to appear",
        channel="The channel to enable random events in (Current channel if not provided)",
    )
    @app_commands.choices(
        frequency=[
            app_commands.Choice(name="Very Frequent (~10%)", value="10"),
            app_commands.Choice(name="Frequent (~5%)", value="20"),
            app_commands.Choice(name="Occasional (~3%)", value="30"),
            app_commands.Choice(name="Uncommon (~2%)", value="50"),
            app_commands.Choice(name="Rare (~1%)", value="100"),
            app_commands.Choice(name="Very Rare (~0.5%)", value="200"),
        ]
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def events_enable(
        self,
        interaction: discord.Interaction,
        frequency: app_commands.Choice[str],
        channel: discord.TextChannel = None,
    ) -> None:
        if channel is None:
            channel = interaction.channel

        ref = db.reference("/Global Events System")
        stickies = ref.get()

        originalList = letterList
        try:
            for key, val in stickies.items():
                if val["Channel ID"] == channel.id:
                    originalList = val["Events"]
                    db.reference("/Global Events System").child(key).delete()
                    break
        except Exception:
            pass

        data = {
            channel.id: {
                "Channel ID": channel.id,
                "Frequency": int(frequency.value),
                "Events": originalList,
            }
        }

        for key, value in data.items():
            ref.push().set(value)

        embed = discord.Embed(
            title="All random events enabled!",
            description=f"Now, there will be a **{100//(int(frequency.value))}%** chance for every message sent in {channel.mention} to trigger a random event! \n\n***Tip:** You can use `/events settings` to blacklist/whitelist the events you want to appear!*",
            colour=0x00FF00,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        with open("./commands/Events/enabledChannels.py", "r") as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("enabledChannels ="):
                existing_dict = eval(line.split("=", 1)[1].strip())
                existing_dict[channel.id] = int(frequency.value)
                lines[i] = f"enabledChannels = {existing_dict}\n"
                break

        with open("./commands/Events/enabledChannels.py", "w") as file:
            file.writelines(lines)


    @events_enable.error
    async def events_enable_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="settings",
        description="Customize the selection of random events in your server",
    )
    @app_commands.describe(
        channel="The channel that already has random events enabled (Current channel if not provided)",
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def events_settings(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ) -> None:
        if channel == None:
            channel = interaction.channel
        ref = db.reference("/Global Events System")
        stickies = ref.get()
        found = None
        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                found = val.get("Events", [])
                frequency = val.get("Frequency", None)
                break

        if found is not None:
            string = "\n> ".join(
                [
                    f"{emoji} - {title} <:yes:1036811164891480194>"
                    if letter in found
                    else f"{emoji} - {title} <:no:1036810470860013639>"
                    for letter, emoji, title in zip(
                        letterString, letter_emojis, minigame_titles
                    )
                ]
            )

            embed = discord.Embed(
                title="Customize which mini-games you'd like to enable",
                description=f"**Channel:** {channel.mention}\n**Spawn Rate:** `{int(100/frequency) if frequency is not None else '0'}%`\n\n > {string}\n\nClick the button below and type in the **corresponding letter(s)** (i.e. `h` or `abdfm`) to **toggle** the mini-game(s). *To edit the frequency, use </events enable:1339782470677299260> again.*",
                color=discord.Color.blurple(),
            )
            view = View()
            view.add_item(ToggleEventButton())
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
        else:
            embed = discord.Embed(
                title="Random events are not enabled!",
                description=f"What are you thinking? Random event is currently not even enabled in {channel.mention}. To enable the function, use </events enable:1339782470677299260>.",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @events_settings.error
    async def events_settings_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)

    @app_commands.command(
        name="disable", description="Disable random events in a channel"
    )
    @app_commands.describe(
        channel="The channel to disable random events in (Current channel if not provided)"
    )
    @app_commands.checks.has_permissions(manage_guild=True, manage_channels=True)
    async def events_disable(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ) -> None:
        if channel is None:
            channel = interaction.channel

        ref = db.reference("/Global Events System")
        stickies = ref.get()

        found = False
        for key, val in stickies.items():
            if val["Channel ID"] == channel.id:
                db.reference("/Global Events System").child(key).delete()
                found = True
                break

        if found:
            embed = discord.Embed(
                title="Random events disabled!",
                description=f"Sad to see you go. If you change your mind at anytime, you could use </events enable:1339782470677299260> to re-enable random events again.",
                colour=0xFF0000,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            with open("./commands/Events/enabledChannels.py", "r") as file:
                lines = file.readlines()

            for i, line in enumerate(lines):
                if line.startswith("enabledChannels ="):
                    existing_dict = eval(line.split("=", 1)[1].strip())
                    if channel.id in existing_dict:
                        del existing_dict[channel.id]  # or: existing_dict.pop(channel.id)
                    lines[i] = f"enabledChannels = {existing_dict}\n"
                    break

            with open("./commands/Events/enabledChannels.py", "w") as file:
                file.writelines(lines)

        else:
            embed = discord.Embed(
                title="Random events are not enabled!",
                description=f"What are you thinking? Random event is currently not even enabled in {channel.mention}. To start having fun, use </events enable:1339782470677299260> to enable random games in this channel!",
                colour=0xFFFF00,
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @events_disable.error
    async def events_disable_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        await interaction.response.send_message(f"```{str(error)}```", ephemeral=True)
        
        
async def format_animated_background(ctx, gif_name): # Darken and resize an animated background GIF for profile cards
    if not gif_name.lower().endswith('.gif'):
        return await ctx.send("Please provide a GIF file!", delete_after=5)

    base_path = "./assets/Animated Mora Inventory Background/"
    input_path = os.path.join(base_path, gif_name)
    
    if not os.path.exists(input_path):
        return await ctx.send(f"File not found: {gif_name}", delete_after=10)
    
    try:
        with Image.open(input_path) as im:
            frames = []
            duration_info = []
            
            for frame in ImageSequence.Iterator(im):
                frame = frame.convert("RGBA")
                width, height = frame.size
                target_aspect = 720 / 256
                current_aspect = width / height
                
                if current_aspect > target_aspect:
                    new_width = int(target_aspect * height)
                    left = (width - new_width) // 2
                    frame = frame.crop((left, 0, left + new_width, height))
                else:
                    new_height = int(width / target_aspect)
                    top = (height - new_height) // 2
                    frame = frame.crop((0, top, width, top + new_height))
                
                frame = frame.resize((720, 256), Image.LANCZOS)
                
                enhancer = ImageEnhance.Brightness(frame)
                frame = enhancer.enhance(0.4)
                
                frames.append(frame)
                duration_info.append(frame.info.get('duration', 100))
            
            output_path = os.path.join(base_path, f"{gif_name}")
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=duration_info,
                loop=0,
                disposal=2
            )
        
        await ctx.send(f"✅ Successfully formatted `{gif_name}`!", 
                       file=discord.File(output_path))
    
    except Exception as e:
        await ctx.send(f"❌ Error processing GIF: {str(e)}", delete_after=15)
        
class NewGameUpdate(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author == self.client.user or message.author.bot == True:
            return

        if message.content.startswith("-format") and message.author.id == 692254240290242601:
            await format_animated_background(message.channel, message.content.split(":")[1])

        if message.content.startswith("-report "):
            uid = message.content.split(" ")[1].replace("<@", "").replace(">", "")
            ian = self.client.get_user(692254240290242601)
            await ian.send(f"User with ID `{message.author.id}` reported the inventory background of a user with ID `{uid}` in **{message.guild.name}**")
            await ian.send(file=discord.File(f"./assets/Mora Inventory Background/{uid}.png"))
            await message.add_reaction("<:yes:1036811164891480194>")

        if message.content.startswith("-newgameupdate") and message.author.id == 692254240290242601:
            LETTER = message.content.split(" ")[1].strip().upper()  # NEW GAME LETTER

            ref = db.reference("/Global Events System")
            stickies = ref.get()
            originalList = None
            count = 0

            for key, val in stickies.items():
                if ("beta" in message.content and 1303235296254759008 != val["Channel ID"]) or ("beta" not in message.content and 1303235296254759008 == val["Channel ID"]):
                    continue

                originalList = val["Events"]
                frequency = val["Frequency"]
                channelID = val["Channel ID"]
                originalList.append(LETTER)
                db.reference("/Global Events System").child(key).delete()

                data = {
                    channelID: {
                        "Channel ID": channelID,
                        "Frequency": frequency,
                        "Events": originalList,
                    }
                }

                for key, value in data.items():
                    ref.push().set(value)

                count += 1

                if "beta" in message.content and 1303235296254759008 == val["Channel ID"]:
                    await message.channel.send(f"<#{channelID}> updated with `{LETTER}` enabled by default.")
                    break

            await message.channel.send(f"`{count}` channels updated with `{LETTER}` enabled by default.")

        if message.content.startswith("-removegame") and message.author.id == 692254240290242601:
            LETTER = message.content.split(" ")[1].strip().upper()  # GAME LETTER TO REMOVE

            ref = db.reference("/Global Events System")
            stickies = ref.get()
            originalList = None
            count = 0
            
            for key, val in stickies.items():
                if ("beta" in message.content and 1303235296254759008 != val["Channel ID"]) or ("beta" not in message.content and 1303235296254759008 == val["Channel ID"]):
                    continue

                originalList = val["Events"]
                frequency = val["Frequency"]
                channelID = val["Channel ID"]

                if LETTER in originalList:
                    originalList.remove(LETTER)  # Remove only the first occurrence
                    db.reference("/Global Events System").child(key).delete()
                    data = {
                        channelID: {
                            "Channel ID": channelID,
                            "Frequency": frequency,
                            "Events": originalList,
                        }
                    }

                    for key, value in data.items():
                        ref.push().set(value)

                    count += 1

                    if "beta" in message.content and 1303235296254759008 == val["Channel ID"]:
                        await message.channel.send(f"<#{channelID}> updated with `{LETTER}` removed from the defaults.")
                        break

            await message.channel.send(f"`{count}` channels updated with `{LETTER}` removed from defaults.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventSystem(bot))
    await bot.add_cog(NewGameUpdate(bot))