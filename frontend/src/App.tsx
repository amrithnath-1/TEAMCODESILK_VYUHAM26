import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import { Header, NavItem } from "./components/Header";
import { Toast } from "./components/ui";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AuditView } from "./pages/AuditView";
import { CoordinatorView } from "./pages/CoordinatorView";
import { Login } from "./pages/Login";
import { ManagerView } from "./pages/ManagerView";
import { StaffPortal } from "./pages/StaffPortal";
import { WorkforceView } from "./pages/WorkforceView";
import type { SessionUser, Summary } from "./types";

const ADMIN_NAV: NavItem[] = [
  { key: "dashboard", label: "Enterprise Admin" },
  { key: "manager", label: "Project Manager" },
  { key: "coordinator", label: "AI Coordinator" },
  { key: "workforce", label: "Workforce & Integrations" },
  { key: "audit", label: "Audit Ledger" },
];
const STAFF_NAV: NavItem[] = [
  { key: "portal", label: "My Portal" },
  { key: "coordinator", label: "AI Assistant" },
];
const TILE_ROUTES: Record<string, string> = { risks: "dashboard", integrations: "workforce" };

export default function App() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [booting, setBooting] = useState(true);
  const [view, setView] = useState("dashboard");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [toast, setToastState] = useState<{ m: string; k: "ok" | "err" } | null>(null);
  const [chatSeed, setChatSeed] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setSummary(null);
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
    if (user?.role !== "ADMIN") return;
    api<Summary>("/dashboard/summary").then((s) => { setSummary(s); setLoadErr(null); }).catch((e) => setLoadErr(e.message));
  }, [user]);
  useEffect(() => { reload(); }, [reload]);

  const notify = useCallback((m: string, k: "ok" | "err" = "ok") => setToastState({ m, k }), []);
  const noopPending = useCallback(() => {}, []);

  if (booting) return <div className="grid min-h-screen place-items-center text-sm text-slate-400">Loading…</div>;
  if (!user) return <Login onLogin={(u) => { setUser(u); setView(u.role === "ADMIN" ? "dashboard" : "portal"); }} />;

  const isAdmin = user.role === "ADMIN";
  const nav = (k: string) => setView(TILE_ROUTES[k] ?? k);
  const reset = async () => {
    if (!confirm("Reset all demo data to the seeded state?")) return;
    try {
      await api("/reset", { body: {} });
      notify("Demo data reset to the seeded state.");
      reload();
    } catch (e: any) {
      notify(e.message, "err");
    }
  };

  return (
    <div className="min-h-screen bg-[#f4f6fa]">
      <Header user={user} nav={isAdmin ? ADMIN_NAV : STAFF_NAV} active={view} onNav={nav} pending={summary?.pending_approvals.length ?? 0}
        onLogout={logout} onReset={isAdmin ? reset : undefined} onSearch={(q) => { if (q.trim()) { setChatSeed(q); setView("coordinator"); } }} />
      <main className="mx-auto max-w-[1400px] px-4 py-6 md:px-6">
        {isAdmin && !summary && <div className="p-10 text-center text-sm text-slate-400">{loadErr ? `Cannot reach the API: ${loadErr}` : "Loading enterprise data…"}</div>}
        {isAdmin && summary && view === "dashboard" && <AdminDashboard summary={summary} reload={reload} onNav={nav} toast={notify} />}
        {isAdmin && summary && view === "manager" && <ManagerView summary={summary} reload={reload} toast={notify} />}
        {isAdmin && summary && view === "workforce" && <WorkforceView summary={summary} reload={reload} toast={notify} />}
        {isAdmin && summary && view === "audit" && <AuditView refreshKey={summary} />}
        {view === "coordinator" && (isAdmin ? summary : true) && (
          <CoordinatorView summary={summary ?? undefined} isAdmin={isAdmin} seed={chatSeed} onConsumedSeed={() => setChatSeed(null)} reload={reload} />
        )}
        {!isAdmin && view === "portal" && <StaffPortal toast={notify} onPending={noopPending} />}
      </main>
      {toast && <Toast message={toast.m} kind={toast.k} onDone={() => setToastState(null)} />}
    </div>
  );
}
