import { BadgeCheck, CalendarClock, MessageSquareWarning, Send, ShieldAlert, Sprout, Target } from "lucide-react";
import { AssistantPanel } from "../components/AssistantPanel";
import { ProjectProgressCard } from "../components/ProgressDonut";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ScoreGrid } from "../components/Modals";
import { Card, Empty, PillButton, PriorityBadge, Ring, StatusPill } from "../components/ui";
import type { ChangeRequest, EmployeeScores, Nav, ProjectProgress, Task } from "../types";

interface Portal {
  scores: EmployeeScores;
  tasks: Task[];
  workload: { committed_hrs: number; free_capacity_hrs: number; utilization_pct: number; is_overloaded: boolean };
  evidence: {
    accepted_deliverables: number; rework_total: number; complexity_weighted_output: number;
    deliverables: { id: string; task_id: string; accepted: boolean; rework_count: number; complexity_weight: number }[];
    integration_events: { id: string; source_system: string; summary: string; pr_review_score: number | null }[];
    excluded_signals: string[];
  };
  growth: { skill: string; recommendation: string }[];
  change_requests: ChangeRequest[];
}

export function StaffPortal({ toast, projects, reload, onNav, refreshKey }: { toast: (m: string, k?: "ok" | "err") => void; projects: ProjectProgress[]; reload: () => void; onNav: Nav; refreshKey: unknown }) {
  const [data, setData] = useState<Portal | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [dispute, setDispute] = useState("");
  const [progress, setProgress] = useState<Record<string, number>>({});

  const [req, setReq] = useState({ kind: "reassignment", task_id: "", details: "" });
  const load = useCallback(() => api<Portal>("/me/portal").then(setData).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load, refreshKey]);

  if (err) return <Empty>{err}</Empty>;
  if (!data) return <div className="p-10 text-center text-sm text-slate-400">Loading your portal…</div>;
  const s = data.scores;

  const saveProgress = async (t: Task) => {
    const pct = progress[t.id] ?? t.progress_pct;
    try {
      await api(`/tasks/${t.id}/progress`, { body: { progress_pct: pct, status: pct >= 100 ? "DELIVERABLE_IN_REVIEW" : "IN_PROGRESS" } });
      toast(pct >= 100 ? `${t.id} submitted for review` : `${t.id} progress saved (${pct}%)`);
      load();
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const fileDispute = async () => {
    try {
      await api("/employees/dispute", { body: { reason: dispute } });
      setDispute("");
      toast("Dispute filed — your manager will review it. It is recorded in the audit ledger.");
      load();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const sendRequest = async () => {
    try {
      await api("/change-requests", { body: { kind: req.kind, task_id: req.task_id || null, details: req.details } });
      setReq({ ...req, details: "" });
      toast("Request sent to your manager. Nothing changes until they approve it.");
      load();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <div className="min-w-0 space-y-5">
        <AssistantPanel isAdmin={false} projects={projects} reload={() => { load(); reload(); }} onNav={onNav} height={260} />
        {projects.length > 0 && <div className="grid gap-4 sm:grid-cols-2">{projects.map((p) => <ProjectProgressCard key={p.project_id} p={p} onNav={onNav} />)}</div>}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-[13px] text-slate-500">Employee Intelligence Portal</div>
              <h1 className="text-2xl font-semibold text-slate-800">{s.name}</h1>
              <div className="mt-1 text-[13px] text-slate-500">{s.designation} · {s.department} · reports to {s.manager}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className={`rounded-full px-3 py-1.5 text-[12px] font-medium ${s.sufficient_evidence ? "bg-brand-50 text-brand-700" : "bg-violet-50 text-violet-700"}`}>{s.level}</span>
              <StatusPill status={s.status} />
            </div>
          </div>
          <div className="mt-5"><ScoreGrid e={s} suitability={data.tasks.find((t) => t.suitability_score != null)?.suitability_score ?? null} /></div>
          <p className="mt-3 text-[11px] text-slate-400">These six scores are kept separate on purpose. Task suitability is computed per task by the allocation engine — see “Why me?” on each task.</p>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Target size={16} className="text-brand-500" />My assigned tasks</span>}>
          <div className="space-y-3">
            {data.tasks.length === 0 && <Empty>No tasks assigned yet. Your manager will run the allocation.</Empty>}
            {data.tasks.map((t) => {
              const locked = ["PENDING_HITL_APPROVAL", "AT_RISK_DISRUPTED", "REALLOCATION_PROPOSED", "COMPLETED_AND_AUDITED", "DELIVERABLE_IN_REVIEW"].includes(t.status);
              return (
                <div key={t.id} className="rounded-xl border border-slate-100 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2"><span className="text-[12px] font-semibold text-brand-600">{t.id}</span><PriorityBadge priority={t.priority} /></div>
                    <StatusPill status={t.status} />
                  </div>
                  <div className="mt-1 text-[14px] font-semibold text-slate-800">{t.title}</div>
                  <div className="text-[12px] text-slate-500">{t.description}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
                    <span className="flex items-center gap-1"><CalendarClock size={12} />Due day {t.deadline_days}</span>
                    <span>· {t.estimated_hours}h</span><span>· Deliverable: {t.deliverable_criteria}</span>
                  </div>
                  {t.dependency_status && t.dependency_status.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {t.dependency_status.map((d) => (
                        <span key={d.task_id} className={`rounded px-1.5 py-0.5 text-[10px] ${d.status === "COMPLETED_AND_AUDITED" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                          ⟵ {d.task_id}: {d.status === "COMPLETED_AND_AUDITED" ? "done" : "in flight"}
                        </span>
                      ))}
                    </div>
                  )}
                  {t.why_me && <p className="mt-3 rounded-lg bg-brand-50/60 p-2.5 text-[11px] leading-relaxed text-slate-600"><b className="text-brand-700">Why me? </b>{t.why_me}</p>}
                  {!locked && (
                    <div className="mt-3 flex items-center gap-3">
                      <input type="range" min={0} max={100} step={5} value={progress[t.id] ?? t.progress_pct} onChange={(e) => setProgress({ ...progress, [t.id]: Number(e.target.value) })} className="flex-1 accent-emerald-500" />
                      <span className="w-10 text-right text-[12px] font-medium text-slate-700">{progress[t.id] ?? t.progress_pct}%</span>
                      <PillButton variant="primary" onClick={() => saveProgress(t)}>{(progress[t.id] ?? t.progress_pct) >= 100 ? "Submit" : "Update"}</PillButton>
                    </div>
                  )}
                  {t.status === "PENDING_HITL_APPROVAL" && <p className="mt-2 text-[11px] text-orange-600">Awaiting manager approval before you can start.</p>}
                </div>
              );
            })}
          </div>
        </Card>

        <Card title="Verified evidence">
          <div className="grid gap-3 md:grid-cols-3">
            <Stat label="Accepted deliverables" value={data.evidence.accepted_deliverables} />
            <Stat label="Rework cycles" value={data.evidence.rework_total} />
            <Stat label="Complexity-weighted output" value={data.evidence.complexity_weighted_output} />
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {s.skills.map((sk) => (
              <div key={sk.skill_name} className="flex items-start gap-2 rounded-xl bg-slate-50 p-3">
                {sk.is_verified ? <BadgeCheck size={16} className="mt-0.5 text-emerald-500" /> : <ShieldAlert size={16} className="mt-0.5 text-amber-500" />}
                <div><div className="text-[13px] font-medium text-slate-800">{sk.skill_name} · {sk.level}</div><div className="text-[11px] text-slate-500">{sk.evidence_source}</div></div>
              </div>
            ))}
            {data.evidence.integration_events.map((e) => (
              <div key={e.id} className="rounded-xl border border-slate-100 p-3 text-[12px] text-slate-600"><b className="text-slate-700">{e.source_system}:</b> {e.summary}</div>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-slate-400">Never used for evaluation: {data.evidence.excluded_signals.join(", ")}.</p>
        </Card>
      </div>

      <aside className="space-y-5">
        <Card title="My workload">
          <div className="flex items-center gap-4">
            <Ring value={data.workload.utilization_pct} size={84} stroke={8} color={data.workload.is_overloaded ? "#ef4444" : "#2f80ed"} />
            <div className="text-[12px] text-slate-500">
              <div><b className="text-slate-800">{data.workload.free_capacity_hrs}h</b> free this week</div>
              <div>{s.committed_hrs}h committed · {s.meeting_hrs}h meetings</div>
              {data.workload.is_overloaded && <div className="mt-1 text-rose-500">Above the 85% sustainability threshold</div>}
            </div>
          </div>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Sprout size={16} className="text-emerald-500" />Growth plan</span>}>
          <div className="mb-2 flex flex-wrap gap-1">{s.learning_goals.map((g) => <span key={g} className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">{g}</span>)}</div>
          {data.growth.length ? data.growth.map((g) => <p key={g.skill} className="text-[12px] text-slate-600">↗ {g.recommendation}</p>)
            : <p className="text-[12px] text-slate-400">No open demand for your learning goals right now.</p>}
        </Card>

        <Card title={<span className="flex items-center gap-2"><Send size={15} className="text-brand-500" />Request a change</span>}>
          <label className="block text-[12px] text-slate-600">Type<select value={req.kind} onChange={(e) => setReq({ ...req, kind: e.target.value })} className="field"><option value="reassignment">Reassignment</option><option value="deadline_change">Deadline change</option><option value="leave">Leave</option></select></label>
          {req.kind !== "leave" && <label className="mt-2 block text-[12px] text-slate-600">Task<select value={req.task_id} onChange={(e) => setReq({ ...req, task_id: e.target.value })} className="field"><option value="">Choose a task</option>{data.tasks.map((t) => <option key={t.id} value={t.id}>{t.id}</option>)}</select></label>}
          <label className="mt-2 block text-[12px] text-slate-600">Details<textarea rows={2} value={req.details} onChange={(e) => setReq({ ...req, details: e.target.value })} className="field" /></label>
          <PillButton variant="primary" className="mt-2" disabled={req.details.trim().length < 3 || (req.kind !== "leave" && !req.task_id)} onClick={sendRequest}>Send to manager</PillButton>
          {data.change_requests.slice(0, 4).map((r) => <p key={r.id} className="mt-2 border-t border-slate-50 pt-2 text-[11px] text-slate-500"><b className="capitalize">{r.kind.replace("_", " ")}</b>: {r.status}{r.resolution ? `. ${r.resolution}` : ""}</p>)}
        </Card>

        <Card title={<span className="flex items-center gap-2"><MessageSquareWarning size={16} className="text-amber-500" />Review & dispute</span>}>
          <p className="text-[12px] text-slate-500">Think a skill level or metric is wrong? File a dispute — a manager must review it, and it is logged in the audit ledger.</p>
          {s.dispute_status !== "None" && <div className="mt-2 rounded-lg bg-amber-50 p-2 text-[12px] text-amber-700">Current: {s.dispute_status}</div>}
          <textarea value={dispute} onChange={(e) => setDispute(e.target.value)} rows={3} placeholder="Describe what is inaccurate and point to evidence…"
            className="mt-3 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] outline-none focus:border-brand-500" />
          <PillButton variant="primary" className="mt-2" disabled={dispute.trim().length < 5 || s.dispute_status === "Pending Manager Review"} onClick={fileDispute}>File dispute</PillButton>
        </Card>
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl border border-slate-100 p-3"><div className="text-xl font-bold text-slate-800">{value}</div><div className="text-[11px] text-slate-500">{label}</div></div>;
}
