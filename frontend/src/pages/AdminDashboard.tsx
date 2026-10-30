import { Bot, Brain, FolderKanban, GitBranch, Plug, Radar, Scale, ScrollText, Users } from "lucide-react";
import { AssistantPanel } from "../components/AssistantPanel";
import { ProjectProgressCard } from "../components/ProgressDonut";
import { useEffect, useMemo, useState } from "react";
import { Bar as RBar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ProjectDonut } from "../components/ProjectDonut";
import { Avatar, Card, Empty, FACTOR_LABELS, PillButton, Ring, StatusPill } from "../components/ui";
import type { Nav, ProjectProgress, Risk, SkillGap, Summary, Weights } from "../types";

const TILES = [
  { key: "projects", label: "Project Management", icon: FolderKanban, bg: "bg-tile-yellow", fg: "text-amber-700" },
  { key: "workforce", label: "Workforce Intelligence", icon: Users, bg: "bg-tile-blue", fg: "text-sky-700" },
  { key: "manager", label: "Task Allocation", icon: GitBranch, bg: "bg-tile-teal", fg: "text-teal-700" },
  { key: "risks", label: "Risk Radar", icon: Radar, bg: "bg-tile-peach", fg: "text-orange-700" },
  { key: "workforce", label: "Performance Evaluation", icon: Brain, bg: "bg-tile-lilac", fg: "text-violet-700" },
  { key: "settings", label: "Integrations", icon: Plug, bg: "bg-tile-blue", fg: "text-sky-700" },
  { key: "coordinator", label: "AI Coordinator", icon: Bot, bg: "bg-tile-mint", fg: "text-emerald-700" },
  { key: "audit", label: "Audit Ledger", icon: ScrollText, bg: "bg-tile-yellow", fg: "text-amber-700" },
];

const DEPT_COLORS = ["#2f80ed", "#22c3d6", "#34c38f", "#f6a03b", "#e8577a", "#8b5cf6"];

