/* DM Game Master — vanilla frontend.
 *
 * Single page: sidebar campaign list + main chat. Two WS modes:
 *   game   — /ws/game?campaign=<name>&after_id=<n>  (persistent per campaign)
 *   wizard — /ws/wizard  (one-shot campaign creation, in-chat choices)
 *
 * Backend protocol (unchanged): stream, text, activity, error, done, history,
 * show_choices, clear_choices, wizard_complete.
 *
 * Streaming typewriter mirrors Orchestra's app.js: RAF loop, adaptive chunk,
 * ~20 DOM writes/sec, blink cursor. See _tick()/pushStream()/finalizeStream().
 */

// ─────────────────────────── Config ───────────────────────────────────────
const CAMPAIGN_POLL_MS = 5000;
const MAX_MESSAGES = 500;
const AUTOSCROLL_THRESHOLD_PX = 80;
const ACTIVITY_COLLAPSE_LEN = 200;

const STREAM_BASE_CPS = 12;        // min chars drawn per frame (Orchestra _STREAM_BASE_CPS)
const STREAM_PARSE_INTERVAL = 50;  // ms between visible re-parses (Orchestra _STREAM_PARSE_INTERVAL)

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_DELAY_MS = 30000;

const TOOL_BLOCK_RE = /```tool:\w+\s*\n\{[\s\S]*?\}\s*\n```/g;  // wizard strips inline tool blocks

// ─────────────────────────── DOM refs ─────────────────────────────────────
const el = {
  app: document.getElementById('app'),
  mobileHeader: document.querySelector('.mobile-header'),
  mobileBack: document.getElementById('mobile-back'),
  mobileNew: document.getElementById('mobile-new-btn'),
  mobileTitle: document.getElementById('mobile-title'),
  campaignList: document.getElementById('campaign-list'),
  newBtn: document.getElementById('new-campaign-btn'),
  welcomeNewBtn: document.getElementById('welcome-new-btn'),
  welcome: document.getElementById('welcome'),
  chatPane: document.getElementById('chat-pane'),
  chat: document.getElementById('chat'),
  titleText: document.getElementById('chat-title-text'),
  connStatus: document.getElementById('conn-status'),
  connLabel: document.querySelector('#conn-status .conn-label'),
  modelSelect: document.getElementById('model-select'),
  ctxUsage: document.getElementById('ctx-usage'),
  ctxFill: document.querySelector('#ctx-usage .ctx-fill'),
  ctxLabel: document.querySelector('#ctx-usage .ctx-label'),
  rightPanel: document.getElementById('right-panel'),
  choices: document.getElementById('choices'),
  wizardResetBtn: document.getElementById('wizard-reset-btn'),
  input: document.getElementById('input'),
  sendBtn: document.getElementById('send-btn'),
};

// ─────────────────────────── App state ────────────────────────────────────
const state = {
  mode: null,            // 'game' | 'wizard' | null
  campaign: null,        // active campaign name (game mode)
  ws: null,
  afterId: 0,            // replay cursor for game mode
  attempt: 0,            // reconnect attempts
  reconnectTimer: null,
  connStatus: 'disconnected',
  generating: false,     // a turn is in flight (show waiting indicator)
  localEcho: new Set(),  // "role:content" keys to dedup on history replay
  wizardFirstMsgSent: false,   // inject sidebar-preset context on first wizard message
  activeChoices: null,   // current wizard choices payload
  choiceSel: {},         // radio/checkbox selections {controlId: id | id[]}
  choiceText: {},        // text_input values {controlId: value}
};

// ─────────────────────────── Streaming buffer (Orchestra port) ────────────
const stream = {
  pending: '',      // raw deltas not yet drawn  (streamPending)
  shown: '',        // chars already drawn       (streamContent)
  raf: null,
  lastParse: 0,
  active: false,
  bubble: null,     // the .msg-dm element currently animating
  contentEl: null,  // its .markdown-body child
};

