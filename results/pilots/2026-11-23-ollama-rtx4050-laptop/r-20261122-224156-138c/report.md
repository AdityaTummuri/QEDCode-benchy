# Benchy report `r-20261122-224156-138c`

- **Suite:** bugzoo unversioned (10 tasks, fingerprint `16f7a8116244`)
- **Model:** qwen3.5:4b (ollama)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 3 · **time limit:** 600s per condition · **QEDCode speed:** normal · **order seed:** 0
- **Evaluator:** benchy-pytest-hidden v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-22T22:41:56+00:00 · **finished:** 2026-11-22T22:50:51+00:00

## Results

| | baseline | qedcode |
|---|---|---|
| Attempts | 30 | 30 |
| Verified resolved | 28 (93.3%) | 26 (86.7%) |
| 95% CI (Wilson) | 78.7% – 98.2% | 70.3% – 94.7% |
| Regressions | 0 (0.0%) | 0 (0.0%) |
| Timeouts / errors | 0 / 0 | 0 / 0 |
| No usable change | 0 | 4 |
| Median time (s) | 2.74 | 11.48 |
| Model calls | 30 | 163 |
| Tokens (est., median / total) | 575.0 / 17035 | 2852.5 / 101172 |
| Est. cost (USD) | – | – |

### Paired comparison (same task, same repetition)

- Pairs: 30 · both resolved: 25 · neither: 1
- Resolved only by qedcode: **1** · only by baseline: **3**
- Difference in resolution rate (qedcode − baseline): **-6.7%** · exact McNemar p = 0.625

### QEDCode's own grade vs. the independent evaluator

| QEDCode grade | attempts | verified resolved |
|---|---|---|
| A | 26 | 26 |
| none | 4 | 0 |

## Per task

