import { useEffect, useLayoutEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import type { QueueItem } from '../api/types';
import { send } from '../api/ws';
import { bindTrackSwipe, miniTapBlocked, type SwipeHandle } from '../lib/gestures';
import { hasQueueNeighbor, playbackPositionSec, togglePlaying, useClock, usePlaybackSelector } from '../store/playback';
import './MiniPlayer.css';

function MiniSide({ item, id }: { item: QueueItem | null; id: string }) {
  return (
    <div className={item ? 'mini-swipe-pane' : 'mini-swipe-pane empty'} id={id} aria-hidden="true">
      <img className="mini-cover-peek" alt="" hidden={!item?.cover} src={item?.cover || undefined} />
      <div className="mini-meta-peek">
        <div className="mini-title mini-title-peek">{item?.title || '—'}</div>
        <div className="mini-artist mini-artist-peek">{item?.artist || ''}</div>
      </div>
    </div>
  );
}

export function MiniPlayer({ onOpen }: { onOpen: () => void }) {
  const view = usePlaybackSelector((item) => item);
  const clock = useClock();
  const innerRef = useRef<HTMLDivElement>(null);
  const playedRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const swipeRef = useRef<SwipeHandle | null>(null);

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
    swipeRef.current?.measure();
  }, [view.hasTrack]);

  useLayoutEffect(() => {
    const inner = innerRef.current;
    const played = playedRef.current;
    if (!inner || !played) return;
    const fullW = inner.clientWidth || 0;
    const dur = view.duration;
    const pos = playbackPositionSec();
    const pct = dur > 0 ? (pos / dur) * 100 : 0;
    const clamped = Math.max(0, Math.min(100, pct));
    played.style.width = `${Math.round((fullW * clamped) / 100)}px`;
    if (fullW > 0) inner.style.setProperty('--mini-bar-w', `${fullW}px`);
  });

  useEffect(() => {
    const inner = innerRef.current;
    if (!inner || typeof ResizeObserver === 'undefined') return;
    const paint = () => {
      const played = playedRef.current;
      if (!played) return;
      const fullW = inner.clientWidth || 0;
      const dur = view.duration;
      const pos = playbackPositionSec();
      const pct = dur > 0 ? (pos / dur) * 100 : 0;
      played.style.width = `${Math.round((fullW * Math.max(0, Math.min(100, pct))) / 100)}px`;
      if (fullW > 0) inner.style.setProperty('--mini-bar-w', `${fullW}px`);
    };
    const observer = new ResizeObserver(paint);
    observer.observe(inner);
    return () => observer.disconnect();
  }, [view.duration]);

  const look = view.mini;
  const style = {
    '--mini-bg-image': look.bgImage ?? 'none',
    '--mini-c1': look.c1,
    '--mini-c2': look.c2,
    '--mini-c-fade': look.fade,
    '--mini-glow': look.glow,
    '--mini-halo': look.halo,
    '--mini-halo-soft': look.haloSoft,
  } as CSSProperties;
  const playing = view.isPlaying;
  void clock;

  return (
    <div className={view.hasTrack ? 'mini-player' : 'mini-player hidden'} id="miniPlayer" style={style}>
      <div className="mini-player-frame">
        <div
          className={look.hasArt ? 'mini-player-inner mini-player-inner--has-art' : 'mini-player-inner'}
          id="miniPlayerInner"
          ref={innerRef}
          style={style}
          onClick={(event) => {
            if (miniTapBlocked()) return;
            if ((event.target as HTMLElement).closest('.mini-play')) return;
            onOpen();
          }}
        >
          <div className="mini-player-visual" aria-hidden="true">
            <div className="mini-player-idle" />
          </div>
          <div className="mini-player-played" id="miniPlayerPlayed" ref={playedRef}>
            <div className="mini-player-played-fill" aria-hidden="true">
              <div className="mini-player-bg" />
              <div className="mini-player-scrim" />
            </div>
          </div>
          <div className="mini-player-content">
            <div className="mini-swipe-viewport" id="miniSwipeViewport" ref={viewportRef}>
              <div className="mini-swipe-strip" id="miniSwipeStrip" ref={stripRef}>
                <MiniSide item={view.neighbors.prev} id="miniPanePrev" />
                <div className="mini-swipe-pane">
                  <img className="mini-cover" id="miniCover" alt="" hidden={!view.coverUrl} src={view.coverUrl || undefined} />
                  <div className="mini-meta" id="miniMetaTap">
                    <div className="mini-title" id="miniTitle">{view.title}</div>
                    <div className="mini-artist" id="miniArtist">{view.artist}</div>
                  </div>
                </div>
                <MiniSide item={view.neighbors.next} id="miniPaneNext" />
              </div>
            </div>
            <button
              type="button"
              className="mini-play"
              id="miniPlayBtn"
              aria-label={playing ? 'Пауза' : 'Воспроизведение'}
              onClick={(event) => {
                event.stopPropagation();
                togglePlaying();
                send({ command: 'play_pause' });
              }}
            >
              <svg className={playing ? '' : 'show'} viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7L8 5z" />
              </svg>
              <svg className={playing ? 'show' : ''} viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 5h4v14H6V5zm8 0h4v14h-4V5z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
