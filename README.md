https://teamcodesilk-vyuham-26-5p3x.vercel.app/


# Vyuham — AF-07 AI Team Coordination & Task Allocation Agent

**Team CodeSilk · Agent Forge '26 Hackathon (Theme: Agentic AI)**

Vyuham is an enterprise AI workforce intelligence and coordination platform. It decides **who should do each task**, **what they should do next**, **whether work is progressing**, **whether the workload is fair**, and **what should happen when something changes**. Every decision comes with an explanation, a human approval step where it matters, and a tamper-evident audit trail.

## Architecture

```
React 18 + TS + Tailwind + Recharts       Sidebar app: Dashboard + AI chat, Projects, Allocation, Workforce, Profiles, Audit, Settings
        │  REST (/api/v1, bearer token), polling every 10 to 15 seconds
FastAPI + Pydantic v2                     Role checks, project access checks, validation, rate limits
        │
assistant.py                              Claude tool loop or labelled offline router; every action passes one permission-checked registry
workflow.py / progress.py / workforce.py  Document analysis, specification, plans; verified progress; skill scores, resumes, links
agents.py / services.py                   7 logical agents; shared operations used by REST and chat
engine.py                                 Hard constraints, weighted scoring, DAG and critical path, Gini (no LLM involved)
        │
SQLite (backend/data/vyuham.db)           Versioned migrations; FTS5 document index; hash-chained audit ledger
```

**The product loop:** upload documents → extract and index → analyse → answer clarification questions → approve the specification → generate and edit a plan → approve (creates tasks once) → allocate → track verified progress → evaluate → adapt.

**Hybrid allocation:** the LLM never picks an assignee. The Python engine applies hard constraints (leave, capacity, the 95% ceiling, critical skills, dependency order) and ranks candidates with configurable weights:

`Suitability = 0.30·Skill + 0.20·Availability + 0.20·Balance + 0.15·Priority + 0.10·Performance + 0.05·Growth`

Critical tasks, and assignments that push someone above 85% load, wait for human approval.

**Progress calculation:** each task is weighted by `estimated hours × priority factor` (Critical 1.5, High 1.2, Medium 1.0, Low 0.8).
Verified % is the weight of tasks whose deliverable a manager accepted, divided by total weight. In-progress, blocked and pending are shown as separate bands. Employee and manager percentages are shown beside verified progress and never added to it.

**Skill scores (0 to 10):** separate from performance, availability and workload. Each lists its evidence, marked verified, employee-reported or inferred, with a confidence level and any missing evidence. A single unverified mention gets no number.

**Document retrieval:** SQLite FTS5 with BM25, restricted to one project. No embedding model is used: Claude's API does not provide embeddings, and keyword retrieval is sufficient at per-project scale. Document text is always treated as untrusted data, and suspected embedded instructions are flagged.

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

### Connecting Claude

Copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, and restart the backend. The default model is `claude-opus-5-5` (change it with `AF07_MODEL`). The key stays on the server.

Without a key, the app runs in **offline mode**: chat, analysis, plans and resume extraction use built-in rules on your real data, and every result is labelled `rule-based`.

### Data

Data is stored in `backend/data/` (not committed). The **Reset all demo data** button in Settings saves a backup to `backend/data/backups/`, then restores the seeded state. Pending migrations also take a backup first. Backups contain password hashes, so treat them as confidential.

Set `VYUHAM_ENV` to `development`, `staging` or `production` (default `development`). Outside development, demo data is never seeded, reset is refused, `AF07_SECRET_KEY` is required, and the API docs are off. Sample files to try are in `docs/samples/`.

## Companies, roles and data

- **Company registration:** choose *New company* on the sign-in page, then answer the onboarding conversation. Type `<start>` at the review step to reach the dashboard. Answers are saved, so signing out never restarts it.
- **Joining:** employees use an invitation code from *Team & Roles*. Codes work once, expire after 7 days, and can be tied to one email. Nobody joins by naming a company.
- **Roles:** Owner, Administrator, Manager, Employee, enforced by the API. Role changes need the current password again and are written to the audit ledger. A company always keeps at least one owner.
- **Isolation:** every request runs as the company in its signed token. On Supabase the app connects as `vyuham_app`, a restricted role, and row-level security limits it to that company's rows.
- **Core records:** employees, skills, projects, tasks, assignments, approvals, users and the audit ledger are real tables, written through from the server's memory. Run one backend worker only, because the process holds the working copy. An older `core_state` JSON row is imported on first use and left in place.
- **Files** stay on the backend's disk (`backend/data/uploads`), not in Supabase Storage. They are not scanned for malware.
- **Team rooms** refresh by polling every few seconds rather than Supabase Realtime.

