
let acknowledged = false;
let lastSender = null;
const chatMessages = document.getElementById('chatMessages');
const userMessage = document.getElementById('userMessage');
const sendButton = document.getElementById('sendButton');

function addMessage(content, isUser = false) {
const sender = isUser ? 'user' : 'fischl';
const isGrouped = lastSender === sender;

const messageDiv = document.createElement('div');
messageDiv.className = 'message' + (isGrouped ? ' grouped' : ' not-grouped');

const avatarHTML = isGrouped
    ? `<div class="avatar-spacer"></div>`
    : `<img class="avatar" src="${isUser ? 'assets/oz.png' : 'https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=1024'}" />`;

const usernameLine = isUser 
    ? `<div><span class='username' style='color: #aff800;'>Oz</span></div>`
    : `<div><span class='username glow-text'>Fischl</span> <div class='app-badge'>APP</div></div>`;

messageDiv.innerHTML = `
    ${avatarHTML}
    <div class="content">
    ${isGrouped ? '' : usernameLine}
    <div class="text">${content}</div>
    </div>
`;


chatMessages.appendChild(messageDiv);
chatMessages.scrollTop = chatMessages.scrollHeight;

lastSender = sender;
}

function showGuardEmbed() {
const embedDiv = document.createElement('div');
embedDiv.className = 'message not-grouped';
embedDiv.innerHTML = `
    <img class='avatar' src='https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=1024' />
    <div class='content'>
    <div><span class='username glow-text'>Fischl</span> <div class='app-badge'>APP</div></div>
    <div class="discord-embed" style="border-left-color: #e44d41; margin-top: 6px; display: block;"">
        <div class="discord-embed-title">Channel Rules</div>
        <div class="discord-embed-description">
        • No NSFW content
        • No spamming or self-promotion
        • Be respectful to others<br>
        Please acknowledge to start sending messages!
        </div>
    </div>
    <div style="margin-top: 8px;">
        <button id="ackButton" class="discord-button" style="background-color: #3ba55d; padding: 6px 12px;">Got it!</button>
    </div>
    </div>
`;

chatMessages.appendChild(embedDiv);
chatMessages.scrollTop = chatMessages.scrollHeight;
document.getElementById("userMessage").disabled = true;
document.getElementById("sendButton").disabled = true;

document.getElementById('ackButton').addEventListener('click', () => {
    acknowledged = true;
    embedDiv.remove();
    addMessage(userMessage.value, true);
    document.getElementById("userMessage").disabled = false;
    document.getElementById("sendButton").disabled = false;
    userMessage.value = '';
});
}

sendButton.addEventListener('click', () => {
if (!userMessage.value.trim()) return;

if (!acknowledged) {
    showGuardEmbed();
} else {
    addMessage(userMessage.value, true);
    userMessage.value = '';
}
});

userMessage.addEventListener('keypress', (e) => {
if (e.key === 'Enter') {
    sendButton.click();
}
});