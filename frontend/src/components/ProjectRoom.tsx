import { CheckCircle2, Download, FileUp, Search, Send, Trash2 } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, apiDownload, apiUpload } from "../api";
import { Card, Empty, PillButton, StatusPill } from "./ui";
import type { RoomMessage, RoomView } from "../types";

type Toast = (m: string, k?: "ok" | "err") => void;

/** Project discussion. Refreshes by polling; the server checks membership on every request. */
export function ProjectRoom({ id, canManage, username, toast }: { id: string; canManage: boolean; username: string; toast: Toast }) {
  const [room, setRoom] = useState<RoomView | null>(null);
  const [denied, setDenied] = useState<string | null>(null);
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RoomMessage[] | null>(null);
  const [minutes, setMinutes] = useState({ title: "", text: "" });
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api<RoomView>(`/projects/${id}/room`).then((r) => { setRoom(r); setDenied(null); }).catch((e) => setDenied(e.message));
    api<RoomMessage[]>(`/projects/${id}/room/messages`).then(setMessages).catch(() => {});
  }, [id]);
  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    try {
      await api(`/projects/${id}/room/messages`, { body: { content: text } });
      setText("");
      load();
    } catch (error: any) { toast(error.message, "err"); }
  };
  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return setResults(null);
    try { setResults(await api<RoomMessage[]>(`/projects/${id}/room/messages?q=${encodeURIComponent(query)}`)); } catch (error: any) { toast(error.message, "err"); }
  };
  const upload = async (file?: File) => {
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try { await apiUpload(`/projects/${id}/room/files`, form); load(); } catch (error: any) { toast(error.message, "err"); } finally { setUploading(false); }
  };
  const addMinutes = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/projects/${id}/room/minutes`, { body: { title: minutes.title || "Meeting minutes", text: minutes.text } });
      setMinutes({ title: "", text: "" });
      load();
    } catch (error: any) { toast(error.message, "err"); }
  };
  const approve = async (minutesId: string) => {
    try { await api(`/projects/${id}/room/minutes/${minutesId}/approve`, { body: {} }); toast("Minutes approved. Decisions and action items are saved."); load(); } catch (error: any) { toast(error.message, "err"); }
  };
  const remove = async (fileId: string) => {
    try { await api(`/projects/${id}/room/files/${fileId}`, { method: "DELETE" }); load(); } catch (error: any) { toast(error.message, "err"); }
  };

  if (denied) return <Empty>{denied}</Empty>;
  if (!room) return <div className="p-10 text-center text-sm text-slate-400">Loading room…</div>;
  const active = room.members.filter((m) => m.status === "active");
  const shown = results ?? messages;

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
      <div className="min-w-0 space-y-5">
        <Card title={room.room.name} action={<form onSubmit={search} className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1.5"><Search size={13} className="text-slate-400" /><input aria-label="Search messages" value={query} onChange={(e) => { setQuery(e.target.value); if (!e.target.value) setResults(null); }} placeholder="Search" className="w-28 bg-transparent text-[12px] outline-none" /></form>}>
          <div className="max-h-[380px] space-y-2 overflow-y-auto rounded-xl bg-slate-50 p-3">
            {!shown.length && <p className="p-6 text-center text-[13px] text-slate-400">{results ? "No matching messages." : "No messages yet. Start the discussion."}</p>}
            {shown.map((m) => (
              <div key={m.id} className={`max-w-[85%] rounded-2xl px-3 py-2 text-[13px] ${m.username === username ? "ml-auto bg-brand-500 text-white" : "bg-white text-slate-700 shadow-sm"}`}>
                <div className={`text-[11px] ${m.username === username ? "text-white/80" : "text-slate-500"}`}>{m.display_name} · {m.created_at.slice(0, 16).replace("T", " ")}</div>
                <div className="whitespace-pre-line break-words">{m.content}</div>
              </div>
            ))}
          </div>
          <form onSubmit={send} className="mt-3 flex items-center gap-2">
            <input aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} placeholder="Message the team" className="field !mt-0 flex-1" />
            <input ref={fileRef} type="file" hidden onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
            <PillButton onClick={() => fileRef.current?.click()} disabled={uploading}><FileUp size={13} />{uploading ? "Uploading…" : "File"}</PillButton>
            <PillButton type="submit" variant="primary" disabled={!text.trim()}><Send size={13} />Send</PillButton>
          </form>
        </Card>

        <Card title="Meeting minutes">
          <form onSubmit={addMinutes} className="space-y-2">
            <input aria-label="Minutes title" value={minutes.title} onChange={(e) => setMinutes({ ...minutes, title: e.target.value })} placeholder="Title" className="field !mt-0" />
            <textarea aria-label="Minutes text" rows={4} value={minutes.text} onChange={(e) => setMinutes({ ...minutes, text: e.target.value })} placeholder={"Paste the minutes. Lines like Date:, Attendees:, Decision:, Action:, Risk: are recognized."} className="field !mt-0" />
            <PillButton type="submit" variant="primary" disabled={minutes.text.trim().length < 10}>Add minutes</PillButton>
          </form>
          <div className="mt-3 space-y-2">
            {room.minutes.map((m) => {
              const f = m.extracted.facts;
              return (
                <div key={m.id} className="rounded-xl border border-slate-100 p-3 text-[12px] text-slate-600">
                  <div className="flex flex-wrap items-center gap-2"><b className="text-[13px] text-slate-800">{m.title}</b><StatusPill status={m.status} /><span className="text-slate-400">{m.source}</span>
                    {canManage && m.status === "draft" && <PillButton variant="success" className="ml-auto" onClick={() => approve(m.id)}><CheckCircle2 size={12} />Approve</PillButton>}</div>
                  {m.status === "draft" && <p className="mt-1 text-amber-700">Not approved yet, so nothing here counts as an agreed decision.</p>}
                  {f.meeting_date && <p className="mt-1">Date: {f.meeting_date}</p>}
                  {!!f.participants.length && <p>Participants: {f.participants.join(", ")}</p>}
                  {!!f.decisions.length && <p>Decisions: {f.decisions.join("; ")}</p>}
                  {!!f.action_items.length && <p>Actions: {f.action_items.map((a) => `${a.text}${a.owner ? ` (${a.owner})` : ""}`).join("; ")}</p>}
                  {!!f.open_questions.length && <p>Open questions: {f.open_questions.join("; ")}</p>}
                  {!!f.risks.length && <p>Risks: {f.risks.join("; ")}</p>}
                  {!!m.extracted.interpretations.length && <p className="mt-1 italic text-violet-700">AI interpretation, not in the text: {m.extracted.interpretations.join("; ")}</p>}
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <aside className="min-w-0 space-y-5">
        <Card title={`Team (${active.length})`}>
          {!active.length && <p className="text-[12px] text-slate-400">Nobody is assigned to this project yet.</p>}
          <ul className="space-y-1 text-[13px] text-slate-700">{active.map((m) => <li key={m.username}>{m.display_name} <span className="text-[11px] text-slate-400">{m.role}</span></li>)}</ul>
        </Card>
        <Card title="Decisions">
          {!room.decisions.length && <p className="text-[12px] text-slate-400">No approved decisions yet.</p>}
          <ul className="space-y-1 text-[12px] text-slate-700">{room.decisions.map((d) => <li key={d.id}>• {d.text} <span className="text-slate-400">({d.approved_by})</span></li>)}</ul>
        </Card>
        <Card title="Action items">
          {!room.action_items.length && <p className="text-[12px] text-slate-400">No action items yet.</p>}
          <ul className="space-y-1 text-[12px] text-slate-700">{room.action_items.map((a) => <li key={a.id}>• {a.text}{a.owner ? ` · ${a.owner}` : ""}{a.due ? ` · due ${a.due}` : ""}</li>)}</ul>
        </Card>
        <Card title="Files">
          {!room.attachments.length && <p className="text-[12px] text-slate-400">No files yet.</p>}
          <ul className="space-y-1">{room.attachments.map((f) => (
            <li key={f.id} className="flex items-center gap-2 text-[12px] text-slate-700">
              <span className="min-w-0 flex-1 truncate" title={f.filename}>{f.filename}</span>
              <button aria-label={`Download ${f.filename}`} className="text-brand-600" onClick={() => apiDownload(`/projects/${id}/room/files/${f.id}`, f.filename).catch((e) => toast(e.message, "err"))}><Download size={14} /></button>
              {(canManage || f.uploaded_by === username) && <button aria-label={`Remove ${f.filename}`} className="text-rose-500" onClick={() => remove(f.id)}><Trash2 size={14} /></button>}
            </li>
          ))}</ul>
          {!!room.attachments.length && <p className="mt-2 text-[11px] text-slate-400">Files are not scanned for malware. Open them with care.</p>}
        </Card>
      </aside>
    </div>
  );
}
