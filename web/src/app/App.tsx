import { useCallback, useEffect, useRef, useState } from 'react';
import type { CatalogTrack, PlayContext, PlayMode } from '../api/types';
import { buildPlayCommand } from '../api/play';
import { connectWs, disconnectWs, send } from '../api/ws';
import { MiniPlayer } from '../chrome/MiniPlayer';
import { TabBar } from '../chrome/TabBar';
import { Toasts } from '../chrome/Toasts';
import { Home } from '../screens/Home';
import { Player } from '../screens/Player';
import { Playlist, type PlaylistRequest } from '../screens/Playlist';
import { More } from '../screens/More';
import { Search } from '../screens/Search';
import { Volume } from '../screens/Volume';
import type { PlayerPhase, RememberedScreen, ScreenName } from './screen';
import { QueueSheet } from '../sheets/QueueSheet';
import { QrSheet } from '../sheets/QrSheet';
import { TrackActions } from '../sheets/TrackActions';
import { pushToast, usePlaybackSelector } from '../store/playback';
import { Busy } from '../chrome/Busy';
import { startShade } from '../lib/shade';

export function App() {
  const connected = usePlaybackSelector((view) => view.connected);
  const statusTitle = usePlaybackSelector((view) => view.statusTitle);
  const hasTrack = usePlaybackSelector((view) => view.hasTrack);
  const [screen, setScreen] = useState<ScreenName>('home');
  const [phase, setPhase] = useState<PlayerPhase>('closed');
  const [slideIn, setSlideIn] = useState(false);
  const [searchFromHome, setSearchFromHome] = useState(false);
  const [playlistReq, setPlaylistReq] = useState<PlaylistRequest | null>(null);
  const [actions, setActions] = useState<CatalogTrack | null>(null);
  const [qrOpen, setQrOpen] = useState(false);
  const [queueOpen, setQueueOpen] = useState(false);
  const phaseRef = useRef<PlayerPhase>('closed');
  const screenRef = useRef<ScreenName>('home');
  const searchFromHomeRef = useRef(false);
  const lastMain = useRef<RememberedScreen>('home');
  const likesRef = useRef<PlayContext | null>(null);
  const playlistRef = useRef<PlayContext | null>(null);
  phaseRef.current = phase;
  screenRef.current = screen;

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
      setScreen(lastMain.current);
    }, 320);
  }, []);

  const openPlayer = useCallback(() => {
    if (phaseRef.current !== 'closed') return;
    setQueueOpen(false);
    setActions(null);
    phaseRef.current = 'open';
    setPhase('open');
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => setSlideIn(true));
    });
  }, []);

  const go = useCallback((name: ScreenName, fromHome?: boolean) => {
    const searchHome = fromHome ?? searchFromHomeRef.current;
    if (fromHome !== undefined) {
      searchFromHomeRef.current = fromHome;
      setSearchFromHome(fromHome);
    }
    if (phaseRef.current === 'open') {
      closePlayer();
      return;
    }
    setQueueOpen(false);
    setActions(null);
    setQrOpen(false);
    setScreen(name);
    if (name !== 'volume' && !(name === 'search' && searchHome)) {
      if (name === 'home' || name === 'playlist' || name === 'search' || name === 'more') {
        lastMain.current = name;
      }
    }
  }, [closePlayer]);

  const play = useCallback((track: CatalogTrack, mode: PlayMode) => {
    const where = screenRef.current;
    const context = where === 'home' ? likesRef.current : where === 'playlist' ? playlistRef.current : null;
    const command = buildPlayCommand(mode, track, context);
    if (!command) {
      pushToast('Не удалось выполнить действие с треком', 'error');
      setActions(null);
      return;
    }
    send(command);
    setActions(null);
  }, []);

  useEffect(() => {
    const playerOpen = phase !== 'closed';
    const hideChrome = playerOpen || screen === 'home' || screen === 'playlist' || (screen === 'search' && searchFromHome);
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
          onSearch={() => go('search', true)}
          onOpenPlaylist={(kind, title) => {
            setPlaylistReq({ kind, title, nonce: Date.now() });
            go('playlist');
          }}
          onPlay={(track) => play(track, 'now')}
          onMenu={setActions}
          onLikesContext={onLikesContext}
        />
        <Playlist
          active={screen === 'playlist'}
          request={playlistReq}
          onBack={() => go('home')}
          onPlay={(track) => play(track, 'now')}
          onMenu={setActions}
          onContext={onPlaylistContext}
        />
        <Search
          active={screen === 'search'}
          fromHome={searchFromHome}
          onBack={() => go('home', false)}
          onPlay={(track) => play(track, 'now')}
          onMenu={setActions}
        />
        <Player phase={phase} onClose={closePlayer} onQueue={() => setQueueOpen(true)} />
        <Volume active={screen === 'volume'} />
        <More active={screen === 'more'} />
      </div>
      <MiniPlayer onOpen={openPlayer} />
      <TabBar
        screen={screen}
        playerOpen={phase !== 'closed'}
        onSearch={() => go('search', false)}
        onVolume={() => go('volume')}
        onMore={() => go('more')}
      />
      <QrSheet open={qrOpen} onClose={() => setQrOpen(false)} />
      <TrackActions track={actions} onClose={() => setActions(null)} onAction={play} />
      <QueueSheet open={queueOpen} onClose={() => setQueueOpen(false)} />
    </>
  );
}
