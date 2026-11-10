import { useSyncExternalStore } from 'react';

const listeners = new Set<() => void>();

let pending = 0;

function emit(): void {
  listeners.forEach((listener) => listener());
}

export function beginWork(): () => void {
  pending += 1;
  emit();
  let closed = false;
  return () => {
    if (closed) return;
    closed = true;
    pending = Math.max(0, pending - 1);
    emit();
  };
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useWorkPending(): boolean {
  return useSyncExternalStore(subscribe, () => pending > 0, () => false);
}
