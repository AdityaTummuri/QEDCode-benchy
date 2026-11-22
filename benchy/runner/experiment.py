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
from benchy.runner import baseline_swe
from benchy.runner.agent_cli import AGENT_CONDITIONS, QuotaExhausted, run_agent
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
    baseline_context: str = "bm25"  # SWE-bench tasks: "bm25" or "oracle"
    skipped_here: list[str] = field(default_factory=list)  # not valid on this computer


def make_evaluator(task: Task):
    """The judge for one task: the hidden-test evaluator, or the SWE-bench evaluator."""
    if task.swe is not None:
        from benchy.swebench.evaluate import SweEvaluator

        return SweEvaluator(task.swe, task.python())
    return Evaluator(task)


@dataclass
class RunState:
    run_id: str
    started_at: str
    attempts: list[dict] = field(default_factory=list)
    finished_at: str = ""
    complete: bool = False
    stopped_reason: str = ""


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
    evaluator,
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
        if condition in AGENT_CONDITIONS:
            out = run_agent(
                client,
                task.request,
                workspace,
                condition=condition,
                python=task.python(),
                limit_s=cfg.time_limit_s,
                log_dir=log_dir,
            )
            if out.status == "quota":
                raise QuotaExhausted(out.message or "the agent's plan ran out of quota")
            status, message = out.status, out.message
            extra = {
                "agent_used_qedcode": out.used_qedcode,
                "agent_receipts": out.receipts,
                "agent_claimed_fixed": out.claimed_fixed,
                "qed_grade": out.grade,
                "agent_final_text": out.final_text[-600:],
                "agent_qedcode_calls": out.qedcode_calls,
                "agent_web_blocked": out.web_blocked,
                "agent_tool_seconds": out.tool_seconds,
                # Counted by the agent CLI itself (not estimated); 0 when it reported nothing.
                "model_calls": out.turns or 0,
                "prompt_tokens_est": out.input_tokens or 0,
                "completion_tokens_est": out.output_tokens or 0,
                "tokens_est": (out.input_tokens or 0) + (out.output_tokens or 0),
            }
        elif condition == "baseline" and task.swe is not None:
            out, shown = baseline_swe.run_baseline_swe(
                metered,
                task.request,
                workspace,
                context=cfg.baseline_context,
                oracle_patch=task.swe.patch,
            )
            status, message = out.status, out.message
            extra = {
                "files_written": out.files_written,
                "rejected_paths": out.rejected_paths,
                "baseline_context_files": shown,
            }
        elif condition == "baseline":
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
                python=task.python(),
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
        if condition == "qedcode":  # the model-mode QEDCode condition
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
        "mode": "agent" if cfg.model.agent else "model",
        "stopped_reason": state.stopped_reason,
        "benchy_version": __version__,
        "qedcode_version": qedcode_version(),
        "suite": {
            "name": cfg.suite.name,
            "version": cfg.suite.version,
            "kind": cfg.suite.kind,
            "fingerprint_sha256": cfg.suite.fingerprint(),
            "tasks": [t.id for t in cfg.tasks],
            "skipped_not_valid_here": list(cfg.skipped_here),
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
            "baseline_max_tokens": (
                baseline_swe.MAX_TOKENS if cfg.suite.kind == "swebench" else baseline_mod.MAX_TOKENS
            ),
            "baseline_context": (
                f"{cfg.baseline_context}-{baseline_swe.CONTEXT_TOKENS // 1000}k-tokens"
                if cfg.suite.kind == "swebench" and cfg.baseline_context == "bm25"
                else (
                    cfg.baseline_context if cfg.suite.kind == "swebench" else "every project file"
                )
            ),
            "same_model_client_for_both": True,
            "price_per_mtok_usd": (
                {"input": cfg.price_in_per_mtok, "output": cfg.price_out_per_mtok}
                if cfg.price_in_per_mtok is not None
                else None
            ),
        },
        "evaluator": _evaluator_meta(cfg),
        "environment": {
            "os": platform.system(),
            "arch": platform.machine(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    }


def _evaluator_meta(cfg: ExperimentConfig) -> dict:
    if cfg.suite.kind == "swebench":
        from benchy.swebench.evaluate import SweEvaluator

        return {"name": SweEvaluator.name, "version": SweEvaluator.version}
    return {"name": Evaluator.name, "version": Evaluator.version}


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
    evaluators = {t.id: make_evaluator(t) for t in cfg.tasks}
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
    except QuotaExhausted as exc:
        state.stopped_reason = f"agent quota or rate limit reached: {exc}"
        # Keep only complete pairs: the unfinished pair would compare one side with nothing.
        state.attempts = [a for a in state.attempts if (a["task_id"], a["rep"]) != (task.id, rep)]
        progress(
            f"Stopped: the agent's plan reached its quota or rate limit ({exc}). Writing a "
            "report of the finished task pairs; run the remaining tasks later."
        )
    except KeyboardInterrupt:
        state.stopped_reason = "stopped by you"
        progress("Stopped by you. Writing a report of the attempts that finished...")
    finally:
        state.finished_at = _now()
        write_report(run_dir, metadata(cfg, state), state.attempts)
    return state, run_dir
