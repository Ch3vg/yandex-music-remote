import { send } from '../api/ws';
import { VolumeIcon } from '../components/VolumeIcon';
import { isVolumeEcho, setVolumeLocal, usePlaybackSelector } from '../store/playback';
import './Volume.css';

export function Volume({ active }: { active: boolean }) {
  const volume = usePlaybackSelector((view) => view.volume);
  const onInput = (value: string) => {
    if (isVolumeEcho()) return;
    const next = Math.round(Number(value));
    if (!Number.isFinite(next)) return;
    setVolumeLocal(next);
    send({ command: 'set_volume', value: next });
  };
  return (
    <section className={active ? 'screen active' : 'screen'} id="screenVolume">
      <div className="screen-header">
        <h1 className="screen-title">Громкость</h1>
        <span className="status-dot" aria-hidden="true" />
      </div>
      <div className="volume-screen">
        <VolumeIcon pct={volume} size={56} />
        <div className="vol-pct" id="volLabel">{volume}%</div>
        <input
          type="range"
          id="volume"
          min={0}
          max={100}
          value={volume}
          onInput={(event) => onInput(event.currentTarget.value)}
        />
      </div>
    </section>
  );
}
