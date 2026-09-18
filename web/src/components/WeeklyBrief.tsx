import { Brief } from "@/lib/api";

export default function WeeklyBrief({ brief }: { brief: Brief | null }) {
  if (!brief) {
    return (
      <div className="text-sm text-black/50 dark:text-white/50">
        no weekly brief yet
      </div>
    );
  }

  const b = brief.brief;
  return (
    <div className="space-y-3 text-sm">
      <div>
        <div className="font-medium">{b.headline}</div>
        <div className="text-black/60 dark:text-white/60 mt-1">{b.summary}</div>
      </div>
      {b.highlights.length > 0 && (
        <ul className="list-disc pl-5 space-y-1">
          {b.highlights.map((h, i) => (
            <li key={i}>
              {h.claim}
              <span className="text-black/40 dark:text-white/40 text-xs ml-2">
                {h.source}
              </span>
            </li>
          ))}
        </ul>
      )}
      {b.watchouts.length > 0 && (
        <div className="text-amber-700 dark:text-amber-400">
          {b.watchouts.join(" · ")}
        </div>
      )}
      <div className="text-xs text-black/40 dark:text-white/40">
        {b.coverage_note} · {brief.period_start} → {brief.period_end} · {brief.model}
      </div>
    </div>
  );
}
