import { api } from "@/lib/api";
import StatsHeader from "@/components/StatsHeader";
import DailyChangesChart from "@/components/DailyChangesChart";
import DropsTable from "@/components/DropsTable";

export default async function Home() {
  const [stats, changes, drops] = await Promise.all([
    api.stats(),
    api.changesDaily(30),
    api.drops(7, 30),
  ]);

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-8">
      <h1 className="text-lg font-semibold">steamcents</h1>

      <StatsHeader stats={stats} />

      <section>
        <h2 className="text-sm font-medium mb-3">price changes, last 30 days</h2>
        <DailyChangesChart series={changes.series} />
      </section>

      <section>
        <h2 className="text-sm font-medium mb-3">biggest drops, last 7 days</h2>
        <DropsTable drops={drops.drops} />
      </section>
    </main>
  );
}
