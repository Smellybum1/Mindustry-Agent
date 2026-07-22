"""Pure tests for the train-only V40 teacher-conflict diagnostic."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mindustry_agents.training.teacher_conflict_diagnostic import (
    EXPECTED_COUNTS,
    EXPECTED_SOURCE_SHA256,
    REPORT_SCHEMA,
    atomic_write_json,
    build_report,
    sampling_conflict_mapping,
    validate_acceptance_counts,
    validate_bound_inputs,
)


def _config(version: str, *, filtered: bool) -> dict:
    value = {
        "schema": "selector_training_config_v1",
        "candidate_version": version,
        "quality_intervention": version,
        "confirmation_seed_set": f"unused-{version}",
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "teacher_warmup_seed_set": (
            "configs/evaluation/bootstrap-defense-v1-teacher-train-v1.json"
        ),
        "partner_intent_duplication_risk": {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        },
        "teacher_warmup_cycles": 1,
        "teacher_warmup_epochs": 2,
        "teacher_warmup_minibatch_size": 8,
        "teacher_warmup_success_only": True,
        "teacher_warmup_shuffle_seed": 8605,
        "teacher_warmup_minibatch_seed": 11,
        "teacher_warmup_samples_per_epoch": 3,
        "teacher_rehearsal_epochs_per_update": 1,
        "teacher_rehearsal_minibatch_seed": 12,
        "teacher_rehearsal_samples_per_epoch": 3,
        "training_cycles": 2,
    }
    if filtered:
        value["partner_intent_teacher_conflict_filter"] = {
            "schema": "partner_intent_teacher_conflict_filter_v1",
            "match": "teacher_action_index_in_risk_candidate_indices",
            "applies_to": [
                "teacher_warmup",
                "teacher_rehearsal",
                "ppo_teacher_imitation",
            ],
        }
    return value


def _teacher_set() -> dict:
    return {
        "seed_set_id": "bootstrap-defense-v1-teacher-train-v1",
        "seed_set_version": 1,
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "train",
        "seeds": list(range(291001, 291257)),
    }


def _episode(seed: int, outcome: str, rows: list[tuple[bool, bool, int, str]]):
    transitions = [
        SimpleNamespace(
            policy_loss_mask=eligible,
            teacher_action=0 if eligible else None,
            teacher_partner_intent_risk_conflict=conflict,
        )
        for eligible, conflict, _, _ in rows
    ]
    trace = [
        {"tick": tick, "teacher_candidate_diagnostics": {"task_type": task_type}}
        for _, _, tick, task_type in rows
    ]
    return SimpleNamespace(
        seed=seed, outcome=outcome, transitions=transitions, trace=trace
    )


class TeacherConflictDiagnosticTests(unittest.TestCase):
    def test_bound_inputs_require_exact_train_identity_and_config_coordinate(self):
        v39 = _config("v39", filtered=False)
        v40 = _config("v40", filtered=True)
        seeds = validate_bound_inputs(
            v39,
            v40,
            _teacher_set(),
            source_sha256=EXPECTED_SOURCE_SHA256,
        )
        self.assertEqual(sorted(seeds), list(range(291001, 291257)))
        self.assertNotEqual(seeds, sorted(seeds))

        bad = _teacher_set()
        bad["split"] = "dev"
        with self.assertRaisesRegex(ValueError, "not a train split"):
            validate_bound_inputs(
                v39, v40, bad, source_sha256=EXPECTED_SOURCE_SHA256
            )
        with self.assertRaisesRegex(ValueError, "source digest drift"):
            validate_bound_inputs(v39, v40, _teacher_set(), source_sha256={})
        drifted = copy.deepcopy(v40)
        drifted["training_cycles"] = 33
        with self.assertRaisesRegex(ValueError, "config drift"):
            validate_bound_inputs(
                v39,
                drifted,
                _teacher_set(),
                source_sha256=EXPECTED_SOURCE_SHA256,
            )

    def test_sampling_mapping_is_deterministic_and_counts_presentations(self):
        flags = [False, True, False, True, True]
        kwargs = {
            "epochs": 3,
            "samples_per_epoch": 4,
            "generator_seed": 17,
            "calls": 2,
        }
        first = sampling_conflict_mapping(flags, **kwargs)
        second = sampling_conflict_mapping(flags, **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["sampled_presentations"], 24)
        sampled = [
            index
            for order in first["sampled_transition_indices_by_epoch"]
            for index in order
        ]
        self.assertEqual(
            first["sampled_conflict_presentations"],
            sum(flags[index] for index in sampled),
        )
        self.assertEqual(
            first["sampled_unique_conflict_transitions"],
            len({index for index in sampled if flags[index]}),
        )

    def test_report_counts_conflicts_boundaries_tasks_and_affected_episodes(self):
        episodes = [
            _episode(
                1,
                "win",
                [
                    (True, True, 0, "BUILD_SCHEMATIC"),
                    (True, False, 10, "SUPPLY_TURRET"),
                    (False, True, 20, "HARVEST_RESOURCE"),
                ],
            ),
            _episode(
                2,
                "loss",
                [
                    (True, True, 30, "BUILD_SCHEMATIC"),
                    (True, True, 40, "SUPPLY_TURRET"),
                ],
            ),
        ]
        report = build_report(
            episodes,
            source_bindings={"v39_config": {"path": "x", "sha256": "a"}},
            v39_config=_config("v39", filtered=False),
        )
        self.assertEqual(report["schema"], REPORT_SCHEMA)
        self.assertEqual(report["episodes"]["affected_by_conflict"], {
            "winning": 1,
            "losing": 1,
        })
        self.assertEqual(report["transitions"]["total"], 5)
        self.assertEqual(report["transitions"]["policy_eligible"], 4)
        self.assertEqual(report["transitions"]["conflicting"], 3)
        self.assertEqual(
            report["transitions"]["conflicts_by_teacher_task_type"],
            {"BUILD_SCHEMATIC": 2, "SUPPLY_TURRET": 1},
        )
        self.assertEqual(
            report["transitions"]["conflicts_by_boundary"],
            {"tick_0": 1, "later": 2},
        )
        self.assertEqual(
            report["successful_corpus"],
            {"policy_eligible": 2, "conflicting": 1},
        )

        repeat = build_report(
            episodes,
            source_bindings={"v39_config": {"path": "x", "sha256": "a"}},
            v39_config=_config("v39", filtered=False),
        )
        self.assertEqual(report, repeat)
        payload = dict(report)
        digest = payload.pop("report_payload_sha256")
        rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        import hashlib

        self.assertEqual(digest, hashlib.sha256(rendered.encode()).hexdigest())

    def test_report_fails_closed_on_trace_drift_and_bad_conflict_diagnostics(self):
        episode = _episode(1, "win", [(True, True, 0, "BUILD")])
        episode.trace = []
        with self.assertRaisesRegex(ValueError, "length drift"):
            build_report(
                [episode], source_bindings={}, v39_config=_config("v39", filtered=False)
            )
        episode = _episode(1, "win", [(True, True, 0, "BUILD")])
        episode.trace[0] = {"tick": 0}
        with self.assertRaisesRegex(ValueError, "lacks teacher diagnostics"):
            build_report(
                [episode], source_bindings={}, v39_config=_config("v39", filtered=False)
            )

    def test_acceptance_gate_requires_every_precommitted_count(self):
        report = {
            "episodes": {
                "total": EXPECTED_COUNTS["episodes"],
                "wins": EXPECTED_COUNTS["wins"],
            },
            "transitions": {
                "policy_eligible": EXPECTED_COUNTS["policy_eligible_transitions"],
                "conflicting": EXPECTED_COUNTS["conflicting_transitions"],
            },
            "successful_corpus": {
                "policy_eligible": EXPECTED_COUNTS[
                    "successful_policy_eligible_transitions"
                ],
                "conflicting": EXPECTED_COUNTS[
                    "successful_conflicting_transitions"
                ],
            },
            "v39_sample_schedule_mapping": {
                "warmup": {
                    "sampled_presentations": EXPECTED_COUNTS[
                        "warmup_presentations"
                    ],
                    "sampled_conflict_presentations": EXPECTED_COUNTS[
                        "warmup_conflict_presentations"
                    ],
                },
                "rehearsal": {
                    "sampled_presentations": EXPECTED_COUNTS[
                        "rehearsal_presentations"
                    ],
                    "sampled_conflict_presentations": EXPECTED_COUNTS[
                        "rehearsal_conflict_presentations"
                    ],
                },
            },
        }
        validate_acceptance_counts(report)
        report["transitions"]["conflicting"] -= 1
        with self.assertRaisesRegex(RuntimeError, "acceptance counts differ"):
            validate_acceptance_counts(report)

    def test_atomic_output_is_sorted_and_preserves_destination_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "report.json"
            atomic_write_json(output, {"b": 2, "a": 1})
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                '{\n  "a": 1,\n  "b": 2\n}\n',
            )
            with patch.object(os, "replace", side_effect=OSError("failed")):
                with self.assertRaisesRegex(RuntimeError, "atomically write"):
                    atomic_write_json(output, {"a": 3})
            self.assertEqual(json.loads(output.read_text()), {"a": 1, "b": 2})
            self.assertEqual(list(output.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
