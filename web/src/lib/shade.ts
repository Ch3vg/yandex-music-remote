import { useSyncExternalStore } from 'react';
import { ensureWsAlive, send } from '../api/ws';
import {
  getSnapshot,
  playbackPositionSec,
  pushToast,
  subscribePlayback,
  togglePlaying,
} from '../store/playback';

const STORAGE_KEY = 'ym_shade';
const OLD_TAG = 'ym-now';

let enabled = true;
try {
  enabled = localStorage.getItem(STORAGE_KEY) !== '0';
} catch {
  enabled = true;
}

const shadeListeners = new Set<() => void>();
let started = false;
let audioEl: HTMLAudioElement | null = null;
let silenceUrl: string | null = null;
let handlersBound = false;
let lastMetaKey = '';
let lastPosSyncAt = 0;
let releaseWakeLock: (() => void) | null = null;
let keepAliveWorker: Worker | null = null;
let pausedBySystem = false;
let internalPause = false;

function emitShade(): void {
  shadeListeners.forEach((listener) => listener());
}

export function isShadeSupported(): boolean {
  return typeof window !== 'undefined' && typeof navigator !== 'undefined' && 'mediaSession' in navigator;
}

export function isShadeActive(): boolean {
  return isShadeSupported() && enabled;
}

export function useShadeEnabled(): boolean {
  return useSyncExternalStore(
    (listener) => {
      shadeListeners.add(listener);
      return () => shadeListeners.delete(listener);
    },
    isShadeActive,
    () => false,
  );
}

function holdWebLock(): void {
  if (releaseWakeLock) return;
  const nav = navigator as Navigator & {
    locks?: {
      request: (name: string, cb: () => Promise<void>) => Promise<void>;
    };
  };
  if (!nav.locks || typeof nav.locks.request !== 'function') return;
  try {
    nav.locks
      .request('ym_remote_shade_lock', () => new Promise<void>((resolve) => {
        releaseWakeLock = () => {
          releaseWakeLock = null;
          resolve();
        };
      }))
      .catch(() => {
        releaseWakeLock = null;
      });
  } catch {
    releaseWakeLock = null;
  }
}

function dropWebLock(): void {
  if (releaseWakeLock) {
    releaseWakeLock();
  }
}

function startKeepAliveWorker(): void {
  if (keepAliveWorker || typeof Worker === 'undefined') return;
  try {
    const code = 'setInterval(() => postMessage(1), 1500);';
    const blob = new Blob([code], { type: 'application/javascript' });
    const url = URL.createObjectURL(blob);
    const worker = new Worker(url);
    worker.onmessage = () => {
      if (!isShadeActive()) return;
      ensureWsAlive();
    };
    keepAliveWorker = worker;
  } catch {
    // ignore
  }
}

function stopKeepAliveWorker(): void {
  if (keepAliveWorker) {
    keepAliveWorker.terminate();
    keepAliveWorker = null;
  }
}

function buildSilentWavUrl(): string {
  if (silenceUrl) return silenceUrl;
  const sampleRate = 8000;
  const seconds = 30;
  const numSamples = sampleRate * seconds;
  const dataSize = numSamples * 2;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);
  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, dataSize, true);
  // 1 Hz infrasound: keeps Chromium AudioPowerMonitor active in background while completely inaudible.
  const twoPiF = (2 * Math.PI * 1) / sampleRate;
  for (let i = 0; i < numSamples; i += 1) {
    const sample = Math.round(Math.sin(i * twoPiF) * 600);
    view.setInt16(44 + i * 2, sample, true);
  }
  const blob = new Blob([buffer], { type: 'audio/wav' });
  silenceUrl = URL.createObjectURL(blob);
  return silenceUrl;
}

function pauseCarrierInternally(el: HTMLAudioElement): void {
  if (el.paused) return;
  internalPause = true;
  try {
    el.pause();
  } catch {
    // ignore
  } finally {
    window.setTimeout(() => {
      internalPause = false;
    }, 0);
  }
}

