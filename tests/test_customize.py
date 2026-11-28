import io
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from PIL import Image

from commands.Events import config, customize

NO = config.NO_EMOTE
YES = config.YES_EMOTE
USER, GUILD, CHANNEL = 20, 10, 30
SAMPLE = ("69,420", "69", "6,767", "67", "69,420", "69", "6,767", "67")


def picture(size, kind="PNG", frames=1):
    """Gives the bytes of a plain picture, or of a GIF with several frames."""
    images = [Image.new("RGB", size, (200, 100 + 20 * n, 50)) for n in range(frames)]
    data = io.BytesIO()
    if kind == "GIF":
        images[0].save(
            data, "GIF", save_all=True, append_images=images[1:], duration=[70] * frames
        )
    else:
        images[0].save(data, kind)
    return data.getvalue()


class Upload:
    """Stands in for an uploaded file."""

    def __init__(self, filename, data):
        self.filename = filename
        self.data = data

    async def save(self, path):
        with open(path, "wb") as file:
            file.write(self.data)


class World:
    """Stands in for the stored cosmetics, inventory and Elite Track; `calls` lists the writes."""

    def __init__(self, root):
        self.root = root
        self.cosmetics = None
        self.inventory = []
        self.pinned = None
        self.elite = False
        self.calls = []
        self.cards = []

    async def get_cosmetics(self, pool, gid, uid):
        return dict(self.cosmetics) if self.cosmetics is not None else None

    async def upsert_cosmetics(self, pool, gid, uid, **values):
        self.calls.append(("cosmetics", gid, uid, values))
        self.cosmetics = {**(self.cosmetics or {}), **values}

    async def get_user_inventory(self, pool, uid, gid):
        return list(self.inventory)

    async def get_pinned_item(self, pool, uid, gid):
        return self.pinned

    async def unpin_all_items(self, pool, uid, gid):
        self.calls.append(("unpin", uid, gid))

    async def pin_item(self, pool, uid, gid, title):
        self.calls.append(("pin", uid, gid, title))

    async def update_quest(self, uid, gid, channel, progress, client):
        self.calls.append(("quest", uid, gid, channel, progress))

    async def is_elite_active(self, pool, uid, gid):
        return self.elite

    async def createProfileCard(self, user, *numbers, **looks):
        self.cards.append((numbers, looks))
        card = io.BytesIO(b"card")
        card.name = "card.png"
        return card


@pytest.fixture
def world(monkeypatch, tmp_path):
    world = World(str(tmp_path))
    for name in dir(World):
        if not name.startswith("_") and hasattr(customize, name):
            monkeypatch.setattr(customize, name, getattr(world, name))
    for name in ("INVENTORY_BG_PATH", "ANIMATED_INVENTORY_BG_PATH", "FRAMES_DIRECTORY"):
        os.mkdir(tmp_path / name)
        monkeypatch.setattr(customize, name, str(tmp_path / name))
    (tmp_path / "default.png").write_bytes(b"default")
    monkeypatch.setattr(customize, "DEFAULT_BG_PATH", str(tmp_path / "default.png"))
    return world


def path(world, folder, name):
    return f"{world.root}/{folder}/{name}"


def interaction(user=USER):
    it = MagicMock()
    it.user.id = user
    it.user.mention = f"<@{user}>"
    it.guild.id = GUILD
    it.channel.id = CHANNEL
    it.guild.get_role = lambda rid: (
        SimpleNamespace(name="Champion") if rid == 123 else None
    )
    it.response.defer = AsyncMock()
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.followup.send = AsyncMock()
    return it


def cog(channel=True):
    bot = MagicMock()
    room = MagicMock()
    room.send = AsyncMock(
        return_value=SimpleNamespace(
            attachments=[SimpleNamespace(proxy_url="https://proxy/card.png")]
        )
    )
    bot.get_channel = MagicMock(return_value=room if channel else None)
    return customize.Customize(bot), room


async def run(world, it=None, **options):
    it = it or interaction()
    the_cog, room = cog()
    await customize.Customize.customize.callback(the_cog, it, **options)
    return it, room


def sent(it):
    """Gives each follow-up as its text or embed, with whether it was ephemeral."""
    out = []
    for call in it.followup.send.await_args_list:
        body = call.args[0] if call.args else call.kwargs["embed"]
        out.append((body, call.kwargs.get("ephemeral", False)))
    return out


def choices(found):
    return [(choice.name, choice.value) for choice in found]


