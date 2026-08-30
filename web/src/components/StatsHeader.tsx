import { Stats } from "@/lib/api";

function ago(iso: string | null) {
  if (!iso) return "-";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-black/10 dark:border-white/15 p-4">
      <div className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {sub && <div className="text-xs text-black/40 dark:text-white/40 mt-1">{sub}</div>}
    </div>
  );
}

export default function StatsHeader({ stats }: { stats: Stats }) {
  const alive = stats.sweep && stats.sweep.heartbeat_age_s < 120;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <Tile label="apps tracked" value={stats.catalog.live.toLocaleString()} sub={`${stats.coverage_pct}% checked`} />
      <Tile
        label="price observations"
        value={stats.prices.observations.toLocaleString()}
        sub={stats.prices.days_of_history ? `${stats.prices.days_of_history} days of history` : undefined}
      />
      <Tile
        label="crawl"
        value={alive ? "running" : "stopped"}
        sub={stats.sweep ? `heartbeat ${ago(stats.sweep.heartbeat_at)}` : undefined}
      />
      <Tile label="changes seen" value={stats.totals.changes.toLocaleString()} sub={`${stats.totals.checks.toLocaleString()} checks`} />
    </div>
  );
}