function _streamTick() {
  stream.raf = null;
  if (!stream.pending) return;
  // Adaptive chunk: catch up if the buffer is large (Orchestra Math.floor(len/8))
  const size = Math.max(STREAM_BASE_CPS, Math.floor(stream.pending.length / 8));
  stream.shown += stream.pending.slice(0, size);
  stream.pending = stream.pending.slice(size);

  const now = performance.now();
  if (now - stream.lastParse >= STREAM_PARSE_INTERVAL || !stream.pending) {
    stream.lastParse = now;
    renderStreamBubble(stream.shown);
    maybeAutoScroll();
  }
  if (stream.pending) stream.raf = requestAnimationFrame(_streamTick);
}

function pushStream(delta) {
  if (!stream.active) {
    stream.active = true;
    hideWaiting();
    createStreamBubble();
  }
  stream.pending += delta;
  if (stream.raf == null) stream.raf = requestAnimationFrame(_streamTick);
}

/** Flush the animation and return the full text. `final` overrides if given. */
function finalizeStream(final) {
  if (stream.raf != null) { cancelAnimationFrame(stream.raf); stream.raf = null; }
  const text = final != null ? final : (stream.shown + stream.pending);
  stream.pending = ''; stream.shown = ''; stream.lastParse = 0; stream.active = false;
  if (stream.bubble) { stream.bubble.remove(); stream.bubble = null; stream.contentEl = null; }
  return text;
}

function resetStream() {
  if (stream.raf != null) cancelAnimationFrame(stream.raf);
  stream.raf = null; stream.pending = ''; stream.shown = ''; stream.lastParse = 0; stream.active = false;
  if (stream.bubble) { stream.bubble.remove(); stream.bubble = null; stream.contentEl = null; }
}

function createStreamBubble() {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-dm';
  wrap.innerHTML = '<div class="msg-role">DM</div>';
  const body = document.createElement('div');
  body.className = 'msg-body streaming';
  const md = document.createElement('div');
  md.className = 'markdown-body';
  body.appendChild(md);
  const cursor = document.createElement('span');
  cursor.className = 'typing-cursor';
  cursor.textContent = '▍';
  body.appendChild(cursor);
  wrap.appendChild(body);
  el.chat.appendChild(wrap);
  stream.bubble = wrap;
  stream.contentEl = md;
}

function renderStreamBubble(text) {
  if (!stream.contentEl) return;
  stream.contentEl.innerHTML = renderMarkdown(cleanWizardText(text));
}

// ─────────────────────────── Markdown / sanitize ──────────────────────────
function renderMarkdown(text) {
  const raw = marked.parse(text || '', { breaks: true, gfm: true });
  return DOMPurify.sanitize(raw);
}

/** Wizard streams may contain inline ```tool:...``` blocks — strip them from display. */
function cleanWizardText(text) {
  return state.mode === 'wizard' ? text.replace(TOOL_BLOCK_RE, '').trim() : text;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ─────────────────────────── Chat rendering ───────────────────────────────
function clearChat() {
  el.chat.innerHTML = '';
  resetStream();
  hideWaiting();
}

function trimMessages() {
  // Keep last MAX_MESSAGES message/activity/error nodes (streaming bubble/waiting excluded)
  const nodes = el.chat.querySelectorAll('.msg, .msg-activity, .msg-error');
  for (let i = 0; i < nodes.length - MAX_MESSAGES; i++) nodes[i].remove();
}

function scrollAtBottom() {
  return el.chat.scrollHeight - el.chat.scrollTop - el.chat.clientHeight < AUTOSCROLL_THRESHOLD_PX;
}
let _stickBottom = true;
function maybeAutoScroll() {
  if (_stickBottom) el.chat.scrollTop = el.chat.scrollHeight;
}
el.chat.addEventListener('scroll', () => { _stickBottom = scrollAtBottom(); });

function addUserMessage(content) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-user';
  wrap.innerHTML = '<div class="msg-role">Игрок</div>';
  const body = document.createElement('div');
  body.className = 'msg-body';
  body.textContent = content;
  wrap.appendChild(body);
  insertBeforeStream(wrap);
  trimMessages(); maybeAutoScroll();
}

