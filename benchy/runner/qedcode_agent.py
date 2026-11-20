"""The QEDCode condition: the same model, driven by QEDCode's engine (`qedcode.engine.api`).

Controls that keep the comparison fair:
- the model client is the one the baseline uses (passed in, never rebuilt from config);
- mix-mode helpers are off (a second, stronger model would change the experiment);
- QEDCode's memory of past fixes is off (no learning carried between tasks or repetitions);
- QEDCode never gets interactive answers: questions get no answer and approvals are declined;
- the time limit is enforced through QEDCode's own cancel hook and the shared client deadline.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

APPLY_POLICIES = ("any", "ab")  # apply any graded result, or only grades A/B


@dataclass
class QedOutcome:
    status: str  # "done" | "no_change" | "timeout" | "error"
    qed_status: str = ""  # QEDCode's own SolveResult.status
    grade: str | None = None
    applied: bool = False
    candidates: int = 0
    message: str = ""
    events: list[str] = field(default_factory=list)


def qedcode_version() -> str:
    try:
        import qedcode

        return str(qedcode.__version__)
    except Exception:  # pragma: no cover - reported, not fatal
        return "unavailable"


def run_qedcode(
    client,
    request: str,
    workspace: Path,
    *,
    speed: str,
    deadline: float,
    apply_policy: str = "any",
) -> QedOutcome:
    from qedcode.config import ProjectConfig, load_global, save_project
    from qedcode.engine import api
    from qedcode.engine.callbacks import NonInteractiveCallbacks
    from qedcode.models.schemas import Grade, Mode, Speed

    from benchy.runner.clients import DeadlineExceeded

    cfg = load_global().model_copy(deep=True)
    cfg.engine.learn = False
    mode = Mode.LOCAL if cfg.engine.mode is Mode.MIX else cfg.engine.mode
    save_project(workspace, ProjectConfig(python=sys.executable, confirmed=True))
    events: list[str] = []
    cb = NonInteractiveCallbacks(
        on_event=lambda e: events.append(f"[{e.kind}] {e.message}"),
        confirm_answer=False,
        cancelled=lambda: time.monotonic() > deadline,
    )
    try:
        result = api.solve(
            workspace, request, speed=Speed(speed), mode=mode, cb=cb, config=cfg, client=client
        )
    except DeadlineExceeded:
        return QedOutcome("timeout", message="time limit reached", events=events)
    except Exception as exc:
        return QedOutcome("error", message=f"{type(exc).__name__}: {exc}"[:500], events=events)

    out = QedOutcome(
        status="no_change",
        qed_status=result.status,
        grade=result.best.grade.value if result.best and result.best.grade else None,
        candidates=len(result.candidates),
        message=result.message[:500],
        events=events,
    )
    if result.status == "cancelled" or time.monotonic() > deadline:
        out.status = "timeout"
    elif result.status == "error":
        out.status = "error"
    if result.status == "done" and result.best is not None:
        allowed = apply_policy == "any" or result.best.grade in (Grade.A, Grade.B)
        if allowed:
            applied = api.apply_result(workspace, result.task.id, allow_low_grade=True, learn=False)
            out.applied = applied.status == "applied"
            if not out.applied:
                out.message = f"{out.message} | apply: {applied.message}"[:500]
        if out.status == "no_change" and out.applied:
            out.status = "done"
    return out
