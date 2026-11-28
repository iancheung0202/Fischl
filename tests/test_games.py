import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events.config import NO_EMOTE, YES_EMOTE
from commands.Events.games import boss, common, counting, guess, maths, tictactoe
from tests.games import (
    Channel,
    button_styles,
    client,
    member,
    mora,
    press,
    started,
    typed,
    won,
)

# --- Simple Math ---


async def test_maths_pays_the_first_right_answer_once(client):
    channel = Channel()
    await maths.simpleMathGame(channel, client)
    game = channel.last
    assert game.embed.title == "Simple Math Game 🧮"
    assert "One try per person!" in game.embed.description
    right = next(i for i, child in enumerate(game.view.children) if child.right)
    wrong = next(i for i, child in enumerate(game.view.children) if not child.right)

    missed = await press(client, game, 5, index=wrong)
    assert missed.said == ["That is incorrect!"]
    again = await press(client, game, 5, index=right)
    assert again.said == ["You have already guessed!"]

    await asyncio.gather(
        press(client, game, 6, index=right), press(client, game, 7, index=right)
    )
    assert await mora(client.pool) == {6: game.view.reward}
    assert "<@6> solved it correctly" in game.embed.description
    assert "First to answer" not in game.embed.description
    assert game.embed.color == discord.Color.green()
    assert game.view.children[right].style == discord.ButtonStyle.success
    assert all(child.disabled for child in game.view.children)
    assert won(client, 6)[0]["win_minigames"] == 1
    assert won(client, 5) == [{"participate_minigames": 1}]


async def test_maths_question_has_five_different_answers():
    for _ in range(200):
        numbers, signs, answer = maths.question()
        assert 0 <= answer <= 1000
        assert maths.worked_out(numbers, signs) == answer
        wrong = maths.wrong_answers(numbers, answer)
        assert len(wrong) == 4 and answer not in wrong


async def test_maths_greys_its_buttons_when_time_runs_out(client):
    channel = Channel()
    await maths.simpleMathGame(channel, client)
    await channel.last.view.on_timeout()
    assert all(child.disabled for child in channel.last.view.children)
    assert len(channel.last.view.children) == 5


# --- Tic Tac Tok ---


async def test_tictactoe_needs_two_recent_members(client):
    channel = Channel([member(5)])
    await tictactoe.ticTacTok(channel, client)
    assert channel.sent == []


async def test_tictactoe_turns_win_and_payment(client):
    channel = Channel([member(5), member(1, bot=True), member(5), member(6)])
    await tictactoe.ticTacTok(channel, client)
    game = channel.last
    assert game.content.endswith("<@5>'s turn!")
    assert game.embed.title == "Tik Tac Tok"

    assert (await press(client, game, 6, index=0)).said == ["It's not your turn!"]
    assert (await press(client, game, 9, index=0)).said == [
        "You are not part of this game!"
    ]
    for player, square in ((5, 0), (6, 3), (5, 1), (6, 4)):
        await press(client, game, player, index=square)
    assert game.content.endswith("<@5>'s turn!")
    await asyncio.gather(
        press(client, game, 5, index=2), press(client, game, 5, index=8)
    )
    assert game.content.startswith("🎉 <@5> won the Tik Tac Tok match")
    assert await mora(client.pool) == {5: game.view.reward}
    styles = [child.style for child in game.view.children]
    assert styles[:3] == [discord.ButtonStyle.success] * 3
    assert all(child.disabled for child in game.view.children)
    assert won(client, 5)[-1]["win_1v1_minigames"] == 1
    assert won(client, 6) == [{"participate_minigames": 1}]


async def test_tictactoe_draw_pays_nobody(client):
    channel = Channel([member(5), member(6)])
    await tictactoe.ticTacTok(channel, client)
    game = channel.last
    order = [0, 1, 2, 4, 3, 5, 7, 6, 8]
    for turn, square in enumerate(order):
        await press(client, game, 5 if turn % 2 == 0 else 6, index=square)
    assert game.content == "It's a draw!"
    assert await mora(client.pool) == {}
    assert all(child.disabled for child in game.view.children)


