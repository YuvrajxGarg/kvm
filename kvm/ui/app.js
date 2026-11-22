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
    keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6.5 10h.01M10 10h.01M14 10h.01M17.5 10h.01M7.5 14h9"/>',
  };
  const icon = (n) => `<svg class="i" viewBox="0 0 24 24">${ICONS[n] || ''}</svg>`;
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const human = (n) => { if (!n) return '0 B'; const u = ['B', 'KB', 'MB', 'GB', 'TB']; let i = 0; while (n >= 1000 && i < 4) { n /= 1000; i++; } return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + u[i]; };
  const fillIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach((el) => { el.outerHTML = icon(el.dataset.icon); });
  const DEMO = location.search.includes('demo');
  const OS_ICON = { mac: 'laptop', windows: 'monitor', linux: 'monitor' };
  const OS_NAME = { mac: 'Mac', windows: 'Windows', linux: 'Linux' };
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
    const paired = peers.filter((p) => p.paired);
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
        ? placed.map((p) => `${p.name} is to the ${SIDE_NAME[p.side]}${p.connected ? '' : ' (not connected)'}`).join(' · ')
        : 'Drag it next to this one, where it sits on your desk.';
    }
    $('#home-btn').classList.toggle('hidden', a.mode === 'home');
    const lb = $('#lock-btn');
    lb.classList.toggle('hidden', a.mode !== 'driving' && !a.locked);
    lb.querySelector('span').textContent = a.locked ? 'Cursor locked' : 'Cursor lock';
    renderDesk(a, paired);
    renderPeers(a, peers);
    renderTransfers(a);
    // notices from the agent (pairing done, files received, ring)
    for (const n of a.notices || []) {
      if (n.id > seenNotice) { if (seenNotice) toast(n.text); seenNotice = n.id; }
    }
    renderPairing(a);
  }

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
        <span>macOS needs ${perm.needs.map((n) => n === 'accessibility' ? 'Accessibility' : 'Input Monitoring').join(' and ')} for Kvm in Privacy &amp; Security. Turn it on, then reopen Kvm.</span></div>
        <button class="btn-quiet" data-act="perm-ask">Ask again</button>
        <button class="btn-quiet" data-act="perm-open" data-which="${perm.needs[0]}">Open Settings</button></div>`);
    }
    if (info.platform === 'win32' && st && st.mode === 'app') {
      out.push(`<div class="banner info">${icon('shield')}<div class="t"><b>Admin prompts and the sign-in screen</b>
        <span>Install Kvm with Kvm-Setup so your other computer’s keyboard also works on Windows admin prompts and when this PC is locked.</span></div>
        <button class="btn-quiet" data-act="get-setup">Get the setup</button></div>`);
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

  function renderDesk(a, paired) {
    const bySide = {};
    paired.forEach((p) => { if (p.side) bySide[p.side] = p; });
    const unplaced = paired.filter((p) => !p.side);
    let html = '';
    for (const side of ['left', 'right', 'top', 'bottom']) {
      const p = bySide[side];
      html += `<div class="slot ${side} ${p ? 'filled' : ''}" data-side="${side}">${p
        ? `<div class="screen-wrap" draggable="true" data-pid="${p.id}">${screenHTML(p, 'peer' + (p.connected ? '' : ' offline') + (a.active === p.id ? ' active' : ''))}</div>`
        : (paired.length ? 'Drop here' : '')}</div>`;
    }
    html += `<div class="me">${screenHTML({ name: a.me.name, platform: a.me.platform, screens: a.me.screens }, a.mode === 'home' || a.mode === 'driven' ? (a.mode === 'driven' ? 'active' : '') : '')}</div>`;
    const key = JSON.stringify([html, unplaced.map((p) => [p.id, p.name, p.connected])]);
    const desk = $('#desk');
    if (desk.dataset.key !== key) {
      desk.dataset.key = key;
      desk.innerHTML = html;
      desk.querySelectorAll('.screen-wrap').forEach((w) => { w.style.position = 'absolute'; w.style.inset = '0'; });
    }
    const hint = $('#desk-hint');
    const trayKey = JSON.stringify(unplaced.map((p) => [p.id, p.name, p.connected, p.platform]));
    if (hint.dataset.key !== trayKey) {
      hint.dataset.key = trayKey;
      hint.innerHTML = unplaced.length
        ? `<div>Drag a computer to the side of this one where it really is.</div><div class="tray">${unplaced.map((p) =>
            `<div class="chip screen-wrap" draggable="true" data-pid="${p.id}">${screenHTML(p, 'peer' + (p.connected ? '' : ' offline'))}</div>`).join('')}</div>`
        : (paired.length ? 'Drag a computer to move it. Push the pointer past that edge to go there.' : '');
    }
  }

  function renderPeers(a, peers) {
    const el = $('#peers');
    let html;
    if (!peers.length) {
      html = `<div class="empty">No other computers found yet.<br>Open Kvm on the other computer on this Wi-Fi, or add it by its address.</div>`;
    } else {
      html = peers.map((p) => {
        const sub = p.paired
          ? `<i class="dotst ${p.connected ? 'on' : ''}"></i>${p.connected ? 'Connected' : (p.online ? 'Connecting…' : 'Not on this network')}${p.side ? ` · to the ${SIDE_NAME[p.side]}` : ''}`
          : `<i class="dotst"></i>Nearby · not paired`;
        const acts = p.paired
          ? `<button class="btn-quiet" data-act="view" data-pid="${p.id}" ${p.connected ? '' : 'disabled'}>${icon('monitor')}<span>Screen</span></button>
             <button class="btn-quiet" data-act="send" data-pid="${p.id}" ${p.connected ? '' : 'disabled'}>${icon('send')}<span>Send files</span></button>
             <button class="btn-icon lg" data-act="more" data-pid="${p.id}" title="More">${icon('more')}</button>`
          : `<button class="btn-primary inline" data-act="pair" data-pid="${p.id}">Pair</button>`;
        return `<div class="peer-row" data-pid="${p.id}"><div class="ic">${icon(OS_ICON[p.platform] || 'monitor')}</div>
          <div class="t"><b>${esc(p.name)}</b><span>${sub}</span></div><div class="acts">${acts}</div></div>`;
      }).join('');
    }
    if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
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
      if (pairModal && pairModal.kind !== 'address') closeModal();
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
  async function openSettings() {
    const a = st && st.agent;
    const s = (a && a.settings) || {};
    const login = (await api.login_state()) || {};
    const sw = (on, key, scope) => `<span class="switch ${on ? 'on' : ''}" data-key="${key}" data-scope="${scope}"></span>`;
    const opt = (title, sub, on, key, scope = 'share') => `<button class="opt" data-toggle="${key}" data-scope="${scope}"><span class="t"><b>${title}</b><span>${sub}</span></span>${sw(on, key, scope)}</button>`;
    const isMac = info.platform === 'darwin';
    const u = info.update || {};
    const m = modal(`<div class="modal-title"><div class="logomark"><span class="mark" style="--size:15px">kvm<span class="twin"><i class="a"></i><i class="dot"></i><i class="b"></i></span></span></div><h2>Settings</h2>
        <button class="btn-icon lg" data-act="close">${icon('x')}</button></div>
      <div class="label">This computer</div>
      <div class="group">
        <div><span class="k">Name</span><input class="field" id="set-name" value="${esc(a ? a.me.name : '')}" style="width:220px"></div>
        <div><span class="k">Address</span><span class="v">${esc(a ? (a.me.addresses || []).join(', ') : '')}${a && a.me.port !== 47610 ? ':' + a.me.port : ''}</span></div>
        ${login.supported ? `<button class="opt" data-login="1"><span class="t"><b>Open at login</b><span>Kvm runs in the background so the other computer can reach this one.</span></span>${sw(login.on, 'login', 'login')}</button>` : ''}
      </div>
      <div class="label">Keyboard and mouse</div>
      <div class="group">
        ${opt(isMac ? 'Use ⌘ as Ctrl on a PC' : 'Use Ctrl as ⌘ on a Mac', isMac ? '⌘C, ⌘V and other shortcuts work as Ctrl shortcuts on Windows.' : 'Ctrl shortcuts work as Command shortcuts on a Mac.', s.swap_cmd_ctrl, 'swap_cmd_ctrl')}
        <div><span class="k">Hold a key to cross<br><span class="hint">The pointer only leaves this screen while it’s held.</span></span>
          <select id="cross-mod">${[['', 'Off'], ['ctrl', isMac ? 'Control' : 'Ctrl'], ['alt', isMac ? 'Option' : 'Alt'], ['shift', 'Shift'], ['meta', isMac ? 'Command' : 'Windows']].map(([v, l]) =>
            `<option value="${v}" ${s.cross_modifier === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
        <div><span class="k">Pointer speed on the other computer</span><input type="range" id="speed" min="0.5" max="3" step="0.05" value="${s.speed || 1}"><span class="v" id="speed-v">${(+s.speed || 1).toFixed(2)}×</span></div>
        <div><span class="k">Bring the pointer back</span><span class="v"><kbd>${esc(hk(s.return_hotkey))}</kbd></span></div>
        <div><span class="k">Cursor lock (stay on this screen)</span><span class="v"><kbd>${isMac ? 'F14' : 'Scroll Lock'}</kbd></span></div>
      </div>
      <div class="label">Sharing</div>
      <div class="group">
        ${opt('Shared clipboard', 'Copy on one computer, paste on the other.', s.clipboard, 'clipboard')}
        ${opt('Pictures too', 'Screenshots and copied images, up to 24 MB.', s.clipboard_images, 'clipboard_images')}
        ${opt('Accept files', 'Files from paired computers are saved without asking.', s.files, 'files')}
        <div><span class="k">Save received files to</span><span class="v" style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(a ? a.receive_dir : '')}</span>
          <button class="btn-quiet" data-act="pick-dir">Change</button></div>
        ${opt('Ring, lock and sleep from paired computers', 'Lets a paired computer find, lock or put this one to sleep.', s.remote_actions, 'remote_actions')}
        ${opt('Share this screen', 'Paired computers can see this screen in a Kvm window.', s.screen_share, 'screen_share')}
        ${opt('Allow control from the viewer', 'They can also click and type on it from that window.', s.screen_control, 'screen_control')}
      </div>
      <div class="label">Updates</div>
      <div class="group">
        <div class="ver-row"><span class="t"><b>Kvm ${esc(info.version)}</b><span id="upd-line">${esc(updLine(u))}</span></span>
          <button class="btn-quiet" data-act="check-upd">Check now</button></div>
        ${opt('Check for updates automatically', 'Kvm asks GitHub for new releases every few hours.', info.settings.auto_check, 'auto_check', 'app')}
        ${opt('Install updates automatically', 'Downloads in the background and installs when Kvm quits.', info.settings.auto_install, 'auto_install', 'app')}
      </div>
      <p class="hint">Kvm talks only to computers you pair, over your own network, encrypted end to end. No account and no cloud. <button class="link" data-act="site">kvm.pxlvzn.in</button></p>
      <div class="foot"><button class="btn-quiet" data-act="quit">Quit Kvm</button><span class="spacer"></span><button class="btn-primary inline" data-act="close">Done</button></div>`, 'settings');
    m.addEventListener('click', async (e) => {
      const t = e.target.closest('[data-toggle]');
      if (t) {
        const swEl = t.querySelector('.switch');
        const on = !swEl.classList.contains('on');
        swEl.classList.toggle('on', on);
        if (t.dataset.scope === 'app') info.settings = await api.set_setting(t.dataset.toggle, on);
        else await api.set_share(t.dataset.toggle, on);
      }
      const l = e.target.closest('[data-login]');
      if (l) { const r = await api.set_login(!l.querySelector('.switch').classList.contains('on')); l.querySelector('.switch').classList.toggle('on', !!(r && r.on)); }
    });
    $('#set-name').addEventListener('change', (e) => api.rename(e.target.value));
    $('#cross-mod').addEventListener('change', (e) => api.set_share('cross_modifier', e.target.value));
    $('#speed').addEventListener('input', (e) => { $('#speed-v').textContent = (+e.target.value).toFixed(2) + '×'; });
    $('#speed').addEventListener('change', (e) => api.set_share('speed', +e.target.value));
  }

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
      case 'stop-share': api.stop_sharing(); break;
      case 'cancel-tr': api.cancel_transfer(b.dataset.tid); break;
      case 'reveal': api.reveal(b.dataset.path); break;
      case 'perm-ask': api.request_permissions(); break;
      case 'perm-open': api.open_privacy(b.dataset.which); break;
      case 'get-setup': api.open_url(info.site); break;
      case 'pick-dir': await api.pick_receive_dir(); openSettings(); break;
      case 'check-upd': info.update = await api.check_updates(); renderUpdate(); break;
      case 'site': api.open_url(info.site); break;
      case 'quit': api.quit(); break;
    }
  });
  $('#open-settings').addEventListener('click', openSettings);
  $('#add-address').addEventListener('click', addByAddress);
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
  document.addEventListener('dragend', () => { dragPid = null; document.querySelectorAll('.slot.over').forEach((s) => s.classList.remove('over')); });
  document.addEventListener('dragover', (e) => {
    const files = !dragPid && e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files');
    if (dragPid) {
      const slot = e.target.closest && e.target.closest('.slot');
      document.querySelectorAll('.slot.over').forEach((s) => s !== slot && s.classList.remove('over'));
      if (slot) { e.preventDefault(); slot.classList.add('over'); }
      return;
    }
    if (files) {
      e.preventDefault();
      $('#drop-veil').classList.remove('hidden');
      const row = e.target.closest && (e.target.closest('.peer-row[data-pid]') || e.target.closest('.screen-wrap[data-pid]'));
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
      const slot = e.target.closest && e.target.closest('.slot');
      if (slot) api.set_side(dragPid, slot.dataset.side);
      dragPid = null;
      setTimeout(poll, 50);
    }
  });

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
    const pc = { id: 'pc', name: 'Yuvraj-PC', platform: 'windows', paired: true, connected: true, online: true, side: 'right', screens: [[0, 0, 1920, 1080], [1920, 0, 2560, 1440]] };
    const state = {
      mode: 'app', error: null,
      agent: {
        me, mode: scene === 'driving' ? 'driving' : 'home', active: scene === 'driving' ? 'pc' : null, locked: false,
        peers: scene === 'empty' ? [] : [pc, ...(scene === 'pair' ? [] : [{ id: 'nb', name: 'Studio iMac', platform: 'mac', paired: false, online: true }])],
        pairing: scene === 'pair' ? { role: 'responder', phase: 'showing', code: '481 096'.replace(' ', ''), peer: 'Studio iMac' } : null,
        transfers: scene === 'home' || scene === 'driving' ? [
          { id: 't1', dir: 'out', peer: 'pc', peer_name: 'Yuvraj-PC', label: 'Edit v3 - Final.mov', count: 1, total: 2.4e9, done: 1.5e9, phase: 'sending', started: 2 },
          { id: 't2', dir: 'in', peer: 'pc', peer_name: 'Yuvraj-PC', label: 'thumbnails', count: 24, total: 48e6, done: 48e6, phase: 'received', started: 1, open: '/x' },
        ] : [],
        settings: { clipboard: true, clipboard_images: true, swap_cmd_ctrl: true, cross_modifier: '', return_hotkey: 'ctrl+alt+esc', speed: 1.25, files: true, remote_actions: true },
        receive_dir: '~/Downloads/Kvm', notices: [], permissions: { needs: [] },
      },
    };
    const noop = async () => null;
    return new Proxy({
      info: async () => ({ version: '1.0.0', platform: 'darwin', settings: { auto_check: true, auto_install: true }, update: { phase: 'uptodate' }, site: 'https://kvm.pxlvzn.in' }),
      state: async () => state,
      login_state: async () => ({ supported: true, on: true }),
      set_side: async (pid, side) => { const p = state.agent.peers.find((x) => x.id === pid); if (p) p.side = side; },
    }, { get: (t, k) => t[k] || noop });
  }
})();