### Budget-aware allocation

Money is stored as integer minor units. *Budget* on a project shows estimated, committed and actual costs separately. *Propose a team* runs `backend/app/optimizer.py`, an exact branch-and-bound search: required skills, suitability threshold and weekly capacity come first, then the budget, then cost plus configurable penalties. It changes nothing until each assignment is approved. Suitability is an explainable heuristic, not a probability. The default penalties are a starting policy, not a validated optimum.

### Supabase setup

```
SUPABASE_DB_URL=            restricted vyuham_app role, session pooler, port 5432
SUPABASE_MIGRATION_DB_URL=  owner login, used only for migrations
VYUHAM_ENV=development
VYUHAM_DEV_PROJECT_REF=     the only project where reset and demo seeding are allowed
```

Without `SUPABASE_DB_URL` the app uses local SQLite. `python -m scripts.load_sqlite_backup <file>` (from `backend/`, using the owner login) copies a SQLite backup into an empty Supabase schema. To run tests on Postgres, set `VYUHAM_TEST_DB_URL` and `VYUHAM_TEST_OWNER_URL`; they use a temporary schema that is dropped afterwards. The Free plan has no automatic backups, so schedule your own.

## Demo accounts (seeded in development only)

| Portal | Username | Password |
|---|---|---|
| Admin login (Enterprise Admin / PM) | `admin` | `Admin@2026` |
| Staff login | any employee's first name, e.g. `sneha`, `vikram`, `kabir` | `Staff@2026` |

## Demo script

1. **Admin → Projects → New project**, then upload the files from `docs/samples/` on the **Documents** tab.
2. On the dashboard chat, choose the project and ask *"Analyze the documents and prepare the execution plan"*. It reports the 8-week vs 12-week conflict and asks clarification questions.
3. Answer them, approve the specification, then ask *"Generate the project plan"*. Review or edit it on the **Plan** tab and approve it. Tasks are created once.
4. **Tasks → Run allocation**, then approve items under **Allocation & Approvals**.
5. **Staff login (sneha):** ask *"What should I prioritize today?"*, report progress, submit a task for review. Verified progress does not move yet.
6. **Admin → project → Tasks → Accept deliverable.** The donut's verified band moves. Enter a manager report of 70% and open **Evaluation** to see the gap flagged.
7. In chat, say *"Vikram is on sick leave for 3 days"* and approve the card. Reassignment proposals appear for approval.
8. **Audit Ledger:** every action is hash-chained, and *Re-verify chain* confirms nothing was altered.

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

The tests cover the reference allocation, hard constraints, approvals, RBAC, audit tamper detection, concurrency, document formats and validation, cross-project isolation, prompt-injection handling, the clarification-to-plan flow, verified progress, restart persistence, skill evidence, resume screening, integration status, employee management, and the assistant in offline mode and with a scripted Claude client.

## Known limitations

- Capacity is modelled per week, from the reference formulas. Long projects can show capacity gaps because all their work is compared with one week of free hours.
- Non-critical tasks can go to someone with a partial skill match, as the reference allocation requires. The gap is shown on the suggestion.
- Core entities are saved as a JSON snapshot in SQLite after each change; new features use normal tables. This suits one server, not several.
- Single organization. Calendar, Slack, Jira, LinkedIn, Instagram and X are not connected; only GitHub public data is read.
- Scanned PDFs need OCR before they can be indexed.

## Privacy and governance

- Evaluation uses verified outcomes only: accepted deliverables, rework, review quality and defect rate. **Never** commit counts, lines of code, online status, hours logged or social media.
- Staff can only see their own records. Disputes go to a manager and are audited.
- Every allocation, score-weight change, disruption, approval and evidence ingestion is written to an append-only SHA-256 hash chain.

UI style reference: [`docs/ui-reference.png`](docs/ui-reference.png).
