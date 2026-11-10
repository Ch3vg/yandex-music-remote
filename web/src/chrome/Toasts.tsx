import { usePlaybackSelector } from '../store/playback';
import './Toasts.css';

export function Toasts() {
  const toasts = usePlaybackSelector((view) => view.toasts);
  return (
    <div className="toast-host" id="errorBox">
      {toasts.map((toast) => (
        <div key={toast.id} className={toast.kind === 'error' ? 'error-toast' : 'notice-toast'}>
          {toast.message}
        </div>
      ))}
    </div>
  );
}
