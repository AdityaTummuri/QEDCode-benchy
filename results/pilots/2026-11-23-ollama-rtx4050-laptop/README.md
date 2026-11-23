# Laptop runs, 2026-11-23: Ollama on an RTX 4050 (6 GB)

**Small and easy, so read them as a first look, not a verdict.** Four runs of the same model bare
and through QEDCode, judged by hidden tests: `benchy-core` (8 tasks) and QEDCode's bug zoo
(10 tasks), 3 repetitions each, at normal speed.

Machine: a laptop with an NVIDIA RTX 4050 Laptop GPU (6 GB), Ryzen 7 7840HS, Ubuntu 24.04.
Models served by Ollama. QEDCode 0.1.0 from main (commit 862df76). The two `benchy-core` runs are
also in `results/submissions/`.

| Run | Model | Suite | Bare resolved | QEDCode resolved | Only QEDCode / only bare | McNemar p |
|---|---|---|---|---|---|---|
| `r-20261122-223305-6b54` | qwen3.5:4b | benchy-core | 19/24 (79.2%) | 22/24 (91.7%) | 4 / 1 | 0.375 |
| `r-20261122-224156-138c` | qwen3.5:4b | bug zoo | 28/30 (93.3%) | 26/30 (86.7%) | 1 / 3 | 0.625 |
| `r-20261122-225052-9a89` | qwen2.5-coder:7b | benchy-core | 24/24 (100%) | 23/24 (95.8%) | 0 / 1 | 1.0 |
| `r-20261122-230252-4e97` | qwen2.5-coder:7b | bug zoo | 26/30 (86.7%) | 26/30 (86.7%) | 3 / 3 | 1.0 |

## What they say

1. **No significant difference in how many tasks get solved.** These tasks are easy enough that
   the bare models already solve 79-100% of them; none of the differences is significant.
2. **Grade honesty: 86 of 89 grade A results were right.** The 3 wrong A's are one task,
   `008_slugify_feature`, with qwen2.5-coder:7b: the task says "drop punctuation", the model's own
   test dropped dashes too, and the hidden test keeps them. An under-specified task meets the
   limit of a test written by the same model; the task text was not changed after the fact.
3. **Silent failures: 11 bare, 4 with QEDCode.** A bare model's wrong change always looks done.
   QEDCode's other misses came back as "no fix", not as a wrong change.
4. **A real QEDCode bug, found and fixed.** In a recorded `qed try` run a repair edited the repro
   test (to add a missing import) and the fail-before check reused the old failures, so a test
   that passes on the old code counted as proof. `qed verify` caught it (NOT VERIFIED). Fixed in
   QEDCode commit 5928385.
