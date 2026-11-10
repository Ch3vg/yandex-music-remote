import type { CatalogTrack, PlayMode } from '../api/types';
import './TrackActions.css';

const ACTIONS: { id: PlayMode; label: string }[] = [
  { id: 'now', label: 'Включить сейчас' },
  { id: 'next', label: 'Играть следующим' },
  { id: 'queue', label: 'Добавить в очередь' },
];

type Props = {
  track: CatalogTrack | null;
  onClose: () => void;
  onAction: (track: CatalogTrack, mode: PlayMode) => void;
};

export function TrackActions({ track, onClose, onAction }: Props) {
  return (
    <div
      className={track ? 'track-action-sheet open' : 'track-action-sheet'}
      id="trackActionSheet"
      aria-hidden={!track}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="track-action-panel" role="dialog" aria-labelledby="trackActionTitle">
        <div className="track-action-head">
          <div className="title" id="trackActionTitle">{track?.title || 'Трек'}</div>
          <div className="artist" id="trackActionArtist">{track?.artist || ''}</div>
        </div>
        <ul className="track-action-list" id="trackActionList">
          {ACTIONS.map((action) => (
            <li key={action.id}>
              <button
                type="button"
                onClick={() => {
                  if (track) onAction(track, action.id);
                }}
              >
                {action.label}
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="track-action-cancel" id="trackActionCancel" onClick={onClose}>
          Отмена
        </button>
      </div>
    </div>
  );
}
