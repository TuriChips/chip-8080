# Copy to the chip repo root. Bump TOOLCHAIN_REF on purpose, never track main.
TOOLCHAIN_REF ?= v0.9
TC := .toolchain
ifeq (,$(wildcard $(TC)/chip.mk))
$(shell rm -rf $(TC); gh repo clone TuriChips/toolchain $(TC) -- -q --depth 1 --branch $(TOOLCHAIN_REF))
endif
# Pin check lives here, in the chip repo, so it also catches a stale .toolchain from before v0.4
# (whose chip.mk has no check). `make TOOLCHAIN_REF=` turns it off.
ifneq (,$(TOOLCHAIN_REF))
ifeq (,$(filter $(TOOLCHAIN_REF),$(shell git -C $(TC) tag --points-at HEAD 2>/dev/null)))
$(error toolchain mismatch: Makefile pins $(TOOLCHAIN_REF) but $(TC) is a different version. Run: rm -rf $(TC))
endif
endif
include $(TC)/chip.mk

# Nightly: the full 8080EXM on Verilator (too long for every PR, spec section 9).
# scripts/exm/run_full_fast.sh (Homer) fetches the pinned exerciser, runs it, writes
# logs/nightly/8080exm.log; exit 0 = full pass, 2 = not run, anything else = fail.
# bash + pipefail so the script's exit code survives `| tee` (make's /bin/sh is dash).
.PHONY: nightly
nightly: SHELL := /bin/bash
nightly: .SHELLFLAGS := -o pipefail -c
nightly:
	@mkdir -p logs/nightly
	@if [ -x scripts/exm/run_full_fast.sh ]; then scripts/exm/run_full_fast.sh 2>&1 | tee logs/nightly/run.log; \
	else echo "nightly: scripts/exm/run_full_fast.sh is missing" | tee logs/nightly/run.log; exit 1; fi
