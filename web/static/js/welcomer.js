
function joinServer() {
document.getElementById('inviteBox').style.display = 'none';

const welcomeEmbed = document.getElementById('welcomeEmbed');
welcomeEmbed.style.display = 'block';
welcomeEmbed.style.animation = 'fadeIn 0.3s ease forwards';

document.getElementById('leaveButton').style.display = 'block';
}

function leaveServer() {
document.getElementById('welcomeEmbed').style.display = 'none';
document.getElementById('leaveButton').style.display = 'none';

const inviteBox = document.getElementById('inviteBox');
inviteBox.style.display = 'block';
inviteBox.style.animation = 'fadeIn 0.3s ease forwards';
}