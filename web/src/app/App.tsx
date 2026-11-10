import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { buildPlayCommand } from '../api/play';
import type { ArtistRef, CatalogTrack, PlayContext, PlayMode } from '../api/types';
import { connectWs, disconnectWs, send } from '../api/ws';
import { Busy } from '../chrome/Busy';
import { MiniPlayer } from '../chrome/MiniPlayer';
import { TabBar } from '../chrome/TabBar';
import { Toasts } from '../chrome/Toasts';
import {
  type ArtistChipItem,
  resolveArtistChipClick,
  resolveArtistsForPlayer,
  resolveArtistsForTrack,
  type ResolvedArtist,
} from '../lib/artistResolver';
import { startShade } from '../lib/shade';
import { Album, type AlbumRouteRequest } from '../screens/Album';
import { Artist, type ArtistRouteRequest } from '../screens/Artist';
import { ArtistTracks, type ArtistTracksRouteRequest } from '../screens/ArtistTracks';
import { Home } from '../screens/Home';
import { More } from '../screens/More';
import { Player } from '../screens/Player';
import { Playlist, type PlaylistRequest } from '../screens/Playlist';
import { Search } from '../screens/Search';
import { Volume } from '../screens/Volume';
import { ArtistPickerSheet, type ArtistPickerState } from '../sheets/ArtistPickerSheet';
import { QrSheet } from '../sheets/QrSheet';
import { QueueSheet } from '../sheets/QueueSheet';
import { TrackActions } from '../sheets/TrackActions';
import { getSnapshot, pushToast, usePlaybackSelector } from '../store/playback';
import type { ArtistTracksMode, PlayerPhase, RouteEntry } from './screen';

type ActionsState = {
  track: CatalogTrack;
  context: PlayContext | null;
};

function findLastRoute<K extends RouteEntry['screen']>(
  stack: RouteEntry[],
  kind: K,
): Extract<RouteEntry, { screen: K }> | null {
  for (let i = stack.length - 1; i >= 0; i -= 1) {
    const entry = stack[i];
    if (entry.screen === kind) {
      return entry as Extract<RouteEntry, { screen: K }>;
    }
  }
  return null;
}

