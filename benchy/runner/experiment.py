"""Experiment orchestration: every (task, repetition) runs both conditions under identical controls.

For each task and repetition:
  1. a fresh, identical git snapshot is built for each condition (the commit sha is checked to be
     the same, so both start from exactly the same repository);
  2. the conditions run in an order shuffled with the recorded seed (so warm-cache or ordering
     effects do not systematically favour one side);
  3. each condition gets the same model client, the same time limit and the same usage meter;
  4. the same independent evaluator judges both final workspaces.

Every attempt is recorded, including timeouts, crashes and "no change" answers.
"""

from __future__ import annotations

import json
import platform
import random
import secrets
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from benchy import __version__
from benchy.evaluators.pytest_eval import Evaluator
from benchy.runner import baseline as baseline_mod
from benchy.runner.clients import MeteredClient, ModelSpec
from benchy.runner.qedcode_agent import run_qedcode
from benchy.suite import Suite, Task, prepare_workspace

CONDITIONS = ("baseline", "qedcode")


@dataclass
class ExperimentConfig:
    suite: Suite
    tasks: list[Task]
    model: ModelSpec
    reps: int = 1
    conditions: tuple[str, ...] = CONDITIONS
    speed: str = "normal"
    time_limit_s: float = 600.0
    seed: int = 0
    qed_apply: str = "any"
    price_in_per_mtok: float | None = None
    price_out_per_mtok: float | None = None


@dataclass
class RunState:
    run_id: str
    started_at: str
    attempts: list[dict] = field(default_factory=list)
    finished_at: str = ""
    complete: bool = False


def new_run_id() -> str:
    return datetime.now(UTC).strftime("r-%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def condition_order(cfg: ExperimentConfig, task: Task, rep: int) -> list[str]:
    order = list(cfg.conditions)
    random.Random(f"{cfg.seed}:{task.id}:{rep}").shuffle(order)
    return order


def _cost(cfg: ExperimentConfig, prompt_tok: int, completion_tok: int) -> float | None:
    if cfg.price_in_per_mtok is None or cfg.price_out_per_mtok is None:
        return None
    return round(
        prompt_tok / 1e6 * cfg.price_in_per_mtok + completion_tok / 1e6 * cfg.price_out_per_mtok, 6
    )


def run_attempt(
    cfg: ExperimentConfig,
    client,
    task: Task,
    rep: int,
    condition: str,
    order_index: int,
    evaluator: Evaluator,
    log_dir: Path,
    expected_commit: str | None,
) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"benchy-{condition}-") as tmp:
        workspace = Path(tmp) / task.id
        commit = prepare_workspace(task, workspace)
        if expected_commit is not None and commit != expected_commit:
            raise RuntimeError(
                f"Fairness check failed: {task.id} produced different snapshots ({commit} vs "
                f"{expected_commit}). Nothing was recorded for this pair."
            )
        if hasattr(client, "set_task"):  # scripted stand-in only
            client.set_task(task)
        started = time.monotonic()
        metered = MeteredClient(client, deadline=started + cfg.time_limit_s)
        extra: dict = {}
        if condition == "baseline":
            out = baseline_mod.run_baseline(metered, task.request, workspace, task.project_files())
            status, message = out.status, out.message
            extra = {"files_written": out.files_written, "rejected_paths": out.rejected_paths}
        else:
            out = run_qedcode(
                metered,
                task.request,
                workspace,
                speed=cfg.speed,
                deadline=started + cfg.time_limit_s,
                apply_policy=cfg.qed_apply,
            )
            status, message = out.status, out.message
            extra = {
                "qed_status": out.qed_status,
                "qed_grade": out.grade,
                "qed_applied": out.applied,
                "qed_candidates": out.candidates,
            }
        seconds = round(time.monotonic() - started, 2)
        if seconds > cfg.time_limit_s and status not in ("error",):
            status = "timeout"
        evaluation = evaluator.evaluate(workspace, log_dir=log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "transcript.json").write_text(
            json.dumps(metered.transcript, indent=1), encoding="utf-8"
        )
        if condition == "qedcode":
            (log_dir / "qedcode_events.txt").write_text("\n".join(out.events), encoding="utf-8")
    usage = metered.usage
    return {
        "task_id": task.id,
        "rep": rep,
        "condition": condition,
        "order": order_index,
        "snapshot_commit": commit,
        "status": status,
        "message": message,
        "seconds": seconds,
        "model_calls": usage.calls,
        "prompt_tokens_est": usage.prompt_tokens_est,
        "completion_tokens_est": usage.completion_tokens_est,
        "tokens_est": usage.total_tokens_est,
        "cost_usd_est": _cost(cfg, usage.prompt_tokens_est, usage.completion_tokens_est),
        "resolved": evaluation.resolved,
        "regression": evaluation.regression,
        "hidden_passed": evaluation.hidden_passed,
        "hidden_total": evaluation.hidden_total,
        "visible_passed": evaluation.visible_passed,
        "visible_total": evaluation.visible_total,
        "regressed_tests": evaluation.regressed_tests,
        "changed_files": evaluation.changed_files,
        "discarded_test_changes": evaluation.discarded_files,
        "eval_error": evaluation.error,
        **extra,
    }


