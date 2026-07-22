"""Pure tests for the primary-only V39 confirmation freezer."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "freeze-confirmation-seed-set.py"
SPEC = importlib.util.spec_from_file_location("confirmation_seed_freezer", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FREEZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZER)


def _umbrella():
    return {
        "schema": "m8_confirmation_evaluation_umbrella_v1",
        "candidate_version": "v39",
        "status": "reserved_before_membership_creation",
        "training_config": {
            "path": (
                "configs/training/"
                "m8-selector-v39-partner-intent-duplication-risk.json"
            ),
            "sha256": "config-sha",
        },
        "access_owner": "primary_agent_only",
        "delegation_forbidden": True,
        "replacement_set": {
            "role": "confirmation",
            "seed_set_id": "bootstrap-defense-v1-dev-v35",
            "seed_set_version": 35,
            "split": "dev",
            "count": 160,
            "path": "configs/evaluation/bootstrap-defense-v1-dev-v35.json",
            "membership_state_at_reservation": "not_created",
            "exclusive_umbrella_attempt": (
                "runs/m8-selector-v39-dev-v35-umbrella-attempt.json"
            ),
            "replaces": "bootstrap-defense-v1-dev-v34",
        },
        "sealed_final_binding": {
            "seed_set_id": "bootstrap-defense-v1-held-out-v5",
            "seed_set_version": 5,
            "split": "held-out",
            "count": 160,
            "path": "configs/evaluation/bootstrap-defense-v1-held-out-v5.json",
            "sha256": (
                "1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910"
            ),
            "consumption_state": "sealed_unconsumed",
            "membership_read_for_v39_reservation": False,
        },
    }


class ConfirmationSeedFreezerTests(unittest.TestCase):
    def test_exact_reservation_is_required(self):
        reserved = FREEZER._validate_reservation(_umbrella(), "config-sha")
        self.assertEqual(reserved["seed_set_version"], 35)
        changed = _umbrella()
        changed["replacement_set"]["count"] = 159
        with self.assertRaisesRegex(ValueError, "reservation drifted"):
            FREEZER._validate_reservation(changed, "config-sha")

    def test_generation_stays_in_disjoint_signed_int_namespace(self):
        with patch.object(FREEZER.secrets, "randbelow", side_effect=[2, 0, 2, 1]):
            seeds = FREEZER._generate(3)
        self.assertEqual(
            seeds,
            [
                FREEZER.MIN_ROOT_SEED,
                FREEZER.MIN_ROOT_SEED + 1,
                FREEZER.MIN_ROOT_SEED + 2,
            ],
        )
        self.assertTrue(
            all(
                2_000_000_000 <= seed <= 2_147_483_647
                for seed in seeds
            )
        )

    def test_manifest_is_value_bearing_but_never_rendered_by_freezer(self):
        reserved = FREEZER._validate_reservation(_umbrella(), "config-sha")
        manifest = FREEZER._manifest(reserved, [2_000_000_001])
        self.assertEqual(manifest["split"], "dev")
        self.assertEqual(manifest["seeds"], [2_000_000_001])
        self.assertIn("primary-only", manifest["policy"])


if __name__ == "__main__":
    unittest.main()
