import { useSyncExternalStore } from 'react';

export type Role = 'guest' | 'admin';

const listeners = new Set<() => void>();
let role: Role = 'guest';

function emit(): void {
  listeners.forEach((listener) => listener());
}

export function subscribeRole(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getRole(): Role {
  return role;
}

export function applyRole(next: Role): void {
  if (next === role) return;
  role = next;
  emit();
}

export function useRole(): Role {
  return useSyncExternalStore(subscribeRole, getRole, getRole);
}
