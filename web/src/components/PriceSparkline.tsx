import { Observation } from "@/lib/api";

export default function PriceSparkline({ observations }: { observations: Observation[] }) {
  const w = 600;
  const h = 100;
  const prices = observations.map((o) => o.final_cents);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;

  const points = observations
    .map((o, i) => {
      const x = (i / (observations.length - 1)) * w;
      const y = h - ((o.final_cents - min) / span) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto">
      <polyline points={points} fill="none" strokeWidth={2} className="stroke-emerald-500" />
    </svg>
  );
}
