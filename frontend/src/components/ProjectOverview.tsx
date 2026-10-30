import { useEffect, useState } from "react";
import { api } from "../api";
import type { EmployeeScores, Nav, ProjectsOverview, Task } from "../types";
import { ProjectDonut } from "./ProjectDonut";
import { PillButton } from "./ui";

const STAGE_COLORS: Record<string, string> = {
  draft: "#cbd5e1", under_evaluation: "#f6c453", awaiting_clarification: "#f6a03b", awaiting_approval: "#f59e8b", approved: "#6cc7d9",
  awaiting_allocation: "#a78bfa", in_progress: "#2f80ed", blocked: "#e8577a", completed: "#34c38f", cancelled: "#94a3b8",
};

/** The selected project's task stages as a donut, with its real team rotating inside. No team means no people, never placeholders. */
export function ProjectOverview({ onNav, refreshKey, tasks, employees }: { onNav: Nav; refreshKey: unknown; tasks: Task[]; employees: EmployeeScores[] }) {
  const [data, setData] = useState<ProjectsOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    api<ProjectsOverview>("/projects/overview").then((d) => { setData(d); setErr(null); }).catch((e) => setErr(e.message));
  }, [refreshKey]);

  if (err) return <p role="alert" className="rounded-xl bg-rose-50 p-3 text-[13px] text-rose-600">Could not load projects: {err}</p>;
  if (!data) return <div className="grid h-[260px] place-items-center text-[13px] text-slate-400">Loading projects…</div>;
  if (!data.total) return <p className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-[13px] text-slate-400">No projects yet. Create one from the Projects page.</p>;

  const current = data.projects.find((p) => p.project_id === selected) ?? data.projects[0];

  return (
    <div className="grid gap-5 md:grid-cols-[300px_1fr]">
      <ProjectDonut key={current.project_id} tasks={tasks.filter((t) => t.project_id === current.project_id)} employees={employees} />

      <div className="min-w-0">
        <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1" aria-label="Projects by status">
          {data.stages.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5 text-[12px] text-slate-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: STAGE_COLORS[s.key] }} />{s.label} <b className="text-slate-800">{s.count}</b>
            </span>
          ))}
        </div>
        <ul className="max-h-[190px] space-y-1 overflow-y-auto">
          {data.projects.map((p) => (
            <li key={p.project_id} className={`flex items-center gap-2 rounded-xl px-3 py-2 ${p.project_id === current.project_id ? "bg-brand-50" : "hover:bg-slate-50"}`}>
              <button onClick={() => setSelected(p.project_id)} aria-pressed={p.project_id === current.project_id} className="flex min-w-0 flex-1 items-center gap-2 text-left">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: STAGE_COLORS[p.stage] }} />
                <span className="min-w-0"><span className="block truncate text-[13px] font-medium text-slate-800">{p.name}</span><span className="block text-[11px] text-slate-500">{p.stage_label} · {p.team.length ? `${p.team.length} people` : "no team yet"}</span></span>
              </button>
              <PillButton onClick={() => onNav("project", p.project_id)}>Open</PillButton>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
