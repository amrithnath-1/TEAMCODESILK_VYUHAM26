"""Turns raw benchmark results into statistics, CSV/JSON summaries and graphs. Needs numpy, scipy, matplotlib (see requirements.txt)."""
import csv
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS, FIGURES = ROOT / "results", ROOT / "figures"
FIGURES.mkdir(exist_ok=True)
RNG = np.random.default_rng(20261031)
METHODS = ["round_robin", "skill_first", "vyuham_engine", "vyuham_optimizer"]
LABEL = {"round_robin": "Basic (round robin)", "skill_first": "Skill-first", "vyuham_engine": "VYUHAM engine", "vyuham_optimizer": "VYUHAM optimizer"}
COLOR = {"vyuham_optimizer": "#2a78d6", "vyuham_engine": "#eb6834", "skill_first": "#1baf7a", "round_robin": "#eda100"}    # fixed order, validated for colour-vision deficiency
MARK = {"vyuham_optimizer": "o", "vyuham_engine": "s", "skill_first": "^", "round_robin": "D"}
DASH = {"vyuham_optimizer": "-", "vyuham_engine": "-", "skill_first": "--", "round_robin": ":"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
plt.rcParams.update({"font.family": "Calibri", "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "figure.dpi": 200, "savefig.bbox": "tight", "legend.frameon": False})


def boot_ci(values, n=10000):
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (None, None)
    means = RNG.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return float((c - r) / d * 100), float((c + r) / d * 100)


def write_csv(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (RESULTS / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def by(rows, **match):
    return [r for r in rows if all(r[k] == v for k, v in match.items())]


def summarise_sizes(rows):
    out = []
    metrics = ["coverage_pct", "qualified_pct", "valid_pct", "fully_valid", "gini_flat", "gini_peak", "max_peak_util_pct", "overloaded_employees_pct", "cost_ratio_to_planted", "runtime_ms"]
    for size in sorted({r["size"] for r in rows}):
        for m in METHODS:
            sel = by(rows, size=size, method=m)
            row = {"size": size, "method": m, "n": len(sel)}
            for k in metrics:
                vals = [float(r[k]) for r in sel]
                low, high = boot_ci(vals)
                row.update({k: float(np.mean(vals)), f"{k}_low": low, f"{k}_high": high})
            row["runtime_ms_median"] = float(np.median([r["runtime_ms"] for r in sel]))
            statuses = [r.get("solver_status") for r in sel if r.get("solver_status")]
            if statuses:
                row["proved_optimal_pct"] = statuses.count("optimal") / len(statuses) * 100
                row["no_plan_pct"] = sum(s == "stopped_without_plan" for s in statuses) / len(statuses) * 100
                gaps = [r["solver_gap"] for r in sel if r.get("solver_gap") not in (None, "")]
                row["median_gap_pct"] = float(np.median(gaps)) * 100 if gaps else None
            out.append(row)
    return out


def compare(rows):
    """Paired by scenario: both methods saw exactly the same data."""
    pairs = [("vyuham_optimizer", "round_robin"), ("vyuham_optimizer", "skill_first"), ("vyuham_optimizer", "vyuham_engine"), ("vyuham_engine", "round_robin"), ("vyuham_engine", "skill_first")]
    metrics = [("valid_pct", "points"), ("qualified_pct", "points"), ("gini_flat", "percent"), ("max_peak_util_pct", "points"), ("overloaded_employees_pct", "points"), ("cost_ratio_to_planted", "percent"), ("runtime_ms", "percent")]
    out = []
    key = lambda r: (r["size"], r["seed"])
    index = {m: {key(r): r for r in by(rows, method=m)} for m in METHODS}
    for a, b in pairs:
        for metric, unit in metrics:
            ids = sorted(index[a])
            if metric == "cost_ratio_to_planted":   # cost means nothing unless both plans are actually valid
                ids = [i for i in ids if index[a][i]["fully_valid"] and index[b][i]["fully_valid"]]
            x = np.array([float(index[a][i][metric]) for i in ids])
            y = np.array([float(index[b][i][metric]) for i in ids])
            if len(ids) < 5:
                out.append({"a": a, "b": b, "metric": metric, "n": len(ids), "note": "too few comparable scenarios"})
                continue
            d = x - y
            low, high = boot_ci(d)
            nz = d[d != 0]
            p = float(stats.wilcoxon(nz).pvalue) if len(nz) else 1.0
            ranks = stats.rankdata(np.abs(nz))
            rb = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum()) if len(nz) else 0.0
            pct = float((x.mean() - y.mean()) / y.mean() * 100) if y.mean() else None
            out.append({"a": a, "b": b, "metric": metric, "unit": unit, "n": len(ids), "mean_a": float(x.mean()), "mean_b": float(y.mean()), "mean_diff": float(d.mean()), "diff_low": low, "diff_high": high, "percent_change": pct, "wilcoxon_p": p, "rank_biserial": rb})
    tested = sorted([r for r in out if "wilcoxon_p" in r], key=lambda r: r["wilcoxon_p"])     # Holm correction across everything tested
    worst = 0.0
    for i, r in enumerate(tested):
        worst = max(worst, min(1.0, r["wilcoxon_p"] * (len(tested) - i)))
        r["holm_p"] = worst
    return out


def summarise_budget(rows):
    out = []
    for t in sorted({r["tightness"] for r in rows}):
        for m in METHODS:
            sel = by(rows, tightness=t, method=m)
            n = len(sel)
            within = sum(int(r["within_budget"]) for r in sel)
            both = sum(int(r["valid_and_within"]) for r in sel)
            low, high = wilson(both, n)
            out.append({"tightness": t, "method": m, "n": n, "within_budget_pct": within / n * 100, "valid_and_within_pct": both / n * 100, "valid_and_within_low": low, "valid_and_within_high": high,
                        "mean_overrun_pct": float(np.mean([r["overrun_pct"] for r in sel])), "fully_valid_pct": float(np.mean([r["fully_valid"] for r in sel]) * 100)})
    return out


def retrieval_summary(app, label):
    runs = app["retrieval"]["runs"]
    n_chunks = app["retrieval"]["chunks"]
    out = []
    for kind in ("direct", "paraphrase"):
        sel = [r for r in runs if r["kind"] == kind]
        row = {"engine": label, "kind": kind, "n": len(sel), "chunks": n_chunks, "median_latency_ms": float(np.median([r["latency_ms"] for r in sel]))}
        for field, name in (("rank", "app"), ("baseline_rank", "overlap_baseline")):
            ranks = [r[field] for r in sel]
            for k in (1, 3, 6):
                hits = sum(1 for x in ranks if x and x <= k)
                row[f"{name}_hit_{k}_pct"] = hits / len(sel) * 100
            row[f"{name}_mrr"] = float(np.mean([1 / x if x else 0 for x in ranks]))
        low, high = wilson(sum(1 for r in sel if r["rank"] and r["rank"] <= 3), len(sel))
        row.update(app_hit_3_low=low, app_hit_3_high=high, returned_nothing_pct=sum(r["returned"] == 0 for r in sel) / len(sel) * 100)
        for k in (1, 3, 6):
            row[f"random_hit_{k}_pct"] = min(1.0, k / n_chunks) * 100
        out.append(row)
    return out


def flow_summary(rows, label):
    ok = [r for r in rows if "failed" not in r]
    stages = ["upload_and_index_seconds", "analysis_seconds", "plan_generation_seconds", "plan_approval_seconds", "allocation_seconds", "total_seconds"]
    out = {"label": label, "runs": len(rows), "succeeded": len(ok), "failed": len(rows) - len(ok), "sources": sorted({str(r.get("source")) for r in ok}), "median_tasks": float(np.median([r["tasks"] for r in ok])) if ok else None}
    for s in stages:
        vals = [r[s] for r in ok]
        if vals:
            out[s] = {"median": float(np.median(vals)), "min": float(min(vals)), "max": float(max(vals))}
    return out


# ------------------------------------------------------------------ graphs
def line_by_size(summary, metric, ylabel, title, name, log=False, ylim=None, band=True, value=lambda v: v):
    fig, ax = plt.subplots(figsize=(7.0, 3.9))
    sizes = sorted({r["size"] for r in summary})
    for m in METHODS:
        sel = [next(r for r in summary if r["size"] == s and r["method"] == m) for s in sizes]
        y = [value(r[metric]) for r in sel]
        if band and f"{metric}_low" in sel[0]:
            ax.fill_between(sizes, [value(r[f"{metric}_low"]) for r in sel], [value(r[f"{metric}_high"]) for r in sel], color=COLOR[m], alpha=0.14, linewidth=0)
        ax.plot(sizes, y, color=COLOR[m], linestyle=DASH[m], marker=MARK[m], markersize=6, linewidth=2, label=LABEL[m], markeredgecolor="white", markeredgewidth=1)
    ax.set_xlabel("Tasks in the scenario")
    ax.set_ylabel(ylabel)
    ax.set_xticks(sizes)
    if log:
        ax.set_yscale("log")
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_title(title, loc="left", fontsize=13, color=INK, fontweight="bold", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, fontsize=9.5, handlelength=2.4, columnspacing=1.2)
    fig.savefig(FIGURES / name)
    plt.close(fig)


def budget_figure(summary):
    fig, ax = plt.subplots(figsize=(7.0, 3.9))
    ts = sorted({r["tightness"] for r in summary})
    for m in METHODS:
        sel = [next(r for r in summary if r["tightness"] == t and r["method"] == m) for t in ts]
        ax.plot(ts, [r["valid_and_within_pct"] for r in sel], color=COLOR[m], linestyle=DASH[m], marker=MARK[m], markersize=6, linewidth=2, label=LABEL[m], markeredgecolor="white", markeredgewidth=1)
    ax.axvline(1.0, color=MUTED, linewidth=1, linestyle=(0, (2, 3)))
    ax.text(1.01, 58, "Budget = cost of the\nhidden valid plan", fontsize=9, color=MUTED)
    ax.set_xlabel("Budget as a multiple of the hidden valid plan's cost")
    ax.set_ylabel("Scenarios fully valid and within budget (%)")
    ax.set_ylim(-3, 103)
    ax.set_title("Valid plans inside the budget, as the budget tightens", loc="left", fontsize=13, color=INK, fontweight="bold", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, fontsize=9.5, handlelength=2.4, columnspacing=1.2)
    fig.savefig(FIGURES / "fig5_budget_tightness.png")
    plt.close(fig)


def percent_figure(comparisons):
    """Optimizer against each other method, in the same units on one axis: percentage points of valid allocation."""
    fig, ax = plt.subplots(figsize=(7.0, 3.1))
    sel = [r for r in comparisons if r["a"] == "vyuham_optimizer" and r["metric"] == "valid_pct"] + [r for r in comparisons if r["a"] == "vyuham_engine" and r["metric"] == "valid_pct"]
    labels = [f"{LABEL[r['a']]} vs {LABEL[r['b']]}" for r in sel]
    y = np.arange(len(sel))[::-1]
    values = [r["mean_diff"] for r in sel]
    ax.barh(y, values, height=0.56, color=[COLOR[r["a"]] for r in sel], xerr=[[v - r["diff_low"] for v, r in zip(values, sel)], [r["diff_high"] - v for v, r in zip(values, sel)]], error_kw={"ecolor": MUTED, "elinewidth": 1, "capsize": 3})
    for yi, v, r in zip(y, values, sel):
        ax.text(max(v, r["diff_high"]) + 1.2 if v >= 0 else 1.2, yi, f"{v:+.1f} pts", va="center", fontsize=10, color=INK)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Difference in valid-allocation rate (percentage points, 95% CI)")
    ax.grid(axis="y", visible=False)
    ax.set_title("How much more of the work is placed validly", loc="left", fontsize=13, color=INK, fontweight="bold")
    fig.savefig(FIGURES / "fig7_valid_difference.png")
    plt.close(fig)


def retrieval_figure(apps):
    fig, ax = plt.subplots(figsize=(7.0, 3.9))
    ks = [1, 2, 3, 4, 5, 6]
    styles = {("Postgres", "direct"): ("#2a78d6", "-", "o", "Direct wording (Supabase)"), ("Postgres", "paraphrase"): ("#eb6834", "-", "s", "Paraphrased (Supabase)"),
              ("SQLite", "direct"): ("#2a78d6", ":", "o", "Direct wording (SQLite)"), ("SQLite", "paraphrase"): ("#eb6834", ":", "s", "Paraphrased (SQLite)")}
    n_chunks = None
    for label, app in apps.items():
        n_chunks = app["retrieval"]["chunks"]
        for kind in ("direct", "paraphrase"):
            sel = [r for r in app["retrieval"]["runs"] if r["kind"] == kind]
            color, dash, marker, name = styles[(label, kind)]
            ax.plot(ks, [sum(1 for r in sel if r["rank"] and r["rank"] <= k) / len(sel) * 100 for k in ks], color=color, linestyle=dash, marker=marker, markersize=6, linewidth=2, label=name, markeredgecolor="white", markeredgewidth=1)
    ax.plot(ks, [min(1, k / n_chunks) * 100 for k in ks], color=MUTED, linestyle="--", linewidth=1.5, label="Random passage (expected)")
    ax.set_xlabel("Passages returned (k)")
    ax.set_ylabel("Questions with the right passage in the top k (%)")
    ax.set_ylim(-3, 103)
    ax.set_xticks(ks)
    ax.set_title("Document retrieval: wording matters", loc="left", fontsize=13, color=INK, fontweight="bold", pad=44)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=9.5, handlelength=2.4, columnspacing=1.2)
    fig.savefig(FIGURES / "fig8_retrieval.png")
    plt.close(fig)


def answers_figure(rows):
    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    y = np.arange(len(rows))[::-1]
    v = [r["accuracy_pct"] for r in rows]
    ax.barh(y, v, height=0.56, color="#2a78d6", xerr=[[max(0, a - r["low"]) for a, r in zip(v, rows)], [max(0, r["high"] - a) for a, r in zip(v, rows)]], error_kw={"ecolor": MUTED, "elinewidth": 1, "capsize": 3})
    for yi, r in zip(y, rows):
        ax.text(min(r["high"] + 1.5, 103), yi, f"{r['correct']}/{r['n']}", va="center", fontsize=10, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=10)
    ax.set_xlim(0, 115)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Correct answers (%, with 95% Wilson interval)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Assistant answers through live Claude", loc="left", fontsize=13, color=INK, fontweight="bold")
    fig.savefig(FIGURES / "fig9_answers.png")
    plt.close(fig)


def planning_figure(flows):
    stages = [("upload_and_index_seconds", "Upload and index"), ("analysis_seconds", "Analysis"), ("plan_generation_seconds", "Plan generation"), ("plan_approval_seconds", "Plan approval"), ("allocation_seconds", "Allocation")]
    fig, ax = plt.subplots(figsize=(7.0, 3.3))
    x = np.arange(len(flows))
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    left = np.zeros(len(flows))
    for (key, name), color in zip(stages, colors):
        v = np.array([f[key]["median"] if key in f else 0 for f in flows])
        ax.barh(x, v, left=left, height=0.5, color=color, label=name, edgecolor="white", linewidth=1)
        left += v
    for xi, total in zip(x, left):
        ax.text(total * 1.01 + 0.2, xi, f"{total:.1f} s", va="center", fontsize=10, color=INK)
    ax.set_yticks(x)
    ax.set_yticklabels([f["label"] for f in flows], fontsize=10)
    ax.set_xlabel("Median seconds per project (software time only, no human review)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, left.max() * 1.15)
    ax.set_title("Time from documents to an allocated plan", loc="left", fontsize=13, color=INK, fontweight="bold", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=5, fontsize=9, handlelength=1.2, columnspacing=1)
    fig.savefig(FIGURES / "fig10_planning_time.png")
    plt.close(fig)


def main():
    raw = json.loads((RESULTS / "allocation_runs.json").read_text(encoding="utf-8"))
    sizes = summarise_sizes(raw["sizes"])
    comparisons = compare(raw["sizes"])
    budget = summarise_budget(raw["budget"])
    write_csv("summary_by_size.csv", sizes)
    write_csv("comparisons.csv", comparisons)
    write_csv("summary_budget.csv", budget)
    line_by_size(sizes, "valid_pct", "Tasks placed validly (%)", "Task allocation accuracy (valid placements)", "fig1_valid_allocation.png", ylim=(0, 104))
    line_by_size(sizes, "gini_flat", "Gini coefficient (lower is more even)", "Workload balance: Gini of total hours per person", "fig2_gini.png", ylim=(0, None))
    line_by_size(sizes, "max_peak_util_pct", "Busiest person's peak week (% of capacity)", "Workload peak: the most overloaded week", "fig3_peak_utilization.png")
    line_by_size(sizes, "cost_ratio_to_planted", "Labor cost vs the hidden valid plan (= 1.0)", "Labor cost of each method's plan", "fig4_cost.png")
    line_by_size(sizes, "runtime_ms", "Mean milliseconds per scenario (log scale)", "Allocation computing time", "fig6_runtime.png", log=True, band=False)
    budget_figure(budget)
    percent_figure(comparisons)
    summary = {"data": "SIMULATED scenarios and documents, measured with the application's real code", "config": raw["config"], "by_size": sizes, "comparisons": comparisons, "budget": budget,
               "validation": json.loads((RESULTS / "validation_allocation.json").read_text(encoding="utf-8"))}
    apps = {}
    for label, name in (("SQLite", "app_sqlite.json"), ("Postgres", "app_postgres_live.json")):
        path = RESULTS / name
        if path.exists():
            apps[label] = json.loads(path.read_text(encoding="utf-8"))
    if apps:
        summary["retrieval"] = [row for label, app in apps.items() for row in retrieval_summary(app, label)]
        write_csv("summary_retrieval.csv", summary["retrieval"])
        retrieval_figure(apps)
        summary["reference"] = {label: {k: v for k, v in app["reference"].items()} for label, app in apps.items()}
        summary["minutes_search"] = {label: {"n": len(app["minutes_search"]), "found": sum(r["found"] for r in app["minutes_search"]), "right_type": sum(r["right_source_type"] for r in app["minutes_search"]), "rows": app["minutes_search"]} for label, app in apps.items()}
        flows = [flow_summary(app["planning_rule_based"], f"Rule-based, {label}") for label, app in apps.items()]
        live = apps.get("Postgres", {})
        if live.get("planning_claude"):
            flows.append(flow_summary(live["planning_claude"], "Live Claude, Supabase"))
        summary["planning"] = flows
        write_csv("summary_planning.csv", [{"label": f["label"], "runs": f["runs"], "succeeded": f["succeeded"], "median_tasks": f["median_tasks"], **{f"{k}_median": v["median"] for k, v in f.items() if isinstance(v, dict)}} for f in flows])
        planning_figure(flows)
        if live.get("answers"):
            names = {"document_direct": "Documents, direct wording", "document_paraphrase": "Documents, paraphrased", "meeting_minutes": "Meeting minutes", "unanswerable": "Unanswerable (must decline)"}
            rows = []
            for group, name in names.items():
                sel = [r for r in live["answers"] if r["group"] == group]
                k = sum(r["correct"] for r in sel)
                low, high = wilson(k, len(sel))
                rows.append({"group": group, "label": name, "n": len(sel), "correct": k, "accuracy_pct": k / len(sel) * 100, "low": low, "high": high, "median_seconds": float(np.median([r["seconds"] for r in sel]))})
            summary["answers"] = rows
            write_csv("summary_answers.csv", rows)
            answers_figure(rows)
            summary["injection"] = live.get("injection", [])
            summary["ai_usage"] = live.get("ai_usage")
            summary["answer_misses"] = [{"group": r["group"], "question": r["question"], "answer": r["answer"][:300]} for r in live["answers"] if not r["correct"]]
    (RESULTS / "benchmark_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print("analysis written;", len(comparisons), "comparisons")


if __name__ == "__main__":
    main()
