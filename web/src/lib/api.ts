const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return res.json();
}

export type Stats = {
  catalog: { apps: number; live: number; checked: number; unpriced: number; parked: number };
  prices: {
    observations: number;
    apps_with_price: number;
    first_observed: string | null;
    last_observed: string | null;
    days_of_history: number | null;
  };
  coverage_pct: number;
  sweep: {
    id: number;
    heartbeat_at: string;
    exit_reason: string | null;
    heartbeat_age_s: number;
  } | null;
  totals: { checks: number; changes: number; http_429s: number; errors: number; tracked_since: string | null };
  tiers: { tier: number; apps: number }[];
};

export type DailyChanges = { day: string; changes: number; drops: number; rises: number; apps: number };

export type Drop = {
  appid: number;
  name: string;
  observed_at: string;
  currency: string;
  prev_final_cents: number;
  final_cents: number;
  discount_pct: number;
  drop_cents: number;
  drop_pct: number;
};

export type AppDetail = {
  appid: number;
  name: string;
  delisted_at: string | null;
  tier: number;
  no_price_seen_at: string | null;
  currency: string | null;
  final_cents: number | null;
  discount_pct: number | null;
  observed_at: string | null;
};

export type Observation = {
  observed_at: string;
  currency: string;
  initial_cents: number;
  final_cents: number;
  discount_pct: number;
};

export type BriefBody = {
  headline: string;
  summary: string;
  highlights: { claim: string; source: string }[];
  watchouts: string[];
  coverage_note: string;
};

export type Brief = {
  id: number;
  period_start: string;
  period_end: string;
  brief: BriefBody;
  model: string;
  prompt_version: string;
  created_at: string;
};

export const api = {
  stats: () => get<Stats>("/stats"),
  changesDaily: (days = 30) => get<{ series: DailyChanges[] }>(`/changes/daily?days=${days}`),
  drops: (days = 7, limit = 30) => get<{ drops: Drop[] }>(`/drops?days=${days}&limit=${limit}`),
  briefLatest: async () => {
    const res = await fetch(`${BASE}/briefs/latest`, { cache: "no-store" });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`/briefs/latest -> ${res.status}`);
    return res.json() as Promise<Brief>;
  },
  app: (appid: number) => get<AppDetail>(`/apps/${appid}`),
  history: (appid: number, limit = 500) =>
    get<{ observations: Observation[] }>(`/apps/${appid}/history?limit=${limit}`),
};

export function money(cents: number | null, currency: string | null) {
  if (cents == null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(cents / 100);
}
