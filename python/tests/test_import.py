"""Trivial import/smoke test: the core package installs and imports with zero
third-party dependencies, and pins match ENGINE_VERSION.
"""

import ast
from pathlib import Path
import unittest


class TestImport(unittest.TestCase):
    def test_package_imports(self):
        import mindustry_agents

        self.assertEqual(mindustry_agents.PROTOCOL_VERSION, 1)
        self.assertEqual(mindustry_agents.ENGINE_TAG, "v159.7")
        self.assertTrue(mindustry_agents.ENGINE_COMMIT.startswith("c9686eb5"))

    def test_subpackages_import(self):
        # Each skeleton subpackage must import cleanly (real docstrings, no deps).
        from mindustry_agents import (  # noqa: F401
            env,
            process,
            policies,
            training,
            evaluation,
            telemetry,
            tools,
        )

    def test_rl_framework_imports_are_training_only(self):
        """ADR-0011 keeps every RL framework import below training/."""
        package_root = Path(__file__).parents[1] / "src" / "mindustry_agents"
        forbidden = {"numpy", "pettingzoo", "torch"}
        violations = []

        for source_path in sorted(package_root.rglob("*.py")):
            relative = source_path.relative_to(package_root)
            if relative.parts[0] == "training":
                continue
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".", 1)[0] in forbidden:
                        violations.append(f"{relative}:{node.lineno}:{name}")

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