# --- Defeat the Boss ---


async def test_boss_pays_every_attacker_with_the_bonuses(client, monkeypatch):
    monkeypatch.setattr(boss.random, "randint", lambda low, high: low)
    monkeypatch.setattr(boss.random, "random", lambda: 1)
    monkeypatch.setattr(boss.random, "choice", lambda options: options[0])
    monkeypatch.setattr(boss.asyncio, "create_task", lambda coro: coro.close())
    channel = Channel()
    await boss.defeatTheBoss(channel, client)
    game = channel.last
    view = game.view
    assert view.max_hp == 3000
    for _ in range(40):
        await press(client, game, 5, label="Attack!")
    await asyncio.gather(*(press(client, game, 6, label="Attack!") for _ in range(30)))
    assert view.current_hp == 0 and view.total_damage == 3000
    late = await press(client, game, 7, label="Attack!")
    assert late.said == ["The boss is already defeated!"]
    assert "BOSS DEFEATED" in game.embed.description
    assert view.attack.disabled

    await view.update_loop()
    result = channel.last.embed
    assert result.title.startswith("Boss Defeated! - ")
    assert await mora(client.pool) == {5: 3000 + 2000 + 2000, 6: 3000 + 1000 + 1500}
    assert "🥇 **Best Damage Dealer!**" in result.description.split("\n")[2]
    assert "🗡️ **Last Hit!**" in result.description.split("\n")[3]


async def test_boss_escapes_when_time_runs_out(client, monkeypatch):
    monkeypatch.setattr(boss.asyncio, "create_task", lambda coro: coro.close())
    channel = Channel()
    await boss.defeatTheBoss(channel, client)
    view = channel.last.view
    await press(client, channel.last, 5, label="Attack!")
    view.start_time -= 61
    await view.update_loop()
    assert channel.last.embed.title == "Boss Escaped!"
    assert await mora(client.pool) == {}


# --- Match the PFP, Know Your Members, Memory Game ---


async def test_pfp_needs_three_recent_members(client):
    channel = Channel([member(5), member(6), member(5)])
    await guess.matchThePFP(channel, client)
    assert channel.texts() == [
        f"{guess.NO_EMOTE} Not enough unique users for the game."
    ]


async def test_pfp_tells_members_with_one_name_apart(client, monkeypatch):
    twins = [member(5, "Twin"), member(6, "Twin"), member(7, "Other")]
    twins[1].avatar = None
    monkeypatch.setattr(guess.random, "choice", lambda users: users[1])
    channel = Channel(twins)
    await guess.matchThePFP(channel, client)
    game = channel.last
    assert [child.right for child in game.view.children] == [False, True, False]
    assert game.embed.image.url == "https://cdn/6.png"

    missed = await press(client, game, 8, index=0)
    assert missed.said == [f"Wrong! {guess.NO_EMOTE}"]
    assert (await press(client, game, 8, index=1)).said == [
        f"{guess.NO_EMOTE} You already guessed!"
    ]
    await press(client, game, 9, index=1)
    assert await mora(client.pool) == {9: game.view.reward}
    assert game.embed.description.startswith("<@9> ")
    assert "guessed **Twin** correctly" in game.embed.description
    assert (await press(client, game, 10, index=1)).said == [
        f"{guess.NO_EMOTE} You already guessed!"
    ]
    assert await mora(client.pool) == {9: game.view.reward}


async def test_guess_view_times_out(client):
    channel = Channel([member(5), member(6), member(7)])
    await guess.matchThePFP(channel, client)
    await channel.last.view.on_timeout()
    assert channel.last.view is None
    assert channel.last.embed.description == guess.TIMED_OUT