def test_the_commands_keep_their_names_and_options():
    command = customize.Customize.customize
    assert (command.name, command.description) == (
        "customize",
        "Customize your inventory and profile",
    )
    assert [p.name for p in command.parameters] == [
        "background",
        "pin_inventory",
        "profile_frame",
        "profile_title",
        "animated_background",
        "custom_accent_color",
        "profile_font",
    ]
    assert all(not p.required for p in command.parameters)
    assert [str(p.description) for p in command.parameters] == [
        "Your desired inventory background (auto cropped and scaled to 720x256px)",
        "Guild inventory reward to pin (displayed next to your name in mini-games)",
        "Your desried inventory profile frame (static or animated)",
        "Free Track: Select owned titles from autocomplete; Elite Track: Enter any custom title",
        "Elite Track only: upload a GIF to use as your animated inventory background",
        "Elite Track only: your custom accent color in hex code (e.g. #ff0000)",
        "Elite Track only: your profile card font preset",
    ]
    assert customize.PREVIEW_CHANNEL == 1026968305208131645
    assert [p.name for p in command.parameters if p.autocomplete] == [
        "pin_inventory",
        "profile_frame",
        "profile_title",
        "profile_font",
    ]
    preview = customize.Customize.preview
    assert (preview.name, preview.description) == (
        "preview",
        "Preview a profile frame on your profile card",
    )
    assert [(p.name, p.required) for p in preview.parameters] == [
        ("profile_frame", True)
    ]


async def test_pin_choices_skip_free_items_and_repeats(world):
    world.inventory = [
        ("123", "d", 5, GUILD, 0, False),
        ("Cool Item", "d", 3, GUILD, 0, True),
        ("Free", "d", 0, GUILD, 0, False),
        ("123", "d", 9, GUILD, 0, False),
        ("999", "d", 1, GUILD, 0, False),
    ]
    assert choices(await customize.pin_title_autocomplete(interaction(), "")) == [
        ("Unpin my current item only", "unpin"),
        ("Role: Champion", "123"),
        ("Title: Cool Item", "Cool Item"),
        ("Role: 999", "999"),
    ]
    assert choices(await customize.pin_title_autocomplete(interaction(), "CHAMP")) == [
        ("Unpin my current item only", "unpin"),
        ("Role: Champion", "123"),
    ]


async def test_pin_choices_survive_a_failed_read(world, monkeypatch):
    monkeypatch.setattr(
        customize, "get_user_inventory", AsyncMock(side_effect=RuntimeError("down"))
    )
    assert choices(await customize.pin_title_autocomplete(interaction(), "")) == [
        ("Unpin my current item only", "unpin")
    ]


async def test_title_choices_mark_animated_titles(world):
    assert choices(await customize.title_autocomplete(interaction(), "")) == [
        ("Unset title", "unset")
    ]
    world.cosmetics = {
        "titles": [["t1", "Hero"], ["t2", "<a:tada:12> Cool"], ["t3", ""], ["t4"]]
    }
    assert choices(await customize.title_autocomplete(interaction(), "")) == [
        ("Unset title", "unset"),
        ("Hero", "t1"),
        ("Cool (Animated)", "t2"),
    ]
    assert choices(await customize.title_autocomplete(interaction(), "anim")) == [
        ("Unset title", "unset"),
        ("Cool (Animated)", "t2"),
    ]


async def test_font_choices_mark_elite_fonts(world):
    found = choices(await customize.font_autocomplete(interaction(), ""))
    assert found[0] == ("Default", "Default")
    assert ("Arimo (Elite Track)", "Arimo") in found
    assert choices(await customize.font_autocomplete(interaction(), "arim")) == [
        ("Arimo (Elite Track)", "Arimo")
    ]


async def test_frame_choices_are_the_owned_frames(world):
    assert await customize.frame_autocomplete(interaction(), "") == []
    world.cosmetics = {"frames": ["Golden Ring.png", "Jade Stone.gif"]}
    assert choices(await customize.frame_autocomplete(interaction(), "")) == [
        ("Golden Ring", "Golden Ring.png"),
        ("Jade Stone (Animated)", "Jade Stone.gif"),
    ]
    assert choices(await customize.frame_autocomplete(interaction(), "animated")) == [
        ("Jade Stone (Animated)", "Jade Stone.gif")
    ]