function addDmMessage(content) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-dm';
  wrap.innerHTML = '<div class="msg-role">DM</div>';
  const body = document.createElement('div');
  body.className = 'msg-body';
  const md = document.createElement('div');
  md.className = 'markdown-body';
  md.innerHTML = renderMarkdown(cleanWizardText(content));
  body.appendChild(md);
  wrap.appendChild(body);
  insertBeforeStream(wrap);
  trimMessages(); maybeAutoScroll();
}

function addActivity(content) {
  const div = document.createElement('div');
  div.className = 'msg-activity';
  const isLong = content.length > ACTIVITY_COLLAPSE_LEN;
  if (isLong) {
    div.classList.add('clickable');
    let expanded = false;
    const render = () => {
      const shown = expanded ? content : content.slice(0, ACTIVITY_COLLAPSE_LEN) + '…';
      div.innerHTML = `<span>${escapeHtml(shown)}</span><span class="activity-toggle"> ${expanded ? '[свернуть]' : '[показать всё]'}</span>`;
    };
    render();
    div.addEventListener('click', () => { expanded = !expanded; render(); });
  } else {
    div.textContent = content;
  }
  insertBeforeStream(div);
  trimMessages(); maybeAutoScroll();
}

function addError(content) {
  const div = document.createElement('div');
  div.className = 'msg-error';
  div.textContent = '⚠ ' + content;
  insertBeforeStream(div);
  trimMessages(); maybeAutoScroll();
}

/** Non-stream nodes must land BEFORE the streaming bubble/waiting indicator (Orchestra ordering). */
function insertBeforeStream(node) {
  const anchor = stream.bubble || el.chat.querySelector('.waiting');
  if (anchor) el.chat.insertBefore(node, anchor);
  else el.chat.appendChild(node);
}

// Waiting indicator (before first token) ------------------------------------
function showWaiting() {
  if (el.chat.querySelector('.waiting')) return;
  const div = document.createElement('div');
  div.className = 'waiting';
  div.innerHTML = '<span>DM печатает</span><span class="waiting-dots"><span>•</span><span>•</span><span>•</span></span>';
  el.chat.appendChild(div);
  maybeAutoScroll();
}
function hideWaiting() {
  const w = el.chat.querySelector('.waiting');
  if (w) w.remove();
}

function setGenerating(on) {
  state.generating = on;
  if (on) { if (!stream.active) showWaiting(); }
  else hideWaiting();
}

// ─────────────────────────── Connection status ────────────────────────────
const STATUS_LABEL = {
  connecting: 'Подключение…', connected: 'Подключено',
  reconnecting: 'Переподключение…', disconnected: 'Отключено', failed: 'Соединение потеряно',
};
function setConnStatus(s) {
  state.connStatus = s;
  el.connStatus.className = 'conn-status ' + s;
  el.connLabel.textContent = STATUS_LABEL[s] || s;
  updateInputEnabled();
}
function updateInputEnabled() {
  const connected = state.connStatus === 'connected';
  el.input.disabled = !connected;
  el.sendBtn.disabled = !connected || !el.input.value.trim();
}

// Context usage indicator ---------------------------------------------------
function updateCtxUsage(percent, used, total) {
  const pct = Math.max(0, Math.min(100, percent || 0));
  el.ctxUsage.hidden = false;
  el.ctxFill.style.width = pct + '%';
  el.ctxFill.style.background = pct > 80 ? 'var(--danger)' : pct >= 50 ? 'var(--warn)' : 'var(--ok)';
  el.ctxLabel.textContent = pct + '% ctx';
  el.ctxUsage.title = total ? `${(used || 0).toLocaleString()} / ${total.toLocaleString()} токенов контекста` : 'Использование контекста';
}
function hideCtxUsage() {
  el.ctxUsage.hidden = true;
  el.ctxFill.style.width = '0';
  el.ctxLabel.textContent = '0%';
}

// ─────────────────────────── WebSocket lifecycle ──────────────────────────
function closeWs() {
  if (state.reconnectTimer) { clearTimeout(state.reconnectTimer); state.reconnectTimer = null; }
  const sock = state.ws;
  state.ws = null;
  if (sock && (sock.readyState === WebSocket.OPEN || sock.readyState === WebSocket.CONNECTING)) {
    sock.onclose = null; sock.onmessage = null; sock.onerror = null; sock.onopen = null;
    sock.close();
  }
}

