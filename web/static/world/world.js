const B = window.BOOT, Q = s => document.querySelector(s), QA = s => document.querySelectorAll(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fmt = s => { s = Math.max(0, Math.floor(s)); return [s/3600|0, (s%3600)/60|0, s%60].map(n => String(n).padStart(2,'0')).join(':'); };
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const now = () => Date.now() / 1000;
let M, S = null, G = [], sel = null, hrs = 4, tab = 'pass', tipTimer;

async function api(url, body) {
  const r = await fetch(url, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
  if (r.status === 401) location = '/auth';
  return r.json().catch(() => ({error:'Something went wrong. Try again.'}));
}
function toast(t) { const e = Q('#toast'); e.textContent = t; e.classList.add('on'); clearTimeout(e.t); e.t = setTimeout(() => e.classList.remove('on'), 2800); }
const imgReady = url => new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = url; setTimeout(r, 3000); });
function pan(el) {   // drag-to-pan with a mouse; touch already scrolls natively
  let d, x, y, l, t;
  el.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' || e.target.closest('button,.mk')) return; d = 1; x = e.clientX; y = e.clientY; l = el.scrollLeft; t = el.scrollTop; el.classList.add('drag'); });
  addEventListener('pointermove', e => { if (d) { el.scrollLeft = l - (e.clientX - x); el.scrollTop = t - (e.clientY - y); } });
  addEventListener('pointerup', () => { d = 0; el.classList.remove('drag'); });
}
pan(Q('#wscroll')); pan(Q('#rscroll'));

/* ---------- world map ---------- */
function renderWorld() {
  Q('#wcanvas').style.setProperty('--map', `url(${M.world.image})`);
  const A = M.world.anchors, used = new Set(); let off = 0;
  if (!G.length) { Q('#wnodes').innerHTML = '<p class="empty">None of your servers have events turned on yet.<br>Ask a server admin to enable them.</p>'; return; }
  Q('#wnodes').innerHTML = G.map((g, i) => {   // each server keeps the same spot on the map every visit
    if (used.size >= A.length) { used.clear(); off += 26; }
    let k = Number(BigInt(g.id) % BigInt(A.length)); while (used.has(k)) k = (k + 1) % A.length; used.add(k);
    const x = (A[k][0] + off) / 10, y = (A[k][1] + off) / 6;
    const ic = g.icon ? `<img src="https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png?size=128" alt="">` : esc(g.name[0]);
    return `<button class="node" data-gid="${g.id}" style="--i:${i};left:${x}%;top:${y}%"><div class="ico">${ic}</div><em>${esc(g.name)}</em></button>`;
  }).join('');
  const sc = Q('#wscroll'); sc.scrollLeft = (sc.scrollWidth - sc.clientWidth) / 2; sc.scrollTop = (sc.scrollHeight - sc.clientHeight) / 2;
}
Q('#wnodes').addEventListener('click', e => { const b = e.target.closest('.node'); if (b) enter(b.dataset.gid, false, b); });

async function enter(gid, instant, node) {
  const p = api(`/api/profile/${gid}/state`), w = Q('#world');
  if (!instant && node) {
    const r = node.getBoundingClientRect();
    w.style.transformOrigin = `${r.left + r.width / 2}px ${r.top + r.height / 2}px`;
    w.classList.add('zoom'); Q('#flash').classList.add('on'); await sleep(750);
  }
  const s = await p;
  if (s.error) { toast(s.error); w.classList.remove('zoom'); Q('#flash').classList.remove('on'); if (instant) history.replaceState({}, '', '/profile'); return; }
  S = s; sel = null; Q('#rname').textContent = S.guild.name;
  Q('#rcanvas').style.setProperty('--map', `url(${M.region.image})`);
  w.hidden = true; Q('#region').hidden = false; Q('#flash').classList.remove('on');
  drawMap(); drawDock();
  const sc = Q('#rscroll'); sc.scrollLeft = M.region.camp[0] / 1000 * sc.scrollWidth - sc.clientWidth * .3; sc.scrollTop = M.region.camp[1] / 600 * sc.scrollHeight - sc.clientHeight * .6;
  if (!instant) history.pushState({}, '', `/profile/${gid}`);
}
function leave(push = true) {
  S = null; closeMenu(); closeSheet(); Q('#region').hidden = true;
  const w = Q('#world'); w.hidden = false; w.classList.remove('zoom');
  if (push) history.pushState({}, '', '/profile');
}
Q('#back').onclick = () => leave();
addEventListener('popstate', () => { const m = location.pathname.match(/\/profile\/(\d+)/); m ? enter(m[1], true) : leave(false); });

