import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


def _candidate(index=0, task_type="BUILD_LINE"):
    return {
        "index": index,
        "task_id": f"task:{index}",
        "task_type": task_type,
        "priority": 0.75,
        "estimated_ticks": 600,
        "estimated_cost": {"copper": 31},
        "helpers_requested": 1,
        "dependency_count": 0,
        "exclusive": True,
        "semantic_task_active": False,
        "semantic_task_owned_by_other": False,
        "utility_features": {
            "team_value": 0.75,
            "urgency": 1.0,
            "capability_fit": 1.0,
            "role_fit": 1.0,
            "proximity": 0.5,
            "help_synergy": 1.0,
            "human_priority": 0.0,
            "travel_cost": 0.5,
            "resource_cost": 0.2,
            "duplication_risk": 0.0,
            "switching_cost": 0.0,
            "danger": 0.0,
            "uncertainty": 0.0,
        },
    }


def _boundary():
    team = {
        "tick": 600,
        "wave": 1,
        "copper": 250,
        "core_health": 1100,
        "core_copper_inflow_per_s": 0.3,
        "core_copper_inflow_target_per_s": 0.6,
        "time_to_next_wave": 2100,
        "enemy_count": 0,
        "enemy_total_health": 0,
        "enemy_nearest_core_dist": -1,
        "line_operational": False,
        "defense_ammo_coverage": 0.2,
        "defense_health_coverage": 1.0,
        "defense_turret_coverage": 0.5,
        "defense_readiness": 0.2,
        "broken_block_count": 0,
    }
    observation = {
        "unit": {
            "x": 216,
            "y": 192,
            "health": 150,
            "max_health": 150,
            "dead": False,
            "item_amount": 10,
            "item_capacity": 30,
            "build_queue_depth": 0,
            "build_plan_progress": 0,
        },
        "skill": {"status": "READY", "progress": 0},
        "team": team,
        "task_candidates": [_candidate(), _candidate(1, "WAIT")],
    }
    mask = {
        "candidate_task": [True, True],
        "continue_current_task": False,
        "wait": True,
        "abandon": False,
    }
    metadata = {
        "width": 48,
        "height": 48,
        "tile_size": 8,
        "tick_cap": 9000,
        "wave_count": 3,
        "wave_ticks": [2700, 4500, 6300],
        "copper_budget": 4000,
        "core_health_max": 1100,
    }
    return (
        [deepcopy(observation) for _ in range(3)],
        [deepcopy(mask) for _ in range(3)],
        metadata,
    )


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestSharedRecurrentIPPO(unittest.TestCase):
    def test_pinned_shapes_seed_and_role_sensitivity(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )

        first = SharedRecurrentSelector(9601)
        second = SharedRecurrentSelector(9601)
        self.assertEqual(model_state_digest(first), model_state_digest(second))
        candidates = torch.zeros((3, 8, 37))
        scalars = torch.zeros((3, 160))
        present = torch.tensor([[True] * 3 + [False] * 5] * 3)
        mask = torch.tensor([[True, False, True] + [False] * 6 + [True]] * 3)
        hidden = torch.zeros((3, 64))
        raw, masked, value, next_hidden = first(
            candidates,
            scalars,
            present,
            mask,
            torch.tensor([0, 1, 2]),
            hidden,
        )
        self.assertEqual(tuple(raw.shape), (3, 10))
        self.assertEqual(tuple(value.shape), (3,))
        self.assertEqual(tuple(next_hidden.shape), (3, 64))
        self.assertTrue((masked[:, 1] < -1e30).all())
        self.assertFalse(torch.equal(next_hidden[0], next_hidden[1]))
        self.assertFalse(torch.equal(next_hidden[1], next_hidden[2]))

    def test_one_model_all_seats_ordered_atomic_bundle(self):
        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            SharedSeatState,
            decide_all_seats,
        )

        observations, masks, metadata = _boundary()
        model = SharedRecurrentSelector(9601)
        state = SharedSeatState.fresh()
        teacher = [
            {
                "agent_id": agent_id,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 0,
                },
            }
            for agent_id in range(3)
        ]
        decision = decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            evaluation=True,
            teacher_actions=teacher,
        )
        self.assertEqual(decision.agent_actions, teacher)
        self.assertEqual(decision.evaluation_order, (0, 1, 2))
        self.assertEqual([row["agent_id"] for row in decision.agent_actions], [0, 1, 2])
        self.assertEqual(len({decision.model_state_sha256}), 1)
        self.assertTrue(all(state.hidden[index].abs().sum() > 0 for index in range(3)))

    def test_dead_seat_resets_only_its_private_state(self):
        import torch

        from mindustry_agents.training.ippo import SharedSeatState

        observations, _, _ = _boundary()
        state = SharedSeatState.fresh()
        state.hidden[:] = 1.0
        state.histories[0].previous_task_type = "BUILD_LINE"
        state.histories[1].previous_task_type = "DEFEND_REGION"
        state.histories[2].previous_task_type = "HARVEST_RESOURCE"
        observations[1]["unit"]["dead"] = True
        state.observe_lifecycle(observations)
        self.assertTrue(torch.equal(state.hidden[0], torch.ones(64)))
        self.assertTrue(torch.equal(state.hidden[1], torch.zeros(64)))
        self.assertTrue(torch.equal(state.hidden[2], torch.ones(64)))
        self.assertEqual(state.histories[0].previous_task_type, "BUILD_LINE")
        self.assertIsNone(state.histories[1].previous_task_type)
        self.assertEqual(state.histories[2].previous_task_type, "HARVEST_RESOURCE")

    def test_teacher_bundle_must_be_agent_ordered(self):
        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            SharedSeatState,
            decide_all_seats,
        )

        observations, masks, metadata = _boundary()
        teacher = [
            {"agent_id": 1, "task_action": {"type": "WAIT"}},
            {"agent_id": 0, "task_action": {"type": "WAIT"}},
            {"agent_id": 2, "task_action": {"type": "WAIT"}},
        ]
        with self.assertRaisesRegex(ValueError, "agent-id order"):
            decide_all_seats(
                SharedRecurrentSelector(9601),
                SharedSeatState.fresh(),
                observations,
                masks,
                metadata,
                evaluation=True,
                teacher_actions=teacher,
            )

    def test_ippo_reward_is_separate_per_seat_and_all_adversaries_pass(self):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_reward import IPPOReward
        from mindustry_agents.training.ippo_reward_adversary import (
            CASES,
            run_case,
        )
        from mindustry_agents.training.ippo_ppo import load_ippo_v1_config

        config = load_ippo_v1_config(
            repo_root() / "configs/training/m9-ippo-v1.json"
        )
        reward = IPPOReward(
            config["team_quality_reward"], config["individual_shaping"]
        )
        result = reward.observe(
            {"tick": 0, "enemy_count": 0},
            {"tick": 60, "enemy_count": 0},
            advanced_ticks=60,
            tick_cap=9000,
            coordination_metrics={
                "agent_ticks": 180,
                "idle_agent_ticks": 60,
                "idle_agent_ticks_by_agent": [10, 20, 30],
                "unavailable_agent_ticks": 0,
                "unavailable_agent_ticks_by_agent": [0, 0, 0],
                "duplicate_work_incidents": 0,
                "announced_messages": 0,
            },
        )
        self.assertEqual(
            result.individual_components, (-0.0025, -0.005, -0.0075)
        )
        self.assertEqual(len(set(result.reward_by_agent)), 3)
        reports = [run_case(case, config) for case in CASES]
        self.assertTrue(all(report["pass"] for report in reports))

    def test_ippo_config_is_hash_bound_and_sealed_paths_are_absent(self):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_ppo import load_ippo_v1_config

        path = repo_root() / "configs/training/m9-ippo-v1.json"
        config = load_ippo_v1_config(path)
        self.assertIsNone(config["confirmation_seed_set"])
        self.assertIsNone(config["held_out_seed_set"])
        with tempfile.TemporaryDirectory() as directory:
            drifted = json.loads(path.read_text(encoding="utf-8"))
            drifted["training_cycles"] += 1
            target = Path(directory) / "drifted.json"
            target.write_text(json.dumps(drifted), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash"):
                load_ippo_v1_config(target)

    def test_ippo_gae_never_crosses_private_seat_sequences(self):
        import torch

        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            IPPOTransition,
            ippo_advantages,
        )

        def transition(agent_id, reward, done):
            return IPPOTransition(
                agent_id=agent_id,
                candidates=torch.zeros((8, 37)),
                scalars=torch.zeros(160),
                candidate_present=torch.ones(8, dtype=torch.bool),
                action_mask=torch.ones(10, dtype=torch.bool),
                hidden_input=torch.zeros(64),
                action=0,
                old_log_prob=0.0,
                old_value=0.0,
                team_reward=float(reward),
                individual_reward=0.0,
                advanced_ticks=60,
                done=done,
                policy_loss_mask=False,
            )

        episode = IPPOEpisodeRollout(
            seed=1,
            outcome="win",
            transitions=tuple(
                [transition(agent_id, agent_id + 1, False) for agent_id in range(3)]
                + [
                    transition(agent_id, (agent_id + 1) * 10, True)
                    for agent_id in range(3)
                ]
            ),
        )
        _, advantages, returns = ippo_advantages(
            [episode], gamma_per_second=1.0, gae_lambda=1.0
        )
        self.assertEqual(advantages.tolist(), [11, 22, 33, 10, 20, 30])
        self.assertEqual(returns.tolist(), advantages.tolist())

    def test_ippo_update_is_cpu_deterministic(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            IPPOTransition,
            ippo_update,
        )

        torch.set_num_threads(1)
        source = SharedRecurrentSelector(9601)
        transitions = []
        for boundary in range(2):
            for agent_id in range(3):
                candidates = torch.zeros((8, 37))
                candidates[:, 0] = boundary + agent_id / 10
                scalars = torch.zeros(160)
                present = torch.ones(8, dtype=torch.bool)
                mask = torch.ones(10, dtype=torch.bool)
                hidden = torch.full((64,), agent_id / 10)
                with torch.no_grad():
                    _, logits, value, _ = source(
                        candidates[None],
                        scalars[None],
                        present[None],
                        mask[None],
                        torch.tensor([agent_id]),
                        hidden[None],
                    )
                    action = agent_id
                    log_prob = torch.log_softmax(logits[0], dim=-1)[action]
                transitions.append(
                    IPPOTransition(
                        agent_id=agent_id,
                        candidates=candidates,
                        scalars=scalars,
                        candidate_present=present,
                        action_mask=mask,
                        hidden_input=hidden,
                        action=action,
                        old_log_prob=float(log_prob),
                        old_value=float(value[0]),
                        team_reward=1.0,
                        individual_reward=-0.01 * agent_id,
                        advanced_ticks=60,
                        done=boundary == 1,
                    )
                )
        episode = IPPOEpisodeRollout(1, "win", tuple(transitions))
        config = {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": 3,
            "ppo_epochs": 2,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.02,
            "max_grad_norm": 0.5,
        }
        first = SharedRecurrentSelector(9601)
        second = SharedRecurrentSelector(9601)
        first_optimizer = torch.optim.Adam(first.parameters(), lr=0.0001, eps=1e-8)
        second_optimizer = torch.optim.Adam(second.parameters(), lr=0.0001, eps=1e-8)
        first_metrics = ippo_update(
            first,
            first_optimizer,
            [episode],
            config,
            torch.Generator().manual_seed(9603),
        )
        second_metrics = ippo_update(
            second,
            second_optimizer,
            [episode],
            config,
            torch.Generator().manual_seed(9603),
        )
        self.assertEqual(first_metrics, second_metrics)
        self.assertEqual(model_state_digest(first), model_state_digest(second))

    def test_ippo_checkpoint_roundtrip_rejects_state_tampering(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_artifacts import (
            load_ippo_checkpoint,
            save_ippo_checkpoint,
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pt"
            source = SharedRecurrentSelector(9601)
            optimizer = torch.optim.Adam(source.parameters(), lr=0.0001, eps=1e-8)
            evidence = save_ippo_checkpoint(
                path,
                source,
                optimizer,
                update=0,
                parent_checkpoint_content_sha256=None,
            )
            twin = save_ippo_checkpoint(
                Path(directory) / "different-name.pt",
                source,
                optimizer,
                update=0,
                parent_checkpoint_content_sha256=None,
            )
            self.assertEqual(
                evidence["checkpoint_content_sha256"],
                twin["checkpoint_content_sha256"],
            )
            loaded = SharedRecurrentSelector(123)
            loaded_optimizer = torch.optim.Adam(
                loaded.parameters(), lr=0.0001, eps=1e-8
            )
            payload = load_ippo_checkpoint(path, loaded, loaded_optimizer)
            self.assertEqual(model_state_digest(source), model_state_digest(loaded))
            self.assertEqual(payload["model_state_sha256"], evidence["model_state_sha256"])

            payload["model_state"]["role_embedding.weight"][0, 0] += 1.0
            tampered = Path(directory) / "tampered.pt"
            torch.save(payload, tampered)
            with self.assertRaisesRegex(ValueError, "model digest"):
                load_ippo_checkpoint(
                    tampered, SharedRecurrentSelector(9601)
                )

    def test_ippo_run_manifests_compare_path_independent_evidence(self):
        import torch

        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_artifacts import (
            atomic_write_manifest,
            base_run_manifest,
            compare_ippo_run_manifests,
            finalize_run_manifest,
        )

        root = repo_root()
        train_path = root / "configs/evaluation/bootstrap-defense-v1-m9-train-v1.json"
        dev_path = root / "configs/evaluation/bootstrap-defense-v1-m9-dev-v1.json"
        train = json.loads(train_path.read_text(encoding="utf-8"))
        dev = json.loads(dev_path.read_text(encoding="utf-8"))
        seed_identity = lambda document, path: {
            "id": document["seed_set_id"],
            "version": document["seed_set_version"],
            "split": document["split"],
            "path": str(path.relative_to(root).as_posix()),
            "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        }
        torch.set_num_threads(1)
        manifest = base_run_manifest(
            root / "configs/training/m9-ippo-v1.json",
            initial_model_state_sha256=model_state_digest(
                SharedRecurrentSelector(9601)
            ),
            train_seed_set=seed_identity(train, train_path),
            dev_seed_set=seed_identity(dev, dev_path),
            baseline_path=(
                root
                / "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
            ),
        )
        manifest["selected_checkpoint"] = {
            "update": 1,
            "parent_checkpoint_content_sha256": None,
            "model_state_sha256": "model-a",
            "optimizer_state_sha256": "optimizer-a",
        }
        manifest["deterministic_checkpoint_verification"] = {
            "seed": 18000000001,
            "trace_digest_a": "trace-a",
            "trace_digest_b": "trace-a",
            "bit_exact": True,
        }
        manifest = finalize_run_manifest(manifest)
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "replica-a.json"
            second = Path(directory) / "replica-b.json"
            atomic_write_manifest(first, manifest)
            atomic_write_manifest(second, manifest)
            compare_ippo_run_manifests(first, second)
            changed = deepcopy(manifest)
            changed["deterministic_checkpoint_verification"][
                "trace_digest_b"
            ] = "trace-b"
            changed = finalize_run_manifest(changed)
            atomic_write_manifest(second, changed)
            with self.assertRaisesRegex(RuntimeError, "diverged"):
                compare_ippo_run_manifests(first, second)

    def test_committed_ippo_preflight_is_public_only_and_complete(self):
        from mindustry_agents.training.ippo_preflight import validate_preflight

        result = validate_preflight()
        self.assertTrue(result["passed"])
        self.assertFalse(result["confirmation_or_held_out_access"])
        self.assertEqual(result["public_baseline_wins"], 36)
        self.assertEqual(len(result["artifacts"]), 4)


if __name__ == "__main__":
    unittest.main()
