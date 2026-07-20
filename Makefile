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

.PHONY: help bootstrap build test test-java test-python smoke determinism \
        stress-reset benchmark scripted-demo evaluate-scripted demo-server

help: ## List available targets
	@echo "mindustry-coop-agents — make targets:"
	@echo "  bootstrap     verify toolchain versions and print them"
	@echo "  build         build Java modules + Python package"
	@echo "  test          all fast tests (Java + Python)"
	@echo "  test-java     JUnit tests"
	@echo "  test-python   python -m pytest python/tests -q"
	@echo "  smoke         one reset/step/close (M1)"
	@echo "  determinism   golden replay / hash check (M1)"
	@echo "  stress-reset  repeated in-memory reset test (M2)"
	@echo "  benchmark     scaling + timing report (M2)"
	@echo "  scripted-demo headless scripted team (M6)"
	@echo "  evaluate-scripted five-seed episode summaries (M6)"
	@echo "  demo-server   human-joinable real-time server (M6/M10)"

bootstrap: ## Verify/print toolchain versions (works today)
	@bash $(SCRIPTS)/bootstrap.sh

build: ## Build Java modules + Python package
	@bash $(SCRIPTS)/build.sh

test: test-python ## All fast tests (Java pending harness wiring)
	@echo "test: Python tests passed; Java test harness pending (see docs/ROADMAP.md#milestone-0)"

test-java: ## JUnit tests (pending)
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

scripted-demo: ## Headless scripted team (M6)
	@bash $(SCRIPTS)/scripted-demo.sh

evaluate-scripted: ## Evaluate the scripted M6 expert
	@bash $(SCRIPTS)/evaluate-scripted.sh

demo-server: ## Human-joinable real-time server (M6/M10)
	@bash $(SCRIPTS)/demo-server.sh
