# QEDCode Benchy — Project Plan

**Status:** Proposed architecture  
**Core project:** [QEDCode](https://github.com/AdityaTummuri/QEDCode)  
**Companion project:** `qedcode-benchy` (separate repository; create when implementation begins)

---

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

Proposed repository: `qedcode-benchy`

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

During QEDCode setup, offer:

- Install Benchy now.
- Skip for now.
- Don't remind me again.

Normal QEDCode installation and operation must remain unaffected if Benchy is skipped.

If Benchy is not installed, QEDCode may occasionally show a low-frequency reminder, subject to the user's preference. Provide clear controls:

- Remind me later.
- Don't remind me again.

If Benchy is already installed, suppress installation reminders. If the user disables or uninstalls Benchy, stop reminders. The user can reinstall it later.

### Suggested commands

These are proposed command names; confirm compatibility with QEDCode's actual CLI before implementation.

| Command | Purpose |
|---|---|
| `qedcode benchy` | Open Benchy |
| `qedcode benchy run` | Run a benchmark |
| `qedcode benchy report` | View local reports |
| `qedcode benchy share` | Configure community sharing |
| `qedcode benchy status` | Show installation and sharing status |
| `qedcode benchy disable` | Disable Benchy and reminders |
| `qedcode benchy uninstall` | Remove Benchy |
| `qedcode benchy leaderboard` | View community results |

A standalone `qedcode-benchy` executable may also be provided, but it should not be required for normal use.

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

The user should be able to enable or disable community sharing through a clear setting or command. Explain what fields will be shared before the first opt-in. Sharing should be revocable.

When sharing is enabled and the user explicitly runs Benchy:

1. Generate the local report.
2. Build a separate community submission from approved fields.
3. Sanitize the submission.
4. Submit it automatically through the community submission service.
5. Create a PR under the project's bot identity.
6. Show the user whether submission succeeded and provide a reference to the PR or submission.

Do not embed a GitHub personal access token or repository write token in the distributed QEDCode/Benchy client.

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

Use a random pseudonymous contributor identifier only if needed for deduplication or aggregate contributor counts. Do not claim perfect anonymity: combinations of rare hardware, software, and timing details can still be identifying. Minimize and generalize metadata.

## 7. Submission service and GitHub PR creation

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

- Normalize records into a stable format.
- Store sanitized raw submissions.
- Mark records as accepted, rejected, incomplete, or awaiting review.
- Recalculate aggregates from accepted records.
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

## 11. Suggested repository layout

```text
qedcode-benchy/
├── README.md
├── LICENSE
├── docs/
│   ├── methodology.md
│   ├── privacy.md
│   ├── installation.md
│   └── contributing.md
├── schemas/
│   └── result.schema.json
├── benchy/
│   ├── runner/
│   ├── evaluators/
│   ├── reports/
│   └── submission/
├── results/
│   ├── raw/
│   ├── accepted/
│   └── aggregates/
├── leaderboard/
│   └── leaderboard.json
├── dashboard/
├── bot/
│   ├── validator.py
│   ├── sanitizer.py
│   ├── deduplicator.py
│   ├── aggregator.py
│   └── readme_updater.py
└── .github/
    └── workflows/
        ├── validate-submission.yml
        ├── process-results.yml
        └── update-dashboard.yml
```

This is a target structure, not a requirement to create every directory immediately. Keep the first implementation small.

## 12. Implementation milestones

### Milestone 1 — Prove the benchmark

- Build one real baseline-versus-QEDCode comparison.
- Use one real task and an independent evaluator.
- Save a local JSON and Markdown report.
- Verify that the only intended experimental difference is QEDCode.

### Milestone 2 — Make results reproducible

- Add a small fixed task suite.
- Add repetitions and failure tracking.
- Record versions, configurations, and resource limits.
- Test report consistency.

### Milestone 3 — Integrate optional Benchy into QEDCode

- Add optional installation and lifecycle management.
- Add status, run, report, disable, and uninstall commands.
- Add reminders with user controls.
- Ensure normal QEDCode usage is unchanged.

### Milestone 4 — Add privacy-safe sharing

- Define the public result schema.
- Implement sanitization and local preview.
- Add explicit sharing consent.
- Build the server-side submission service and GitHub App integration.

### Milestone 5 — Automate PR validation

- Add GitHub Actions validation.
- Add duplicate detection and security checks.
- Test malicious and malformed submissions.
- Start with human approval before merging.

### Milestone 6 — Publish community results

- Generate aggregate statistics from accepted records.
- Update README and leaderboard automatically.
- Publish a simple static dashboard.
- Document methodology and limitations.

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
