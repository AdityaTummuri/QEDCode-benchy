# Benchy report `r-20261122-074643-d32f`

- **Suite:** swebench-verified-py 1.0.0 (1 tasks, fingerprint `bce7613e19c5`)
- **Model:** gemini-3.8-flash-medium (agy) · **mode:** agent (agent alone vs agent + QEDCode)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 1 · **time limit:** 900s per condition · **order seed:** 0
- **Evaluator:** benchy-swebench v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-22T07:46:43+00:00 · **finished:** 2026-11-22T08:14:14+00:00

## Results

| | agent | agent+qedcode |
|---|---|---|
| Attempts | 1 | 1 |
| Verified resolved | 1 (100.0%) | 1 (100.0%) |
| 95% CI (Wilson) | 20.6% – 100.0% | 20.6% – 100.0% |
| Regressions | 0 (0.0%) | 0 (0.0%) |
| Timeouts / errors | 0 / 0 | 1 / 0 |
| No usable change | 0 | 0 |
| Median time (s) | 733.37 | 908.11 |
| Used QEDCode | 0 of 1 | 0 of 1 |
| Said it was fixed | 1 | 0 |
| …but the hidden tests fail | 0 (0.0%) | 0 (–) |

### Paired comparison (same task, same repetition)

- Pairs: 1 · both resolved: 1 · neither: 0
- Resolved only by agent+qedcode: **0** · only by agent: **0**
- Difference in resolution rate (agent+qedcode − agent): **0.0%** · exact McNemar p = 1.0

### QEDCode's own grade vs. the independent evaluator

| QEDCode grade | attempts | verified resolved |
|---|---|---|
| none | 1 | 1 |

## Per task

| task | agent | agent+qedcode |
|---|---|---|
| sympy__sympy-14711 | 1/1 | 1/1 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| sympy__sympy-14711 | 1 | agent | done | yes | no | 1/1 | 733.37 | – |
| sympy__sympy-14711 | 1 | agent+qedcode | timeout | yes | no | 1/1 | 908.11 | – |

## Limitations

- Small sample (1 paired attempts). Treat differences as indicative only; the confidence intervals and the McNemar p-value show how uncertain they are.
- Agent mode: both conditions are the same agent CLI with the same model, prompt, snapshot, time limit and permissions; the QEDCode side also has the QEDCode skill and MCP server. The prompt does not name QEDCode, so the agent chose whether to use it (see 'used QEDCode').
- The agent's model calls run on the user's plan: Benchy cannot count tokens, set a temperature or seed the model, so repeated runs can differ.
- 'Said it was fixed' is read from the agent's final message (it finished normally, changed source code and did not say it failed); it is a heuristic.
- SWE-bench tasks run in environments rebuilt without Docker; results are not comparable with the official SWE-bench leaderboard (a subset of repositories).
- SWE-bench Verified is public, so recent models may have seen these issues and fixes in training.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions run the same agent CLI and model with the same prompt, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to the base commit, adds SWE-bench's test patch and runs the instance's tests. *Resolved* = every FAIL_TO_PASS test passes and no PASS_TO_PASS test that passed before now fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
