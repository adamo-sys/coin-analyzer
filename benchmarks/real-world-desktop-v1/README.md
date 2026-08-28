# Real-World Desktop Acceptance Set v1

This directory defines the authoring contract for a future paired-image,
real-world desktop acceptance set. It intentionally contains no manifest and no
images yet. Dataset assembly and recognition execution are separate, explicitly
authorized units of work.

`manifest.schema.json` documents the v1 foundation. Runtime loading additionally
checks safe relative paths, exact image-byte SHA-256 values, deterministic case
ordering, unique case IDs, image roles, privacy classifications, and reserved
attribution placeholders.

Every case reserves nullable `mint`, `mint_mark`, `variety`, and
`catalog_reference` fields. They remain `null` in this foundation unless a later
approved contract explicitly changes that rule.

Private or uncertain-local inputs remain local. This foundation validates local
metadata and frozen bytes only; it does not run recognition or authorize
provider execution.