function gameUrl() {
  const params = new URLSearchParams({ campaign: state.campaign, after_id: String(state.afterId) });
  if (el.modelSelect.value) params.set('model', el.modelSelect.value);
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/game?${params.toString()}`;
}

function connect(url) {
  setConnStatus(state.attempt === 0 ? 'connecting' : 'reconnecting');
  const sock = new WebSocket(url);
  state.ws = sock;

  sock.onopen = () => {
    if (state.ws !== sock) return;
    state.attempt = 0;
    setConnStatus('connected');
  };

  sock.onmessage = (ev) => {
    if (state.ws !== sock) return;
    let data;
    try { data = JSON.parse(ev.data); } catch { return; }
    if (data && typeof data.id === 'number') state.afterId = data.id;  // bump replay cursor
    handleEvent(data);
  };

  sock.onerror = () => { /* onclose follows for failures */ };

  sock.onclose = (event) => {
    if (state.ws !== sock) return;
    state.ws = null;
    if (event.wasClean) { setConnStatus('disconnected'); return; }
    if (state.attempt >= MAX_RECONNECT_ATTEMPTS) { setConnStatus('failed'); return; }
    setConnStatus('reconnecting');
    const delay = Math.min(BASE_RECONNECT_DELAY_MS * 2 ** state.attempt, MAX_RECONNECT_DELAY_MS);
    state.attempt += 1;
    state.reconnectTimer = setTimeout(() => {
      if (state.mode === 'game') connect(gameUrl());
      else if (state.mode === 'wizard') connect(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/wizard`);
    }, delay);
  };
}

// ─────────────────────────── Event dispatch ───────────────────────────────
function handleEvent(data) {
  if (!data || !data.type) return;
  switch (data.type) {
    case 'stream':
      setGenerating(true);
      pushStream(data.content);
      break;

    case 'text': {
      const text = stream.active ? finalizeStream(data.content) : data.content;
      addDmMessage(text);
      break;
    }

    case 'activity':
      // finalize any in-flight stream first, then the tool line (correct order)
      if (stream.active) { const t = finalizeStream(); if (t.trim()) addDmMessage(t); }
      addActivity(data.content);
      break;

    case 'error':
      resetStream();
      setGenerating(false);
      addError(data.content);
      break;

    case 'history':
      renderHistory(data.messages || []);
      break;

    case 'usage':
      updateCtxUsage(data.percent, data.used, data.total);
      break;

    case 'done':
      // flush any leftover streamed text into a finalized bubble (wizard has no `text` event)
      if (stream.active) { const t = finalizeStream(); if (t.trim()) addDmMessage(t); }
      setGenerating(false);
      break;

    case 'show_choices':
      renderChoices(data.data);
      break;

    case 'clear_choices':
      clearChoices();
      break;

    case 'wizard_complete':
      onWizardComplete(data.campaign_name);
      break;
  }
}

/** Replay past events (game only). Each carries id/type/content; dedup local echoes. */
function renderHistory(messages) {
  resetStream();
  clearChat();
  for (const m of messages) {
    if (typeof m.id === 'number' && m.id > state.afterId) state.afterId = m.id;
    const role = m.type === 'user_message' ? 'user' : 'assistant';
    if (state.localEcho.has(`${role}:${m.content}`)) continue;
    if (m.type === 'user_message') addUserMessage(m.content);
    else if (m.type === 'activity') addActivity(m.content);
    else if (m.type === 'error') addError(m.content);
    else addDmMessage(m.content);  // 'text'
  }
  maybeAutoScroll();
}

// ─────────────────────────── Sending ──────────────────────────────────────
function sendGame() {
  const content = el.input.value.trim();
  if (!content || state.connStatus !== 'connected') return;
  state.localEcho.add(`user:${content}`);
  addUserMessage(content);
  setGenerating(true);
  state.ws.send(content);
  el.input.value = '';
  autosize();
  updateInputEnabled();
}

