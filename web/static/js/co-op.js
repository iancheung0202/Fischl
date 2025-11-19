
let currentRegion = '';

function openCoOpForm(region) {
    currentRegion = region;
    document.getElementById('coopFormTitle').textContent = `Request Co-op Help - ${region}`;
    document.getElementById('coopInitial').style.display = 'none';
    document.getElementById('coopInitialButtons').style.display = 'none';
    document.getElementById('coopForm').style.display = 'block';
    document.getElementById('coopUID').value = '';
    document.getElementById('coopWL').value = '';
    document.getElementById('coopRuns').value = '';
    document.getElementById('coopRequestText').value = '';
}

function cancelCoOpForm() {
    document.getElementById('coopForm').style.display = 'none';
    document.getElementById('coopInitial').style.display = 'block';
    document.getElementById('coopInitialButtons').style.display = 'block';
}

function submitCoOpForm() {
    const uid = document.getElementById('coopUID').value || '1234567890';
    const wl = document.getElementById('coopWL').value || '8';
    const runs = document.getElementById('coopRuns').value || '1';
    const request = document.getElementById('coopRequestText').value || 'Need help with weekly boss';
    
    document.getElementById('coopForm').style.display = 'none';
    
    let color, helperRole;
    switch(currentRegion) {
    case 'NA':
        color = '#6161F9';
        helperRole = 'NA Co-Op Ping';
        break;
    case 'EU':
        color = '#50C450';
        helperRole = 'EU Co-Op Ping';
        break;
    case 'Asia':
        color = '#F96262';
        helperRole = 'Asia Co-Op Ping';
        break;
    case 'SAR':
        color = '#F7D31A';
        helperRole = 'SAR Co-Op Ping';
        break;
    }

    const requestContent = `👋 <b><span class='mention'>@Oz</span> is requesting for co-op</b> - <span class='mention' style='background-color: rgba(76, 112, 65, 0.601); color: rgb(128, 209, 101); '>@${helperRole}</span> `;
    document.getElementById('coopRequestContent').innerHTML = requestContent;
    document.getElementById('coopRequestContent').style.display = 'block';
    document.getElementById('coopRequestContent').style.color = '#f3f4f6';
    document.getElementById('coopRequestContent').style.marginBottom = '4px';
    
    const embed = document.getElementById('coopRequest');
    embed.innerHTML = `
    <div class="discord-embed-title">${currentRegion} Region Co-op Request</div>
    <div class="discord-embed-description"><span style="color: rgb(161,162,168); line-height: 0.7; font-size: small">
        • Coordinate with each other in the <b>thread</b> below.
        • Click on <b><code>Claim</code></b> if you are intending to help.
        • If you are the requester and <b>no longer need help</b>, press <b><code>Close</code></b>.
    </span></div>
    <div class="embed-fields">
        <div class="embed-field"><strong>UID</strong><span>${uid}</span></div>
        <div class="embed-field"><strong>World Level</strong><span>WL${wl}</span></div>
        <div class="embed-field"><strong>Runs</strong><span>${runs} run${runs != '1' ? 's' : ''}</span></div>
        <div class="embed-field"><strong>Request</strong><span>${request}</span></div>
    </div>
    `;
    embed.style.borderLeft = `4px solid ${color}`;
    embed.style.display = 'block';
    
    document.getElementById('coopRequestButtons').style.display = 'flex';
    document.getElementById('coopRequestButtons').style.gap = '8px';
}

function closeCoOpRequest() {
    document.getElementById('coopRequestContent').style.display = 'none';
    document.getElementById('coopRequest').style.display = 'none';
    document.getElementById('coopRequestButtons').style.display = 'none';
    
    document.getElementById('coopInitial').style.display = 'block';
    document.getElementById('coopInitialButtons').style.display = 'flex';
}

function copyUIDToClipboard(button) {
    if (button.dataset.copied) return;

    const uidSpan = document.querySelector('#coopRequest .embed-field strong:nth-child(1) + span');
    if (!uidSpan) return;

    const uid = uidSpan.textContent.trim();
    navigator.clipboard.writeText(uid)
    .then(() => {
        button.style.backgroundColor = 'rgb(0,134,58)';
        button.innerText = 'Copied UID';
        button.dataset.copied = true;
    })
    .catch(err => {
        console.error('Clipboard copy failed:', err);
    });
}