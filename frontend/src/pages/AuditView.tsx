import { ShieldCheck, ShieldX } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { api } from "../api";
import { Card, PillButton } from "../components/ui";
import type { AuditEntry } from "../types";

export function AuditView({ refreshKey }: { refreshKey: unknown }) {
  const [data, setData] = useState<{ entries: AuditEntry[]; verification: { valid: boolean; entries: number; broken_at: string | null; head?: string } } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const load = () => api("/audit?limit=200").then(setData).catch(() => {});
  useEffect(() => { load(); }, [refreshKey]);

  return (
    <Card title="Immutable audit ledger" action={<PillButton onClick={load}>Re-verify chain</PillButton>}>
      {data && (
        <div className={`mb-4 flex items-center gap-3 rounded-xl p-4 ${data.verification.valid ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
          {data.verification.valid ? <ShieldCheck /> : <ShieldX />}
          <div className="text-[13px]">
            <div className="font-semibold">{data.verification.valid ? "SHA-256 hash chain intact" : `Chain broken at ${data.verification.broken_at}`}</div>
            <div className="break-all text-[11px] opacity-80">{data.verification.entries} append-only entries · head {data.verification.head?.slice(0, 32)}…</div>
          </div>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-[12px]">
          <thead className="text-slate-500"><tr className="border-b border-slate-100"><th className="py-2 font-medium">ID</th><th className="font-medium">Time (UTC)</th><th className="font-medium">Actor</th><th className="font-medium">Action</th><th className="font-medium">Entity</th><th className="font-medium">SHA-256 proof</th></tr></thead>
          <tbody>
            {data?.entries.map((e) => (
              <Fragment key={e.id}>
                <tr onClick={() => setOpen(open === e.id ? null : e.id)} className="cursor-pointer border-b border-slate-50 hover:bg-slate-50">
                  <td className="py-2 font-medium text-slate-700">{e.id}</td>
                  <td className="text-slate-500">{e.timestamp.replace("T", " ").replace("Z", "")}</td>
                  <td className="text-slate-600">{e.actor}</td>
                  <td><span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700">{e.action}</span></td>
                  <td className="text-slate-600">{e.entity_id}</td>
                  <td className="font-mono text-[11px] text-slate-400">{e.sha256_proof.slice(0, 20)}…</td>
                </tr>
                {open === e.id && (
                  <tr className="bg-slate-50/60"><td colSpan={6} className="p-3">
                    <div className="break-all font-mono text-[10px] text-slate-400">prev: {e.prev_hash}<br />hash: {e.sha256_proof}</div>
                    <pre className="mt-2 overflow-x-auto rounded-lg bg-white p-3 text-[11px] text-slate-600">{JSON.stringify(e.details, null, 2)}</pre>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
