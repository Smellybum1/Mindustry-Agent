#!/usr/bin/env bash
# Resolve the portable Python command used by project entry scripts. Windows
# commonly exposes `python`; stock Ubuntu commonly exposes only `python3`.

if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
else
  python_path="$(command -v python 2>/dev/null || true)"
  python3_path="$(command -v python3 2>/dev/null || true)"
  if [[ -n "$python_path" && ! -d "$python_path" ]]; then
    PY="python"
  elif [[ -n "$python3_path" && ! -d "$python3_path" ]]; then
    PY="python3"
  else
    # Preserve the existing command-not-found diagnostics in callers.
    PY="python"
  fi
  unset python_path python3_path
fi
