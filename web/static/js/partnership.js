
function openPartnershipModal() {
    document.getElementById('partnershipModal').style.display = 'block';
}

function closePartnershipModal() {
    document.getElementById('partnershipModal').style.display = 'none';
}

function submitPartnershipRequest() {
    const inviteLink = document.getElementById('inviteLinkInput').value;
    const code = inviteLink.split('/').pop();
    
    if (code === 'kaycd3fxHh') {
    document.getElementById('partnershipInitial').style.display = 'none';
    document.getElementById('partnershipButton').style.display = 'none';
    
    document.getElementById('partnershipSuccess').style.display = 'block';
    document.getElementById('partnershipThread').style.display = 'block';
    document.getElementById('partnershipButtons').style.display = 'flex';
    } else {
    document.getElementById('partnershipInitial').style.display = 'none';
    document.getElementById('partnershipButton').style.display = 'none';
    document.getElementById('partnershipError').style.display = 'block';
    }
    
    closePartnershipModal();
}

function resetPartnershipDemo() {
    document.getElementById('partnershipInitial').style.display = 'block';
    document.getElementById('partnershipButton').style.display = 'block';
    
    document.getElementById('partnershipSuccess').style.display = 'none';
    document.getElementById('partnershipThread').style.display = 'none';
    document.getElementById('partnershipButtons').style.display = 'none';
    document.getElementById('partnershipError').style.display = 'none';
}