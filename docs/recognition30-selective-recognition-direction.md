# Recognition30 Selective Recognition and Evidence Sufficiency Direction

Status: **QUEUED / DIRECTION LOCKED**  
Date: 2026-09-26

## Decision

Coin Analyzer will evaluate recognition quality as a selective-decision problem, not only as raw top-1 accuracy or a single opaque confidence number.

The canonical Recognition30 v1 dataset remains frozen. Any uncertainty, abstention, or evidence-degradation work must be derived from Recognition30 without mutating its canonical identity, ground truth, specimen set, or benchmark fingerprint.

The intended routing vocabulary is:

- `AUTO_ACCEPT`
- `REVIEW`
- `ABSTAIN`

The primary operational metrics are:

- error rate among auto-accepted specimens;
- coverage / auto-accept rate;
- review burden;
- abstention rate; and
- catastrophic false-auto-accept count.

## Confidence semantics

Coin Analyzer should avoid treating one model-supplied number as authoritative probability confidence.

Where supported by defensible evidence, future evaluation may separate:

- visual evidence sufficiency;
- candidate / retrieval agreement;
- field-specific evidence such as date or denomination;
- cross-side agreement; and
- downstream reasoning or decision confidence.

These signals are advisory inputs to routing. They do not own persistence, collection mutation, or final collector decisions.

## Derived evidence-degradation suite

A small derived benchmark may be created from selected Recognition30 specimens using controlled variants such as crop, blur, glare, contrast loss, obscured date, or partial evidence.

This suite must remain separate from canonical Recognition30 v1.

Its purpose is to test whether routing becomes more conservative as useful evidence is removed, including whether the system appropriately moves from `AUTO_ACCEPT` to `REVIEW` or `ABSTAIN`.

## Recognition architecture direction

The preferred recognition direction remains:

`phone capture -> specialized visual evidence / retrieval -> candidate generation -> VLM reasoning or fusion -> calibrated routing / abstention -> human confirmation -> authoritative save`

This direction is intentionally preferred over a VLM-only `photo -> answer` architecture.

Planned retrieval work, including Coin-CLIP/reference-corpus/two-sided retrieval and fusion, remains a primary recognition path to evaluate.

When that retrieval path is ready, run a bounded comparison on the same frozen Recognition30 specimens:

- A: current VLM-centered baseline;
- B: retrieval / specialized visual candidate generation;
- C: retrieval + VLM evidence fusion.

The experiment must measure whether added complexity produces a real gain.

## Research intake rule

Future research findings must answer:

> What existing Coin Analyzer decision does this evidence change?

If the answer is `none`, keep the result as reference material rather than changing the roadmap.

Research should be classified as:

- **TEST NEXT** — strong enough to justify the smallest bounded experiment;
- **WATCH** — relevant but not sufficient to alter current sequencing;
- **NO ACTION** — interesting but not decision-relevant.

Novelty alone is not sufficient reason to adopt a framework, model, dependency, or architecture.

## Explicit non-decisions

This direction does **not** authorize:

- mutation of Recognition30 v1;
- production auto-save from model confidence;
- heavyweight RL/VL-calibration training machinery;
- replacement of human confirmation;
- broad architecture rewrites;
- new external dependencies merely because a paper or benchmark is new.

Any implementation still requires its own bounded task contract and applicable review/validation.
