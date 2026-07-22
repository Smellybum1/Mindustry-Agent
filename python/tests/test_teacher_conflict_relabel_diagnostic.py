"""Pure tests for the V42 production-path conflict-relabel diagnostic."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mindustry_agents.training import teacher_conflict_relabel_diagnostic as diagnostic


def _transition(
    *, conflict: bool, status: str, original: int = 0, effective: int | None = 1,
    eligible: bool = True,
):
    return SimpleNamespace(
        policy_loss_mask=eligible,
        teacher_action=original,
        teacher_effective_action=effective,
        teacher_partner_intent_risk_conflict=conflict,
        teacher_partner_intent_relabel_status=status,
        action_mask=[True] * 8,
    )


def _row(
    *, tick: int, conflict: bool, status: str, original: int = 0,
    effective: int | None = 1, task_type: str = "BUILD_SCHEMATIC",
):
    task_action = {"type": "SELECT", "task_id": "task:original"}
    return {
        "tick": tick,
        "action_index": original,
        "teacher_action_index": original,
        "action": task_action,
        "teacher_action": copy.deepcopy(task_action),
        "agent_actions": [
            {"agent_id": 0, "task_action": copy.deepcopy(task_action)},
            {"agent_id": 1, "task_action": {"type": "WAIT"}},
            {"agent_id": 2, "task_action": {"type": "WAIT"}},
        ],
        "state_hash": f"state-{tick}",
        "teacher_effective_action_index": effective,
        "teacher_alternate_action_index": (
            effective if status == "relabeled_nonconflict" else None
        ),
        "teacher_original_partner_intent_risk_conflict": conflict,
        "teacher_conflict_relabel_status": status,
        "partner_intent_duplication_risk_candidate_indices": (
            [original] if conflict else []
        ),
        "teacher_candidate_diagnostics": {"task_type": task_type},
    }


def _episodes():
    return [
        SimpleNamespace(
            seed=1,
            outcome="win",
            transitions=[
                _transition(conflict=True, status="relabeled_nonconflict"),
                _transition(
                    conflict=False, status="original_nonconflict", original=2,
                    effective=2,
                ),
            ],
            trace=[
                _row(tick=0, conflict=True, status="relabeled_nonconflict"),
                _row(
                    tick=10, conflict=False, status="original_nonconflict",
                    original=2, effective=2, task_type="HARVEST_RESOURCE",
                ),
            ],
        ),
        SimpleNamespace(
            seed=2,
            outcome="loss",
            transitions=[
                _transition(
                    conflict=True, status="fallback_excluded", effective=None
                )
            ],
            trace=[
                _row(
                    tick=20, conflict=True, status="fallback_excluded",
                    effective=None, task_type="SUPPLY_TURRET",
                )
            ],
        ),
    ]


def _config():
    return {
        "candidate_version": "v42",
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
    }


class TeacherConflictRelabelDiagnosticTests(unittest.TestCase):
    def test_report_validates_and_summarizes_production_fields_deterministically(self):
        kwargs = {
            "source_bindings": {"v42_config": {"path": "config", "sha256": "a"}},
            "config": _config(),
            "tool_inputs": {"java": "java", "jvm_args": ["-Xbatch"], "port": 1},
        }
        report = diagnostic.build_report(_episodes(), **kwargs)
        self.assertEqual(report["episodes"], {"total": 2, "wins": 1, "losses": 1})
        self.assertEqual(report["transitions"]["policy_eligible"], 3)
        self.assertEqual(report["transitions"]["original_conflicts"], 2)
        self.assertEqual(report["transitions"]["relabeled"], 1)
        self.assertEqual(report["transitions"]["fallback"], 1)
        self.assertEqual(
            report["transitions"]["conflict_status_by_boundary"],
            {
                "tick_0": {"relabeled": 1, "fallback": 0},
                "later": {"relabeled": 0, "fallback": 1},
            },
        )
        self.assertEqual(
            report["successful_corpus"],
            {
                "policy_eligible": 2,
                "original_conflicts": 1,
                "relabeled": 1,
                "fallback": 0,
            },
        )
        self.assertEqual(report, diagnostic.build_report(_episodes(), **kwargs))
        payload = dict(report)
        digest = payload.pop("report_payload_sha256")
        rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.assertEqual(digest, hashlib.sha256(rendered.encode()).hexdigest())
        self.assertEqual(len(report["coordinate"]["action_state_sha256"]), 64)
        self.assertNotIn("trace", json.dumps(report))

    def test_report_fails_closed_on_each_relabel_invariant(self):
        mutations = [
            (lambda es: es[0].trace.pop(), "length drift"),
            (lambda es: es[0].trace[0].update(action_index=7), "action drift"),
            (lambda es: es[0].trace[0].update(state_hash=""), "state hash"),
            (
                lambda es: setattr(es[0].transitions[0], "teacher_effective_action", 0),
                "effective teacher index drift",
            ),
            (
                lambda es: (
                    setattr(es[0].transitions[0], "teacher_effective_action", 0),
                    es[0].trace[0].update(
                        teacher_effective_action_index=0,
                        teacher_alternate_action_index=0,
                    ),
                ),
                "invalid relabeled",
            ),
            (
                lambda es: setattr(
                    es[0].transitions[0],
                    "action_mask",
                    [True, False] + [True] * 6,
                ),
                "invalid relabeled",
            ),
            (
                lambda es: (
                    setattr(es[1].transitions[0], "teacher_effective_action", 1),
                    es[1].trace[0].update(teacher_effective_action_index=1),
                ),
                "fallback must",
            ),
            (
                lambda es: (
                    setattr(es[0].transitions[1], "teacher_effective_action", 3),
                    es[0].trace[1].update(teacher_effective_action_index=3),
                ),
                "nonconflict must preserve",
            ),
            (lambda es: es[0].trace[0].update(tick=-1), "invalid tick"),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                episodes = _episodes()
                mutate(episodes)
                with self.assertRaisesRegex(ValueError, message):
                    diagnostic.build_report(
                        episodes, source_bindings={}, config=_config(), tool_inputs={}
                    )

    def test_bound_inputs_require_exact_hash_train_identity_and_schedule(self):
        config = {
            "schema": "selector_training_config_v1",
            "candidate_version": "v42",
            "teacher_warmup_seed_set": diagnostic.TEACHER_SET_RELATIVE,
            "scenario_id": "bootstrap-defense-v1",
            "scenario_version": 2,
        }
        teacher_set = {
            "split": "train",
            "seed_set_id": "bootstrap-defense-v1-teacher-train-v1",
            "seed_set_version": 1,
            "scenario_id": "bootstrap-defense-v1",
            "scenario_version": 2,
            "seeds": list(range(291001, 291257)),
        }
        patches = [
            patch.object(
                diagnostic, "_partner_intent_duplication_risk", return_value={}
            ),
            patch.object(
                diagnostic,
                "_partner_intent_teacher_conflict_filter",
                return_value=None,
            ),
            patch.object(
                diagnostic,
                "_partner_intent_teacher_conflict_relabel",
                return_value={},
            ),
            patch.object(diagnostic, "_teacher_warmup_policy", return_value={}),
            patch.object(diagnostic, "_teacher_rehearsal_policy", return_value={}),
            patch.object(
                diagnostic, "_teacher_warmup_seed_schedule",
                return_value=list(reversed(teacher_set["seeds"])),
            ),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.assertEqual(
            diagnostic.validate_bound_inputs(
                config, teacher_set, source_sha256=diagnostic.EXPECTED_SOURCE_SHA256
            ),
            list(reversed(teacher_set["seeds"])),
        )
        with self.assertRaisesRegex(ValueError, "source digest drift"):
            diagnostic.validate_bound_inputs(config, teacher_set, source_sha256={})
        bad = copy.deepcopy(teacher_set)
        bad["split"] = "dev"
        with self.assertRaisesRegex(ValueError, "not a train split"):
            diagnostic.validate_bound_inputs(
                config, bad, source_sha256=diagnostic.EXPECTED_SOURCE_SHA256
            )

    def test_acceptance_gate_fails_for_every_precommitted_count(self):
        report = {
            "episodes": {
                "total": diagnostic.EXPECTED_COUNTS["episodes"],
                "wins": diagnostic.EXPECTED_COUNTS["wins"],
            },
            "transitions": {
                "policy_eligible": diagnostic.EXPECTED_COUNTS[
                    "policy_eligible_transitions"
                ],
                "original_conflicts": diagnostic.EXPECTED_COUNTS["original_conflicts"],
                "relabeled": diagnostic.EXPECTED_COUNTS["relabeled"],
                "fallback": diagnostic.EXPECTED_COUNTS["fallback"],
                "conflict_status_by_boundary": {
                    "tick_0": {
                        "relabeled": diagnostic.EXPECTED_COUNTS["tick_0_relabeled"],
                        "fallback": diagnostic.EXPECTED_COUNTS["tick_0_fallback"],
                    },
                    "later": {
                        "relabeled": diagnostic.EXPECTED_COUNTS["later_relabeled"],
                        "fallback": diagnostic.EXPECTED_COUNTS["later_fallback"],
                    },
                },
            },
            "successful_corpus": {
                "policy_eligible": diagnostic.EXPECTED_COUNTS[
                    "successful_policy_eligible_transitions"
                ],
                "original_conflicts": diagnostic.EXPECTED_COUNTS[
                    "successful_original_conflicts"
                ],
                "relabeled": diagnostic.EXPECTED_COUNTS["successful_relabeled"],
                "fallback": diagnostic.EXPECTED_COUNTS["successful_fallback"],
            },
        }
        diagnostic.validate_acceptance_counts(report)
        locations = {
            "episodes": ("episodes", "total"),
            "wins": ("episodes", "wins"),
            "policy_eligible_transitions": ("transitions", "policy_eligible"),
            "original_conflicts": ("transitions", "original_conflicts"),
            "relabeled": ("transitions", "relabeled"),
            "fallback": ("transitions", "fallback"),
            "successful_policy_eligible_transitions": (
                "successful_corpus",
                "policy_eligible",
            ),
            "successful_original_conflicts": (
                "successful_corpus",
                "original_conflicts",
            ),
            "successful_relabeled": ("successful_corpus", "relabeled"),
            "successful_fallback": ("successful_corpus", "fallback"),
        }
        for name, (section, key) in locations.items():
            with self.subTest(name=name):
                drifted = copy.deepcopy(report)
                drifted[section][key] += 1
                with self.assertRaisesRegex(RuntimeError, "acceptance counts differ"):
                    diagnostic.validate_acceptance_counts(drifted)
        for boundary, key, expected_key in (
            ("tick_0", "relabeled", "tick_0_relabeled"),
            ("tick_0", "fallback", "tick_0_fallback"),
            ("later", "relabeled", "later_relabeled"),
            ("later", "fallback", "later_fallback"),
        ):
            with self.subTest(name=expected_key):
                drifted = copy.deepcopy(report)
                drifted["transitions"]["conflict_status_by_boundary"][boundary][
                    key
                ] += 1
                with self.assertRaisesRegex(RuntimeError, "acceptance counts differ"):
                    diagnostic.validate_acceptance_counts(drifted)

    def test_atomic_hash_and_cli_success_and_failure_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            digest = diagnostic.atomic_write_json(output, {"b": 2, "a": 1})
            self.assertEqual(digest, hashlib.sha256(output.read_bytes()).hexdigest())
            report = {
                "episodes": {"total": 256},
                "transitions": {
                    "original_conflicts": 752,
                    "relabeled": 682,
                    "fallback": 70,
                },
                "report_payload_sha256": "payload",
            }
            with patch.object(
                diagnostic, "run_diagnostic", return_value=(report, "output")
            ):
                self.assertEqual(diagnostic.main(["--output", str(output)]), 0)
            with patch.object(
                diagnostic, "run_diagnostic", side_effect=ValueError("bad")
            ):
                self.assertEqual(diagnostic.main(["--output", str(output)]), 1)


if __name__ == "__main__":
    unittest.main()
