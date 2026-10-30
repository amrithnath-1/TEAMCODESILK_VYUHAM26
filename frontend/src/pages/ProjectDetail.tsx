import { AlertTriangle, ArrowLeft, CheckCircle2, Download, Eye, FileUp, Lock, RefreshCw, RotateCcw, Sparkles, Trash2, Unlock, UserPlus, X } from "lucide-react";
import { DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, apiDownload, apiUpload } from "../api";
import { BANDS, Donut, HealthBadge } from "../components/ProgressDonut";
import { CandidateModal } from "../components/Modals";
import { Bar, Card, Empty, Modal, PillButton, PriorityBadge, StatusPill } from "../components/ui";
import type { DocumentRow, EvidenceItem, Nav, Plan, PlanTask, Project, ProjectProgress, Spec, Summary, Task } from "../types";

type Toast = (m: string, k?: "ok" | "err") => void;
const SPEC_SECTIONS: [string, string][] = [["objectives", "Objectives"], ["business_requirements", "Business requirements"], ["functional_requirements", "Functional requirements"], ["non_functional_requirements", "Non-functional requirements"],
  ["deliverables", "Deliverables"], ["technical_requirements", "Technical requirements"], ["constraints", "Constraints & dependencies"], ["deadlines", "Deadlines & milestones"], ["budget", "Budget & resources"], ["required_skills", "Required skills"], ["risks", "Risks"]];

