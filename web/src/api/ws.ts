import type { ClientCommand, QueueItem, QueuePayload, RepeatMode } from './types';
import { beginWork } from '../store/busy';
import { applyPlayback, applyQueue, getSnapshot, markStopped, pushToast, setConnected, type PlaybackFields } from '../store/playback';

let socket: WebSocket | null = null;
let generation = 0;
let manualClose = false;
let reconnectTimer: number | null = null;
let neighborTimer: number | null = null;
let queuedShadeCommand: 'prev' | 'play_pause' | 'next' | null = null;
let shadeBound = false;
let lastRxAt = 0;
let lastReconnectAttempt = 0;

type Waiter = {
  kind: 'play' | 'menu' | 'queue';
  expectedKey: string;
  expectedTitle: string;
  prevTrackId: string;
  end: () => void;
  timer: number;
};

const waiters: Waiter[] = [];

function dropWaiter(waiter: Waiter): void {
  const index = waiters.indexOf(waiter);
  if (index < 0) return;
  window.clearTimeout(waiter.timer);
  waiters.splice(index, 1);
  waiter.end();
}

function dropKind(kind: Waiter['kind']): void {
  const waiter = waiters.find((item) => item.kind === kind);
  if (waiter) dropWaiter(waiter);
}

function dropAll(): void {
  while (waiters.length) dropWaiter(waiters[0]);
}

function dropPlay(playback: PlaybackFields): void {
  const incomingKey = playback.track_id.trim().toLowerCase();
  const incomingTitle = playback.title.trim().toLowerCase();
  const matched = waiters.filter((item) => {
    if (item.kind !== 'play') return false;
    if (item.expectedKey && incomingKey === item.expectedKey) return true;
    if (item.expectedTitle && incomingTitle === item.expectedTitle) return true;
    if (playback.track_id && playback.track_id !== item.prevTrackId) return true;
    return false;
  });
  matched.forEach(dropWaiter);
}

function armWaiter(command: ClientCommand): void {
  const end = beginWork();
  let kind: Waiter['kind'] = 'queue';
  let expectedKey = '';
  let expectedTitle = '';
  const prevTrackId = getSnapshot().trackId;
  if (command.command === 'play_now') {
    kind = 'play';
    expectedTitle = command.title.trim().toLowerCase();
    expectedKey = `${command.artist.trim()}|${command.title.trim()}`.toLowerCase();
  } else if (command.command === 'play_queue_track') {
    kind = 'queue';
  } else if (command.command === 'play_next' || command.command === 'add_to_queue') {
    kind = 'menu';
  }
  const waiter: Waiter = { kind, expectedKey, expectedTitle, prevTrackId, end, timer: 0 };
  waiter.timer = window.setTimeout(() => dropWaiter(waiter), 90000);
  waiters.push(waiter);
}

function shouldWait(command: ClientCommand, forced: boolean): boolean {
  if (forced) return true;
  return command.command === 'play_now'
    || command.command === 'play_next'
    || command.command === 'add_to_queue'
    || command.command === 'play_queue_track';
}

export function send(command: ClientCommand, options?: { wait?: boolean }): boolean {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    if (shouldWait(command, options?.wait === true)) pushToast('Нет связи с пультом', 'error');
    return false;
  }
  if (shouldWait(command, options?.wait === true)) armWaiter(command);
  socket.send(JSON.stringify(command));
  return true;
}

function scheduleNeighbors(): void {
  if (neighborTimer != null) window.clearTimeout(neighborTimer);
  neighborTimer = window.setTimeout(() => {
    neighborTimer = null;
    send({ command: 'refresh_queue' });
  }, 280);
}

function scheduleReconnect(): void {
  if (reconnectTimer != null) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    if (!manualClose) openSocket();
  }, 2000);
}

function asRepeat(value: unknown): RepeatMode {
  if (value === 'queue' || value === 'one' || value === 'off') return value;
  return 'off';
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null;
}

function numOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function parsePlayback(raw: Record<string, unknown>): PlaybackFields {
  const trackId = raw.track_id == null ? '' : String(raw.track_id);
  return {
    track_id: trackId,
    title: text(raw.title),
    artist: text(raw.artist),
    is_playing: raw.is_playing !== false,
    cover_url: textOrNull(raw.cover_url),
    cover_url_hq: textOrNull(raw.cover_url_hq),
    volume: typeof raw.volume === 'number' && Number.isFinite(raw.volume) ? raw.volume : null,
    position_sec: typeof raw.position_sec === 'number' && Number.isFinite(raw.position_sec) ? raw.position_sec : null,
    duration_sec: typeof raw.duration_sec === 'number' && Number.isFinite(raw.duration_sec) ? raw.duration_sec : null,
    repeat_mode: asRepeat(raw.repeat_mode),
    shuffle: raw.shuffle === true,
    liked: typeof raw.liked === 'boolean' ? raw.liked : null,
    queue_name: text(raw.queue_name),
  };
}

