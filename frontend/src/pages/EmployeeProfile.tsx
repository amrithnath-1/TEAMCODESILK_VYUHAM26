import { ArrowLeft, BadgeCheck, ExternalLink, FileUp, Link2, RefreshCw, ShieldAlert, Sparkles, Unlink } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload } from "../api";
import { ScoreGrid } from "../components/Modals";
import { Avatar, Bar, Card, Empty, Modal, PillButton, StatusPill } from "../components/ui";
import type { Intelligence, Nav, SkillAssessment } from "../types";

const KIND: Record<string, { label: string; cls: string }> = {
  verified: { label: "Verified", cls: "bg-emerald-50 text-emerald-700" },
  employee_reported: { label: "Employee-reported", cls: "bg-amber-50 text-amber-700" },
  ai_inferred: { label: "Inferred", cls: "bg-violet-50 text-violet-700" },
};

export function EmployeeProfile({ employeeId, isAdmin, isSelf, onNav, toast, reload }: { employeeId: string; isAdmin: boolean; isSelf: boolean; onNav: Nav; toast: (m: string, k?: "ok" | "err") => void; reload: () => void }) {
  const [data, setData] = useState<Intelligence | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [skill, setSkill] = useState<SkillAssessment | null>(null);
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState("");
  const [uploading, setUploading] = useState(false);
  const [linkValues, setLinkValues] = useState<Record<string, string>>({});
  const [form, setForm] = useState({ bio: "", education: "", certifications: "", previous_projects: "", portfolio_urls: "" });
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<Intelligence>(`/employees/${employeeId}/intelligence`).then((d) => {
    setData(d);
    setForm({ bio: d.profile.bio, education: d.profile.education.join("\n"), certifications: d.profile.certifications.join("\n"), previous_projects: d.profile.previous_projects.join("\n"), portfolio_urls: d.profile.portfolio_urls.join("\n") });
  }).catch((e) => setErr(e.message)), [employeeId]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>, msg?: string) => { try { await fn(); if (msg) toast(msg); await load(); reload(); return true; } catch (e: any) { toast(e.message, "err"); return false; } };
  if (err) return <Empty>{err}</Empty>;
  if (!data) return <div className="p-10 text-center text-sm text-slate-400">Loading profile…</div>;
  const e = data.employee;
  const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
  const canEdit = isSelf || isAdmin;

  const uploadResume = async (f: File) => {
    const fd = new FormData();
    fd.append("file", f);
    if (target.trim()) fd.append("target_text", target);
    setUploading(true);
    try { await apiUpload(`/employees/${employeeId}/resume`, fd); toast("Resume processed."); await load(); } catch (x: any) { toast(x.message, "err"); } finally { setUploading(false); if (file.current) file.current.value = ""; }
  };
  const r = data.resume;

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          {isAdmin && <button aria-label="Back to workforce" onClick={() => onNav("workforce")} className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><ArrowLeft size={18} /></button>}
          <Avatar name={e.name} id={e.employee_id} size={52} />
          <div className="mr-auto min-w-0">
            <h1 className="text-xl font-semibold text-slate-800">{e.name} <span className="text-[12px] font-normal text-slate-400">{e.employee_id}</span></h1>
            <p className="text-[13px] text-slate-500">{e.designation} · {e.department} · {e.years_exp} yrs · {e.email}</p>
          </div>
          <span className={`rounded-full px-3 py-1.5 text-[12px] font-medium ${e.sufficient_evidence ? "bg-brand-50 text-brand-700" : "bg-violet-50 text-violet-700"}`}>{e.level}</span>
          <StatusPill status={e.status} />
        </div>
        <div className="mt-4"><ScoreGrid e={e} /></div>
        {e.dispute_status !== "None" && (
          <div className="mt-4 rounded-xl bg-amber-50 p-3 text-[13px]">
            <div className="font-medium text-amber-800">Evidence dispute: {e.dispute_status}</div>
            {e.dispute_note && <p className="mt-1 text-amber-700">“{e.dispute_note}”</p>}
            {isAdmin && e.dispute_status === "Pending Manager Review" && (
              <div className="mt-2 flex gap-2">
                <PillButton variant="success" onClick={() => act(() => api(`/employees/${employeeId}/dispute/resolve`, { body: { resolution: "Upheld", note: "Resolved from the profile page" } }), "Dispute upheld.")}>Uphold</PillButton>
                <PillButton onClick={() => act(() => api(`/employees/${employeeId}/dispute/resolve`, { body: { resolution: "Rejected", note: "Resolved from the profile page" } }), "Dispute rejected.")}>Reject</PillButton>
              </div>
            )}
          </div>
        )}
      </Card>

      <Card title="Skill assessment (0 to 10)" action={isAdmin && <PillButton onClick={() => act(() => api(`/employees/${employeeId}/skills/evaluate`, { body: {} }), "Skills re-evaluated from current evidence.")}><RefreshCw size={13} />Re-evaluate</PillButton>}>
        <p className="mb-3 text-[12px] text-slate-500">Each score is separate from performance, availability and workload. Open a skill to see its evidence.</p>
        {!data.skills.length && <Empty>No skills on record yet. Upload a resume or ask a manager to add skills.</Empty>}
        <div className="grid gap-2 md:grid-cols-2">
          {data.skills.map((s) => (
            <button key={s.skill} onClick={() => { setSkill(s); setReason(""); }} className="rounded-xl border border-slate-100 p-3 text-left transition hover:border-brand-500/40">
              <div className="flex items-center justify-between gap-2"><span className="truncate text-[13px] font-medium text-slate-800">{s.skill}</span><b className="text-[14px] text-slate-800">{s.score === null ? <span className="text-[11px] font-medium text-slate-400">Insufficient evidence</span> : `${s.score.toFixed(1)}/10`}</b></div>
              <div className="my-1.5"><Bar value={(s.score ?? 0) * 10} color={s.confidence === "High" ? "bg-emerald-400" : s.confidence === "Medium" ? "bg-brand-500" : "bg-amber-400"} /></div>
              <div className="flex flex-wrap items-center gap-1 text-[10px] text-slate-400"><span>{s.confidence} confidence</span>·<span>{s.last_evaluated ? `evaluated ${s.last_evaluated.slice(0, 10)}` : "not yet saved"}</span>
                {[...new Set(s.evidence.map((x) => x.kind))].map((k) => <span key={k} className={`rounded px-1.5 py-0.5 ${KIND[k]?.cls}`}>{KIND[k]?.label}</span>)}</div>
            </button>
          ))}
        </div>
        {data.challenges.length > 0 && (
          <div className="mt-4 space-y-1">
            <h3 className="text-[12px] font-semibold text-slate-600">Challenges</h3>
            {data.challenges.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-2 text-[12px] text-slate-600">
                <span className="mr-auto"><b>{c.skill}:</b> {c.reason}{c.resolution ? ` → ${c.resolution}` : ""}</span>
                <span className="text-[11px] text-slate-400">{c.status}</span>
                {isAdmin && c.status === "open" && <>
                  <PillButton variant="success" onClick={() => act(() => api(`/skill-challenges/${c.id}/resolve`, { body: { resolution: "Reevaluated", note: "Evidence rechecked" } }), "Re-evaluated.")}>Re-evaluate</PillButton>
                  <PillButton onClick={() => act(() => api(`/skill-challenges/${c.id}/resolve`, { body: { resolution: "Rejected", note: "Evidence supports the score" } }), "Challenge rejected.")}>Reject</PillButton>
                </>}
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Resume screen">
          <p className="mb-2 text-[12px] text-slate-500">A keyword and structure check. It is not a real applicant tracking system, and it only reports what is written in your file.</p>
          {canEdit && <>
            <label className="block text-[12px] font-medium text-slate-600">Job or role description to compare against (optional)<textarea rows={2} value={target} onChange={(x) => setTarget(x.target.value)} className="field" /></label>
            <input ref={file} type="file" hidden accept=".pdf,.docx,.txt" onChange={(x) => x.target.files?.[0] && uploadResume(x.target.files[0])} />
            <PillButton variant="primary" className="mt-2" disabled={uploading} onClick={() => file.current?.click()}><FileUp size={13} />{uploading ? "Processing…" : r ? "Upload a new resume" : "Upload resume"}</PillButton>
          </>}
          {!r && <p className="mt-3 text-[12px] text-slate-400">No resume uploaded yet.</p>}
          {r && (
            <div className="mt-3 space-y-2 text-[12px] text-slate-600">
              <p className="text-[11px] text-slate-400">{r.filename} · {r.source} · {r.uploaded_at.slice(0, 10)}</p>
              <div className="grid grid-cols-3 gap-2">
                <Mini label="Skill coverage" value={r.assessment.skill_coverage_pct === null ? "No target" : `${r.assessment.skill_coverage_pct}%`} />
                <Mini label="Structure" value={`${r.assessment.structure_score}/100`} />
                <Mini label="Skills found" value={String(r.assessment.skills_found)} />
              </div>
              <p className="text-[11px] text-slate-400">{r.assessment.criteria}</p>
              {r.assessment.matched_keywords.length > 0 && <p><b>Matched:</b> {r.assessment.matched_keywords.join(", ")}</p>}
              {r.assessment.missing_keywords.length > 0 && <p><b>Missing:</b> {r.assessment.missing_keywords.join(", ")}</p>}
              {r.extracted.skills.length > 0 && <p><b>Skills found:</b> {r.extracted.skills.join(", ")}</p>}
              {r.extracted.education.length > 0 && <p><b>Education:</b> {r.extracted.education.join("; ")}</p>}
              {r.extracted.certifications.length > 0 && <p><b>Certifications:</b> {r.extracted.certifications.join("; ")}</p>}
              {r.assessment.formatting_issues.map((i) => <p key={i} className="text-amber-700">⚠ {i}</p>)}
              {r.assessment.suggestions.map((i) => <p key={i}>• {i}</p>)}
            </div>
          )}
        </Card>

        <Card title="Professional accounts">
          <p className="mb-2 text-[12px] text-slate-500">Only you can link your accounts. Data is used as skill evidence only; private content and activity levels are never read.</p>
          <div className="space-y-2">
            {data.links.map((l) => (
              <div key={l.provider} className="rounded-xl border border-slate-100 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mr-auto text-[13px] font-medium text-slate-800">{l.label}</span>
                  <StatusPill status={l.status} />
                  {l.url && <a href={l.url} target="_blank" rel="noreferrer noopener" aria-label={`Open ${l.label} profile`} className="text-slate-400 hover:text-brand-600"><ExternalLink size={14} /></a>}
                  {isSelf && l.status !== "not_connected" && <button aria-label={`Remove ${l.label}`} onClick={() => act(() => api(`/employees/${employeeId}/links/${l.provider}`, { method: "DELETE" }), `${l.label} removed.`)} className="text-slate-400 hover:text-rose-600"><Unlink size={14} /></button>}
                </div>
                <p className="mt-1 text-[11px] text-slate-500">{l.status_detail ?? (l.mode === "public_api" ? "Reads public repositories through GitHub's API." : l.setup_note)}</p>
                {l.data.languages && Object.keys(l.data.languages).length > 0 && <p className="mt-1 text-[11px] text-slate-600">Languages: {Object.entries(l.data.languages).map(([k, v]) => `${k} (${v})`).join(", ")}</p>}
                {isSelf && (
                  <form className="mt-2 flex gap-2" onSubmit={(x) => { x.preventDefault(); act(() => api(`/employees/${employeeId}/links`, { body: { provider: l.provider, value: linkValues[l.provider] ?? "" } })).then((ok) => ok && setLinkValues({ ...linkValues, [l.provider]: "" })); }}>
                    <input aria-label={`${l.label} ${l.mode === "public_api" ? "username" : "URL"}`} value={linkValues[l.provider] ?? ""} onChange={(x) => setLinkValues({ ...linkValues, [l.provider]: x.target.value })} placeholder={l.mode === "public_api" ? "GitHub username" : "https://…"} className="field mt-0 min-w-0 flex-1" />
                    <PillButton type="submit" disabled={!(linkValues[l.provider] ?? "").trim()}><Link2 size={13} />{l.mode === "public_api" ? "Connect" : "Save link"}</PillButton>
                  </form>
                )}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Profile details" action={canEdit && <PillButton variant="primary" onClick={() => act(() => api(`/employees/${employeeId}/profile`, { method: "PUT", body: { bio: form.bio, education: lines(form.education), certifications: lines(form.certifications), previous_projects: lines(form.previous_projects), portfolio_urls: lines(form.portfolio_urls) } }), "Profile saved.")}>Save profile</PillButton>}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="block text-[12px] font-medium text-slate-600 md:col-span-2">About<textarea rows={2} disabled={!canEdit} value={form.bio} onChange={(x) => setForm({ ...form, bio: x.target.value })} className="field" /></label>
          {(["education", "certifications", "previous_projects", "portfolio_urls"] as const).map((k) => (
            <label key={k} className="block text-[12px] font-medium capitalize text-slate-600">{k.replace("_", " ")} (one per line)<textarea rows={3} disabled={!canEdit} value={form[k]} onChange={(x) => setForm({ ...form, [k]: x.target.value })} className="field" /></label>
          ))}
        </div>
        {data.completed.length > 0 && <p className="mt-3 text-[12px] text-slate-600"><b>Verified completed work:</b> {data.completed.map((t) => `${t.id} ${t.title}`).join("; ")}</p>}
      </Card>

      <Modal open={!!skill} onClose={() => setSkill(null)} wide title={skill ? `${skill.skill}: ${skill.score === null ? "insufficient evidence" : `${skill.score.toFixed(1)}/10`}` : ""}>
        {skill && (
          <div className="space-y-3">
            <p className="text-[12px] text-slate-500">{skill.confidence} confidence · last evaluated {skill.last_evaluated?.slice(0, 10) ?? "not yet saved"}</p>
            <div className="space-y-2">
              {skill.evidence.map((x, i) => (
                <div key={i} className="flex items-start gap-2 rounded-xl bg-slate-50 p-3 text-[12px]">
                  {x.kind === "verified" ? <BadgeCheck size={15} className="mt-0.5 text-emerald-500" /> : x.kind === "ai_inferred" ? <Sparkles size={15} className="mt-0.5 text-violet-500" /> : <ShieldAlert size={15} className="mt-0.5 text-amber-500" />}
                  <div><span className={`rounded px-1.5 py-0.5 text-[10px] ${KIND[x.kind]?.cls}`}>{KIND[x.kind]?.label}</span> <b className="text-slate-700">{x.source}</b><div className="text-slate-500">{x.detail}</div></div>
                </div>
              ))}
            </div>
            {skill.missing_evidence.length > 0 && <div><h4 className="text-[12px] font-semibold text-slate-600">Missing evidence</h4><ul className="list-inside list-disc text-[12px] text-slate-500">{skill.missing_evidence.map((m) => <li key={m}>{m}</li>)}</ul></div>}
            {skill.history && skill.history.length > 1 && <p className="text-[12px] text-slate-500">History: {skill.history.map((h) => h.score ?? "n/a").join(" → ")}</p>}
            {isSelf && (
              <div className="border-t border-slate-100 pt-3">
                <label className="block text-[12px] font-medium text-slate-600">Think this is wrong? Request a re-evaluation<textarea rows={2} value={reason} onChange={(x) => setReason(x.target.value)} placeholder="Point to the evidence that was missed" className="field" /></label>
                <PillButton variant="primary" className="mt-2" disabled={reason.trim().length < 5} onClick={async () => { if (await act(() => api(`/employees/${employeeId}/skills/challenge`, { body: { skill: skill.skill, reason } }), "Sent to your manager.")) setSkill(null); }}>Submit challenge</PillButton>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-100 p-2"><div className="text-[15px] font-bold text-slate-800">{value}</div><div className="text-[10px] text-slate-400">{label}</div></div>;
}
