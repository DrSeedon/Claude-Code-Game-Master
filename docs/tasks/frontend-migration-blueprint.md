# Frontend Migration Blueprint — Orchestra UX → DnD React

**Task:** Recreate Orchestra's session-management + streaming-chat UX in DnD's React frontend.
**Status:** Phase 1 research. No code written. Every claim below is grounded in a file/line read this session.
**Date:** 2026-07-12

---

## 0. TL;DR — the truth, up front

DnD's **backend already is a partial port of Orchestra's architecture** (in-memory pub/sub broker, append-only event log with monotonic ids, turns that run independently of the WebSocket, idle-hibernate). The port stalled at the boundary. The real gaps are:

1. **Streaming is broken on the game screen.** Backend publishes `{type:"stream", content:<token>}` for every delta (`game_session.py:76`), but the React client has **no `stream` handler** — `isWsServerEvent()` (`types.ts:72-76`) drops it, so tokens never render. Text only appears as whole blocks via the `text` event. There is no typewriter on `/game`. (Ironically, `Wizard.tsx` *does* stream correctly — but over a different, non-broker socket.)
2. **Reconnect corrupts the game.** On reconnect the client sends `{type:"replay", after_id:N}` (`useWebSocket.ts:37`), but the backend treats **every** inbound WS text as a player message (`server.py:517,527` → `session.send(...)`). The replay JSON is fed to the LLM as if the player typed it. Meanwhile the backend's actual "replay" is a blind full-history dump on connect (`server.py:510-512`) that **ignores `after_id`**.
3. **No multi-session model.** DnD has ONE global active campaign (`config.campaign_name`), switched by `POST /api/campaigns/{name}/activate` (`Game.tsx:16`). The `/ws/game` socket reads that global (`server.py:501`). You cannot stream two campaigns at once, and activating campaign B silently changes what campaign A's open tab is talking to. Orchestra addresses every session **by name in the URL** (`/api/sessions/{name}/stream`) — N independent streams, zero global state.

Orchestra solves all three. This blueprint maps its mechanisms onto DnD's React + WS stack, keeping DnD's transport (WebSocket) rather than forcing SSE — the event *semantics* are what matter, not the wire.

**Confidence:** CONFIRMED for all three (read both codebases end-to-end; the mismatches are direct code reads, not inference).

---

## 1. Orchestra Frontend Architecture (how it actually works)

Vanilla JS (`app.js`, 5547 lines) + Jinja template (`dashboard.html`) + `style.css`. SSE for live data, `fetch` for everything else. No framework, no build step.

### 1.1 Data flow (one agent, happy path)

```
User picks agent  → selectAgent(name)                     app.js:1140
    ├─ eventSource.close(); localMessages.clear()          app.js:1142
    ├─ #chat.innerHTML = ''; chatLogs[name] reset          app.js:1151-1155
    ├─ await refreshSessions()  (agent list + status)
    └─ connectSSE()                                        app.js:159
         GET /api/sessions/{name}/stream?scope=…&after_id=0&limit=100
              backend: sessions.py:272 stream_session_logs
                ├─ after_id==0 → dump last `limit` history rows (one-shot)
                └─ loop: drain broker partials → poll DB logs → sleep
         eventSource.onmessage → JSON.parse → addChatEntry(type,…)  app.js:167,186
```

### 1.2 The event protocol (SSE → client)

