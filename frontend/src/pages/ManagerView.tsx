import { ArrowRight, CheckCircle2, FlaskConical, Play, Sparkles, UserX, XCircle, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import { CandidateModal } from "../components/Modals";
import { Avatar, Bar, Card, Empty, FACTOR_LABELS, PillButton, PriorityBadge, StatusPill } from "../components/ui";
import type { Allocation, Approval, Summary, Task } from "../types";

interface DraftTask {
  key: string;
  title: string;
  required_skills: Record<string, string>;
  estimated_hours: number;
  priority: string;
  deadline_days: number;
  depends_on_keys: string[];
  deliverable_criteria: string;
}

export function ManagerView({ summary, reload, toast }: { summary: Summary; reload: () => void; toast: (m: string, k?: "ok" | "err") => void }) {
  const [project, setProject] = useState(summary.projects[0]?.id ?? "PRJ-CRM");
  const [busy, setBusy] = useState<string | null>(null);
  const [allocs, setAllocs] = useState<Allocation[]>([]);
  const [giniDelta, setGiniDelta] = useState<{ before: number; after: number } | null>(null);
  const [inspect, setInspect] = useState<Task | null>(null);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [disruptEmp, setDisruptEmp] = useState("EMP-01");
  const [disruptStatus, setDisruptStatus] = useState<"On Leave" | "Overloaded" | "Available">("On Leave");
  const [disruptDays, setDisruptDays] = useState(3);
  const [wiTask, setWiTask] = useState("TSK-104");
  const [wiEmp, setWiEmp] = useState("EMP-03");
  const [wi, setWi] = useState<any>(null);
  const [brief, setBrief] = useState({ name: "", objective: "", priority: "High", deadline_days: 30 });
  const [drafts, setDrafts] = useState<{ draft_tasks: DraftTask[]; source: string; total_effort_hrs: number; feasibility: string } | null>(null);

  const tasks = summary.tasks.filter((t) => t.project_id === project);
  const empName = (id: string | null) => summary.employees.find((e) => e.employee_id === id)?.name ?? "—";
  const levels = useMemo(() => dagLevels(tasks), [tasks]);
  const assignmentFor = (taskId: string) => [...summary.assignments].reverse().find((a) => a.task_id === taskId && a.status !== "RELEASED");

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try {
      await fn();
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(null);
      reload();
    }
  };

  const allocate = () => run("alloc", async () => {
    const r = await api<{ allocations: Allocation[]; allocated_count: number; gini_before: number; gini_after: number }>("/tasks/allocate-all", { body: {} });
    setAllocs(r.allocations);
    setGiniDelta({ before: r.gini_before, after: r.gini_after });
    toast(`Allocated ${r.allocated_count} task(s). Gini ${r.gini_before} → ${r.gini_after}`);
  });

  const decide = (a: Approval, approve: boolean) => run(a.approval_id, async () => {
    const r = await api<{ status: string }>(`/approvals/${a.approval_id}/${approve ? "approve" : "reject"}`, { body: { comments: comments[a.approval_id] || null } });
    toast(`${a.approval_id}: ${r.status.replace(/_/g, " ")}`);
  });

  const disrupt = () => run("disrupt", async () => {
    const r = await api<{ proposals_created: unknown[]; disrupted_employee: string }>("/disruptions/simulate", {
      body: { employee_id: disruptEmp, new_status: disruptStatus, leave_days: disruptDays, reason: "Simulated from PM console" },
    });
    toast(`${r.disrupted_employee} → ${disruptStatus}. ${r.proposals_created.length} reallocation proposal(s) queued for approval.`);
  });

  const whatIf = () => run("whatif", async () => setWi(await api("/simulate/what-if", { body: { task_id: wiTask, employee_id: wiEmp } })));

  const analyze = () => run("analyze", async () => setDrafts(await api("/projects/analyze", { body: brief })));
  const createProject = () => run("create", async () => {
    const r = await api<{ project: { id: string }; tasks: Task[] }>("/projects", { body: brief });
    setProject(r.project.id);
    setDrafts(null);
    setBrief({ name: "", objective: "", priority: "High", deadline_days: 30 });
    toast(`Project ${r.project.id} created with ${r.tasks.length} DAG tasks. Run allocation next.`);
  });

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <Card title="Project DAG & allocation"
          action={<div className="flex items-center gap-2">
            <select value={project} onChange={(e) => setProject(e.target.value)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs outline-none">
              {summary.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <PillButton variant="primary" disabled={busy === "alloc"} onClick={allocate}><Play size={13} />{busy === "alloc" ? "Allocating…" : "Run AI allocation"}</PillButton>
          </div>}>
          {giniDelta && (
            <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl bg-emerald-50 px-4 py-2.5 text-[13px] text-emerald-700">
              <Sparkles size={15} /> Workload Gini improved {giniDelta.before} <ArrowRight size={13} /> <b>{giniDelta.after}</b>
              <span className="text-emerald-600/70">— Critical or &gt;85% load assignments routed to HITL approval</span>
            </div>
          )}
          <div className="overflow-x-auto pb-2">
            <div className="flex min-w-max gap-4">
              {levels.map((col, i) => (
                <div key={i} className="w-[220px] space-y-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Stage {i + 1}</div>
                  {col.map((t) => {
                    const asg = assignmentFor(t.id);
                    return (
                      <button key={t.id} onClick={() => setInspect(t)} className="w-full rounded-xl border border-slate-100 bg-white p-3 text-left shadow-sm transition hover:border-brand-500/40 hover:shadow-md">
                        <div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold text-brand-600">{t.id}</span><PriorityBadge priority={t.priority} /></div>
                        <div className="mt-1 line-clamp-2 text-[13px] font-medium leading-snug text-slate-800">{t.title}</div>
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {t.dependencies.map((d) => <span key={d} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">⟵ {d}</span>)}
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{t.estimated_hours}h</span>
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          {t.assigned_to ? <span className="flex items-center gap-1.5 text-[11px] text-slate-600"><Avatar name={empName(t.assigned_to)} id={t.assigned_to} size={20} />{empName(t.assigned_to).split(" ")[0]}</span>
                            : <span className="text-[11px] text-slate-400">Unassigned</span>}
                          {asg && <span className="text-[11px] font-semibold text-slate-700">{asg.suitability_score}</span>}
                        </div>
                        <div className="mt-2"><StatusPill status={t.status} /></div>
                      </button>
                    );
                  })}
                </div>
              ))}
              {!tasks.length && <Empty>No tasks in this project</Empty>}
            </div>
          </div>
        </Card>

        <Card title={`HITL approval queue (${summary.pending_approvals.length})`}>
          <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
            {summary.pending_approvals.length === 0 && <Empty>No pending approvals. Run allocation or simulate a disruption.</Empty>}
            {summary.pending_approvals.map((a) => (
              <div key={a.approval_id} className="rounded-xl border border-orange-100 bg-orange-50/40 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-500">{a.approval_id} · {a.kind === "REALLOCATION" ? "Reallocation" : "Initial allocation"}</span>
                  <PriorityBadge priority={a.priority} />
                </div>
                <div className="mt-1 text-[13px] font-medium text-slate-800">{a.task_id} · {a.task_title}</div>
                <div className="mt-2 flex items-center gap-2 text-[12px]">
                  {a.previous_owner && <><span className="text-slate-500 line-through">{a.previous_owner}</span><ArrowRight size={12} className="text-slate-400" /></>}
                  {a.recommended_new_owner_name ? <><Avatar name={a.recommended_new_owner_name} id={a.recommended_new_owner_id!} size={22} /><b className="text-slate-800">{a.recommended_new_owner_name}</b>
                    <span className="text-slate-500">· {a.suitability_score} · {a.post_utilization_pct}% load</span></> : <b className="text-rose-600">Escalation — no eligible candidate</b>}
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-slate-600">{a.explanation}</p>
                <input value={comments[a.approval_id] ?? ""} onChange={(e) => setComments({ ...comments, [a.approval_id]: e.target.value })}
                  placeholder="Manager comment (optional)" className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] outline-none focus:border-brand-500" />
                <div className="mt-2 flex gap-2">
                  <PillButton variant="success" disabled={!!busy || !a.recommended_new_owner_id} onClick={() => decide(a, true)}><CheckCircle2 size={13} />Approve</PillButton>
                  <PillButton disabled={!!busy} onClick={() => decide(a, false)}><XCircle size={13} />Reject</PillButton>
                </div>
              </div>
            ))}
            {summary.decided_approvals.length > 0 && (
              <div className="pt-2">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Recently decided</div>
                {summary.decided_approvals.slice().reverse().map((a) => (
                  <div key={a.approval_id} className="flex items-center justify-between border-b border-slate-50 py-1.5 text-[12px]">
                    <span className="text-slate-600">{a.task_id} → {a.recommended_new_owner_name ?? "—"}</span><StatusPill status={a.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {allocs.length > 0 && (
        <Card title="Explainable allocation cards" action={<span className="text-[11px] text-slate-400">Agent 3 · deterministic engine</span>}>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {allocs.map((a) => (
              <div key={a.task_id} className="rounded-xl border border-slate-100 p-4">
                <div className="flex items-center justify-between"><span className="text-[11px] font-semibold text-brand-600">{a.task_id}</span><StatusPill status={a.status} /></div>
                <div className="mt-1 text-[13px] font-medium text-slate-800">{a.task_title}</div>
                {a.recommended && (
                  <>
                    <div className="mt-3 flex items-center gap-2"><Avatar name={a.recommended.employee_name} id={a.recommended.employee_id} size={30} />
                      <div><div className="text-[13px] font-semibold text-slate-800">{a.recommended.employee_name}</div><div className="text-[11px] text-slate-500">Score {a.recommended.suitability_score} · {a.recommended.utilization_after_pct}% load</div></div></div>
                    <div className="mt-3 space-y-1.5">
                      {Object.entries(a.recommended.factor_breakdown).map(([k, v]) => (
                        <div key={k} className="grid grid-cols-[100px_1fr_34px] items-center gap-2 text-[10px] text-slate-500"><span>{FACTOR_LABELS[k]}</span><Bar value={v} /><span className="text-right">{v}</span></div>
                      ))}
                    </div>
                  </>
                )}
                <p className="mt-3 text-[11px] leading-relaxed text-slate-500">{a.explanation}</p>
                <button onClick={() => setInspect(summary.tasks.find((t) => t.id === a.task_id) ?? null)} className="mt-2 text-[11px] font-medium text-brand-600 hover:underline">Inspect all candidates →</button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title={<span className="flex items-center gap-2"><Zap size={16} className="text-rose-500" />One-click disruption</span>}>
          <p className="mb-3 text-[12px] text-slate-500">Agent 6 detects the change, classifies risk on the DAG, and Agent 7 proposes cascade reassignments for approval.</p>
          <label className="text-[12px] text-slate-600">Employee</label>
          <select value={disruptEmp} onChange={(e) => setDisruptEmp(e.target.value)} className="mb-2 mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none">
            {summary.employees.map((e) => <option key={e.employee_id} value={e.employee_id}>{e.name} ({e.status}, {e.workload_score}%)</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="text-[12px] text-slate-600">New status</label>
              <select value={disruptStatus} onChange={(e) => setDisruptStatus(e.target.value as any)} className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none">
                <option>On Leave</option><option>Overloaded</option><option>Available</option></select></div>
            <div><label className="text-[12px] text-slate-600">Leave days</label>
              <input type="number" min={1} max={60} value={disruptDays} onChange={(e) => setDisruptDays(Number(e.target.value))} className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" /></div>
          </div>
          <PillButton variant="danger" className="mt-3" disabled={busy === "disrupt"} onClick={disrupt}><UserX size={13} />Trigger disruption</PillButton>
        </Card>

        <Card title={<span className="flex items-center gap-2"><FlaskConical size={16} className="text-violet-500" />What-if simulator</span>}>
          <p className="mb-3 text-[12px] text-slate-500">Counterfactual: score a specific person for a task without changing anything.</p>
          <div className="grid grid-cols-2 gap-2">
            <select value={wiTask} onChange={(e) => setWiTask(e.target.value)} className="rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none">
              {summary.tasks.map((t) => <option key={t.id} value={t.id}>{t.id}</option>)}</select>
            <select value={wiEmp} onChange={(e) => setWiEmp(e.target.value)} className="rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none">
              {summary.employees.map((e) => <option key={e.employee_id} value={e.employee_id}>{e.name}</option>)}</select>
          </div>
          <PillButton variant="primary" className="mt-3" disabled={busy === "whatif"} onClick={whatIf}>Simulate</PillButton>
          {wi && (
            <div className="mt-3 rounded-xl bg-slate-50 p-3 text-[12px] text-slate-600">
              <div className="font-semibold text-slate-800">{wi.candidate.employee_name} on {wi.task_id}: {wi.candidate.suitability_score} (rank #{wi.rank})</div>
              <div>Post-load {wi.candidate.utilization_after_pct}% · Gini {wi.gini_before} → {wi.gini_after}</div>
              <div>Best alternative: {wi.best_alternative.employee_name} ({wi.best_alternative.suitability_score})</div>
              <div className={wi.candidate.eligible ? "text-emerald-600" : "text-rose-600"}>{wi.verdict}</div>
            </div>
          )}
        </Card>

        <Card title={<span className="flex items-center gap-2"><Sparkles size={16} className="text-brand-500" />Project brief → DAG</span>}>
          <input value={brief.name} onChange={(e) => setBrief({ ...brief, name: e.target.value })} placeholder="Project name" className="mb-2 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" />
          <textarea value={brief.objective} onChange={(e) => setBrief({ ...brief, objective: e.target.value })} rows={3}
            placeholder="Business objective, e.g. Build a customer portal and dashboard with AI churn prediction…" className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" />
          <div className="mt-2 grid grid-cols-2 gap-2">
            <select value={brief.priority} onChange={(e) => setBrief({ ...brief, priority: e.target.value })} className="rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none">
              {["Low", "Medium", "High", "Critical"].map((p) => <option key={p}>{p}</option>)}</select>
            <input type="number" min={3} max={365} value={brief.deadline_days} onChange={(e) => setBrief({ ...brief, deadline_days: Number(e.target.value) })} className="rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none" />
          </div>
          <div className="mt-3 flex gap-2">
            <PillButton disabled={!brief.name || brief.objective.length < 10 || !!busy} onClick={analyze}>Analyze (Agent 1)</PillButton>
            <PillButton variant="primary" disabled={!drafts || !!busy} onClick={createProject}>Approve & create</PillButton>
          </div>
          {drafts && (
            <div className="mt-3 space-y-1.5 rounded-xl bg-slate-50 p-3">
              <div className="text-[11px] text-slate-500">Source: {drafts.source} · {drafts.total_effort_hrs}h total · <b className={drafts.feasibility === "OK" ? "text-emerald-600" : "text-rose-600"}>{drafts.feasibility}</b></div>
              {drafts.draft_tasks.map((d) => (
                <div key={d.key} className="text-[12px] text-slate-700">• {d.title} <span className="text-slate-400">({d.estimated_hours}h, {d.priority}{d.depends_on_keys.length ? `, after ${d.depends_on_keys.join("+")}` : ""})</span></div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <CandidateModal task={inspect} onClose={() => setInspect(null)} />
    </div>
  );
}

/** Group tasks into columns by dependency depth for a left-to-right DAG view. */
function dagLevels(tasks: Task[]): Task[][] {
  const byId = new Map(tasks.map((t) => [t.id, t]));
  const depth = new Map<string, number>();
  const visit = (t: Task, seen = new Set<string>()): number => {
    if (depth.has(t.id)) return depth.get(t.id)!;
    if (seen.has(t.id)) return 0;
    seen.add(t.id);
    const d = t.dependencies.reduce((m, id) => (byId.has(id) ? Math.max(m, visit(byId.get(id)!, seen) + 1) : m), 0);
    depth.set(t.id, d);
    return d;
  };
  tasks.forEach((t) => visit(t));
  const cols: Task[][] = [];
  tasks.forEach((t) => (cols[depth.get(t.id)!] ??= []).push(t));
  return cols.filter(Boolean);
}