export function AdminDashboard({ summary, projects, reload, onNav, toast }: { summary: Summary; projects: ProjectProgress[]; reload: () => void; onNav: Nav; toast: (m: string, k?: "ok" | "err") => void }) {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [gaps, setGaps] = useState<SkillGap[]>([]);
  const [weights, setWeights] = useState<Weights>(summary.weights);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState("All");

  useEffect(() => {
    api<{ risks: Risk[] }>("/risks").then((r) => setRisks(r.risks)).catch(() => {});
    api<{ gaps: SkillGap[] }>("/skills/gaps").then((r) => setGaps(r.gaps)).catch(() => {});
  }, [summary]);
  useEffect(() => setWeights(summary.weights), [summary.weights]);

  const departments = useMemo(() => {
    const m = new Map<string, { cap: number; used: number }>();
    summary.employees.forEach((e) => {
      const d = m.get(e.department) ?? { cap: 0, used: 0 };
      d.cap += e.weekly_capacity_hrs;
      d.used += e.weekly_capacity_hrs - e.free_capacity_hrs;
      m.set(e.department, d);
    });
    return [...m.entries()].map(([name, d]) => ({ name, pct: Math.round((d.used / d.cap) * 100) }));
  }, [summary]);

  const weightSum = Object.values(weights).reduce((a, b) => a + b, 0);
  const saveWeights = async () => {
    setSaving(true);
    try {
      await api("/admin/weights", { body: weights });
      toast("Scoring weights saved and audited. Re-run allocation to apply.");
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setSaving(false);
    }
  };
  const normalize = () => {
    const s = weightSum || 1;
    const keys = Object.keys(weights) as (keyof Weights)[];
    const out = Object.fromEntries(keys.map((k) => [k, Math.round((weights[k] / s) * 100) / 100])) as unknown as Weights;
    const diff = Math.round((1 - Object.values(out).reduce((a, b) => a + b, 0)) * 100) / 100;
    out.skill_match = Math.round((out.skill_match + diff) * 100) / 100;
    setWeights(out);
  };

  const activeStaff = summary.employees.filter((e) => e.status !== "Inactive");
  const util = activeStaff.map((e) => ({ name: e.name.split(" ")[0], value: e.workload_score, status: e.status }));
  const avgUtil = Math.round(summary.employees.filter((e) => e.status !== "On Leave").reduce((a, e) => a + e.workload_score, 0) /
    Math.max(1, summary.employees.filter((e) => e.status !== "On Leave").length));
  const fairness = Math.round((1 - summary.workload_gini_index) * 100);
  const depts = ["All", ...new Set(summary.employees.map((e) => e.department))];
  const shown = summary.employees.filter((e) => filter === "All" || e.department === filter);

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
      <div className="min-w-0 space-y-5">
        <AssistantPanel isAdmin projects={projects} reload={reload} onNav={onNav} height={300} />

        <Card title="Project progress" action={<PillButton onClick={() => onNav("projects")}>View all</PillButton>}>
          {projects.length === 0 ? <p className="text-[13px] text-slate-400">No active projects.</p> : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{projects.slice(0, 6).map((p) => <ProjectProgressCard key={p.project_id} p={p} onNav={onNav} />)}</div>
          )}
        </Card>

        <Card title="Modules">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {TILES.map((t) => (
              <button key={t.label} onClick={() => onNav(t.key)} className={`flex items-center gap-3 rounded-xl ${t.bg} px-4 py-4 text-left transition hover:-translate-y-0.5 hover:shadow-md`}>
                <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white/70 ${t.fg}`}><t.icon size={22} /></span>
                <span className="text-[13px] font-medium leading-tight text-slate-700">{t.label}</span>
              </button>
            ))}
          </div>
        </Card>

        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <Card><ProjectDonut tasks={summary.tasks} employees={summary.employees} /></Card>

          <Card title="Workload distribution" action={<span className="text-[11px] text-slate-400">Guardrails: 85% HITL · 95% hard ceiling</span>}>
            <div className="mb-3 grid grid-cols-3 gap-3">
              <Kpi label="Workload Gini" value={summary.workload_gini_index.toFixed(4)} sub="0 = perfectly even" />
              <Kpi label="Overloaded (>85%)" value={summary.overloaded_count} sub={`${summary.on_leave_count} on leave`} />
              <Kpi label="Team free hours" value={`${summary.team_free_hrs}h`} sub="net of meetings & leave" />
            </div>
            <div className="h-[230px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={util} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} interval={0} angle={-30} textAnchor="end" height={45} />
                  <YAxis domain={[0, 110]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v: number) => [`${v}%`, "Utilisation"]} cursor={{ fill: "#f8fafc" }} />
                  <ReferenceLine y={85} stroke="#f59e0b" strokeDasharray="4 4" />
                  <ReferenceLine y={95} stroke="#ef4444" strokeDasharray="4 4" />
                  <RBar dataKey="value" radius={[6, 6, 0, 0]}>
                    {util.map((u) => <Cell key={u.name} fill={u.status === "On Leave" ? "#cbd5e1" : u.value > 95 ? "#ef4444" : u.value > 85 ? "#f59e0b" : "#2f80ed"} />)}
                  </RBar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <Card title="Workforce — 6 disaggregated scores"
          action={<select value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 outline-none">{depts.map((d) => <option key={d}>{d}</option>)}</select>}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-[13px]">
              <thead className="text-[12px] text-slate-500">
                <tr className="border-b border-slate-100">
                  <th className="py-2 font-medium">Employee</th><th className="font-medium">Skill</th><th className="font-medium">Performance</th>
                  <th className="font-medium">Availability</th><th className="font-medium">Workload</th><th className="font-medium">Collab.</th>
                  <th className="font-medium">Level</th><th className="font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e) => (
                  <tr key={e.employee_id} onClick={() => onNav("employee", e.employee_id)} className="cursor-pointer border-b border-slate-50 hover:bg-slate-50/70">
                    <td className="py-2.5"><div className="flex items-center gap-2.5"><Avatar name={e.name} id={e.employee_id} size={32} />
                      <div><div className="font-medium text-slate-800">{e.name}</div><div className="text-[11px] text-slate-400">{e.designation}</div></div></div></td>
                    <td>{e.skill_score}</td>
                    <td>{e.performance_score ?? <span className="text-slate-400">—</span>}</td>
                    <td>{e.availability_score}</td>
                    <td className={e.workload_score > 85 ? "font-semibold text-rose-500" : ""}>{e.workload_score}%</td>
                    <td>{e.collaboration_score}</td>
                    <td><span className={`rounded-full px-2 py-0.5 text-[11px] ${e.sufficient_evidence ? "bg-brand-50 text-brand-700" : "bg-violet-50 text-violet-700"}`}>{e.level.replace(" (New Hire Onboarding)", "")}</span>
                      {e.dispute_status === "Pending Manager Review" && <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] text-amber-700">Dispute</span>}</td>
                    <td><StatusPill status={e.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card title={<span id="risks">Risk radar</span>} action={<span className="text-[11px] text-slate-400">Agent 6</span>}>
            <div className="space-y-2">
              {risks.length === 0 && <Empty>No active risks</Empty>}
              {risks.slice(0, 7).map((r, i) => (
                <div key={i} className="flex items-start gap-3 rounded-xl bg-slate-50 p-3">
                  <span className={`mt-0.5 rounded-md px-2 py-0.5 text-[10px] font-semibold ${r.level === "Critical" ? "bg-rose-500 text-white" : r.level === "High" ? "bg-orange-400 text-white" : "bg-amber-100 text-amber-700"}`}>{r.level}</span>
                  <div><div className="text-[12px] font-medium text-slate-700">{r.type.replace(/_/g, " ")}</div><div className="text-[12px] text-slate-500">{r.detail}</div></div>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Skill gaps & training" action={<span className="text-[11px] text-slate-400">Agent 2</span>}>
            <div className="space-y-2">
              {gaps.slice(0, 6).map((g) => (
                <div key={g.skill} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex items-center justify-between">
                    <div className="text-[13px] font-medium text-slate-800">{g.skill} <span className="text-[11px] text-slate-400">≥ {g.required_level}</span></div>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${g.severity === "Critical" ? "bg-rose-100 text-rose-600" : g.severity === "High" ? "bg-orange-100 text-orange-600" : g.severity === "Medium" ? "bg-amber-100 text-amber-700" : "bg-emerald-50 text-emerald-600"}`}>{g.severity}</span>
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">Verified: {g.verified_holders.join(", ") || "none"} · demand {g.demand_hrs}h / supply {g.supply_hrs}h</div>
                  {g.training_recommendations.slice(0, 1).map((t) => <div key={t.employee_id} className="mt-1 text-[11px] text-emerald-600">↗ {t.name}: {t.recommendation}</div>)}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <aside className="space-y-5">
        <Card title="Department capacity">
          <div className="space-y-3">
            {departments.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between text-[13px]">
                <span className="flex items-center gap-2 text-slate-600"><span className="h-2.5 w-2.5 rounded-full" style={{ background: DEPT_COLORS[i % DEPT_COLORS.length] }} />{d.name}</span>
                <span className="text-slate-500">{d.pct}%</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Targets">
          <div className="space-y-3">
            <TargetRow label="Fairness" sub="1 − Gini" value={fairness} color="#34c38f" />
            <TargetRow label="Utilisation" sub="Team average" value={avgUtil} color={avgUtil > 85 ? "#ef4444" : "#2f80ed"} />
            <TargetRow label="Approvals" sub={`${summary.pending_approvals.length} pending`} value={summary.pending_approvals.length ? 100 - Math.min(100, summary.pending_approvals.length * 15) : 100} color="#f6a03b" onClick={() => onNav("manager")} />
          </div>
        </Card>

        <Card title="Scoring weights" action={<span className={`text-[11px] font-medium ${Math.abs(weightSum - 1) < 0.001 ? "text-emerald-600" : "text-rose-500"}`}>Σ {weightSum.toFixed(2)}</span>}>
          <div className="space-y-3">
            {(Object.keys(weights) as (keyof Weights)[]).map((k) => (
              <div key={k}>
                <div className="mb-1 flex justify-between text-[12px] text-slate-600"><span>{FACTOR_LABELS[k]}</span><span className="font-medium">{Math.round(weights[k] * 100)}%</span></div>
                <input type="range" min={0} max={0.6} step={0.01} value={weights[k]} onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} className="w-full accent-brand-500" />
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <PillButton onClick={normalize}><Scale size={13} />Normalize</PillButton>
            <PillButton variant="primary" disabled={saving || Math.abs(weightSum - 1) > 0.001} onClick={saveWeights}>Save weights</PillButton>
          </div>
        </Card>

        <Card title="Ledger integrity">
          <div className={`rounded-xl p-3 text-[12px] ${summary.ledger_status.valid ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
            {summary.ledger_status.valid ? "✓ Hash chain verified" : `✗ Broken at ${summary.ledger_status.broken_at}`} · {summary.ledger_status.entries} entries
          </div>
          <PillButton className="mt-3" onClick={() => onNav("audit")}>Open ledger</PillButton>
        </Card>
      </aside>

    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: React.ReactNode; sub: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-800">{value}</div>
      <div className="text-[10px] text-slate-400">{sub}</div>
    </div>
  );
}

function TargetRow({ label, sub, value, color, onClick }: { label: string; sub: string; value: number; color: string; onClick?: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-100 p-3">
      <div className="flex items-center gap-3">
        <Ring value={value} size={44} stroke={5} color={color} />
        <div><div className="text-[13px] font-semibold text-slate-800">{label}</div><div className="text-[11px] text-slate-400">{sub}</div></div>
      </div>
      {onClick && <PillButton onClick={onClick}>View</PillButton>}
    </div>
  );
}
