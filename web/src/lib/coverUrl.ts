export function normalizeCoverUrl(url: string | null | undefined, size = '200x200'): string | null {
  if (!url) return null;
  let u = String(url).trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = `https://${u.replace(/^\/+/, '')}`;
  return u.replace(/%%/g, size);
}
