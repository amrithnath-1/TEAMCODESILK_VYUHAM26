import { Lock, Mail, ShieldCheck, User } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, setToken } from "../api";
import type { SessionUser } from "../types";

type Mode = "signin" | "register" | "join";
const MODES: [Mode, string][] = [["signin", "Sign in"], ["register", "New company"], ["join", "Join company"]];

export function Login({ onLogin }: { onLogin: (u: SessionUser) => void }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [form, setForm] = useState({ username: "", password: "", company: "", name: "", email: "", code: "", department: "", designation: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = mode === "signin"
        ? await api<{ token: string; user: SessionUser }>("/auth/login", { body: { username: form.username, password: form.password } })
        : mode === "register"
          ? await api<{ token: string; user: SessionUser }>("/org/register", { body: { company_name: form.company, admin_name: form.name, email: form.email, password: form.password } })
          : await api<{ token: string; user: SessionUser }>("/org/join", { body: { code: form.code, name: form.name, email: form.email, password: form.password, department: form.department, designation: form.designation } });
      setToken(r.token);
      onLogin(r.user);
    } catch (error: any) {
      setErr(error.message);
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
            <li>• Each company's data kept separate</li>
            <li>• Budget-aware team plans that never trade away required skills</li>
            <li>• Human approvals with a SHA-256 audit chain</li>
          </ul>
        </div>
        <div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10" />
        <div className="absolute -top-16 right-24 h-40 w-40 rounded-full bg-white/10" />
        <p className="text-xs text-white/60">Team CodeSilk · TEAMCODESILK_VYUHAM26</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-md rounded-3xl bg-white p-8 shadow-card">
          <h2 className="text-2xl font-semibold text-slate-800">{mode === "signin" ? "Sign in" : mode === "register" ? "Register your company" : "Join your company"}</h2>
          <p className="mt-1 text-sm text-slate-500">{mode === "join" ? "Use the invitation code from your administrator." : mode === "register" ? "You become the organization's owner." : "Welcome back."}</p>

          <div className="mt-6 grid grid-cols-3 gap-1 rounded-2xl bg-slate-100 p-1" role="tablist">
            {MODES.map(([m, label]) => (
              <button type="button" role="tab" aria-selected={mode === m} key={m} onClick={() => { setMode(m); setErr(null); }}
                className={`rounded-xl py-2.5 text-[13px] font-medium transition ${mode === m ? "bg-white text-brand-600 shadow" : "text-slate-500"}`}>{label}</button>
            ))}
          </div>

          <div className="mt-5 space-y-3">
            {mode === "signin" && <Field icon={<User size={16} />} label="Username or email" value={form.username} onChange={set("username")} autoComplete="username" />}
            {mode === "register" && <Field icon={<ShieldCheck size={16} />} label="Company name" value={form.company} onChange={set("company")} autoComplete="organization" />}
            {mode === "join" && <Field icon={<Lock size={16} />} label="Invitation code" value={form.code} onChange={set("code")} autoComplete="off" />}
            {mode !== "signin" && <Field icon={<User size={16} />} label="Your name" value={form.name} onChange={set("name")} autoComplete="name" />}
            {mode !== "signin" && <Field icon={<Mail size={16} />} label="Work email" type="email" value={form.email} onChange={set("email")} autoComplete="email" />}
            {mode === "join" && (
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[13px] font-medium text-slate-600">Department<input value={form.department} onChange={set("department")} className="field" /></label>
                <label className="block text-[13px] font-medium text-slate-600">Designation<input value={form.designation} onChange={set("designation")} className="field" /></label>
              </div>
            )}
            <Field icon={<Lock size={16} />} label={mode === "signin" ? "Password" : "Password (at least 10 characters)"} type="password" value={form.password} onChange={set("password")} autoComplete={mode === "signin" ? "current-password" : "new-password"} />
          </div>

          {err && <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{err}</p>}

          <button type="submit" disabled={busy} className="mt-6 w-full rounded-xl bg-brand-500 py-3 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-60">
            {busy ? "One moment…" : mode === "signin" ? "Sign in" : mode === "register" ? "Create company" : "Join company"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({ icon, label, onChange, value, type = "text", autoComplete }: { icon: React.ReactNode; label: string; value: string; onChange: (e: { target: { value: string } }) => void; type?: string; autoComplete?: string }) {
  return (
    <label className="block text-[13px] font-medium text-slate-600">{label}
      <span className="mt-1.5 flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-brand-500">
        <span className="text-slate-400">{icon}</span>
        <input required type={type} value={value} onChange={onChange} autoComplete={autoComplete} className="w-full text-sm font-normal outline-none" />
      </span>
    </label>
  );
}
