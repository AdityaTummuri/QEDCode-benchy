"""pytest plugin loaded by Benchy's SWE-bench evaluator (`-p benchy_swe_report`).

It writes `{node id: outcome}` as JSON to the path in `BENCHY_SWE_REPORT` when the session ends.
Outcomes: passed, failed, error (setup/teardown/collection), skipped, xfailed, xpassed.
Kept to hooks that exist in every pytest since 3.x, and to Python 3.6 syntax, because it runs
inside each task's own (old) environment.
"""

import json
import os

_RESULTS = {}
_BAD = ("failed", "error")


def _record(nodeid, outcome):
    if _RESULTS.get(nodeid) in _BAD:
        return
    _RESULTS[nodeid] = outcome


def pytest_runtest_logreport(report):
    if hasattr(report, "wasxfail"):
        if report.when == "call" or report.skipped:
            _record(report.nodeid, "xfailed" if report.skipped else "xpassed")
        return
    if report.when == "call":
        _record(report.nodeid, report.outcome)
    elif report.failed:
        _record(report.nodeid, "error")
    elif report.skipped:
        _record(report.nodeid, "skipped")


def pytest_collectreport(report):
    if report.failed:
        _record(report.nodeid or "<collection>", "error")


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("BENCHY_SWE_REPORT")
    if path:
        with open(path, "w") as fh:
            json.dump(_RESULTS, fh)
