"""Write the local report of a run: report.md, results.json, results.csv, metadata.json, logs/."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from benchy.reports.stats import paired, summarize_condition

RESULTS_SCHEMA_VERSION = 1
SMALL_SAMPLE = 30
CSV_FIELDS = [
    "task_id", "rep", "condition", "order", "status", "resolved", "regression",
    "hidden_passed", "hidden_total", "visible_passed", "visible_total", "seconds",
    "model_calls", "prompt_tokens_est", "completion_tokens_est", "tokens_est", "cost_usd_est",
    "qed_status", "qed_grade", "qed_applied", "qed_candidates", "eval_error",
]  # fmt: skip


def summarize(attempts: list[dict], conditions: list[str]) -> dict:
    per_condition = {
        c: summarize_condition([a for a in attempts if a["condition"] == c]) for c in conditions
    }
    per_task: dict[str, dict] = {}
    for a in attempts:
        empty = {c: {"resolved": 0, "attempts": 0} for c in conditions}
        row = per_task.setdefault(a["task_id"], empty)
        row[a["condition"]]["attempts"] += 1
        row[a["condition"]]["resolved"] += int(a["resolved"])
    qed = [a for a in attempts if a["condition"] == "qedcode"]
    grades: dict[str, dict] = {}
    for a in qed:
        g = grades.setdefault(a.get("qed_grade") or "none", {"attempts": 0, "resolved": 0})
        g["attempts"] += 1
        g["resolved"] += int(a["resolved"])
    return {
        "per_condition": per_condition,
        "paired": paired(attempts) if {"baseline", "qedcode"} <= set(conditions) else None,
        "per_task": per_task,
        "qedcode_grades": grades,
    }


def limitations(meta: dict, summary: dict) -> list[str]:
    notes = []
    if not meta["is_real_measurement"]:
        notes.append(
            "NOT A REAL MEASUREMENT: a scripted stand-in model was used to test the pipeline. "
            "These numbers say nothing about QEDCode or any model."
        )
    if not meta["complete"]:
        notes.append("The run was stopped early; only finished attempts are included.")
    pairs = (summary.get("paired") or {}).get("pairs", 0)
    if pairs and pairs < SMALL_SAMPLE:
        notes.append(
            f"Small sample ({pairs} paired attempts). Treat differences as indicative only; "
            "the confidence intervals and the McNemar p-value show how uncertain they are."
        )
    swe = meta.get("suite", {}).get("kind") == "swebench"
    notes.append(
        "Token counts are estimates (characters / 3.5), not counts from the model's tokenizer."
    )
    if swe:
        skipped = meta["suite"].get("skipped_not_valid_here") or []
        notes += [
            "SWE-bench tasks run in environments rebuilt without Docker; results are not "
            "comparable with the official SWE-bench leaderboard (a subset of repositories, a "
            "retrieval baseline instead of an agent).",
            "The baseline saw the issue plus retrieved files "
            f"({meta['controls'].get('baseline_context')}) and answered with one patch. Other "
            "harnesses would be different baselines.",
            "SWE-bench Verified is public, so recent models may have seen these issues and fixes "
            "in training.",
        ]
        if skipped:
            notes.append(
                f"{len(skipped)} task(s) were skipped for both conditions because they are not "
                "valid on this computer (see metadata.json)."
            )
    else:
        notes += [
            "Tasks are small single-file Python problems; results may not carry over to large "
            "real-world repositories.",
            "The baseline is the bare model with one plain prompt and one answer. Other agent "
            "harnesses (with their own retries or tools) would be different baselines.",
        ]
    notes.append(
        "Times include model latency on this machine and are only comparable within this run."
    )
    return notes


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:.1f}%"


def _num(x) -> str:
    return "–" if x is None else str(x)


def render_markdown(meta: dict, summary: dict, attempts: list[dict]) -> str:
    conds = meta["controls"]["conditions"]
    pc = summary["per_condition"]
    lines = [f"# Benchy report `{meta['run_id']}`", ""]
    if not meta["is_real_measurement"]:
        lines += ["> **⚠ SELF-TEST — NOT A REAL MEASUREMENT.** Scripted stand-in model.", ""]
    s = meta["suite"]
    lines += [
        f"- **Suite:** {s['name']} {s['version']} ({len(s['tasks'])} tasks, "
        f"fingerprint `{s['fingerprint_sha256'][:12]}`)",
        f"- **Model:** {meta['model']['name']} ({meta['model']['backend']})",
        f"- **Versions:** Benchy {meta['benchy_version']}, QEDCode {meta['qedcode_version']}",
        f"- **Repetitions:** {meta['controls']['repetitions']} · **time limit:** "
        f"{meta['controls']['time_limit_s_per_condition']:g}s per condition · "
        f"**QEDCode speed:** {meta['controls']['qedcode_speed']} · **order seed:** "
        f"{meta['controls']['order_seed']}",
        f"- **Evaluator:** {meta['evaluator']['name']} v{meta['evaluator']['version']} "
        "(hidden tests, never shown to either condition)",
        f"- **Started:** {meta['started_at']} · **finished:** {meta['finished_at']}"
        + ("" if meta["complete"] else " · **INCOMPLETE**"),
        "",
        "## Results",
        "",
        "| | " + " | ".join(conds) + " |",
        "|---|" + "---|" * len(conds),
    ]
    rows = [
        ("Attempts", lambda c: _num(pc[c]["attempts"])),
        ("Verified resolved", lambda c: f"{pc[c]['resolved']} ({_pct(pc[c]['resolution_rate'])})"),
        (
            "95% CI (Wilson)",
            lambda c: f"{_pct(pc[c]['resolution_ci95'][0])} – {_pct(pc[c]['resolution_ci95'][1])}",
        ),
        ("Regressions", lambda c: f"{pc[c]['regressions']} ({_pct(pc[c]['regression_rate'])})"),
        ("Timeouts / errors", lambda c: f"{pc[c]['timeouts']} / {pc[c]['errors']}"),
        ("No usable change", lambda c: _num(pc[c]["no_change"])),
        ("Median time (s)", lambda c: _num(pc[c]["median_seconds"])),
        ("Model calls", lambda c: _num(pc[c]["model_calls"])),
        ("Tokens (est., median / total)", lambda c: f"{_num(pc[c]['tokens_est_median'])} / "
         f"{pc[c]['tokens_est_total']}"),
        ("Est. cost (USD)", lambda c: _num(pc[c]["cost_usd_est"])),
    ]  # fmt: skip
    for label, fn in rows:
        lines.append(f"| {label} | " + " | ".join(fn(c) for c in conds) + " |")
    p = summary.get("paired")
    if p:
        lines += [
            "",
            "### Paired comparison (same task, same repetition)",
            "",
            f"- Pairs: {p['pairs']} · both resolved: {p['both_resolved']} · "
            f"neither: {p['neither']}",
            f"- Resolved only with QEDCode: **{p['only_qedcode']}** · only by the baseline: "
            f"**{p['only_baseline']}**",
            f"- Difference in resolution rate (QEDCode − baseline): **{_pct(p['difference'])}** "
            f"· exact McNemar p = {p['mcnemar_p']}",
        ]
    if summary["qedcode_grades"]:
        lines += ["", "### QEDCode's own grade vs. the independent evaluator", ""]
        lines += ["| QEDCode grade | attempts | verified resolved |", "|---|---|---|"]
        for g, v in sorted(summary["qedcode_grades"].items()):
            lines.append(f"| {g} | {v['attempts']} | {v['resolved']} |")
    lines += ["", "## Per task", "", "| task | " + " | ".join(conds) + " |"]
    lines.append("|---|" + "---|" * len(conds))
    for tid, row in summary["per_task"].items():
        cells = [f"{row[c]['resolved']}/{row[c]['attempts']}" for c in conds]
        lines.append(f"| {tid} | " + " | ".join(cells) + " |")
    lines += ["", "## Every attempt", ""]
    lines += [
        "| task | rep | condition | status | resolved | regression | hidden | seconds | grade |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for a in attempts:
        lines.append(
            f"| {a['task_id']} | {a['rep']} | {a['condition']} | {a['status']} | "
            f"{'yes' if a['resolved'] else 'no'} | {'YES' if a['regression'] else 'no'} | "
            f"{a['hidden_passed']}/{a['hidden_total']} | {a['seconds']} | "
            f"{a.get('qed_grade') or '–'} |"
        )
    lines += ["", "## Limitations", ""] + [f"- {n}" for n in meta["limitations"]]
    lines += [
        "",
        "## Method",
        "",
        "Both conditions use the same model client, the same fresh repository snapshot (checked "
        "by commit sha), the same time limit and the same evaluator. "
        + (
            "The evaluator applies only changes to non-test source files to the base commit, adds "
            "SWE-bench's test patch and runs the instance's tests. *Resolved* = every "
            "FAIL_TO_PASS test passes and no PASS_TO_PASS test that passed before now fails. "
            if meta.get("suite", {}).get("kind") == "swebench"
            else "The evaluator applies only changes to non-test source files to a pristine copy, "
            "then runs the original visible tests and the hidden tests. *Resolved* = all hidden "
            "tests pass and no previously passing visible test fails. "
        )
        + "Condition order is shuffled per task and repetition with the seed above. "
        "See docs/methodology.md.",
        "",
    ]
    return "\n".join(lines)


def write_report(run_dir: Path, meta: dict, attempts: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)
    summary = summarize(attempts, meta["controls"]["conditions"])
    meta = {**meta, "limitations": limitations(meta, summary)}
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    results = {
        "schema_version": RESULTS_SCHEMA_VERSION,
        "run_id": meta["run_id"],
        "metadata": meta,
        "summary": summary,
        "attempts": attempts,
    }
    (run_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for a in attempts:
            writer.writerow({k: a.get(k, "") for k in CSV_FIELDS})
    (run_dir / "report.md").write_text(render_markdown(meta, summary, attempts), encoding="utf-8")
