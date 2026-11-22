"""Agent mode (agent vs agent+qedcode), tested offline with a fake `agy` script on PATH.

The fake agent reads its mode from FAKE_AGY_MODE:
  fix      writes the reference fix and says it is done
  wrong    changes the code without fixing it and still says it is done
  nothing  changes nothing and says it could not fix it
  quota    exits 1 with a quota error
On the QEDCode side (a `.agents/mcp_config.json` exists) it also writes a receipt, as an agent that
called QEDCode's check tool would. Every call's arguments are appended to FAKE_AGY_LOG.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from benchy.cli import main
from benchy.runner import agent_cli
from tests.test_swebench import BUGGY, FIXED, fake  # noqa: F401  (fixture)

FAKE_AGY = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
with open(os.environ["FAKE_AGY_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
mode = os.environ.get("FAKE_AGY_MODE", "fix")
if mode == "quota":
    sys.stderr.write("Error: RESOURCE_EXHAUSTED: you have used your quota\\n")
    sys.exit(1)
ops = Path("calc/ops.py")
if mode == "fix":
    ops.write_text({FIXED!r})
elif mode == "wrong":
    ops.write_text({BUGGY!r} + "\\n# looked at it\\n")
def ev(**kw):
    print(json.dumps(kw))
ev(event="init", init={{"model": "fake"}})
if Path(".agents/mcp_config.json").exists() and mode != "nothing":
    Path(".qed/receipts").mkdir(parents=True, exist_ok=True)
    Path(".qed/receipts/t1.json").write_text(json.dumps({{"grade": "A"}}))
    ev(event="step_update", step_update={{"step_type": "tool", "state": "DONE",
       "tool_name": "call_mcp_tool", "duration_seconds": 4.5,
       "tool_info": {{"parameters": {{"ServerName": "qedcode", "ToolName": "check"}}}}}})
ev(event="step_update", step_update={{"step_type": "tool", "state": "DONE",
   "tool_name": "run_command", "duration_seconds": 1.0,
   "tool_info": {{"parameters": {{"CommandLine": ".venv/bin/python -m pytest tests"}}}}}})
answer = "I could not fix it." if mode == "nothing" else "Done: the bug is fixed and tested."
ev(event="result", result={{"status": "SUCCESS", "response": answer, "num_turns": 3,
   "usage": {{"input_tokens": 1000, "output_tokens": 50, "thinking_tokens": 20}}}})
"""


