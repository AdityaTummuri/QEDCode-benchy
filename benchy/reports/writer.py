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
    "agent_used_qedcode", "agent_receipts", "agent_claimed_fixed",
]  # fmt: skip
# (without QEDCode, with QEDCode) per mode
PAIRS = (("baseline", "qedcode"), ("agent", "agent+qedcode"))


def pair_of(conditions) -> tuple[str, str] | None:
    return next((p for p in PAIRS if set(p) <= set(conditions)), None)


def agent_stats(attempts: list[dict]) -> dict:
    """Agent mode: how often each side said it fixed the issue, and how often that was wrong."""
    claimed = [a for a in attempts if a.get("agent_claimed_fixed")]
    false = [a for a in claimed if not a["resolved"]]
    return {
        "attempts": len(attempts),
        "used_qedcode": sum(bool(a.get("agent_used_qedcode")) for a in attempts),
        "claimed_fixed": len(claimed),
        "false_claims": len(false),
        "false_claim_rate": round(len(false) / len(claimed), 4) if claimed else None,
    }


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
    pair = pair_of(conditions)
    qed = [a for a in attempts if pair and a["condition"] == pair[1]]
    grades: dict[str, dict] = {}
    for a in qed:
        g = grades.setdefault(a.get("qed_grade") or "none", {"attempts": 0, "resolved": 0})
        g["attempts"] += 1
        g["resolved"] += int(a["resolved"])
    return {
        "per_condition": per_condition,
        "paired": paired(attempts, *pair) if pair else None,
        "per_task": per_task,
        "qedcode_grades": grades,
        "agent": (
            {c: agent_stats([a for a in attempts if a["condition"] == c]) for c in conditions}
            if set(conditions) & set(PAIRS[1])
            else None
        ),
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
    if meta.get("stopped_reason") and not meta["complete"]:
        notes.append(f"Why it stopped: {meta['stopped_reason']}.")
    swe = meta.get("suite", {}).get("kind") == "swebench"
    agent_mode = meta.get("mode") == "agent"
    if agent_mode:
        notes += [
            "Agent mode: both conditions are the same agent CLI with the same model, prompt, "
            "snapshot, time limit and permissions; the QEDCode side also has the QEDCode skill "
            "and MCP server. The prompt does not name QEDCode, so the agent chose whether to use "
            "it (see 'used QEDCode').",
            "The agent's model calls run on the user's plan. Turns and tokens are the agent "
            "CLI's own counts; Benchy cannot set a temperature or seed, so repeated runs can "
            "differ.",
            "Neither side had internet access (web tools refused by a hook, URL reads and "
            "network commands denied), so fixes could not be looked up online.",
            "'Said it was fixed' is read from the agent's final message (it finished normally, "
            "changed source code and did not say it failed); it is a heuristic.",
        ]
    else:
        notes.append(
            "Token counts are estimates (characters / 3.5), not counts from the model's tokenizer."
        )
    if swe and agent_mode:
        notes += [
            "SWE-bench tasks run in environments rebuilt without Docker; results are not "
            "comparable with the official SWE-bench leaderboard (a subset of repositories).",
            "SWE-bench Verified is public, so recent models may have seen these issues and fixes "
            "in training.",
        ]
    elif swe:
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
    else:
        notes.append(
            "Tasks are small single-file Python problems; results may not carry over to large "
            "real-world repositories."
        )
        if not agent_mode:
            notes.append(
                "The baseline is the bare model with one plain prompt and one answer. Other agent "
                "harnesses (with their own retries or tools) would be different baselines."
            )
    skipped = meta["suite"].get("skipped_not_valid_here") or []
    if swe and skipped:
        notes.append(
            f"{len(skipped)} task(s) were skipped for both conditions because they are not "
            "valid on this computer (see metadata.json)."
        )
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
    agent_mode = meta.get("mode") == "agent"
    pair = pair_of(conds)
    lines = [f"# Benchy report `{meta['run_id']}`", ""]
    if not meta["is_real_measurement"]:
        lines += ["> **⚠ SELF-TEST — NOT A REAL MEASUREMENT.** Scripted stand-in model.", ""]
    s = meta["suite"]
    lines += [
        f"- **Suite:** {s['name']} {s['version']} ({len(s['tasks'])} tasks, "
        f"fingerprint `{s['fingerprint_sha256'][:12]}`)",
        f"- **Model:** {meta['model']['name']} ({meta['model']['backend']})"
        + (" · **mode:** agent (agent alone vs agent + QEDCode)" if agent_mode else ""),
        f"- **Versions:** Benchy {meta['benchy_version']}, QEDCode {meta['qedcode_version']}",
        f"- **Repetitions:** {meta['controls']['repetitions']} · **time limit:** "
        f"{meta['controls']['time_limit_s_per_condition']:g}s per condition · "
        + ("" if agent_mode else f"**QEDCode speed:** {meta['controls']['qedcode_speed']} · ")
        + f"**order seed:** {meta['controls']['order_seed']}",
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
    ag = summary.get("agent")
    if agent_mode:  # turns and tokens as the agent CLI reports them; no cost (a flat plan)
        rows = rows[:7] + [
            ("Agent turns", lambda c: _num(pc[c]["model_calls"])),
            (
                "Tokens (median / total)",
                lambda c: f"{_num(pc[c]['tokens_est_median'])} / {pc[c]['tokens_est_total']}",
            ),
        ]
    if ag:
        rows += [
            ("Used QEDCode", lambda c: f"{ag[c]['used_qedcode']} of {ag[c]['attempts']}"),
            ("Said it was fixed", lambda c: _num(ag[c]["claimed_fixed"])),
            (
                "…but the hidden tests fail",
                lambda c: f"{ag[c]['false_claims']} ({_pct(ag[c]['false_claim_rate'])})",
            ),
        ]
    for label, fn in rows:
        lines.append(f"| {label} | " + " | ".join(fn(c) for c in conds) + " |")
    p = summary.get("paired")
    if p and pair:
        a, b = pair
        lines += [
            "",
            "### Paired comparison (same task, same repetition)",
            "",
            f"- Pairs: {p['pairs']} · both resolved: {p['both_resolved']} · "
            f"neither: {p['neither']}",
            f"- Resolved only by {b}: **{p['only_' + b]}** · only by {a}: **{p['only_' + a]}**",
            f"- Difference in resolution rate ({b} − {a}): **{_pct(p['difference'])}** "
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
        (
            "Both conditions run the same agent CLI and model with the same prompt"
            if agent_mode
            else "Both conditions use the same model client"
        )
        + ", the same fresh repository snapshot (checked "
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
