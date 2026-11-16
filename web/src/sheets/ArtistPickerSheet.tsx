import { useEffect, useState } from 'react';
import {
  extractValidArtists,
  fetchArtistsByIds,
  fetchHydratedArtistRefs,
  type ResolvedArtist,
} from '../lib/artistResolver';
import { normalizeCoverUrl } from '../lib/coverUrl';
import './ArtistPickerSheet.css';

export type ArtistPickerState = {
  subtitle: string;
  artistLine?: string;
  artists: ResolvedArtist[];
};

type Props = {
  picker: ArtistPickerState | null;
  onClose: () => void;
  onSelect: (artist: ResolvedArtist) => void;
};

function PickerAvatar({ url, name }: { url: string | null | undefined; name: string }) {
  const src = normalizeCoverUrl(url, '200x200');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  const initial = (name || '').trim().charAt(0).toUpperCase() || '♪';

  return (
    <span className="artist-picker-avatar" aria-hidden="true">
      {src && !failed ? (
        <img src={src} alt="" onError={() => setFailed(true)} />
      ) : (
        <span className="artist-picker-initial">{initial}</span>
      )}
    </span>
  );
}

export function ArtistPickerSheet({ picker, onClose, onSelect }: Props) {
  const open = Boolean(picker && picker.artists.length > 0);
  const [hydratedCovers, setHydratedCovers] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!picker || picker.artists.length === 0) return;
    const missingIds = picker.artists
      .filter((item) => !item.cover_url && !hydratedCovers[item.id])
      .map((item) => item.id);
    if (missingIds.length === 0) return;

    let cancelled = false;
    void (async () => {
      const byIds = await fetchArtistsByIds(missingIds);
      if (cancelled) return;
      const foundMap: Record<number, string> = {};
      for (const item of byIds) {
        if (item.id != null && item.cover_url) {
          foundMap[item.id] = item.cover_url;
        }
      }
      const stillMissing = missingIds.some((id) => !foundMap[id]);
      if (stillMissing) {
        const title = (picker.subtitle || '').trim();
        const artistLine = (picker.artistLine || picker.artists.map((a) => a.name).join(', ')).trim();
        if (title || artistLine) {
          const refs = await fetchHydratedArtistRefs({ title, artist: artistLine });
          if (cancelled) return;
          for (const item of extractValidArtists(refs)) {
            if (item.cover_url && !foundMap[item.id]) {
              foundMap[item.id] = item.cover_url;
            }
          }
        }
      }
      if (Object.keys(foundMap).length > 0 && !cancelled) {
        setHydratedCovers((prev) => ({ ...prev, ...foundMap }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [picker]);

  return (
    <div
      className={open ? 'artist-picker-sheet open' : 'artist-picker-sheet'}
      id="artistPickerSheet"
      aria-hidden={!open}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="artist-picker-panel" role="dialog" aria-labelledby="artistPickerTitle">
        <div className="artist-picker-head">
          <div className="title" id="artistPickerTitle">Выберите исполнителя</div>
          {picker?.subtitle ? <div className="subtitle">{picker.subtitle}</div> : null}
        </div>
        <ul className="artist-picker-list" id="artistPickerList">
          {(picker?.artists ?? []).map((artist) => {
            const coverUrl = artist.cover_url || hydratedCovers[artist.id] || null;
            return (
              <li key={artist.id}>
                <button
                  type="button"
                  onClick={() => onSelect(artist)}
                >
                  <PickerAvatar url={coverUrl} name={artist.name} />
                  <span className="artist-picker-name">{artist.name}</span>
                  <span className="artist-picker-chev" aria-hidden="true">›</span>
                </button>
              </li>
            );
          })}
        </ul>
        <button type="button" className="artist-picker-cancel" id="artistPickerCancel" onClick={onClose}>
          Отмена
        </button>
      </div>
    </div>
  );
}
