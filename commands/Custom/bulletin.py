import time

import discord
from discord import app_commands
from discord.ext import commands

from commands.Custom import winnerStore as store

BULLETIN = 1281655927791030293
LEADERBOARD_CHANNEL = 1312858564695687310
WINNER_ROLE = 1313053449549512704
WINNER_MORA = 100000
MORA_SOURCE = 10

INVITE_LINKS = ("discord.com/invite/", "discord.gg/", "discordapp.com/invite/")
INVITE_CATEGORIES = [
    1281655927791030302,
    1299725218767568997,
    1281690196357808240,
    1301601587059490836,
]
INVITE_ROLES = (1282396278071890086, 1282395927168159876)
MOD_LOG = 1288400196220227594

RULES_CHANNEL = 1281655927971250305
RULES_MESSAGE = 1297054467107328000
ANNOUNCEMENTS = [
    1281673438435741696,
    1281675540511850639,
    1281675690416279633,
    1281675725216284753,
]

ABOUT = (
    "The leaderboard will be updated every Saturday. The member who secures the top "
    "position in the **text message leaderboard** will be granted the prestigious "
    f"<@&{WINNER_ROLE}> role for the entire week, along with the following generous "
    "reward:\n\n- The role comes with its own category and autorespond GIF\n- Members "
    "will be able to mention your role any time (flex)\n\n> To view the current "
    "leaderboard, please use </stats message:1025501230044286982>. Alternatively, you "
    "can check your personal statistics by using </me:1025501230044286978>."
)
SAVE_MORA = """INSERT INTO minigame_mora (uid, gid, cid, timestamp, count)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (gid, uid, cid, timestamp)
    DO UPDATE SET count = $5"""


def leaderboard(winner, link):
    """Gives the two embeds that announce the week's winner."""
    about = discord.Embed(title="Weekly Leaderboard", description=ABOUT, color=0x00FFAF)
    week = discord.Embed(
        description="***Presenting this week's leaderboard...***", color=0x00FFAF
    )
    week.add_field(
        name="🏆 Top Message User",
        value=f"<:reply:1036792837821435976> {winner.mention}",
        inline=True,
    )
    week.set_image(url=link)
    return [about, week]


def deleted_invite(message):
    """Gives the mod-log embed for a deleted invite link."""
    embed = discord.Embed(
        title="Auto Moderation - External Server Invites", color=discord.Color.red()
    )
    embed.add_field(
        name="User:",
        value=f"{message.author.mention} `({message.author.id})`",
        inline=False,
    )
    embed.add_field(name="Channel(s):", value=message.channel.mention, inline=False)
    embed.add_field(name="Message Content", value=message.content, inline=False)
    embed.set_footer(text="Message deleted")
    return embed


class CustomCommands(commands.Cog):
    """Meropide Bulletin's leaderboard, invite filter, rule lookup and auto-publish."""

    def __init__(self, bot):
        self.client = bot

    async def cog_load(self):
        """Makes sure the winners table is there."""
        await store.create(self.client.pool)

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
        guild, pool = interaction.guild, interaction.client.pool
        if guild.id != BULLETIN:
            return await interaction.response.send_message(
                content="This command can only be used in the **Meropide Bulletin** server.",
                ephemeral=True,
            )
        embeds = leaderboard(text_user, link)
        await interaction.client.get_channel(LEADERBOARD_CHANNEL).send(embeds=embeds)
        role = guild.get_role(WINNER_ROLE)
        last = await store.winner(pool, guild.id)
        if last:
            last = await guild.fetch_member(last)
            if role in last.roles:
                await last.remove_roles(role)
        await text_user.add_roles(role)
        await store.crown(pool, guild.id, text_user.id)
        await interaction.response.send_message(
            content=f"The following embed is sent to <#{LEADERBOARD_CHANNEL}>:",
            embeds=embeds,
        )
        await pool.execute(
            SAVE_MORA,
            text_user.id,
            guild.id,
            MORA_SOURCE,
            int(time.time()),
            WINNER_MORA,
        )
        await interaction.followup.send(
            "<:yes:1036811164891480194> Added exactly <:MORA:1364030973611610205> "
            f"`100,000` to <@{text_user.id}>'s inventory. \n-# This is not boosted "
            "and doesn't count towards quest progression.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        """Runs Meropide Bulletin's three chat rules on a member's message."""
        if message.author.bot or not message.guild or message.guild.id != BULLETIN:
            return
        if any(link in message.content for link in INVITE_LINKS):
            await self.filter_invite(message)
        text = message.content.lower()
        if text.startswith("-r") and text[2:].isdigit() and 1 <= int(text[2:]) <= 10:
            if not await self.show_rule(message, int(text[2:]) - 1):
                return
        if message.channel.id in ANNOUNCEMENTS:
            try:
                await message.publish()
            except Exception as e:
                print(f"Error auto publishing message: {e}")

    async def filter_invite(self, message):
        """Deletes an invite to another server, unless the place or member may post one."""
        guild, author = message.guild, message.author
        if message.channel.category.id in INVITE_CATEGORIES or any(
            guild.get_role(role) in author.roles for role in INVITE_ROLES
        ):
            return
        invites = await guild.invites()
        if not invites or any(invite.code in message.content for invite in invites):
            return
        await message.delete()
        await message.channel.send(
            f"{author.mention}, no invite links!", delete_after=300
        )
        await guild.get_channel(MOD_LOG).send(embed=deleted_invite(message))

    async def show_rule(self, message, index):
        """Posts one rule from the rules message; says False if there is no such rule."""
        try:
            channel = self.client.get_channel(RULES_CHANNEL)
            if not channel:
                channel = await self.client.fetch_channel(RULES_CHANNEL)
            rules = (await channel.fetch_message(RULES_MESSAGE)).embeds
            if index >= len(rules):
                await message.channel.send(
                    "❌ That rule number doesn’t exist.", delete_after=10
                )
                return False
            await message.channel.send(embed=rules[index])
        except Exception as e:
            await message.channel.send("⚠️ Failed to fetch the rule.", delete_after=10)
            print(f"Error fetching rule: {e}")
        return True


async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