function ensureAudio(): HTMLAudioElement {
  if (audioEl) return audioEl;
  const el = document.createElement('audio');
  el.src = buildSilentWavUrl();
  el.loop = true;
  el.preload = 'auto';
  el.volume = 0.05;
  el.setAttribute('playsinline', 'true');
  el.style.display = 'none';

  el.addEventListener('timeupdate', () => {
    if (el.currentTime > 24) {
      try {
        el.currentTime = 1;
      } catch {
        // ignore
      }
    }
    ensureWsAlive();
    const now = performance.now();
    if (now - lastPosSyncAt > 1000) {
      lastPosSyncAt = now;
      syncMediaSession();
    }
  });

  el.addEventListener('play', () => {
    pausedBySystem = false;
    syncMediaSession();
  });

  // Distinguish between our own pause (when PC music paused) vs Android system pause (when YouTube started).
  el.addEventListener('pause', () => {
    if (!isShadeActive()) return;
    if (!internalPause && getSnapshot().isPlaying) {
      // Another app on the phone (e.g. YouTube) took audio focus.
      // Do NOT re-play carrier in background (so YouTube keeps playing),
      // and do NOT change PC playback state (notification still shows playing).
      pausedBySystem = true;
    }
    syncMediaSession();
  });

  document.body.appendChild(el);
  audioEl = el;
  return el;
}

async function closeLegacyNotification(): Promise<void> {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg || !reg.getNotifications) return;
    const list = await reg.getNotifications({ tag: OLD_TAG });
    list.forEach((item) => item.close());
  } catch {
    // ignore
  }
}

function bindMediaSessionHandlers(): void {
  if (handlersBound || !isShadeSupported()) return;
  handlersBound = true;
  const ms = navigator.mediaSession;
  const safeSet = (action: MediaSessionAction, handler: MediaSessionActionHandler | null) => {
    try {
      ms.setActionHandler(action, handler);
    } catch {
      // ignore unsupported action
    }
  };

  safeSet('play', () => {
    ensureWsAlive();
    pausedBySystem = false;
    const snap = getSnapshot();
    if (!snap.isPlaying) {
      togglePlaying();
    }
    send({ command: 'play_pause' });
    const el = ensureAudio();
    if (el.paused) {
      el.play().catch(() => {});
    }
    syncMediaSession();
  });

  safeSet('pause', () => {
    ensureWsAlive();
    const snap = getSnapshot();
    if (snap.isPlaying) {
      togglePlaying();
    }
    send({ command: 'play_pause' });
    // Pause carrier audio so Chromium MediaSession transitions to State::SUSPENDED + kPaused:
    // the notification stays in the shade (does not hide) and its button changes to Play (▶).
    if (audioEl) {
      pauseCarrierInternally(audioEl);
    }
    syncMediaSession();
  });

  safeSet('previoustrack', () => {
    ensureWsAlive();
    pausedBySystem = false;
    send({ command: 'prev' });
  });

  safeSet('nexttrack', () => {
    ensureWsAlive();
    pausedBySystem = false;
    send({ command: 'next' });
  });

  safeSet('seekbackward', null);
  safeSet('seekforward', null);

  safeSet('seekto', (details) => {
    ensureWsAlive();
    if (typeof details.seekTime === 'number' && Number.isFinite(details.seekTime)) {
      const sec = Math.max(0, Math.floor(details.seekTime));
      send({ command: 'seek', position_sec: sec });
    }
  });
}

function unbindMediaSession(): void {
  if (!isShadeSupported()) return;
  const ms = navigator.mediaSession;
  const actions: MediaSessionAction[] = [
    'play',
    'pause',
    'previoustrack',
    'nexttrack',
    'seekto',
    'seekbackward',
    'seekforward',
  ];
  actions.forEach((action) => {
    try {
      ms.setActionHandler(action, null);
    } catch {
      // ignore
    }
  });
  try {
    ms.metadata = null;
    ms.playbackState = 'none';
  } catch {
    // ignore
  }
  handlersBound = false;
  lastMetaKey = '';
}

function stopAudio(): void {
  pausedBySystem = false;
  dropWebLock();
  stopKeepAliveWorker();
  if (audioEl) {
    pauseCarrierInternally(audioEl);
    try {
      audioEl.currentTime = 0;
    } catch {
      // ignore
    }
  }
  unbindMediaSession();
}

