import { useEffect, useState } from 'react';
import type { NetworkInfo } from '../api/types';
import { fetchJson } from '../api/http';
import { isShadeSupported, toggleShade, useShadeEnabled } from '../lib/shade';
import { pushToast } from '../store/playback';
import './QrSheet.css';

export function useNetworkQr(active: boolean): { info: NetworkInfo | null; src: string } {
  const [info, setInfo] = useState<NetworkInfo | null>(null);
  const [stamp, setStamp] = useState(0);
  useEffect(() => {
    if (!active) return;
    let cancel = false;
    setStamp(Date.now());
    fetchJson<NetworkInfo>('/network-info', '')
      .then((data) => {
        if (!cancel) setInfo(data);
      })
      .catch(() => {});
    return () => {
      cancel = true;
    };
  }, [active]);
  const src = info && stamp ? `/qr?ip=${encodeURIComponent(info.chosen)}&t=${stamp}` : '';
  return { info, src };
}

export function QrLink({ info }: { info: NetworkInfo | null }) {
  if (!info) return null;
  const url = info.url || `http://${info.chosen}:${info.port}/`;
  return (
    <div className="qr-url-wrap">
      <p className="qr-url-text">{url}</p>
      <button
        type="button"
        className="qr-open-link"
        onClick={() => {
          const copy = async () => {
            try {
              await navigator.clipboard.writeText(url);
              pushToast('Ссылка скопирована', 'notice');
            } catch {
              pushToast('Не удалось скопировать', 'error');
            }
          };
          void copy();
        }}
      >
        Скопировать ссылку
      </button>
      <p className="qr-open-hint">
        Отсканируйте QR или скопируйте ссылку и откройте в браузере телефона. На некоторых Android после скана доступно только «Копировать».
      </p>
    </div>
  );
}

export function QrSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { info, src } = useNetworkQr(open);
  const shadeSupported = isShadeSupported();
  const shadeOn = useShadeEnabled();
  return (
    <div
      className={open ? 'qr-sheet open' : 'qr-sheet'}
      id="qrSheet"
      aria-hidden={!open}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="qr-sheet-panel">
        <img id="qrSheetImage" alt="QR" src={src || undefined} />
        <QrLink info={info} />
        {shadeSupported && (
          <button
            type="button"
            className="qr-shade-row"
            id="qrShadeToggle"
            role="switch"
            aria-checked={shadeOn}
            onClick={() => void toggleShade()}
          >
            <span>Плеер в шторке</span>
            <span className={shadeOn ? 'qr-switch on' : 'qr-switch'} aria-hidden="true">
              <span className="qr-switch-thumb" />
            </span>
          </button>
        )}
        <button type="button" className="search-go" id="btnQrClose" onClick={onClose}>
          Закрыть
        </button>
      </div>
    </div>
  );
}
