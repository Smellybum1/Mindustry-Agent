"""Pure tests for the primary-only V45 confirmation freezer."""

import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/freeze-v45-confirmation-seed-set.py"
SPEC = importlib.util.spec_from_file_location("v45_confirmation_seed_freezer", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FREEZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZER)


class V45ConfirmationSeedFreezerTests(unittest.TestCase):
    def test_committed_inputs_match_pinned_freezer(self):
        umbrella_path = ROOT / FREEZER.UMBRELLA_PATH
        config_path = ROOT / FREEZER.CONFIG_PATH
        umbrella = json.loads(umbrella_path.read_text(encoding="utf-8"))
        self.assertEqual(FREEZER._sha256(umbrella_path), FREEZER.UMBRELLA_SHA256)
        self.assertEqual(FREEZER._sha256(config_path), FREEZER.CONFIG_SHA256)
        reserved = FREEZER._validate_reservation(
            umbrella, FREEZER._sha256(config_path)
        )
        self.assertEqual(reserved["seed_set_version"], 41)

    def test_generation_stays_in_reserved_namespace(self):
        with patch.object(FREEZER.BASE.secrets, "randbelow", side_effect=[2, 0, 2, 1]):
            seeds = FREEZER._generate(3)
        self.assertEqual(
            seeds,
            [FREEZER.MIN_ROOT_SEED, FREEZER.MIN_ROOT_SEED + 1, FREEZER.MIN_ROOT_SEED + 2],
        )

    def test_receipt_is_value_free(self):
        umbrella = json.loads(
            (ROOT / FREEZER.UMBRELLA_PATH).read_text(encoding="utf-8")
        )
        reserved = FREEZER._validate_reservation(umbrella, FREEZER.CONFIG_SHA256)
        receipt = FREEZER._receipt(
            ROOT,
            ROOT / FREEZER.UMBRELLA_PATH,
            "umbrella",
            "script",
            "helper",
            reserved,
            "membership",
        )
        self.assertFalse(receipt["values_emitted"])
        self.assertEqual(receipt["membership_documents_read"], 0)
        self.assertFalse(receipt["generated_membership_read_after_write"])
        self.assertFalse(receipt["retired_confirmation_membership_read"])
        self.assertFalse(receipt["sealed_final_membership_read"])
        self.assertNotIn("seeds", receipt)
        self.assertEqual(
            receipt["namespace_proof"]["v45_confirmation_min_inclusive"],
            9_000_000_000,
        )

    def test_out_of_range_counts_fail_closed(self):
        for count in (0, FREEZER.ROOT_SEED_SPAN + 1):
            with self.assertRaisesRegex(ValueError, "outside the V45 namespace"):
                FREEZER._generate(count)

    def test_committed_receipt_is_value_free_without_membership_read(self):
        receipt_path = ROOT / FREEZER.RECEIPT_PATH
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(receipt["candidate_version"], "v45")
        self.assertEqual(receipt["status"], "membership_frozen_unconsumed")
        self.assertFalse(receipt["values_emitted"])
        self.assertEqual(receipt["membership_documents_read"], 0)
        self.assertFalse(receipt["generated_membership_read_after_write"])
        self.assertFalse(receipt["retired_confirmation_membership_read"])
        self.assertFalse(receipt["sealed_final_membership_read"])
        self.assertEqual(receipt["set"]["count"], 160)
        self.assertEqual(
            receipt["set"]["sha256"],
            "591513526bdd0bceb38d9ca63b525be8d4db665567d166b7f1a4e8a247347192",
        )
        self.assertTrue((ROOT / receipt["set"]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
