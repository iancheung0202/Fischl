import discord
from discord.ext import commands

from commands.CoOp import reputationStore as store

NO = "<:no:1036810470860013639>"
YES = "<:yes:1036811164891480194>"


def mentioned(word):
    """Gives the user id in a mention or a bare id."""
    return int(word.replace("<@", "").replace(">", ""))


async def show(message, pool):
    """Answers `-rep` with a member's reps, the author's when nobody valid is named."""
    try:
        member = await message.guild.fetch_member(
            mentioned(message.content.split(" ")[1])
        )
    except Exception:
        member = message.author
    found = await store.points(pool, message.guild.id, member.id)
    await message.channel.send(f"**{member.name}**: **{found}** rep")


async def leaderboard(message, pool):
    """Answers `-toprep` with the server's members holding the most reps."""
    try:
        count = min(max(int(message.content.split(" ")[1]), 1), 50)
    except Exception:
        count = 10
    rows = await store.top(pool, message.guild.id, count)
    if not rows:
        return await message.channel.send("No reputation data found.")
    lines = []
    for place, row in enumerate(rows, 1):
        try:
            user = await message.guild.fetch_member(row["user_id"])
        except discord.NotFound:
            continue
        lines.append(f"{place}. **{user.name}** `({user.id})` - **{row['points']}**\n")
    embed = discord.Embed(
        title=f"Global Reputation Leaderboard - Top {count}",
        description="".join(lines),
        color=0xEB7660,
    )
    await message.channel.send(embed=embed)


def refusal(message, user_id, amount, most):
    """Gives why reps cannot be given, or None when they can."""
    if amount > most:
        return f"{NO} You can't give more than {most} reps at once."
    if user_id == message.author.id:
        return f"{NO} You can't give yourself reps!"
    if amount <= 0:
        return f"{NO} You must give at least 1 rep."


async def earned(member, before, after, rewards):
    """Gives the member every role whose cost they just reached, with an embed for each."""
    embeds = []
    for role_id, cost in rewards.items():
        role = member.guild.get_role(role_id)
        if role is None or not before <= cost <= after:
            continue
        await member.add_roles(role)
        embeds.append(
            discord.Embed(
                description=f"**{member.name}** just earned a new role: **{role.mention}**",
                color=discord.Color.green(),
            )
        )
    return embeds


async def give(message, pool, most):
    """Answers `-giverep @user amount`."""
    parts = message.content.split(" ")
    if len(parts) < 3:
        return await message.reply("Command Usage: `-giverep @user amount`")
    try:
        user_id, amount = mentioned(parts[1]), int(parts[2])
    except ValueError:
        return await message.reply(f"{NO} Invalid format. Use `-giverep @user amount`")
    problem = refusal(message, user_id, amount, most)
    if problem:
        return await message.reply(problem)
    member = await message.guild.fetch_member(user_id)
    after = await store.give(pool, message.guild.id, user_id, amount)
    rewards = await store.rewards(pool, message.guild.id)
    embeds = await earned(member, after - amount, after, rewards)
    await message.channel.send(
        f"{YES} Gave `{amount}` Rep to **{member.name}** (current - `{after}`)",
        embeds=embeds,
    )


class ReputationSystem(commands.Cog):
    """The `-rep`, `-toprep` and `-giverep` messages of the reputation system."""

    def __init__(self, bot):
        self.client = bot

    async def cog_load(self):
        await store.create(self.client.pool)

    @commands.Cog.listener()
    async def on_message(self, message):
        text = message.content.lower()
        if message.author.bot or not message.guild or not text.startswith("-"):
            return
        if not text.startswith(("-rep", "-toprep", "-giverep")):
            return
        pool = self.client.pool
        most = await store.max_rep(pool, message.guild.id)
        if most is None:
            return
        if text.startswith("-rep"):
            await show(message, pool)
        elif text.startswith("-toprep"):
            await leaderboard(message, pool)
        else:
            await give(message, pool, most)


async def setup(bot):
    await bot.add_cog(ReputationSystem(bot))