async def test_every_frame_file_is_offered_in_order(world):
    for name in ("B.png", "a.GIF", ".hidden"):
        open(path(world, "FRAMES_DIRECTORY", name), "wb").close()
    os.mkdir(path(world, "FRAMES_DIRECTORY", "folder"))
    assert choices(await customize.all_frames_autocomplete(interaction(), "")) == [
        ("a (Animated)", "a.GIF"),
        ("B", "B.png"),
    ]
    assert choices(await customize.all_frames_autocomplete(interaction(), "PNG")) == [
        ("B", "B.png")
    ]
    os.rmdir(path(world, "FRAMES_DIRECTORY", "folder"))
    for name in os.listdir(customize.FRAMES_DIRECTORY):
        os.remove(path(world, "FRAMES_DIRECTORY", name))
    os.rmdir(customize.FRAMES_DIRECTORY)
    assert await customize.all_frames_autocomplete(interaction(), "") == []


def test_an_animated_background_is_found_by_path_or_name(world):
    find = customize.resolve_animated_background_path
    stored = path(world, "ANIMATED_INVENTORY_BG_PATH", "Night.gif")
    open(stored, "wb").close()
    assert find(None) is None and find("") is None
    assert find(stored) == stored
    assert find("Night.gif") == stored
    assert find("Night") == stored
    assert find("Day") is None and find("Day.gif") is None


async def test_nothing_chosen_and_both_backgrounds_are_refused(world):
    it, _ = await run(world)
    it.response.defer.assert_awaited_once_with(thinking=True)
    assert sent(it) == [
        (f"{NO} Please specify at least one customization option!", False)
    ]
    it, _ = await run(
        world, background=Upload("a.png", b""), animated_background=Upload("a.gif", b"")
    )
    assert sent(it) == [
        (
            f"{NO} You can't set both a static and animated background at the same time!",
            False,
        )
    ]
    assert world.calls == []


@pytest.mark.parametrize(
    "font, elite, unlocked, text",
    [
        ("Nope", True, True, "Invalid font preset. Choose one of the available presets."),
        ("Arimo", False, True, "You have not unlocked **custom font preset** on the Elite Track!"),
        ("Arimo", True, False, "You have not unlocked **custom font preset** on the Elite Track!"),
    ],
)  # fmt: skip
async def test_a_font_needs_the_elite_track(world, font, elite, unlocked, text):
    world.elite = elite
    world.cosmetics = {"selected_font_unlocked": unlocked}
    it, _ = await run(world, profile_font=font)
    assert sent(it) == [(f"{NO} {text}", False)]
    assert world.calls == [] and world.cards == []


async def test_a_font_is_previewed_then_saved_on_confirm(world):
    world.elite = True
    world.cosmetics = {"selected_font_unlocked": True, "selected_font": "Cousine"}
    it, room = await run(world, profile_font="Arimo")
    assert world.cards == [
        (
            SAMPLE,
            {
                "bg": customize.DEFAULT_BG_PATH,
                "profile_frame": None,
                "accent_color_hex": None,
                "font_name": "Arimo",
            },
        )
    ]
    room.send.assert_awaited_once()
    (call,) = it.followup.send.await_args_list
    embed, view = call.kwargs["embed"], call.kwargs["view"]
    assert embed.to_dict() == {
        "title": "🎨 Customization Preview",
        "description": f"Final preview for <@{USER}>'s customization:",
        "color": discord.Color.gold().value,
        "image": {"url": "https://proxy/card.png"},
        "type": "rich",
        "flags": 0,
    }
    assert view.timeout == 600
    assert [(b.label, b.style) for b in view.children] == [
        ("Confirm", discord.ButtonStyle.green),
        ("Cancel", discord.ButtonStyle.grey),
    ]
    assert world.calls == [("quest", USER, GUILD, CHANNEL, {"customize_profile": 1})]

    world.calls.clear()
    press = interaction()
    await view.confirm_callback.callback(press)
    assert world.calls == [
        (
            "cosmetics",
            GUILD,
            USER,
            {
                "selected_animated_background": None,
                "selected_profile_frame": None,
                "selected_font": "Arimo",
            },
        ),
        ("quest", USER, GUILD, CHANNEL, {"customize_profile": 1}),
    ]
    done = press.response.edit_message.await_args.kwargs
    assert done["view"] is None
    assert done["embed"].title == f"{YES} Customization Complete"
    assert done["embed"].description == (
        f"<@{USER}>, your customization has been confirmed!"
        "\n\nChanges applied:\n- font to **Arimo**"
    )
    assert done["embed"].color == discord.Color.green()


