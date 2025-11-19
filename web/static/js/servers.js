
async function fetchServerData(inviteCode) {
    try {
    const inviteURL = inviteCode
    const response = await fetch(`https://discord.com/api/v10/invites/${inviteCode}?with_counts=true&with_expiration=true`);
    if (!response.ok) throw new Error(`Failed to fetch data for ${inviteCode}`);
    
    const data = await response.json();
    
    const serverName = data.guild.name;
    const memberCount = data.approximate_member_count;
    const onlineCount = data.approximate_presence_count;
    const serverID = data.guild.id;
    const iconID = data.guild.icon;
    const iconURL = iconID ? `https://cdn.discordapp.com/icons/${serverID}/${iconID}.png?size=256` : "assets/default-server-icon.png";
    
    insertServerCard(serverName, memberCount, onlineCount, iconURL, inviteURL);
    } catch (error) {
    console.error(error);
    }
}

function insertServerCard(name, members, online, iconURL, inviteCode) {
    const icon_container = document.getElementById("server-icons"); 
    icon_container.innerHTML += `<a href="https://discord.gg/${inviteCode}" target="_blank"><img src="${iconURL}" alt="${name}" style="height: 35px; width: 35px; border-radius: 1000px; margin-right: 4px;" data-bs-toggle='tooltip' title="${name}"></a>`;

    const container = document.getElementById("server-cards"); 
    container.innerHTML += `
    <a href="https://discord.gg/${inviteCode}" target="_blank" id="serverInvite"><div class="card server-card" style="width: 18rem; text-align: center; display: flex; justify-content: center; align-items: center;">
            <img src="${iconURL}" class="card-img-top" alt="${name}" style="height: 150px; width: 150px; border-radius: 1000px;">
            <div class="card-body">
                <h5 class="card-title">${name}</h5>
                <p class="card-subtitle"><span class="status-dot gray"></span> ${members.toLocaleString()} members <br> <span class="status-dot green"></span> ${online.toLocaleString()} online</p>
            </div>
    </div></a>
    `;
}

const inviteCodes = ["liyue", "celestial", "kaW5pjvEcP", "EJ8zxxBauz", "liyuepavilion", "ABMNKauUgG", "yQNdsXRw72", "visionholders", "AG4CwUQCyh", "JeNEfH6Mc7", "yj7rYCYxxS"];
inviteCodes.forEach(fetchServerData);