# Benchy privacy

## Nothing is sent by Benchy

Benchy has no network code of its own and no upload, telemetry or background feature. The only
network traffic is whatever your chosen model backend does, exactly as when you use QEDCode.
Benchy runs only when you type a `benchy` (or `qed benchy`) command, and writes only to your
reports folder (default `~/.qedcode/benchy/reports`).

`results.json` and `metadata.json` avoid identifying details even locally. They contain no
hostname, username, home folder or temporary paths, and record only the OS family, CPU architecture
and Python major.minor version. The `logs/` folder holds full model transcripts and test output for
your own debugging, and it is never part of a submission.

## Sharing is something you do yourself

`benchy share` shows the exact record that would be shared, and `benchy share --export` saves it
as a file. Sharing it means opening a pull request yourself, which **shows your GitHub account**.
That is the only way a result leaves your machine.

The record is built from an **allowlist**:

| Shared | Not shared |
|---|---|
| Benchy and QEDCode versions | code, patches, file names |
| the day of the run | time of day, run id |
| suite name, version, fingerprint | model prompts and replies, logs, error messages |
| model backend and name (any local path removed) | hostname, username, paths, IP address |
| repetitions, time limit, QEDCode speed/apply policy, order seed | API keys, environment variables |
| OS family, CPU architecture (x86_64/arm64), Python major.minor | GitHub account (except through your PR) |
| per attempt: task id, outcome, test counts, seconds, model calls, estimated tokens, QEDCode grade | |

Before writing, every field is scanned for anything that looks like a key, token, email address,
IP address or local path. A match refuses the whole submission; nothing is "cleaned up" and
shared anyway. Self-tests and incomplete runs can never be shared.

There is no contributor id, and no attempt to count contributors.

**Not perfect anonymity.** A rare combination (an unusual model name on an uncommon platform on a
given day) can still narrow down who ran something. Preview the record and share only what you are
comfortable with.
