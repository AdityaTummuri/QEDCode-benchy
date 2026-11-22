# Fresh suites: real projects, newly planted bugs

Public benchmarks leak. SWE-bench issues and their upstream fixes are on the web and in training
data: in Benchy's first agent-mode run, Gemini named a SWE-bench task from memory and the agent
searched the web for the fix. A result on such tasks cannot show whether a tool helps or whether
the model remembered.

A fresh suite avoids that. Each task is a **real, well-tested open-source project** with **one new
bug** that Benchy planted, so no model can have seen its fix, while the code around it is ordinary
production code.

## How a task is made (`tools/plant_bugs.py`)

1. **Find candidate bugs.** `plant_bugs.py scan` makes one small edit at a time in the project's
   source (flip a comparison, swap `and`/`or`, drop a `not`, off-by-one on a small integer, `+`
   and `-`, flip a returned bool, drop a one-line guard) and runs the project's own tests. An
   edit is kept only when 1-10 tests that passed before now fail, in at most two test files,
   without collection errors. Which edits are tried depends on a private seed.
2. **Review by hand.** A maintainer drops candidates that are unrealistic (`tuple - tuple`), that
   give the answer away in an error message, or that undo a real past fix (a model may have seen
   that fix). Selection never looks at any model's result.
3. **Write the issue.** Each task gets a bug report in a user's words: a short example, what
   happens, what was expected. The example is run against the bugged code first, so the report
   describes real behaviour. It never names the file or the line.
4. **Build.** `plant_bugs.py build` commits the bug to a local copy of the project with the test
   functions that catch it removed (the rest of every test file stays visible). The removed tests
   become the hidden tests; the reference fix undoes the edit.
5. **Validate.** `benchy suites check` proves, on the user's machine, that the hidden tests fail
   on the bugged code, pass with the reference fix, and that no other test breaks.

Tasks use the SWE-bench task format, so the same evaluator, environments and reports apply, and
the projects need no Docker: Python 3.12 environments built with uv
(`benchy/swebench/specs.py`, `FRESH_SPECS`).

## Why the tasks are not in this repository

The suite holds the answers (reference fixes and hidden tests). Published, it would end up in
training data and stop being fresh. So the tool is public and the tasks are private; results name
the suite version and fingerprint, and the suite is rotated (new seed, new bugs) over time.

## benchy-fresh 1.0.0

34 tasks in boltons (7), pyparsing (7), tomlkit (6), more-itertools (7) and networkx (7), built
2026-11-22 from each project's main branch. All 34 are valid on the reference machine (macOS
arm64).
