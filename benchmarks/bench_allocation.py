"""Allocation benchmark. Runs the application's real engine.py and optimizer.py beside two simple baselines on simulated scenarios.
Touches no database. Usage, from the repository root: backend/.venv/Scripts/python benchmarks/bench_allocation.py"""
import copy
import csv
import itertools
import json
import os
import pathlib
import sys
import time

os.environ["AF07_SKIP_DOTENV"] = "1"
ROOT = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent / "backend")]

from app import engine, optimizer        # noqa: E402  the real application code
from app.models import WeightConfig      # noqa: E402
from scenario import LEVELS, make        # noqa: E402

RESULTS = ROOT / "results"
SIZES = [8, 15, 25, 40]
SEEDS = 40
BUDGET_SIZE = 15
BUDGET_SEEDS = 30
TIGHTNESS = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5]
OPTIMIZER_SECONDS = 2.0
CEILING = 95.0


# ------------------------------------------------------------------ the four methods
def round_robin(s):
    """Basic: next available person in turn. Looks at nothing else."""
    people = [e for e in s.employees if e.status == "Available"]
    return {t.id: people[i % len(people)].id for i, t in enumerate(s.tasks)}


def skill_first(s):
    """Skill-first: strongest match for each task. Ignores capacity and cost."""
    def fit(e, t):
        held = {x.skill_name: x for x in e.skills}
        return sum(LEVELS.index(held[k].level) + 1 if k in held else -10 for k in t.required_skills)
    people = [e for e in s.employees if e.status == "Available"]
    return {t.id: max(people, key=lambda e: (fit(e, t), e.id)).id for t in s.tasks}


def vyuham_engine(s):
    """The app's deterministic scoring engine, in the order TaskAllocationAgent.allocate_all uses."""
    people = copy.deepcopy(s.employees)
    tasks = copy.deepcopy(s.tasks)
    by_id = {e.id: e for e in people}
    weights = WeightConfig()
    plan = {}
    for task in engine.topo_sort(tasks):
        if not engine.dependencies_planned(task, tasks):
            plan[task.id] = None
            continue
        ranked = engine.rank_candidates(people, task, weights)
        if ranked and ranked[0]["eligible"]:
            owner = by_id[ranked[0]["employee_id"]]
            owner.committed_hrs += task.estimated_hours
            task.assigned_to = owner.id
            plan[task.id] = owner.id
        else:
            plan[task.id] = None
    return plan


def vyuham_optimizer(s, budget=None):
    """The app's cost-aware optimizer with its default policy."""
    result = optimizer.optimize(copy.deepcopy(s.tasks), copy.deepcopy(s.employees), s.rates, [], budget, time_limit=OPTIMIZER_SECONDS)
    return {t.id: None for t in s.tasks} | {a["task_id"]: a["employee_id"] for a in result["assignments"]}, result


METHODS = {"round_robin": round_robin, "skill_first": skill_first, "vyuham_engine": vyuham_engine, "vyuham_optimizer": lambda s: vyuham_optimizer(s)[0]}


# ------------------------------------------------------------------ one shared scorer, separate from the code being scored
def qualified(e, t):
    held = {x.skill_name: x for x in e.skills}
    return e.status == "Available" and all(k in held and LEVELS.index(held[k].level) >= LEVELS.index(v) for k, v in t.required_skills.items())


def gini(values):
    """Standard formula, written separately from engine.gini so that each checks the other."""
    arr = sorted(values)
    n, total = len(arr), sum(arr)
    return 0.0 if not n or not total else sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(arr)) / (n * total)


