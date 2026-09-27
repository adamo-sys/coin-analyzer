# E7 v2 CA-R30-023 query-vocabulary investigation

CA-R30-023 remains `REVIEW_REQUIRED` after the canonical 24/6 metadata audit because the current frozen query (`West Germany 2 Deutsche Mark 1976`) returned zero candidates.

This is intentionally **not** treated as a normalization success. Candidate discovery must produce catalogue metadata before exact identity and design-reference gates can operate.

Safe follow-up: test bounded alternate search vocabulary derived from established issuer/denomination terminology, record every returned candidate and its catalogue references, and retain `REVIEW_REQUIRED` unless the ordinary issuer/value/year gate and any frozen design evidence independently pass. Do not hard-code a Numista type ID and do not bypass candidate discovery.

No image acquisition, model inference, benchmark-truth mutation, or execution is authorized by this note.
