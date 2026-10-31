import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, FileUp, Trash2, XCircle } from "lucide-react";
import { DragEvent, useEffect, useRef, useState } from "react";
import { api, apiUpload } from "../api";
import { AI_STEPS, AIProgress, useSingleRun } from "./AIProgress";
import { Card, Modal, PillButton } from "./ui";

type Issue = { field: string; severity: "error" | "warning"; message: string };
type Skill = { name: string; level: string };
type Row = {
  key: number; source_file?: string; issues: Issue[]; name: string; email: string; phone: string; employee_code: string; designation: string; department: string; skills: Skill[];
  years_experience: number | null; education: string[]; certifications: string[]; projects: string[]; links: string[];
};
type FileReport = { filename: string; status: string; source?: string; found: number; error?: string; warnings: string[] };
type Result = { imported: { employee_id: string; name: string; email: string }[]; failed: { name: string; email: string; reasons: string[] }[] };

const payload = (r: Row) => ({ name: r.name, email: r.email, phone: r.phone, employee_code: r.employee_code, designation: r.designation, department: r.department, skills: r.skills, years_experience: r.years_experience, education: r.education, certifications: r.certifications, projects: r.projects, links: r.links });
const skillsText = (s: Skill[]) => s.map((x) => `${x.name} (${x.level})`).join(", ");
const parseSkills = (text: string): Skill[] => text.split(",").map((part) => {
  const m = part.trim().match(/^(.*?)\s*\((Beginner|Intermediate|Advanced|Expert)\)\s*$/i);
  return m ? { name: m[1].trim(), level: m[2][0].toUpperCase() + m[2].slice(1).toLowerCase() } : { name: part.trim(), level: "Intermediate" };
}).filter((s) => s.name);
const splitList = (text: string) => text.split(/\n/).map((x) => x.trim()).filter(Boolean);

