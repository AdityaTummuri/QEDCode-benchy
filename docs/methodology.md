# Benchy methodology

## The question

*Given one model, does running it through QEDCode resolve more tasks, correctly and without
regressions, than using the model directly?*

## Conditions

| | baseline | qedcode |
|---|---|---|
| Model | the experiment's client | **the same client object** |
| Input | task text + every project file | task text + the project (QEDCode reads it itself) |
| Procedure | one request at temperature 0.2 (QEDCode's first-try temperature), full-file answers written as-is | `qedcode.engine.api.solve` at the chosen speed, then `apply_result` |
| Retries / checks | none | QEDCode's own (tries, cascade, repair) |
| Helper model | – | off (mix mode is run as local) |
| Memory of past fixes | – | off |
| Interactive answers | – | none: questions go unanswered, approvals are declined |
| Time limit | `--time-limit` | the same |

The baseline deliberately reuses nothing from QEDCode: no prompts, edit protocol, locator, test
writer or checks. A different harness (an agent with its own tools and retries) would be a different
baseline. Benchy measures QEDCode against the bare model.

`--qed-apply any` (default) applies QEDCode's best result at any grade, which mirrors QEDCode's bug
zoo runner. `--qed-apply ab` applies only grades A/B, trading resolutions for safety. The policy is
recorded in metadata.

## Agent mode

A second question, for people who code with an agent: *given one agent and one model, does adding
QEDCode make its fixes more reliable?* `benchy run --model agy:<model>` runs Google Antigravity's
agent CLI (`agy -p`) under two conditions:

| | agent | agent+qedcode |
|---|---|---|
| Agent and model | `agy`, `--model` as given | the same |
| Prompt | issue text + where the Python environment is + "make sure the fix is proven" | **the same text**; it does not name QEDCode |
| Workspace | fresh snapshot, `.venv` pointing at the task's environment | the same, plus the QEDCode skill (`.agents/skills/qedcode`) and `qed mcp` (`.agents/mcp_config.json`) for this workspace only |
| Permissions (one run, never saved) | the project's Python, read-only git, `ls`, `cat`, `grep`; no internet | the same, plus `qed` and QEDCode's MCP tools |
| Time limit | `--time-limit` (passed to `agy --print-timeout`) | the same |

**No internet on either side.** SWE-bench issues and their upstream fixes are public, and in a
first test run the agent searched the web eight times before writing its fix. So both workspaces
get a `PreToolUse` hook (`.agents/hooks.json`) that refuses the web-search and browser tools
(permission rules do not cover `search_web`), and both runs deny URL reads and network commands
(`gh`, `curl`, `wget`, `git fetch/clone/pull`, `pip`, `uv`, `npm`); deny rules override the user's
own allow rules. A program the agent writes could still open a socket; the report counts refused
web calls per attempt (`agent_web_blocked`).

Setup files are hidden from git (`.git/info/exclude`), so the evaluator never sees them, and pip
and uv are told to stay offline so the shared task environments cannot be changed. The agent
decides by itself whether to use QEDCode; the report says how often it did (a receipt in
`.qed/receipts/`). Besides the resolution rate, the report counts how often each side *said* it had
fixed the issue (it finished normally, changed source code, and its final message does not say it
failed) and how often the hidden tests then disagreed: a false claim. That reading of the final
message is a heuristic and is labelled as one.

Turns, tokens and per-tool times come from the agent's own event stream
(`agy --output-format stream-json`, kept in each attempt's `logs/`). Benchy cannot set the
agent's temperature or seed, so repeated runs can differ, and no cost is estimated (a flat plan). If the plan's quota or rate limit stops the agent, the run ends, the unfinished pair
is dropped, and the report says why (`benchy run` exits with code 3).

## Controls

1. **Snapshot.** For every attempt, Benchy builds a fresh git repository from the task's project
   files, with a fixed author, dates and line endings. Both conditions of a pair must produce the
   same commit sha; otherwise the run stops.
2. **Order.** Condition order is shuffled per (task, repetition) with `--seed`, so warm-cache
   effects do not always favour the same side.
3. **Metering.** One wrapper counts calls and estimated tokens (characters / 3.5) and enforces the
   deadline before each call and on every streamed token, the same way for both conditions.

## Evaluation

The evaluator (`benchy-pytest-hidden` v1) is the only judge, and it ignores every claim made by an
agent, including QEDCode's grade.

1. Start from a pristine copy of the project.
2. Copy in the agent's changes to non-test source files only. Changes under `tests/`, `test_*.py`,
   `*_test.py`, `conftest.py`, `pyproject.toml`, `setup.cfg`, `pytest.ini` and `tox.ini` are
   discarded and listed in the results.
3. Add the hidden tests.
4. Run the original visible tests and the hidden tests in separate pytest runs with a timeout, a
   scrubbed environment and JUnit XML for per-test outcomes.

**Resolved** means every hidden test passes and no visible test that passed on the original code
now fails. **Regression** means a previously passing visible test fails, errors or times out.

## SWE-bench suites

`swebench-verified-py` (`kind = "swebench"`) runs real GitHub issues from SWE-bench Verified on
whole repositories. The question and the controls stay the same; four things differ.

**Environments.** No Docker. Each repository version gets a uv virtualenv with uv-managed CPython
at SWE-bench's Python version and SWE-bench's pins (`benchy/swebench/specs.py`, adapted from the
SWE-bench harness). The project itself is installed non-editable for its dependencies and entry
points; tests run with `python -m pytest` from the workspace, which puts the workspace's own code
first on `sys.path`. Both conditions and the judge use the same interpreter.

**Baseline input.** A repository does not fit in a prompt, so the bare model gets SWE-bench's
retrieval baseline: the issue text plus the source files that BM25 ranks highest against it, whole
and with line numbers, up to about 13,000 tokens. It answers with one unified diff, applied with
`git apply`. `--baseline-context oracle` gives instead the files the reference fix changes. That
tells the baseline where the bug is, so it is the strictest test of QEDCode. The setting is
recorded in metadata and shared records, and aggregates never pool the two.

**Judge** (`benchy-swebench` v1). Start from the base commit, copy in only the agent's changes to
non-test files (the same discard rules as above), apply SWE-bench's test patch, run the instance's
test files with pytest, and read one outcome per test node. **Resolved** = every FAIL_TO_PASS test
passes and every PASS_TO_PASS test that passes on the base commit still passes. xfail counts as a
pass, as in SWE-bench. Test ids follow SWE-bench's logs: sympy ids are bare function names, and ids
SWE-bench cut at a space inside parameters are matched by prefix.

**The one deviation.** A rebuilt environment never matches SWE-bench's images exactly, so a few
PASS_TO_PASS tests can fail before any change. Like visible tests in `benchy-pytest-hidden`, only
tests that pass on the original code can count as a regression. `benchy suites check` lists how
many PASS_TO_PASS tests each task loses this way and marks a task invalid when it loses more than
10%. FAIL_TO_PASS tests are never relaxed: each must fail on the base commit and pass with the
reference fix, or the task is invalid.

**Validity per computer.** `benchy suites check` records which tasks are valid on this computer
(keyed by the suite fingerprint, which covers the instances and their environment specs). `benchy
run` skips the others for *both* conditions and lists them in metadata
(`skipped_not_valid_here`). The shipped instance list contains only instances that were valid on
the reference machine (macOS arm64); the rest are listed with reasons in the suite's EXCLUDED.md.
Selection never used any model's result.

**Time.** QEDCode at normal speed runs the whole test suite of the repository once before it
starts, which takes minutes on these repositories. The suite's default time limit is therefore
1800 s per condition. The baseline makes one call either way, so a longer limit cannot help it.

## Statistics

- Resolution rate per condition, with a 95% Wilson score interval.
- A paired comparison over complete (task, repetition) pairs: both resolved, only baseline, only
  QEDCode, neither. The difference in rate comes with a two-sided exact McNemar p-value.
- Medians for time and tokens. Costs only when you give prices.
- Reports flag any run with fewer than 30 pairs as a small sample. Use `--reps` for stochastic
  models.

## Task validity

`benchy suites check <suite>` proves, for each task, that the visible tests pass on the original
code, the hidden tests fail on it, and the reference `solution.patch` makes both pass. The suite
fingerprint (sha256 over every task file, including hidden tests) is recorded with each run, so
results always name the exact data.

## Self-tests are not measurements

`scripted:oracle` replays reference fixes and `scripted:broken` replays harmless non-fixes. They
check the whole pipeline against known answers. Their reports are labelled
"NOT A REAL MEASUREMENT", and `is_real_measurement` is false in their metadata.

## Known limitations

- `benchy-core` tasks are small single-file Python projects. `swebench-verified-py` covers real
  repositories, but only four of them, and its numbers are not comparable with the official
  SWE-bench leaderboard (a subset, environments rebuilt without Docker, a retrieval baseline
  instead of an agent).
- Agent mode compares one agent with and without QEDCode, not models; its "said it was fixed"
  count is read from the agent's final message.
- Token counts are estimates. Times depend on the machine and are comparable only within a run.
- Agent-written code runs on your machine during evaluation (as with QEDCode itself). Run Benchy
  where you would run QEDCode.
- Hidden tests in a public suite could leak into future model training data. Results on
  `benchy-core` should be read with that in mind.
