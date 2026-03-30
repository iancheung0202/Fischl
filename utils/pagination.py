import discord

from discord.ui import Button, Select, View
from typing import List, Optional

SUPER_PREV_EMOJI = "<:fastbackward:1351972112696479824>"
PREV_EMOJI = "<:backarrow:1351972111010369618>"
NEXT_EMOJI = "<:rightarrow:1351972116819480616>"
SUPER_NEXT_EMOJI = "<:fastforward:1351972114433048719>"
NO_EMOJI = "<:no:1036810470860013639>"


class BaseSortSelect(discord.ui.Select):
    def __init__(self, options_list, default, initial_author=None, custom_id="sort"):
        self.initial_author = initial_author
        options = []
        
        for label, emoji in options_list:
            options.append(
                discord.SelectOption(
                    label=label,
                    emoji=emoji,
                    default=(label == default),
                )
            )
        
        super().__init__(
            placeholder="Choose the Sorting",
            max_values=1,
            min_values=1,
            options=options,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction):
        raise NotImplementedError("Subclasses must implement callback()")


class BasePaginationView(View):
    def __init__(
        self,
        pages: List[discord.Embed],
        initial_author: Optional[discord.User] = None,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.page = 0
        self.initial_author = initial_author
        self.message: Optional[discord.Message] = None
        self.original_footers = [page.footer.text if page.footer else None for page in pages]
        
        if self.pages:
            first_page = self.pages[0]
            footer_text = f"Page 1 of {len(self.pages)}"
            if self.original_footers[0]:
                footer_text += f" • {self.original_footers[0]}"
            first_page.set_footer(text=footer_text)
        
        self._update_button_states()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.initial_author and self.initial_author != interaction.user:
            await interaction.response.send_message(
                f"{NO_EMOJI} You are not the author of this command",
                ephemeral=True,
            )
            return False
        return True

    def _update_button_states(self) -> None:
        is_first_page = self.page == 0
        is_last_page = self.page == len(self.pages) - 1
        is_single_page = len(self.pages) == 1

        for child in self.children:
            if isinstance(child, Button):
                if child.custom_id == "super_prev":
                    child.disabled = is_first_page or is_single_page
                elif child.custom_id == "prev":
                    child.disabled = is_first_page or is_single_page
                elif child.custom_id == "super_next":
                    child.disabled = is_last_page or is_single_page
                elif child.custom_id == "next":
                    child.disabled = is_last_page or is_single_page

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, Button) and child.style == discord.ButtonStyle.link:
                continue
            child.disabled = True
            if isinstance(child, Select):
                child.add_option(
                    label="Disabled due to timeout",
                    value="X",
                    emoji=NO_EMOJI,
                    default=True,
                )

        try:
            if self.message:
                await self.message.edit(view=self)
        except discord.NotFound:
            pass

        self.stop()

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="super_prev",
        emoji=SUPER_PREV_EMOJI,
    )
    async def super_prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = 0
        self._update_button_states()
        embed = self.pages[self.page]
        footer_text = f"Page {self.page + 1} of {len(self.pages)}"
        if self.original_footers[self.page]:
            footer_text += f" • {self.original_footers[self.page]}"
        embed.set_footer(text=footer_text)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="prev",
        emoji=PREV_EMOJI,
    )
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page > 0:
            self.page -= 1
        else:
            self.page = len(self.pages) - 1

        self._update_button_states()
        embed = self.pages[self.page]
        footer_text = f"Page {self.page + 1} of {len(self.pages)}"
        if self.original_footers[self.page]:
            footer_text += f" • {self.original_footers[self.page]}"
        embed.set_footer(text=footer_text)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="next",
        emoji=NEXT_EMOJI,
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page < len(self.pages) - 1:
            self.page += 1
        else:
            self.page = 0

        self._update_button_states()
        embed = self.pages[self.page]
        footer_text = f"Page {self.page + 1} of {len(self.pages)}"
        if self.original_footers[self.page]:
            footer_text += f" • {self.original_footers[self.page]}"
        embed.set_footer(text=footer_text)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        custom_id="super_next",
        emoji=SUPER_NEXT_EMOJI,
    )
    async def super_next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = len(self.pages) - 1
        self._update_button_states()
        embed = self.pages[self.page]
        footer_text = f"Page {self.page + 1} of {len(self.pages)}"
        if self.original_footers[self.page]:
            footer_text += f" • {self.original_footers[self.page]}"
        embed.set_footer(text=footer_text)
        await interaction.response.edit_message(embed=embed, view=self)
