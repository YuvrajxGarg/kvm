(() => {
  'use strict';
  const ICONS = {
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.4-5.7L20 8.5"/><path d="M20 3.5v5h-5"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    chev: '<path d="m9 6 6 6-6 6"/>',
    reveal: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    loader: '<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>',
    download: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M4 20h16"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/>',
    send: '<path d="M21 3 10.5 13.5"/><path d="M21 3l-6.5 18-4-7.5L3 9.5z"/>',
    monitor: '<rect x="3" y="4" width="18" height="12.5" rx="2"/><path d="M8.5 20.5h7M12 16.5v4"/>',
    laptop: '<rect x="4.5" y="5" width="15" height="10.5" rx="1.6"/><path d="M2.5 19h19"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8.5 3 8.5H3S6 15 6 8"/><path d="M10.3 20a1.9 1.9 0 0 0 3.4 0"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    more: '<circle cx="5.5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18.5" cy="12" r="1.3"/>',
    folder: '<path d="M3.5 6.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    file: '<path d="M7 3.5h7l4 4v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2z"/><path d="M14 3.5v4h4"/>',
    unlink: '<path d="M9.5 14.5 14.5 9.5"/><path d="m11 6.5 1.5-1.5a4 4 0 0 1 5.6 5.6L16.5 12.2M7.5 11.8l-1.6 1.6a4 4 0 0 0 5.6 5.6l1.5-1.5"/><path d="M4 4l16 16"/>',
    speaker: '<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    camera: '<path d="M3.5 8a2 2 0 0 1 2-2h8.5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2z"/><path d="m16 10.5 4.5-3v9l-4.5-3"/>',
    phone: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    link: '<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/>',
    pointer: '<path d="M5 3.5 18.5 10l-6 1.8-2.6 5.7z"/><path d="m12.6 11.9 5 5"/>',
    clip: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="M9.5 10h5M9.5 14h5"/>',
    keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6.5 10h.01M10 10h.01M14 10h.01M17.5 10h.01M7.5 14h9"/>',
  };
  const icon = (n) => `<svg class="i" viewBox="0 0 24 24">${ICONS[n] || ''}</svg>`;
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const human = (n) => { if (!n) return '0 B'; const u = ['B', 'KB', 'MB', 'GB', 'TB']; let i = 0; while (n >= 1000 && i < 4) { n /= 1000; i++; } return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + u[i]; };
  const fillIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach((el) => { el.outerHTML = icon(el.dataset.icon); });
  const DEMO = location.search.includes('demo');
  const OS_ICON = { mac: 'laptop', windows: 'monitor', linux: 'monitor', android: 'phone', ios: 'phone' };
  const OS_NAME = { mac: 'Mac', windows: 'Windows', linux: 'Linux', android: 'Android', ios: 'iPhone' };
  const isPhone = (p) => p.platform === 'android' || p.platform === 'ios';
  const SIDE_NAME = { left: 'left', right: 'right', top: 'above', bottom: 'below' };

  let api = null;
  let info = { version: '', platform: '', settings: {}, update: {} };
  let st = null;          // last state() from Python
  let pairModal = null;   // what the pairing modal shows
  let seenNotice = 0;
  let dropTarget = null;
  let menuEl = null;

  // ---------------------------------------------------------------- toasts
  function toast(text, err) {
    const t = document.createElement('div');
    t.className = 'toast' + (err ? ' err' : '');
    t.innerHTML = icon(err ? 'alert' : 'check') + `<span>${esc(text)}</span>`;
    $('#toasts').appendChild(t);
    setTimeout(() => { t.style.transition = 'opacity .3s'; t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3800);
  }

  // ---------------------------------------------------------------- modal
  function modal(html, cls = '') {
    closeModal();
    const back = document.createElement('div');
    back.className = 'modal-back';
    back.innerHTML = `<div class="modal ${cls}">${html}</div>`;
    back.addEventListener('mousedown', (e) => { if (e.target === back && !back.dataset.sticky) closeModal(); });
    $('#modal-root').appendChild(back);
    fillIcons(back);
    return back.firstElementChild;
  }
  function closeModal() { $('#modal-root').innerHTML = ''; pairModal = null; }

  // ---------------------------------------------------------------- menu
  function openMenu(anchor, items) {
    closeMenu();
    menuEl = document.createElement('div');
    menuEl.className = 'menu';
    menuEl.innerHTML = items.map((it, i) => it === '-' ? '<hr>' :
      `<button data-i="${i}" class="${it.danger ? 'danger' : ''}">${icon(it.icon)}<span>${esc(it.label)}</span></button>`).join('');
    document.body.appendChild(menuEl);
    const r = anchor.getBoundingClientRect();
    menuEl.style.top = Math.min(r.bottom + 6, innerHeight - menuEl.offsetHeight - 10) + 'px';
    menuEl.style.left = Math.max(10, r.right - menuEl.offsetWidth) + 'px';
    menuEl.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-i]');
      if (b) { closeMenu(); items[+b.dataset.i].run(); }
    });
    setTimeout(() => document.addEventListener('mousedown', outside), 0);
  }
  function outside(e) { if (menuEl && !menuEl.contains(e.target)) closeMenu(); }
  function closeMenu() { if (menuEl) { menuEl.remove(); menuEl = null; } document.removeEventListener('mousedown', outside); }

  // ---------------------------------------------------------------- render
  function render() {
    const a = st && st.agent;
    $('#version').textContent = info.version ? 'v' + info.version : '';
    renderBanners();
    if (!a) {
      $('#now-title').textContent = st && st.mode === 'service-down' ? 'The Kvm service isn’t running' : 'Getting ready';
      $('#now-sub').textContent = st && st.mode === 'service-down' ? 'Restart this PC, or run Kvm-Setup again to repair it.' : (st && st.error) || '';
      return;
    }
    const peers = a.peers || [];
    const paired = peers.filter((p) => p.paired && !isPhone(p));
    const active = peers.find((p) => p.id === a.active);
    const now = $('.now');
    now.classList.toggle('on', a.mode !== 'home');
    if (a.mode === 'driving' && active) {
      $('#now-title').textContent = `Using ${active.name}`;
      $('#now-sub').innerHTML = `This ${OS_NAME[a.me.platform] || 'computer'}’s keyboard and mouse are on ${esc(active.name)}. Push back past the edge, or press <kbd>${esc(hk(a.settings.return_hotkey))}</kbd>.`;
    } else if (a.mode === 'driven' && active) {
      $('#now-title').textContent = `${active.name} is using this ${OS_NAME[a.me.platform] || 'computer'}`;
      $('#now-sub').textContent = 'Its keyboard and mouse are here right now.';
    } else if (!paired.length) {
      $('#now-title').textContent = 'One keyboard and mouse for your computers';
      $('#now-sub').textContent = 'Open Kvm on your other computer, then pair it below.';
    } else {
      const placed = paired.filter((p) => p.side);
      $('#now-title').textContent = placed.length ? `${a.me.name}` : 'Place your other computer';
      $('#now-sub').textContent = placed.length
        ? placed.map((p) => `${p.name} is ${p.layout_set ? 'set up around this one' : 'to the ' + SIDE_NAME[p.side]}${p.connected ? '' : ' (not connected)'}`).join(' · ')
        : 'Drag it next to this one, where it sits on your desk.';
    }
    $('#home-btn').classList.toggle('hidden', a.mode === 'home');
    const lb = $('#lock-btn');
    lb.classList.toggle('hidden', a.mode !== 'driving' && !a.locked);
    lb.querySelector('span').textContent = a.locked ? 'Cursor locked' : 'Cursor lock';
    renderDesk(a, paired);
    renderPeers(a, peers.filter((p) => !isPhone(p)));
    renderPeers(a, peers.filter((p) => !isPhone(p) && p.paired), '#quick');
    renderPages(false);
    renderPhones(a, peers.filter(isPhone));
    renderTransfers(a);
    // notices from the agent (pairing done, files received, ring)
    for (const n of a.notices || []) {
      if (n.id > seenNotice) { if (seenNotice) toast(n.text); seenNotice = n.id; }
    }
    // sound that couldn't start (sharing off there, no virtual microphone, ...)
    const snd = a.sound || {};
    for (const kind of ['hear', 'mic']) {
      for (const [pid, v] of Object.entries(snd[kind] || {})) {
        const k = kind + pid + (v.error || '');
        if (v.error && !soundErrs.has(k)) { soundErrs.add(k); toast(v.error, true); }
      }
    }
    // another computer extending onto this one: show its display full screen (and close it when it stops)
    const ext = a.extend || {};
    const want = new Set((ext.in || []).map((x) => x.id));
    for (const id of want) if (!displays.has(id)) { displays.add(id); api.open_display(id); }
    for (const id of [...displays]) if (!want.has(id)) { displays.delete(id); api.close_display(id); }
    for (const [pid, v] of Object.entries(ext.out || {})) {
      const k = 'ext' + pid + (v.error || '');
      if (v.error && !soundErrs.has(k)) { soundErrs.add(k); toast(v.error, true); }
    }
    renderPairing(a);
  }
  const displays = new Set();
  const soundErrs = new Set();

  function hk(s) {
    const isMac = info.platform === 'darwin';
    return (s || '').split('+').map((k) => ({ ctrl: isMac ? '⌃' : 'Ctrl', alt: isMac ? '⌥' : 'Alt', shift: isMac ? '⇧' : 'Shift', meta: isMac ? '⌘' : 'Win', esc: 'Esc' }[k] || k.toUpperCase())).join(isMac ? '' : '+');
  }

  function renderBanners() {
    const out = [];
    const a = st && st.agent;
    const perm = a && a.permissions;
    if (perm && perm.needs && perm.needs.length) {
      out.push(`<div class="banner">${icon('alert')}<div class="t"><b>Allow Kvm to use the keyboard and mouse</b>
        <span>macOS needs ${perm.needs.map((n) => n === 'accessibility' ? 'Accessibility' : 'Input Monitoring').join(' and ')} for Kvm in Privacy &amp; Security. Turn it on, then reopen Kvm. Without Input Monitoring the pointer still crosses, but typing doesn’t. If Kvm is already on there, select it, remove it with −, add it again with +, then reopen Kvm.</span></div>
        <button class="btn-quiet" data-act="perm-ask">Ask again</button>
        <button class="btn-quiet" data-act="perm-open" data-which="${perm.needs[0]}">Open Settings</button></div>`);
    }
    if (perm && perm.secure_input && !(perm.needs && perm.needs.length)) {
      out.push(`<div class="banner">${icon('alert')}<div class="t"><b>Typing can’t reach the other computer right now</b>
        <span>A password field or an app on this Mac has turned on Secure Input, which hides every key from Kvm. Click out of the password field, or quit the app that holds it (often a terminal with Secure Keyboard Entry, or a password manager).</span></div></div>`);
    }
    if (info.platform === 'win32' && st && st.mode === 'app') {
      out.push(`<div class="banner info">${icon('shield')}<div class="t"><b>Admin prompts and the sign-in screen</b>
        <span>Install Kvm with Kvm-Setup so your other computer’s keyboard also works on Windows admin prompts and when this PC is locked.</span></div>
        <button class="btn-quiet" data-act="get-setup">Get the setup</button></div>`);
    }
    const snd = (a && a.sound) || {};
    for (const w of snd.listeners || []) {
      out.push(`<div class="banner info">${icon('speaker')}<div class="t"><b>${esc(w.name)} is hearing this computer</b>
        <span>What plays here also plays there.</span></div>
        <button class="btn-quiet" data-act="listen-drop" data-pid="${w.id}">Stop</button></div>`);
    }
    for (const w of snd.mic_in || []) {
      out.push(`<div class="banner info">${icon('mic')}<div class="t"><b>${esc(w.name)}’s microphone is on here</b>
        <span>Apps here can use it: pick ${info.platform === 'darwin' ? '“BlackHole”' : '“CABLE Output”'} as the microphone.</span></div></div>`);
    }
    for (const [pid, v] of Object.entries(((a && a.extend) || {}).out || {})) {
      if (v.phase !== 'live' && v.phase !== 'starting') continue;
      const p = (a.peers || []).find((x) => x.id === pid) || {};
      out.push(`<div class="banner info">${icon('monitor')}<div class="t"><b>${v.phase === 'live' ? 'Using ' + esc(p.name || 'the other computer') + ' as a display' : 'Adding a display…'}</b>
        <span>Move the pointer onto it like any other display. Arrange it in System Settings › Displays.</span></div>
        <button class="btn-quiet" data-act="extend-stop" data-pid="${pid}">Stop</button></div>`);
    }
    for (const w of ((a && a.camera) || {}).watchers || []) {
      out.push(`<div class="banner info">${icon('camera')}<div class="t"><b>${esc(w.name)} is using this camera</b>
        <span>It sees what this computer’s camera sees.</span></div>
        <button class="btn-quiet" data-act="stop-camera">Stop</button></div>`);
    }
    for (const w of (a && a.watchers) || []) {
      out.push(`<div class="banner info">${icon('monitor')}<div class="t"><b>${esc(w.name)} is looking at this screen</b>
        <span>${a.settings && a.settings.screen_control ? 'It can also click and type here.' : 'It can see but not control it.'}</span></div>
        <button class="btn-quiet" data-act="stop-share">Stop sharing</button></div>`);
    }
    const html = out.join('');
    const el = $('#banners');
    if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
  }

  function screenHTML(p, extra = '') {
    const mons = (p.screens || []).slice(0, 4);
    let monHTML = '';
    if (mons.length > 1) {
      const maxh = Math.max(...mons.map((m) => m[3]));
      monHTML = `<div class="monitors">${mons.map((m) => `<i style="width:${Math.round(22 * m[2] / maxh)}px;height:${Math.round(18 * m[3] / maxh)}px"></i>`).join('')}</div>`;
    } else {
      monHTML = `<span class="os">${icon(OS_ICON[p.platform] || 'monitor')}</span>`;
    }
    return `<div class="screen ${extra}">${monHTML}<b>${esc(p.name)}</b><span>${esc(OS_NAME[p.platform] || '')}${p.connected === false ? ' · offline' : ''}</span></div>`;
  }

  // The desk: this computer's screens, and each screen of the others placed where it really
  // sits, like Windows' display settings. Every screen of another computer drags on its own.
  const SNAP = 12;  // px on the desk
  let deskView = null;  // {scale, ox, oy, minx, miny, peers: {pid: items}}
  let deskDrag = null;

  function guessLayout(a, p) {
    // Placed, but its screens aren't known yet (never connected): one 16:9 block on its side.
    const mine = (a.me.screens && a.me.screens.length) ? a.me.screens : [[0, 0, 1440, 900]];
    const L = Math.min(...mine.map((r) => r[0])), T = Math.min(...mine.map((r) => r[1]));
    const R = Math.max(...mine.map((r) => r[0] + r[2])), B = Math.max(...mine.map((r) => r[1] + r[3]));
    const w = 1920, h = 1080;
    const at = { left: [L - w, (T + B - h) / 2], right: [R, (T + B - h) / 2], top: [(L + R - w) / 2, T - h], bottom: [(L + R - w) / 2, B] }[p.side];
    return [{ r: [0, 0, w, h], at, guess: true }];
  }

  function renderDesk(a, paired) {
    const placed = paired.filter((p) => p.side);
    const unplaced = paired.filter((p) => !p.side);
    const desk = $('#desk');
    if (deskDrag) return;  // don't redraw under the pointer
    const mine = (a.me.screens && a.me.screens.length) ? a.me.screens : [[0, 0, 1440, 900]];
    const peers = {};
    placed.forEach((p) => { peers[p.id] = (p.layout && p.layout.length) ? p.layout : guessLayout(a, p); });
    const all = mine.map((r) => r.slice(0, 4));
    Object.values(peers).forEach((items) => items.forEach((i) => all.push([i.at[0], i.at[1], i.r[2], i.r[3]])));
    const minx = Math.min(...all.map((r) => r[0])), miny = Math.min(...all.map((r) => r[1]));
    const maxx = Math.max(...all.map((r) => r[0] + r[2])), maxy = Math.max(...all.map((r) => r[1] + r[3]));
    const W = desk.clientWidth || 640, H = desk.clientHeight || 300, pad = 28;
    // Room around the arrangement so a screen can be dragged to any side.
    const spanW = (maxx - minx) * 1.0, spanH = (maxy - miny) * 1.0;
    const scale = Math.min((W - pad * 2) / Math.max(spanW, 1), (H - pad * 2) / Math.max(spanH, 1), 0.12);
    const ox = (W - spanW * scale) / 2, oy = (H - spanH * scale) / 2;
    deskView = { scale, ox, oy, minx, miny, peers, mine };
    const box = (r) => `left:${Math.round(ox + (r[0] - minx) * scale)}px;top:${Math.round(oy + (r[1] - miny) * scale)}px;width:${Math.max(8, Math.round(r[2] * scale))}px;height:${Math.max(8, Math.round(r[3] * scale))}px`;
    let html = mine.map((r, i) => `<div class="scr me-scr ${a.mode !== 'driving' ? 'active' : ''}" style="${box(r)}">${i === 0
      ? `<span class="os">${icon(OS_ICON[a.me.platform] || 'monitor')}</span><b>${esc(a.me.name)}</b>` : ''}</div>`).join('');
    placed.forEach((p) => {
      peers[p.id].forEach((it, i) => {
        const cls = 'scr peer-scr' + (p.connected ? '' : ' offline') + (a.active === p.id ? ' active' : '');
        html += `<div class="${cls}" data-pid="${p.id}" data-i="${i}" ${it.guess ? 'data-guess="1"' : ''} style="${box([it.at[0], it.at[1], it.r[2], it.r[3]])}" title="Drag to where this screen really is">
          ${i === 0 ? `<span class="os">${icon(OS_ICON[p.platform] || 'monitor')}</span>` : ''}<b>${esc(p.name)}</b><span class="dim">${Math.round(it.r[2])}×${Math.round(it.r[3])}</span></div>`;
      });
    });
    if (!placed.length && paired.length) html += `<div class="desk-empty">Drop a computer next to this one</div>`;
    const key = JSON.stringify([html, W, H]);
    if (desk.dataset.key !== key) { desk.dataset.key = key; desk.innerHTML = html; }
    const hint = $('#desk-hint');
    const trayKey = JSON.stringify([unplaced.map((p) => [p.id, p.name, p.connected, p.platform]), placed.map((p) => [p.id, !!p.layout_set])]);
    if (hint.dataset.key !== trayKey) {
      hint.dataset.key = trayKey;
      hint.innerHTML = unplaced.length
        ? `<div>Drag a computer onto the desk, next to this one where it really is.</div><div class="tray">${unplaced.map((p) =>
            `<div class="chip screen-wrap" draggable="true" data-pid="${p.id}">${screenHTML(p, 'peer' + (p.connected ? '' : ' offline'))}</div>`).join('')}</div>`
        : (paired.length ? `Drag each screen to where it sits on your desk. The pointer crosses only where the edges touch. ${placed.some((p) => p.layout_set)
          ? '<a href="#" data-act="desk-reset">Reset</a>' : ''}` : '');
    }
  }

  // Dragging one screen of another computer around the desk.
  function deskRects(except) {
    const v = deskView, out = v.mine.map((r) => ({ r: r.slice(0, 4), mine: true }));
    for (const [pid, items] of Object.entries(v.peers)) {
      items.forEach((it, i) => { if (!(except && except.pid === pid && except.i === i)) out.push({ r: [it.at[0], it.at[1], it.r[2], it.r[3]], pid }); });
    }
    return out;
  }
  const overlap = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
  function snapRect(r, others, thr) {
    let best = [thr + 1, 0], bestY = [thr + 1, 0];
    for (const o of others) {
      const q = o.r;
      for (const d of [q[0] + q[2] - r[0], q[0] - (r[0] + r[2]), q[0] - r[0], q[0] + q[2] - (r[0] + r[2])]) if (Math.abs(d) < best[0]) best = [Math.abs(d), d];
      for (const d of [q[1] + q[3] - r[1], q[1] - (r[1] + r[3]), q[1] - r[1], q[1] + q[3] - (r[1] + r[3])]) if (Math.abs(d) < bestY[0]) bestY = [Math.abs(d), d];
    }
    r = r.slice();
    if (best[0] <= thr) r[0] += best[1];
    if (bestY[0] <= thr) r[1] += bestY[1];
    // Never on top of another screen: push out the shortest way.
    for (let n = 0; n < 4; n++) {
      const o = others.find((x) => overlap(r, x.r));
      if (!o) break;
      const q = o.r;
      const moves = [[q[0] + q[2] - r[0], 0], [q[0] - (r[0] + r[2]), 0], [0, q[1] + q[3] - r[1]], [0, q[1] - (r[1] + r[3])]];
      moves.sort((m1, m2) => Math.abs(m1[0] + m1[1]) - Math.abs(m2[0] + m2[1]));
      r[0] += moves[0][0]; r[1] += moves[0][1];
    }
    // And touching something, so the pointer can get there.
    const gap = (q) => Math.max(q[0] - (r[0] + r[2]), r[0] - (q[0] + q[2]), 0) + Math.max(q[1] - (r[1] + r[3]), r[1] - (q[1] + q[3]), 0);
    if (others.length && !others.some((o) => gap(o.r) === 0)) {
      const o = others.reduce((m, x) => (gap(x.r) < gap(m.r) ? x : m));
      const q = o.r;
      const dx = q[0] - (r[0] + r[2]) > 0 ? q[0] - (r[0] + r[2]) : (r[0] - (q[0] + q[2]) > 0 ? q[0] + q[2] - r[0] : 0);
      const dy = q[1] - (r[1] + r[3]) > 0 ? q[1] - (r[1] + r[3]) : (r[1] - (q[1] + q[3]) > 0 ? q[1] + q[3] - r[1] : 0);
      if (Math.abs(dx) && Math.abs(dy)) { if (Math.abs(dx) < Math.abs(dy)) { r[0] += dx; r[1] += dy; } else { r[0] += dx; r[1] += dy; } }
      else { r[0] += dx; r[1] += dy; }
      // A corner-only touch can't be crossed: slide along to share an edge.
      if (!(r[0] < q[0] + q[2] && q[0] < r[0] + r[2]) && !(r[1] < q[1] + q[3] && q[1] < r[1] + r[3])) {
        if (Math.abs(dx)) r[1] = Math.min(Math.max(r[1], q[1] - r[3] + 40), q[1] + q[3] - 40);
        else r[0] = Math.min(Math.max(r[0], q[0] - r[2] + 40), q[0] + q[2] - 40);
      }
    }
    return r;
  }

  $('#desk').addEventListener('pointerdown', (e) => {
    const el = e.target.closest('.peer-scr');
    if (!el || !deskView || e.button !== 0) return;
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    deskDrag = { el, pid: el.dataset.pid, i: +el.dataset.i, x0: e.clientX, y0: e.clientY,
      l0: parseFloat(el.style.left), t0: parseFloat(el.style.top), moved: false };
    el.classList.add('dragging');
  });
  $('#desk').addEventListener('pointermove', (e) => {
    const d = deskDrag;
    if (!d) return;
    const dx = e.clientX - d.x0, dy = e.clientY - d.y0;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    const v = deskView, it = v.peers[d.pid][d.i];
    let r = [v.minx + (d.l0 + dx - v.ox) / v.scale, v.miny + (d.t0 + dy - v.oy) / v.scale, it.r[2], it.r[3]];
    r = snapRect(r, deskRects(d), SNAP / v.scale);
    d.r = r;
    d.el.style.left = Math.round(v.ox + (r[0] - v.minx) * v.scale) + 'px';
    d.el.style.top = Math.round(v.oy + (r[1] - v.miny) * v.scale) + 'px';
  });
  const endDeskDrag = async () => {
    const d = deskDrag;
    if (!d) return;
    deskDrag = null;
    d.el.classList.remove('dragging');
    if (!d.moved || !d.r) return;
    const items = deskView.peers[d.pid].filter((it) => !it.guess).map((it, i) => ({ r: it.r, at: i === d.i ? [Math.round(d.r[0]), Math.round(d.r[1])] : it.at }));
    if (items.length) await api.set_layout(d.pid, items);
    else {  // screens not known yet: still lets them pick the side
      const v = deskView, mine = v.mine;
      const cx = d.r[0] + d.r[2] / 2, cy = d.r[1] + d.r[3] / 2;
      const L = Math.min(...mine.map((r) => r[0])), T = Math.min(...mine.map((r) => r[1]));
      const R = Math.max(...mine.map((r) => r[0] + r[2])), B = Math.max(...mine.map((r) => r[1] + r[3]));
      const fx = (cx - (L + R) / 2) / (R - L), fy = (cy - (T + B) / 2) / (B - T);
      await api.set_side(d.pid, Math.abs(fx) >= Math.abs(fy) ? (fx > 0 ? 'right' : 'left') : (fy > 0 ? 'bottom' : 'top'));
    }
    $('#desk').dataset.key = '';
    poll();
  };
  $('#desk').addEventListener('pointerup', endDeskDrag);
  $('#desk').addEventListener('pointercancel', endDeskDrag);

  function renderPeers(a, peers, sel = '#peers') {
    const el = $(sel);
    let html;
    if (!peers.length) {
      html = `<div class="empty">No other computers found yet.<br>Open Kvm on the other computer on this Wi-Fi, or add it by its address.</div>`;
    } else {
      html = peers.map((p) => {
        const sub = p.paired
          ? `<i class="dotst ${p.connected ? 'on' : ''}"></i>${p.connected ? 'Connected' : (p.online ? 'Connecting…' : 'Not on this network')}${p.side ? ` · to the ${SIDE_NAME[p.side]}` : ''}`
          : `<i class="dotst"></i>Nearby · not paired`;
        const snd = (a.sound && a.sound.hear && a.sound.hear[p.id]) || null;
        const mic = (a.sound && a.sound.mic && a.sound.mic[p.id]) || null;
        const acts = p.paired
          ? `<button class="btn-icon lg ${snd && snd.phase !== 'refused' ? 'on' : ''}" data-act="listen" data-pid="${p.id}" ${p.connected ? '' : 'disabled'} title="${snd ? 'Stop hearing ' + esc(p.name) : 'Hear ' + esc(p.name) + '’s sound here'}">${icon('speaker')}</button>
             <button class="btn-icon lg ${mic && mic.phase !== 'refused' && mic.phase !== 'failed' ? 'on' : ''}" data-act="mic" data-pid="${p.id}" ${p.connected ? '' : 'disabled'} title="${mic ? 'Stop using this microphone on ' + esc(p.name) : 'Use this microphone on ' + esc(p.name)}">${icon('mic')}</button>
             <button class="btn-quiet" data-act="view" data-pid="${p.id}" ${p.connected ? '' : 'disabled'}>${icon('monitor')}<span>Screen</span></button>
             <button class="btn-quiet" data-act="send" data-pid="${p.id}" ${p.connected ? '' : 'disabled'}>${icon('send')}<span>Send files</span></button>
             <button class="btn-icon lg" data-act="more" data-pid="${p.id}" title="More">${icon('more')}</button>`
          : `<button class="btn-primary inline" data-act="pair" data-pid="${p.id}">Pair</button>`;
        return `<div class="peer-row" data-pid="${p.id}"><div class="ic">${icon(OS_ICON[p.platform] || 'monitor')}</div>
          <div class="t"><b>${esc(p.name)}</b><span>${sub}</span></div><div class="acts">${acts}</div></div>`;
      }).join('');
    }
    if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
  }

  function ago(ts) {
    const s = Math.max(0, Date.now() / 1000 - ts);
    return s < 60 ? 'now' : s < 3600 ? Math.floor(s / 60) + 'm' : s < 86400 ? Math.floor(s / 3600) + 'h' : Math.floor(s / 86400) + 'd';
  }

  function renderPhones(a, phones) {
    const el = $('#phones');
    const html = !phones.length
      ? `<div class="empty">Get Kvm for Android from <a href="#" data-act="site">kvm.pxlvzn.in</a>, then pair it here to see its notifications, share the clipboard and send photos and files both ways.</div>`
      : phones.map((p) => {
        const ph = p.phone || {};
        const bat = ph.battery != null ? ` · ${ph.battery}%${ph.charging ? ' charging' : ''}` : '';
        const n = (ph.notifs || []).length;
        return `<div class="peer-row" data-pid="${p.id}"><div class="ic">${icon('phone')}</div>
          <div class="t"><b>${esc(p.name)}</b><span><i class="dotst ${p.connected ? 'on' : ''}"></i>${p.connected ? 'Connected' : 'Not connected · open Kvm on the phone'}${bat}</span></div>
          <div class="acts">
            <button class="btn-quiet" data-act="notifs" data-pid="${p.id}">${icon('bell')}<span>${n ? n + ' notification' + (n > 1 ? 's' : '') : 'Notifications'}</span></button>
            <button class="btn-quiet" data-act="send" data-pid="${p.id}" ${p.connected ? '' : 'disabled'}>${icon('send')}<span>Send files</span></button>
            <button class="btn-icon lg" data-act="phone-more" data-pid="${p.id}" title="More">${icon('more')}</button></div></div>`;
      }).join('');
    if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
    if (pairModal && pairModal.kind === 'notifs') renderNotifs(pairModal.pid);
    if (pairModal && pairModal.kind === 'qr' && a.qr) pairModal.seen = true;
    if (pairModal && pairModal.kind === 'qr' && pairModal.seen && !a.qr) {
      const done = a.pairing && a.pairing.phone && a.pairing.phase === 'done';
      closeModal();
      if (!done) toast('The pairing code ran out. Show a new one to pair a phone.', true);
    }
  }

  function renderNotifs(pid) {
    const p = ((st.agent && st.agent.peers) || []).find((x) => x.id === pid);
    const list = (p && p.phone && p.phone.notifs) || [];
    const html = list.length ? list.map((n) => `<div class="notif"><div class="t"><b>${esc(n.app || '')}${n.title ? ' · ' + esc(n.title) : ''}</b>
        <span>${esc(n.text || '')}</span></div><span class="faint">${ago(n.ts)}</span>
        <button class="btn-icon" data-act="notif-x" data-pid="${pid}" data-key="${esc(n.key)}" title="Clear on the phone">${icon('x')}</button></div>`).join('')
      : '<div class="empty">No notifications on the phone right now.</div>';
    const el = $('#notif-list');
    if (el && el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
  }

  async function pairPhone() {
    const r = await api.pair_phone();
    if (!r) return;
    const m = modal(`<div class="modal-title"><h2>Pair a phone</h2></div>
      <p class="lead">Open Kvm on the phone, tap <b>Scan the code</b> and point it at this. The phone must be on the same Wi-Fi as this computer.</p>
      <div class="qr">${r.svg}</div>
      <p class="faint center">This code works once, for the next 5 minutes.</p>
      <div class="foot"><button class="btn-quiet" data-act="qr-cancel">Cancel</button></div>`);
    m.parentElement.dataset.sticky = '1';
    pairModal = { kind: 'qr' };
  }

  function renderTransfers(a) {
    const ts = a.transfers || [];
    $('#transfers-head').classList.toggle('hidden', !ts.length);
    const html = ts.map((t) => {
      const pct = t.total ? Math.round(100 * t.done / t.total) : (t.phase === 'sent' || t.phase === 'received' ? 100 : 0);
      const verb = { sending: `Sending to ${t.peer_name}`, receiving: `From ${t.peer_name}`, sent: `Sent to ${t.peer_name}`,
        received: `Received from ${t.peer_name}`, failed: 'Didn’t finish', cancelled: 'Cancelled' }[t.phase] || t.phase;
      const live = t.phase === 'sending' || t.phase === 'receiving';
      return `<div class="tr-row"><div class="ic">${icon(t.count > 1 ? 'folder' : 'file')}</div><div class="t"><b>${esc(t.label)}</b>
        <span class="${t.error ? 'err' : ''}">${esc(t.error || verb)} · ${human(live ? t.done : t.total)}${live ? ' of ' + human(t.total) : ''}</span>
        ${live ? `<div class="bar"><div style="width:${pct}%"></div></div>` : ''}</div>
        ${live ? `<button class="btn-icon" data-act="cancel-tr" data-tid="${t.id}" title="Cancel">${icon('x')}</button>` : ''}
        ${t.phase === 'received' && t.open ? `<button class="btn-icon" data-act="reveal" data-path="${esc(t.open)}" title="Show">${icon('reveal')}</button>` : ''}</div>`;
    }).join('');
    const el = $('#transfers');
    if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
  }

  // ---------------------------------------------------------------- pairing
  function renderPairing(a) {
    const p = a.pairing;
    if (!p) {
      if (pairModal && !['address', 'notifs', 'qr'].includes(pairModal.kind)) closeModal();
      return;
    }
    if (p.role === 'responder' && p.phase === 'showing') {
      if (!pairModal || pairModal.kind !== 'show' || pairModal.code !== p.code) {
        const m = modal(`<div class="modal-title"><h2>Pair with ${esc(p.peer)}</h2></div>
          <p class="lead">Type this code on ${esc(p.peer)} to pair. Only computers you pair can use this one.</p>
          <div class="code-big">${esc(p.code.slice(0, 3))} ${esc(p.code.slice(3))}</div>
          <div class="foot"><button class="btn-quiet" data-act="pair-cancel">Cancel</button></div>`);
        m.parentElement.dataset.sticky = '1';
        pairModal = { kind: 'show', code: p.code };
      }
    } else if (p.role === 'initiator' && (p.phase === 'connecting' || p.phase === 'code' || p.phase === 'checking')) {
      if (!pairModal || pairModal.kind !== 'enter') {
        const m = modal(`<div class="modal-title"><h2>Pair with ${esc(p.peer || 'computer')}</h2></div>
          <p class="lead" id="pair-lead">Connecting…</p>
          <div class="code-in" id="code-in">${[0, 1, 2, 3, 4, 5].map((i) => (i === 3 ? '<span class="gap"></span>' : '') + `<input maxlength="1" inputmode="numeric" data-i="${i}">`).join('')}</div>
          <div class="foot"><button class="btn-quiet" data-act="pair-cancel">Cancel</button><button class="btn-primary inline" id="pair-go" disabled>Pair</button></div>`);
        m.parentElement.dataset.sticky = '1';
        pairModal = { kind: 'enter' };
        wireCode(m);
      }
      const lead = $('#pair-lead');
      if (lead) lead.textContent = p.phase === 'connecting' ? 'Connecting…' : p.phase === 'checking' ? 'Checking…'
        : `Type the code ${p.peer} is showing now.`;
      const inputs = document.querySelectorAll('#code-in input');
      inputs.forEach((i) => { i.disabled = p.phase !== 'code'; });
      if (p.phase === 'code' && !pairModal.focused) { pairModal.focused = true; inputs[0] && inputs[0].focus(); }
    } else if (p.phase === 'done' && pairModal) {
      closeModal();
    } else if (p.phase === 'failed' && pairModal && pairModal.kind !== 'failed') {
      const m = modal(`<div class="modal-title"><h2>Didn’t pair</h2></div><p class="lead">${esc(p.error || 'Try again.')}</p>
        <div class="foot"><button class="btn-primary inline" data-act="pair-cancel">OK</button></div>`);
      pairModal = { kind: 'failed' };
      void m;
    }
  }

  function wireCode(m) {
    const inputs = [...m.querySelectorAll('#code-in input')];
    const go = $('#pair-go');
    const code = () => inputs.map((i) => i.value).join('');
    const check = () => { go.disabled = code().length !== 6; if (!go.disabled) submit(); };
    const submit = () => { api.pair_code(code()); };
    inputs.forEach((inp, i) => {
      inp.addEventListener('input', () => {
        inp.value = inp.value.replace(/\D/g, '').slice(-1);
        if (inp.value && inputs[i + 1]) inputs[i + 1].focus();
        check();
      });
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !inp.value && inputs[i - 1]) inputs[i - 1].focus();
      });
      inp.addEventListener('paste', (e) => {
        const t = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 6);
        if (t) { e.preventDefault(); t.split('').forEach((c, k) => { if (inputs[k]) inputs[k].value = c; }); check(); }
      });
    });
    go.addEventListener('click', submit);
  }

  function addByAddress() {
    const m = modal(`<div class="modal-title"><h2>Add by address</h2></div>
      <p class="lead">If the other computer doesn’t show up, type the address shown in its Kvm settings (for example 192.168.1.20).</p>
      <div class="key-row"><input id="addr" placeholder="192.168.1.20" spellcheck="false"></div>
      <div class="foot"><button class="btn-quiet" data-act="close">Cancel</button><button class="btn-primary inline" id="addr-go">Pair</button></div>`);
    pairModal = { kind: 'address' };
    const go = async () => { const v = $('#addr').value.trim(); if (!v) return; closeModal(); const ok = await api.add_address(v); if (!ok) toast('Couldn’t start pairing with ' + v, true); };
    $('#addr-go').addEventListener('click', go);
    $('#addr').addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
    setTimeout(() => $('#addr').focus(), 50);
    void m;
  }

  // ---------------------------------------------------------------- settings
  // ---------------------------------------------------------------- pages
  const PAGES = {
    overview: { title: 'Overview', sub: 'Your computers, where they sit, and what they’re doing.' },
    connection: { title: 'Connection', sub: 'Pair computers on this network, or add one by its address.' },
    phones: { title: 'Phones', sub: 'Notifications, clipboard and files with your Android phone.' },
    mouse: { title: 'Mouse', sub: 'Move the pointer past the edge of the screen to use the other computer.', sw: 'share_out' },
    keyboard: { title: 'Keyboard', sub: 'Type on whichever computer the pointer is on.' },
    clipboard: { title: 'Clipboard', sub: 'Copy on one computer, paste on the other.', sw: 'clipboard' },
    files: { title: 'Files', sub: 'Send files and folders, or copy and paste them between computers.', sw: 'files' },
    media: { title: 'Screen & sound', sub: 'What other computers may see, hear and use here.' },
    general: { title: 'General', sub: '' },
  };
  let page = 'overview';
  try { page = localStorage.getItem('kvm.page') || 'overview'; } catch (e) { /* private mode */ }
  if (!PAGES[page]) page = 'overview';
  let loginState = null;

  function setPage(name) {
    if (!PAGES[name]) return;
    page = name;
    try { localStorage.setItem('kvm.page', name); } catch (e) { /* ignore */ }
    document.querySelectorAll('#nav button[data-page]').forEach((b) => b.classList.toggle('on', b.dataset.page === name));
    document.querySelectorAll('.page').forEach((p) => p.classList.toggle('on', p.dataset.page === name));
    $('#page-title').textContent = PAGES[name].title;
    $('#page-sub').textContent = PAGES[name].sub;
    $('#scroll').scrollTop = 0;
    if (name === 'general' && api) api.login_state().then((r) => { loginState = r || {}; renderPages(true); });
    renderPages(true);
  }

  const isMacUI = () => info.platform === 'darwin';
  const meName = () => OS_NAME[((st && st.agent && st.agent.me) || {}).platform] || 'computer';
  const row = (title, sub, ctl) => `<div class="row"><div class="t"><b>${title}</b>${sub ? `<span>${sub}</span>` : ''}</div>${ctl || ''}</div>`;
  const swc = (key, on, scope = 'share') => `<span class="switch ${on ? 'on' : ''}" data-set="${key}" data-kind="bool" data-scope="${scope}"></span>`;
  const selc = (key, val, opts, kind = 'str') => `<select data-set="${key}" data-kind="${kind}">${opts.map(([v, l]) =>
    `<option value="${esc(v)}" ${String(val) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  const segc = (key, val, opts) => `<div class="seg">${opts.map(([v, l]) => `<button data-seg="${key}" data-v="${esc(v)}" class="${val === v ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>`;
  const rangec = (key, val, min, max, step, unit) => `<div class="rng"><input type="range" data-set="${key}" data-kind="num" min="${min}" max="${max}" step="${step}" value="${val}"
    data-unit="${unit}"><span class="v">${unit === '×' ? (+val).toFixed(2) + '×' : Math.round(val) + ' ' + unit}</span></div>`;
  const group = (label, rows) => `${label ? `<div class="label">${label}</div>` : ''}<div class="group">${rows.join('')}</div>`;
  const kbd = (s) => `<kbd>${esc(s)}</kbd>`;

  function dirCards(left, right) {
    const a = st.agent, me = a.me;
    const others = (a.peers || []).filter((p) => p.paired && !isPhone(p));
    const other = others.length === 1 ? others[0].name : 'other computers';
    const oIcon = others.length === 1 ? (OS_ICON[others[0].platform] || 'monitor') : 'monitor';
    const head = (from, fi, to, ti) => `<div class="dh">${icon(fi)}<b>${esc(from)}</b><i class="arrow"></i>${icon(ti)}<b>${esc(to)}</b></div>`;
    return `<div class="dirs"><div class="dir">${head(me.name, OS_ICON[me.platform] || 'monitor', other, oIcon)}${left}</div>
      <div class="dir">${head(other, oIcon, me.name, OS_ICON[me.platform] || 'monitor')}${right}</div></div>`;
  }

  function pageHTML(name, a) {
    const s = a.settings || {}, mac = isMacUI();
    const others = (a.peers || []).filter((p) => p.paired && !isPhone(p));
    const other = others.length === 1 ? others[0].name : 'other computers';
    if (name === 'mouse') {
      return dirCards(
        row(`Use this ${meName()}’s mouse and keyboard on ${esc(other)}`, 'Push the pointer past the edge.', swc('share_out', s.share_out)),
        row(`Let ${esc(other)} use this ${meName()}`, 'Its pointer can come onto this screen.', swc('accept_in', s.accept_in)))
        + group('Cursor lock', [
          row('Lock the cursor', `Keeps the pointer on this screen even when you push past the edge. Press ${kbd(mac ? 'F14' : 'Scroll Lock')} on either keyboard to lock or unlock it.`, ''),
        ])
        + group('Coming back', [
          row('Return shortcut', 'Brings the pointer back to this computer from anywhere.', kbd(hk(s.return_hotkey))),
          row('Shake to bring the pointer back', 'While you use another computer, shake the mouse or trackpad left and right: the pointer comes back here.', swc('shake_home', s.shake_home)),
        ])
        + `<div class="label">Where the other computer is</div><div class="group"><div class="row"><div class="t"><span>Drag each screen of the other computer to where it sits on your desk, on the <a href="#" data-go="overview">Overview</a>. The pointer crosses only where the screens touch.</span></div></div></div>`
        + group('Feel', [
          row('Edge resistance', 'Push a little further past the edge to cross.', rangec('edge_resistance', s.edge_resistance || 0, 0, 200, 5, 'px')),
          row('Hold a key to cross', 'The pointer only leaves this screen while it’s held.', selc('cross_modifier', s.cross_modifier || '',
            [['', 'None'], ['ctrl', mac ? 'Control' : 'Ctrl'], ['alt', mac ? 'Option' : 'Alt'], ['shift', 'Shift'], ['meta', mac ? 'Command' : 'Windows']])),
          row('Pointer speed on the other computer', '', rangec('speed', s.speed || 1, 0.5, 3, 0.05, '×')),
          row(`Reverse scrolling from ${esc(other)}`, 'Flips the scroll direction of the other computer’s mouse here.', swc('reverse_scroll', s.reverse_scroll)),
        ]);
    }
    if (name === 'keyboard') {
      const keysOpts = [['', 'Off'], ['rshift', mac ? 'Right Shift ⇧' : 'Right Shift'], ['lshift', 'Left Shift'], ['rctrl', mac ? 'Right Control ⌃' : 'Right Ctrl'],
        ['ralt', mac ? 'Right Option ⌥' : 'Right Alt'], ['rmeta', mac ? 'Right Command ⌘' : 'Right Windows']];
      return group('Hotkey', [
        row('Sharing hotkey', 'Double-tap to turn keyboard and mouse sharing on or off.', selc('toggle_key', s.toggle_key || '', keysOpts)),
        row('Bring the pointer back', 'Works on either keyboard.', kbd(hk(s.return_hotkey))),
      ]) + dirCards(
        row(mac ? 'Shortcuts on Windows' : 'Shortcuts on a Mac', mac ? '⌘ works as Ctrl, so ⌘C copies there.' : 'Ctrl works as ⌘, so Ctrl+C copies there.', swc('swap_cmd_ctrl', s.swap_cmd_ctrl)),
        row('Keys that only one has', 'Media, volume and brightness keys carry over. Ctrl+Alt+Del reaches Windows, even its sign-in screen.', ''));
    }
    if (name === 'clipboard') {
      return group('Options', [
        row('Sync', s.clip_mode === 'switch' ? 'What you copy goes over when the pointer moves to the other computer.' : 'As soon as you copy.',
          segc('clip_mode', s.clip_mode || 'instant', [['switch', 'When you switch'], ['instant', 'Instantly']])),
        row('Pictures', 'Screenshots and copied images, up to 24 MB.', swc('clipboard_images', s.clipboard_images)),
        row('Skip passwords', 'From password managers (1Password, Bitwarden, Keychain and others).', `<span class="switch ${!s.clipboard_secrets ? 'on' : ''}" data-set="clipboard_secrets" data-kind="bool" data-invert="1"></span>`),
        row('Largest text', 'Longer text isn’t shared.', selc('clip_max_kb', s.clip_max_kb || 256, [[64, '64 KB'], [256, '256 KB'], [1024, '1 MB'], [4096, '4 MB']], 'num')),
        row('Recent items', 'Kept in memory only, never saved to disk.', selc('clip_recent', s.clip_recent == null ? 20 : s.clip_recent, [[0, 'Off'], [10, '10 items'], [20, '20 items'], [50, '50 items']], 'num')),
      ]);
    }
    if (name === 'files') {
      const live = others.filter((p) => p.connected);
      return `<div class="drop card"><div>${icon('send')}<b>Drop files or folders here</b><span>Or drag them onto a computer anywhere in Kvm.</span></div>
          <div class="acts">${live.map((p) => `<button class="btn-quiet" data-act="send" data-pid="${p.id}">Send to ${esc(p.name)}…</button>`).join('') || '<span class="faint">Connect a computer to send files.</span>'}</div></div>`
        + group('Copy and paste files', [
          row('Copy and paste files between computers', `Select files, press ${kbd(mac ? '⌃⌥C' : 'Ctrl+Alt+C')}, then paste on the other computer with ${kbd(mac ? '⌘V' : 'Ctrl+V')} or ${kbd(mac ? '⌃⌥V' : 'Ctrl+Alt+V')}.`, swc('file_keys', s.file_keys)),
        ])
        + group('Arriving files', [
          row('Save to', esc(a.receive_dir || ''), `<button class="btn-quiet" data-act="pick-dir">Choose…</button><button class="btn-quiet" data-act="reveal" data-path="${esc(a.receive_dir || '')}">Open</button>`),
        ]);
    }
    if (name === 'media') {
      return group('Screen', [
        row('Share this screen', 'Paired computers can see it in a Kvm window.', swc('screen_share', s.screen_share)),
        row('Allow control from the viewer', 'They can also click and type on it from that window.', swc('screen_control', s.screen_control)),
        row('Be a display for paired computers', 'A paired Mac can use this screen as an extra display. It opens full screen; close it to stop.', swc('display_accept', s.display_accept)),
      ]) + group('Sound', [
        row('Share this computer’s sound', 'Paired computers can hear what plays here.', swc('sound_share', s.sound_share)),
        row('Take a microphone from paired computers', mac ? 'Their microphone plays into BlackHole, so apps here can use it.' : 'Their microphone plays into VB-CABLE, so apps here can use it.', swc('mic_accept', s.mic_accept)),
      ]) + group('Camera', [
        row('Share this computer’s camera', 'Paired computers can use it, in a Kvm window or as a webcam.', swc('camera_share', s.camera_share)),
      ]) + group('Actions', [
        row('Ring, lock and sleep from paired computers', 'Lets a paired computer find, lock or put this one to sleep.', swc('remote_actions', s.remote_actions)),
        row('Show phone notifications', 'Notifications from a paired phone also show up here.', swc('phone_notifs', s.phone_notifs)),
      ]);
    }
    if (name === 'general') {
      const u = info.update || {}, lg = loginState || {};
      return group('This computer', [
        row('Name', 'How other computers see this one.', `<input class="field" id="set-name" value="${esc(a.me.name)}">`),
        row('Address', 'Type it into Kvm on the other computer if it doesn’t show up.', `<span class="v sel">${esc((a.me.addresses || []).join(', '))}${a.me.port !== 47610 ? ':' + a.me.port : ''}</span>`),
        ...(lg.supported ? [row('Open at login', 'Kvm runs in the background so the other computer can reach this one.', `<span class="switch ${lg.on ? 'on' : ''}" data-login="1"></span>`)] : []),
      ]) + group('Updates', [
        row(`Kvm ${esc(info.version)}`, `<span id="upd-line">${esc(updLine(u))}</span>`, '<button class="btn-quiet" data-act="check-upd">Check now</button>'),
        row('Check for updates automatically', 'Kvm asks GitHub for new releases every few hours.', swc('auto_check', info.settings.auto_check, 'app')),
        row('Install updates automatically', 'Downloads in the background and installs when Kvm quits.', swc('auto_install', info.settings.auto_install, 'app')),
      ]) + `<p class="hint">Kvm talks only to computers you pair, over your own network, encrypted end to end. No account and no cloud. <button class="link" data-act="site">kvm.pxlvzn.in</button></p>
        <div class="foot"><button class="btn-quiet" data-act="quit">Quit Kvm</button></div>`;
    }
    if (name === 'connection') {
      return group('This computer', [
        row(esc(a.me.name), 'Its address', `<span class="v sel">${esc((a.me.addresses || []).join(', '))}${a.me.port !== 47610 ? ':' + a.me.port : ''}</span>`),
      ]);
    }
    return '';
  }

  function renderClips(a) {
    const el = $('#pg-clips');
    if (!el) return;
    const clips = a.clips || [];
    const html = `<div class="section-head"><h3>Recent</h3><span class="spacer"></span>${clips.length ? '<button class="link" data-act="clips-clear">Clear</button>' : ''}</div>
      <div class="group">${clips.length ? clips.map((c, i) => `<div class="row clip"><div class="t"><b>${c.kind === 'text' ? esc(c.data.slice(0, 140)) : 'Picture'}</b>
        <span>${c.from ? 'From ' + esc(c.from) : 'Copied here'} · ${ago(c.ts)}</span></div>${c.kind === 'text' ? `<button class="btn-quiet" data-act="clip-use" data-i="${i}">Copy</button>` : ''}</div>`).join('')
        : '<div class="row"><div class="t"><span>Nothing yet. What’s copied on either computer shows here.</span></div></div>'}</div>`;
    if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
  }

  function renderPages(force) {
    const a = st && st.agent;
    if (!a) return;
    const meta = PAGES[page] || {};
    const psw = $('#page-switch');
    psw.classList.toggle('hidden', !meta.sw);
    if (meta.sw) { psw.classList.toggle('on', !!a.settings[meta.sw]); psw.dataset.set = meta.sw; psw.dataset.kind = 'bool'; psw.dataset.scope = 'share'; }
    const el = $('#pg-' + page) || (page === 'connection' ? $('#pg-connection-top') : null);
    if (el) {
      const active = document.activeElement;
      const editing = active && el.contains(active) && (active.tagName === 'INPUT' || active.tagName === 'SELECT');
      const html = pageHTML(page, a);
      if ((force || !editing) && el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
    }
    if (page === 'clipboard') renderClips(a);
    // nav dots: what's on right now
    const live = (a.peers || []).some((p) => p.paired && p.connected && !isPhone(p));
    const phone = (a.peers || []).some((p) => p.connected && isPhone(p));
    const s = a.settings || {};
    const on = { overview: a.mode !== 'home', connection: live, phones: phone, mouse: live && s.share_out, keyboard: live && s.share_out,
      clipboard: live && s.clipboard, files: live && s.files, media: live && (s.screen_share || s.sound_share) };
    document.querySelectorAll('#nav button[data-page]').forEach((b) => b.classList.toggle('live', !!on[b.dataset.page]));
    // the computers in the sidebar
    const side = (a.peers || []).filter((p) => p.paired && !isPhone(p)).map((p) => `<button class="sp ${a.active === p.id ? 'active' : ''}" data-go="overview">
      ${icon(OS_ICON[p.platform] || 'monitor')}<span class="t"><b>${esc(p.name)}</b><span>${p.connected ? (a.active === p.id ? (a.mode === 'driving' ? 'Using it now' : 'Using this one') : 'Connected') : 'Not connected'}</span></span>
      <i class="dotst ${p.connected ? 'on' : ''}"></i></button>`).join('');
    const sp = $('#side-peers');
    if (sp.dataset.html !== side) { sp.dataset.html = side; sp.innerHTML = side; }
  }

  // settings controls on the pages
  async function setOne(el, value) {
    const key = el.dataset.set;
    if (el.dataset.scope === 'app') { info.settings = await api.set_setting(key, value); return; }
    const r = await api.set_share(key, value);
    if (r && st && st.agent) st.agent.settings = r;
    renderPages(true);
  }
  document.addEventListener('click', async (e) => {
    const n = e.target.closest('#nav button[data-page], [data-go]');
    if (n) { e.preventDefault(); setPage(n.dataset.page || n.dataset.go); return; }
    const sw = e.target.closest('.switch[data-set]');
    if (sw) {
      const on = !sw.classList.contains('on');
      sw.classList.toggle('on', on);
      await setOne(sw, sw.dataset.invert ? !on : on);
      return;
    }
    const sg = e.target.closest('[data-seg]');
    if (sg) { sg.parentElement.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b === sg)); await setOne({ dataset: { set: sg.dataset.seg } }, sg.dataset.v); return; }
    const lg = e.target.closest('[data-login]');
    if (lg) { const r = await api.set_login(!lg.classList.contains('on')); lg.classList.toggle('on', !!(r && r.on)); loginState = r || loginState; }
  });
  document.addEventListener('input', (e) => {
    const r = e.target.closest('input[type=range][data-set]');
    if (r) { const v = r.parentElement.querySelector('.v'); if (v) v.textContent = r.dataset.unit === '×' ? (+r.value).toFixed(2) + '×' : Math.round(r.value) + ' ' + r.dataset.unit; }
  });
  document.addEventListener('change', async (e) => {
    const c = e.target.closest('select[data-set], input[type=range][data-set]');
    if (c) { await setOne(c, c.dataset.kind === 'num' || c.type === 'range' ? +c.value : c.value); return; }
    if (e.target.id === 'set-name') api.rename(e.target.value);
  });

  function updLine(u) {
    if (!u) return '';
    return { checking: 'Checking…', uptodate: 'Up to date', available: `Version ${u.latest} is available`, downloading: `Downloading ${u.latest}… ${Math.round((u.progress || 0) * 100)}%`,
      ready: `Version ${u.latest || ''} is ready to install`, installing: 'Installing…', failed: u.error || 'Update check failed' }[u.phase] || '';
  }

  function renderUpdate() {
    const u = info.update || {};
    const pill = $('#update-pill');
    const show = ['available', 'downloading', 'ready'].includes(u.phase);
    pill.classList.toggle('hidden', !show);
    if (show) pill.innerHTML = icon('download') + `<span>${u.phase === 'ready' ? 'Restart to update' : u.phase === 'downloading' ? `Updating ${Math.round((u.progress || 0) * 100)}%` : `Update to ${esc(u.latest)}`}</span>`;
    const l = $('#upd-line');
    if (l) l.textContent = updLine(u);
  }

  // ---------------------------------------------------------------- actions
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-act]');
    if (!b) return;
    const pid = b.dataset.pid;
    switch (b.dataset.act) {
      case 'close': closeModal(); break;
      case 'pair': api.pair(pid); break;
      case 'pair-cancel': api.pair_cancel(); closeModal(); break;
      case 'qr-cancel': api.pair_phone_cancel(); closeModal(); break;
      case 'notifs': {
        const p = (st.agent.peers || []).find((x) => x.id === pid) || {};
        modal(`<div class="modal-title"><h2>${esc(p.name)}</h2><span class="spacer"></span><button class="btn-icon" data-act="close">${icon('x')}</button></div>
          <div class="notifs" id="notif-list"></div>`);
        pairModal = { kind: 'notifs', pid };
        renderNotifs(pid);
        break;
      }
      case 'notif-x': api.notif_dismiss(pid, b.dataset.key); setTimeout(poll, 50); break;
      case 'phone-more': {
        const p = (st.agent.peers || []).find((x) => x.id === pid) || {};
        openMenu(b, [
          { icon: 'bell', label: `Ring ${p.name}`, run: () => api.remote_action(pid, 'ring') },
          { icon: 'send', label: 'Send files…', run: () => api.send_files(pid, false) },
          '-',
          { icon: 'unlink', label: 'Unpair', danger: true, run: () => api.forget(pid) },
        ]);
        break;
      }
      case 'send': api.send_files(pid, false); break;
      case 'view': {
        const r = await api.open_viewer(pid);
        if (r && r.error) toast(r.error, true);
        break;
      }
      case 'more': {
        const p = (st.agent.peers || []).find((x) => x.id === pid) || {};
        openMenu(b, [
          { icon: 'monitor', label: `See ${p.name}'s screen`, run: () => api.open_viewer(pid) },
          ...((st.agent.extend && st.agent.extend.can) ? [(st.agent.extend.out || {})[pid]
            ? { icon: 'monitor', label: `Stop using ${p.name} as a display`, run: () => api.extend(pid, false) }
            : { icon: 'monitor', label: `Use ${p.name} as a display for this Mac`, run: async () => { const r = await api.extend(pid, true); if (r && r.error) toast(r.error, true); } }] : []),
          { icon: 'camera', label: `Use ${p.name}'s camera`, run: async () => { const r = await api.open_camera(pid); if (r && r.error) toast(r.error, true); } },
          { icon: 'send', label: 'Send files…', run: () => api.send_files(pid, false) },
          { icon: 'folder', label: 'Send a folder…', run: () => api.send_files(pid, true) },
          '-',
          { icon: 'bell', label: `Ring ${p.name}`, run: () => api.remote_action(pid, 'ring') },
          { icon: 'lock', label: `Lock ${p.name}`, run: () => api.remote_action(pid, 'lock') },
          { icon: 'moon', label: `Put ${p.name} to sleep`, run: () => api.remote_action(pid, 'sleep') },
          '-',
          ...(p.side ? [{ icon: 'x', label: 'Take off the desk', run: () => api.set_side(pid, null) }] : []),
          { icon: 'unlink', label: 'Unpair', danger: true, run: () => api.forget(pid) },
        ]);
        break;
      }
      case 'desk-reset':
        e.preventDefault();
        for (const p of (st.agent.peers || []).filter((x) => x.layout_set)) await api.reset_layout(p.id);
        $('#desk').dataset.key = '';
        poll();
        break;
      case 'clip-use': if (await api.clip_use(+b.dataset.i)) toast('Copied'); break;
      case 'clips-clear': await api.clip_clear(); poll(); break;
      case 'addr-go': { const v = ($('#addr-input') || {}).value; if (v && v.trim()) { const r = await api.add_address(v.trim()); if (!r) toast('Couldn’t reach that address.', true); } break; }
      case 'stop-share': api.stop_sharing(); break;
      case 'extend-stop': api.extend(pid, false); break;
      case 'stop-camera': api.stop_camera(); break;
      case 'listen': case 'mic': {
        const cur = st.agent.sound && st.agent.sound[b.dataset.act === 'listen' ? 'hear' : 'mic'][pid];
        const on = !(cur && cur.phase !== 'refused' && cur.phase !== 'failed');
        const r = await api[b.dataset.act](pid, on);
        if (r && r.error) toast(r.error, true);
        poll();
        break;
      }
      case 'listen-drop': api.stop_sound(); break;
      case 'cancel-tr': api.cancel_transfer(b.dataset.tid); break;
      case 'reveal': api.reveal(b.dataset.path); break;
      case 'perm-ask': api.request_permissions(); break;
      case 'perm-open': api.open_privacy(b.dataset.which); break;
      case 'get-setup': api.open_url(info.site); break;
      case 'pick-dir': await api.pick_receive_dir(); poll(); break;
      case 'check-upd': info.update = await api.check_updates(); renderUpdate(); break;
      case 'site': api.open_url(info.site); break;
      case 'quit': api.quit(); break;
    }
  });
  $('#add-address').addEventListener('click', addByAddress);
  $('#pair-phone').addEventListener('click', pairPhone);
  $('#home-btn').addEventListener('click', () => api.go_home());
  $('#lock-btn').addEventListener('click', () => api.set_locked(!(st.agent && st.agent.locked)));
  $('#open-received').addEventListener('click', () => st && st.agent && api.reveal(st.agent.receive_dir));
  $('#clear-transfers').addEventListener('click', () => api.clear_transfers());
  $('#update-pill').addEventListener('click', () => {
    const u = info.update || {};
    if (u.phase === 'ready') api.install_update();
    else if (u.phase === 'available') api.download_update();
  });

  // dragging computers onto the desk
  let dragPid = null;
  document.addEventListener('dragstart', (e) => {
    const w = e.target.closest && e.target.closest('.screen-wrap');
    if (w) { dragPid = w.dataset.pid; e.dataTransfer.setData('text/plain', 'kvm:' + dragPid); e.dataTransfer.effectAllowed = 'move'; }
  });
  document.addEventListener('dragend', () => { dragPid = null; $('#desk').classList.remove('over'); });
  document.addEventListener('dragover', (e) => {
    const files = !dragPid && e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files');
    if (dragPid) {
      const over = e.target.closest && e.target.closest('#desk');
      $('#desk').classList.toggle('over', !!over);
      if (over) e.preventDefault();
      return;
    }
    if (files) {
      e.preventDefault();
      $('#drop-veil').classList.remove('hidden');
      const row = e.target.closest && (e.target.closest('.peer-row[data-pid]') || e.target.closest('.screen-wrap[data-pid]') || e.target.closest('.peer-scr[data-pid]'));
      document.querySelectorAll('.peer-row.drop').forEach((r) => r !== row && r.classList.remove('drop'));
      if (row) { row.classList.add('drop'); dropTarget = row.dataset.pid; } else dropTarget = null;
    }
  });
  document.addEventListener('dragleave', (e) => { if (!e.relatedTarget) { $('#drop-veil').classList.add('hidden'); } });
  document.addEventListener('drop', (e) => {
    e.preventDefault();
    $('#drop-veil').classList.add('hidden');
    document.querySelectorAll('.peer-row.drop').forEach((r) => r.classList.remove('drop'));
    if (dragPid) {
      $('#desk').classList.remove('over');
      if (e.target.closest && e.target.closest('#desk')) api.set_side(dragPid, deskSide(e));
      dragPid = null;
      setTimeout(poll, 50);
    }
  });

  // Which side of this computer's screens a drop on the desk landed.
  function deskSide(e) {
    const mes = [...document.querySelectorAll('#desk .me-scr')].map((el) => el.getBoundingClientRect());
    if (!mes.length) return 'right';
    const L = Math.min(...mes.map((r) => r.left)), R = Math.max(...mes.map((r) => r.right));
    const T = Math.min(...mes.map((r) => r.top)), B = Math.max(...mes.map((r) => r.bottom));
    const fx = (e.clientX - (L + R) / 2) / Math.max(R - L, 1), fy = (e.clientY - (T + B) / 2) / Math.max(B - T, 1);
    return Math.abs(fx) >= Math.abs(fy) ? (fx > 0 ? 'right' : 'left') : (fy > 0 ? 'bottom' : 'top');
  }

  function onDropped(paths) {
    const peers = ((st && st.agent && st.agent.peers) || []).filter((p) => p.paired && p.connected);
    const pid = dropTarget || (peers.length === 1 ? peers[0].id : null);
    dropTarget = null;
    if (!pid) { toast('Drop the files on the computer to send them to.', true); return; }
    api.send_paths(pid, paths);
  }

  // ---------------------------------------------------------------- Python -> page
  window.App = {
    on(ev, data) {
      if (ev === 'update') { info.update = data; renderUpdate(); }
      else if (ev === 'toast') toast(data.text, data.err);
      else if (ev === 'dropped') onDropped(data.paths);
    },
  };

  async function poll() {
    try { st = await api.state(); render(); } catch (e) { /* the window is closing */ }
  }

  async function boot() {
    fillIcons();
    document.body.classList.add(info.platform === 'darwin' ? 'mac' : info.platform === 'win32' ? 'win' : 'other');
    info = await api.info();
    document.body.classList.remove('mac', 'win', 'other');
    document.body.classList.add(info.platform === 'darwin' ? 'mac' : info.platform === 'win32' ? 'win' : 'other');
    renderUpdate();
    await poll();
    setPage((new URLSearchParams(location.search)).get('page') || page);
    setInterval(poll, 400);
    setTimeout(() => { $('#splash').classList.add('out'); $('#app').classList.add('in'); }, DEMO ? 1900 : 1700);
    setTimeout(() => $('#splash') && $('#splash').remove(), 2400);
  }

  if (DEMO) {
    api = demoApi();
    boot();
  } else if (window.pywebview && window.pywebview.api) {
    api = window.pywebview.api; boot();
  } else {
    window.addEventListener('pywebviewready', () => { api = window.pywebview.api; boot(); });
  }

  // ---------------------------------------------------------------- demo (browser preview, site screenshots)
  function demoApi() {
    const scene = (new URLSearchParams(location.search)).get('scene') || 'home';
    const me = { id: 'me', name: 'Yuvraj’s MacBook Air', platform: 'mac', version: '1.0.0', screens: [[0, 0, 1470, 956]], port: 47610, addresses: ['192.168.1.14'] };
    const pc = { id: 'pc', name: 'Yuvraj-PC', platform: 'windows', paired: true, connected: true, online: true, side: 'right', screens: [[0, 0, 1920, 1080], [1920, 0, 2560, 1440]], layout_set: true,
      layout: [{ r: [0, 0, 1920, 1080], at: [-225, -1080] }, { r: [1920, 0, 2560, 1440], at: [1470, 150] }] };
    const state = {
      mode: 'app', error: null,
      agent: {
        me, mode: scene === 'driving' ? 'driving' : 'home', active: scene === 'driving' ? 'pc' : null, locked: false,
        peers: scene === 'empty' ? [] : [pc, ...(scene === 'pair' ? [] : [{ id: 'nb', name: 'Studio iMac', platform: 'mac', paired: false, online: true }]),
          { id: 'ph', name: 'Pixel 9', platform: 'android', paired: true, connected: true, online: true,
            phone: { battery: 81, charging: true, notifs: [{ key: 'a', app: 'WhatsApp', title: 'Mum', text: 'Dinner at 8?', ts: Date.now() / 1000 - 120 },
              { key: 'b', app: 'Gmail', title: 'Invoice #2291', text: 'Your invoice is ready.', ts: Date.now() / 1000 - 4000 }] } }],
        pairing: scene === 'pair' ? { role: 'responder', phase: 'showing', code: '481 096'.replace(' ', ''), peer: 'Studio iMac' } : null,
        transfers: scene === 'home' || scene === 'driving' ? [
          { id: 't1', dir: 'out', peer: 'pc', peer_name: 'Yuvraj-PC', label: 'Edit v3 - Final.mov', count: 1, total: 2.4e9, done: 1.5e9, phase: 'sending', started: 2 },
          { id: 't2', dir: 'in', peer: 'pc', peer_name: 'Yuvraj-PC', label: 'thumbnails', count: 24, total: 48e6, done: 48e6, phase: 'received', started: 1, open: '/x' },
        ] : [],
        settings: { clipboard: true, clipboard_images: true, swap_cmd_ctrl: true, cross_modifier: '', return_hotkey: 'ctrl+alt+esc', speed: 1.25, files: true, remote_actions: true,
          share_out: true, accept_in: true, toggle_key: 'rshift', edge_resistance: 0, reverse_scroll: false, shake_home: true, clip_mode: 'instant',
          clipboard_secrets: false, clip_max_kb: 256, clip_recent: 20, file_keys: true, phone_notifs: true, screen_share: false, sound_share: false },
        clips: [{ kind: 'text', data: 'https://kvm.pxlvzn.in/download', from: 'Yuvraj-PC', ts: Date.now() / 1000 - 40 },
          { kind: 'image', data: '', from: null, ts: Date.now() / 1000 - 600 }, { kind: 'text', data: 'Meeting notes: ship 1.7 on Friday', from: null, ts: Date.now() / 1000 - 3600 }],
        receive_dir: '~/Downloads/Kvm', notices: [], permissions: { needs: [] },
      },
    };
    const noop = async () => null;
    return new Proxy({
      info: async () => ({ version: '1.0.0', platform: 'darwin', settings: { auto_check: true, auto_install: true }, update: { phase: 'uptodate' }, site: 'https://kvm.pxlvzn.in' }),
      state: async () => state,
      login_state: async () => ({ supported: true, on: true }),
      pair_phone: async () => (state.agent.qr = true) && ({ svg: '<svg viewBox="0 0 10 10"><rect width="10" height="10" fill="#fff"/><rect x="1" y="1" width="3" height="3"/><rect x="6" y="1" width="3" height="3"/><rect x="1" y="6" width="3" height="3"/></svg>' }),
      set_side: async (pid, side) => { const p = state.agent.peers.find((x) => x.id === pid); if (p) p.side = side; },
      set_share: async (k, v) => { state.agent.settings[k] = v; return state.agent.settings; },
      clip_use: async () => true,
      clip_clear: async () => { state.agent.clips = []; },
      set_layout: async (pid, items) => { const p = state.agent.peers.find((x) => x.id === pid); if (p) { p.layout = items; p.layout_set = true; } return true; },
    }, { get: (t, k) => t[k] || noop });
  }
})();