def metadata(cfg: ExperimentConfig, state: RunState) -> dict:
    """Configuration and environment, generalized: no hostnames, usernames or local paths."""
    from benchy.runner.qedcode_agent import qedcode_version

    return {
        "run_id": state.run_id,
        "started_at": state.started_at,
        "finished_at": state.finished_at,
        "complete": state.complete,
        "is_real_measurement": not cfg.model.scripted,
        "benchy_version": __version__,
        "qedcode_version": qedcode_version(),
        "suite": {
            "name": cfg.suite.name,
            "version": cfg.suite.version,
            "fingerprint_sha256": cfg.suite.fingerprint(),
            "tasks": [t.id for t in cfg.tasks],
        },
        "model": {"backend": cfg.model.backend, "name": cfg.model.model},
        "controls": {
            "conditions": list(cfg.conditions),
            "repetitions": cfg.reps,
            "time_limit_s_per_condition": cfg.time_limit_s,
            "order_seed": cfg.seed,
            "qedcode_speed": cfg.speed,
            "qedcode_apply_policy": cfg.qed_apply,
            "qedcode_memory": "off",
            "qedcode_helper_model": "off",
            "baseline_temperature": baseline_mod.TEMPERATURE,
            "baseline_max_tokens": baseline_mod.MAX_TOKENS,
            "same_model_client_for_both": True,
            "price_per_mtok_usd": (
                {"input": cfg.price_in_per_mtok, "output": cfg.price_out_per_mtok}
                if cfg.price_in_per_mtok is not None
                else None
            ),
        },
        "evaluator": {"name": Evaluator.name, "version": Evaluator.version},
        "environment": {
            "os": platform.system(),
            "arch": platform.machine(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    }


def run_experiment(
    cfg: ExperimentConfig,
    client,
    out_root: Path,
    progress: Callable[[str], None] = lambda _m: None,
) -> tuple[RunState, Path]:
    """Run the experiment and write the local report. Always writes a report, even if stopped."""
    from benchy.reports.writer import write_report

    state = RunState(run_id=new_run_id(), started_at=_now())
    run_dir = out_root / state.run_id
    logs = run_dir / "logs"
    total = len(cfg.tasks) * cfg.reps * len(cfg.conditions)
    done = 0
    evaluators = {t.id: Evaluator(t) for t in cfg.tasks}
    try:
        for rep in range(1, cfg.reps + 1):
            for task in cfg.tasks:
                expected: str | None = None
                for index, condition in enumerate(condition_order(cfg, task, rep)):
                    done += 1
                    progress(f"[{done}/{total}] {task.id} rep {rep}: {condition} ...")
                    attempt = run_attempt(
                        cfg,
                        client,
                        task,
                        rep,
                        condition,
                        index,
                        evaluators[task.id],
                        logs / task.id / f"rep{rep}-{condition}",
                        expected,
                    )
                    expected = attempt["snapshot_commit"]
                    state.attempts.append(attempt)
                    verdict = "RESOLVED" if attempt["resolved"] else "not resolved"
                    if attempt["regression"]:
                        verdict += ", REGRESSION"
                    progress(
                        f"      {verdict} ({attempt['status']}, {attempt['seconds']}s, "
                        f"hidden {attempt['hidden_passed']}/{attempt['hidden_total']})"
                    )
        state.complete = True
    except KeyboardInterrupt:
        progress("Stopped by you. Writing a report of the attempts that finished...")
    finally:
        state.finished_at = _now()
        write_report(run_dir, metadata(cfg, state), state.attempts)
    return state, run_dir
