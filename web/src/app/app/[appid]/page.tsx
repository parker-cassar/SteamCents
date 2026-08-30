import { notFound } from "next/navigation";
import { api, money } from "@/lib/api";
import PriceSparkline from "@/components/PriceSparkline";

export default async function AppPage({ params }: { params: Promise<{ appid: string }> }) {
  const { appid: appidRaw } = await params;
  const appid = Number(appidRaw);
  if (!Number.isInteger(appid)) notFound();

  let app;
  try {
    app = await api.app(appid);
  } catch {
    notFound();
  }

  const { observations } = await api.history(appid);

  return (
    <main className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">{app.name}</h1>
        <div className="text-sm text-black/50 dark:text-white/50">appid {app.appid}</div>
      </div>

      <div className="text-3xl font-semibold">{money(app.final_cents, app.currency)}</div>

      {observations.length > 1 ? (
        <PriceSparkline observations={observations} />
      ) : (
        <div className="text-sm text-black/50 dark:text-white/50">not enough history for a chart yet</div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-black/50 dark:text-white/50 border-b border-black/10 dark:border-white/15">
            <th className="py-2 pr-2">when</th>
            <th className="py-2 pr-2">price</th>
            <th className="py-2 pr-2">discount</th>
          </tr>
        </thead>
        <tbody>
          {[...observations].reverse().map((o) => (
            <tr key={o.observed_at} className="border-b border-black/5 dark:border-white/10">
              <td className="py-2 pr-2 text-black/60 dark:text-white/60">
                {new Date(o.observed_at).toLocaleString()}
              </td>
              <td className="py-2 pr-2">{money(o.final_cents, o.currency)}</td>
              <td className="py-2 pr-2">{o.discount_pct > 0 ? `${o.discount_pct}%` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
