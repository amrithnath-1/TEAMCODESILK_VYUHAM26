import { Copy, KeyRound, ShieldAlert, UserPlus } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Card, Empty, Modal, PillButton, StatusPill } from "../components/ui";
import type { Invitation, Member, Nav, SessionUser, SkillRequest } from "../types";

type Toast = (m: string, k?: "ok" | "err") => void;
const ROLE_LABELS: Record<string, string> = { OWNER: "Owner", ADMIN: "Administrator", MANAGER: "Manager", STAFF: "Employee" };

export function TeamView({ user, toast, reload, onNav, refreshKey }: { user: SessionUser; toast: Toast; reload: () => void; onNav: Nav; refreshKey: unknown }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [requests, setRequests] = useState<SkillRequest[]>([]);
  const [permissions, setPermissions] = useState<Record<string, string[]>>({});
  const [inviteForm, setInviteForm] = useState({ role: "STAFF", email: "" });
  const [newCode, setNewCode] = useState<string | null>(null);
  const [change, setChange] = useState<{ member: Member; role: string } | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState<SkillRequest | null>(null);
  const [review, setReview] = useState({ status: "approved", notes: "", score: "", confidence: "medium" });

  const load = useCallback(() => {
    api<Member[]>("/org/members").then(setMembers).catch((e) => toast(e.message, "err"));
    api<Invitation[]>("/org/invitations").then(setInvites).catch(() => {});
    api<SkillRequest[]>("/skill-requests").then(setRequests).catch(() => {});
    api("/org/roles").then(setPermissions).catch(() => {});
  }, [toast]);
  useEffect(load, [load, refreshKey]);

  const invite = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const r = await api<{ code: string }>("/org/invitations", { body: { role: inviteForm.role, email: inviteForm.email || null } });
      setNewCode(r.code);
      setInviteForm({ role: "STAFF", email: "" });
      load();
    } catch (error: any) { toast(error.message, "err"); }
  };

  const revoke = async (id: string) => {
    try { await api(`/org/invitations/${id}`, { method: "DELETE" }); load(); } catch (error: any) { toast(error.message, "err"); }
  };

  const applyRole = async (e: FormEvent) => {
    e.preventDefault();
    if (!change) return;
    setBusy(true);
    try {
      const { reauth_token } = await api<{ reauth_token: string }>("/org/reauth", { body: { password } });
      await api(`/org/members/${encodeURIComponent(change.member.username)}/role`, { body: { role: change.role, reauth_token } });
      toast(`${change.member.display_name} is now ${ROLE_LABELS[change.role]}.`);
      setChange(null);
      load();
      reload();
    } catch (error: any) {
      toast(error.message, "err");
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  const submitReview = async (e: FormEvent) => {
    e.preventDefault();
    if (!reviewing) return;
    try {
      await api(`/skill-requests/${reviewing.id}/review`, { body: { status: review.status, notes: review.notes, score: review.score === "" ? null : Number(review.score), confidence: review.confidence } });
      toast("Request updated.");
      setReviewing(null);
      load();
      reload();
    } catch (error: any) { toast(error.message, "err"); }
  };

  const pending = requests.filter((r) => r.status === "pending" || r.status === "under_review");
  const canChange = (m: Member) => m.username !== user.username && (user.org_role === "OWNER" || m.role !== "OWNER");
  const offered = user.org_role === "OWNER" ? ["STAFF", "MANAGER", "ADMIN", "OWNER"] : ["STAFF", "MANAGER"];

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
      <div className="min-w-0 space-y-5">
        <Card title={<span>Skill requests {pending.length > 0 && <span className="ml-1 rounded-full bg-rose-500 px-2 py-0.5 text-[11px] text-white">{pending.length}</span>}</span>}>
          {!requests.length && <Empty>No skill requests yet.</Empty>}
          <ul className="space-y-2">
            {requests.map((r) => (
              <li key={r.id} className="rounded-xl border border-slate-100 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <b className="text-[13px] text-slate-800">{r.skill}</b><span className="text-[12px] text-slate-500">{r.employee_name} · {r.kind.replace(/_/g, " ")}{r.requested_score != null ? ` · asks for ${r.requested_score}/10` : ""}</span>
                  <span className="ml-auto"><StatusPill status={r.status} /></span>
                </div>
                <p className="mt-1 text-[12px] text-slate-600">{r.explanation}</p>
                {r.evidence && <p className="text-[12px] text-slate-500">Evidence: {r.evidence}</p>}
                {r.review_notes && <p className="text-[12px] text-slate-500">Review ({r.reviewer}): {r.review_notes}</p>}
                <div className="mt-2 flex gap-2">
                  {!["approved", "rejected"].includes(r.status) && <PillButton variant="primary" onClick={() => { setReviewing(r); setReview({ status: "approved", notes: "", score: r.requested_score?.toString() ?? "", confidence: "medium" }); }}>Review</PillButton>}
                  <PillButton onClick={() => onNav("employee", r.employee_id)}>Open profile</PillButton>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Members">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-[13px]">
              <thead className="text-[12px] text-slate-500"><tr className="border-b border-slate-100"><th className="py-2 font-medium">Name</th><th className="font-medium">Sign-in</th><th className="font-medium">Role</th><th /></tr></thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.username} className="border-b border-slate-50">
                    <td className="py-2.5 font-medium text-slate-800">{m.display_name}</td>
                    <td className="text-slate-500">{m.username}</td>
                    <td>{ROLE_LABELS[m.role]}</td>
                    <td className="text-right">{canChange(m) && <PillButton onClick={() => setChange({ member: m, role: m.role === "STAFF" ? "MANAGER" : "STAFF" })}><KeyRound size={12} />Change role</PillButton>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <aside className="min-w-0 space-y-5">
        <Card title={<span className="flex items-center gap-2"><UserPlus size={15} className="text-brand-500" />Invite an employee</span>}>
          <form onSubmit={invite} className="space-y-3">
            <label className="block text-[12px] font-medium text-slate-600">Role<select value={inviteForm.role} onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })} className="field"><option value="STAFF">Employee</option><option value="MANAGER">Manager</option></select></label>
            <label className="block text-[12px] font-medium text-slate-600">Only for this email (optional)<input type="email" value={inviteForm.email} onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })} className="field" /></label>
            <PillButton type="submit" variant="primary">Create invitation</PillButton>
          </form>
          {newCode && (
            <div className="mt-3 rounded-xl bg-amber-50 p-3 text-[12px] text-amber-800">
              <b>Copy this code now.</b> It is shown only once and works once, for 7 days.
              <code className="mt-1 block break-all rounded bg-white p-2 text-slate-700">{newCode}</code>
              <PillButton className="mt-2" onClick={() => navigator.clipboard?.writeText(newCode).then(() => toast("Code copied."))}><Copy size={12} />Copy</PillButton>
            </div>
          )}
          <ul className="mt-3 space-y-1">
            {invites.slice(0, 8).map((i) => (
              <li key={i.id} className="flex items-center gap-2 text-[12px] text-slate-500">
                <span className="min-w-0 flex-1 truncate">{ROLE_LABELS[i.role]}{i.email ? ` · ${i.email}` : ""} · {i.used_at ? `used by ${i.used_by}` : i.revoked_at ? "revoked" : `expires ${i.expires_at.slice(0, 10)}`}</span>
                {!i.used_at && !i.revoked_at && <button className="text-rose-500 hover:underline" onClick={() => revoke(i.id)}>Revoke</button>}
              </li>
            ))}
          </ul>
        </Card>
      </aside>

      <Modal open={!!change} onClose={() => setChange(null)} title={change ? `Change ${change.member.display_name}'s role` : ""}>
        {change && (
          <form onSubmit={applyRole} className="space-y-3">
            <label className="block text-[12px] font-medium text-slate-600">New role<select value={change.role} onChange={(e) => setChange({ ...change, role: e.target.value })} className="field">{offered.filter((r) => r !== change.member.role).map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</select></label>
            <div className="rounded-xl bg-slate-50 p-3 text-[12px] text-slate-600"><b>{ROLE_LABELS[change.role]} can:</b><ul className="mt-1 list-disc pl-4">{(permissions[change.role] ?? []).map((p) => <li key={p}>{p}</li>)}</ul></div>
            {change.role === "OWNER" && <p className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-[12px] text-amber-800"><ShieldAlert size={14} className="mt-0.5 shrink-0" />This transfers ownership. You become an administrator.</p>}
            <label className="block text-[12px] font-medium text-slate-600">Confirm your password<input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="field" /></label>
            <div className="flex justify-end gap-2"><PillButton onClick={() => setChange(null)}>Cancel</PillButton><PillButton type="submit" variant="primary" disabled={busy || !password}>Confirm change</PillButton></div>
          </form>
        )}
      </Modal>

      <Modal open={!!reviewing} onClose={() => setReviewing(null)} title={reviewing ? `Review: ${reviewing.skill}` : ""}>
        {reviewing && (
          <form onSubmit={submitReview} className="space-y-3">
            <p className="text-[13px] text-slate-600">{reviewing.employee_name}: {reviewing.explanation}</p>
            <label className="block text-[12px] font-medium text-slate-600">Decision<select value={review.status} onChange={(e) => setReview({ ...review, status: e.target.value })} className="field"><option value="approved">Approve</option><option value="under_review">Mark under review</option><option value="more_information">Ask for more information</option><option value="rejected">Reject</option></select></label>
            {review.status === "approved" && (
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[12px] font-medium text-slate-600">Score (0-10)<input type="number" min={0} max={10} step={0.5} required value={review.score} onChange={(e) => setReview({ ...review, score: e.target.value })} className="field" /></label>
                <label className="block text-[12px] font-medium text-slate-600">Evidence confidence<select value={review.confidence} onChange={(e) => setReview({ ...review, confidence: e.target.value })} className="field"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
              </div>
            )}
            <label className="block text-[12px] font-medium text-slate-600">Notes<textarea rows={3} required={review.status === "rejected" || review.status === "more_information"} value={review.notes} onChange={(e) => setReview({ ...review, notes: e.target.value })} className="field" /></label>
            <div className="flex justify-end gap-2"><PillButton onClick={() => setReviewing(null)}>Cancel</PillButton><PillButton type="submit" variant="primary">Save decision</PillButton></div>
          </form>
        )}
      </Modal>
    </div>
  );
}
