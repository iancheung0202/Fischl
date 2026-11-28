import datetime

import discord
from discord import app_commands
from discord.ext import commands

FIELD_LIMIT = 1024


def role_list(member, everyone_id: int) -> str:
    """Gives a member's roles, highest first, cut with a count of the rest when they pass a field's limit."""
    if len(getattr(member, "roles", ())) <= 1:
        return "None"
    roles = sorted(member.roles, key=lambda role: role.position, reverse=True)
    mentions = [f"<@&{role.id}>" for role in roles if role.id != everyone_id]
    shown, length = [], 0
    for index, mention in enumerate(mentions):
        left = len(mentions) - index - 1
        suffix = f" ({left} more roles)" if left > 0 else ""
        longer = length + len(mention) + (2 if shown else 0)
        if longer + len(suffix) > FIELD_LIMIT:
            break
        shown.append(mention)
        length = longer
    left = len(mentions) - len(shown)
    return ", ".join(shown) + (f" ({left} more roles)" if left > 0 else "")


class User(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="user", description="Shows the details of a server member"
    )
    @app_commands.describe(
        user="Specify any user",
    )
    async def user(
        self, interaction: discord.Interaction, user: discord.Member = None
    ) -> None:
        user = user or interaction.user
        embed = discord.Embed(
            colour=user.top_role.colour.value,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        if user.banner:
            embed.set_image(url=user.banner.url)
        fields = {
            "Username": user.name,
            "Server Nick": user.nick if hasattr(user, "nick") else "None",
            "User ID": f"`{user.id}`",
            "Account created": f"<t:{int(user.created_at.timestamp())}:R>",
            "Joined this server": f"<t:{int(user.joined_at.timestamp())}:R>",
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)
        roles = role_list(user, interaction.guild.default_role.id)
        embed.add_field(name="Roles", value=roles, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(User(bot))
