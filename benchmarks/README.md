# VYUHAM benchmarks

The report is `VYUHAM_Benchmark_Report.docx`. Results are in `results/` (CSV and JSON) and graphs in `figures/`.

All scenarios and documents are simulated. Nothing here reads or changes the live database: the tests use a temporary local database or a temporary Supabase schema that is dropped afterwards.

To reproduce, from the repository root, in this order:

1. `backend/.venv/Scripts/python benchmarks/bench_allocation.py`
2. `backend/.venv/Scripts/python benchmarks/bench_app.py --engine sqlite`
3. `backend/.venv/Scripts/python benchmarks/bench_app.py --engine postgres --live --flow-runs 3` (uses Supabase and paid Claude API credit)
4. `python benchmarks/analyze.py`, in an environment with `benchmarks/requirements.txt`
5. `backend/.venv/Scripts/python benchmarks/build_report.py`

Allocation scenarios are fixed by seed. Timings and live Claude answers will vary between runs.
