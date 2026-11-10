import { useEffect, useMemo, useRef, useState } from 'react';
import type { CatalogTrack, PlayMode } from '../api/types';
import {
  type ArtistChipItem,
  buildInitialArtistChips,
  hydrateArtistChipsForTrack,
} from '../lib/artistResolver';
import { normalizeCoverUrl } from '../lib/coverUrl';
import './TrackActions.css';

const ACTIONS: { id: PlayMode; label: string }[] = [
  { id: 'now', label: 'Включить сейчас' },
  { id: 'next', label: 'Играть следующим' },
  { id: 'queue', label: 'Добавить в очередь' },
];

type Props = {
  track: CatalogTrack | null;
  onClose: () => void;
  onAction: (track: CatalogTrack, mode: PlayMode) => void;
  onSelectArtist: (chip: ArtistChipItem, track: CatalogTrack) => void;
};

function ActionIcon({ mode }: { mode: PlayMode }) {
  if (mode === 'now') {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
        <path d="M7.5 5.6L18.2 12 7.5 18.4V5.6z" />
      </svg>
    );
  }
  if (mode === 'next') {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M7 6l5 5 5-5" />
        <path d="M4 15h16" />
        <path d="M4 19.5h16" />
      </svg>
    );
  }
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 6.5h16" />
      <path d="M4 11h16" />
      <path d="M7 19l5-5 5 5" />
    </svg>
  );
}

function TrackThumb({ url }: { url: string | null | undefined }) {
  const src = normalizeCoverUrl(url, '200x200');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  return (
    <div className="track-action-cover" aria-hidden="true">
      {src && !failed ? (
        <img src={src} alt="" onError={() => setFailed(true)} />
      ) : (
        <span className="track-action-cover-ph">♪</span>
      )}
    </div>
  );
}

function ArtistChipAvatar({ url, name }: { url: string | null | undefined; name: string }) {
  const src = normalizeCoverUrl(url, '200x200');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  const initial = (name || '').trim().charAt(0).toUpperCase() || '♪';

  return (
    <span className="track-action-artist-avatar" aria-hidden="true">
      {src && !failed ? (
        <img src={src} alt="" onError={() => setFailed(true)} />
      ) : (
        <span className="track-action-artist-initial">{initial}</span>
      )}
    </span>
  );
}

export function TrackActions({ track, onClose, onAction, onSelectArtist }: Props) {
  const lastTrackRef = useRef<CatalogTrack | null>(null);
  if (track) {
    lastTrackRef.current = track;
  }
  const displayTrack = track ?? lastTrackRef.current;

  const trackKey = displayTrack
    ? `${Number.isFinite(Number(displayTrack.id)) ? displayTrack.id : 'x'}|${displayTrack.title}|${displayTrack.artist}`
    : '';

  const baseChips = useMemo(() => buildInitialArtistChips(displayTrack), [displayTrack]);
  const [hydrated, setHydrated] = useState<{ key: string; chips: ArtistChipItem[] } | null>(null);

  useEffect(() => {
    if (!track) return;
    const key = `${Number.isFinite(Number(track.id)) ? track.id : 'x'}|${track.title}|${track.artist}`;
    const initial = buildInitialArtistChips(track);
    const needsHydration =
      initial.length === 0
      || initial.some((item) => item.id == null || !item.cover_url);
    if (!needsHydration) return;

    let cancelled = false;
    void hydrateArtistChipsForTrack(track, initial).then((nextChips) => {
      if (cancelled) return;
      setHydrated({ key, chips: nextChips });
    });
    return () => {
      cancelled = true;
    };
  }, [track]);

  const chips = hydrated && hydrated.key === trackKey ? hydrated.chips : baseChips;
  const canPlayTrack =
    displayTrack == null
    || (Number.isFinite(Number(displayTrack.id)) && Number(displayTrack.id) > 0);

  return (
    <div
      className={track ? 'track-action-sheet open' : 'track-action-sheet'}
      id="trackActionSheet"
      aria-hidden={!track}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="track-action-panel" role="dialog" aria-labelledby="trackActionTitle">
        <div className="track-action-grabber" aria-hidden="true" />
        <div className="track-action-top">
          <div className="track-action-head">
            <TrackThumb url={displayTrack?.cover_url_hq || displayTrack?.cover_url} />
            <div className="track-action-meta">
              <div className="title" id="trackActionTitle">{displayTrack?.title || 'Трек'}</div>
            </div>
          </div>

          {chips.length > 0 ? (
            <div className="track-action-artists" id="trackActionArtists">
              {chips.map((chip, idx) => (
                <button
                  key={`${chip.id ?? 'n'}-${chip.name}-${idx}`}
                  type="button"
                  className="track-action-artist-chip"
                  onClick={() => {
                    if (track) onSelectArtist(chip, track);
                  }}
                >
                  <ArtistChipAvatar url={chip.cover_url} name={chip.name} />
                  <span className="track-action-artist-name">{chip.name}</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {canPlayTrack ? (
          <ul className="track-action-list" id="trackActionList">
            {ACTIONS.map((action) => (
              <li key={action.id}>
                <button
                  type="button"
                  onClick={() => {
                    if (track) onAction(track, action.id);
                  }}
                >
                  <span className="track-action-icon">
                    <ActionIcon mode={action.id} />
                  </span>
                  <span>{action.label}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <button type="button" className="track-action-cancel" id="trackActionCancel" onClick={onClose}>
          Отмена
        </button>
      </div>
    </div>
  );
}