@pytest.fixture()
def agy(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "agy"
    script.write_text(FAKE_AGY)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    log = tmp_path / "agy_calls.jsonl"
    monkeypatch.setenv("FAKE_AGY_LOG", str(log))
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: qedcode\n---\n")
    monkeypatch.setenv("BENCHY_QEDCODE_SKILL", str(skill))
    return log


def _run(suite, out: Path, *extra: str) -> int:
    return main(
        [
            "run",
            "--model",
            "agy:gemini-test",
            "--suite",
            str(suite.path),
            "--out",
            str(out),
            *extra,
        ]
    )


def _results(out: Path) -> dict:
    (run_dir,) = [p for p in out.iterdir() if p.is_dir()]
    return json.loads((run_dir / "results.json").read_text())


def test_agent_mode_runs_both_conditions_with_the_same_prompt(fake, agy, tmp_path, monkeypatch):
    suite, _, _ = fake
    monkeypatch.setenv("FAKE_AGY_MODE", "fix")
    out = tmp_path / "out"
    assert _run(suite, out) == 0
    res = _results(out)
    by = {a["condition"]: a for a in res["attempts"]}
    assert set(by) == {"agent", "agent+qedcode"}
    assert all(a["resolved"] for a in by.values())
    assert by["agent+qedcode"]["agent_used_qedcode"] and by["agent+qedcode"]["qed_grade"] == "A"
    assert not by["agent"]["agent_used_qedcode"]
    assert (
        by["agent+qedcode"]["agent_qedcode_calls"] == 1 and by["agent"]["agent_qedcode_calls"] == 0
    )
    assert by["agent"]["tokens_est"] == 1070 and by["agent"]["model_calls"] == 3
    assert by["agent"]["agent_tool_seconds"] == {"run_command": 1.0}
    # The setup files never reach the evaluator.
    for a in by.values():
        assert a["changed_files"] == ["calc/ops.py"]
    calls = [json.loads(line) for line in agy.read_text().splitlines()]
    assert len(calls) == 2
    prompts = {c[c.index("-p") + 1] for c in calls}
    assert len(prompts) == 1 and "QEDCode" not in prompts.pop()
    assert all(c[c.index("--model") + 1] == "gemini-test" for c in calls)
    allows = sorted(json.loads(c[c.index("--settings") + 1])["permissions"]["allow"] for c in calls)
    assert not any("qed" in rule for rule in allows[0])  # the agent-only side
    assert "mcp(qedcode/check)" in allows[1]
    # No internet on either side: the same deny rules, and the offline hook in both workspaces.
    denies = [json.loads(c[c.index("--settings") + 1])["permissions"]["deny"] for c in calls]
    assert denies[0] == denies[1] and "read_url(*)" in denies[0] and "command(gh)" in denies[0]
    md = (next(p for p in out.iterdir() if p.is_dir()) / "report.md").read_text()
    assert "Used QEDCode" in md and "agent + QEDCode" in md and "Agent turns" in md


def test_wrong_fix_counts_as_a_false_claim(fake, agy, tmp_path, monkeypatch):
    suite, _, _ = fake
    monkeypatch.setenv("FAKE_AGY_MODE", "wrong")
    out = tmp_path / "out"
    assert _run(suite, out, "--conditions", "agent") == 0
    res = _results(out)
    (att,) = res["attempts"]
    assert att["status"] == "done" and not att["resolved"] and att["agent_claimed_fixed"]
    assert res["summary"]["agent"]["agent"]["false_claims"] == 1


def test_giving_up_is_not_a_claim(fake, agy, tmp_path, monkeypatch):
    suite, _, _ = fake
    monkeypatch.setenv("FAKE_AGY_MODE", "nothing")
    out = tmp_path / "out"
    assert _run(suite, out, "--conditions", "agent") == 0
    (att,) = _results(out)["attempts"]
    assert att["status"] == "no_change" and not att["agent_claimed_fixed"]


def test_quota_stops_the_run_and_keeps_only_complete_pairs(fake, agy, tmp_path, monkeypatch):
    suite, _, _ = fake
    monkeypatch.setenv("FAKE_AGY_MODE", "quota")
    out = tmp_path / "out"
    assert _run(suite, out) == 3  # stopped by quota: a report of the finished pairs is written
    res = _results(out)
    assert res["attempts"] == []
    assert not res["metadata"]["complete"]
    assert "quota" in res["metadata"]["stopped_reason"]


def test_model_conditions_are_refused_in_agent_mode(fake, agy, tmp_path):
    suite, _, _ = fake
    assert _run(suite, tmp_path / "out", "--conditions", "baseline") == 2


def test_missing_skill_is_a_clear_error(fake, agy, tmp_path, monkeypatch):
    suite, _, _ = fake
    monkeypatch.setenv("BENCHY_QEDCODE_SKILL", str(tmp_path / "nowhere"))
    monkeypatch.setattr(agent_cli, "find_skill_dir", lambda: None)
    assert _run(suite, tmp_path / "out") == 2


def test_both_workspaces_get_the_offline_hook(tmp_path):
    import re

    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("x")
    spec = agent_cli.AgentSpec(skill_dir=skill, qed_command=["qed"])
    for condition in agent_cli.AGENT_CONDITIONS:
        ws = tmp_path / condition
        (ws / ".git" / "info").mkdir(parents=True)
        agent_cli.prepare_agent_workspace(ws, Path(sys.executable), condition, spec)
        hook = json.loads((ws / ".agents" / "hooks.json").read_text())
        (group,) = hook["benchy-offline"]["PreToolUse"]
        assert re.fullmatch(group["matcher"], "search_web")
        assert re.fullmatch(group["matcher"], "browser_click_element")
        assert not re.fullmatch(group["matcher"], "run_command")
        assert ".agents/" in (ws / ".git" / "info" / "exclude").read_text()


def test_claim_heuristic():
    assert agent_cli.GAVE_UP_RE.search("Sorry, I was not able to reproduce it")
    assert not agent_cli.GAVE_UP_RE.search("Fixed: the clamp now returns high.")
    assert agent_cli.QUOTA_RE.search("429 Too Many Requests")


def test_parse_stream_survives_a_cut_off_run():
    lines = [
        '{"event":"step_update","step_update":{"step_type":"agent_response","state":"DONE",'
        '"text_delta":"Working","usage":{"input_tokens":10,"output_tokens":2}}}',
        "not json",
        '{"event":"step_update","step_update":{"step_type":"tool","state":"DONE",'
        '"tool_name":"run_command","duration_seconds":2,'
        '"tool_info":{"parameters":{"CommandLine":"qed check --json"}}}}',
    ]
    lines.append(
        '{"event":"step_update","step_update":{"step_type":"tool","state":"ERROR",'
        '"tool_name":"search_web"}}'
    )
    s = agent_cli.parse_stream("\n".join(lines))
    assert s.web_blocked == 1
    assert s.status == "" and s.final_text == "Working"
    assert (s.input_tokens, s.output_tokens, s.qedcode_calls) == (10, 2, 1)


def test_agent_mode_runs_are_not_shareable_yet():
    from benchy.submission.sanitize import SubmissionError, build_submission

    with pytest.raises(SubmissionError, match="Agent-mode"):
        build_submission({"metadata": {"is_real_measurement": True, "mode": "agent"}})
