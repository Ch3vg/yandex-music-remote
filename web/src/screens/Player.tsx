import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import type { QueueItem } from '../api/types';
import { send } from '../api/ws';
import { VolumeIcon } from '../components/VolumeIcon';
import { bindTrackSwipe, horizontalSwipe, type SwipeHandle } from '../lib/gestures';
import { formatTime } from '../lib/time';
import {
  beginTimelineDrag,
  cycleRepeat,
  endTimelineDrag,
  hasQueueNeighbor,
  isVolumeEcho,
  playbackPositionSec,
  setVolumeLocal,
  toggleLike,
  togglePlaying,
  toggleShuffle,
  updateTimelineDrag,
  useClock,
  usePlaybackSelector,
} from '../store/playback';
import type { PlayerPhase } from '../app/screen';
import { useRef } from 'react';
import './Player.css';

function SidePane({ item, prefix }: { item: QueueItem | null; prefix: 'Prev' | 'Next' }) {
  const url = item?.cover || '';
  return (
    <div
      className={item ? 'player-track-swipe-pane player-swipe-side' : 'player-track-swipe-pane player-swipe-side empty'}
      id={prefix === 'Prev' ? 'playerPanePrev' : 'playerPaneNext'}
      aria-hidden="true"
    >
      <div className="player-art-wrap player-art-wrap--peek">
        <img className="player-art player-art-peek" id={`npCover${prefix}`} alt="" hidden={!url} src={url || undefined} />
        <div className="player-art placeholder player-art-peek-ph" id={`npCover${prefix}Ph`} hidden={!!url}>♪</div>
      </div>
      <div className="player-track-peek">
        <div className="player-title" id={`npTitle${prefix}`}>{item?.title || '—'}</div>
        <div className="player-artist" id={`npArtist${prefix}`}>{item ? item.artist || '' : ''}</div>
      </div>
    </div>
  );
}

type Props = {
  phase: PlayerPhase;
  onClose: () => void;
  onQueue: () => void;
};

