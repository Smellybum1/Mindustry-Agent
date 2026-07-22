"""Pure tests for the primary-only V39 final freezer."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "freeze-final-seed-set.py"
SPEC = importlib.util.spec_from_file_location("final_seed_freezer", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FREEZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZER)


class FinalSeedFreezerTests(unittest.TestCase):
    def test_generation_uses_third_disjoint_namespace(self):
        with patch.object(FREEZER.secrets, "randbelow", side_effect=[2, 0, 1]):
            self.assertEqual(FREEZER._generate(3), [3_000_000_000, 3_000_000_001, 3_000_000_002])

    def test_encoded_manifest_is_held_out(self):
        reserved = {"seed_set_id": "bootstrap-defense-v1-held-out-v6", "seed_set_version": 6}
        rendered = FREEZER._encoded(reserved, [3_000_000_001]).decode("utf-8")
        self.assertIn('"split": "held-out"', rendered)
        self.assertIn("primary-only", rendered)


if __name__ == "__main__":
    unittest.main()
