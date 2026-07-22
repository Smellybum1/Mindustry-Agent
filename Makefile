# Makefile — command surface for mindustry-coop-agents
#
# Every target delegates to scripts/*.sh so that Git Bash (Windows dev) and
# WSL2/Linux (reference training runtime) use identical entry points.
# `make` may be absent on Windows; if so, run `bash scripts/<name>.sh` directly.
#
# Unimplemented targets exit nonzero with a pointer to docs/ROADMAP.md.

SHELL := /bin/bash
SCRIPTS := scripts

.DEFAULT_GOAL := help

.PHONY: help codex-status bootstrap build test test-java test-python smoke \
        determinism stress-reset benchmark scripted-demo evaluate-scripted \
        candidate-policy-check secondary-claim-wake-check \
        owned-schematic-staging-check coordination-parity \
        public-demo-parity \
        adaptive-planning-check \
        scenario-variation-check evaluate-ladder verify-rl-boundary \
        training-gate demo-server human-session-check

help: ## List available targets
	@echo "mindustry-coop-agents — make targets:"
	@echo "  codex-status  compact read-only takeover status"
	@echo "  bootstrap     verify toolchain versions and print them"
	@echo "  build         build Java modules + Python package"
	@echo "  test          all fast tests (Java + Python)"
	@echo "  test-java     JUnit tests"
	@echo "  test-python   python -m pytest python/tests -q"
	@echo "  smoke         one reset/step/close (M1)"
	@echo "  determinism   golden replay / hash check (M1)"
	@echo "  stress-reset  repeated in-memory reset test (M2)"
	@echo "  benchmark     scaling + timing report (M2)"
	@echo "  scripted-demo headless public greedy team (M7.3)"
	@echo "  evaluate-scripted five-seed greedy summaries (M7.3)"
	@echo "  candidate-policy-check public greedy candidate-policy survival (M7.3)"
	@echo "  secondary-claim-wake-check fixed-seat claim-loss boundary (M8.5/V35)"
	@echo "  owned-schematic-staging-check one-tick live-owner staging boundary"
	@echo "  coordination-parity shared policy decision parity (M7.2)"
	@echo "  public-demo-parity exact public-path Java/Python parity (M10)"
	@echo "  adaptive-planning-check adaptive-vs-frozen variant probe (M7.4)"
	@echo "  scenario-variation-check bounded scenario-v2 dev acceptance (M7.5)"
	@echo "  evaluate-ladder permanent baselines + teammate scorecard (M7.6)"
	@echo "  verify-rl-boundary reconstruct pinned WSL2 CPU training runtime (M8.2)"
	@echo "  training-gate WSL2 event collector + inference + 10k resets (M8.3)"
	@echo "  train-selector WSL2 audited one-seat PPO + exact checkpoint replay (M8.4)"
	@echo "  demo-server   human-joinable real-time server (M6/M10)"
	@echo "  human-session-check opt-in M10.3 capture/replay/profile gate"

codex-status: ## Print compact read-only takeover status
	@bash $(SCRIPTS)/codex-status.sh

bootstrap: ## Verify/print toolchain versions (works today)
	@bash $(SCRIPTS)/bootstrap.sh

build: ## Build Java modules + Python package
	@bash $(SCRIPTS)/build.sh

test: test-python test-java ## All fast tests
	@echo "test: Python and Java tests passed"

test-java: ## JUnit tests and custom-module compile checks
	@bash $(SCRIPTS)/test-java.sh

test-python: ## Python unit tests
	@bash $(SCRIPTS)/test-python.sh

smoke: ## One reset/step/close (M1)
	@bash $(SCRIPTS)/smoke.sh

determinism: ## Golden replay / hash check (M1)
	@bash $(SCRIPTS)/determinism.sh

stress-reset: ## Repeated in-memory reset test (M2)
	@bash $(SCRIPTS)/stress-reset.sh

benchmark: ## Scaling + timing report (M2)
	@bash $(SCRIPTS)/benchmark.sh

scripted-demo: ## Headless public greedy team (M7.3)
	@bash $(SCRIPTS)/scripted-demo.sh

evaluate-scripted: ## Evaluate the public M7.3 greedy expert
	@bash $(SCRIPTS)/evaluate-scripted.sh

candidate-policy-check: ## Evaluate the public greedy candidate policy
	@bash $(SCRIPTS)/candidate-policy-check.sh

secondary-claim-wake-check: ## Verify V35's fixed-seat claim-loss boundary
	@bash $(SCRIPTS)/secondary-claim-wake-check.sh

owned-schematic-staging-check: ## Verify live schematic ownership exposes seat-zero staging
	@bash $(SCRIPTS)/owned-schematic-staging-check.sh

coordination-parity: ## Shared fixed-step/demo decision parity (M7.2)
	@bash $(SCRIPTS)/coordination-parity.sh

public-demo-parity: ## Exact public-path Java/Python parity (M10 prerequisite)
	@bash $(SCRIPTS)/public-demo-parity.sh

adaptive-planning-check: ## Adaptive-vs-frozen fixed/probe acceptance (M7.4)
	@bash $(SCRIPTS)/adaptive-planning-check.sh

scenario-variation-check: ## Scenario-v2 variation and frozen-dev acceptance (M7.5)
	@bash $(SCRIPTS)/scenario-variation-check.sh

evaluate-ladder: ## Permanent policy ladder and teammate scorecard (M7.6)
	@bash $(SCRIPTS)/evaluate-ladder.sh

verify-rl-boundary: ## Reconstruct and verify the M8.2 WSL2 CPU runtime
	@bash $(SCRIPTS)/verify-rl-boundary.sh

training-gate: ## Run the M8.3 WSL2 throughput and long-reset gates
	@bash $(SCRIPTS)/training-gate.sh

train-selector: ## Train and verify the M8.4 one-seat selector
	@bash $(SCRIPTS)/train-selector.sh

demo-server: ## Human-joinable real-time server (M6/M10)
	@bash $(SCRIPTS)/demo-server.sh

human-session-check: ## Validate opt-in M10.3 session capture and replay
	@bash $(SCRIPTS)/human-session-check.sh