export function Player({ phase, onClose, onQueue }: Props) {
  const view = usePlaybackSelector((item) => item);
  const clock = useClock();
  const bgRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const swipeRef = useRef<SwipeHandle | null>(null);
  const [localPos, setLocalPos] = useState(0);
  const seeking = useRef(false);

  useEffect(() => {
    const viewport = viewportRef.current;
    const strip = stripRef.current;
    if (!viewport || !strip) return;
    return bindTrackSwipe(viewport, strip, swipeRef, {
      hasPrev: () => hasQueueNeighbor('prev'),
      hasNext: () => hasQueueNeighbor('next'),
      onCommit: (dir) => send({ command: dir === 'next' ? 'next' : 'prev' }),
    });
  }, []);

  useEffect(() => {
    swipeRef.current?.reset();
  }, [view.swipeGen]);

  useEffect(() => {
    if (phase === 'open') swipeRef.current?.measure();
  }, [phase]);

  useEffect(() => {
    if (view.playerC1) document.documentElement.style.setProperty('--player-c1', view.playerC1);
  }, [view.playerC1]);

  useEffect(() => {
    const el = bgRef.current;
    if (!el) return;
    let sx = 0;
    let sy = 0;
    let active = false;
    const start = (event: TouchEvent) => {
      if (horizontalSwipe()) return;
      const touch = event.touches[0];
      sx = touch.clientX;
      sy = touch.clientY;
      active = true;
    };
    const end = (event: TouchEvent) => {
      if (!active || horizontalSwipe()) {
        active = false;
        return;
      }
      active = false;
      const touch = event.changedTouches[0];
      const dx = touch.clientX - sx;
      const dy = touch.clientY - sy;
      if (dy > 56 && dy > Math.abs(dx) * 1.2) onClose();
    };
    el.addEventListener('touchstart', start, { passive: true });
    el.addEventListener('touchend', end);
    return () => {
      el.removeEventListener('touchstart', start);
      el.removeEventListener('touchend', end);
    };
  }, [onClose]);

  const playing = view.isPlaying;
  const repeatClass = [
    'btn-mode',
    'btn-repeat',
    view.repeatMode !== 'off' ? 'active' : '',
    view.repeatMode === 'one' ? 'repeat-one' : '',
  ].filter(Boolean).join(' ');
  const shown = view.dragging ? localPos : Math.floor(playbackPositionSec());
  void clock;
  const bgStyle = view.playerC1 && view.playerC2
    ? ({ '--player-c1': view.playerC1, '--player-c2': view.playerC2 } as CSSProperties)
    : undefined;

  return (
    <section className={phase === 'closed' ? 'screen' : 'screen active'} id="screenPlayer">
      <div className="player-bg" id="nowPlaying" ref={bgRef} style={bgStyle}>
        <div className="player-nav">
          <button type="button" className="nav-btn" id="btnPlayerClose" aria-label="Свернуть" onClick={onClose}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
          <div className="player-nav-center">
            <div className="player-nav-kicker">Сейчас играет</div>
            <div className="player-nav-title" id="playerQueueName">{view.queueName || '—'}</div>
          </div>
          <button type="button" className="nav-btn" id="btnPlayerQueue" aria-label="Очередь" onClick={onQueue}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
            </svg>
          </button>
        </div>
        <div className="player-track-swipe-viewport" id="playerSwipeViewport" ref={viewportRef}>
          <div className="player-track-swipe-strip" id="playerSwipeStrip" ref={stripRef}>
            <SidePane item={view.neighbors.prev} prefix="Prev" />
            <div className="player-track-swipe-pane player-swipe-center">
              <div className="player-art-wrap">
                <img className="player-art" id="npCover" alt="" hidden={!view.coverHq} src={view.coverHq || undefined} />
                <div className="player-art placeholder" id="npCoverPh" hidden={!!view.coverHq}>♪</div>
              </div>
              <button
                type="button"
                className="player-track-row"
                id="playerTrackRow"
                onClick={() => send({ command: 'navigate', target: 'artist' })}
              >
                <img className="track-thumb" id="npThumb" alt="" hidden={!view.coverUrl} src={view.coverUrl || undefined} width={44} height={44} />
                <div className="track-thumb ph" id="npThumbPh" hidden={!!view.coverUrl}>♪</div>
                <div className="track-meta">
                  <div className="player-title" id="npTitle">{view.title}</div>
                  <div className="player-artist" id="npArtist">{view.artist}</div>
                </div>
                <span className="track-chevron" aria-hidden="true">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                </span>
              </button>
            </div>
            <SidePane item={view.neighbors.next} prefix="Next" />
          </div>
        </div>
        <div className="timeline-block">
          <input
            type="range"
            id="timeline"
            min={0}
            max={view.duration > 0 ? view.duration : 0}
            value={shown}
            onPointerDown={() => {
              seeking.current = true;
              const sec = Math.floor(playbackPositionSec());
              setLocalPos(sec);
              beginTimelineDrag();
            }}
            onInput={(event) => {
              const sec = parseInt(event.currentTarget.value, 10) || 0;
              setLocalPos(sec);
              updateTimelineDrag(sec);
            }}
            onChange={(event) => {
              if (!seeking.current) return;
              seeking.current = false;
              endTimelineDrag();
              send({ command: 'seek', position_sec: parseInt(event.currentTarget.value, 10) || 0 });
            }}
            onPointerUp={(event) => {
              if (!seeking.current) return;
              seeking.current = false;
              endTimelineDrag();
              send({ command: 'seek', position_sec: parseInt(event.currentTarget.value, 10) || 0 });
            }}
            onPointerCancel={() => {
              seeking.current = false;
              endTimelineDrag();
            }}
          />
          <div className="timeline-labels">
            <span id="timeCurrent">{formatTime(shown)}</span>
            <span id="timeDuration">{formatTime(view.duration)}</span>
          </div>
        </div>
        <div className="transport-main">
          <button type="button" className="btn-side" id="btnDislike" aria-label="Не нравится" onClick={() => send({ command: 'track_reaction', kind: 'dislike' })}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
              <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
            </svg>
          </button>
          <button
            type="button"
            className={view.shuffle ? 'btn-mode active' : 'btn-mode'}
            id="btnShuffle"
            aria-label="Перемешать"
            onClick={() => send({ command: 'set_shuffle', on: toggleShuffle() })}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 3h5v5" />
              <path d="M4 20L21 3" />
              <path d="M21 16v5h-5" />
              <path d="M15 15l6 6" />
              <path d="M4 4l5 5" />
            </svg>
          </button>
          <button type="button" className="btn-skip" aria-label="Назад" onClick={() => send({ command: 'prev' })}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z" />
            </svg>
          </button>
          <button
            type="button"
            className={playing ? 'btn-play is-playing' : 'btn-play'}
            id="btnPlayPause"
            aria-label={playing ? 'Пауза' : 'Воспроизведение'}
            onClick={() => {
              togglePlaying();
              send({ command: 'play_pause' });
            }}
          >
            <svg className={playing ? 'icon-play' : 'icon-play show'} viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7L8 5z" />
            </svg>
            <svg className={playing ? 'icon-pause show' : 'icon-pause'} viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 5h4v14H6V5zm8 0h4v14h-4V5z" />
            </svg>
          </button>
          <button type="button" className="btn-skip" aria-label="Вперёд" onClick={() => send({ command: 'next' })}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 18h2V6h-2v12zM6 18l8.5-6L6 6v12z" />
            </svg>
          </button>
          <button
            type="button"
            className={repeatClass}
            id="btnRepeat"
            aria-label="Повтор"
            onClick={() => {
              cycleRepeat();
              send({ command: 'cycle_repeat' });
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 1l4 4-4 4" />
              <path d="M3 11V9a4 4 0 0 1 4-4h14" />
              <path d="M7 23l-4-4 4-4" />
              <path d="M21 13v2a4 4 0 0 1-4 4H3" />
            </svg>
          </button>
          <button
            type="button"
            className={view.liked ? 'btn-side liked' : 'btn-side'}
            id="btnLike"
            aria-label={view.liked ? 'Убрать из коллекции' : 'Нравится'}
            aria-pressed={view.liked}
            onClick={() => {
              toggleLike();
              send({ command: 'track_reaction', kind: 'like' });
            }}
          >
            <svg className="heart-outline" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <svg className="heart-fill" width="26" height="26" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
            </svg>
          </button>
        </div>
        <div className="player-volume-dock">
          <VolumeIcon pct={view.volume} size={22} />
          <input
            type="range"
            id="volumePlayer"
            min={0}
            max={100}
            value={view.volume}
            aria-label="Громкость"
            onInput={(event) => {
              if (isVolumeEcho()) return;
              const next = Math.round(Number(event.currentTarget.value));
              if (!Number.isFinite(next)) return;
              setVolumeLocal(next);
              send({ command: 'set_volume', value: next });
            }}
          />
        </div>
      </div>
    </section>
  );
}
