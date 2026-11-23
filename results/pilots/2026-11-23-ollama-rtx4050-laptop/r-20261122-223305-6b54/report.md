# Benchy report `r-20261122-223305-6b54`

- **Suite:** benchy-core 1.0.0 (8 tasks, fingerprint `0d6751707950`)
- **Model:** qwen3.5:4b (ollama)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 3 · **time limit:** 600s per condition · **QEDCode speed:** normal · **order seed:** 0
- **Evaluator:** benchy-pytest-hidden v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-22T22:33:05+00:00 · **finished:** 2026-11-22T22:41:55+00:00

## Results

| | baseline | qedcode |
|---|---|---|
| Attempts | 24 | 24 |
| Verified resolved | 19 (79.2%) | 22 (91.7%) |
| 95% CI (Wilson) | 59.5% – 90.8% | 74.2% – 97.7% |
| Regressions | 2 (8.3%) | 0 (0.0%) |
| Timeouts / errors | 0 / 0 | 0 / 0 |
| No usable change | 0 | 2 |
| Median time (s) | 2.52 | 13.77 |
| Model calls | 24 | 133 |
| Tokens (est., median / total) | 511.0 / 12327 | 2850.5 / 89459 |
| Est. cost (USD) | – | – |

### Paired comparison (same task, same repetition)

- Pairs: 24 · both resolved: 18 · neither: 1
- Resolved only by qedcode: **4** · only by baseline: **1**
- Difference in resolution rate (qedcode − baseline): **12.5%** · exact McNemar p = 0.375

### QEDCode's own grade vs. the independent evaluator

| QEDCode grade | attempts | verified resolved |
|---|---|---|
| A | 21 | 21 |
| B | 1 | 1 |
| none | 2 | 0 |

## Per task

