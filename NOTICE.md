# NOTICE — Licensing and GPL-3.0 compliance

This repository is a **fork of [Anuken/Mindustry](https://github.com/Anuken/Mindustry)**,
pinned at tag `v159.7` (commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`).

Mindustry is licensed under the **GNU General Public License, version 3.0
(GPL-3.0)**. The full license text is in [`LICENSE`](LICENSE).

## What this means for this project

- All original Mindustry source under `core/`, `server/`, `desktop/`,
  `annotations/`, `tools/`, `tests/`, and related upstream directories remains
  under GPL-3.0, © the Mindustry authors.
- The custom modules added by this project (`rl-server/`, `agent-core/`,
  `agent-plugin/`) link against and are derived from GPL-3.0 engine code. They
  are therefore **also GPL-3.0**. There is no attempt to relicense engine-derived
  code.
- The Python package under `python/` communicates with the engine only over a
  network/IPC protocol (length-prefixed JSON / later Protobuf). It does not link
  the GPL Java code into the same process. Its license will be declared
  explicitly in `python/pyproject.toml`; treat it as GPL-3.0-compatible until a
  deliberate decision states otherwise.

## Source-availability obligation

GPL-3.0 requires that **anyone who receives a distributed binary built from this
modified source is entitled to the corresponding complete source code**,
including our modifications, under the same license.

Practical consequences for this project:

- If you distribute a modified Mindustry binary (e.g. a built `server` or
  `rl-server` jar, or the `agent-plugin`), you must also make the corresponding
  source of **this exact revision** available under GPL-3.0.
- Keep upstream modifications catalogued in
  [`docs/UPSTREAM_PATCHES.md`](docs/UPSTREAM_PATCHES.md) so the delta from
  upstream is auditable.
- Do **not** strip Mindustry copyright headers or the license from redistributed
  artifacts.
- This is a **private, non-commercial research project** by default (see brief
  §4.7). It is not operated as a public-server bot. That does not remove the
  GPL obligations if a binary is ever distributed.

This notice is informational and is not legal advice.