function syncMediaSession(): void {
  if (!isShadeActive()) {
    stopAudio();
    return;
  }
  const view = getSnapshot();
  if (!view.connected || !view.hasTrack || !view.trackId) {
    if (!view.hasTrack) stopAudio();
    return;
  }

  holdWebLock();
  startKeepAliveWorker();
  bindMediaSessionHandlers();
  const el = ensureAudio();

  if (view.isPlaying) {
    // Start carrier audio when PC is playing, UNLESS another phone app (YouTube) took audio focus.
    if (el.paused && !pausedBySystem) {
      el.play().catch(() => {});
    }
  } else if (!el.paused) {
    // When PC is paused, pause carrier audio so Chromium shows the paused state in the shade
    // (State::SUSPENDED keeps the notification visible in the shade without hiding it).
    pauseCarrierInternally(el);
  }

  const ms = navigator.mediaSession;
  const coverHq = view.coverHq || view.coverUrl || '';
  const cover = view.coverUrl || coverHq || '';
  const metaKey = `${view.trackId}|${view.title}|${view.artist}|${view.queueName}|${cover}|${coverHq}`;
  if (metaKey !== lastMetaKey && typeof MediaMetadata !== 'undefined') {
    lastMetaKey = metaKey;
    const artwork: MediaImage[] = [];
    if (cover) artwork.push({ src: cover, sizes: '200x200', type: 'image/jpeg' });
    if (coverHq && coverHq !== cover) artwork.push({ src: coverHq, sizes: '600x600', type: 'image/jpeg' });
    if (!artwork.length) artwork.push({ src: '/icon-512.png', sizes: '512x512', type: 'image/png' });
    try {
      ms.metadata = new MediaMetadata({
        title: view.title || 'YM Remote',
        artist: view.artist || '—',
        album: view.queueName || 'Яндекс Музыка',
        artwork,
      });
    } catch {
      // ignore
    }
  }

  // Always reflect the actual PC playback state in MediaSession.
  // In Chromium GetMediaSessionInfoSync(), even when YouTube suspended our <audio>,
  // setting ms.playbackState = 'playing' forces info->playback_state = kPlaying in the shade!
  try {
    ms.playbackState = view.isPlaying ? 'playing' : 'paused';
  } catch {
    // ignore
  }

  if (typeof ms.setPositionState === 'function' && view.duration > 0) {
    const pos = Math.max(0, Math.min(view.duration, playbackPositionSec()));
    try {
      ms.setPositionState({
        duration: view.duration,
        playbackRate: view.isPlaying ? 1 : 0.000001,
        position: pos,
      });
    } catch {
      // ignore
    }
  }
}

export async function toggleShade(): Promise<void> {
  void closeLegacyNotification();
  if (!isShadeSupported()) {
    pushToast('Браузер не поддерживает Media Session', 'error');
    return;
  }
  if (enabled) {
    enabled = false;
    try {
      localStorage.setItem(STORAGE_KEY, '0');
    } catch {
      // ignore
    }
    stopAudio();
    emitShade();
    pushToast('Плеер в шторке выключен', 'notice');
    return;
  }

  enabled = true;
  pausedBySystem = false;
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // ignore
  }
  emitShade();

  const el = ensureAudio();
  if (getSnapshot().isPlaying) {
    try {
      await el.play();
    } catch {
      // ignore
    }
  }
  syncMediaSession();
  pushToast('Плеер в шторке включён', 'notice');
}

export function startShade(): () => void {
  if (started) return () => {};
  started = true;
  void closeLegacyNotification();

  const unlockOnGesture = () => {
    if (!isShadeActive()) return;
    pausedBySystem = false;
    const view = getSnapshot();
    const el = ensureAudio();
    if (view.connected && view.hasTrack && view.isPlaying && el.paused) {
      el.play().then(() => syncMediaSession()).catch(() => {});
    }
  };

  const onVisible = () => {
    ensureWsAlive();
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      pausedBySystem = false;
    }
    syncMediaSession();
  };

  window.addEventListener('pointerdown', unlockOnGesture, { passive: true });
  document.addEventListener('visibilitychange', onVisible);
  const unsub = subscribePlayback(() => {
    syncMediaSession();
  });
  syncMediaSession();

  return () => {
    started = false;
    window.removeEventListener('pointerdown', unlockOnGesture);
    document.removeEventListener('visibilitychange', onVisible);
    unsub();
  };
}
