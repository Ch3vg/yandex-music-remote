export function formatTrackCount(n: number): string {
  const num = Number(n) || 0;
  if (!num) return '';
  const spaced = String(num).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0');
  const mod10 = num % 10;
  const mod100 = num % 100;
  let word = 'треков';
  if (mod10 === 1 && mod100 !== 11) word = 'трек';
  else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) word = 'трека';
  return `${spaced} ${word}`;
}
