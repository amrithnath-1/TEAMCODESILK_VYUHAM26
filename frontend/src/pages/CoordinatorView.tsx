import { Sparkles } from "lucide-react";
import { AssistantPanel } from "../components/AssistantPanel";
import { Card } from "../components/ui";
import type { Nav, ProjectProgress, Summary } from "../types";

const AGENTS = [
  ["7", "Coordination & Supervisor", "Routes requests, gates approvals"],
  ["1", "Project Analysis", "Documents to specification and plan"],
  ["2", "Workforce Intelligence", "Skills, evidence, gaps, training"],
  ["3", "Task Allocation", "Deterministic engine and explanations"],
  ["4", "Progress Monitoring", "Status, prerequisites, blockers"],
  ["5", "Performance Evaluation", "Separate scores and levels"],
  ["6", "Risk Prediction", "Disruptions, overload, reassignment"],
];

export function CoordinatorView({ summary, projects, isAdmin, seed, onConsumedSeed, reload, onNav }: {
  summary?: Summary; projects: ProjectProgress[]; isAdmin: boolean; seed?: string | null; onConsumedSeed?: () => void; reload: () => void; onNav: Nav;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <AssistantPanel isAdmin={isAdmin} projects={projects} reload={reload} seed={seed} onSeedUsed={onConsumedSeed} onNav={onNav} height={520} />
      <div className="min-w-0 space-y-5">
        <Card title="Agent roster">
          <div className="space-y-2">
            {AGENTS.map(([id, name, desc]) => (
              <div key={id} className="flex items-start gap-3 rounded-xl bg-slate-50 p-2.5">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-[11px] font-bold text-brand-600">{id}</span>
                <div><div className="text-[12px] font-semibold text-slate-800">{name}</div><div className="text-[11px] text-slate-500">{desc}</div></div>
              </div>
            ))}
          </div>
        </Card>
        {summary && (
          <Card title={<span className="flex items-center gap-2"><Sparkles size={15} className="text-violet-500" />Recent agent decisions</span>}>
            <div className="max-h-[260px] space-y-2 overflow-y-auto">
              {!summary.decisions.length && <p className="text-[12px] text-slate-400">No decisions yet.</p>}
              {summary.decisions.slice(0, 10).map((d) => (
                <div key={d.id} className="border-b border-slate-50 pb-2 text-[12px]">
                  <div className="flex justify-between gap-2"><span className="font-medium text-slate-700">{d.recommended_action}</span><span className={`text-[10px] font-semibold ${d.risk_level === "Critical" ? "text-rose-500" : d.risk_level === "High" ? "text-orange-500" : "text-slate-400"}`}>{d.risk_level}</span></div>
                  <div className="text-[11px] text-slate-400">{d.agent_name} · {d.requires_approval ? "needs approval" : "automatic"}</div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
