# Benchy report `r-20261122-225052-9a89`

- **Suite:** benchy-core 1.0.0 (8 tasks, fingerprint `0d6751707950`)
- **Model:** qwen2.5-coder:7b (ollama)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 3 · **time limit:** 600s per condition · **QEDCode speed:** normal · **order seed:** 0
- **Evaluator:** benchy-pytest-hidden v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-22T22:50:52+00:00 · **finished:** 2026-11-22T23:02:52+00:00

## Results

| | baseline | qedcode |
|---|---|---|
| Attempts | 24 | 24 |
| Verified resolved | 24 (100.0%) | 23 (95.8%) |
| 95% CI (Wilson) | 86.2% – 100.0% | 79.8% – 99.3% |
| Regressions | 0 (0.0%) | 0 (0.0%) |
| Timeouts / errors | 0 / 0 | 0 / 0 |
| No usable change | 0 | 0 |
| Median time (s) | 8.04 | 21.07 |
| Model calls | 24 | 130 |
| Tokens (est., median / total) | 564.5 / 13554 | 2857.5 / 72255 |
| Est. cost (USD) | – | – |

### Paired comparison (same task, same repetition)

- Pairs: 24 · both resolved: 23 · neither: 0
- Resolved only by qedcode: **0** · only by baseline: **1**
- Difference in resolution rate (qedcode − baseline): **-4.2%** · exact McNemar p = 1.0

### QEDCode's own grade vs. the independent evaluator

| QEDCode grade | attempts | verified resolved |
|---|---|---|
| A | 19 | 19 |
| B | 5 | 4 |

## Per task