async def test_the_default_font_needs_nothing(world):
    it, _ = await run(world, profile_font="Default")
    assert world.cards[0][1]["font_name"] == "Default"


@pytest.mark.parametrize(
    "given, unlocked, text",
    [
        ("#ff0000", False, "You have not unlocked **custom accent color** on the Elite Track!"),
        ("fff", True, "Invalid hex format! Use 6-digit hex code (e.g. #ff0000)"),
        ("gggggg", True, "Invalid hex characters! Use 0-9 and A-F only"),
    ],
)  # fmt: skip
async def test_a_bad_accent_colour_is_refused(world, given, unlocked, text):
    world.cosmetics = {"embed_color": unlocked}
    it, _ = await run(world, custom_accent_color=given)
    assert sent(it) == [(f"{NO} {text}", False)]
    assert world.calls == []


async def test_an_accent_colour_needs_stored_cosmetics(world):
    it, _ = await run(world, custom_accent_color="#ff0000")
    assert "custom accent color" in sent(it)[0][0]


async def test_an_accent_colour_is_saved_at_once(world):
    world.cosmetics = {"embed_color": True}
    it, _ = await run(world, custom_accent_color=" ##12AbCd ")
    ((embed, ephemeral),) = sent(it)
    assert not ephemeral
    assert embed.title == f"{YES} Custom Accent Color Updated"
    assert (
        embed.description == f"<@{USER}>, your accent color has been set to `#12AbCd`!"
    )
    assert embed.color.value == 0x12ABCD
    assert world.calls == [
        ("cosmetics", GUILD, USER, {"selected_embed_color_hex": "12AbCd"}),
        ("quest", USER, GUILD, CHANNEL, {"customize_profile": 1}),
    ]
    assert world.cards == []


async def test_the_preview_uses_an_accent_colour_saved_a_moment_ago(world):
    world.elite = True
    world.cosmetics = {"embed_color": True, "frames": []}
    await run(world, custom_accent_color="00ff00", profile_font="Default")
    assert world.cards[0][1]["accent_color_hex"] == "00ff00"


async def test_a_title_is_unset(world):
    world.cosmetics = {"titles": [["t1", "Hero"]]}
    it, _ = await run(world, profile_title="unset")
    ((embed, ephemeral),) = sent(it)
    assert ephemeral
    assert embed.description == "Your title has been unset."
    assert embed.color == discord.Color.green()
    assert world.calls[0] == (
        "cosmetics",
        GUILD,
        USER,
        {"selected_title": None, "selected_custom_title": None},
    )
    assert world.calls[1][0] == "quest"


async def test_an_owned_title_is_chosen(world):
    world.cosmetics = {"titles": [["t1", "Hero"], ["t1", "Second"], ["t4"]]}
    it, _ = await run(world, profile_title="t1")
    assert sent(it)[0][0].description == "Title set to: **Hero**"
    assert world.calls[0][3] == {"selected_title": "t1", "selected_custom_title": None}


async def test_a_custom_title_needs_the_elite_track(world):
    refusal = (
        f"{NO} You cannot use custom titles, as you haven't unlocked them on the Elite Track."
        " You can still select owned titles from the autocomplete.",
        True,
    )
    for elite, unlocked in ((False, True), (True, False)):
        world.elite = elite
        world.cosmetics = {"titles": [], "selected_custom_title_unlocked": unlocked}
        it, _ = await run(world, profile_title="Mine")
        assert sent(it) == [refusal]
    world.cosmetics = None
    it, _ = await run(world, profile_title="Mine")
    assert sent(it) == [refusal]
    # The quest still counts a refused title.
    assert [call[0] for call in world.calls] == ["quest"] * 3


async def test_a_custom_title_is_set_without_its_outer_spaces(world):
    world.elite = True
    world.cosmetics = {"titles": [], "selected_custom_title_unlocked": True}
    it, _ = await run(world, profile_title="  Mine  ")
    assert sent(it)[0][0].description == "Custom title set to: **Mine**"
    assert world.calls[0][3] == {
        "selected_title": None,
        "selected_custom_title": "Mine",
    }
    world.calls.clear()
    it, _ = await run(world, profile_title="   ")
    assert sent(it) == [(f"{NO} Custom title cannot be empty!", True)]
    assert [call[0] for call in world.calls] == ["quest"]


