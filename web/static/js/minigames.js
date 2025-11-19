
const allEmojis = ["😄", "😊", "😃", "😉", "😍", "😘", "😚", "😗", "😙", "😜", "😝", "😛", "🤑", "🤓", "😎", "🤗", "🙂", "🤔", "😐", "😑", "😶", "🙄", "😏", "😒", "🤥", "😌", "😔", "😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤧", "😢", "😭", "😰", "😥", "😓", "😈", "👿", "👹", "👺", "💩", "👻", "💀", "👽", "🤖", "🎃", "🎉", "🌟", "🔥", "❤️", "💙", "💜", "💛", "💚", "🖤", "💖", "💗", "💓", "💕", "💞", "💘", "💝", "💌", "💍", "💎", "🎀", "🌈", "👍", "👎", "👌", "✌", "🤞", "🤟", "🤘", "👏", "🙌", "🤲", "💪", "🙏", "👊", "🤛", "🤜", "💅", "👀", "👁", "👅", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐷", "🐸", "🐵", "🦄", "🐉", "🐲", "🐍", "🦎", "🐢", "🍕", "🌺", "📚", "⚽", "🎵", "🍔", "🍦", "🎂", "🎁", "🎈", "🎨", "🚀", "⌛", "💡", "🎮", "📷", "📱", "💻", "⭐", "🌙", "🍎", "🍉", "🍇", "🍓", "🥑", "🍩", "🥨", "🥗", "🍿", "🍰", "🚗", "🚕", "🚙", "🚌", "🚎", "🚜", "🚲", "✈", "🚁", "🛳"];

let gameState = {
    emojis: [],
    chosenColumn: 0,
    chosenEmote: ""
};

function getRandomEmojis(count) {
    const shuffled = [...allEmojis].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, count);
}

function startMemoryGame() {
    document.getElementById('minigameInitial').style.display = 'none';
    document.getElementById('minigameButton').style.display = 'none';
    
    const display = document.getElementById('minigameDisplay');
    display.style.display = 'block';
    
    gameState.emojis = getRandomEmojis(3);
    gameState.chosenColumn = Math.floor(Math.random() * 3) + 1;
    gameState.chosenEmote = gameState.emojis[gameState.chosenColumn - 1];
    
    const embed = document.getElementById('minigameEmbed');
    embed.style.display = "block";
    embed.innerHTML = `
    <div class="discord-embed-title">Memory Game</div>
    <div class="discord-embed-description">
        Remember the following order of emotes. You'll be asked to recall which column an emoji is from.
    </div>
    <div class="minigame-columns">
        <div class="minigame-column">
        <span class="emoji-large">${gameState.emojis[0]}</span>
        <strong>Column 1</strong>
        </div>
        <div class="minigame-column">
        <span class="emoji-large">${gameState.emojis[1]}</span>
        <strong>Column 2</strong>
        </div>
        <div class="minigame-column">
        <span class="emoji-large">${gameState.emojis[2]}</span>
        <strong>Column 3</strong>
        </div>
    </div>
    `;
    
    document.getElementById('minigameControls').innerHTML = '';
    setTimeout(showMemoryQuestion, 4000);
}

function showMemoryQuestion() {
    const embed = document.getElementById('minigameEmbed');
    embed.innerHTML = `
    <div class="discord-embed-title">Memory Game</div>
    <div class="discord-embed-description">
        Now, which of the following emote was in <strong>Column ${gameState.chosenColumn}</strong>?
    </div>
    `;
    
    const controls = document.getElementById('minigameControls');
    controls.innerHTML = '';
    
    const shuffledEmojis = [...gameState.emojis].sort(() => 0.5 - Math.random());
    
    shuffledEmojis.forEach(emoji => {
    const button = document.createElement('button');
    button.className = 'discord-button';
    button.innerHTML = emoji;
    button.style.fontSize = '24px';
    button.style.width = '50px';
    button.style.height = '50px';
    button.style.marginRight = '5px';
    button.onclick = () => checkMemoryAnswer(emoji);
    controls.appendChild(button);
    });
}

function checkMemoryAnswer(selectedEmoji) {
    const isCorrect = selectedEmoji === gameState.chosenEmote;
    const reward = isCorrect ? Math.floor(Math.random() * 2001) + 3000 : 0;
    
    const embed = document.getElementById('minigameEmbed');
    const controls = document.getElementById('minigameControls');
    
    if (isCorrect) {
    embed.innerHTML = `
        <div class="discord-embed-title">Memory Game - Success! 🎉</div>
        <div class="discord-embed-description">
        ✅ <span class="mention">@Oz</span> guessed correctly and earned <strong>${reward.toLocaleString()}</strong> Mora!
        </div>
        <div style="text-align: center; margin-top: 16px; font-size: 48px;">
        ${selectedEmoji}
        </div>
    `;
    } else {
    embed.innerHTML = `
        <div class="discord-embed-title">Memory Game - Try Again 😢</div>
        <div class="discord-embed-description">
        ❌ The correct emoji was ${gameState.chosenEmote} (Column ${gameState.chosenColumn}). Better luck next time!
        </div>
        <div style="text-align: center; margin-top: 16px; font-size: 48px;">
        ${gameState.chosenEmote}
        </div>
    `;
    }
    
    controls.innerHTML = '';
    const playAgain = document.createElement('button');
    playAgain.className = 'discord-button';
    playAgain.textContent = 'Play Again';
    playAgain.onclick = startMemoryGame;
    controls.appendChild(playAgain);
}