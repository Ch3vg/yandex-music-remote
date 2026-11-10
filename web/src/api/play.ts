import type { CatalogTrack, PlayContext, PlayMode } from './types';

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
};

function albumId(track: CatalogTrack): number | null {
  if (track.album_id == null) return null;
  const n = Number(track.album_id);
  return Number.isFinite(n) ? n : null;
}

export function buildPlayCommand(
  mode: PlayMode,
  track: CatalogTrack,
  context: PlayContext | null,
): PlayCommand | null {
  const id = Number(track.id);
  if (!Number.isFinite(id)) return null;
  const command = mode === 'now' ? 'play_now' : mode === 'next' ? 'play_next' : 'add_to_queue';
  const payload: PlayCommand = {
    command,
    track_id: id,
    album_id: albumId(track),
    title: track.title ?? '',
    artist: track.artist ?? '',
  };
  if (!context?.playlist_uuid) return payload;
  payload.playlist_uuid = context.playlist_uuid;
  payload.playlist_kind = Number(context.playlist_kind);
  if (context.playlist_uid != null && Number.isFinite(Number(context.playlist_uid))) {
    payload.playlist_uid = Number(context.playlist_uid);
  }
  if (track.playlist_index != null && Number(track.playlist_index) >= 0) {
    payload.playlist_track_index = Number(track.playlist_index);
  }
  return payload;
}
