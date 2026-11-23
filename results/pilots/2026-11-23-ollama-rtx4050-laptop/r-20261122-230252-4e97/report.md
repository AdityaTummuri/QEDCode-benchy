# Benchy report `r-20261122-230252-4e97`

- **Suite:** bugzoo unversioned (10 tasks, fingerprint `16f7a8116244`)
- **Model:** qwen2.5-coder:7b (ollama)
- **Versions:** Benchy 0.1.0, QEDCode 0.1.0
- **Repetitions:** 3 · **time limit:** 600s per condition · **QEDCode speed:** normal · **order seed:** 0
- **Evaluator:** benchy-pytest-hidden v1 (hidden tests, never shown to either condition)
- **Started:** 2026-11-22T23:02:52+00:00 · **finished:** 2026-11-22T23:16:03+00:00

## Results

| | baseline | qedcode |
|---|---|---|
| Attempts | 30 | 30 |
| Verified resolved | 26 (86.7%) | 26 (86.7%) |
| 95% CI (Wilson) | 70.3% – 94.7% | 70.3% – 94.7% |
| Regressions | 0 (0.0%) | 0 (0.0%) |
| Timeouts / errors | 0 / 0 | 0 / 0 |
| No usable change | 0 | 1 |
| Median time (s) | 4.73 | 17.17 |
| Model calls | 30 | 157 |
| Tokens (est., median / total) | 584.5 / 17220 | 2723.0 / 87071 |
| Est. cost (USD) | – | – |

### Paired comparison (same task, same repetition)

- Pairs: 30 · both resolved: 23 · neither: 1
- Resolved only by qedcode: **3** · only by baseline: **3**
- Difference in resolution rate (qedcode − baseline): **0.0%** · exact McNemar p = 1.0

### QEDCode's own grade vs. the independent evaluator

| QEDCode grade | attempts | verified resolved |
|---|---|---|
| A | 23 | 20 |
| B | 6 | 6 |
| none | 1 | 0 |

## Per task

| task | baseline | qedcode |
|---|---|---|
| 001_paginate_off_by_one | 3/3 | 2/3 |
| 002_discount_threshold | 3/3 | 3/3 |
| 003_mutable_default | 3/3 | 3/3 |
| 004_empty_input_crash | 0/3 | 3/3 |
| 005_integer_average | 3/3 | 3/3 |
| 006_missing_config_key | 3/3 | 3/3 |
| 007_sort_order | 3/3 | 3/3 |
| 008_slugify_feature | 2/3 | 0/3 |
| 009_factorial_zero | 3/3 | 3/3 |
| 010_cart_quantity | 3/3 | 3/3 |

## Every attempt

