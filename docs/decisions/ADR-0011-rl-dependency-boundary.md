# ADR-0011: RL dependencies are training-only and Linux CPU locked

**Status:** Accepted

## Context

The framework-neutral environment is intentionally usable with the Python
standard library alone (ADR-0007), while M8 needs a reproducible PyTorch
training runtime. Development and demos remain supported on Windows, but the
reference training runtime is Linux/WSL2 (ADR-0009). An unconstrained extra or
a platform-ambiguous PyTorch install would make run manifests irreproducible
and could silently select CUDA packages on a CPU machine.

## Decision

The project keeps `python/pyproject.toml` core `dependencies = []` and pins the
M8 RL extra exactly to:

- NumPy `2.4.2`;
- PettingZoo `1.26.1`;
- PyTorch `2.12.1`, resolved only from
  `https://download.pytorch.org/whl/cpu` by the checked-in uv source rule.

NumPy 2.4.2 is the newest selected line that retains Python 3.11 support, so
installing the optional extra does not contradict the package's `>=3.11`
metadata. The certified training target is CPython 3.12 on x86-64 Ubuntu
24.04/WSL2. The exact transitive Linux CPU environment, including artifact
hashes, is `python/requirements-rl-linux-py312.lock`; it is generated with uv
0.11.16 from the optional extra. Training manifests record the exact Python
patch version, OS/kernel, device, uv version, and lockfile SHA-256.

Imports of `torch`, `numpy`, or `pettingzoo` are permitted only beneath
`mindustry_agents.training`. The environment, protocol, process, evaluation,
scripted policies, telemetry, and tools remain framework-neutral. Training
adapters consume their ordinary Python lists, numbers, masks, and structured
events; they do not change protocol or simulation behavior.

`scripts/verify-rl-boundary.sh` is the reproducible acceptance command. It
first runs the import, protocol, environment, and process-supervisor tests using
`python -S` (no site packages), then creates a temporary uv environment from
the lock, verifies the three direct versions and CPU-only PyTorch, and imports
the framework-neutral modules. The ordinary test command still runs the full
suite. Neither command makes a machine-global installation.

CUDA, another Python minor version, another architecture, or native Windows
training requires a separately named lock and an ADR update. Windows remains
the development/demo runtime and is not certified by this Linux lock.

## Alternatives considered

- **Put PyTorch in core dependencies:** rejected because it violates ADR-0007
  and makes protocol/process tests depend on a large framework.
- **Use lower bounds in the RL extra:** rejected because repeated installs can
  resolve different trainers and transitive packages.
- **Use the default PyPI PyTorch resolution:** rejected because the Linux
  artifact set is not an explicit CPU-only training target.
- **Pin NumPy 2.5.x:** rejected for this boundary because that line requires
  Python 3.12 and would make the declared Python 3.11 optional-extra behavior
  misleading.
- **Certify native Windows and WSL2 from one lock:** rejected because wheels and
  runtime behavior are platform-specific.

## Consequences

- Core imports and tests stay light, deterministic, and third-party-free.
- A WSL2 training environment can be reconstructed from an exact hashed lock.
- RL upgrades require deliberate edits, lock regeneration, and boundary
  re-verification.
- CPU training is reproducible now; GPU throughput work remains a later,
  explicit platform lock rather than an accidental resolver choice.

## Reversal conditions

Supersede this ADR if the training framework changes or a supported training
platform cannot consume the framework-neutral boundary. Do not weaken the core
zero-dependency rule; add a thin training adapter or a separate lock instead.
