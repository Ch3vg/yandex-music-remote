import { beginWork } from '../store/busy';

export async function fetchJson<T>(url: string, fallback: string): Promise<T> {
  const done = beginWork();
  try {
    const res = await fetch(url);
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (!res.ok) {
      let message = fallback;
      if (body && typeof body === 'object' && 'detail' in body) {
        const detail = (body as { detail: unknown }).detail;
        if (typeof detail === 'string' && detail) message = detail;
      }
      throw new Error(message);
    }
    return body as T;
  } finally {
    done();
  }
}
