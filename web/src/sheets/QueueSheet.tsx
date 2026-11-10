import { useEffect, useLayoutEffect, useRef } from 'react';
import type { CatalogTrack, QueueItem, QueuePayload } from '../api/types';
import { send } from '../api/ws';
import { usePlaybackSelector } from '../store/playback';
import './QueueSheet.css';

function scrollQueueToDefault(container: HTMLElement): void {
  const anchor = container.querySelector<HTMLElement>('#queueScrollAnchor');
  const target = anchor || container.querySelector<HTMLElement>('.queue-track.current');
  if (!target) return;
  const top = target.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop;
  const pad = anchor ? 6 : container.clientHeight * 0.22;
  container.scrollTop = Math.max(0, top - pad);
}

function Dots() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="5" cy="12" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="19" cy="12" r="1.8" />
    </svg>
  );
}

function queueItemToCatalogTrack(item: QueueItem): CatalogTrack {
  return {
    id: item.track_id != null ? item.track_id : Number.NaN,
    album_id: item.album_id,
    title: item.title,
    artist: item.artist,
    artists: item.artists,
    cover_url: item.cover,
  };
}

function QueueTrack({
  item,
  current,
  anchor,
  onPick,
  onMenu,
}: {
  item: QueueItem;
  current: boolean;
  anchor: boolean;
  onPick: (item: QueueItem) => void;
  onMenu: (track: CatalogTrack) => void;
}) {
  return (
    <li
      className={current ? 'queue-track current' : 'queue-track'}
      id={anchor ? 'queueScrollAnchor' : undefined}
      onClick={item.track_id == null ? undefined : () => onPick(item)}
    >
      {item.cover ? <img src={item.cover} alt="" /> : null}
      <div className="queue-meta">
        <span className="title">{`${current ? '▶ ' : ''}${item.title || ''}`}</span>
        {item.artist ? <span className="artist">{item.artist}</span> : null}
      </div>
      <button
        type="button"
        className="queue-row-action"
        aria-label="Действия с треком"
        onClick={(event) => {
          event.stopPropagation();
          onMenu(queueItemToCatalogTrack(item));
        }}
      >
        <Dots />
      </button>
    </li>
  );
}

function QueueBody({
  queue,
  onPick,
  onMenu,
}: {
  queue: QueuePayload | null;
  onPick: (item: QueueItem) => void;
  onMenu: (track: CatalogTrack) => void;
}) {
  if (!queue) return null;
  const { before, current, after } = queue;
  if (!before.length && !current && !after.length) {
    return <li className="queue-empty">Очередь пуста или панель не открылась в приложении</li>;
  }
  const beforeAnchor = before.length >= 3 ? before.length - 3 : -1;
  const currentAnchor = before.length < 3 && current != null;
  let nowTitle = queue.now_meta.subtitle || 'Сейчас играет';
  if (queue.now_meta.source) nowTitle += ` · ${queue.now_meta.source}`;
  return (
    <>
      {before.length > 0 ? (
        <>
          <li className="queue-section-title">{queue.before_title || 'Предыдущая очередь'}</li>
          {before.map((item, index) => (
            <QueueTrack
              key={`b-${index}-${item.track_id ?? 'x'}`}
              item={item}
              current={false}
              anchor={index === beforeAnchor}
              onPick={onPick}
              onMenu={onMenu}
            />
          ))}
        </>
      ) : null}
      {current ? (
        <>
          <li className="queue-section-title">{nowTitle}</li>
          <QueueTrack item={current} current anchor={currentAnchor} onPick={onPick} onMenu={onMenu} />
        </>
      ) : null}
      {after.length > 0 ? (
        <>
          <li className="queue-section-title">{queue.after_title || 'Далее в очереди'}</li>
          {after.map((item, index) => (
            <QueueTrack
              key={`a-${index}-${item.track_id ?? 'x'}`}
              item={item}
              current={false}
              anchor={false}
              onPick={onPick}
              onMenu={onMenu}
            />
          ))}
        </>
      ) : null}
    </>
  );
}

export function QueueSheet({
  open,
  onClose,
  onMenu,
}: {
  open: boolean;
  onClose: () => void;
  onMenu: (track: CatalogTrack) => void;
}) {
  const queue = usePlaybackSelector((view) => view.queue);
  const epoch = usePlaybackSelector((view) => view.queueEpoch);
  const scrollRef = useRef<HTMLDivElement>(null);
  const saved = useRef(0);
  const epochAtOpen = useRef<number | null>(null);
  const didInitial = useRef(false);

  useEffect(() => {
    if (!open) return;
    send({ command: 'show_queue' }, { wait: true });
    const timer = window.setInterval(() => {
      send({ command: 'refresh_queue' });
    }, 2500);
    return () => window.clearInterval(timer);
  }, [open]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!open || !el) {
      if (!open) {
        epochAtOpen.current = null;
        didInitial.current = false;
      }
      return;
    }
    if (epochAtOpen.current == null) epochAtOpen.current = epoch;
    if (!didInitial.current && epoch !== epochAtOpen.current) {
      didInitial.current = true;
      window.requestAnimationFrame(() => scrollQueueToDefault(el));
      return;
    }
    if (didInitial.current) el.scrollTop = saved.current;
  }, [open, epoch, queue]);

  const pick = (item: QueueItem) => {
    if (item.track_id == null) return;
    send({
      command: 'play_queue_track',
      track_id: item.track_id,
      album_id: item.album_id,
      title: item.title,
      artist: item.artist,
    });
  };

  return (
    <div className={open ? 'queue-sheet open' : 'queue-sheet'} id="queueSheet" aria-hidden={!open}>
      <div className="queue-sheet-header">
        <button type="button" className="nav-btn" id="btnQueueClose" aria-label="Назад" onClick={onClose}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <h2>Очередь</h2>
      </div>
      <div
        className="queue-scroll queue-panel"
        id="queueScroll"
        ref={scrollRef}
        onScroll={(event) => {
          saved.current = event.currentTarget.scrollTop;
        }}
      >
        <ul id="queueList">
          <QueueBody queue={queue} onPick={pick} onMenu={onMenu} />
        </ul>
      </div>
    </div>
  );
}