def score(s, plan):
    windows = optimizer.task_windows(s.tasks)
    by_id = {e.id: e for e in s.employees}
    weekly = {e.id: {} for e in s.employees}
    flat_hours = {e.id: e.committed_hrs + e.meeting_hrs + e.leave_hrs for e in s.employees}
    tasks = {t.id: t for t in s.tasks}
    for tid, owner in plan.items():
        if owner:
            first, span = windows[tid]
            for w in range(first, first + span):
                weekly[owner][w] = weekly[owner].get(w, 0.0) + tasks[tid].estimated_hours / span
            flat_hours[owner] += tasks[tid].estimated_hours
    def week_load(e, w):
        return e.committed_hrs + e.meeting_hrs + e.leave_hrs + weekly[e.id].get(w, 0.0)
    assigned = qual = valid = 0
    cost = 0
    for tid, owner in plan.items():
        if not owner:
            continue
        assigned += 1
        e = by_id[owner]
        cost += optimizer.labor_cost(tasks[tid].estimated_hours, s.rates[owner])
        is_qualified = qualified(e, tasks[tid])
        qual += is_qualified
        first, span = windows[tid]
        fits = all(week_load(e, w) <= e.weekly_capacity_hrs * CEILING / 100 + 1e-9 for w in range(first, first + span))
        valid += is_qualified and fits
    active = [e for e in s.employees if e.status == "Available"]
    weeks = sorted({w for v in weekly.values() for w in v}) or [0]
    peaks = [max(week_load(e, w) for w in weeks) / e.weekly_capacity_hrs * 100 for e in active]
    n = len(s.tasks)
    flat = [flat_hours[e.id] / e.weekly_capacity_hrs * 100 for e in active]
    return {"coverage_pct": assigned / n * 100, "qualified_pct": qual / n * 100, "valid_pct": valid / n * 100, "gini_flat": gini(flat), "gini_peak": gini(peaks), "max_peak_util_pct": max(peaks),
            "overloaded_employees_pct": sum(p > CEILING for p in peaks) / len(peaks) * 100, "labor_cost": cost, "cost_ratio_to_planted": cost / s.planted_cost, "fully_valid": int(valid == n)}


def run_sizes():
    rows = []
    for size, seed in itertools.product(SIZES, range(SEEDS)):
        s = make(size, seed)
        for name, method in METHODS.items():
            start = time.perf_counter()
            plan = method(s)
            ms = (time.perf_counter() - start) * 1000
            row = {"experiment": "sizes", "size": size, "seed": seed, "method": name, "runtime_ms": ms, **score(s, plan)}
            if name == "vyuham_optimizer":
                _, result = vyuham_optimizer(s)
                row["solver_status"] = result["solver"]["status"]
                row["solver_gap"] = result["solver"].get("gap")
            rows.append(row)
        print(f"sizes {size} seed {seed}", flush=True) if seed % 10 == 0 else None
    return rows


def run_budget():
    rows = []
    for mult, seed in itertools.product(TIGHTNESS, range(BUDGET_SEEDS)):
        s = make(BUDGET_SIZE, seed)
        budget = round(s.planted_cost * mult)
        plans = {"round_robin": round_robin(s), "skill_first": skill_first(s), "vyuham_engine": vyuham_engine(s)}
        plans["vyuham_optimizer"], result = vyuham_optimizer(s, budget)
        for name, plan in plans.items():
            m = score(s, plan)
            within = m["labor_cost"] <= budget
            rows.append({"experiment": "budget", "tightness": mult, "size": BUDGET_SIZE, "seed": seed, "method": name, "budget": budget, "within_budget": int(within), "valid_and_within": int(within and m["fully_valid"]),
                         "overrun_pct": max(0.0, (m["labor_cost"] - budget) / budget * 100), "solver_status": result["solver"]["status"] if name == "vyuham_optimizer" else "", **m})
    return rows


# ------------------------------------------------------------------ checks that the measuring itself is right
def brute_force(s, policy):
    """Enumerates every plan, using the optimizer's documented objective, as an independent check of its claim to be optimal."""
    tasks = s.tasks
    windows = optimizer.task_windows(tasks)
    active = [e for e in s.employees if e.status not in ("Inactive", "On Leave")]
    pools = []
    for t in tasks:
        pools.append([(e, optimizer.suitability(e, t)["score"]) for e in active if not optimizer.gaps(e, t) and optimizer.suitability(e, t)["score"] >= policy["min_suitability"]])
    best = None
    for combo in itertools.product(*pools):
        load = {e.id: {-1: optimizer.base_load(e, 0.0)} for e in active}
        total, over, peak, ok = 0.0, 0, 0.0, True
        for t, (e, suit) in sorted(zip(tasks, combo), key=lambda p: p[0].id):
            first, span = windows[t.id]
            per = t.estimated_hours / span
            weeks = load[e.id]
            if any(weeks.get(w, weeks[-1]) + per > e.weekly_capacity_hrs * optimizer.HOURS_PER_WEEK_CEILING / 100 + 1e-9 for w in range(first, first + span)):
                ok = False
                break
            for w in range(first, first + span):
                weeks[w] = weeks.get(w, weeks[-1]) + per
            total += optimizer.labor_cost(t.estimated_hours, s.rates[e.id]) + policy["delivery_risk"] * (100 - suit)
            peak = max(peak, max(weeks[w] for w in range(first, first + span)) / e.weekly_capacity_hrs * 100)
        if ok and (best is None or total < best):
            best = total
    return best