async def test_unpinning_with_nothing_pinned(world):
    it, _ = await run(world, pin_inventory="unpin")
    ((embed, ephemeral),) = sent(it)
    assert not ephemeral
    assert embed.title == f"{config.HMM_EMOTE} No Pinned Item"
    assert embed.description == f"<@{USER}>, you don't have any items pinned!"
    assert embed.color == discord.Color.blue()
    assert [call[0] for call in world.calls] == ["quest"]


@pytest.mark.parametrize("pinned, shown", [("123", "<@&123>"), ("Cool", "Cool")])
async def test_unpinning_names_the_item(world, pinned, shown):
    world.pinned = pinned
    it, _ = await run(world, pin_inventory="unpin")
    embed = sent(it)[0][0]
    assert embed.title == "📌 Item Unpinned"
    assert embed.description == f"**{shown}** is now unpinned!"
    assert embed.color == discord.Color.green()
    assert world.calls[0] == ("unpin", USER, GUILD)


async def test_pinning_an_item_that_is_not_owned(world):
    world.inventory = [("Cool", "d", 1, GUILD, 0, False)]
    it, _ = await run(world, pin_inventory="456")
    embed = sent(it)[0][0]
    assert embed.title == f"{NO} Invalid Item"
    assert embed.description == "**<@&456>** isn't in your inventory!"
    assert embed.color == discord.Color.red()
    assert [call[0] for call in world.calls] == ["quest"]


async def test_pinning_an_owned_item(world):
    world.inventory = [("Cool", "d", 1, GUILD, 0, False)]
    it, _ = await run(world, pin_inventory="Cool")
    embed = sent(it)[0][0]
    assert embed.title == "📌 Item Pinned"
    assert embed.description == (
        "**Cool** is now pinned! It will appear alongside your name every time you win a game."
    )
    assert world.calls[0] == ("pin", USER, GUILD, "Cool")


async def test_the_preview_notes_a_pin_already_made(world):
    world.inventory = [("Cool", "d", 1, GUILD, 0, False)]
    it, _ = await run(world, pin_inventory="Cool", profile_font="Default")
    assert it.followup.send.await_args.kwargs["embed"].footer.text == (
        "Note: Your pin changes were already applied"
    )
    it, _ = await run(world, pin_inventory="Other", profile_font="Default")
    assert it.followup.send.await_args.kwargs["embed"].footer.text is None


async def test_a_frame_must_be_owned_and_on_disk(world):
    world.cosmetics = {"frames": ["Ring.png"]}
    it, _ = await run(world, profile_frame="Jade.gif")
    assert sent(it) == [(f"{NO} You don't own **Jade** profile frame!", True)]
    it, _ = await run(world, profile_frame="Ring.png")
    assert sent(it) == [(f"{NO} File for **Ring** not found!", True)]
    assert world.calls == [] and world.cards == []


async def test_a_frame_is_previewed_then_saved_on_confirm(world):
    world.cosmetics = {"frames": ["Ring.png"], "selected_font": "Arimo"}
    open(path(world, "FRAMES_DIRECTORY", "Ring.png"), "wb").close()
    it, _ = await run(world, profile_frame="Ring.png")
    assert world.cards[0][1]["profile_frame"] == "Ring.png"
    assert world.cards[0][1]["font_name"] is None
    assert world.calls == []
    view = it.followup.send.await_args.kwargs["view"]
    press = interaction()
    await view.confirm_callback.callback(press)
    assert world.calls[0][3] == {
        "selected_animated_background": None,
        "selected_profile_frame": "Ring.png",
        "selected_font": "Arimo",
    }
    assert press.response.edit_message.await_args.kwargs["embed"].description.endswith(
        "Changes applied:\n- profile frame to **Ring**"
    )


async def test_the_preview_shows_the_looks_already_chosen(world):
    world.elite = True
    world.cosmetics = {
        "selected_profile_frame": "Old.png",
        "selected_embed_color_hex": "abcdef",
        "selected_font": "Arimo",
        "selected_animated_background": "Night",
    }
    stored = path(world, "ANIMATED_INVENTORY_BG_PATH", "Night.gif")
    open(stored, "wb").close()
    open(path(world, "INVENTORY_BG_PATH", f"{USER}.png"), "wb").close()
    it, _ = await run(world, profile_font="Default")
    assert it.followup.send.await_args.kwargs["view"].animated_bg_path is None
    assert world.cards[0][1] == {
        "bg": stored,
        "profile_frame": "Old.png",
        "accent_color_hex": "abcdef",
        "font_name": "Default",
    }
    world.elite = False
    await run(world, profile_font="Default")
    assert world.cards[1][1] == {
        "bg": path(world, "INVENTORY_BG_PATH", f"{USER}.png"),
        "profile_frame": "Old.png",
        "accent_color_hex": None,
        "font_name": "Default",
    }


