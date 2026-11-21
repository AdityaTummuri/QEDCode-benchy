# QEDCode Benchy — Project Plan

**Status:** Milestones 1–6 implemented (2026-11-21); see *Revisions* below  
**Core project:** [QEDCode](https://github.com/AdityaTummuri/QEDCode)  
**Companion project:** [QEDCode-benchy](https://github.com/AdityaTummuri/QEDCode-benchy)

---

## Revisions (2026-11-21)

These parts of the original plan were removed or simplified during implementation. Each was either
unnecessary for the goal or created a risk or burden that outweighed its value.

| Original plan | Now | Why |
|---|---|---|
| Periodic "install Benchy" reminders with remind-later / don't-remind-again state | **Removed.** `qed setup` ends with one line naming `qed benchy install`. It never asks again. | Nagging an optional tool is user-hostile and needs state, a scheduler and settings for little gain. |
| `qedcode benchy disable` | **Removed.** `qed benchy uninstall` removes it and keeps reports. | With no reminders and no background work, there is nothing to disable. |
| `qedcode benchy leaderboard` | **Removed.** The dashboard and README table are in the Benchy repo. | A command that only prints a URL adds surface without value. |
| Command name `qedcode benchy ...` | `qed benchy ...` | QEDCode's executable is `qed`. |
| Persistent "sharing enabled" setting and automatic submission after each run | **Replaced** by per-run, explicit `benchy share` (preview) and `--export` (save a file). | Consent per result, after seeing it, is clearer than a standing setting. Nothing is ever sent automatically. |
| Server-side submission service + GitHub App opening anonymous bot PRs | **Deferred.** Contributors open the PR themselves; docs say plainly that it shows their GitHub account. | It needs hosting, a privileged credential, abuse controls and ongoing operation, and it is a large attack surface. Community results cannot be verified anyway, so anonymity buys little. It can be added later without changing the record format. |
| Random pseudonymous contributor id | **Removed.** Duplicates are found by content hash (`submission_id`). | Any stable id is a tracking identifier. Contributor counts are not needed. |
| `results/raw/` + `results/accepted/` + status markers | **One folder** `results/submissions/`: merged means accepted. `results/reproduced.json` lists reproduced ids. | Git history and review already give the states. Fewer places mean fewer inconsistencies. |
| Separate `sanitizer.py`, `deduplicator.py`, `readme_updater.py`, three workflows | `benchy/submission/` (shared by client and CI), `bot/validate_pr.py`, `bot/aggregate.py`; workflows `ci`, `validate-submission`, `update-results` | The client and CI must agree on validity, so they share one implementation. The dashboard is static and needs no workflow. |

Also changed in QEDCode: a candidate that changes no code outside tests (only comments or
formatting) is now graded C instead of B. Benchy's scripted self-test found it.

Added later the same day: **milestone 7, a standard suite.** `benchy-core` is eight small tasks,
which is enough to prove the pipeline but too easy and too small to be persuasive. Terminal-Bench
was considered and rejected as the main benchmark: its tasks need an agent with a shell, and
QEDCode by design never lets a model run commands, so it would measure something QEDCode does not
do. SWE-bench Verified matches what QEDCode does (patch a Python repository so its tests pass,
judged by hidden fail-to-pass tests).

## 1. Project goal

QEDCode Benchy is an optional benchmarking companion for QEDCode. It measures whether using QEDCode improves coding-agent outcomes compared with using the same agent without QEDCode.

The benchmark must produce reproducible, honest comparisons. Community participation is optional, privacy-conscious, and initiated only when a user explicitly runs Benchy.

**Core principle:** QEDCode does the work. Benchy measures the results. Users decide whether their results are shared.

## 2. Repository strategy

Keep the two projects separate:

### QEDCode

Repository: https://github.com/AdityaTummuri/QEDCode

Responsibilities:

- Continue to provide the core coding engine, CLI/TUI/MCP functionality.
- Detect whether the optional Benchy component is installed.
- Offer optional Benchy installation during setup.
- Provide commands to launch, update, disable, and uninstall Benchy.
- Never require Benchy for normal QEDCode operation.
- Never run benchmarks or collect benchmark data in the background.

### QEDCode Benchy

Repository: https://github.com/AdityaTummuri/QEDCode-benchy (Python package `qedcode-benchy`)

Responsibilities:

- Benchmark runner and experiment orchestration.
- Baseline-versus-QEDCode comparison.
- Independent evaluation and test execution.
- Local reports and logs.
- Privacy sanitization and optional community submission.
- Submission schemas and validation.
- GitHub Actions workflows.
- Aggregation, leaderboard data, and public dashboard.

The Benchy repository should link prominently back to QEDCode. QEDCode should link to Benchy documentation and releases.

## 3. Installation and lifecycle

Benchy is an optional component managed through QEDCode. Users should not need to clone a second repository or manually install a separate application.

`qed benchy install` installs it into QEDCode's own environment (after a yes). Normal QEDCode
installation and operation are unaffected whether or not Benchy is installed.

QEDCode shows no reminders (see *Revisions*): `qed setup` ends with one line naming the install
command, and that is all.

### Commands (implemented in QEDCode as `qed benchy`, see QEDCode's AGENTS.md 15.5)

| Command | Purpose |
|---|---|
| `qed benchy` / `qed benchy status` | Show whether Benchy is installed and how to use it |
| `qed benchy install [--from <path>]` | Install Benchy into QEDCode's environment (asks first) |
| `qed benchy uninstall` | Remove Benchy (reports are kept) |
| `qed benchy run` | Run a benchmark |
| `qed benchy report` | View local reports |
| `qed benchy selftest` | Check the pipeline with scripted models |
| `qed benchy suites [check]` | List or validate suites |
| `qed benchy share [--export]` | Preview or save a sanitized result |

The standalone `benchy` (alias `qedcode-benchy`) executable does the same and is not required.

## 4. Benchmark workflow

When a user explicitly runs Benchy:

1. Select a benchmark suite and task set.
2. Prepare a clean, reproducible repository snapshot for each task.
3. Run the baseline condition without QEDCode.
4. Run the QEDCode-assisted condition.
5. Keep the model/agent, model version, task, repository snapshot, permissions, time limits, and resource limits equivalent. The intended difference should be QEDCode's involvement.
6. Evaluate both outcomes using the same independent evaluator.
7. Record failures, incomplete runs, timeouts, and regressions—not only successful tasks.
8. Generate a local report.

Use isolated workspaces and do not expose hidden evaluator tests to the coding agent.

### Metrics

At minimum, capture:

- Verified task-resolution rate.
- Regression rate.
- Test pass/fail outcomes.
- Median completion time.
- Token usage and estimated API cost, when available.
- Candidate success rate, where applicable.
- Number of tasks and completed repetitions.
- Benchmark suite, dataset, and version.
- Model/agent and version.
- QEDCode and Benchy versions.
- Reproducibility information and evaluation limitations.

Use repeated runs for stochastic models. Report sample sizes and uncertainty; do not present small samples as definitive evidence.

## 5. Local reports

Every benchmark run should produce a local report, even if community sharing is disabled.

Suggested outputs:

```text
reports/
  <run-id>/
    report.md
    results.json
    results.csv
    metadata.json
    logs/
```

Reports should include the configuration, task outcomes, failures, metrics, and limitations. Keep private source code, patches, credentials, and local paths out of community submissions.

## 6. Community sharing: explicit opt-in only

**No benchmark run means no submission. No explicit sharing consent means no submission.**

Benchy must not:

- Run benchmarks in the background.
- Monitor coding activity.
- Upload reports automatically without consent.
- Send source code, private patches, API keys, or personal files.
- Collect data merely because QEDCode is installed.

Sharing is decided per result (see *Revisions*):

1. `benchy run` generates the local report (always).
2. `benchy share` builds the community record from an allowlist of approved fields, scans it for
   secrets and personal data, validates it, and shows it with a list of what is and is not shared.
   Nothing is written or sent.
3. `benchy share --export` saves the record as `<submission id>.json`.
4. The user may open a pull request adding it to `results/submissions/`. That is the only way a
   result leaves their machine, and it shows their GitHub account (stated in the tool and the docs).

The client contains no tokens or credentials of any kind.

### Privacy fields

Never publish:

- GitHub username or email address.
- Hostname or machine username.
- Local filesystem paths.
- API keys, access tokens, or environment secrets.
- Private repository contents or patches.
- Raw IP addresses.
- Unnecessary identifying metadata.

Potentially publish, where useful and consented to:

- Model/agent name and version.
- QEDCode and Benchy versions.
- Benchmark suite, task identifiers, and task outcomes.
- Runtime, token usage, and estimated cost.
- Generalized hardware/software categories.

No contributor identifier is used. Duplicates are detected by content hash. Do not claim perfect anonymity: combinations of rare hardware, software, and timing details can still be identifying. Minimize and generalize metadata.

## 7. Submission service and GitHub PR creation — deferred

*Not built (see Revisions).* Kept as the design if anonymous submission is ever needed. The record
format and the CI validation already work unchanged behind such a service.

Use a small server-side submission service integrated with a GitHub App.

Responsibilities:

- Receive sanitized result records.
- Validate request size and structure.
- Apply rate limits and abuse controls.
- Create a branch and PR using the project's bot identity.
- Avoid exposing contributor identity in the public PR.
- Return a submission/PR reference to Benchy.

The distributed client must never contain a privileged repository credential.

A GitHub App or server-side service is required for the anonymous, bot-authored PR workflow. A direct PR from a user's own GitHub account would reveal their account identity.

## 8. GitHub Actions: automated PR validation

GitHub Actions is the primary free automation layer for the public repository.

Run workflows when a community submission PR is opened, synchronized, or updated.

### Validation pipeline

1. Check the submission file paths and file sizes.
2. Validate JSON against a versioned JSON Schema.
3. Check required fields and supported schema versions.
4. Check benchmark suite, task IDs, and tool versions.
5. Check that the run is structurally complete.
6. Detect duplicate run IDs and duplicate records.
7. Check numeric values for impossible or invalid ranges.
8. Check for accidental secrets and obvious personal information.
9. Reject unexpected file types and executable content.
10. Produce a clear validation summary.

Validation must treat all PR content as untrusted input.

Implemented in `.github/workflows/validate-submission.yml` + `bot/validate_pr.py`. The validator
comes from the base branch, and the PR is read only through `git show`/`git ls-tree`. With the
`pull_request` trigger the workflow file itself comes from the PR, so human review must confirm
that a submission PR changes only `results/submissions/` (see `docs/contributing.md`).

### Security requirements

- Use least-privilege workflow permissions.
- Do not expose secrets to workflows triggered by untrusted PR code.
- Do not execute scripts, binaries, or arbitrary code supplied by contributors.
- Prefer validating data files without checking out or running contributor-controlled code.
- Pin third-party GitHub Actions to reviewed commit SHAs.
- Separate validation from any privileged publishing workflow.
- Protect the default branch with required checks and review rules.
- Never allow a submission PR to directly modify trusted workflow files without review.

GitHub Actions minutes and usage limits depend on the repository plan and current GitHub policies. Public-repository usage is generally suitable for this workflow, but verify current limits before relying on them.

## 9. Processing accepted results

After validation and the repository's acceptance policy are satisfied:

- Records are already canonical (built by one sanitizer, checked by one validator).
- Merged files in `results/submissions/` are the accepted records. Rejected PRs are never merged.
- `bot/aggregate.py` validates every record again and recalculates aggregates from them.
- Regenerate leaderboard data.
- Update the README statistics.
- Refresh the public dashboard.

Do not let a PR directly overwrite trusted aggregate statistics. Generate aggregates from validated records using project-maintained code.

For the initial release, require human approval before merging. Consider automated merging only after validation, abuse controls, and security policies have been tested thoroughly.

## 10. Public results and transparency

The README and dashboard should show:

- Number of accepted benchmark runs.
- Number of distinct pseudonymous contributors, if measured.
- Baseline versus QEDCode resolution rates.
- Results grouped by model/agent.
- Results grouped by benchmark suite.
- Regression rates and failure rates.
- Sample sizes and last-updated timestamp.
- Methodology, limitations, and links to raw sanitized records.

Clearly label results as:

- **Community-reported / schema-validated**, or
- **Independently reproduced**.

A valid PR and passing schema checks do not prove that a benchmark run genuinely occurred. Do not present community submissions as independently verified unless they have actually been reproduced.

## 11. Repository layout (as built)

```text
QEDCode-benchy/
├── README.md                  status, quick start, community results table (generated)
├── docs/                      methodology.md, privacy.md, contributing.md, this plan
├── benchy/
│   ├── cli.py                 run | report | suites | selftest | share | status
│   ├── suite.py               suites, clean workspaces, fingerprints, validity checks
│   ├── runner/                baseline, qedcode condition, experiment, metered clients, scripted
│   ├── evaluators/            independent hidden-test evaluator
│   ├── reports/               statistics and the local report writer
│   └── submission/            schema.json, sanitizer, validator (shared by client and CI)
├── suites/benchy-core/        8 tasks with hidden tests and reference patches
├── results/submissions/       accepted community records (<submission id>.json)
├── results/reproduced.json    ids a maintainer reproduced
├── leaderboard/leaderboard.json   generated by bot/aggregate.py
├── dashboard/index.html       static page reading the leaderboard
├── bot/                       validate_pr.py, aggregate.py (trusted CI code)
└── .github/                   CODEOWNERS; workflows ci, validate-submission, update-results
```

## 12. Implementation milestones

All seven milestones are implemented. What remains is running them with real models and
publishing the first reproduced results.

### Milestone 1 — Prove the benchmark (done)

- Build one real baseline-versus-QEDCode comparison.
- Use one real task and an independent evaluator.
- Save a local JSON and Markdown report.
- Verify that the only intended experimental difference is QEDCode.

### Milestone 2 — Make results reproducible (done)

- Add a small fixed task suite.
- Add repetitions and failure tracking.
- Record versions, configurations, and resource limits.
- Test report consistency.

### Milestone 3 — Integrate optional Benchy into QEDCode (done, in QEDCode)

- Add optional installation and lifecycle management.
- Add status, run, report, disable, and uninstall commands.
- ~~Add reminders with user controls.~~ Removed (see Revisions).
- Ensure normal QEDCode usage is unchanged.

### Milestone 4 — Add privacy-safe sharing (done; submission service deferred)

- Define the public result schema.
- Implement sanitization and local preview.
- Add explicit sharing consent.
- ~~Build the server-side submission service and GitHub App integration.~~ Deferred.

### Milestone 5 — Automate PR validation (done)

- Add GitHub Actions validation.
- Add duplicate detection and security checks.
- Test malicious and malformed submissions.
- Start with human approval before merging.

### Milestone 6 — Publish community results (done)

- Generate aggregate statistics from accepted records.
- Update README and leaderboard automatically.
- Publish a simple static dashboard.
- Document methodology and limitations.

### Milestone 7 — A standard suite: SWE-bench Verified (done)

- `swebench-verified-py`: SWE-bench Verified instances from sympy, sphinx (up to 7.1), pylint and
  xarray, the repositories that use pytest and rebuild without Docker or compilers. The suite
  ships only the instance data. `benchy suites fetch` (asks first) clones the repositories and
  builds uv environments with SWE-bench's pins.
- Judge `benchy-swebench`: SWE-bench's test patch plus FAIL_TO_PASS / PASS_TO_PASS, with
  per-test outcomes from a small pytest plugin. Test edits are discarded as in
  `benchy-pytest-hidden`.
- Baseline: SWE-bench's BM25 retrieval baseline (about 13k tokens, one unified diff), or
  `--baseline-context oracle` for the strictest comparison. Recorded in shared records; aggregates
  never pool the two.
- `benchy suites check` records which tasks are valid on each computer, and `benchy run` skips
  the others for both conditions. Instances that do not rebuild faithfully on the reference
  machine are excluded with reasons (EXCLUDED.md), never because of a model's result.
- Next: a bigger, harder Benchy-owned suite (40-60 tasks, some JavaScript/TypeScript) that has
  never been public, so training-data leakage cannot inflate results.

---

## 13. Non-negotiable project rules

1. Benchy is optional; QEDCode must work without it.
2. Benchy runs only when the user explicitly launches it.
3. Community sharing requires explicit opt-in.
4. No personal identity or secrets in public submissions.
5. No source-code or private-patch uploads.
6. Baseline and QEDCode conditions must be fairly controlled.
7. Use an independent evaluator.
8. Include failures and incomplete runs.
9. Never fabricate, cherry-pick, or misrepresent results.
10. GitHub Actions validates untrusted data safely.
11. Aggregates are generated from accepted records, not manually edited.
12. Distinguish schema validation from independent reproduction.

## 14. First thing to build

Do not start with the dashboard, reminders, PR bot, or submission service.

First prove that Benchy can run one fair baseline-versus-QEDCode experiment and produce a trustworthy local report. Everything else depends on that foundation.
