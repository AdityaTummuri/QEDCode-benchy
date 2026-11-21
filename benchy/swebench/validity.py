"""Which SWE-bench tasks are valid on this computer, as found by `benchy suites check`.

Stored per suite fingerprint in the cache, so a changed suite or changed environment specs need a
new check. `benchy run` skips tasks recorded as invalid and lists them in the report metadata.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchy.suite import Suite
from benchy.swebench import cache


def validity_path(suite: Suite) -> Path:
    return cache.cache_root() / "validity" / f"{suite.name}-{suite.fingerprint()[:16]}.json"


def save_validity(suite: Suite, results: dict[str, bool]) -> Path:
    path = validity_path(suite)
    known = load_validity(suite) or {}
    known.update(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(known, indent=1, sort_keys=True), encoding="utf-8")
    return path


def load_validity(suite: Suite) -> dict[str, bool] | None:
    path = validity_path(suite)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return {str(k): bool(v) for k, v in data.items()}