| task | baseline | qedcode |
|---|---|---|
| b01_chunk_drops_tail | 3/3 | 3/3 |
| b02_clamp_upper_bound | 3/3 | 3/3 |
| b03_word_counts_case | 3/3 | 3/3 |
| b04_duration_minutes | 3/3 | 3/3 |
| b05_retry_attempts | 1/3 | 3/3 |
| b06_merge_touching_intervals | 3/3 | 3/3 |
| b07_roman_subtractive | 3/3 | 2/3 |
| b08_get_path_non_dict | 0/3 | 2/3 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| b01_chunk_drops_tail | 1 | baseline | done | yes | no | 3/3 | 4.66 | – |
| b01_chunk_drops_tail | 1 | qedcode | done | yes | no | 3/3 | 16.22 | A |
| b02_clamp_upper_bound | 1 | qedcode | done | yes | no | 3/3 | 9.39 | A |
| b02_clamp_upper_bound | 1 | baseline | done | yes | no | 3/3 | 1.83 | – |
| b03_word_counts_case | 1 | qedcode | done | yes | no | 2/2 | 11.07 | A |
| b03_word_counts_case | 1 | baseline | done | yes | no | 2/2 | 1.96 | – |
| b04_duration_minutes | 1 | baseline | done | yes | no | 3/3 | 3.66 | – |
| b04_duration_minutes | 1 | qedcode | done | yes | no | 3/3 | 10.84 | A |
| b05_retry_attempts | 1 | qedcode | done | yes | no | 3/3 | 24.17 | B |
| b05_retry_attempts | 1 | baseline | done | no | no | 1/3 | 3.68 | – |
| b06_merge_touching_intervals | 1 | qedcode | done | yes | no | 3/3 | 12.41 | A |
| b06_merge_touching_intervals | 1 | baseline | done | yes | no | 3/3 | 2.29 | – |
| b07_roman_subtractive | 1 | baseline | done | yes | no | 3/3 | 4.7 | – |
| b07_roman_subtractive | 1 | qedcode | done | yes | no | 3/3 | 15.94 | A |
| b08_get_path_non_dict | 1 | qedcode | done | yes | no | 3/3 | 32.61 | A |
| b08_get_path_non_dict | 1 | baseline | done | no | YES | 3/3 | 2.52 | – |
| b01_chunk_drops_tail | 2 | qedcode | done | yes | no | 3/3 | 16.45 | A |
| b01_chunk_drops_tail | 2 | baseline | done | yes | no | 3/3 | 2.13 | – |
| b02_clamp_upper_bound | 2 | qedcode | done | yes | no | 3/3 | 10.59 | A |
| b02_clamp_upper_bound | 2 | baseline | done | yes | no | 3/3 | 1.89 | – |
| b03_word_counts_case | 2 | qedcode | done | yes | no | 2/2 | 11.9 | A |
| b03_word_counts_case | 2 | baseline | done | yes | no | 2/2 | 1.99 | – |
| b04_duration_minutes | 2 | qedcode | done | yes | no | 3/3 | 10.75 | A |
| b04_duration_minutes | 2 | baseline | done | yes | no | 3/3 | 3.67 | – |
| b05_retry_attempts | 2 | baseline | done | yes | no | 3/3 | 3.38 | – |
| b05_retry_attempts | 2 | qedcode | done | yes | no | 3/3 | 33.71 | A |
| b06_merge_touching_intervals | 2 | baseline | done | yes | no | 3/3 | 2.35 | – |
| b06_merge_touching_intervals | 2 | qedcode | done | yes | no | 3/3 | 12.93 | A |
| b07_roman_subtractive | 2 | qedcode | no_change | no | no | 0/3 | 27.56 | – |
| b07_roman_subtractive | 2 | baseline | done | yes | no | 3/3 | 4.76 | – |
| b08_get_path_non_dict | 2 | baseline | done | no | no | 2/3 | 2.89 | – |
| b08_get_path_non_dict | 2 | qedcode | no_change | no | no | 2/3 | 24.33 | – |
| b01_chunk_drops_tail | 3 | qedcode | done | yes | no | 3/3 | 14.74 | A |
| b01_chunk_drops_tail | 3 | baseline | done | yes | no | 3/3 | 1.96 | – |
| b02_clamp_upper_bound | 3 | qedcode | done | yes | no | 3/3 | 9.22 | A |
| b02_clamp_upper_bound | 3 | baseline | done | yes | no | 3/3 | 1.75 | – |
| b03_word_counts_case | 3 | baseline | done | yes | no | 2/2 | 1.87 | – |
| b03_word_counts_case | 3 | qedcode | done | yes | no | 2/2 | 12.16 | A |
| b04_duration_minutes | 3 | baseline | done | yes | no | 3/3 | 3.56 | – |
| b04_duration_minutes | 3 | qedcode | done | yes | no | 3/3 | 10.47 | A |
| b05_retry_attempts | 3 | qedcode | done | yes | no | 3/3 | 38.53 | A |
| b05_retry_attempts | 3 | baseline | done | no | no | 1/3 | 3.14 | – |
| b06_merge_touching_intervals | 3 | qedcode | done | yes | no | 3/3 | 12.19 | A |
| b06_merge_touching_intervals | 3 | baseline | done | yes | no | 3/3 | 2.21 | – |
| b07_roman_subtractive | 3 | qedcode | done | yes | no | 3/3 | 26.56 | A |
| b07_roman_subtractive | 3 | baseline | done | yes | no | 3/3 | 4.61 | – |
| b08_get_path_non_dict | 3 | qedcode | done | yes | no | 3/3 | 14.6 | A |
| b08_get_path_non_dict | 3 | baseline | done | no | YES | 3/3 | 2.52 | – |

## Limitations

- Small sample (24 paired attempts). Treat differences as indicative only; the confidence intervals and the McNemar p-value show how uncertain they are.
- Token counts are estimates (characters / 3.5), not counts from the model's tokenizer.
- Tasks are small single-file Python problems; results may not carry over to large real-world repositories.
- The baseline is the bare model with one plain prompt and one answer. Other agent harnesses (with their own retries or tools) would be different baselines.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions use the same model client, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to a pristine copy, then runs the original visible tests and the hidden tests. *Resolved* = all hidden tests pass and no previously passing visible test fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
