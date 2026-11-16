export type MiniLook = {
  hasArt: boolean;
  bgImage: string | null;
  c1: string;
  c2: string;
  fade: string;
  glow: string;
  halo: string;
  haloSoft: string;
};

export type CoverLook = {
  mini: MiniLook;
  playerC1: string | null;
  playerC2: string | null;
};

const RESET_HALO = {
  glow: 'rgba(150, 158, 178, 0.45)',
  halo: 'rgba(130, 140, 165, 0.72)',
  haloSoft: 'rgba(120, 132, 158, 0.55)',
};

export function resetMini(): MiniLook {
  return {
    hasArt: false,
    bgImage: null,
    c1: 'rgba(36, 36, 42, 0.9)',
    c2: 'rgba(28, 28, 34, 0.75)',
    fade: 'rgba(48, 48, 56, 0.38)',
    ...RESET_HALO,
  };
}

function cssUrl(url: string): string {
  return `url("${url.replace(/"/g, '%22')}")`;
}

function neutralMini(url: string): MiniLook {
  return {
    hasArt: true,
    bgImage: cssUrl(url),
    c1: 'rgba(36, 38, 44, 0.62)',
    c2: 'rgba(24, 26, 32, 0.45)',
    fade: 'rgba(42, 44, 52, 0.24)',
    ...RESET_HALO,
  };
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
        break;
      case g:
        h = ((b - r) / d + 2) / 6;
        break;
      default:
        h = ((r - g) / d + 4) / 6;
        break;
    }
  }
  return [h, s, l];
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  if (s === 0) {
    const v = Math.round(l * 255);
    return [v, v, v];
  }
  const hue2rgb = (p: number, q: number, t: number) => {
    let tt = t;
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  return [
    Math.round(hue2rgb(p, q, h + 1 / 3) * 255),
    Math.round(hue2rgb(p, q, h) * 255),
    Math.round(hue2rgb(p, q, h - 1 / 3) * 255),
  ];
}

type Sample =
  | { neutral: true }
  | { neutral: false; top: number[]; bottom: number[]; fade: number[]; glow: number[] };

function sampleCoverPalette(img: HTMLImageElement): Sample | null {
  const canvas = document.createElement('canvas');
  const size = 56;
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.drawImage(img, 0, 0, size, size);
  const data = ctx.getImageData(0, 0, size, size).data;
  let r = 0;
  let g = 0;
  let b = 0;
  let n = 0;
  let rC = 0;
  let gC = 0;
  let bC = 0;
  let nC = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 100) continue;
    const pr = data[i];
    const pg = data[i + 1];
    const pb = data[i + 2];
    const max = Math.max(pr, pg, pb);
    const min = Math.min(pr, pg, pb);
    r += pr;
    g += pg;
    b += pb;
    n += 1;
    if (max < 42) continue;
    if (max - min < 20) continue;
    rC += pr;
    gC += pg;
    bC += pb;
    nC += 1;
  }
  if (!n) return null;
  const use = nC >= 10 ? [rC / nC, gC / nC, bC / nC] : [r / n, g / n, b / n];
  const [h, s, l] = rgbToHsl(use[0], use[1], use[2]);
  if (s < 0.14 || l < 0.22) return { neutral: true };
  const sat = Math.min(0.88, s * 1.15 + 0.04);
  const lit = Math.min(0.58, Math.max(l, l + 0.06));
  const top = hslToRgb(h, sat, Math.min(0.62, lit + 0.1));
  const bottom = hslToRgb(h, sat * 0.9, Math.max(0.16, lit - 0.18));
  const glow = hslToRgb(h, Math.min(0.82, sat * 1.05), Math.min(0.55, lit + 0.12));
  const fade = hslToRgb(h, sat * 0.85, Math.min(0.5, lit + 0.02));
  return { neutral: false, top, bottom, fade, glow };
}

function haloFromGlow(rgb: number[]): Pick<MiniLook, 'glow' | 'halo' | 'haloSoft'> {
  const [h, s, l] = rgbToHsl(rgb[0], rgb[1], rgb[2]);
  if (s < 0.14 || l < 0.2) return RESET_HALO;
  const sat = Math.min(0.78, s * 1.02 + 0.04);
  const glowL = Math.min(0.52, Math.max(l, l + 0.1));
  const edge = hslToRgb(h, sat, Math.min(0.58, glowL + 0.08));
  const core = hslToRgb(h, sat * 0.95, glowL);
  const soft = hslToRgb(h, sat * 0.88, Math.max(0.28, glowL - 0.06));
  return {
    glow: `rgba(${edge.join(',')}, 0.72)`,
    halo: `rgba(${core.join(',')}, 0.82)`,
    haloSoft: `rgba(${soft.join(',')}, 0.68)`,
  };
}

