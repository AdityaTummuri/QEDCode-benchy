# Benchy report `r-20261123-022402-edee`

- **Suite:** swebench-verified-py 1.0.0 (10 tasks, fingerprint `bce7613e19c5`)
- **Model:** qwen3.5:4b (ollama)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 1 · **time limit:** 900s per condition · **QEDCode speed:** normal · **order seed:** 0
- **Evaluator:** benchy-swebench v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-23T02:24:02+00:00 · **finished:** 2026-11-23T02:59:06+00:00

## Results

| | baseline | qedcode |
|---|---|---|
| Attempts | 10 | 10 |
| Verified resolved | 0 (0.0%) | 2 (20.0%) |
| 95% CI (Wilson) | 0.0% – 27.8% | 5.7% – 51.0% |
| Regressions | 0 (0.0%) | 0 (0.0%) |
| Timeouts / errors | 0 / 0 | 0 / 0 |
| No usable change | 8 | 8 |
| Median time (s) | 9.5 | 116.45 |
| Model calls | 10 | 67 |
| Tokens (est., median / total) | 13562.5 / 139667 | 50017.0 / 521592 |
| Est. cost (USD) | – | – |

### Paired comparison (same task, same repetition)

- Pairs: 10 · both resolved: 0 · neither: 8
- Resolved only by qedcode: **2** · only by baseline: **0**
- Difference in resolution rate (qedcode − baseline): **20.0%** · exact McNemar p = 0.5

### QEDCode's own grade vs. the independent evaluator

| QEDCode grade | attempts | verified resolved |
|---|---|---|
| A | 1 | 1 |
| B | 1 | 1 |
| none | 8 | 0 |

## Per task

| task | baseline | qedcode |
|---|---|---|
| sympy__sympy-14711 | 0/1 | 1/1 |
| sympy__sympy-15875 | 0/1 | 0/1 |
| sphinx-doc__sphinx-9230 | 0/1 | 0/1 |
| sphinx-doc__sphinx-9711 | 0/1 | 0/1 |
| pydata__xarray-4629 | 0/1 | 1/1 |
| sympy__sympy-13798 | 0/1 | 0/1 |
| sympy__sympy-18211 | 0/1 | 0/1 |
| sphinx-doc__sphinx-8056 | 0/1 | 0/1 |
| sphinx-doc__sphinx-9673 | 0/1 | 0/1 |
| pylint-dev__pylint-6386 | 0/1 | 0/1 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| sympy__sympy-14711 | 1 | baseline | unparsable | no | no | 0/1 | 13.68 | – |
| sympy__sympy-14711 | 1 | qedcode | done | yes | no | 1/1 | 162.27 | B |
| sympy__sympy-15875 | 1 | qedcode | no_change | no | no | 0/1 | 403.71 | – |
| sympy__sympy-15875 | 1 | baseline | unparsable | no | no | 0/1 | 10.49 | – |
| sphinx-doc__sphinx-9230 | 1 | baseline | unparsable | no | no | 0/1 | 7.94 | – |
| sphinx-doc__sphinx-9230 | 1 | qedcode | no_change | no | no | 0/1 | 67.3 | – |
| sphinx-doc__sphinx-9711 | 1 | qedcode | no_change | no | no | 0/1 | 75.3 | – |
| sphinx-doc__sphinx-9711 | 1 | baseline | unparsable | no | no | 0/1 | 9.15 | – |
| pydata__xarray-4629 | 1 | baseline | unparsable | no | no | 0/1 | 9.05 | – |
| pydata__xarray-4629 | 1 | qedcode | done | yes | no | 1/1 | 67.1 | A |
| sympy__sympy-13798 | 1 | baseline | unparsable | no | no | 0/1 | 9.86 | – |
| sympy__sympy-13798 | 1 | qedcode | no_change | no | no | 0/1 | 346.53 | – |
| sympy__sympy-18211 | 1 | baseline | unparsable | no | no | 0/1 | 10.4 | – |
| sympy__sympy-18211 | 1 | qedcode | no_change | no | no | 0/1 | 452.14 | – |
| sphinx-doc__sphinx-8056 | 1 | baseline | unparsable | no | no | 0/1 | 9.05 | – |
| sphinx-doc__sphinx-8056 | 1 | qedcode | no_change | no | no | 0/1 | 119.67 | – |
| sphinx-doc__sphinx-9673 | 1 | qedcode | no_change | no | no | 0/1 | 113.23 | – |
| sphinx-doc__sphinx-9673 | 1 | baseline | done | no | no | 0/1 | 66.24 | – |
| pylint-dev__pylint-6386 | 1 | baseline | done | no | no | 0/1 | 7.71 | – |
| pylint-dev__pylint-6386 | 1 | qedcode | no_change | no | no | 0/1 | 57.24 | – |

## Limitations

- Small sample (10 paired attempts). Treat differences as indicative only; the confidence intervals and the McNemar p-value show how uncertain they are.
- Token counts are estimates (characters / 3.5), not counts from the model's tokenizer.
- SWE-bench tasks run in environments rebuilt without Docker; results are not comparable with the official SWE-bench leaderboard (a subset of repositories, a retrieval baseline instead of an agent).
- The baseline saw the issue plus retrieved files (bm25-13k-tokens) and answered with one patch. Other harnesses would be different baselines.
- SWE-bench Verified is public, so recent models may have seen these issues and fixes in training.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions use the same model client, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to the base commit, adds SWE-bench's test patch and runs the instance's tests. *Resolved* = every FAIL_TO_PASS test passes and no PASS_TO_PASS test that passed before now fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
