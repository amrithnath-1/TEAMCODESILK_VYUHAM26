import { Plus, Search } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { ProjectProgressCard } from "../components/ProgressDonut";
import { Card, Empty, Modal, PillButton } from "../components/ui";
import type { Nav, ProjectProgress } from "../types";

export function ProjectsView({ isAdmin, onNav, toast, refreshKey, reload }: { isAdmin: boolean; onNav: Nav; toast: (m: string, k?: "ok" | "err") => void; refreshKey: unknown; reload: () => void }) {
  const [projects, setProjects] = useState<ProjectProgress[] | null>(null);
  const [q, setQ] = useState("");
  const [health, setHealth] = useState("All");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", objective: "", priority: "High", deadline_days: 30 });
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<ProjectProgress[]>("/projects").then(setProjects).catch((e) => toast(e.message, "err")); }, [refreshKey, toast]);

  const shown = (projects ?? []).filter((p) => p.name.toLowerCase().includes(q.toLowerCase()) && (health === "All" || p.health === health));

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const p = await api<{ id: string }>("/projects/draft", { body: form });
      setCreating(false);
      setForm({ name: "", objective: "", priority: "High", deadline_days: 30 });
      reload();
      onNav("project", p.id);
    } catch (err: any) {
      toast(err.message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card title={<span className="text-xl font-semibold">Projects</span>} action={isAdmin && <PillButton variant="primary" onClick={() => setCreating(true)}><Plus size={13} />New project</PillButton>}>
        <div className="flex flex-wrap gap-2">
          <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-slate-500">
            <Search size={14} /><input aria-label="Search projects" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search projects" className="w-full bg-transparent text-[13px] outline-none" />
          </label>
          <select aria-label="Filter by health" value={health} onChange={(e) => setHealth(e.target.value)} className="rounded-full border border-slate-200 px-3 py-2 text-xs outline-none">
            {["All", "On track", "At risk", "Off track", "Not planned", "Complete"].map((h) => <option key={h}>{h}</option>)}
          </select>
        </div>
      </Card>
      {projects && !shown.length && <Empty>{projects.length ? "No projects match this filter." : isAdmin ? "No projects yet. Create one and upload its documents." : "You are not assigned to any project yet."}</Empty>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{shown.map((p) => <ProjectProgressCard key={p.project_id} p={p} onNav={onNav} />)}</div>
      <Modal open={creating} onClose={() => setCreating(false)} title="New project">
        <form onSubmit={create} className="space-y-3">
          <p className="text-[12px] text-slate-500">Create the workspace, then upload documents. The AI turns them into a specification and plan.</p>
          <label className="block text-[12px] font-medium text-slate-600">Project name<input required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="field" /></label>
          <label className="block text-[12px] font-medium text-slate-600">Objective (optional)<textarea rows={3} value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} className="field" /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-[12px] font-medium text-slate-600">Priority<select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="field">{["Low", "Medium", "High", "Critical"].map((p) => <option key={p}>{p}</option>)}</select></label>
            <label className="block text-[12px] font-medium text-slate-600">Deadline (days)<input type="number" min={3} max={730} required value={form.deadline_days} onChange={(e) => setForm({ ...form, deadline_days: Number(e.target.value) })} className="field" /></label>
          </div>
          <div className="flex justify-end gap-2"><PillButton onClick={() => setCreating(false)}>Cancel</PillButton><PillButton type="submit" variant="primary" disabled={busy}>Create project</PillButton></div>
        </form>
      </Modal>
    </div>
  );
}
