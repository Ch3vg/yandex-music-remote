import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { fetchJson } from '../api/http';
import type { AlbumDetail, ArtistRef, CatalogTrack, PlayContext } from '../api/types';
import { send } from '../api/ws';
import { TrackRow } from '../components/TrackRow';
import { normalizeCoverUrl } from '../lib/coverUrl';
import { formatTrackCount } from '../lib/trackCount';
import './Album.css';

export type AlbumRouteRequest = {
  albumId: number;
  initialTitle?: string;
  nonce: number;
};

type Props = {
  active: boolean;
  request: AlbumRouteRequest | null;
  onBack: () => void;
  onOpenArtist: (options: {
    artists?: ArtistRef[];
    trackId?: number | null;
    title?: string;
    artist?: string;
  }) => void;
  onPlay: (track: CatalogTrack, context: PlayContext) => void;
  onMenu: (track: CatalogTrack, context: PlayContext) => void;
};

const albumCache = new Map<number, AlbumDetail>();
const albumScrollPositions = new Map<string, number>();

function formatAlbumType(albumType: string | null): string {
  const raw = (albumType || '').toLowerCase();
  if (raw === 'single') return 'Сингл';
  if (raw === 'ep') return 'EP';
  if (raw === 'compilation') return 'Сборник';
  return 'Альбом';
}

function AlbumHeroArt({ url }: { url: string | null }) {
  const src = normalizeCoverUrl(url, '400x400');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  return (
    <div className="album-hero-cover">
      {src && !failed ? (
        <img src={src} alt="" onError={() => setFailed(true)} />
      ) : (
        <span className="album-hero-ph" aria-hidden="true">♪</span>
      )}
    </div>
  );
}

export function Album({ active, request, onBack, onOpenArtist, onPlay, onMenu }: Props) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [album, setAlbum] = useState<AlbumDetail | null>(null);
  const [error, setError] = useState('');
  const [retrySeq, setRetrySeq] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const routeKey = request ? `${request.albumId}:${request.nonce}` : '';

  useEffect(() => {
    if (!request) return;
    const cached = retrySeq === 0 ? albumCache.get(request.albumId) : undefined;
    if (cached) {
      setAlbum(cached);
      setStatus('ready');
      setError('');
      return;
    }

    let cancel = false;
    setStatus('loading');
    setAlbum(null);
    setError('');

    fetchJson<AlbumDetail>(`/api/library/album/${request.albumId}`, 'Не удалось загрузить альбом')
      .then((body) => {
        if (cancel) return;
        albumCache.set(request.albumId, body);
        setAlbum(body);
        setStatus('ready');
      })
      .catch((reason: unknown) => {
        if (cancel) return;
        setError(reason instanceof Error ? reason.message : 'Не удалось загрузить альбом');
        setStatus('error');
      });

    return () => {
      cancel = true;
    };
  }, [request?.albumId, request?.nonce, retrySeq]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!active || !el || !routeKey) return;
    if (status === 'ready' && album && album.id !== request?.albumId) return;
    el.scrollTop = albumScrollPositions.get(routeKey) ?? 0;
  }, [active, routeKey, status, album?.id, request?.albumId]);

  const albumId = album?.id ?? request?.albumId ?? 0;
  const context: PlayContext = { context_album_id: albumId };

  const tracks = (album?.tracks ?? []).map((track, idx) => ({
    ...track,
    playlist_index: track.playlist_index ?? idx,
  }));

  const artistLine = album
    ? album.artist || album.artists.map((a) => a.name).join(', ')
    : '';

  const trackCountText = album
    ? formatTrackCount(album.track_count || tracks.length)
    : '';

  const metaParts = album
    ? [formatAlbumType(album.album_type), album.year ? String(album.year) : '', trackCountText].filter(Boolean)
    : [];

  return (
    <section className={active ? 'screen active' : 'screen'} id="screenAlbum">
      <div className="album-topbar">
        <button type="button" className="nav-btn" id="btnAlbumBack" aria-label="Назад" onClick={onBack}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="album-topbar-title">{album?.title || request?.initialTitle || ''}</div>
      </div>

      <div
        className="album-scroll"
        id="albumScroll"
        ref={scrollRef}
        onScroll={(event) => {
          if (routeKey && (!album || album.id === request?.albumId)) {
            albumScrollPositions.set(routeKey, event.currentTarget.scrollTop);
          }
        }}
      >
        {status === 'loading' ? <p className="list-meta">Загрузка…</p> : null}

        {status === 'error' ? (
          <div className="album-error-box">
            <p className="list-meta">{error}</p>
            <button type="button" className="album-retry-btn" onClick={() => setRetrySeq((n) => n + 1)}>
              Повторить
            </button>
          </div>
        ) : null}

        {status === 'ready' && album ? (
          <>
            <div className="album-hero">
              <AlbumHeroArt url={album.cover_url_hq || album.cover_url} />
              <h1 className="album-title" id="albumTitle">{album.title}</h1>
              {album.version ? <div className="album-version">{album.version}</div> : null}
              {artistLine ? (
                <button
                  type="button"
                  className="album-artist-btn"
                  id="btnAlbumArtist"
                  onClick={() =>
                    onOpenArtist({
                      artists: album.artists,
                      trackId: album.artists.length > 1 ? null : (tracks[0]?.id ?? null),
                      title: album.artists.length > 1 ? '' : (tracks[0]?.title || album.title),
                      artist: artistLine,
                    })
                  }
                >
                  <span>{artistLine}</span>
                  <span className="chev" aria-hidden="true">›</span>
                </button>
              ) : null}
              {metaParts.length > 0 ? (
                <div className="album-meta">{metaParts.join(' · ')}</div>
              ) : null}
              <button
                type="button"
                className="album-play-btn"
                id="btnPlayAlbum"
                onClick={() => {
                  if (album.id > 0) send({ command: 'play_album', album_id: album.id });
                }}
              >
                <span className="album-play-circle" aria-hidden="true">
                  <svg
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    stroke="currentColor"
                    strokeWidth="2.6"
                    strokeLinejoin="round"
                  >
                    <path d="M7.4 5.4L18.8 12 7.4 18.6V5.4z" />
                  </svg>
                </span>
                <span className="album-play-caption">Слушать</span>
              </button>
            </div>

            <ul className="track-list" id="albumTracks">
              {tracks.length === 0 ? <li className="list-meta">Нет треков</li> : null}
              {tracks.map((track, idx) => (
                <TrackRow
                  key={`${track.id}-${track.playlist_index ?? idx}`}
                  track={track}
                  variant="list"
                  onPlay={(item) => onPlay(item, context)}
                  onMenu={(item) => onMenu(item, context)}
                />
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </section>
  );
}