async def test_a_lost_animated_background_stops_the_preview(world):
    world.elite = True
    world.cosmetics = {"selected_animated_background": "Gone"}
    it, _ = await run(world, profile_font="Default")
    assert sent(it) == [(f"{NO} Animated background file not found!", True)]
    assert world.cards == []


async def test_a_static_background_is_cut_dimmed_and_kept_on_confirm(world):
    world.cosmetics = {"selected_animated_background": f"{USER}.gif"}
    it, _ = await run(world, background=Upload("a.png", picture((1000, 200))))
    temp = path(world, "INVENTORY_BG_PATH", f"{USER}-temp.png")
    with Image.open(temp) as image:
        assert image.size == (720, 256)
        assert image.convert("RGB").getpixel((5, 5)) == (80, 40, 20)
    assert world.cards[0][1]["bg"] == temp
    assert world.calls == []
    view = it.followup.send.await_args.kwargs["view"]

    other = interaction(user=99)
    await view.confirm_callback.callback(other)
    other.response.send_message.assert_awaited_once_with(
        f"{NO} You can't confirm this customization!", ephemeral=True
    )
    assert os.path.exists(temp)

    press = interaction()
    await view.confirm_callback.callback(press)
    assert not os.path.exists(temp)
    assert os.path.exists(path(world, "INVENTORY_BG_PATH", f"{USER}.png"))
    assert world.calls[0][3]["selected_animated_background"] is None
    assert press.response.edit_message.await_args.kwargs["embed"].description.endswith(
        "Changes applied:\n- static background"
    )


async def test_a_tall_static_background_is_cut_too(world):
    await run(world, background=Upload("a.png", picture((100, 900))))
    with Image.open(path(world, "INVENTORY_BG_PATH", f"{USER}-temp.png")) as image:
        assert image.size == (720, 256)


@pytest.mark.parametrize(
    "size, kept", [((900, 256), (90, 0, 810, 256)), ((720, 400), (0, 72, 720, 328))]
)
async def test_a_static_background_is_cut_from_its_middle(world, size, kept):
    image = Image.new("RGB", size, (0, 0, 0))
    image.paste((250, 250, 250), kept)
    data = io.BytesIO()
    image.save(data, "PNG")
    await run(world, background=Upload("a.png", data.getvalue()))
    with Image.open(path(world, "INVENTORY_BG_PATH", f"{USER}-temp.png")) as cut:
        spots = [cut.convert("RGB").getpixel(spot)[0] for spot in ((3, 3), (716, 252))]
    assert spots == [100, 100]


async def test_a_broken_static_background_is_reported(world):
    it, _ = await run(world, background=Upload("a.png", b"not a picture"))
    ((text, ephemeral),) = sent(it)
    assert text.startswith(f"{NO} Background processing failed: ")
    assert not ephemeral and world.cards == []


async def test_a_background_that_cannot_be_dimmed_is_left_cut(world):
    buffer = io.BytesIO()
    Image.new("P", (300, 300)).save(buffer, "PNG")
    it, _ = await run(world, background=Upload("a.png", buffer.getvalue()))
    ((text, _),) = sent(it)
    assert text == f"{NO} Background processing failed: image has wrong mode"
    with Image.open(path(world, "INVENTORY_BG_PATH", f"{USER}-temp.png")) as image:
        assert image.size == (720, 256)


async def test_confirm_reports_a_background_that_is_gone(world):
    it, _ = await run(world, background=Upload("a.png", picture((720, 256))))
    view = it.followup.send.await_args.kwargs["view"]
    os.remove(path(world, "INVENTORY_BG_PATH", f"{USER}-temp.png"))
    press = interaction()
    await view.confirm_callback.callback(press)
    text = press.response.send_message.await_args.args[0]
    assert text.startswith(f"{NO} Failed to save background: ")
    assert press.response.send_message.await_args.kwargs == {"ephemeral": True}
    assert world.calls == []