async def test_know_your_members_asks_about_join_dates(client, monkeypatch):
    import datetime

    channel = Channel([member(5), member(6), member(1, bot=True)])

    async def fetch(uid):
        if uid == 6:
            raise discord.NotFound(MagicMock(status=404), "gone")
        return member(uid)

    channel.guild.fetch_member = fetch
    await guess.knowYourMembers(channel, client)
    assert channel.texts() == [
        f"{guess.NO_EMOTE} Not enough valid members for the game."
    ]

    def joined(uid):
        who = member(uid)
        who.joined_at = datetime.datetime(
            2020 + uid, 1, 1, tzinfo=datetime.timezone.utc
        )
        return who

    channel.guild.fetch_member = AsyncMock(side_effect=joined)
    monkeypatch.setattr(guess.random, "choice", lambda modes: "earlier")
    await guess.knowYourMembers(channel, client)
    game = channel.last
    assert game.embed.description.startswith(
        "Which user has been in **Server** longer?"
    )
    right = next(child for child in game.view.children if child.right)
    assert right.label == "member5"
    await press(client, game, 9, label="member5")
    assert "**Server Join Dates:**" in game.embed.description
    assert await mora(client.pool) == {9: game.view.reward}


async def test_know_your_members_needs_two_writers(client):
    channel = Channel([member(5)])
    await guess.knowYourMembers(channel, client)
    assert "Not enough unique recent messaging users" in channel.texts()[0]


async def test_memory_game_hides_the_emotes_then_asks(client, monkeypatch):
    monkeypatch.setattr(guess.asyncio, "sleep", AsyncMock())
    channel = Channel()
    await guess.memoryGame(channel, client)
    shown, game = channel.sent
    assert shown.deleted and len(shown.embed.fields) == 3
    assert [child.right for child in game.view.children].count(True) == 1
    right = next(i for i, child in enumerate(game.view.children) if child.right)
    column = int(game.embed.description.split("**Column ")[1][0])
    assert (
        shown.embed.fields[column - 1].value == f"`{game.view.children[right].emoji}`"
    )
    await press(client, game, 5, index=right)
    assert f"Which emote was in Column {column}?" in game.embed.description
    assert await mora(client.pool) == {5: game.view.reward}


# --- Emoji riddles ---

NAMES = {name: f"emoji-{name}" for name in ("Amber", "Bennett", "Chongyun", "Diluc", "Eula", "Fischl")}  # fmt: skip


@pytest.mark.parametrize("kind, title", [("hsr", "Galaxy *Emojified* Riddles | HSR Character"), ("genshin", "Teyvat *Emojified* Riddles | Genshin Character")])  # fmt: skip
async def test_riddle_pays_the_first_right_answer_once(
    client, monkeypatch, kind, title
):
    from commands.Events.games import quiz

    monkeypatch.setattr(quiz, "characters", AsyncMock(return_value=dict(NAMES)))
    channel = Channel()
    task = await started(channel, quiz.riddle(channel, client, kind))
    game = channel.last
    view = game.view
    assert game.embed.title == title
    assert game.embed.footer.text.endswith("• 5-minute time limit")
    labels = [child.label for child in view.children]
    assert len(set(labels)) == 5 and view.answer in labels
    assert NAMES[view.answer] in game.embed.description
    wrong = next(label for label in labels if label != view.answer)

    assert (await press(client, game, 5, label=wrong)).said == ["That is incorrect!"]
    assert (await press(client, game, 5, label=view.answer)).said == [
        "You have already answered!"
    ]
    await asyncio.gather(
        press(client, game, 6, label=view.answer),
        press(client, game, 7, label=view.answer),
    )
    await task
    assert await mora(client.pool) == {6: view.reward}
    assert f"answered `{view.answer}` and won" in game.embed.description
    assert button_styles(view) == {view.answer: discord.ButtonStyle.success}
    assert won(client, 5) == [{"participate_minigames": 1}]
    assert won(client, 7) == []


