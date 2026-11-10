import { useWorkPending } from '../store/busy';
import './Busy.css';

export function Busy() {
  const pending = useWorkPending();
  if (!pending) return null;
  return (
    <div className="busy-indicator" role="status" aria-live="polite" aria-label="Запрос выполняется">
      <div className="busy-spinner" />
    </div>
  );
}