async def test_an_animated_background_needs_the_elite_track_and_a_gif(world):
    refusal = (
        f"{NO} You have not unlocked **custom animated GIF background** on the Elite Track!",
        True,
    )
    upload = Upload("a.gif", picture((80, 40), "GIF", 2))
    world.cosmetics = {"selected_animated_background_unlocked": True}
    it, _ = await run(world, animated_background=upload)
    assert sent(it) == [refusal]
    world.elite = True
    world.cosmetics = {"selected_animated_background_unlocked": False}
    it, _ = await run(world, animated_background=upload)
    assert sent(it) == [refusal]
    world.cosmetics = {"selected_animated_background_unlocked": True}
    it, _ = await run(
        world, animated_background=Upload("a.png", picture((80, 40), "GIF", 2))
    )
    assert sent(it) == [
        (f"{NO} Animated backgrounds must be uploaded as GIF files!", True)
    ]
    assert world.cards == [] and world.calls == []


async def test_an_animated_background_is_cut_dimmed_and_kept_on_confirm(world):
    world.elite = True
    world.cosmetics = {"selected_animated_background_unlocked": True}
    it, _ = await run(
        world, animated_background=Upload("a.GIF", picture((80, 40), "GIF", 3))
    )
    temp = path(world, "ANIMATED_INVENTORY_BG_PATH", f"{USER}-temp.gif")
    assert not os.path.exists(f"{temp}.upload")
    with Image.open(temp) as image:
        assert (image.size, image.n_frames) == ((720, 256), 3)
        assert image.info["duration"] == 70
        red, green, blue = image.convert("RGB").getpixel((5, 5))
        assert abs(red - 80) < 6 and abs(green - 40) < 6 and abs(blue - 20) < 6
    assert world.cards[0][1]["bg"] == temp
    view = it.followup.send.await_args.kwargs["view"]
    assert view.animated_bg_path == temp
    press = interaction()
    await view.confirm_callback.callback(press)
    assert not os.path.exists(temp)
    assert os.path.exists(path(world, "ANIMATED_INVENTORY_BG_PATH", f"{USER}.gif"))
    assert world.calls[0][3]["selected_animated_background"] == f"{USER}.gif"
    assert press.response.edit_message.await_args.kwargs["embed"].description.endswith(
        "Changes applied:\n- animated background upload"
    )


async def test_confirm_reports_an_animated_background_that_is_gone(world):
    world.elite = True
    world.cosmetics = {"selected_animated_background_unlocked": True}
    it, _ = await run(
        world, animated_background=Upload("a.gif", picture((80, 40), "GIF", 2))
    )
    view = it.followup.send.await_args.kwargs["view"]
    os.remove(view.animated_bg_path)
    press = interaction()
    await view.confirm_callback.callback(press)
    assert press.response.send_message.await_args.args[0].startswith(
        f"{NO} Failed to save animated background: "
    )
    assert world.calls == []


async def test_cancel_and_timeout_delete_the_waiting_uploads(world):
    for end in ("cancel", "timeout"):
        it, _ = await run(world, background=Upload("a.png", picture((720, 256))))
        temp = path(world, "INVENTORY_BG_PATH", f"{USER}-temp.png")
        view = it.followup.send.await_args.kwargs["view"]
        if end == "timeout":
            await view.on_timeout()
        else:
            other = interaction(user=99)
            await view.cancel_callback.callback(other)
            other.response.send_message.assert_awaited_once_with(
                f"{NO} You can't cancel this customization!", ephemeral=True
            )
            assert os.path.exists(temp)
            press = interaction()
            await view.cancel_callback.callback(press)
            done = press.response.edit_message.await_args.kwargs
            assert done["view"] is None
            assert done["embed"].title == f"{NO} Customization Cancelled"
            assert done["embed"].description == f"<@{USER}>, no changes were applied."
            assert done["embed"].color == discord.Color.red()
        assert not os.path.exists(temp)
        assert world.calls == []


async def test_cancel_deletes_a_waiting_animated_upload(world):
    world.elite = True
    world.cosmetics = {"selected_animated_background_unlocked": True}
    it, _ = await run(
        world, animated_background=Upload("a.gif", picture((80, 40), "GIF", 2))
    )
    view = it.followup.send.await_args.kwargs["view"]
    await view.cancel_callback.callback(interaction())
    assert not os.path.exists(view.animated_bg_path)


