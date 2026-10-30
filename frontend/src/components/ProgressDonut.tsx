import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Nav, ProjectProgress } from "../types";

export const BANDS = [
  { key: "verified", label: "Verified complete", color: "#34c38f" },
  { key: "in_progress", label: "In progress", color: "#2f80ed" },
  { key: "blocked", label: "Blocked", color: "#ef6a6a" },
  { key: "pending", label: "Pending", color: "#dbe2ea" },
] as const;

const HEALTH: Record<string, string> = {
  "On track": "bg-emerald-100 text-emerald-700", Complete: "bg-emerald-100 text-emerald-700", "At risk": "bg-amber-100 text-amber-800",
  "Off track": "bg-rose-100 text-rose-700", "Not planned": "bg-slate-100 text-slate-600",
};

export function HealthBadge({ health }: { health: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${HEALTH[health] ?? HEALTH["Not planned"]}`}>{health}</span>;
}

export function Donut({ p, size = 120 }: { p: ProjectProgress; size?: number }) {
  const data = BANDS.map((b) => ({ ...b, value: p.bands_pct[b.key] }));
  const empty = !p.total_tasks;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`${p.name}: ${p.completion_pct}% verified complete`}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={empty ? [{ key: "none", label: "No tasks yet", value: 100, color: "#eef2f7" }] : data} dataKey="value" innerRadius="70%" outerRadius="100%" stroke="none" startAngle={90} endAngle={-270} isAnimationActive={false}>
            {(empty ? [{ key: "none", color: "#eef2f7" }] : data).map((d: any) => <Cell key={d.key} fill={d.color} />)}
          </Pie>
          {!empty && <Tooltip formatter={(v: number, _n, x: any) => [`${v}%`, x.payload.label]} />}
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
        <div><div className="text-lg font-bold leading-none text-slate-800">{empty ? "–" : `${Math.round(p.completion_pct)}%`}</div><div className="mt-0.5 text-[9px] uppercase tracking-wide text-slate-400">{empty ? "no plan" : "verified"}</div></div>
      </div>
    </div>
  );
}

export function ProjectProgressCard({ p, onNav }: { p: ProjectProgress; onNav: Nav }) {
  return (
    <button onClick={() => onNav("project", p.project_id)} className="w-full min-w-0 rounded-2xl bg-white p-4 text-left shadow-card transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <h3 className="truncate text-[14px] font-semibold text-slate-800">{p.name}</h3>
        <HealthBadge health={p.health} />
      </div>
      <div className="mt-3 flex items-center gap-4">
        <Donut p={p} size={104} />
        <dl className="min-w-0 flex-1 space-y-1 text-[11px] text-slate-500">
          {BANDS.map((b) => (
            <div key={b.key} className="flex items-center justify-between gap-2"><dt className="flex items-center gap-1.5 truncate"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: b.color }} />{b.label}</dt><dd className="font-medium text-slate-700">{p.bands_pct[b.key]}%</dd></div>
          ))}
        </dl>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
        <span className="truncate">Milestone: <b className="font-medium text-slate-700">{p.current_milestone ?? "—"}</b></span>
        <span className="text-right">{p.days_remaining < 0 ? `${-p.days_remaining} days overdue` : `${p.days_remaining} days left`}</span>
        <span>{p.open_tasks} open · {p.overdue_tasks.length} overdue</span>
        <span className={`text-right ${p.critical_blockers.length ? "font-medium text-rose-600" : ""}`}>{p.critical_blockers.length} critical blocker{p.critical_blockers.length === 1 ? "" : "s"}</span>
      </div>
    </button>
  );
}
