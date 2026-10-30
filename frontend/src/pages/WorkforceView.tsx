import { CheckCircle2, GitPullRequest, Plug } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { EmployeeModal } from "../components/Modals";
import { Avatar, Bar, Card, PillButton, StatusPill } from "../components/ui";
import type { EmployeeScores, Summary } from "../types";

interface ProgressRow { task_id: string; title: string; status: string; progress_pct: number; owner: string | null; incomplete_prerequisites: string[]; blockers: string[] }

export function WorkforceView({ summary, reload, toast }: { summary: Summary; reload: () => void; toast: (m: string, k?: "ok" | "err") => void }) {
  const [progress, setProgress] = useState<{ velocity_pct: number; completed: number; total: number; tasks: ProgressRow[] } | null>(null);
  const [selected, setSelected] = useState<EmployeeScores | null>(null);
  const [ev, setEv] = useState({ employee_id: "EMP-03", source_system: "GitHub", external_id: "gh-pr-5001", pr_review_score: 92, defect_rate: 1, summary: "Reviewed tenant-isolation PR; suggestions adopted" });

  useEffect(() => { api("/progress").then(setProgress).catch(() => {}); }, [summary]);
  useEffect(() => {
    if (selected) setSelected(summary.employees.find((e) => e.employee_id === selected.employee_id) ?? null);
  }, [summary]); // eslint-disable-line react-hooks/exhaustive-deps

  const ingest = async () => {
    try {
      const r = await api<{ status: string }>("/integrations/events", { body: ev });
      toast(r.status === "DUPLICATE_IGNORED" ? "Duplicate event ignored (idempotent intake)." : "Evidence ingested and audited.");
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const accept = async (taskId: string) => {
    try {
      await api(`/tasks/${taskId}/accept`, { body: {} });
      toast(`${taskId} deliverable accepted → COMPLETED_AND_AUDITED`);
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <Card title="Progress monitoring" action={progress && <span className="text-[11px] text-slate-400">Agent 4 · velocity {progress.velocity_pct}% · {progress.completed}/{progress.total} done</span>}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-[13px]">
              <thead className="text-[12px] text-slate-500"><tr className="border-b border-slate-100"><th className="py-2 font-medium">Task</th><th className="font-medium">Owner</th><th className="w-40 font-medium">Progress</th><th className="font-medium">Status</th><th className="font-medium">Blockers</th><th /></tr></thead>
              <tbody>
                {progress?.tasks.map((t) => (
                  <tr key={t.task_id} className="border-b border-slate-50">
                    <td className="py-2.5"><div className="font-medium text-slate-800">{t.task_id}</div><div className="max-w-[220px] truncate text-[11px] text-slate-400">{t.title}</div></td>
                    <td className="text-slate-600">{t.owner ?? "—"}</td>
                    <td><div className="flex items-center gap-2"><Bar value={t.progress_pct} color="bg-emerald-400" /><span className="text-[11px] text-slate-500">{t.progress_pct}%</span></div></td>
                    <td><StatusPill status={t.status} /></td>
                    <td className="text-[11px] text-rose-500">{t.blockers.join("; ") || (t.incomplete_prerequisites.length ? <span className="text-slate-400">waits on {t.incomplete_prerequisites.join(", ")}</span> : "—")}</td>
                    <td>{t.status === "DELIVERABLE_IN_REVIEW" && <PillButton variant="success" onClick={() => accept(t.task_id)}><CheckCircle2 size={13} />Accept</PillButton>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Plug size={16} className="text-sky-500" />Authorized evidence adapters</span>}>
          <p className="mb-3 text-[12px] text-slate-500">GitHub / Jira / Calendar signals arrive as verified outcomes (review quality, defect rate, meeting load). Raw commit counts, LOC and online status are never ingested. Duplicate deliveries are ignored.</p>
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <select value={ev.source_system} onChange={(e) => setEv({ ...ev, source_system: e.target.value })} className="rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none"><option>GitHub</option><option>Jira</option><option>Calendar</option></select>
              <select value={ev.employee_id} onChange={(e) => setEv({ ...ev, employee_id: e.target.value })} className="rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none">
                {summary.employees.map((e) => <option key={e.employee_id} value={e.employee_id}>{e.name}</option>)}</select>
            </div>
            <input value={ev.external_id} onChange={(e) => setEv({ ...ev, external_id: e.target.value })} placeholder="External id (PR / issue / event)" className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" />
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[11px] text-slate-500">Review quality<input type="number" min={0} max={100} value={ev.pr_review_score} onChange={(e) => setEv({ ...ev, pr_review_score: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" /></label>
              <label className="text-[11px] text-slate-500">Defect rate %<input type="number" min={0} max={100} value={ev.defect_rate} onChange={(e) => setEv({ ...ev, defect_rate: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" /></label>
            </div>
            <input value={ev.summary} onChange={(e) => setEv({ ...ev, summary: e.target.value })} className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" />
            <PillButton variant="primary" onClick={ingest}><GitPullRequest size={13} />Ingest evidence event</PillButton>
          </div>
        </Card>
      </div>

      <Card title="People">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {summary.employees.map((e) => (
            <button key={e.employee_id} onClick={() => setSelected(e)} className="rounded-xl border border-slate-100 p-4 text-left transition hover:shadow-md">
              <div className="flex items-center gap-3"><Avatar name={e.name} id={e.employee_id} size={40} />
                <div className="min-w-0"><div className="truncate text-[13px] font-semibold text-slate-800">{e.name}</div><div className="truncate text-[11px] text-slate-400">{e.designation}</div></div></div>
              <div className="mt-3 flex flex-wrap gap-1">{e.skills.map((s) => <span key={s.skill_name} className={`rounded px-1.5 py-0.5 text-[10px] ${s.is_verified ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{s.skill_name}</span>)}</div>
              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500"><span>{e.free_capacity_hrs}h free · {e.workload_score}%</span><StatusPill status={e.status} /></div>
            </button>
          ))}
        </div>
      </Card>
      <EmployeeModal employee={selected} onClose={() => setSelected(null)} onChanged={reload} isAdmin />
    </div>
  );
}