async def test_confirm_with_nothing_to_apply(world):
    view = customize.ConfirmCustomizationView(USER, GUILD)
    press = interaction()
    await view.confirm_callback.callback(press)
    assert press.response.edit_message.await_args.kwargs["embed"].description == (
        f"<@{USER}>, your customization has been confirmed! (No visual changes were made)"
    )


async def preview(world, frame, channel=True, it=None):
    it = it or interaction()
    the_cog, room = cog(channel)
    await customize.Customize.preview.callback(the_cog, it, frame)
    return it, room


async def test_previewing_a_frame_that_does_not_exist(world):
    it, _ = await preview(world, "Ring.png")
    it.response.defer.assert_awaited_once_with(thinking=True)
    assert sent(it) == [(f"{NO} Profile frame **Ring** not found!", False)]


@pytest.mark.parametrize(
    "frame, shown", [("Ring.png", "Ring (Static)"), ("Jade.GIF", "Jade (Animated)")]
)
async def test_previewing_a_frame(world, frame, shown):
    open(path(world, "FRAMES_DIRECTORY", frame), "wb").close()
    it, room = await preview(world, frame)
    assert world.cards == [
        (SAMPLE, {"bg": customize.DEFAULT_BG_PATH, "profile_frame": frame})
    ]
    room.send.assert_awaited_once()
    ((embed, ephemeral),) = sent(it)
    assert not ephemeral
    assert embed.to_dict() == {
        "title": "🖼️ Profile Frame Preview",
        "description": f"Preview of **{shown}** on <@{USER}>'s profile card",
        "color": discord.Color.blue().value,
        "image": {"url": "https://proxy/card.png"},
        "footer": {"text": "This is just a preview with placeholder values"},
        "type": "rich",
        "flags": 0,
    }


async def test_a_frame_preview_picks_the_members_background(world):
    open(path(world, "FRAMES_DIRECTORY", "Ring.png"), "wb").close()
    world.elite = True
    world.cosmetics = {"selected_animated_background": "Night"}
    stored = path(world, "ANIMATED_INVENTORY_BG_PATH", "Night.gif")
    open(stored, "wb").close()
    await preview(world, "Ring.png")
    assert world.cards[-1][1]["bg"] == stored
    world.elite = False
    await preview(world, "Ring.png")
    assert world.cards[-1][1]["bg"] == customize.DEFAULT_BG_PATH
    world.elite = True
    static = path(world, "INVENTORY_BG_PATH", f"{USER}.png")
    open(static, "wb").close()
    await preview(world, "Ring.png")
    assert world.cards[-1][1]["bg"] == static


async def test_a_frame_preview_without_the_preview_channel_sends_the_file(world):
    open(path(world, "FRAMES_DIRECTORY", "Ring.png"), "wb").close()
    it, _ = await preview(world, "Ring.png", channel=False)
    call = it.followup.send.await_args
    assert call.args == (f"{NO} Preview of **Ring** frame:",)
    assert isinstance(call.kwargs["file"], discord.File)


async def test_a_failed_frame_preview_is_reported(world, monkeypatch):
    open(path(world, "FRAMES_DIRECTORY", "Ring.png"), "wb").close()
    monkeypatch.setattr(
        customize, "createProfileCard", AsyncMock(side_effect=RuntimeError("no font"))
    )
    it, _ = await preview(world, "Ring.png")
    assert sent(it) == [(f"{NO} Failed to generate preview: no font", False)]


async def test_an_animated_background_is_cut_from_its_middle(world):
    image = Image.new("RGB", (600, 100), (0, 0, 0))
    image.paste((250, 250, 250), (0, 0, 100, 100))
    data = io.BytesIO()
    second = image.copy()
    second.paste((250, 250, 250), (290, 0, 310, 100))
    image.save(data, "GIF", save_all=True, append_images=[second])
    output = path(world, "ANIMATED_INVENTORY_BG_PATH", "out.gif")
    await customize.process_animated_background_upload(
        Upload("a.gif", data.getvalue()), output
    )
    with Image.open(output) as saved:
        assert saved.size == (720, 256)
        assert max(saved.convert("RGB").getpixel((3, 100))) < 10


async def test_a_gif_with_one_frame_is_not_accepted(world):
    # Pillow refuses the list of disposals for a single frame; kept as it was.
    output = path(world, "ANIMATED_INVENTORY_BG_PATH", "out.gif")
    with pytest.raises(TypeError):
        await customize.process_animated_background_upload(
            Upload("a.gif", picture((80, 40), "GIF", 1)), output
        )
