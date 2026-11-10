import { useState } from 'react';
import { QrLink, useNetworkQr } from '../sheets/QrSheet';
import { isShadeSupported, toggleShade, useShadeEnabled } from '../lib/shade';
import './More.css';

export function More({ active }: { active: boolean }) {
  const [qrOpen, setQrOpen] = useState(false);
  const { info, src } = useNetworkQr(qrOpen);
  const shadeSupported = isShadeSupported();
  const shadeOn = useShadeEnabled();
  return (
    <section className={active ? 'screen active' : 'screen'} id="screenMore">
      <div className="screen-header">
        <h1 className="screen-title">Ещё</h1>
      </div>
      <details
        className="more-card"
        id="qrSection"
        onToggle={(event) => setQrOpen((event.currentTarget as HTMLDetailsElement).open)}
      >
        <summary>
          QR для подключения <span>›</span>
        </summary>
        <div className="qr-container">
          <img id="qrImage" src={src || undefined} alt="QR" />
          <QrLink info={info} />
        </div>
      </details>
      {shadeSupported && (
        <button
          type="button"
          className="more-card more-row"
          id="shadeToggle"
          role="switch"
          aria-checked={shadeOn}
          onClick={() => void toggleShade()}
        >
          <span>Плеер в шторке</span>
          <span className={shadeOn ? 'more-switch on' : 'more-switch'} aria-hidden="true">
            <span className="more-switch-thumb" />
          </span>
        </button>
      )}
      <p className="more-hint">Пульт управляет Яндекс Музыкой на компьютере через CDP.</p>
    </section>
  );
}
