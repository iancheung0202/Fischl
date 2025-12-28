const firebaseConfig = {
    apiKey: "AIzaSyADOvbi-c0s3lF3oqlIeAhmYtW9auNvYZ4",
    authDomain: "fischl-beta.firebaseapp.com",
    databaseURL: "https://fischl-beta-default-rtdb.firebaseio.com",
    projectId: "fischl-beta",
    storageBucket: "fischl-beta.firebasestorage.app",
    messagingSenderId: "706126285135",
    appId: "1:706126285135:web:3a387bc06f62390312dd3a",
    measurementId: "G-2PZNDPFWBF"
};

firebase.initializeApp(firebaseConfig);
const db = firebase.database();

const statusDiv = document.getElementById('botStatus');
const lastPingDiv = document.getElementById('lastPing');
const uptimeDurationDiv = document.getElementById('uptimeDuration');
const uptimePercentDiv = document.getElementById('uptimePercent');
const uptimeBar = document.getElementById('uptimeBar');
const pingLatencyDiv = document.getElementById('pingLatency');

let lastPingDate = null;
let lastLatencyMs = null;
let uptimeStart = null;
let pingHistory = [];

function formatDuration(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;

    let result = "";
    if (d > 0) result += `${d}d `;
    result += `${h}h ${m}m ${s}s`;
    return result.trim();
}

function updateDisplay() {
    const now = new Date();
    if (!lastPingDate) {
        statusDiv.textContent = "Offline";
        statusDiv.className = "status-value offline";
        lastPingDiv.textContent = "";
        uptimeDurationDiv.textContent = "";
        pingLatencyDiv.textContent = "";
        uptimePercentDiv.textContent = "-";
        uptimeBar.style.width = "0%";
        return;
    }

    const diffSec = (now - lastPingDate) / 1000;
    const isOnline = diffSec < 180;  // 3 minutes threshold to indicate offline
    statusDiv.textContent = isOnline ? "Online" : "Offline";
    statusDiv.className = "status-value " + (isOnline ? "online" : "offline");

    lastPingDiv.textContent = lastPingDate.toLocaleString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        timeZone: 'America/Los_Angeles',
        timeZoneName: 'short'
    });

    if (isOnline && uptimeStart) {
        const uptimeSec = Math.floor((Date.now() / 1000) - uptimeStart);
        uptimeDurationDiv.textContent = formatDuration(uptimeSec);
    } else {
        uptimeDurationDiv.textContent = "-";
    }

    pingLatencyDiv.textContent = (isOnline && lastLatencyMs !== null) ? `${lastLatencyMs} ms` : "-";

    const cutoffTime = Date.now() - 24 * 60 * 60 * 1000; // 24 hours ago
    const threshold = 180000; // 3 minutes in milliseconds

    const relevant = pingHistory.filter(e => e.timestamp >= cutoffTime);

    if (relevant.length > 0) {
        let uptimeMs = 0;

        const firstPingTime = relevant[0].timestamp;
        const timeBeforeFirst = firstPingTime - cutoffTime;
        uptimeMs += timeBeforeFirst;

        for (let i = 1; i < relevant.length; i++) {
            const gap = relevant[i].timestamp - relevant[i - 1].timestamp;
            if (gap < threshold) {
                uptimeMs += gap;
            } else {
            }
        }

        const lastPingTime = relevant[relevant.length - 1].timestamp;
        const timeAfterLast = Date.now() - lastPingTime;
        if (timeAfterLast < threshold) {
            uptimeMs += timeAfterLast;
        } else {
        }

        const percent = Math.min(100, (uptimeMs / (24 * 60 * 60 * 1000)) * 100);

        uptimePercentDiv.textContent = percent.toFixed(2) + "%";
        uptimeBar.style.width = percent.toFixed(1) + "%";
    } else {
        uptimePercentDiv.textContent = "-";
        uptimeBar.style.width = "0%";
    }
}


db.ref('Bot Status/last_ping').on('value', snapshot => {
    const val = snapshot.val().substring(0, 29);
    if (val) {
        lastPingDate = new Date(val);
        updateDisplay();
    }
});

db.ref('Bot Status/last_latency_ms').on('value', snapshot => {
    const val = snapshot.val();
    if (val !== null) {
        lastLatencyMs = val;
        updateDisplay();
    }
});

db.ref('Bot Status/ping_history').limitToLast(100).on('child_added', snapshot => {
    const p = snapshot.val();
    if (p && p.timestamp) {
        pingHistory.push({
            timestamp: p.timestamp,
            latency_ms: p.latency_ms
        });
        
        if (pingHistory.length > 100) {
            pingHistory.shift(); 
        }
        updateDisplay();
    }
});

db.ref('Bot Status/ping_history').limitToLast(100).once('value', snapshot => {
    const val = snapshot.val() || {};
    pingHistory = Object.values(val).map(p => ({
        timestamp: p.timestamp,
        latency_ms: p.latency_ms
    })).sort((a,b) => a.timestamp - b.timestamp);
    updateDisplay();
});

db.ref('Uptime').limitToFirst(1).once('value').then(snapshot => {
    const val = snapshot.val();
    if (val) {
        uptimeStart = Object.values(val)[0].Uptime;
        updateDisplay();
    }
});

function scheduleUpdate() {
    const now = new Date();
    const delay = 1000 - now.getMilliseconds();

    setTimeout(() => {
        updateDisplay();
        scheduleUpdate();
    }, delay);
}

scheduleUpdate();
