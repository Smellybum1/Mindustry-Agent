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
        candidate-policy-check single-brain-failover-check \
        per-seat-history-check \
        m9-shared-policy-check m9-reward-check m9-rollout-check \
        m9-artifact-check m9-sequence-check m9-pretraining-check \
        m9-v2-pretraining-check m9-diverse-roots-check m9-v3-pretraining-check \
        m9-policy-mode-diagnostic m9-entropy-check m9-v4-pretraining-check \
        m9-late-checkpoint-diagnostic m9-success-imitation-check \
        m9-v5-pretraining-check m9-v5-mode-margin-diagnostic \
        m9-success-margin-check m9-v6-pretraining-check \
        m9-expert-projection-diagnostic m9-candidate-native-planner-check \
        m9-candidate-native-planner-v2-check \
        m9-candidate-native-planner-v3-check \
        m9-candidate-native-planner-v4-check \
        m9-candidate-native-planner-v5-check \
        m9-candidate-native-planner-v6-check \
        m9-candidate-native-planner-v7-check \
        m9-candidate-native-planner-v8-check \
        m9-candidate-native-planner-v9-check \
        m9-candidate-native-planner-v10-check \
        m9-candidate-native-planner-v11-check \
        m9-baseline train-m9-ippo train-m9-ippo-v2 train-m9-ippo-v3 \
        train-m9-ippo-v4 train-m9-ippo-v5 train-m9-ippo-v6 \
        secondary-claim-wake-check \
        owned-schematic-staging-check coordination-parity \
        public-demo-parity \
        adaptive-planning-check \
        scenario-variation-check evaluate-ladder verify-rl-boundary \
        training-gate demo-server human-session-check human-absent-check

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
	@echo "  single-brain-failover-check V47 live death-only control transfer"
	@echo "  per-seat-history-check V48 live target-seat history-cache transfer"
	@echo "  m9-shared-policy-check M9 all-seat shared-model teacher parity"
	@echo "  m9-reward-check M9 per-seat reward adversary gate"
	@echo "  m9-rollout-check M9 stochastic all-seat rollout/reset gate"
	@echo "  m9-artifact-check M9 checkpoint/manifest exact replay gate"
	@echo "  m9-sequence-check M9 v2 recurrent optimizer determinism gate"
	@echo "  m9-pretraining-check complete M9 gate before replica A"
	@echo "  m9-v2-pretraining-check complete sequence-IPPO gate before replica A"
	@echo "  m9-baseline M9 public fixed-role shared-expert baseline"
	@echo "  train-m9-ippo exact M9 IPPO replicas + direct comparison"
	@echo "  train-m9-ippo-v2 governed sequence-IPPO construction"
	@echo "  train-m9-ippo-v3 governed diverse-root IPPO construction"
	@echo "  m9-policy-mode-diagnostic rejected-v3 stochastic/argmax diagnostic"
	@echo "  m9-entropy-check M9 v4 entropy-schedule inheritance check"
	@echo "  m9-v4-pretraining-check complete entropy-IPPO gate before replica A"
	@echo "  train-m9-ippo-v4 governed entropy-annealed IPPO construction"
	@echo "  m9-late-checkpoint-diagnostic rejected-v4 update-31/32 mode diagnostic"
	@echo "  m9-success-imitation-check M9 v5 inheritance/optimizer check"
	@echo "  m9-v5-pretraining-check complete success-imitation gate before A"
	@echo "  train-m9-ippo-v5 governed success-imitation IPPO construction"
	@echo "  m9-v5-mode-margin-diagnostic rejected-v5 public mode diagnostic"
	@echo "  m9-success-margin-check M9 v6 inheritance/optimizer check"
	@echo "  m9-v6-pretraining-check complete success-margin gate before A"
	@echo "  train-m9-ippo-v6 governed success-margin IPPO construction"
	@echo "  m9-expert-projection-diagnostic shared-expert candidate projection"
	@echo "  m9-candidate-native-planner-check governed ordinary-action planner gate"
	@echo "  m9-candidate-native-planner-v2-check serialized-schematic planner gate"
	@echo "  m9-candidate-native-planner-v3-check active-build planner gate"
	@echo "  m9-candidate-native-planner-v4-check active-build supply planner gate"
	@echo "  m9-candidate-native-planner-v5-check candidate-actionable supply gate"
	@echo "  m9-candidate-native-planner-v6-check completed-fortification gate"
	@echo "  m9-candidate-native-planner-v7-check active-fortification gate"
	@echo "  m9-candidate-native-planner-v8-check interwave-demobilization gate"
	@echo "  m9-candidate-native-planner-v9-check active-defend-cap gate"
	@echo "  m9-candidate-native-planner-v10-check wave-spawn-preemption gate"
	@echo "  m9-candidate-native-planner-v11-check single-defender gate"
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
	@echo "  human-session-check M10.3 capture/replay + M10.4 scorecard gate"
	@echo "  human-absent-check M10 paired human-only capture gate"

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

single-brain-failover-check: ## Verify V47's live death-only control transfer
	@bash $(SCRIPTS)/single-brain-failover-check.sh

per-seat-history-check: ## Verify V48's live per-seat history-cache transfer
	@bash $(SCRIPTS)/per-seat-history-check.sh

m9-shared-policy-check: ## Verify M9 all-seat shared-model teacher parity
	@bash $(SCRIPTS)/m9-shared-policy-check.sh

