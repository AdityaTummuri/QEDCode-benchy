"""Benchy's command line. Nothing here runs unless you type it: no background work, no uploads.

benchy run [--model qedcode] [--suite benchy-core] [--reps 3] [--tasks b01,b02]
benchy report [RUN_ID]          show a report (the latest when no id is given)
benchy report --list            list local runs
benchy suites                   list built-in suites
benchy suites check [SUITE]     prove every task in a suite is valid
benchy suites fetch [SUITE]     download what a SWE-bench suite needs (asks first)
benchy selftest                 check the pipeline end to end with scripted models
benchy status                   versions, model setup, where reports go
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from benchy import __version__


def reports_root(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    home = os.environ.get("QEDCODE_HOME") or str(Path.home() / ".qedcode")
    return Path(home) / "benchy" / "reports"


def _say(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _run_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    runs = [p for p in root.iterdir() if (p / "results.json").exists()]
    return sorted(runs, key=lambda p: p.name)


# --------------------------------------------------------------------------- commands


def cmd_run(args: argparse.Namespace) -> int:
    from benchy.runner.clients import make_model
    from benchy.runner.experiment import ExperimentConfig, run_experiment
    from benchy.suite import SuiteError, load_suite

    try:
        suite = load_suite(args.suite)
        tasks = suite.select([t for t in args.tasks.split(",") if t.strip()] if args.tasks else [])
    except SuiteError as exc:
        _say(f"Error: {exc}")
        return 2
    agent_mode = args.model.partition(":")[0] == "agy"
    allowed = ("agent", "agent+qedcode") if agent_mode else ("baseline", "qedcode")
    raw = args.conditions or ",".join(allowed)
    conditions = tuple(c.strip() for c in raw.split(",") if c.strip())
    if not conditions or any(c not in allowed for c in conditions):
        _say(f"Error: --conditions takes {allowed[0]}, {allowed[1]} or both (comma-separated).")
        return 2
    skipped: list[str] = []
    if suite.kind == "swebench":
        from benchy.swebench.validity import load_validity

        try:
            for task in tasks:
                task.python()
        except SuiteError as exc:
            _say(f"Error: {exc}")
            return 2
        validity = load_validity(suite)
        if validity is None:
            _say(
                "Note: `benchy suites check` has not been run for this suite on this computer, so "
                "tasks whose environment differs here are not skipped. Run it once first."
            )
        else:
            skipped = [t.id for t in tasks if validity.get(t.id) is False]
            tasks = [t for t in tasks if validity.get(t.id) is not False]
            unchecked = [t.id for t in tasks if t.id not in validity]
            if skipped:
                _say(f"Skipping {len(skipped)} task(s) that are not valid on this computer.")
            if unchecked:
                _say(
                    f"Note: {len(unchecked)} task(s) have not been checked on this computer yet "
                    "(`benchy suites check --tasks ...`); they run anyway."
                )
            if not tasks:
                _say("Error: no valid tasks left to run.")
                return 2
    time_limit = args.time_limit
    if time_limit is None:
        time_limit = suite.time_limit_s or 600.0
    try:
        client, spec = make_model(args.model)
    except Exception as exc:
        _say(f"Error: could not set up the model: {exc}")
        return 2
    if spec.agent:
        if not client.health():
            _say(f"Error: `{client.cli}` was not found. Install it and sign in, then try again.")
            return 2
        if "agent+qedcode" in conditions and (client.skill_dir is None or not client.qed_command):
            _say(
                "Error: agent+qedcode needs the QEDCode agent skill (set BENCHY_QEDCODE_SKILL to "
                "its skills/qedcode folder) and the `qed` command. Nothing was run."
            )
            return 2
    elif not spec.scripted and not client.health():
        _say(
            f"Error: the model '{spec.model}' ({spec.backend}) is not answering. Start its "
            "server (or run `qed doctor`), then try again. Nothing was run."
        )
        return 2
    cfg = ExperimentConfig(
        suite=suite,
        tasks=tasks,
        model=spec,
        reps=args.reps,
        conditions=conditions,
        speed=args.speed,
        time_limit_s=time_limit,
        seed=args.seed,
        qed_apply=args.qed_apply,
        price_in_per_mtok=args.price_in,
        price_out_per_mtok=args.price_out,
        baseline_context=args.baseline_context,
        skipped_here=skipped,
    )
    total = len(tasks) * args.reps * len(conditions)
    _say(
        f"Benchy {__version__}: {len(tasks)} task(s) × {args.reps} repetition(s) × "
        f"{len(conditions)} condition(s) = {total} attempts with {spec.model}."
    )
    if spec.scripted:
        _say("Scripted stand-in model: this is a pipeline self-test, NOT a real measurement.")
    try:
        state, run_dir = run_experiment(cfg, client, reports_root(args.out), progress=_say)
    finally:
        try:
            client.unload()
        except Exception:
            pass
    print((run_dir / "report.md").read_text(encoding="utf-8"))
    _say(f"Report saved in {run_dir}")
    if state.complete:
        return 0
    return 3 if state.stopped_reason.startswith("agent quota") else 130


def cmd_report(args: argparse.Namespace) -> int:
    root = reports_root(args.out)
    runs = _run_dirs(root)
    if args.list:
        if not runs:
            _say(f"No reports yet in {root}. Run `benchy run` first.")
            return 0
        for run in runs:
            meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
            tag = "" if meta.get("is_real_measurement") else "  [self-test]"
            print(f"{run.name}  {meta['suite']['name']}  {meta['model']['name']}{tag}")
        return 0
    chosen = [r for r in runs if r.name == args.run_id] if args.run_id else runs[-1:]
    if not chosen:
        what = f"a run called {args.run_id}" if args.run_id else "any runs"
        _say(f"There is not {what} in {root}. `benchy report --list` shows what exists.")
        return 1
    run = chosen[0]
    if args.json:
        print((run / "results.json").read_text(encoding="utf-8"))
    else:
        print((run / "report.md").read_text(encoding="utf-8"))
    return 0


def _pick_run(root: Path, run_id: str | None) -> Path | None:
    runs = _run_dirs(root)
    chosen = [r for r in runs if r.name == run_id] if run_id else runs[-1:]
    return chosen[0] if chosen else None


def cmd_share(args: argparse.Namespace) -> int:
    """Preview (default) or export the sanitized record of one run. Never uploads anything."""
    from benchy.submission import SubmissionError
    from benchy.submission.sanitize import (
        FIELD_NOTES,
        NOT_SHARED,
        build_submission,
        load_results,
    )

    run = _pick_run(reports_root(args.out), args.run_id)
    if run is None:
        _say("There is no such run. `benchy report --list` shows your runs.")
        return 1
    try:
        record = build_submission(load_results(run))
    except SubmissionError as exc:
        _say(f"Cannot share {run.name}: {exc}")
        return 1
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if not args.export:
        _say(f"This is exactly what would be shared for run {run.name}:\n")
        for field_name, note in FIELD_NOTES:
            _say(f"  {field_name:<12} {note}")
        _say(f"  never shared: {NOT_SHARED}\n")
        print(text)
        _say(
            "Nothing was written or sent. To save it for a contribution: "
            "benchy share --export [FILE]"
        )
        return 0
    target = Path(args.export if args.export != "-" else f"{record['submission_id']}.json")
    target.write_text(text, encoding="utf-8")
    _say(f"Saved {target}. Nothing was sent anywhere.")
    _say(
        "To contribute it, open a pull request that adds it as "
        f"results/submissions/{record['submission_id']}.json in "
        "https://github.com/AdityaTummuri/QEDCode-benchy. Note: a pull request shows your "
        "GitHub account name; the file itself contains no identity."
    )
    return 0


def cmd_suites(args: argparse.Namespace) -> int:
    from benchy.suite import SuiteError, check_task, list_builtin_suites, load_suite

    if args.action in ("check", "fetch"):
        try:
            suite = load_suite(args.suite)
            tasks = suite.select([t for t in args.tasks.split(",") if t.strip()])
        except SuiteError as exc:
            _say(f"Error: {exc}")
            return 2
    if args.action == "fetch":
        if suite.kind != "swebench":
            _say(f"{suite.name} ships everything it needs; there is nothing to fetch.")
            return 0
        from benchy.swebench.fetch import fetch

        return fetch(tasks, assume_yes=args.yes, say=_say)
    if args.action == "check":
        bad = 0
        results = {}
        for task in tasks:
            try:
                result = check_task(task)
            except SuiteError as exc:
                _say(f"Error: {exc}")
                return 2
            results[task.id] = result.valid
            bad += not result.valid
            lost = (
                f"  ({len(result.p2p_lost)} PASS_TO_PASS fail here already)"
                if result.p2p_lost
                else ""
            )
            print(
                f"{'ok     ' if result.valid else 'INVALID'}  {task.id}"
                + (lost if result.valid else f"  ({'; '.join(result.problems)})"),
                flush=True,
            )
        if suite.kind == "swebench":
            from benchy.swebench.validity import save_validity

            path = save_validity(suite, results)
            _say(f"Saved which tasks are valid on this computer in {path}")
        print(
            f"{len(tasks) - bad} of {len(tasks)} tasks valid "
            f"(suite {suite.name} {suite.version}, fingerprint {suite.fingerprint()[:12]})"
        )
        return 1 if bad else 0
    for name in list_builtin_suites():
        suite = load_suite(name)
        print(f"{suite.name} {suite.version}  ({len(suite.tasks)} tasks)  {suite.description}")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Known answers: the oracle must resolve everything, the broken model nothing."""
    from benchy.runner.clients import make_model
    from benchy.runner.experiment import ExperimentConfig, run_experiment
    from benchy.suite import SuiteError, load_suite

    try:
        suite = load_suite(args.suite)
        for task in suite.select([t for t in args.tasks.split(",") if t.strip()]):
            task.python()  # SWE-bench tasks must be fetched first
    except SuiteError as exc:
        _say(f"Error: {exc}")
        return 2
    expectations = {"scripted:oracle": True, "scripted:broken": False}
    failures = []
    with tempfile.TemporaryDirectory(prefix="benchy-selftest-") as tmp:
        out = Path(args.out).expanduser() if args.out else Path(tmp)
        for model, expect in expectations.items():
            client, spec = make_model(model)
            swe = suite.kind == "swebench"
            tasks = suite.select([t for t in args.tasks.split(",") if t.strip()])
            cfg = ExperimentConfig(
                suite=suite,
                tasks=tasks,
                model=spec,
                time_limit_s=1800 if swe else 120,
                speed="fast" if swe else "normal",  # big repos: skip the full-suite baseline
            )
            wanted = "resolved" if expect else "unresolved"
            _say(f"Self-test with {model} (expect every task {wanted})")
            state, run_dir = run_experiment(cfg, client, out, progress=_say)
            for a in state.attempts:
                if a["resolved"] is not expect:
                    failures.append(f"{model}: {a['task_id']} {a['condition']} -> {a['status']}")
    if failures:
        _say("SELF-TEST FAILED:\n  " + "\n  ".join(failures))
        return 1
    _say("Self-test passed: runner, both conditions, evaluator and report match known answers.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from benchy.runner.qedcode_agent import qedcode_version
    from benchy.suite import list_builtin_suites

    print(f"Benchy {__version__}")
    print(f"QEDCode {qedcode_version()}")
    print(f"Built-in suites: {', '.join(list_builtin_suites())}")
    root = reports_root(args.out)
    print(f"Reports folder: {root} ({len(_run_dirs(root))} runs)")
    print("Sharing: nothing is ever uploaded; `benchy share` previews or exports a record.")
    try:
        from benchy.runner.clients import make_model

        client, spec = make_model("qedcode")
        ok = client.health()
        state = "answering" if ok else "NOT answering"
        print(f"QEDCode model: {spec.model} ({spec.backend}) — {state}")
    except Exception as exc:
        print(f"QEDCode model: not set up ({exc})")
    return 0


# --------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchy",
        description="Measure QEDCode against the same model without QEDCode. Runs only when you "
        "ask; reports stay on this computer.",
    )
    parser.add_argument("--version", action="version", version=f"benchy {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def out_flag(p: argparse.ArgumentParser) -> None:
        p.add_argument("--out", help="reports folder (default: $QEDCODE_HOME/benchy/reports)")

    run = sub.add_parser("run", help="run a benchmark")
    run.add_argument(
        "--model",
        default="qedcode",
        help="qedcode (your QEDCode model), ollama:<name>, openai:<url>#<model>, "
        "agy:<model> (agent mode: Antigravity's agent with and without QEDCode), "
        "scripted:oracle|broken (self-test)",
    )
    run.add_argument("--suite", default="benchy-core", help="built-in suite name or a folder path")
    run.add_argument("--tasks", default="", help="comma-separated task ids or prefixes")
    run.add_argument("--reps", type=int, default=1, help="repetitions per task (default 1)")
    run.add_argument(
        "--conditions",
        default=None,
        help="baseline,qedcode (default) or, with an agy: model, agent,agent+qedcode",
    )
    run.add_argument("--speed", default="normal", choices=["fast", "normal", "sure"])
    run.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="seconds per condition per attempt (default: the suite's, else 600)",
    )
    run.add_argument(
        "--baseline-context",
        default="bm25",
        choices=["bm25", "oracle"],
        help="SWE-bench suites: files the bare model sees: BM25 retrieval (default) or the files "
        "the reference fix changes (oracle; favours the baseline)",
    )
    run.add_argument("--seed", type=int, default=0, help="seed for the condition order")
    run.add_argument(
        "--qed-apply",
        default="any",
        choices=["any", "ab"],
        help="apply QEDCode's result at any grade (default) or only grade A/B",
    )
    run.add_argument("--price-in", type=float, help="USD per million input tokens (for cost)")
    run.add_argument("--price-out", type=float, help="USD per million output tokens (for cost)")
    out_flag(run)
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="view local reports")
    rep.add_argument("run_id", nargs="?")
    rep.add_argument("--list", action="store_true")
    rep.add_argument("--json", action="store_true", help="print results.json")
    out_flag(rep)
    rep.set_defaults(func=cmd_report)

    su = sub.add_parser("suites", help="list, check or fetch suites")
    su.add_argument("action", nargs="?", choices=["list", "check", "fetch"], default="list")
    su.add_argument("suite", nargs="?", default="benchy-core")
    su.add_argument("--tasks", default="", help="comma-separated task ids or prefixes")
    su.add_argument("--yes", "-y", action="store_true", help="fetch without asking first")
    su.set_defaults(func=cmd_suites)

    st = sub.add_parser("selftest", help="check the pipeline with scripted models (no GPU)")
    st.add_argument("--suite", default="benchy-core")
    st.add_argument("--tasks", default="", help="comma-separated task ids or prefixes")
    st.add_argument("--out", help="keep the self-test reports in this folder")
    st.set_defaults(func=cmd_selftest)

    sh = sub.add_parser("share", help="preview or export a sanitized result (never uploads)")
    sh.add_argument("run_id", nargs="?")
    sh.add_argument(
        "--export",
        nargs="?",
        const="-",
        metavar="FILE",
        help="write the record to FILE (default: <submission id>.json here)",
    )
    out_flag(sh)
    sh.set_defaults(func=cmd_share)

    status = sub.add_parser("status", help="versions, model and report folder")
    out_flag(status)
    status.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "reps", 1) < 1:
        _say("Error: --reps must be at least 1.")
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
