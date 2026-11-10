export type RepeatMode = 'off' | 'queue' | 'one';

export type CatalogTrack = {
  id: number;
  album_id: number | null;
  title: string;
  artist: string;
  cover_url: string | null;
  cover_url_hq?: string | null;
  playlist_index?: number;
};

export type PlaylistCard = {
  kind: number;
  uid: number | null;
  playlist_uuid: string | null;
  title: string;
  track_count: number;
  cover_url: string | null;
  is_likes?: boolean;
};

export type HomeLikes = {
  title: string;
  tracks: CatalogTrack[];
  kind: number;
  uid: number | null;
  playlist_uuid: string | null;
  track_count: number;
  cover_url: string | null;
};

export type HomeResponse = {
  likes: HomeLikes;
  playlists: PlaylistCard[];
};

export type PlaylistResponse = {
  kind: number;
  uid: number | null;
  playlist_uuid: string | null;
  title: string;
  tracks: CatalogTrack[];
};

export type NetworkInfo = {
  chosen: string;
  port: number;
  all: string[];
  url: string;
};

export type PlayContext = {
  playlist_kind: number;
  playlist_uid: number | null;
  playlist_uuid: string;
};

export type QueueItem = {
  title: string;
  artist: string;
  cover: string | null;
  track_id: number | null;
  album_id: number | null;
  is_playing: boolean;
  is_current: boolean;
};

export type QueuePayload = {
  before: QueueItem[];
  current: QueueItem | null;
  after: QueueItem[];
  before_title: string;
  after_title: string;
  now_meta: { subtitle: string; source: string };
};

export type PlayMode = 'now' | 'next' | 'queue';

export type ClientCommand =
  | { command: 'play_pause' | 'next' | 'prev' | 'cycle_repeat' | 'show_queue' | 'refresh_queue' }
  | { command: 'set_volume'; value: number }
  | { command: 'seek'; position_sec: number }
  | { command: 'set_shuffle'; on: boolean }
  | { command: 'track_reaction'; kind: 'like' | 'dislike' }
  | { command: 'navigate'; target: 'artist' | 'album' }
  | {
      command: 'play_now' | 'play_next' | 'add_to_queue';
      track_id: number;
      album_id: number | null;
      title: string;
      artist: string;
      playlist_uuid?: string;
      playlist_kind?: number;
      playlist_uid?: number;
      playlist_track_index?: number;
    }
  | {
      command: 'play_queue_track';
      track_id: number;
      album_id: number | null;
      title: string;
      artist: string;
    };
