import { AlertTriangle, CircleSlash } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Candidate, EmployeeScores, Task } from "../types";
import { Avatar, Bar, FACTOR_LABELS, Modal, PillButton, PriorityBadge } from "./ui";

/** Full ranked candidate list for one task with every factor and every hard-constraint violation. */
export function CandidateModal({ task, onClose, onAssigned }: { task: Task | null; onClose: () => void; onAssigned?: (message: string) => void }) {
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!task) return;
    setCands(null);
    setErr(null);
    api<{ candidates: Candidate[] }>(`/tasks/${task.id}/candidates`).then((r) => setCands(r.candidates)).catch((e) => setErr(e.message));
  }, [task]);
  return (
    <Modal open={!!task} onClose={onClose} wide title={task ? <span>{task.id} · {task.title}</span> : ""}>
      {task && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <PriorityBadge priority={task.priority} /> <span>{task.estimated_hours}h</span> <span>· due day {task.deadline_days}</span>
          <span>· needs {Object.entries(task.required_skills).map(([k, v]) => `${k} (${v})`).join(", ")}</span>
        </div>
      )}
      {err && <p className="text-sm text-rose-600">{err}</p>}
      {!cands && !err && <p className="text-sm text-slate-400">Scoring candidates…</p>}
      <div className="space-y-3">
        {cands?.map((c, i) => (
          <div key={c.employee_id} className={`rounded-xl border p-4 ${c.eligible ? "border-slate-100" : "border-rose-100 bg-rose-50/40"}`}>
            <div className="flex flex-wrap items-center gap-3">
              <span className="w-5 text-sm font-semibold text-slate-400">#{i + 1}</span>
              <Avatar name={c.employee_name} id={c.employee_id} size={34} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-slate-800">{c.employee_name} {c.new_hire_protected && <span className="ml-1 rounded bg-violet-50 px-1.5 py-0.5 text-[10px] text-violet-600">New-hire protected</span>}</div>
                <div className="text-[11px] text-slate-500">{c.designation} · {c.free_hrs_before}h free → {c.utilization_after_pct}% post-load</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-bold ${c.eligible ? "text-slate-800" : "text-rose-500"}`}>{c.suitability_score}</div>
                <div className="text-[10px] uppercase tracking-wide text-slate-400">{c.eligible ? "eligible" : "disqualified"}</div>
                {onAssigned && c.eligible && task?.assigned_to !== c.employee_id && (
                  <PillButton className="mt-1" onClick={() => {
                    if (!task) return;
                    api(`/tasks/${task.id}/assign`, { body: { employee_id: c.employee_id, reason: "Selected from the candidate ranking" } })
                      .then(() => onAssigned(`${task.id} assigned to ${c.employee_name}.`)).catch((e) => setErr(e.message));
                  }}>Assign</PillButton>
                )}
                {task?.assigned_to === c.employee_id && <div className="mt-1 text-[10px] font-medium text-emerald-600">Current owner</div>}
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 md:grid-cols-3">
              {Object.entries(c.factor_breakdown).map(([k, v]) => (
                <div key={k}>
                  <div className="mb-1 flex justify-between text-[11px] text-slate-500"><span>{FACTOR_LABELS[k] ?? k}</span><span className="font-medium text-slate-700">{v}</span></div>
                  <Bar value={v} color={c.eligible ? "bg-brand-500" : "bg-rose-300"} />
                </div>
              ))}
            </div>
            {c.hard_violations.map((v) => <p key={v} className="mt-2 flex items-center gap-1.5 text-[12px] text-rose-600"><CircleSlash size={13} />{v}</p>)}
            {c.warnings.map((w) => <p key={w} className="mt-1 flex items-center gap-1.5 text-[12px] text-amber-600"><AlertTriangle size={13} />{w}</p>)}
          </div>
        ))}
      </div>
    </Modal>
  );
}

export function ScoreGrid({ e, suitability }: { e: EmployeeScores; suitability?: number | null }) {
  const items: { label: string; value: number | null; hint: string; color: string; suffix?: string }[] = [
    { label: "Skill", value: e.skill_score, hint: "Proficiency × verification", color: "bg-sky-400" },
    { label: "Performance", value: e.performance_score, hint: "Delivery, quality, reliability", color: "bg-violet-400" },
    { label: "Availability", value: e.availability_score, hint: `${e.free_capacity_hrs}h free this week`, color: "bg-emerald-400" },
    { label: "Workload", value: e.workload_score, hint: "Utilisation of capacity", color: e.workload_score > 85 ? "bg-rose-400" : "bg-amber-400", suffix: "%" },
    { label: "Collaboration", value: e.collaboration_score, hint: "Verified reviews & sharing", color: "bg-teal-400" },
    { label: "Task suitability", value: suitability ?? null, hint: "Computed per task", color: "bg-brand-500" },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {items.map((it) => (
        <div key={it.label} className="rounded-xl border border-slate-100 bg-white p-3">
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{it.label}</div>
          <div className="my-1 text-xl font-bold text-slate-800">
            {it.value === null ? <span className="text-sm font-medium text-slate-400">{it.label === "Performance" ? "Withheld" : "Per task"}</span> : <>{it.value}{it.suffix ?? ""}</>}
          </div>
          <Bar value={it.value ?? 0} color={it.color} />
          <div className="mt-1.5 text-[10px] leading-tight text-slate-400">{it.label === "Performance" && it.value === null ? "Insufficient evidence — new hire protected" : it.hint}</div>
        </div>
      ))}
    </div>
  );
}
