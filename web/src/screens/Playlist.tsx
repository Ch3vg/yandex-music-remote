import { useEffect, useState } from 'react';
import type { CatalogTrack, PlayContext, PlaylistResponse } from '../api/types';
import { fetchJson } from '../api/http';
import { send } from '../api/ws';
import { TrackRow } from '../components/TrackRow';
import { WaveBanner } from '../components/WaveBanner';
import { useWorkPending } from '../store/busy';
import './Playlist.css';

export type PlaylistRequest = {
  kind: number;
  title: string;
  nonce: number;
};

type Props = {
  active: boolean;
  request: PlaylistRequest | null;
  onBack: () => void;
  onPlay: (track: CatalogTrack) => void;
  onMenu: (track: CatalogTrack) => void;
  onContext: (context: PlayContext | null) => void;
};

function indexed(tracks: CatalogTrack[], track: CatalogTrack): CatalogTrack {
  const index = tracks.findIndex((item) => Number(item.id) === Number(track.id));
  if (index < 0) return { ...track, playlist_index: undefined };
  return { ...track, playlist_index: index };
}

export function Playlist({ active, request, onBack, onPlay, onMenu, onContext }: Props) {
  const waveBusy = useWorkPending();
  const [title, setTitle] = useState(request?.title || 'Плейлист');
  const [filter, setFilter] = useState('');
  const [tracks, setTracks] = useState<CatalogTrack[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [error, setError] = useState('');
  const [playlistUuid, setPlaylistUuid] = useState<string | null>(null);
  const [playlistUid, setPlaylistUid] = useState<number | null>(null);
  const [playlistKind, setPlaylistKind] = useState<number | null>(null);

  useEffect(() => {
    setFilter('');
    if (!request) return;
    let cancel = false;
    setTitle(request.title || 'Плейлист');
    setStatus('loading');
    setTracks([]);
    fetchJson<PlaylistResponse>(`/api/library/playlist/${request.kind}`, 'Не удалось загрузить плейлист')
      .then((body) => {
        if (cancel) return;
        const list = body.tracks || [];
        setTracks(list);
        setTitle(body.title || request.title || 'Плейлист');
        setPlaylistUuid(body.playlist_uuid || null);
        setPlaylistUid(body.uid ?? null);
        setPlaylistKind(body.kind ?? request.kind);
        onContext(
          body.playlist_uuid
            ? {
                playlist_kind: request.kind,
                playlist_uid: body.uid ?? null,
                playlist_uuid: body.playlist_uuid,
              }
            : null,
        );
        setStatus('ready');
      })
      .catch((reason: unknown) => {
        if (cancel) return;
        setError(reason instanceof Error ? reason.message : 'Не удалось загрузить плейлист');
        onContext(null);
        setStatus('error');
      });
    return () => {
      cancel = true;
    };
  }, [request, onContext]);

  const query = filter.trim().toLowerCase();
  const visible = query
    ? tracks.filter((track) => `${track.title} ${track.artist}`.toLowerCase().includes(query))
    : tracks;

  return (
    <section className={active ? 'screen active' : 'screen'} id="screenPlaylist">
      <div className="playlist-header">
        <button type="button" className="nav-btn" id="btnPlaylistBack" aria-label="Назад" onClick={onBack}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <h1 id="playlistScreenTitle">{title}</h1>
        <span className="header-balance" />
      </div>
      <div className="playlist-search">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.45">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3-3" />
        </svg>
        <input
          type="search"
          id="playlistFilter"
          placeholder="Поиск в плейлисте"
          autoComplete="off"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
      </div>
      {playlistUuid ? (
        <div className="playlist-wave">
          <WaveBanner
            id="btnPlaylistWave"
            kicker="Моя волна по плейлисту"
            title={title}
            tone="playlist"
            disabled={waveBusy}
            onClick={() => {
              const command: {
                command: 'start_wave';
                source: 'playlist';
                playlist_uuid: string;
                playlist_kind?: number;
                playlist_uid?: number;
              } = {
                command: 'start_wave',
                source: 'playlist',
                playlist_uuid: playlistUuid,
              };
              if (playlistKind && playlistKind > 0) command.playlist_kind = playlistKind;
              if (playlistUid && playlistUid > 0) command.playlist_uid = playlistUid;
              send(command);
            }}
          />
        </div>
      ) : null}
      <ul className="track-list" id="playlistTracks">
        {status === 'loading' ? <li className="list-meta">Загрузка…</li> : null}
        {status === 'error' ? <li className="list-meta">{error}</li> : null}
        {status === 'ready' && visible.length === 0 ? <li className="list-meta">Ничего не найдено</li> : null}
        {status === 'ready'
          ? visible.map((track) => {
              const row = indexed(tracks, track);
              return (
                <TrackRow
                  key={`${row.id}-${row.playlist_index ?? 'x'}`}
                  track={row}
                  variant="list"
                  onPlay={onPlay}
                  onMenu={onMenu}
                />
              );
            })
          : null}
      </ul>
    </section>
  );
}
