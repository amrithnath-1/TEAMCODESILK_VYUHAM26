import { X } from "lucide-react";
import { ReactNode, useEffect } from "react";

export function Card({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-2xl bg-white p-5 shadow-card ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-[15px] font-semibold text-slate-800">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function PillButton({ children, onClick, variant = "ghost", disabled, type = "button", className = "" }: {
  children: ReactNode; onClick?: () => void; variant?: "ghost" | "primary" | "danger" | "success"; disabled?: boolean;
  type?: "button" | "submit"; className?: string;
}) {
  const styles = {
    ghost: "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
    primary: "bg-brand-500 text-white hover:bg-brand-600",
    danger: "bg-rose-500 text-white hover:bg-rose-600",
    success: "bg-emerald-500 text-white hover:bg-emerald-600",
  }[variant];
  return (
    <button type={type} disabled={disabled} onClick={onClick}
      className={`inline-flex items-center justify-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}>
      {children}
    </button>
  );
}

const STATUS_STYLES: Record<string, string> = {
  ASSIGNED: "bg-emerald-400/90 text-white",
  ACTIVE: "bg-emerald-400/90 text-white",
  APPROVED: "bg-emerald-400/90 text-white",
  COMPLETED_AND_AUDITED: "bg-emerald-500 text-white",
  Available: "bg-emerald-400/90 text-white",
  IN_PROGRESS: "bg-amber-400 text-white",
  DELIVERABLE_IN_REVIEW: "bg-sky-400 text-white",
  PENDING_HITL_APPROVAL: "bg-orange-400 text-white",
  PENDING: "bg-orange-400 text-white",
  REALLOCATION_PROPOSED: "bg-violet-400 text-white",
  AT_RISK_DISRUPTED: "bg-rose-400 text-white",
  REJECTED: "bg-rose-400 text-white",
  Overloaded: "bg-rose-400 text-white",
  "On Leave": "bg-slate-400 text-white",
  BLOCKED_BY_DEPENDENCY: "bg-slate-300 text-slate-700",
  READY_FOR_ALLOCATION: "bg-slate-100 text-slate-600",
  UNASSIGNED_INFEASIBLE: "bg-rose-100 text-rose-700",
};

export function StatusPill({ status }: { status: string }) {
  const label = status.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  return <span className={`inline-block whitespace-nowrap rounded-md px-2.5 py-1 text-[11px] font-medium ${STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600"}`}>{label}</span>;
}

const PRIORITY_STYLES: Record<string, string> = {
  Critical: "bg-rose-50 text-rose-600 ring-rose-200",
  High: "bg-amber-50 text-amber-700 ring-amber-200",
  Medium: "bg-sky-50 text-sky-700 ring-sky-200",
  Low: "bg-slate-50 text-slate-600 ring-slate-200",
};

export function PriorityBadge({ priority }: { priority: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.Low}`}>{priority}</span>;
}

const AVATAR_GRADIENTS = [
  "from-sky-400 to-blue-600", "from-amber-300 to-orange-500", "from-emerald-300 to-teal-600", "from-pink-300 to-rose-500",
  "from-violet-300 to-indigo-600", "from-lime-300 to-green-600", "from-cyan-300 to-sky-600", "from-fuchsia-300 to-purple-600",
];

export function avatarGradient(id: string) {
  const n = [...id].reduce((s, c) => s + c.charCodeAt(0), 0);
  return AVATAR_GRADIENTS[n % AVATAR_GRADIENTS.length];
}

export function initials(name: string) {
  return name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

export function Avatar({ name, id, size = 36, ring = false }: { name: string; id: string; size?: number; ring?: boolean }) {
  return (
    <div style={{ width: size, height: size, fontSize: size * 0.36 }}
      className={`grid shrink-0 place-items-center rounded-full bg-gradient-to-br font-semibold text-white ${avatarGradient(id)} ${ring ? "ring-4 ring-white" : ""}`}>
      {initials(name)}
    </div>
  );
}

export function Ring({ value, size = 56, stroke = 6, color = "#2f80ed", label }: { value: number; size?: number; stroke?: number; color?: string; label?: ReactNode }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#eef2f7" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c - (v / 100) * c} style={{ transition: "stroke-dashoffset .6s ease" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-[11px] font-semibold text-slate-700">{label ?? `${Math.round(v)}%`}</div>
    </div>
  );
}

export function Bar({ value, color = "bg-brand-500", max = 100 }: { value: number; color?: string; max?: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-slate-100">
      <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.max(0, Math.min(100, (value / max) * 100))}%` }} />
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide = false }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className={`max-h-[90vh] w-full overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl ${wide ? "max-w-4xl" : "max-w-xl"}`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
          <button onClick={onClose} className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" aria-label="Close"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Toast({ message, kind, onDone }: { message: string; kind: "ok" | "err"; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4200);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div className={`fixed bottom-5 right-5 z-[60] max-w-sm rounded-xl px-4 py-3 text-sm text-white shadow-xl ${kind === "ok" ? "bg-slate-800" : "bg-rose-600"}`}>
      {message}
    </div>
  );
}

export const FACTOR_LABELS: Record<string, string> = {
  skill_match: "Skill match",
  availability: "Availability",
  workload_balance: "Workload balance",
  priority_alignment: "Priority alignment",
  past_performance: "Past performance",
  growth_opportunity: "Growth opportunity",
  development_opportunity: "Development opportunity",
};

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">{children}</div>;
}
