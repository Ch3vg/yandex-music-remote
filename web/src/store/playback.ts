import { useRef, useSyncExternalStore } from 'react';
import type { ArtistRef, QueueItem, QueuePayload, RepeatMode } from '../api/types';
import { lookFromImage, resetMini, type MiniLook } from '../lib/palette';

export type ToastItem = {
  id: number;
  message: string;
  kind: 'error' | 'notice';
};

type State = {
  connected: boolean;
  statusTitle: string;
  hasTrack: boolean;
  trackId: string;
  title: string;
  artist: string;
  artists: ArtistRef[];
  artistHref: string | null;
  coverUrl: string | null;
  coverHq: string | null;
  isPlaying: boolean;
  volume: number;
  shuffle: boolean;
  repeatMode: RepeatMode;
  liked: boolean;
  queueName: string;
  pos: number;
  dur: number;
  at: number;
  playing: boolean;
  dragging: boolean;
  dragPos: number;
  swipeGen: number;
  queue: QueuePayload | null;
  queueEpoch: number;
  mini: MiniLook;
  playerC1: string | null;
  playerC2: string | null;
  toasts: ToastItem[];
};

export type PlaybackView = {
  connected: boolean;
  statusTitle: string;
  hasTrack: boolean;
  trackId: string;
  title: string;
  artist: string;
  artists: ArtistRef[];
  artistHref: string | null;
  coverUrl: string | null;
  coverHq: string | null;
  isPlaying: boolean;
  volume: number;
  shuffle: boolean;
  repeatMode: RepeatMode;
  liked: boolean;
  queueName: string;
  duration: number;
  dragging: boolean;
  swipeGen: number;
  neighbors: { prev: QueueItem | null; next: QueueItem | null };
  queue: QueuePayload | null;
  queueEpoch: number;
  mini: MiniLook;
  playerC1: string | null;
  playerC2: string | null;
  toasts: ToastItem[];
};

export type PlaybackFields = {
  track_id: string;
  title: string;
  artist: string;
  artists?: ArtistRef[];
  artist_href?: string | null;
  is_playing: boolean;
  cover_url: string | null;
  cover_url_hq: string | null;
  volume: number | null;
  position_sec: number | null;
  duration_sec: number | null;
  repeat_mode: RepeatMode;
  shuffle: boolean;
  liked: boolean | null;
  queue_name: string;
};

const listeners = new Set<() => void>();

let volumeEcho = false;
let coverToken = 0;
let toastSeq = 0;
let lastBackdropUrl = '';
let playLockUntil = 0;
let playLockTarget: boolean | null = null;
let likeLockUntil = 0;
let likeLockTarget: boolean | null = null;

const state: State = {
  connected: false,
  statusTitle: 'Подключение',
  hasTrack: false,
  trackId: '',
  title: '—',
  artist: '—',
  artists: [],
  artistHref: null,
  coverUrl: null,
  coverHq: null,
  isPlaying: false,
  volume: 50,
  shuffle: false,
  repeatMode: 'off',
  liked: false,
  queueName: '',
  pos: 0,
  dur: 0,
  at: 0,
  playing: false,
  dragging: false,
  dragPos: 0,
  swipeGen: 0,
  queue: null,
  queueEpoch: 0,
  mini: resetMini(),
  playerC1: null,
  playerC2: null,
  toasts: [],
};

function neighborsOf(queue: QueuePayload | null): { prev: QueueItem | null; next: QueueItem | null } {
  if (!queue) return { prev: null, next: null };
  return {
    prev: queue.before.length ? queue.before[queue.before.length - 1] : null,
    next: queue.after.length ? queue.after[0] : null,
  };
}

function toView(): PlaybackView {
  return {
    connected: state.connected,
    statusTitle: state.statusTitle,
    hasTrack: state.hasTrack,
    trackId: state.trackId,
    title: state.title,
    artist: state.artist,
    artists: state.artists,
    artistHref: state.artistHref,
    coverUrl: state.coverUrl,
    coverHq: state.coverHq,
    isPlaying: state.isPlaying,
    volume: state.volume,
    shuffle: state.shuffle,
    repeatMode: state.repeatMode,
    liked: state.liked,
    queueName: state.queueName,
    duration: state.dur,
    dragging: state.dragging,
    swipeGen: state.swipeGen,
    neighbors: neighborsOf(state.queue),
    queue: state.queue,
    queueEpoch: state.queueEpoch,
    mini: state.mini,
    playerC1: state.playerC1,
    playerC2: state.playerC2,
    toasts: state.toasts,
  };
}

