import { Bell, Bot, FolderKanban, GitBranch, LayoutDashboard, LogOut, Menu, ScrollText, Search, Settings, ShieldCheck, UserCircle, Users, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import { Avatar, Toast } from "./components/ui";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AuditView } from "./pages/AuditView";
import { CoordinatorView } from "./pages/CoordinatorView";
import { EmployeeProfile } from "./pages/EmployeeProfile";
import { Login } from "./pages/Login";
import { ManagerView } from "./pages/ManagerView";
import { ProjectDetail } from "./pages/ProjectDetail";
import { ProjectsView } from "./pages/ProjectsView";
import { SettingsView } from "./pages/SettingsView";
import { StaffPortal } from "./pages/StaffPortal";
import { WorkforceView } from "./pages/WorkforceView";
import type { NotificationRow, ProjectProgress, SessionUser, Summary } from "./types";

const ADMIN_NAV = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "projects", label: "Projects", icon: FolderKanban },
  { key: "manager", label: "Allocation & Approvals", icon: GitBranch },
  { key: "coordinator", label: "AI Coordinator", icon: Bot },
  { key: "workforce", label: "Workforce", icon: Users },
  { key: "audit", label: "Audit Ledger", icon: ScrollText },
  { key: "settings", label: "Settings", icon: Settings },
];
const STAFF_NAV = [
  { key: "portal", label: "My Work", icon: LayoutDashboard },
  { key: "projects", label: "My Projects", icon: FolderKanban },
  { key: "profile", label: "My Profile", icon: UserCircle },
  { key: "coordinator", label: "AI Assistant", icon: Bot },
];

