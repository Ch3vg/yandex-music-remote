import { useEffect, useState } from 'react';
import { normalizeCoverUrl } from '../lib/coverUrl';
import './CoverArt.css';

export function CoverArt({ url }: { url: string | null | undefined }) {
  const src = normalizeCoverUrl(url);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) return <div className="cover" />;
  return <img className="cover" alt="" src={src} onError={() => setFailed(true)} />;
}

export function CoverFrame({ url }: { url: string | null | undefined }) {
  const src = normalizeCoverUrl(url);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  return (
    <div className="cover-frame">
      {src && !failed ? <img alt="" src={src} onError={() => setFailed(true)} /> : null}
    </div>
  );
}