async def test_riddle_times_out_with_the_answer(client, monkeypatch):
    from commands.Events.games import quiz

    monkeypatch.setattr(quiz, "characters", AsyncMock(return_value=dict(NAMES)))
    channel = Channel()
    task = await started(channel, quiz.hsrEmojiRiddle(channel, client))
    view = channel.last.view
    await view.on_timeout()
    view.stop()
    await task
    assert channel.last.embed.title == "HSR Emoji Riddle - Time Out! ⌛"
    assert f"**Correct Answer:** `{view.answer}`" in channel.last.embed.description
    assert all(child.disabled for child in view.children)


async def test_riddle_reports_a_sheet_it_cannot_read(client, monkeypatch):
    from commands.Events.games import quiz

    monkeypatch.setattr(quiz, "characters", AsyncMock(return_value=503))
    client.fetch_user = AsyncMock()
    channel = Channel()
    await quiz.genshinEmojiRiddle(channel, client)
    assert channel.texts() == ["Event crashed: `Failed to fetch minigame data (HTTP 503)`"]  # fmt: skip
    client.fetch_user.return_value.send.assert_awaited_once()


# --- Eggwalk, Guess the Number, Currency Counting ---


async def test_eggwalk_pays_each_number_when_ten_is_reached(client):
    channel = Channel()
    lines = [(5 + n % 2, str(n)) for n in range(1, 11)]
    heard = typed(client, channel, (5, "hi"), *lines)
    await counting.eggWalk(channel, client)
    reward = int(channel.sent[0].embed.description.split("`")[1])
    assert await mora(client.pool) == {5: 5 * reward, 6: 5 * reward}
    assert channel.last.embed.title == "Eggwalk - Success!"
    assert "5 numbers" in channel.last.embed.description
    heard[0].add_reaction.assert_not_awaited()
    heard[1].add_reaction.assert_awaited_once_with(YES_EMOTE)
    assert won(client, 5)[0]["earn_mora"] == 5 * reward


@pytest.mark.parametrize("lines, reason", [
    ([(5, "1"), (6, "3")], "Wrong number. Next number should be `2`! Better luck next time!"),
    ([(5, "1"), (5, "2")], "<@5> did not alternate! Good luck next time!"),
])  # fmt: skip
async def test_eggwalk_ends_on_a_mistake_and_pays_nobody(client, lines, reason):
    channel = Channel()
    heard = typed(client, channel, *lines)
    await counting.eggWalk(channel, client)
    heard[-1].add_reaction.assert_awaited_once_with(NO_EMOTE)
    assert channel.last.embed.description == reason
    assert await mora(client.pool) == {}
    assert won(client, 5) == [{"participate_minigames": 1}]


async def test_eggwalk_times_out(client):
    channel = Channel()
    typed(client, channel, (5, "1"))
    await counting.eggWalk(channel, client)
    assert channel.sent[0].embed.title == "Eggwalk - Time Out!"
    assert await mora(client.pool) == {}


async def test_guess_the_number_pays_one_winner(client):
    channel = Channel()
    task = await started(channel, counting.guessTheNumber(channel, client))
    game = channel.last
    view = game.view
    assert [child.label for child in view.children] == [str(n) for n in range(1, 11)]
    wrong = 1 if view.target_number != 1 else 2
    await press(client, game, 5, label=str(wrong))
    missed = view.children[wrong - 1]
    assert missed.disabled and missed.style == discord.ButtonStyle.danger
    await asyncio.gather(
        press(client, game, 6, label=str(view.target_number)),
        press(client, game, 7, label=str(view.target_number)),
    )
    await task
    assert await mora(client.pool) == {6: view.reward}
    assert "🏆 <@6> " in game.embed.description
    assert game.embed.color == discord.Color.green()
    assert all(child.disabled for child in view.children)
    assert won(client, 5) == [{"participate_minigames": 1}]
    assert won(client, 6)[0]["win_minigames"] == 1


async def test_guess_the_number_times_out(client):
    channel = Channel()
    task = await started(channel, counting.guessTheNumber(channel, client))
    channel.last.view.stop()
    await task
    assert channel.last.embed.description.startswith("⏳ Was it really that hard")
    assert all(child.disabled for child in channel.last.view.children)