export const DEFAULT_ARTIST_AMBIENT_RGB: [number, number, number] = [66, 68, 74];

export function formatRgbTriplet(rgb: [number, number, number]): string {
  return `${rgb[0]}, ${rgb[1]}, ${rgb[2]}`;
}

function toAtmosphericMistRgb(r: number, g: number, b: number): [number, number, number] {
  const [h, s, l] = rgbToHsl(r, g, b);
  if (s < 0.02) {
    const neutralL = Math.min(0.51, Math.max(0.27, l * 0.84));
    return hslToRgb(h, s, neutralL);
  }
  const nextS = s <= 0.12 ? s : Math.min(0.36, 0.12 + (s - 0.12) * 0.52);
  const maxL = nextS > 0.18 ? 0.43 : 0.51;
  const finalL = Math.min(maxL, Math.max(0.27, l * 0.84));
  return hslToRgb(h, nextS, finalL);
}

export function normalizeArtistAmbientHex(
  hex: string | null | undefined,
): [number, number, number] | null {
  if (!hex) return null;
  const cleaned = hex.trim().replace(/^#/, '');
  let full = cleaned;
  if (/^[0-9a-fA-F]{3}$/.test(cleaned)) {
    full = cleaned
      .split('')
      .map((ch) => ch + ch)
      .join('');
  }
  if (!/^[0-9a-fA-F]{6}$/.test(full)) return null;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return toAtmosphericMistRgb(r, g, b);
}

export function sampleBottomEdgeColor(img: HTMLImageElement): [number, number, number] {
  try {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx) return DEFAULT_ARTIST_AMBIENT_RGB;
    ctx.drawImage(img, 0, 0, size, size);
    const { data } = ctx.getImageData(0, 0, size, size);

    const startY = Math.floor(size * 0.36);
    const bandRows = Math.max(1, size - 1 - startY);
    const leftEdge = Math.floor(size * 0.24);
    const rightEdge = Math.ceil(size * 0.76);

    let rSum = 0;
    let gSum = 0;
    let bSum = 0;
    let wSum = 0;

    for (let y = startY; y < size; y += 1) {
      const rowWeight = 0.55 + 0.45 * ((y - startY) / bandRows);
      for (let x = 0; x < size; x += 1) {
        const idx = (y * size + x) * 4;
        if (data[idx + 3] < 100) continue;
        const pr = data[idx];
        const pg = data[idx + 1];
        const pb = data[idx + 2];
        const colWeight = x < leftEdge || x >= rightEdge ? 1.5 : 0.85;
        const w = rowWeight * colWeight;
        rSum += pr * w;
        gSum += pg * w;
        bSum += pb * w;
        wSum += w;
      }
    }

    if (wSum <= 0) return DEFAULT_ARTIST_AMBIENT_RGB;

    return toAtmosphericMistRgb(rSum / wSum, gSum / wSum, bSum / wSum);
  } catch {
    return DEFAULT_ARTIST_AMBIENT_RGB;
  }
}

export function lookFromImage(url: string, img: HTMLImageElement): CoverLook {
  try {
    const palette = sampleCoverPalette(img);
    if (!palette) return { mini: neutralMini(url), playerC1: null, playerC2: null };
    if (palette.neutral) {
      return {
        mini: neutralMini(url),
        playerC1: 'rgb(42, 44, 50)',
        playerC2: 'rgb(28, 30, 36)',
      };
    }
    return {
      mini: {
        hasArt: true,
        bgImage: cssUrl(url),
        c1: `rgba(${palette.top.join(',')}, 0.56)`,
        c2: `rgba(${palette.bottom.join(',')}, 0.38)`,
        fade: `rgba(${palette.fade.join(',')}, 0.22)`,
        ...haloFromGlow(palette.glow),
      },
      playerC1: `rgb(${palette.top.join(',')})`,
      playerC2: `rgb(${palette.bottom.join(',')})`,
    };
  } catch {
    return { mini: neutralMini(url), playerC1: null, playerC2: null };
  }
}
