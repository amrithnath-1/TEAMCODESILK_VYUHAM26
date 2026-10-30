import { Send, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";
import { PillButton } from "../components/ui";
import type { OnboardingStatus, SessionUser } from "../types";

/** Conversational company setup. Answers are stored as a structured profile, so signing out never restarts it. */
export function Onboarding({ user, onComplete, onLogout }: { user: SessionUser; onComplete: () => void; onLogout: () => void }) {
  const [state, setState] = useState<OnboardingStatus | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { api<OnboardingStatus>("/org/onboarding").then(setState).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [state]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const next = await api<OnboardingStatus>("/org/onboarding/message", { body: { message } });
      setState(next);
      setText("");
      if (next.state === "complete") onComplete();
    } catch (error: any) {
      setErr(error.message);      // the typed answer stays in the box so nothing is lost
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-[#f4f6fa] p-4">
      <div className="flex h-[min(720px,92vh)] w-full max-w-2xl flex-col rounded-3xl bg-white p-6 shadow-card">
        <header className="mb-4 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white"><ShieldCheck size={18} /></div>
          <div className="mr-auto min-w-0"><h1 className="truncate text-lg font-semibold text-slate-800">Set up {user.org_name}</h1><p className="text-[12px] text-slate-500">A short conversation so VYUHAM fits how your company works.</p></div>
          <PillButton onClick={onLogout}>Sign out</PillButton>
        </header>
        <div className="flex-1 space-y-3 overflow-y-auto rounded-2xl bg-slate-50 p-4" aria-live="polite">
          {!state && !err && <p className="text-[13px] text-slate-400">Loading…</p>}
          {state?.messages.map((m, i) => (
            <div key={i} className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[13px] ${m.role === "user" ? "ml-auto bg-brand-500 text-white" : "bg-white text-slate-700 shadow-sm"}`}>
              {m.role === "user" ? m.content : <div className="chat-md"><ReactMarkdown>{m.content}</ReactMarkdown></div>}
            </div>
          ))}
          <div ref={end} />
        </div>
        {err && <p role="alert" className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-[13px] text-rose-600">{err}</p>}
        <form onSubmit={send} className="mt-3 flex items-center gap-2">
          <input aria-label="Your answer" value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} disabled={busy}
            placeholder={state?.state === "review" ? "Type <start> to continue, or tell me what to correct" : "Type your answer"} className="field !mt-0 flex-1" />
          <PillButton type="submit" variant="primary" disabled={busy || !text.trim()}><Send size={13} />Send</PillButton>
        </form>
      </div>
    </div>
  );
}
