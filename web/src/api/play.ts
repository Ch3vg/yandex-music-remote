import type { ArtistPlayMode, CatalogTrack, PlayContext, PlayMode } from './types';

type PlayCommand = {
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
};

function albumId(track: CatalogTrack): number | null {
  if (track.album_id == null) return null;
  const n = Number(track.album_id);
  return Number.isFinite(n) ? n : null;
}

function applyTrackIndex(payload: PlayCommand, track: CatalogTrack): void {
  if (track.playlist_index != null && Number(track.playlist_index) >= 0) {
    payload.playlist_track_index = Number(track.playlist_index);
  }
}

export function buildPlayCommand(
  mode: PlayMode,
  track: CatalogTrack,
  context: PlayContext | null,
): PlayCommand | null {
  const id = Number(track.id);
  if (!Number.isFinite(id) || id <= 0) return null;
  const command = mode === 'now' ? 'play_now' : mode === 'next' ? 'play_next' : 'add_to_queue';
  const payload: PlayCommand = {
    command,
    track_id: id,
    album_id: albumId(track),
    title: track.title ?? '',
    artist: track.artist ?? '',
  };
  if (!context) return payload;

  if (context.playlist_uuid) {
    payload.playlist_uuid = context.playlist_uuid;
    payload.playlist_kind = Number(context.playlist_kind);
    if (context.playlist_uid != null && Number.isFinite(Number(context.playlist_uid))) {
      payload.playlist_uid = Number(context.playlist_uid);
    }
    applyTrackIndex(payload, track);
    return payload;
  }

  if (context.artist_id != null && Number.isFinite(Number(context.artist_id)) && Number(context.artist_id) > 0) {
    payload.artist_id = Number(context.artist_id);
    payload.artist_mode = context.artist_mode;
    applyTrackIndex(payload, track);
    return payload;
  }

  if (context.context_album_id != null && Number.isFinite(Number(context.context_album_id)) && Number(context.context_album_id) > 0) {
    payload.context_album_id = Number(context.context_album_id);
    applyTrackIndex(payload, track);
    return payload;
  }

  return payload;
}
