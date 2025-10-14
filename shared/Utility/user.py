import discord
import datetime

from discord import app_commands
from discord.ext import commands


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
        if user is None:
            user = interaction.user

        if len(user.roles) > 1:
            sorted_roles = [role for role in sorted(user.roles, key=lambda role: role.position, reverse=True) if role.id != interaction.guild.default_role.id]
            roles_str = ""
            total_length = 0
            included_roles = []

            for i, role in enumerate(sorted_roles):
                role_mention = f"<@&{role.id}>"
                next_length = total_length + len(role_mention) + (2 if included_roles else 0)
                remaining = len(sorted_roles) - (i + 1)
                suffix = f" ({remaining} more roles)" if remaining > 0 else ""
                if next_length + len(suffix) <= 1024:
                    included_roles.append(role_mention)
                    total_length = next_length
                else:
                    break

            remaining = len(sorted_roles) - len(included_roles)
            roles_str = ", ".join(included_roles)
            if remaining > 0:
                roles_str += f" ({remaining} more roles)"
        else:
            roles_str = "None"

        embed = discord.Embed(colour=user.top_role.colour.value)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        if user.banner:
            embed.set_image(url=user.banner.url)
        embed.add_field(name="Username", value=user.name, inline=True)
        embed.add_field(
            name="Server Nick",
            value=user.nick if hasattr(user, "nick") else "None",
            inline=True,
        )
        embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
        embed.add_field(
            name="Account created",
            value=f"<t:{int(user.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Joined this server",
            value=f"<t:{int(user.joined_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(name="Roles", value=roles_str, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(User(bot))
