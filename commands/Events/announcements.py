import discord
from utils.commands import SlashCommand

from commands.Events.config import DOT_EMOTE

announcement_embed = None

# discord.Embed(
#     title="",
#     description=(
#         "## <:YanfeiNote:1335644122253623458> **Mora Gifting Glitch**\n"
#         "We recently identified an issue where **passive Mora boosts** were incorrectly applying to gifts, allowing more Mora to be received than was actually sent. To keep the economy fair for everyone, we have deployed a fix. <:HuTaoEvil:1350630212617896120>\n"
#         "### <:NingguangStonks:1265470501707321344> **What Has Changed?**\n"
#         f"{DOT_EMOTE} **Boosts Disabled for Gifts:** Your personal Mora boosts no longer apply to incoming gifts. The recipient now receives **exactly** what the donor sends.\n"
#         f"{DOT_EMOTE} **Balance Adjustments:** Any extra Mora generated via this exploit has been **automatically reverted** from affected accounts.\n"
#         f"{DOT_EMOTE} **Improved Notifications:** Gift messages now explicitly show the tax paid and ping the recipient directly! 🔔\n"
#         "### <:CharlotteHeart:1191594476263702528> **Keeping it Fair**\n"
#         "Fischl is watching! Exploiting system bugs to inflate the economy hurts the value of everyone's hard-earned Mora. We appreciate the honest players who reported this to us. <:PaimonWow:1188553806456291489>\n\n"
#         f"-# You can still support your friends using {SlashCommand('gift')}, just remember that Fischl always takes her cut! 🦅"
#     ),
#     color=discord.Color.blue()
# ).set_footer(text="Thank you for helping us maintain a balanced and fun economy! 🫶")

# embed = discord.Embed(
#     title="",
#     description=(
#         "## <:MelonBread_KeqingNote:1342924552392671254> **Database Migration**\n"
#         "Fischl just underwent a **huge refactor** with a **complete database migration** to improve stability and performance! <:PaimonWow:1188553806456291489>\n\n"
#         f"{DOT_EMOTE} Everything remains the same for now (in preparation for a major update)\n"
#         f"{DOT_EMOTE} All your minigame stats has been **carefully moved** to the new database\n"
#         f"{DOT_EMOTE} Everything has been **tested** with no errors so far\n\n"
#         f"-# However, it is entirely possible that I might have missed something. **If you discover any bugs or issues**, please don't hesitate to let me know by **creating a support ticket** in our [support server](https://discord.gg/BXkc8CC4uJ)!\n"
#         "### <:CharlotteHeart:1191594476263702528> Thank you for your understanding! Stay tuned for the new season on April 1! 🫶"
#     ),
#     color=discord.Color.blurple()
# )
# await interaction.followup.send(embed=embed, ephemeral=True)

# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:PinkCelebrate:1204614140044386314> **Minigames Just Got a Fresh New Look!**\n"
#             "We’ve given **many minigames a visual revamp** with cleaner layouts, smoother flow, and an overall fresher feel. "
#             "Everything should now feel clearer and more fun to play! <:PaimonWow:1188553806456291489>\n"
#             "### <:YanfeiNote:1335644122253623458> **2 New Minigames Added**\n"
#             f"{DOT_EMOTE} **Simple Math Game** — Quick mental math challenges to test your speed and accuracy 🧠\n"
#             f"{DOT_EMOTE} **Tik Tac Tok** — The classic **tic-tac-toe**, but with a *punny twist* 😏\n\n"
#             f"-# Jump in and try them out — your usual rewards, streaks, and progression all work just like before!"
#         ),
#         color=discord.Color.green()
#     ),
#     ephemeral=True
# )

# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:CharlotteHeart:1191594476263702528> **Bot Development Isn't Cheap**\n"
#             f"<:reply:1036792837821435976> Consider purchasing the **Elite Track** for **{interaction.guild.name}** to unlock exclusive cosmetics and boosts, all while supporting ~~your favorite bot~~ Fischl! ***[:yum: Click the link and select {interaction.guild.name} to view and purchase the Elite Track!](https://fischl.app/profile)***"
#         ),
#         color=discord.Color.gold()
#     ),
#     ephemeral=True,
#     view=View().add_item(Button(label="Your Support Would Mean A Lot!", url="https://fischl.app/profile", style=discord.ButtonStyle.link))
# )

# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:YanfeiNote:1335644122253623458> **How do you even check your staff past experiences?**\n"
#             "Introducing **ServerCV** — a **verified staff experience resume** applicants can share when applying for roles. "
#             "It helps servers instantly spot real experience and reduce fake claims. <:PaimonWow:1188553806456291489>\n\n"
#             f"{DOT_EMOTE} Clean, trusted resume link (example: https://servercv.com/u/ian)\n"
#             f"{DOT_EMOTE} No setup required for your server. Just endorse your staff members!\n"
#             "### <:CharlotteHeart:1191594476263702528> **Check us out for more info:** https://servercv.com/"
#         ),
#         color=discord.Color.blurple()
#     ).set_footer(text="Share this to your server owner or staff members!"),
#     ephemeral=True,
#     view=View().add_item(Button(label="Try ServerCV", url="https://servercv.com/", style=discord.ButtonStyle.link))
# )

# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:HuTaoEvil:1350630212617896120> **Free Mora & Summons Every day?!**\n"
#             "You can do just that for each server that has minigame enabled at **https://fischl.app/profile**! <:PaimonWow:1188553806456291489>\n\n"
#             f"{DOT_EMOTE}Play a **random daily minigame** on the website to earn **bonus Mora** + **1 extra summon** each day\n"
#             f"{DOT_EMOTE}Each challenge refreshes **daily at 00:00 UTC** (like daily chests)!\n\n"
#             f"-# Once you finish, your rewards will **automatically be credited** to your {SlashCommand('mora')} inventory. <:AyakaShine:1191592023946432522>"
#         ),
#         color=discord.Color.gold()
#     ).set_footer(text="Why are we doing this? We just launched our brand new profile website and dashboard! Check them out!"),
#     ephemeral=True,
#     view=View().add_item(Button(label="Complete your daily challenge", url="https://fischl.app/profile", style=discord.ButtonStyle.link))
# ) 

# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:CharlotteHeart:1191594476263702528> **Introducing the Fischl Profile Website!**\n"
#             "You can now access **your Fischl profile** directly from your browser at **https://fischl.app/profile**! <:PaimonWow:1188553806456291489>\n\n"
#             f"{DOT_EMOTE}View your **Mora inventory**, **Elite status**, and **track progress** — everything you see in {SlashCommand('mora')}.\n"
#             f"{DOT_EMOTE}**Purchase Elite Track instantly!** No more waiting for manual activation — it’ll **unlock automatically** right after purchase.\n"
#             "### <:PinkCelebrate:1204614140044386314> Still only **$0.99/month** *(or $2.97 per 3-month season!)*\n"
#             f"<:reply:1036792837821435976> ***[View Your Profile & Become Elite Now](https://fischl.app/profile)***"
#         ),
#         color=discord.Color.random()
#     ).set_thumbnail(url="https://media.discordapp.net/attachments/1106727534479032341/1381827880488669327/elite_track.png"),
#     ephemeral=True,
#     view=View().add_item(Button(label="View Your Profile", url="https://fischl.app/profile", style=discord.ButtonStyle.link))
# )

# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:YanfeiNote:1335644122253623458> **Prestige Reset Notice**\n"
#             "Due to a **season reset malfunction**, all players’ **Prestige levels were accidentally reset to 0**, even though Prestige is meant to be **permanent**.\n\n"
#             f"{DOT_EMOTE}Players who **completed all 31 tiers in Season 1’s track** should have **`+1 Prestige`**.\n"
#             f"{DOT_EMOTE}Those who **purchased the Elite Track** *and* reached its end should receive an **additional `+1 Prestige`** *(total of 2)*.\n"
#             "### <:CharlotteHeart:1191594476263702528> **How to Restore Your Prestige**\n"
#             f"If you believe you’re affected by this issue:\n"
#             f"<:reply:1036792837821435976> Join our [support server](https://discord.gg/BXkc8CC4uJ) and create a **support ticket**\n"
#             f"<:reply:1036792837821435976> **Forward a message by Fischl** showing your {SlashCommand('mora')} command as proof of your Season 1 track progress\n"
#             f"<:reply:1036792837821435976> If you cannot find proof, **please provide any relevant information about your progress**\n\n"
#             "-# Your Prestige will then be **restored manually** after verification. Thank you for your understanding and patience!"
#         ),
#         color=discord.Color.red()
#     ).set_thumbnail(url="https://i.imgur.com/Lhyd7HI.png"),
#     ephemeral=True
# )

