import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mindustry_agents.tools import evaluate_ladder


def _seed_contract(path: Path, seed_set_id: str, split: str, seeds: list[int]):
    path.write_text(
        json.dumps(
            {
                "seed_set_id": seed_set_id,
                "seed_set_version": 1,
                "scenario_id": "temporary-test-scenario",
                "scenario_version": 1,
                "split": split,
                "seeds": seeds,
            }
        ),
        encoding="utf-8",
    )


class _FakeProcess:
    config = None

    def __init__(self, config):
        type(self).config = config

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def handshake(self, _client):
        return SimpleNamespace(
            engine_version="v",
            engine_commit="c",
            arc_version="a",
            protocol_version=1,
        )

    def reset(self, **_kwargs):
        return SimpleNamespace(episode_id="episode", metadata={"wave_ticks": [10]})

    def step(self, *_args, **_kwargs):
        return None


class TestEvaluateLadderRuntime(unittest.TestCase):
    def test_direct_loader_reads_only_explicit_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "direct.json"
            _seed_contract(direct, "direct-dev", "dev", [101])
            poison = root / "unreadable-or-missing.json"
            with patch.dict(
                evaluate_ladder.SEED_SET_FILES,
                {"poison": poison.name},
                clear=True,
            ):
                contracts = evaluate_ladder._load_direct_contracts([direct])
            self.assertEqual(list(contracts), ["direct-dev"])

    def test_direct_loader_rejects_duplicate_ids_and_cross_set_seed_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            _seed_contract(first, "same", "dev", [1])
            _seed_contract(second, "same", "dev", [2])
            with self.assertRaisesRegex(ValueError, "duplicate direct seed set id"):
                evaluate_ladder._load_direct_contracts([first, second])
            _seed_contract(second, "other", "dev", [1])
            with self.assertRaisesRegex(ValueError, "appears in both"):
                evaluate_ladder._load_direct_contracts([first, second])

    def test_direct_cli_is_mutually_exclusive_and_requires_runtime_config(self):
        with tempfile.TemporaryDirectory() as directory:
            direct = Path(directory) / "direct.json"
            _seed_contract(direct, "direct-dev", "dev", [1])
            with self.assertRaises(SystemExit):
                evaluate_ladder.main(
                    ["--seed-set-file", str(direct), "--seed-sets", "fixed"]
                )
            with self.assertRaises(SystemExit):
                evaluate_ladder.main(["--seed-set-file", str(direct)])

    def test_direct_cli_requires_declared_split(self):
        with tempfile.TemporaryDirectory() as directory:
            direct = Path(directory) / "direct.json"
            config = Path(directory) / "runtime.json"
            _seed_contract(direct, "direct-dev", "dev", [1])
            config.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                evaluate_ladder.main(
                    [
                        "--seed-set-file",
                        str(direct),
                        "--runtime-config",
                        str(config),
                    ]
                )

    def test_direct_held_out_authorization_uses_contract_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            held_out = root / "arbitrary-name.json"
            dev = root / "ordinary-dev.json"
            config = root / "runtime.json"
            _seed_contract(held_out, "not-the-held-out-alias", "held-out", [1])
            _seed_contract(dev, "held-out", "dev", [2])
            config.write_text("{}", encoding="utf-8")
            provenance = {"schema": evaluate_ladder.RUNTIME_PROVENANCE_SCHEMA}
            with patch.object(
                evaluate_ladder, "_runtime_provenance", return_value=provenance
            ):
                with self.assertRaises(SystemExit):
                    evaluate_ladder.main(
                        [
                            "--seed-set-file",
                            str(held_out),
                            "--runtime-config",
                            str(config),
                            "--seed-set-split",
                            "held-out",
                        ]
                    )
                with self.assertRaises(SystemExit):
                    evaluate_ladder.main(
                        [
                            "--seed-set-file",
                            str(dev),
                            "--runtime-config",
                            str(config),
                            "--seed-set-split",
                            "dev",
                            "--allow-held-out-final",
                        ]
                    )

    def test_unauthorized_direct_held_out_rejects_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            held_out = root / "visible-held-out.json"
            ordinary = root / "ordinary.json"
            config = root / "runtime.json"
            config.write_text("{}", encoding="utf-8")
            cases = (
                (held_out, "dev", False),
                (ordinary, "held-out", False),
                (ordinary, "dev", True),
            )
            for path, split, allow in cases:
                argv = [
                    "--seed-set-file",
                    str(path),
                    "--seed-set-split",
                    split,
                    "--runtime-config",
                    str(config),
                ]
                if allow:
                    argv.append("--allow-held-out-final")
                with patch.object(
                    evaluate_ladder, "_load_direct_contracts"
                ) as loader:
                    with self.assertRaises(SystemExit):
                        evaluate_ladder.main(argv)
                    loader.assert_not_called()

    def test_direct_declared_split_must_match_loaded_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "ordinary.json"
            config = root / "runtime.json"
            _seed_contract(direct, "direct-dev", "dev", [1])
            config.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                evaluate_ladder.main(
                    [
                        "--seed-set-file",
                        str(direct),
                        "--seed-set-split",
                        "fixed",
                        "--runtime-config",
                        str(config),
                    ]
                )

    def test_partition_disables_build_and_stamps_provenance(self):
        provenance = {"schema": evaluate_ladder.RUNTIME_PROVENANCE_SCHEMA}
        job = {
            "order": 0,
            "policy": "greedy-utility",
            "seed": 7,
            "seed_set": {
                "seed_set_id": "temporary-dev",
                "seed_set_version": 1,
                "scenario_id": "temporary-test-scenario",
                "scenario_version": 1,
                "split": "dev",
                "seeds": [7],
            },
        }
        with patch.object(evaluate_ladder, "RlServerProcess", _FakeProcess), patch.object(
            evaluate_ladder, "run_utility_episode", return_value=object()
        ), patch.object(
            evaluate_ladder,
            "ladder_episode_record",
            side_effect=lambda _result, manifest, _seed_set: {"manifest": manifest},
        ):
            records = evaluate_ladder._run_partition(
                0,
                [job],
                base_port=47810,
                java="java",
                runtime_provenance=provenance,
            )
        self.assertFalse(_FakeProcess.config.build_if_missing)
        self.assertIs(records[0][1]["manifest"]["runtime_provenance"], provenance)

    def test_direct_cli_stamps_top_level_aggregate_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "direct.json"
            config = root / "runtime.json"
            output = root / "records.jsonl"
            aggregate_output = root / "aggregate.json"
            _seed_contract(direct, "direct-dev", "dev", [1])
            config.write_text("{}", encoding="utf-8")
            provenance = {"schema": evaluate_ladder.RUNTIME_PROVENANCE_SCHEMA}
            with patch.object(
                evaluate_ladder, "_runtime_provenance", return_value=provenance
            ) as provenance_call, patch.object(
                evaluate_ladder, "_run_jobs", return_value=[]
            ), patch.object(
                evaluate_ladder, "aggregate_records", return_value=[]
            ), patch.object(
                evaluate_ladder, "held_out_promotions", return_value=[]
            ):
                result = evaluate_ladder.main(
                    [
                        "--seed-set-file",
                        str(direct),
                        "--runtime-config",
                        str(config),
                        "--seed-set-split",
                        "dev",
                        "--output",
                        str(output),
                        "--aggregate-output",
                        str(aggregate_output),
                    ]
                )
            self.assertEqual(result, 0)
            provenance_call.assert_called_once()
            document = json.loads(aggregate_output.read_text(encoding="utf-8"))
            self.assertEqual(document["runtime_provenance"], provenance)


if __name__ == "__main__":
    unittest.main()
