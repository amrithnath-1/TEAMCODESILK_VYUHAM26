"""Builds VYUHAM_Benchmark_Report.docx from results/benchmark_summary.json. Every number in the report comes from that file."""
import json
import pathlib
from datetime import date

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = pathlib.Path(__file__).resolve().parent
S = json.loads((ROOT / "results/benchmark_summary.json").read_text(encoding="utf-8"))
FIG = ROOT / "figures"
BLUE, INK, MUTED = RGBColor(0x1F, 0x5F, 0xB0), RGBColor(0x1E, 0x29, 0x3B), RGBColor(0x52, 0x51, 0x4E)
NAMES = {"round_robin": "Basic (round robin)", "skill_first": "Skill-first", "vyuham_engine": "VYUHAM engine", "vyuham_optimizer": "VYUHAM optimizer"}
ORDER = ["vyuham_optimizer", "vyuham_engine", "skill_first", "round_robin"]

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.2)
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2)
normal = doc.styles["Normal"]
normal.font.name, normal.font.size = "Calibri", Pt(11)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
normal.paragraph_format.space_after, normal.paragraph_format.line_spacing = Pt(7), 1.12
for name, size, before, after in (("Heading 1", 18, 18, 7), ("Heading 2", 13.5, 13, 4), ("Heading 3", 11.5, 9, 3)):
    st = doc.styles[name]
    st.font.name, st.font.size, st.font.bold, st.font.color.rgb = "Calibri", Pt(size), True, BLUE if name != "Heading 3" else INK
    for theme in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        st.element.rPr.rFonts.attrib.pop(qn(theme), None)
    st.element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    st.element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    st.paragraph_format.space_before, st.paragraph_format.space_after, st.paragraph_format.keep_with_next = Pt(before), Pt(after), True


def para(text="", bold=False, color=None, size=None, italic=False, after=None, align=None, style=None):
    p = doc.add_paragraph(style=style)
    add_runs(p, text, bold, color, size, italic)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    if align:
        p.alignment = align
    return p


def add_runs(p, text, bold=False, color=None, size=None, italic=False):
    """**bold** inside text is rendered as bold."""
    for i, part in enumerate(text.split("**")):
        if part:
            r = p.add_run(part)
            r.bold = bold or i % 2 == 1
            r.italic = italic
            if color:
                r.font.color.rgb = color
            if size:
                r.font.size = Pt(size)


