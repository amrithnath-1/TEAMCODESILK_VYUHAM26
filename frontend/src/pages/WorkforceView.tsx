import { CheckCircle2, Download, GitPullRequest, Pencil, Plug, Plus, Search, UserMinus } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api, apiDownload } from "../api";
import { Avatar, Bar, Card, Modal, PillButton, StatusPill } from "../components/ui";
import type { EmployeeScores, Nav, Skill, Summary } from "../types";

interface ProgressRow { task_id: string; title: string; status: string; progress_pct: number; owner: string | null; incomplete_prerequisites: string[]; blockers: string[] }

const BLANK = { name: "", email: "", department: "Engineering", designation: "", manager: "Anil Menon", years_exp: 0, weekly_capacity_hrs: 40, meeting_hrs: 0, password: "", skills: "" };
const parseSkills = (text: string): Skill[] => text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
  const [name, level] = l.split(":").map((x) => x.trim());
  const valid = ["Beginner", "Intermediate", "Advanced", "Expert"].find((v) => v.toLowerCase() === (level ?? "").toLowerCase()) ?? "Intermediate";
  return { skill_name: name, level: valid as Skill["level"], is_verified: false, evidence_source: "Entered by manager; not yet verified" };
});

export function WorkforceView({ summary, reload, toast, onNav }: { summary: Summary; reload: () => void; toast: (m: string, k?: "ok" | "err") => void; onNav: Nav }) {
  const [progress, setProgress] = useState<{ velocity_pct: number; completed: number; total: number; tasks: ProgressRow[] } | null>(null);
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("All");
  const [editing, setEditing] = useState<EmployeeScores | "new" | null>(null);
  const [form, setForm] = useState(BLANK);
  const [ev, setEv] = useState({ employee_id: "EMP-03", source_system: "GitHub", external_id: "gh-pr-5001", pr_review_score: 92, defect_rate: 1, summary: "Reviewed tenant-isolation PR; suggestions adopted" });

  useEffect(() => { api("/progress").then(setProgress).catch(() => {}); }, [summary]);
  const openEdit = (e: EmployeeScores | "new") => {
    setEditing(e);
    setForm(e === "new" ? BLANK : { name: e.name, email: e.email, department: e.department, designation: e.designation, manager: e.manager, years_exp: e.years_exp, weekly_capacity_hrs: e.weekly_capacity_hrs, meeting_hrs: e.meeting_hrs, password: "", skills: e.skills.map((s) => `${s.skill_name}: ${s.level}`).join("\n") });
  };
  const saveEmployee = async (ev: FormEvent) => {
    ev.preventDefault();
    const { skills, password, ...fields } = form;
    try {
      if (editing === "new") {
        const r = await api<{ username: string }>("/employees", { body: { ...fields, password, skills: parseSkills(skills) } });
        toast(`Employee added. They sign in as "${r.username}".`);
      } else if (editing) {
        const known = new Map(editing.skills.map((s) => [s.skill_name, s]));
        const merged = parseSkills(skills).map((s) => { const old = known.get(s.skill_name); return old && old.level === s.level ? old : s; });
        await api(`/employees/${editing.employee_id}`, { method: "PATCH", body: { ...fields, skills: merged } });
        toast("Employee updated.");
      }
      setEditing(null);
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const deactivate = async (e: EmployeeScores) => {
    if (!confirm(`Deactivate ${e.name}? They can no longer sign in or receive tasks. Their records stay for audit.`)) return;
    try {
      await api(`/employees/${e.employee_id}`, { method: "DELETE" });
      toast(`${e.name} deactivated.`);
      reload();
    } catch (err: any) {
      toast(err.message, "err");
    }
  };
  const depts = ["All", ...new Set(summary.employees.map((e) => e.department))];
  const people = summary.employees.filter((e) => (dept === "All" || e.department === dept) && `${e.name} ${e.designation} ${e.skills.map((s) => s.skill_name).join(" ")}`.toLowerCase().includes(q.toLowerCase()));

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

      <Card title={`People (${people.length})`} action={<div className="flex flex-wrap gap-2">
        <PillButton onClick={() => apiDownload("/employees/export.csv", "employees.csv").catch((e) => toast(e.message, "err"))}><Download size={13} />Export CSV</PillButton>
        <PillButton variant="primary" onClick={() => openEdit("new")}><Plus size={13} />Add employee</PillButton>
      </div>}>
        <div className="mb-3 flex flex-wrap gap-2">
          <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-slate-500"><Search size={14} /><input aria-label="Search people" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, role or skill" className="w-full bg-transparent text-[13px] outline-none" /></label>
          <select aria-label="Filter by department" value={dept} onChange={(e) => setDept(e.target.value)} className="rounded-full border border-slate-200 px-3 py-2 text-xs outline-none">{depts.map((d) => <option key={d}>{d}</option>)}</select>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {people.map((e) => (
            <div key={e.employee_id} className={`rounded-xl border border-slate-100 p-4 transition hover:shadow-md ${e.status === "Inactive" ? "opacity-60" : ""}`}>
              <button onClick={() => onNav("employee", e.employee_id)} className="w-full text-left"><div className="flex items-center gap-3"><Avatar name={e.name} id={e.employee_id} size={40} />
                <div className="min-w-0"><div className="truncate text-[13px] font-semibold text-slate-800">{e.name}</div><div className="truncate text-[11px] text-slate-400">{e.designation}</div></div></div>
              <div className="mt-3 flex flex-wrap gap-1">{e.skills.map((s) => <span key={s.skill_name} className={`rounded px-1.5 py-0.5 text-[10px] ${s.is_verified ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{s.skill_name}</span>)}</div>
              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500"><span>{e.free_capacity_hrs}h free · {e.workload_score}%</span><StatusPill status={e.status} /></div>
              </button>
              {e.status !== "Inactive" && <div className="mt-2 flex gap-2">
                <PillButton onClick={() => openEdit(e)}><Pencil size={12} />Edit</PillButton>
                <PillButton onClick={() => deactivate(e)}><UserMinus size={12} />Deactivate</PillButton>
              </div>}
            </div>
          ))}
        </div>
      </Card>
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing === "new" ? "Add employee" : "Edit employee"}>
        <form onSubmit={saveEmployee} className="grid grid-cols-2 gap-3 text-[12px] font-medium text-slate-600">
          <label>Name<input required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="field" /></label>
          <label>Email<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="field" /></label>
          <label>Department<input required value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="field" /></label>
          <label>Designation<input required value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })} className="field" /></label>
          <label>Manager<input value={form.manager} onChange={(e) => setForm({ ...form, manager: e.target.value })} className="field" /></label>
          <label>Years of experience<input type="number" min={0} step={0.5} value={form.years_exp} onChange={(e) => setForm({ ...form, years_exp: Number(e.target.value) })} className="field" /></label>
          <label>Weekly capacity (h)<input type="number" min={1} max={60} value={form.weekly_capacity_hrs} onChange={(e) => setForm({ ...form, weekly_capacity_hrs: Number(e.target.value) })} className="field" /></label>
          <label>Meeting hours<input type="number" min={0} max={40} value={form.meeting_hrs} onChange={(e) => setForm({ ...form, meeting_hrs: Number(e.target.value) })} className="field" /></label>
          {editing === "new" && <label className="col-span-2">Temporary password (at least 8 characters)<input required minLength={8} type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="field" /></label>}
          <label className="col-span-2">Skills, one per line as “Skill: Level”<textarea rows={4} value={form.skills} onChange={(e) => setForm({ ...form, skills: e.target.value })} placeholder={"Python: Advanced\nSQL: Intermediate"} className="field" /><span className="mt-1 block text-[11px] font-normal text-slate-400">New or changed skills are saved as unverified until evidence confirms them.</span></label>
          <div className="col-span-2 flex justify-end gap-2"><PillButton onClick={() => setEditing(null)}>Cancel</PillButton><PillButton type="submit" variant="primary">Save</PillButton></div>
        </form>
      </Modal>
    </div>
  );
}