function parseItem(raw: unknown, current = false): QueueItem | null {
  if (!raw || typeof raw !== 'object') return null;
  const item = raw as Record<string, unknown>;
  return {
    title: text(item.title),
    artist: text(item.artist),
    cover: textOrNull(item.cover),
    track_id: numOrNull(item.track_id),
    album_id: numOrNull(item.album_id),
    is_playing: item.is_playing === true,
    is_current: current || item.is_current === true,
  };
}

function parseQueue(raw: Record<string, unknown>): QueuePayload {
  const before = Array.isArray(raw.before)
    ? raw.before.map((item) => parseItem(item)).filter((item): item is QueueItem => item != null)
    : [];
  const after = Array.isArray(raw.after)
    ? raw.after.map((item) => parseItem(item)).filter((item): item is QueueItem => item != null)
    : [];
  const meta = raw.now_meta && typeof raw.now_meta === 'object' ? (raw.now_meta as Record<string, unknown>) : {};
  return {
    before,
    current: raw.current == null ? null : parseItem(raw.current, true),
    after,
    before_title: text(raw.before_title) || 'Предыдущая очередь',
    after_title: text(raw.after_title) || 'Далее в очереди',
    now_meta: {
      subtitle: text(meta.subtitle),
      source: text(meta.source),
    },
  };
}

function openSocket(): void {
  const gen = ++generation;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  socket = ws;
  ws.onopen = () => {
    if (gen !== generation) return;
    lastRxAt = performance.now();
    setConnected(true);
    if (queuedShadeCommand) {
      const cmd = queuedShadeCommand;
      queuedShadeCommand = null;
      send({ command: cmd });
    }
    send({ command: 'refresh_queue' });
  };
  ws.onclose = () => {
    if (gen !== generation) return;
    if (waiters.length) pushToast('Нет связи с пультом', 'error');
    dropAll();
    setConnected(false);
    if (!manualClose) scheduleReconnect();
  };
  ws.onmessage = (event) => {
    if (gen !== generation) return;
    lastRxAt = performance.now();
    let parsed: unknown;
    try {
      parsed = JSON.parse(String(event.data));
    } catch {
      return;
    }
    if (!parsed || typeof parsed !== 'object') return;
    const raw = parsed as Record<string, unknown>;
    if (raw.type === 'now_playing' || raw.type === 'player_tick') {
      const playback = parsePlayback(raw);
      const changed = applyPlayback(playback, raw.type === 'now_playing');
      if (playback.track_id) dropPlay(playback);
      if (changed) scheduleNeighbors();
    } else if (raw.type === 'stopped') {
      markStopped();
    } else if (raw.type === 'error' || raw.type === 'notice') {
      if (raw.type === 'error') {
        const waiter = [...waiters].reverse().find((item) => item.kind === 'play' || item.kind === 'menu') || waiters[0];
        if (waiter) dropWaiter(waiter);
      } else {
        dropKind('menu');
      }
      if (typeof raw.message === 'string') {
        pushToast(raw.message, raw.type === 'error' ? 'error' : 'notice');
      }
    } else if (raw.type === 'queue') {
      dropKind('queue');
      applyQueue(parseQueue(raw));
    }
  };
}

function dispatchShadeCommand(raw: unknown): void {
  if (raw !== 'prev' && raw !== 'play_pause' && raw !== 'next') return;
  if (!send({ command: raw })) {
    queuedShadeCommand = raw;
  }
}

function bindShadeInput(): void {
  if (shadeBound || typeof window === 'undefined') return;
  shadeBound = true;
  try {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get('shade');
    if (fromUrl) {
      dispatchShadeCommand(fromUrl);
      params.delete('shade');
      const query = params.toString();
      window.history.replaceState(null, '', window.location.pathname + (query ? `?${query}` : ''));
    }
  } catch {
    // ignore
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
      const data = event.data as Record<string, unknown> | null;
      if (data && data.type === 'shade_command') {
        dispatchShadeCommand(data.command);
      }
    });
  }
}

export function ensureWsAlive(): void {
  if (manualClose) return;
  const now = performance.now();
  if (now - lastReconnectAttempt < 2000) return;
  const dead = !socket || socket.readyState === WebSocket.CLOSED || socket.readyState === WebSocket.CLOSING;
  const stale = socket && socket.readyState === WebSocket.OPEN && lastRxAt > 0 && now - lastRxAt > 6000;
  if (dead || stale) {
    lastReconnectAttempt = now;
    if (reconnectTimer != null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    try {
      socket?.close();
    } catch {
      // ignore
    }
    openSocket();
  }
}

export function connectWs(): void {
  manualClose = false;
  bindShadeInput();
  if (reconnectTimer != null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  openSocket();
}

export function disconnectWs(): void {
  manualClose = true;
  generation += 1;
  if (reconnectTimer != null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (neighborTimer != null) {
    window.clearTimeout(neighborTimer);
    neighborTimer = null;
  }
  socket?.close();
  socket = null;
}