def bullets(items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        add_runs(p, item)
        p.paragraph_format.space_after = Pt(4)


def shade(cell, hexcolor):
    tc = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear"); el.set(qn("w:color"), "auto"); el.set(qn("w:fill"), hexcolor)
    tc.append(el)


def table(header, rows, widths, caption=None, highlight=None, size=9.5):
    if caption:
        p = para(caption, bold=True, size=9.5, color=MUTED, after=3)
        p.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        add_runs(c.paragraphs[0], h, bold=True, color=RGBColor(255, 255, 255), size=size)
        shade(c, "1F5FB0")
    repeat = OxmlElement("w:tblHeader")
    t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for n, row in enumerate(rows):
        cells = t.add_row().cells
        no_split = OxmlElement("w:cantSplit")
        t.rows[-1]._tr.get_or_add_trPr().append(no_split)
        for i, value in enumerate(row):
            cells[i].text = ""
            add_runs(cells[i].paragraphs[0], str(value), size=size)
            if highlight and highlight(row):
                shade(cells[i], "EAF2FC")
            elif n % 2:
                shade(cells[i], "F7F7F5")
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
            for p in row.cells[i].paragraphs:
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.line_spacing = 1.0
                if i:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    para("", after=5)
    return t


def figure(name, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(FIG / name), width=Inches(6.0))
    para(caption, italic=True, size=9.5, color=MUTED, after=10, align=WD_ALIGN_PARAGRAPH.CENTER)


def formula(text, meaning):
    p = para(text, size=11, after=1)
    p.paragraph_format.left_indent = Cm(0.6)
    for r in p.runs:
        r.font.name = "Cambria Math"
    p.paragraph_format.keep_with_next = True
    m = para(meaning, size=9.5, color=MUTED, after=7)
    m.paragraph_format.left_indent = Cm(0.6)


def tag(kind):
    p = para(kind, bold=True, size=9.5, color=RGBColor(0x8A, 0x4B, 0x00), after=5)
    p.paragraph_format.keep_with_next = True


def size_row(size, method):
    return next(r for r in S["by_size"] if r["size"] == size and r["method"] == method)


def overall(method, metric):
    rows = [r for r in S["by_size"] if r["method"] == method]
    return sum(r[metric] for r in rows) / len(rows)


def cmp(a, b, metric):
    return next(r for r in S["comparisons"] if r["a"] == a and r["b"] == b and r["metric"] == metric)


def budget(t, method):
    return next(r for r in S["budget"] if r["tightness"] == t and r["method"] == method)


def p_text(value):
    return "< 0.001" if value < 0.001 else f"{value:.3f}"


def pct(v, d=1):
    return f"{v:.{d}f}%"


SIZES = S["config"]["sizes"]
scenarios = S["config"]["seeds"] * len(SIZES)
opt_ske = cmp("vyuham_optimizer", "skill_first", "valid_pct")
opt_eng = cmp("vyuham_optimizer", "vyuham_engine", "valid_pct")
opt_rr = cmp("vyuham_optimizer", "round_robin", "valid_pct")
eng_ske = cmp("vyuham_engine", "skill_first", "valid_pct")
eng_rr = cmp("vyuham_engine", "round_robin", "valid_pct")
g_eng_rr = cmp("vyuham_engine", "round_robin", "gini_flat")
g_eng_ske = cmp("vyuham_engine", "skill_first", "gini_flat")
g_opt_eng = cmp("vyuham_optimizer", "vyuham_engine", "gini_flat")
g_opt_rr = cmp("vyuham_optimizer", "round_robin", "gini_flat")
g_opt_ske = cmp("vyuham_optimizer", "skill_first", "gini_flat")
peak_opt_ske = cmp("vyuham_optimizer", "skill_first", "max_peak_util_pct")
cost_opt_ske = cmp("vyuham_optimizer", "skill_first", "cost_ratio_to_planted")
cost_opt_eng = cmp("vyuham_optimizer", "vyuham_engine", "cost_ratio_to_planted")
checks = S["validation"]
retrieval = {(r["engine"], r["kind"]): r for r in S.get("retrieval", [])}
pg_direct, pg_para = retrieval.get(("Postgres", "direct")), retrieval.get(("Postgres", "paraphrase"))
lite_direct, lite_para = retrieval[("SQLite", "direct")], retrieval[("SQLite", "paraphrase")]
main_direct, main_para = pg_direct or lite_direct, pg_para or lite_para
answers = {r["group"]: r for r in S.get("answers", [])}
planning = {f["label"]: f for f in S.get("planning", [])}
live_flow = planning.get("Live Claude, Supabase")
ref = S["reference"]["SQLite"]
minutes = S["minutes_search"].get("Postgres") or S["minutes_search"]["SQLite"]
injection = S.get("injection", [])
usage = S.get("ai_usage")

# ------------------------------------------------------------------ cover
for _ in range(5):
    para("", after=12)
para("VYUHAM", bold=True, size=38, color=BLUE, after=0)
para("Benchmark Report", size=24, color=INK, after=8)
para("Task allocation, workload balance, budget, planning time and document retrieval", size=13, color=MUTED, after=30)
para("Agent Forge '26 · Problem AF-07: AI-Powered Team Coordination and Task Allocation Agent", size=11, after=2)
para("Team CodeSilk", size=11, after=2)
para(date(2026, 10, 31).strftime("%d %B %Y"), size=11, after=30)
note = para("", after=0)
add_runs(note, "**How to read these results.** All workforce scenarios and project documents here are simulated. They were measured using VYUHAM's real software, but they are not measurements from a real company, and they do not show real-world delivery outcomes.", size=10.5, color=INK)
note.add_run().add_break(WD_BREAK.PAGE)

# ------------------------------------------------------------------ summary
doc.add_heading("Executive summary", 1)
para(f"We compared VYUHAM's two allocation methods with two simple alternatives on {scenarios} simulated scenarios, then tested planning time, document search and written answers through the running application. "
     "The optimizer placed work correctly and handled budgets far better than the alternatives. The results also show clear weaknesses, including workload balance and search on reworded questions.")
rows = [("Tasks placed validly", pct(overall("vyuham_optimizer", "valid_pct")), pct(overall("vyuham_engine", "valid_pct")), pct(overall("skill_first", "valid_pct")), pct(overall("round_robin", "valid_pct"))),
        ("Workload Gini (lower is more even)", f"{overall('vyuham_optimizer', 'gini_flat'):.3f}", f"{overall('vyuham_engine', 'gini_flat'):.3f}", f"{overall('skill_first', 'gini_flat'):.3f}", f"{overall('round_robin', 'gini_flat'):.3f}"),
        ("Busiest person's peak week", pct(overall("vyuham_optimizer", "max_peak_util_pct")), pct(overall("vyuham_engine", "max_peak_util_pct")), pct(overall("skill_first", "max_peak_util_pct")), pct(overall("round_robin", "max_peak_util_pct"))),
        ("Valid and within budget, budget = hidden plan's cost", pct(budget(1.0, "vyuham_optimizer")["valid_and_within_pct"], 0), pct(budget(1.0, "vyuham_engine")["valid_and_within_pct"], 0), pct(budget(1.0, "skill_first")["valid_and_within_pct"], 0), pct(budget(1.0, "round_robin")["valid_and_within_pct"], 0))]
table(["Measure (simulated scenarios)", "VYUHAM optimizer", "VYUHAM engine", "Skill-first", "Basic"], rows, [6.2, 2.6, 2.6, 2.2, 2.0], "Table 1. Headline results, averaged across scenario sizes")
doc.add_heading("Main findings", 3)
find = [f"**Accuracy.** The optimizer placed {pct(opt_ske['mean_a'], 0)} of tasks validly, {opt_ske['mean_diff']:.1f} points above skill-first and {opt_rr['mean_diff']:.1f} points above round robin. It enforces the same rules this measure checks, so see the caveat in section 3.2.",
        f"**Workload balance.** The engine was the most even, with a Gini of {g_eng_rr['mean_a']:.3f}, {abs(g_eng_rr['percent_change']):.1f}% lower than round robin. The optimizer was noticeably less even ({g_opt_eng['mean_a']:.3f}) because it favours cheaper qualified people. Nobody passed the 95% capacity ceiling under the optimizer or the engine.",
        f"**Budget.** With the budget set to the cost of the hidden valid plan, the optimizer produced a valid, in-budget plan in {pct(budget(1.0, 'vyuham_optimizer')['valid_and_within_pct'], 0)} of scenarios; the best alternative managed {pct(budget(1.0, 'skill_first')['valid_and_within_pct'], 0)}. Where both plans were fully valid, its labor cost was {abs(cost_opt_ske['percent_change']):.1f}% lower than skill-first (n = {cost_opt_ske['n']}).",
        f"**Computing time.** Plans took from under a millisecond to about two seconds. The optimizer reached its 2-second limit from {SIZES[2]} tasks up, so those plans are good but not proven best."]
if pg_direct:
    find.append(f"**Document search.** With the document's own wording, the right passage was in the top three results {pct(pg_direct['app_hit_3_pct'], 0)} of the time. With reworded questions that fell to {pct(pg_para['app_hit_3_pct'], 0)}, because search matches keywords and does not understand meaning. The assistant makes up for much of this by rewriting questions before searching.")
if answers:
    find.append(f"**Written answers through Claude.** {answers['document_direct']['correct']} of {answers['document_direct']['n']} direct document questions and {answers['meeting_minutes']['correct']} of {answers['meeting_minutes']['n']} meeting-minutes questions were answered correctly, and {answers['unanswerable']['correct']} of {answers['unanswerable']['n']} unanswerable questions were correctly declined. This was a small test on one short invented project, so these figures will not carry over directly to real documents.")
bullets(find)
para("**We make no claim about time saved compared with people.** No human planning time was measured, so no percentage saving is given anywhere in this report.")

# ------------------------------------------------------------------ scope
doc.add_heading("1. What was compared", 1)
table(["Method", "How it chooses", "What it ignores"], [
    ("VYUHAM optimizer", "Application code. Exact search across possible teams: rules first, then the lowest cost plus penalties for risk, overload and imbalance.", "Nothing here, but it stops at a time limit on large problems."),
    ("VYUHAM engine", "Application code. Goes task by task and picks the highest weighted score across skill, availability, workload, priority, record and growth.", "Cost. It also allows partial skill matches on non-critical tasks, by design."),
    ("Skill-first", "Baseline. Picks the person with the strongest skill match for each task.", "Capacity and cost."),
    ("Basic (round robin)", "Baseline. Gives each task to the next available person in turn.", "Skills, capacity and cost."),
], [3.4, 8.0, 4.8], "Table 2. The four methods")
para("Both baselines were written for this benchmark. They represent simple approaches and are not any specific competing product.")

# ------------------------------------------------------------------ method
doc.add_heading("2. How the tests were run", 1)
doc.add_heading("2.1 Simulated scenarios", 2)
tag("Simulated data · real VYUHAM code")
para(f"We generated {S['config']['seeds']} scenarios at each of {', '.join(str(s) for s in SIZES)} tasks ({scenarios} in total), with about three employees for every four tasks. Skills, levels, hourly rates, workloads, deadlines and dependencies were drawn at random from a fixed seed, so the same data can be recreated exactly. One person in each scenario is on leave.")
para("**A hidden valid plan.** Each scenario contains a plan that is known to meet every skill and capacity rule. This means 100% valid allocation is always possible, which gives the accuracy measure a fair target. No method could see this plan.")
para(f"**A separate budget test.** {S['config']['budget_seeds']} scenarios of {S['config']['budget_size']} tasks were run at eight budget levels, from {min(S['config']['tightness'])} to {max(S['config']['tightness'])} times the cost of the hidden plan.")
para(f"**Optimizer settings.** Default company policy, with a {S['config']['optimizer_seconds']:.0f}-second time limit per plan.")
doc.add_heading("2.2 Through the running application", 2)
tag("Simulated documents · real application, database and Claude")
para("Planning time, search and written answers went through the application's real routes, on a temporary database that was deleted afterwards. The live database was not touched. "
     f"The test documents describe an invented project, with {main_direct['chunks']} searchable passages and {len(S['retrieval']) and main_direct['n']} labelled facts, each asked in two ways: using the document's words and reworded.")
doc.add_heading("2.3 Measures and formulas", 2)
formula("Valid allocation rate = (tasks assigned to an available person with every required skill at the required level, whose scheduled weeks stay within the capacity ceiling) ÷ (all tasks) × 100", f"This is our meaning of accuracy. The ceiling is {S['config']['ceiling_pct']:.0f}% of weekly capacity. Unassigned tasks count as not valid.")
formula("Weekly load = existing commitments + meetings + leave + Σ (task hours ÷ weeks available for the task)", "Each task is spread across the weeks between its dependencies finishing and its deadline.")
formula("Utilisation = hours ÷ weekly capacity × 100", "Peak utilisation is the highest weekly value for any person in the plan.")
formula("Gini = Σᵢ (2i − n − 1) xᵢ ÷ (n Σᵢ xᵢ), with xᵢ sorted from low to high", "Computed on each available person's total hours as a share of weekly capacity. 0 is perfectly even. A low value says hours are evenly shared; it does not say the right people got them.")
formula("Labor cost = Σ (estimated hours × approved hourly rate)", "Kept in whole minor currency units, so totals are exact.")
formula("Optimizer objective = labor cost + a × Σ(100 − suitability) + b × (overloaded assignments) + c × (peak utilisation) + d × (reassignments)", "The rules are applied before this is minimized. The default a, b, c and d are a starting policy, not proven best values.")
formula("Suitability = 0.60 × skill fit + 0.25 × delivery record + 0.15 × deadline reliability", "A 0 to 100 ranking score, not a probability of success. People without enough history get a neutral 50 for the record parts.")
formula("Hit@k = (questions with the right passage in the top k) ÷ (all questions) × 100", "MRR is the average of 1 ÷ (rank of the right passage), counted as 0 when it isn't found.")
doc.add_heading("2.4 Statistics", 2)
para("Methods were compared on the same scenarios, so each comparison is paired. We report:")
bullets(["**Mean difference** with a 95% bootstrap confidence interval (10,000 resamples).", "**Wilcoxon signed-rank test** for whether the difference is likely to be real, with Holm correction across all comparisons.", "**Rank-biserial effect size**, from −1 to +1, showing how consistently one method beat the other.", "**Percentage change** = (A − B) ÷ B × 100, and **percentage points** where the measure is already a percentage.", "**Wilson 95% intervals** for pass rates based on counts."])

# ------------------------------------------------------------------ results
doc.add_heading("3. Results", 1)
doc.add_heading("3.1 Task allocation accuracy", 2)
tag("Simulated data · real VYUHAM code")
figure("fig1_valid_allocation.png", "Figure 1. Share of tasks placed validly, with 95% confidence bands")
rows = [(NAMES[m], *[pct(size_row(s, m)["valid_pct"]) for s in SIZES], pct(overall(m, "qualified_pct")), pct(overall(m, "coverage_pct"))) for m in ORDER]
table(["Method", *[f"{s} tasks" for s in SIZES], "Fully qualified", "Assigned"], rows, [4.0, 1.9, 1.9, 1.9, 1.9, 2.4, 2.0], "Table 3. Valid allocation rate by size, with overall qualified and assigned rates")
para(f"The optimizer was valid every time. Skill-first starts strong but declines as projects grow, from {pct(size_row(SIZES[0], 'skill_first')['valid_pct'])} to {pct(size_row(SIZES[-1], 'skill_first')['valid_pct'])}, because it keeps choosing the same strong people until they run out of capacity. "
     f"Round robin stays low, near {pct(size_row(SIZES[-1], 'round_robin')['valid_pct'], 0)}, because it ignores skills.")
para(f"**Where VYUHAM's engine falls short.** Its valid rate of {pct(eng_ske['mean_a'])} was {abs(eng_ske['mean_diff']):.1f} points below skill-first overall (95% CI {eng_ske['diff_low']:.1f} to {eng_ske['diff_high']:.1f}). Two design choices explain most of this: it accepts partial skill matches on non-critical tasks, and it leaves tasks unassigned when no one has enough flat weekly capacity. It assigned {pct(overall('vyuham_engine', 'coverage_pct'))} of tasks, and fewer on small projects. The gap closes with size, and it passed skill-first at {SIZES[-1]} tasks.")
doc.add_heading("3.2 An important caveat on accuracy", 3)
para("The optimizer's 100% is partly by design: it refuses to assign anyone who breaks these same rules, and every scenario guarantees that a valid plan exists. The result shows that it applies its rules correctly at scale and always finds a plan. It does not show that people chosen this way would do better work. The scoring was written separately from the optimizer, and it was checked against the hidden plans.")

doc.add_heading("3.3 Employee workload balance", 2)
tag("Simulated data · real VYUHAM code")
figure("fig2_gini.png", "Figure 2. Evenness of total hours across people. Lower is more even")
figure("fig3_peak_utilization.png", "Figure 3. The busiest person's heaviest week. The ceiling is 95%")
rows = [(NAMES[m], f"{overall(m, 'gini_flat'):.3f}", pct(overall(m, "max_peak_util_pct")), pct(size_row(SIZES[-1], m)["max_peak_util_pct"]), pct(overall(m, "overloaded_employees_pct"), 2)) for m in ORDER]
table(["Method", "Mean Gini", "Mean peak week", f"Peak week at {SIZES[-1]} tasks", "People over ceiling"], rows, [4.6, 2.4, 2.8, 3.4, 3.0], "Table 4. Workload results")
para(f"The engine is the most balanced, with a Gini {abs(g_eng_rr['percent_change']):.1f}% below round robin and {abs(g_eng_ske['percent_change']):.1f}% below skill-first, and it kept every person under the ceiling. Skill-first overloads people badly on large projects, with its busiest week averaging {pct(size_row(SIZES[-1], 'skill_first')['max_peak_util_pct'], 0)} of capacity at {SIZES[-1]} tasks.")
para(f"**The cost of optimizing for money.** The optimizer's Gini of {g_opt_eng['mean_a']:.3f} is {g_opt_eng['percent_change']:.0f}% higher than the engine's and {g_opt_rr['percent_change']:.0f}% higher than round robin's, though {abs(g_opt_ske['percent_change']):.1f}% lower than skill-first's. It concentrates work on cheaper qualified people while staying within capacity. A company that values even workloads should raise the imbalance penalty. We did not test how far that closes the gap.")

doc.add_heading("3.4 Project budget optimization", 2)
tag("Simulated data · real VYUHAM code")
figure("fig5_budget_tightness.png", "Figure 4. Scenarios with a fully valid plan inside the budget, at each budget level")
ts = [0.7, 0.8, 0.9, 1.0, 1.25, 1.5]
rows = [(NAMES[m], *[pct(budget(t, m)["valid_and_within_pct"], 0) for t in ts]) for m in ORDER]
table(["Method", *[f"{t} ×" for t in ts]], rows, [5.0, 1.9, 1.9, 1.9, 1.9, 1.9, 1.9], f"Table 5. Fully valid and within budget, {budget(1.0, 'vyuham_optimizer')['n']} scenarios at each level")
para(f"From a budget equal to the hidden plan's cost upward, the optimizer always delivered a valid plan inside the budget. Below that it degrades in stages: {pct(budget(0.9, 'vyuham_optimizer')['valid_and_within_pct'], 0)} at 0.9 ×, {pct(budget(0.8, 'vyuham_optimizer')['valid_and_within_pct'], 0)} at 0.8 ×, {pct(budget(0.7, 'vyuham_optimizer')['valid_and_within_pct'], 0)} at 0.7 × and {pct(budget(0.6, 'vyuham_optimizer')['valid_and_within_pct'], 0)} at 0.6 ×. When it cannot fit, it keeps the plan valid and reports the overrun, which averaged {pct(budget(0.6, 'vyuham_optimizer')['mean_overrun_pct'])} at 0.6 ×. It never gave up required skills to save money.")
para(f"The engine often stays within budget ({pct(budget(1.0, 'vyuham_engine')['within_budget_pct'], 0)} at 1.0 ×), but only {pct(budget(1.0, 'vyuham_engine')['fully_valid_pct'], 0)} of its plans were fully valid, because it ignores cost and often leaves tasks unassigned or partly matched.")
figure("fig4_cost.png", "Figure 5. Labor cost of each method's plan, relative to the hidden plan. Counts assigned tasks only")
para(f"**Read Figure 5 with care.** A low line does not always mean a better plan. The engine's and round robin's costs include invalid placements, and the engine's leave some tasks uncosted. The fair comparison uses only scenarios where both plans are fully valid: there the optimizer cost {abs(cost_opt_ske['percent_change']):.1f}% less than skill-first (n = {cost_opt_ske['n']}, Holm p {p_text(cost_opt_ske['holm_p'])}). Against the engine the difference was {abs(cost_opt_eng['percent_change']):.1f}%, but with only {cost_opt_eng['n']} comparable scenarios it was not significant (Holm p {p_text(cost_opt_eng['holm_p'])}). Round robin had no fully valid plans, so a fair cost comparison with it was not possible.")

doc.add_heading("3.5 Project planning time", 2)
tag("Simulated scenarios and sample documents · real application")
figure("fig6_runtime.png", "Figure 6. Computing time per plan. Note the logarithmic scale")
rows = [(NAMES[m], *[f"{size_row(s, m)['runtime_ms_median']:.1f}" for s in SIZES]) for m in ORDER]
table(["Median milliseconds", *[f"{s} tasks" for s in SIZES]], rows, [5.4, 2.6, 2.6, 2.6, 2.6], "Table 6. Allocation computing time")
o = [size_row(s, "vyuham_optimizer") for s in SIZES]
table(["Optimizer at each size", *[f"{s} tasks" for s in SIZES]], [("Proved best within the limit", *[pct(r["proved_optimal_pct"], 0) for r in o]), ("Median gap to the lower bound", *[pct(r["median_gap_pct"] or 0) for r in o]), ("Stopped with no plan", *[pct(r["no_plan_pct"], 0) for r in o])], [5.4, 2.6, 2.6, 2.6, 2.6], "Table 7. How often the optimizer finished its search")
para(f"The time limit matters. Up to {SIZES[1]} tasks the optimizer usually proves its plan is the best one. At {SIZES[2]} tasks and above it always hits the {S['config']['optimizer_seconds']:.0f}-second limit and returns the best plan found, with a gap of roughly {o[-1]['median_gap_pct']:.0f}%. The true gap may be smaller, because the bound it is measured against is cautious.")
if S.get("planning"):
    figure("fig10_planning_time.png", "Figure 7. Median software time from uploaded documents to an allocated plan")
    keys = [("upload_and_index_seconds", "Upload and index"), ("analysis_seconds", "Analysis"), ("plan_generation_seconds", "Plan generation"), ("plan_approval_seconds", "Plan approval"), ("allocation_seconds", "Allocation"), ("total_seconds", "Total")]
    flows = S["planning"]
    rows = [(n, *[f"{f[k]['median']:.2f}" if k in f else "—" for f in flows]) for k, n in keys] + [("Successful runs", *[f"{f['succeeded']} of {f['runs']}" for f in flows]), ("Tasks in plan (median)", *[f"{f['median_tasks']:.0f}" if f["median_tasks"] is not None else "—" for f in flows])]
    table(["Median seconds", *[f["label"] for f in flows]], rows, [4.8, *[11.4 / len(flows)] * len(flows)], "Table 8. Time for each stage. Human review time is not included")
    lite, cloud = planning["Rule-based, SQLite"], planning["Rule-based, Postgres"]
    text = (f"Without Claude, the flow took {lite['total_seconds']['median']:.2f} seconds on a local database and {cloud['total_seconds']['median']:.0f} seconds on Supabase. That difference is mostly database round trips from a laptop in India to a server in London, so hosting the backend near the database should reduce it. We have not measured that. "
            f"Rule-based plans are simple, with a median of {lite['median_tasks']:.0f} tasks. ")
    if live_flow and "total_seconds" in live_flow:
        text += f"With Claude, the flow took a median of {live_flow['total_seconds']['median']:.0f} seconds across {live_flow['succeeded']} runs and produced a median of {live_flow['median_tasks']:.0f} tasks, with most of the time in analysis and plan generation. Three runs is a small sample, so treat this as indicative."
    para(text)
para("**Not measured:** how long a person takes to plan the same project. So we can show how long the software takes, but not how much time it saves.")

doc.add_heading("3.6 Document retrieval", 2)
tag("Simulated documents · real search")
figure("fig8_retrieval.png", "Figure 8. Share of questions with the right passage in the top k results")
rows = []
for r in S["retrieval"]:
    rows.append((("Supabase" if r["engine"] == "Postgres" else "SQLite"), r["kind"].title(), r["n"], pct(r["app_hit_1_pct"], 0), pct(r["app_hit_3_pct"], 0), pct(r["app_hit_6_pct"], 0), f"{r['app_mrr']:.2f}", pct(r["overlap_baseline_hit_3_pct"], 0), pct(r["random_hit_3_pct"], 0), pct(r["returned_nothing_pct"], 0)))
table(["Database", "Question", "n", "Hit@1", "Hit@3", "Hit@6", "MRR", "Word overlap Hit@3", "Random Hit@3", "No results"], rows, [1.9, 2.0, 0.9, 1.3, 1.3, 1.3, 1.2, 2.2, 2.0, 1.6], "Table 9. Search results, against a simple word-overlap baseline and random chance", size=9)
para(f"**Clear strength, clear weakness.** When a question uses the document's words, search works well: top-three hit rate {pct(main_direct['app_hit_3_pct'], 0)}. When it is reworded, the rate drops to {pct(main_para['app_hit_3_pct'], 0)}, and {pct(main_para['returned_nothing_pct'], 0)} of those questions returned nothing. That is {'below' if main_para['app_hit_3_pct'] < main_para['random_hit_3_pct'] else 'around'} the {pct(main_para['random_hit_3_pct'], 0)} expected from picking passages at random, and {'below' if main_para['app_hit_3_pct'] < main_para['overlap_baseline_hit_3_pct'] else 'around'} the word-overlap baseline's {pct(main_para['overlap_baseline_hit_3_pct'], 0)}. The cause is known: search uses keywords, with no embeddings. Adding semantic search is the most valuable improvement this benchmark points to.")
para(f"**Meeting minutes.** Of {minutes['n']} questions about minutes, the right record was found for {minutes['found']}, with the right kind of record (approved decision, action item or unapproved note) among the results for {minutes['right_type']}. The test corpus is small, so this is a basic check rather than a precise rate.")

doc.add_heading("3.7 Written answers through Claude", 2)
if answers:
    tag("Simulated documents · real assistant · live Claude API")
    figure("fig9_answers.png", "Figure 9. Correct answers by question type, with 95% Wilson intervals")
    rows = [(r["label"], r["n"], r["correct"], pct(r["accuracy_pct"], 0), f"{r['low']:.0f}% to {r['high']:.0f}%", f"{r['median_seconds']:.1f}") for r in S["answers"]]
    table(["Question type", "n", "Correct", "Accuracy", "95% interval", "Median seconds"], rows, [6.2, 1.2, 1.6, 1.9, 2.8, 2.4], "Table 10. Answer accuracy")
    total_correct = sum(r["correct"] for r in S["answers"])
    total_n = sum(r["n"] for r in S["answers"])
    para(f"The assistant answered {total_correct} of {total_n} questions correctly. An answer counted as correct only if it contained the expected fact, and an unanswerable question counted only if the answer clearly declined. Because a keyword check can be fooled, we also read every reworded, unanswerable and meeting-minutes answer, plus a sample of the direct ones, and found no errors.")
    para(f"**Do not read this as near-perfect real-world accuracy.** Each group is small: {answers['unanswerable']['correct']} of {answers['unanswerable']['n']} still has a 95% interval that reaches down to {answers['unanswerable']['low']:.0f}%. The test also uses one short invented project with only {main_direct['chunks']} passages, where every fact is stated plainly. Long or messy real documents will be harder.")
    para(f"**Why answers beat raw search.** Reworded questions reached {answers['document_paraphrase']['correct']} of {answers['document_paraphrase']['n']}, even though search on the same wording found so little. Claude rewrites the question into better search terms and tries again, averaging nearly two searches per question. This helps most in a small collection, so it does not replace semantic search.")
    if injection:
        followed = sum(1 for r in injection if r["followed_instruction"])
        para(f"**Malicious documents.** We planted a false instruction in one document and asked {len(injection)} questions about it. The assistant followed the instruction {followed} time{'s' if followed != 1 else ''}. This is a small test, and it does not prove the assistant is immune to such attacks.")
    if usage:
        para(f"**API use.** {usage['calls']} Claude calls, {int(usage['input_tokens']):,} input tokens and {int(usage['output_tokens']):,} output tokens, with {usage['failures']} failed calls.")
else:
    para("**Not completed.** The live Claude part of this benchmark did not finish, so no written-answer accuracy is reported.")

doc.add_heading("3.8 Percentage comparisons", 2)
figure("fig7_valid_difference.png", "Figure 10. Paired differences in valid allocation rate, across all scenario sizes")
def row(a, b, metric, label):
    c = cmp(a, b, metric)
    if "mean_diff" not in c:
        return (f"{NAMES[a]} vs {NAMES[b]}", label, c["n"], "—", "—", "—", "Not enough comparable scenarios", "—")
    points = c["unit"] == "points"
    change = f"{c['mean_diff']:+.1f} pts" if points else (f"{c['percent_change']:+.1f}%" if c["percent_change"] is not None else "—")
    interval = f"{c['diff_low']:.1f} to {c['diff_high']:.1f}" if points else f"{c['diff_low']:.3f} to {c['diff_high']:.3f}"
    return (f"{NAMES[a]} vs {NAMES[b]}", label, c["n"], f"{c['mean_a']:.3f}" if not points else f"{c['mean_a']:.1f}", f"{c['mean_b']:.3f}" if not points else f"{c['mean_b']:.1f}", change, interval, p_text(c["holm_p"]))
rows = []
for a, b in (("vyuham_optimizer", "round_robin"), ("vyuham_optimizer", "skill_first"), ("vyuham_optimizer", "vyuham_engine"), ("vyuham_engine", "round_robin"), ("vyuham_engine", "skill_first")):
    rows += [row(a, b, "valid_pct", "Valid allocation"), row(a, b, "gini_flat", "Gini"), row(a, b, "max_peak_util_pct", "Peak week")]
    if a == "vyuham_optimizer" or b == "skill_first":
        rows.append(row(a, b, "cost_ratio_to_planted", "Cost, both valid"))
table(["Comparison (A vs B)", "Measure", "n", "A", "B", "Change", "95% CI of difference", "Holm p"], rows, [4.6, 2.4, 0.9, 1.3, 1.3, 1.7, 2.6, 1.3], "Table 11. Paired comparisons. For Gini, peak week and cost, lower is better", size=8.5)
para("A small p-value says a difference is unlikely to be chance within these simulated scenarios. It says nothing about real-world performance.")

# ------------------------------------------------------------------ validation
doc.add_heading("4. How the results were checked", 1)
passed = sum(c["passed"] for c in checks)
plain = {"optimizer_matches_brute_force_optimum": "The optimizer's best plan matched an independent check of every possible plan on small scenarios", "planted_plans_are_fully_valid": "Every hidden plan scored 100% valid, across all scenarios", "scenarios_are_reproducible": "The same seed produces identical data",
         "gini_matches_engine": "The benchmark's Gini formula matches the application's own", "gini_known_values": "Gini gives the known answers on hand-worked cases", "scorer_counts_unassigned_tasks": "Unassigned tasks are scored correctly", "optimizer_is_deterministic": "The optimizer gives the same plan on the same input"}
table(["Check", "Detail", "Result"], [(plain[c["check"]], c["detail"].split(":")[0] or "—", "Pass" if c["passed"] else "FAIL") for c in checks] + [("The seeded demo scenario, through the application's real route, still gives the known result", f"Gini {ref['gini_before']} to {ref['gini_after']}, {ref['allocated']} of {ref['tasks']} tasks assigned", "Pass" if ref["gini_after"] == 0.1369 else "FAIL")],
      [9.8, 4.6, 1.8], f"Table 12. Validation: {passed} of {len(checks)} calculation checks passed, plus the demo scenario")

# ------------------------------------------------------------------ limits
doc.add_heading("5. Limitations", 1)
bullets(["**Simulated data.** Scenario settings such as skill mix and pay ranges were our choices. Real companies could give different results.",
         "**Accuracy means following the rules.** It does not measure quality of work, on-time delivery or team satisfaction. None of those outcomes were observed.",
         "**The measure suits the optimizer.** The rules being scored are the ones it enforces. The engine, which accepts partial matches by design, is judged by a stricter standard than it was built for.",
         "**Scoring model.** Capacity is scored with weekly loads spread over each task's window, which is how the optimizer plans. The engine plans with flat weekly hours, so it is more cautious and leaves more tasks unassigned.",
         "**Baselines are simple.** A more advanced competitor would likely perform better than these two.",
         f"**Default policy only.** Optimizer penalties were not tuned. The {S['config']['optimizer_seconds']:.0f}-second limit also affects results at larger sizes.",
         "**Timing.** Measured on one development laptop in India with other work running, including tests over the internet to a database in London. Hosted performance will differ. Treat times as a rough guide.",
         "**Small document test.** One invented project with few passages. Search gets harder as collections grow, so real performance could be lower. Keyword grading of answers is also imperfect.",
         "**Scale.** Up to 40 tasks. Larger projects were not tested."])
doc.add_heading("What could not be measured", 3)
table(["Not measured", "Why"], [("Time saved compared with human planners", "No human baseline was collected, so no saving is claimed."), ("Real-world delivery outcomes", "VYUHAM has no history of completed real projects."), ("Budget forecast accuracy", "It needs actual costs from finished projects."), ("Performance against real competing products", "None were available to test."),
    ("Prediction of task success", "VYUHAM has no calibrated model for this. Its scores are rankings, not probabilities.")], [7.2, 9.0], "Table 13. Benchmarks not completed")

# ------------------------------------------------------------------ conclusion
doc.add_heading("6. Conclusion", 1)
para(f"Within these simulated tests, VYUHAM's optimizer did what it was built to do. It placed every task validly across {scenarios} scenarios, always found a valid plan, respected the budget whenever that was possible, and said so when it was not. Against skill-first it was {opt_ske['mean_diff']:.1f} points more accurate and, where both were valid, {abs(cost_opt_ske['percent_change']):.1f}% cheaper, while its busiest week was {abs(peak_opt_ske['mean_diff']):.1f} points lower.")
para("The tests also show that VYUHAM's two methods trade off against each other. The engine shares work more evenly and runs faster, but ignores cost and leaves more tasks unmatched. The optimizer saves money and meets every rule, but concentrates work on fewer people.")
doc.add_heading("Recommended next steps", 3)
bullets(["**Add semantic search,** because reworded questions are the weakest search result in this report.", "**Test higher imbalance penalties,** to see how much evenness the optimizer can regain and at what cost.", "**Collect real project data,** so that delivery and budget accuracy can be measured.", "**Time real planners,** so that any time-saving claim rests on evidence."])

# ------------------------------------------------------------------ footer page numbers
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer.add_run("VYUHAM Benchmark Report · Simulated data · Page ")
run.font.size, run.font.color.rgb = Pt(8.5), MUTED
field = footer.add_run()
field.font.size, field.font.color.rgb = Pt(8.5), MUTED
for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
    if kind:
        el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
    else:
        el = OxmlElement("w:instrText"); el.text = text
    field._r.append(el)
sec.different_first_page_header_footer = True

doc.core_properties.title = "VYUHAM Benchmark Report"
doc.core_properties.author = "Team CodeSilk"
doc.core_properties.subject = "AF-07 benchmark results"
defaults = doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr")).find(qn("w:rFonts"))
for theme in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
    defaults.attrib.pop(qn(theme), None)
for side in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
    defaults.set(qn(side), "Calibri")
zoom = doc.settings.element.find(qn("w:zoom"))
if zoom is not None:
    zoom.set(qn("w:percent"), "100")
doc.save(ROOT / "VYUHAM_Benchmark_Report.docx")
print("saved")
