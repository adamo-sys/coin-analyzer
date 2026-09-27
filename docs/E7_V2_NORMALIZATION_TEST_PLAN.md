# E7 v2 bounded-normalization validation plan

Before merge, CI must run the focused gallery-audit test module. After merge, the owner-run Numista metadata audit against canonical `C:\Projects\recognition30_v2` remains the authoritative live check because CI has no Numista API key or local benchmark dataset.

Expected behavior from this slice:

- CA-R30-020 may become auto-resolvable if the live candidate remains uniquely compatible after bounded issuer/value normalization.
- CA-R30-022 may become auto-resolvable if the live candidate remains uniquely compatible after bounded denomination normalization.
- CA-R30-028 must remain review-required unless its frozen KM#21a.1 reference is actually present on a nominally matching live candidate.
- CA-R30-007 and CA-R30-009 must remain review-required.
- CA-R30-023 remains separately unresolved pending query-vocabulary evidence.

No target resolved-count is used as a success criterion; gate behavior and evidence are authoritative.
