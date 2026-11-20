"""Community submissions: build a sanitized record from a local run, and validate one.

The same code runs on the user's machine (`benchy share`) and in the repository's CI (from the
trusted base branch, never from the pull request), so both agree on what is acceptable.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).with_name("schema.json")
MAX_BYTES = 512 * 1024
FILENAME = re.compile(r"^results/submissions/([0-9a-f]{64})\.json$")

# Values that look like credentials or personal data. A match rejects the submission outright:
# the sanitizer never tries to "clean" a secret, it refuses to share it.
SECRET_PATTERNS = [
    re.compile(p)
    for p in (
        r"sk-[A-Za-z0-9_-]{16,}",  # OpenAI-style keys
        r"sk-ant-[A-Za-z0-9_-]{16,}",
        r"gh[pousr]_[A-Za-z0-9]{20,}",  # GitHub tokens
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",  # AWS access key id
        r"hf_[A-Za-z0-9]{20,}",  # Hugging Face
        r"xox[abprs]-[A-Za-z0-9-]{10,}",  # Slack
        r"AIza[0-9A-Za-z_-]{30,}",  # Google
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",  # email addresses
        r"(?:\d{1,3}\.){3}\d{1,3}",  # IPv4 addresses
        r"(?:/Users/|/home/|[A-Za-z]:\\\\|~/)",  # local paths
    )
]


class SubmissionError(ValueError):
    """The run cannot be shared, or a submission is invalid. The message says why."""


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def canonical(record: dict) -> bytes:
    """Stable bytes of a record without its id: sorted keys, no whitespace."""
    body = {k: v for k, v in record.items() if k != "submission_id"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def submission_id(record: dict) -> str:
    return hashlib.sha256(canonical(record)).hexdigest()


def find_secrets(value: Any, where: str = "$") -> list[str]:
    """Every string (key or value) in `value` that matches a secret or personal-data pattern."""
    found: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            found += find_secrets(k, f"{where}.<key>")
            found += find_secrets(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += find_secrets(v, f"{where}[{i}]")
    elif isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                found.append(f"{where} looks like a secret, address or local path")
                break
    return found
