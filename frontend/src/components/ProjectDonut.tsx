import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { EmployeeScores, Task } from "../types";
import { avatarGradient, initials } from "./ui";

const STAGES = [
  { key: "evaluation", label: "Evaluation in progress", color: "#f6c453", statuses: ["DRAFT_GENERATED", "READY_FOR_ALLOCATION", "BLOCKED_BY_DEPENDENCY", "CANDIDATES_SCORED"] },
  { key: "approval", label: "Awaiting approval", color: "#f59e8b", statuses: ["PENDING_HITL_APPROVAL", "REALLOCATION_PROPOSED", "AT_RISK_DISRUPTED"] },
  { key: "allocated", label: "Team allocated", color: "#6cc7d9", statuses: ["ASSIGNED"] },
  { key: "progress", label: "In progress", color: "#2f80ed", statuses: ["IN_PROGRESS", "DELIVERABLE_IN_REVIEW"] },
  { key: "done", label: "Completed", color: "#34c38f", statuses: ["COMPLETED_AND_AUDITED"] },
];

/** Ongoing-projects donut: stage segments, with the allocated team rotating in 3D in the centre. */
export function ProjectDonut({ tasks, employees, title }: { tasks: Task[]; employees: EmployeeScores[]; title?: string }) {
  const [stage, setStage] = useState<string | null>(null);
  const [front, setFront] = useState(0);
  const [paused, setPaused] = useState(false);

  const data = STAGES.map((s) => ({ ...s, value: tasks.filter((t) => s.statuses.includes(t.status)).length }));
  const total = tasks.length;

  const members = useMemo(() => {
    const pool = stage ? tasks.filter((t) => STAGES.find((s) => s.key === stage)!.statuses.includes(t.status)) : tasks;
    const ids = [...new Set(pool.map((t) => t.assigned_to).filter(Boolean))] as string[];
    const list = ids.map((id) => employees.find((e) => e.employee_id === id)).filter(Boolean) as EmployeeScores[];
    return list;
  }, [stage, tasks, employees]);

  useEffect(() => setFront(0), [stage]);
  useEffect(() => {
    if (paused || members.length < 2) return;
    const t = setInterval(() => setFront((f) => (f + 1) % members.length), 2200);
    return () => clearInterval(t);
  }, [paused, members.length]);

  const n = members.length;
  const radius = Math.min(46, 14 + n * 4);
  const current = members[front % Math.max(n, 1)];
  const currentTask = current ? tasks.find((t) => t.assigned_to === current.employee_id) : undefined;

  return (
    <div>
      <div className="mb-3 flex min-h-[26px] items-center justify-between">
        {title && <h2 className="text-[15px] font-semibold text-slate-800">{title}</h2>}
        {stage && <button onClick={() => setStage(null)} className="ml-auto rounded-full border border-slate-200 px-3 py-1 text-[11px] text-slate-600 hover:bg-slate-50">Show all</button>}
      </div>
      <div className="relative mx-auto h-[250px] w-full max-w-[280px]" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data.filter((d) => d.value > 0).length ? data : [{ key: "none", label: "No tasks", value: 1, color: "#e2e8f0" }]}
              dataKey="value" innerRadius={86} outerRadius={118} paddingAngle={2} stroke="none" startAngle={90} endAngle={-270}
              onClick={(d: any) => d?.key && d.key !== "none" && setStage(d.key === stage ? null : d.key)} className="cursor-pointer outline-none">
              {(data.filter((d) => d.value > 0).length ? data : [{ color: "#e2e8f0", key: "none" }]).map((d: any) => (
                <Cell key={d.key} fill={d.color} opacity={!stage || stage === d.key ? 1 : 0.3} />
              ))}
            </Pie>
            <Tooltip formatter={(v: number, _n, p: any) => [`${v} task${v === 1 ? "" : "s"}`, p.payload.label]} />
          </PieChart>
        </ResponsiveContainer>

        {/* rotating team carousel */}
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <div className="flex flex-col items-center">
            <div className="relative h-[86px] w-[150px]" style={{ perspective: 420 }}>
              {members.map((m, i) => {
                const angle = ((i - front) / Math.max(n, 1)) * 2 * Math.PI;
                const depth = Math.cos(angle);             // 1 = front, -1 = back
                const x = Math.sin(angle) * radius;
                const scale = 0.55 + 0.45 * ((depth + 1) / 2);
                return (
                  <div key={m.employee_id} className="absolute left-1/2 top-1/2"
                    style={{
                      transform: `translate(-50%, -50%) translateX(${x}px) translateZ(${depth * 30}px) scale(${scale})`,
                      opacity: 0.25 + 0.75 * ((depth + 1) / 2), zIndex: Math.round((depth + 1) * 50),
                      filter: depth > 0.95 ? "none" : `blur(${(1 - depth) * 0.7}px)`, transition: "all 0.9s cubic-bezier(.4,.2,.2,1)",
                    }}>
                    <div className={`grid h-[62px] w-[62px] place-items-center rounded-full bg-gradient-to-br text-lg font-semibold text-white ring-4 ring-white ${avatarGradient(m.employee_id)} ${depth > 0.95 ? "shadow-lg" : ""}`}>
                      {initials(m.name)}
                    </div>
                  </div>
                );
              })}
              {!n && <div className="absolute inset-0 grid place-items-center text-center text-[11px] text-slate-400">No team yet</div>}
            </div>
            <div className="mt-1 h-9 text-center">
              {current && (
                <>
                  <div className="text-[13px] font-semibold leading-tight text-slate-800">{current.name}</div>
                  <div className="max-w-[150px] truncate text-[10px] text-slate-500">{currentTask ? `${currentTask.id} · ${currentTask.status.replace(/_/g, " ").toLowerCase()}` : current.designation}</div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
        {data.map((d) => (
          <button key={d.key} onClick={() => setStage(stage === d.key ? null : d.key)}
            className={`flex items-center justify-between rounded-lg px-2 py-1 text-left text-[12px] transition hover:bg-slate-50 ${stage === d.key ? "bg-slate-50" : ""}`}>
            <span className="flex items-center gap-2 text-slate-600"><span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />{d.label}</span>
            <span className="font-semibold text-slate-800">{total ? Math.round((d.value / total) * 100) : 0}%</span>
          </button>
        ))}
      </div>
    </div>
  );
}