| task | baseline | qedcode |
|---|---|---|
| b01_chunk_drops_tail | 3/3 | 3/3 |
| b02_clamp_upper_bound | 3/3 | 3/3 |
| b03_word_counts_case | 3/3 | 3/3 |
| b04_duration_minutes | 3/3 | 3/3 |
| b05_retry_attempts | 3/3 | 2/3 |
| b06_merge_touching_intervals | 3/3 | 3/3 |
| b07_roman_subtractive | 3/3 | 3/3 |
| b08_get_path_non_dict | 3/3 | 3/3 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| b01_chunk_drops_tail | 1 | baseline | done | yes | no | 3/3 | 8.33 | – |
| b01_chunk_drops_tail | 1 | qedcode | done | yes | no | 3/3 | 17.75 | A |
| b02_clamp_upper_bound | 1 | qedcode | done | yes | no | 3/3 | 21.19 | A |
| b02_clamp_upper_bound | 1 | baseline | done | yes | no | 3/3 | 3.25 | – |
| b03_word_counts_case | 1 | qedcode | done | yes | no | 2/2 | 17.19 | A |
| b03_word_counts_case | 1 | baseline | done | yes | no | 2/2 | 7.27 | – |
| b04_duration_minutes | 1 | baseline | done | yes | no | 3/3 | 11.18 | – |
| b04_duration_minutes | 1 | qedcode | done | yes | no | 3/3 | 22.67 | A |
| b05_retry_attempts | 1 | qedcode | done | yes | no | 3/3 | 22.82 | B |
| b05_retry_attempts | 1 | baseline | done | yes | no | 3/3 | 5.03 | – |
| b06_merge_touching_intervals | 1 | qedcode | done | yes | no | 3/3 | 22.71 | A |
| b06_merge_touching_intervals | 1 | baseline | done | yes | no | 3/3 | 8.44 | – |
| b07_roman_subtractive | 1 | baseline | done | yes | no | 3/3 | 8.38 | – |
| b07_roman_subtractive | 1 | qedcode | done | yes | no | 3/3 | 25.24 | A |
| b08_get_path_non_dict | 1 | qedcode | done | yes | no | 3/3 | 18.58 | A |
| b08_get_path_non_dict | 1 | baseline | done | yes | no | 3/3 | 8.25 | – |
| b01_chunk_drops_tail | 2 | qedcode | done | yes | no | 3/3 | 27.55 | A |
| b01_chunk_drops_tail | 2 | baseline | done | yes | no | 3/3 | 3.47 | – |
| b02_clamp_upper_bound | 2 | qedcode | done | yes | no | 3/3 | 18.81 | A |
| b02_clamp_upper_bound | 2 | baseline | done | yes | no | 3/3 | 3.07 | – |
| b03_word_counts_case | 2 | qedcode | done | yes | no | 2/2 | 17.72 | A |
| b03_word_counts_case | 2 | baseline | done | yes | no | 2/2 | 7.08 | – |
| b04_duration_minutes | 2 | qedcode | done | yes | no | 3/3 | 20.95 | A |
| b04_duration_minutes | 2 | baseline | done | yes | no | 3/3 | 11.06 | – |
| b05_retry_attempts | 2 | baseline | done | yes | no | 3/3 | 4.75 | – |
| b05_retry_attempts | 2 | qedcode | done | yes | no | 3/3 | 23.61 | B |
| b06_merge_touching_intervals | 2 | baseline | done | yes | no | 3/3 | 8.45 | – |
| b06_merge_touching_intervals | 2 | qedcode | done | yes | no | 3/3 | 23.86 | A |
| b07_roman_subtractive | 2 | qedcode | done | yes | no | 3/3 | 16.0 | B |
| b07_roman_subtractive | 2 | baseline | done | yes | no | 3/3 | 8.12 | – |
| b08_get_path_non_dict | 2 | baseline | done | yes | no | 3/3 | 8.02 | – |
| b08_get_path_non_dict | 2 | qedcode | done | yes | no | 3/3 | 18.92 | A |
| b01_chunk_drops_tail | 3 | qedcode | done | yes | no | 3/3 | 19.15 | A |
| b01_chunk_drops_tail | 3 | baseline | done | yes | no | 3/3 | 3.45 | – |
| b02_clamp_upper_bound | 3 | qedcode | done | yes | no | 3/3 | 17.18 | A |
| b02_clamp_upper_bound | 3 | baseline | done | yes | no | 3/3 | 3.07 | – |
| b03_word_counts_case | 3 | baseline | done | yes | no | 2/2 | 7.07 | – |
| b03_word_counts_case | 3 | qedcode | done | yes | no | 2/2 | 16.05 | A |
| b04_duration_minutes | 3 | baseline | done | yes | no | 3/3 | 11.1 | – |
| b04_duration_minutes | 3 | qedcode | done | yes | no | 3/3 | 27.16 | A |
| b05_retry_attempts | 3 | qedcode | done | no | no | 0/3 | 23.67 | B |
| b05_retry_attempts | 3 | baseline | done | yes | no | 3/3 | 4.8 | – |
| b06_merge_touching_intervals | 3 | qedcode | done | yes | no | 3/3 | 23.66 | A |
| b06_merge_touching_intervals | 3 | baseline | done | yes | no | 3/3 | 8.16 | – |
| b07_roman_subtractive | 3 | qedcode | done | yes | no | 3/3 | 24.35 | B |
| b07_roman_subtractive | 3 | baseline | done | yes | no | 3/3 | 12.78 | – |
| b08_get_path_non_dict | 3 | qedcode | done | yes | no | 3/3 | 18.59 | A |
| b08_get_path_non_dict | 3 | baseline | done | yes | no | 3/3 | 8.05 | – |

## Limitations

- Small sample (24 paired attempts). Treat differences as indicative only; the confidence intervals and the McNemar p-value show how uncertain they are.
- Token counts are estimates (characters / 3.5), not counts from the model's tokenizer.
- Tasks are small single-file Python problems; results may not carry over to large real-world repositories.
- The baseline is the bare model with one plain prompt and one answer. Other agent harnesses (with their own retries or tools) would be different baselines.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions use the same model client, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to a pristine copy, then runs the original visible tests and the hidden tests. *Resolved* = all hidden tests pass and no previously passing visible test fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
