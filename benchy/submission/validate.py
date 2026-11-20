"""Validate a community submission: structure (JSON Schema) and meaning (consistency checks).

Stdlib only, so the repository's CI can run it from the trusted base branch with a plain Python and
no installed dependencies. It treats every input as untrusted data and never executes any of it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from benchy.submission import (
    MAX_BYTES,
    find_secrets,
    load_schema,
    submission_id,
)

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _is_type(value: Any, name: str) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return isinstance(value, _TYPES[name])


def check_schema(value: Any, schema: dict, where: str = "$") -> list[str]:
    """The JSON Schema subset the submission schema uses (type, enum, required, properties,
    additionalProperties, items, minItems, maxItems, pattern, maxLength, minimum, maximum)."""
    errors: list[str] = []
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        if not any(_is_type(value, n) for n in names):
            return [f"{where}: expected {' or '.join(names)}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{where}: {value!r} is not one of {schema['enum']}"]
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing {key}")
        for key, item in value.items():
            if key in props:
                errors += check_schema(item, props[key], f"{where}.{key}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{where}: unexpected field {str(key)[:40]!r}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']} items")
        if len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{where}: at most {schema['maxItems']} items")
        if "items" in schema and not errors:
            for i, item in enumerate(value):
                errors += check_schema(item, schema["items"], f"{where}[{i}]")
                if len(errors) > 20:
                    break
    if isinstance(value, str):
        if len(value) > schema.get("maxLength", len(value)):
            errors.append(f"{where}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value[:40]!r} has an unexpected format")
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: above {schema['maximum']}")
    return errors


def check_meaning(record: dict, known_suites: dict[tuple[str, str], dict] | None) -> list[str]:
    """Consistency checks a schema cannot express. `known_suites` maps (name, version) to
    {"fingerprint": sha, "tasks": [ids]}; None skips the suite check (local preview)."""
    errors: list[str] = []
    if record["submission_id"] != submission_id(record):
        errors.append("submission_id does not match the record's content")
    name = record["model"]["name"]
    if ".." in name or "//" in name or name.startswith("/"):
        errors.append("model.name looks like a path")
    suite = record["suite"]
    tasks: list[str] | None = None
    if known_suites is not None:
        known = known_suites.get((suite["name"], suite["version"]))
        if known is None:
            errors.append(f"unknown suite {suite['name']} {suite['version']}")
        elif known["fingerprint"] != suite["fingerprint_sha256"]:
            errors.append("suite fingerprint does not match the published suite (modified tasks?)")
        else:
            tasks = known["tasks"]
    reps = record["controls"]["repetitions"]
    limit = record["controls"]["time_limit_s_per_condition"]
    seen: set[tuple] = set()
    for i, a in enumerate(record["attempts"]):
        where = f"attempts[{i}]"
        key = (a["task_id"], a["rep"], a["condition"])
        if key in seen:
            errors.append(f"{where}: duplicate attempt {key}")
        seen.add(key)
        if tasks is not None and a["task_id"] not in tasks:
            errors.append(f"{where}: task {a['task_id']} is not in the suite")
        if a["rep"] > reps:
            errors.append(f"{where}: rep {a['rep']} exceeds repetitions {reps}")
        if a["hidden_passed"] > a["hidden_total"]:
            errors.append(f"{where}: more hidden tests passed than exist")
        if a["visible_passed"] > a["visible_total"]:
            errors.append(f"{where}: more visible tests passed than exist")
        if a["resolved"] and (a["regression"] or a["hidden_passed"] != a["hidden_total"]):
            errors.append(f"{where}: resolved needs all hidden tests passing and no regression")
        if a["seconds"] > limit * 1.5 + 120:
            errors.append(f"{where}: seconds far above the time limit")
        if a["condition"] == "baseline" and a["qed_grade"] is not None:
            errors.append(f"{where}: a baseline attempt cannot have a QEDCode grade")
        if a["condition"] == "baseline" and a["model_calls"] > 1:
            errors.append(f"{where}: the baseline makes at most one model call")
        if len(errors) > 30:
            break
    # Structurally complete: every task in the run has every rep for both conditions.
    run_tasks = sorted({a["task_id"] for a in record["attempts"]})
    conds = ("baseline", "qedcode")
    expected = {(t, r, c) for t in run_tasks for r in range(1, reps + 1) for c in conds}
    missing = expected - seen
    if missing:
        example = sorted(missing)[0]
        errors.append(f"incomplete run: {len(missing)} attempt(s) missing, e.g. {example}")
    return errors


def validate_record(record: Any, known_suites: dict | None = None) -> list[str]:
    errors = check_schema(record, load_schema())
    if errors:
        return errors
    errors = find_secrets(record)
    return errors + check_meaning(record, known_suites)


def validate_bytes(data: bytes, known_suites: dict | None = None) -> tuple[dict | None, list[str]]:
    """Parse and validate the raw bytes of a submission file."""
    if len(data) > MAX_BYTES:
        return None, [f"file is larger than {MAX_BYTES // 1024} KB"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, ["file is not UTF-8 text"]
    try:
        record = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"not valid JSON: {exc.msg} at line {exc.lineno}"]
    return record, validate_record(record, known_suites)


def known_suites(suites_dir) -> dict[tuple[str, str], dict]:
    """(name, version) -> fingerprint and task ids for every suite folder in `suites_dir`."""
    from pathlib import Path

    from benchy.suite import SuiteError, load_suite

    found: dict[tuple[str, str], dict] = {}
    for path in sorted(Path(suites_dir).iterdir()):
        if not path.is_dir():
            continue
        try:
            suite = load_suite(path)
        except SuiteError:
            continue
        found[(suite.name, suite.version)] = {
            "fingerprint": suite.fingerprint(),
            "tasks": [t.id for t in suite.tasks],
        }
    return found
