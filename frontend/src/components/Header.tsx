import { Bell, LayoutGrid, LogOut, RotateCcw, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { SessionUser } from "../types";
import { Avatar } from "./ui";

export interface NavItem {
  key: string;
  label: string;
}

export function Header({ user, nav, active, onNav, pending, onLogout, onReset, onSearch }: {
  user: SessionUser; nav: NavItem[]; active: string; onNav: (k: string) => void; pending: number;
  onLogout: () => void; onReset?: () => void; onSearch?: (q: string) => void;
}) {
  const [q, setQ] = useState("");
  const first = user.display_name.split(" (")[0];
  return (
    <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-4 px-4 py-3 md:px-6">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white"><ShieldCheck size={18} /></div>
          <div className="leading-tight">
            <div className="text-lg font-bold tracking-tight text-brand-600">Vyuham</div>
            <div className="-mt-0.5 text-[10px] font-medium uppercase tracking-widest text-slate-400">AF-07 Workforce AI</div>
          </div>
        </div>

        {onSearch && (
          <form className="order-3 w-full md:order-none md:ml-6 md:w-72" onSubmit={(e) => { e.preventDefault(); onSearch(q); }}>
            <label className="flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-500">
              <Search size={15} />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask the AI coordinator…" className="w-full bg-transparent text-[13px] outline-none placeholder:text-slate-400" />
            </label>
          </form>
        )}

        <div className="ml-auto flex items-center gap-3">
          {onReset && (
            <button onClick={onReset} title="Reset demo data" className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><RotateCcw size={17} /></button>
          )}
          <button title="Pending approvals" onClick={() => user.role === "ADMIN" && onNav("manager")} className="relative rounded-full p-2 text-slate-500 hover:bg-slate-100">
            <Bell size={17} />
            {pending > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">{pending}</span>}
          </button>
          <div className="flex items-center gap-2">
            <Avatar name={first} id={user.employee_id ?? user.username} size={36} />
            <div className="hidden leading-tight sm:block">
              <div className="text-[11px] text-slate-400">Welcome back,</div>
              <div className="text-[13px] font-semibold text-slate-800">{first}</div>
            </div>
          </div>
          <button onClick={onLogout} title="Sign out" className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><LogOut size={17} /></button>
          <LayoutGrid size={18} className="hidden text-slate-400 sm:block" />
        </div>
      </div>
      {nav.length > 1 && (
        <nav className="mx-auto flex max-w-[1400px] gap-1 overflow-x-auto px-4 pb-2 md:px-6">
          {nav.map((n) => (
            <button key={n.key} onClick={() => onNav(n.key)}
              className={`whitespace-nowrap rounded-full px-4 py-1.5 text-[13px] font-medium transition ${active === n.key ? "bg-brand-500 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
              {n.label}
            </button>
          ))}
        </nav>
      )}
    </header>
  );
}
