# Benchy report `r-20261122-083622-3f9a`

- **Suite:** swebench-verified-py 1.0.0 (10 tasks, fingerprint `bce7613e19c5`)
- **Model:** gemini-3.8-flash-medium (agy) · **mode:** agent (agent alone vs agent + QEDCode)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 1 · **time limit:** 900s per condition · **order seed:** 0
- **Evaluator:** benchy-swebench v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-22T08:36:22+00:00 · **finished:** 2026-11-22T08:53:58+00:00 · **INCOMPLETE**

## Results

| | agent | agent+qedcode |
|---|---|---|
| Attempts | 1 | 0 |
| Verified resolved | 1 (100.0%) | 0 (–) |
| 95% CI (Wilson) | 20.6% – 100.0% | 0.0% – 100.0% |
| Regressions | 0 (0.0%) | 0 (–) |
| Timeouts / errors | 0 / 0 | 0 / 0 |
| No usable change | 0 | 0 |
| Median time (s) | 738.34 | – |
| Agent turns | 1 | 0 |
| Tokens (median / total) | 213915 / 213915 | – / 0 |
| Used QEDCode | 0 of 1 | 0 of 0 |
| Said it was fixed | 1 | 0 |
| …but the hidden tests fail | 0 (0.0%) | 0 (–) |

## Per task

| task | agent | agent+qedcode |
|---|---|---|
| sympy__sympy-14711 | 1/1 | 0/0 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| sympy__sympy-14711 | 1 | agent | done | yes | no | 1/1 | 738.34 | – |

## Limitations

- The run was stopped early; only finished attempts are included.
- Why it stopped: stopped by you.
- Agent mode: both conditions are the same agent CLI with the same model, prompt, snapshot, time limit and permissions; the QEDCode side also has the QEDCode skill and MCP server. The prompt does not name QEDCode, so the agent chose whether to use it (see 'used QEDCode').
- The agent's model calls run on the user's plan. Turns and tokens are the agent CLI's own counts; Benchy cannot set a temperature or seed, so repeated runs can differ.
- 'Said it was fixed' is read from the agent's final message (it finished normally, changed source code and did not say it failed); it is a heuristic.
- SWE-bench tasks run in environments rebuilt without Docker; results are not comparable with the official SWE-bench leaderboard (a subset of repositories).
- SWE-bench Verified is public, so recent models may have seen these issues and fixes in training.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions run the same agent CLI and model with the same prompt, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to the base commit, adds SWE-bench's test patch and runs the instance's tests. *Resolved* = every FAIL_TO_PASS test passes and no PASS_TO_PASS test that passed before now fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
