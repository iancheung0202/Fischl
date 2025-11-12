import discord
import time

from firebase_admin import db
from discord import app_commands
from discord.ext import commands

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    @app_commands.command(
        name="send-leaderboard",
        description="Posts the weekly leaderboard (Meropide Bulletin only)",
    )
    @app_commands.describe(
        text_user="User with the most messages",
        link="The link of the leaderboard image",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def send_leaderboard(
        self,
        interaction: discord.Interaction,
        text_user: discord.Member,
        link: str,
    ) -> None:
        if interaction.guild.id == 1281655927791030293:
            chn = interaction.client.get_channel(1312858564695687310)
            embed1 = discord.Embed(
                title="Weekly Leaderboard",
                description="The leaderboard will be updated every Saturday. The member who secures the top position in the **text message leaderboard** will be granted the prestigious <@&1313053449549512704> role for the entire week, along with the following generous reward:\n\n- The role comes with its own category and autorespond GIF\n- Members will be able to mention your role any time (flex)\n\n> To view the current leaderboard, please use </stats message:1025501230044286982>. Alternatively, you can check your personal statistics by using </me:1025501230044286978>.",
                color=0x00FFAF,
            )
            embed2 = discord.Embed(
                description="***Presenting this week's leaderboard...***",
                color=0x00FFAF,
            )
            embed2.add_field(
                name="🏆 Top Message User",
                value=f"<:reply:1036792837821435976> {text_user.mention}",
                inline=True,
            )
            embed2.set_image(url=link)
            await chn.send(
                embeds=[embed1, embed2]
            )
            role = interaction.guild.get_role(1313053449549512704)
            db_path = f"/Weekly Leaderboard/{interaction.guild.id}"
            prev_winner_id = db.reference(db_path).get()

            # Remove role from previous winner if they exist
            if prev_winner_id:
                prev_member = await interaction.guild.fetch_member(int(prev_winner_id))
                if prev_member and role in prev_member.roles:
                    await prev_member.remove_roles(role)

            # Add role to new winner
            await text_user.add_roles(role)

            # Update database with new winner
            db.reference(db_path).set(str(text_user.id))
            await interaction.response.send_message(
                content="The following embed is sent to <#1312858564695687310>:",
                embeds=[embed1, embed2],
            )

            ts = str(int(time.time()))
            path = f"/Mora/{text_user.id}/{interaction.guild.id}/{10}/{ts}"
            db.reference(path).set(100000)

            await interaction.followup.send(
                f"<:yes:1036811164891480194> Added exactly <:MORA:1364030973611610205> `100,000` to <@{text_user.id}>'s inventory. \n-# This is not boosted and doesn't count towards quest progression.",
                ephemeral=True,
            )
        else:
            return await interaction.response.send_message(
                content="This command can only be used in the **Meropide Bulletin** server.",
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author == self.client.user or message.author.bot == True:
            return

        # MEROPIDE BULLETIN REPLACED SAPPHIRE INVITE LINK AUTOMOD RULE #

        if message.guild.id == 1281655927791030293 and ("discord.com/invite/" in message.content or "discord.gg/" in message.content):
            if (
                message.channel.category.id in [1281655927791030302, 1299725218767568997, 1281690196357808240, 1301601587059490836]
                or message.guild.get_role(1282396278071890086) in message.author.roles
                or message.guild.get_role(1282395927168159876) in message.author.roles
            ):
                pass
            else:
                invites = await message.guild.invites()
                for invite in invites:
                    if invite.code in message.content:
                        ownServer = True
                        break
                    else:
                        ownServer = False
                if not ownServer:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, no invite links!", delete_after=300)

                    embed = discord.Embed(
                        title="Auto Moderation - External Server Invites",
                        color=discord.Color.red(),
                    )
                    embed.add_field(name="User:", value=f"{message.author.mention} `({message.author.id})`", inline=False)
                    embed.add_field(name="Channel(s):", value=f"{message.channel.mention}", inline=False)
                    embed.add_field(name="Message Content", value=message.content, inline=False)
                    embed.set_footer(text=f"Message deleted")

                    await message.guild.get_channel(1288400196220227594).send(embed=embed)

        # MEROPIDE BULLETIN SERVER RULE TRIGGER PHRASES #

        if (message.guild.id == 1281655927791030293 and message.content.lower().startswith("-r") and message.content.lower()[2:].isdigit()):
            index = int(message.content.lower()[2:]) - 1  # Convert to 0-based index
            if 0 <= index < 10:
                try:
                    channel = self.client.get_channel(1281655927971250305)
                    if not channel:
                        channel = await self.client.fetch_channel(1281655927971250305)

                    msg = await channel.fetch_message(1297054467107328000)
                    if index >= len(msg.embeds):
                        await message.channel.send("❌ That rule number doesn’t exist.", delete_after=10)
                        return

                    embed = msg.embeds[index]
                    await message.channel.send(embed=embed)

                except Exception as e:
                    await message.channel.send("⚠️ Failed to fetch the rule.", delete_after=10)
                    print(f"Error fetching rule: {e}")


async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