| task | rep | condition | status | resolved | regression | hidden | seconds | grade |
|---|---|---|---|---|---|---|---|---|
| 001_paginate_off_by_one | 1 | qedcode | done | yes | no | 3/3 | 22.35 | A |
| 001_paginate_off_by_one | 1 | baseline | done | yes | no | 3/3 | 4.4 | – |
| 002_discount_threshold | 1 | qedcode | done | yes | no | 3/3 | 16.75 | A |
| 002_discount_threshold | 1 | baseline | done | yes | no | 3/3 | 9.16 | – |
| 003_mutable_default | 1 | baseline | done | yes | no | 2/2 | 3.66 | – |
| 003_mutable_default | 1 | qedcode | done | yes | no | 2/2 | 25.32 | B |
| 004_empty_input_crash | 1 | qedcode | done | yes | no | 2/2 | 16.2 | A |
| 004_empty_input_crash | 1 | baseline | done | no | no | 0/2 | 4.84 | – |
| 005_integer_average | 1 | baseline | done | yes | no | 2/2 | 3.57 | – |
| 005_integer_average | 1 | qedcode | done | yes | no | 2/2 | 13.89 | A |
| 006_missing_config_key | 1 | qedcode | done | yes | no | 2/2 | 31.32 | A |
| 006_missing_config_key | 1 | baseline | done | yes | no | 2/2 | 4.47 | – |
| 007_sort_order | 1 | baseline | done | yes | no | 2/2 | 7.07 | – |
| 007_sort_order | 1 | qedcode | done | yes | no | 2/2 | 10.72 | B |
| 008_slugify_feature | 1 | qedcode | done | no | no | 2/3 | 15.81 | A |
| 008_slugify_feature | 1 | baseline | done | yes | no | 3/3 | 12.16 | – |
| 009_factorial_zero | 1 | baseline | done | yes | no | 2/2 | 5.1 | – |
| 009_factorial_zero | 1 | qedcode | done | yes | no | 2/2 | 16.98 | B |
| 010_cart_quantity | 1 | qedcode | done | yes | no | 2/2 | 20.6 | A |
| 010_cart_quantity | 1 | baseline | done | yes | no | 2/2 | 11.36 | – |
| 001_paginate_off_by_one | 2 | qedcode | done | yes | no | 3/3 | 16.11 | A |
| 001_paginate_off_by_one | 2 | baseline | done | yes | no | 3/3 | 4.16 | – |
| 002_discount_threshold | 2 | baseline | done | yes | no | 3/3 | 9.08 | – |
| 002_discount_threshold | 2 | qedcode | done | yes | no | 3/3 | 18.55 | A |
| 003_mutable_default | 2 | baseline | done | yes | no | 2/2 | 3.48 | – |
| 003_mutable_default | 2 | qedcode | done | yes | no | 2/2 | 18.87 | A |
| 004_empty_input_crash | 2 | baseline | done | no | no | 0/2 | 4.62 | – |
| 004_empty_input_crash | 2 | qedcode | done | yes | no | 2/2 | 16.08 | A |
| 005_integer_average | 2 | baseline | done | yes | no | 2/2 | 3.38 | – |
| 005_integer_average | 2 | qedcode | done | yes | no | 2/2 | 13.13 | A |
| 006_missing_config_key | 2 | qedcode | done | yes | no | 2/2 | 17.36 | A |
| 006_missing_config_key | 2 | baseline | done | yes | no | 2/2 | 4.25 | – |
| 007_sort_order | 2 | qedcode | done | yes | no | 2/2 | 19.83 | B |
| 007_sort_order | 2 | baseline | done | yes | no | 2/2 | 6.87 | – |
| 008_slugify_feature | 2 | qedcode | done | no | no | 2/3 | 14.48 | A |
| 008_slugify_feature | 2 | baseline | done | yes | no | 3/3 | 11.84 | – |
| 009_factorial_zero | 2 | baseline | done | yes | no | 2/2 | 4.94 | – |
| 009_factorial_zero | 2 | qedcode | done | yes | no | 2/2 | 17.88 | B |
| 010_cart_quantity | 2 | baseline | done | yes | no | 2/2 | 5.5 | – |
| 010_cart_quantity | 2 | qedcode | done | yes | no | 2/2 | 15.58 | A |
| 001_paginate_off_by_one | 3 | qedcode | no_change | no | no | 1/3 | 40.36 | – |
| 001_paginate_off_by_one | 3 | baseline | done | yes | no | 3/3 | 4.21 | – |
| 002_discount_threshold | 3 | qedcode | done | yes | no | 3/3 | 16.21 | A |
| 002_discount_threshold | 3 | baseline | done | yes | no | 3/3 | 9.09 | – |
| 003_mutable_default | 3 | baseline | done | yes | no | 2/2 | 3.5 | – |
| 003_mutable_default | 3 | qedcode | done | yes | no | 2/2 | 21.68 | A |
| 004_empty_input_crash | 3 | qedcode | done | yes | no | 2/2 | 24.15 | A |
| 004_empty_input_crash | 3 | baseline | done | no | no | 0/2 | 4.59 | – |
| 005_integer_average | 3 | qedcode | done | yes | no | 2/2 | 20.49 | A |
| 005_integer_average | 3 | baseline | done | yes | no | 2/2 | 3.36 | – |
| 006_missing_config_key | 3 | qedcode | done | yes | no | 2/2 | 17.77 | A |
| 006_missing_config_key | 3 | baseline | done | yes | no | 2/2 | 4.11 | – |
| 007_sort_order | 3 | qedcode | done | yes | no | 2/2 | 8.61 | B |
| 007_sort_order | 3 | baseline | done | yes | no | 2/2 | 2.76 | – |
| 008_slugify_feature | 3 | baseline | done | no | no | 2/3 | 11.65 | – |
| 008_slugify_feature | 3 | qedcode | done | no | no | 2/3 | 15.46 | A |
| 009_factorial_zero | 3 | qedcode | done | yes | no | 2/2 | 15.93 | A |
| 009_factorial_zero | 3 | baseline | done | yes | no | 2/2 | 4.94 | – |
| 010_cart_quantity | 3 | qedcode | done | yes | no | 2/2 | 21.78 | A |
| 010_cart_quantity | 3 | baseline | done | yes | no | 2/2 | 5.52 | – |

## Limitations

- Token counts are estimates (characters / 3.5), not counts from the model's tokenizer.
- Tasks are small single-file Python problems; results may not carry over to large real-world repositories.
- The baseline is the bare model with one plain prompt and one answer. Other agent harnesses (with their own retries or tools) would be different baselines.
- Times include model latency on this machine and are only comparable within this run.

## Method

Both conditions use the same model client, the same fresh repository snapshot (checked by commit sha), the same time limit and the same evaluator. The evaluator applies only changes to non-test source files to a pristine copy, then runs the original visible tests and the hidden tests. *Resolved* = all hidden tests pass and no previously passing visible test fails. Condition order is shuffled per task and repetition with the seed above. See docs/methodology.md.
