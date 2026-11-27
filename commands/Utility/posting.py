import datetime

import discord

STORAGE_CHANNEL = 1026968305208131645
NO_PING = "<:no:1036810470860013639> You don't have permissions to mention `@everyone`, `@here`, or other roles!"
SENT = "<:yes:1036811164891480194> Sent!"


async def hosted(interaction, image, name):
    """Keeps an uploaded picture in the bot's own channel and gives its link."""
    path = f"./assets/{name}.png"
    await image.save(path)
    channel = interaction.client.get_channel(STORAGE_CHANNEL)
    stored = await channel.send(file=discord.File(path))
    return stored.attachments[0].proxy_url


def sign(embed, guild):
    """Puts the server's name, its icon if it has one, and the time on an embed."""
    try:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    except Exception:
        embed.set_footer(text=guild.name)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)


async def post(interaction, headline, role, embed, view):
    """Posts an announcement in the channel, with a role ping if the member may."""
    if role is not None:
        if not interaction.user.guild_permissions.mention_everyone:
            await interaction.response.send_message(NO_PING, ephemeral=True)
            return False
        headline = f"{role.mention} {headline}"
    await interaction.channel.send(
        f"<:blurplemic:1108805037230129302> {headline}", embed=embed, view=view
    )
    return True


async def setup(bot):
    pass