# if datetime.datetime.now(datetime.timezone.utc).month == 10:
#     await interaction.followup.send(
#         embed=discord.Embed(
#             title="",
#             description=(
#                 "## <:MelonBread_KeqingNote:1342924552392671254> **Season 2 Starts Now!**\n"
#                 f"> The new season **started <t:1759276801:R>**! All seasonal boosts and cosmetics have been **reset**.\n\n"
#                 f"- <:YanfeiNote:1335644122253623458> We've capped chest streak earnings at {MORA_EMOTE} `10,000` (if you reach >100 days on your streak)\n"
#                 f"- <:AyakaShine:1191592023946432522> We also added a {SlashCommand('preview')} command, allowing you to check out the **new profile frames**!\n\n"
#                 "-# *The XP needed to get to the end of the season track is **decreased by half** (from 90K to 55K XP)! <:CharlotteHeart:1191594476263702528> "
#                 "Visit https://fischl.app/track/season_2/index.html and consider **purchasing the Elite Track** to support Fischl!*\n"
#             ),
#             color=discord.Color.random()
#         ),
#         ephemeral=True
#     )

# if sigils_earned:
#     embed = discord.Embed(
#         title=f"What Are Lunar Sigils? <:AlbedoQuestion:1191574408544923799>",
#         description="-# Earn <a:sigils:1402736987902967850> **Sigils** by chatting actively and use them to enter giveaways!",
#         color=discord.Color.purple()
#     )
#     embed.add_field(
#         name="<:NingguangStonks:1265470501707321344> Chat ➜ Sigils",
#         value="-# Start **meaningful conversations** to passively earn {SlashCommand('sigils')} in batches!",
#         inline=True
#     )
#     embed.add_field(
#         name=f"<:CharlotteHeart:1191594476263702528> Sigils ➜ Giveaways",
#         value="-# Spend your Sigils to **enter giveaways** and increase your chances with extra entries!",
#         inline=True
#     )
#     embed.add_field(
#         name="<:MelonBread_KeqingNote:1342924552392671254> Boost Your Earnings",
#         value="-# **Special roles** can get increased daily Sigil caps for more rewards!",
#         inline=True
#     )
#     await interaction.followup.send(embed=embed, ephemeral=True)
# else:
#     embed = discord.Embed(
#         title=f"A new feature has just arrived <:AlbedoQuestion:1191574408544923799>",
#         description=f"-# Ask your server admins to enable this system via {SlashCommand('giveaway enable')}.",
#         color=discord.Color.purple()
#     )
#     embed.add_field(
#         name="<:NingguangStonks:1265470501707321344> Chat ➜ Sigils",
#         value=f"-# Start **meaningful conversations** to passively earn <a:sigils:1402736987902967850> {SlashCommand('sigils')} in batches!",
#         inline=True
#     )
#     embed.add_field(
#         name=f"<:CharlotteHeart:1191594476263702528> Sigils ➜ Giveaways",
#         value=f"-# Spend your Sigils to **enter giveaways** and increase your chances with extra entries!",
#         inline=True
#     )
#     embed.add_field(
#         name="<:MelonBread_KeqingNote:1342924552392671254> Boost Your Earnings",
#         value=f"-# **Special roles** can get increased daily Sigil caps for more rewards!",
#         inline=True
#     )
#     await interaction.followup.send(embed=embed, ephemeral=True)
# embed = discord.Embed(
#     title="",
#     description=(
#         "## <:YanfeiNote:1335644122253623458> **Chest System Just Got Smarter!**\n"
#         "We’ve improved how **message-based chest unlocking** works to make things fairer and less abusable for everyone. Here’s what’s changed:\n\n"
#         f"{DOT_EMOTE}Messages must now meet **minimum quality** (no spam, repeats, or filler)\n"
#         f"{DOT_EMOTE}Added a **cooldown** between countable messages\n"
#         f"{DOT_EMOTE}Anywhere between **4 to 6** effortful messages are needed for chest to spawn\n"
#         "### <:PinkCelebrate:1204614140044386314> All your **upgrades, streaks, and chest rewards** stay the same!\n"
#         f"<:reply:1036792837821435976> ***[Unlock the Elite Track](https://fischlbot.web.app/track/season_1)***"
#     ),
#     color=discord.Color.teal()
# )
# embed.set_footer(text="Thank you for helping keep things fair for everyone! 🫶")
# await interaction.followup.send(embed=embed, ephemeral=True)

