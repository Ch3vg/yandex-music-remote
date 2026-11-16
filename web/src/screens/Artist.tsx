import { type CSSProperties, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { fetchJson } from '../api/http';
import type { AlbumCard, ArtistDetail, CatalogTrack, PlayContext } from '../api/types';
import { send } from '../api/ws';
import type { ArtistTracksMode } from '../app/screen';
import { TrackRow } from '../components/TrackRow';
import { normalizeCoverUrl } from '../lib/coverUrl';
import {
  DEFAULT_ARTIST_AMBIENT_RGB,
  formatRgbTriplet,
  normalizeArtistAmbientHex,
  sampleBottomEdgeColor,
} from '../lib/palette';
import { formatTrackCount } from '../lib/trackCount';
import './Artist.css';

export type ArtistRouteRequest = {
  artistId: number;
  initialName?: string;
  nonce: number;
};

type Props = {
  active: boolean;
  request: ArtistRouteRequest | null;
  onBack: () => void;
  onOpenTracks: (artistId: number, artistName: string, mode: ArtistTracksMode) => void;
  onOpenAlbum: (albumId: number, title: string) => void;
  onPlay: (track: CatalogTrack, context: PlayContext) => void;
  onMenu: (track: CatalogTrack, context: PlayContext) => void;
};

const artistCache = new Map<number, ArtistDetail>();
const scrollPositions = new Map<string, number>();
const heroAmbientCache = new Map<string, [number, number, number]>();

function HeroPhoto({
  url,
  skipSample,
  onAmbient,
}: {
  url: string | null;
  skipSample: boolean;
  onAmbient: (rgb: [number, number, number]) => void;
}) {
  const src = normalizeCoverUrl(url, '1000x1000');
  const [useCors, setUseCors] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setUseCors(true);
    setFailed(false);
    if (skipSample) return;
    if (!src) {
      onAmbient(DEFAULT_ARTIST_AMBIENT_RGB);
      return;
    }
    const cached = heroAmbientCache.get(src);
    if (cached) {
      onAmbient(cached);
    }
  }, [src, skipSample, onAmbient]);

  if (!src || failed) {
    return (
      <div className="artist-hero-fallback" aria-hidden="true">
        <span>♪</span>
      </div>
    );
  }

  return (
    <img
      className="artist-hero-img"
      src={src}
      alt=""
      crossOrigin={!skipSample && useCors ? 'anonymous' : undefined}
      onLoad={(event) => {
        if (skipSample || !useCors) return;
        const cached = heroAmbientCache.get(src);
        if (cached) {
          onAmbient(cached);
          return;
        }
        const sampled = sampleBottomEdgeColor(event.currentTarget);
        heroAmbientCache.set(src, sampled);
        onAmbient(sampled);
      }}
      onError={() => {
        if (!skipSample && useCors) {
          setUseCors(false);
          onAmbient(DEFAULT_ARTIST_AMBIENT_RGB);
        } else {
          setFailed(true);
          if (!skipSample) onAmbient(DEFAULT_ARTIST_AMBIENT_RGB);
        }
      }}
    />
  );
}

function AlbumCover({ url }: { url: string | null }) {
  const src = normalizeCoverUrl(url, '400x400');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  return (
    <div className="album-card-cover">
      {src && !failed ? (
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} />
      ) : (
        <span className="album-card-ph" aria-hidden="true">♪</span>
      )}
    </div>
  );
}

function FamiliarBadge() {
  return (
    <div className="artist-familiar-badge" aria-hidden="true">
      <svg width="56" height="56" viewBox="0 0 56 56" fill="none">
        <rect width="56" height="56" rx="12" fill="#2b1216" />
        <rect x="8" y="8" width="23" height="23" rx="5" fill="#f48fb1" />
        <rect
          x="14.5"
          y="14.5"
          width="24"
          height="24"
          rx="5.2"
          fill="rgba(255, 198, 208, 0.38)"
          stroke="rgba(255, 220, 226, 0.34)"
          strokeWidth="1"
        />
        <rect x="21" y="21" width="27" height="27" rx="5.8" fill="#ff6e63" />
      </svg>
    </div>
  );
}

