import { AlertTriangle, Bot, CheckCircle2, FileText, Loader2, Paperclip, Plus, RefreshCw, Send, ShieldQuestion, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { api, apiUpload } from "../api";
import type { AssistantAction, Nav } from "../types";
import { PillButton } from "./ui";

interface Msg {
  role: "user" | "assistant";
  text: string;
  state?: string;
  trace?: string[];
  citations?: { document: string; location: string }[];
  actions?: AssistantAction[];
  retry?: string;
  mode?: string;
}

const STATE_LABEL: Record<string, { label: string; cls: string }> = {
  needs_clarification: { label: "Asking a question", cls: "bg-violet-100 text-violet-700" },
  awaiting_approval: { label: "Waiting for your approval", cls: "bg-orange-100 text-orange-700" },
  executed: { label: "Action completed", cls: "bg-emerald-100 text-emerald-700" },
  failed: { label: "Action failed", cls: "bg-rose-100 text-rose-700" },
  rejected: { label: "Cancelled", cls: "bg-slate-100 text-slate-600" },
  error: { label: "Could not complete", cls: "bg-rose-100 text-rose-700" },
};

const ADMIN_PROMPTS = ["Analyze the documents and prepare the execution plan", "How is this project progressing?", "Who should do TSK-104?", "Are there any blockers?", "Is the workload fair right now?", "Vikram is on sick leave for 3 days"];
const STAFF_PROMPTS = ["What should I prioritize today?", "Show my tasks", "Why was I selected for my task?", "Who has free capacity this week?"];

export function AssistantPanel({ isAdmin, projects, defaultProject, reload, seed, onSeedUsed, onNav, height = 420 }: {
  isAdmin: boolean; projects: { project_id: string; name: string }[]; defaultProject?: string; reload: () => void; seed?: string | null; onSeedUsed?: () => void; onNav?: Nav; height?: number;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversation, setConversation] = useState<string | null>(null);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([]);
  const [project, setProject] = useState(defaultProject ?? "");
  const [upload, setUpload] = useState<string | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => { if (defaultProject) setProject(defaultProject); }, [defaultProject]);
  const loadList = useCallback(() => { api("/assistant/conversations").then(setConversations).catch(() => {}); }, []);
  useEffect(loadList, [loadList]);
  useEffect(() => { const el = scroller.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, busy]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setMsgs((m) => [...m.map((x) => (x.retry ? { ...x, retry: undefined } : x)), { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api<any>("/assistant/chat", { body: { message: q, conversation_id: conversation, project_id: project || null } });
      setConversation(r.conversation_id);
      setOffline(r.mode === "offline" ? r.setup_required : null);
      setMsgs((m) => [...m, { role: "assistant", text: r.response, state: r.state, trace: r.trace, citations: r.citations, actions: r.actions, mode: r.mode, retry: r.retryable ? q : undefined }]);
      reload();
      loadList();
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", text: e.message, state: "error", retry: q }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (seed) {
      send(seed);
      onSeedUsed?.();
    }
  }, [seed]); // eslint-disable-line react-hooks/exhaustive-deps

  const decide = async (a: AssistantAction, approve: boolean) => {
    setBusy(true);
    try {
      const r = await api<AssistantAction>(`/assistant/actions/${a.id}/${approve ? "approve" : "reject"}`, { body: {} });
      setMsgs((m) => [...m.map((x) => ({ ...x, actions: x.actions?.map((y) => (y.id === a.id ? r : y)) })),
        { role: "assistant" as const, text: r.result?.message ?? "Done.", state: r.status }]);
      reload();
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", text: e.message, state: "error" }]);
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    if (!id) return;
    const r = await api<any>(`/assistant/conversations/${id}`);
    setConversation(id);
    if (r.conversation.project_id) setProject(r.conversation.project_id);
    const pending = r.actions.filter((a: AssistantAction) => a.status === "pending");
    const list: Msg[] = r.messages.map((m: any) => ({ role: m.role, text: m.content, state: m.meta.state, trace: m.meta.trace, citations: m.meta.citations }));
    if (pending.length && list.length) list[list.length - 1].actions = pending;
    setMsgs(list);
  };

  const attach = async (files: FileList | null) => {
    if (!files?.length) return;
    if (!project) {
      setMsgs((m) => [...m, { role: "assistant", text: "Choose a project above the chat first, so these files are stored with the right project.", state: "needs_clarification" }]);
      return;
    }
    const form = new FormData();
    [...files].forEach((f) => form.append("files", f));
    try {
      const r = await apiUpload<{ results: { filename: string; status: string; error?: string }[] }>(`/projects/${project}/documents`, form, (p) => setUpload(`Uploading ${p}%`));
      const lines = r.results.map((x) => `${x.filename}: ${x.status === "uploaded" ? "uploaded, indexing now" : x.error ?? x.status}`).join("\n");
      setMsgs((m) => [...m, { role: "assistant", text: `${lines}\nAsk me to analyse the documents when you are ready.` }]);
      reload();
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", text: e.message, state: "error" }]);
    } finally {
      setUpload(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const prompts = isAdmin ? ADMIN_PROMPTS : STAFF_PROMPTS;
  return (
    <section aria-label="AI assistant" className="min-w-0 rounded-2xl bg-white p-4 shadow-card md:p-5">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white"><Bot size={18} /></span>
        <div className="mr-auto">
          <h2 className="text-[15px] font-semibold text-slate-800">VYUHAM AI Coordinator</h2>
          <p className="text-[11px] text-slate-400">{isAdmin ? "Analyse projects, plan work, allocate tasks, resolve risks" : "Your tasks, priorities and requests"}</p>
        </div>
        <label className="sr-only" htmlFor="chat-project">Project</label>
        <select id="chat-project" value={project} onChange={(e) => setProject(e.target.value)} className="max-w-[170px] rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 outline-none">
          <option value="">No project selected</option>
          {projects.map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
        </select>
        {conversations.length > 0 && (
          <select aria-label="Earlier conversations" value="" onChange={(e) => open(e.target.value).catch(() => {})} className="max-w-[140px] rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 outline-none">
            <option value="">History</option>
            {conversations.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        )}
        <PillButton onClick={() => { setConversation(null); setMsgs([]); }}><Plus size={13} />New</PillButton>
      </header>

      {offline && (
        <p className="mb-3 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span><b>Offline mode: Claude is not connected.</b> Answers come from built-in rules and your real data. {offline}</span>
        </p>
      )}

      <div ref={scroller} aria-live="polite" className="space-y-3 overflow-y-auto pr-1" style={{ height }}>
        {msgs.length === 0 && (
          <div className="grid h-full place-items-center text-center">
            <div>
              <p className="text-[15px] font-medium text-slate-700">{isAdmin ? "What would you like to work on?" : "How can I help with your work today?"}</p>
              <div className="mx-auto mt-3 flex max-w-xl flex-wrap justify-center gap-2">
                {prompts.map((p) => <button key={p} onClick={() => send(p)} className="rounded-full border border-slate-200 px-3 py-1.5 text-[12px] text-slate-600 hover:border-brand-500 hover:text-brand-600">{p}</button>)}
              </div>
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${m.role === "user" ? "rounded-br-sm bg-brand-500 text-white" : "rounded-bl-sm bg-slate-100 text-slate-700"}`}>
              {m.state && STATE_LABEL[m.state] && <span className={`mb-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATE_LABEL[m.state].cls}`}>{STATE_LABEL[m.state].label}</span>}
              {m.role === "user" ? <div className="whitespace-pre-line break-words">{m.text}</div> : (
                // react-markdown does not render raw HTML, so model and document text stays inert.
                <div className="chat-md break-words">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{ a: (p) => <a href={p.href} target="_blank" rel="noreferrer noopener">{p.children}</a> }}>{m.text}</ReactMarkdown>
                </div>
              )}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {[...new Map(m.citations.map((c) => [`${c.document}${c.location}`, c])).values()].slice(0, 5).map((c) => (
                    <span key={`${c.document}${c.location}`} className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-500"><FileText size={10} />{c.document} · {c.location}</span>
                  ))}
                </div>
              )}
              {m.actions?.map((a) => (
                <div key={a.id} className="mt-2 rounded-xl border border-orange-200 bg-white p-3 text-slate-700">
                  <div className="flex items-start gap-2 text-[12px] font-medium"><ShieldQuestion size={15} className="mt-0.5 shrink-0 text-orange-500" />{a.summary}</div>
                  {a.status === "pending" ? (
                    <div className="mt-2 flex gap-2">
                      <PillButton variant="success" disabled={busy} onClick={() => decide(a, true)}><CheckCircle2 size={13} />Approve</PillButton>
                      <PillButton disabled={busy} onClick={() => decide(a, false)}><XCircle size={13} />Cancel</PillButton>
                    </div>
                  ) : <p className="mt-1 text-[11px] text-slate-500">{a.status === "executed" ? "Completed and verified." : a.status === "failed" ? a.result?.message : "Cancelled."}</p>}
                  {a.status === "executed" && a.result?.project_id && onNav && <button onClick={() => onNav("project", a.result!.project_id)} className="mt-1 text-[11px] font-medium text-brand-600 hover:underline">Open project</button>}
                </div>
              ))}
              {m.retry && <PillButton className="mt-2" onClick={() => send(m.retry!)}><RefreshCw size={12} />Retry</PillButton>}
            </div>
          </div>
        ))}
        {busy && <div className="flex items-center gap-2 text-[12px] text-slate-400"><Loader2 size={14} className="animate-spin" />Working on it…</div>}
      </div>

      <form className="mt-3 flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        {isAdmin && (
          <>
            <input ref={fileInput} type="file" multiple hidden accept=".pdf,.docx,.pptx,.txt,.csv,.xlsx" onChange={(e) => attach(e.target.files)} />
            <button type="button" title="Attach project documents" aria-label="Attach project documents" onClick={() => fileInput.current?.click()} className="rounded-full border border-slate-200 p-2.5 text-slate-500 hover:bg-slate-50"><Paperclip size={15} /></button>
          </>
        )}
        <input aria-label="Message" value={input} onChange={(e) => setInput(e.target.value)} placeholder={upload ?? "Ask in plain English…"} className="min-w-0 flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-[13px] outline-none focus:border-brand-500" />
        <PillButton type="submit" variant="primary" disabled={busy || !input.trim()} className="px-4 py-2.5"><Send size={14} /><span className="hidden sm:inline">Send</span></PillButton>
      </form>
    </section>
  );
}
