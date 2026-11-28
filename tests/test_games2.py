import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from commands.Events.config import NO_EMOTE
from commands.Events.games import duel
from tests.games import (
    GUILD,
    Channel,
    Message,
    Press,
    client,
    member,
    mora,
    press,
    started,
    won,
)

# --- Split or Steal ---


async def duel_game(client, game, authors=(5, 6)):
    channel = Channel([member(uid) for uid in authors])
    await game(channel, client)
    return channel, channel.last


async def test_split_or_steal_needs_two_members(client):
    channel, said = await duel_game(client, duel.splitOrSteal, (5, 5))
    assert said.embed.description == f"{NO_EMOTE} Not enough unique recent messaging users for the game."  # fmt: skip


async def test_both_split_share_the_reward(client):
    channel, game = await duel_game(client, duel.splitOrSteal)
    reward = game.view.reward
    assert game.content == "<@5> vs <@6>"
    assert (await press(client, game, 9, label="Split")).said == ["You're not part of this game!"]  # fmt: skip
    first = await press(client, game, 5, label="Split")
    assert first.said == ["Waiting for <@6>  to choose..."]
    assert (await press(client, game, 5, label="Steal")).said == ["You can't change your selection!"]  # fmt: skip
    second = await press(client, game, 6, label="Split")
    assert second.deferred and game.view is None
    assert await mora(client.pool) == {5: reward // 2, 6: reward // 2}
    assert channel.last.embed.title == "Split Success! 🎉"
    assert f"You each won" in channel.last.embed.description
    assert won(client, 5)[0]["win_1v1_minigames"] == 1


async def test_one_steal_takes_everything(client):
    channel, game = await duel_game(client, duel.splitOrSteal)
    reward = game.view.reward
    await press(client, game, 5, label="Split")
    await press(client, game, 6, label="Steal")
    assert await mora(client.pool) == {6: reward}
    assert channel.last.embed.title == "It's a Steal! 💰"
    assert won(client, 5) == [{"participate_minigames": 1}]
    assert won(client, 6)[0]["win_minigames"] == 1


async def test_both_steal_get_nothing(client):
    channel, game = await duel_game(client, duel.splitOrSteal)
    await press(client, game, 5, label="Steal")
    await press(client, game, 6, label="Steal")
    assert await mora(client.pool) == {}
    assert "chose Steal. No money for y'all." in channel.last.embed.description
    assert won(client, 5) == won(client, 6) == [{"participate_minigames": 1}]


async def test_duel_times_out(client):
    channel, game = await duel_game(client, duel.splitOrSteal)
    await game.view.on_timeout()
    assert game.embed.description == "🕒 This game session has timed out" and game.view is None  # fmt: skip
    channel, game = await duel_game(client, duel.rockPaperScissors)
    await game.view.on_timeout()
    assert game.embed.description == "⌛ This game session has timed out"


# --- Rock Paper Scissors ---


async def test_rps_needs_two_members(client):
    channel, said = await duel_game(client, duel.rockPaperScissors, (5,))
    assert said.content == f"{NO_EMOTE} Not enough players for the game."


@pytest.mark.parametrize("first, second, winner", [("Rock", "Scissors", 5), ("Rock", "Paper", 6), ("Scissors", "Paper", 5)])  # fmt: skip
async def test_rps_pays_the_winner(client, first, second, winner):
    channel, game = await duel_game(client, duel.rockPaperScissors)
    reward = game.view.reward
    quiet = await press(client, game, 5, label=first)
    assert quiet.deferred and quiet.said == []
    assert (await press(client, game, 5, label=second)).said == ["You already made your choice!"]  # fmt: skip
    await press(client, game, 6, label=second)
    assert await mora(client.pool) == {winner: reward}
    assert channel.last.embed.description.startswith(f"### <@{winner}> ")
    assert f"-# <@5> chose {duel.RPS_EMOJIS[first]}" in channel.last.embed.description
    assert won(client, winner)[0]["win_1v1_minigames"] == 1
    assert won(client, 11 - winner) == [{"participate_minigames": 1}]


async def test_rps_tie_pays_both_a_seventh_without_a_win(client):
    channel, game = await duel_game(client, duel.rockPaperScissors)
    reward = game.view.reward
    await press(client, game, 5, label="Paper")
    await press(client, game, 6, label="Paper")
    assert await mora(client.pool) == {5: reward // 7, 6: reward // 7}
    assert channel.last.embed.title == "Both of you chose 📄!"
    assert channel.last.embed.description.startswith("It's a tie! <@5> earned")
    assert "win_minigames" not in won(client, 5)[0]


# --- Bank Heist ---


async def test_heist_pays_every_click_and_counts_the_top_member(client, monkeypatch):
    from commands.Events.games import heist

    monkeypatch.setattr(heist, "SECONDS", 0.2)
    monkeypatch.setattr(heist.random, "randint", lambda low, high: 500)
    channel = Channel()
    await heist.bankHeist(channel, client)
    game = channel.last
    assert game.embed.title == "Bank Heist! 💰 "
    assert game.embed.fields[0].value == "No participants yet"
    for uid in (5, 6, 5):
        await press(client, game, uid, label="Click to Steal")
    assert game.embed.fields[0].name == "Leaderboard (2 participants)"
    assert game.embed.fields[0].value.startswith("-# <@5>: 2 clicks → ")
    await asyncio.sleep(0.5)
    assert game.view is None and game.embed.title == "⏳ Bank Heist - Finished!"
    assert game.embed.fields[1].value.startswith("1. <@5>: ")
    assert await mora(client.pool) == {5: 1000, 6: 500}
    assert channel.last.embed.title == "Rewards Distributed"
    assert "win_minigames" in won(client, 5)[0]
    assert "win_minigames" not in won(client, 6)[0]


async def test_heist_with_nobody_ends_quietly(client, monkeypatch):
    from commands.Events.games import heist

    monkeypatch.setattr(heist, "SECONDS", 0)
    channel = Channel()
    await heist.bankHeist(channel, client)
    game = channel.last
    await asyncio.sleep(0.2)
    assert game.embed.fields[1].value == "No participants"
    assert await mora(client.pool) == {}


# --- Grand Auction House ---


async def give(pool, uid: int, amount: int) -> None:
    await pool.execute(
        "INSERT INTO minigame_mora (uid, gid, cid, timestamp, count) VALUES ($1, $2, 30, 1, $3)",
        uid,
        GUILD,
        amount,
    )


async def bid(client, game, uid: int, amount: str):
    """Opens the bid form as a member and sends it; gives how the form was answered."""
    opened = await press(client, game, uid, label="Place Bid")
    if opened.modal is None:
        return opened
    opened.modal.bid_amount._value = amount
    sent = Press(client, game, uid)
    await opened.modal.on_submit(sent)
    return sent


async def auction_run(client, monkeypatch, box: int):
    from commands.Events.games import auction

    monkeypatch.setattr(auction, "SECONDS", 0.5)
    monkeypatch.setattr(auction.random, "randint", lambda low, high: box)
    channel = Channel()
    task = await started(channel, auction.grandAuctionHouse(channel, client))
    return channel, channel.last, task


async def test_auction_pays_the_closest_bid_under_the_box(client, monkeypatch):
    for uid in (5, 6, 7):
        await give(client.pool, uid, 20000)
    channel, game, task = await auction_run(client, monkeypatch, 9000)
    assert game.embed.title == "Grand Auction House 🏛️"
    assert (await bid(client, game, 5, "abcd")).said[
        0
    ].title == f"Invalid Bid {NO_EMOTE}"
    assert (await bid(client, game, 5, "999")).said[
        0
    ].title == f"Invalid Bid {NO_EMOTE}"
    assert (await bid(client, game, 8, "5000")).said[
        0
    ].title == f"Bid Failed {NO_EMOTE}"
    placed = await bid(client, game, 5, "8000")
    assert placed.said[0].description.startswith("You've bid")
    assert channel.last.embed.description == "📈 Total bids received: **1**"
    assert (await bid(client, game, 5, "8500")).said[0].description == f"{NO_EMOTE} You've already bid!"  # fmt: skip
    await bid(client, game, 6, "7000")
    await bid(client, game, 7, "9500")
    await task
    assert game.view is None and game.embed.description.endswith(
        "**Auction Closed!** 🔒"
    )
    assert "Auction ended <t:" in game.embed.description
    assert "### 🏆 Winner: <@5>" in channel.last.embed.description
    assert await mora(client.pool) == {5: 21000, 6: 20000, 7: 20000}
    assert "win_minigames" in won(client, 5)[0]
    assert won(client, 6) == won(client, 7) == [{"participate_minigames": 1}]


async def test_auction_everyone_overbids(client, monkeypatch):
    await give(client.pool, 5, 20000)
    channel, game, task = await auction_run(client, monkeypatch, 5000)
    await bid(client, game, 5, "6000")
    await task
    assert channel.last.embed.title == "Auction Failed! 🏚️"
    assert await mora(client.pool) == {5: 20000}
    assert won(client, 5) == [{"participate_minigames": 1}]


async def test_auction_without_bids_and_bids_after_close(client, monkeypatch):
    from commands.Events.games import auction

    await give(client.pool, 5, 20000)
    channel, game, task = await auction_run(client, monkeypatch, 5000)
    view = game.view
    await task
    assert channel.last.embed.description == f"{NO_EMOTE} Auction ended with no bids."
    late = auction.BidModal(view)
    late.bid_amount._value = "5000"
    sent = Press(client, game, 5)
    await late.on_submit(sent)
    assert sent.said[0].description == "This auction has closed!" and view.bids == {}


# --- Double or Keep ---


async def choose(client, game, uid: int, chosen: int) -> Press:
    """Picks a member in the round's menu as a member."""
    select = game.view.children[0]
    select._values = [str(chosen)]
    interaction = Press(client, game, uid)
    await select.callback(interaction)
    return interaction


async def test_double_or_keep_needs_two_members(client):
    from commands.Events.games import double

    channel = Channel([member(5)])
    await double.doubleOrKeep(channel, client)
    assert channel.last.embed.description == f"{NO_EMOTE} Not enough unique recent messaging users for the game."  # fmt: skip


async def test_double_or_keep_claimed_at_once(client):
    from commands.Events.games import double

    channel = Channel([member(5), member(6), member(7)])
    await double.doubleOrKeep(channel, client)
    game = channel.last
    reward = game.view.reward
    assert (
        game.content == "<@5>" and "**(5 times remaining)**" in game.embed.description
    )
    assert [option.value for option in game.view.children[0].options] == ["6", "7"]
    assert (await press(client, game, 6, label="Claim Reward")).said == ["You can't claim the reward for someone else!"]  # fmt: skip
    assert (await choose(client, game, 6, 7)).said == ["You're not allowed to make this choice."]  # fmt: skip
    first, second = await asyncio.gather(
        press(client, game, 5, label="Claim Reward"),
        press(client, game, 5, label="Claim Reward"),
    )
    assert second.said == [double.EXPIRED]
    assert game.deleted and await mora(client.pool) == {5: reward}
    assert channel.last.embed.description.startswith(
        "<@5>  has claimed the current reward of"
    )
    assert channel.last.embed.footer.text is None


async def test_double_or_keep_doubles_to_the_end(client):
    from commands.Events.games import double

    channel = Channel([member(5), member(6)])
    await double.doubleOrKeep(channel, client)
    reward = channel.last.view.reward
    turn, other = 5, 6
    for left in (4, 3, 2, 1):
        game = channel.last
        await choose(client, game, turn, other)
        turn, other = other, turn
        assert game.deleted and channel.last.content == f"<@{turn}>"
        assert f"**({left} times remaining)**" in channel.last.embed.description
        assert channel.last.embed.footer.text == f"Last doubled by member{other}"
    await choose(client, channel.last, turn, other)
    assert await mora(client.pool) == {other: reward * 32}
    assert "receives the final reward of" in channel.last.embed.description
    assert "win_minigames" in won(client, other)[0]
    assert won(client, turn) == [{"participate_minigames": 1}]


async def test_double_or_keep_round_from_before_a_restart_says_expired(client):
    from commands.Events.games import double

    channel = Channel()
    game = await channel.send(view=double.UserSelectView())
    assert [child.custom_id for child in game.view.children] == ["userSelectEvent", "claim_reward_"]  # fmt: skip
    assert (await press(client, game, 5, label="Claim Reward")).said == [double.EXPIRED]


# --- Two Truths and a Lie ---


async def test_two_truths_needs_a_member(client):
    from commands.Events.games import truths

    channel = Channel([member(2, bot=True)])
    await truths.twoTruthsAndALie(channel, client)
    assert "Not enough unique users for the game." in channel.last.embed.description


async def test_two_truths_round(client, monkeypatch):
    from commands.Events.games import truths

    monkeypatch.setattr(truths.random, "shuffle", lambda items: items.reverse())
    channel = Channel([member(5)])
    await truths.twoTruthsAndALie(channel, client)
    seat = channel.last
    reward = seat.view.reward
    assert seat.content == "<@5>, you have been put in the hot seat!"
    assert (await press(client, seat, 6, index=0)).said == [
        "You can't click this button!"
    ]
    opened = await press(client, seat, 5, index=0)
    assert seat.embed.description.endswith(
        "> *<@5>  is entering their truths and lies...*"
    )
    form = opened.modal
    form.truth1._value, form.truth2._value, form.lie._value = "one", "two", "fib"
    sent = Press(client, seat, 5)
    await form.on_submit(sent)
    again = Press(client, seat, 5)
    await form.on_submit(again)
    assert again.said == [f"{NO_EMOTE} This game session has expired!"]
    assert seat.view is None and "is entering" not in seat.embed.description
    game = channel.last
    assert '"fib"\n' in game.embed.description and game.embed.description.endswith(
        '"one"'
    )
    assert (await press(client, game, 5, index=0)).said == ["You can't answer your own question smh"]  # fmt: skip
    await press(client, game, 6, index=1)
    assert (await press(client, game, 6, index=0)).said == [f"{NO_EMOTE} You have guessed once already. No second try!"]  # fmt: skip
    await press(client, game, 7, index=0)
    assert await mora(client.pool) == {7: reward}
    assert "🏆 <@7>  chose" in game.embed.description
    assert (
        game.embed.footer.text == "Now y'all know a little bit more about each other."
    )
    assert won(client, 5) == [{"participate_minigames": 1}]


# --- Who Said That ---


async def phrase(client, game, uid: int, text: str) -> Press:
    """Sends a phrase through the form as a member; gives how the button or form was answered."""
    opened = await press(client, game, uid, label="Submit a Phrase")
    if opened.modal is None:
        return opened
    opened.modal.phrase_input._value = text
    sent = Press(client, game, uid)
    await opened.modal.on_submit(sent)
    return sent


async def who_said(client, monkeypatch):
    from commands.Events.games import whosaid

    monkeypatch.setattr(whosaid, "SUBMISSION_WINDOW", 3600)
    monkeypatch.setattr(whosaid.random, "choice", lambda items: items[0])
    monkeypatch.setattr(whosaid.random, "shuffle", lambda items: None)
    channel = Channel()
    await whosaid.whoSaidIt(channel, client)
    return whosaid, channel.last, channel.last.view


async def test_who_said_that_with_nobody_times_out(client, monkeypatch):
    whosaid, game, view = await who_said(client, monkeypatch)
    assert game.embed.description.endswith("**Submissions:** `0`")
    await view.time_up()
    assert game.embed.description == whosaid.TIMED_OUT and game.view is None
    assert (await phrase(client, Message(game.channel, view=view), 5, "x")).said == [whosaid.EXPIRED]  # fmt: skip


async def test_who_said_that_with_one_phrase_pays_by_default(client, monkeypatch):
    whosaid, game, view = await who_said(client, monkeypatch)
    await phrase(client, game, 5, "I like tea")
    assert (await phrase(client, game, 5, "again")).said == [whosaid.SUBMITTED]
    await view.time_up()
    await view.time_up()
    assert await mora(client.pool) == {5: view.reward}
    assert "they win" in game.embed.description and game.view is None


async def test_who_said_that_guess_round_after_five_phrases(client, monkeypatch):
    whosaid, game, view = await who_said(client, monkeypatch)
    for uid in (5, 6, 7, 8):
        await phrase(client, game, uid, f"phrase {uid}")
    late = await press(client, game, 9, label="Submit a Phrase")
    await phrase(client, game, 4, "phrase 4")
    late.modal.phrase_input._value = "too late"
    refused = Press(client, game, 9)
    await late.modal.on_submit(refused)
    assert refused.said == [whosaid.EXPIRED]
    assert "> phrase 5\n" in game.embed.description
    assert [child.label for child in game.view.children] == [f"member{uid}" for uid in (5, 6, 7, 8, 4)]  # fmt: skip
    assert (
        "your phrase is chosen"
        in (await press(client, game, 5, label="member5")).said[0]
    )
    await press(client, game, 6, label="member7")
    await press(client, game, 7, label="member5")
    assert await mora(client.pool) == {7: view.reward}
    assert "🏆 <@7>  guessed **member5** correctly" in game.embed.description
    await view.time_up()
    assert await mora(client.pool) == {7: view.reward}


# --- Group Blackjack ---


def card(rank: str) -> tuple:
    return (rank, "♠")


async def table(client, monkeypatch, player, dealer, draws=()):
    """Opens a table whose next game deals these ranks; gives the lobby message and the member's press."""
    from commands.Events.games import blackjack

    dealt = [card(player[0]), card(dealer[0]), (player[1], "♥"), (dealer[1], "♥")]
    coming = [(rank, "♦") for rank in draws]
    monkeypatch.setattr(blackjack.random, "shuffle", lambda deck: deck.__setitem__(slice(0, 4), dealt))  # fmt: skip
    monkeypatch.setattr(blackjack.random, "choice", lambda cards: coming.pop(0))
    channel = Channel()
    lobby = blackjack.EventBlackjackLobbyView(client, channel, 4000)
    lobby.game_msg = await channel.send(view=lobby)
    return lobby, await press(client, lobby.game_msg, 5, label="Play Blackjack")


def test_hand_value_counts_aces_down():
    from commands.Events.games.blackjack import hand_value, shown

    assert hand_value([card("A"), card("K")]) == 21
    assert hand_value([card("A"), card("A"), card("9")]) == 21
    assert hand_value([card("A"), card("9"), card("5")]) == 15
    assert shown([card("A"), card("10")], hide_first=True) == "`??` `10♠️`"


async def test_blackjack_one_game_each(client, monkeypatch):
    lobby, dealt = await table(client, monkeypatch, "Q9", "K7")
    embed = dealt.said[0]
    assert embed.title == "🃏 Blackjack — Your Turn!"
    assert embed.fields[0].value == "`??` `7♥️` (Value: ?)"
    assert embed.fields[1].value == "`Q♠️` `9♥️` (Value: 19)"
    assert lobby.game_msg.embed.footer.text == "1 player playing so far!"
    again = await press(client, lobby.game_msg, 5, label="Play Blackjack")
    assert again.said == [f"{NO_EMOTE} You already have an active game!"]
    game = dealt.reply
    assert (await press(client, game, 6, label="Stand")).said == [
        "This isn't your game!"
    ]
    await asyncio.gather(press(client, game, 5, label="Stand"), press(client, game, 5, label="Stand"))  # fmt: skip
    assert game.embed.title == "🎉 You Win!" and game.view.children == []
    assert await mora(client.pool) == {5: 4000}
    again = await press(client, lobby.game_msg, 5, label="Play Blackjack")
    assert again.said == [f"{NO_EMOTE} You've already played your game for this event!"]
    lobby.deadline = 0
    late = await press(client, lobby.game_msg, 6, label="Play Blackjack")
    assert late.said == [f"{NO_EMOTE} The blackjack table is closed! No new games can be started."]  # fmt: skip


@pytest.mark.parametrize(
    "player, dealer, draws, label, title, paid",
    [
        ("98", "97", ["K"], "Hit", "💥 Bust!", 0),
        ("98", "97", ["4", "A"], "Hit", "🎉 You Win!", 4000),
        ("98", "K9", [], "Stand", "💔 You Lose!", 0),
        ("98", "K7", [], "Stand", "🤝 Push!", 1000),
        ("98", "K6", ["K"], "Stand", "🎉 You Win!", 4000),
        ("56", "K7", ["K"], "Double Down", "🎉 You Win!", 8000),
        ("98", "K7", ["K"], "Double Down", "💥 Bust!", 0),
        ("98", "K7", [], "Surrender", "🏳️ Surrendered", 1000),
    ],
)
async def test_blackjack_moves(client, monkeypatch, player, dealer, draws, label, title, paid):  # fmt: skip
    lobby, dealt = await table(client, monkeypatch, player, dealer, draws)
    await press(client, dealt.reply, 5, label=label)
    assert dealt.reply.embed.title == title
    assert await mora(client.pool) == ({5: paid} if paid else {})
    assert (
        lobby.active_players == set() and "??" not in dealt.reply.embed.fields[0].value
    )


async def test_blackjack_hit_keeps_the_game_going(client, monkeypatch):
    lobby, dealt = await table(client, monkeypatch, "23", "K7", ["4"])
    await press(client, dealt.reply, 5, label="Hit")
    assert dealt.reply.embed.title == "🎲 Blackjack — Your Turn"
    assert dealt.reply.embed.fields[1].value.endswith("(Value: 9)")
    await dealt.reply.view.on_timeout()
    assert (
        dealt.reply.embed.title == "⏰ Game Timeout!" and lobby.active_players == set()
    )


@pytest.mark.parametrize(
    "player, dealer, title, paid",
    [
        ("AK", "K7", "🎰 Natural Blackjack!", 6000),
        ("AK", "AQ", "🤝 Push!", 0),
        ("98", "AQ", "💔 Dealer Blackjack!", 0),
    ],
)
async def test_blackjack_naturals_settle_at_once(client, monkeypatch, player, dealer, title, paid):  # fmt: skip
    lobby, dealt = await table(client, monkeypatch, player, dealer)
    assert dealt.said[0].title == title and dealt.reply.view is None
    assert await mora(client.pool) == ({5: paid} if paid else {})
    assert lobby.active_players == set()


async def test_blackjack_table_closes_and_counts_everyone(client, monkeypatch):
    from types import SimpleNamespace

    from commands.Events.games import blackjack

    channel = Channel()
    gate = asyncio.Event()
    monkeypatch.setattr(blackjack, "asyncio", SimpleNamespace(sleep=lambda seconds: gate.wait()))  # fmt: skip
    task = await started(channel, blackjack.groupBlackjack(channel, client))
    game = channel.last
    assert game.embed.title == "🃏 Group Blackjack Event!"
    assert game.embed.footer.text == "Hit, Stand, Double Down or Surrender!"
    await press(client, game, 5, label="Play Blackjack")
    gate.set()
    await task
    assert game.embed.title == "🃏 Group Blackjack — Table Closed"
    assert "**1** player participated!" in game.embed.description
    assert game.view.children[0].disabled
    assert {"participate_minigames": 1} in won(client, 5)
