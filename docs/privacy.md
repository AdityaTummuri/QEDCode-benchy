# Benchy privacy

## Today (0.1.0)

**Nothing leaves your computer.** Benchy has no network code of its own. The only network traffic
is whatever your chosen model backend does, exactly as when you use QEDCode. Benchy:

- runs only when you type a `benchy` command (no background work, no monitoring);
- writes reports only to your reports folder (default `~/.qedcode/benchy/reports`);
- has no upload, telemetry or sharing feature.

`results.json` and `metadata.json` avoid identifying details even locally. They contain no
hostname, username, home folder or temporary paths, and record only the OS family, CPU architecture
and Python major.minor version. The `logs/` folder holds full model transcripts and test output for
your own debugging, and it is never meant to be shared.

## Later (planned in milestone 4, not built)

Community sharing will be explicit opt-in, previewable and revocable, and will follow the rules in
[the plan](QEDCode_Benchy_Plan.md#6-community-sharing-explicit-opt-in-only). Only approved,
sanitized fields will be sent: no code, patches, secrets, paths or account identity. Self-test runs
(`is_real_measurement: false`) will never be shareable.
