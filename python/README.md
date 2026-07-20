# mindustry-agents (Python)

Python side of the `mindustry-coop-agents` project: the PettingZoo `ParallelEnv`
facade, the JVM process supervisor, policies, training, evaluation, and telemetry.

The **core package is installable with zero third-party dependencies** (stdlib
only) so the protocol and env contracts are importable anywhere. Heavier
dependencies live behind extras:

```bash
pip install -e python              # core, zero deps
pip install -e "python[dev]"       # + pytest
pip install -e "python[rl]"        # + pettingzoo, numpy
```

Run tests (works with stdlib `unittest` even if pytest is unavailable):

```bash
python -m pytest python/tests -q        # preferred
python -m unittest discover -s python/tests   # stdlib fallback
```

See `docs/ARCHITECTURE.md` and `docs/PROTOCOL.md`. The env layer must stay
framework-neutral: **no `torch` import** in `env/` or `protocol.py` (ADR-0007).
