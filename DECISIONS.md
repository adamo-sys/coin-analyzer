# Coin Analyzer Decisions

## D001 — Stable IDs

**Decision:** GUI row position is presentation state only. Stable item ID is authoritative.

**Status:** Accepted

## D002 — Ground Truth

**Decision:** Ground truth is authored independently before model execution.

**Status:** Accepted

## D003 — Sparse Records

**Decision:** `PARTIAL` and `UNIDENTIFIED` are legitimate states and must not be filled with inferred identity.

**Status:** Accepted

## D004 — Evaluation Evidence

**Decision:** Authored expected results and actual execution results remain separate artifacts.

**Status:** Accepted

## D005 — Smallest Correct Patch

**Decision:** Implementation work should prefer the smallest correct patch that satisfies acceptance criteria and existing contracts.

**Status:** Accepted

## D006 — Completion Evidence

**Decision:** A unit is not complete merely because code exists. Completion requires applicable tests and evidence, with claims labeled VERIFIED, INFERRED, or UNVERIFIED.

**Status:** Accepted

## Decision Rule

Do not reopen an accepted decision unless new implementation evidence demonstrates a real contradiction, defect, or blocked requirement. Record any replacement decision explicitly rather than silently changing architecture.
