# ADR-0009: Reference training runtime is Linux/WSL2

**Status:** Accepted

## Context

Development happens on Windows 11 (Git Bash + PowerShell), but large-scale
training will run on Linux. Tooling that only works on Windows would fracture the
project and make training non-reproducible.

## Decision

The **reference training runtime is Linux/WSL2**. **Windows Git Bash is
supported for development.** Nothing may depend on Windows-only tooling. All
command entry points are `scripts/*.sh` that run identically in Git Bash and
Linux/WSL2; the Makefile only delegates to them.

## Alternatives considered

- **Windows-native scripts (PowerShell/`.bat`) as primary**: rejected — not the
  training runtime; would need a parallel Linux path anyway.
- **Linux-only, no Windows dev support**: rejected — the developer machine is
  Windows; blocking local dev is costly.

## Consequences

- One set of shell entry points for both platforms.
- Contributors must avoid Windows-only assumptions (paths, line endings, tools).
- `make` may be absent on Windows; scripts are runnable directly via `bash`.

## Reversal conditions

None expected. If training moves to another OS, update this ADR and re-verify the
scripts there.