export function ProjectDetail({ id, isAdmin, onNav, toast, reload, summary }: { id: string; isAdmin: boolean; onNav: Nav; toast: Toast; reload: () => void; summary: Summary | null }) {
  const [data, setData] = useState<{ project: Project; progress: ProjectProgress; tasks: Task[] } | null>(null);
  const [tab, setTab] = useState("overview");
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => { api(`/projects/${id}`).then((d) => { setData(d); setErr(null); }).catch((e) => setErr(e.message)); }, [id]);
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);     // keeps progress live; every value comes from the backend
    return () => clearInterval(t);
  }, [load]);
  const changed = () => { load(); reload(); };

  if (err) return <Empty>{err} <button className="ml-2 text-brand-600 underline" onClick={() => onNav("projects")}>Back to projects</button></Empty>;
  if (!data) return <div className="p-10 text-center text-sm text-slate-400">Loading project…</div>;
  const { project, progress: p, tasks } = data;
  const tabs = isAdmin ? [["overview", "Overview"], ["documents", "Documents"], ["spec", "Specification"], ["plan", "Plan"], ["tasks", `Tasks (${tasks.length})`], ["evaluation", "Evaluation"]] : [["overview", "Overview"], ["documents", "Documents"], ["tasks", `Tasks (${tasks.length})`]];

  const archive = async () => {
    if (!confirm(`Archive ${project.name}? It leaves dashboards but its records are kept.`)) return;
    try {
      await api(`/projects/${id}`, { method: "PATCH", body: { status: "Archived" } });
      reload();
      onNav("projects");
    } catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-start gap-3">
          <button aria-label="Back to projects" onClick={() => onNav("projects")} className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><ArrowLeft size={18} /></button>
          <div className="mr-auto min-w-0">
            <div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-semibold text-slate-800">{project.name}</h1><StatusPill status={project.status} /><PriorityBadge priority={project.priority} /><HealthBadge health={p.health} /></div>
            <p className="mt-1 max-w-3xl text-[13px] text-slate-500">{project.business_objective || "No objective recorded yet."}</p>
          </div>
          <div className="flex gap-2">
            <PillButton onClick={() => apiDownload(`/projects/${id}/export.csv`, `${id}-tasks.csv`).catch((e) => toast(e.message, "err"))}><Download size={13} />Export CSV</PillButton>
            {isAdmin && <PillButton onClick={archive}>Archive</PillButton>}
          </div>
        </div>
        <nav className="mt-4 flex gap-1 overflow-x-auto">
          {tabs.map(([k, label]) => <button key={k} onClick={() => setTab(k)} className={`whitespace-nowrap rounded-full px-4 py-1.5 text-[13px] font-medium ${tab === k ? "bg-brand-500 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}
        </nav>
      </Card>
      {tab === "overview" && <Overview p={p} isAdmin={isAdmin} id={id} toast={toast} changed={changed} />}
      {tab === "documents" && <Documents id={id} isAdmin={isAdmin} toast={toast} onAnalyze={() => setTab("spec")} />}
      {tab === "spec" && isAdmin && <Specification id={id} toast={toast} onPlan={() => setTab("plan")} changed={changed} />}
      {tab === "plan" && isAdmin && <PlanTab id={id} toast={toast} changed={changed} onTasks={() => setTab("tasks")} />}
      {tab === "tasks" && <TasksTab id={id} tasks={tasks} isAdmin={isAdmin} toast={toast} changed={changed} summary={summary} />}
      {tab === "evaluation" && isAdmin && <Evaluation id={id} tasks={tasks} />}
    </div>
  );
}

function Overview({ p, isAdmin, id, toast, changed }: { p: ProjectProgress; isAdmin: boolean; id: string; toast: Toast; changed: () => void }) {
  const [pct, setPct] = useState("");
  const [note, setNote] = useState("");
  const submit = async () => {
    try {
      await api(`/projects/${id}/progress-report`, { body: { reported_pct: Number(pct), note } });
      setPct(""); setNote("");
      toast("Report saved. It is shown beside verified progress and does not change it.");
      changed();
    } catch (e: any) { toast(e.message, "err"); }
  };
  const history = p.history.map((h) => ({ ...h, at: h.created_at.slice(5, 16).replace("T", " ") }));
  return (
    <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
      <Card title="Progress">
        <div className="flex justify-center"><Donut p={p} size={180} /></div>
        <dl className="mt-4 space-y-1.5 text-[12px] text-slate-500">
          {BANDS.map((b) => <div key={b.key} className="flex justify-between"><dt className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: b.color }} />{b.label}</dt><dd className="font-medium text-slate-700">{p.bands_pct[b.key]}%</dd></div>)}
        </dl>
        <p className="mt-3 rounded-lg bg-slate-50 p-2.5 text-[11px] leading-relaxed text-slate-500">{p.method}</p>
      </Card>
      <div className="min-w-0 space-y-5">
        <div className="grid grid-cols-2 gap-3 2xl:grid-cols-4">
          <Stat label="Deadline" value={p.deadline} sub={p.days_remaining < 0 ? `${-p.days_remaining} days overdue` : `${p.days_remaining} days left`} />
          <Stat label="Current milestone" value={p.current_milestone ?? "—"} sub={`${p.milestones.filter((m) => m.done === m.total).length}/${p.milestones.length} done`} />
          <Stat label="Open / overdue" value={`${p.open_tasks} / ${p.overdue_tasks.length}`} sub={`${p.total_tasks} tasks total`} />
          <Stat label="Last update" value={p.last_update ? p.last_update.slice(0, 10) : "None"} sub={p.last_update ? p.last_update.slice(11, 16) + " UTC" : "No activity yet"} />
        </div>
        <Card title="Reported vs verified">
          <div className="space-y-3 text-[12px] text-slate-600">
            <Row label="Verified (accepted deliverables)" value={p.completion_pct} color="bg-emerald-400" />
            <Row label="Reported by employees" value={p.reported_by_employees_pct} color="bg-brand-500" />
            {p.reported_by_manager && <Row label={`Reported by ${p.reported_by_manager.reported_by}`} value={p.reported_by_manager.reported_pct} color="bg-violet-400" />}
            <Row label="Expected by schedule" value={p.expected_pct_by_schedule} color="bg-slate-300" />
          </div>
          {isAdmin && (
            <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-slate-100 pt-3">
              <label className="text-[11px] text-slate-500">Manager report %<input aria-label="Reported percent" type="number" min={0} max={100} value={pct} onChange={(e) => setPct(e.target.value)} className="field w-24" /></label>
              <label className="min-w-[160px] flex-1 text-[11px] text-slate-500">Note<input value={note} onChange={(e) => setNote(e.target.value)} className="field" /></label>
              <PillButton variant="primary" disabled={pct === "" || Number(pct) < 0 || Number(pct) > 100} onClick={submit}>Save report</PillButton>
            </div>
          )}
        </Card>
        {p.critical_blockers.length > 0 && (
          <Card title={<span className="flex items-center gap-2 text-rose-600"><AlertTriangle size={16} />Critical blockers</span>}>
            {p.critical_blockers.map((b) => <p key={b.task_id} className="border-b border-slate-50 py-1.5 text-[13px] text-slate-600"><b>{b.task_id}</b> {b.title}: {b.reason.replace(/_/g, " ").toLowerCase()}</p>)}
          </Card>
        )}
        <Card title="Progress history">
          {history.length < 2 ? <Empty>History appears after the project's progress changes.</Empty> : (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history} margin={{ left: -20, right: 8, top: 8 }}>
                  <CartesianGrid vertical={false} stroke="#f1f5f9" /><XAxis dataKey="at" tick={{ fontSize: 10 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 10 }} /><Tooltip />
                  <Area type="stepAfter" dataKey="verified_pct" name="Verified %" stackId="1" stroke="#34c38f" fill="#34c38f" />
                  <Area type="stepAfter" dataKey="in_progress_pct" name="In progress %" stackId="1" stroke="#2f80ed" fill="#2f80ed" />
                  <Area type="stepAfter" dataKey="blocked_pct" name="Blocked %" stackId="1" stroke="#ef6a6a" fill="#ef6a6a" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return <div className="min-w-0 rounded-2xl bg-white p-3 shadow-card"><div className="text-[11px] text-slate-500">{label}</div><div className="break-words text-[15px] font-semibold text-slate-800" title={value}>{value}</div><div className="text-[10px] text-slate-400">{sub}</div></div>;
}

function Row({ label, value, color }: { label: string; value: number; color: string }) {
  return <div><div className="mb-1 flex justify-between"><span>{label}</span><b>{value}%</b></div><Bar value={value} color={color} /></div>;
}

function Documents({ id, isAdmin, toast, onAnalyze }: { id: string; isAdmin: boolean; toast: Toast; onAnalyze: () => void }) {
  const [docs, setDocs] = useState<DocumentRow[] | null>(null);
  const [pct, setPct] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const [results, setResults] = useState<{ filename: string; status: string; error?: string }[]>([]);
  const [preview, setPreview] = useState<{ filename: string; version: number; chunks: { location: string; text: string; suspicious: number }[] } | null>(null);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ id: string; filename: string; location: string; text: string }[] | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<DocumentRow[]>(`/projects/${id}/documents`).then((d) => { setDocs(d); return d; }).catch((e) => { toast(e.message, "err"); return []; }), [id, toast]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!docs?.some((d) => ["uploaded", "extracting"].includes(d.status))) return;
    const t = setTimeout(load, 1500);
    return () => clearTimeout(t);
  }, [docs, load]);

  const upload = async (files: FileList | File[]) => {
    const form = new FormData();
    [...files].forEach((f) => form.append("files", f));
    if (![...files].length) return;
    setPct(0);
    try {
      const r = await apiUpload<{ results: typeof results }>(`/projects/${id}/documents`, form, setPct);
      setResults(r.results);
      load();
    } catch (e: any) { toast(e.message, "err"); } finally { setPct(null); if (input.current) input.current.value = ""; }
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); };
  const remove = async (d: DocumentRow) => {
    if (!confirm(`Remove ${d.filename} v${d.version} from this project? Its indexed text is deleted too.`)) return;
    try { await api(`/projects/${id}/documents/${d.id}`, { method: "DELETE" }); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const reindex = async (d: DocumentRow) => {
    try { await api(`/projects/${id}/documents/${d.id}/reindex`, { body: {} }); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const search = async () => {
    try { setHits(await api(`/projects/${id}/documents-search?q=${encodeURIComponent(q)}`)); } catch (e: any) { toast(e.message, "err"); }
  };
  const ready = docs?.some((d) => d.status === "indexed");
  return (
    <div className="space-y-5">
      {isAdmin && (
        <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
          className={`rounded-2xl border-2 border-dashed bg-white p-8 text-center transition ${drag ? "border-brand-500 bg-brand-50" : "border-slate-200"}`}>
          <FileUp className="mx-auto text-brand-500" />
          <p className="mt-2 text-[14px] font-medium text-slate-700">Drag project files here, or <button className="text-brand-600 underline" onClick={() => input.current?.click()}>browse</button></p>
          <p className="text-[12px] text-slate-400">PDF, DOCX, PPTX, TXT, CSV, XLSX · up to 20 MB each · several at once</p>
          <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.pptx,.txt,.csv,.xlsx" onChange={(e) => e.target.files && upload(e.target.files)} />
          {pct !== null && <div className="mx-auto mt-3 max-w-xs"><Bar value={pct} /><p className="mt-1 text-[11px] text-slate-500">Uploading {pct}%</p></div>}
          {results.length > 0 && <div className="mt-3 space-y-1 text-left text-[12px]">{results.map((r, i) => <p key={i} className={r.status === "uploaded" ? "text-emerald-600" : "text-rose-600"}>{r.filename}: {r.status === "uploaded" ? "uploaded" : r.error}</p>)}</div>}
        </div>
      )}
      <Card title="Documents" action={isAdmin && <PillButton variant="primary" disabled={!ready} onClick={onAnalyze}><Sparkles size={13} />Continue to analysis</PillButton>}>
        {docs && !docs.length && <Empty>No documents yet.</Empty>}
        <div className="space-y-2">
          {docs?.map((d) => (
            <div key={d.id} className={`flex flex-wrap items-center gap-3 rounded-xl border border-slate-100 p-3 ${d.is_current ? "" : "opacity-60"}`}>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-slate-800">{d.filename} <span className="text-slate-400">v{d.version}</span></div>
                <div className="text-[11px] text-slate-400">{(d.size / 1024).toFixed(0)} KB · {d.chunk_count} passages · {d.uploaded_by}</div>
                {d.error && <p className="text-[12px] text-rose-600">{d.error}</p>}
                {d.suspicious_count > 0 && <p className="text-[12px] text-amber-700">⚠ {d.suspicious_count} passage(s) look like embedded instructions. They are treated as data and ignored as commands.</p>}
              </div>
              <StatusPill status={d.status} />
              <PillButton disabled={d.status !== "indexed"} onClick={() => api(`/projects/${id}/documents/${d.id}/preview`).then(setPreview).catch((e) => toast(e.message, "err"))}><Eye size={13} />Preview</PillButton>
              {isAdmin && <PillButton disabled={!d.is_current} onClick={() => reindex(d)}><RefreshCw size={13} />Reindex</PillButton>}
              {isAdmin && <PillButton onClick={() => input.current?.click()}>Replace</PillButton>}
              {isAdmin && <button aria-label={`Remove ${d.filename}`} onClick={() => remove(d)} className="rounded-full p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={15} /></button>}
            </div>
          ))}
        </div>
        {isAdmin && docs && docs.length > 0 && <p className="mt-2 text-[11px] text-slate-400">To replace a file, upload one with the same name; it becomes a new version.</p>}
      </Card>
      <Card title="Search these documents">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); search(); }}>
          <input aria-label="Search documents" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find passages by keyword" className="field mt-0 flex-1" />
          <PillButton type="submit" variant="primary" disabled={q.trim().length < 2}>Search</PillButton>
        </form>
        {hits && !hits.length && <p className="mt-3 text-[12px] text-slate-400">No matching passages.</p>}
        {hits?.map((h) => <div key={h.id} className="mt-2 rounded-xl bg-slate-50 p-3 text-[12px] text-slate-600"><div className="mb-1 font-medium text-slate-700">{h.filename} · {h.location}</div>{h.text.slice(0, 400)}</div>)}
      </Card>
      <Modal open={!!preview} onClose={() => setPreview(null)} wide title={preview ? `${preview.filename} v${preview.version}` : ""}>
        <p className="mb-2 text-[11px] text-slate-400">Extracted text (first passages)</p>
        {preview?.chunks.map((c, i) => <div key={i} className="mb-2 rounded-xl bg-slate-50 p-3 text-[12px] text-slate-600"><div className="mb-1 font-medium text-slate-700">{c.location}</div><div className="whitespace-pre-line">{c.text}</div></div>)}
      </Modal>
    </div>
  );
}

function Specification({ id, toast, onPlan, changed }: { id: string; toast: Toast; onPlan: () => void; changed: () => void }) {
  const [spec, setSpec] = useState<Spec | null>(null);
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [summary, setSummary] = useState("");
  const [notes, setNotes] = useState("");

  const apply = (s: Spec) => { setSpec(s); setSummary(s.analysis?.summary ?? ""); setNotes(s.analysis?.manager_notes ?? ""); };
  useEffect(() => { api<Spec>(`/projects/${id}/spec`).then(apply).catch((e) => toast(e.message, "err")); }, [id, toast]);
  const run = async (fn: () => Promise<Spec>, done?: string) => {
    setBusy(true);
    try { apply(await fn()); if (done) toast(done); changed(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  if (!spec) return <div className="p-10 text-center text-sm text-slate-400">Loading…</div>;
  const open = spec.clarifications.filter((c) => c.status === "open");
  const a = spec.analysis;
  const dirty = a && (summary !== (a.summary ?? "") || notes !== (a.manager_notes ?? ""));
  return (
    <div className="space-y-5">
      <Card title="Document analysis" action={<PillButton variant="primary" disabled={busy} onClick={() => run(() => api(`/projects/${id}/analyze`, { body: {} }))}><Sparkles size={13} />{busy ? "Analysing…" : a ? "Re-analyse" : "Analyse documents"}</PillButton>}>
        {!a && <Empty>Upload documents, then analyse them. The result appears here for your review.</Empty>}
        {a && (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px]">
              <StatusPill status={spec.status} />
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">Source: {spec.source}</span>
              {spec.source === "rule-based" && <span className="text-amber-700">Claude is not connected, so this uses keyword rules. Add ANTHROPIC_API_KEY for full AI analysis.</span>}
              {a.truncated_input && <span className="text-amber-700">Documents exceeded the context limit, so the later text was not analysed.</span>}
            </div>
            <label className="block text-[12px] font-medium text-slate-600">Summary<textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} className="field" /></label>
            <label className="mt-2 block text-[12px] font-medium text-slate-600">Manager notes (added to the specification)<textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className="field" /></label>
            {dirty && <PillButton className="mt-2" disabled={busy} onClick={() => run(() => api(`/projects/${id}/spec`, { method: "PATCH", body: { summary, notes } }), "Specification updated.")}>Save changes</PillButton>}
          </>
        )}
      </Card>
      {spec.clarifications.length > 0 && (
        <Card title={`Clarification questions (${open.length} open)`}>
          <div className="space-y-3">
            {spec.clarifications.map((c) => (
              <div key={c.id} className={`rounded-xl border p-3 ${c.status === "open" ? "border-violet-200 bg-violet-50/40" : "border-slate-100"}`}>
                <p className="text-[13px] font-medium text-slate-800">{c.question}</p>
                {c.why && <p className="text-[11px] text-slate-500">{c.why}</p>}
                {c.answer && <p className="mt-1 text-[12px] text-emerald-700">Answer: {c.answer}</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  {c.options.map((o) => <button key={o} onClick={() => setAnswers({ ...answers, [c.id]: o })} className={`rounded-full border px-3 py-1 text-[11px] ${answers[c.id] === o ? "border-brand-500 text-brand-600" : "border-slate-200 text-slate-600"}`}>{o}</button>)}
                </div>
                <div className="mt-2 flex gap-2">
                  <input aria-label="Your answer" value={answers[c.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [c.id]: e.target.value })} placeholder={c.answer ? "Change the answer" : "Type your answer"} className="field mt-0 flex-1" />
                  <PillButton variant="primary" disabled={busy || !answers[c.id]?.trim()} onClick={() => run(() => api(`/projects/${id}/clarifications/${c.id}`, { body: { answer: answers[c.id] } }))}>Save</PillButton>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      {a?.contradictions?.length > 0 && (
        <Card title={<span className="flex items-center gap-2 text-amber-700"><AlertTriangle size={16} />Conflicts between documents</span>}>
          {a!.contradictions.map((c: any, i: number) => <p key={i} className="border-b border-slate-50 py-2 text-[12px] text-slate-600"><b>{c.topic}:</b> {c.detail}</p>)}
        </Card>
      )}
      {a && (
        <div className="grid gap-4 md:grid-cols-2">
          {SPEC_SECTIONS.map(([key, label]) => (
            <Card key={key} title={<span>{label} <span className="text-slate-400">({(a[key] as EvidenceItem[] | undefined)?.length ?? 0})</span></span>}>
              {!(a[key] as EvidenceItem[] | undefined)?.length ? <p className="text-[12px] text-slate-400">Nothing found in the documents.</p> : (
                <ul className="max-h-56 space-y-2 overflow-y-auto pr-1">
                  {(a[key] as EvidenceItem[]).map((i, n) => <li key={n} className="text-[12px] text-slate-600">{i.text}<span className="block text-[10px] text-slate-400">{i.document} · {i.location}</span></li>)}
                </ul>
              )}
            </Card>
          ))}
        </div>
      )}
      {a && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13px] text-slate-600">{spec.status === "approved" ? `Approved by ${spec.approved_by}. You can generate the plan.` : open.length ? `Answer the ${open.length} open question(s) to approve.` : "Review the specification, then approve it."}</p>
            {spec.status === "approved" ? <PillButton variant="primary" onClick={onPlan}>Go to plan</PillButton>
              : <PillButton variant="success" disabled={busy || open.length > 0} onClick={() => run(() => api(`/projects/${id}/spec/approve`, { body: {} }), "Specification approved.")}><CheckCircle2 size={13} />Approve specification</PillButton>}
          </div>
        </Card>
      )}
    </div>
  );
}

function PlanTab({ id, toast, changed, onTasks }: { id: string; toast: Toast; changed: () => void; onTasks: () => void }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => { api<any>(`/projects/${id}/plan`).then((p) => { setPlan(p.id ? p : null); setLoaded(true); }).catch((e) => toast(e.message, "err")); }, [id, toast]);
  const run = async (fn: () => Promise<void>) => { setBusy(true); try { await fn(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  const generate = (force: boolean) => run(async () => { setPlan(await api(`/projects/${id}/plan/generate?force=${force}`, { body: {} })); setDirty(false); });
  const save = () => run(async () => { setPlan(await api(`/projects/${id}/plan/${plan!.id}`, { method: "PUT", body: plan!.plan })); setDirty(false); toast("Plan saved and suggestions recalculated."); });
  const approve = () => run(async () => {
    const r = await api<{ tasks: Task[] }>(`/projects/${id}/plan/${plan!.id}/approve`, { body: {} });
    toast(`${r.tasks.length} tasks are saved.`);
    setPlan(await api(`/projects/${id}/plan`));
    changed();
    onTasks();
  });
  const edit = (key: string, patch: Partial<PlanTask>) => {
    setPlan({ ...plan!, plan: { ...plan!.plan, tasks: plan!.plan.tasks.map((t) => (t.key === key ? { ...t, ...patch } : t)) } });
    setDirty(true);
  };
  const removeTask = (key: string) => {
    setPlan({ ...plan!, plan: { ...plan!.plan, tasks: plan!.plan.tasks.filter((t) => t.key !== key).map((t) => ({ ...t, depends_on_keys: t.depends_on_keys.filter((d) => d !== key) })) } });
    setDirty(true);
  };
  if (!loaded) return <div className="p-10 text-center text-sm text-slate-400">Loading…</div>;
  if (!plan) return <Card title="Project plan" action={<PillButton variant="primary" disabled={busy} onClick={() => generate(false)}><Sparkles size={13} />{busy ? "Generating…" : "Generate plan"}</PillButton>}><Empty>Approve the specification, then generate a plan. No tasks are created until you approve the plan.</Empty></Card>;
  const editable = plan.status === "draft";
  const p = plan.plan;
  return (
    <div className="space-y-5">
      <Card title={`Plan v${plan.version}`} action={<div className="flex flex-wrap gap-2">
        {editable && <PillButton disabled={busy} onClick={() => generate(true)}><RotateCcw size={13} />Regenerate</PillButton>}
        {editable && dirty && <PillButton disabled={busy} onClick={save}>Save edits</PillButton>}
        {editable && <PillButton variant="success" disabled={busy || dirty} onClick={approve}><CheckCircle2 size={13} />Approve and create tasks</PillButton>}
      </div>}>
        <div className="flex flex-wrap items-center gap-2 text-[11px]"><StatusPill status={plan.status} /><span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">Source: {plan.source}</span><span className="text-slate-400">Suggested people come from the allocation engine, not the AI.</span></div>
        <p className="mt-2 text-[13px] text-slate-600">{p.summary}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">{p.milestones.map((m) => <span key={m.name} className="rounded-full bg-brand-50 px-2.5 py-1 text-brand-700">{m.name} · day {m.due_day}</span>)}</div>
        {p.risks.map((r, i) => <p key={i} className="mt-2 text-[12px] text-amber-700">⚠ {r}</p>)}
        {p.resource_gaps.map((r, i) => <p key={i} className="mt-2 text-[12px] text-rose-600">Capacity gap: {r}</p>)}
      </Card>
      <div className="grid gap-3 lg:grid-cols-2">
        {p.tasks.map((t) => (
          <div key={t.key} className="min-w-0 rounded-2xl bg-white p-4 shadow-card">
            <div className="flex items-center gap-2 text-[11px] text-slate-400"><span className="truncate">{t.phase} · {t.milestone}</span>{editable && <button aria-label={`Remove ${t.title}`} onClick={() => removeTask(t.key)} className="ml-auto rounded-full p-1 hover:bg-rose-50 hover:text-rose-600"><X size={14} /></button>}</div>
            {editable ? <input aria-label="Task title" value={t.title} onChange={(e) => edit(t.key, { title: e.target.value })} className="field mt-1 font-medium" /> : <h3 className="mt-1 text-[14px] font-medium text-slate-800">{t.title}</h3>}
            <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-slate-500">
              <label>Priority{editable ? <select value={t.priority} onChange={(e) => edit(t.key, { priority: e.target.value })} className="field">{["Low", "Medium", "High", "Critical"].map((x) => <option key={x}>{x}</option>)}</select> : <div className="mt-1"><PriorityBadge priority={t.priority} /></div>}</label>
              <label>Effort (h){editable ? <input type="number" min={1} value={t.estimated_hours} onChange={(e) => edit(t.key, { estimated_hours: Number(e.target.value) })} className="field" /> : <div className="font-medium text-slate-700">{t.estimated_hours}</div>}</label>
              <label>Due day{editable ? <input type="number" min={1} value={t.deadline_days} onChange={(e) => edit(t.key, { deadline_days: Number(e.target.value) })} className="field" /> : <div className="font-medium text-slate-700">{t.deadline_days}</div>}</label>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">Skills: {Object.entries(t.required_skills).map(([k, v]) => `${k} (${v})`).join(", ")}</p>
            {t.depends_on_keys.length > 0 && <p className="text-[11px] text-slate-500">After: {t.depends_on_keys.map((d) => p.tasks.find((x) => x.key === d)?.title ?? d).join(", ")}</p>}
            {t.acceptance_criteria.length > 0 && <ul className="mt-1 list-inside list-disc text-[11px] text-slate-500">{t.acceptance_criteria.slice(0, 3).map((c, i) => <li key={i} className="truncate" title={c}>{c}</li>)}</ul>}
            <p className={`mt-2 rounded-lg p-2 text-[11px] ${t.suggested_assignee_id ? "bg-brand-50/60 text-slate-600" : "bg-rose-50 text-rose-700"}`}><b>{t.suggested_assignee_name ?? "No eligible employee"}</b> {t.suggestion_reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TasksTab({ id, tasks, isAdmin, toast, changed, summary }: { id: string; tasks: Task[]; isAdmin: boolean; toast: Toast; changed: () => void; summary: Summary | null }) {
  const [status, setStatus] = useState("All");
  const [q, setQ] = useState("");
  const [inspect, setInspect] = useState<Task | null>(null);
  const [edit, setEdit] = useState<Task | null>(null);
  const [form, setForm] = useState({ priority: "Medium", deadline_days: 14, estimated_hours: 8 });
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ title: "", skill: "", level: "Intermediate", estimated_hours: 8, priority: "Medium", deadline_days: 14 });
  const [history, setHistory] = useState<Task | null>(null);
  const name = (eid: string | null) => summary?.employees.find((e) => e.employee_id === eid)?.name ?? (eid ? eid : "Unassigned");
  const act = async (fn: () => Promise<unknown>, msg?: string) => { try { await fn(); if (msg) toast(msg); changed(); return true; } catch (e: any) { toast(e.message, "err"); return false; } };
  const shown = tasks.filter((t) => (status === "All" || t.status === status) && (t.title + t.id).toLowerCase().includes(q.toLowerCase()));
  const statuses = ["All", ...new Set(tasks.map((t) => t.status))];
  return (
    <Card title="Tasks" action={isAdmin && <div className="flex gap-2"><PillButton onClick={() => act(() => api(`/tasks/allocate-all?project_id=${id}`, { body: {} }), "Allocation finished. Check the approval queue.")}>Run allocation</PillButton><PillButton variant="primary" onClick={() => setAdding(true)}>Add task</PillButton></div>}>
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Search tasks" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tasks" className="field mt-0 min-w-[160px] flex-1" />
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-slate-200 px-2 py-2 text-[12px] outline-none">{statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ").toLowerCase()}</option>)}</select>
      </div>
      {!shown.length && <Empty>{tasks.length ? "No tasks match this filter." : "No tasks yet. Approve a plan or add one."}</Empty>}
      <div className="space-y-2">
        {shown.map((t) => (
          <div key={t.id} className="rounded-xl border border-slate-100 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold text-brand-600">{t.id}</span><PriorityBadge priority={t.priority} /><StatusPill status={t.status} />
              {t.blocked && <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] text-rose-700">Blocked: {t.blocked_reason}</span>}
              <span className="ml-auto text-[11px] text-slate-500">{name(t.assigned_to)} · {t.estimated_hours}h · due day {t.deadline_days}</span>
            </div>
            <p className="mt-1 text-[13px] font-medium text-slate-800">{t.title}</p>
            {t.acceptance_criteria.length > 0 && <p className="truncate text-[11px] text-slate-500" title={t.acceptance_criteria.join("; ")}>Accepts when: {t.acceptance_criteria.join("; ")}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              <PillButton onClick={() => setHistory(t)}>Activity ({t.activity.length})</PillButton>
              {isAdmin && <PillButton onClick={() => setInspect(t)}><UserPlus size={13} />Candidates</PillButton>}
              {isAdmin && <PillButton onClick={() => { setEdit(t); setForm({ priority: t.priority, deadline_days: t.deadline_days, estimated_hours: t.estimated_hours }); }}>Edit</PillButton>}
              {isAdmin && <PillButton onClick={() => {
                const reason = t.blocked ? "" : prompt("Why is this task blocked?") ?? "";
                if (t.blocked || reason) act(() => api(`/tasks/${t.id}`, { method: "PATCH", body: { blocked: !t.blocked, blocked_reason: reason || undefined } }));
              }}>{t.blocked ? <><Unlock size={13} />Unblock</> : <><Lock size={13} />Block</>}</PillButton>}
              {isAdmin && t.status === "DELIVERABLE_IN_REVIEW" && <PillButton variant="success" onClick={() => act(() => api(`/tasks/${t.id}/accept`, { body: {} }), `${t.id} accepted and counted as verified.`)}><CheckCircle2 size={13} />Accept deliverable</PillButton>}
              {isAdmin && t.status === "DELIVERABLE_IN_REVIEW" && <PillButton onClick={() => { const reason = prompt("What needs rework?"); if (reason) act(() => api(`/tasks/${t.id}/rework`, { body: { reason } }), "Sent back for rework."); }}>Request rework</PillButton>}
              {isAdmin && <PillButton onClick={() => { if (confirm(`Delete ${t.id}? This cannot be undone.`)) act(() => api(`/tasks/${t.id}`, { method: "DELETE" }), `${t.id} deleted.`); }}><Trash2 size={13} />Delete</PillButton>}
            </div>
          </div>
        ))}
      </div>
      <CandidateModal task={inspect} onClose={() => setInspect(null)} onAssigned={(m) => { toast(m); changed(); setInspect(null); }} />
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit ? `Edit ${edit.id}` : ""}>
        <div className="grid grid-cols-3 gap-3 text-[12px] text-slate-600">
          <label>Priority<select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="field">{["Low", "Medium", "High", "Critical"].map((p) => <option key={p}>{p}</option>)}</select></label>
          <label>Due day<input type="number" min={1} value={form.deadline_days} onChange={(e) => setForm({ ...form, deadline_days: Number(e.target.value) })} className="field" /></label>
          <label>Effort (h)<input type="number" min={1} value={form.estimated_hours} onChange={(e) => setForm({ ...form, estimated_hours: Number(e.target.value) })} className="field" /></label>
        </div>
        <div className="mt-4 flex justify-end gap-2"><PillButton onClick={() => setEdit(null)}>Cancel</PillButton><PillButton variant="primary" onClick={async () => { if (await act(() => api(`/tasks/${edit!.id}`, { method: "PATCH", body: form }), "Task updated.")) setEdit(null); }}>Save</PillButton></div>
      </Modal>
      <Modal open={adding} onClose={() => setAdding(false)} title="Add task">
        <form className="space-y-3 text-[12px] text-slate-600" onSubmit={async (e) => {
          e.preventDefault();
          const ok = await act(() => api(`/projects/${id}/tasks`, { body: { title: draft.title, required_skills: { [draft.skill]: draft.level }, estimated_hours: draft.estimated_hours, priority: draft.priority, deadline_days: draft.deadline_days } }), "Task added.");
          if (ok) { setAdding(false); setDraft({ ...draft, title: "", skill: "" }); }
        }}>
          <label className="block">Title<input required minLength={3} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="field" /></label>
          <div className="grid grid-cols-2 gap-3">
            <label>Required skill<input required value={draft.skill} onChange={(e) => setDraft({ ...draft, skill: e.target.value })} className="field" /></label>
            <label>Level<select value={draft.level} onChange={(e) => setDraft({ ...draft, level: e.target.value })} className="field">{["Beginner", "Intermediate", "Advanced", "Expert"].map((l) => <option key={l}>{l}</option>)}</select></label>
            <label>Effort (h)<input type="number" min={1} value={draft.estimated_hours} onChange={(e) => setDraft({ ...draft, estimated_hours: Number(e.target.value) })} className="field" /></label>
            <label>Due day<input type="number" min={1} value={draft.deadline_days} onChange={(e) => setDraft({ ...draft, deadline_days: Number(e.target.value) })} className="field" /></label>
          </div>
          <label className="block">Priority<select value={draft.priority} onChange={(e) => setDraft({ ...draft, priority: e.target.value })} className="field">{["Low", "Medium", "High", "Critical"].map((p) => <option key={p}>{p}</option>)}</select></label>
          <div className="flex justify-end gap-2"><PillButton onClick={() => setAdding(false)}>Cancel</PillButton><PillButton type="submit" variant="primary">Add task</PillButton></div>
        </form>
      </Modal>
      <Modal open={!!history} onClose={() => setHistory(null)} title={history ? `${history.id} activity` : ""}>
        {!history?.activity.length && <p className="text-[13px] text-slate-400">No activity recorded yet.</p>}
        {history?.activity.map((a, i) => <p key={i} className="border-b border-slate-50 py-2 text-[12px] text-slate-600"><span className="text-slate-400">{String(a.at).slice(0, 16).replace("T", " ")} · {String(a.actor)}</span><br />{String(a.text)}</p>)}
      </Modal>
    </Card>
  );
}

function Evaluation({ id, tasks }: { id: string; tasks: Task[] }) {
  const [ev, setEv] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api(`/projects/${id}/evaluation`).then(setEv).catch((e) => setErr(e.message)); }, [id, tasks]);
  if (err) return <Empty>{err}</Empty>;
  if (!ev) return <div className="p-10 text-center text-sm text-slate-400">Evaluating…</div>;
  const color: Record<string, string> = { Critical: "bg-rose-500 text-white", High: "bg-orange-400 text-white", Medium: "bg-amber-100 text-amber-800" };
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card title="Findings" action={<HealthBadge health={ev.health} />}>
        {!ev.findings.length && <Empty>No issues found from the available evidence.</Empty>}
        <div className="space-y-2">{ev.findings.map((f: any, i: number) => <div key={i} className="flex items-start gap-3 rounded-xl bg-slate-50 p-3"><span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${color[f.level] ?? ""}`}>{f.level}</span><div><div className="text-[13px] font-medium text-slate-700">{f.title}</div><div className="text-[12px] text-slate-500">{f.detail}</div></div></div>)}</div>
      </Card>
      <div className="min-w-0 space-y-5">
        <Card title="Corrective actions">{ev.corrective_actions.length ? <ul className="list-inside list-disc space-y-1 text-[13px] text-slate-600">{ev.corrective_actions.map((a: string) => <li key={a}>{a}</li>)}</ul> : <p className="text-[13px] text-slate-400">None recommended right now.</p>}</Card>
        <Card title="Requirement coverage">{ev.requirement_coverage ? <p className="text-[13px] text-slate-600">{ev.requirement_coverage.requirements - ev.requirement_coverage.uncovered.length} of {ev.requirement_coverage.requirements} extracted requirements match a task.</p> : <p className="text-[13px] text-slate-400">Not available until documents are analysed.</p>}</Card>
        <Card title="Limits of this evaluation">{ev.limitations.length ? <ul className="list-inside list-disc space-y-1 text-[12px] text-slate-500">{ev.limitations.map((a: string) => <li key={a}>{a}</li>)}</ul> : <p className="text-[12px] text-slate-400">No known evidence gaps.</p>}</Card>
      </div>
    </div>
  );
}
