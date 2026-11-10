import type { CatalogTrack } from '../api/types';
import { CoverArt } from './CoverArt';
import './TrackRow.css';

function Dots() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="5" cy="12" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="19" cy="12" r="1.8" />
    </svg>
  );
}

type Props = {
  track: CatalogTrack;
  variant: 'list' | 'likes';
  onPlay: (track: CatalogTrack) => void;
  onMenu: (track: CatalogTrack) => void;
};

export function TrackRow({ track, variant, onPlay, onMenu }: Props) {
  const menu = (
    <button
      type="button"
      className="row-action"
      aria-label="Действия с треком"
      onClick={(event) => {
        event.stopPropagation();
        onMenu(track);
      }}
    >
      <Dots />
    </button>
  );
  const body = (
    <>
      <CoverArt url={track.cover_url} />
      <div className="meta">
        <div className="title">{track.title}</div>
        <div className="artist">{track.artist}</div>
      </div>
      {menu}
    </>
  );
  if (variant === 'likes') {
    return (
      <div
        className="likes-row"
        role="button"
        tabIndex={0}
        onClick={() => onPlay(track)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') onPlay(track);
        }}
      >
        {body}
      </div>
    );
  }
  return <li onClick={() => onPlay(track)}>{body}</li>;
}
