# Agent-mode pilot, 2026-11-22: Antigravity + Gemini 3.8 Flash (medium)

**Not a measurement.** These are the first real agent-mode runs (`benchy run --model
agy:gemini-3.8-flash-medium`, agent alone vs agent + QEDCode, SWE-bench Verified), kept because
they found real problems. One task finished as a pair; nothing here says whether QEDCode helps.

Machine: macOS arm64. `agy` 1.5.13. QEDCode 0.1.0 working tree (before the `qed check` fix
below for the first run). Local paths in the logs are replaced with `<tmp>/` and `~`.

| Run | What happened |
|---|---|
| `r-20261122-074643-d32f` | First end-to-end test, `sympy__sympy-14711`, 900 s per side, web access **allowed**. Both sides resolved the issue (hidden tests pass). Agent alone: 733 s. Agent + QEDCode: hit the 900 s limit with no receipt, because `qed check` waited 300 s for sympy's full suite (fixed in QEDCode, see below); its change still passed the hidden tests. Logs are plain text (stream-json logging came later). |
| `r-20261122-083622-3f9a` | The 10-task pilot, web access still allowed. The first attempt (agent alone) resolved the task in 738 s but ran **8 web searches** first, so the run was stopped and web access blocked for both sides. `agent_stream.jsonl` is the full event log (tools, timings, tokens). |
| `r-20261122-085515-637a` | The pilot restarted with no internet. The first attempt ran about 14 minutes, then Antigravity returned `RESOURCE_EXHAUSTED (code 429): Individual quota reached ... Resets in 166h37m`. Benchy stopped, dropped the unfinished pair and wrote this report (0 attempts); the partial event log is kept. |

## What it found

1. **Web search.** On public SWE-bench issues the agent looks the fix up online. Agent mode now
   blocks web and browser tools on both sides with a `PreToolUse` hook, and denies URL reads and
   network commands (see `docs/methodology.md#agent-mode`).
2. **`qed check` on big repositories.** It ignored the speed's full-suite limit and waited the
   project's 300 s test timeout: 306 s per check on sympy, now 126 s at normal speed and 6 s at
   fast (same grade), and a project now remembers a too-slow suite. Fixed in QEDCode.
3. **Quota.** Each attempt used about 190-230k fresh tokens plus about 3M cache-read tokens
   (`agent_stream.jsonl`). About 5-6 attempts in one day used up this account's quota, which then
   reset after about 7 days. A 20-attempt pilot does not fit in one such account's week.

## Planned pilot

Ten tasks picked by a fixed rule (valid on the reference machine, no PASS_TO_PASS drift,
validation under 120 s; per SWE-bench difficulty "<15 min fix" and "15 min - 1 hour", the first by
SHA-256 of the instance id within each repository), not by any model's result:

```bash
benchy run --model agy:gemini-3.8-flash-medium --suite swebench-verified-py --time-limit 900 \
  --tasks sympy__sympy-14711,sympy__sympy-15875,sphinx-doc__sphinx-9230,sphinx-doc__sphinx-9711,pydata__xarray-4629,sympy__sympy-13798,sympy__sympy-18211,sphinx-doc__sphinx-8056,sphinx-doc__sphinx-9673,pylint-dev__pylint-6386
```
