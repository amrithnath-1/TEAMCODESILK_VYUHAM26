"""Synthetic workforce scenarios for the allocation benchmark. SIMULATED DATA: no real employee or project records are used.

Every scenario contains a hidden "planted" plan that is known to satisfy all skill and capacity rules, so a 100% valid
allocation is always possible. That gives accuracy a defensible meaning: the share of tasks placed without breaking a rule.
Rates, skills and workloads are random draws, not measurements of any real company.
"""
import random
from dataclasses import dataclass
from typing import Dict, List

from app.models import AvailabilitySchedule, Employee, EmployeeSkill, Task
from app.optimizer import labor_cost, task_windows

SKILLS = ["Python", "React", "PostgreSQL", "FastAPI", "Docker", "Kubernetes", "TypeScript", "QA Automation", "Figma", "Security", "Data Engineering", "DevOps"]
LEVELS = ["Beginner", "Intermediate", "Advanced", "Expert"]
RATE_BY_LEVEL = {0: 800, 1: 1400, 2: 2200, 3: 3200}     # minor currency units per hour, invented for the simulation
HEADROOM = 0.70     # the planted plan stays this far under capacity, so that it is clearly achievable


@dataclass
class Scenario:
    seed: int
    size: int
    tasks: List[Task]
    employees: List[Employee]
    rates: Dict[str, int]
    planted: Dict[str, str]
    planted_cost: int


def _employee(i: int, rng: random.Random) -> Employee:
    seniority = rng.choices(range(4), weights=[3, 4, 3, 1])[0]
    held = rng.sample(SKILLS, rng.randint(2, 5))
    reliable = rng.uniform(55, 98)
    return Employee(id=f"E{i:03d}", name=f"Employee {i}", email=f"e{i}@sim.test", department="Simulated", designation=LEVELS[seniority], manager="", team_role_id="", years_exp=seniority * 3 + rng.uniform(0, 3),
                    skills=[EmployeeSkill(skill_name=s, level=LEVELS[min(3, max(0, seniority + rng.choice([-1, 0, 0, 1])))], is_verified=rng.random() < 0.75, evidence_source="simulated") for s in held],
                    weekly_capacity_hrs=40.0, committed_hrs=float(rng.randint(0, 8)), meeting_hrs=float(rng.randint(2, 6)), delivery_completion_rate=reliable, work_quality_acceptance_rate=rng.uniform(55, 98),
                    deadline_reliability_rate=rng.uniform(55, 98), collaboration_review_score=rng.uniform(50, 95), learning_improvement_score=rng.uniform(50, 95), preferred_tasks=[], learning_goals=rng.sample(SKILLS, 1),
                    sufficient_evidence=rng.random() < 0.85, availability=AvailabilitySchedule(meeting_hrs_week=3))


def make(size: int, seed: int) -> Scenario:
    rng = random.Random(f"{size}-{seed}")
    employees = [_employee(i, rng) for i in range(max(4, round(size * 0.75)))]
    tasks: List[Task] = []
    for i in range(size):
        deps = rng.sample([t.id for t in tasks], min(len(tasks), rng.choice([0, 0, 1, 2]))) if tasks else []
        floor = max([t.deadline_days for t in tasks if t.id in deps], default=0)
        tasks.append(Task(id=f"T{i:03d}", project_id="SIM", title=f"Task {i}", description="Simulated", required_skills={s: rng.choice(LEVELS[:3]) for s in rng.sample(SKILLS, rng.randint(1, 2))},
                          estimated_hours=float(rng.randint(6, 24)), priority=rng.choices(["Low", "Medium", "High", "Critical"], weights=[2, 5, 3, 1])[0], deadline_days=floor + rng.choice([7, 14, 21, 28]), dependencies=deps, deliverable_criteria="Simulated"))
    # Plant a valid plan: give each task to someone with room, and make sure they hold its skills. One other person goes on leave.
    windows = task_windows(tasks)
    weekly = {e.id: {} for e in employees}
    by_id = {e.id: e for e in employees}
    planted: Dict[str, str] = {}
    on_leave = employees[-1]
    for t in tasks:
        floor = max((x.deadline_days for x in tasks if x.id in t.dependencies), default=0)
        if t.deadline_days <= floor:     # a dependency's deadline was widened below
            t.deadline_days = floor + 7
        windows = task_windows(tasks)
        first, span = windows[t.id]
        per_week = t.estimated_hours / span
        pool = [e for e in employees if e is not on_leave]
        rng.shuffle(pool)
        owner = None
        for e in pool:
            base = e.committed_hrs + e.meeting_hrs
            if all(base + weekly[e.id].get(w, 0.0) + per_week <= e.weekly_capacity_hrs * HEADROOM for w in range(first, first + span)):
                owner = e
                break
        if owner is None:       # widen the deadline until the planted plan fits, so the guarantee always holds
            owner = pool[0]
            t.deadline_days += 56
            windows = task_windows(tasks)
            first, span = windows[t.id]
            per_week = t.estimated_hours / span
        for w in range(first, first + span):
            weekly[owner.id][w] = weekly[owner.id].get(w, 0.0) + per_week
        planted[t.id] = owner.id
        held = {s.skill_name: s for s in owner.skills}
        for skill, level in t.required_skills.items():
            if skill not in held or LEVELS.index(held[skill].level) < LEVELS.index(level):
                owner.skills = [s for s in owner.skills if s.skill_name != skill]
                held[skill] = EmployeeSkill(skill_name=skill, level=level, is_verified=True, evidence_source="simulated")
                owner.skills.append(held[skill])
    on_leave.status = "On Leave"
    rates = {e.id: round(RATE_BY_LEVEL[LEVELS.index(e.designation)] * rng.uniform(0.85, 1.15)) for e in employees}
    cost = sum(labor_cost(t.estimated_hours, rates[planted[t.id]]) for t in tasks)
    return Scenario(seed, size, tasks, employees, rates, planted, cost)