/* ---------- region: live map of everyone who is out ---------- */
const pos = f => f < .45 ? f / .45 : f < .55 ? 1 : Math.max(0, (1 - f) / .45);   // walk out, rest at the destination, walk back
const jit = (id, k) => ((id * k) % 13) - 6;                                         // keeps overlapping markers from stacking exactly
const mineRun = () => S.runs.find(r => r.uid === S.me);
const dest = h => M.region.routes[h];
function drawMap() {
  const R = M.region, t = now(), hs = Object.keys(R.routes);
  const runs = S.runs.filter(r => r.ends_at > t || r.uid === S.me);
  Q('#rsvg').innerHTML = `<defs><clipPath id="cl"><circle r="14"/></clipPath></defs>
    ${hs.map(h => `<path id="r${h}" d="${R.routes[h].d}" fill="none"/>`).join('')}
    <g id="trails">${runs.filter(r => r.ends_at > t).map(r => `<path class="trail ${r.uid === S.me ? 'me' : ''}" id="t${r.id}" d="${R.routes[r.hours].d}" pathLength="1000"/>`).join('')}</g><g id="pins"></g>
    <g id="marks">${runs.map(r => { const c = S.roster.find(c => c.name === r.character) || {};
      return `<g class="mk ${r.uid === S.me ? 'me' : ''}" id="m${r.id}" data-id="${r.id}"><circle class="bg" r="15"/><text>${esc(r.character[0])}</text><image href="${esc(c.icon || '')}" x="-14" y="-14" width="28" height="28" clip-path="url(#cl)"/><circle class="ring" r="15"/></g>`; }).join('')}</g>`;
  const pins = Q('#pins');
  hs.forEach(h => { const p = Q('#r' + h), e = p.getPointAtLength(p.getTotalLength());
    pins.insertAdjacentHTML('beforeend', `<g class="pin"><circle cx="${e.x}" cy="${e.y}" r="6"/><text x="${e.x}" y="${e.y + 20}">${esc(R.routes[h].name)}</text></g>`); });
  pins.insertAdjacentHTML('beforeend', `<g class="pin"><circle cx="${R.camp[0]}" cy="${R.camp[1]}" r="8"/><text x="${R.camp[0]}" y="${R.camp[1] + 24}">Camp</text></g>`);
  tick();
}
function tick() {
  if (!S || Q('#region').hidden) return; const t = now(), R = M.region;
  S.runs.forEach(r => {
    const m = Q('#m' + r.id); if (!m) return;
    const f = (t - r.started_at) / (r.ends_at - r.started_at), back = f >= 1, mine = r.uid === S.me;
    if (back && !mine) { m.style.display = 'none'; return; }
    const route = Q('#r' + r.hours), p = back ? 0 : pos(f), pt = route.getPointAtLength(route.getTotalLength() * p);
    m.setAttribute('transform', `translate(${pt.x + jit(r.id, 37)} ${pt.y + jit(r.id, 53)})`);
    m.classList.toggle('ready', back && mine);
    const tr = Q('#t' + r.id); if (tr) tr.style.strokeDasharray = `${p * 1000} 1000`;
  });
  const dt = Q('#dt'), mine = mineRun();
  if (dt && mine) { const left = mine.ends_at - t; left > 0 ? dt.textContent = fmt(left) : drawDock(); }
}
setInterval(tick, 1000);
setInterval(() => { if (S && !document.hidden) refresh(); }, 30000);   // so you can watch other people come and go

Q('#rsvg').addEventListener('click', e => {
  const k = e.target.closest('.mk'); if (!k) return;
  const r = S.runs.find(r => r.id == k.dataset.id), left = r.ends_at - now(), mine = r.uid === S.me;
  if (mine && left <= 0) return claim(r.id);
  const tip = Q('#tip');
  tip.textContent = `${mine ? 'You' : r.name} sent ${r.character} to ${dest(r.hours).name}. ${left > 0 ? 'Back in ' + fmt(left) + '.' : ''}`;
  tip.classList.add('on'); clearTimeout(tipTimer); tipTimer = setTimeout(() => tip.classList.remove('on'), 3500);
});

function drawDock() {
  const mine = mineRun(), t = now(), free = S.roster.length - S.runs.filter(r => r.ends_at > t).length;
  Q('#dock').innerHTML = !mine
    ? `<p>${free} of ${S.roster.length} characters are free to send out.</p><button class="btn gold" data-send>Send someone out</button>`
    : mine.ends_at > t
      ? `<p><b>${esc(mine.character)}</b> is on the way to ${esc(dest(mine.hours).name)}.</p><time id="dt">${fmt(mine.ends_at - t)}</time>`
      : `<p><b>${esc(mine.character)}</b> is back from ${esc(dest(mine.hours).name)}.</p><button class="btn gold" data-claim="${mine.id}">Collect</button>`;
}
Q('#dock').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.dataset.claim) claim(b.dataset.claim); else openSheet();
});
async function claim(id) {
  const r = await api(`/api/profile/${S.guild.id}/claim`, {id: +id});
  toast(r.error || `Collected ${r.mora.toLocaleString()} mora and ${plural(r.summons, 'summon')}.`); refresh();
}
async function refresh() {
  const s = await api(`/api/profile/${S.guild.id}/state`); if (s.error) return;
  S = s; drawMap(); drawDock();
  if (Q('#menu').classList.contains('open')) drawMenu();
  if (Q('#sheet').classList.contains('on')) drawGrid();
}

