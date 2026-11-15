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
# Contract: tests/acc1/run_full.sh (Homer) fetches the pinned exerciser, runs it, writes
# logs/nightly/8080exm.log and exits 0 only on a full pass. Until it exists this is a no-op.
.PHONY: nightly
nightly:
	@mkdir -p logs/nightly
	@if [ -x tests/acc1/run_full.sh ]; then tests/acc1/run_full.sh 2>&1 | tee logs/nightly/run.log; exit $${PIPESTATUS[0]}; \
	else echo "nightly: tests/acc1/run_full.sh not there yet (Homer), nothing run" | tee logs/nightly/run.log; fi
