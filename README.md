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
| 1. Prove the benchmark: one fair baseline-vs-QEDCode comparison, local report | **Done** |
| 2. Reproducible: fixed suite, repetitions, failure tracking, versions/config recorded | **Done** |
| 3. Optional install and lifecycle inside QEDCode (`qedcode benchy ...`) | Not started (QEDCode repo) |
| 4–6. Privacy-safe sharing, PR validation, community dashboard | Not started |

No real-model results have been published yet. Every number Benchy prints comes from a run you made.

## Quick start

Benchy lives in the same Python environment as QEDCode.

```bash
# from a checkout of this repository, next to a QEDCode checkout
uv venv --python 3.12 && uv pip install -e ../QEDCode -e .

benchy selftest            # pipeline check with scripted stand-in models (no GPU, ~1 min)
benchy status              # versions, your QEDCode model, where reports go
benchy run                 # benchy-core suite, your QEDCode model, both conditions
benchy run --reps 5 --tasks b01,b04 --speed sure
benchy run --suite ../QEDCode/bugzoo          # any folder in bug-zoo format works
benchy report              # latest report;  benchy report --list  for all runs
```

Models: `--model qedcode` (default: the model `qed` is set up with), `ollama:<name>`,
`openai:<base url>#<model>` (LM Studio and others), or `scripted:oracle|broken` for self-tests.
Add `--price-in/--price-out` (USD per million tokens) to get estimated costs for paid models.

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
(nothing, today): [docs/privacy.md](docs/privacy.md).

## Suites

`benchy-core` 1.0.0 has eight small Python tasks (seven bug fixes, one feature), written for Benchy
separately from QEDCode's own bug zoo. `benchy suites check` proves that every task is valid: the
visible tests pass on the original code, the hidden tests fail on it, and the reference patch makes
both pass.

## Development

```bash
.venv/bin/python -m pytest -q     # 34 tests, real pytest + real QEDCode engine, scripted models
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Licensed under MIT. QEDCode itself is a separate project:
https://github.com/AdityaTummuri/QEDCode.
