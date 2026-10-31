import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bar } from "./ui";

export const AI_STEPS = {
  documents: ["Uploading your files...", "Reading project documents...", "Extracting text and indexing passages..."],
  analysis: ["Reading project documents...", "Understanding project requirements...", "Identifying required skills...", "Looking for gaps and conflicts...", "Preparing clarification questions..."],
  plan: ["Reading the approved specification...", "Breaking the work into tasks...", "Preparing project workflow...", "Evaluating available resources...", "Checking dependencies and deadlines..."],
  tasks: ["Creating tasks and workflows...", "Saving dependencies and milestones..."],
  skills: ["Reading employee evidence...", "Evaluating skills against the evidence...", "Updating skill scores..."],
  resume: ["Reading the resume...", "Extracting experience and skills...", "Evaluating skills against the evidence..."],
  evaluation: ["Reading project records...", "Comparing reported and verified progress...", "Checking tasks against the requirements...", "Generating the project evaluation..."],
  minutes: ["Reading the meeting minutes...", "Finding decisions and action items..."],
  importing: ["Reading the uploaded files...", "Extracting employee details...", "Checking for missing and duplicate records..."],
  saving: ["Validating the records...", "Saving approved employees..."],
};

/** Shows what the AI is working on. Messages describe the stages of the job, not a measured position: only a real upload gets a percentage. */
export function AIProgress({ steps, pct, compact = false }: { steps: string[]; pct?: number | null; compact?: boolean }) {
  const [index, setIndex] = useState(0);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - started) / 1000);
      setSeconds(elapsed);
      setIndex(Math.min(Math.floor(elapsed / 6), steps.length - 1));      // stops on the last message and does not loop
    }, 1000);
    return () => clearInterval(timer);
  }, [steps]);

  const uploading = pct !== null && pct !== undefined && pct < 100;
  return (
    <div role="status" aria-live="polite" className={`flex items-start gap-3 rounded-xl border border-brand-100 bg-brand-50/60 ${compact ? "p-2.5" : "p-4"}`}>
      <Loader2 size={compact ? 15 : 18} className="mt-0.5 shrink-0 animate-spin text-brand-500" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-slate-700">{uploading ? `Uploading ${pct}%` : steps[index]}</p>
        {uploading ? <div className="mt-1.5 max-w-xs"><Bar value={pct as number} /></div>
          : <p className="text-[11px] text-slate-500">{seconds < 3 ? "This can take a minute. You can stay on this page." : `${seconds} seconds so far. You can stay on this page.`}</p>}
      </div>
    </div>
  );
}

/** Runs one job at a time. A second click while it runs does nothing, even before the button has re-rendered as disabled. */
export function useSingleRun() {
  const running = useRef(false);
  const [busy, setBusy] = useState<string | null>(null);
  const run = useCallback(async <T,>(name: string, job: () => Promise<T>): Promise<T | undefined> => {
    if (running.current) return undefined;
    running.current = true;
    setBusy(name);
    try {
      return await job();
    } finally {
      running.current = false;
      setBusy(null);
    }
  }, []);
  return { busy, run };
}
