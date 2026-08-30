import { DailyChanges } from "@/lib/api";

export default function DailyChangesChart({ series }: { series: DailyChanges[] }) {
  if (series.length === 0) {
    return <div className="text-sm text-black/50 dark:text-white/50">no changes recorded yet</div>;
  }

  const max = Math.max(...series.map((d) => d.changes), 1);
  const w = 720;
  const h = 160;
  const barW = w / series.length;

  return (
    <svg viewBox={`0 0 ${w} ${h + 24}`} className="w-full h-auto">
      {series.map((d, i) => {
        const total = Math.max(d.changes, 1);
        const barH = (d.changes / max) * h;
        const dropH = (d.drops / total) * barH;
        const x = i * barW + barW * 0.15;
        const bw = barW * 0.7;
        return (
          <g key={d.day}>
            <rect x={x} y={h - barH} width={bw} height={barH - dropH} className="fill-emerald-400/70" />
            <rect x={x} y={h - dropH} width={bw} height={dropH} className="fill-rose-400/80" />
            <title>{`${d.day}: ${d.changes} changes, ${d.drops} drops, ${d.rises} rises`}</title>
          </g>
        );
      })}
      <text x={0} y={h + 16} fontSize="10" className="fill-black/40 dark:fill-white/40">
        {series[0]?.day}
      </text>
      <text x={w} y={h + 16} fontSize="10" textAnchor="end" className="fill-black/40 dark:fill-white/40">
        {series[series.length - 1]?.day}
      </text>
    </svg>
  );
}