/* ---------- picking someone to send out ---------- */
function openSheet() { drawSheet(); Q('#sheet').classList.add('on'); }
function closeSheet() { Q('#sheet').classList.remove('on'); }
function drawSheet() {
  Q('#spanel').innerHTML = `<div class="shead"><h2>Where to?</h2><button class="btn" data-x>Close</button></div>
    <div class="durs">${Object.keys(S.rewards).map(h => `<button class="dur ${+h === hrs ? 'sel' : ''}" data-h="${h}"><b>${h} hours</b><span>${esc(dest(h).name)}</span><small>${S.rewards[h].mora.toLocaleString()} mora, ${plural(S.rewards[h].summons, 'summon')}</small></button>`).join('')}</div>
    ${S.elite ? '<p class="hint">Your Elite bonus is already included.</p>' : ''}
    <input id="q" placeholder="Search ${S.roster.length} characters" autocomplete="off"><p class="hint" id="free"></p><div class="grid" id="grid"></div>
    <button class="btn gold wide" id="go" disabled>Pick a character</button>`;
  drawGrid();
}
function drawGrid() {
  const busy = new Map(S.runs.filter(r => r.ends_at > now()).map(r => [r.character, r])), q = (Q('#q')?.value || '').toLowerCase();
  if (sel && busy.has(sel)) sel = null;
  Q('#free').textContent = `${S.roster.length - busy.size} of ${S.roster.length} are free right now. Once someone sends a character out, nobody else can until they're back.`;
  Q('#grid').innerHTML = S.roster.filter(c => c.name.toLowerCase().includes(q)).map(c => { const b = busy.get(c.name);
    return `<button class="ch ${c.name === sel ? 'sel' : ''}" data-n="${esc(c.name)}" ${b ? 'disabled' : ''}><img src="${esc(c.icon)}" loading="lazy" referrerpolicy="no-referrer" alt=""><span>${esc(c.name)}</span>${b ? `<i>${esc(b.name)}</i>` : ''}</button>`; }).join('');
  markSel();
}
function markSel() {
  QA('.ch').forEach(c => c.classList.toggle('sel', c.dataset.n === sel));
  QA('.dur').forEach(d => d.classList.toggle('sel', +d.dataset.h === hrs));
  const go = Q('#go'); go.disabled = !sel; go.textContent = sel ? `Send ${sel} to ${dest(hrs).name}` : 'Pick a character';
}
Q('#spanel').addEventListener('input', e => { if (e.target.id === 'q') drawGrid(); });
Q('#spanel').addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b) return;
  if ('x' in b.dataset) return closeSheet();
  if (b.dataset.h) { hrs = +b.dataset.h; return markSel(); }
  if (b.dataset.n) { sel = b.dataset.n; return markSel(); }
  if (b.id === 'go') {
    b.disabled = true; const who = sel, r = await api(`/api/profile/${S.guild.id}/dispatch`, {character: who, hours: hrs});
    if (r.error) toast(r.error); else { toast(`${who} is heading to ${dest(hrs).name}.`); closeSheet(); sel = null; }
    refresh();
  }
});
Q('#sheet').addEventListener('click', e => { if (e.target.id === 'sheet') closeSheet(); });

