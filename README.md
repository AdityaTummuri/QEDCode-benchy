<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="QEDCode" width="300">
  </picture>
</p>

# QEDCode Benchy

**An honest way to measure whether [QEDCode](https://github.com/AdityaTummuri/QEDCode) helps.**

Benchy runs the same model on the same tasks twice: once **bare** (one prompt, one answer) and once
**through QEDCode** (several tries, deterministic checks, one graded result). Both final results are
judged by the same **independent evaluator**, using hidden tests that neither side ever sees.

> QEDCode does the work. Benchy measures the results. You decide whether results are shared.
> (This version shares nothing: reports stay on your computer.)

## Status

| Milestone (from [the plan](docs/QEDCode_Benchy_Plan.md)) | State |
|---|---|
| 1. Prove the benchmark: one fair baseline-vs-QEDCode comparison, local report | Done |
| 2. Reproducible: fixed suite, repetitions, failure tracking, versions/config recorded | Done |
| 3. Optional install and lifecycle inside QEDCode (`qed benchy ...`) | Done (in QEDCode) |
| 4. Privacy-safe sharing: schema, sanitizer, local preview, export | Done (no upload service, see the plan) |
| 5. Automated PR validation of submissions | Done (GitHub Actions, human merge) |
| 6. Aggregates, README statistics, static dashboard | Done (fills in as results arrive) |
| 7. Standard suite: SWE-bench Verified (sympy, sphinx, pylint, xarray) without Docker | Done |

## Community results

<!-- benchy:stats:start -->
_No community results yet. Run `benchy run`, then `benchy share` to preview what a contribution contains._
<!-- benchy:stats:end -->

Dashboard: [`dashboard/index.html`](dashboard/index.html) (serve the repository, e.g. GitHub Pages).
Data: [`leaderboard/leaderboard.json`](leaderboard/leaderboard.json), generated only by
`bot/aggregate.py` from the records in [`results/submissions/`](results/submissions/).
A passing schema check does not prove a run happened, so results are labelled
*community-reported* until a maintainer reproduces them.

## Quick start

Benchy lives in the same Python environment as QEDCode. The easy way is `qed benchy install`.
For development:

```bash
# from a checkout of this repository, next to a QEDCode checkout
uv venv --python 3.12 && uv pip install -e ../QEDCode -e .

benchy selftest            # pipeline check with scripted stand-in models (no GPU, ~1 min)
benchy status              # versions, your QEDCode model, where reports go
benchy run                 # benchy-core suite, your QEDCode model, both conditions
benchy run --reps 5 --tasks b01,b04 --speed sure
benchy run --suite ../QEDCode/bugzoo          # any folder in bug-zoo format works
benchy report              # latest report;  benchy report --list  for all runs
benchy share               # preview exactly what a contribution would contain (sends nothing)
benchy share --export      # save it as <submission id>.json to add in a pull request
```

From QEDCode, the same commands are `qed benchy install`, `qed benchy run`, `qed benchy report`,
and so on.

Models: `--model qedcode` (default: the model `qed` is set up with), `ollama:<name>`,
`openai:<base url>#<model>` (LM Studio and others), `agy:<model>` (agent mode, below), or
`scripted:oracle|broken` for self-tests.
Add `--price-in/--price-out` (USD per million tokens) to get estimated costs for paid models.

**Agent mode (Antigravity).** `benchy run --model agy:gemini-3.8-flash-medium --suite
swebench-verified-py` runs Antigravity's agent CLI on each task twice: on its own, and with the
QEDCode skill and MCP server set up for that workspace. The prompt is the same and never names
QEDCode. The report adds how often the agent used QEDCode and how often each side said "fixed" when
the hidden tests disagreed. It runs on your Antigravity plan (no API key); if the quota runs out,
Benchy stops and reports the finished tasks. Needs `agy` signed in, and the
[QEDCode agent skill](https://github.com/AdityaTummuri/QEDCode-AgentSkill) (found next to this
checkout, in `~/.agents/skills/qedcode`, or via `BENCHY_QEDCODE_SKILL`). Details:
[methodology](docs/methodology.md#agent-mode).

**No GPU?** Set QEDCode up with a cloud model (`qed setup`, then choose cloud) and run
`benchy run --model qedcode --price-in <usd> --price-out <usd>`. Both conditions then use that
cloud model, and the task code is sent to its provider ([privacy](docs/privacy.md)). It works the
same from the terminal inside Antigravity or VS Code. QEDCode itself connects to those IDEs with
`qed connect antigravity` or `qed connect vscode`.

## What a run produces

```text
~/.qedcode/benchy/reports/<run-id>/     (or --out <folder>)
  report.md      human-readable results, uncertainty and limitations
  results.json   every attempt + summary (schema_version 1)
  results.csv    one row per attempt
  metadata.json  versions, suite fingerprint, controls, generalized environment
  logs/          per attempt: model transcript, QEDCode events, evaluator output
```

Metrics per condition: verified resolution rate with a 95% Wilson interval, regression rate,
timeouts and errors, "no usable change" answers, median time, model calls, estimated tokens and
cost. There is also a paired comparison over the same task and repetition, with an exact McNemar
p-value. A table compares QEDCode's own grade with the evaluator's verdict, so an over-confident
grade is visible.

## Fairness, in one list

- Same model client object for both conditions. QEDCode's helper model and its memory are off.
- Identical repository snapshot per task: fixed author/dates, and the commit sha is checked.
- Same time limit per condition. Condition order is shuffled per task and repetition with a
  recorded seed.
- One evaluator for both. It keeps only changes to non-test source files, discards edits to tests,
  `conftest.py` or test config, and runs the original visible tests plus the hidden tests.
- Every attempt counts: timeouts, crashes and unparsable answers stay in the denominator.

Details and known limitations: [docs/methodology.md](docs/methodology.md). What leaves your machine
(nothing, unless you open a pull request yourself): [docs/privacy.md](docs/privacy.md).
How contributions are checked: [docs/contributing.md](docs/contributing.md).

## Suites

| Suite | Tasks | What it is |
|---|---|---|
| `swebench-verified-py` 1.0.0 | 143 | [SWE-bench Verified](suites/swebench-verified-py/README.md) instances from sympy, sphinx, pylint and xarray, on the whole repository, judged by SWE-bench's FAIL_TO_PASS / PASS_TO_PASS tests. The standard suite: use it for results you publish. |
| `benchy-fresh` 1.0.0 (private) | 34 | [Real projects with newly planted bugs](docs/fresh-suites.md) (boltons, pyparsing, tomlkit, more-itertools, networkx): no model can have seen these fixes. Not published, because it holds the answers. |
| `benchy-core` 1.0.0 | 8 | small Python tasks (seven bug fixes, one feature) written for Benchy. Quick to run; good for trying a model and checking the pipeline. |

```bash
benchy suites fetch swebench-verified-py     # clones 4 repos and builds environments (asks first)
benchy suites check swebench-verified-py     # which tasks are valid on this computer
benchy run --suite swebench-verified-py      # 30 minutes per condition per task at most
```

On SWE-bench tasks the bare model gets SWE-bench's retrieval baseline (the issue plus the files
BM25 ranks highest, about 13k tokens, answered with one patch); `--baseline-context oracle` gives
it the files the real fix touched instead, the strictest comparison for QEDCode. The suite needs
`git` and [uv](https://docs.astral.sh/uv/), not Docker. Its numbers are not comparable with the
official SWE-bench leaderboard (see the [suite README](suites/swebench-verified-py/README.md)).

`benchy suites check` proves that every task is valid: on `benchy-core`, the visible tests pass on
the original code, the hidden tests fail on it, and the reference patch makes both pass; on
SWE-bench, the FAIL_TO_PASS tests fail before and pass with the reference fix, which breaks no
PASS_TO_PASS test.

## Development

```bash
.venv/bin/python -m pytest -q     # real pytest + the real QEDCode engine, scripted models
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Licensed under MIT. QEDCode itself is a separate project:
https://github.com/AdityaTummuri/QEDCode.
