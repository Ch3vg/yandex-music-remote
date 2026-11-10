export type SwipeHandle = {
  measure: () => void;
  reset: () => void;
};

let blockUntil = 0;
let horizontal = false;

export function blockMiniTap(): void {
  blockUntil = performance.now() + 450;
}

export function miniTapBlocked(): boolean {
  return performance.now() < blockUntil;
}

export function setHorizontalSwipe(value: boolean): void {
  horizontal = value;
}

export function horizontalSwipe(): boolean {
  return horizontal;
}

export function bindTrackSwipe(
  viewport: HTMLElement,
  strip: HTMLElement,
  handle: { current: SwipeHandle | null },
  opts: {
    hasPrev: () => boolean;
    hasNext: () => boolean;
    onCommit: (dir: 'prev' | 'next') => void;
  },
): () => void {
  let width = 0;
  let startX = 0;
  let startY = 0;
  let dragDx = 0;
  let axis: 'x' | 'y' | null = null;
  let pointerId: number | null = null;

  const measure = () => {
    width = viewport.clientWidth || 1;
    const panes = strip.children;
    strip.style.width = `${width * panes.length}px`;
    for (const pane of panes) {
      (pane as HTMLElement).style.width = `${width}px`;
    }
    const off = Number(strip.dataset.offset || 0);
    strip.style.transition = 'none';
    strip.style.transform = `translate3d(${-width + off}px, 0, 0)`;
  };

  const reset = () => {
    strip.dataset.offset = '0';
    measure();
  };

  const rubber = (dx: number) => {
    if (dx > 0 && !opts.hasPrev()) return dx * 0.22;
    if (dx < 0 && !opts.hasNext()) return dx * 0.22;
    return dx;
  };

  const applyDrag = (dx: number, animate: boolean) => {
    const rx = rubber(dx);
    strip.style.transition = animate ? 'transform 0.32s cubic-bezier(0.32, 0.72, 0, 1)' : 'none';
    strip.style.transform = `translate3d(${-width + rx}px, 0, 0)`;
    strip.dataset.offset = String(rx);
  };

  const onDown = (e: PointerEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest('button, input, a, [data-no-swipe]')) return;
    pointerId = e.pointerId;
    try {
      viewport.setPointerCapture(pointerId);
    } catch {
      pointerId = null;
      return;
    }
    startX = e.clientX;
    startY = e.clientY;
    dragDx = 0;
    axis = null;
  };

  const finishPointer = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    try {
      viewport.releasePointerCapture(pointerId);
    } catch {
      /* already released */
    }
    pointerId = null;
  };

  const onMove = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    if (!axis) {
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      axis = Math.abs(dx) >= Math.abs(dy) ? 'x' : 'y';
      if (axis !== 'x') {
        finishPointer(e);
        setHorizontalSwipe(false);
        return;
      }
      setHorizontalSwipe(true);
    }
    if (axis !== 'x') return;
    e.preventDefault();
    dragDx = dx;
    applyDrag(dragDx, false);
  };

  const onUp = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    finishPointer(e);
    const dx = dragDx;
    dragDx = 0;
    axis = null;
    setHorizontalSwipe(false);
    const threshold = Math.min(88, width * 0.28);
    if (dx <= -threshold && opts.hasNext()) {
      applyDrag(-width, true);
      strip.dataset.offset = String(-width);
      opts.onCommit('next');
      blockMiniTap();
      return;
    }
    if (dx >= threshold && opts.hasPrev()) {
      applyDrag(width, true);
      strip.dataset.offset = String(width);
      opts.onCommit('prev');
      blockMiniTap();
      return;
    }
    applyDrag(0, true);
    strip.dataset.offset = '0';
  };

  viewport.addEventListener('pointerdown', onDown);
  viewport.addEventListener('pointermove', onMove, { passive: false });
  viewport.addEventListener('pointerup', onUp);
  viewport.addEventListener('pointercancel', onUp);
  window.addEventListener('resize', measure);
  measure();
  handle.current = { measure, reset };

  return () => {
    viewport.removeEventListener('pointerdown', onDown);
    viewport.removeEventListener('pointermove', onMove);
    viewport.removeEventListener('pointerup', onUp);
    viewport.removeEventListener('pointercancel', onUp);
    window.removeEventListener('resize', measure);
    if (handle.current?.measure === measure) handle.current = null;
  };
}