async def test_currency_counting_pays_the_right_count(client, monkeypatch):
    monkeypatch.setattr(counting.asyncio, "create_task", lambda coro: coro.close())
    channel = Channel()
    typed(client, channel)
    await counting.countingCurrency(channel, client)
    board = channel.sent[0].embed.description
    number = int(board.split("**Correct Count:** `")[1].split("`")[0])
    assert channel.sent[0].embed.title == "Currency Counting - Time Out! ⌛"

    channel = Channel()
    monkeypatch.setattr(counting.random, "random", lambda: 0)
    monkeypatch.setattr(counting.random, "choice", lambda options: options[0])
    heard = typed(client, channel, (5, "words"), (5, "3"), (6, "225"), (7, "225"))
    await counting.countingCurrency(channel, client)
    reward = int(channel.sent[0].embed.description.split("`")[-2])
    heard[1].add_reaction.assert_awaited_once_with(NO_EMOTE)
    heard[2].add_reaction.assert_awaited_once_with(YES_EMOTE)
    heard[3].add_reaction.assert_not_awaited()
    assert "<@6> " in channel.last.embed.description
    assert await mora(client.pool) == {6: reward}
    assert won(client, 5) == [{"participate_minigames": 1}]
    assert number >= 0


# --- Roll a Dice ---


async def test_dice_pays_the_closest_and_doubles_an_exact_roll(client, monkeypatch):
    from commands.Events.games import dice

    rolls = iter(
        [7, 5000, 3, 4, 1, 1, 6]
    )  # the target, the reward, then 5's two rolls, 6's two, 7's one
    monkeypatch.setattr(dice.random, "randint", lambda low, high: next(rolls))
    channel = Channel()
    await dice.rollADice(channel, client)
    game = channel.sent[0]
    view = game.view
    first = await press(client, game, 5, label="Roll Dice")
    assert "Click again to roll your second dice!" in first.said[0].description
    second = await press(client, game, 5, label="Roll Dice")
    assert "Your total: **7**" in second.said[0].description
    third = await press(client, game, 5, label="Roll Dice")
    assert third.said == [f"{NO_EMOTE} You've already rolled twice!"]
    await press(client, game, 6, label="Roll Dice")
    await press(client, game, 6, label="Roll Dice")
    await press(client, game, 7, label="Roll Dice")

    await view.on_timeout()
    assert game.view is None
    assert await mora(client.pool) == {5: view.reward * 2}
    assert channel.last.embed.title == "Roll a Dice 🎲 - Results"
    assert "(Exact match! Rolled: 7)" in channel.last.embed.description
    assert won(client, 6) == [{"participate_minigames": 1}]
    assert won(client, 7) == []


async def test_dice_with_no_rolls_says_so(client):
    from commands.Events.games import dice

    channel = Channel()
    await dice.rollADice(channel, client)
    await channel.last.view.on_timeout()
    assert channel.last.embed.description == "No one rolled the dice in time!"
    assert channel.last.view is None


# --- Hangman ---


async def hangman_game(client, monkeypatch, word="aba"):
    from commands.Events.games import hangman

    monkeypatch.setattr(hangman, "choose_word", lambda: word)
    channel = Channel()
    task = await started(channel, hangman.hangmanGame(channel, client))
    return channel, task


async def test_hangman_pays_letters_and_the_finisher(client, monkeypatch):
    channel, task = await hangman_game(client, monkeypatch)
    game = channel.last
    view = game.view
    assert len(view.children) == 25 and view.tries == 6
    await press(client, game, 5, label="A")
    assert game.embed.fields[0].value == "`a_a`"
    await press(client, game, 6, label="C")
    assert view.tries == 5 and button_styles(view) == {
        "A": discord.ButtonStyle.success,
        "C": discord.ButtonStyle.danger,
    }
    await asyncio.gather(press(client, game, 6, label="B"), press(client, game, 7, label="D"))  # fmt: skip
    await task
    assert await mora(client.pool) == {5: 3000, 6: 1500 + 3000}
    assert (
        "Everyone got" in game.embed.description
        and "**`1500`**" in game.embed.description
    )
    assert "<@6> " in game.embed.description
    assert game.embed.fields[0].value == "`aba`"
    assert all(child.disabled for child in view.children)
    assert won(client, 6)[0]["win_minigames"] == 1
    assert won(client, 5) == [{"participate_minigames": 1}]
    assert won(client, 7) == []