/* ---------- menu: season pass and wayfarers ---------- */
function drawMenu() {
  QA('.tab').forEach(t => t.classList.toggle('sel', t.dataset.tab === tab));
  const body = Q('#mbody'), t = now();
  if (tab === 'board') {
    const out = S.runs.filter(r => r.ends_at > t);
    body.innerHTML = `<h3>On the road right now</h3><ul class="list">${out.map(r => `<li><span>${esc(r.name)} · ${esc(r.character)}</span><small>${esc(dest(r.hours).name)}, back in ${fmt(r.ends_at - t)}</small></li>`).join('') || '<li><small>Nobody. The map is quiet.</small></li>'}</ul>
      <h3>Most time on the road</h3><ul class="list">${S.board.map((b, i) => `<li><span>${i + 1}. ${esc(b.name)}</span><small>${b.hours} hours over ${plural(b.trips, 'trip')}</small></li>`).join('') || '<li><small>No finished expeditions yet.</small></li>'}</ul>`;
    return;
  }
  const pct = S.tier_need ? Math.min(100, S.tier_xp / S.tier_need * 100) : 100;
  body.innerHTML = `<h2>Season ${S.season.id}: ${esc(S.season.name)}</h2>
    <p class="hint">Tier ${S.tier}, ${S.xp.toLocaleString()} XP${S.tier_need ? `, ${S.tier_xp.toLocaleString()} of ${S.tier_need.toLocaleString()} to the next tier` : ''}</p><div class="bar"><i style="width:${pct}%"></i></div>
    ${S.elite ? '' : `<div class="perks"><b>Elite track</b><ul><li>Animated backgrounds, frames and badge titles</li><li>More mora from chests, chat games and expeditions</li><li>One extra Prestige at the final tier</li></ul><button class="btn gold wide" id="buy">Unlock for $${B.price} (this season, this server)</button></div>`}
    <div class="pass">${S.tiers.map(x => `<div class="tier ${x.tier <= S.tier ? 'done' : ''} ${x.tier === S.tier + 1 ? 'next' : ''}"><b>${x.tier}</b><div class="cell">${esc(x.free)}</div><div class="cell elite ${S.elite ? '' : 'lock'}">${esc(x.elite)}</div></div>`).join('')}</div>`;
  const b = Q('#buy'); if (b) b.onclick = buy;
  const n = body.querySelector('.next') || body.querySelector('.tier.done:last-child'); if (n) n.scrollIntoView({inline: 'center', block: 'nearest'});
}
function closeMenu() { Q('#menu').classList.remove('open'); }
Q('#openmenu').onclick = () => { drawMenu(); Q('#menu').classList.add('open'); };
Q('#closemenu').onclick = closeMenu;
QA('.tab').forEach(t => t.onclick = () => { tab = t.dataset.tab; drawMenu(); });

/* ---------- PayPal ---------- */
function buy() {
  Q('#pp').classList.add('on');
  const go = () => { Q('#ppbox').innerHTML = ''; paypal.Buttons({
    createOrder: (d, a) => a.order.create({purchase_units: [{amount: {value: String(B.price), currency_code: 'USD'}, description: 'Fischl Elite Track (1 season)', custom_id: `${B.user.id}-${S.guild.id}`}], application_context: {shipping_preference: 'NO_SHIPPING'}}),
    onApprove: (d, a) => a.order.capture().then(det => api('/payment/activate', {user_id: B.user.id, guild_id: S.guild.id, order_id: d.orderID, payment_details: det}))
      .then(async r => { Q('#pp').classList.remove('on'); toast(r.error ? 'Your payment went through but activation failed. Please contact support.' : 'Elite track unlocked. Thank you!'); await refresh(); }),
    onError: () => toast('The payment didn\'t go through.')}).render('#ppbox'); };
  if (window.paypal) go(); else { const s = document.createElement('script'); s.src = `https://www.paypal.com/sdk/js?client-id=${B.paypal}&intent=capture&currency=USD`; s.onload = go; document.head.append(s); }
}
Q('#ppclose').onclick = () => Q('#pp').classList.remove('on');

/* ---------- map editor: open /profile?edit=1 and click the map to get coordinates ---------- */
if (new URLSearchParams(location.search).has('edit')) {
  const pts = [], box = document.createElement('div'); box.id = 'edit'; box.className = 'card';
  box.innerHTML = '<textarea readonly></textarea><button class="btn">Clear</button>'; document.body.append(box);
  const smooth = p => p.reduce((s, q, i) => { if (!i) return `M${q[0]} ${q[1]}`; const a = p[i-2] || p[i-1], b = p[i-1], d = p[i+1] || q;
    return s + `C${Math.round(b[0] + (q[0]-a[0])/6)} ${Math.round(b[1] + (q[1]-a[1])/6)} ${Math.round(q[0] - (d[0]-b[0])/6)} ${Math.round(q[1] - (d[1]-b[1])/6)} ${q[0]} ${q[1]}`; }, '');
  const show = () => box.firstChild.value = `points: ${JSON.stringify(pts)}\npath d: ${pts.length > 1 ? smooth(pts) : ''}`;
  box.lastChild.onclick = () => { pts.length = 0; show(); };
  document.addEventListener('click', e => { const c = e.target.closest('.canvas'); if (!c || e.target.closest('button,.mk')) return;
    const r = c.getBoundingClientRect(); pts.push([Math.round((e.clientX - r.left) / r.width * 1000), Math.round((e.clientY - r.top) / r.height * 600)]); show(); });
}

/* ---------- boot ---------- */
(async () => {
  Q('#me').textContent = B.user.username; Q('#av').src = B.user.avatar;
  M = await fetch('/world/map.json').then(r => r.json());
  const [d] = await Promise.all([api('/api/profile/data'), imgReady(M.world.image), imgReady(M.region.image), sleep(1100)]);
  G = d.guilds || []; renderWorld();
  if (B.gid) await enter(B.gid, true);
  Q('#veil').classList.add('open');
})();
