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

- The tasks are small single-file Python projects. Larger repositories may behave differently.
- Token counts are estimates. Times depend on the machine and are comparable only within a run.
- Agent-written code runs on your machine during evaluation (as with QEDCode itself). Run Benchy
  where you would run QEDCode.
- Hidden tests in a public suite could leak into future model training data. Results on
  `benchy-core` should be read with that in mind.