async def test_hangman_ends_when_the_tries_run_out(client, monkeypatch):
    channel, task = await hangman_game(client, monkeypatch)
    game = channel.last
    await press(client, game, 5, label="A")
    for letter in "CDEFGH":
        await press(client, game, 6, label=letter)
    await press(client, game, 6, label="B")
    await task
    assert game.embed.description == "Game over! The word was `aba`. Better luck next time!"  # fmt: skip
    assert game.embed.color == discord.Color.red()
    assert await mora(client.pool) == {5: 3000}


async def test_hangman_times_out(client, monkeypatch):
    channel, task = await hangman_game(client, monkeypatch)
    channel.last.view.stop()
    await task
    assert channel.last.embed.title == "Hangman - Time Out! ⌛"
    assert all(child.disabled for child in channel.last.view.children)


def test_hangman_words_fit_the_buttons():
    from commands.Events.games import hangman

    for _ in range(50):
        assert set(hangman.choose_word().upper()) <= set(hangman.LETTERS)


# --- Typing races ---


@pytest.fixture
def uploads(client, monkeypatch):
    """Stands in for the channel pictures are uploaded to; gives the texts that were drawn."""
    from commands.Events.games import typed as races

    drawn = []
    monkeypatch.setattr(races, "draw", lambda text, background: drawn.append(text))
    monkeypatch.setattr(races.discord, "File", MagicMock())
    upload = MagicMock(attachments=[MagicMock(proxy_url="https://cdn/picture.png")])
    client.get_channel.return_value.send = AsyncMock(return_value=upload)
    return drawn


async def test_reverse_quicktype_pays_the_first_right_message(
    client, uploads, monkeypatch
):
    from commands.Events.games import typed as races

    digits = iter([4000, 1, 2, 3, 4, 5, 6, 7, 8])
    monkeypatch.setattr(races.random, "randint", lambda low, high: next(digits))
    monkeypatch.setattr(common.random, "randint", lambda low, high: next(digits))
    channel = Channel()
    heard = typed(client, channel, (5, "hello"), (5, "87654320"), (6, " 87654321 "), (7, "87654321"))  # fmt: skip
    await races.reverseQuicktype(channel, client)
    assert uploads == ["12345678"]
    game = channel.sent[0]
    assert game.embed.image.url == "https://cdn/picture.png"
    assert (
        game.embed.description.startswith("<@6> ") and "won" in game.embed.description
    )
    heard[0].add_reaction.assert_not_awaited()
    heard[1].add_reaction.assert_awaited_once_with(NO_EMOTE)
    heard[2].add_reaction.assert_awaited_once_with(YES_EMOTE)
    heard[3].add_reaction.assert_not_awaited()
    assert await mora(client.pool) == {6: 4000}
    assert won(client, 5) == [{"participate_minigames": 1}]


async def test_reverse_quicktype_times_out_with_the_answer(client, uploads):
    from commands.Events.games import typed as races

    channel = Channel()
    typed(client, channel)
    await races.reverseQuicktype(channel, client)
    shown = channel.sent[0].embed
    assert shown.title == "Reverse Quicktype - Time Out! ⌛"
    assert f"**Reversed Answer:** `{uploads[0][::-1]}`" in shown.description