function AlbumCarouselSection({
  heading,
  items,
  fallbackArtist,
  onOpenAlbum,
}: {
  heading: string;
  items: AlbumCard[];
  fallbackArtist: string;
  onOpenAlbum: (albumId: number, title: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="artist-albums-block">
      <div className="artist-section-static">
        <h2>{heading}</h2>
      </div>
      <div className="album-carousel">
        {items.map((album) => {
          const artistLabel = (album.artist || fallbackArtist).trim();
          const subtitle = album.year
            ? artistLabel
              ? `${artistLabel} · ${album.year}`
              : String(album.year)
            : artistLabel;
          return (
            <button
              key={album.id}
              type="button"
              className="album-card"
              onClick={() => onOpenAlbum(album.id, album.title)}
            >
              <AlbumCover url={album.cover_url_hq || album.cover_url} />
              <div className="album-card-title">{album.title}</div>
              {subtitle ? <div className="album-card-subtitle">{subtitle}</div> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Artist({
  active,
  request,
  onBack,
  onOpenTracks,
  onOpenAlbum,
  onPlay,
  onMenu,
}: Props) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [detail, setDetail] = useState<ArtistDetail | null>(null);
  const [error, setError] = useState('');
  const [retrySeq, setRetrySeq] = useState(0);
  const [scrolled, setScrolled] = useState(false);
  const [ambientRgb, setAmbientRgb] = useState<[number, number, number]>(DEFAULT_ARTIST_AMBIENT_RGB);
  const scrollRef = useRef<HTMLDivElement>(null);

  const routeKey = request ? `${request.artistId}:${request.nonce}` : '';
  const heroSrc = detail ? normalizeCoverUrl(detail.cover_url_hq || detail.cover_url, '1000x1000') : null;
  const apiAmbient = detail ? normalizeArtistAmbientHex(detail.ambient_color) : null;

  useEffect(() => {
    if (apiAmbient) {
      setAmbientRgb(apiAmbient);
      return;
    }
    if (!heroSrc) {
      setAmbientRgb(DEFAULT_ARTIST_AMBIENT_RGB);
      return;
    }
    setAmbientRgb(heroAmbientCache.get(heroSrc) ?? DEFAULT_ARTIST_AMBIENT_RGB);
  }, [heroSrc, detail?.ambient_color]);

  useEffect(() => {
    if (!request) return;
    const cached = retrySeq === 0 ? artistCache.get(request.artistId) : undefined;
    if (cached) {
      setDetail(cached);
      setStatus('ready');
      setError('');
      return;
    }

    let cancel = false;
    setStatus('loading');
    setDetail(null);
    setError('');

    fetchJson<ArtistDetail>(
      `/api/library/artist/${request.artistId}`,
      'Не удалось загрузить страницу исполнителя',
    )
      .then((body) => {
        if (cancel) return;
        artistCache.set(request.artistId, body);
        setDetail(body);
        setStatus('ready');
      })
      .catch((reason: unknown) => {
        if (cancel) return;
        setError(reason instanceof Error ? reason.message : 'Не удалось загрузить страницу исполнителя');
        setStatus('error');
      });

    return () => {
      cancel = true;
    };
  }, [request?.artistId, request?.nonce, retrySeq]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!active || !el || !routeKey) return;
    if (status === 'ready' && detail && detail.id !== request?.artistId) return;
    const saved = scrollPositions.get(routeKey) ?? 0;
    el.scrollTop = saved;
    setScrolled(saved > 220);
  }, [active, routeKey, status, detail?.id, request?.artistId]);

  const displayName = detail?.name || request?.initialName || 'Исполнитель';
  const artistId = detail?.id ?? request?.artistId ?? 0;

  const popularContext: PlayContext = {
    artist_id: artistId,
    artist_mode: 'popular',
  };

  const popularTracks = (detail?.popular_tracks ?? []).slice(0, 12).map((track, index) => ({
    ...track,
    playlist_index: track.playlist_index ?? index,
  }));

  const popularSlides: CatalogTrack[][] = [];
  for (let i = 0; i < popularTracks.length; i += 3) {
    popularSlides.push(popularTracks.slice(i, i + 3));
  }

  const showSolidTopbar = scrolled || status === 'error';
  const effectiveAmbient =
    apiAmbient ?? (heroSrc ? (heroAmbientCache.get(heroSrc) ?? ambientRgb) : DEFAULT_ARTIST_AMBIENT_RGB);
  const stageStyle = {
    '--artist-ambient-rgb': formatRgbTriplet(effectiveAmbient),
  } as CSSProperties;

  return (
    <section className={active ? 'screen active' : 'screen'} id="screenArtist">
      <div
        className="artist-scroll"
        id="artistScroll"
        ref={scrollRef}
        onScroll={(event) => {
          const top = event.currentTarget.scrollTop;
          if (routeKey && (!detail || detail.id === request?.artistId)) {
            scrollPositions.set(routeKey, top);
          }
          const nextScrolled = top > 220;
          if (nextScrolled !== scrolled) setScrolled(nextScrolled);
        }}
      >
        <div className={showSolidTopbar ? 'artist-topbar scrolled' : 'artist-topbar'} id="artistTopbar">
          <button type="button" className="nav-btn artist-back-btn" id="btnArtistBack" aria-label="Назад" onClick={onBack}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" />
              <path d="M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="artist-topbar-title" id="artistTopbarTitle">{displayName}</div>
        </div>

        {status === 'loading' ? (
          <div
            className="artist-stage artist-state-wrap"
            style={{ '--artist-ambient-rgb': formatRgbTriplet(DEFAULT_ARTIST_AMBIENT_RGB) } as CSSProperties}
          >
            <div className="artist-hero artist-hero--skeleton">
              <div className="artist-hero-top-scrim" aria-hidden="true" />
              <div className="artist-hero-gradient" aria-hidden="true" />
              <h1 className="artist-hero-name">{displayName}</h1>
            </div>
            <div className="artist-ambient-tail" aria-hidden="true" />
            <div className="artist-content">
              <p className="list-meta">Загрузка…</p>
            </div>
          </div>
        ) : null}

        {status === 'error' ? (
          <div className="artist-error-box">
            <p className="list-meta">{error}</p>
            <button
              type="button"
              className="artist-retry-btn"
              onClick={() => setRetrySeq((n) => n + 1)}
            >
              Повторить
            </button>
          </div>
        ) : null}

        {status === 'ready' && detail ? (
          <div className="artist-stage" style={stageStyle}>
            <div className="artist-hero" id="artistHero">
              <HeroPhoto
                url={detail.cover_url_hq || detail.cover_url}
                skipSample={apiAmbient != null}
                onAmbient={setAmbientRgb}
              />
              <div className="artist-hero-top-scrim" aria-hidden="true" />
              <div className="artist-hero-gradient" aria-hidden="true" />
              <h1 className="artist-hero-name" id="artistHeroName">{detail.name}</h1>
            </div>

            <div className="artist-ambient-tail" aria-hidden="true" />

            <div className="artist-content">
              <div className="artist-actions">
                <button
                  type="button"
                  className="artist-play-action"
                  id="btnPlayArtist"
                  onClick={() => {
                    if (artistId > 0) send({ command: 'play_artist', artist_id: artistId });
                  }}
                >
                  <span className="artist-play-circle" aria-hidden="true">
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
                  <span className="artist-play-caption">Слушать</span>
                </button>
              </div>

              {popularSlides.length > 0 ? (
                <div className="artist-popular-block">
                  <button
                    type="button"
                    className="artist-section-link"
                    id="btnArtistAllTracks"
                    onClick={() => onOpenTracks(detail.id, detail.name, 'all')}
                  >
                    <span>Популярные треки</span>
                    <span className="chev" aria-hidden="true">›</span>
                  </button>
                  <div className="likes-carousel artist-popular-carousel" id="artistPopularCarousel">
                    {popularSlides.map((slide, slideIdx) => (
                      <div className="likes-slide" key={slideIdx}>
                        {slide.map((track) => (
                          <TrackRow
                            key={`${track.id}-${track.playlist_index ?? 0}`}
                            track={track}
                            variant="likes"
                            onPlay={(item) => onPlay(item, popularContext)}
                            onMenu={(item) => onMenu(item, popularContext)}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {detail.familiar_total > 0 ? (
                <button
                  type="button"
                  className="artist-familiar-row"
                  id="btnArtistFamiliar"
                  onClick={() => onOpenTracks(detail.id, detail.name, 'familiar')}
                >
                  <FamiliarBadge />
                  <div className="artist-familiar-meta">
                    <div className="artist-familiar-title">
                      <span>Знакомое вам</span>
                      <span className="chev" aria-hidden="true">›</span>
                    </div>
                    <div className="artist-familiar-count">{formatTrackCount(detail.familiar_total)}</div>
                  </div>
                </button>
              ) : null}

              <AlbumCarouselSection
                heading="Альбомы"
                items={detail.albums}
                fallbackArtist={detail.name}
                onOpenAlbum={onOpenAlbum}
              />

              <AlbumCarouselSection
                heading="Синглы и EP"
                items={detail.singles}
                fallbackArtist={detail.name}
                onOpenAlbum={onOpenAlbum}
              />
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