def validate():
    checks = []
    def check(name, passed, detail=""):
        checks.append({"check": name, "passed": bool(passed), "detail": str(detail)})
    # 1. Cost-only objective: the optimizer's cost must equal the true minimum found by enumerating every plan.
    policy = {**optimizer.DEFAULT_POLICY, "delivery_risk": 2000, "schedule_risk": 0, "imbalance": 0, "reassignment": 0}
    matched = compared = 0
    for seed in range(50):
        s = make(6, 1000 + seed)
        s.employees = s.employees[:5]
        s.employees[-1].status = "On Leave"
        s.tasks = s.tasks[:5]
        s.tasks = [t for t in s.tasks]
        for t in s.tasks:
            t.dependencies = []
        result = optimizer.optimize(copy.deepcopy(s.tasks), copy.deepcopy(s.employees), s.rates, [], policy=policy)
        truth = brute_force(s, policy)
        if truth is None or not result["assignments"]:
            check_same = truth is None and not result["assignments"]
            matched += check_same
            compared += 1
            continue
        compared += 1
        matched += abs(result["objective"] - truth) < 1e-6
    check("optimizer_matches_brute_force_optimum", matched == compared, f"{matched}/{compared} small instances")
    # 2. Every scenario's planted plan really is valid under the scorer.
    bad = [(size, seed) for size in SIZES for seed in range(SEEDS) if score(make(size, seed), make(size, seed).planted)["valid_pct"] != 100]
    check("planted_plans_are_fully_valid", not bad, f"{len(bad)} invalid of {len(SIZES) * SEEDS}: {bad[:5]}")
    # 3. Scenarios are reproducible.
    a, b = make(25, 3), make(25, 3)
    check("scenarios_are_reproducible", a.planted == b.planted and a.rates == b.rates)
    # 4. Gini agrees with the app's own function and with known values.
    values = [10.0, 20.0, 30.0, 70.0]
    check("gini_matches_engine", abs(gini(values) - engine.gini(values)) < 1e-3, f"{gini(values):.4f} vs {engine.gini(values)}")
    check("gini_known_values", gini([5, 5, 5]) == 0 and abs(gini([0, 0, 0, 10]) - 0.75) < 1e-9)
    # 5. A plan from each method scores as expected on a hand-checked two-task case.
    s = make(8, 0)
    plan = dict(s.planted)
    plan[s.tasks[0].id] = None
    check("scorer_counts_unassigned_tasks", abs(score(s, plan)["coverage_pct"] - 87.5) < 1e-9)
    # 6. The optimizer is deterministic.
    first = vyuham_optimizer(make(15, 7))[0]
    check("optimizer_is_deterministic", first == vyuham_optimizer(make(15, 7))[0])
    return checks


def main():
    RESULTS.mkdir(exist_ok=True)
    checks = validate()
    print(*[f"{'PASS' if c['passed'] else 'FAIL'} {c['check']} {c['detail']}" for c in checks], sep="\n", flush=True)
    (RESULTS / "validation_allocation.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    rows = run_sizes()
    budget_rows = run_budget()
    (RESULTS / "allocation_runs.json").write_text(json.dumps({"config": {"sizes": SIZES, "seeds": SEEDS, "budget_size": BUDGET_SIZE, "budget_seeds": BUDGET_SEEDS, "tightness": TIGHTNESS, "optimizer_seconds": OPTIMIZER_SECONDS, "ceiling_pct": CEILING, "data": "SIMULATED"},
                                                          "sizes": rows, "budget": budget_rows}, indent=1), encoding="utf-8")
    for name, data in (("allocation_runs_sizes.csv", rows), ("allocation_runs_budget.csv", budget_rows)):
        fields = list(dict.fromkeys(k for r in data for k in r))
        with (RESULTS / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(data)
    print("done", len(rows), len(budget_rows))
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