let snapshot: PlaybackView = toView();

function emit(): void {
  snapshot = toView();
  listeners.forEach((listener) => listener());
}

export function subscribePlayback(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSnapshot(): PlaybackView {
  return snapshot;
}

export function usePlaybackSelector<T>(selector: (view: PlaybackView) => T): T {
  const selectorRef = useRef(selector);
  selectorRef.current = selector;
  return useSyncExternalStore(
    subscribePlayback,
    () => selectorRef.current(snapshot),
    () => selectorRef.current(snapshot),
  );
}

let clock = 0;
const clockListeners = new Set<() => void>();

window.setInterval(() => {
  clock += 1;
  clockListeners.forEach((listener) => listener());
}, 200);

function subscribeClock(listener: () => void): () => void {
  clockListeners.add(listener);
  return () => clockListeners.delete(listener);
}

function getClock(): number {
  return clock;
}

export function useClock(): number {
  return useSyncExternalStore(subscribeClock, getClock, getClock);
}

export function playbackPositionSec(): number {
  if (state.dragging) return state.dragPos;
  if (state.dur <= 0) return 0;
  let pos = state.pos;
  if (state.playing) {
    pos += (performance.now() - state.at) / 1000;
    if (pos > state.dur) pos = state.dur;
  }
  return pos;
}

export function isVolumeEcho(): boolean {
  return volumeEcho;
}

export function hasQueueNeighbor(side: 'prev' | 'next'): boolean {
  return neighborsOf(state.queue)[side] != null;
}

export function setConnected(on: boolean): void {
  state.connected = on;
  state.statusTitle = on ? 'Подключено' : 'Переподключение…';
  emit();
}

export function pushToast(message: string, kind: 'error' | 'notice'): void {
  const id = ++toastSeq;
  state.toasts = [...state.toasts, { id, message, kind }];
  emit();
  window.setTimeout(() => {
    state.toasts = state.toasts.filter((item) => item.id !== id);
    emit();
  }, 5000);
}

function clampVolume(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function rememberQueueName(name: string): void {
  const text = name.trim();
  if (text) state.queueName = text;
}

function clearCover(): void {
  coverToken += 1;
  lastBackdropUrl = '';
  state.mini = resetMini();
}

function requestPalette(url: string): void {
  if (url === lastBackdropUrl) return;
  lastBackdropUrl = url;
  const token = ++coverToken;
  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => {
    if (token !== coverToken) return;
    const look = lookFromImage(url, img);
    state.mini = look.mini;
    if (look.playerC1) state.playerC1 = look.playerC1;
    if (look.playerC2) state.playerC2 = look.playerC2;
    emit();
  };
  img.onerror = () => {
    if (token !== coverToken) return;
    state.mini = {
      hasArt: true,
      bgImage: `url("${url.replace(/"/g, '%22')}")`,
      c1: 'rgba(36, 38, 44, 0.62)',
      c2: 'rgba(24, 26, 32, 0.45)',
      fade: 'rgba(42, 44, 52, 0.24)',
      glow: 'rgba(150, 158, 178, 0.45)',
      halo: 'rgba(130, 140, 165, 0.72)',
      haloSoft: 'rgba(120, 132, 158, 0.55)',
    };
    emit();
  };
  img.src = url;
}

export function applyPlayback(msg: PlaybackFields, full: boolean): boolean {
  const incoming = msg.track_id || '';
  const trackChanged = incoming !== state.trackId;
  state.hasTrack = true;
  if (trackChanged) state.swipeGen += 1;
  if (full || trackChanged) {
    state.trackId = incoming || state.trackId;
    state.title = msg.title || '—';
    state.artist = msg.artist || '—';
    state.artists = msg.artists ?? [];
    state.artistHref = msg.artist_href ?? null;
    const coverHq = msg.cover_url_hq || msg.cover_url;
    state.coverHq = coverHq;
    state.coverUrl = msg.cover_url || coverHq;
    if (coverHq) requestPalette(coverHq);
    else clearCover();
  } else {
    if (msg.artists && msg.artists.length > 0) {
      state.artists = msg.artists;
    }
    if (msg.artist_href != null) {
      state.artistHref = msg.artist_href;
    }
  }
  const incomingPlaying = msg.is_playing !== false;
  if (playLockTarget !== null) {
    if (incomingPlaying === playLockTarget || performance.now() > playLockUntil) {
      playLockTarget = null;
      playLockUntil = 0;
      state.isPlaying = incomingPlaying;
    }
  } else {
    state.isPlaying = incomingPlaying;
  }
  state.shuffle = msg.shuffle;
  state.repeatMode = msg.repeat_mode;
  if (msg.liked != null) {
    if (likeLockTarget !== null) {
      if (msg.liked === likeLockTarget || performance.now() > likeLockUntil) {
        likeLockTarget = null;
        likeLockUntil = 0;
        state.liked = msg.liked;
      }
    } else {
      state.liked = msg.liked;
    }
  }
  if (msg.queue_name) rememberQueueName(msg.queue_name);

  let echoedVolume = false;
  if (msg.volume != null) {
    volumeEcho = true;
    state.volume = clampVolume(msg.volume);
    echoedVolume = true;
  }

  if (!state.dragging) {
    const effectivePlaying = state.isPlaying;
    if ((msg.duration_sec ?? 0) > 0) {
      state.pos = Number(msg.position_sec) || 0;
      state.dur = Number(msg.duration_sec) || 0;
      state.playing = effectivePlaying;
      state.at = performance.now();
    } else if (msg.position_sec != null && state.dur > 0) {
      state.pos = Number(msg.position_sec) || 0;
      state.playing = effectivePlaying;
      state.at = performance.now();
    } else {
      state.playing = effectivePlaying;
      state.at = performance.now();
    }
  }

  emit();
  if (echoedVolume) {
    window.requestAnimationFrame(() => {
      volumeEcho = false;
    });
  }
  return trackChanged;
}

export function markStopped(): void {
  state.hasTrack = false;
  state.trackId = '';
  state.artists = [];
  state.artistHref = null;
  state.isPlaying = false;
  state.playing = false;
  emit();
}

export function applyQueue(queue: QueuePayload): void {
  state.queue = queue;
  state.queueEpoch += 1;
  const name = queue.now_meta.source || queue.now_meta.subtitle;
  if (name) rememberQueueName(name);
  emit();
}

export function setVolumeLocal(value: number): void {
  state.volume = clampVolume(value);
  emit();
}

export function togglePlaying(): void {
  const now = performance.now();
  if (state.dur > 0 && state.playing) {
    let pos = state.pos + (now - state.at) / 1000;
    if (pos > state.dur) pos = state.dur;
    state.pos = pos;
  }
  const next = !state.isPlaying;
  state.isPlaying = next;
  state.playing = next;
  state.at = now;
  playLockTarget = next;
  playLockUntil = now + 2500;
  emit();
}

export function toggleShuffle(): boolean {
  state.shuffle = !state.shuffle;
  emit();
  return state.shuffle;
}

const REPEAT_CYCLE: RepeatMode[] = ['off', 'queue', 'one'];

export function cycleRepeat(): void {
  const index = REPEAT_CYCLE.indexOf(state.repeatMode);
  state.repeatMode = REPEAT_CYCLE[(index + 1) % REPEAT_CYCLE.length];
  emit();
}

export function toggleLike(): void {
  const next = !state.liked;
  state.liked = next;
  likeLockTarget = next;
  likeLockUntil = performance.now() + 2500;
  emit();
}

export function beginTimelineDrag(): void {
  const sec = Math.floor(playbackPositionSec());
  state.dragging = true;
  state.dragPos = sec;
  emit();
}

export function updateTimelineDrag(sec: number): void {
  state.dragPos = sec;
}

export function endTimelineDrag(): void {
  state.dragging = false;
  emit();
}
