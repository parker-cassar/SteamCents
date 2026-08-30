import Link from "next/link";
import { Drop, money } from "@/lib/api";

export default function DropsTable({ drops }: { drops: Drop[] }) {
  if (drops.length === 0) {
    return <div className="text-sm text-black/50 dark:text-white/50">no drops in this window</div>;
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-black/50 dark:text-white/50 border-b border-black/10 dark:border-white/15">
          <th className="py-2 pr-2">app</th>
          <th className="py-2 pr-2">was</th>
          <th className="py-2 pr-2">now</th>
          <th className="py-2 pr-2">off</th>
        </tr>
      </thead>
      <tbody>
        {drops.map((d) => (
          <tr key={d.appid} className="border-b border-black/5 dark:border-white/10">
            <td className="py-2 pr-2">
              <Link href={`/app/${d.appid}`} className="hover:underline">
                {d.name}
              </Link>
            </td>
            <td className="py-2 pr-2 text-black/50 dark:text-white/50 line-through">
              {money(d.prev_final_cents, d.currency)}
            </td>
            <td className="py-2 pr-2 font-medium">{money(d.final_cents, d.currency)}</td>
            <td className="py-2 pr-2 text-emerald-600 dark:text-emerald-400">-{d.drop_pct}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
