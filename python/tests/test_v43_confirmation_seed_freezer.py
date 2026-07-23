"""Pure tests for the primary-only V43 confirmation freezer."""

import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "freeze-v43-confirmation-seed-set.py"
SPEC = importlib.util.spec_from_file_location(
    "v43_confirmation_seed_freezer", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
FREEZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZER)


def _umbrella():
    return {
        "schema": "m8_confirmation_evaluation_umbrella_v1",
        "candidate_version": "v43",
        "status": "reserved_before_membership_creation",
        "training_config": {
            "path": FREEZER.CONFIG_PATH,
            "sha256": FREEZER.CONFIG_SHA256,
        },
        "access_owner": "primary_agent_only",
        "delegation_forbidden": True,
        "replacement_set": {
            "role": "confirmation",
            "seed_set_id": "bootstrap-defense-v1-dev-v39",
            "seed_set_version": 39,
            "split": "dev",
            "count": 160,
            "path": "configs/evaluation/bootstrap-defense-v1-dev-v39.json",
            "exclusive_namespace": {
                "minimum_inclusive": FREEZER.MIN_ROOT_SEED,
                "maximum_exclusive": FREEZER.MAX_ROOT_SEED_EXCLUSIVE,
            },
            "membership_state_at_reservation": "not_created",
            "exclusive_umbrella_attempt": (
                "runs/m8-selector-v43-dev-v39-umbrella-attempt.json"
            ),
            "replaces": "bootstrap-defense-v1-dev-v38",
        },
        "sealed_final_binding": {
            "seed_set_id": "bootstrap-defense-v1-held-out-v6",
            "seed_set_version": 6,
            "split": "held-out",
            "count": 160,
            "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
            "sha256": FREEZER.HELD_OUT_V6_SHA256,
            "consumption_state": "sealed_unconsumed",
            "membership_read_for_v43_reservation": False,
        },
    }


class V43ConfirmationSeedFreezerTests(unittest.TestCase):
    def test_committed_value_free_inputs_match_pinned_freezer(self):
        umbrella_path = ROOT / FREEZER.UMBRELLA_PATH
        config_path = ROOT / FREEZER.CONFIG_PATH
        umbrella = json.loads(umbrella_path.read_text(encoding="utf-8"))

        self.assertEqual(FREEZER._sha256(umbrella_path), FREEZER.UMBRELLA_SHA256)
        self.assertEqual(FREEZER._sha256(config_path), FREEZER.CONFIG_SHA256)
        reserved = FREEZER._validate_reservation(
            umbrella, FREEZER._sha256(config_path)
        )
        self.assertEqual(
            reserved["path"],
            "configs/evaluation/bootstrap-defense-v1-dev-v39.json",
        )

    def test_exact_reservation_is_required_without_membership_access(self):
        reserved = FREEZER._validate_reservation(
            _umbrella(), FREEZER.CONFIG_SHA256
        )
        self.assertEqual(reserved["seed_set_version"], 39)
        changed = _umbrella()
        changed["replacement_set"]["count"] = 159
        with self.assertRaisesRegex(ValueError, "reservation drifted"):
            FREEZER._validate_reservation(changed, FREEZER.CONFIG_SHA256)

    def test_generation_stays_in_reserved_no_read_namespace(self):
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
                FREEZER.MIN_ROOT_SEED
                <= seed
                < FREEZER.MAX_ROOT_SEED_EXCLUSIVE
                for seed in seeds
            )
        )

    def test_manifest_is_value_bearing_but_receipt_output_is_value_free(self):
        reserved = FREEZER._validate_reservation(
            _umbrella(), FREEZER.CONFIG_SHA256
        )
        manifest = FREEZER._manifest(reserved, [FREEZER.MIN_ROOT_SEED + 1])
        self.assertEqual(manifest["split"], "dev")
        self.assertEqual(manifest["seeds"], [FREEZER.MIN_ROOT_SEED + 1])
        self.assertIn("primary-only", manifest["policy"])

    def test_out_of_range_counts_fail_closed(self):
        for count in (0, FREEZER.ROOT_SEED_SPAN + 1):
            with self.assertRaisesRegex(ValueError, "outside the V43 namespace"):
                FREEZER._generate(count)

    def test_committed_receipt_is_value_free_without_membership_read(self):
        receipt_path = ROOT / FREEZER.RECEIPT_PATH
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(receipt["candidate_version"], "v43")
        self.assertEqual(receipt["status"], "membership_frozen_unconsumed")
        self.assertFalse(receipt["values_emitted"])
        self.assertEqual(receipt["membership_documents_read"], 0)
        self.assertFalse(receipt["generated_membership_read_after_write"])
        self.assertFalse(receipt["retired_confirmation_membership_read"])
        self.assertFalse(receipt["sealed_final_membership_read"])
        self.assertEqual(receipt["set"]["count"], 160)
        self.assertEqual(
            receipt["set"]["sha256"],
            "0b88fda1b37647aa8ee8bb6225ac20a2ebf64d0154195461b5cf0ed804d69bb3",
        )
        self.assertTrue((ROOT / receipt["set"]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
