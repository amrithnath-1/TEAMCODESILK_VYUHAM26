import { Bot, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Card, PillButton } from "../components/ui";
import type { ChatMessage, Summary } from "../types";

const AGENTS = [
  ["Agent 7", "Coordination & Supervisor", "Routes requests, gates HITL execution"],
  ["Agent 1", "Project Analysis", "Brief → DAG tasks, skills, effort"],
  ["Agent 2", "Workforce Intelligence", "Verified skills, gaps, training"],
  ["Agent 3", "Task Allocation", "Deterministic solver + explanations"],
  ["Agent 4", "Progress Monitoring", "Velocity, prerequisites, blockers"],
  ["Agent 5", "Performance Evaluation", "6 disaggregated scores, levels"],
  ["Agent 6", "Risk Prediction", "Disruptions, overload, cascade swaps"],
];

const ADMIN_PROMPTS = [
  "Who should do TSK-104?",
  "Is the workload fair right now?",
  "Vikram is on sick leave for 3 days",
  "What if Priya takes TSK-104?",
  "Show the top risks",
  "Where are our skill gaps?",
  "Run allocation",
];

const STAFF_PROMPTS = ["Who has free capacity this week?", "Is the workload fair right now?", "Show the top risks"];

export function CoordinatorView({ summary, isAdmin, seed, onConsumedSeed, reload }: {
  summary?: Summary; isAdmin: boolean; seed?: string | null; onConsumedSeed?: () => void; reload: () => void;
}) {
  const [msgs, setMsgs] = useState<ChatMessage[]>([
    { from: "agent", agent: "Agent 7 (Coordination Supervisor)", text: "Hi! I coordinate the 7 workforce agents. Ask me who should take a task, simulate a disruption, check fairness, or run a what-if." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setMsgs((m) => [...m, { from: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api<{ agent: string; response: string; trace: string[] }>("/chat/coordinator", { body: { query: q } });
      setMsgs((m) => [...m, { from: "agent", agent: r.agent, text: r.response, trace: r.trace }]);
      reload();
    } catch (e: any) {
      setMsgs((m) => [...m, { from: "agent", agent: "System", text: `⚠ ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (seed) {
      send(seed);
      onConsumedSeed?.();
    }
  }, [seed]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
      <Card title={<span className="flex items-center gap-2"><Bot size={18} className="text-brand-500" />AI Coordinator Command Center</span>}
        action={summary && <span className="text-[11px] text-slate-400">Gini {summary.workload_gini_index} · {summary.pending_approvals.length} pending approvals</span>}>
        <div className="flex h-[560px] flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto pr-2">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-[13px] leading-relaxed ${m.from === "user" ? "rounded-br-sm bg-brand-500 text-white" : "rounded-bl-sm bg-slate-100 text-slate-700"}`}>
                  {m.agent && <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-brand-600">{m.agent}</div>}
                  <div className="whitespace-pre-line">{m.text}</div>
                  {m.trace && m.trace.length > 1 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.trace.map((t) => <span key={t} className="rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-500">{t}</span>)}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && <div className="text-[12px] text-slate-400">Agents are working…</div>}
            <div ref={endRef} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(isAdmin ? ADMIN_PROMPTS : STAFF_PROMPTS).map((p) => (
              <button key={p} onClick={() => send(p)} disabled={busy} className="rounded-full border border-slate-200 px-3 py-1 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-50">{p}</button>
            ))}
          </div>
          <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask in plain English…"
              className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-[13px] outline-none focus:border-brand-500" />
            <PillButton type="submit" variant="primary" disabled={busy || !input.trim()} className="px-5"><Send size={14} />Send</PillButton>
          </form>
        </div>
      </Card>

      <div className="min-w-0 space-y-5">
        <Card title="Agent roster">
          <div className="space-y-2">
            {AGENTS.map(([id, name, desc]) => (
              <div key={id} className="flex items-start gap-3 rounded-xl bg-slate-50 p-2.5">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-[10px] font-bold text-brand-600">{id.split(" ")[1]}</span>
                <div><div className="text-[12px] font-semibold text-slate-800">{name}</div><div className="text-[11px] text-slate-500">{desc}</div></div>
              </div>
            ))}
          </div>
        </Card>
        {summary && (
          <Card title={<span className="flex items-center gap-2"><Sparkles size={15} className="text-violet-500" />Recent agent decisions</span>}>
            <div className="max-h-[260px] space-y-2 overflow-y-auto">
              {summary.decisions.length === 0 && <p className="text-[12px] text-slate-400">No decisions yet.</p>}
              {summary.decisions.slice(0, 10).map((d: any) => (
                <div key={d.id} className="border-b border-slate-50 pb-2 text-[12px]">
                  <div className="flex justify-between"><span className="font-medium text-slate-700">{d.recommended_action}</span>
                    <span className={`text-[10px] font-semibold ${d.risk_level === "Critical" ? "text-rose-500" : d.risk_level === "High" ? "text-orange-500" : "text-slate-400"}`}>{d.risk_level}</span></div>
                  <div className="text-[11px] text-slate-400">{d.agent_name} · {d.requires_approval ? "needs approval" : "auto"}</div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