export default function App() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [booting, setBooting] = useState(true);
  const [view, setView] = useState("dashboard");
  const [viewId, setViewId] = useState<string | undefined>();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [projects, setProjects] = useState<ProjectProgress[]>([]);
  const [notes, setNotes] = useState<NotificationRow[]>([]);
  const [notesOpen, setNotesOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToastState] = useState<{ m: string; k: "ok" | "err" } | null>(null);
  const [chatSeed, setChatSeed] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [tick, setTick] = useState(0);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setSummary(null);
    setProjects([]);
    setNotes([]);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!getToken()) {
      setBooting(false);
      return;
    }
    api<SessionUser>("/auth/me").then((u) => { setUser(u); setView(u.role === "ADMIN" ? "dashboard" : "portal"); }).catch(logout).finally(() => setBooting(false));
  }, [logout]);

  const reload = useCallback(() => {
    if (!user) return;
    setTick((t) => t + 1);
    api<ProjectProgress[]>("/projects").then(setProjects).catch(() => {});
    api<NotificationRow[]>("/notifications").then(setNotes).catch(() => {});
    if (user.role === "ADMIN") {
      api<Summary>("/dashboard/summary").then((s) => { setSummary(s); setLoadErr(null); }).catch((e) => setLoadErr(e.message));
    }
  }, [user]);

  useEffect(() => {
    reload();
    if (!user) return;
    const t = setInterval(reload, 15000);     // dashboards refresh from persisted data
    return () => clearInterval(t);
  }, [reload, user]);

  const notify = useCallback((m: string, k: "ok" | "err" = "ok") => setToastState({ m, k }), []);

  const nav = useCallback((k: string, id?: string) => {
    setMenuOpen(false);
    setNotesOpen(false);
    if (k === "risks") {
      setView("dashboard");
      setTimeout(() => document.getElementById("risks")?.scrollIntoView({ behavior: "smooth" }), 80);
      return;
    }
    setView(k);
    setViewId(id);
    window.scrollTo({ top: 0 });
  }, []);

  if (booting) return <div className="grid min-h-screen place-items-center text-sm text-slate-400">Loading…</div>;
  if (!user) return <Login onLogin={(u) => { setUser(u); setView(u.role === "ADMIN" ? "dashboard" : "portal"); }} />;

  const isAdmin = user.role === "ADMIN";
  const items = isAdmin ? ADMIN_NAV : STAFF_NAV;
  const first = user.display_name.split(" (")[0];
  const unread = notes.filter((n) => !n.is_read).length;
  const reset = async () => {
    if (!confirm("Delete all documents, plans, conversations and changes, and restore the seeded demo data? A backup is saved first.")) return;
    try {
      await api("/reset", { body: { confirm: "RESET" } });
      notify("Demo data restored. A backup of the previous data was saved.");
      reload();
    } catch (e: any) { notify(e.message, "err"); }
  };
  const openNote = async (n: NotificationRow) => {
    await api(`/notifications/${n.id}/read`, { body: {} }).catch(() => {});
    reload();
    const target = n.link_view === "employee" ? "employee" : n.link_view ?? (isAdmin ? "dashboard" : "portal");
    nav(target === "manager" && !isAdmin ? "portal" : target, n.link_id ?? undefined);
  };
  const needSummary = isAdmin && !summary;

  return (
    <div className="min-h-screen bg-[#f4f6fa] lg:pl-60">
      {menuOpen && <button aria-label="Close menu" className="fixed inset-0 z-40 bg-slate-900/30 lg:hidden" onClick={() => setMenuOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r border-slate-100 bg-white transition-transform lg:translate-x-0 ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-2 px-5 py-4">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white"><ShieldCheck size={18} /></div>
          <div className="mr-auto leading-tight"><div className="text-lg font-bold tracking-tight text-brand-600">Vyuham</div><div className="-mt-0.5 text-[10px] font-medium uppercase tracking-widest text-slate-400">Workforce AI</div></div>
          <button aria-label="Close menu" className="rounded-full p-1 text-slate-400 lg:hidden" onClick={() => setMenuOpen(false)}><X size={18} /></button>
        </div>
        <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto px-3">
          {items.map((i) => {
            const active = view === i.key || (i.key === "projects" && view === "project") || (i.key === "workforce" && view === "employee");
            return (
              <button key={i.key} onClick={() => nav(i.key)} aria-current={active ? "page" : undefined}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition ${active ? "bg-brand-500 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                <i.icon size={17} />{i.label}
                {i.key === "manager" && !!summary?.pending_approvals.length && <span className={`ml-auto rounded-full px-1.5 text-[10px] font-bold ${active ? "bg-white text-brand-600" : "bg-rose-500 text-white"}`}>{summary.pending_approvals.length}</span>}
              </button>
            );
          })}
        </nav>
        <div className="border-t border-slate-100 p-3">
          <button onClick={logout} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-slate-600 hover:bg-slate-100"><LogOut size={17} />Sign out</button>
        </div>
      </aside>

      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-100 bg-white/90 px-4 py-3 backdrop-blur md:px-6">
        <button aria-label="Open menu" className="rounded-full p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setMenuOpen(true)}><Menu size={18} /></button>
        <form className="min-w-0 flex-1 md:max-w-sm" onSubmit={(e) => { e.preventDefault(); if (search.trim()) { setChatSeed(search); setSearch(""); nav("coordinator"); } }}>
          <label className="flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-slate-500">
            <Search size={15} /><input aria-label="Ask the AI coordinator" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Ask the AI anything…" className="w-full min-w-0 bg-transparent text-[13px] outline-none placeholder:text-slate-400" />
          </label>
        </form>
        <div className="relative ml-auto">
          <button aria-label={`Notifications, ${unread} unread`} onClick={() => setNotesOpen(!notesOpen)} className="relative rounded-full p-2 text-slate-500 hover:bg-slate-100">
            <Bell size={17} />
            {unread > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">{unread}</span>}
          </button>
          {notesOpen && (
            <div className="absolute right-0 top-11 z-50 max-h-[70vh] w-[320px] max-w-[85vw] overflow-y-auto rounded-2xl bg-white p-3 shadow-2xl">
              <div className="mb-2 flex items-center justify-between">
                <b className="text-[13px] text-slate-800">Notifications</b>
                {unread > 0 && <button className="text-[11px] text-brand-600 hover:underline" onClick={() => api("/notifications/read-all", { body: {} }).then(reload).catch(() => {})}>Mark all read</button>}
              </div>
              {!notes.length && <p className="p-4 text-center text-[12px] text-slate-400">Nothing yet.</p>}
              {notes.map((n) => (
                <button key={n.id} onClick={() => openNote(n)} className={`mb-1 block w-full rounded-xl p-2.5 text-left hover:bg-slate-50 ${n.is_read ? "" : "bg-brand-50/50"}`}>
                  <div className="text-[12px] font-medium text-slate-800">{n.title}</div><div className="text-[11px] text-slate-500">{n.body}</div><div className="text-[10px] text-slate-400">{n.created_at.slice(0, 16).replace("T", " ")}</div>
                </button>
              ))}
            </div>
          )}
        </div>
        <button onClick={() => nav(isAdmin ? "settings" : "profile")} className="flex items-center gap-2 rounded-full pr-1 hover:bg-slate-100">
          <Avatar name={first} id={user.employee_id ?? user.username} size={36} />
          <span className="hidden text-left leading-tight sm:block"><span className="block text-[11px] text-slate-400">Welcome back,</span><span className="block text-[13px] font-semibold text-slate-800">{first}</span></span>
        </button>
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-6 md:px-6">
        {needSummary && <div className="p-10 text-center text-sm text-slate-400">{loadErr ? `Cannot reach the API: ${loadErr}` : "Loading enterprise data…"}</div>}
        {!needSummary && (
          <>
            {isAdmin && view === "dashboard" && <AdminDashboard summary={summary!} projects={projects} reload={reload} onNav={nav} toast={notify} />}
            {isAdmin && view === "manager" && <ManagerView summary={summary!} reload={reload} toast={notify} />}
            {isAdmin && view === "workforce" && <WorkforceView summary={summary!} reload={reload} toast={notify} onNav={nav} />}
            {isAdmin && view === "audit" && <AuditView refreshKey={tick} toast={notify} />}
            {isAdmin && view === "settings" && <SettingsView summary={summary!} reload={reload} toast={notify} onReset={reset} />}
            {view === "projects" && <ProjectsView isAdmin={isAdmin} onNav={nav} toast={notify} refreshKey={tick} reload={reload} />}
            {view === "project" && viewId && <ProjectDetail key={viewId} id={viewId} isAdmin={isAdmin} onNav={nav} toast={notify} reload={reload} summary={summary} />}
            {view === "employee" && viewId && <EmployeeProfile key={viewId} employeeId={viewId} isAdmin={isAdmin} isSelf={user.employee_id === viewId} onNav={nav} toast={notify} reload={reload} />}
            {view === "profile" && user.employee_id && <EmployeeProfile employeeId={user.employee_id} isAdmin={isAdmin} isSelf onNav={nav} toast={notify} reload={reload} />}
            {view === "coordinator" && <CoordinatorView summary={summary ?? undefined} projects={projects} isAdmin={isAdmin} seed={chatSeed} onConsumedSeed={() => setChatSeed(null)} reload={reload} onNav={nav} />}
            {!isAdmin && view === "portal" && <StaffPortal toast={notify} projects={projects} reload={reload} onNav={nav} refreshKey={tick} />}
          </>
        )}
      </main>
      {toast && <Toast message={toast.m} kind={toast.k} onDone={() => setToastState(null)} />}
    </div>
  );
}
