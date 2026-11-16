export type RepeatMode = 'off' | 'queue' | 'one';

export type ArtistRef = {
  id: number | null;
  name: string;
  cover_url?: string | null;
};

export type CatalogTrack = {
  id: number;
  album_id: number | null;
  title: string;
  artist: string;
  artists?: ArtistRef[];
  cover_url: string | null;
  cover_url_hq?: string | null;
  playlist_index?: number;
};

export type ArtistCard = {
  id: number;
  name: string;
  cover_url: string | null;
  cover_url_hq?: string | null;
};

export type AlbumCard = {
  id: number;
  title: string;
  artist: string;
  year: number | null;
  album_type: string | null;
  version: string | null;
  track_count: number;
  cover_url: string | null;
  cover_url_hq?: string | null;
};

export type AlbumDetail = AlbumCard & {
  artists: ArtistRef[];
  tracks: CatalogTrack[];
};

export type ArtistDetail = {
  id: number;
  name: string;
  cover_url: string | null;
  cover_url_hq: string | null;
  ambient_color?: string | null;
  total_tracks: number;
  total_albums: number;
  popular_tracks: CatalogTrack[];
  familiar_total: number;
  albums: AlbumCard[];
  singles: AlbumCard[];
};

export type ArtistTracksPage = {
  tracks: CatalogTrack[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
};

export type ArtistFamiliarResponse = {
  collection_tracks?: CatalogTrack[];
  wave_tracks?: CatalogTrack[];
  tracks?: CatalogTrack[];
};

export type SearchResponse = {
  artists: ArtistCard[];
  tracks: CatalogTrack[];
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

export type ArtistPlayMode =
  | 'popular'
  | 'tracks'
  | 'familiar'
  | 'familiar_collection'
  | 'familiar_wave';

export type PlayContext =
  | {
      playlist_kind: number;
      playlist_uid: number | null;
      playlist_uuid: string;
      artist_id?: undefined;
      artist_mode?: undefined;
      context_album_id?: undefined;
    }
  | {
      artist_id: number;
      artist_mode: ArtistPlayMode;
      playlist_uuid?: undefined;
      context_album_id?: undefined;
    }
  | {
      context_album_id: number;
      playlist_uuid?: undefined;
      artist_id?: undefined;
    };

export type QueueItem = {
  title: string;
  artist: string;
  artists?: ArtistRef[];
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
  | { command: 'play_artist'; artist_id: number }
  | { command: 'play_album'; album_id: number }
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
      artist_id?: number;
      artist_mode?: ArtistPlayMode;
      context_album_id?: number;
    }
  | {
      command: 'play_queue_track';
      track_id: number;
      album_id: number | null;
      title: string;
      artist: string;
    };
