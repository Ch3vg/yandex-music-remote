import './VolumeIcon.css';

type Props = {
  pct: number;
  size: number;
};

export function VolumeIcon({ pct, size }: Props) {
  const p = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
  const wave1 = p === 0 ? 0.2 : 1;
  const wave2 = p >= 35 ? 1 : 0.22;
  const wave3 = p >= 70 ? 1 : 0.22;
  return (
    <span className="vol-icon-dynamic" aria-hidden="true">
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.65"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M11 5L6 9H2v6h4l5 4V5z" />
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" opacity={wave1} />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" opacity={wave2} />
        <path d="M22.54 2.46a15 15 0 0 1 0 19.08" opacity={wave3} />
        {p === 0 ? <path d="M16 9l6 6M22 9l-6 6" strokeWidth="1.5" /> : null}
      </svg>
    </span>
  );
}