async def test_quicktype_wants_the_exact_phrase(client, uploads, monkeypatch):
    import sys

    from commands.Events.games import typed as races

    generator = MagicMock()
    generator.DocumentGenerator.return_value.sentence.return_value = "The quick brown fox jumps over the dog"  # fmt: skip
    monkeypatch.setitem(sys.modules, "essential_generators", generator)
    channel = Channel()
    heard = typed(client, channel, (5, "The quick brown fox jumpz ove"), (6, "The quick brown fox jumps"))  # fmt: skip
    await races.quicktype(channel, client)
    assert uploads == ["The quick brown fox jumps"]
    heard[0].add_reaction.assert_awaited_once_with(NO_EMOTE)
    assert list(await mora(client.pool)) == [6]
    assert channel.sent[0].embed.title == "Quicktype Racer"


async def test_unscramble_counts_a_wrong_order_as_taking_part(client, monkeypatch):
    from commands.Events.games import typed as races

    monkeypatch.setattr(races.random, "choice", lambda words: "Stream ")
    channel = Channel()
    heard = typed(client, channel, (5, "master"), (6, "nope"), (7, "STREAM"))
    await races.unscrambleWords(channel, client)
    scrambled = channel.sent[0].embed.description.split("**Scrambled:** `")[1][:6]
    assert sorted(scrambled) == sorted("stream") and scrambled != "stream"
    heard[0].add_reaction.assert_awaited_once_with(NO_EMOTE)
    heard[1].add_reaction.assert_not_awaited()
    assert "**Correct:** `stream`" in channel.sent[0].embed.description
    assert list(await mora(client.pool)) == [7]
    assert won(client, 5) == [{"participate_minigames": 1}]


def test_draw_gives_the_picture_in_memory(tmp_path, monkeypatch):
    from PIL import Image, ImageFont

    from commands.Events.games import typed as races

    default = ImageFont.load_default()
    Image.new("RGB", (600, 200), "white").save(tmp_path / "background.png")
    monkeypatch.setattr(races.ImageFont, "truetype", lambda *font: default)  # fmt: skip
    picture = races.draw("12345678", str(tmp_path / "background.png"))
    assert list(tmp_path.iterdir()) == [tmp_path / "background.png"]
    assert picture.read(8) == b"\x89PNG\r\n\x1a\n"


# --- Watermelon and ice cream ---


async def test_watermelon_goes_to_one_member(client):
    from commands.Events.games import pickup

    channel = Channel()
    await pickup.pickUpTheWatermelon(channel, client)
    game = channel.last
    assert str(game.view.pick.emoji) == "🍉"
    await asyncio.gather(press(client, game, 5, index=0), press(client, game, 6, index=0))  # fmt: skip
    assert await mora(client.pool) == {5: game.view.reward}
    assert "<@5> " in game.embed.description and "picked up the `🍉`" in game.embed.description  # fmt: skip
    assert game.view.pick.disabled and game.content == ""
    assert won(client, 5)[0]["win_minigames"] == 1


@pytest.mark.parametrize("toss, reason, text, sign", [
    ("pos", None, "enjoyed the `🍦` while earning", 1),
    ("neg", "melt", "The ice cream melted and", -1),
    ("neg", "catching a cold", "for catching a cold.", -1),
])  # fmt: skip
async def test_ice_cream_pays_or_charges(client, monkeypatch, toss, reason, text, sign):
    from commands.Events.games import pickup

    monkeypatch.setattr(pickup.random, "choice", lambda options: toss if "pos" in options else reason)  # fmt: skip
    monkeypatch.setattr(pickup.random, "randint", lambda low, high: low)
    channel = Channel()
    await pickup.pickUpIceCream(channel, client)
    game = channel.last
    await press(client, game, 5, index=0)
    assert text in game.embed.description
    assert await mora(client.pool) == {5: sign * 3000}
    assert ("win_minigames" in won(client, 5)[0]) == (sign > 0)


async def test_pickup_expires(client):
    from commands.Events.games import pickup

    channel = Channel()
    await pickup.pickUpIceCream(channel, client)
    await channel.last.view.on_timeout()
    assert channel.last.embed.description == "⏳ The ice cream melted before anyone could eat it!"  # fmt: skip
    assert channel.last.view.pick.disabled
