import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, FACTOR_LABELS, PillButton, StatusPill } from "../components/ui";
import type { Summary, Weights } from "../types";

export function SettingsView({ summary, reload, toast, onReset }: { summary: Summary; reload: () => void; toast: (m: string, k?: "ok" | "err") => void; onReset: () => void }) {
  const [status, setStatus] = useState<any>(null);
  const [weights, setWeights] = useState<Weights>(summary.weights);
  useEffect(() => { api("/system/status").then(setStatus).catch((e) => toast(e.message, "err")); }, [summary, toast]);
  useEffect(() => setWeights(summary.weights), [summary.weights]);
  const sum = Object.values(weights).reduce((a, b) => a + b, 0);
  const save = async () => {
    try {
      await api("/admin/weights", { body: weights });
      toast("Scoring weights saved. Re-run allocation to apply them.");
      reload();
    } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card title="AI connection">
        <div className="flex items-center gap-2"><StatusPill status={summary.ai.configured ? "connected" : "not_connected"} /><span className="text-[13px] text-slate-600">Model: {summary.ai.model}</span></div>
        {summary.ai.setup && <p className="mt-2 rounded-lg bg-amber-50 p-3 text-[12px] text-amber-800">{summary.ai.setup} Until then, analysis and chat use labelled rule-based logic with your real data.</p>}
        {status && <p className="mt-3 text-[12px] text-slate-500">Usage so far: {status.ai_usage.calls} calls, {status.ai_usage.input_tokens} input and {status.ai_usage.output_tokens} output tokens, {status.ai_usage.failures} failures.</p>}
        {status && <p className="mt-1 text-[12px] text-slate-500">Document retrieval: {status.retrieval}. Upload limit: {status.upload_limit_mb} MB per file.</p>}
      </Card>
      <Card title="Integrations">
        <ul className="space-y-2 text-[12px] text-slate-600">
          <li><b>GitHub:</b> reads public profile data with no setup. Each employee connects their own username on their profile.</li>
          <li><b>LinkedIn, Instagram, X:</b> profile links are stored only. Reading data needs each provider's approved developer access, which is not configured, so nothing is retrieved or scored from them.</li>
          <li><b>Calendar, Slack, Jira:</b> not connected. Availability comes from recorded leave and meeting hours. Evidence events can be entered on the Workforce page.</li>
        </ul>
      </Card>
      <Card title="Allocation scoring weights" action={<span className={`text-[11px] font-medium ${Math.abs(sum - 1) < 0.001 ? "text-emerald-600" : "text-rose-500"}`}>Total {sum.toFixed(2)} (must be 1.00)</span>}>
        <div className="space-y-3">
          {(Object.keys(weights) as (keyof Weights)[]).map((k) => (
            <label key={k} className="block text-[12px] text-slate-600">
              <span className="mb-1 flex justify-between"><span>{FACTOR_LABELS[k]}</span><b>{Math.round(weights[k] * 100)}%</b></span>
              <input type="range" min={0} max={0.6} step={0.01} value={weights[k]} onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} className="w-full accent-brand-500" />
            </label>
          ))}
        </div>
        <PillButton variant="primary" className="mt-3" disabled={Math.abs(sum - 1) > 0.001} onClick={save}>Save weights</PillButton>
      </Card>
      <Card title="Data">
        <p className="text-[12px] text-slate-500">Data is stored in {status?.database ?? "the database"} and survives restarts. Audit ledger: {summary.ledger_status.valid ? "hash chain verified" : "chain broken"}, {summary.ledger_status.entries} entries.</p>
        <PillButton variant="danger" className="mt-3" onClick={onReset}>Reset all demo data</PillButton>
        <p className="mt-2 text-[11px] text-slate-400">This deletes uploaded documents, plans, conversations and changes, then restores the seeded data. A backup is saved to data/backups first. Development only.</p>
      </Card>
    </div>
  );
}
