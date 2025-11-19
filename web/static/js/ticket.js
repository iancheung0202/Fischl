
function openTicket() {
document.getElementById('embedInitial').style.display = 'none';
document.getElementById('buttonInitial').style.display = 'none';
const embedFinal = document.getElementById('embedFinal');
embedFinal.style.display = 'block';
embedFinal.style.animation = 'fadeIn 0.3s ease forwards';
document.getElementById('buttonFinal').style.display = 'block';
document.getElementById('timestamp').textContent = 'just now';
}

function closeTicket() {
document.getElementById('embedFinal').style.display = 'none';
document.getElementById('buttonFinal').style.display = 'none';
const embedInitial = document.getElementById('embedInitial');
embedInitial.style.display = 'block';
embedInitial.style.animation = 'fadeIn 0.3s ease forwards';
document.getElementById('buttonInitial').style.display = 'block';
}