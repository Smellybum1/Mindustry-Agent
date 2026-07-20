"""Trivial import/smoke test: the core package installs and imports with zero
third-party dependencies, and pins match ENGINE_VERSION.
"""

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


if __name__ == "__main__":
    unittest.main()
