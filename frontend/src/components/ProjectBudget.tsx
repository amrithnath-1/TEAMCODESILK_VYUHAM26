import { Calculator, CheckCircle2, Wallet } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Card, PillButton, StatusPill } from "./ui";
import type { BudgetReport, Optimization } from "../types";

type Toast = (m: string, k?: "ok" | "err") => void;

/** Whole currency units on screen, integer minor units everywhere else, so totals stay exact. */
const toMinor = (value: string) => Math.round(Number(value || 0) * 100);
const show = (minor: number | null | undefined, currency?: string | null) => minor == null ? "—" : `${currency ?? ""} ${(minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim();

export function ProjectBudget({ id, isAdmin, toast, changed }: { id: string; isAdmin: boolean; toast: Toast; changed: () => void }) {
  const [report, setReport] = useState<BudgetReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ currency: "", total: "", reserve: "", non_labor: "", includes_tax: false, hard_limit: false });
  const [cost, setCost] = useState({ kind: "actual", amount: "", note: "" });
  const [plan, setPlan] = useState<Optimization | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<BudgetReport>(`/projects/${id}/budget`).then((r) => {
      setReport(r);
      setErr(null);
      if (r.has_budget) setForm((f) => f.currency ? f : { currency: r.currency ?? "", total: String((r.total_minor ?? 0) / 100), reserve: String((r.reserve_minor ?? 0) / 100), non_labor: String(r.estimated_non_labor_minor / 100), includes_tax: !!r.includes_tax, hard_limit: !!r.hard_limit });
    }).catch((e) => setErr(e.message));
  }, [id]);
  useEffect(load, [load]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/projects/${id}/budget`, { method: "PUT", body: { currency: form.currency, total_minor: toMinor(form.total), reserve_minor: toMinor(form.reserve), non_labor_minor: toMinor(form.non_labor), includes_tax: form.includes_tax, hard_limit: form.hard_limit } });
      toast("Budget saved.");
      load();
    } catch (error: any) { toast(error.message, "err"); }
  };
  const addCost = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setReport(await api<BudgetReport>(`/projects/${id}/costs`, { body: { kind: cost.kind, amount_minor: toMinor(cost.amount), note: cost.note || null } }));
      setCost({ kind: "actual", amount: "", note: "" });
    } catch (error: any) { toast(error.message, "err"); }
  };
  const propose = async () => {
    setBusy(true);
    try { setPlan(await api<Optimization>(`/projects/${id}/optimize`, { body: {} })); } catch (error: any) { toast(error.message, "err"); } finally { setBusy(false); }
  };
  const submit = async () => {
    if (!plan) return;
    setBusy(true);
    try {
      const r = await api<{ approvals: string[] }>(`/projects/${id}/optimize/apply`, { body: { proposal_id: plan.proposal_id } });
      toast(`${r.approvals.length} assignment(s) sent for approval.`);
      setPlan(null);
      load();
      changed();
    } catch (error: any) { toast(error.message, "err"); } finally { setBusy(false); }
  };

  if (err) return <p role="alert" className="rounded-xl bg-rose-50 p-4 text-[13px] text-rose-600">{err}</p>;
  if (!report) return <div className="p-10 text-center text-sm text-slate-400">Loading budget…</div>;
  const c = report.currency;

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
      <div className="min-w-0 space-y-5">
        <Card title={<span className="flex items-center gap-2"><Wallet size={15} className="text-brand-500" />Budget</span>} action={report.status && <StatusPill status={report.status} />}>
          {!report.has_budget && <p className="text-[13px] text-slate-500">No budget set yet.</p>}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {report.has_budget && <Stat label="Approved total" value={show(report.total_minor, c)} />}
            <Stat label="Estimated labor" value={show(report.estimated_labor_minor, c)} />
            <Stat label="Estimated non-labor" value={show(report.estimated_non_labor_minor, c)} />
            <Stat label="Committed" value={show(report.committed_minor, c)} />
            <Stat label="Actual" value={show(report.actual_minor, c)} />
            {report.has_budget && <><Stat label="Remaining" value={show(report.remaining_minor, c)} /><Stat label="Forecast at completion" value={show(report.forecast_at_completion_minor, c)} /><Stat label="Variance" value={show(report.variance_minor, c)} /><Stat label="Reserve" value={show(report.reserve_minor, c)} /></>}
          </div>
          {report.scenarios && <p className="mt-3 text-[12px] text-slate-600">Range from {report.scenarios.basis}: {show(report.scenarios.optimistic_minor, c)} to {show(report.scenarios.conservative_minor, c)}, expected {show(report.scenarios.expected_minor, c)}.</p>}
          <ul className="mt-3 list-disc pl-4 text-[11px] text-slate-500">{report.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
          {!!report.tasks_without_rate.length && <p className="mt-2 text-[12px] text-amber-700">No approved rate for the owners of: {report.tasks_without_rate.join(", ")}.</p>}
        </Card>

        <Card title={<span className="flex items-center gap-2"><Calculator size={15} className="text-brand-500" />Budget-aware team plan</span>} action={<PillButton variant="primary" disabled={busy} onClick={propose}>{busy ? "Working…" : "Propose a team"}</PillButton>}>
          <p className="text-[12px] text-slate-500">Required skills and capacity are checked first. Cost and risk are then minimized among the people who qualify. Nothing changes until each assignment is approved.</p>
          {plan && (
            <div className="mt-3 space-y-3">
              <p className="text-[12px] text-slate-600">Status: <b>{plan.status.replace(/_/g, " ")}</b> · solver {plan.solver.status.replace(/_/g, " ")}{plan.solver.gap ? `, gap ${(plan.solver.gap * 100).toFixed(1)}%` : ""}{plan.total_cost_minor != null ? ` · estimated cost ${show(plan.total_cost_minor, plan.currency)}` : ""}{!plan.cost_aware ? " · no cost rates, so cost was not considered" : ""}</p>
              {plan.over_budget && <div className="rounded-xl bg-amber-50 p-3 text-[12px] text-amber-800"><b>Over budget by {show(plan.over_budget.overrun_minor, plan.currency)}.</b> {plan.over_budget.why}<ul className="mt-1 list-disc pl-4">{plan.over_budget.options.map((o) => <li key={o}>{o}</li>)}</ul></div>}
              {plan.problems?.map((p, i) => <div key={i} className="rounded-xl bg-rose-50 p-3 text-[12px] text-rose-700"><b>{p.title}:</b> {p.reason}<ul className="mt-1 list-disc pl-4">{p.options.map((o) => <li key={o}>{o}</li>)}</ul></div>)}
              {plan.assignments.map((a) => (
                <div key={a.task_id} className="rounded-xl border border-slate-100 p-3 text-[12px] text-slate-600">
                  <div className="flex flex-wrap justify-between gap-2"><b className="text-[13px] text-slate-800">{a.task_id} · {a.task_title}</b><span className="font-medium text-brand-600">{a.employee_name}</span></div>
                  <p>{a.estimated_hours}h, {a.hours_per_week}h per week in weeks {a.weeks[0] + 1}-{a.weeks[1] + 1} · existing {a.existing_weekly_hours}h of {a.weekly_capacity}h · suitability {a.suitability.score}{a.estimated_cost_minor != null ? ` · ${show(a.estimated_cost_minor, plan.currency)}` : ""}</p>
                  <p>{a.rationale}</p>
                  {a.risks.map((r) => <p key={r} className="text-amber-700">{r}</p>)}
                </div>
              ))}
              {plan.explanation && <p className="text-[11px] text-slate-500">{plan.explanation}</p>}
              {plan.assignments.length > 0 && <PillButton variant="success" disabled={busy} onClick={submit}><CheckCircle2 size={13} />Send for approval</PillButton>}
            </div>
          )}
        </Card>
      </div>

      <aside className="min-w-0 space-y-5">
        {isAdmin && (
          <Card title="Set budget">
            <form onSubmit={save} className="space-y-2">
              <label className="block text-[12px] font-medium text-slate-600">Currency code<input required maxLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} placeholder="INR" className="field" /></label>
              <label className="block text-[12px] font-medium text-slate-600">Total<input required type="number" min={0} step="0.01" value={form.total} onChange={(e) => setForm({ ...form, total: e.target.value })} className="field" /></label>
              <label className="block text-[12px] font-medium text-slate-600">Reserve<input type="number" min={0} step="0.01" value={form.reserve} onChange={(e) => setForm({ ...form, reserve: e.target.value })} className="field" /></label>
              <label className="block text-[12px] font-medium text-slate-600">Non-labor estimate<input type="number" min={0} step="0.01" value={form.non_labor} onChange={(e) => setForm({ ...form, non_labor: e.target.value })} className="field" /></label>
              <label className="flex items-center gap-2 text-[12px] text-slate-600"><input type="checkbox" checked={form.includes_tax} onChange={(e) => setForm({ ...form, includes_tax: e.target.checked })} />Amounts include tax</label>
              <label className="flex items-center gap-2 text-[12px] text-slate-600"><input type="checkbox" checked={form.hard_limit} onChange={(e) => setForm({ ...form, hard_limit: e.target.checked })} />Treat as a hard limit</label>
              <PillButton type="submit" variant="primary">Save budget</PillButton>
            </form>
          </Card>
        )}
        {report.has_budget && (
          <Card title="Record a cost">
            <form onSubmit={addCost} className="space-y-2">
              <label className="block text-[12px] font-medium text-slate-600">Type<select value={cost.kind} onChange={(e) => setCost({ ...cost, kind: e.target.value })} className="field"><option value="actual">Actual</option><option value="committed">Committed</option><option value="non_labor_estimate">Non-labor estimate</option></select></label>
              <label className="block text-[12px] font-medium text-slate-600">Amount<input required type="number" min={0} step="0.01" value={cost.amount} onChange={(e) => setCost({ ...cost, amount: e.target.value })} className="field" /></label>
              <label className="block text-[12px] font-medium text-slate-600">Note<input value={cost.note} onChange={(e) => setCost({ ...cost, note: e.target.value })} className="field" /></label>
              <PillButton type="submit" variant="primary">Add cost</PillButton>
            </form>
          </Card>
        )}
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-50 p-3"><div className="text-[11px] text-slate-500">{label}</div><div className="text-[15px] font-semibold text-slate-800">{value}</div></div>;
}
