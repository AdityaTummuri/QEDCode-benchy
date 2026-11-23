# SWE-bench Verified pilot, 2026-11-23: qwen3.5:4b on an RTX 4050 laptop

Ten real GitHub issues from `swebench-verified-py` (the planned pilot list), one attempt per side,
900 s per side, no internet. qwen3.5:4b served by Ollama with a 16k context on both sides.

| | Bare model | Through QEDCode |
|---|---|---|
| Resolved (hidden FAIL_TO_PASS tests pass, no regressions) | 0/10 | 2/10 (`pydata__xarray-4629` graded A, `sympy__sympy-14711` graded B) |
| Wrong changes handed back | 0 | 0 (the other 8 ended as "no fix") |

**Read with care.** All ten bare replies were unusable diffs (for example a hunk whose removed and
added lines are identical), so the bare side never produced an applicable change. QEDCode's edit
protocol (exact SEARCH/REPLACE blocks, checked by an applier) and its several tries are why it
got a change through at all; part of this lift is the edit format, not only the checks. Ten tasks
and one repetition say nothing statistically. Both QEDCode results were right: grade honesty 2/2.