Every SSE `data:` line is one JSON object: `{ id?, type, content, ts, subagent_id? }`. `id` is present on every DB-persisted row and **absent on ephemeral `stream` partials** (that's how the client knows not to count them for replay).

Event types the client dispatches on (`app.js` `addChatEntry`, `type===` checks):

| `type` | Carries | Client action | Has `id`? |
|---|---|---|---|
| `stream` | partial text delta | append to `streamPending`, RAF typewriter (`app.js:2319`) | no |
| `text` | final complete text block | flush stream buffer, replace with authoritative HTML, finalize bubble (`app.js:2338`) | yes |
| `user_message` | player/user input | de-dup against `localMessages`, render user bubble (`app.js:171,2463`) | yes |
| `tool` | `"ToolName: {json}"` | parse header, render tool block, mark `data-last-tool` (`app.js:2491`) | yes |
| `tool_result` | tool output | find preceding `[data-last-tool]`, attach result (`app.js:3087`) | yes |
| `status` | status string | centered italic badge, parse rate-limit (`app.js:2351`) | yes |
| `thinking` | reasoning | render if not hidden (`app.js:2196`) | yes |
| `subagent_start/end/progress/stream/event` | nested agent | collapsible accordion (`app.js:2385-2447`) | mixed |

**Key invariant:** a `stream` partial always precedes its matching `text` final. The backend enforces this by draining broker partials *before* polling DB finals each tick (`sessions.py:294-308`). The client relies on it: `stream` builds the live bubble, `text` replaces it with the canonical version.

### 1.3 Streaming typewriter — the heart (verbatim mechanics)

State (module-level, `app.js:1872-1878`):
```js
let streamBubble   = null;   // the in-progress <div>
let streamContent  = '';     // markdown accumulated so far
let streamPending  = '';     // raw delta buffer not yet drawn
let _streamRafId   = null;   // requestAnimationFrame handle
let _streamLastParse = 0;    // last marked.parse() timestamp
const _STREAM_BASE_CPS = 12;         // min chars drawn per frame
const _STREAM_PARSE_INTERVAL = 50;   // ms between markdown re-parses
```

On a `stream` event (`app.js:2319-2333`):
```js
if (type === 'stream') {
    removeWaitingIndicator();
    if (!streamBubble) {                       // first delta → create bubble
        streamBubble = document.createElement('div');
        streamBubble.className = 'px-3 py-2 rounded-lg text-sm break-words chat-bot markdown-body streaming';
        _insert(streamBubble);
        _streamLastParse = 0;
    }
    streamPending += content;                  // accumulate raw
    if (!_streamRafId) _streamRafId = requestAnimationFrame(_streamRenderTick);
    return;
}
```

The render tick (`app.js:1880-1906`) — this is the animation loop:
```js
function _streamRenderTick() {
    _streamRafId = null;
    if (!streamBubble || !streamPending) return;
    // adaptive: if buffer is big, draw more per frame so we don't lag behind
    const chunkSize = Math.max(_STREAM_BASE_CPS, Math.floor(streamPending.length / 8));
    const chunk = streamPending.slice(0, chunkSize);
    streamPending = streamPending.slice(chunkSize);
    streamContent += chunk;
    const now = performance.now();
    if (now - _streamLastParse >= _STREAM_PARSE_INTERVAL || !streamPending) {
        _streamLastParse = now;
        streamBubble.innerHTML = DOMPurify.sanitize(marked.parse(streamContent));  // re-render markdown ≤20×/s
    }
    // blinking cursor appended to last element
    streamBubble.querySelector('.typing-cursor')?.remove();
    const lastEl = streamBubble.querySelector(':scope > :last-child') || streamBubble;
    const cur = document.createElement('span'); cur.className = 'typing-cursor'; cur.textContent = '▍';
    lastEl.appendChild(cur);
    // auto-scroll only if user is near bottom
    const chat = $('#chat');
    if (chat.scrollHeight - chat.scrollTop - chat.clientHeight < 80)
        chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
    if (streamPending) _streamRafId = requestAnimationFrame(_streamRenderTick);  // loop
}
```

Finalize on `text` (`app.js:2338-2348`):
```js
if (type === 'text' && streamBubble) {
    _streamFlush();                                  // drain remaining buffer
    streamBubble.classList.remove('streaming');
    streamBubble.innerHTML = DOMPurify.sanitize(marked.parse(content || streamContent));
    addCopyBtn(streamBubble, content); addTimestamp(streamBubble, ts);
    streamBubble = null; streamContent = ''; streamPending = '';
    return;
}
```

Why it's built this way (the design rationale a React dev must preserve):
- **Decouple network cadence from paint cadence.** Tokens arrive bursty; the RAF loop drains a smooth 12+ chars/frame. Never `innerHTML=` on every token.
- **Throttle markdown parsing** to ≤20×/sec (`_STREAM_PARSE_INTERVAL`), not per token — `marked.parse` on a growing string every token is O(n²) and janks.
- **Adaptive chunk** (`pending.length/8`) means if the model dumps a big block, the UI catches up instead of trickling for seconds after the stream ended.
- **`text` is authoritative.** The partial stream is a preview; the final `text` event is the real content (correct markdown, no truncation) and replaces the preview wholesale.

### 1.4 Reconnect + replay (`after_id`)

- Per-agent cursor: `chatLogs[name] = { lastId, firstId, initialCount }` (`app.js:1155`). `lastId` bumps on every event that has a finite `id` (`app.js:190-194`).
- SSE URL always carries `after_id=${lastId}` (`app.js:163-165`). On first connect `lastId=0` → server sends `&limit=100` history.
- On error: `eventSource.close()`, retry after 2s, reconnect with the *same* `lastId` (`app.js:210-215`). Server resumes from there — no dupes, no gaps.
- **In-flight stream is discarded on reconnect** (streamBubble was nulled on close). A fresh `stream`/`text` pair rebuilds it. Simpler than trying to resume a half-rendered partial, and correct because `text` is authoritative.
- Load-older-history is a separate path: `GET /api/sessions/{name}/logs?before_id=${firstId}&limit=500` (`app.js:240`), prepended.

### 1.5 Session list (right panel)

- Polled, not pushed: `refreshSessions()` every **3s** (`app.js:151-156`) → `GET /api/sessions?scope=…` + `/api/stats`.
- Rendered as a **parent/child tree** (`app.js:1369-1424`) — orchestrator → workers, via `parent_name`. Not relevant to DnD (flat campaign list), but the render-from-array-on-poll pattern is.
- Each item (`createAgentItem`, `app.js:1490`): icon + name + status badge + model + cache pill + cost. Status colors `running=#22c55e, idle=#eab308, waiting=#f59e0b` (`app.js:1516`).
- Click → `selectAgent(name)` (full teardown + reconnect, §1.1).

### 1.6 Send (optimistic)

`sendChat()` (`app.js:1630`): push to `localMessages` set → show pending bubble immediately → `POST /api/sessions/{name}/send {message,scope}` (15s timeout). The server echoes the message back as a `user_message` SSE event; the client de-dups it against `localMessages` so it isn't rendered twice (`app.js:171-184`).

### 1.7 Layout & theme (`dashboard.html`, `style.css`)

- 3-panel flex: left `#file-panel` 250px | center chat flex-1 | right agent panel 320px.
- Center: `#chat` (`flex-1 overflow-y-auto p-4 space-y-2`) + `#chat-input` textarea + `#send-btn`/`#stop-btn`.
- Theme = CSS custom properties in `:root` (`style.css:1-16`): `--bg:#0a0e17`, `--surface:#0f172a`, `--surface-2:#1e293b`, `--border:#334155`, `--ink:#e2e8f0`, `--accent:#818cf8`, `--accent-alt:#38bdf8`, `--ok:#22c55e`, `--warn:#eab308`, `--danger:#ef4444`, radii `--r-sm/md/lg = 6/8/12px`, fonts Inter (sans) + JetBrains Mono (mono).
- Streaming CSS worth copying verbatim: `.typing-cursor` blink (`style.css:104`), `.streaming` fade-in (`style.css:102`), `.chat-user`/`.chat-bot`/`.chat-tool` left-border accents (`style.css:38-41`), `.waiting-dots` (`style.css:98`).
- Vendor: Tailwind (CDN build), `marked`, `DOMPurify`, `highlight.js`, `Chart.js`. DnD already uses `react-markdown` (equivalent to marked+DOMPurify).

---

## 2. DnD Current State

### 2.1 Backend (`backend/`) — already Orchestra-shaped, keep it

| File | Role | Verdict |
|---|---|---|
| `live_broker.py` | in-mem pub/sub, drop-oldest at 256 backlog | ✅ = Orchestra's broker. Keep. |
| `event_log.py` | append-only JSONL, monotonic `id`, `read_events(after_id)` | ✅ = Orchestra's DB log. Keep. `after_id` param already exists but is unused by the WS handler. |
| `game_session.py` | turn runs in bg `asyncio.Task`, WS-independent, hibernate at 5min idle | ✅ = Orchestra's session model. Keep. Publishes `stream`/`text`/`activity`/`error`/`done`. |
| `providers/claude_sdk.py` | SDK streaming, `include_partial_messages=True`, `text_delta`→ deltas | ✅ Keep. Emits `text_delta` (partial), `text` (block), `activity` (tool), `error`. |
| `server.py` | FastAPI routes + `/ws/game` + `/ws/wizard` | ⚠️ WS handler has the two bugs (§0). Needs surgery, not rewrite. |

**Event vocabulary the backend actually emits** (game path, `game_session.py:75-94`):
`stream` (delta, no id, broker-only) · `text` (block, logged w/ id) · `activity` (tool call/result, logged) · `error` (logged) · `done` (broker-only) · plus `history` (full log dump on connect, `server.py:512`).

### 2.2 Frontend (`frontend/src/`)

| File | Lines | Role | Verdict |
|---|---|---|---|
| `App.tsx` | 38 | Router: `/` Lobby, `/game`, `/wizard`, `/dashboard` | Keep, extend for multi-tab. |
| `pages/Lobby.tsx` | 424 | Campaign grid + "New" → wizard. Polls `/api/campaigns` 5s. | Keep; = Orchestra session list. Good bones. |
| `pages/Game.tsx` | 176 | Activates campaign, renders `<Chat>` + `<CharacterPanel>`. | ⚠️ Rework: the `activate`-on-mount global-state model is the multi-session blocker. |
| `pages/Wizard.tsx` | 625 | WS `/ws/wizard`, **streams correctly** (`streamingRef` accumulate). | Keep as reference — it already does the React streaming pattern. |
| `pages/Dashboard.tsx` | 587 | campaign management | Out of scope; leave. |
| `components/Chat.tsx` | 520 | WS chat, message list, input, status. | 🔧 Core rewrite target: add `stream` handler + typewriter. |
| `components/CharacterPanel.tsx` | 364 | polls `/api/status` 5s | Keep. |
| `components/CampaignList.tsx` | 260 | older card list (Lobby has its own copy) | Dead-ish dup of Lobby's inline list — flag, don't delete blindly. |
| `hooks/useWebSocket.ts` | 103 | WS lifecycle, exp-backoff reconnect (5 tries, 2s→30s), sends `replay` | 🔧 Good backbone; the `replay` message is unhandled by backend. |
| `types.ts` | 103 | `WsServerEvent` union + type guard | 🔧 Missing `stream`; `history`/`done` shapes ok. |

**What's good:** exp-backoff reconnect with `ConnectionStatus` states + UI (`Chat.tsx:124-152`) is *better* than Orchestra's naive 2s retry. `bounded()` message cap (500) matches Orchestra's limit. `localEchoRef` de-dup = Orchestra's `localMessages`. `react-markdown` per assistant message = marked+DOMPurify. Wizard's streaming loop is a working template.

**What's bad / missing (ranked):**
1. **No `stream` handling** → no typewriter (§0.1). The whole point of the task.
2. **Reconnect sends a message to the LLM** (§0.2). Actively corrupts play.
3. **Single global campaign** → no real multi-session; opening two `/game` tabs on different campaigns races on `config.campaign_name`.
4. **`text` semantics collide.** Backend sends `text` = one full block; `Chat.tsx:73-85` treats consecutive `text` events as appendable stream chunks (`target.content + event.content`). With real streaming added, `text` must become *finalize*, not *append*.
5. Inline `<style>` string-blobs per component (works, but no shared token system like Orchestra's `:root`).
6. No auto-scroll gating — `Chat.tsx:92-94` always `scrollIntoView` on every render, so a user scrolled up gets yanked to bottom (Orchestra gates on `<80px from bottom`).

---

## 3. Migration Spec (component-by-component)

Guiding principle (from Orchestra's own design notes): **one route per task, minimum surface, fail loud.** Keep DnD's WebSocket transport. Align the *event semantics* to Orchestra's, then port the typewriter.

### 3.1 Event protocol alignment (Orchestra SSE → DnD WS)

Target unified event set on `/ws/game` (server→client). This is the contract both sides implement:

| DnD WS event | Orchestra equiv | Shape | Client action |
|---|---|---|---|
| `stream` | `stream` | `{type:'stream', content}` (no id) | typewriter append |
| `text` | `text` | `{type:'text', content, id}` | **finalize** streaming bubble |
| `activity` | `tool`+`tool_result` | `{type:'activity', content, id}` | inline tool line (already works) |
| `error` | `status`/error | `{type:'error', content, id}` | red banner |
| `done` | (status idle) | `{type:'done'}` | stop generating indicator |
| `history` | initial log dump | `{type:'history', messages:[…]}` | replace history, then resume |

Decision — **drop the client→server `replay` message entirely.** Orchestra does replay in the *URL/query* on (re)connect, not as an in-band message. DnD's WS has no query cursor today, so the clean port is: on (re)connect the server always sends `history` filtered by a cursor the **client passes in the connect URL** (`/ws/game?campaign=<id>&after_id=<n>`), exactly like Orchestra's `after_id`. This removes the "replay text becomes a player message" bug at the root — the socket's `receive_text()` is then *unambiguously* always a player turn.

### 3.2 Multi-session — the architectural change

Replace global-active-campaign with **campaign-addressed sockets**, mirroring Orchestra's name-in-URL:

- WS: `/ws/game?campaign=<name>&after_id=<n>` — campaign from query, not `config.campaign_name`.
- Backend: `game_websocket` reads `campaign` from `websocket.query_params`, calls `get_or_create_session(campaign,…)` (registry already keyed by campaign — `game_session.py:21,27`), subscribes to `broker.subscribe(campaign)`. **Delete** the `config.campaign_name` dependency in the WS path.
- `/api/status` must also take `?campaign=<name>` (today it reads the global). Same for send.
- Frontend: `Game.tsx` stops calling `/activate`; it just opens `/ws/game?campaign=<id>`. Multiple tabs = multiple independent sockets = multiple independent streams. This is exactly Orchestra's model.

This is the single highest-value change: it's what makes "play multiple campaigns like Orchestra sessions" true instead of cosmetic.

### 3.3 Components: keep / kill / create

**KEEP (as-is or minor):**
- `Lobby.tsx` — it's the session list. Add per-card status dot (idle/running from a `/api/campaigns` field or `/api/status`), "last played" and a subtle "▶ playing" indicator when a socket is open. Optional: real-time-ish via existing 5s poll (fine — Orchestra polls at 3s).
- `CharacterPanel.tsx` — add `campaign` prop → `/api/status?campaign=`.
- `useWebSocket.ts` — keep backbone; change: accept an `afterIdRef` and build the connect URL with `&after_id=`; **remove** the `socket.send({type:'replay'})` block (`useWebSocket.ts:36-38`).
- `Wizard.tsx` — unchanged (reference implementation).

**KILL:**
- The `/activate`-on-mount flow in `Game.tsx:14-22` (replaced by campaign-in-query).
- `CampaignList.tsx` if confirmed unused after Lobby owns the list (grep first — CLAUDE.md rule: verify real imports before deleting).
- The `text`-as-append branch in `Chat.tsx:76-84` (replaced by finalize).

**CREATE:**
- `hooks/useStreamingBuffer.ts` — the typewriter engine (RAF loop, adaptive chunk, throttled markdown). See §4.
- `styles/theme.css` — port Orchestra's `:root` tokens (§1.7) so components stop hardcoding `#3b82f6` etc.
- (optional, if true multi-tab-in-one-page is wanted) `pages/GameTabs.tsx` — a tab bar over N `<Chat campaign=…>` instances. If instead you keep one campaign per browser tab/route, skip this and rely on the URL.

### 3.4 State management

No Redux/Zustand needed — Orchestra uses plain module vars; React equivalent is component state + refs. Per `<Chat>`:
- `messageHistory: ChatMessage[]` (state) — finalized messages only.
- `streamRef` (ref) — the in-progress partial (NOT state; mutated by RAF, see §4 for why refs).
- `afterIdRef` (ref) — replay cursor, bumped on every `id`-bearing event.
- `localEchoRef` (ref) — de-dup set (already present).
- `isGenerating` (state) — drives the "DM печатает…" indicator.

The streaming buffer lives in a **ref + imperative DOM/`useState` flush**, because you cannot `setState` 60×/sec per token without murdering React. Two valid patterns in §4.

### 3.5 Styling approach

Port Orchestra's `:root` token block into a global stylesheet and reference `var(--…)`. Keep DnD's existing dark gradient page shells (`Game.tsx` styles are fine). Copy verbatim: `.typing-cursor`, `.streaming`, `.waiting-dots`, chat-bubble left-border accents. Do **not** try to import Tailwind CDN — DnD is a Vite build; use plain CSS with the tokens. This keeps the visual language identical without adopting Orchestra's toolchain.

---

## 4. Streaming Deep Dive — exact React implementation

The problem: tokens arrive up to hundreds/sec; React re-render per token = jank/death. Orchestra sidesteps React entirely (imperative DOM in a RAF loop). In React you have two faithful ports:

### Option A (recommended) — ref-buffered RAF + throttled `setState`

The partial text lives in a **ref** (mutated freely, no re-render). A RAF loop drains the pending buffer into `displayedRef` and calls `setState` only on the throttle interval — so React re-renders ≤20×/sec, not per token. `react-markdown` renders `displayed`. Cursor is a CSS pseudo-element on the streaming bubble.

```tsx
// hooks/useStreamingBuffer.ts  (new)
import { useRef, useState, useCallback, useEffect } from 'react';

const BASE_CPS = 12;          // min chars per frame  (Orchestra _STREAM_BASE_CPS)
const PARSE_INTERVAL = 50;    // ms between visible updates (Orchestra _STREAM_PARSE_INTERVAL)

export function useStreamingBuffer() {
  const pending = useRef('');        // raw deltas not yet shown  (streamPending)
  const shown   = useRef('');        // chars already drawn       (streamContent)
  const raf      = useRef<number | null>(null);
  const lastParse= useRef(0);
  const [display, setDisplay] = useState('');   // what react-markdown renders
  const [active, setActive]   = useState(false);

  const tick = useCallback(() => {
    raf.current = null;
    if (!pending.current) return;
    // adaptive chunk: catch up if buffer is large   (Orchestra Math.floor(len/8))
    const size = Math.max(BASE_CPS, Math.floor(pending.current.length / 8));
    shown.current += pending.current.slice(0, size);
    pending.current = pending.current.slice(size);
    const now = performance.now();
    if (now - lastParse.current >= PARSE_INTERVAL || !pending.current) {
      lastParse.current = now;
      setDisplay(shown.current);          // <-- the ONLY setState in the loop, ≤20/s
    }
    if (pending.current) raf.current = requestAnimationFrame(tick);
  }, []);

  const push = useCallback((delta: string) => {   // called on every `stream` event
    setActive(true);
    pending.current += delta;
    if (raf.current == null) raf.current = requestAnimationFrame(tick);
  }, [tick]);

  const finalize = useCallback((final?: string) => {   // called on `text`
    if (raf.current != null) { cancelAnimationFrame(raf.current); raf.current = null; }
    const text = final ?? (shown.current + pending.current);
    pending.current = ''; shown.current = ''; lastParse.current = 0;
    setDisplay(''); setActive(false);
    return text;    // caller pushes this into messageHistory as a finalized message
  }, []);

  const reset = useCallback(() => {   // on reconnect / campaign switch
    if (raf.current != null) cancelAnimationFrame(raf.current);
    raf.current = null; pending.current = ''; shown.current = '';
    setDisplay(''); setActive(false);
  }, []);

  useEffect(() => () => { if (raf.current != null) cancelAnimationFrame(raf.current); }, []);
  return { display, active, push, finalize, reset };
}
```

Wiring in `Chat.tsx`:
```tsx
const stream = useStreamingBuffer();

const handleEvent = useCallback((e: WsServerEvent) => {
  switch (e.type) {
    case 'stream':                       // NEW — the missing handler
      setIsGenerating(true);
      stream.push(e.content);
      break;
    case 'text': {                       // now FINALIZE, not append
      const finalText = stream.active ? stream.finalize(e.content) : e.content;
      setMessageHistory(prev => bounded([...prev,
        { role: 'assistant', content: finalText, timestamp: Date.now() }]));
      break;
    }
    case 'activity':
      stream.finalize();                 // close any open partial before a tool line
      setMessageHistory(prev => bounded([...prev,
        { role:'assistant', kind:'activity', content:e.content, timestamp:Date.now() }]));
      break;
    case 'done':   setIsGenerating(false); break;
    case 'error':  stream.reset(); setIsGenerating(false);
                   setMessageHistory(prev => bounded([...prev,
                     { role:'assistant', kind:'error', content:e.content, timestamp:Date.now() }])); break;
    case 'history':
      stream.reset();
      setMessageHistory(bounded(e.messages
        .filter(m => !localEchoRef.current.has(`${m.role}:${m.content}`))
        .map(m => ({ role:m.role, content:m.content, timestamp:m.timestamp ?? Date.now() }))));
      break;
  }
}, [stream]);
```

Render (the live bubble is separate from finalized history, exactly like Orchestra's `streamBubble`):
```tsx
{messageHistory.map(renderMessage)}
{stream.active && (
  <div className="message message-assistant">
    <div className="message-role">DM</div>
    <div className="message-content markdown-body streaming">
      <Markdown>{stream.display}</Markdown>
      <span className="typing-cursor">▍</span>
    </div>
  </div>
)}
```

Why refs, not state, for `pending`/`shown`: a `stream` event fires far faster than React can commit. `setState` per token queues hundreds of renders/sec and drops frames. The ref mutates for free; the RAF loop is the single throttled writer to `setDisplay`. This is the direct analogue of Orchestra mutating `streamPending`/`streamContent` outside any framework.

### Option B — imperative DOM (closest 1:1 to Orchestra)

Hold a `ref` to the streaming bubble `<div>` and do `bubbleRef.current.innerHTML = DOMPurify.sanitize(marked.parse(shown))` inside the RAF tick — literally Orchestra's code inside a React ref. Faster (no reconciliation) but bypasses React/`react-markdown` and needs `marked`+`DOMPurify` added as deps. Use only if Option A profiles too slow on very long streams (unlikely for DM-length replies). **Default to A.**

### Auto-scroll (port Orchestra's gating; fix `Chat.tsx:92-94`)

```tsx
const atBottomRef = useRef(true);
const onScroll = (el: HTMLDivElement) => {
  atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;  // Orchestra's 80px
};
useEffect(() => {                        // run when history OR live display grows
  if (atBottomRef.current) messagesEndRef.current?.scrollIntoView({ behavior:'smooth' });
}, [messageHistory, stream.display]);
```

### Reconnect (fix both bugs)

- Client: on (re)connect build URL `/ws/game?campaign=${id}&after_id=${afterIdRef.current}`; bump `afterIdRef` on every event with `id`; **remove** the `send({type:'replay'})` block.
- Server: read `after_id` from query, send `history` = `read_events(campaign_dir, after_id=after_id)` (the param already exists — `event_log.py:23`), then subscribe to broker for live. `receive_text()` is now always a real player turn.
- In-flight partial on reconnect: `stream.reset()` on socket open, let the next `stream`/`text` rebuild. (Orchestra discards too.)

---

## 5. File-by-file implementation plan

Vertical slices, each shippable & testable. Ordered by dependency.

### Backend (do first — the client can't stream correct events until the server sends them right)

**`backend/server.py`** — `game_websocket` surgery:
- Read `campaign = websocket.query_params.get('campaign')` and `after_id = int(query_params.get('after_id', 0))`. Reject (close) if no campaign. Stop using `config.campaign_name` here.
- `get_or_create_session(campaign, project_root, model_name)`; `campaign_dir` from the session.
- Replace blind full dump (`server.py:510-512`) with `history = read_events(session.campaign_dir, after_id=after_id)`.
- Loop unchanged (`receive_text` = player turn; broker queue = live events) — now unambiguous.
- `/api/status` and `POST send` (if added): accept `?campaign=`.
- AC: connecting with `after_id=N` returns only events with id>N; a reconnect mid-turn does NOT create a phantom player message; two different `campaign` sockets stream independently.

**`backend/game_session.py`** — no change needed (already publishes `stream`/`text`/`activity`/`error`/`done`; registry already per-campaign). Verify `activity` for tool calls is what the client renders as inline lines — it is.

### Frontend

**`frontend/src/types.ts`**
- Add `| { type: 'stream'; content: string }` to `WsServerEvent`.
- Add `'stream'` to `isWsServerEvent`'s allow-list (`types.ts:75`).
- AC: a `stream` frame passes the type guard and reaches `onEvent`.

**`frontend/src/hooks/useWebSocket.ts`**
- Accept `afterIdRef` (or return `lastEventId`); build connect URL with `&after_id=`.
- Delete the `socket.send(JSON.stringify({type:'replay',…}))` block (`useWebSocket.ts:36-38`).
- Keep exp-backoff + `ConnectionStatus`.
- AC: reconnect reuses the last id in the URL; no JSON control frame is ever sent to the server.

**`frontend/src/hooks/useStreamingBuffer.ts`** (new) — §4 Option A verbatim.
- AC: pushing 500 deltas in a tight loop causes ≤ (elapsed_ms/50) React renders; `finalize()` returns full text and clears state.

**`frontend/src/components/Chat.tsx`**
- Wire `useStreamingBuffer`; add `stream` case; change `text` to finalize; `activity`/`error`/`history` close/reset the buffer (§4).
- Render the live streaming bubble separately from `messageHistory`.
- Fix auto-scroll gating (80px).
- Accept a `campaign` prop; pass to `useWebSocket` URL.
- AC: typing a message shows token-by-token DM reply with blinking cursor; final render matches the `text` block; scrolling up during a stream is not interrupted.

**`frontend/src/pages/Game.tsx`**
- Remove `/activate` call; read `campaign` from query; render `<Chat campaign={id}/>` + `<CharacterPanel campaign={id}/>`.
- AC: navigating to `/game?campaign=X` opens a stream for X without mutating any global; opening `/game?campaign=Y` in a second tab streams Y concurrently.

**`frontend/src/components/CharacterPanel.tsx`**
- `campaign` prop → `/api/status?campaign=`.
- AC: panel shows the correct campaign's character even with two tabs open.

**`frontend/src/styles/theme.css`** (new) + `main.tsx` import
- Port Orchestra `:root` tokens (§1.7) + `.typing-cursor`, `.streaming`, `.waiting-dots`, chat-bubble accents.
- AC: cursor blinks; streaming bubble fades in; colors come from `var(--…)`.

**`frontend/src/pages/Lobby.tsx`**
- Add a status/"playing" affordance per card (optional, low priority). Keep the 5s poll.
- AC: active/playing campaigns are visually distinguished.

### Optional (only if single-page multi-tab is desired over per-browser-tab)

**`frontend/src/pages/GameTabs.tsx`** (new) — tab strip over N `<Chat campaign=…>`; each keeps its own socket. Skip if URL-per-tab is acceptable (simpler, and Orchestra-faithful since Orchestra also has one selected agent per browser tab).

---

## 6. Risks & edge cases

- **`text` double-render.** If the backend ever emits `text` *without* a preceding stream (e.g. tool-only turn), `finalize()` must handle `active===false` (it does — falls back to `e.content`). Covered.
- **`activity` mid-stream.** A tool call can interrupt an assistant text block. Must `finalize()` the open partial before appending the activity line, else the partial hangs. Handled in §4 `activity` case. (Orchestra does the same by closing the stream bubble when a non-stream event inserts.)
- **Reconnect during a turn.** New: `history(after_id)` returns finalized events only; the *currently streaming* partial (broker-only, no id) is lost and resumes live from the next delta — the eventual `text` finalizes it. No dupe because `text` has an id > after_id only if it hadn't been sent; if it was already persisted+seen, `after_id` filters it. Verify the ordering: persist `text` to log *before* publishing `done` (already the case — `game_session.py:79` logs, `:94` dones).
- **De-dup echo.** Keep `localEchoRef`; user message is echoed via `history`/log. Orchestra's exact pattern.
- **Backpressure.** Broker drops oldest partial at 256 backlog (`live_broker.py:32`). Fine — partials are ephemeral; the `text` final is authoritative and logged. Don't "fix" this.
- **Two tabs, same campaign.** Both subscribe to the same broker channel → both see the same stream (good, mirrors Orchestra). `session.send` rejects a second concurrent turn (`game_session.py:53`) → surface the existing `"turn already in progress"` error in UI.

---

## 7. Counter-evidence / what argues against this plan

- **"Just fix `stream` in Chat.tsx, skip multi-session."** Valid if the user only wants the typewriter. But the task explicitly says "play multiple campaigns like Orchestra sessions", and the global-active-campaign model makes two tabs silently fight. Fixing streaming without fixing the global blocks the stated goal. Recommend both, but they're independently shippable (streaming slice first).
- **SSE vs WS.** Orchestra uses SSE; DnD uses WS. One could argue "match Orchestra exactly → switch to SSE." Rejected: WS already carries the same event JSON, DnD's reconnect/broker are built for it, and SSE can't carry the client→server send (Orchestra uses a separate POST for that). Keeping WS is less code and semantically identical. The *events*, not the transport, are the UX.
- **Imperative DOM (Option B) is closer to Orchestra.** True, but Option A keeps React idioms and `react-markdown` (already a dep) and profiles fine for DM-length text. B is the escape hatch, documented, not the default.

---

## 8. Sources (all read this session)

Orchestra: `app/static/js/app.js` (streaming core L1872-1914, 2319-2348; SSE L159-216; selectAgent L1140-1163; session list L1369-1568; send L1630-1688), `app/static/css/style.css` (tokens L1-16, streaming L102-105), `app/templates/dashboard.html` (layout/ids), `app/static/js/tool-renderers.js` (tool icon/label/render), `app/routes/sessions.py` (stream endpoint L272-315, send L329-379).

DnD: `backend/server.py` (`/ws/game` L489-541 — bugs; `/ws/wizard` L373-471), `backend/game_session.py` (turn+publish L47-102), `backend/live_broker.py`, `backend/event_log.py`, `backend/providers/claude_sdk.py` (stream events L121-151), `frontend/src/hooks/useWebSocket.ts` (replay bug L36-38), `frontend/src/types.ts` (missing `stream` L62-76), `frontend/src/components/Chat.tsx` (text-append L73-85, scroll L92-94), `frontend/src/pages/{Game,Lobby,Wizard}.tsx`, `frontend/src/components/{CampaignList,CharacterPanel}.tsx`, `frontend/vite.config.ts` (proxy → :18083).
```
