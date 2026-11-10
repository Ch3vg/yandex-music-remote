import type { ScreenName } from '../app/screen';
import './TabBar.css';

type Props = {
  screen: ScreenName;
  playerOpen: boolean;
  onSearch: () => void;
  onVolume: () => void;
  onMore: () => void;
};

export function TabBar({ screen, playerOpen, onSearch, onVolume, onMore }: Props) {
  const active = playerOpen ? '' : screen;
  return (
    <nav className="tab-bar" aria-label="Разделы">
      <button type="button" className={active === 'search' ? 'tab active' : 'tab'} aria-label="Поиск" onClick={onSearch}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3-3" />
        </svg>
        Поиск
      </button>
      <button type="button" className={active === 'volume' ? 'tab active' : 'tab'} aria-label="Громкость" onClick={onVolume}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M11 5L6 9H3v6h3l5 4V5z" />
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        </svg>
        Громкость
      </button>
      <button type="button" className={active === 'more' ? 'tab active' : 'tab'} aria-label="Ещё" onClick={onMore}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="6" r="1.5" fill="currentColor" />
          <circle cx="12" cy="12" r="1.5" fill="currentColor" />
          <circle cx="12" cy="18" r="1.5" fill="currentColor" />
        </svg>
        Ещё
      </button>
    </nav>
  );
}