export function App() {
  const connected = usePlaybackSelector((view) => view.connected);
  const statusTitle = usePlaybackSelector((view) => view.statusTitle);
  const hasTrack = usePlaybackSelector((view) => view.hasTrack);

  const [navStack, setNavStack] = useState<RouteEntry[]>([{ screen: 'home' }]);
  const [phase, setPhase] = useState<PlayerPhase>('closed');
  const [slideIn, setSlideIn] = useState(false);
  const [actionsState, setActionsState] = useState<ActionsState | null>(null);
  const [picker, setPicker] = useState<ArtistPickerState | null>(null);
  const [qrOpen, setQrOpen] = useState(false);
  const [queueOpen, setQueueOpen] = useState(false);

  const phaseRef = useRef<PlayerPhase>('closed');
  const likesRef = useRef<PlayContext | null>(null);
  const playlistRef = useRef<PlayContext | null>(null);
  const windowScrollMap = useRef<Map<number, number>>(new Map());
  const resolveTokenRef = useRef(0);

  phaseRef.current = phase;

  const currentRoute = navStack[navStack.length - 1] ?? { screen: 'home' };
  const screen = currentRoute.screen;

  const lastPlaylist = findLastRoute(navStack, 'playlist');
  const lastSearch = findLastRoute(navStack, 'search');
  const lastArtist = findLastRoute(navStack, 'artist');
  const lastArtistTracks = findLastRoute(navStack, 'artistTracks');
  const lastAlbum = findLastRoute(navStack, 'album');

  const searchFromHome = currentRoute.screen === 'search'
    ? currentRoute.fromHome
    : (lastSearch?.fromHome ?? false);

  const playlistReq = useMemo<PlaylistRequest | null>(
    () =>
      lastPlaylist
        ? { kind: lastPlaylist.kind, title: lastPlaylist.title, nonce: lastPlaylist.nonce }
        : null,
    [lastPlaylist?.kind, lastPlaylist?.title, lastPlaylist?.nonce],
  );

  const artistReq = useMemo<ArtistRouteRequest | null>(
    () =>
      lastArtist
        ? { artistId: lastArtist.artistId, initialName: lastArtist.initialName, nonce: lastArtist.nonce }
        : null,
    [lastArtist?.artistId, lastArtist?.initialName, lastArtist?.nonce],
  );

  const artistTracksReq = useMemo<ArtistTracksRouteRequest | null>(
    () =>
      lastArtistTracks
        ? {
            artistId: lastArtistTracks.artistId,
            artistName: lastArtistTracks.artistName,
            mode: lastArtistTracks.mode,
            nonce: lastArtistTracks.nonce,
          }
        : null,
    [lastArtistTracks?.artistId, lastArtistTracks?.artistName, lastArtistTracks?.mode, lastArtistTracks?.nonce],
  );

  const albumReq = useMemo<AlbumRouteRequest | null>(
    () =>
      lastAlbum
        ? { albumId: lastAlbum.albumId, initialTitle: lastAlbum.initialTitle, nonce: lastAlbum.nonce }
        : null,
    [lastAlbum?.albumId, lastAlbum?.initialTitle, lastAlbum?.nonce],
  );

  const onLikesContext = useCallback((context: PlayContext | null) => {
    likesRef.current = context;
  }, []);
  const onPlaylistContext = useCallback((context: PlayContext | null) => {
    playlistRef.current = context;
  }, []);

  const closePlayer = useCallback(() => {
    if (phaseRef.current !== 'open') return;
    setSlideIn(false);
    setQueueOpen(false);
    phaseRef.current = 'closing';
    setPhase('closing');
    window.setTimeout(() => {
      phaseRef.current = 'closed';
      setPhase('closed');
    }, 320);
  }, []);

  const openPlayer = useCallback(() => {
    if (phaseRef.current !== 'closed') return;
    setQueueOpen(false);
    setActionsState(null);
    setPicker(null);
    phaseRef.current = 'open';
    setPhase('open');
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => setSlideIn(true));
    });
  }, []);

  const pushRoute = useCallback((entry: RouteEntry) => {
    setQueueOpen(false);
    setActionsState(null);
    setPicker(null);
    setQrOpen(false);
    setNavStack((prev) => {
      windowScrollMap.current.set(prev.length - 1, window.scrollY);
      return [...prev, entry];
    });
  }, []);

  const popRoute = useCallback(() => {
    setQueueOpen(false);
    setActionsState(null);
    setPicker(null);
    setQrOpen(false);
    setNavStack((prev) => {
      if (prev.length <= 1) return [{ screen: 'home' }];
      return prev.slice(0, -1);
    });
  }, []);

  const selectTab = useCallback(
    (entry: RouteEntry) => {
      if (phaseRef.current === 'open') {
        closePlayer();
        return;
      }
      setQueueOpen(false);
      setActionsState(null);
      setPicker(null);
      setQrOpen(false);
      windowScrollMap.current.clear();
      setNavStack([entry]);
    },
    [closePlayer],
  );

  const navigateToArtist = useCallback(
    (artistId: number, initialName?: string) => {
      setActionsState(null);
      setPicker(null);
      setQueueOpen(false);
      setQrOpen(false);
      setNavStack((prev) => {
        const top = prev[prev.length - 1];
        if (top && top.screen === 'artist' && top.artistId === artistId) {
          return prev;
        }
        windowScrollMap.current.set(prev.length - 1, window.scrollY);
        return [
          ...prev,
          {
            screen: 'artist',
            artistId,
            initialName,
            nonce: Date.now(),
          },
        ];
      });
      if (phaseRef.current === 'open') {
        closePlayer();
      }
    },
    [closePlayer],
  );

  const openArtistTracks = useCallback(
    (artistId: number, artistName: string, mode: ArtistTracksMode) => {
      pushRoute({
        screen: 'artistTracks',
        artistId,
        artistName,
        mode,
        nonce: Date.now(),
      });
    },
    [pushRoute],
  );

  const openAlbum = useCallback(
    (albumId: number, initialTitle?: string) => {
      setActionsState(null);
      setPicker(null);
      setQueueOpen(false);
      setQrOpen(false);
      setNavStack((prev) => {
        const top = prev[prev.length - 1];
        if (top && top.screen === 'album' && top.albumId === albumId) {
          return prev;
        }
        windowScrollMap.current.set(prev.length - 1, window.scrollY);
        return [
          ...prev,
          {
            screen: 'album',
            albumId,
            initialTitle,
            nonce: Date.now(),
          },
        ];
      });
    },
    [],
  );

  const openResolvedArtists = useCallback(
    (resolved: ResolvedArtist[], subtitle: string, artistLine: string, onEmpty: () => void) => {
      if (resolved.length === 1) {
        navigateToArtist(resolved[0].id, resolved[0].name);
        return;
      }
      if (resolved.length > 1) {
        setPicker({ subtitle, artistLine, artists: resolved });
        return;
      }
      onEmpty();
    },
    [navigateToArtist],
  );

  const openArtistFromSource = useCallback(
    (options: {
      artists?: ArtistRef[];
      trackId?: number | null;
      title?: string;
      artist?: string;
    }) => {
      const token = ++resolveTokenRef.current;
      void resolveArtistsForTrack(options).then((resolved) => {
        if (token !== resolveTokenRef.current) return;
        openResolvedArtists(resolved, options.title || '', options.artist || '', () => {
          pushToast('Исполнитель не найден', 'error');
        });
      });
    },
    [openResolvedArtists],
  );

  const handlePlayerArtistClick = useCallback(() => {
    const view = getSnapshot();
    const token = ++resolveTokenRef.current;
    void resolveArtistsForPlayer({
      artists: view.artists,
      artistHref: view.artistHref,
      title: view.title,
      artist: view.artist,
    }).then((resolved) => {
      if (token !== resolveTokenRef.current) return;
      const subtitle = view.title === '—' ? '' : view.title;
      const artistLine = view.artist === '—' ? '' : view.artist;
      openResolvedArtists(resolved, subtitle, artistLine, () => {
        send({ command: 'navigate', target: 'artist' });
      });
    });
  }, [openResolvedArtists]);

  const playWithContext = useCallback((track: CatalogTrack, mode: PlayMode, context: PlayContext | null) => {
    const command = buildPlayCommand(mode, track, context);
    if (!command) {
      pushToast('Не удалось выполнить действие с треком', 'error');
      setActionsState(null);
      return;
    }
    send(command);
    setActionsState(null);
  }, []);

  const openActions = useCallback((track: CatalogTrack, context: PlayContext | null) => {
    setActionsState({ track, context });
  }, []);

  const handleActionSelect = useCallback(
    (track: CatalogTrack, mode: PlayMode) => {
      playWithContext(track, mode, actionsState?.context ?? null);
    },
    [actionsState, playWithContext],
  );

  const handleTrackArtistSelect = useCallback(
    (chip: ArtistChipItem, track: CatalogTrack) => {
      setActionsState(null);
      if (chip.id != null && chip.id > 0) {
        navigateToArtist(chip.id, chip.name);
        return;
      }
      const token = ++resolveTokenRef.current;
      void resolveArtistChipClick(chip, track).then((resolved) => {
        if (token !== resolveTokenRef.current) return;
        if (resolved) {
          navigateToArtist(resolved.id, resolved.name);
          return;
        }
        pushToast('Исполнитель не найден', 'error');
      });
    },
    [navigateToArtist],
  );

  useEffect(() => {
    if (screen === 'search' || screen === 'more' || screen === 'volume') {
      const saved = windowScrollMap.current.get(navStack.length - 1) ?? 0;
      window.scrollTo(0, saved);
    } else {
      window.scrollTo(0, 0);
    }
  }, [navStack.length, screen]);

  useEffect(() => {
    const playerOpen = phase !== 'closed';
    const hideChrome =
      playerOpen
      || screen === 'home'
      || screen === 'playlist'
      || screen === 'artist'
      || screen === 'artistTracks'
      || screen === 'album'
      || (screen === 'search' && searchFromHome);
    document.body.classList.toggle('player-open', playerOpen);
    document.body.classList.toggle('player-slide-in', slideIn);
    document.body.classList.toggle('chrome-hidden', hideChrome);
    document.body.classList.toggle('mini-absent', !hasTrack);
  }, [phase, slideIn, screen, searchFromHome, hasTrack]);

  useEffect(() => {
    connectWs();
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
    const stopShade = startShade();
    return () => {
      stopShade();
      disconnectWs();
    };
  }, []);

  return (
    <>
      <Toasts />
      <Busy />
      <div className="app">
        <Home
          active={screen === 'home'}
          connected={connected}
          statusTitle={statusTitle}
          onQr={() => setQrOpen(true)}
          onSearch={() => pushRoute({ screen: 'search', fromHome: true })}
          onOpenPlaylist={(kind, title) => {
            pushRoute({ screen: 'playlist', kind, title, nonce: Date.now() });
          }}
          onPlay={(track) => playWithContext(track, 'now', likesRef.current)}
          onMenu={(track) => openActions(track, likesRef.current)}
          onLikesContext={onLikesContext}
        />
        <Playlist
          active={screen === 'playlist'}
          request={playlistReq}
          onBack={popRoute}
          onPlay={(track) => playWithContext(track, 'now', playlistRef.current)}
          onMenu={(track) => openActions(track, playlistRef.current)}
          onContext={onPlaylistContext}
        />
        <Search
          active={screen === 'search'}
          fromHome={searchFromHome}
          onBack={popRoute}
          onOpenArtist={(artistId, name) => navigateToArtist(artistId, name)}
          onPlay={(track) => playWithContext(track, 'now', null)}
          onMenu={(track) => openActions(track, null)}
        />
        <Artist
          active={screen === 'artist'}
          request={artistReq}
          onBack={popRoute}
          onOpenTracks={openArtistTracks}
          onOpenAlbum={openAlbum}
          onPlay={(track, context) => playWithContext(track, 'now', context)}
          onMenu={(track, context) => openActions(track, context)}
        />
        <ArtistTracks
          active={screen === 'artistTracks'}
          request={artistTracksReq}
          onBack={popRoute}
          onPlay={(track, context) => playWithContext(track, 'now', context)}
          onMenu={(track, context) => openActions(track, context)}
        />
        <Album
          active={screen === 'album'}
          request={albumReq}
          onBack={popRoute}
          onOpenArtist={openArtistFromSource}
          onPlay={(track, context) => playWithContext(track, 'now', context)}
          onMenu={(track, context) => openActions(track, context)}
        />
        <Player
          phase={phase}
          onClose={closePlayer}
          onQueue={() => setQueueOpen(true)}
          onArtist={handlePlayerArtistClick}
        />
        <Volume active={screen === 'volume'} />
        <More active={screen === 'more'} />
      </div>
      <MiniPlayer onOpen={openPlayer} />
      <TabBar
        screen={screen}
        playerOpen={phase !== 'closed'}
        onSearch={() => selectTab({ screen: 'search', fromHome: false })}
        onVolume={() => selectTab({ screen: 'volume' })}
        onMore={() => selectTab({ screen: 'more' })}
      />
      <QrSheet open={qrOpen} onClose={() => setQrOpen(false)} />
      <QueueSheet
        open={queueOpen}
        onClose={() => setQueueOpen(false)}
        onMenu={(track) => openActions(track, null)}
      />
      <TrackActions
        track={actionsState?.track ?? null}
        onClose={() => setActionsState(null)}
        onAction={handleActionSelect}
        onSelectArtist={handleTrackArtistSelect}
      />
      <ArtistPickerSheet
        picker={picker}
        onClose={() => setPicker(null)}
        onSelect={(artist) => navigateToArtist(artist.id, artist.name)}
      />
    </>
  );
}
