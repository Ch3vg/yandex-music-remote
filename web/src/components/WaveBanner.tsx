import { useEffect, useState } from 'react';
import { fetchJson } from '../api/http';
import './WaveBanner.css';

type Tone = 'collection' | 'playlist' | 'track';

type Props = {
  id?: string;
  kicker: string;
  title: string;
  tone: Tone;
  disabled?: boolean;
  onClick: () => void;
};

type WaveArt = { cover_url: string | null; background: string | null };

const emptyArt: WaveArt = { cover_url: null, background: null };
let cached: WaveArt | null = null;
let inflight: Promise<WaveArt> | null = null;
let missAt = 0;

function loadWaveArt(): Promise<WaveArt> {
  if (cached && (cached.cover_url || cached.background)) return Promise.resolve(cached);
  if (inflight) return inflight;
  if (Date.now() - missAt < 15000) return Promise.resolve(emptyArt);
  inflight = fetchJson<WaveArt>('/api/library/wave-background', 'фон волны')
    .then((body) => {
      const art: WaveArt = {
        cover_url: body?.cover_url || null,
        background: body?.background || null,
      };
      if (art.cover_url || art.background) cached = art;
      else missAt = Date.now();
      return art;
    })
    .catch(() => {
      missAt = Date.now();
      return emptyArt;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

function artStyle(art: WaveArt | null): { background?: string; backgroundImage?: string; backgroundSize?: string; backgroundPosition?: string } | undefined {
  const cover = art?.cover_url?.trim();
  if (cover && !/^blob:/i.test(cover)) {
    const image = /^data:image\//i.test(cover) ? cover : cover;
    return {
      backgroundImage: `url("${image.replace(/"/g, '')}")`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    };
  }
  if (art?.background) return { background: art.background };
  return undefined;
}

export function WaveBanner({ id, kicker, title, tone, disabled, onClick }: Props) {
  const [art, setArt] = useState<WaveArt | null>(cached);
  useEffect(() => {
    let cancel = false;
    loadWaveArt().then((next) => {
      if (!cancel) setArt(next);
    });
    return () => {
      cancel = true;
    };
  }, []);
  const painted = artStyle(art);
  return (
    <button
      type="button"
      id={id}
      className={`wave-banner wave-banner--${tone}${painted ? ' wave-banner--art' : ''}`}
      style={painted}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="wave-banner-kicker">{kicker}</span>
      <span className="wave-banner-line">
        <span className="wave-banner-play" aria-hidden="true">▶</span>
        {title}
      </span>
    </button>
  );
}
