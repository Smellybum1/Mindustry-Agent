"""Run the shared expert through the fixed-step adapter and report its opening digest."""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M7.2 fixed-step shared-policy probe")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            env.handshake("m7-shared-policy-check")
            reset = env.reset(
                root_seed=12345,
                agent_count=3,
                options={"shared_expert_policy": True},
            )
            episode = reset.episode_id
            tick = reset.tick
            metrics = {}
            while tick < 2100:
                response = env.step(
                    episode,
                    expected_tick=tick,
                    ticks_to_advance=min(30, 2100 - tick),
                    agent_actions=[],
                )
                tick = response.tick
                metrics = response.coordination_metrics
                if metrics.get("shared_policy_phase") == "reserve-mining":
                    break
            digest = str(metrics.get("shared_decision_digest", ""))
            count = int(metrics.get("shared_decision_count", 0))
            if not digest or count < 1 or metrics.get("shared_policy_phase") != "reserve-mining":
                raise AssertionError(
                    f"fixed-step shared expert did not reach opening parity: {metrics}"
                )
    except Exception as exc:
        print(f"SHARED-POLICY FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"FIXED DECISION DIGEST digest={digest} selections={count} tick={tick}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
