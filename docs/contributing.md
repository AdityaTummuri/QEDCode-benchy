# Contributing results and code

## Sharing a benchmark result

1. Run a benchmark with a real model: `benchy run --reps 3` (or `qed benchy run --reps 3`).
2. Preview exactly what would be shared: `benchy share`. Nothing is written or sent.
3. Save it: `benchy share --export`. This writes `<submission id>.json` in the current folder.
4. Open a pull request that adds that file as `results/submissions/<submission id>.json`.

**The pull request shows your GitHub account.** The file itself contains no identity (see
[privacy.md](privacy.md)). If you do not want your account linked to a result, do not open a pull
request. There is no anonymous upload service (see the plan's revisions for why).

Only complete runs with both conditions on a published suite can be shared. Self-tests
(`scripted:*` models) are always refused.

## What the automated check does

`validate-submission` runs on every pull request that touches `results/`. It:

- uses the validator from the **base branch** and reads the pull request only as data (through
  `git show`). Nothing from the pull request is executed;
- accepts only **new** regular, non-executable files named `results/submissions/<64 hex>.json`,
  at most 20 per pull request and 512 KB each;
- checks the JSON Schema (`benchy/submission/schema.json`), with no unknown fields anywhere;
- checks that the `submission_id` matches the content and the file name, and that the record is
  not a duplicate;
- checks that the suite name, version and fingerprint match a suite published in this repository,
  and that task ids exist in it;
- checks that the run is complete: every task × repetition × condition is present exactly once;
- checks that the numbers are possible: test counts, "resolved" consistent with the tests, times
  within the limit, no QEDCode grade on baseline attempts, at most one baseline model call;
- rejects anything that looks like a key, token, email address, IP address or local path.

## What a maintainer does before merging

A passing check proves the file is well-formed and consistent. **It does not prove the benchmark
really ran.** For the first releases every submission is merged by hand:

- confirm the pull request changes **only** files in `results/submissions/`. With the
  `pull_request` trigger, the workflow file comes from the pull request itself, so the review is
  what stops a pull request that edits the workflow;
- glance at the numbers for anything implausible;
- merge. `update-results` then regenerates `leaderboard/leaderboard.json` and the README table
  with `bot/aggregate.py`. Aggregates are never edited by hand.

To mark a result **independently reproduced**, re-run the same suite, model and QEDCode version
yourself, then add its `submission_id` to `results/reproduced.json` in a separate pull request.

Repository settings this relies on: protect `main` (required review, required `ci` and
`validate-submission` checks, CODEOWNERS review), and let `github-actions[bot]` push the
aggregate commit. If branch protection blocks that push, run `python3 bot/aggregate.py` and commit
the result in the merge pull request instead (`ci` fails while aggregates are stale).

## Code changes

```bash
uv venv --python 3.12 && uv pip install -e ../QEDCode -e . pytest ruff
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/benchy suites check benchy-core
```

Changing a task in a suite changes its fingerprint, so it needs a new suite version. Results from
different versions are never pooled.