# embed=discord.Embed(
#         title="",
#         description=(
#             "## " + MONEYDANCE_EMOTE + " Did you know...?\n"
#             "Upgrade to **Elite Track** and get more than **DOUBLE** the rewards of the free version! Here's what you're missing: <:KokoWow:1191868161851666583>\n\n"
#             f"{DOT_EMOTE}**Extra `60%` Mora Boosts** (Free: `+50%` only)\n"
#             f"{DOT_EMOTE}**Extra `18` Minigame Summons** (Free: `+9` only)\n"
#             f"{DOT_EMOTE}**Extra `2` Chest Upgrades** (Free: `+3` only)\n"
#             f"{DOT_EMOTE}**4+ Exclusive Animated Cosmetics**\n"
#             f"{DOT_EMOTE}Personalize your {SlashCommand('mora')} inventory with **custom colors**\n"
#             "### <:PinkCelebrate:1204614140044386314> **All this and more for less than USD $1/month!**\n"
#             f"<:reply:1036792837821435976> ***[Compare Tracks / Purchase Now](https://fischlbot.web.app/track/season_1)***"
#         ),
#         color=0xfa0af6
#     ).set_thumbnail(url="https://media.discordapp.net/attachments/1106727534479032341/1381827880488669327/elite_track.png")
# embed.set_footer(text="Your purchase will help support bot development tremendously! 🙏")
# await interaction.followup.send(
#     embed=embed,
#     ephemeral=True
# )
# await interaction.followup.send(embed=discord.Embed(title="", description=f"## <:PaimonWow:1188553806456291489> NEW FEATURE ALERT! <:YanfeiNote:1335644122253623458>\nYou can now earn **XP** by **completing quests** or buying items! Unlock **Mora boosts**, **additional chest upgrades**, **Mora gifting**, exclusive cosmetics and titles in the new Progression Track! <:HuTaoEvil:1350630212617896120> \n### <:PinkCelebrate:1204614140044386314> **Use {SlashCommand('mora')} to check your daily quests & free rewards now!** \n-# **You can find the [full update release notes here!](https://fischlbot.web.app/track/update/)** <:MelonBread_KeqingNote:1342924552392671254> ", color=discord.Color.gold()), ephemeral=True)
# frequency = enabledChannels[interaction.channel.id]
# await interaction.followup.send(
#     embed=discord.Embed(
#         title="",
#         description=(
#             "## <:MelonBread_KeqingNote:1342924552392671254> **1 Day Until the Massive Update!**\n"
#             f"> The first season **starts <t:1751328000:R>**! When you claim your chest tomorrow, you’ll see everything you need to know to **maximize your rewards**.\n\n"
#             f"<:AyakaShine:1191592023946432522> Hang out and chat - minigames are still the best way to earn **tons of {MORA_EMOTE}**!\n"
#             "-# **Feeling curious?** Sneak a peek at ||the [update preview](https://fischlbot.web.app/track/update/) and the new [season track](https://fischlbot.web.app/track/season_1/) :eyes:||"
#         ),
#         color=discord.Color.random()
#     ),
#     ephemeral=True
# )

async def setup(bot):
    pass