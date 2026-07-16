# Project Philosophy

Coin Analyzer is local-first, collector-controlled software for organizing evidence and making explainable collecting decisions.

## Principles

### Collector value before complexity

Build only when a real collector problem or verified engineering risk justifies the maintenance cost. Prefer removing friction to adding surface area. Do not introduce a new engine, persistence format, dependency, or abstraction without clear ownership and user value.

### Local-first and user-controlled

Core collection workflows work without cloud services. Personal collection data remains local unless the collector deliberately exports it. Analysis may advise; collection mutations require an explicit user action.

### Evidence and explainability

Recommendations expose their inputs, reasons, limits, and missing evidence. Deterministic behavior is preferred where it can solve the problem. Uncertainty is reported rather than hidden.

### Regression-first development

Inspect existing behavior before changing it. Add focused tests for the new contract and run the complete suite before completion. A falling test count or changed behavior requires an explanation.

### Backward compatibility

Existing collection files, imports, exports, and public workflows should continue to work unless a reviewed decision explicitly authorizes a breaking change. Optional data stays optional, and migrations must preserve user data.

### Small, focused changes

One commit should tell one coherent story. Keep unrelated worktree changes untouched. Separate feature work, cleanup, documentation, and migrations when they carry different risks.

### AI assistance with human review

AI may inspect, propose, implement, and test changes. A human approves scope, material architectural choices, destructive actions, and publication. Generated work receives the same review and verification as human-written work.

### Architecture should become easier to maintain

Reuse existing models and engines before creating parallel concepts. Business rules belong in backend modules; interfaces collect input and present results. Prefer plain, replaceable components over speculative frameworks.

## Definition of Done

A change is done when:

- its acceptance criteria are met;
- relevant edge cases and regressions are tested;
- the complete test suite passes;
- persistence and backward compatibility have been considered;
- user-facing or architectural behavior is documented where necessary;
- the diff contains no unrelated changes or formatting errors;
- manual checks are completed when automated tests cannot cover the behavior;
- the resulting commit is focused and reviewable.

Product direction is described in [`../PRODUCT_PRINCIPLES.md`](../PRODUCT_PRINCIPLES.md) and [`../VISION.md`](../VISION.md). Working practices are defined in [`ENGINEERING_PLAYBOOK.md`](ENGINEERING_PLAYBOOK.md).