// ─────────────────────────── Campaign list ────────────────────────────────
async function pollCampaigns() {
  let list;
  try {
    const r = await fetch('/api/campaigns');
    list = await r.json();
  } catch { return; }
  if (!Array.isArray(list)) list = Array.isArray(list?.campaigns) ? list.campaigns : [];
  renderCampaignList(list);
}

function renderCampaignList(list) {
  el.campaignList.innerHTML = '';
  if (list.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'campaign-list-empty';
    empty.textContent = 'Нет кампаний. Создайте новую →';
    el.campaignList.appendChild(empty);
    return;
  }
  for (const c of list) {
    const item = document.createElement('div');
    item.className = 'campaign-item' + (state.mode === 'game' && c.name === state.campaign ? ' active' : '');
    const meta = [c.genre, typeof c.tone === 'string' ? c.tone : null].filter(Boolean).join(' · ');
    item.innerHTML =
      `<div class="campaign-item-name">${escapeHtml(c.name)}${c.active ? '<span class="playing-badge">▶</span>' : ''}</div>` +
      (meta ? `<div class="campaign-item-meta">${escapeHtml(meta)}</div>` : '');
    item.addEventListener('click', () => selectCampaign(c.name));
    el.campaignList.appendChild(item);
  }
}

function markActiveInList() {
  el.campaignList.querySelectorAll('.campaign-item').forEach(node => {
    const name = node.querySelector('.campaign-item-name')?.textContent?.replace('▶', '').trim();
    node.classList.toggle('active', state.mode === 'game' && name === state.campaign);
  });
}

// ─────────────────────────── View switching ───────────────────────────────
function showChat() { el.welcome.hidden = true; el.chatPane.hidden = false; }
function showWelcome() { el.welcome.hidden = false; el.chatPane.hidden = true; }

// ── Mobile navigation (Telegram-style: list ⇄ full-screen chat) ────────────
const MOBILE_MAX = 768;
const isMobile = () => window.innerWidth <= MOBILE_MAX;

/** Slide to the chat screen and set the top-bar title + back button. */
function showMobileChat(title) {
  el.app.classList.add('show-chat');
  el.mobileTitle.textContent = title;
  el.mobileBack.hidden = false;
  el.mobileNew.hidden = true;   // no "+" while in a chat
}

/** Slide back to the campaign list; restore the list title + "+" button. */
function showMobileSidebar() {
  el.app.classList.remove('show-chat');
  el.mobileTitle.textContent = '🎲 DM Game Master';
  el.mobileBack.hidden = true;
  el.mobileNew.hidden = false;
}

function mobileBack() {
  closeWs();            // leaving the chat drops its socket
  state.mode = null;
  markActiveInList();
  showMobileSidebar();
}

function selectCampaign(name) {
  if (state.mode === 'game' && state.campaign === name) return;
  closeWs();
  clearChoices();
  clearChat();
  hideCtxUsage();
  state.mode = 'game';
  state.campaign = name;
  state.afterId = 0;
  state.attempt = 0;
  state.generating = false;
  state.localEcho = new Set();
  el.titleText.textContent = name;
  el.input.placeholder = 'Введите сообщение…';
  el.wizardResetBtn.hidden = true;   // game mode: no wizard reset
  el.modelSelect.hidden = false;     // model selectable in game
  showChat();
  markActiveInList();
  if (isMobile()) showMobileChat(name);
  connect(gameUrl());
  el.input.focus();
}

