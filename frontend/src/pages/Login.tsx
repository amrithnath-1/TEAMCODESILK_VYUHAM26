import { Briefcase, Lock, ShieldCheck, User, UserCog } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, setToken } from "../api";
import type { SessionUser } from "../types";

export function Login({ onLogin }: { onLogin: (u: SessionUser) => void }) {
  const [mode, setMode] = useState<"admin" | "staff">("admin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ token: string; user: SessionUser }>("/auth/login", { body: { username, password } });
      if (mode === "admin" && r.user.role !== "ADMIN") throw new Error("This is a staff account — use the Staff login tab.");
      if (mode === "staff" && r.user.role !== "STAFF") throw new Error("This is an admin account — use the Admin login tab.");
      setToken(r.token);
      onLogin(r.user);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-[#f4f6fa] lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 via-brand-500 to-cyan-400 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-white/20"><ShieldCheck /></div>
          <div><div className="text-2xl font-bold">Vyuham</div><div className="text-xs uppercase tracking-widest text-white/70">AF-07 · Agent Forge '26</div></div>
        </div>
        <div>
          <h1 className="text-4xl font-semibold leading-tight">AI workforce intelligence that allocates work fairly — and explains why.</h1>
          <ul className="mt-8 space-y-3 text-[15px] text-white/85">
            <li>• Deterministic constraint engine + 7 coordinating agents</li>
            <li>• 6 separate scores, evidence-based, no surveillance</li>
            <li>• Human-in-the-loop approvals with a SHA-256 audit chain</li>
          </ul>
        </div>
        <div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10" />
        <div className="absolute -top-16 right-24 h-40 w-40 rounded-full bg-white/10" />
        <p className="text-xs text-white/60">Team CodeSilk · TEAMCODESILK_VYUHAM26</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-md rounded-3xl bg-white p-8 shadow-card">
          <h2 className="text-2xl font-semibold text-slate-800">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Choose your portal to continue.</p>

          <div className="mt-6 grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
            {(["admin", "staff"] as const).map((m) => (
              <button type="button" key={m} onClick={() => { setMode(m); setErr(null); setUsername(""); setPassword(""); }}
                className={`flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium transition ${mode === m ? "bg-white text-brand-600 shadow" : "text-slate-500"}`}>
                {m === "admin" ? <UserCog size={16} /> : <Briefcase size={16} />}{m === "admin" ? "Admin login" : "Staff login"}
              </button>
            ))}
          </div>

          <label className="mt-6 block text-[13px] font-medium text-slate-600">Username</label>
          <div className="mt-1.5 flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-brand-500">
            <User size={16} className="text-slate-400" />
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required
              className="w-full text-sm outline-none" />
          </div>
          <label className="mt-4 block text-[13px] font-medium text-slate-600">Password</label>
          <div className="mt-1.5 flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-brand-500">
            <Lock size={16} className="text-slate-400" />
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required className="w-full text-sm outline-none" />
          </div>

          {err && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{err}</p>}

          <button type="submit" disabled={busy} className="mt-6 w-full rounded-xl bg-brand-500 py-3 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-60">
            {busy ? "Signing in…" : `Sign in to ${mode === "admin" ? "Admin console" : "Staff portal"}`}
          </button>
        </form>
      </div>
    </div>
  );
}
