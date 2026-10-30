# Vyuham — AF-07 AI Team Coordination & Task Allocation Agent

**Team CodeSilk · Agent Forge '26 Hackathon (Theme: Agentic AI)**

Vyuham is an enterprise AI workforce intelligence and coordination platform. It decides **who should do each task**, **what they should do next**, **whether work is progressing**, **whether the workload is fair**, and **what should happen when something changes**. Every decision comes with an explanation, a human approval step where it matters, and a tamper-evident audit trail.

## Architecture

```
React 18 + TS + Tailwind + Recharts      Admin · Project Manager · Employee Portal · AI Coordinator
        │  REST (/api/v1, bearer token)
FastAPI + Pydantic v2                     RBAC (ADMIN / STAFF), validation, idempotency
        │
7 logical agents (backend/app/agents.py)  1 Project Analysis · 2 Workforce Intelligence · 3 Task Allocation
                                          4 Progress Monitoring · 5 Performance Evaluation · 6 Risk Prediction
                                          7 Coordination Supervisor (router + HITL gatekeeper)
        │
Deterministic engine (engine.py)          hard-constraint filter → weighted scorer → DAG topo sort /
                                          critical path → Gini fairness
        │
In-memory store + SHA-256 hash-chained audit ledger (state.py, audit.py)
```

**Hybrid allocation:** the LLM never picks an assignee. The Python engine filters hard constraints (leave, capacity, the 95% ceiling, critical skills, DAG order) and ranks candidates with configurable weights:

`Suitability = 0.30·Skill + 0.20·Availability + 0.20·Balance + 0.15·Priority + 0.10·Performance + 0.05·Growth`

Critical tasks, and assignments that push someone above 85% load, go to a **PENDING HITL approval** first.

**Six separate scores** for each employee: skill, performance, availability, workload, collaboration, and task suitability (per task). New hires are shown as *Insufficient Evidence (New Hire Onboarding)* instead of getting a low score.

## Run locally

Requires Python 3.10+ and Node 18+.

```bash
./start.sh            # macOS / Linux / Git Bash
```
```powershell
./start.ps1           # Windows PowerShell
```

- Frontend: http://localhost:5173
- API docs: http://127.0.0.1:8000/docs

To run each part manually:

```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # (.venv/bin/python on macOS/Linux)
.venv/Scripts/python -m uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```

Optional: copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Agent 1 then uses Claude to break project briefs into tasks, and validates the result before using it. Without a key, a deterministic skill catalog is used, so the demo works offline.

## Demo accounts (seeded, demo only)

| Portal | Username | Password |
|---|---|---|
| Admin login (Enterprise Admin / PM) | `admin` | `Admin@2026` |
| Staff login | any employee's first name, e.g. `sneha`, `vikram`, `kabir` | `Staff@2026` |

## Demo script (≈3 minutes)

1. **Admin → Project Manager → Run AI allocation.** All 8 CRM tasks are assigned and the workload Gini goes from **0.1584 to 0.1369**. Meera (97.5% load) is blocked by the capacity guardrail, and Kabir is protected as a new hire.
2. Click any DAG card to see every candidate's six-factor breakdown and the reasons others were disqualified.
3. **Approve** the Critical tasks in the HITL queue.
4. **One-click disruption:** mark Vikram *On Leave*. Agent 6 classifies the risk and Agent 7 proposes a cascade reassignment. Approve it, and the action is executed and verified.
5. **AI Coordinator:** try *"Who should do TSK-104?"*, *"What if Priya takes TSK-104?"* or *"Is the workload fair?"*.
6. **Staff login (sneha):** shows assigned tasks with a *"Why me?"* explanation, the six separate scores, verified evidence, progress updates and an evidence dispute.
7. **Audit Ledger:** every action is hash-chained, and *Re-verify chain* proves nothing was altered.

### Reference allocation (verified by `backend/tests`)

| Task | Assignee | Suitability | Post-load |
|---|---|---|---|
| TSK-101 CRM Requirements | Sneha Patel | 82.58 | 70.0% |
| TSK-102 PostgreSQL Schema (Critical) | Vikram Rao | 78.97 | 85.0% |
| TSK-103 Design System | Karthik Iyer | 79.45 | 85.0% |
| TSK-104 API Gateway (Critical) | Ananya Sharma | 78.54 | 90.0% |
| TSK-105 AI Lead Scoring | Rohan Verma | 63.10 | 67.5% |
| TSK-106 Frontend Kanban | Arjun Mehta | 78.24 | 82.5% |
| TSK-107 E2E & OWASP (Critical) | Nikhil Joshi | 81.32 | 80.0% |
| TSK-108 K8s & CI/CD | Siddharth Rao | 79.93 | 90.0% |

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

The tests cover the reference allocation, the capacity guardrail and new-hire protection, HITL gating, disruption and approval execution, double-approval rejection, duplicate disruptions and integration events, RBAC (staff vs admin), weight validation, audit tamper detection, concurrent allocation, brief-to-DAG decomposition, and chat routing.

## Privacy and governance

- Evaluation uses verified outcomes only: accepted deliverables, rework, review quality and defect rate. **Never** commit counts, lines of code, online status, hours logged or social media.
- Staff can only see their own records. Disputes go to a manager and are audited.
- Every allocation, score-weight change, disruption, approval and evidence ingestion is written to an append-only SHA-256 hash chain.

UI style reference: [`docs/ui-reference.png`](docs/ui-reference.png).