/** Entry from "+" (and the 🗑️ reset). Ephemeral: opens a fresh one-shot wizard WS. */
function startWizard() {
  closeWs();
  clearChoices();
  clearChat();
  hideCtxUsage();
  state.mode = 'wizard';
  state.campaign = null;
  state.wizardFirstMsgSent = false;
  state.activeChoices = null;
  state.attempt = 0;
  state.generating = false;
  state.localEcho = new Set();
  el.titleText.textContent = 'Создание кампании';
  el.input.placeholder = 'Опишите мир или выберите вариант…';
  el.wizardResetBtn.hidden = false;
  el.modelSelect.hidden = true;  // model is fixed in wizard (config)
  showChat();
  markActiveInList();
  if (isMobile()) showMobileChat('Создание кампании');
  connect(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/wizard`);
  showInitialWizardGreeting();
  el.input.focus();
}

/** 🗑️ reset — just start a brand-new ephemeral wizard (old socket is dropped). */
function resetWizard() {
  startWizard();
}

// ─────────────────────────── Wizard ───────────────────────────────────────
// Preset settings shown client-side on wizard open (ported from React Wizard.tsx)
const WIZARD_PRESETS = {
  step: 'concept',
  title: 'Мир кампании',
  submit_label: 'Выбрать',
  controls: [
    {
      type: 'radio', id: 'preset', label: 'Готовые сеттинги',
      options: [
        { id: 'standard-dnd', title: 'Стандартный D&D', description: 'Классическое фэнтези — драконы, подземелья, магия', color: 'green', comment: 'Проверенная классика для любого игрока' },
        { id: 'zombie-apocalypse', title: 'Зомби-апокалипсис', description: 'Мертвецы, выживание, дефицит ресурсов', color: 'green', comment: 'Напряжение и моральные дилеммы' },
        { id: 'survival-zone', title: 'Зона выживания (STALKER)', description: 'Аномалии, радиация, артефакты, фракции', color: 'green', comment: 'Атмосфера постапока и исследование' },
        { id: 'space-travel', title: 'Космос', description: 'Корабль, экипаж, галактика, ресурсы', color: 'green', comment: 'Эпик среди звёзд' },
        { id: 'horror-investigation', title: 'Хоррор-расследование', description: 'Безумие, культы, запретное знание', color: 'yellow', comment: 'Для любителей Лавкрафта' },
        { id: 'political-intrigue', title: 'Политические интриги', description: 'Влияние, альянсы, предательства', color: 'yellow', comment: 'Война умов, а не мечей' },
        { id: 'gladiator-arena', title: 'Гладиаторская арена', description: 'Раб → бог арены, пермасмерть', color: 'yellow', comment: 'Чистый бой и прогрессия' },
        { id: 'roguelike-missions', title: 'Рогалик: База + Миссии', description: 'XCOM/Darkest Dungeon — хаб + вылазки', color: 'yellow', comment: 'Прогрессия и риск' },
        { id: 'civilization', title: 'Цивилизация', description: 'От племени до империи', color: 'yellow', comment: 'Управляешь народом, а не персонажем' },
        { id: 'monster-hunters', title: 'Охотники на монстров', description: 'Ведьмак meets Warhammer — контракты, бой', color: 'yellow', comment: 'Структурированные сессии' },
      ],
    },
    {
      type: 'text_input', id: 'custom_idea', label: 'Или опиши свой мир',
      placeholder: 'Киберпанк-детектив, пиратское фэнтези, что угодно…', required: false,
    },
  ],
};

function showInitialWizardGreeting() {
  addDmMessage('Привет! Давай создадим кампанию.\n\nВыбери готовый сеттинг ниже или опиши свой мир в чате.');
  renderChoices(WIZARD_PRESETS);
}

function sendWizard(text, meta) {
  const trimmed = (text || '').trim();
  if (!trimmed || state.connStatus !== 'connected' || state.generating) return;
  addUserMessage(trimmed);
  setGenerating(true);

  let msg = trimmed;
  // First message includes sidebar context so the DM knows step 1 = choosing the world
  if (!state.wizardFirstMsgSent) {
    state.wizardFirstMsgSent = true;
    const presetNames = (state.activeChoices?.controls || [])
      .flatMap(c => (c.options || []).map(o => o.title)).join(', ');
    if (presetNames) {
      msg = `[System: The sidebar currently shows campaign setting presets: ${presetNames}. This is step 1 — choosing the campaign world.]\n\n${msg}`;
    }
  }
  if (meta) msg = `${meta}\n${msg}`;

  state.ws.send(msg);
  el.input.value = '';
  autosize();
  updateInputEnabled();
}

function onWizardComplete(campaignName) {
  clearChoices();
  selectCampaign(campaignName);  // switch to the freshly created campaign's game socket
  pollCampaigns();
}

// ─────────────────────────── Choices UI (wizard) ──────────────────────────
const CHOICE_COLORS = {
  green: { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.4)', dot: '#10b981' },
  yellow: { bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.4)', dot: '#fbbf24' },
  red: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.4)', dot: '#ef4444' },
};

function clearChoices() {
  state.activeChoices = null;
  state.choiceSel = {};
  state.choiceText = {};
  el.rightPanel.hidden = true;
  el.choices.innerHTML = '';
}

function renderChoices(data) {
  if (!data || !Array.isArray(data.controls)) return;
  state.activeChoices = data;
  state.choiceSel = {};
  state.choiceText = {};
  el.rightPanel.hidden = false;
  el.choices.innerHTML = '';

  const head = document.createElement('div');
  head.className = 'choices-head';
  head.innerHTML = `<span class="choices-title">${escapeHtml(data.title || 'Выбор')}</span>` +
    (data.step ? `<span class="choices-step">${escapeHtml(data.step)}</span>` : '');
  el.choices.appendChild(head);

  for (const ctrl of data.controls) {
    const group = document.createElement('div');
    group.className = 'control-group';
    const label = document.createElement('div');
    label.className = 'control-label';
    label.innerHTML = escapeHtml(ctrl.label || ctrl.id) + (ctrl.required ? '<span class="req">*</span>' : '');
    group.appendChild(label);

    if (ctrl.type === 'text_input') {
      const inp = document.createElement('input');
      inp.className = 'ctrl-text';
      inp.type = 'text';
      inp.placeholder = ctrl.placeholder || '';
      inp.addEventListener('input', () => { state.choiceText[ctrl.id] = inp.value; });
      group.appendChild(inp);
    } else if ((ctrl.type === 'radio' || ctrl.type === 'checkbox') && Array.isArray(ctrl.options)) {
      const list = document.createElement('div');
      list.className = 'options-list';
      for (const opt of ctrl.options) {
        const colors = CHOICE_COLORS[opt.color] || CHOICE_COLORS.green;
        const card = document.createElement('div');
        card.className = 'option-card';
        const mark = ctrl.type === 'checkbox' ? '☐' : '○';
        card.innerHTML =
          `<div class="option-top">` +
            `<span class="color-dot" style="background:${colors.dot}"></span>` +
            `<span class="option-title">${escapeHtml(opt.title)}</span>` +
            `<span class="option-mark">${mark}</span>` +
          `</div>` +
          (opt.description ? `<div class="option-desc">${escapeHtml(opt.description)}</div>` : '') +
          (opt.comment ? `<div class="option-comment" style="color:${colors.dot}">${escapeHtml(opt.comment)}</div>` : '');
        card.addEventListener('click', () => toggleChoice(ctrl, opt.id, card, colors));
        list.appendChild(card);
      }
      group.appendChild(list);
    }
    el.choices.appendChild(group);
  }

  const footer = document.createElement('div');
  footer.className = 'choices-footer';
  const skip = document.createElement('button');
  skip.className = 'btn';
  skip.textContent = 'Пропустить';
  skip.addEventListener('click', () => {
    sendWizard('Пропускаю этот шаг', `[Sidebar skip for step "${data.step}"]`);
    clearChoices();
  });
  const submit = document.createElement('button');
  submit.className = 'btn btn-primary submit-btn';
  submit.textContent = data.submit_label || 'Выбрать';
  submit.addEventListener('click', submitChoices);
  footer.appendChild(skip);
  footer.appendChild(submit);
  el.choices.appendChild(footer);
}

function toggleChoice(ctrl, optId, card, colors) {
  const group = card.parentElement;
  if (ctrl.type === 'radio') {
    state.choiceSel[ctrl.id] = optId;
    group.querySelectorAll('.option-card').forEach(c => {
      c.classList.remove('selected');
      c.style.background = ''; c.style.borderColor = '';
      const m = c.querySelector('.option-mark'); if (m) m.textContent = '○';
    });
    card.classList.add('selected');
    card.style.background = colors.bg; card.style.borderColor = colors.border;
    const m = card.querySelector('.option-mark'); if (m) m.textContent = '◉';
  } else {
    const cur = Array.isArray(state.choiceSel[ctrl.id]) ? state.choiceSel[ctrl.id] : [];
    const on = cur.includes(optId);
    state.choiceSel[ctrl.id] = on ? cur.filter(x => x !== optId) : [...cur, optId];
    card.classList.toggle('selected', !on);
    card.style.background = on ? '' : colors.bg;
    card.style.borderColor = on ? '' : colors.border;
    const m = card.querySelector('.option-mark'); if (m) m.textContent = on ? '☐' : '☑';
  }
}

function submitChoices() {
  const data = state.activeChoices;
  if (!data || state.connStatus !== 'connected') return;
  const parts = [];
  for (const ctrl of data.controls) {
    const label = ctrl.label || ctrl.id;
    if (ctrl.type === 'text_input') {
      const v = (state.choiceText[ctrl.id] || '').trim();
      if (v) parts.push(`${label}: ${v}`);
    } else if (ctrl.type === 'radio') {
      const v = state.choiceSel[ctrl.id];
      if (typeof v === 'string') {
        const opt = (ctrl.options || []).find(o => o.id === v);
        parts.push(`${label}: ${opt ? opt.title : v}`);
      }
    } else if (ctrl.type === 'checkbox') {
      const vals = state.choiceSel[ctrl.id];
      if (Array.isArray(vals) && vals.length) {
        const names = vals.map(v => ((ctrl.options || []).find(o => o.id === v) || {}).title || v);
        parts.push(`${label}: ${names.join(', ')}`);
      }
    }
  }
  if (parts.length === 0) parts.push('Пропускаю этот шаг');
  sendWizard(parts.join('\n'), `[Sidebar selection for step "${data.step}"]`);
  clearChoices();
}

// ─────────────────────────── Input handlers ───────────────────────────────
function autosize() {
  el.input.style.height = 'auto';
  el.input.style.height = Math.min(el.input.scrollHeight, 160) + 'px';
}

function onSend() {
  if (state.mode === 'wizard') sendWizard(el.input.value);
  else if (state.mode === 'game') sendGame();
}

el.input.addEventListener('input', () => { autosize(); updateInputEnabled(); });
el.input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
});
el.sendBtn.addEventListener('click', onSend);
el.newBtn.addEventListener('click', startWizard);
el.welcomeNewBtn.addEventListener('click', startWizard);
el.wizardResetBtn.addEventListener('click', resetWizard);

// Mobile top-bar buttons
el.mobileNew.addEventListener('click', startWizard);
el.mobileBack.addEventListener('click', mobileBack);

// Crossing the mobile/desktop boundary (rotate / resize) — re-sync the top bar.
// Desktop uses flex layout + chat-header; mobile uses the sliding panels + top bar.
window.addEventListener('resize', () => {
  if (!isMobile()) {
    el.app.classList.remove('show-chat');  // desktop shows both panels, no slide
    return;
  }
  // On mobile, mirror the current mode into the top bar.
  if (state.mode === 'game' || state.mode === 'wizard') {
    showMobileChat(state.mode === 'wizard' ? 'Создание кампании' : state.campaign);
  } else {
    showMobileSidebar();
  }
});

// Switching model reconnects the current campaign with the new model (GameSession
// binds model at creation, so a fresh socket is the only way to swap it).
el.modelSelect.addEventListener('change', () => {
  if (state.mode === 'game' && state.campaign) {
    const name = state.campaign;
    state.campaign = null;   // force selectCampaign to act (it early-returns on same name)
    selectCampaign(name);
  }
});

// ─────────────────────────── Model select ─────────────────────────────────
async function loadModels() {
  let data;
  try { data = await (await fetch('/api/models')).json(); } catch { return; }
  const models = Array.isArray(data.models) ? data.models : [];
  el.modelSelect.innerHTML = '';
  for (const m of models) {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m.replace(/^claude-/, '');  // "claude-opus-4-8" → "opus-4-8"
    if (m === data.default) opt.selected = true;
    el.modelSelect.appendChild(opt);
  }
}

// ─────────────────────────── Boot ─────────────────────────────────────────
showWelcome();
loadModels();
pollCampaigns();
setInterval(pollCampaigns, CAMPAIGN_POLL_MS);
