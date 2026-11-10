export function normalizeCoverUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  let u = String(url).trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = `https://${u.replace(/^\/+/, '')}`;
  return u.replace(/%%/g, '200x200');
}
