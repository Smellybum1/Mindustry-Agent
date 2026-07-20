"""Make the src-layout package importable during tests without an editable
install, so `python -m pytest python/tests -q` works in a bare checkout.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