export function EmployeeImport({ toast, reload }: { toast: (m: string, k?: "ok" | "err") => void; reload: () => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [files, setFiles] = useState<FileReport[]>([]);
  const [pct, setPct] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const { busy, run } = useSingleRun();
  const input = useRef<HTMLInputElement>(null);
  const nextKey = useRef(1);
  const revision = useRef(0);

  const upload = (list: FileList | File[]) => {
    const chosen = [...list];
    if (!chosen.length) return;
    run("analyze", async () => {
      const form = new FormData();
      chosen.forEach((f) => form.append("files", f));
      setPct(0);
      setResult(null);
      try {
        const r = await apiUpload<{ records: Omit<Row, "key">[]; files: FileReport[] }>("/org/employees/import/analyze", form, setPct);
        setFiles(r.files);
        setRows(r.records.map((x) => ({ ...x, key: nextKey.current++ })));
        toast(r.records.length ? `Found ${r.records.length} employee record(s). Review them before importing.` : "No employee records were found.", r.records.length ? "ok" : "err");
      } catch (e: any) {
        toast(e.message, "err");
      } finally {
        setPct(null);
        if (input.current) input.current.value = "";
      }
    });
  };

  // Rechecks after edits, on the server, so duplicates and invalid fields are always judged by the same rules as the import.
  const signature = JSON.stringify(rows.map(payload));
  useEffect(() => {
    if (!rows.length) return;
    const mine = ++revision.current;
    const timer = setTimeout(() => {
      api<Issue[][]>("/org/employees/import/validate", { body: { records: rows.map(payload) } }).then((issues) => {
        if (mine === revision.current) setRows((current) => current.length === issues.length ? current.map((r, i) => ({ ...r, issues: issues[i] })) : current);
      }).catch(() => {});
    }, 600);
    return () => clearTimeout(timer);
  }, [signature]); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (key: number, patch: Partial<Row>) => setRows((current) => current.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const remove = (key: number) => setRows((current) => current.filter((r) => r.key !== key));
  const hasError = (r: Row, field?: string) => r.issues.some((i) => i.severity === "error" && (!field || i.field === field));
  const ready = rows.filter((r) => !hasError(r));
  const blocked = rows.length - ready.length;

  const importNow = () => run("save", async () => {
    try {
      const r = await api<Result>("/org/employees/import/confirm", { body: { confirm: true, records: ready.map(payload) } });
      setResult(r);
      setRows((current) => current.filter((x) => hasError(x)));
      setConfirming(false);
      toast(`${r.imported.length} employee(s) imported.`);
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    }
  });

  const cell = (r: Row, field: keyof Row, label: string, width = "w-36") => (
    <td className="p-1 align-top">
      <input aria-label={`${label} for ${r.name || "this record"}`} aria-invalid={hasError(r, field as string)} value={(r[field] as string) ?? ""} onChange={(e) => edit(r.key, { [field]: e.target.value } as Partial<Row>)}
        className={`${width} rounded-lg border px-2 py-1.5 text-[12px] outline-none focus:border-brand-500 ${hasError(r, field as string) ? "border-rose-400 bg-rose-50" : r.issues.some((i) => i.field === field) ? "border-amber-300 bg-amber-50/50" : "border-slate-200"}`} />
    </td>
  );

  return (
    <Card title={<span className="flex items-center gap-2"><FileUp size={15} className="text-brand-500" />Import employees from documents</span>}>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e: DragEvent) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
        className={`rounded-xl border-2 border-dashed p-5 text-center transition ${drag ? "border-brand-500 bg-brand-50" : "border-slate-200"}`}>
        <p className="text-[13px] font-medium text-slate-700">Drag employee files here, or <button type="button" disabled={!!busy} className="text-brand-600 underline disabled:opacity-50" onClick={() => input.current?.click()}>browse</button></p>
        <p className="text-[11px] text-slate-400">CSV, XLSX, PDF, DOCX, PPTX or TXT · up to 10 files, 20 MB each · nothing is saved until you confirm</p>
        <input ref={input} type="file" multiple hidden accept=".csv,.xlsx,.pdf,.docx,.pptx,.txt" onChange={(e) => e.target.files && upload(e.target.files)} />
      </div>
      {busy === "analyze" && <div className="mt-3"><AIProgress steps={AI_STEPS.importing} pct={pct} /></div>}

      {files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {files.map((f, i) => (
            <li key={i} className="text-[12px] text-slate-600">
              <span className="font-medium">{f.filename}:</span> {f.status === "read" ? `${f.found} record(s), read using ${f.source}` : <span className="text-rose-600">{f.error}</span>}
              {f.warnings.map((w) => <span key={w} className="mt-0.5 flex items-start gap-1 text-amber-700"><AlertTriangle size={12} className="mt-0.5 shrink-0" />{w}</span>)}
            </li>
          ))}
        </ul>
      )}

      {rows.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <p className="mr-auto text-[12px] text-slate-600"><b>{ready.length}</b> ready to import{blocked > 0 && <>, <b className="text-rose-600">{blocked}</b> need fixing</>}. Edit anything below, and remove records you don't want.</p>
            <PillButton variant="primary" disabled={!ready.length || !!busy} onClick={() => setConfirming(true)}><CheckCircle2 size={13} />Review and import</PillButton>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="text-[11px] text-slate-500"><tr className="border-b border-slate-100"><th className="p-1" /><th className="p-1 font-medium">Name</th><th className="p-1 font-medium">Email</th><th className="p-1 font-medium">Phone</th><th className="p-1 font-medium">Employee ID</th><th className="p-1 font-medium">Designation</th><th className="p-1 font-medium">Department</th><th className="p-1 font-medium">Status</th><th className="p-1" /></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const errors = r.issues.filter((i) => i.severity === "error");
                  const warnings = r.issues.filter((i) => i.severity === "warning");
                  const expanded = open === r.key;
                  return [
                    <tr key={r.key} className="border-b border-slate-50">
                      <td className="p-1 align-top"><button aria-label={expanded ? `Hide details for ${r.name}` : `Show details for ${r.name}`} aria-expanded={expanded} onClick={() => setOpen(expanded ? null : r.key)} className="rounded p-1 text-slate-500 hover:bg-slate-100">{expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button></td>
                      {cell(r, "name", "Name")}
                      {cell(r, "email", "Email", "w-48")}
                      {cell(r, "phone", "Phone", "w-28")}
                      {cell(r, "employee_code", "Employee ID", "w-24")}
                      {cell(r, "designation", "Designation")}
                      {cell(r, "department", "Department", "w-28")}
                      <td className="min-w-[160px] p-1 align-top text-[11px]">
                        {errors.map((i) => <span key={i.field + i.message} className="flex items-start gap-1 text-rose-600"><XCircle size={12} className="mt-0.5 shrink-0" />{i.message}</span>)}
                        {!errors.length && <span className="flex items-center gap-1 text-emerald-700"><CheckCircle2 size={12} />Ready{warnings.length > 0 && `, ${warnings.length} missing`}</span>}
                        {warnings.filter((i) => i.field !== "name").length > 0 && <span className="block text-amber-700">{warnings.filter((i) => i.field !== "name").map((i) => i.message.replace(" is missing", "").replace("No skills found", "Skills")).join(", ")}</span>}
                        {warnings.filter((i) => i.field === "name").map((i) => <span key={i.message} className="block text-amber-700">{i.message}</span>)}
                      </td>
                      <td className="p-1 align-top"><button aria-label={`Remove ${r.name || "this record"}`} onClick={() => remove(r.key)} className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={14} /></button></td>
                    </tr>,
                    expanded && (
                      <tr key={`${r.key}-more`} className="border-b border-slate-100 bg-slate-50/60">
                        <td />
                        <td colSpan={8} className="p-2">
                          <div className="grid gap-2 md:grid-cols-2">
                            <label className="block text-[11px] font-medium text-slate-600">Skills, as Name (Level), separated by commas<input defaultValue={skillsText(r.skills)} onBlur={(e) => edit(r.key, { skills: parseSkills(e.target.value) })} className="field" /></label>
                            <label className="block text-[11px] font-medium text-slate-600">Years of experience<input type="number" min={0} max={70} step={0.5} value={r.years_experience ?? ""} onChange={(e) => edit(r.key, { years_experience: e.target.value === "" ? null : Number(e.target.value) })} className="field" /></label>
                            {([["education", "Education"], ["certifications", "Certifications"], ["projects", "Relevant projects"], ["links", "Profile links"]] as const).map(([field, label]) => (
                              <label key={field} className="block text-[11px] font-medium text-slate-600">{label}, one per line<textarea rows={2} defaultValue={r[field].join("\n")} onBlur={(e) => edit(r.key, { [field]: splitList(e.target.value) } as Partial<Row>)} className="field" /></label>
                            ))}
                          </div>
                          {r.source_file && <p className="mt-1 text-[11px] text-slate-400">From {r.source_file}. Imported skills stay marked as unverified until an administrator assesses them.</p>}
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-xl bg-emerald-50 p-3 text-[12px] text-emerald-800">
            <b className="flex items-center gap-1"><CheckCircle2 size={13} />Imported ({result.imported.length})</b>
            <ul className="mt-1">{result.imported.map((e) => <li key={e.employee_id}>{e.name} · {e.email} · {e.employee_id}</li>)}</ul>
            {result.imported.length > 0 && <p className="mt-2 text-[11px]">To let them sign in, create an invitation below using each person's email.</p>}
          </div>
          <div className="rounded-xl bg-rose-50 p-3 text-[12px] text-rose-800">
            <b className="flex items-center gap-1"><XCircle size={13} />Not imported ({result.failed.length})</b>
            {!result.failed.length && <p className="mt-1">None.</p>}
            <ul className="mt-1">{result.failed.map((e, i) => <li key={i}>{e.name || e.email || "Unnamed record"}: {e.reasons.join("; ")}</li>)}</ul>
          </div>
        </div>
      )}

      <Modal open={confirming} onClose={() => busy !== "save" && setConfirming(false)} title="Import these employees?">
        <p className="text-[13px] text-slate-600">This adds <b>{ready.length}</b> employee record(s) to your company.{blocked > 0 && <> <b>{blocked}</b> record(s) with problems will stay here for you to fix.</>}</p>
        <ul className="mt-2 max-h-52 overflow-y-auto rounded-xl bg-slate-50 p-3 text-[12px] text-slate-600">{ready.map((r) => <li key={r.key}>{r.name} · {r.email}{r.designation ? ` · ${r.designation}` : ""}</li>)}</ul>
        <p className="mt-2 text-[11px] text-slate-500">They won't get sign-in access or task assignments yet, and their skills stay unverified until assessed.</p>
        {busy === "save" && <div className="mt-3"><AIProgress steps={AI_STEPS.saving} compact /></div>}
        <div className="mt-4 flex justify-end gap-2"><PillButton disabled={busy === "save"} onClick={() => setConfirming(false)}>Cancel</PillButton><PillButton variant="success" disabled={!!busy} onClick={importNow}>{busy === "save" ? "Importing…" : `Import ${ready.length}`}</PillButton></div>
      </Modal>
    </Card>
  );
}
