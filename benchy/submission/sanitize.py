"""Build a community submission from a local run, keeping only approved, generalized fields.

What is shared is decided here by listing the allowed fields (an allowlist), never by removing
known-bad ones. Everything else in the local report stays on the user's machine: messages, model
transcripts, file names, run ids, exact timestamps and logs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from benchy.submission import SubmissionError, find_secrets, submission_id
from benchy.submission.validate import validate_record

ATTEMPT_FIELDS = (
    "task_id", "rep", "condition", "status", "resolved", "regression", "hidden_passed",
    "hidden_total", "visible_passed", "visible_total", "seconds", "model_calls", "tokens_est",
    "qed_grade",
)  # fmt: skip
_PATHLIKE = re.compile(r"^(?:/|~|[A-Za-z]:[\\/])|\\|\.gguf$", re.IGNORECASE)


def _general_model_name(name: str) -> str:
    """A model name without any local path: '/models/x/qwen-4b.gguf' -> 'qwen-4b'."""
    if _PATHLIKE.search(name):
        name = re.split(r"[\\/]", name)[-1]
        name = re.sub(r"\.gguf$", "", name, flags=re.IGNORECASE)
    if name.count(":") and name.split(":", 1)[0] in ("llamacpp", "ollama", "openai_compat"):
        name = name.split(":", 1)[1]  # the backend is recorded separately
    return name[:100]


def _general_os(value: str) -> str:
    return value if value in ("Linux", "Darwin", "Windows") else "other"


def _general_arch(value: str) -> str:
    v = value.lower()
    if v in ("x86_64", "amd64"):
        return "x86_64"
    if v in ("arm64", "aarch64"):
        return "arm64"
    return "other"


def build_submission(results: dict) -> dict:
    """The record that would be shared for a local results.json. Raises SubmissionError."""
    meta = results.get("metadata", {})
    if not meta.get("is_real_measurement", False):
        raise SubmissionError(
            "This run used a scripted stand-in model (a self-test). Self-tests are never shared."
        )
    if not meta.get("complete", False):
        raise SubmissionError(
            "This run did not finish (it was stopped early). Only complete runs can be shared."
        )
    controls = meta["controls"]
    if sorted(controls["conditions"]) != ["baseline", "qedcode"]:
        raise SubmissionError("Only runs with both conditions (baseline, qedcode) can be shared.")
    record = {
        "schema_version": 1,
        "benchy_version": meta["benchy_version"],
        "qedcode_version": meta["qedcode_version"],
        "run_date": str(meta["started_at"])[:10],  # the day only, not the time
        "suite": {
            "name": meta["suite"]["name"],
            "version": meta["suite"]["version"],
            "fingerprint_sha256": meta["suite"]["fingerprint_sha256"],
        },
        "model": {
            "backend": meta["model"]["backend"],
            "name": _general_model_name(str(meta["model"]["name"])),
        },
        "controls": {
            "conditions": ["baseline", "qedcode"],
            "repetitions": controls["repetitions"],
            "time_limit_s_per_condition": controls["time_limit_s_per_condition"],
            "qedcode_speed": controls["qedcode_speed"],
            "qedcode_apply_policy": controls["qedcode_apply_policy"],
            "order_seed": controls["order_seed"],
            **(
                {"baseline_context": controls["baseline_context"]}
                if "baseline_context" in controls
                else {}
            ),
        },
        "environment": {
            "os": _general_os(meta["environment"]["os"]),
            "arch": _general_arch(meta["environment"]["arch"]),
            "python": meta["environment"]["python"],
        },
        "attempts": [
            {
                **{k: a.get(k) for k in ATTEMPT_FIELDS},
                "seconds": round(float(a["seconds"]), 1),
                "qed_grade": a.get("qed_grade") if a["condition"] == "qedcode" else None,
            }
            for a in sorted(
                results["attempts"], key=lambda a: (a["task_id"], a["rep"], a["condition"])
            )
        ],
    }
    secrets = find_secrets(record)
    if secrets:
        raise SubmissionError(
            "Refusing to share: " + "; ".join(secrets[:5]) + ". Nothing was written."
        )
    record["submission_id"] = submission_id(record)
    problems = validate_record(record)
    if problems:
        raise SubmissionError("The submission would be invalid: " + "; ".join(problems[:5]))
    return record


def load_results(run_dir: Path) -> dict:
    try:
        return json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionError(f"Cannot read {run_dir / 'results.json'}: {exc}") from exc


FIELD_NOTES = [
    ("versions", "Benchy and QEDCode versions"),
    ("run_date", "the day of the run (no time of day)"),
    ("suite", "suite name, version and fingerprint"),
    ("model", "model backend and name (any local file path removed)"),
    ("controls", "repetitions, time limit, QEDCode speed and apply policy, order seed"),
    ("environment", "OS family, CPU architecture (x86_64/arm64), Python major.minor"),
    ("attempts", "per attempt: task id, outcome, test counts, seconds, model calls, est. tokens, "
     "QEDCode grade"),
]  # fmt: skip
NOT_SHARED = (
    "code, patches, file names, model prompts and replies, logs, error messages, hostname, "
    "username, paths, exact timestamps, run id, IP address, GitHub account"
)