m9-expert-projection-diagnostic: ## Diagnose shared-expert candidate projection
	@bash $(SCRIPTS)/m9-expert-projection-diagnostic.sh

m9-candidate-native-planner-check: ## Validate candidate-native supervision source
	@bash $(SCRIPTS)/m9-candidate-native-planner-check.sh

m9-candidate-native-planner-v2-check: ## Validate build-serialized candidate planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v2-check.sh

m9-candidate-native-planner-v3-check: ## Validate active-build-aware candidate planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v3-check.sh

m9-candidate-native-planner-v4-check: ## Validate active-build supply planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v4-check.sh

m9-candidate-native-planner-v5-check: ## Validate candidate-actionable supply planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v5-check.sh

m9-candidate-native-planner-v6-check: ## Validate completed-fortification planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v6-check.sh

m9-candidate-native-planner-v7-check: ## Validate active-fortification planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v7-check.sh

m9-candidate-native-planner-v8-check: ## Validate interwave-demobilizing planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v8-check.sh

m9-candidate-native-planner-v9-check: ## Validate active-defend-capped planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v9-check.sh

m9-candidate-native-planner-v10-check: ## Validate wave-spawn preemption planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v10-check.sh

m9-candidate-native-planner-v11-check: ## Validate single-defender planner
	@bash $(SCRIPTS)/m9-candidate-native-planner-v11-check.sh

m9-reward-check: ## Verify M9 audited per-seat shaping adversaries
	@bash $(SCRIPTS)/m9-reward-check.sh

m9-rollout-check: ## Verify M9 stochastic all-seat rollout/reset
	@bash $(SCRIPTS)/m9-rollout-check.sh

m9-artifact-check: ## Verify M9 checkpoint and manifest replay lineage
	@bash $(SCRIPTS)/m9-artifact-check.sh

m9-sequence-check: ## Verify M9 v2 recurrent optimizer determinism
	@bash $(SCRIPTS)/m9-sequence-check.sh

m9-pretraining-check: ## Run the complete M9 pretraining gate
	@bash $(SCRIPTS)/m9-pretraining-check.sh

m9-v2-pretraining-check: ## Run the complete M9 v2 pretraining gate
	@bash $(SCRIPTS)/m9-v2-pretraining-check.sh

m9-baseline: ## Freeze M9 public fixed-role shared-expert evidence
	@bash $(SCRIPTS)/m9-baseline.sh

train-m9-ippo: ## Run exact M9 IPPO replicas and direct comparison
	@bash $(SCRIPTS)/train-m9-ippo.sh

train-m9-ippo-v2: ## Run governed M9 v2 sequence-IPPO construction
	@bash $(SCRIPTS)/train-m9-ippo-v2.sh

m9-diverse-roots-check: ## Verify M9 v3 public root membership and schedule
	@bash $(SCRIPTS)/m9-diverse-roots-check.sh

m9-v3-pretraining-check: ## Run all gates required before M9 v3 training
	@bash $(SCRIPTS)/m9-v3-pretraining-check.sh

train-m9-ippo-v3: ## Run governed M9 v3 diverse-root construction
	@bash $(SCRIPTS)/train-m9-ippo-v3.sh

m9-policy-mode-diagnostic: ## Diagnose rejected-v3 stochastic/argmax behavior
	@bash $(SCRIPTS)/m9-policy-mode-diagnostic.sh

m9-entropy-check: ## Verify M9 v4 inheritance and entropy schedule
	@bash $(SCRIPTS)/m9-entropy-check.sh

m9-v4-pretraining-check: ## Run all gates required before M9 v4 training
	@bash $(SCRIPTS)/m9-v4-pretraining-check.sh

train-m9-ippo-v4: ## Run governed M9 v4 entropy-annealed construction
	@bash $(SCRIPTS)/train-m9-ippo-v4.sh

m9-late-checkpoint-diagnostic: ## Diagnose rejected-v4 update-31/32 modes
	@bash $(SCRIPTS)/m9-late-checkpoint-diagnostic.sh

m9-success-imitation-check: ## Verify M9 v5 inheritance and optimizer
	@bash $(SCRIPTS)/m9-success-imitation-check.sh

m9-v5-pretraining-check: ## Run all gates required before M9 v5 training
	@bash $(SCRIPTS)/m9-v5-pretraining-check.sh

train-m9-ippo-v5: ## Run governed M9 v5 success-imitation construction
	@bash $(SCRIPTS)/train-m9-ippo-v5.sh

m9-v5-mode-margin-diagnostic: ## Diagnose rejected-v5 stochastic modes/margins
	@bash $(SCRIPTS)/m9-v5-mode-margin-diagnostic.sh

m9-success-margin-check: ## Verify M9 v6 inheritance and optimizer
	@bash $(SCRIPTS)/m9-success-margin-check.sh

m9-v6-pretraining-check: ## Run all gates required before M9 v6 training
	@bash $(SCRIPTS)/m9-v6-pretraining-check.sh

train-m9-ippo-v6: ## Run governed M9 v6 success-margin construction
	@bash $(SCRIPTS)/train-m9-ippo-v6.sh

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

human-absent-check: ## Validate the M10 zero-agent comparison condition
	@bash $(SCRIPTS)/human-absent-check.sh