| task | baseline | qedcode |
|---|---|---|
| 001_paginate_off_by_one | 3/3 | 2/3 |
| 002_discount_threshold | 3/3 | 3/3 |
| 003_mutable_default | 3/3 | 3/3 |
| 004_empty_input_crash | 3/3 | 3/3 |
| 005_integer_average | 3/3 | 3/3 |
| 006_missing_config_key | 3/3 | 2/3 |
| 007_sort_order | 3/3 | 3/3 |
| 008_slugify_feature | 1/3 | 1/3 |
| 009_factorial_zero | 3/3 | 3/3 |
| 010_cart_quantity | 3/3 | 3/3 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| 001_paginate_off_by_one | 1 | qedcode | done | yes | no | 3/3 | 15.46 | A |
| 001_paginate_off_by_one | 1 | baseline | done | yes | no | 3/3 | 2.44 | – |
| 002_discount_threshold | 1 | qedcode | done | yes | no | 3/3 | 11.68 | A |
| 002_discount_threshold | 1 | baseline | done | yes | no | 3/3 | 2.37 | – |
| 003_mutable_default | 1 | baseline | done | yes | no | 2/2 | 2.05 | – |
| 003_mutable_default | 1 | qedcode | done | yes | no | 2/2 | 12.2 | A |
| 004_empty_input_crash | 1 | qedcode | done | yes | no | 2/2 | 11.64 | A |
| 004_empty_input_crash | 1 | baseline | done | yes | no | 2/2 | 2.92 | – |
| 005_integer_average | 1 | baseline | done | yes | no | 2/2 | 4.46 | – |
| 005_integer_average | 1 | qedcode | done | yes | no | 2/2 | 9.09 | A |
| 006_missing_config_key | 1 | qedcode | no_change | no | no | 1/2 | 26.29 | – |
| 006_missing_config_key | 1 | baseline | done | yes | no | 2/2 | 2.6 | – |
| 007_sort_order | 1 | baseline | done | yes | no | 2/2 | 1.66 | – |
| 007_sort_order | 1 | qedcode | done | yes | no | 2/2 | 9.32 | A |
| 008_slugify_feature | 1 | qedcode | no_change | no | no | 0/1 | 19.31 | – |
| 008_slugify_feature | 1 | baseline | done | no | no | 2/3 | 6.93 | – |
| 009_factorial_zero | 1 | baseline | done | yes | no | 2/2 | 2.82 | – |
| 009_factorial_zero | 1 | qedcode | done | yes | no | 2/2 | 9.21 | A |
| 010_cart_quantity | 1 | qedcode | done | yes | no | 2/2 | 11.1 | A |
| 010_cart_quantity | 1 | baseline | done | yes | no | 2/2 | 3.39 | – |
| 001_paginate_off_by_one | 2 | qedcode | no_change | no | no | 1/3 | 18.44 | – |
| 001_paginate_off_by_one | 2 | baseline | done | yes | no | 3/3 | 2.35 | – |
| 002_discount_threshold | 2 | baseline | done | yes | no | 3/3 | 2.25 | – |
| 002_discount_threshold | 2 | qedcode | done | yes | no | 3/3 | 11.41 | A |
| 003_mutable_default | 2 | baseline | done | yes | no | 2/2 | 2.02 | – |
| 003_mutable_default | 2 | qedcode | done | yes | no | 2/2 | 27.02 | A |
| 004_empty_input_crash | 2 | baseline | done | yes | no | 2/2 | 2.85 | – |
| 004_empty_input_crash | 2 | qedcode | done | yes | no | 2/2 | 10.92 | A |
| 005_integer_average | 2 | baseline | done | yes | no | 2/2 | 4.48 | – |
| 005_integer_average | 2 | qedcode | done | yes | no | 2/2 | 9.17 | A |
| 006_missing_config_key | 2 | qedcode | done | yes | no | 2/2 | 11.46 | A |
| 006_missing_config_key | 2 | baseline | done | yes | no | 2/2 | 2.66 | – |
| 007_sort_order | 2 | qedcode | done | yes | no | 2/2 | 11.67 | A |
| 007_sort_order | 2 | baseline | done | yes | no | 2/2 | 1.69 | – |
| 008_slugify_feature | 2 | qedcode | no_change | no | no | 0/1 | 14.66 | – |
| 008_slugify_feature | 2 | baseline | done | yes | no | 3/3 | 7.11 | – |
| 009_factorial_zero | 2 | baseline | done | yes | no | 2/2 | 2.84 | – |
| 009_factorial_zero | 2 | qedcode | done | yes | no | 2/2 | 9.51 | A |
| 010_cart_quantity | 2 | baseline | done | yes | no | 2/2 | 3.13 | – |
| 010_cart_quantity | 2 | qedcode | done | yes | no | 2/2 | 11.18 | A |
| 001_paginate_off_by_one | 3 | qedcode | done | yes | no | 3/3 | 14.23 | A |
| 001_paginate_off_by_one | 3 | baseline | done | yes | no | 3/3 | 2.49 | – |
| 002_discount_threshold | 3 | qedcode | done | yes | no | 3/3 | 11.49 | A |
| 002_discount_threshold | 3 | baseline | done | yes | no | 3/3 | 2.39 | – |
| 003_mutable_default | 3 | baseline | done | yes | no | 2/2 | 2.06 | – |
| 003_mutable_default | 3 | qedcode | done | yes | no | 2/2 | 12.73 | A |
| 004_empty_input_crash | 3 | qedcode | done | yes | no | 2/2 | 11.63 | A |
| 004_empty_input_crash | 3 | baseline | done | yes | no | 2/2 | 2.94 | – |
| 005_integer_average | 3 | qedcode | done | yes | no | 2/2 | 9.01 | A |
| 005_integer_average | 3 | baseline | done | yes | no | 2/2 | 4.53 | – |
| 006_missing_config_key | 3 | qedcode | done | yes | no | 2/2 | 10.67 | A |
| 006_missing_config_key | 3 | baseline | done | yes | no | 2/2 | 2.58 | – |
| 007_sort_order | 3 | qedcode | done | yes | no | 2/2 | 11.36 | A |
| 007_sort_order | 3 | baseline | done | yes | no | 2/2 | 1.69 | – |
| 008_slugify_feature | 3 | baseline | done | no | no | 2/3 | 7.65 | – |
| 008_slugify_feature | 3 | qedcode | done | yes | no | 3/3 | 14.16 | A |
| 009_factorial_zero | 3 | qedcode | done | yes | no | 2/2 | 9.6 | A |
| 009_factorial_zero | 3 | baseline | done | yes | no | 2/2 | 2.84 | – |
| 010_cart_quantity | 3 | qedcode | done | yes | no | 2/2 | 11.29 | A |
| 010_cart_quantity | 3 | baseline | done | yes | no | 2/2 | 3.28 | – |

## Limitations

- Token counts are estimates (characters / 3.5), not counts from the model's tokenizer.
- Tasks are small single-file Python problems; results may not carry over to large real-world repositories.
- The baseline is the bare model with one plain prompt and one answer. Other agent harnesses (with their own retries or tools) would be different baselines.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions use the same model client, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to a pristine copy, then runs the original visible tests and the hidden tests. *Resolved* = all hidden tests pass and no previously passing visible test fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
